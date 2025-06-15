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
from .html_generator import render_role_attribute,img_to_base64,render_role_cd_record,render_role_luck,render_sandbox_html,render_trade_records_html,render_role_achievement_html,render_diary_achievement_html,render_member_recruit_html,render_auction_html,render_black_book_html
from .render_image import generate_html_screenshot
from src.config import STATIC_PATH
from jx3api.exception import APIError  # 添加导入
import os
from .database import TeamRecordDB  # 添加数据库导入


AUTHORIZATION = "Basic ZXlKaGJHY2lPaUpJVXpJMU5pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SjFhV1FpT2pJNU5qQTVOeXdpYm1GdFpTSTZJdVdCbXVTN2dPUzVpT2FpcHVXUm9pSXNJbWR5YjNWd0lqb3hMQ0p6YVdkdUlqb2lNakEyTURKak5EVmlZMkU1WVRGbVpXSXpNMlE1WWpSaE1qWTROV1kwWVdRaUxDSnBZWFFpT2pFM05EazBNams0TXpNc0ltVjRjQ0k2TVRjMU1qQXlNVGd6TTMwLk1RTTJScndrSVhOdUFEcllJSHJLMXk5dm9jYmZmVkc4T0NpVkRCMUJGMVU6bm9kZSBjb21tb24gcmVxdWVzdA=="  # 请替换为实际的authorization
COOKIES = "Hm_lvt_8661e9bde42eb87b91ee7b8525cc93eb=1748219930,1748829732; HMACCOUNT=26A628DEBFF22275; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjI5NjA5NywibmFtZSI6IuWBmuS7gOS5iOaipuWRoiIsImdyb3VwIjoxLCJzaWduIjoiMjA2MDJjNDViY2E5YTFmZWIzM2Q5YjRhMjY4NWY0YWQiLCJpYXQiOjE3NDk0Mjk4MzMsImV4cCI6MTc1MjAyMTgzM30.MQM2RrwkIXNuADrYIHrK1y9vocbffVG8OCiVDB1BF1U; season_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjI5NjA5NywibmFtZSI6IuWBmuS7gOS5iOaipuWRoiIsImdyb3VwIjoxLCJzaWduIjoiMjA2MDJjNDViY2E5YTFmZWIzM2Q5YjRhMjY4NWY0YWQiLCJpYXQiOjE3NDk0Mjk4MzMsImV4cCI6MTc1MjAyMTgzM30.Vd0CYD0TtVHTD3iAobgHwBSCKTV6i9lvTZ6-ujI83CM; Hm_lpvt_8661e9bde42eb87b91ee7b8525cc93eb=1749910225"  # 请替换为实际的cookies

token ='v255c2a8b3e7c0098f'
ticket = '1cf7637eaef344ff92add3b739463564:18231851515@163.com:kingsoft::mnTKaKUCXj8qduVypwuLHA=='
base_url = 'https://www.jx3api.com'
async_api = AsyncJX3API(token = token, ticket=ticket, base_url = base_url)
api = JX3API(token = token, ticket=ticket, base_url = base_url)
default_server = '唯我独尊'

# 初始化数据库
db = TeamRecordDB()
db.init_db()

# 插件名称
PLUGIN_NAME = "jx3_api"

# 状态检查装饰器
def check_plugin_enabled(func):
    async def wrapper(bot: Bot, event: GroupMessageEvent, state: T_State):
        group_id = str(event.group_id)
        if not db.get_plugin_status(PLUGIN_NAME, group_id):
            # await bot.send(event=event, message="剑网3 API插件已关闭，请联系管理员开启")
            return
        return await func(bot, event, state)
    return wrapper

# 插件开关控制命令
JX3PluginControl = on_regex(pattern=r'^剑三助手\s*(开启|关闭|状态)$', priority=1)
@JX3PluginControl.handle()
async def handle_plugin_control(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查是否为管理员或群主
    user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id)
    if user_info['role'] not in ['admin', 'owner']:
        await JX3PluginControl.finish(message="只有管理员或群主可以控制插件开关")
        return
    
    action = state['_matched'].group(1)
    group_id = str(event.group_id)
    
    if action == "状态":
        status = db.get_plugin_status(PLUGIN_NAME, group_id)
        status_text = "已开启" if status else "已关闭"
        await JX3PluginControl.finish(message=f"剑三助手当前状态：{status_text}")
    elif action == "开启":
        db.set_plugin_status(PLUGIN_NAME, group_id, True)
        await JX3PluginControl.finish(message="剑三助手已开启")
    elif action == "关闭":
        db.set_plugin_status(PLUGIN_NAME, group_id, False)
        await JX3PluginControl.finish(message="剑三助手已关闭")


