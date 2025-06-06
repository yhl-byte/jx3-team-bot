'''
Author: yhl
Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-06 10:11:36
FilePath: /team-bot/jx3-team-bot/src/plugins/forbidden_word_game.py
'''
# src/plugins/forbidden_word_game.py
from nonebot import on_regex, on_command, on_message
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message, PrivateMessageEvent
import random
import time
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from .game_score import update_player_score

# 游戏状态
class GameStatus(Enum):
    WAITING = "waiting"    # 等待开始
    SIGNUP = "signup"      # 报名中
    PLAYING = "playing"    # 游戏中
    ENDED = "ended"        # 已结束

@dataclass
class Player:
    user_id: str
    nickname: str
    forbidden_word: str = ""  # 分配给该玩家的禁词
    violation_count: int = 0  # 违规次数（说了自己禁词的次数）
    score: int = -10  # 基础分数20分

@dataclass
class ForbiddenWordGame:
    group_id: str
    status: GameStatus = GameStatus.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    start_time: Optional[float] = None
    game_duration: int = 300  # 5分钟
    game_timer: Optional[asyncio.Task] = None
    used_words: Set[str] = field(default_factory=set)  # 已使用的词汇

# 游戏实例存储
games: Dict[str, ForbiddenWordGame] = {}

# 禁词词库（500个词汇）
FORBIDDEN_WORDS = [
    # 日常用词
    "谢谢", "再见", "晚", "早",  "想",  "说",  "快来",  "落落", 
    "是的", "可以", "好的", "不好", "喜欢",  "想要", 
    "吃饭", "睡觉", "工作", "休息","老三","解散","笑亖","球","秋","季","跑",
    "无聊", "累", "饿", "渴", "困","不","好","报名","OK","欧克","等","结束","你","我","他","她","它",
    "猜词","开口中","猜歌", "21","卧底","看", "听", "说", "想", "做", "玩", "买", "卖", "给", "拿",
    "装备", "装分", "同事", "蛋丁", "帅帅", "一直哭", "一粒蛋", "HR", "hr","潇潇","阿翼","苏打",
    "大佬", "萌新", "bug", "更新", "维护","属性","在线","沙盘",
    "躺平", "摸鱼", "划水", "打工人", "社畜","破防", 
    "副本", "团本", "日常", "周常", "活动", "奇遇", "成就",
    "PVP", "PVE", "DPS", "T", "奶妈", "开荒", "治疗",
    "哈哈", "呵呵", "嘿嘿", "嘻嘻", "哇", "哦", "啊", "嗯", "额", "呃","哈",
    "666", "厉害", "赞", "棒", "强", "弱", "菜","服了",
    "花萝", "818", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "零", "百", "千", "万", "亿", "最后", "倒数","日","然后",
    "手机", "电脑",  "钱",
    "今天", "明天", "昨天", "现在", "以前", "以后", "早上", "中午", "下午", "晚上",
    "家", "学校", "公司",
    "猫", "狗", "鸟", "鱼", "马", "牛", "羊", "猪", "鸡", "鸭",
    "兔", "小强", "蛇",
]

# 开始游戏命令（支持自定义时长）
start_game = on_regex(pattern=r'^开始害你在心口难开(?:\s+(\d+)分钟?)?$', priority=1)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id in games and games[group_id].status != GameStatus.ENDED:
        await start_game.finish(message="当前已有游戏在进行中，请等待结束后再开始新游戏")
        return
    
    # 解析游戏时长
    message_text = str(event.get_message()).strip()
    import re
    match = re.match(r'^开始害你在心口难开(?:\s+(\d+)分钟?)?$', message_text)
    
    game_duration = 300  # 默认5分钟
    if match and match.group(1):
        custom_duration = int(match.group(1))
        if 1 <= custom_duration <= 30:  # 限制1-30分钟
            game_duration = custom_duration * 60
        else:
            await start_game.finish(message="游戏时长必须在1-30分钟之间")
            return
    
    # 创建新游戏
    games[group_id] = ForbiddenWordGame(group_id=group_id, status=GameStatus.SIGNUP, game_duration=game_duration)
    
    duration_text = f"{game_duration // 60}分钟"
    
    msg = "🚫 害你在心口难开游戏开始报名！\n\n"
    msg += "🎮 游戏规则：\n"
    msg += "• 每位玩家会被分配一个禁词\n"
    msg += "• 机器人会私聊告诉你其他人的禁词\n"
    msg += f"• 游戏时间{duration_text}，在群聊中正常聊天\n"
    msg += "• 说了自己禁词的玩家会被扣分\n\n"
    msg += "💰 积分规则：\n"
    msg += "• 基础参与分：-10分\n"
    msg += "• 每说一次自己的禁词：-5分\n\n"
    msg += "📝 发送 '报名害你' 或 '报名禁词' 参加游戏\n"
    msg += "⏰ 300秒后自动开始游戏，或发送 '开始禁词游戏' 立即开始"
    
    await start_game.send(message=msg)
    
    # 30秒后自动开始游戏
    await asyncio.sleep(300)
    if group_id in games and games[group_id].status == GameStatus.SIGNUP:
        await start_playing(bot, group_id)

