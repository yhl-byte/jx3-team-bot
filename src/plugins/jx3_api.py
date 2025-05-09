'''
Date: 2024-03-17
Description: 剑网3 API 插件
'''
import token
from nonebot import on_regex, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent,MessageSegment, GroupMessageEvent, Bot, Message
import aiohttp
import json
from typing import Dict, List, Optional
from jx3api import JX3API,AsyncJX3API
from ..utils.index import format_daily_data,format_role_data,path_to_base64,render_team_template,get_code_by_name
from .html_generator import render_role_attribute,img_to_base64
from .render_image import generate_html_screenshot
from src.config import STATIC_PATH
# from html2image import Html2Image
import os

token ='v255c2a8b3e7c0098f'
ticket = '46d16dd34f70408d88aad51273b75242:18231851515@163.com:kingsoft::00f0e071281d72a2'
base_url = 'https://www.jx3api.com'
async_api = AsyncJX3API(token = token, ticket=ticket, base_url = base_url)
api = JX3API(token = token, ticket=ticket, base_url = base_url)
default_server = '唯我独尊'

# 开服检测
OpenServer = on_regex(pattern=r'^(开服|倒闭了)(?:\s+(\S+))?$', priority=1)
@OpenServer.handle()
async def handle_server_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    server_name = state['_matched'].group(2) if state['_matched'].group(2) else default_server
    res = api.server_check(server= server_name)
    print(res)
    msg = f"{server_name} {'开服了' if res['status'] == 1 else '维护中'}"
    await OpenServer.finish(message=Message(msg))

# 查看日常
CheckDaily = on_regex(pattern=r'^日常(?:\s+(\S+))?$', priority=1)
@CheckDaily.handle()
async def handle_daily(bot: Bot, event: GroupMessageEvent, state: T_State):
    server_name = state['_matched'].group(1) if state['_matched'].group(1) else default_server
    res = api.active_calendar(server= server_name)
    msg = f"{server_name} {format_daily_data(res)}"
    await CheckDaily.finish(message=Message(msg))

# 角色信息
RoleDetail = on_regex(pattern=r'^角色\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleDetail.handle()
async def handle_role_detail(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
    # 第二个捕获组一定是角色名
    role_name = matched.group(2)
    res = api.role_detailed(server= server_name, name=role_name)
    msg = f"{format_role_data(res)}"
    await RoleDetail.finish(message=Message(msg))

# 角色属性
RoleAttribute = on_regex(pattern=r'^属性\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleAttribute.handle()
async def handle_role_detail(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
    # 第二个捕获组一定是角色名
    role_name = matched.group(2)
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成属性信息，请稍候...")
    res = await async_api.role_attribute(server= server_name, name=role_name)
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
    xf_icon = img_to_base64(STATIC_PATH.absolute() / f"xf-cn-icon/{icon_name.strip()}.png")
    card = await async_api.show_cache(server= server_name, name=role_name)
    print(11,card)
    roleInfo = {
        "color": colors.get(xf_name, "#e8e8e8"),
        "xfIcon": xf_icon,
        "show": card.get('showAvatar', ''),
        "serverName": res.get('serverName', '未知服务器'),
        "roleName": res.get('roleName', '未知角色'),
        "kungfuNam": res.get('kungfuName', '未知等级'),
        "forceName": res.get('forceName', '未知职业'),
        "score": res.get('panelList', {}).get('score', 0),
        "equipList": res.get('equipList', []),
        "qixueList": res.get('qixueList', []),
        "base_panels": [
            panel for panel in res.get('panelList', {}).get("panel", [])
            if panel.get("name") in ["会心", "会心效果", "破防", "无双", "破招", "加速"]
        ],
        "other_panels": [
            panel for panel in res.get('panelList', {}).get("panel", [])
            if panel.get("name") not in ["会心", "会心效果", "破防", "无双", "破招", "加速"]
        ]
    }
    # 生成 HTML 内容
    html_content = render_role_attribute(roleInfo)
    # # 转换为图片
    image_path = await generate_html_screenshot(html_content, 1200)
    # # 发送图片
    await RoleAttribute.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)
