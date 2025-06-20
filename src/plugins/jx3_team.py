'''
Date: 2025-02-18 13:34:16
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-20 13:37:08
FilePath: /team-bot/jx3-team-bot/src/plugins/jx3_team.py
'''
# src/plugins/chat_plugin/handler.py
from nonebot import on_message,on_regex,on_command
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.onebot.utils import highlight_rich_message
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message,GroupMessageEvent
from src.utils.html_generator import render_team_html,render_team_help,render_game_help
from src.utils.render_context import render_and_cleanup
from .api import check_default_team_exists, check_enroll, check_member, clear_teams, close_team, del_member, enroll_member, team_info, team_list, create_team, update_team_default, update_team_name,move_member,team_info_by_id,del_member_by_name
from ..utils.index import find_default_team, find_earliest_team, find_id_by_team_name, format_teams, get_code_by_name, get_info_by_id, path_to_base64, upload_image,render_team_template,generate_team_stats
from ..utils.jx3_profession import JX3PROFESSION
from ..utils.permission import require_admin_permission
from src.config import STATIC_PATH
import os
from .database import TeamRecordDB  # 添加数据库导入

# 添加数据库实例
db = TeamRecordDB()
db.init_db()

# # 用于存储每个群的状态
# COMMAND_ENABLED = {}
# 用于存储每个群的报名格式设置 (True: 心法+昵称, False: 昵称+心法)
# SIGNUP_FORMAT = {}

# 修改检查函数
async def check_command_enabled(bot: Bot, event: GroupMessageEvent, command_name: str = None) -> bool:
    """检查开团功能是否启用"""
    group_id = event.group_id
    enabled = db.get_plugin_status("jx3_team", group_id)
    
    if not enabled:
        # await bot.send(event=event, message="开团功能已关闭，请联系管理员开启")
        return False
    return True


# 添加开关命令处理器
ToggleCommands = on_regex(pattern=r'^开团功能\s+(开启|关闭|状态)?$', priority=1)
# 修改开关命令处理器
@ToggleCommands.handle()
async def handle_toggle_commands(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, ToggleCommands):
        return
    
    matched = state["_matched"]
    if matched:
        action = matched.group(1)  # "开" 或 "关"
        group_id = event.group_id
        
        if action == "开启":
            success = db.set_plugin_status("jx3_team", group_id, True)
            if success:
                msg = "开团功能已开启"
            else:
                msg = "开启开团功能失败，请稍后重试"
        elif action == "关闭":
            success = db.set_plugin_status("jx3_team", group_id, False)
            if success:
                msg = "开团功能已关闭"
            else:
                msg = "关闭开团功能失败，请稍后重试"
        else:
            # 查询状态
            enabled = db.get_plugin_status("jx3_team", group_id)
            status = "开启" if enabled else "关闭"
            msg = f"当前开团功能状态：{status}"
        
        await ToggleCommands.finish(message=Message(msg))
    else:
        # 查询状态
        enabled = db.get_plugin_status("jx3_team", group_id)
        status = "开启" if enabled else "关闭"
        msg = f"当前开团功能状态：{status}"
        await ToggleCommands.finish(message=Message(msg))



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

# 设置报名格式命令
SetSignupFormat = on_regex(pattern=r'^设置报名格式\s+(1|2)$', priority=1)
@SetSignupFormat.handle()
async def handle_set_signup_format(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "设置报名格式"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, SetSignupFormat):
        return
    
    matched = state["_matched"]
    if matched:
        format_type = matched.group(1)
        group_id = str(event.group_id)
        
        if format_type == "1":
            success = db.set_signup_format(group_id, True)
            if success:
                msg = "报名格式已设置为：心法 + 昵称（ID）\n示例：报名 花间 余年"
            else:
                msg = "设置报名格式失败，请稍后重试"
        else:  # format_type == "2"
            success = db.set_signup_format(group_id, False)
            if success:
                msg = "报名格式已设置为：昵称（ID）+ 心法\n示例：报名 余年 花间"
            else:
                msg = "设置报名格式失败，请稍后重试"
        
        await SetSignupFormat.finish(message=Message(msg))
    else:
        await SetSignupFormat.finish(message=Message("未匹配到有效内容"))

