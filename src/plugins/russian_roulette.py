from nonebot import on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict, List, Optional
from .game_score import update_player_score
import random
import asyncio
import time

# 俄罗斯转盘游戏状态管理
class RussianRouletteGame:
    def __init__(self):
        self.players = {}  # 玩家信息 {user_id: {"nickname": str, "qq": str}}
        self.game_status = 'waiting'  # 游戏状态：waiting, signup, playing, finished
        self.player_order = []  # 玩家顺序列表
        self.current_player_index = 0  # 当前玩家索引
        self.bullet_position = 0  # 子弹位置 (1-6)
        self.current_shot = 0  # 当前开枪次数
        self.chamber_size = 6  # 弹夹容量
        self.group_id = None  # 群组ID
        self.timeout_task: Optional[asyncio.Task] = None  # 超时任务
        self.last_action_time = 0  # 最后操作时间
        self.timeout_duration = 60  # 超时时间（秒）
        
    def calculate_chamber_size(self):
        """根据玩家数量计算弹夹容量"""
        player_count = len(self.players)
        if player_count <= 4:
            return 6
        else:
            return 6 + (player_count - 4)
        
    def start_signup(self, group_id: str):
        """开始报名阶段"""
        self.game_status = 'signup'
        self.group_id = group_id
        self.players = {}
        self.player_order = []
        self.current_player_index = 0
        self.current_shot = 0
        self.last_action_time = time.time()
        # 取消之前的超时任务
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
        # 初始弹夹容量为6
        self.chamber_size = 6
        # 随机生成子弹位置 (1-6)
        self.bullet_position = random.randint(1, self.chamber_size)
        
    def add_player(self, user_id: str, nickname: str):
        """添加玩家"""
        if self.game_status != 'signup':
            return False, "当前不在报名阶段"
        if user_id in self.players:
            return False, "你已经报名了"
        # 移除最大玩家数限制
            
        self.players[user_id] = {
            "nickname": nickname,
            "qq": user_id
        }
        
        # 动态更新弹夹容量
        self.chamber_size = self.calculate_chamber_size()
        # 重新生成子弹位置
        self.bullet_position = random.randint(1, self.chamber_size)
        
        return True, f"{nickname} 报名成功！当前报名人数：{len(self.players)}，弹夹容量：{self.chamber_size}发"
        
    def start_game(self):
        """开始游戏"""
        if self.game_status != 'signup':
            return False, "当前不在报名阶段"
        if len(self.players) < 2:
            return False, "至少需要2人才能开始游戏"
            
        # 最终确定弹夹容量
        self.chamber_size = self.calculate_chamber_size()
        # 重新生成子弹位置
        self.bullet_position = random.randint(1, self.chamber_size)
        
        # 随机排列玩家顺序
        self.player_order = list(self.players.keys())
        random.shuffle(self.player_order)
        
        self.game_status = 'playing'
        self.current_player_index = 0
        self.current_shot = 0
        self.last_action_time = time.time()
        
        return True, self.get_game_start_message()
        
    def get_game_start_message(self):
        """获取游戏开始消息"""
        message = "🎯 俄罗斯转盘游戏开始！\n"
        message += f"📦 弹夹容量：{self.chamber_size}发（玩家数：{len(self.players)}人）\n"
        message += f"💥 子弹已装填（位置随机）\n\n"
        message += "🎲 玩家顺序：\n"
        for i, player_id in enumerate(self.player_order, 1):
            nickname = self.players[player_id]["nickname"]
            message += f"{i}. {nickname}\n"
        message += "\n⚠️ 游戏规则：\n"
        message += "• 按顺序轮流开枪\n"
        message += "• 中弹者游戏结束，扣除100积分\n"
        message += "• 其他玩家获得50积分\n"
        message += "• 发送'砰'进行游戏\n"
        message += f"• ⏰ 超时{self.timeout_duration}秒未开枪将自动中弹\n\n"
        
        current_player = self.players[self.player_order[0]]["nickname"]
        message += f"🎯 请 @{current_player} 开枪！"
        return message
        
    def shoot(self, user_id: str):
        """开枪"""
        if self.game_status != 'playing':
            return False, "游戏未开始"
            
        # 检查是否轮到该玩家
        current_player_id = self.player_order[self.current_player_index]
        if user_id != current_player_id:
            current_nickname = self.players[current_player_id]["nickname"]
            return False, f"还没轮到你！当前轮到：{current_nickname}"
            
        # 更新最后操作时间
        self.last_action_time = time.time()
        self.current_shot += 1
        current_nickname = self.players[user_id]["nickname"]
        
        # 检查是否中弹
        if self.current_shot == self.bullet_position:
            # 中弹了
            self.game_status = 'finished'
            # 取消超时任务
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()
            return True, self.get_game_end_message(user_id, True)
        else:
            # 没中弹，继续游戏
            if self.current_shot >= self.chamber_size:
                # 所有子弹都打完了，游戏结束（理论上不会发生，因为必定有一发是子弹）
                self.game_status = 'finished'
                # 取消超时任务
                if self.timeout_task and not self.timeout_task.done():
                    self.timeout_task.cancel()
                return True, "🎯 奇迹！所有子弹都是空弹！游戏平局！"
            else:
                # 下一个玩家
                self.current_player_index = (self.current_player_index + 1) % len(self.player_order)
                next_player = self.players[self.player_order[self.current_player_index]]["nickname"]
                message = f"💨 {current_nickname} 开枪...空弹！\n"
                message += f"🎯 请 @{next_player} 开枪！\n"
                message += f"📊 当前进度：{self.current_shot}/{self.chamber_size}\n"
                message += f"⏰ 请在{self.timeout_duration}秒内开枪，否则自动中弹"
                return False, message
                
    def timeout_shoot(self):
        """超时开枪（自动中弹）"""
        if self.game_status != 'playing':
            return False, "游戏未开始"
            
        current_player_id = self.player_order[self.current_player_index]
        current_nickname = self.players[current_player_id]["nickname"]
        
        # 超时自动中弹
        self.game_status = 'finished'
        return True, self.get_timeout_end_message(current_player_id)
        
    def get_timeout_end_message(self, timeout_player_id: str):
        """获取超时结束消息"""
        timeout_nickname = self.players[timeout_player_id]["nickname"]
        
        message = f"⏰ {timeout_nickname} 超时未开枪，自动中弹！游戏结束！\n\n"
        message += "🏆 游戏结果：\n"
        message += f"💀 超时中弹者：{timeout_nickname} (-100积分)\n"
        message += "🎉 幸存者：\n"
        
        for player_id in self.players:
            if player_id != timeout_player_id:
                nickname = self.players[player_id]["nickname"]
                message += f"   • {nickname} (+50积分)\n"
                
        message += "\n💡 发送'开始转盘'可以开始新游戏"
        return message
                
    def get_game_end_message(self, loser_id: str, hit: bool):
        """获取游戏结束消息"""
        loser_nickname = self.players[loser_id]["nickname"]
        
        if hit:
            message = f"💥 {loser_nickname} 中弹了！游戏结束！\n\n"
            message += "🏆 游戏结果：\n"
            message += f"💀 中弹者：{loser_nickname} (-100积分)\n"
            message += "🎉 幸存者：\n"
            
            for player_id in self.players:
                if player_id != loser_id:
                    nickname = self.players[player_id]["nickname"]
                    message += f"   • {nickname} (+50积分)\n"
                    
            message += "\n💡 发送'开始转盘'可以开始新游戏"
            return message
        else:
            return "🎯 游戏异常结束"
            
    def force_end_game(self):
        """强制结束游戏"""
        if self.game_status == 'waiting':
            return False, "当前没有进行中的游戏"
            
        # 取消超时任务
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
            
        old_status = self.game_status
        self.reset_game()
        
        if old_status == 'signup':
            return True, "📝 转盘报名已强制结束"
        elif old_status == 'playing':
            return True, "🎯 转盘游戏已强制结束，无积分变动"
        else:
            return True, "🎯 游戏已强制结束"
            
    def get_status_message(self):
        """获取当前状态消息"""
        if self.game_status == 'waiting':
            return "🎯 当前没有进行中的俄罗斯转盘游戏\n💡 发送'开始转盘'开始新游戏"
        elif self.game_status == 'signup':
            message = "📝 俄罗斯转盘报名中...\n\n"
            message += f"👥 当前报名人数：{len(self.players)}/8\n"
            if self.players:
                message += "📋 报名列表：\n"
                for i, (user_id, info) in enumerate(self.players.items(), 1):
                    message += f"{i}. {info['nickname']}\n"
            message += "\n💡 发送'biu'参与游戏\n"
            message += "💡 发送'结束转盘报名'开始游戏\n"
            message += "💡 发送'强制结束转盘'取消游戏"
            return message
        elif self.game_status == 'playing':
            current_player = self.players[self.player_order[self.current_player_index]]["nickname"]
            elapsed_time = int(time.time() - self.last_action_time)
            remaining_time = max(0, self.timeout_duration - elapsed_time)
            
            message = f"🎯 俄罗斯转盘进行中...\n\n"
            message += f"🎲 当前轮到：{current_player}\n"
            message += f"📊 进度：{self.current_shot}/{self.chamber_size}\n"
            message += f"⏰ 剩余时间：{remaining_time}秒\n\n"
            message += "🎮 玩家顺序：\n"
            for i, player_id in enumerate(self.player_order):
                nickname = self.players[player_id]["nickname"]
                status = "👉" if i == self.current_player_index else "  "
                message += f"{status} {i+1}. {nickname}\n"
            message += "\n💡 发送'强制结束转盘'取消游戏"
            return message
        else:
            return "🎯 游戏已结束\n💡 发送'开始转盘'开始新游戏"
            
    def reset_game(self):
        """重置游戏"""
        # 取消超时任务
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
            
        self.players = {}
        self.game_status = 'waiting'
        self.player_order = []
        self.current_player_index = 0
        self.current_shot = 0
        self.bullet_position = 0
        self.group_id = None
        self.timeout_task = None
        self.last_action_time = 0