# 报名命令
signup_game = on_regex(pattern=r'^(报名害你|报名禁词)$', priority=1)
@signup_game.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await signup_game.finish(message="当前没有进行中的害你在心口难开游戏，发送 '开始害你在心口难开' 开始新游戏")
        return
    
    if games[group_id].status != GameStatus.SIGNUP:
        await signup_game.finish(message="当前游戏不在报名阶段")
        return
    
    if user_id in games[group_id].players:
        await signup_game.finish(message="你已经报名了")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('card') or user_info.get('nickname', f"用户{user_id}")
    except:
        nickname = f"用户{user_id}"
    
    # 添加玩家
    games[group_id].players[user_id] = Player(user_id=user_id, nickname=nickname)
    
    player_count = len(games[group_id].players)
    await signup_game.send(message=f"✅ {nickname} 报名成功！当前玩家数：{player_count}人")

# 立即开始游戏命令
start_playing_cmd = on_regex(pattern=r'^结束禁词报名$', priority=1)
@start_playing_cmd.handle()
async def handle_start_playing(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await start_playing_cmd.finish(message="当前没有进行中的害你在心口难开游戏")
        return
    
    if games[group_id].status != GameStatus.SIGNUP:
        await start_playing_cmd.finish(message="当前游戏不在报名阶段")
        return
    
    await start_playing(bot, group_id)

# 开始游戏逻辑
async def start_playing(bot: Bot, group_id: str):
    game = games[group_id]
    
    if len(game.players) < 2:
        await bot.send_group_msg(group_id=int(group_id), message="参与人数不足2人，游戏取消")
        del games[group_id]
        return
    
    # 分配禁词
    available_words = [word for word in FORBIDDEN_WORDS if word not in game.used_words]
    if len(available_words) < len(game.players):
        available_words = FORBIDDEN_WORDS.copy()  # 如果词汇不够，重新使用所有词汇
        game.used_words.clear()
    
    selected_words = random.sample(available_words, len(game.players))
    
    for i, (user_id, player) in enumerate(game.players.items()):
        player.forbidden_word = selected_words[i]
        game.used_words.add(selected_words[i])
    
    # 私聊发送其他人的禁词
    for user_id, player in game.players.items():
        other_players_words = []
        for other_user_id, other_player in game.players.items():
            if other_user_id != user_id:
                other_players_words.append(f"{other_player.nickname}：{other_player.forbidden_word}")
        
        private_msg = "🚫 害你在心口难开 - 其他玩家的禁词：\n\n"
        private_msg += "\n".join(other_players_words)
        # private_msg += f"\n\n⚠️ 你的禁词是：{player.forbidden_word}\n"
        # private_msg += "记住不要在群里说出你的禁词哦！"
        
        try:
            await bot.send_private_msg(user_id=int(user_id), message=private_msg)
        except:
            # 如果私聊失败，在群里提醒
            await bot.send_group_msg(group_id=int(group_id), 
                                   message=f"⚠️ 无法向 {player.nickname} 发送私聊消息，请确保已添加机器人为好友")
    
    # 更新游戏状态
    game.status = GameStatus.PLAYING
    game.start_time = time.time()
    
    # 发送游戏开始消息
    duration_text = f"{game.game_duration // 60}分钟"
    msg = "🎮 害你在心口难开游戏开始！\n\n"
    msg += f"👥 参与玩家：{len(game.players)}人\n"
    msg += f"⏰ 游戏时间：{duration_text}\n\n"
    msg += "📝 已私聊发送其他玩家的禁词\n"
    msg += "💬 现在开始自由聊天，注意不要说出自己的禁词！\n\n"
    msg += "参与玩家：" + "、".join([p.nickname for p in game.players.values()])
    
    await bot.send_group_msg(group_id=int(group_id), message=msg)
    
    # 设置游戏计时器
    game.game_timer = asyncio.create_task(game_timer(bot, group_id))

# 游戏计时器
async def game_timer(bot: Bot, group_id: str):
    if group_id in games:
        await asyncio.sleep(games[group_id].game_duration)  # 使用自定义时长
        if group_id in games and games[group_id].status == GameStatus.PLAYING:
            await end_game(bot, group_id)

# 监听群消息，检测禁词
message_monitor = on_message(priority=10)
@message_monitor.handle()
async def handle_message_monitor(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games or games[group_id].status != GameStatus.PLAYING:
        return
    
    if user_id not in games[group_id].players:
        return
    
    game = games[group_id]
    player = game.players[user_id]
    message_text = str(event.get_message()).strip()
    
    # 检查是否说了自己的禁词
    if player.forbidden_word in message_text:
        player.violation_count += 1
        player.score -= 5
        
        # # 发送提醒消息
        # msg = f"💥 {player.nickname} 说了禁词 '{player.forbidden_word}'！\n"
        # msg += f"扣除5分，当前得分：{player.score}分"
        
        # await bot.send_group_msg(group_id=int(group_id), message=msg)
    # 检查消息字数，超过3个字加1分
    if len(message_text) > 3:
        player.score += 1

# 结束游戏
async def end_game(bot: Bot, group_id: str, reason: str = "游戏时间结束"):
    if group_id not in games:
        return
    
    game = games[group_id]
    game.status = GameStatus.ENDED
    
    if game.game_timer:
        game.game_timer.cancel()
    
    # 计算最终分数并更新数据库
    final_scores = []
    for user_id, player in game.players.items():
        final_score = player.score
        final_scores.append((player, final_score))
        
        # 更新数据库分数
        await update_player_score(
            user_id=user_id,
            group_id=group_id,
            score_change=final_score,
            game_type="害你在心口难开",
            game_result=f"违规{player.violation_count}次"
        )
    
    # 按分数排序
    final_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 发送结算消息
    msg = f"🏁 害你在心口难开游戏结束！\n\n"
    msg += f"📊 {reason}\n\n"
    msg += "🏆 最终排名：\n"
    
    for i, (player, score) in enumerate(final_scores):
        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        msg += f"{rank_emoji} {player.nickname}：{score}分（违规{player.violation_count}次）\n"
    
    msg += "\n📝 禁词公布：\n"
    for player in game.players.values():
        msg += f"{player.nickname}：{player.forbidden_word}\n"
    
    await bot.send_group_msg(group_id=int(group_id), message=msg)
    
    # 清理游戏数据
    del games[group_id]

# 强制结束游戏命令
force_end_game = on_regex(pattern=r'^强制结束禁词$', priority=1)
@force_end_game.handle()
async def handle_force_end_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await force_end_game.finish(message="当前没有进行中的害你在心口难开游戏")
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
            await force_end_game.finish(message="只有管理员才能强制结束游戏")
            return
    except:
        pass  # 如果获取管理员列表失败，允许任何人结束游戏
    
    if games[group_id].status != GameStatus.ENDED:
        await end_game(bot, group_id, "游戏被管理员强制结束")
    else:
        await force_end_game.finish(message="游戏已经结束")

check_game_status = on_regex(pattern=r'^禁词状态$', priority=1)
@check_game_status.handle()
async def handle_game_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await check_game_status.finish(message="当前没有进行中的害你在心口难开游戏")
        return
    
    game = games[group_id]
    status_text = ""
    
    if game.status == GameStatus.WAITING:
        status_text = "等待开始"
    elif game.status == GameStatus.SIGNUP:
        status_text = "报名中"
    elif game.status == GameStatus.PLAYING:
        status_text = "游戏进行中"
    elif game.status == GameStatus.ENDED:
        status_text = "已结束"
    
    player_count = len(game.players)
    
    msg = f"🚫 害你在心口难开状态：{status_text}\n"
    msg += f"👥 玩家数量：{player_count}人\n"
    
    if game.status == GameStatus.PLAYING:
        if game.start_time:
            elapsed = int(time.time() - game.start_time)
            remaining = max(0, game.game_duration - elapsed)
            msg += f"⏰ 剩余时间：{remaining//60}分{remaining%60}秒\n"
        
        # 显示当前分数
        sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
        msg += "\n💰 当前分数：\n"
        for i, player in enumerate(sorted_players):
            msg += f"{i+1}. {player.nickname}：{player.score}分（违规{player.violation_count}次）\n"
    
    await check_game_status.finish(message=msg)

# 设置游戏时长命令
set_game_duration = on_regex(pattern=r'^设置禁词时长\s+(\d+)分钟?$', priority=1)
@set_game_duration.handle()
async def handle_set_duration(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await set_game_duration.finish(message="当前没有进行中的害你在心口难开游戏")
        return
    
    if games[group_id].status != GameStatus.SIGNUP:
        await set_game_duration.finish(message="只能在报名阶段设置游戏时长")
        return
    
    # 解析时长
    message_text = str(event.get_message()).strip()
    import re
    match = re.match(r'^设置禁词时长\s+(\d+)分钟?$', message_text)
    
    if not match:
        await set_game_duration.finish(message="格式错误，请使用：设置禁词时长 X分钟")
        return
    
    duration_minutes = int(match.group(1))
    
    if not (1 <= duration_minutes <= 30):
        await set_game_duration.finish(message="游戏时长必须在1-30分钟之间")
        return
    
    # 更新游戏时长
    games[group_id].game_duration = duration_minutes * 60
    
    await set_game_duration.finish(message=f"✅ 游戏时长已设置为 {duration_minutes} 分钟")

# 私聊查询禁词命令
check_forbidden_words = on_regex(pattern=r'^查询禁词$', priority=1)
@check_forbidden_words.handle()
async def handle_check_forbidden_words(bot: Bot, event: MessageEvent, state: T_State):
    user_id = str(event.user_id)
    
    # 检查是否是私聊
    if not isinstance(event, PrivateMessageEvent):
        return
    
    # 查找用户参与的游戏
    user_game = None
    user_group_id = None
    
    for group_id, game in games.items():
        if user_id in game.players and game.status == GameStatus.PLAYING:
            user_game = game
            user_group_id = group_id
            break
    
    if not user_game:
        await check_forbidden_words.finish(message="你当前没有参与任何进行中的害你在心口难开游戏")
        return
    
    # 获取其他玩家的禁词
    other_players_words = []
    for other_user_id, other_player in user_game.players.items():
        if other_user_id != user_id:
            other_players_words.append(f"{other_player.nickname}：{other_player.forbidden_word}")
    
    if not other_players_words:
        await check_forbidden_words.finish(message="当前游戏中没有其他玩家")
        return
    
    # 发送禁词信息
    player = user_game.players[user_id]
    private_msg = "🚫 害你在心口难开 - 其他玩家的禁词：\n\n"
    private_msg += "\n".join(other_players_words)
    # private_msg += f"\n\n⚠️ 你的禁词是：{player.forbidden_word}\n"
    # private_msg += "记住不要在群里说出你的禁词哦！"
    
    await check_forbidden_words.finish(message=private_msg)

# 害你在心口难开帮助命令
forbidden_help = on_regex(pattern=r'^禁词帮助$', priority=1)
@forbidden_help.handle()
async def handle_forbidden_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    help_msg = """🚫 害你在心口难开指令说明：

🎮 游戏指令：
• 开始害你在心口难开 [X分钟] - 开始新游戏（可选择时长1-30分钟，默认5分钟）
• 报名害你 / 报名禁词 - 报名参加游戏
• 结束禁词报名 - 提前结束报名阶段并开始游戏
• 设置禁词时长 X分钟 - 在报名阶段设置游戏时长
• 禁词状态 - 查看当前游戏状态
• 强制结束禁词 - 强制结束当前游戏（仅管理员）
• 禁词帮助 - 显示此帮助信息

📱 私聊指令：
• 查询禁词 - 私聊机器人查询其他玩家的禁词（适用于无法接收私聊的情况）

🎯 游戏规则：
• 游戏时长：可自定义1-30分钟（默认5分钟）
• 每位玩家会被分配一个禁词
• 机器人会私聊告诉你其他人的禁词
• 在群聊中正常聊天，但不能说出自己的禁词
• 说了自己禁词会被扣分并公开提醒
• 如果无法接收私聊，可以私聊机器人发送"查询禁词"获取信息

💰 积分规则：
• 基础参与分 -10分
• 每说一次自己的禁词：-5分
• 每说一句超过3个字的话：+1分
• 最终得分会记录到个人积分系统

📝 使用示例：
• 开始害你在心口难开 - 开始5分钟游戏
• 开始害你在心口难开 10分钟 - 开始10分钟游戏
• 设置禁词时长 15分钟 - 设置游戏时长为15分钟

🎮 词汇类型：
• 日常用语、网络用语、情感表达
• 剑网三门派、技能、地图、NPC
• 游戏术语、江湖用语等
• 总计700+个词汇供随机分配

📝 游戏技巧：
• 记住其他人的禁词，可以引导他们说出来
• 小心不要说出自己的禁词
• 可以用同义词或谐音来表达意思
• 观察其他人的聊天内容，寻找机会
"""
    await forbidden_help.finish(message=help_msg)