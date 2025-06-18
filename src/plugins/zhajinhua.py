from nonebot import on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict, List
from .game_score import update_player_score
import random
import asyncio

# 游戏状态管理
class ZhajinhuaGame:
    def __init__(self):
        self.deck = []  # 牌组
        self.players = {}  # 玩家手牌 {user_id: {"cards": [], "number": int, "bet": int, "folded": bool, "looked": bool}}
        self.current_player = None  # 当前操作的玩家
        self.game_status = 'waiting_signup'  # 游戏状态：waiting_signup, playing, finished
        self.timer = None  # 用于计时的变量
        self.player_order = []  # 玩家顺序
        self.player_count = 0  # 玩家计数（用于分配编号）
        self.pot = 0  # 底池
        self.current_bet = 1  # 当前下注额
        self.round_count = 0  # 轮次计数
        self.max_rounds = 10  # 最大轮次

    def init_deck(self):
        suits = ['♠', '♥', '♣', '♦']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.deck = [(suit, rank) for suit in suits for rank in ranks]
        random.shuffle(self.deck)

    def deal_card(self):
        return self.deck.pop() if self.deck else None

    def get_card_value(self, rank):
        """获取牌的数值，用于比较大小"""
        if rank == 'A':
            return 14
        elif rank == 'K':
            return 13
        elif rank == 'Q':
            return 12
        elif rank == 'J':
            return 11
        else:
            return int(rank)

    def get_hand_type(self, cards):
        """判断牌型：豹子(7) > 顺金(6) > 金花(5) > 顺子(4) > 对子(3) > 单牌(2)"""
        if len(cards) != 3:
            return 0, []
        
        # 按数值排序
        values = sorted([self.get_card_value(card[1]) for card in cards], reverse=True)
        suits = [card[0] for card in cards]
        
        # 豹子（三张相同）
        if values[0] == values[1] == values[2]:
            return 7, values
        
        # 是否同花
        is_flush = len(set(suits)) == 1
        
        # 是否顺子（特殊处理A-2-3）
        is_straight = False
        if values == [14, 3, 2]:  # A-2-3特殊顺子
            is_straight = True
            values = [3, 2, 1]  # 重新排序，A当1
        elif values[0] - values[1] == 1 and values[1] - values[2] == 1:
            is_straight = True
        
        # 顺金（同花顺）
        if is_flush and is_straight:
            return 6, values
        
        # 金花（同花）
        if is_flush:
            return 5, values
        
        # 顺子
        if is_straight:
            return 4, values
        
        # 对子
        if values[0] == values[1] or values[1] == values[2] or values[0] == values[2]:
            if values[0] == values[1]:
                pair_value = values[0]
                single_value = values[2]
            elif values[1] == values[2]:
                pair_value = values[1]
                single_value = values[0]
            else:  # values[0] == values[2]
                pair_value = values[0]
                single_value = values[1]
            return 3, [pair_value, single_value]
        
        # 单牌
        return 2, values

    def compare_hands(self, cards1, cards2):
        """比较两手牌的大小，返回1表示cards1大，-1表示cards2大，0表示相等"""
        type1, values1 = self.get_hand_type(cards1)
        type2, values2 = self.get_hand_type(cards2)
        
        if type1 > type2:
            return 1
        elif type1 < type2:
            return -1
        else:
            # 牌型相同，比较数值
            for v1, v2 in zip(values1, values2):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            return 0

    def get_hand_name(self, cards):
        """获取牌型名称"""
        hand_type, _ = self.get_hand_type(cards)
        names = {
            7: "豹子",
            6: "顺金", 
            5: "金花",
            4: "顺子",
            3: "对子",
            2: "单牌"
        }
        return names.get(hand_type, "未知")

    def format_cards(self, cards):
        return ' '.join([f"{suit}{rank}" for suit, rank in cards])

    def get_active_players(self):
        """获取未弃牌的玩家"""
        return [uid for uid in self.player_order if not self.players[uid]['folded']]

