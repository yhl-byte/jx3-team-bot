'''
Date: 2024-03-17
Description: 剑网3 API 插件
'''
import token
import asyncio
from datetime import datetime
from warnings import catch_warnings
from nonebot import on_regex, require, get_driver
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent,MessageSegment, GroupMessageEvent, Bot, Message
import aiohttp
import json
from typing import Dict, List, Optional
from jx3api import JX3API,AsyncJX3API
from ..utils.index import format_daily_data,format_role_data,path_to_base64,render_team_template,darken_color
from src.utils.html_generator import render_role_attribute,img_to_base64,render_role_cd_record,render_role_luck,render_sandbox_html,render_trade_records_html,render_role_achievement_html,render_diary_achievement_html,render_member_recruit_html,render_auction_html,render_black_book_html,render_baizhan_html,render_gold_price_html,render_mountain_pass_html,render_daily_prediction_html
from src.utils.render_context import render_and_cleanup
from ..utils.permission import require_admin_permission
from jx3api.exception import APIError  # 添加导入
import os
from .database import NianZaiDB  # 添加数据库导入
from src.config import STATIC_PATH,JX3_AUTHORIZATION, JX3_COOKIES, JX3_TOKEN, JX3_TICKET


# 使用配置文件中的变量
AUTHORIZATION = JX3_AUTHORIZATION
COOKIES = JX3_COOKIES
token = JX3_TOKEN
ticket = JX3_TICKET
base_url = 'https://www.jx3api.com'
async_api = AsyncJX3API(token = token, ticket=ticket, base_url = base_url)
api = JX3API(token = token, ticket=ticket, base_url = base_url)
default_server = '唯我独尊'

async def get_group_default_server(bot: Bot, event: GroupMessageEvent) -> Optional[str]:
    """
    获取群组默认服务器的公共方法
    如果未设置则提示用户进行服务器绑定
    
    Args:
        bot: Bot实例
        event: 群消息事件
        
    Returns:
        str: 服务器名称，如果未设置则返回None
    """
    group_id = str(event.group_id)
    group_config = db.get_group_config(group_id)
    
    if group_config and group_config.get('default_server'):
        return group_config.get('default_server')
    else:
        # 提示用户进行服务器绑定
        await bot.send(event, "❌ 未设置默认服务器，请使用 绑定服务器 [服务器名称] 命令进行服务器绑定")
        return None

# 导入定时任务模块
scheduler = require("nonebot_plugin_apscheduler").scheduler

# 全局变量存储上次获取的沙盘记录
last_sandbox_data = {}

# 初始化数据库
db = NianZaiDB()
db.init_db()

# 插件名称
PLUGIN_NAME = "jx3_api"

# 状态检查装饰器
def check_plugin_enabled(func):
    """检查插件是否启用的装饰器"""
    async def wrapper(bot: Bot, event: GroupMessageEvent, state: T_State):
        group_id = event.group_id
        enabled = db.get_plugin_status("jx3_api", group_id)
        
        if not enabled:
            # await bot.send(event=event, message="剑三助手功能已关闭，请联系管理员开启")
            return
        
        return await func(bot, event, state)
    return wrapper

# 插件开关控制命令
JX3PluginControl = on_regex(pattern=r'^剑三助手\s*(开启|关闭|状态)$', priority=1)
@JX3PluginControl.handle()
async def handle_plugin_control(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, JX3PluginControl):
        return
    
    matched = state["_matched"]
    if matched:
        action = matched.group(1)  # "开启"、"关闭" 或 "状态"
        group_id = event.group_id
        
        if action == "开启":
            success = db.set_plugin_status("jx3_api", group_id, True)
            if success:
                msg = "剑三助手功能已开启"
            else:
                msg = "开启剑三助手功能失败，请稍后重试"
        elif action == "关闭":
            success = db.set_plugin_status("jx3_api", group_id, False)
            if success:
                msg = "剑三助手功能已关闭"
            else:
                msg = "关闭剑三助手功能失败，请稍后重试"
        else:  # 状态
            enabled = db.get_plugin_status("jx3_api", group_id)
            status = "开启" if enabled else "关闭"
            msg = f"当前剑三助手功能状态：{status}"
        
        await JX3PluginControl.finish(message=Message(msg))


# 开服检测
OpenServer = on_regex(pattern=r'^(开服|倒闭了)(?:\s+(\S+))?$', priority=1)
@OpenServer.handle()
@check_plugin_enabled
async def handle_server_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    if state['_matched'].group(2):
        server_name = state['_matched'].group(2)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    res = api.server_check(server= server_name)
    print(res)
    msg = f"{server_name} {'开服了' if res['status'] == 1 else '维护中'}"
    await OpenServer.finish(message=Message(msg))

