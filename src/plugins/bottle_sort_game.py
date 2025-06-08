from nonebot import on_regex, on_message
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, MessageSegment
from typing import Dict, List, Optional, Tuple
from .game_score import update_player_score
import random
import asyncio
import time
import re
from enum import Enum
from dataclasses import dataclass

# 游戏状态枚举
class GameState(Enum):
    WAITING = "waiting"
    SIGNUP = "signup"
    PLAYING = "playing"
    FINISHED = "finished"

# 颜色定义
COLORS = [
    ("🔴", "红色"),
    ("🟠", "橙色"),
    ("🟡", "黄色"),
    ("🟢", "绿色"),
    ("🔵", "蓝色"),
    ("🟣", "紫色"),
    ("🟤", "棕色")
]

@dataclass
class Player:
    user_id: str
    nickname: str
    score: int = 0
    correct_moves: int = 0
    wrong_moves: int = 0
    timeout_count: int = 0
    last_move_time: float = 0

@dataclass
class GameMove:
    player_id: str
    pos1: int
    pos2: int
    timestamp: float
    correct_count: int  # 这次移动正确放置的瓶子数量

class BottleSortGame:
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.state = GameState.WAITING
        self.players: Dict[str, Player] = {}
        self.player_order: List[str] = []
        self.current_player_index = 0
        
        # 游戏配置
        self.bottle_count = 7
        self.move_timeout = 60  # 每次移动的超时时间（秒）
        self.game_duration = 600  # 游戏总时长（秒）
        
        # 游戏状态
        self.target_order = list(range(7))  # 目标顺序 [0,1,2,3,4,5,6]
        self.current_order = list(range(7))  # 当前外部瓶子顺序
        random.shuffle(self.current_order)  # 打乱外部瓶子顺序
        
        self.moves_history: List[GameMove] = []
        self.start_time = 0
        self.last_move_time = 0
        self.timeout_task: Optional[asyncio.Task] = None
        self.game_timeout_task: Optional[asyncio.Task] = None
        
    def add_player(self, user_id: str, nickname: str) -> Tuple[bool, str]:
        """添加玩家"""
        if self.state != GameState.SIGNUP:
            return False, "当前不在报名阶段"
        
        if user_id in self.players:
            return False, "你已经报名了"
        
        if len(self.players) >= 8:
            return False, "游戏人数已满（最多8人）"
        
        self.players[user_id] = Player(user_id=user_id, nickname=nickname)
        return True, f"玩家 {nickname} 报名成功"
    
    def start_game(self) -> Tuple[bool, str]:
        """开始游戏"""
        if self.state != GameState.SIGNUP:
            return False, "游戏不在报名阶段"
        
        if len(self.players) < 1:
            return False, "至少需要1名玩家才能开始游戏"
        
        self.state = GameState.PLAYING
        self.player_order = list(self.players.keys())
        random.shuffle(self.player_order)
        self.current_player_index = 0
        self.start_time = time.time()
        self.last_move_time = time.time()
        
        return True, "游戏开始！"
    
    def get_current_player(self) -> Optional[Player]:
        """获取当前玩家"""
        if not self.player_order:
            return None
        return self.players[self.player_order[self.current_player_index]]
    
    def next_player(self):
        """切换到下一个玩家"""
        self.current_player_index = (self.current_player_index + 1) % len(self.player_order)
    
    def make_move(self, player_id: str, pos1: int, pos2: int) -> Tuple[bool, str, int]:
        """执行移动"""
        if self.state != GameState.PLAYING:
            return False, "游戏未在进行中", 0
        
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player_id:
            return False, "不是你的回合", 0
        
        if pos1 < 0 or pos1 >= self.bottle_count or pos2 < 0 or pos2 >= self.bottle_count:
            return False, "位置超出范围", 0
        
        if pos1 == pos2:
            return False, "不能交换相同位置的瓶子", 0
        
        # 记录移动前的正确数量
        before_correct = self.count_correct_positions()
        
        # 执行交换
        self.current_order[pos1], self.current_order[pos2] = self.current_order[pos2], self.current_order[pos1]
        
        # 记录移动后的正确数量
        after_correct = self.count_correct_positions()
        correct_change = after_correct - before_correct
        
        # 计算分数变化
        score_change = 0
        if correct_change > 0:
            score_change = correct_change * 5  # 每个正确位置+5分
            current_player.correct_moves += 1
        elif correct_change < 0:
            score_change = correct_change * 5  # 每个错误位置-5分
            current_player.wrong_moves += 1
        
        current_player.score += score_change
        current_player.last_move_time = time.time()
        
        # 记录移动
        move = GameMove(
            player_id=player_id,
            pos1=pos1,
            pos2=pos2,
            timestamp=time.time(),
            correct_count=max(0, correct_change)
        )
        self.moves_history.append(move)
        
        self.last_move_time = time.time()
        
        # 检查是否完成
        if self.is_completed():
            self.state = GameState.FINISHED
            return True, "恭喜完成游戏！", score_change
        
        # 切换到下一个玩家
        self.next_player()
        
        return True, f"移动成功，分数变化：{score_change:+d}", score_change
    
    def handle_timeout(self, player_id: str):
        """处理超时"""
        if player_id in self.players:
            player = self.players[player_id]
            player.score -= 10  # 超时扣10分
            player.timeout_count += 1
        
        # 切换到下一个玩家
        self.next_player()
        self.last_move_time = time.time()
    
    def count_correct_positions(self) -> int:
        """计算当前正确位置的数量"""
        return sum(1 for i in range(self.bottle_count) if self.current_order[i] == self.target_order[i])
    
    def is_completed(self) -> bool:
        """检查是否完成"""
        return self.current_order == self.target_order
    
    def get_board_display(self, show_target: bool = False) -> str:
        """获取游戏面板显示"""
        display = "🎯 目标顺序（盒子内部）：\n"
        if show_target:
            target_line = "".join([f"{i+1}{COLORS[i][0]}" for i in self.target_order])
            display += f"📦 {target_line}\n\n"
        else:
            display += "📦 ❓❓❓❓❓❓❓ （隐藏）\n\n"
        
        display += "🔄 当前顺序（盒子外部）：\n"
        current_line = "".join([f"【{i+1} {COLORS[color][0]}】\n" for i, color in enumerate(self.current_order)])
        display += f"{current_line}\n\n"
        
        # 显示正确位置数量
        correct_count = self.count_correct_positions()
        display += f"✅ 正确位置：{correct_count}/{self.bottle_count}\n"
        
        return display
    
    def get_game_summary(self) -> str:
        """获取游戏总结"""
        game_duration = int(time.time() - self.start_time)
        
        summary = "🎮 瓶子排序游戏结束！\n\n"
        summary += self.get_board_display(show_target=True)
        
        # 排行榜
        sorted_players = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        summary += "🏆 最终排名：\n"
        for i, player in enumerate(sorted_players, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📍"
            summary += f"{emoji} {i}. {player.nickname} - {player.score}分\n"
            summary += f"   ✅正确:{player.correct_moves} ❌错误:{player.wrong_moves} ⏰超时:{player.timeout_count}\n"
        
        summary += f"\n⏱️ 游戏时长：{game_duration // 60}分{game_duration % 60}秒\n"
        summary += f"🔄 总移动次数：{len(self.moves_history)}次"
        
        return summary

# 游戏实例存储
games: Dict[str, BottleSortGame] = {}

# 命令注册
start_bottle_game = on_regex(pattern=r"^(开始瓶子游戏|瓶子排序|开始瓶子)$", priority=5)
signup_bottle = on_regex(pattern=r"^(报名瓶子|报名排序|加入瓶子游戏)$", priority=5)
start_bottle_playing = on_regex(pattern=r"^(结束瓶子报名)$", priority=5)
move_bottles = on_regex(pattern=r"^(移动|交换|move)\s+(\d+)\s+(\d+)$", priority=5)
bottle_status = on_regex(pattern=r"^(瓶子状态|游戏状态|排序状态)$", priority=5)
end_bottle_game = on_regex(pattern=r"^(强制结束瓶子)$", priority=5)
bottle_rules = on_regex(pattern=r"^(瓶子游戏规则|排序游戏规则)$", priority=5)

@start_bottle_game.handle()
async def handle_start_bottle_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id in games and games[group_id].state != GameState.FINISHED:
        await start_bottle_game.finish("瓶子排序游戏已经在进行中！")
    
    games[group_id] = BottleSortGame(group_id)
    games[group_id].state = GameState.SIGNUP
    
    await start_bottle_game.finish(
        "🎮 瓶子排序游戏开始！\n\n"
        "📝 游戏说明：\n"
        "• 盒子内有7个颜色瓶子（隐藏顺序）\n"
        "• 盒子外有相同颜色瓶子（顺序打乱）\n"
        "• 目标：让内外顺序一致\n\n"
        "🎯 请发送【报名瓶子】参与游戏\n"
        "🚀 发送【结束瓶子报名】开始游戏\n"
        "📋 发送【瓶子游戏规则】查看详细规则"
    )

@signup_bottle.handle()
async def handle_signup_bottle(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await signup_bottle.finish("游戏还未开始，请先发送【开始瓶子游戏】")
    
    game = games[group_id]
    
    # 获取玩家信息
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'玩家{user_id}')
    except:
        nickname = f'玩家{user_id}'
    
    success, message = game.add_player(user_id, nickname)
    
    if success:
        # 添加参与游戏基础分
        await update_player_score(user_id, group_id, 5, 'bottle_sort', None, 'participation')
        await signup_bottle.finish(f"🎯 {message}！当前玩家数：{len(game.players)}")
    else:
        await signup_bottle.finish(f"❌ {message}")

@start_bottle_playing.handle()
async def handle_start_bottle_playing(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await start_bottle_playing.finish("游戏还未开始，请先发送【开始瓶子游戏】")
    
    game = games[group_id]
    success, message = game.start_game()
    
    if success:
        # 启动游戏超时任务
        game.game_timeout_task = asyncio.create_task(game_timeout(bot, group_id))
        
        # 启动第一个玩家的移动超时任务
        game.timeout_task = asyncio.create_task(move_timeout(bot, group_id))
        
        current_player = game.get_current_player()
        
        await start_bottle_playing.finish(
            f"🎮 {message}\n\n"
            f"{game.get_board_display()}\n"
            f"👤 当前玩家：{current_player.nickname}\n"
            f"💡 发送【移动 位置1 位置2】来交换瓶子\n"
            f"⏰ 每次移动限时 {game.move_timeout} 秒\n" + MessageSegment.at(current_player.user_id)
        )
    else:
        await start_bottle_playing.finish(f"❌ {message}")

@move_bottles.handle()
async def handle_move_bottles(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await move_bottles.finish("当前没有进行中的瓶子排序游戏！")
    
    game = games[group_id]
    
    # 解析移动命令
    match = re.match(r"^(移动|交换|move)\s+(\d+)\s+(\d+)$", event.get_plaintext())
    if not match:
        await move_bottles.finish("❌ 命令格式错误，请使用：移动 位置1 位置2")
    
    pos1 = int(match.group(2)) - 1  # 转换为0索引
    pos2 = int(match.group(3)) - 1  # 转换为0索引
    
    success, message, score_change = game.make_move(user_id, pos1, pos2)
    
    if success:
        # 取消当前超时任务
        if game.timeout_task:
            game.timeout_task.cancel()
        
        response = f"✅ {message}\n\n{game.get_board_display()}"
        
        if game.state == GameState.FINISHED:
            # 游戏结束
            if game.game_timeout_task:
                game.game_timeout_task.cancel()
            
            # 计算最终奖励
            await calculate_final_rewards(game)
            
            summary = game.get_game_summary()
            
            # 清理游戏数据
            del games[group_id]
            
            await move_bottles.finish(f"{response}\n\n{summary}")
        else:
            # 继续游戏，启动下一个玩家的超时任务
            game.timeout_task = asyncio.create_task(move_timeout(bot, group_id))
            
            current_player = game.get_current_player()
            response += f"\n👤 下一位玩家：{current_player.nickname}\n" + MessageSegment.at(current_player.user_id)
            
            await move_bottles.finish(response)
    else:
        await move_bottles.finish(f"❌ {message}")

@bottle_status.handle()
async def handle_bottle_status(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await bottle_status.finish("当前没有进行中的瓶子排序游戏！")
    
    game = games[group_id]
    
    if game.state == GameState.SIGNUP:
        player_list = "\n".join([f"{i+1}. {player.nickname}" for i, player in enumerate(game.players.values())])
        status_msg = (
            f"🎮 瓶子排序游戏状态\n\n"
            f"📊 当前阶段：报名中\n"
            f"👥 已报名玩家（{len(game.players)}人）：\n{player_list or '暂无玩家'}"
        )
    elif game.state == GameState.PLAYING:
        current_player = game.get_current_player()
        game_duration = int(time.time() - game.start_time)
        
        status_msg = (
            f"🎮 瓶子排序游戏状态\n\n"
            f"{game.get_board_display()}\n"
            f"👤 当前玩家：{current_player.nickname}\n"
            f"⏱️ 游戏时长：{game_duration // 60}分{game_duration % 60}秒\n"
            f"🔄 移动次数：{len(game.moves_history)}次\n\n"
            f"📊 玩家分数：\n"
        )
        
        for player in game.players.values():
            status_msg += f"• {player.nickname}：{player.score}分\n"
    else:
        status_msg = "游戏已结束或未开始"
    
    await bottle_status.finish(status_msg)

@end_bottle_game.handle()
async def handle_end_bottle_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await end_bottle_game.finish("当前没有进行中的瓶子排序游戏！")
    
    # 检查权限（群管理员或游戏参与者可以结束游戏）
    try:
        member_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        is_admin = member_info.get('role') in ['admin', 'owner']
        is_player = user_id in games[group_id].players
        
        if not (is_admin or is_player):
            await end_bottle_game.finish("只有群管理员或游戏参与者可以结束游戏！")
    except:
        if user_id not in games[group_id].players:
            await end_bottle_game.finish("只有游戏参与者可以结束游戏！")
    
    game = games[group_id]
    
    # 取消所有任务
    if game.timeout_task:
        game.timeout_task.cancel()
    if game.game_timeout_task:
        game.game_timeout_task.cancel()
    
    summary = "🎮 瓶子排序游戏被强制结束！"
    
    if game.state == GameState.PLAYING and game.players:
        summary = game.get_game_summary()
    
    # 清理游戏数据
    del games[group_id]
    
    await end_bottle_game.finish(summary)

@bottle_rules.handle()
async def handle_bottle_rules(bot: Bot, event: GroupMessageEvent):
    rules = (
        "🎮 瓶子排序游戏规则\n\n"
        "📝 游戏目标：\n"
        "让盒子外部的瓶子顺序与内部顺序一致\n\n"
        "🎯 游戏流程：\n"
        "1. 发送【开始瓶子】创建游戏\n"
        "2. 发送【报名瓶子】参与游戏\n"
        "3. 发送【结束瓶子报名】开始游戏\n"
        "4. 轮流发送【移动 位置1 位置2】交换瓶子\n\n"
        "💯 计分规则：\n"
        "• 将瓶子移到正确位置：+5分/个\n"
        "• 将瓶子移到错误位置：-5分/个\n"
        "• 超时未移动：-10分\n"
        "• 完成游戏额外奖励\n\n"
        "⏰ 时间限制：\n"
        "• 每次移动限时60秒\n"
        "• 游戏总时长10分钟\n\n"
        "🎲 其他命令：\n"
        "• 瓶子状态 - 查看游戏状态\n"
        "• 强制结束瓶子 - 强制结束游戏"
    )
    
    await bottle_rules.finish(rules)

# 超时处理函数
async def move_timeout(bot: Bot, group_id: str):
    """移动超时处理"""
    try:
        if group_id not in games:
            return
        
        game = games[group_id]
        await asyncio.sleep(game.move_timeout)
        
        # 检查游戏是否仍在进行
        if group_id in games and games[group_id].state == GameState.PLAYING:
            current_player = game.get_current_player()
            if current_player:
                game.handle_timeout(current_player.user_id)
                
                await bot.send_group_msg(
                    group_id=int(group_id),
                    message=f"⏰ {current_player.nickname} 移动超时，扣除10分！\n\n"
                           f"👤 下一位玩家：{game.get_current_player().nickname}\n"  + MessageSegment.at(game.get_current_player().user_id)
                )
                
                # 启动下一个玩家的超时任务
                game.timeout_task = asyncio.create_task(move_timeout(bot, group_id))
    
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"移动超时处理出错: {e}")

async def game_timeout(bot: Bot, group_id: str):
    """游戏总超时处理"""
    try:
        if group_id not in games:
            return
        
        game = games[group_id]
        await asyncio.sleep(game.game_duration)
        
        # 检查游戏是否仍在进行
        if group_id in games and games[group_id].state == GameState.PLAYING:
            game.state = GameState.FINISHED
            
            # 取消移动超时任务
            if game.timeout_task:
                game.timeout_task.cancel()
            
            # 计算最终奖励
            await calculate_final_rewards(game)
            
            summary = game.get_game_summary()
            
            await bot.send_group_msg(
                group_id=int(group_id),
                message=f"⏰ 游戏时间到！\n\n{summary}"
            )
            
            # 清理游戏数据
            del games[group_id]
    
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"游戏超时处理出错: {e}")

async def calculate_final_rewards(game: BottleSortGame):
    """计算最终奖励"""
    try:
        # 游戏完成奖励
        completion_bonus = 50 if game.is_completed() else 20
        
        # 时间奖励（越快完成奖励越高）
        game_duration = time.time() - game.start_time
        time_bonus = max(0, int((game.game_duration - game_duration) / 60 * 5))
        
        for player in game.players.values():
            # 基础完成奖励
            await update_player_score(player.user_id, game.group_id, completion_bonus, 'bottle_sort', None, 'completion')
            
            # 时间奖励
            if time_bonus > 0:
                await update_player_score(player.user_id, game.group_id, time_bonus, 'bottle_sort', None, 'time_bonus')
            
            # 正确移动奖励
            if player.correct_moves > 0:
                move_bonus = player.correct_moves * 3
                await update_player_score(player.user_id, game.group_id, move_bonus, 'bottle_sort', None, 'correct_moves')
    
    except Exception as e:
        print(f"计算最终奖励时出错: {e}")

# 定期清理已结束的游戏
async def cleanup_finished_games():
    """清理已结束的游戏"""
    while True:
        try:
            current_time = time.time()
            to_remove = []
            
            for group_id, game in games.items():
                # 清理超过1小时的已结束游戏
                if (game.state == GameState.FINISHED and 
                    current_time - game.start_time > 3600):
                    to_remove.append(group_id)
            
            for group_id in to_remove:
                if group_id in games:
                    del games[group_id]
            
            await asyncio.sleep(300)  # 每5分钟清理一次
        except Exception as e:
            print(f"清理瓶子游戏时出错: {e}")
            await asyncio.sleep(300)

# 启动清理任务
from nonebot import get_driver
driver = get_driver()

@driver.on_startup
async def start_cleanup():
    """在bot启动时开始清理任务"""
    asyncio.create_task(cleanup_finished_games())