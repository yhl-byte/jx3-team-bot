'''
Date: 2025-02-18 13:34:16
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 17:21:21
FilePath: /bott/bot-dd/src/plugins/handler.py
'''
# src/plugins/chat_plugin/handler.py
from nonebot import on_message,on_regex,on_command
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.onebot.utils import highlight_rich_message
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message,GroupMessageEvent
from .html_generator import render_html,render_help
from .render_image import html_to_image
from .api import check_default_team_exists, check_enroll, check_member, clear_teams, close_team, del_member, enroll_member, team_info, team_list, create_team, update_team_default, update_team_name,move_member,team_info_by_id
from ..utils.index import find_default_team, find_earliest_team, find_id_by_team_name, format_teams, get_code_by_name, get_info_by_id, path_to_base64, upload_image,render_team_template
from ..utils.jx3_profession import JX3PROFESSION
from ..utils.permission import require_admin_permission
from src.config import STATIC_PATH
import os

# 用于存储每个群的状态
COMMAND_ENABLED = {}

# 添加开关命令处理器
ToggleCommands = on_regex(pattern=r'^年崽\s*(开|关)?$', priority=1)
# 修改开关命令处理器
@ToggleCommands.handle()
async def handle_toggle_commands(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, ToggleCommands):
        return
    
    group_id = event.group_id
    matched = state["_matched"]
    # 获取当前群的状态，默认为开启
    current_status = COMMAND_ENABLED.get(group_id, True)
    status = matched.group(1) if matched.group(1) else ("关" if current_status else "开")
    
    COMMAND_ENABLED[group_id] = status == "开"
    msg = f"年崽已{'开启，欢迎使用！' if COMMAND_ENABLED[group_id] else '关闭，所有命令已被禁用！'}"
    await ToggleCommands.finish(message=Message(msg))

# 修改检查命令状态的函数
async def check_command_enabled(bot: Bot, event: GroupMessageEvent, command: str) -> bool:
    group_id = event.group_id
    if not COMMAND_ENABLED.get(group_id, True):  # 默认为开启状态
        msg = "年崽已关闭，请联系管理员开启"
        await bot.send(event=event, message=Message(msg))
        return False
    return True

