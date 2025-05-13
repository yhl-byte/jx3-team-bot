'''
Date: 2024-03-17
Description: 剑网3 API 插件
'''
import token
import asyncio
from datetime import datetime
from warnings import catch_warnings
from nonebot import on_regex, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent,MessageSegment, GroupMessageEvent, Bot, Message
import aiohttp
import json
from typing import Dict, List, Optional
from jx3api import JX3API,AsyncJX3API
from ..utils.index import format_daily_data,format_role_data,path_to_base64,render_team_template,darken_color
from .html_generator import render_role_attribute,img_to_base64,render_role_cd_record,render_role_luck
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
    
    try:
         res = await async_api.role_attribute(server=server_name, name=role_name)
    except:  # 不推荐，但可以捕获所有异常
        await RoleAttribute.finish(message=f"角色属性接口调用失败: {str(e)}")
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
    image_path = await generate_html_screenshot(html_content, 1200)
    # # 发送图片
    await RoleAttribute.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)


# 角色状态
RoleStatus = on_regex(pattern=r'^在线\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleStatus.handle()
async def handle_role_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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
async def handle_role_team_cd_list(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
    # 第二个捕获组一定是角色名 
    role_name = matched.group(2)
    res = await async_api.role_team_cd_list(server= server_name, name=role_name)
    list = res.get('data', [])
    if len(list) > 0:
       # 生成 HTML 内容
        html_content = render_role_cd_record(res)
        # # 转换为图片
        image_path = await generate_html_screenshot(html_content, 1200)
        # # 发送图片
        await RoleTeamCdList.finish(MessageSegment.image(path_to_base64(image_path)))
        # 清理临时文件
        os.unlink(image_path)
    else:
        msg = f"{server_name} {role_name} 无副本CD记录"
        await RoleTeamCdList.finish(message=Message(msg))

# 角色奇遇
RoleLuckRecord = on_regex(pattern=r'^查询\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleLuckRecord.handle()
async def handle_role_luck_record(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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
    print(records)
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
    image_path = await generate_html_screenshot(html_content, 1600)
    # # 发送图片
    await RoleLuckRecord.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)

