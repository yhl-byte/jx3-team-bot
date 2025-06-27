# src/plugins/werewolf.py
from nonebot import on_regex, on_command, on_message, require
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message, PrivateMessageEvent
from nonebot.permission import SUPERUSER
import random
import time
import asyncio
from typing import Dict, List, Tuple, Set, Optional
from .game_score import update_player_score

# 游戏状态
class WerewolfGameStatus:
    WAITING = 0    # 等待开始
    SIGNUP = 1     # 报名中
    NIGHT = 2      # 夜晚阶段
    DAY = 3        # 白天讨论
    SPEAKING = 4   # 轮流发言阶段
    VOTING = 5     # 投票阶段
    ENDED = 6      # 已结束

# 角色定义
class Role:
    VILLAGER = "村民"      # 普通村民
    WEREWOLF = "狼人"      # 狼人
    SEER = "预言家"        # 预言家
    WITCH = "女巫"         # 女巫
    HUNTER = "猎人"        # 猎人
    GUARD = "守卫"         # 守卫

# 游戏数据
class WerewolfGame:
    def __init__(self, group_id: int):
        self.group_id = group_id
        self.status = WerewolfGameStatus.WAITING
        self.players = {}  # user_id -> {"nickname": str, "role": str, "alive": bool, "code": int}
        self.current_day = 0
        self.werewolves = []  # 狼人列表
        self.night_actions = {}  # 夜晚行动记录
        self.day_speeches = {}  # 白天发言记录
        self.votes = {}  # 投票记录
        self.game_timer = None
        self.witch_poison_used = False  # 女巫毒药是否已使用
        self.witch_antidote_used = False  # 女巫解药是否已使用
        self.guard_last_target = None  # 守卫上次守护的目标
        self.killed_player = None  # 当晚被杀的玩家
        self.saved_player = None  # 当晚被救的玩家
        self.poisoned_player = None  # 当晚被毒的玩家
        self.guarded_player = None  # 当晚被守护的玩家
        self.seer_result = None  # 预言家查验结果
        # 新增发言相关字段
        self.speaking_order = []  # 发言顺序
        self.current_speaker_index = 0  # 当前发言者索引
        self.has_spoken = set()  # 已发言的玩家
        self.speeches = {}  # 记录每个玩家的发言内容 {player_id: speech_content}

# 存储每个群的游戏状态
games: Dict[int, WerewolfGame] = {}

# 角色配置（根据人数分配角色）
def get_role_config(player_count: int) -> List[str]:
    """根据玩家数量返回角色配置"""
    if player_count < 6:
        return None  # 人数不足
    elif player_count == 6:
        return [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]
    elif player_count == 7:
        return [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.WITCH, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]
    elif player_count == 8:
        return [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.WITCH, Role.HUNTER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]
    elif player_count == 9:
        return [Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.WITCH, Role.HUNTER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]
    elif player_count >= 10:
        return [Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]

