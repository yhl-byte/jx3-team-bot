from nonebot import on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict, List, Tuple, Optional
from .game_score import update_player_score
import random
import asyncio

# 游戏状态管理
class SichuanMajiangGame:
    def __init__(self):
        self.tiles = []  # 牌组
        self.players = {}  # 玩家信息
        self.current_player = None  # 当前出牌玩家
        self.game_status = 'waiting_signup'  # 游戏状态
        self.timer = None  # 计时器
        self.player_order = []  # 玩家顺序
        self.player_count = 0  # 玩家计数
        self.wall_tiles = []  # 牌墙
        self.discarded_tiles = []  # 弃牌堆
        self.discarded_records = []  # 出牌记录：[{'player_id': user_id, 'tile': tile, 'nickname': nickname}]
        self.current_discard = None  # 当前打出的牌
        self.banker = None  # 庄家
        self.que_decisions = {}  # 定缺决定
        self.round_count = 0  # 轮数计数
        self.gang_scores = {}  # 杠分记录
        self.hu_records = {}  # 胡牌记录
        self.waiting_actions = {}  # 等待操作的玩家
        self.last_draw_player = None  # 最后摸牌的玩家
        self.gang_tile = None  # 杠牌补牌
        
    def init_tiles(self):
        """初始化麻将牌（108张）"""
        suits = ['万', '条', '筒']
        numbers = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
        
        # 每种牌4张
        self.tiles = []
        for suit in suits:
            for number in numbers:
                for _ in range(4):
                    self.tiles.append(f"{number}{suit}")
        
        random.shuffle(self.tiles)
        self.wall_tiles = self.tiles.copy()
    
    def get_tile_suit(self, tile):
        """获取牌的花色"""
        if tile.endswith('万'):
            return '万'
        elif tile.endswith('条'):
            return '条'
        elif tile.endswith('筒'):
            return '筒'
        return None
    
    def get_tile_number(self, tile):
        """获取牌的数字"""
        return int(tile[0])
    
    def sort_hand(self, hand):
        """整理手牌"""
        def tile_key(tile):
            suit_order = {'万': 0, '条': 1, '筒': 2}
            suit = self.get_tile_suit(tile)
            number = self.get_tile_number(tile)
            return (suit_order.get(suit, 3), number)
        
        return sorted(hand, key=tile_key)
    
    def format_hand(self, hand, melds=None):
        """格式化显示手牌"""
        sorted_hand = self.sort_hand(hand)
        result = ' '.join(sorted_hand)
        
        if melds:
            meld_strs = []
            for meld in melds:
                if meld['type'] == 'peng':
                    meld_strs.append(f"[碰:{meld['tile']}]")
                elif meld['type'] == 'gang':
                    meld_strs.append(f"[杠:{meld['tile']}]")
            if meld_strs:
                result += ' ' + ' '.join(meld_strs)
        
        return result
    
    def can_peng(self, player_hand, tile):
        """检查是否可以碰"""
        return player_hand.count(tile) >= 2
    
    def can_gang(self, player_hand, tile, melds=None):
        """检查是否可以杠"""
        # 明杠：手中有3张相同的牌
        if player_hand.count(tile) >= 3:
            return 'ming_gang'
        
        # 补杠：已经碰过，手中有1张
        if melds:
            for meld in melds:
                if meld['type'] == 'peng' and meld['tile'] == tile and tile in player_hand:
                    return 'bu_gang'
        
        return None
    
    def can_an_gang(self, player_hand):
        """检查是否可以暗杠"""
        tile_count = {}
        for tile in player_hand:
            tile_count[tile] = tile_count.get(tile, 0) + 1
        
        an_gang_tiles = []
        for tile, count in tile_count.items():
            if count >= 4:
                an_gang_tiles.append(tile)
        
        return an_gang_tiles
    
    def check_hu(self, hand, melds=None, new_tile=None, que_suit=None):
        """检查是否可以胡牌"""
        test_hand = hand.copy()
        if new_tile:
            test_hand.append(new_tile)
        
        # 检查是否有缺门的牌
        if que_suit:
            for tile in test_hand:
                if self.get_tile_suit(tile) == que_suit:
                    return False
        
        # 计算已有的面子数
        meld_count = len(melds) if melds else 0
        remaining_tiles = len(test_hand)

        # 检查十八罗汉：4个杠子 + 1对将（2张牌）
        if melds:
            gang_count = sum(1 for meld in melds if meld['type'] == 'gang')
            if gang_count == 4 and remaining_tiles == 2:
                # 检查剩余2张是否为对子
                if len(set(test_hand)) == 1 and len(test_hand) == 2:
                    return True
        
        # 胡牌需要4副面子+1对将，总共14张牌
        total_needed = 14 - meld_count * 3
        if remaining_tiles != total_needed:
            return False
        
        return self._check_winning_pattern(test_hand)
    
    def _check_winning_pattern(self, hand):
        """检查胡牌牌型"""
        if len(hand) % 3 == 2:  # 应该有一个对子
            # 检查七对子
            if len(hand) == 14 and self._check_seven_pairs(hand):
                return True
            
            # 检查基本胡牌型
            return self._check_basic_winning(hand)
        
        return False
    
    def _check_seven_pairs(self, hand):
        """检查七对子"""
        tile_count = {}
        for tile in hand:
            tile_count[tile] = tile_count.get(tile, 0) + 1
        
        pairs = 0
        for count in tile_count.values():
            if count == 2:
                pairs += 1
            elif count % 2 != 0:
                return False
        
        return pairs == 7
    
    def _check_basic_winning(self, hand):
        """检查基本胡牌型"""
        tile_count = {}
        for tile in hand:
            tile_count[tile] = tile_count.get(tile, 0) + 1
        
        # 寻找对子
        for tile, count in tile_count.items():
            if count >= 2:
                temp_count = tile_count.copy()
                temp_count[tile] -= 2
                if temp_count[tile] == 0:
                    del temp_count[tile]
                
                if self._check_melds(temp_count):
                    return True
        
        return False
    
    def _check_melds(self, tile_count):
        """检查是否能组成顺子/刻子"""
        total_tiles = sum(tile_count.values())
        if total_tiles == 0:
            return True
        if total_tiles % 3 != 0:
            return False
        
        # 优先检查刻子
        for tile, count in list(tile_count.items()):
            if count >= 3:
                temp_count = tile_count.copy()
                temp_count[tile] -= 3
                if temp_count[tile] == 0:
                    del temp_count[tile]
                return self._check_melds(temp_count)
        
        # 检查顺子
        for suit in ['万', '条', '筒']:
            for num in range(1, 8):
                tile1 = f"{num}{suit}"
                tile2 = f"{num+1}{suit}"
                tile3 = f"{num+2}{suit}"
                
                if (tile1 in tile_count and tile2 in tile_count and tile3 in tile_count and
                    tile_count[tile1] > 0 and tile_count[tile2] > 0 and tile_count[tile3] > 0):
                    temp_count = tile_count.copy()
                    temp_count[tile1] -= 1
                    temp_count[tile2] -= 1
                    temp_count[tile3] -= 1
                    
                    for tile in [tile1, tile2, tile3]:
                        if temp_count[tile] == 0:
                            del temp_count[tile]
                    
                    return self._check_melds(temp_count)
        
        return False
    
    def draw_tile(self):
        """摸牌"""
        if self.wall_tiles:
            return self.wall_tiles.pop()
        return None
    
    def is_ting(self, hand, melds=None, que_suit=None):
        """检查是否听牌"""
        for suit in ['万', '条', '筒']:
            for num in range(1, 10):
                test_tile = f"{num}{suit}"
                if self.check_hu(hand, melds, test_tile, que_suit):
                    return True
        return False

