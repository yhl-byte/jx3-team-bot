from nonebot import on_command, on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict, List
from .game_score import update_player_score
import random
import asyncio

# 游戏状态管理
class BlackjackGame:
    def __init__(self):
        self.deck = []  # 牌组
        self.players = {}  # 玩家手牌 {user_id: {"cards": [], "number": int}}
        self.dealer_cards = []  # 庄家手牌
        self.dealer_id = None  # 庄家ID
        self.current_player = None  # 当前操作的玩家
        self.game_status = 'waiting_signup'  # 游戏状态：waiting_signup, waiting_dealer, playing, finished
        self.timer = None  # 用于计时的变量
        self.player_order = []  # 玩家顺序
        self.player_count = 0  # 玩家计数（用于分配编号）
        self.dealer_candidates = []  # 新增：申请当庄家的玩家

    def init_deck(self):
        suits = ['♠', '♥', '♣', '♦']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.deck = [(suit, rank) for suit in suits for rank in ranks]
        random.shuffle(self.deck)

    def deal_card(self):
        return self.deck.pop() if self.deck else None

    def calculate_points(self, cards):
        points = 0
        ace_count = 0
        
        for _, rank in cards:
            if rank in ['J', 'Q', 'K']:
                points += 10
            elif rank == 'A':
                ace_count += 1
                points += 11
            else:
                points += int(rank)
        
        while points > 21 and ace_count:
            points -= 10
            ace_count -= 1
            
        return points

    def format_cards(self, cards):
        return ' '.join([f"{suit}{rank}" for suit, rank in cards])

# 存储每个群的游戏实例
games: Dict[int, BlackjackGame] = {}

# 开始21点游戏命令
start_game = on_regex(pattern=r"^开始21点$", priority=5)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id in games and games[group_id].game_status != 'finished':
        await start_game.finish("游戏已经在进行中！")
        return

    games[group_id] = BlackjackGame()
    game = games[group_id]
    game.init_deck()
    
    await start_game.finish("21点游戏开始！请玩家发送【报名21点】进行报名，通过【结束21点报名】来结束报名阶段，开始游戏。")

# 玩家报名
signup = on_regex(pattern=r"^报名21点$", priority=5)
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
    
    game.player_count += 1
    game.players[user_id] = {"cards": [], "number": game.player_count}
    game.player_order.append(user_id)
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    # 添加参与游戏基础分
    await update_player_score(str(user_id), str(group_id), 5, 'guessing', None, 'participation')
    msg = (
        MessageSegment.at(user_id)  + '\n'  + 
        Message(f"【{user_info['nickname']}】报名成功！您的编号是 {game.player_count}")
    )
    await signup.finish(message=Message(msg))

# 结束报名
end_signup = on_regex(pattern=r"^结束21点报名$", priority=5)
@end_signup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_signup':
        return
        
    game = games[group_id]
    if len(game.players) < 2:
        await end_signup.finish("报名人数不足，至少需要2人才能开始游戏！")
        return
    
    game.game_status = 'waiting_dealer'
    msg = "报名结束！请想要当庄家的玩家在30秒内发送【我要当庄】\n当前玩家列表：\n"
    for user_id in game.player_order:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        msg += f"编号 {game.players[user_id]['number']}: {user_info['nickname']}\n"
    
    await end_signup.send(msg)
    
    # 设置30秒定时器等待庄家
    if game.timer:
        game.timer.cancel()
    game.timer = asyncio.create_task(asyncio.sleep(30))
    try:
        await game.timer
        if not game.dealer_id and game.game_status == 'waiting_dealer':
            # 随机选择庄家
            dealer_id = random.choice(game.player_order)
            game.dealer_id = dealer_id
            user_info = await bot.get_group_member_info(group_id=group_id, user_id=dealer_id)
            await end_signup.send(f"随机选择 {user_info['nickname']} (编号 {game.players[dealer_id]['number']}) 作为庄家！")
            await start_dealing(bot, group_id)
    except asyncio.CancelledError:
        pass

