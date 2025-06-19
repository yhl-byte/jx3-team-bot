from nonebot import on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict, List, Tuple
from .game_score import update_player_score
import random
import asyncio

# 游戏状态管理
class DoudizhuGame:
    def __init__(self):
        self.deck = []  # 牌组
        self.players = {}  # 玩家信息 {user_id: {"cards": [], "number": int, "role": str, "nickname": str}}
        self.landlord = None  # 地主
        self.current_player = None  # 当前出牌玩家
        self.game_status = 'waiting_signup'  # 游戏状态：waiting_signup, bidding, playing, finished
        self.timer = None  # 计时器
        self.player_order = []  # 玩家顺序
        self.player_count = 0  # 玩家计数
        self.landlord_cards = []  # 地主牌（3张底牌）
        self.last_play = None  # 上一次出牌 {"player": user_id, "cards": [], "type": str}
        self.pass_count = 0  # 连续过牌次数
        self.bid_order = []  # 叫地主顺序
        self.current_bidder = None  # 当前叫地主的玩家
        self.bid_score = 0  # 当前叫地主分数
        self.game_multiplier = 1  # 游戏倍数

    def init_deck(self):
        """初始化牌组（54张牌）"""
        suits = ['♠', '♥', '♣', '♦']
        ranks = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
        self.deck = [(suit, rank) for suit in suits for rank in ranks]
        # 添加大小王
        self.deck.append(('', '小王'))
        self.deck.append(('', '大王'))
        random.shuffle(self.deck)

    def get_card_value(self, rank):
        """获取牌的数值（用于比较大小）"""
        values = {
            '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
            'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15, '小王': 16, '大王': 17
        }
        return values.get(rank, 0)

    def sort_cards(self, cards):
        """按牌值排序"""
        return sorted(cards, key=lambda x: self.get_card_value(x[1]))

    def format_cards(self, cards):
        """格式化显示牌"""
        sorted_cards = self.sort_cards(cards)
        return ' '.join([f"{suit}{rank}" if suit else rank for suit, rank in sorted_cards])

    def analyze_cards(self, cards):
        """分析牌型"""
        if not cards:
            return None
            
        card_count = len(cards)
        values = [self.get_card_value(card[1]) for card in cards]
        value_counts = {}
        for value in values:
            value_counts[value] = value_counts.get(value, 0) + 1
        
        # 单牌
        if card_count == 1:
            return {"type": "single", "value": values[0], "length": 1}
        
        # 对子
        if card_count == 2 and len(set(values)) == 1:
            return {"type": "pair", "value": values[0], "length": 1}
        
        # 三张
        if card_count == 3 and len(set(values)) == 1:
            return {"type": "triple", "value": values[0], "length": 1}
        
        # 三带一
        if card_count == 4:
            for value, count in value_counts.items():
                if count == 3:
                    return {"type": "triple_single", "value": value, "length": 1}
        
        # 三带二
        if card_count == 5:
            triple_value = None
            pair_value = None
            for value, count in value_counts.items():
                if count == 3:
                    triple_value = value
                elif count == 2:
                    pair_value = value
            if triple_value and pair_value:
                return {"type": "triple_pair", "value": triple_value, "length": 1}
        
        # 顺子（至少5张）
        if card_count >= 5:
            sorted_values = sorted(set(values))
            if len(sorted_values) == card_count and sorted_values[-1] - sorted_values[0] == card_count - 1:
                # 不能包含2和王
                if all(v < 15 for v in sorted_values):
                    return {"type": "straight", "value": sorted_values[0], "length": card_count}
        
        # 连对（至少3对）
        if card_count >= 6 and card_count % 2 == 0:
            pairs = [value for value, count in value_counts.items() if count == 2]
            if len(pairs) == card_count // 2:
                pairs.sort()
                if pairs[-1] - pairs[0] == len(pairs) - 1 and all(v < 15 for v in pairs):
                    return {"type": "straight_pairs", "value": pairs[0], "length": len(pairs)}
        
        # 飞机（连续的三张）
        triples = [value for value, count in value_counts.items() if count == 3]
        if len(triples) >= 2:
            triples.sort()
            # 检查是否连续
            consecutive_count = 1
            for i in range(1, len(triples)):
                if triples[i] - triples[i-1] == 1:
                    consecutive_count += 1
                else:
                    break
            
            if consecutive_count >= 2:
                remaining_cards = card_count - consecutive_count * 3
                if remaining_cards == 0:
                    return {"type": "airplane", "value": triples[0], "length": consecutive_count}
                elif remaining_cards == consecutive_count:
                    return {"type": "airplane_single", "value": triples[0], "length": consecutive_count}
                elif remaining_cards == consecutive_count * 2:
                    return {"type": "airplane_pair", "value": triples[0], "length": consecutive_count}
        
        # 四带二
        if card_count == 6 or card_count == 8:
            quad_value = None
            for value, count in value_counts.items():
                if count == 4:
                    quad_value = value
                    break
            if quad_value:
                if card_count == 6:
                    return {"type": "quad_single", "value": quad_value, "length": 1}
                else:
                    return {"type": "quad_pair", "value": quad_value, "length": 1}
        
        # 王炸
        if card_count == 2 and 16 in values and 17 in values:
            return {"type": "rocket", "value": 17, "length": 1}
        
        # 炸弹
        if card_count == 4 and len(set(values)) == 1:
            return {"type": "bomb", "value": values[0], "length": 1}
        
        return None

    def can_beat(self, cards1, cards2):
        """判断cards1是否能压过cards2"""
        if not cards2:  # 首次出牌
            return True
            
        type1 = self.analyze_cards(cards1)
        type2 = self.analyze_cards(cards2)
        
        if not type1 or not type2:
            return False
        
        # 王炸最大
        if type1["type"] == "rocket":
            return True
        if type2["type"] == "rocket":
            return False
        
        # 炸弹大于非炸弹
        if type1["type"] == "bomb" and type2["type"] != "bomb":
            return True
        if type2["type"] == "bomb" and type1["type"] != "bomb":
            return False
        
        # 同类型比较
        if type1["type"] == type2["type"] and type1["length"] == type2["length"]:
            return type1["value"] > type2["value"]
        
        return False

    def get_card_type_name(self, cards):
        """获取牌型名称"""
        card_type = self.analyze_cards(cards)
        if not card_type:
            return "无效牌型"
        
        type_names = {
            "single": "单牌",
            "pair": "对子",
            "triple": "三张",
            "triple_single": "三带一",
            "triple_pair": "三带二",
            "straight": "顺子",
            "straight_pairs": "连对",
            "airplane": "飞机",
            "airplane_single": "飞机带单牌",
            "airplane_pair": "飞机带对子",
            "quad_single": "四带二单牌",
            "quad_pair": "四带二对子",
            "bomb": "炸弹",
            "rocket": "王炸"
        }
        return type_names.get(card_type["type"], "未知牌型")