# 全局游戏实例管理
games: Dict[str, RussianRouletteGame] = {}

def get_game(group_id: str) -> RussianRouletteGame:
    """获取或创建游戏实例"""
    if group_id not in games:
        games[group_id] = RussianRouletteGame()
    return games[group_id]

async def timeout_handler(group_id: str, bot: Bot):
    """超时处理函数"""
    try:
        await asyncio.sleep(60)  # 等待60秒
        game = get_game(group_id)
        
        if game.game_status == 'playing':
            # 检查是否真的超时了
            elapsed_time = time.time() - game.last_action_time
            if elapsed_time >= game.timeout_duration:
                current_player_id = game.player_order[game.current_player_index]
                is_end, message = game.timeout_shoot()
                
                if is_end:
                    # 更新积分
                    if "超时" in message:
                        # 扣除超时者积分
                        await update_player_score(current_player_id, group_id, -100, "俄罗斯转盘", "超时中弹者", "失败")
                        
                        # 给幸存者加分
                        for player_id in game.players:
                            if player_id != current_player_id:
                                await update_player_score(player_id, group_id, 50, "俄罗斯转盘", "幸存者", "胜利")
                    
                    # 发送超时消息
                    from nonebot import get_bot
                    try:
                        bot = get_bot()
                        await bot.send_group_msg(group_id=int(group_id), message=message)
                        # 艾特超时的玩家
                        at_message = MessageSegment.at(current_player_id)
                        await bot.send_group_msg(group_id=int(group_id), message=at_message + " 你超时了！")
                    except Exception as e:
                        print(f"发送超时消息失败: {e}")
                    
                    game.reset_game()
    except asyncio.CancelledError:
        # 任务被取消，正常情况
        pass
    except Exception as e:
        print(f"超时处理异常: {e}")