# 开始游戏命令
StartWerewolf = on_regex(pattern=r'^开始狼人杀$', priority=1)
@StartWerewolf.handle()
async def handle_start_werewolf(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    # 检查是否已有游戏在进行
    if group_id in games and games[group_id].status != WerewolfGameStatus.WAITING and games[group_id].status != WerewolfGameStatus.ENDED:
        await StartWerewolf.finish(message="游戏已经在进行中，请等待当前游戏结束")
        return
    
    # 创建新游戏
    games[group_id] = WerewolfGame(group_id)
    games[group_id].status = WerewolfGameStatus.SIGNUP
    
    await StartWerewolf.finish(message="狼人杀游戏开始报名！请想参加的玩家发送「报名狼人杀」。发送「结束狼人杀报名」开始游戏。\n\n游戏需要6-12人参与，建议8-10人。")
    
    # 300秒后自动结束报名
    await asyncio.sleep(300)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.SIGNUP:
        if len(games[group_id].players) < 6:
            await bot.send_group_msg(group_id=group_id, message="报名人数不足6人，游戏取消")
            del games[group_id]
        else:
            await start_werewolf_game(bot, group_id)

# 报名命令
SignupWerewolf = on_regex(pattern=r'^报名狼人杀$', priority=1)
@SignupWerewolf.handle()
async def handle_signup_werewolf(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != WerewolfGameStatus.SIGNUP:
        await SignupWerewolf.finish(message="当前没有狼人杀游戏正在报名")
        return
    
    if user_id in games[group_id].players:
        await SignupWerewolf.finish(message="你已经报名了")
        return
    
    if len(games[group_id].players) >= 12:
        await SignupWerewolf.finish(message="报名人数已满（最多12人）")
        return
    
    # 添加玩家
    games[group_id].players[user_id] = {
        "nickname": event.sender.nickname,
        "user_id": event.user_id,
        "role": "",
        "alive": True,
        "code": len(games[group_id].players) + 1
    }

    msg = (
        MessageSegment.at(event.user_id) + 
        Message(f"{event.sender.nickname} (编号:{len(games[group_id].players)})报名成功！当前已有 {len(games[group_id].players)} 人报名")
    )
    await SignupWerewolf.finish(message=Message(msg))

# 结束报名命令
EndWerewolfSignup = on_regex(pattern=r'^结束狼人杀报名$', priority=1)
@EndWerewolfSignup.handle()
async def handle_end_werewolf_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games or games[group_id].status != WerewolfGameStatus.SIGNUP:
        await EndWerewolfSignup.finish(message="当前没有狼人杀游戏正在报名")
        return
    
    if len(games[group_id].players) < 6:
        await EndWerewolfSignup.finish(message="报名人数不足6人，无法开始游戏")
        return
    
    await start_werewolf_game(bot, group_id)

# 开始游戏流程
async def start_werewolf_game(bot: Bot, group_id: int):
    game = games[group_id]
    player_count = len(game.players)
    
    # 获取角色配置
    role_config = get_role_config(player_count)
    if not role_config:
        await bot.send_group_msg(group_id=group_id, message="人数配置错误，游戏取消")
        del games[group_id]
        return
    
    # 随机分配角色
    player_ids = list(game.players.keys())
    random.shuffle(player_ids)
    random.shuffle(role_config)
    
    for i, player_id in enumerate(player_ids):
        game.players[player_id]["role"] = role_config[i]
        if role_config[i] == Role.WEREWOLF:
            game.werewolves.append(player_id)
    
    # 发送角色信息
    await send_role_info(bot, group_id)
    
    # 开始第一个夜晚
    game.current_day = 1
    await start_night_phase(bot, group_id)

# 发送角色信息
async def send_role_info(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 发送游戏开始消息
    role_summary = {}
    for player_info in game.players.values():
        role = player_info["role"]
        role_summary[role] = role_summary.get(role, 0) + 1
    
    summary_text = "\n".join([f"{role}: {count}人" for role, count in role_summary.items()])
    await bot.send_group_msg(group_id=group_id, message=f"游戏开始！角色分配如下：\n{summary_text}\n\n我已经私聊告知大家各自的角色，请查看。")
    
    # 私聊发送角色信息
    failed_users = []
    for player_id, player_info in game.players.items():
        role = player_info["role"]
        role_msg = f"你的角色是：{role}\n\n"
        
        if role == Role.WEREWOLF:
            # 告知狼人队友
            werewolf_names = []
            for wid in game.werewolves:
                if wid != player_id:
                    werewolf_names.append(f"{game.players[wid]['code']}号 {game.players[wid]['nickname']}")
            if werewolf_names:
                role_msg += f"你的狼人队友：{', '.join(werewolf_names)}\n\n"
            role_msg += "夜晚阶段请与队友商议杀害目标，然后发送「杀害 玩家编号」"
        elif role == Role.SEER:
            role_msg += "夜晚阶段你可以查验一名玩家的身份，发送「查验 玩家编号」"
        elif role == Role.WITCH:
            role_msg += "夜晚阶段你可以使用药剂：\n- 发送「救人」使用解药救活被杀的玩家\n- 发送「毒杀 玩家编号」使用毒药杀害一名玩家"
        elif role == Role.HUNTER:
            role_msg += "如果你被投票出局或被狼人杀害，可以开枪带走一名玩家，发送「开枪 玩家编号」"
        elif role == Role.GUARD:
            role_msg += "夜晚阶段你可以守护一名玩家，发送「守护 玩家编号」（不能连续两晚守护同一人）"
        else:
            role_msg += "你是普通村民，白天请仔细观察和分析，投票淘汰狼人"
        
        try:
            await bot.send_private_msg(user_id=player_id, message=role_msg)
        except Exception as e:
            print(f"向玩家 {player_id} 发送私聊失败: {e}")
            failed_users.append(player_id)
    
    if failed_users:
        await bot.send_group_msg(group_id=group_id, message="部分玩家无法接收私聊消息。请通过私聊机器人发送「查询角色」来获取你的角色信息。")

# 查询角色命令（私聊）
QueryWerewolfRole = on_regex(pattern=r'^查询角色$', priority=1)
@QueryWerewolfRole.handle()
async def handle_query_werewolf_role(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    
    # 查找用户所在的游戏
    user_game = None
    for group_id, game in games.items():
        if user_id in game.players:
            user_game = game
            break
    
    if not user_game:
        await QueryWerewolfRole.finish(message="你当前没有参加任何狼人杀游戏")
        return
    
    player_info = user_game.players[user_id]
    role = player_info["role"]
    
    role_msg = f"你的角色是：{role}\n\n"
    
    if role == Role.WEREWOLF:
        werewolf_names = []
        for wid in user_game.werewolves:
            if wid != user_id:
                werewolf_names.append(f"{user_game.players[wid]['code']}号 {user_game.players[wid]['nickname']}")
        if werewolf_names:
            role_msg += f"你的狼人队友：{', '.join(werewolf_names)}"
    
    await QueryWerewolfRole.finish(message=role_msg)

# 开始夜晚阶段
async def start_night_phase(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = WerewolfGameStatus.NIGHT
    game.night_actions = {}
    game.killed_player = None
    game.saved_player = None
    game.poisoned_player = None
    game.guarded_player = None
    game.seer_result = None
    
    await bot.send_group_msg(group_id=group_id, message=f"第 {game.current_day} 天，夜晚降临，所有人请闭眼...")
    
    # 按顺序进行各角色行动
    await werewolf_action_phase(bot, group_id)

# 狼人行动阶段
async def werewolf_action_phase(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否有存活的狼人
    alive_werewolves = [wid for wid in game.werewolves if game.players[wid]["alive"]]
    
    if alive_werewolves:
        await bot.send_group_msg(group_id=group_id, message="🐺 狼人请睁眼，狼人请选择要杀害的目标...\n请狼人通过私聊发送「杀害 玩家编号」进行选择\n⏰ 30秒后进入下一阶段")
        
        # 30秒后进入预言家阶段
        if game.game_timer:
            game.game_timer.cancel()
        game.game_timer = asyncio.create_task(werewolf_timer(bot, group_id))
    else:
        # 没有存活狼人，直接进入预言家阶段
        await seer_action_phase(bot, group_id)

# 狼人行动计时器
async def werewolf_timer(bot: Bot, group_id: int):
    await asyncio.sleep(30)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.NIGHT:
        await seer_action_phase(bot, group_id)

# 预言家行动阶段
async def seer_action_phase(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否有存活的预言家
    seer_id = None
    for pid, pinfo in game.players.items():
        if pinfo["role"] == Role.SEER and pinfo["alive"]:
            seer_id = pid
            break
    
    if seer_id:
        await bot.send_group_msg(group_id=group_id, message="🔮 预言家请睁眼，预言家请选择要查验的目标...\n请预言家通过私聊发送「查验 玩家编号」进行选择\n⏰ 20秒后进入下一阶段")
        
        # 20秒后进入女巫阶段
        if game.game_timer:
            game.game_timer.cancel()
        game.game_timer = asyncio.create_task(seer_timer(bot, group_id))
    else:
        # 没有存活预言家，直接进入女巫阶段
        await witch_action_phase(bot, group_id)

# 预言家行动计时器
async def seer_timer(bot: Bot, group_id: int):
    await asyncio.sleep(20)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.NIGHT:
        await witch_action_phase(bot, group_id)

# 女巫行动阶段
async def witch_action_phase(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否有存活的女巫
    witch_id = None
    for pid, pinfo in game.players.items():
        if pinfo["role"] == Role.WITCH and pinfo["alive"]:
            witch_id = pid
            break
    
    if witch_id:
        # 告知女巫今晚的死亡情况
        killed_info = ""
        if game.night_actions.get('werewolf_kill'):
            killed_player = game.players[game.night_actions['werewolf_kill']]
            killed_info = f"今晚 {killed_player['code']}号 {killed_player['nickname']} 被狼人杀害"
        else:
            killed_info = "今晚没有人被狼人杀害"
        
        try:
            await bot.send_private_msg(
                user_id=witch_id,
                message=f"{killed_info}\n\n你可以选择：\n1. 救人：发送「救人」（如果有人被杀且还有解药）\n2. 毒人：发送「毒杀 玩家编号」（如果还有毒药）\n3. 不行动：发送「不行动」"
            )
        except Exception as e:
            print(f"向女巫发送信息失败: {e}")
        
        await bot.send_group_msg(group_id=group_id, message="💊 女巫请睁眼，女巫请选择是否使用药品...\n请女巫通过私聊进行选择\n⏰ 25秒后进入下一阶段")
        
        # 25秒后进入守卫阶段
        if game.game_timer:
            game.game_timer.cancel()
        game.game_timer = asyncio.create_task(witch_timer(bot, group_id))
    else:
        # 没有存活女巫，直接进入守卫阶段
        await guard_action_phase(bot, group_id)

# 女巫行动计时器
async def witch_timer(bot: Bot, group_id: int):
    await asyncio.sleep(25)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.NIGHT:
        await guard_action_phase(bot, group_id)

# 守卫行动阶段
async def guard_action_phase(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否有存活的守卫
    guard_id = None
    for pid, pinfo in game.players.items():
        if pinfo["role"] == Role.GUARD and pinfo["alive"]:
            guard_id = pid
            break
    
    if guard_id:
        await bot.send_group_msg(group_id=group_id, message="🛡️ 守卫请睁眼，守卫请选择要守护的目标...\n请守卫通过私聊发送「守护 玩家编号」进行选择\n⏰ 20秒后夜晚结束")
        
        # 20秒后结束夜晚
        if game.game_timer:
            game.game_timer.cancel()
        game.game_timer = asyncio.create_task(guard_timer(bot, group_id))
    else:
        # 没有存活守卫，直接结束夜晚
        await night_timer(bot, group_id)

# 守卫行动计时器
async def guard_timer(bot: Bot, group_id: int):
    await asyncio.sleep(20)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.NIGHT:
        await process_night_actions(bot, group_id)

# 夜晚计时器
async def night_timer(bot: Bot, group_id: int):
    await asyncio.sleep(5)  # 短暂延迟后处理夜晚结果
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.NIGHT:
        await process_night_actions(bot, group_id)

# 处理夜晚行动
async def process_night_actions(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 处理狼人杀人
    werewolf_target = game.night_actions.get('werewolf_kill')
    if werewolf_target:
        game.killed_player = werewolf_target
    
    # 处理守卫守护
    guard_target = game.night_actions.get('guard_protect')
    if guard_target:
        game.guarded_player = guard_target
    
    # 处理女巫行动
    witch_save = game.night_actions.get('witch_save')
    witch_poison = game.night_actions.get('witch_poison')
    
    if witch_save and game.killed_player:
        game.saved_player = game.killed_player
    
    if witch_poison:
        game.poisoned_player = witch_poison
    
    # 计算最终死亡结果
    dead_players = []
    
    # 被狼人杀害且未被守护且未被女巫救活
    if (game.killed_player and 
        game.killed_player != game.guarded_player and 
        game.killed_player != game.saved_player):
        dead_players.append(game.killed_player)
    
    # 被女巫毒杀
    if game.poisoned_player:
        dead_players.append(game.poisoned_player)
    
    # 标记死亡玩家
    for player_id in dead_players:
        game.players[player_id]["alive"] = False
    
    # 发送夜晚结果
    await announce_night_result(bot, group_id, dead_players)
    
    # 检查游戏是否结束
    if check_game_end(game):
        await end_werewolf_game(bot, group_id)
        return
    
    # 进入白天阶段
    await start_day_phase(bot, group_id)

# 公布夜晚结果
async def announce_night_result(bot: Bot, group_id: int, dead_players: List[int]):
    game = games[group_id]
    
    if not dead_players:
        result_msg = "天亮了，昨晚是平安夜，没有人死亡。"
    else:
        dead_names = []
        for player_id in dead_players:
            player_info = game.players[player_id]
            dead_names.append(f"{player_info['code']}号 {player_info['nickname']}")
        result_msg = f"天亮了，昨晚 {', '.join(dead_names)} 死亡。"
    
    await bot.send_group_msg(group_id=group_id, message=result_msg)

    # 如果猎人在夜晚死亡，触发开枪
    if dead_players:
        for player_id in dead_players:
            if game.players[player_id]["role"] == Role.HUNTER:
                await bot.send_group_msg(group_id=group_id, message="猎人死亡，可以开枪带走一名玩家！请猎人在30秒内发送「开枪 玩家编号」")
                # 等待猎人开枪
                await asyncio.sleep(30)
                break

# 开始白天阶段
async def start_day_phase(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = WerewolfGameStatus.SPEAKING  # 改为发言阶段
    
    # 重置发言相关数据
    game.speeches = {}
    game.has_spoken = set()
    game.current_speaker_index = 0
    
    # 获取存活玩家并随机排序
    alive_players = [pid for pid, pinfo in game.players.items() if pinfo["alive"]]
    random.shuffle(alive_players)
    game.speaking_order = alive_players
    
    # 显示存活玩家和发言顺序
    player_list = []
    for i, player_id in enumerate(alive_players):
        player_info = game.players[player_id]
        player_list.append(f"{i+1}. {player_info['code']}号 {player_info['nickname']}")
    
    order_text = "\n".join(player_list)
    
    await bot.send_group_msg(
        group_id=group_id, 
        message=f"现在是白天发言阶段，请按顺序发言讨论。\n\n发言顺序：\n{order_text}\n\n请使用「观点 内容」格式发言，每人限时60秒。"
    )
    
    # 开始第一个玩家发言
    await start_next_speaker(bot, group_id)

# 开始下一个玩家发言
async def start_next_speaker(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否所有人都已发言
    if game.current_speaker_index >= len(game.speaking_order):
        # 所有人发言完毕，进入投票阶段
        await start_voting_phase(bot, group_id)
        return
    
    # 获取当前发言者
    current_speaker_id = game.speaking_order[game.current_speaker_index]
    current_speaker = game.players[current_speaker_id]
    
    await bot.send_group_msg(
        group_id=group_id,
        message=f"请 {current_speaker['code']}号 {current_speaker['nickname']} 发言，限时60秒。\n发送「观点 内容」或「跳过发言」"
    )
    
    # 设置60秒计时器
    if game.game_timer:
        game.game_timer.cancel()
    game.game_timer = asyncio.create_task(speaking_timer(bot, group_id))

# 发言计时器
async def speaking_timer(bot: Bot, group_id: int):
    await asyncio.sleep(60)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.SPEAKING:
        game = games[group_id]
        current_speaker_id = game.speaking_order[game.current_speaker_index]
        current_speaker = game.players[current_speaker_id]
        
        await bot.send_group_msg(
            group_id=group_id,
            message=f"{current_speaker['code']}号 {current_speaker['nickname']} 发言时间到，自动跳过。"
        )
        
        # 进入下一个发言者
        game.current_speaker_index += 1
        await start_next_speaker(bot, group_id)

# 发言命令
Speech = on_regex(pattern=r'^观点\s+(.+)$', priority=1)
@Speech.handle()
async def handle_speech(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    speech_content = state["_matched"].group(1)
    
    if group_id not in games:
        await Speech.finish(message="当前没有进行中的狼人杀游戏")
        return
    
    game = games[group_id]
    
    if game.status != WerewolfGameStatus.SPEAKING:
        await Speech.finish(message="当前不是发言阶段")
        return
    
    if user_id not in game.players or not game.players[user_id]["alive"]:
        await Speech.finish(message="只有存活的玩家才能发言")
        return
    
    # 检查是否轮到该玩家发言
    current_speaker_id = game.speaking_order[game.current_speaker_index]
    if user_id != current_speaker_id:
        current_speaker = game.players[current_speaker_id]
        await Speech.finish(message=f"请等待 {current_speaker['code']}号 {current_speaker['nickname']} 发言完毕")
        return
    
    # 记录发言
    game.speeches[user_id] = speech_content
    game.has_spoken.add(user_id)
    
    player_info = game.players[user_id]
    await bot.send_group_msg(
        group_id=group_id, 
        message=f"{player_info['code']}号 {player_info['nickname']} 发言：{speech_content}"
    )
    
    # 取消计时器并进入下一个发言者
    if game.game_timer:
        game.game_timer.cancel()
    
    game.current_speaker_index += 1
    await start_next_speaker(bot, group_id)

# 跳过发言命令
SkipSpeech = on_regex(pattern=r'^跳过发言$', priority=1)
@SkipSpeech.handle()
async def handle_skip_speech(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games:
        await SkipSpeech.finish(message="当前没有进行中的狼人杀游戏")
        return
    
    game = games[group_id]
    
    if game.status != WerewolfGameStatus.SPEAKING:
        await SkipSpeech.finish(message="当前不是发言阶段")
        return
    
    if user_id not in game.players or not game.players[user_id]["alive"]:
        await SkipSpeech.finish(message="只有存活的玩家才能发言")
        return
    
    # 检查是否轮到该玩家发言
    current_speaker_id = game.speaking_order[game.current_speaker_index]
    if user_id != current_speaker_id:
        current_speaker = game.players[current_speaker_id]
        await SkipSpeech.finish(message=f"请等待 {current_speaker['code']}号 {current_speaker['nickname']} 发言完毕")
        return
    
    player_info = game.players[user_id]
    await bot.send_group_msg(
        group_id=group_id, 
        message=f"{player_info['code']}号 {player_info['nickname']} 选择跳过发言。"
    )
    
    # 取消计时器并进入下一个发言者
    if game.game_timer:
        game.game_timer.cancel()
    
    game.current_speaker_index += 1
    await start_next_speaker(bot, group_id)


# 开始投票阶段
async def start_voting_phase(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = WerewolfGameStatus.VOTING
    game.votes = {}
    
    # 显示所有玩家的发言记录
    if game.speeches:
        speech_summary = "\n=== 发言记录 ===\n"
        for player_id in game.speaking_order:
            if player_id in game.speeches:
                player_info = game.players[player_id]
                speech_summary += f"{player_info['code']}号 {player_info['nickname']}：{game.speeches[player_id]}\n"
        speech_summary += "\n=== 开始投票 ===\n"
    else:
        speech_summary = "\n=== 开始投票 ===\n"
    
    alive_players = [pinfo for pinfo in game.players.values() if pinfo["alive"]]
    alive_list = "、".join([f"{p['code']}号 {p['nickname']}" for p in alive_players])
    
    vote_msg = f"{speech_summary}存活玩家：{alive_list}\n\n请所有存活玩家在120秒内发送「票 玩家编号」进行投票"
    await bot.send_group_msg(group_id=group_id, message=vote_msg)
    
    # 设置投票计时器
    if game.game_timer:
        game.game_timer.cancel()
    game.game_timer = asyncio.create_task(voting_timer(bot, group_id))

# 投票计时器
async def voting_timer(bot: Bot, group_id: int):
    await asyncio.sleep(60)
    
    if group_id in games and games[group_id].status == WerewolfGameStatus.VOTING:
        await process_voting_result(bot, group_id)

# 夜晚行动命令处理

# 狼人杀人命令（私聊）
WerewolfKill = on_regex(pattern=r'^杀害\s+(\d+)$', priority=1)
@WerewolfKill.handle()
async def handle_werewolf_kill(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    target_code = int(state["_matched"].group(1))
    
    # 查找用户所在的游戏
    user_game = None
    user_group_id = None
    for group_id, game in games.items():
        if (user_id in game.players and 
            game.status == WerewolfGameStatus.NIGHT and 
            game.players[user_id]["role"] == Role.WEREWOLF and
            game.players[user_id]["alive"]):
            user_game = game
            user_group_id = group_id
            break
    
    if not user_game:
        await WerewolfKill.finish(message="当前不是夜晚阶段或你不是存活的狼人")
        return

    # 检查是否已经选择过杀人目标（新增）
    if 'werewolf_kill' in user_game.night_actions:
        current_target = user_game.players[user_game.night_actions['werewolf_kill']]
        await WerewolfKill.finish(message=f"狼人今晚已经选择杀害 {current_target['code']}号 {current_target['nickname']}，不能重复选择！")
        return
    
    # 查找目标玩家
    target_id = None
    for pid, pinfo in user_game.players.items():
        if pinfo["code"] == target_code and pinfo["alive"]:
            target_id = pid
            break
    
    if not target_id:
        await WerewolfKill.finish(message=f"找不到编号为 {target_code} 的存活玩家")
        return
    
    if target_id in user_game.werewolves:
        await WerewolfKill.finish(message="不能杀害狼人队友")
        return
    
    # 记录杀人行动
    user_game.night_actions['werewolf_kill'] = target_id
    target_name = user_game.players[target_id]['nickname']
    
    # 通知所有狼人
    for werewolf_id in user_game.werewolves:
        if user_game.players[werewolf_id]["alive"]:
            try:
                await bot.send_private_msg(
                    user_id=werewolf_id,
                    message=f"狼人决定杀害：{target_code}号 {target_name}"
                )
            except Exception as e:
                print(f"通知狼人失败: {e}")
    
    await WerewolfKill.finish(message=f"已选择杀害 {target_code}号 {target_name}")

# 预言家查验命令（私聊）
SeerCheck = on_regex(pattern=r'^查验\s+(\d+)$', priority=1)
@SeerCheck.handle()
async def handle_seer_check(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    target_code = int(state["_matched"].group(1))
    
    # 查找用户所在的游戏
    user_game = None
    for group_id, game in games.items():
        if (user_id in game.players and 
            game.status == WerewolfGameStatus.NIGHT and 
            game.players[user_id]["role"] == Role.SEER and
            game.players[user_id]["alive"]):
            user_game = game
            break
    
    if not user_game:
        await SeerCheck.finish(message="当前不是夜晚阶段或你不是存活的预言家")
        return

    # 检查是否已经查验过（新增）
    if 'seer_check' in user_game.night_actions:
        await SeerCheck.finish(message="你今晚已经查验过了，每晚只能查验一次！")
        return
    
    # 查找目标玩家
    target_id = None
    for pid, pinfo in user_game.players.items():
        if pinfo["code"] == target_code and pinfo["alive"] and pid != user_id:
            target_id = pid
            break
    
    if not target_id:
        await SeerCheck.finish(message=f"找不到编号为 {target_code} 的其他存活玩家")
        return
    
    # 记录查验行动
    user_game.night_actions['seer_check'] = (user_id, target_id)
    # 立即返回查验结果
    target_info = user_game.players[target_id]
    is_werewolf = target_info["role"] == Role.WEREWOLF
    result_text = "狼人" if is_werewolf else "好人"
    
    await SeerCheck.finish(message=f"查验结果：{target_info['code']}号 {target_info['nickname']} 是 {result_text}")

# 女巫救人命令（私聊）
WitchSave = on_regex(pattern=r'^救人$', priority=1)
@WitchSave.handle()
async def handle_witch_save(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    
    # 查找用户所在的游戏
    user_game = None
    for group_id, game in games.items():
        if (user_id in game.players and 
            game.status == WerewolfGameStatus.NIGHT and 
            game.players[user_id]["role"] == Role.WITCH and
            game.players[user_id]["alive"]):
            user_game = game
            break
    
    if not user_game:
        await WitchSave.finish(message="当前不是夜晚阶段或你不是存活的女巫")
        return
    
    if user_game.witch_antidote_used:
        await WitchSave.finish(message="你的解药已经使用过了")
        return
    
    if not user_game.killed_player:
        await WitchSave.finish(message="今晚没有人被狼人杀害")
        return
    
    # 记录救人行动
    user_game.night_actions['witch_save'] = user_game.killed_player
    user_game.witch_antidote_used = True
    
    killed_name = user_game.players[user_game.killed_player]['nickname']
    await WitchSave.finish(message=f"已使用解药救活 {killed_name}")

# 女巫毒杀命令（私聊）
WitchPoison = on_regex(pattern=r'^毒杀\s+(\d+)$', priority=1)
@WitchPoison.handle()
async def handle_witch_poison(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    target_code = int(state["_matched"].group(1))
    
    # 查找用户所在的游戏
    user_game = None
    for group_id, game in games.items():
        if (user_id in game.players and 
            game.status == WerewolfGameStatus.NIGHT and 
            game.players[user_id]["role"] == Role.WITCH and
            game.players[user_id]["alive"]):
            user_game = game
            break
    
    if not user_game:
        await WitchPoison.finish(message="当前不是夜晚阶段或你不是存活的女巫")
        return
    
    if user_game.witch_poison_used:
        await WitchPoison.finish(message="你的毒药已经使用过了")
        return
    
    # 查找目标玩家
    target_id = None
    for pid, pinfo in user_game.players.items():
        if pinfo["code"] == target_code and pinfo["alive"] and pid != user_id:
            target_id = pid
            break
    
    if not target_id:
        await WitchPoison.finish(message=f"找不到编号为 {target_code} 的其他存活玩家")
        return
    
    # 记录毒杀行动
    user_game.night_actions['witch_poison'] = target_id
    user_game.witch_poison_used = True
    target_name = user_game.players[target_id]['nickname']
    
    await WitchPoison.finish(message=f"已使用毒药毒杀 {target_code}号 {target_name}")

# 守卫守护命令（私聊）
GuardProtect = on_regex(pattern=r'^守护\s+(\d+)$', priority=1)
@GuardProtect.handle()
async def handle_guard_protect(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    target_code = int(state["_matched"].group(1))
    
    # 查找用户所在的游戏
    user_game = None
    for group_id, game in games.items():
        if (user_id in game.players and 
            game.status == WerewolfGameStatus.NIGHT and 
            game.players[user_id]["role"] == Role.GUARD and
            game.players[user_id]["alive"]):
            user_game = game
            break
    
    if not user_game:
        await GuardProtect.finish(message="当前不是夜晚阶段或你不是存活的守卫")
        return
    
    # 查找目标玩家
    target_id = None
    for pid, pinfo in user_game.players.items():
        if pinfo["code"] == target_code and pinfo["alive"]:
            target_id = pid
            break
    
    if not target_id:
        await GuardProtect.finish(message=f"找不到编号为 {target_code} 的存活玩家")
        return
    
    if target_id == user_game.guard_last_target:
        await GuardProtect.finish(message="不能连续两晚守护同一人")
        return
    
    # 记录守护行动
    user_game.night_actions['guard_protect'] = target_id
    user_game.guard_last_target = target_id
    target_name = user_game.players[target_id]['nickname']
    
    await GuardProtect.finish(message=f"已选择守护 {target_code}号 {target_name}")

# 投票命令
WerewolfVote = on_regex(pattern=r'^票\s+(\d+)$', priority=1)
@WerewolfVote.handle()
async def handle_werewolf_vote(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    target_code = int(state["_matched"].group(1))
    
    if group_id not in games or games[group_id].status != WerewolfGameStatus.VOTING:
        await WerewolfVote.finish(message="当前不是投票阶段")
        return
    
    game = games[group_id]
    
    # 检查投票者是否存活
    if user_id not in game.players or not game.players[user_id]["alive"]:
        await WerewolfVote.finish(message="只有存活玩家才能投票")
        return
    
    # 查找目标玩家
    target_id = None
    for pid, pinfo in game.players.items():
        if pinfo["code"] == target_code and pinfo["alive"]:
            target_id = pid
            break
    
    if not target_id:
        await WerewolfVote.finish(message=f"找不到编号为 {target_code} 的存活玩家")
        return
    
    if target_id == user_id:
        await WerewolfVote.finish(message="不能投票给自己")
        return
    
    # 记录投票
    game.votes[user_id] = target_id
    
    voter_name = game.players[user_id]['nickname']
    target_name = game.players[target_id]['nickname']
    
    await WerewolfVote.send(message=f"{voter_name} 投票给了 {target_code}号 {target_name}")
    
    # 检查是否所有存活玩家都已投票
    alive_players = [pid for pid, pinfo in game.players.items() if pinfo["alive"]]
    if all(pid in game.votes for pid in alive_players):
        if game.game_timer:
            game.game_timer.cancel()
        await process_voting_result(bot, group_id)

# 处理投票结果
async def process_voting_result(bot: Bot, group_id: int):
    game = games[group_id]

    if not game.votes:
        await bot.send_group_msg(group_id=group_id, message="没有人投票，进入下一个夜晚")
        game.current_day += 1
        await start_night_phase(bot, group_id)
        return
    
    # 统计投票结果
    vote_count = {}
    for target_id in game.votes.values():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1
    
    if not vote_count:
        await bot.send_group_msg(group_id=group_id, message="没有人投票，进入下一个夜晚")
        game.current_day += 1
        await start_night_phase(bot, group_id)
        return
    
    # 找出得票最多的玩家
    max_votes = max(vote_count.values())
    eliminated_candidates = [pid for pid, votes in vote_count.items() if votes == max_votes]
    
    if len(eliminated_candidates) > 1:
        # 平票，随机选择
        eliminated_player_id = random.choice(eliminated_candidates)
        await bot.send_group_msg(group_id=group_id, message="出现平票，随机选择一人出局")
    else:
        eliminated_player_id = eliminated_candidates[0]
    
    # 标记玩家出局
    game.players[eliminated_player_id]["alive"] = False
    eliminated_player = game.players[eliminated_player_id]
    
    await bot.send_group_msg(
        group_id=group_id, 
        message=f"投票结束，{eliminated_player['code']}号 {eliminated_player['nickname']} 被投票出局！"
    )
    
    # 检查猎人技能
    if eliminated_player["role"] == Role.HUNTER:
        await bot.send_group_msg(group_id=group_id, message="猎人被出局，可以开枪带走一名玩家！请猎人在30秒内发送「开枪 玩家编号」")
        # 等待猎人开枪
        await asyncio.sleep(30)
    
    # 检查游戏是否结束
    if check_game_end(game):
        await end_werewolf_game(bot, group_id)
        return
    
    # 进入下一个夜晚
    game.current_day += 1
    await start_night_phase(bot, group_id)

# 猎人开枪命令
HunterShoot = on_regex(pattern=r'^开枪\s+(\d+)$', priority=1)
@HunterShoot.handle()
async def handle_hunter_shoot(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    target_code = int(state["_matched"].group(1))
    
    if group_id not in games:
        await HunterShoot.finish(message="当前没有进行中的狼人杀游戏")
        return
    
    game = games[group_id]
    
    # 检查是否是猎人且已死亡
    if (user_id not in game.players or 
        game.players[user_id]["role"] != Role.HUNTER or 
        game.players[user_id]["alive"]):
        await HunterShoot.finish(message="只有死亡的猎人才能开枪")
        return
    
    # 查找目标玩家
    target_id = None
    for pid, pinfo in game.players.items():
        if pinfo["code"] == target_code and pinfo["alive"]:
            target_id = pid
            break
    
    if not target_id:
        await HunterShoot.finish(message=f"找不到编号为 {target_code} 的存活玩家")
        return
    
    # 击杀目标
    game.players[target_id]["alive"] = False
    target_player = game.players[target_id]
    
    await bot.send_group_msg(
        group_id=group_id, 
        message=f"猎人开枪带走了 {target_player['code']}号 {target_player['nickname']}！"
    )
    
    # 检查游戏是否结束
    if check_game_end(game):
        await end_werewolf_game(bot, group_id)

# 检查游戏是否结束
def check_game_end(game: WerewolfGame) -> bool:
    alive_werewolves = 0
    alive_villagers = 0
    
    for player_info in game.players.values():
        if player_info["alive"]:
            if player_info["role"] == Role.WEREWOLF:
                alive_werewolves += 1
            else:
                alive_villagers += 1
    
    # 狼人全部死亡，好人胜利
    if alive_werewolves == 0:
        return True
    
    # 狼人数量大于等于好人数量，狼人胜利
    if alive_werewolves >= alive_villagers:
        return True
    
    return False

# 结束游戏
async def end_werewolf_game(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = WerewolfGameStatus.ENDED
    
    # 统计存活情况
    alive_werewolves = 0
    alive_villagers = 0
    
    for player_info in game.players.values():
        if player_info["alive"]:
            if player_info["role"] == Role.WEREWOLF:
                alive_werewolves += 1
            else:
                alive_villagers += 1
    
    # 确定胜利方
    if alive_werewolves == 0:
        winner = "好人阵营"
        # 好人胜利，所有好人+15分
        for player_id, player_info in game.players.items():
            if player_info["role"] != Role.WEREWOLF:
                await update_player_score(
                    str(player_id),
                    str(group_id),
                    15,
                    'werewolf',
                    '好人阵营',
                    'win'
                )
    else:
        winner = "狼人阵营"
        # 狼人胜利，所有狼人+20分
        for player_id, player_info in game.players.items():
            if player_info["role"] == Role.WEREWOLF:
                await update_player_score(
                    str(player_id),
                    str(group_id),
                    20,
                    'werewolf',
                    '狼人阵营',
                    'win'
                )
    
    # 给所有参与者加5分参与奖励
    for player_id in game.players:
        await update_player_score(
            str(player_id),
            str(group_id),
            5,
            'werewolf',
            '参与奖励',
            'participation'
        )
    
    # 生成游戏结果消息
    result_msg = f"游戏结束！{winner}获胜！\n\n玩家身份：\n"
    
    for player_id, player_info in game.players.items():
        status = "存活" if player_info["alive"] else "死亡"
        result_msg += f"{player_info['code']}号 {player_info['nickname']}：{player_info['role']} ({status})\n"
    
    await bot.send_group_msg(group_id=group_id, message=result_msg)
    
    # 清理游戏数据
    if group_id in games:
        del games[group_id]

# 强制结束游戏命令
ForceEndWerewolf = on_regex(pattern=r'^强制结束狼人杀$', priority=1)
@ForceEndWerewolf.handle()
async def handle_force_end_werewolf(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games:
        await ForceEndWerewolf.finish(message="当前没有进行中的狼人杀游戏")
        return
    
    # 检查是否是管理员
    try:
        admins = await bot.get_group_member_list(group_id=event.group_id)
        user_id = event.user_id
        is_admin = any(
            admin["user_id"] == user_id and 
            (admin["role"] in ["admin", "owner"]) 
            for admin in admins
        )
        
        if not is_admin:
            await ForceEndWerewolf.finish(message="只有管理员才能强制结束游戏")
            return
    except:
        pass
    
    if games[group_id].status != WerewolfGameStatus.ENDED:
        await end_werewolf_game(bot, group_id)
    else:
        await ForceEndWerewolf.finish(message="游戏已经结束")

# 查看游戏状态命令
WerewolfStatus = on_regex(pattern=r'^狼人杀状态$', priority=1)
@WerewolfStatus.handle()
async def handle_werewolf_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games:
        await WerewolfStatus.finish(message="当前没有进行中的狼人杀游戏")
        return
    
    game = games[group_id]
    status_text = ""
    
    if game.status == WerewolfGameStatus.WAITING:
        status_text = "等待开始"
    elif game.status == WerewolfGameStatus.SIGNUP:
        status_text = "报名中"
    elif game.status == WerewolfGameStatus.NIGHT:
        status_text = f"第{game.current_day}天夜晚"
    elif game.status == WerewolfGameStatus.DAY:
        status_text = f"第{game.current_day}天白天"
    elif game.status == WerewolfGameStatus.VOTING:
        status_text = f"第{game.current_day}天投票"
    elif game.status == WerewolfGameStatus.ENDED:
        status_text = "已结束"
    
    player_count = len(game.players)
    alive_count = sum(1 for p in game.players.values() if p["alive"])
    
    msg = f"狼人杀游戏状态：{status_text}\n"
    msg += f"玩家数量：{player_count}人，存活：{alive_count}人\n"
    
    if game.status in [WerewolfGameStatus.NIGHT, WerewolfGameStatus.DAY, WerewolfGameStatus.VOTING]:
        msg += "存活玩家：\n"
        for player_id, player_info in game.players.items():
            if player_info["alive"]:
                msg += f"- {player_info['code']}号 {player_info['nickname']}\n"
    
    await WerewolfStatus.finish(message=msg)

# 狼人杀游戏帮助命令
WerewolfHelp = on_regex(pattern=r'^狼人杀帮助$', priority=1)
@WerewolfHelp.handle()
async def handle_werewolf_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    help_msg = """狼人杀游戏指令说明：

【群聊指令】
1. 开始狼人杀 - 开始一局新游戏并进入报名阶段
2. 报名狼人杀 - 报名参加游戏
3. 结束狼人杀报名 - 提前结束报名阶段并开始游戏
4. 票 玩家编号 - 在投票阶段投票淘汰可疑玩家
4. 观点 内容 - 在白天轮流发言
4. 跳过发言 - 玩家选择跳过发言
5. 开枪 玩家编号 - 猎人死亡后开枪带走一名玩家
6. 狼人杀状态 - 查看当前游戏状态
7. 强制结束狼人杀 - 强制结束当前游戏（仅管理员可用）
8. 狼人杀帮助 - 显示此帮助信息

【私聊指令】
1. 查询角色 - 查询自己的角色信息
2. 杀害 玩家编号 - 狼人夜晚杀人
3. 查验 玩家编号 - 预言家夜晚查验身份
4. 救人 - 女巫使用解药救人
5. 毒杀 玩家编号 - 女巫使用毒药杀人
6. 守护 玩家编号 - 守卫夜晚守护玩家

【游戏规则】
- 需要6-12人参与，建议8-10人
- 狼人在夜晚商议杀害一名好人
- 预言家每晚可查验一名玩家身份
- 女巫有一瓶解药和一瓶毒药，各只能使用一次
- 猎人死亡时可开枪带走一名玩家
- 守卫每晚可守护一名玩家，不能连续守护同一人
- 狼人全部出局好人胜利，狼人数量≥好人数量狼人胜利
"""
    await WerewolfHelp.finish(message=help_msg)