# 存储每个群的游戏实例
games: Dict[int, DoudizhuGame] = {}

# 开始斗地主游戏命令
start_game = on_regex(pattern=r"^开始斗地主$", priority=5)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id in games and games[group_id].game_status != 'finished':
        await start_game.finish("游戏已经在进行中！")
        return

    games[group_id] = DoudizhuGame()
    game = games[group_id]
    game.init_deck()
    
    await start_game.finish("🎮 斗地主游戏开始！请玩家发送【报名斗地主】进行报名，需要3人参与。\n\n⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！")

# 玩家报名
signup = on_regex(pattern=r"^报名斗地主$", priority=5)
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
    
    if len(game.players) >= 3:  # 斗地主需要3人
        await signup.finish("报名人数已满（需要3人）！")
        return
    
    game.player_count += 1
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    game.players[user_id] = {
        "cards": [], 
        "number": game.player_count, 
        "role": "farmer",
        "nickname": user_info['nickname']
    }
    game.player_order.append(user_id)
    
    # 添加参与游戏基础分
    await update_player_score(str(user_id), str(group_id), 5, 'doudizhu', None, 'participation')
    
    msg = (
        MessageSegment.at(user_id) + '\n' + 
        Message(f"【{user_info['nickname']}】报名成功！您的编号是 {game.player_count}")
    )
    
    if len(game.players) == 3:
        await signup.send(message=Message(msg))
        await start_dealing(bot, group_id)
    else:
        await signup.finish(message=Message(msg))