# # 开团|创建团队 - 消息处理器
CreatTeam = on_regex(pattern=r'^(创建团队|开团)$',priority=1)
@CreatTeam.handle()
async def handle_team_create(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "创建团队"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    # 获取群内管理员
    admins = await bot.get_group_member_list(group_id=event.group_id)
    # 获取当前发消息用户的 user_id
    user_id = event.user_id
    # 检查用户是否为管理员
    is_admin = any(
        admin["user_id"] == user_id and 
        (admin["role"] in ["admin", "owner"]) 
        for admin in admins
    )
    if not is_admin:
        msg = "您没有权限执行此操作"
        return await CreatTeam.finish(message=Message(msg))
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    if matched:
        # 检查是否存在 team_default 为 1 的团队
        default_team_exists = check_default_team_exists(event.group_id)
        team_default = 0 if default_team_exists else 1
        team_name = f"团队{len(teamList)+1}"
        res = create_team({
            'user_id': event.user_id,
            'group_id': event.group_id,
            'team_name': team_name,
            'team_state': 1,  
            'team_default': team_default, 
        })
        if res == -1:
            return print(f"命令: 开团, 内容: {team_name} - 数据插入失败")
        default_name = default_team_exists.get('team_name') if default_team_exists else team_name
        msg = f"创建团队成功，团队名称为:【 {team_name}】, 编号为{res.get('id')}；\n 当前默认团队为【{default_name}】"
        await CreatTeam.finish(message=Message(msg))
    else:
        await CreatTeam.finish(message=Message("未匹配到有效内容"))

# # 开团|创建团队-有团名 - 消息处理器
CreatTeam = on_regex(pattern=r'^(创建团队|开团)\s+(\S+)',priority=1)
@CreatTeam.handle()
async def handle_team_create(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "创建团队"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    matched = state["_matched"]
    if matched:
        command = matched.group(1)  # “创建团队”或“开团”
        team_name = matched.group(2)     # 空格之后的文字（最多15个字）
        teamInfo = team_info(team_name)
        if teamInfo != None:
            msg = f"团队 '{team_name}' 已存在，不进行新建操作。"
            return  await CreatTeam.finish(message=Message(msg))
        print(f"命令: {command}, 内容: {team_name}")
        # 检查是否存在 team_default 为 1 的团队
        default_team_exists = check_default_team_exists(event.group_id)
        team_default = 0 if default_team_exists else 1
        
        res = create_team({
            'user_id': event.user_id,
            'group_id': event.group_id,
            'team_name': team_name,
            'team_state': 1,  
            'team_default': team_default, 
        })
        if res == -1:
            return print(f"命令: {command}, 内容: {team_name} - 数据插入失败")
        default_name = default_team_exists.get('team_name') if default_team_exists else team_name
        msg = f"创建团队成功，团队名称为:【 {team_name}】, 编号为{res.get('id')}；\n 当前默认团队为【{default_name}】"
        await CreatTeam.finish(message=Message(msg))
    else:
        await CreatTeam.finish(message=Message("未匹配到有效内容"))

# # 修改团名 - 消息处理器
EditTeam = on_regex(pattern=r'^修改团名\s+(\S+)\s+(\S+)',priority=1)
@EditTeam.handle()
async def handle_team_edit(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "修改团名"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    # 从 state 中获取正则匹配的结果
    matched = state["_matched"]
    if matched:
        originName = matched.group(1)  # 原团队名称
        newName = matched.group(2)  # 新团队名称
        update_team_name(newName, originName)
        print(f"命令: 修改团名, 原团队名称: 【{originName}】, 新团队名称: {newName}")
        msg = f"修改团名成功，团队名称: 【{originName}】, 变更为: 【{newName}】"
        await EditTeam.finish(message=Message(msg))
    else:
        await EditTeam.finish(message=Message("未匹配到有效内容"))

# # 修改默认团队 - 消息处理器
SetDefaultTeam = on_regex(pattern=r'^默认团队\s+(\S+)',priority=1)
@SetDefaultTeam.handle()
async def handle_team_default(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "修改默认团队"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    # 从 state 中获取正则匹配的结果
    matched = state["_matched"]
    if matched:
        team_param = matched.group(1)  # 团队ID或名称
        # 尝试将参数转换为数字（ID）
        try:
            team_id = int(team_param)
            team = team_info_by_id(team_id)
            if not team:
                msg = f"未找到ID为【{team_id}】的团队"
                await SetDefaultTeam.finish(message=Message(msg))
            team_name = team.get('team_name')
        except ValueError:
            # 如果转换失败，则按名称处理
            team_name = team_param
            team = team_info(team_name)
            if not team:
                msg = f"未找到名称为【{team_name}】的团队"
                await SetDefaultTeam.finish(message=Message(msg))
        
        res = update_team_default(team_name)
        print(f"命令: 默认团队, 团队名称: 【{team_name}】")
        msg = f"修改默认团队成功，团队名称: 【{team_name}】, 编号为: {res.get('id')}"
        await SetDefaultTeam.finish(message=Message(msg))
    else:
        await SetDefaultTeam.finish(message=Message("未匹配到有效内容"))

# # 结束默认团队 - 消息处理器
CloseDefaultTeam = on_regex(pattern=r'^结束团队$',priority=1)
@CloseDefaultTeam.handle()
async def handle_team_close_default(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "结束默认团队"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    teamList = team_list(event.group_id)
    team = find_default_team(teamList)
    if team:
        res = close_team(team.get("id"))
        if res == -1:
            return print(f"命令: 结束默认团队, 内容: {team.get('team_name')} - 数据删除失败")
        elseTeam = find_earliest_team(teamList,team.get('team_name'))
        if elseTeam:
            update_team_default(elseTeam.get('team_name'))
            msg = f"已结束默认团队，团队名称: 【{team.get('team_name')}】;\n当前默认团队为【{elseTeam.get('team_name')}】,编号为{elseTeam.get('id')}"
            await CloseDefaultTeam.finish(message=Message(msg))
        else:
            msg = f"已结束默认团队，团队名称: 【{team.get('team_name')}】"
            await CloseDefaultTeam.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await CloseDefaultTeam.finish(message=Message(msg))

# # 结束指定团队 - 消息处理器
CloseTeam = on_regex(pattern=r'^结束团队\s+(\S+)',priority=1)
@CloseTeam.handle()
async def handle_team_close(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "结束指定团队"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    teamList = team_list(event.group_id)
    # 从 state 中获取正则匹配的结果
    matched = state["_matched"]
    if matched:
        team_param = matched.group(1)  # 团队ID或名称
        # 尝试将参数转换为数字（ID）
        try:
            team_id = int(team_param)
            team = team_info_by_id(team_id)
            if not team:
                msg = f"未找到ID为【{team_id}】的团队"
                await CloseTeam.finish(message=Message(msg))
            result_id = team_id
            teamName = team.get('team_name')
        except ValueError:
            # 如果转换失败，则按名称处理
            teamName = team_param
            result_id = find_id_by_team_name(teamList, teamName)
            if result_id is None:
                msg = f"未找到名称为【{teamName}】的团队"
                await CloseTeam.finish(message=Message(msg))

        print(f"命令: 结束团队, 团队: {teamName}(ID:{result_id})")
        res = close_team(result_id)
        if res == -1:
            return print(f"命令: 结束指定团队, 内容: {teamName} - 数据删除失败")
        
        elseTeam = find_earliest_team(teamList, teamName)
        if elseTeam:
            update_team_default(elseTeam.get('team_name'))
            msg = f"已结束团队，团队名称: 【{teamName}】;\n当前默认团队为【{elseTeam.get('team_name')}】,编号为{elseTeam.get('id')}"
            await CloseTeam.finish(message=Message(msg))
        
        msg = f"已结束团队，团队名称: 【{teamName}】"
        await CloseTeam.finish(message=Message(msg))
    else:
        await CloseTeam.finish(message=Message("未匹配到有效内容"))

# # 结束全部团队 - 消息处理器
CloseAllTeam = on_regex(pattern=r'^结束全部团队$',priority=1)
@CloseAllTeam.handle()
async def handle_team_close_all(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "结束全部团队"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    res = clear_teams()
    if res == -1:
        return print(f"命令: 结束全部团队, 数据删除失败")
    msg = "已结束全部团队"
    await CloseAllTeam.finish(message=Message(msg))

# # 团队列表 - 消息处理器
TeamList = on_regex(pattern=r'^团队列表$',priority=1)
@TeamList.handle()
async def handle_team_close_all(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "团队列表"):
        return
    list = team_list(event.group_id)
    if not list:
        msg = "当前无团队，请先创建团队"
        await TeamList.finish(message=Message(msg))
    msg = f"{format_teams(list)}"
    await TeamList.finish(message=Message(msg))


#####################################################3

# # 报名 - 团队成员
SignUp = on_regex(pattern=r'^报名\s+(\S+)\s+(\S+)(?:\s+(\d+))?$',priority=1)
@SignUp.handle()
async def handle_sign_up(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(3)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    xf = matched.group(1)  
    role_name = matched.group(2)   
    role_xf = JX3PROFESSION.get_profession(xf)
    xf_id = get_code_by_name(role_xf)
    duty = get_info_by_id(xf_id)['duty']
    if team:
        user = check_enroll(team.get("id"), event.user_id)
        if (len(user) != 0):
            msg = f"您已报名，【{user[0].get('role_name')}】已在团队【{team.get("team_name")}】中"
            await CancelAgentSignUp.finish(message=Message(msg))
        checkSameUser = check_member(team.get("id"), role_name)
        if len(checkSameUser) != 0:
            msg = f"【{checkSameUser[0].get("role_name")}】已在团队中，请勿重复报名"
            await AgentSignUp.finish(message=Message(msg))
        res = enroll_member({
            'user_id': event.user_id,
            'group_id': event.group_id,
            'team_id': team.get("id"),
            'role_name': role_name,
            'role_xf': role_xf,
            'xf_id': xf_id,
            'xf_duty': duty,
        })
        if res == -1:
            return print(f"命令: 报名, 内容: {xf} - {role_name}- 数据插入失败")
        msg = f"{event.sender.nickname} 你输入的 【{role_name}】 加入团队 【{team.get('team_name')}】 成功！"
        await SignUp.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await SignUp.finish(message=Message(msg))

# # 取消报名 - 团队成员
CancelSignUp = on_regex(pattern=r'^取消报名(?:\s+(\d+))?$',priority=1)
@CancelSignUp.handle()
async def handle_cancel(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "取消报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(1)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    if team:
        user = check_enroll(team.get("id"), event.user_id)
        if (len(user) == 0):
            msg = "您还未报名，请先报名"
            await CancelAgentSignUp.finish(message=Message(msg))
        res = del_member(team.get("id"), event.user_id)
        if res == -1:
            return print(f"命令: 取消报名, 删除成员数据失败")
        msg = f"{event.sender.nickname} 您报名的 【{user[0].get('role_name')}】已退出团队 【{team.get('team_name')}】, 祝您三次生活愉快！"
        await CancelSignUp.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await CancelSignUp.finish(message=Message(msg))


# # 代报名 - 团队成员
AgentSignUp = on_regex(pattern=r'^代报名\s+(\S+)\s+(\S+)(?:\s+(\d+))?$',priority=1)
@AgentSignUp.handle()
async def handle_sign_up(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "代报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(3)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    xf = matched.group(1) 
    role_name = matched.group(2)   
    role_xf = JX3PROFESSION.get_profession(xf)
    xf_id = get_code_by_name(role_xf)
    duty = get_info_by_id(xf_id)['duty']
    agent = len(check_enroll(team.get("id"), event.user_id, True)) + 1
    if team:
        checkSameUser = check_member(team.get("id"), role_name)
        if len(checkSameUser) != 0:
            msg = f"【{checkSameUser[0].get("role_name")}】已在团队中，请勿重复报名"
            await AgentSignUp.finish(message=Message(msg))
        res = enroll_member({
            'user_id': event.user_id,
            'group_id': event.group_id,
            'team_id': team.get("id"),
            'role_name': role_name,
            'role_xf': role_xf,
            'xf_id': xf_id,
            'xf_duty': duty,
            'agent': agent,
        })
        if res == -1:
            return print(f"命令: 代报名, 内容: {xf} - {role_name}- 数据插入失败")
        msg = f"{event.sender.nickname} 你输入的 【{role_name}】 加入团队 【{team.get('team_name')}】 成功！"
        await AgentSignUp.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await AgentSignUp.finish(message=Message(msg))

# # 取消代报名 - 团队成员
CancelAgentSignUp = on_regex(pattern=r'^取消代报名(?:\s+(\d+))?$',priority=1)
@CancelAgentSignUp.handle()
async def handle_cancel(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "取消代报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(1)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    agent_users = check_enroll(team.get("id"), event.user_id, True)
    if (len(agent_users) == 0):
        msg = "您未帮助队友进行代报名，请查看团队检查报名记录"
        await CancelAgentSignUp.finish(message=Message(msg))
    if team:
        res = del_member(team.get("id"), event.user_id , agent_users[0].get("agent"))
        if res == -1:
            return print(f"命令: 取消代报名, 删除成员数据失败")
        msg = f"{event.sender.nickname} 您报名的 【{agent_users[0].get('role_name')}】已退出团队 【{team.get('team_name')}】, 祝其三次生活愉快！"
        await CancelAgentSignUp.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await CancelAgentSignUp.finish(message=Message(msg))

# # 取消指定编号代报名 - 团队成员
CancelAgentSignUpById = on_regex(pattern=r'^取消代报名\s+(\d+)(?:\s+(\d+))?$',priority=1)
@CancelAgentSignUpById.handle()
async def handle_cancel_by_id(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "取消指定编号代报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(2)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    agent_code = matched.group(1)
    agent_users = check_enroll(team.get("id"), event.user_id, agent_code)
    if (len(agent_users) == 0):
        msg = f"为找到代号为{agent_code}的成员，请查看团队检查报名记录"
        await CancelAgentSignUpById.finish(message=Message(msg))
    if team:
        res = del_member(team.get("id"), event.user_id , agent_users[0].get("agent"))
        if res == -1:
            return print(f"命令: 取消代报名, 删除成员数据失败")
        msg = f"{event.sender.nickname} 您报名的 【{agent_users[0].get('role_name')}】已退出团队 【{team.get('team_name')}】, 祝其三次生活愉快！"
        await CancelAgentSignUpById.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await CancelAgentSignUpById.finish(message=Message(msg))

# # 开除团员
KickMember = on_regex(pattern=r'^开除团员\s+(\S+)(?:\s+(\d+))?$',priority=1)
@KickMember.handle()
async def handle_kick_member(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "开除团员"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    role_name = state["_matched"][1]
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(2)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    if team:
        user = check_member(team.get("id"), role_name)
        if len(user) == 0:
            msg = f"【{role_name}】不在团队中，请检查"
            await KickMember.finish(message=Message(msg))
        res = del_member(team.get("id"), event.user_id, user[0].get("agent"))
        if res == -1:
            return print(f"命令: 开除团员, 删除成员数据失败")
        msg = f"{event.sender.nickname} 您已开除 【{role_name}】 成员，祝其三次生活愉快！"
        await KickMember.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await KickMember.finish(message=Message(msg))

# # 移动位置
MoveMember = on_regex(pattern=r'^移动位置\s+(\d+)\s+(\d+)(?:\s+(\d+))?$',priority=1)
@MoveMember.handle()
async def handle_move_member(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "移动位置"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        return
    old_index = state["_matched"][1]
    new_index = state["_matched"][2]
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(3)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    if team:
        old_pos = int(old_index)
        new_pos = int(new_index)
        # 检查位置是否在11-55的范围内，且个位数在1-5之间
        if old_pos < 11 or old_pos > 55 or old_pos % 10 == 0 or old_pos % 10 > 5:
            msg = f"【{old_index}】不在团队位置范围内，请检查（位置范围：11-15, 21-25, 31-35, 41-45, 51-55）"
            await MoveMember.finish(message=Message(msg))
        if new_pos < 11 or new_pos > 55 or new_pos % 10 == 0 or new_pos % 10 > 5:
            msg = f"【{new_index}】不在团队位置范围内，请检查（位置范围：11-15, 21-25, 31-35, 41-45, 51-55）"
        res = move_member(team.get("id"), event.user_id, old_index, new_index)
        if res == -1:
            return print(f"命令: 移动位置, 移动成员数据失败")
        msg = f"{event.sender.nickname} 您已将 【{old_index}】 位置成员，移动到 【{new_index}】 位置！"
        await MoveMember.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await MoveMember.finish(message=Message(msg))

# # 查看团队
CheckTeam = on_regex(pattern=r'^查看团队(?:\s+(\d+))?$',priority=1)
@CheckTeam.handle()
async def handle_check_team(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "查看团队"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(1)
    team_info = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    if team_info is None:
        msg = "当前无团队，请先创建团队"
        await CheckTeam.finish(message=Message(msg))
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在获取团队信息，请稍候...")
    memberslist = check_member(team_info.get("id"))
    colors = render_team_template().get("colors_by_mount_name")     
    internal = external = pastor = tank = 0
    for member in memberslist:
       # 获取心法对应的颜色，如果没有则使用默认颜色
        color = colors.get(member.get("role_xf"), "#e8e8e8")
        # 将颜色添加到 member 数据中
        member["color"] = color
        duty = member.get("xf_duty", "未知")
        if duty == "内功":
            internal += 1
        elif duty == "外功":
            external += 1
        elif duty == "治疗":
            pastor += 1
        elif duty == "坦克":
            tank += 1
    
    team_box = {
        **team_info,
       "internal": internal,
       "external": external,
       "pastor": pastor,
       "tank": tank,
       "members": memberslist
    }
    # 生成 HTML 内容
    html_content = render_html(team_box)
    # 转换为图片
    image_path = html_to_image(html_content)
    # # 发送图片
    await CheckTeam.finish(MessageSegment.image(path_to_base64(image_path)))
    # 清理临时文件
    os.unlink(image_path)

# # 随机黑本
RandomBlack = on_regex(pattern=r'^随机黑本(?:\s+(\d+))?$',priority=1)
@RandomBlack.handle()
async def handle_random_black(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "随机黑本"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(1)
    team_info = find_default_team(teamList) if not team_id else team_info_by_id(team_id)
    if team_info is None:
        msg = "当前无团队，请先创建团队"
        await RandomBlack.finish(message=Message(msg))
    
    # 获取当前团队成员列表
    memberslist = check_member(team_info.get("id"))
    if len(memberslist) == 0:
        msg = "当前团队中还没有成员"
        await RandomBlack.finish(message=Message(msg))
    
    # 随机选择一位成员
    import random
    lucky_member = random.choice(memberslist)
    
    msg = f"恭喜【{lucky_member.get('role_name')}】成为本次黑本幸运儿！"
    await RandomBlack.finish(message=Message(msg))

# # 帮助
Help = on_regex(pattern=r'^帮助$',priority=1)
@Help.handle()
async def handle_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "帮助"):
        return
    
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成帮助信息，请稍候...")
    
    # 生成帮助页面内容
    html_content = render_help()
    
    # 转换为图片
    image_path = html_to_image(html_content)
    
    # 发送图片
    await Help.finish(MessageSegment.image(path_to_base64(image_path)))
    
    # 清理临时文件
    os.unlink(image_path)