# 命令处理器
start_roulette = on_regex(pattern=r"^开始转盘$", priority=5)
signup_roulette = on_regex(pattern=r"^biu$", priority=5)
end_signup = on_regex(pattern=r"^结束转盘报名$", priority=5)
shoot_gun = on_regex(pattern=r"^砰$", priority=5)
roulette_status = on_regex(pattern=r"^转盘状态$", priority=5)
roulette_rules = on_regex(pattern=r"^转盘规则$", priority=5)
force_end_roulette = on_regex(pattern=r"^强制结束转盘$", priority=5)

@start_roulette.handle()
async def handle_start_roulette(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    if game.game_status == 'signup':
        await start_roulette.send("❌ 已有转盘游戏在报名中")
        return
    elif game.game_status == 'playing':
        await start_roulette.send("❌ 已有转盘游戏在进行中")
        return
        
    game.start_signup(group_id)
    message = "🎯 俄罗斯转盘游戏开始报名！\n\n"
    message += "🎮 游戏规则：\n"
    message += "• 弹夹容量6发，其中1发是实弹\n"
    message += "• 玩家轮流开枪，中弹者游戏结束\n"
    message += "• 中弹者扣除100积分\n"
    message += "• 幸存者每人获得50积分\n"
    message += f"• ⏰ 开枪超时{game.timeout_duration}秒自动中弹\n\n"
    message += "📝 发送'biu'参与游戏\n"
    message += "📝 发送'结束转盘报名'开始游戏\n"
    message += "📝 发送'转盘状态'查看当前状态\n"
    message += "📝 发送'强制结束转盘'取消游戏"
    
    await start_roulette.send(message)

@signup_roulette.handle()
async def handle_signup_roulette(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    nickname = event.sender.card or event.sender.nickname or f"用户{user_id}"
    
    game = get_game(group_id)
    success, message = game.add_player(user_id, nickname)
    
    await signup_roulette.send(message)

@end_signup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    success, message = game.start_game()
    
    if success:
        await end_signup.send(message)
        # 艾特第一个玩家
        first_player_id = game.player_order[0]
        at_message = MessageSegment.at(first_player_id)
        await end_signup.send(at_message + f" 轮到你了！发送'砰'进行游戏（{game.timeout_duration}秒内）")
        
        # 启动超时任务
        game.timeout_task = asyncio.create_task(timeout_handler(group_id, bot))
    else:
        await end_signup.send(f"❌ {message}")

@shoot_gun.handle()
async def handle_shoot_gun(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    game = get_game(group_id)
    is_end, message = game.shoot(user_id)
    
    if is_end:
        # 游戏结束，更新积分
        if "中弹" in message:
            # 有人中弹
            loser_id = user_id
            # 扣除中弹者积分
            await update_player_score(loser_id, group_id, -100, "俄罗斯转盘", "中弹者", "失败")
            
            # 给幸存者加分
            for player_id in game.players:
                if player_id != loser_id:
                    await update_player_score(player_id, group_id, 50, "俄罗斯转盘", "幸存者", "胜利")
        
        await shoot_gun.send(message)
        game.reset_game()
    else:
        await shoot_gun.send(message)
        # 如果游戏继续，艾特下一个玩家并重新启动超时任务
        if game.game_status == 'playing':
            next_player_id = game.player_order[game.current_player_index]
            at_message = MessageSegment.at(next_player_id)
            await shoot_gun.send(at_message + f" 轮到你了！（{game.timeout_duration}秒内开枪）")
            
            # 取消之前的超时任务并启动新的
            if game.timeout_task and not game.timeout_task.done():
                game.timeout_task.cancel()
            game.timeout_task = asyncio.create_task(timeout_handler(group_id, bot))

@force_end_roulette.handle()
async def handle_force_end_roulette(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    success, message = game.force_end_game()
    
    if success:
        await force_end_roulette.send(f"✅ {message}")
    else:
        await force_end_roulette.send(f"❌ {message}")

@roulette_status.handle()
async def handle_roulette_status(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    message = game.get_status_message()
    await roulette_status.send(message)

@roulette_rules.handle()
async def handle_roulette_rules(bot: Bot, event: GroupMessageEvent):
    message = "🎯 俄罗斯转盘游戏规则\n\n"
    message += "📋 游戏流程：\n"
    message += "1. 发送'开始转盘'开始报名\n"
    message += "2. 发送'biu'参与游戏\n"
    message += "3. 发送'结束转盘报名'开始游戏\n"
    message += "4. 按顺序发送'砰'进行游戏\n\n"
    message += "🎮 游戏规则：\n"
    message += "• 弹夹容量6发，其中1发是实弹\n"
    message += "• 玩家按随机顺序轮流开枪\n"
    message += "• 中弹者游戏立即结束\n"
    message += "• ⏰ 超时60秒未开枪自动中弹\n\n"
    message += "🏆 积分规则：\n"
    message += "• 中弹者：-100积分\n"
    message += "• 超时中弹者：-100积分\n"
    message += "• 幸存者：+50积分\n\n"
    message += "💡 其他命令：\n"
    message += "• '转盘状态' - 查看当前游戏状态\n"
    message += "• '转盘规则' - 查看游戏规则\n"
    message += "• '强制结束转盘' - 强制结束当前游戏"
    
    await roulette_rules.send(message)