async def start_dealing(bot: Bot, group_id: int):
    """开始发牌和叫地主"""
    game = games[group_id]
    game.game_status = 'bidding'
    
    # 发牌：每人17张，留3张作为地主牌
    for i in range(17):
        for user_id in game.player_order:
            game.players[user_id]['cards'].append(game.deck.pop())
    
    # 剩余3张作为地主牌
    game.landlord_cards = [game.deck.pop() for _ in range(3)]
    
    # 给每个玩家私聊发送手牌
    for user_id in game.player_order:
        cards = game.players[user_id]['cards']
        await bot.send_private_msg(
            user_id=user_id,
            message=f"您的手牌：\n{game.format_cards(cards)}"
        )
    
    await bot.send_group_msg(
        group_id=group_id, 
        message="发牌完成！开始叫地主阶段...\n\n⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！"
    )
    
    # 开始叫地主（从第一个玩家开始）
    game.bid_order = game.player_order.copy()
    game.current_bidder = game.bid_order[0]
    await show_bid_turn(bot, group_id)

async def show_bid_turn(bot: Bot, group_id: int):
    """显示当前叫地主回合"""
    game = games[group_id]
    user_id = game.current_bidder
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    msg = MessageSegment.at(user_id) + '\n'
    msg += f"轮到玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 叫地主\n"
    msg += f"当前叫地主分数：{game.bid_score}分\n"
    msg += "请选择：【叫地主 1】【叫地主 2】【叫地主 3】【不叫】\n"
    msg += "(20秒内未操作将自动不叫)"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 设置超时
    game.timer = asyncio.create_task(handle_bid_timeout(bot, group_id, user_id, 20))

# 叫地主命令
bid_landlord = on_regex(pattern=r"^叫地主\s*([123])$", priority=5)
@bid_landlord.handle()
async def handle_bid_landlord(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'bidding':
        return
        
    game = games[group_id]
    if user_id != game.current_bidder:
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    bid_score = int(event.get_plaintext().split()[-1])
    
    if bid_score <= game.bid_score:
        await bid_landlord.finish(f"叫地主分数必须大于当前分数 {game.bid_score}")
        return
    
    game.bid_score = bid_score
    game.landlord = user_id
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 叫地主 {bid_score}分！"
    )
    
    # 继续下一个玩家叫地主
    await next_bidder(bot, group_id)

# 不叫地主命令
pass_bid = on_regex(pattern=r"^不叫$", priority=5)
@pass_bid.handle()
async def handle_pass_bid(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'bidding':
        return
        
    game = games[group_id]
    if user_id != game.current_bidder:
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 不叫"
    )
    
    await next_bidder(bot, group_id)

async def next_bidder(bot: Bot, group_id: int):
    """下一个叫地主的玩家"""
    game = games[group_id]
    
    # 找到下一个玩家
    current_index = game.bid_order.index(game.current_bidder)
    next_index = (current_index + 1) % len(game.bid_order)
    
    # 如果回到地主或者已经有人叫了3分，结束叫地主阶段
    if (game.landlord and game.bid_order[next_index] == game.landlord) or game.bid_score >= 3:
        await start_playing(bot, group_id)
        return
    
    # 如果所有人都不叫，重新开始
    if not game.landlord and next_index == 0:
        await bot.send_group_msg(
            group_id=group_id,
            message="所有人都不叫地主，游戏结束！"
        )
        del games[group_id]
        return
    
    game.current_bidder = game.bid_order[next_index]
    await show_bid_turn(bot, group_id)