# 查看报名格式命令
ViewSignupFormat = on_regex(pattern=r'^查看报名格式$', priority=1)
@ViewSignupFormat.handle()
async def handle_view_signup_format(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "查看报名格式"):
        return
    
    group_id = str(event.group_id)
    is_xf_first = db.get_signup_format(group_id)  # 从数据库获取
    
    if is_xf_first:
        msg = "当前报名格式：心法 + 昵称（ID）\n示例：报名 花间 余年"
    else:
        msg = "当前报名格式：昵称（ID）+ 心法\n示例：报名 余年 花间"
    
    await ViewSignupFormat.finish(message=Message(msg))

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

   # 获取当前群的报名格式设置（从数据库）
    group_id = str(event.group_id)
    is_xf_first = db.get_signup_format(group_id)  # 从数据库获取

    if is_xf_first:
        # 心法 + 昵称格式
        xf = matched.group(1)
        role_name = matched.group(2)
    else:
        # 昵称 + 心法格式
        role_name = matched.group(1)
        xf = matched.group(2)
    # xf = matched.group(1)  
    # role_name = matched.group(2)   
    role_xf = JX3PROFESSION.get_profession(xf)
    xf_id = get_code_by_name(role_xf)
    duty = get_info_by_id(xf_id)['duty']
    if team:
        user = check_enroll(team.get("id"), event.user_id)
        if (len(user) != 0):
            msg = f"您已报名，【{user[0].get('role_name')}】已在团队【{team.get("team_name")}】中"
            await SignUp.finish(message=Message(msg))
        checkSameUser = check_member(team.get("id"), role_name)
        if len(checkSameUser) != 0:
            msg = f"【{checkSameUser[0].get("role_name")}】已在团队中，请勿重复报名"
            await SignUp.finish(message=Message(msg))
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
        memberslist = check_member(team.get("id"))
        msg = (
            MessageSegment.at(event.user_id) + 
            Message(f" 「{role_name}」报名成功\n{generate_team_stats(memberslist, team)}")
        )
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
        memberslist = check_member(team.get("id"))
        msg = (
            MessageSegment.at(event.user_id) + 
            Message(f" 「{user[0].get('role_name')}」已退出团队\n{generate_team_stats(memberslist, team)}")
        )
        await CancelSignUp.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await CancelSignUp.finish(message=Message(msg))