# 公告
NoticeNew = on_regex(pattern=r'^公告$', priority=1)
@NoticeNew.handle()
@check_plugin_enabled
async def handle_notice_new(bot: Bot, event: GroupMessageEvent, state: T_State):
    try:
        res = await async_api.request(endpoint="/data/news/announce", limit=1)
    except APIError as e:
        # 专门处理 API 错误
        print(f"NoticeNew API错误: code={e.code}, msg={e.msg}")
        await NoticeNew.finish(message=f"公告查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"NoticeNew 其他错误: {type(e).__name__}: {str(e)}")
        await NoticeNew.finish(message=f"公告接口调用失败: {str(e)}")
        return
    print('公告------',res)
    # 检查返回数据是否为空
    if not res or len(res) == 0:
        await NoticeNew.finish(message="暂无最新公告")
        return
    
    # 获取最新公告信息
    latest_notice = res[0]
    # 组织返回消息
    msg = f"📢 最新公告\n" \
          f"标题：{latest_notice['title']}\n" \
          f"分类：{latest_notice['class']}\n" \
          f"日期：{latest_notice['date']}\n" \
          f"详情：{latest_notice['url']}"
    await NoticeNew.finish(message=Message(msg))

# 资讯
NewsAll = on_regex(pattern=r'^资讯(?:\s+(\d+))?$', priority=1)
@NewsAll.handle()
@check_plugin_enabled
async def handle_news_all(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 获取用户输入的数量参数
    limit_str = state['_matched'].group(1) if state['_matched'].group(1) else None
    
    # 设置默认值和范围限制
    if limit_str:
        try:
            limit = int(limit_str)
            # 限制范围在1-50之间
            if limit < 1:
                limit = 1
            elif limit > 50:
                limit = 50
        except ValueError:
            limit = 3  # 如果转换失败，使用默认值
    else:
        limit = 3  # 默认值
    
    try:
        res = await async_api.request(endpoint="/data/news/allnews", limit=limit)
    except APIError as e:
        # 专门处理 API 错误
        print(f"NewsAll API错误: code={e.code}, msg={e.msg}")
        await NewsAll.finish(message=f"资讯查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"NewsAll 其他错误: {type(e).__name__}: {str(e)}")
        await NewsAll.finish(message=f"资讯接口调用失败: {str(e)}")
        return
    print('资讯------',res)
    # 检查返回数据是否为空
    if not res or len(res) == 0:
        await NewsAll.finish(message="暂无最新资讯")
        return
    
    # 组织资讯消息
    msg_parts = [f"📰 最新资讯（最新{limit}条）："]
    
    for news in res:
        title = news.get('title', '未知标题')
        date = news.get('date', '未知日期')
        class_name = news.get('class', '未知分类')
        url = news.get('url', '').strip(' `')
        
        msg_parts.append(f"\n🔸 {title}")
        msg_parts.append(f"   📅 日期：{date}")
        msg_parts.append(f"   🏷️ 分类：{class_name}")
        if url:
            msg_parts.append(f"   🔗 详情链接：{url}")
    
    message = '\n'.join(msg_parts)
    await NewsAll.finish(message=Message(message))

# 技改
TechUpgrade = on_regex(pattern=r'^技改$', priority=1)
@TechUpgrade.handle()
@check_plugin_enabled
async def handle_tech_upgrade(bot: Bot, event: GroupMessageEvent, state: T_State):
    try:
        res = await async_api.request(endpoint="/data/skills/records")
    except APIError as e:
        # 专门处理 API 错误
        print(f"TechUpgrade API错误: code={e.code}, msg={e.msg}")
        await TechUpgrade.finish(message=f"技改查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"TechUpgrade 其他错误: {type(e).__name__}: {str(e)}")
        await TechUpgrade.finish(message=f"技改接口调用失败: {str(e)}")
        return
    print('技改------',res)
    # 检查返回数据是否为空
    if res:
        # 只取最新5条记录
        latest_records = res[:3]
        # 组织技改公告消息
        msg_parts = ["📋 最新技改公告："]
        
        for announcement in latest_records:
            title = announcement.get('title', '未知标题')
            time = announcement.get('time', '未知时间')
            url = announcement.get('url', '').strip(' `')
            
            msg_parts.append(f"\n🔸 {title}")
            msg_parts.append(f"   📅 发布时间：{time}")
            if url:
                msg_parts.append(f"   🔗 详情链接：{url}")
        
        message = '\n'.join(msg_parts)
        await TechUpgrade.finish(message=message)
    else:
        await TechUpgrade.finish(message="暂无技改公告信息")

# 查看日常
CheckDaily = on_regex(pattern=r'^日常(?:\s+(\S+))?$', priority=1)
@CheckDaily.handle()
@check_plugin_enabled
async def handle_daily(bot: Bot, event: GroupMessageEvent, state: T_State):
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    res = api.active_calendar(server= server_name)
    msg = f"{server_name} {format_daily_data(res)}"
    await CheckDaily.finish(message=Message(msg))

# 角色信息
RoleDetail = on_regex(pattern=r'^角色\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleDetail.handle()
@check_plugin_enabled
async def handle_role_detail(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名
    role_name = matched.group(2)
    res = api.role_detailed(server= server_name, name=role_name)
    msg = f"{format_role_data(res)}"
    await RoleDetail.finish(message=Message(msg))

# 角色属性
RoleAttribute = on_regex(pattern=r'^属性\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleAttribute.handle()
@check_plugin_enabled
async def handle_role_detail(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名
    role_name = matched.group(2)
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成属性信息，请稍候...")
    
    import traceback

    try:
         res = await async_api.role_attribute(server=server_name, name=role_name)
    except APIError as e:
        # 专门处理 API 错误
        print(f"RoleAttribute API错误: code={e.code}, msg={e.msg}")
        await RoleAttribute.finish(message=f"角色属性查询失败: {e.msg}")
        return
    except:  # 不推荐，但可以捕获所有异常
        await RoleAttribute.finish(message=f"角色属性接口调用失败")
        return

    colors = render_team_template().get("colors_by_mount_name")
    kungfu_name = res.get('kungfuName', '')
    if '·悟' in kungfu_name:
        xf_name = kungfu_name.replace('·悟', '')
    else:
        xf_name = kungfu_name

    if '·' in kungfu_name:
        icon_name = kungfu_name.replace('·', '')
    else:
        icon_name = kungfu_name
    icon_name = icon_name.strip()
    xf_icon = img_to_base64(STATIC_PATH.absolute() / f"xf-cn-icon/{icon_name}.png")
    pvp_icon = img_to_base64(STATIC_PATH.absolute() / f"pvp.png")
    try:
        card = await async_api.show_card(server=server_name, name=role_name)
    except:  # 不推荐，但可以捕获所有异常
        print("未获取到名片")
        card = {} 

    panel_list = res.get('panelList') or {}
    if not isinstance(panel_list, dict):
        panel_list = {}
    panels = panel_list.get("panel", []) or []  # 确保 panels 是一个列表
     # 获取背景色并生成更深的字体颜色
    bg_color = colors.get(xf_name, "#e8e8e8")
    # 如果是默认的灰色，使用深灰色，否则加深原色
    font_color = "#4a5568" if bg_color == "#e8e8e8" else darken_color(bg_color)
    roleInfo = {
        "color": bg_color,
        "xfIcon": xf_icon,
        "pvpIcon": pvp_icon,
        "fontColor": font_color,
        "show": card.get('showAvatar', ''),
        "serverName": res.get('serverName', '未知服务器'),
        "roleName": res.get('roleName', '未知角色'),
        "kungfuNam": res.get('kungfuName', '未知等级'),
        "forceName": res.get('forceName', '未知职业'),
        "score": res.get('panelList', {}).get('score', 0),
        "equipList": res.get('equipList', []),
        "qixueList": res.get('qixueList', []),
        "base_panels": [
            panel for panel in panels
            if panel.get("name") in ["会心", "会心效果", "破防", "无双", "破招", "加速"]
        ],
        "other_panels": [
            panel for panel in panels
            if panel.get("name") not in ["会心", "会心效果", "破防", "无双", "破招", "加速"]
        ]
    }
    # print(res.get('equipList', []))
    # 生成 HTML 内容
    html_content = render_role_attribute(roleInfo)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1200)

    try:
        # 发送图片
        await RoleAttribute.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 角色状态
RoleStatus = on_regex(pattern=r'^在线\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleStatus.handle()
@check_plugin_enabled
async def handle_role_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名 
    role_name = matched.group(2)
    res = await async_api.request(endpoint="/data/role/online/status", server= server_name, name=role_name)
    msg = (
        f"所在区服：{res.get('zoneName', '未知')} - {res.get('serverName', '未知')}\n"
        f"角色名称：{res.get('roleName', '未知')}\n"
        f"角色体型：{res.get('forceName', '未知')}·{res.get('bodyName', '未知')}\n"
        f"角色阵营：{res.get('campName', '未知')}\n"
        f"角色帮会：{res.get('tongName', '未知')}\n"
        f"角色标识：{res.get('roleId', '未知')}\n"
        f"登录状态：{'游戏在线' if res.get('onlineStatus', True) else '游戏离线'}"
    )
    await RoleStatus.finish(message=Message(msg))


# 角色副本cd记录
RoleTeamCdList = on_regex(pattern=r'^副本\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleTeamCdList.handle()
@check_plugin_enabled
async def handle_role_team_cd_list(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名 
    role_name = matched.group(2)
    res = await async_api.role_team_cd_list(server= server_name, name=role_name)
    list = res.get('data', [])
    if len(list) > 0:
       # 生成 HTML 内容
        html_content = render_role_cd_record(res)
        # # 转换为图片
        image_path = await render_and_cleanup(html_content, 1200)

        try:
            # 发送图片
            await RoleTeamCdList.finish(MessageSegment.image(path_to_base64(image_path)))
        finally:
            if os.path.exists(image_path):
                os.remove(image_path)
    else:
        msg = f"{server_name} {role_name} 无副本CD记录"
        await RoleTeamCdList.finish(message=Message(msg))

# 角色奇遇
RoleLuckRecord = on_regex(pattern=r'^查询\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleLuckRecord.handle()
@check_plugin_enabled
async def handle_role_luck_record(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名 
    role_name = matched.group(2)
    records = await async_api.luck_adventure(server= server_name, name=role_name)
    # 筛选有效时间的奇遇记录
    valid_records = []
    epic_days = None  # 绝世奇遇天数
    normal_days = None  # 普通奇遇天数
    now = datetime.now()
    # 计算各类奇遇数量
    pet_count = 0  # 宠物奇遇数量
    luck_count = 0  # 普通和绝世奇遇总数
    # print(records)
    for record in records:
        time = record.get('time', '')
        level = record.get('level', '')
        # 计算最近奇遇时间
        if level == 2:  # 绝世奇遇
            luck_count += 1
        elif level == 1:  # 普通奇遇
            luck_count += 1
        elif level == 3:  # 宠物奇遇
            pet_count += 1
        if time and time != 0 and level !=3:
            # print( record.get('event', ''))
            valid_records.append(record)
            # 将时间戳转换为datetime对象
            record_time = datetime.fromtimestamp(time)
            days = (now - record_time).days
            
            # 计算最近奇遇时间
            if level == 2:  # 绝世奇遇
                if epic_days is None or days < epic_days:
                    epic_days = days
            elif level == 1:  # 普通奇遇
                if normal_days is None or days < normal_days:
                    normal_days = days
    # 计算标签
    pet_tag = ''
    if pet_count > 0:
        if pet_count < 20:
            pet_tag = '宠物新手'
        elif pet_count < 50:
            pet_tag = '宠物专家'
        else:
            pet_tag = '宠物达人'
    
    luck_tag = ''
    if luck_count < 5:
        luck_tag = '非酋酋长'
    elif luck_count < 10:
        luck_tag = '非酋'
    elif luck_count <= 40:
        luck_tag = '欧皇'
    else:
        luck_tag = '超级幸运儿'
    # print(pet_tag, pet_count, luck_tag, luck_count)
    res = {
        "serverName": records[0].get('server', ''),
        "roleName": records[0].get('name', ''),
        "valid_records": valid_records,
        "records": records,
        "normal_days": normal_days,
        "epic_days": epic_days,
        "pet_tag": pet_tag,
        "luck_tag": luck_tag
    }
    # 生成 HTML 内容
    html_content = render_role_luck(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1600)
    try:
        # 发送图片
        await RoleLuckRecord.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 角色名片
RoleCard = on_regex(pattern=r'^(名片|QQ秀|qq秀)\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleCard.handle()
@check_plugin_enabled
async def handle_role_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(2):
        server_name = matched.group(2)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名 
    role_name = matched.group(3)
    try:
        res = await async_api.show_card(server= server_name, name=role_name)
    except:  # 不推荐，但可以捕获所有异常
        await RoleCard.finish(message=f"名片接口调用失败")
        return
    # print(res.get('showAvatar'))
    # res = await async_api.request(endpoint="/data/role/online/status", server= server_name, name=role_name)
    await RoleCard.finish(MessageSegment.image(res.get('showAvatar')))

# 沙盘
ServerSand = on_regex(pattern=r'^沙盘(?:\s+(\S+))?$', priority=1)
@ServerSand.handle()
@check_plugin_enabled
async def handle_role_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    try:
        res = await async_api.server_sand(server= server_name)
    except:  # 不推荐，但可以捕获所有异常
        await ServerSand.finish(message=f"沙盘接口调用失败")
        return

    info = {
        "updateTime": res.get('update', ''),
        **res
    }
    # print(info)
    # 生成 HTML 内容
    html_content = render_sandbox_html(info)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1340)
    try:
        # 发送图片
        await ServerSand.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 物价
TradeRecords = on_regex(pattern=r'^物价\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@TradeRecords.handle()
@check_plugin_enabled
async def handle_trade_records(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是物品名
    name = matched.group(2)
    try:
        res = await async_api.trade_records(name=name, server= server_name)
    except APIError as e:
        # 专门处理 API 错误
        print(f"TradeRecords API错误: code={e.code}, msg={e.msg}")
        await TradeRecords.finish(message=f"物价查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"TradeRecords 其他错误: {type(e).__name__}: {str(e)}")
        await TradeRecords.finish(message=f"物价接口调用失败: {str(e)}")
        return

    # print('TradeRecords - 物价----', res)
    
    # 生成 HTML 内容
    html_content = render_trade_records_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1920)
    try:
        # 发送图片
        await TradeRecords.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# 成就
RoleAchievement = on_regex(pattern=r'^成就\s+(?:(\S+)\s+)?(\S+)(?:\s+(\S+))?$', priority=1)
@RoleAchievement.handle()
@check_plugin_enabled
async def handle_role_achievement(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
     # 解析参数
    param1 = matched.group(1)  # 第一个参数
    param2 = matched.group(2)  # 第二个参数
    param3 = matched.group(3)  # 第三个参数
    
    # 判断参数个数并分配
    if param3:  # 三个参数：区服 角色名 成就名
        server_name = param1
        role_name = param2
        achievement_name = param3
    else:  # 两个参数：角色名 成就名
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
        role_name = param1
        achievement_name = param2
    
    print(f"成就查询参数: server={server_name}, role={role_name}, achievement={achievement_name}")
    try:
        res = await async_api.role_achievement(server=server_name,role=role_name, name=achievement_name)
    except APIError as e:
        # 专门处理 API 错误
        print(f"RoleAchievement API错误: code={e.code}, msg={e.msg}")
        await RoleAchievement.finish(message=f"成就查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"RoleAchievement 其他错误: {type(e).__name__}: {str(e)}")
        await RoleAchievement.finish(message=f"成就接口调用失败: {str(e)}")
        return

    print('RoleAchievement - 成就----', res)
    
    # 生成 HTML 内容
    html_content = render_role_achievement_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1600)
    try:
        # 发送图片
        await RoleAchievement.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 资历分布
DiaryAchievement = on_regex(pattern=r'^资历分布\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@DiaryAchievement.handle()
@check_plugin_enabled
async def handle_diary_achievement(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是物品名
    role_name = matched.group(2)
    
    print(f"资历分布查询参数: server={server_name}, role={role_name}")
    try:
        res = await async_api.request(endpoint="/data/tuilan/achievement", server= server_name, name=role_name, **{"class": 1, "subclass": None})
    except APIError as e:
        # 专门处理 API 错误
        print(f"DiaryAchievement API错误: code={e.code}, msg={e.msg}")
        await DiaryAchievement.finish(message=f"资历分布查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"DiaryAchievement 其他错误: {type(e).__name__}: {str(e)}")
        await DiaryAchievement.finish(message=f"资历分布接口调用失败: {str(e)}")
        return

    print('DiaryAchievement - 资历分布----', res)
    
    # 生成 HTML 内容
    html_content = render_diary_achievement_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1600)
    try:
        # 发送图片
        await DiaryAchievement.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 招募
MemberRecruit = on_regex(pattern=r'^招募\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@MemberRecruit.handle()
@check_plugin_enabled
async def handle_member_recruit(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是关键字
    keyword = matched.group(2)
    
    print(f"招募查询参数: server={server_name}, keyword={keyword}")
    try:
        res = await async_api.request(endpoint="/data/member/recruit", server= server_name, keyword=keyword)
    except APIError as e:
        # 专门处理 API 错误
        print(f"MemberRecruit API错误: code={e.code}, msg={e.msg}")
        await MemberRecruit.finish(message=f"招募查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"MemberRecruit 其他错误: {type(e).__name__}: {str(e)}")
        await MemberRecruit.finish(message=f"招募接口调用失败: {str(e)}")
        return

    print('MemberRecruit - 招募----', res)
    # 对招募数据按时间排序，获取最近的20条数据
    if res and 'data' in res and isinstance(res['data'], list):
        # 按 createTime 降序排序（最新的在前）
        sorted_data = sorted(res['data'], key=lambda x: x.get('createTime', 0), reverse=True)
        # 只取前20条
        res['data'] = sorted_data[:20]
    
    
    # 生成 HTML 内容
    html_content = render_member_recruit_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1700)
    try:
        # 发送图片
        await MemberRecruit.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 交易行
TradingCompany = on_regex(pattern=r'^交易行\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@TradingCompany.handle()
@check_plugin_enabled
async def handle_trading_company(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是关键字
    keyword = matched.group(2)
    
    print(f"交易行查询参数: server={server_name}, keyword={keyword}")
    try:
        # 第一步：搜索物品获取ID
        import urllib.parse
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://node.jx3box.com/api/node/item/search?ids=&keyword={encoded_keyword}&page=1&per=15&client=std"
        
        headers = {
            "Authorization": AUTHORIZATION,
            "Cookie": COOKIES,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # 使用aiohttp发送请求
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers) as response:
                search_data = await response.json()
        
        if search_data["code"] != 200 or not search_data["data"]["data"]:
            await TradingCompany.finish(message=f"未找到物品: {keyword}")
            return
        
        # 获取前3个物品的ID
        items = search_data["data"]["data"][:3]
        auction_data = []
        stats_data = None
        
        # 第二步：为每个物品ID调用交易行接口
        async with aiohttp.ClientSession() as session:
            for item in items:
                item_id = item["id"]
                
                # 获取小时数据
                auction_url = "https://next2.jx3box.com/api/auction/"
                auction_payload = {
                    "item_id": item_id,
                    "server": server_name,
                    "aggregate_type": "hourly"
                }
                
                async with session.post(auction_url, json=auction_payload, headers=headers) as response:
                    auction_result = await response.json()
                
                if auction_result:
                    # 只取前20条数据
                    auction_result = sorted(auction_result, key=lambda x: x['timestamp'], reverse=True)[:20]
                    auction_data.append({
                        "item": {
                            "id": item["id"],
                            "name": item["Name"],
                            "icon_id": item["IconID"]
                        },
                        "auction_data": auction_result
                    })
        
        # 如果只有一个物品，获取日统计数据
        if len(auction_data) == 1:
            item_id = auction_data[0]["item"]["id"]
            daily_payload = {
                "item_id": item_id,
                "server": server_name,
                "aggregate_type": "daily"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(auction_url, json=daily_payload, headers=headers) as response:
                    daily_result = await response.json()
            
            if daily_result:
                prices = [item["price"] for item in daily_result]
                if prices:
                    stats_data = {
                        "min_price": min(prices),
                        "max_price": max(prices),
                        "avg_price": sum(prices) // len(prices)
                    }
    
    except Exception as e:
        print(f"TradingCompany 错误: {type(e).__name__}: {str(e)}")
        await TradingCompany.finish(message=f"交易行接口调用失败")
        return

    print('TradingCompany - 交易行数据----', auction_data)
    
    # 生成 HTML 内容
    html_content = render_auction_html({
        "server": server_name,
        "keyword": keyword,
        "auction_data": auction_data,
        "stats_data": stats_data
    })
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1600)
    try:
        # 发送图片
        await TradingCompany.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    

# 黑本
BlackBook = on_regex(pattern=r'^黑本(?:\s+(\S+))?$', priority=1)
@BlackBook.handle()
@check_plugin_enabled
async def handle_black_book(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 解析参数：副本类型和难度
    param = matched.group(1) if matched.group(1) else "25yx太极宫"
    
    # 副本映射
    dungeon_map = {
        "25yx一之窟": {"id": 688, "name": "一之窟", "difficulty": "25人英雄"},
        "25pt太极宫": {"id": 707, "name": "太极宫", "difficulty": "25人普通"},
        "25yx太极宫": {"id": 708, "name": "太极宫", "difficulty": "25人英雄"},
    }
    
    # 解析参数
    dungeon_info = None
    param_lower = param.lower()
    
    # 更灵活的匹配逻辑
    if "一之窟" in param or "yzk" in param_lower:
        dungeon_info = dungeon_map["25yx一之窟"]
    elif "太极宫" in param or "tjg" in param_lower:
        if "pt" in param_lower or "普通" in param:
            dungeon_info = dungeon_map["25pt太极宫"]
        else:
            dungeon_info = dungeon_map["25yx太极宫"]
    else:
        # 默认太极宫英雄
        dungeon_info = dungeon_map["25yx太极宫"]
    
    try:
        # 1. 获取副本boss信息
        boss_url = f"https://node.jx3box.com/fb/boss?MapID={dungeon_info['id']}&client=std"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(boss_url) as response:
                boss_data = await response.json()
        
        if not boss_data:
            await BlackBook.finish("获取副本boss信息失败")
            return
        
        print(f"获取到 {len(boss_data)} 个boss信息")
        
        # 2. 获取每个boss的掉落信息
        boss_drops = []
        
        for boss_index, boss in enumerate(boss_data):
            boss_name = boss.get('BOSS', '')
            boss_introduce = boss.get('Introduce', '').strip()[:100] + '...' if boss.get('Introduce') else ''
            
            if not boss_name:
                continue
                
            print(f"正在获取 {boss_name} 的掉落信息...")
            
            # 获取boss掉落 - 使用URL编码
            import urllib.parse
            encoded_boss_name = urllib.parse.quote(boss_name)
            drop_url = f"https://node.jx3box.com/fb/drop/v2/{dungeon_info['id']}?client=std&BossName={encoded_boss_name}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(drop_url) as response:
                    drop_data = await response.json()
            
            # 处理掉落数据
            processed_drops = []
            if drop_data and isinstance(drop_data, list):
                import random
                import json
                import os
                
                # 读取equipment.json文件
                equipment_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'equipment.json')
                equipment_data = {}
                try:
                    with open(equipment_path, 'r', encoding='utf-8') as f:
                        equipment_data = json.load(f)
                except:
                    equipment_data = {"min": [], "min_eff": [], "top": []}
                
                # 判断是否为最后一个boss
                is_last_boss = (boss_index == len(boss_data) - 1)
                
                # 分类物品
                material_items = [item for item in drop_data if item.get('ItemType') == 5]
                equipment_items = [item for item in drop_data if item.get('ItemType') != 5]
                
                # 处理ItemType == 5的材料类物品
                if material_items:
                    # 1. 固定掉落：天极、孤漠开头的牌子物品 3-4个
                    badge_items = [item for item in material_items 
                                if item.get('ItemName', '').startswith(('天极', '孤漠'))]
                    if badge_items:
                        badge_count = random.randint(3, 4)
                        selected_badges = random.sample(badge_items, min(len(badge_items), badge_count))
                        processed_drops.extend(selected_badges)
                    
                    # 2. 秘籍类物品：包含【《】的，5%概率掉落一件
                    book_items = [item for item in material_items 
                                if '《' in item.get('ItemName', '')]
                    if book_items and random.random() < 0.05:
                        selected_book = random.choice(book_items)
                        processed_drops.append(selected_book)
                    
                    # 3. 秘境宝藏碎片：固定掉落一个
                    treasure_items = [item for item in material_items 
                                    if '秘境宝藏碎片' in item.get('ItemName', '')]
                    if treasure_items:
                        selected_treasure = random.choice(treasure_items)
                        processed_drops.append(selected_treasure)
                    
                    # 4. 昆仑玄石：固定掉落两个
                    kunlun_items = [item for item in material_items 
                                if '昆仑玄石' in item.get('ItemName', '')]
                    if kunlun_items:
                        kunlun_count = min(2, len(kunlun_items))
                        if len(kunlun_items) >= 2:
                            selected_kunlun = random.sample(kunlun_items, kunlun_count)
                        else:
                            selected_kunlun = kunlun_items * 2  # 如果只有一种，重复添加
                        processed_drops.extend(selected_kunlun)
                    
                    # 5. 特定材料：陨铁、五行石、五彩石、维峰丹、茶饼，随机掉落3-4件
                    special_materials = [item for item in material_items 
                                    if any(keyword in item.get('ItemName', '') 
                                            for keyword in ['陨铁', '五行石', '五彩石', '维峰丹', '茶饼'])]
                    if special_materials:
                        special_count = random.randint(3, 4)
                        selected_special = random.sample(special_materials, min(len(special_materials), special_count))
                        processed_drops.extend(selected_special)
                    
                    # 6. 玄晶（ItemQuality == 5）：0.5%概率掉落
                    xuanjing_items = [item for item in material_items 
                                    if item.get('ItemQuality') == 5]
                    for item in xuanjing_items:
                        if random.random() < 0.005:  # 0.5%概率
                            processed_drops.append(item)
                    
                    # 7. 其他材料：10%概率随机掉落一件
                    other_materials = [item for item in material_items 
                                    if item not in badge_items 
                                    and item not in book_items 
                                    and item not in treasure_items 
                                    and item not in kunlun_items 
                                    and item not in special_materials 
                                    and item not in xuanjing_items]
                    for item in other_materials:
                        if random.random() < 0.1:  # 10%概率
                            processed_drops.append(item)
                
                # 处理ItemType != 5的装备类物品
                if equipment_items:
                    # 分类装备
                    min_equipment = [item for item in equipment_items 
                                    if item.get('ItemName', '') in equipment_data.get('min', [])]
                    min_eff_equipment = [item for item in equipment_items 
                                        if item.get('ItemName', '') in equipment_data.get('min_eff', [])]
                    normal_equipment = [item for item in equipment_items 
                                    if item not in min_equipment and item not in min_eff_equipment]
                    
                    if not is_last_boss:
                        # 非最后一个boss的处理逻辑
                        # 1. 不在equipment.json中的装备：固定获取3-4件
                        if normal_equipment:
                            normal_count = random.randint(3, 4)
                            selected_normal = random.sample(normal_equipment, min(len(normal_equipment), normal_count))
                            processed_drops.extend(selected_normal)
                        
                        # 2. min装备：10%概率获取一件
                        min_dropped = False
                        for item in min_equipment:
                            if random.random() < 0.1:  # 10%概率
                                processed_drops.append(item)
                                min_dropped = True
                                break
                        
                        # 3. min_eff装备：5%概率获取一件
                        min_eff_dropped = False
                        # for item in min_eff_equipment:
                        #     if random.random() < 0.05:  # 5%概率
                        #         processed_drops.append(item)
                        #         min_eff_dropped = True
                        #         break
                        
                        # 4. 如果min和min_eff都没获取到，从普通装备中双随机获取1-2件
                        if not min_dropped and not min_eff_dropped and normal_equipment:
                            extra_count = random.randint(1, 2)
                            # 从已选择的普通装备中再随机选择，避免重复
                            available_normal = [item for item in normal_equipment if item not in processed_drops]
                            if available_normal:
                                extra_normal = random.sample(available_normal, min(len(available_normal), extra_count))
                                processed_drops.extend(extra_normal)
                    
                    else:
                        # 最后一个boss的处理逻辑
                        # 1. 普通装备中获取4件
                        if normal_equipment:
                            normal_count = min(4, len(normal_equipment))
                            selected_normal = random.sample(normal_equipment, normal_count)
                            processed_drops.extend(selected_normal)
                        
                        # 2. min和min_eff装备中随机获取3件
                        special_equipment = min_equipment + min_eff_equipment
                        if special_equipment:
                            special_count = min(3, len(special_equipment))
                            selected_special = random.sample(special_equipment, special_count)
                            processed_drops.extend(selected_special)
                
                # 转换为标准格式
                final_drops = []
                for item in processed_drops:
                    final_drops.append({
                        "ItemName": item.get('ItemName', '未知物品'),
                        "ItemQuality": item.get('ItemQuality', 1),
                        "ItemIconID": item.get('ItemIconID', 0),
                        "ItemType": item.get('ItemType', 0),
                        "ItemID": item.get('ItemID', 0)
                    })
                
                processed_drops = final_drops

            boss_drops.append({
                "boss_name": boss_name,
                "boss_introduce": boss_introduce,
                "drops": processed_drops,
                "total_drops": len(drop_data) if drop_data and isinstance(drop_data, list) else 0
            })
        
        # 3. 生成HTML
        html_data = {
            "dungeon_name": dungeon_info["name"],
            "difficulty": dungeon_info["difficulty"],
            "boss_drops": boss_drops,
            "total_bosses": len(boss_drops)
        }
        
        html_content = render_black_book_html(html_data)
        print('html_data-----', html_data)
        # 4. 转换为图片
        image_path = await render_and_cleanup(html_content, 1920)
       
    except Exception as e:
        print(f"BlackBook 错误: {type(e).__name__}: {str(e)}")
        await BlackBook.finish(f"副本掉落查询失败: {str(e)}")

    try:
        # 发送图片
        await BlackBook.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 角色百战
RoleDHundred = on_regex(pattern=r'^精耐\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleDHundred.handle()
@check_plugin_enabled
async def handle_role_hundred(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    # 第二个捕获组一定是角色名
    role_name = matched.group(2)

    try:
        res = await async_api.request(endpoint="/data/role/monster", server= server_name, name=role_name)
    except APIError as e:
        # 专门处理 API 错误
        print(f"RoleDHundred API错误: code={e.code}, msg={e.msg}")
        await RoleDHundred.finish(message=f"角色百战查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"RoleDHundred 其他错误: {type(e).__name__}: {str(e)}")
        await RoleDHundred.finish(message=f"角色百战接口调用失败: {str(e)}")
        return
    print(res)
    
    # 生成 HTML 内容
    html_content = render_baizhan_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1200)
    try:
        # 发送图片
        await RoleDHundred.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# 金价
GoldPrice = on_regex(pattern=r'^金价(?:\s+(\S+))?$', priority=1)
@GoldPrice.handle()
@check_plugin_enabled
async def handle_gold_price(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    if state['_matched'].group(1):
        server_name = state['_matched'].group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return

    try:
        res = await async_api.request(endpoint="/data/trade/demon", server= server_name)
    except APIError as e:
        # 专门处理 API 错误
        print(f"GoldPrice API错误: code={e.code}, msg={e.msg}")
        await GoldPrice.finish(message=f"金价查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"GoldPrice 其他错误: {type(e).__name__}: {str(e)}")
        await GoldPrice.finish(message=f"金价接口调用失败: {str(e)}")
        return
    print('金价------',res)
    
    # 生成 HTML 内容
    html_content = render_gold_price_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 820)
    try:
        # 发送图片
        await GoldPrice.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 关隘
MountainPass = on_regex(pattern=r'^关隘$', priority=1)
@MountainPass.handle()
@check_plugin_enabled
async def handle_mountain_pass(bot: Bot, event: GroupMessageEvent, state: T_State):

    try:
        res = await async_api.request(endpoint="/data/server/leader")
    except APIError as e:
        # 专门处理 API 错误
        print(f"MountainPass API错误: code={e.code}, msg={e.msg}")
        await MountainPass.finish(message=f"关隘查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"MountainPass 其他错误: {type(e).__name__}: {str(e)}")
        await MountainPass.finish(message=f"关隘接口调用失败: {str(e)}")
        return
    print('关隘------',res)
    
    # 生成 HTML 内容
    html_content = render_mountain_pass_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 800)
    try:
        # 发送图片
        await MountainPass.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# 日常预测
DailyPrediction = on_regex(pattern=r'^日常预测$', priority=1)
@DailyPrediction.handle()
@check_plugin_enabled
async def handle_daily_prediction(bot: Bot, event: GroupMessageEvent, state: T_State):

    try:
        res = await async_api.request(endpoint="/data/active/list/calendar", num=15)
    except APIError as e:
        # 专门处理 API 错误
        print(f"DailyPrediction API错误: code={e.code}, msg={e.msg}")
        await DailyPrediction.finish(message=f"日常预测查询失败: {e.msg}")
        return
    except Exception as e:
        # 处理其他异常
        print(f"DailyPrediction 其他错误: {type(e).__name__}: {str(e)}")
        await DailyPrediction.finish(message=f"日常预测接口调用失败: {str(e)}")
        return
    print('日常预测------',res)
    
    # 生成 HTML 内容
    html_content = render_daily_prediction_html(res)
    # # 转换为图片
    image_path = await render_and_cleanup(html_content, 1400)
    try:
        # 发送图片
        await DailyPrediction.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


# 金价换算
GoldPriceRate = on_regex(pattern=r'^(\d+(?:\.\d+)?)[jzJZ](?:(\d+(?:\.\d+)?)[jzJZ]?)?$', priority=1)
@GoldPriceRate.handle()
@check_plugin_enabled
async def handle_gold_price(bot: Bot, event: GroupMessageEvent, state: T_State):
    from datetime import datetime
    
    # 检查群组是否启用金价换算功能
    group_id = str(event.group_id)
    group_config = db.get_group_config(group_id)
    
    if group_config and not group_config.get('enable_gold_price', 1):
        return
    
    # 获取完整的匹配字符串进行重新解析
    full_match = state['_matched'].group(0)
    
    # 重新解析输入格式
    import re
    
    # 支持的格式：200j, 3z, 2z3, 2z3j, 1.5z, 2.5z1.2j 等
    pattern = r'^(\d+(?:\.\d+)?)[jzJZ](?:(\d+(?:\.\d+)?)([jzJZ]?))?$'
    match = re.match(pattern, full_match)
    
    if not match:
        await GoldPriceRate.finish(message="❌ 不支持的金币格式，请使用如：200j、1000j、3z、2z3 等格式")
        return
    
    first_num = match.group(1)  # 第一部分数字
    first_unit = full_match[len(first_num)].lower()  # 第一部分单位
    second_num = match.group(2) if match.group(2) else None  # 第二部分数字
    second_unit = match.group(3).lower() if match.group(3) else 'j'  # 第二部分单位，默认为j
    
    # 解析用户输入的金币数量
    try:
        total_gold = 0
        
        # 处理第一部分
        if first_unit == 'j':
            total_gold += float(first_num)
        elif first_unit == 'z':
            total_gold += float(first_num) * 10000
        else:
            await GoldPriceRate.finish(message="❌ 不支持的金币格式，请使用如：200j、1000j、3z、2z3 等格式")
            return
        
        # 处理第二部分（如果存在）
        if second_num:
            if second_unit == 'j':
                total_gold += float(second_num)
            elif second_unit == 'z':
                total_gold += float(second_num) * 10000
            else:
                await GoldPriceRate.finish(message="❌ 不支持的金币格式，请使用如：200j、1000j、3z、2z3 等格式")
                return
                
    except ValueError:
        await GoldPriceRate.finish(message="❌ 金币数量格式错误")
        return
    
    # 获取当前群默认服务器
    server_name = await get_group_default_server(bot, event)
    if not server_name:
        return
    
    # 获取今日日期
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 先尝试从缓存获取金价
    cached_price = db.get_today_gold_price(server_name)
    
    if cached_price:
        # 使用缓存的金价
        wanbaolou_price = cached_price['wanbaolou_price']
        date_info = cached_price['date']
        cache_status = "📦 (缓存)"
        print(f"使用缓存金价: {server_name} - {wanbaolou_price}")
    else:
        # 缓存中没有，调用接口获取
        try:
            res = await async_api.request(endpoint="/data/trade/demon", server=server_name)
        except APIError as e:
            print(f"GoldPriceRate API错误: code={e.code}, msg={e.msg}")
            await GoldPriceRate.finish(message=f"金价查询失败: {e.msg}")
            return
        except Exception as e:
            print(f"GoldPriceRate 其他错误: {type(e).__name__}: {str(e)}")
            await GoldPriceRate.finish(message=f"金价接口调用失败: {str(e)}")
            return
        
        # 检查返回数据并获取今日万宝楼金价
        if not res or len(res) == 0:
            await GoldPriceRate.finish(message="❌ 获取万宝楼金价失败")
            return
        
        try:
            # 获取最新日期的数据（数组第一个元素）
            latest_data = res[0]
            wanbaolou_price = latest_data.get('wanbaolou', '0')
            date_info = latest_data.get('date', today)
            cache_status = "🔄 (实时)"
            
            if wanbaolou_price == '000.00' or wanbaolou_price == '0':
                await GoldPriceRate.finish(message="❌ 今日万宝楼暂无金价数据")
                return
            
            # 保存到缓存
            if db.save_gold_price(server_name, date_info, wanbaolou_price):
                print(f"金价已缓存: {server_name} - {date_info} - {wanbaolou_price}")
            
        except (ValueError, KeyError, IndexError) as e:
            await GoldPriceRate.finish(message="❌ 金价数据解析失败")
            return
    
    try:
        gold_rate = float(wanbaolou_price)
        
        # 计算人民币价值
        rmb_value = total_gold / gold_rate
        
        # 格式化显示
        def format_gold(gold):
            if gold >= 10000:
                z_part = int(gold // 10000)
                j_part = int(gold % 10000)
                if j_part > 0:
                    return f"{z_part}z{j_part}"
                else:
                    return f"{z_part}z"
            else:
                return f"{int(gold)}j"
        
        formatted_gold = format_gold(total_gold)
        
        # 组织返回消息
        msg = f"💰 金价换算结果 {cache_status}\n" \
              f"服务器：{server_name}\n" \
              f"日期：{date_info}\n" \
              f"游戏金币：{formatted_gold}\n" \
              f"万宝楼金价：1元 = {gold_rate}j\n" \
              f"等值人民币：¥{rmb_value:.2f}元"
        
        await GoldPriceRate.finish(message=Message(msg))
        
    except (ValueError, KeyError) as e:
        await GoldPriceRate.finish(message="❌ 金价数据解析失败")
        return

# 设置默认服务器
SetDefaultServer = on_regex(pattern=r'^绑定服务器\s+(\S+)$', priority=1)
@SetDefaultServer.handle()
@check_plugin_enabled
async def handle_set_default_server(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, SetDefaultServer):
        return
    # 检查是否为管理员（可选，根据需要添加权限检查）
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取服务器名称
    match = state['_matched']
    server_name = match.group(1)
    
     # 剑网3有效服务器列表
    valid_servers = {
        # 电信区服务器
        '梦江南', '长安城', '唯我独尊', '乾坤一掷', '斗转星移', '绝代天骄', 
        '幽月轮', '剑胆琴心', '蝶恋花', '龙争虎斗',
        
        # 双线区服务器
        '破阵子', '天鹅坪', '飞龙在天', 
        
        # 无界区
        '眉间雪', '山海相逢'
    }
    
    # 验证服务器名称
    if server_name not in valid_servers:
        await SetDefaultServer.finish(
            message=f"❌ 服务器名称 '{server_name}' 无效\n" +
                   "请输入正确的服务器名称，如：梦江南、长安城、唯我独尊、破阵子、天鹅坪等\n" +
                   "提示：请确保服务器名称完全匹配，区分大小写"
        )
    
    # 更新群组配置
    if db.update_group_config(group_id, {'default_server': server_name}):
        await SetDefaultServer.finish(message=f"✅ 群组默认服务器已设置为：{server_name}")
    else:
        await SetDefaultServer.finish(message="❌ 设置默认服务器失败")

# 查看群组配置
ViewGroupConfig = on_regex(pattern=r'^查看群组配置$', priority=1)
@ViewGroupConfig.handle()
@check_plugin_enabled
async def handle_view_group_config(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    config = db.get_group_config(group_id)
    
    if config:
        default_server = config.get('default_server', '未设置')
        enable_gold_price = "开启" if config.get('enable_gold_price', 1) else "关闭"
        enable_daily_query = "开启" if config.get('enable_daily_query', 1) else "关闭"
        enable_role_query = "开启" if config.get('enable_role_query', 1) else "关闭"
        enable_ai_chat = "开启" if config.get('enable_ai_chat', 1) else "关闭"
        enable_sandbox_monitor = "开启" if config.get('enable_sandbox_monitor', 1) else "关闭"
        
        msg = f"📋 群组配置信息\n" \
              f"默认服务器：{default_server}\n" \
              f"金价换算：{enable_gold_price}\n" \
              f"沙盘监控：{enable_sandbox_monitor}" 
    else:
        msg = "📋 群组配置信息\n" \
              "默认服务器：未设置\n" \
              "金价换算：开启\n" \
              "沙盘监控：开启" 
    
    await ViewGroupConfig.finish(message=msg)


# 金价换算开关
ToggleGoldPrice = on_regex(pattern=r'^金价换算\s+(开启|关闭)$', priority=1)
@ToggleGoldPrice.handle()
@check_plugin_enabled
async def handle_toggle_gold_price(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查是否为管理员（可选，根据需要添加权限检查）
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取操作类型
    match = state['_matched']
    action = match.group(1)
    
    enable_value = 1 if action == '开启' else 0
    
    # 更新群组配置
    if db.update_group_config(group_id, {'enable_gold_price': enable_value}):
        await ToggleGoldPrice.finish(message=f"✅ 金价换算功能已{action}")
    else:
        await ToggleGoldPrice.finish(message=f"❌ {action}金价换算功能失败")

# 功能开关通用命令
ToggleFeature = on_regex(pattern=r'^(日常查询|角色查询|AI对话)\s+(开启|关闭)$', priority=1)
@ToggleFeature.handle()
@check_plugin_enabled
async def handle_toggle_feature(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查是否为管理员（可选，根据需要添加权限检查）
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取功能名称和操作类型
    match = state['_matched']
    feature_name = match.group(1)
    action = match.group(2)
    
    # 映射功能名称到数据库字段
    feature_mapping = {
        '日常查询': 'enable_daily_query',
        '角色查询': 'enable_role_query',
        'AI对话': 'enable_ai_chat'
    }
    
    if feature_name not in feature_mapping:
        await ToggleFeature.finish(message="❌ 不支持的功能名称")
        return
    
    db_field = feature_mapping[feature_name]
    enable_value = 1 if action == '开启' else 0
    
    # 更新群组配置
    if db.update_group_config(group_id, {db_field: enable_value}):
        await ToggleFeature.finish(message=f"✅ {feature_name}功能已{action}")
    else:
        await ToggleFeature.finish(message=f"❌ {action}{feature_name}功能失败")


SerendipityGuide = on_regex(pattern=r'^攻略\s+(\S+)$', priority=1)
@SerendipityGuide.handle()
@check_plugin_enabled
async def handle_serendipity_guide(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 获取用户输入的奇遇名称（必填）
    serendipity_name = state['_matched'].group(1)
    
    try:
        # 调用奇遇API获取数据
        async with aiohttp.ClientSession() as session:
            # 获取所有完美奇遇数据
            url = "https://node.jx3box.com/serendipities"
            params = {
                "per": 3,  # 获取更多数据以确保完整性
                "client": "std",
                "page": 1,
                "name": serendipity_name
            }
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    await SerendipityGuide.send(message="❌ 攻略接口调用失败，请稍后重试")
                    return
                
                data = await response.json()
                
                if not data or 'list' not in data or not data['list']:
                    await SerendipityGuide.send(message="❌ 暂无奇遇攻略数据")
                    return
                
                serendipities = data['list']
                
                 # 查找所有匹配的奇遇（支持多个结果）
                found_serendipities = []
                for item in serendipities:
                    if serendipity_name in item.get('szName', ''):
                        found_serendipities.append(item)
                
                if not found_serendipities:
                    # 显示可用的奇遇列表
                    msg_parts = [f"❌ 未找到包含'{serendipity_name}'的奇遇\n"]
                    msg_parts.append("📋 可用的完美奇遇（前10个）：\n")
                    for i, item in enumerate(serendipities[:10], 1):
                        dw_id = item.get('dwID', '')
                        sz_name = item.get('szName', '未知')
                        link = f"https://jx3box.com/adventure/{dw_id}"
                        msg_parts.append(f"{i}. 🎯 {sz_name}\n   🔗 {link}\n")
                    
                    msg_parts.append("💡 使用'攻略 奇遇名称'查看具体攻略")
                    msg = '\n'.join(msg_parts)
                    await SerendipityGuide.send(message=Message(msg))
                    return
                
                # 显示所有找到的奇遇信息（支持多个结果）
                if len(found_serendipities) == 1:
                    # 单个结果
                    item = found_serendipities[0]
                    dw_id = item.get('dwID', '')
                    sz_name = item.get('szName', '未知奇遇')
                    link = f"https://jx3box.com/adventure/{dw_id}"
                    
                    msg = f"🎯 找到奇遇攻略\n\n" \
                          f"📖 奇遇名称：{sz_name}\n" \
                          f"🔗 详细攻略：{link}"
                else:
                    # 多个结果
                    msg_parts = [f"🎯 找到 {len(found_serendipities)} 个相关奇遇：\n"]
                    for i, item in enumerate(found_serendipities, 1):
                        dw_id = item.get('dwID', '')
                        sz_name = item.get('szName', '未知奇遇')
                        link = f"https://jx3box.com/adventure/{dw_id}"
                        msg_parts.append(f"{i}. 📖 {sz_name}\n   🔗 {link}\n")
                    
                    msg = '\n'.join(msg_parts)
                
                await SerendipityGuide.send(message=Message(msg))
                
    except aiohttp.ClientError as e:
        print(f"SerendipityGuide 网络错误: {str(e)}")
        await SerendipityGuide.finish(message="❌ 网络连接失败，请稍后重试")
    except json.JSONDecodeError as e:
        print(f"SerendipityGuide JSON解析错误: {str(e)}")
        await SerendipityGuide.finish(message="❌ 数据解析失败，请稍后重试")
    except Exception as e:
        print(f"SerendipityGuide 其他错误: {type(e).__name__}: {str(e)}")
        await SerendipityGuide.finish(message="❌ 攻略查询失败，请稍后重试")

# 宏查询命令
MacroGuide = on_regex(r"^宏\s+(\S+)$", priority=5)
@MacroGuide.handle()
@check_plugin_enabled
async def handle_macro_guide(bot: Bot, event: GroupMessageEvent, state: T_State):
    """处理宏查询命令"""
    xinfa_name = state['_matched'].group(1)
    try:
        # 构建API请求URL
        import urllib.parse
        encoded_xinfa = urllib.parse.quote(xinfa_name)
        api_url = f"https://cms.jx3box.com/api/cms/posts?type=macro&per=5&page=1&order=update&client=std&search={encoded_xinfa}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    await MacroGuide.finish(message="❌ API请求失败，请稍后重试")
                    return
                
                data = await response.json()
                
                # 检查返回数据格式
                if not isinstance(data, dict) or 'data' not in data:
                    await MacroGuide.finish(message="❌ 数据格式错误，请稍后重试")
                    return
                
                macro_list = data['data'].get('list', [])
                
                if not macro_list:
                    msg = f"❌ 未找到'{xinfa_name}'相关的宏\n\n" \
                          f"💡 请尝试使用更准确的心法名称，如：冰心、气纯、剑纯等"
                    await MacroGuide.send(message=Message(msg))
                    return
                
                # 显示找到的宏信息
                if len(macro_list) == 1:
                    # 单个结果
                    item = macro_list[0]
                    macro_id = item.get('ID', '')
                    title = item.get('post_title', '未知标题')
                    author = item.get('author', '未知作者')
                    link = f"https://www.jx3box.com/macro/{macro_id}"
                    
                    msg = f"📋 找到宏攻略\n\n" \
                          f"📖 标题：{title}\n" \
                          f"👤 作者：{author}\n" \
                          f"🔗 详细内容：{link}"
                else:
                    # 多个结果
                    msg_parts = [f"📋 找到 {len(macro_list)} 个'{xinfa_name}'相关宏：\n"]
                    for i, item in enumerate(macro_list, 1):
                        macro_id = item.get('ID', '')
                        title = item.get('post_title', '未知标题')
                        author = item.get('author', '未知作者')
                        link = f"https://www.jx3box.com/macro/{macro_id}"
                        msg_parts.append(f"{i}. 📖 {title}\n   👤 作者：{author}\n   🔗 {link}\n")
                    
                    msg = '\n'.join(msg_parts)
                
                await MacroGuide.send(message=Message(msg))
                
    except aiohttp.ClientError as e:
        print(f"MacroGuide 网络错误: {str(e)}")
        await MacroGuide.finish(message="❌ 网络连接失败，请稍后重试")
    except json.JSONDecodeError as e:
        print(f"MacroGuide JSON解析错误: {str(e)}")
        await MacroGuide.finish(message="❌ 数据解析失败，请稍后重试")
    except Exception as e:
        print(f"MacroGuide 其他错误: {type(e).__name__}: {str(e)}")
        await MacroGuide.finish(message="❌ 宏查询失败，请稍后重试")


# 配装查询命令
EquipmentGuide = on_regex(r"^配装\s+([^\s]+)(?:\s+(pve|pvp|PvE|PvP))?$", priority=5)
@EquipmentGuide.handle()
@check_plugin_enabled
async def handle_equipment_guide(bot: Bot, event: GroupMessageEvent, state: T_State):
    """处理配装查询命令"""
    xinfa_name = state['_matched'].group(1)
    tag_input = state['_matched'].group(2) if state['_matched'].group(2) else ""  # 默认PvE
    try:
        # 标准化标签格式
        if tag_input.lower() == "pve":
            tag = "PvE"
        elif tag_input.lower() == "pvp":
            tag = "PvP"
        else:
            tag = ""  # 默认值
        
        # 构建API请求URL
        import urllib.parse
        encoded_xinfa = urllib.parse.quote(xinfa_name)
        api_url = f"https://cms.jx3box.com/api/cms/app/pz?per=10&page=1&search={encoded_xinfa}&tags={tag}&client=std&global_level=130&star=1"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    await EquipmentGuide.finish(message="❌ API请求失败，请稍后重试")
                    return
                
                data = await response.json()
                
                # 检查返回数据格式
                if not isinstance(data, dict) or 'data' not in data:
                    await EquipmentGuide.finish(message="❌ 数据格式错误，请稍后重试")
                    return
                
                equipment_list = data['data'].get('list', [])
                
                if not equipment_list:
                    msg = f"❌ 未找到'{xinfa_name}'的{tag}配装\n\n" \
                          f"💡 请尝试使用更准确的心法名称，如：冰心、气纯、剑纯等\n" \
                          f"🏷️ 或尝试切换标签：配装 {xinfa_name} {'PvP' if tag == 'PvE' else 'PvE'}"
                    await EquipmentGuide.send(message=Message(msg))
                    return
                
                # 显示找到的配装信息
                if len(equipment_list) == 1:
                    # 单个结果
                    item = equipment_list[0]
                    equipment_id = item.get('id', '')
                    title = item.get('title', '未知标题')
                    author_info = item.get('pz_author_info', {})
                    author = author_info.get('display_name', '未知作者')
                    link = f"https://www.jx3box.com/pz/view/{equipment_id}"
                    
                    msg = f"⚔️ 找到{xinfa_name}配装\n\n" \
                          f"📖 标题：{title}\n" \
                          f"👤 作者：{author}\n" \
                          f"🏷️ 标签：{tag}\n" \
                          f"🔗 详细配装：{link}"
                else:
                    # 多个结果
                    msg_parts = [f"⚔️ 找到 {len(equipment_list)} 个'{xinfa_name}'的{tag}配装：\n"]
                    for i, item in enumerate(equipment_list, 1):
                        equipment_id = item.get('id', '')
                        title = item.get('title', '未知标题')
                        author_info = item.get('pz_author_info', {})
                        author = author_info.get('display_name', '未知作者')
                        link = f"https://www.jx3box.com/pz/view/{equipment_id}"
                        msg_parts.append(f"{i}. 📖 {title}\n   👤 作者：{author}\n   🔗 {link}\n")
                    
                    msg = '\n'.join(msg_parts)
                
                await EquipmentGuide.send(message=Message(msg))
                
    except aiohttp.ClientError as e:
        print(f"EquipmentGuide 网络错误: {str(e)}")
        await EquipmentGuide.finish(message="❌ 网络连接失败，请稍后重试")
    except json.JSONDecodeError as e:
        print(f"EquipmentGuide JSON解析错误: {str(e)}")
        await EquipmentGuide.finish(message="❌ 数据解析失败，请稍后重试")
    except Exception as e:
        print(f"EquipmentGuide 其他错误: {type(e).__name__}: {str(e)}")
        await EquipmentGuide.finish(message="❌ 配装查询失败，请稍后重试")

# 沙盘记录查询
SandboxRecord = on_regex(r"^沙盘记录(?:\s+(.+))?$", priority=1)

@SandboxRecord.handle()
@check_plugin_enabled
async def handle_sandbox_record(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    if matched.group(1):
        server_name = matched.group(1)
    else:
        server_name = await get_group_default_server(bot, event)
        if not server_name:
            return
    try:
        async with aiohttp.ClientSession() as session:
            # 构建API请求参数
            params = {}
            if server_name:
                params['server'] = server_name
            
            async with session.get(
                "https://next2.jx3box.com/api/game/reporter/sandbox",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    await SandboxRecord.send(message=f"❌ API请求失败，状态码: {response.status}")
                    return
                
                data = await response.json()
                 # 检查返回数据格式
                if not isinstance(data, dict) or 'data' not in data:
                    await SandboxRecord.send(message="❌ 数据格式错误，请稍后重试")
                    return
                
                record_list = data['data'].get('list', [])
                
                if not record_list:
                    await SandboxRecord.send(message="❌ 暂无沙盘记录数据")
                    return
                
                # 获取第一条记录的日期
                first_record = record_list[0]
                first_created_at = first_record.get('created_at')
                
                if not first_created_at:
                    await SandboxRecord.send(message="❌ 数据格式错误，无法获取时间信息")
                    return
                
                # 解析日期（格式："2025-06-19T21:32:54+08:00"）
                try:
                    first_datetime = datetime.fromisoformat(first_created_at)
                    target_date = first_datetime.date()  # 只取日期部分
                except ValueError:
                    await SandboxRecord.send(message="❌ 时间格式解析失败")
                    return
                
                # 筛选同一天的所有记录
                same_day_records = []
                for record in record_list:
                    record_created_at = record.get('created_at')
                    if record_created_at:
                        try:
                            record_datetime = datetime.fromisoformat(record_created_at)
                            if record_datetime.date() == target_date:
                                same_day_records.append(record)
                        except ValueError:
                            continue
                
                if not same_day_records:
                    await SandboxRecord.send(message=f"❌ 未找到 {target_date} 的沙盘记录")
                    return
                
                # 按时间倒序排列（最新的在前）
                same_day_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                
                # 构建消息
                server_display = server_name if server_name else "默认服务器"
                msg_parts = [f"📊 {server_display} - {target_date} 沙盘记录：\n"]
                
                for i, record in enumerate(same_day_records, 1):
                    content = record.get('content', '无内容')
                    created_at = record.get('created_at', '')

                    if '据点！' in content:
                        content = content.split('据点！')[0] + '据点！'
                    
                    # 格式化时间显示（只显示时分秒）
                    try:
                        dt = datetime.fromisoformat(created_at)
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        time_str = created_at
                    
                    msg_parts.append(f"{i}. [{time_str}] {content}")
                
                msg = '\n'.join(msg_parts)
                
                # 如果消息太长，截断并提示
                if len(msg) > 1000:
                    msg = msg[:1000] + "\n\n... (记录过多，已截断)"
                
                await SandboxRecord.send(message=Message(msg))
                
    except aiohttp.ClientError as e:
        print(f"SandboxRecord 网络错误: {str(e)}")
        await SandboxRecord.finish(message="❌ 网络连接失败，请稍后重试")
    except Exception as e:
        print(f"SandboxRecord 其他错误: {type(e).__name__}: {str(e)}")
        await SandboxRecord.finish(message="❌ 沙盘记录查询失败，请稍后重试")


# 沙盘监控开关
SandboxMonitorSwitch = on_regex(pattern=r'^沙盘监控\s+(开启|关闭)$', priority=1)
@SandboxMonitorSwitch.handle()
@check_plugin_enabled
async def handle_sandbox_monitor_switch(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    action = state['_matched'].group(1)
    
    enable_value = 1 if action == '开启' else 0
    
    if db.update_group_config(group_id, {'enable_sandbox_monitor': enable_value}):
        status = "已开启" if enable_value else "已关闭"
        await SandboxMonitorSwitch.finish(message=f"✅ 沙盘记录监控{status}")
    else:
        await SandboxMonitorSwitch.finish(message="❌ 设置失败")

# 定时轮询沙盘记录 - 周二和周四 20:00-22:00 每分钟执行
@scheduler.scheduled_job("cron", day_of_week="1,3", hour="20-21", minute="*/5", id="sandbox_monitor")
async def poll_sandbox_records():
    """定时轮询沙盘记录"""
    global last_sandbox_data
    # 获取所有bot实例
    driver = get_driver()
    if not driver.bots:
        return
    
    bot = list(driver.bots.values())[0]
    
    # 获取所有启用了jx3_api插件的群
    enabled_groups = db.get_enabled_groups("jx3_api")
    print('0000----', enabled_groups)
    for group_id in enabled_groups:
        try:
            group_key = str(group_id)
            print(1)
            # 获取该群的配置
            group_config = db.get_group_config(group_key)
            if not group_config:
                continue
            print(2)
            # 检查是否启用了沙盘监控功能
            if not group_config.get('enable_sandbox_monitor', 1):
                continue
            print(3)
            # 获取该群的默认服务器
            server_name = group_config.get('default_server')
            if not server_name:
                # 如果没有设置默认服务器，跳过该群
                continue
            print(4)
            # 调用沙盘API
            try:
                async with aiohttp.ClientSession() as session:
                    params = {'server': server_name}
                    
                    async with session.get(
                        "https://next2.jx3box.com/api/game/reporter/sandbox",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status != 200:
                            continue
                        print(5)
                        data = await response.json()
                        if data.get('code') != 0 or not data.get('data', {}).get('list'):
                            continue
                        
                        current_records = data['data']['list']
                        # 检查是否有新记录
                        if group_key in last_sandbox_data:
                            last_records = last_sandbox_data[group_key]
                            new_records = []
                            # 找出新增的记录（通过ID比较）
                            for record in current_records:
                                record_id = record.get('id')
                                if not any(r.get('id') == record_id for r in last_records):
                                    new_records.append(record)
                            print(f"群 {group_id} - 新增记录数: {len(new_records)}")
                            # 如果有新记录，发送通知
                            if new_records:
                                await _send_sandbox_notifications(bot, group_id, server_name, new_records)
                        
                        # 更新该群的记录
                        last_sandbox_data[group_key] = current_records
            except aiohttp.ClientError as e:
                print(f"请求沙盘API失败 (群 {group_id}): {e}")
                continue
            except Exception as e:
                print(f"处理沙盘API响应失败 (群 {group_id}): {e}")
                continue
                
        except Exception as e:
            print(f"轮询群 {group_id} 的沙盘记录失败: {e}")
            continue


async def _send_sandbox_notifications(bot: Bot, group_id: int, server_name: str, new_records: list):
    """发送沙盘记录通知"""
    for record in new_records:
        try:
            content = record.get('content', '')
            created_at = record.get('created_at', '')
            
            # 处理content，只保留"据点！"之前的部分
            if '据点！' in content:
                content = content.split('据点！')[0] + '据点！'
            
            # 处理时间格式
            try:
                dt = datetime.fromisoformat(created_at)
                time_str = dt.strftime('%H:%M:%S')
            except (ValueError, TypeError):
                time_str = created_at
            
            msg = f"🚨 【{server_name}】新沙盘记录\n[{time_str}] {content}"
            
            await bot.send_group_msg(group_id=group_id, message=msg)
            
        except Exception as e:
            print(f"发送沙盘记录到群 {group_id} 失败: {e}")

# 22:00 发送当天阵营记录 - 周二和周四
@scheduler.scheduled_job("cron", day_of_week="1,3", hour="22", minute="0")
async def send_daily_sandbox_summary():
    """发送当天的阵营记录汇总"""
    # 获取所有bot实例
    driver = get_driver()
    if not driver.bots:
        return
    
    bot = list(driver.bots.values())[0]
    
    # 获取所有启用了jx3_api插件的群
    enabled_groups = db.get_enabled_groups("jx3_api")
    
    for group_id in enabled_groups:
        try:
            group_key = str(group_id)

            # 获取该群的配置
            group_config = db.get_group_config(group_key)

            # 检查是否启用了沙盘监控功能
            if not group_config.get('enable_sandbox_monitor', 1):
                continue
            
            # 获取该群的默认服务器
            server_name = group_config.get('default_server')
            
            if not server_name:
                # 如果没有设置默认服务器，跳过该群
                continue
            
            # 调用沙盘API获取当天记录
            async with aiohttp.ClientSession() as session:
                params = {'server': server_name}
                
                async with session.get(
                    "https://next2.jx3box.com/api/game/reporter/sandbox",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        continue
                    
                    data = await response.json()
                    if data.get('code') != 0 or not data.get('data', {}).get('list'):
                        continue
                    
                    records = data['data']['list']
                    
                    if not records:
                        continue
                    
                    # 获取今天的日期
                    today = datetime.now().date()
                    
                    # 筛选今天的记录
                    today_records = []
                    for record in records:
                        try:
                            created_at = record.get('created_at', '')
                            dt = datetime.fromisoformat(created_at)
                            
                            if dt.date() == today:
                                today_records.append(record)
                        except:
                            continue
                    
                    if not today_records:
                        # 如果今天没有记录，发送提示
                        msg = f"📊 【{server_name}】今日阵营记录汇总 ({today.strftime('%Y-%m-%d')})\n\n暂无记录"
                        try:
                            await bot.send_group_msg(group_id=group_id, message=msg)
                        except Exception as e:
                            print(f"发送每日沙盘汇总到群 {group_id} 失败: {e}")
                        continue
                    
                    # 按时间倒序排列
                    today_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                    
                    # 构建消息
                    msg_parts = [f"📊 【{server_name}】今日阵营记录汇总 ({today.strftime('%Y-%m-%d')})"]
                    
                    for i, record in enumerate(today_records[:20], 1):  # 最多显示20条
                        content = record.get('content', '')
                        created_at = record.get('created_at', '')
                        
                        # 处理content，只保留"据点！"之前的部分
                        if '据点！' in content:
                            content = content.split('据点！')[0] + '据点！'
                        
                        # 处理时间格式
                        try:
                            dt = datetime.fromisoformat(created_at)
                            time_str = dt.strftime('%H:%M:%S')
                        except:
                            time_str = created_at
                        
                        msg_parts.append(f"{i}. [{time_str}] {content}")
                    
                    msg = '\n'.join(msg_parts)
                    
                    # 如果消息太长，截断并提示
                    if len(msg) > 1000:
                        msg = msg[:1000] + "\n\n... (记录过多，已截断)"
                    
                    try:
                        await bot.send_group_msg(group_id=group_id, message=msg)
                    except Exception as e:
                        print(f"发送每日沙盘汇总到群 {group_id} 失败: {e}")
                        
        except Exception as e:
            print(f"为群 {group_id} 生成每日沙盘汇总失败: {e}")
            continue

        