# 存储每个群的游戏实例
games: Dict[int, SichuanMajiangGame] = {}

# 开始四川麻将游戏命令
start_game = on_regex(pattern=r"^开始四川麻将$", priority=5)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id in games and games[group_id].game_status != 'finished':
        await start_game.finish("游戏已经在进行中！")
        return

    games[group_id] = SichuanMajiangGame()
    game = games[group_id]
    game.init_tiles()
    
    await start_game.finish("🀄 四川麻将开始！请玩家发送【报名麻将】进行报名，需要4人参与。\n\n⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！")

# 玩家报名
signup = on_regex(pattern=r"^报名麻将$", priority=5)
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
    
    if len(game.players) >= 4:
        await signup.finish("报名人数已满（需要4人）！")
        return
    
    game.player_count += 1
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    game.players[user_id] = {
        "hand": [], 
        "number": game.player_count, 
        "nickname": user_info['nickname'],
        "que": None,
        "melds": [],  # 碰杠的牌
        "score": 0,   # 当前得分
        "hu_count": 0,  # 胡牌次数
        "gang_count": 0  # 杠牌次数
    }
    game.player_order.append(user_id)
    
    # 添加参与游戏基础分
    await update_player_score(str(user_id), str(group_id), 5, 'sichuanmajiang', None, 'participation')
    
    msg = (
        MessageSegment.at(user_id) + '\n' + 
        Message(f"【{user_info['nickname']}】报名成功！您的编号是 {game.player_count}")
    )
    
    if len(game.players) == 4:
        await signup.send(message=Message(msg))
        await start_dealing(bot, group_id)
    else:
        await signup.finish(message=Message(msg))

