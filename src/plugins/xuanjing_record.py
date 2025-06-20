# 玄晶榜单记录插件
from nonebot import on_regex, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message
from .database import TeamRecordDB
from src.utils.html_generator import render_xuanjing_html
from src.utils.render_context import render_and_cleanup
from ..utils.index import path_to_base64
from ..utils.permission import require_admin_permission
import os
import re
from datetime import datetime
from typing import List, Dict, Any

# 初始化数据库
db = TeamRecordDB()
db.init_db()  # 确保数据库表已创建

# 玄晶榜单相关命令
xuanjing_template = on_regex(pattern=r'^玄晶模板$', priority=1)
xuanjing_add = on_regex(pattern=r'^玄晶录入\s+([\s\S]+)$', priority=1)
xuanjing_list = on_regex(pattern=r'^玄晶榜(?:\s+(.+))?$', priority=1)
delete_xuanjing = on_regex(pattern=r'^删除玄晶\s+(\d+)$', priority=1)

@xuanjing_template.handle()
async def handle_xuanjing_template(bot: Bot, event: GroupMessageEvent, state: T_State):
    """获取玄晶录入模板"""
    template = """玄晶录入模板：

使用方法：
玄晶录入 日期：2025-01-20
参与人员：余年,小明,小红
价格：1500j
备注：25英雄太极宫玄晶

注意：
- 价格单位：1z = 10000j，可以用z或j作单位
- 每个字段占一行，格式为：字段名：内容
- 日期格式：YYYY-MM-DD
- 参与人员用逗号分隔
- 必填字段：日期、参与人员、价格"""
    
    await xuanjing_template.finish(template)

@xuanjing_add.handle()
async def handle_xuanjing_add(bot: Bot, event: GroupMessageEvent, state: T_State):
    """录入玄晶信息"""
    # 使用正则表达式直接匹配消息内容
    pattern = r'^玄晶录入\s+([\s\S]+)$'
    match = re.match(pattern, event.get_plaintext())
    
    if not match:
        await xuanjing_add.finish("格式错误，请使用正确格式，发送'玄晶模板'查看模板")
        return
    
    content = match.group(1)

    user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(event.user_id))
    
    try:
        # 解析录入内容
        data = parse_xuanjing_template(content)
        data['group_id'] = str(event.group_id)
        data['user_id'] = str(event.user_id)
        data['user_name'] = user_info['nickname']
        data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 转换价格单位为j
        data['price_j'] = convert_wage_to_j(data['price_display'])
        print('录入玄晶信息----', data)
        # 存入数据库
        record_id = db.insert('xuanjing_records', data)
        
    except Exception as e:
        print('录入玄晶信息失败----', e)
        await xuanjing_add.finish(f"录入失败：{str(e)}\n\n请使用正确格式，发送'玄晶模板'查看模板")
        return

    await xuanjing_add.finish(f"玄晶信息录入成功！\n记录ID：{record_id}\n参与人员：{data['participants']}\n价格：{data['price_display']}")

@xuanjing_list.handle()
async def handle_xuanjing_list(bot: Bot, event: GroupMessageEvent, state: T_State):
    """查看玄晶榜单"""
    # 使用正则表达式匹配消息内容
    pattern = r'^玄晶榜(?:\s+(.+))?$'
    match = re.match(pattern, event.get_plaintext())
    
    if not match:
        await xuanjing_list.finish("命令格式不正确，请使用：玄晶榜 [参与人员]")
    
    # 解析参数
    args_str = match.group(1)
    participant = None
    
    if args_str:
        participant = args_str.strip()
    
    try:
        # 发送处理提示
        processing_msg = await bot.send(event=event, message="正在生成玄晶榜单，请稍候...")
        
        # 获取当前群组的玄晶记录
        records = await get_group_xuanjing(str(event.group_id), participant)
        
        if not records:
            await xuanjing_list.send("暂无玄晶记录")
            return
        
        # 生成HTML
        html_content = render_xuanjing_html(records)
        
        # 转换为图片
        image_path = await render_and_cleanup(html_content, 1200)
        
    except Exception as e:
        await xuanjing_list.finish(f"生成榜单失败：{str(e)}")

    try:
        # 发送图片
        await xuanjing_list.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

@delete_xuanjing.handle()
async def handle_delete_xuanjing(bot: Bot, event: GroupMessageEvent, state: T_State):
    """删除特定玄晶记录"""
    matched = state["_matched"]
    # 提取记录ID
    record_id = matched.group(1)
    print('删除玄晶记录----', record_id)
    
    try:
        record = db.fetch_one('xuanjing_records', f"id = ? AND group_id = ?", (record_id, event.group_id))
        
        if not record:
            await delete_xuanjing.send(f"未找到记录ID为 {record_id} 的玄晶记录")
            return
        
        user_id = record['user_id']

        # 检查操作者是否为记录的创建人或群管理员
        if event.user_id != user_id and not require_admin_permission(bot, event.group_id, event.user_id, delete_xuanjing):
            await delete_xuanjing.send("你没有权限删除这条记录！")
            return
        
        # 删除记录
        affected_rows = db.delete("xuanjing_records", "id = ? AND group_id = ?", (record_id, event.group_id))
        print('删除玄晶记录----', affected_rows)
        if affected_rows > 0:
            await delete_xuanjing.send(f"成功删除记录ID为 {record_id} 的玄晶记录")
        else:
            await delete_xuanjing.send(f"未找到记录ID为 {record_id} 的玄晶记录")
    except Exception as e:
        await delete_xuanjing.finish(f"删除失败：{str(e)}")

# 解析玄晶模板内容
def parse_xuanjing_template(content):
    """解析玄晶模板内容并提取数据"""
    pattern = re.compile(
        r"日期：(?P<date>\d{4}-\d{2}-\d{2})\n"
        r"参与人员：(?P<participants>.+?)\n"
        r"价格：(?P<price_display>.+?)\n"
        r"备注：(?P<remark>.+)"
    )
    match = pattern.search(content)
    if match:
        return match.groupdict()
    else:
        raise ValueError("模板内容格式不正确")

# 将价格单位转换为j
def convert_wage_to_j(wage):
    """将价格单位转换为j"""
    # 匹配价格中的数字和单位
    pattern = re.compile(r"(\d+)([zj])?")
    matches = pattern.findall(wage)
    total_j = 0

    for match in matches:
        amount, unit = match
        amount = int(amount)
        if unit == 'z':
            total_j += amount * 10000
        elif unit == 'j':
            total_j += amount
        else:  # 默认单位是j
            total_j += amount

    return total_j

async def get_group_xuanjing(group_id: str, participant: str = None, limit: int = 1000):
    # 构造查询条件
    condition = f"group_id = {group_id}"
    
    if participant is not None:
        condition += f" AND participants LIKE '%{participant}%'"
    
    condition += f" ORDER BY date DESC LIMIT {limit}"
    
    # 查询玄晶记录
    records = db.fetch_all('xuanjing_records', condition)

    # 将结果转换为字典列表
    return records