# # 代报名 - 团队成员
AgentSignUp = on_regex(pattern=r'^代报名\s+(\S+)\s+(\S+)(?:\s+(\d+))?$',priority=1)
@AgentSignUp.handle()
async def handle_agent_sign_up(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "代报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    team_id = matched.group(3)
    team = find_default_team(teamList) if not team_id else team_info_by_id(team_id)

    # 获取当前群的报名格式设置（从数据库）
    group_id = str(event.group_id)
    is_xf_first = db.get_signup_format(group_id)  # 从数据库获取
    
    if is_xf_first:
        # 心法 + 昵称格式
        xf = matched.group(1)
        role_name = matched.group(2)
    else:
        # 昵称 + 心法格式
        role_name = matched.group(1)
        xf = matched.group(2)

    # xf = matched.group(1) 
    # role_name = matched.group(2)   
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
        memberslist = check_member(team.get("id"))
        msg = (
            MessageSegment.at(event.user_id) + 
            Message(f" 「{role_name}」报名成功\n{generate_team_stats(memberslist, team)}")
        )
        await AgentSignUp.finish(message=Message(msg))
    else:
        msg = "当前无团队，请先创建团队"
        await AgentSignUp.finish(message=Message(msg))

# # 取消代报名 - 团队成员
CancelAgentSignUp = on_regex(pattern=r'^取消代报名(?:\s+(\d+|\S+))?(?:\s+(\d+|\S+))?$',priority=1)
@CancelAgentSignUp.handle()
async def handle_cancel(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "取消代报名"):
        return
    teamList = team_list(event.group_id)
    matched = state["_matched"]
    param1 = matched.group(1)  # 第一个参数：可能是团队ID/名称、代号或角色名
    param2 = matched.group(2)  # 第二个参数：可能是团队ID/名称
    
    # 确定团队
    team = None
    if not param1 and not param2:
        # 情况1：取消代报名
        team = find_default_team(teamList)
    elif param1 and not param2:
        # 情况2：取消代报名 团队名称
        # 情况3：取消代报名 代号
        # 情况4：取消代报名 角色名称
        try:
            team_id = int(param1)
            team = find_default_team(teamList)
        except ValueError:
            # 如果不是数字，则尝试按团队名称查找
            team = team_info(param1)
            if not team:
                # 如果找不到团队，则视为角色名或代号
                team = find_default_team(teamList)
                print(3 )
    else:
        # 情况5：取消代报名 代号 团队名称
        # 情况6：取消代报名 角色名称 团队名称
        try:
            team_id = int(param2)
            team = team_info_by_id(team_id)
        except ValueError:
            team = team_info(param2)
    
    if not team:
        msg = "当前无团队，请先创建团队"
        await CancelAgentSignUp.finish(message=Message(msg))
        return
        
    # 根据不同情况处理取消代报名
    if param1 and param1.isdigit():
        # 按代号取消
        agent_code = int(param1)
        agent_users = check_enroll(team.get("id"), event.user_id, param1)
        if len(agent_users) == 0:
            msg = f"未找到代号为{agent_code}的成员，请查看团队检查报名记录"
            await CancelAgentSignUp.finish(message=Message(msg))
            return
        user_to_cancel = agent_users[0]
    elif param1 and not param1.isdigit():
        # 按角色名取消
        role_name = param1
        agent_users = check_member(team.get("id"), role_name)
        if len(agent_users) == 0:
            msg = f"未找到角色名为「{role_name}」的成员"
            await CancelAgentSignUp.finish(message=Message(msg))
            return
        user_to_cancel = agent_users[0]
    else:
        # 默认取消最近一个代报名
        agent_users = check_enroll(team.get("id"), event.user_id, True)
        if len(agent_users) == 0:
            msg = "您未帮助队友进行代报名，请查看团队检查报名记录"
            await CancelAgentSignUp.finish(message=Message(msg))
            return
        user_to_cancel = agent_users[0]
    
    # 执行取消操作
    res = del_member(team.get("id"), event.user_id, user_to_cancel.get("agent"))
    if res == -1:
        return print(f"命令: 取消代报名, 删除成员数据失败")
    
    memberslist = check_member(team.get("id"))
    msg = (
        MessageSegment.at(event.user_id) + 
        Message(f" 「{user_to_cancel.get('role_name')}」已退出团队\n{generate_team_stats(memberslist, team)}")
    )
    await CancelAgentSignUp.finish(message=Message(msg))


# # 开除团员
KickMember = on_regex(pattern=r'^开除团员\s+(\S+)(?:\s+(\d+))?$',priority=1)
@KickMember.handle()
async def handle_kick_member(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not await check_command_enabled(bot, event, "开除团员"):
        return
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, CreatTeam):
        msg = "仅管理员可以执行此操作"
        await KickMember.finish(message=Message(msg))
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
            return
        res = del_member_by_name(team.get("id"), role_name)
        if res == -1:
            return print(f"命令: 开除团员, 删除成员数据失败")
        memberslist = check_member(team.get("id"))
        msg = (
            MessageSegment.at(event.user_id) + 
            Message(f" 「{role_name}」已退出团队\n{generate_team_stats(memberslist, team)}")
        )
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
       "registered": tank + pastor + external + internal,
       "members": memberslist,
    }
    # 生成 HTML 内容
    html_content = render_team_html(team_box)
    # 转换为图片
    image_path = await render_and_cleanup(html_content, 1160)
    try:
        # 发送图片
        await CheckTeam.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
    

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

# # 开团帮助
Help = on_regex(pattern=r'^开团帮助$',priority=1)
@Help.handle()
async def handle_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    # if not await check_command_enabled(bot, event, "开团帮助"):
    #     return
    
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成开团帮助信息，请稍候...")

    # 生成帮助页面内容
    html_content = render_team_help()

    # 转换为图片
    image_path = await render_and_cleanup(html_content, 960)

    try:
        # 发送图片
        await Help.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
    
    
    