# 开服检测
OpenServer = on_regex(pattern=r'^(开服|倒闭了)(?:\s+(\S+))?$', priority=1)
@OpenServer.handle()
@check_plugin_enabled
async def handle_server_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    server_name = state['_matched'].group(2) if state['_matched'].group(2) else default_server
    res = api.server_check(server= server_name)
    print(res)
    msg = f"{server_name} {'开服了' if res['status'] == 1 else '维护中'}"
    await OpenServer.finish(message=Message(msg))

# 查看日常
CheckDaily = on_regex(pattern=r'^日常(?:\s+(\S+))?$', priority=1)
@CheckDaily.handle()
@check_plugin_enabled
async def handle_daily(bot: Bot, event: GroupMessageEvent, state: T_State):
    server_name = state['_matched'].group(1) if state['_matched'].group(1) else default_server
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
    server_name = matched.group(1) if matched.group(1) else default_server
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
    server_name = matched.group(1) if matched.group(1) else default_server
    # 第二个捕获组一定是角色名
    role_name = matched.group(2)
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成属性信息，请稍候...")
    
    import traceback

    try:
         res = await async_api.role_attribute(server=server_name, name=role_name)
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
    print(res.get('equipList', []))
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
@check_plugin_enabled
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
@check_plugin_enabled
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
@check_plugin_enabled
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
    image_path = await generate_html_screenshot(html_content, 1600)
    # # 发送图片
    await RoleLuckRecord.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)


# 角色名片
RoleCard = on_regex(pattern=r'^(名片|QQ秀|qq秀)\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@RoleCard.handle()
@check_plugin_enabled
async def handle_role_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(2) if matched.group(2) else default_server
    # 第二个捕获组一定是角色名 
    role_name = matched.group(3)
    try:
        res = await async_api.show_card(server= server_name, name=role_name)
    except:  # 不推荐，但可以捕获所有异常
        await RoleCard.finish(message=f"名片接口调用失败")
        return
    print(res.get('showAvatar'))
    # res = await async_api.request(endpoint="/data/role/online/status", server= server_name, name=role_name)
    await RoleCard.finish(MessageSegment.image(res.get('showAvatar')))

# 沙盘
ServerSand = on_regex(pattern=r'^沙盘(?:\s+(\S+))?', priority=1)
@ServerSand.handle()
@check_plugin_enabled
async def handle_role_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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
    image_path = await generate_html_screenshot(html_content, 1340)
    # # 发送图片
    await ServerSand.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)


# 物价
TradeRecords = on_regex(pattern=r'^物价\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@TradeRecords.handle()
@check_plugin_enabled
async def handle_trade_records(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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

    print('TradeRecords - 物价----', res)
    
    # 生成 HTML 内容
    html_content = render_trade_records_html(res)
    # # 转换为图片
    image_path = await generate_html_screenshot(html_content, 1920)
    # # 发送图片
    await TradeRecords.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)

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
        server_name = default_server
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
    image_path = await generate_html_screenshot(html_content, 1600)
    # # 发送图片
    await RoleAchievement.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)


# 资历分布
DiaryAchievement = on_regex(pattern=r'^资历分布\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@DiaryAchievement.handle()
@check_plugin_enabled
async def handle_diary_achievement(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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
    image_path = await generate_html_screenshot(html_content, 1600)
    # # 发送图片
    await DiaryAchievement.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)


# 招募
MemberRecruit = on_regex(pattern=r'^招募\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@MemberRecruit.handle()
@check_plugin_enabled
async def handle_member_recruit(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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
    image_path = await generate_html_screenshot(html_content, 1600)
    # # 发送图片
    await MemberRecruit.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)


# 交易行
TradingCompany = on_regex(pattern=r'^交易行\s+(?:(\S+)\s+)?(\S+)$', priority=1)
@TradingCompany.handle()
@check_plugin_enabled
async def handle_trading_company(bot: Bot, event: GroupMessageEvent, state: T_State):
    matched = state['_matched']
    # 如果第一个捕获组有值，则它是区服名，否则使用默认区服
    server_name = matched.group(1) if matched.group(1) else default_server
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
    image_path = await generate_html_screenshot(html_content, 1600)
    # # 发送图片
    await TradingCompany.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)

    

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
        image_path = await generate_html_screenshot(html_content, 1920)
       
    except Exception as e:
        print(f"BlackBook 错误: {type(e).__name__}: {str(e)}")
        await BlackBook.finish(f"副本掉落查询失败: {str(e)}")

    # 5. 发送图片
    await BlackBook.finish(MessageSegment.image(path_to_base64(image_path)))
    
    # 清理临时文件
    os.unlink(image_path)