# 玩家申请当庄家
dealer_register = on_regex(pattern=r"^我要当庄$", priority=5)
@dealer_register.handle()
async def handle_dealer_register(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_dealer':
        return
        
    game = games[group_id]
    if user_id not in game.players:
        await dealer_register.finish("您没有报名游戏，无法成为庄家！")
        return

    if user_id in game.dealer_candidates:
        await dealer_register.finish("您已经申请过当庄家了！")
        return
        
    game.dealer_candidates.append(user_id)
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    await dealer_register.send(f"玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 申请成为庄家！")

    # 如果是第一个申请的玩家，取消之前的定时器并开始新的30秒倒计时
    if len(game.dealer_candidates) == 1:
        if game.timer:
            game.timer.cancel()
        game.timer = asyncio.create_task(asyncio.sleep(10))
        try:
            await game.timer
            if game.game_status == 'waiting_dealer':
                # 时间到，从申请列表中随机选择庄家
                if game.dealer_candidates:
                    dealer_id = random.choice(game.dealer_candidates)
                    game.dealer_id = dealer_id
                    dealer_info = await bot.get_group_member_info(group_id=group_id, user_id=dealer_id)
                    await bot.send_group_msg(
                        group_id=group_id,
                        message=f"从{len(game.dealer_candidates)}位申请者中随机选择 {dealer_info['nickname']} (编号 {game.players[dealer_id]['number']}) 作为庄家！"
                    )
                    await start_dealing(bot, group_id)
        except asyncio.CancelledError:
            pass

async def start_dealing(bot: Bot, group_id: int):
    game = games[group_id]
    game.game_status = 'playing'
    
    # 给所有玩家发两张牌
    for user_id in game.player_order:
        if user_id != game.dealer_id:
            game.players[user_id]['cards'].extend([game.deal_card() for _ in range(2)])
    
    # 给庄家发牌
    hidden_card = game.deal_card()  # 暗牌
    game.dealer_cards.append(hidden_card)
    game.dealer_cards.append(game.deal_card())  # 明牌
    
    # 私聊发送暗牌给庄家
    await bot.send_private_msg(
        user_id=game.dealer_id,
        message=f"您的暗牌是：{hidden_card[0]}{hidden_card[1]}"
    )
    
    # 展示所有玩家的牌
    msg = "发牌完成！\n当前牌面：\n"
    for user_id in game.player_order:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        if user_id == game.dealer_id:
            msg += f"庄家 {user_info['nickname']} (编号 {game.players[user_id]['number']}):  [暗牌] {game.format_cards([game.dealer_cards[1]])}\n"
        else:
            cards = game.players[user_id]['cards']
            points = game.calculate_points(cards)
            msg += f"玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}): {game.format_cards(cards)} (点数：{points})\n"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 开始询问玩家要牌
    game.current_player = game.player_order[(game.player_order.index(game.dealer_id) + 1) % len(game.player_order)]
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=game.current_player)
    cards = game.players[game.current_player]['cards']
    points = game.calculate_points(cards)
    visible_cards = game.dealer_cards[1:]  # 从索引1开始到末尾的所有牌都是明牌
    dealer_points = game.calculate_points(visible_cards)
    msg = (
        MessageSegment.at(game.current_player)  + '\n'  +
        Message(f"庄家牌面：[暗牌] {game.format_cards(visible_cards)} (点数：{dealer_points})\n 你的牌面：{game.format_cards(cards)} (点数：{points})\n 请玩家 {user_info['nickname']} (编号 {game.players[game.current_player]['number']}) 选择要牌还是停牌")
    )
    await bot.send_group_msg(
        group_id=group_id,
        message=msg
    )