async def handle_bid_timeout(bot: Bot, group_id: int, player_id: int, timeout: int):
    """处理叫地主超时"""
    await asyncio.sleep(timeout)
    game = games.get(group_id)
    
    if game and game.game_status == 'bidding' and game.current_bidder == player_id:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=player_id)
        await bot.send_group_msg(
            group_id=group_id,
            message=f"玩家 {user_info['nickname']} 叫地主超时，自动不叫！"
        )
        await next_bidder(bot, group_id)

async def start_playing(bot: Bot, group_id: int):
    """开始游戏阶段"""
    game = games[group_id]
    game.game_status = 'playing'
    
    if not game.landlord:
        await bot.send_group_msg(
            group_id=group_id,
            message="没有人叫地主，游戏结束！"
        )
        del games[group_id]
        return
    
    # 设置角色
    for user_id in game.player_order:
        if user_id == game.landlord:
            game.players[user_id]['role'] = 'landlord'
        else:
            game.players[user_id]['role'] = 'farmer'
    
    # 地主获得底牌
    game.players[game.landlord]['cards'].extend(game.landlord_cards)
    
    # 发送地主底牌信息
    landlord_info = await bot.get_group_member_info(group_id=group_id, user_id=game.landlord)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"🎉 地主是：{landlord_info['nickname']}\n底牌：{game.format_cards(game.landlord_cards)}"
    )
    
    # 私聊发送地主的完整手牌
    landlord_cards = game.players[game.landlord]['cards']
    await bot.send_private_msg(
        user_id=game.landlord,
        message=f"您是地主！您的完整手牌：\n{game.format_cards(landlord_cards)}"
    )
    
    # 地主先出牌
    game.current_player = game.landlord
    await show_play_turn(bot, group_id)

async def show_play_turn(bot: Bot, group_id: int):
    """显示当前出牌回合"""
    game = games[group_id]
    user_id = game.current_player
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    msg = MessageSegment.at(user_id) + '\n'
    msg += f"轮到玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 出牌\n"
    
    if game.last_play:
        last_player_info = await bot.get_group_member_info(group_id=group_id, user_id=game.last_play['player'])
        msg += f"上家 {last_player_info['nickname']} 出牌：{game.format_cards(game.last_play['cards'])} ({game.get_card_type_name(game.last_play['cards'])})\n"
        msg += "请选择：【出牌 牌面】【要不起】\n"
    else:
        msg += "首次出牌，请选择：【出牌 牌面】\n"
    
    msg += "(30秒内未操作将自动要不起)\n"
    msg += "\n💡 出牌格式：出牌 ♠3 ♥4 ♣5（用空格分隔）或 出牌 345（简化格式）"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 私聊发送最优解提示
    if game.last_play:
        suggestions = get_play_suggestions(game, user_id)
        if suggestions:
            await bot.send_private_msg(
                user_id=user_id,
                message=f"💡 出牌建议：{suggestions}"
            )
    else:
        # 首次出牌建议
        suggestions = get_first_play_suggestions(game, user_id)
        if suggestions:
            await bot.send_private_msg(
                user_id=user_id,
                message=f"💡 出牌建议：{suggestions}"
            )
    
    # 设置超时
    game.timer = asyncio.create_task(handle_play_timeout(bot, group_id, user_id, 30))