# 存储每个群的游戏实例
games: Dict[int, ZhajinhuaGame] = {}

# 开始炸金花游戏命令
start_game = on_regex(pattern=r"^开始炸金花$", priority=5)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id in games and games[group_id].game_status != 'finished':
        await start_game.finish("游戏已经在进行中！")
        return

    games[group_id] = ZhajinhuaGame()
    game = games[group_id]
    game.init_deck()
    
    await start_game.finish("🎮 炸金花游戏开始！请玩家发送【报名炸金花】进行报名，通过【结束炸金花报名】来结束报名阶段，开始游戏。\n\n⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！")

# 玩家报名
signup = on_regex(pattern=r"^报名炸金花$", priority=5)
@signup.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_signup':
        return
        
    game = games[group_id]
    if user_id in game.players:
        await signup.finish(f"您已经报名过了，您的编号是 {game.players[user_id]['number']}")
        return
    
    if len(game.players) >= 6:  # 限制最多6人
        await signup.finish("报名人数已满（最多6人）！")
        return
    
    game.player_count += 1
    game.players[user_id] = {
        "cards": [], 
        "number": game.player_count, 
        "bet": 0, 
        "folded": False, 
        "looked": False
    }
    game.player_order.append(user_id)
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    # 添加参与游戏基础分
    await update_player_score(str(user_id), str(group_id), 5, 'zhajinhua', None, 'participation')
    msg = (
        MessageSegment.at(user_id) + '\n' + 
        Message(f"【{user_info['nickname']}】报名成功！您的编号是 {game.player_count}")
    )
    await signup.finish(message=Message(msg))

# 结束报名
end_signup = on_regex(pattern=r"^结束炸金花报名$", priority=5)
@end_signup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_signup':
        return
        
    game = games[group_id]
    if len(game.players) < 2:
        await end_signup.finish("报名人数不足，至少需要2人才能开始游戏！")
        return
    
    game.game_status = 'playing'
    msg = "报名结束！开始发牌...\n当前玩家列表：\n"
    for user_id in game.player_order:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        msg += f"编号 {game.players[user_id]['number']}: {user_info['nickname']}\n"
    
    await end_signup.send(msg)
    
    # 给所有玩家发3张牌
    for user_id in game.player_order:
        game.players[user_id]['cards'] = [game.deal_card() for _ in range(3)]
    
    # 每人先下1分底注
    for user_id in game.player_order:
        game.players[user_id]['bet'] = 1
        game.pot += 1
    
    await bot.send_group_msg(group_id=group_id, message=f"发牌完成！每人已下1分底注，当前底池：{game.pot}分\n\n⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！")
    
    # 开始第一轮
    game.current_player = game.player_order[0]
    await show_current_turn(bot, group_id)

async def show_current_turn(bot: Bot, group_id: int):
    """显示当前玩家回合信息"""
    game = games[group_id]
    user_id = game.current_player
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    # 只有已经看过牌的玩家才私聊发送手牌
    if game.players[user_id]['looked']:
        cards = game.players[user_id]['cards']
        hand_name = game.get_hand_name(cards)
        await bot.send_private_msg(
            user_id=user_id,
            message=f"您的手牌：{game.format_cards(cards)} ({hand_name})"
        )
    
    # 群内提示操作
    msg = MessageSegment.at(user_id) + '\n'
    msg += f"轮到玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 操作\n"
    msg += f"当前底池：{game.pot}分，当前下注：{game.current_bet}分\n\n"

    # 显示可开牌的玩家列表
    if len(comparable_players) > 0 and game.players[user_id]['looked']:
        msg += "📋 可开牌的玩家：\n"
        for pid in comparable_players:
            player_info = await bot.get_group_member_info(group_id=group_id, user_id=pid)
            looked_status = "已看牌" if game.players[pid]['looked'] else "未看牌"
            msg += f"  编号 {game.players[pid]['number']}: {player_info['nickname']} ({looked_status})\n"
        msg += "\n"
    
    if game.players[user_id]['looked']:
        msg += "您已看牌，请选择：【跟注】【加注】【开牌 编号】【弃牌】"
    else:
        msg += "您未看牌，请选择：【看牌】【闷跟】【闷加】【弃牌】"
    
    msg += "\n(20秒内未操作将自动弃牌)"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 设置超时
    game.timer = asyncio.create_task(handle_timeout(bot, group_id, user_id, 20))