# 要牌命令
hit = on_regex(pattern=r"^要牌$", priority=5)
@hit.handle()
async def handle_hit(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    # 发一张牌
    new_card = game.deal_card()
    if user_id == game.dealer_id:
        game.dealer_cards.append(new_card)
        cards = game.dealer_cards
    else:
        game.players[user_id]['cards'].append(new_card)
        cards = game.players[user_id]['cards']
    
    points = game.calculate_points(cards)
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    if user_id == game.dealer_id:
        # 庄家要牌，显示除暗牌外的所有牌
        visible_cards = game.dealer_cards[1:]  # 从索引1开始到末尾的所有牌都是明牌
        msg = f"庄家 {user_info['nickname']} 要了一张牌\n"
        msg += f"当前明牌：[暗牌] {game.format_cards(visible_cards)}\n"
        # 私聊发送点数给庄家
        await bot.send_private_msg(
            user_id=user_id,
            message=f"您当前的总点数是：{points}"
        )
    else:
        msg = f"玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 的牌面：{game.format_cards(cards)} (点数：{points})\n"
    
    if points > 21:
        if user_id == game.dealer_id:
            await hit.send(f"庄家 {user_info['nickname']} 爆牌了！")
            # 游戏结束
            await end_game(bot, group_id)
        else:
            await hit.send(f"牌面：{game.format_cards(cards)} (点数：{points})\n玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 爆牌了！")
            # 轮到下一个玩家
            await next_player(bot, group_id, user_id)
    else:
        if user_id == game.dealer_id:
            # 庄家要牌，显示除暗牌外的所有牌
            visible_cards = game.dealer_cards[1:]
            msg = MessageSegment.at(user_id) + '\n' + f"庄家 {user_info['nickname']} 要了一张牌\n"
            msg += f"当前明牌：[暗牌] {game.format_cards(visible_cards)}\n"
            # 私聊发送点数给庄家
            await bot.send_private_msg(
                user_id=user_id,
                message=f"您当前的总点数是：{points}"
            )
        else:
            msg = MessageSegment.at(user_id) + '\n' + f"玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}) 的牌面：{game.format_cards(cards)} (点数：{points})\n"
        msg += "请选择【要牌】还是【停牌】"
        await hit.finish(msg)

# 停牌命令
stand = on_regex(pattern=r"^停牌$", priority=5)
@stand.handle()
async def handle_stand(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    if user_id == game.dealer_id:
        # 如果是庄家停牌，直接结束游戏
        await end_game(bot, group_id)
    else:
        # 如果是普通玩家停牌，轮到下一个玩家
        await next_player(bot, group_id, user_id)

async def next_player(bot: Bot, group_id: int, current_user_id: int):
    game = games[group_id]
    current_index = game.player_order.index(current_user_id)
    next_index = (current_index + 1) % len(game.player_order)
    next_player_id = game.player_order[next_index]
    
    if next_player_id == game.dealer_id and current_user_id == game.player_order[game.player_order.index(game.dealer_id) - 1]:
        # 轮到庄家第一次操作
        game.current_player = next_player_id
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=next_player_id)
        msg = MessageSegment.at(next_player_id)  + '\n' 
        # 显示庄家的明牌和暗牌提示
        msg += f"轮到庄家 {user_info['nickname']} (编号 {game.players[next_player_id]['number']}) 操作\n"
        msg += f"庄家明牌：[暗牌] {game.format_cards([game.dealer_cards[1]])}\n"
        # 私聊发送当前点数给庄家
        total_points = game.calculate_points(game.dealer_cards)
        await bot.send_private_msg(
            user_id=next_player_id,
            message=f"您当前的总点数是：{total_points}"
        )
        msg += "请选择【要牌】还是【停牌】"
        await bot.send_group_msg(group_id=group_id, message=msg)
    elif next_player_id == game.dealer_id:
        # 庄家继续操作
        game.current_player = next_player_id
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=next_player_id)
        # 显示庄家当前的明牌和暗牌提示
        msg = f"庄家 {user_info['nickname']} 的明牌：{game.format_cards(game.dealer_cards[:-1])} [有一张暗牌]\n"
        # 私聊发送当前点数给庄家
        total_points = game.calculate_points(game.dealer_cards)
        await bot.send_private_msg(
            user_id=next_player_id,
            message=f"您当前的总点数是：{total_points}"
        )
        msg += "请继续选择要牌还是停牌"
        await bot.send_group_msg(group_id=group_id, message=msg)
    elif current_user_id == game.dealer_id:
        # 庄家停牌，游戏结束
        await end_game(bot, group_id)
    else:
        # 普通玩家回合
        game.current_player = next_player_id
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=next_player_id)
        cards = game.players[next_player_id]['cards']
        points = game.calculate_points(cards)
        visible_cards = game.dealer_cards[1:]  # 从索引1开始到末尾的所有牌都是明牌
        dealer_points = game.calculate_points(visible_cards)
        msg = (
            MessageSegment.at(next_player_id)  + '\n'  + 
            Message(f"庄家牌面：[暗牌] {game.format_cards(visible_cards)} (点数：{dealer_points})\n 你的牌面：{game.format_cards(cards)} (点数：{points})\n请玩家 {user_info['nickname']} (编号 {game.players[next_player_id]['number']}) 选择要牌还是停牌")
        )
        await bot.send_group_msg(
            group_id=group_id,
            message=msg
        )