def get_play_suggestions(game: DoudizhuGame, user_id: int) -> str:
    """获取出牌建议"""
    player_cards = game.players[user_id]['cards']
    last_play_cards = game.last_play['cards']
    last_play_type = game.last_play['type']
    
    suggestions = []
    
    # 根据上家牌型寻找能压过的牌
    if last_play_type['type'] == 'single':
        # 寻找更大的单牌
        for card in player_cards:
            if game.can_beat([card], last_play_cards):
                suggestions.append(game.format_cards([card]))
                break
    elif last_play_type['type'] == 'pair':
        # 寻找更大的对子
        card_counts = {}
        for card in player_cards:
            rank = card[1]
            if rank not in card_counts:
                card_counts[rank] = []
            card_counts[rank].append(card)
        
        for rank, cards in card_counts.items():
            if len(cards) >= 2:
                pair = cards[:2]
                if game.can_beat(pair, last_play_cards):
                    suggestions.append(game.format_cards(pair))
                    break
    
    # 检查是否有炸弹
    card_counts = {}
    for card in player_cards:
        rank = card[1]
        if rank not in card_counts:
            card_counts[rank] = []
        card_counts[rank].append(card)
    
    for rank, cards in card_counts.items():
        if len(cards) == 4:
            suggestions.append(f"炸弹: {game.format_cards(cards)}")
            break
    
    # 检查王炸
    has_big_joker = any(card[1] == '大王' for card in player_cards)
    has_small_joker = any(card[1] == '小王' for card in player_cards)
    if has_big_joker and has_small_joker:
        jokers = [card for card in player_cards if card[1] in ['大王', '小王']]
        suggestions.append(f"王炸: {game.format_cards(jokers)}")
    
    return " | ".join(suggestions[:3])  # 最多显示3个建议

def get_first_play_suggestions(game: DoudizhuGame, user_id: int) -> str:
    """获取首次出牌建议"""
    player_cards = game.players[user_id]['cards']
    suggestions = []
    
    # 建议出最小的单牌
    smallest_card = min(player_cards, key=lambda x: game.get_card_value(x[1]))
    suggestions.append(f"单牌: {game.format_cards([smallest_card])}")
    
    # 寻找顺子
    values = [game.get_card_value(card[1]) for card in player_cards if game.get_card_value(card[1]) < 15]
    values = sorted(set(values))
    
    for i in range(len(values) - 4):
        if values[i+4] - values[i] == 4:  # 找到5张连续的牌
            straight_cards = []
            for j in range(5):
                target_value = values[i] + j
                for card in player_cards:
                    if game.get_card_value(card[1]) == target_value:
                        straight_cards.append(card)
                        break
            if len(straight_cards) == 5:
                suggestions.append(f"顺子: {game.format_cards(straight_cards)}")
                break
    
    return " | ".join(suggestions[:2])

# 出牌命令
play_cards = on_regex(pattern=r"^出牌\s+(.+)$", priority=5)
@play_cards.handle()
async def handle_play_cards(bot: Bot, event: GroupMessageEvent):
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
    
    # 解析出牌
    card_text = event.get_plaintext().split("出牌", 1)[1].strip()
    try:
        played_cards = parse_cards(card_text)
    except:
        await play_cards.finish("牌面格式错误！请使用格式：出牌 ♠3 ♥4 ♣5")
        return
    
    # 检查玩家是否有这些牌
    player_cards = game.players[user_id]['cards']
    for card in played_cards:
        if card not in player_cards:
            await play_cards.finish(f"您没有 {card[0]}{card[1]} 这张牌！")
            return
    
    # 检查牌型是否有效
    card_type = game.analyze_cards(played_cards)
    if not card_type:
        await play_cards.finish("无效的牌型！")
        return
    
    # 检查是否能压过上家
    if game.last_play and not game.can_beat(played_cards, game.last_play['cards']):
        await play_cards.finish("您的牌压不过上家！")
        return
    
    # 出牌成功
    for card in played_cards:
        player_cards.remove(card)
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    game.last_play = {
        "player": user_id,
        "cards": played_cards,
        "type": card_type
    }
    game.pass_count = 0
    
    msg = f"玩家 {user_info['nickname']} 出牌：{game.format_cards(played_cards)} ({game.get_card_type_name(played_cards)})\n"
    msg += f"剩余手牌：{len(player_cards)}张"
    
    await bot.send_group_msg(group_id=group_id, message=msg)

     # 私聊发送剩余手牌
    if len(player_cards) > 0:
        await bot.send_private_msg(
            user_id=user_id,
            message=f"您的剩余手牌：\n{game.format_cards(player_cards)}"
        )
    
    # 检查是否获胜
    if len(player_cards) == 0:
        await end_game(bot, group_id, user_id)
        return
    
    # 下一个玩家
    await next_player(bot, group_id)