# 看牌命令
look_cards = on_regex(pattern=r"^看牌$", priority=5)
@look_cards.handle()
async def handle_look_cards(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if game.players[user_id]['looked']:
        await look_cards.finish("您已经看过牌了！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    game.players[user_id]['looked'] = True
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    # 私聊发送手牌
    cards = game.players[user_id]['cards']
    hand_name = game.get_hand_name(cards)
    await bot.send_private_msg(
        user_id=user_id,
        message=f"您的手牌：{game.format_cards(cards)} ({hand_name})"
    )
    
    await bot.send_group_msg(
        group_id=group_id, 
        message=f"玩家 {user_info['nickname']} 看了牌，请选择：【跟注】【加注】【弃牌】"
    )

# 跟注命令
call_bet = on_regex(pattern=r"^跟注$", priority=5)
@call_bet.handle()
async def handle_call_bet(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if not game.players[user_id]['looked']:
        await call_bet.finish("您还没看牌，请先【看牌】或选择【闷跟】！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    bet_amount = game.current_bet
    game.players[user_id]['bet'] += bet_amount
    game.pot += bet_amount
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 跟注 {bet_amount}分，当前底池：{game.pot}分"
    )
    
    await next_player(bot, group_id)

# 闷跟命令
blind_call = on_regex(pattern=r"^闷跟$", priority=5)
@blind_call.handle()
async def handle_blind_call(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if game.players[user_id]['looked']:
        await blind_call.finish("您已经看过牌了，请选择【跟注】！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    bet_amount = game.current_bet // 2  # 闷跟只需要一半
    if bet_amount < 1:
        bet_amount = 1
    
    game.players[user_id]['bet'] += bet_amount
    game.pot += bet_amount
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 闷跟 {bet_amount}分，当前底池：{game.pot}分"
    )
    
    await next_player(bot, group_id)

# 加注命令
raise_bet = on_regex(pattern=r"^加注$", priority=5)
@raise_bet.handle()
async def handle_raise_bet(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if not game.players[user_id]['looked']:
        await raise_bet.finish("您还没看牌，请先【看牌】或选择【闷加】！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    new_bet = game.current_bet * 2
    game.players[user_id]['bet'] += new_bet
    game.pot += new_bet
    game.current_bet = new_bet
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 加注到 {new_bet}分，当前底池：{game.pot}分"
    )
    
    await next_player(bot, group_id)

# 闷加命令
blind_raise = on_regex(pattern=r"^闷加$", priority=5)
@blind_raise.handle()
async def handle_blind_raise(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if game.players[user_id]['looked']:
        await blind_raise.finish("您已经看过牌了，请选择【加注】！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    # new_bet = game.current_bet
    # game.players[user_id]['bet'] += new_bet
    # game.pot += new_bet
    # game.current_bet = new_bet

    bet_amount = game.current_bet
    new_bet = game.current_bet * 2  # 加注后的新下注额
    game.players[user_id]['bet'] += bet_amount
    game.pot += bet_amount
    game.current_bet = new_bet  # 更新当前下注额
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 闷加到 {new_bet}分，当前底池：{game.pot}分"
    )
    
    await next_player(bot, group_id)

# 弃牌命令
fold_cards = on_regex(pattern=r"^弃牌$", priority=5)
@fold_cards.handle()
async def handle_fold_cards(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    game.players[user_id]['folded'] = True
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 弃牌"
    )
    
    # 检查是否只剩一个玩家
    active_players = game.get_active_players()
    if len(active_players) == 1:
        await end_game(bot, group_id)
    else:
        await next_player(bot, group_id)

# 开牌命令
compare_cards = on_regex(pattern=r"^开牌\s*(\d+)$", priority=5)
@compare_cards.handle()
async def handle_compare_cards(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if not game.players[user_id]['looked']:
        await compare_cards.finish("您还没看牌，无法主动开牌！请先【看牌】")
        return
    
    # 解析目标玩家编号
    import re
    match = re.match(r"^开牌\s*(\d+)$", event.get_plaintext())
    if not match:
        await compare_cards.finish("请使用正确格式：开牌 [编号]")
        return
    
    target_number = int(match.group(1))
    
    # 找到目标玩家
    target_user_id = None
    for uid in game.player_order:
        if game.players[uid]['number'] == target_number and not game.players[uid]['folded']:
            target_user_id = uid
            break
    
    if not target_user_id:
        await compare_cards.finish(f"编号 {target_number} 的玩家不存在或已弃牌！")
        return
    
    if target_user_id == user_id:
        await compare_cards.finish("不能与自己开牌！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    # 开牌需要支付当前下注额
    bet_amount = game.current_bet
    game.players[user_id]['bet'] += bet_amount
    game.pot += bet_amount
    
    # 执行比牌
    await execute_compare(bot, group_id, user_id, target_user_id)

async def execute_compare(bot: Bot, group_id: int, player1_id: int, player2_id: int):
    """执行开牌比较"""
    game = games[group_id]
    
    # 发起开牌的玩家支付当前下注金额
    game.players[player1_id]['bet'] += game.current_bet
    game.pot += game.current_bet
    
    # 获取玩家信息
    player1_info = await bot.get_group_member_info(group_id=group_id, user_id=player1_id)
    player2_info = await bot.get_group_member_info(group_id=group_id, user_id=player2_id)
    
    # 获取手牌
    player1_cards = game.players[player1_id]['cards']
    player2_cards = game.players[player2_id]['cards']
    
    # 比较牌型
    result = game.compare_hands(player1_cards, player2_cards)
    
    # 私聊发送牌面信息给两个参与开牌的玩家
    compare_msg = f"🎴 开牌详情：\n\n"
    compare_msg += f"您的手牌：{game.format_cards(player1_cards)} ({game.get_hand_name(player1_cards)})\n"
    compare_msg += f"对手手牌：{game.format_cards(player2_cards)} ({game.get_hand_name(player2_cards)})\n\n"
    
    if result > 0:
        compare_msg += "🎉 您获胜了！"
        await bot.send_private_msg(user_id=player1_id, message=compare_msg)
        
        compare_msg_p2 = f"🎴 开牌详情：\n\n"
        compare_msg_p2 += f"您的手牌：{game.format_cards(player2_cards)} ({game.get_hand_name(player2_cards)})\n"
        compare_msg_p2 += f"对手手牌：{game.format_cards(player1_cards)} ({game.get_hand_name(player1_cards)})\n\n"
        compare_msg_p2 += "😔 您败了！"
        await bot.send_private_msg(user_id=player2_id, message=compare_msg_p2)
    elif result < 0:
        compare_msg += "😔 您败了！"
        await bot.send_private_msg(user_id=player1_id, message=compare_msg)
        
        compare_msg_p2 = f"🎴 开牌详情：\n\n"
        compare_msg_p2 += f"您的手牌：{game.format_cards(player2_cards)} ({game.get_hand_name(player2_cards)})\n"
        compare_msg_p2 += f"对手手牌：{game.format_cards(player1_cards)} ({game.get_hand_name(player1_cards)})\n\n"
        compare_msg_p2 += "🎉 您获胜了！"
        await bot.send_private_msg(user_id=player2_id, message=compare_msg_p2)
    else:
        compare_msg += "🤝 平局！但您是发起方，视为失败"
        await bot.send_private_msg(user_id=player1_id, message=compare_msg)
        
        compare_msg_p2 = f"🎴 开牌详情：\n\n"
        compare_msg_p2 += f"您的手牌：{game.format_cards(player2_cards)} ({game.get_hand_name(player2_cards)})\n"
        compare_msg_p2 += f"对手手牌：{game.format_cards(player1_cards)} ({game.get_hand_name(player1_cards)})\n\n"
        compare_msg_p2 += "🤝 平局！对方是发起方，您获胜"
        await bot.send_private_msg(user_id=player2_id, message=compare_msg_p2)
    
    # 群内只显示开牌结果，不显示具体牌面
    msg = f"🎴 开牌结果：\n\n"
    msg += f"玩家 {player1_info['nickname']} (编号 {game.players[player1_id]['number']}) VS "
    msg += f"玩家 {player2_info['nickname']} (编号 {game.players[player2_id]['number']})\n\n"
    
    if result > 0:
        # player1 赢
        winner_id = player1_id
        loser_id = player2_id
        msg += f"🎉 {player1_info['nickname']} 获胜！"
    elif result < 0:
        # player2 赢
        winner_id = player2_id
        loser_id = player1_id
        msg += f"🎉 {player2_info['nickname']} 获胜！"
    else:
        # 平局，发起开牌的玩家输
        winner_id = player2_id
        loser_id = player1_id
        msg += f"🤝 平局！发起开牌的玩家 {player1_info['nickname']} 视为失败"
    
    msg += "\n\n💡 具体牌面信息已私聊发送给参与开牌的玩家"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 失败的玩家弃牌
    game.players[loser_id]['folded'] = True
    
    # 检查游戏是否结束
    active_players = game.get_active_players()
    if len(active_players) == 1:
        await end_game(bot, group_id)
    else:
        # 如果当前玩家被淘汰，轮到下一个玩家
        if game.current_player == loser_id:
            await next_player(bot, group_id)
        else:
            # 否则继续当前玩家的回合
            await show_current_turn(bot, group_id)

async def next_player(bot: Bot, group_id: int):
    """轮到下一个玩家"""
    game = games[group_id]
    active_players = game.get_active_players()
    
    if len(active_players) <= 1:
        await end_game(bot, group_id)
        return
    
    # 找到下一个未弃牌的玩家
    current_index = game.player_order.index(game.current_player)
    next_index = (current_index + 1) % len(game.player_order)
    
    while game.players[game.player_order[next_index]]['folded']:
        next_index = (next_index + 1) % len(game.player_order)
    
    game.current_player = game.player_order[next_index]
    
    # 检查是否完成一轮
    if game.current_player == active_players[0]:
        game.round_count += 1
        if game.round_count >= game.max_rounds:
            await bot.send_group_msg(group_id=group_id, message="已达到最大轮次，强制开牌！")
            await end_game(bot, group_id)
            return
    
    await show_current_turn(bot, group_id)

async def handle_timeout(bot: Bot, group_id: int, player_id: int, timeout: int):
    """处理玩家操作超时"""
    await asyncio.sleep(timeout)
    game = games.get(group_id)
    
    if game and game.game_status == 'playing' and game.current_player == player_id:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=player_id)
        await bot.send_group_msg(
            group_id=group_id,
            message=f"玩家 {user_info['nickname']} 操作超时，自动弃牌！"
        )
        
        game.players[player_id]['folded'] = True
        
        # 检查是否只剩一个玩家
        active_players = game.get_active_players()
        if len(active_players) == 1:
            await end_game(bot, group_id)
        else:
            await next_player(bot, group_id)

async def end_game(bot: Bot, group_id: int):
    """结束游戏并结算"""
    game = games[group_id]
    game.game_status = 'finished'
    
    active_players = game.get_active_players()
    
    if len(active_players) == 1:
        # 只剩一个玩家，直接获胜
        winner_id = active_players[0]
        winner_info = await bot.get_group_member_info(group_id=group_id, user_id=winner_id)
        
        # 获胜者获得积分
        await update_player_score(str(winner_id), str(group_id), 20, 'zhajinhua', None, 'win')
        
        msg = f"游戏结束！\n获胜者：{winner_info['nickname']} (编号 {game.players[winner_id]['number']})\n"
        msg += f"获得底池：{game.pot}分"
        
    else:
        # 多个玩家比牌
        msg = "游戏结束！开始比牌：\n\n"
        
        # 收集所有未弃牌玩家的牌型
        player_hands = []
        for user_id in active_players:
            cards = game.players[user_id]['cards']
            hand_type, values = game.get_hand_type(cards)
            hand_name = game.get_hand_name(cards)
            user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
            
            player_hands.append({
                'user_id': user_id,
                'cards': cards,
                'hand_type': hand_type,
                'values': values,
                'hand_name': hand_name,
                'nickname': user_info['nickname'],
                'number': game.players[user_id]['number']
            })
        
        # 排序找出获胜者
        player_hands.sort(key=lambda x: (x['hand_type'], x['values']), reverse=True)
        
        # 显示所有玩家的牌
        for i, player in enumerate(player_hands):
            msg += f"{i+1}. {player['nickname']} (编号 {player['number']}): "
            msg += f"{game.format_cards(player['cards'])} ({player['hand_name']})\n"
        
        # 获胜者获得积分
        winner = player_hands[0]
        await update_player_score(str(winner['user_id']), str(group_id), 20, 'zhajinhua', None, 'win')
        
        msg += f"\n🎉 获胜者：{winner['nickname']} 获得底池 {game.pot}分！"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    del games[group_id]

# 强制结束游戏命令
force_end = on_regex(pattern=r"^强制结束炸金花$", priority=5)
@force_end.handle()
async def handle_force_end(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games:
        await force_end.finish("当前没有进行中的炸金花游戏。")
        return
    
    # 检查是否是管理员
    sender = event.sender
    if not (sender.role in ["admin", "owner"]):
        await force_end.finish("只有管理员才能强制结束游戏。")
        return
    
    await bot.send_group_msg(group_id=group_id, message="游戏被管理员强制结束。")
    del games[group_id]

# 炸金花帮助命令
zhajinhua_help = on_regex(pattern=r"^炸金花帮助$", priority=5)
@zhajinhua_help.handle()
async def handle_zhajinhua_help(bot: Bot, event: GroupMessageEvent):
    help_text = """
🎮 炸金花游戏指令说明：
1. 【开始炸金花】：开始一局新的炸金花游戏
2. 【报名炸金花】：参与当前游戏（最多6人）
3. 【结束炸金花报名】：结束报名阶段，开始游戏
4. 【看牌】：查看自己的手牌
5. 【跟注】：跟上当前下注额（看牌后）
6. 【闷跟】：跟注一半金额（未看牌）
7. 【加注】：将下注额翻倍（看牌后）
8. 【闷加】：加注（未看牌）
9. 【开牌 编号】：与指定编号玩家比牌（需看牌）
10. 【弃牌】：放弃本局游戏
11. 【强制结束炸金花】：管理员可强制结束当前游戏

🃏 牌型大小（从大到小）：
1. 豹子：三张相同牌（如：AAA）
2. 顺金：同花顺（如：♠A♠K♠Q）
3. 金花：同花（如：♥A♥5♥3）
4. 顺子：连续三张（如：A23、JQK）
5. 对子：两张相同牌（如：AAK）
6. 单牌：普通牌型

📋 游戏规则：
1. 每人发3张牌，先下1分底注
2. 未看牌时下注金额减半
3. 可以选择看牌或闷牌进行游戏
4. 最后剩余玩家比牌决定胜负
5. 超过10轮自动开牌
6. 20秒内未操作自动弃牌

🏆 积分规则：
- 参与游戏：+5分
- 获胜：+20分

⚠️ 重要提醒：本游戏仅供娱乐，严禁用于赌博等违法活动！
    """
    await zhajinhua_help.finish(help_text)