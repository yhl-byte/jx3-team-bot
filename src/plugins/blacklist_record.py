'''
Date: 2025-01-20 00:00:00
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-17 10:12:23
FilePath: /team-bot/jx3-team-bot/src/plugins/blacklist_record.py
'''
# 黑本榜单记录插件
from nonebot import on_regex, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message
from .database import TeamRecordDB
from .html_generator import render_blacklist_html
from .render_image import generate_html_screenshot
from ..utils.index import path_to_base64
from ..utils.permission import require_admin_permission
import os
import re
from datetime import datetime
from typing import List, Dict, Any

# 初始化数据库
db = TeamRecordDB()
db.init_db()  # 确保数据库表已创建

# 黑本榜单相关命令
blacklist_template = on_regex(pattern=r'^黑本模板$', priority=1)
blacklist_add = on_regex(pattern=r'^黑本录入\s+([\s\S]+)$', priority=1)
blacklist_list = on_regex(pattern=r'^黑本榜(?:\s+(.+))?$', priority=1)
delete_blacklist = on_regex(pattern=r'^删除黑本\s+(\d+)$', priority=1)

@blacklist_template.handle()
async def handle_blacklist_template(bot: Bot, event: GroupMessageEvent, state: T_State):
    """获取黑本录入模板"""
    template = """黑本录入模板：

使用方法：
黑本录入 日期：2025-01-20
游戏ID：余年
副本：25英雄太极宫
关键掉落：玄晶
工资：500z
备注：拿了装备就跑路

注意：
- 工资单位：1z = 10000j，可以用z或j作单位
- 每个字段占一行，格式为：字段名：内容
- 日期格式：YYYY-MM-DD
- 必填字段：日期、游戏ID、副本、工资"""
    
    await blacklist_template.finish(template)

@blacklist_add.handle()
async def handle_blacklist_add(bot: Bot, event: GroupMessageEvent, state: T_State):
    """录入黑本信息"""
    # 使用正则表达式直接匹配消息内容
    pattern = r'^黑本录入\s+([\s\S]+)$'
    match = re.match(pattern, event.get_plaintext())
    
    if not match:
        await blacklist_add.finish("格式错误，请使用正确格式，发送'黑本模板'查看模板")
        return
    
    content = match.group(1)

    user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(event.user_id))
    
    try:
        # 解析录入内容
        data = parse_template(content)
        data['group_id'] = str(event.group_id)
        data['user_id'] = str(event.user_id)
        data['user_name'] = user_info['nickname']
        data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 转换工资单位为j
        data['salary_j'] = convert_wage_to_j(data['salary_display'])
        print('录入黑本信息----', data)
        # 存入数据库
        record_id = db.insert('blacklist_records', data)
        
    except Exception as e:
        print('录入黑本信息失败----', e)
        await blacklist_add.finish(f"录入失败：{str(e)}\n\n请使用正确格式，发送'黑本模板'查看模板")

    await blacklist_add.finish(f"黑本信息录入成功！\n记录ID：{record_id}\n游戏ID：{data['role_name']}\n副本：{data['dungeon_name']}\n工资：{data['salary_display']}")



def is_dungeon_name(text: str) -> bool:
    """判断文本是否为副本名称"""
    # 常见副本关键词
    dungeon_keywords = [
        '英雄', '普通', '太极宫', '一直哭', '一之窟', 'yx', 'pt',
    ]
    
    # 如果包含副本关键词，认为是副本名
    for keyword in dungeon_keywords:
        if keyword in text:
            return True
    
    # 如果文本较长（超过6个字符），可能是副本名
    if len(text) > 6:
        return True
    
    return False