async def end_game(bot: Bot, group_id: int):
    game = games[group_id]
    game.game_status = 'finished'

    # 计算庄家赢的人数
    dealer_wins = 0
    for user_id in game.player_order:
        if user_id != game.dealer_id:
            points = game.calculate_points(game.players[user_id]['cards'])
            dealer_points = game.calculate_points(game.dealer_cards)
            
            if points <= 21:
                if dealer_points > 21 or points > dealer_points:
                    # 闲家赢
                    await update_player_score(user_id, str(group_id), 10, 'blackjack', 'player', 'win')
                elif points < dealer_points:
                    dealer_wins += 1
    
    # 庄家积分
    if dealer_wins > 0:
        await update_player_score(str(game.dealer_id), str(group_id), dealer_wins * 10, 'blackjack', 'dealer', 'win')
    
    # 计算结果
    msg = "游戏结束！\n最终结果：\n"
    dealer_info = await bot.get_group_member_info(group_id=group_id, user_id=game.dealer_id)
    dealer_points = game.calculate_points(game.dealer_cards)
    
    # 在结算时标记暗牌
    dealer_cards_display = game.format_cards(game.dealer_cards[1:])  # 明牌
    dealer_hidden_card = game.format_cards([game.dealer_cards[0]])    # 暗牌
    msg += f"庄家 {dealer_info['nickname']} (编号 {game.players[game.dealer_id]['number']}): [暗牌:{dealer_hidden_card}] {dealer_cards_display} (点数：{dealer_points})\n"
    
    if dealer_points > 21:
        msg += "庄家爆牌！除爆牌玩家外其他玩家获胜！\n"
    
    for user_id in game.player_order:
        if user_id != game.dealer_id:
            user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
            cards = game.players[user_id]['cards']
            points = game.calculate_points(cards)
            msg += f"玩家 {user_info['nickname']} (编号 {game.players[user_id]['number']}): {game.format_cards(cards)} (点数：{points}) - "
            
            if points > 21:
                msg += "爆牌（输）\n"
            elif dealer_points > 21:
                msg += "获胜\n"
            elif points > dealer_points:
                msg += "获胜\n"
            elif points < dealer_points:
                msg += "失败\n"
            else:
                msg += "平局\n"
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    del games[group_id]


# 添加强制结束游戏命令
force_end = on_regex(pattern=r"^强制结束21点$", priority=5)
@force_end.handle()
async def handle_force_end(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games:
        await force_end.finish("当前没有进行中的21点游戏。")
        return
    
    # 检查是否是管理员
    sender = event.sender
    if not (sender.role in ["admin", "owner"]):
        await force_end.finish("只有管理员才能强制结束游戏。")
        return
    
    game = games[group_id]
    await bot.send_group_msg(group_id=group_id, message="游戏被管理员强制结束。")
    del games[group_id]



# 21点帮助命令
blackjack_help = on_regex(pattern=r"^21点帮助$", priority=5)
@blackjack_help.handle()
async def handle_blackjack_help(bot: Bot, event: GroupMessageEvent):
    help_text = """
        21点游戏指令说明：
        1. 【开始21点】：开始一局新的21点游戏
        2. 【报名21点】：参与当前游戏
        3. 【结束21点报名】：结束报名阶段，进入选庄阶段
        4. 【我要当庄】：申请成为庄家（30秒内有效）
        5. 【要牌】：在自己回合时要一张牌
        6. 【停牌】：在自己回合时停止要牌
        7. 【强制结束21点】：管理员可强制结束当前游戏

        游戏规则：
        1. 牌面点数：
        - A可以算1点或11点
        - J、Q、K算10点
        - 其他牌按面值计算
        2. 超过21点即为爆牌
        3. 未爆牌者中点数最接近21点者获胜
        4. 点数相同时庄家获胜

        游戏流程：
        1. 游戏开始后先进行报名
        2. 报名结束后选择庄家（可申请当庄，无人申请则随机选择）
        3. 选定庄家后自动发牌
        4. 轮流进行要牌/停牌
        5. 所有人结束操作后进行结算
    """
    await blackjack_help.finish(help_text)