# 要不起命令
pass_play = on_regex(pattern=r"^要不起$", priority=5)
@pass_play.handle()
async def handle_pass_play(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    # 首次出牌不能要不起
    if not game.last_play:
        await pass_play.finish("首次出牌不能要不起！")
        return
    
    # 取消超时计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await bot.send_group_msg(
        group_id=group_id,
        message=f"玩家 {user_info['nickname']} 要不起"
    )
    
    game.pass_count += 1
    
    # 如果连续两个人要不起，清空上次出牌
    if game.pass_count >= 2:
        game.last_play = None
        game.pass_count = 0
    
    await next_player(bot, group_id)

async def next_player(bot: Bot, group_id: int):
    """下一个玩家出牌"""
    game = games[group_id]
    
    # 找到下一个玩家
    current_index = game.player_order.index(game.current_player)
    next_index = (current_index + 1) % len(game.player_order)
    game.current_player = game.player_order[next_index]
    
    await show_play_turn(bot, group_id)

async def handle_play_timeout(bot: Bot, group_id: int, player_id: int, timeout: int):
    """处理出牌超时"""
    await asyncio.sleep(timeout)
    game = games.get(group_id)
    
    if game and game.game_status == 'playing' and game.current_player == player_id:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=player_id)
        
        if game.last_play:
            await bot.send_group_msg(
                group_id=group_id,
                message=f"玩家 {user_info['nickname']} 出牌超时，自动要不起！"
            )
            game.pass_count += 1
            if game.pass_count >= 2:
                game.last_play = None
                game.pass_count = 0
        else:
            # 首次出牌超时，随机出一张最小的牌
            player_cards = game.players[player_id]['cards']
            smallest_card = min(player_cards, key=lambda x: game.get_card_value(x[1]))
            player_cards.remove(smallest_card)
            
            game.last_play = {
                "player": player_id,
                "cards": [smallest_card],
                "type": game.analyze_cards([smallest_card])
            }
            
            await bot.send_group_msg(
                group_id=group_id,
                message=f"玩家 {user_info['nickname']} 出牌超时，自动出牌：{game.format_cards([smallest_card])}\n剩余手牌：{len(player_cards)}张"
            )
            
            if len(player_cards) == 0:
                await end_game(bot, group_id, player_id)
                return
        
        await next_player(bot, group_id)

def parse_cards(card_text: str) -> List[Tuple[str, str]]:
    """解析牌面文本"""
    cards = []
    parts = card_text.split()
    
    # 检查是否是简化格式（纯数字字母）
    if len(parts) == 1 and all(c.isalnum() for c in parts[0]):
        # 简化格式：345678 或 JQKA2
        simplified_text = parts[0]
        suits = ['♠', '♥', '♣', '♦']
        
        i = 0
        while i < len(simplified_text):
            if i < len(simplified_text) - 1 and simplified_text[i:i+2] == '10':
                # 处理10
                suit = suits[len(cards) % 4]  # 循环使用花色
                cards.append((suit, '10'))
                i += 2
            else:
                char = simplified_text[i]
                if char in '3456789JQKA2':
                    suit = suits[len(cards) % 4]  # 循环使用花色
                    cards.append((suit, char))
                i += 1
        return cards
    
    # 原有的解析逻辑
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        if part == "大王":
            cards.append(("", "大王"))
        elif part == "小王":
            cards.append(("", "小王"))
        else:
            # 解析花色和点数
            suit = ""
            rank = ""
            
            for char in part:
                if char in ['♠', '♥', '♣', '♦']:
                    suit = char
                else:
                    rank += char
            
            if suit and rank:
                cards.append((suit, rank))
            else:
                raise ValueError(f"无法解析牌面：{part}")
    
    return cards