@blacklist_list.handle()
async def handle_blacklist_list(bot: Bot, event: GroupMessageEvent, state: T_State):
    """查看黑本榜单"""
    # 使用正则表达式匹配消息内容
    pattern = r'^黑本榜(?:\s+(.+))?$'
    match = re.match(pattern, event.get_plaintext())
    
    if not match:
        await blacklist_list.finish("命令格式不正确，请使用：黑本榜 [游戏ID/副本] [副本/游戏ID]")
    
    # 解析参数
    args_str = match.group(1)
    game_id = None
    dungeon_name = None
    
    if args_str:
        # 分割参数
        args = args_str.strip().split()
        
        if len(args) == 1:
            # 只有一个参数，需要判断是游戏ID还是副本名
            arg = args[0]
            if is_dungeon_name(arg):  # 判断是否为副本名
                dungeon_name = arg
            else:
                game_id = arg
        elif len(args) == 2:
            # 两个参数，需要判断哪个是游戏ID，哪个是副本名
            arg1, arg2 = args[0], args[1]
            
            # 判断参数类型
            if is_dungeon_name(arg1) and not is_dungeon_name(arg2):
                # 第一个是副本名，第二个是游戏ID
                dungeon_name = arg1
                game_id = arg2
            elif not is_dungeon_name(arg1) and is_dungeon_name(arg2):
                # 第一个是游戏ID，第二个是副本名
                game_id = arg1
                dungeon_name = arg2
            else:
                # 无法明确判断，按顺序处理：第一个游戏ID，第二个副本名
                game_id = arg1
                dungeon_name = arg2
        else:
            await blacklist_list.finish("参数过多，请使用：黑本榜 [游戏ID/副本] [副本/游戏ID]")

    try:
        # 发送处理提示
        processing_msg = await bot.send(event=event, message="正在生成黑本榜单，请稍候...")
        
        # 获取当前群组的黑本记录
        records = await get_group_blacklist(str(event.group_id), game_id, dungeon_name)
        
        if not records:
            await blacklist_list.send("暂无黑本记录")
            return
        
        # 生成HTML
        html_content = render_blacklist_html(records)
        
        # 转换为图片
        image_path = await generate_html_screenshot(html_content, 1200)
        
    except Exception as e:
        await blacklist_list.finish(f"生成榜单失败：{str(e)}")

    # 发送图片
    await blacklist_list.finish(MessageSegment.image(path_to_base64(image_path)))
    
    # 清理临时文件
    os.unlink(image_path)




@delete_blacklist.handle()
async def handle_delete_blacklist(bot: Bot, event: GroupMessageEvent, state: T_State):
    """删除特定黑本记录"""
    matched = state["_matched"]
    # 提取记录ID
    record_id = matched.group(1)
    print('删除黑本记录----', record_id)
    
    try:
        record = db.fetch_one('blacklist_records', f"id = ? AND group_id = ?", (record_id, event.group_id))
        
        if not record:
            await delete_blacklist.send(f"未找到记录ID为 {record_id} 的黑本记录")
            return
        
        user_id = record['user_id']

        # 检查操作者是否为记录的创建人或群管理员
        if event.user_id != user_id and not require_admin_permission(bot, event.group_id, event.user_id, delete_blacklist):
            await delete_blacklist.send("你没有权限删除这条记录！")
            return
        
        
        # 删除记录
        affected_rows = db.delete("blacklist_records", "id = ? AND group_id = ?", (record_id, event.group_id))
        print('删除黑本记录----', affected_rows)
        if affected_rows > 0:
            await delete_blacklist.send(f"成功删除记录ID为 {record_id} 的黑本记录")
        else:
            await delete_blacklist.send(f"未找到记录ID为 {record_id} 的黑本记录")
    except Exception as e:
        await delete_blacklist.finish(f"删除失败：{str(e)}")


# 解析模板内容
def parse_template(content):
    """解析模板内容并提取数据"""
    pattern = re.compile(
        r"日期：(?P<date>\d{4}-\d{2}-\d{2})\n"
        r"游戏ID：(?P<role_name>.+?)\n"
        r"副本：(?P<dungeon_name>.+?)\n"
        r"关键掉落：(?P<key_drop>.+?)\n"
        r"工资：(?P<salary_display>.+?)\n"
        r"备注：(?P<remark>.+)"
    )
    match = pattern.search(content)
    if match:
        return match.groupdict()
    else:
        raise ValueError("模板内容格式不正确")

# 将工资单位转换为j
def convert_wage_to_j(wage):
    """将工资单位转换为j"""
    # 匹配工资中的数字和单位
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


async def get_group_blacklist(group_id: str,  game_id: str = None, dungeon_name: str = None, limit: int = 1000):
    # 构造查询条件
    condition = f"group_id = {group_id}"
    
    if game_id is not None:
        condition += f" AND role_name = '{game_id}'"

    if dungeon_name is not None:
        condition += f" AND dungeon_name LIKE '%{dungeon_name}%'"
    
    condition += f" ORDER BY salary_j DESC LIMIT {limit}"
    
    # 查询团队中的全部成员
    records = db.fetch_all('blacklist_records', condition)

    # 将结果转换为字典列表
    return records