async def start_dealing(bot: Bot, group_id: int):
    """开始发牌"""
    game = games[group_id]
    game.game_status = 'deciding_que'
    game.banker = game.player_order[0]  # 第一个玩家为庄家
    
    # 发牌：每人13张，庄家14张
    for i in range(13):
        for user_id in game.player_order:
            tile = game.draw_tile()
            if tile:
                game.players[user_id]['hand'].append(tile)
    
    # 庄家多摸一张
    banker_tile = game.draw_tile()
    if banker_tile:
        game.players[game.banker]['hand'].append(banker_tile)
    
    # 给每个玩家私聊发送手牌
    for user_id in game.player_order:
        hand = game.players[user_id]['hand']
        await bot.send_private_msg(
            user_id=user_id,
            message=f"您的手牌：\n{game.format_hand(hand)}"
        )
    
    await bot.send_group_msg(
        group_id=group_id, 
        message="发牌完成！请每位玩家发送【定缺 万/条/筒】选择要缺的花色"
    )
    
    # 设置定缺超时
    game.timer = asyncio.create_task(que_timeout(bot, group_id))

async def que_timeout(bot: Bot, group_id: int):
    """定缺超时处理"""
    await asyncio.sleep(30)
    if group_id in games and games[group_id].game_status == 'deciding_que':
        game = games[group_id]
        suits = ['万', '条', '筒']
        for user_id in game.player_order:
            if user_id not in game.que_decisions:
                game.que_decisions[user_id] = random.choice(suits)
                game.players[user_id]['que'] = game.que_decisions[user_id]
        
        await start_playing(bot, group_id)