async def end_game(bot: Bot, group_id: int, winner_id: int):
    """结束游戏"""
    game = games[group_id]
    game.game_status = 'finished'
    
    winner_info = await bot.get_group_member_info(group_id=group_id, user_id=winner_id)
    winner_role = game.players[winner_id]['role']
    
    msg = f"🎉 游戏结束！\n获胜者：{winner_info['nickname']} ({winner_role})\n\n"
    
    # 显示所有玩家剩余手牌
    for user_id in game.player_order:
        player_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        remaining_cards = game.players[user_id]['cards']
        role = game.players[user_id]['role']
        msg += f"{player_info['nickname']} ({role})：{len(remaining_cards)}张\n"
        if remaining_cards:
            msg += f"  剩余：{game.format_cards(remaining_cards)}\n"
    
    # 计算积分
    if winner_role == 'landlord':
        # 地主获胜
        await update_player_score(str(winner_id), str(group_id), 30, 'doudizhu', None, 'win')
        msg += f"\n🎊 地主获胜！{winner_info['nickname']} 获得30积分！"
    else:
        # 农民获胜
        for user_id in game.player_order:
            if game.players[user_id]['role'] == 'farmer':
                await update_player_score(str(user_id), str(group_id), 20, 'doudizhu', None, 'win')
        msg += f"\n🎊 农民获胜！每位农民获得20积分！"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    del games[group_id]

# 强制结束游戏命令
force_end = on_regex(pattern=r"^强制结束斗地主$", priority=5)
@force_end.handle()
async def handle_force_end(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games:
        await force_end.finish("当前没有进行中的斗地主游戏。")
        return
    
    # 检查权限（群主或管理员）
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=event.user_id)
    if user_info['role'] not in ['owner', 'admin']:
        await force_end.finish("只有群主或管理员可以强制结束游戏！")
        return
    
    del games[group_id]
    await force_end.finish("斗地主游戏已被强制结束！")

# 帮助命令
doudizhu_help = on_regex(pattern=r"^斗地主帮助$", priority=5)
@doudizhu_help.handle()
async def handle_doudizhu_help(bot: Bot, event: GroupMessageEvent):
    help_text = """
🎮 斗地主游戏帮助

📋 游戏规则：
• 3人游戏，一人当地主，两人当农民
• 地主获得3张底牌，共20张牌
• 地主先出牌，农民轮流出牌
• 先出完手牌的一方获胜

🎯 牌型大小（从大到小）：
• 王炸：大王+小王
• 炸弹：四张相同点数的牌
• 单牌：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2 < 小王 < 大王
• 对子：两张相同点数的牌
• 三张：三张相同点数的牌
• 三带一：三张+一张单牌
• 三带二：三张+一对
• 顺子：五张或以上连续的牌（不包含2和王）
• 连对：三对或以上连续的对子
• 飞机：连续的三张（可带单牌或对子）
• 四带二：四张+两张单牌或两对

🎲 游戏流程：
1. 发送【开始斗地主】开始游戏
2. 发送【报名斗地主】报名参与（需要3人）
3. 自动发牌后进入叫地主阶段
4. 发送【叫地主 1/2/3】或【不叫】
5. 地主确定后开始出牌
6. 发送【出牌 牌面】或【要不起】

💡 出牌格式：
• 出牌 ♠3（单牌）
• 出牌 ♠3 ♥3（对子）
• 出牌 ♠3 ♥4 ♣5 ♦6 ♠7（顺子）
• 出牌 大王 小王（王炸）

🏆 积分规则：
• 参与游戏：+5分
• 地主获胜：+30分
• 农民获胜：每人+20分

⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！
"""
    await doudizhu_help.finish(help_text)