# 定缺命令
decide_que = on_regex(pattern=r"^定缺\s+(万|条|筒)$", priority=5)
@decide_que.handle()
async def handle_decide_que(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'deciding_que':
        return
    
    game = games[group_id]
    if user_id not in game.players:
        return
    
    if user_id in game.que_decisions:
        await decide_que.finish("您已经定缺过了！")
        return
    
    que_suit = event.get_plaintext().split()[1]
    game.que_decisions[user_id] = que_suit
    game.players[user_id]['que'] = que_suit
    
    await decide_que.finish(f"定缺成功！您选择缺 {que_suit}")
    
    if len(game.que_decisions) == 4:
        if game.timer:
            game.timer.cancel()
        await start_playing(bot, group_id)

async def start_playing(bot: Bot, group_id: int):
    """开始游戏"""
    game = games[group_id]
    game.game_status = 'playing'
    
    # 显示定缺情况
    que_info = "\n".join([
        f"{game.players[user_id]['nickname']}：缺{game.players[user_id]['que']}"
        for user_id in game.player_order
    ])
    
    await bot.send_group_msg(
        group_id=group_id,
        message=f"定缺完成！\n{que_info}\n\n游戏开始！庄家先出牌。"
    )
    
    game.current_player = game.banker
    await show_current_turn(bot, group_id)

async def show_current_turn(bot: Bot, group_id: int):
    """显示当前玩家回合"""
    game = games[group_id]
    current_user = game.current_player
    player = game.players[current_user]
    
    # 检查暗杠
    an_gang_tiles = game.can_an_gang(player['hand'])
    
    # 检查是否可以胡牌
    can_hu = game.check_hu(player['hand'], player['melds'], None, player['que'])
    
    # 私聊发送手牌
    hand_msg = f"您的手牌：\n{game.format_hand(player['hand'], player['melds'])}"
    
    actions = ["【出牌 牌面】"]
    if can_hu:
        actions.append("【胡牌】")
        hand_msg += "\n🎉 您可以胡牌！"
    if an_gang_tiles:
        actions.append("【暗杠 牌面】")
        hand_msg += f"\n可暗杠：{' '.join(an_gang_tiles)}"
    
    await bot.send_private_msg(user_id=current_user, message=hand_msg)
    
    # 群聊显示当前状态
    msg = (
        f"轮到 {MessageSegment.at(current_user)} 出牌\n"
        f"可用操作：{' 或 '.join(actions)}\n"
        f"剩余牌数：{len(game.wall_tiles)}"
    )
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 设置超时
    game.timer = asyncio.create_task(play_timeout(bot, group_id, current_user))

async def play_timeout(bot: Bot, group_id: int, user_id: int):
    """出牌超时处理"""
    await asyncio.sleep(30)
    if group_id in games and games[group_id].current_player == user_id:
        game = games[group_id]
        player = game.players[user_id]
        
        # 自动出牌（优先出缺门牌）
        que_suit = player['que']
        que_tiles = [tile for tile in player['hand'] if game.get_tile_suit(tile) == que_suit]
        
        if que_tiles:
            auto_discard = random.choice(que_tiles)
        else:
            auto_discard = random.choice(player['hand'])
        
        player['hand'].remove(auto_discard)
        game.discarded_tiles.append(auto_discard)
        game.current_discard = auto_discard

        # 记录出牌者信息
        game.discarded_records.append({
            'player_id': user_id,
            'tile': auto_discard,
            'nickname': player['nickname']
        })
        
        await bot.send_group_msg(
            group_id=group_id,
            message=f"{player['nickname']} 超时，自动出牌：{auto_discard}"
        )
        
        await check_actions_after_discard(bot, group_id, user_id, auto_discard)

# 出牌命令
play_tile = on_regex(pattern=r"^出牌\s+(.+)$", priority=5)
@play_tile.handle()
async def handle_play_tile(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
    
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    tile_text = event.get_plaintext().split()[1]
    player = game.players[user_id]
    
    if tile_text not in player['hand']:
        await play_tile.finish("您的手牌中没有这张牌！")
        return
    
    # 出牌
    player['hand'].remove(tile_text)
    game.discarded_tiles.append(tile_text)
    game.current_discard = tile_text

    # 记录出牌者信息
    game.discarded_records.append({
        'player_id': user_id,
        'tile': tile_text,
        'nickname': player['nickname']
    })
    
    if game.timer:
        game.timer.cancel()
    
    await bot.send_group_msg(
        group_id=group_id,
        message=f"{player['nickname']} 出牌：{tile_text}"
    )
    
    await check_actions_after_discard(bot, group_id, user_id, tile_text)

async def check_actions_after_discard(bot: Bot, group_id: int, discard_player: int, tile: str):
    """检查出牌后其他玩家的操作"""
    game = games[group_id]
    game.waiting_actions = {}
    
    # 检查其他玩家是否可以胡、碰、杠
    for user_id in game.player_order:
        if user_id == discard_player:
            continue
        
        player = game.players[user_id]
        actions = []
        
        # 检查胡牌
        if game.check_hu(player['hand'], player['melds'], tile, player['que']):
            actions.append('hu')
        
        # 检查碰
        if game.can_peng(player['hand'], tile):
            actions.append('peng')
        
        # 检查杠
        gang_type = game.can_gang(player['hand'], tile, player['melds'])
        if gang_type:
            actions.append('gang')
        
        if actions:
            game.waiting_actions[user_id] = actions
            
            # 私聊通知可用操作
            action_strs = []
            if 'hu' in actions:
                action_strs.append("【胡牌】")
            if 'peng' in actions:
                action_strs.append("【碰牌】")
            if 'gang' in actions:
                action_strs.append("【杠牌】")
            action_strs.append("【过】")
            
            await bot.send_private_msg(
                user_id=user_id,
                message=f"{game.players[discard_player]['nickname']} 出牌：{tile}\n您可以：{' 或 '.join(action_strs)}"
            )
    
    if game.waiting_actions:
        # 设置操作超时
        game.timer = asyncio.create_task(action_timeout(bot, group_id))
    else:
        # 没有人要操作，下一个玩家摸牌
        await next_player(bot, group_id)

async def action_timeout(bot: Bot, group_id: int):
    """操作超时处理"""
    await asyncio.sleep(10)
    if group_id in games:
        game = games[group_id]
        # 清空等待操作，继续游戏
        game.waiting_actions = {}
        await next_player(bot, group_id)

# 胡牌命令
hu_pai = on_regex(pattern=r"^胡牌$", priority=5)
@hu_pai.handle()
async def handle_hu_pai(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
    
    game = games[group_id]
    
    # 检查是否在等待操作列表中
    if user_id in game.waiting_actions and 'hu' in game.waiting_actions[user_id]:
        # 点炮胡
        await execute_hu(bot, group_id, user_id, 'dianpao', game.current_discard)
    elif user_id == game.current_player:
        # 自摸胡
        await execute_hu(bot, group_id, user_id, 'zimo', None)
    else:
        await hu_pai.finish("您当前不能胡牌！")

async def execute_hu(bot: Bot, group_id: int, hu_player: int, hu_type: str, hu_tile: str):
    """执行胡牌"""
    game = games[group_id]
    player = game.players[hu_player]
    
    if game.timer:
        game.timer.cancel()
    
    # 清空等待操作
    game.waiting_actions = {}
    
    # 记录胡牌
    player['hu_count'] += 1
    
    # 计算得分
    base_score = 1
    if hu_type == 'zimo':
        # 自摸：其他玩家各付1分
        for other_id in game.player_order:
            if other_id != hu_player:
                game.players[other_id]['score'] -= base_score
                player['score'] += base_score
    else:
        # 点炮：点炮者付3分
        dianpao_player = None
        for other_id in game.player_order:
            if other_id != hu_player and other_id != game.current_player:
                continue
            if other_id == game.current_player:  # 找到点炮者
                dianpao_player = other_id
                break
        
        if dianpao_player:
            game.players[dianpao_player]['score'] -= 3
            player['score'] += 3
    
    # 显示胡牌信息
    hand_display = game.format_hand(player['hand'], player['melds'])
    if hu_tile:
        hand_display += f" +{hu_tile}"
    
    hu_type_str = "自摸" if hu_type == 'zimo' else "点炮"
    await bot.send_group_msg(
        group_id=group_id,
        message=f"🎉 {player['nickname']} {hu_type_str}胡牌！\n胡牌手牌：{hand_display}"
    )
    
    # 更新积分
    await update_player_score(str(hu_player), str(group_id), 20, 'sichuanmajiang', None, 'win')
    
    # 血流成河：继续游戏
    await continue_after_hu(bot, group_id, hu_player)

async def continue_after_hu(bot: Bot, group_id: int, hu_player: int):
    """胡牌后继续游戏"""
    game = games[group_id]
    
    # 检查是否流局
    if len(game.wall_tiles) < 14:  # 牌不够重新发牌
        await end_game(bot, group_id)
        return
    
    # 重新发牌给胡牌的玩家
    game.players[hu_player]['hand'] = []
    game.players[hu_player]['melds'] = []
    
    for _ in range(13):
        tile = game.draw_tile()
        if tile:
            game.players[hu_player]['hand'].append(tile)
    
    await bot.send_private_msg(
        user_id=hu_player,
        message=f"重新发牌！您的手牌：\n{game.format_hand(game.players[hu_player]['hand'])}"
    )
    
    await bot.send_group_msg(
        group_id=group_id,
        message="血流成河！游戏继续，胡牌玩家重新发牌。"
    )
    
    # 下一个玩家继续
    await next_player(bot, group_id)

# 碰牌命令
peng_pai = on_regex(pattern=r"^碰牌$", priority=5)
@peng_pai.handle()
async def handle_peng_pai(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
    
    game = games[group_id]
    
    if user_id not in game.waiting_actions or 'peng' not in game.waiting_actions[user_id]:
        await peng_pai.finish("您当前不能碰牌！")
        return
    
    if game.timer:
        game.timer.cancel()
    
    # 执行碰牌
    tile = game.current_discard
    player = game.players[user_id]
    
    # 移除手牌中的两张相同牌
    for _ in range(2):
        player['hand'].remove(tile)
    
    # 添加到面子中
    player['melds'].append({'type': 'peng', 'tile': tile})
    
    # 清空等待操作
    game.waiting_actions = {}
    
    await bot.send_group_msg(
        group_id=group_id,
        message=f"{player['nickname']} 碰牌：{tile}"
    )
    
    # 碰牌者出牌
    game.current_player = user_id
    await show_current_turn(bot, group_id)

# 杠牌命令
gang_pai = on_regex(pattern=r"^杠牌$", priority=5)
@gang_pai.handle()
async def handle_gang_pai(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
    
    game = games[group_id]
    
    if user_id not in game.waiting_actions or 'gang' not in game.waiting_actions[user_id]:
        await gang_pai.finish("您当前不能杠牌！")
        return
    
    await execute_gang(bot, group_id, user_id, game.current_discard, 'ming_gang')

# 暗杠命令
an_gang = on_regex(pattern=r"^暗杠\s+(.+)$", priority=5)
@an_gang.handle()
async def handle_an_gang(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
    
    game = games[group_id]
    if user_id != game.current_player:
        return
    
    tile_text = event.get_plaintext().split()[1]
    player = game.players[user_id]
    
    if player['hand'].count(tile_text) < 4:
        await an_gang.finish("您没有4张相同的牌进行暗杠！")
        return
    
    await execute_gang(bot, group_id, user_id, tile_text, 'an_gang')

async def execute_gang(bot: Bot, group_id: int, gang_player: int, tile: str, gang_type: str):
    """执行杠牌"""
    game = games[group_id]
    player = game.players[gang_player]
    
    if game.timer:
        game.timer.cancel()
    
    # 清空等待操作
    game.waiting_actions = {}
    
    if gang_type == 'an_gang':
        # 暗杠：移除手牌中的4张
        for _ in range(4):
            player['hand'].remove(tile)
        score = 2  # 暗杠2分
    else:
        # 明杠：移除手牌中的3张
        for _ in range(3):
            player['hand'].remove(tile)
        score = 1  # 明杠1分
    
    # 添加到面子中
    player['melds'].append({'type': 'gang', 'tile': tile})
    player['gang_count'] += 1
    
    # 杠分立即结算
    for other_id in game.player_order:
        if other_id != gang_player:
            game.players[other_id]['score'] -= score
            player['score'] += score
    
    gang_type_str = "暗杠" if gang_type == 'an_gang' else "明杠"
    await bot.send_group_msg(
        group_id=group_id,
        message=f"{player['nickname']} {gang_type_str}：{tile}（立即得{score * 3}分）"
    )
    
    # 杠后补牌
    supplement_tile = game.draw_tile()
    if supplement_tile:
        player['hand'].append(supplement_tile)
        game.gang_tile = supplement_tile
    
    # 杠牌者继续出牌
    game.current_player = gang_player
    await show_current_turn(bot, group_id)

# 查看牌局情况命令
check_game_status = on_regex(pattern=r"^查看牌局$", priority=5)
@check_game_status.handle()
async def handle_check_game_status(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games:
        await check_game_status.finish("当前没有进行中的麻将游戏。")
        return
    
    game = games[group_id]
    if game.game_status not in ['playing', 'deciding_que']:
        await check_game_status.finish("游戏尚未开始或已结束。")
        return
    
    # 构建牌局信息
    status_msg = "🀄 当前牌局情况\n\n"
    
    # 游戏状态
    status_dict = {
        'waiting_signup': '等待报名',
        'deciding_que': '定缺阶段', 
        'playing': '游戏进行中',
        'finished': '游戏结束'
    }
    status_msg += f"📊 游戏状态：{status_dict.get(game.game_status, '未知')}\n"
    status_msg += f"🎯 剩余牌数：{len(game.wall_tiles)}\n\n"
    
    # 玩家信息
    status_msg += "👥 玩家信息：\n"
    for i, user_id in enumerate(game.player_order):
        player = game.players[user_id]
        current_mark = "👉 " if user_id == game.current_player else "   "
        
        # 基本信息
        player_info = f"{current_mark}{player['nickname']}："
        player_info += f"手牌{len(player['hand'])}张"
        
        # 定缺信息
        if player['que']:
            player_info += f" 缺{player['que']}"
        
        # 碰杠信息
        if player['melds']:
            meld_info = []
            for meld in player['melds']:
                if meld['type'] == 'peng':
                    meld_info.append(f"碰{meld['tile']}")
                elif meld['type'] == 'gang':
                    meld_info.append(f"杠{meld['tile']}")
            if meld_info:
                player_info += f" [{'/'.join(meld_info)}]"
        
        # 得分信息
        player_info += f" 得分{player['score']:+d}"
        
        # 胡牌和杠牌次数
        if player['hu_count'] > 0 or player['gang_count'] > 0:
            player_info += f" (胡{player['hu_count']}次/杠{player['gang_count']}次)"
        
        status_msg += player_info + "\n"
    
    # 已出牌信息
    if game.discarded_tiles:
        status_msg += f"\n🗂️ 已出牌（共{len(game.discarded_tiles)}张）：\n"
        # 按花色分组显示
        discarded_by_suit = {'万': [], '条': [], '筒': []}
        for tile in game.discarded_tiles:
            suit = game.get_tile_suit(tile)
            if suit in discarded_by_suit:
                discarded_by_suit[suit].append(tile)
        
        for suit in ['万', '条', '筒']:
            if discarded_by_suit[suit]:
                # 按数字排序
                sorted_tiles = sorted(discarded_by_suit[suit], key=lambda x: game.get_tile_number(x))
                status_msg += f"{suit}：{' '.join(sorted_tiles)}\n"

        # 按玩家分组显示
        status_msg += "\n👤 按玩家分组：\n"
        player_discards = {}
        for record in game.discarded_records:
            player_name = record['nickname']
            tile = record['tile']
            if player_name not in player_discards:
                player_discards[player_name] = []
            player_discards[player_name].append(tile)
        
        for user_id in game.player_order:
            player_name = game.players[user_id]['nickname']
            if player_name in player_discards:
                tiles = player_discards[player_name]
                # 按花色和数字排序
                sorted_tiles = sorted(tiles, key=lambda x: (game.get_tile_suit(x), game.get_tile_number(x)))
                status_msg += f"{player_name}：{' '.join(sorted_tiles)} ({len(tiles)}张)\n"
            else:
                status_msg += f"{player_name}：无出牌\n"
    
    # 当前出牌
    if game.current_discard:
        status_msg += f"\n🎯 当前出牌：{game.current_discard}\n"
    
    # 等待操作的玩家
    if game.waiting_actions:
        waiting_players = []
        for user_id, actions in game.waiting_actions.items():
            player_name = game.players[user_id]['nickname']
            action_names = []
            if 'hu' in actions:
                action_names.append('胡')
            if 'peng' in actions:
                action_names.append('碰')
            if 'gang' in actions:
                action_names.append('杠')
            waiting_players.append(f"{player_name}({'/'.join(action_names)})")
        
        if waiting_players:
            status_msg += f"⏳ 等待操作：{' '.join(waiting_players)}\n"
    
    await check_game_status.finish(status_msg)

# 过牌命令
pass_action = on_regex(pattern=r"^过$", priority=5)
@pass_action.handle()
async def handle_pass(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
    
    game = games[group_id]
    
    if user_id in game.waiting_actions:
        del game.waiting_actions[user_id]
        
        if not game.waiting_actions:
            # 所有人都过了，下一个玩家摸牌
            if game.timer:
                game.timer.cancel()
            await next_player(bot, group_id)

async def next_player(bot: Bot, group_id: int):
    """下一个玩家"""
    game = games[group_id]
    
    # 检查是否流局
    if len(game.wall_tiles) < 4:
        await end_game(bot, group_id)
        return
    
    # 下一个玩家
    current_index = game.player_order.index(game.current_player)
    next_index = (current_index + 1) % 4
    game.current_player = game.player_order[next_index]
    
    # 摸牌
    tile = game.draw_tile()
    if tile:
        game.players[game.current_player]['hand'].append(tile)
        game.last_draw_player = game.current_player
    
    await show_current_turn(bot, group_id)

async def end_game(bot: Bot, group_id: int):
    """结束游戏（流局）"""
    game = games[group_id]
    game.game_status = 'finished'
    
    if game.timer:
        game.timer.cancel()
    
    # 查叫：检查听牌情况
    ting_players = []
    not_ting_players = []
    
    for user_id in game.player_order:
        player = game.players[user_id]
        if game.is_ting(player['hand'], player['melds'], player['que']):
            ting_players.append(user_id)
        else:
            not_ting_players.append(user_id)
    
    # 查花猪：检查缺门情况
    hua_zhu_players = []
    for user_id in game.player_order:
        player = game.players[user_id]
        que_suit = player['que']
        has_que_tile = any(game.get_tile_suit(tile) == que_suit for tile in player['hand'])
        if has_que_tile:
            hua_zhu_players.append(user_id)
    
    # 计算查叫和查花猪的赔偿
    if ting_players and not_ting_players:
        # 未听牌者赔偿听牌者
        compensation = 1
        for not_ting_id in not_ting_players:
            for ting_id in ting_players:
                game.players[not_ting_id]['score'] -= compensation
                game.players[ting_id]['score'] += compensation
    
    if hua_zhu_players:
        # 花猪额外赔偿
        compensation = 2
        for hua_zhu_id in hua_zhu_players:
            for other_id in game.player_order:
                if other_id != hua_zhu_id:
                    game.players[hua_zhu_id]['score'] -= compensation
                    game.players[other_id]['score'] += compensation
    
    # 统计结果
    results = []
    for user_id in game.player_order:
        player = game.players[user_id]
        status = []
        if user_id in ting_players:
            status.append("听牌")
        if user_id in hua_zhu_players:
            status.append("花猪")
        
        status_str = f"({'/'.join(status)})" if status else ""
        results.append(
            f"{player['nickname']}：胡{player['hu_count']}次 杠{player['gang_count']}次 "
            f"得分{player['score']:+d} {status_str}"
        )
    
    msg = "🎮 游戏结束（流局）！\n\n" + "\n".join(results)
    
    await bot.send_group_msg(group_id=group_id, message=msg)
    del games[group_id]

# 强制结束游戏命令
force_end = on_regex(pattern=r"^强制结束麻将$", priority=5)
@force_end.handle()
async def handle_force_end(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games:
        await force_end.finish("当前没有进行中的麻将游戏。")
        return
    
    # 检查权限
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=event.user_id)
    if user_info['role'] not in ['owner', 'admin']:
        await force_end.finish("只有群主或管理员可以强制结束游戏！")
        return
    
    del games[group_id]
    await force_end.finish("麻将游戏已被强制结束！")

# 帮助命令
majiang_help = on_regex(pattern=r"^麻将帮助$", priority=5)
@majiang_help.handle()
async def handle_majiang_help(bot: Bot, event: GroupMessageEvent):
    help_text = """
🀄 四川麻将血流成河帮助

📋 基础规则：
• 4人游戏，使用108张万条筒牌（无风牌箭牌）
• 每人13张牌，庄家14张首轮出牌
• 缺一门：开局选定缺一门花色，胡牌时手牌不能有该花色

🎯 核心玩法：
• 碰：任意玩家打出的牌可碰（不限次数）
• 杠：明杠、暗杠、补杠（抢杠可胡牌）
• 胡牌：可多次胡牌，直至流局
• 不可吃牌：只能碰或杠

🩸 血流模式：
• 每局必须胡牌到无法再胡（流局）
• 胡牌后继续游戏，直到牌墙摸完
• 期间可多次胡他人或自摸

🔄 游戏流程：
1. 【开始四川麻将】- 开始游戏
2. 【报名麻将】- 报名参与（需要4人）
3. 【定缺 万/条/筒】- 选择缺门
4. 【出牌 牌面】- 出牌
5. 【胡牌】【碰牌】【杠牌】【暗杠 牌面】【过】- 各种操作

💰 计分方式：
• 自摸：所有玩家各付1分
• 点炮：点炮者付3分
• 明杠：立即得1分×3人=3分
• 暗杠：立即得2分×3人=6分
• 查叫：流局时未听牌者赔偿听牌者1分
• 查花猪：手牌有缺门牌者额外赔偿2分

🀄 胡牌牌型：
• 基本胡牌：4副刻子/顺子 + 1对将
• 七对子：7个对子
• 清一色：全部同一花色
• 十八罗汉：4个杠子 + 1对将（特殊胡牌型）

💡 操作格式：
• 定缺 万
• 出牌 5条
• 暗杠 3筒
• 胡牌/碰牌/杠牌/过

🏆 积分规则：
• 参与游戏：+5分
• 胡牌一次：+20分

⚠️ 本游戏仅供娱乐，严禁用于赌博等违法活动！
"""
    await majiang_help.finish(help_text)