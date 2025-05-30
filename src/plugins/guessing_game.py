from nonebot import on_command,on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict
import random
import asyncio

# 游戏状态管理
class GuessingGame:
    def __init__(self):
        self.target_number = 0  # 目标数字
        self.players = {}  # 玩家信息 {user_id: {"nickname": str, "number": int}}
        self.game_status = 'waiting_signup'  # 游戏状态：waiting_signup, playing, finished
        self.current_min = 1  # 当前最小值
        self.current_max = 100  # 当前最大值
        self.guessed_numbers = set()  # 已经猜过的数字
        self.player_count = 0  # 玩家计数（用于分配编号）
        self.player_order = []  # 玩家顺序
        self.current_player_index = 0  # 当前玩家索引

    def init_game(self):
        self.target_number = random.randint(1, 100)
        self.current_min = 1
        self.current_max = 100
        self.guessed_numbers = set()
        # 随机打乱玩家顺序
        self.player_order = list(self.players.keys())
        random.shuffle(self.player_order)
        self.current_player_index = 0

# 全局游戏状态
games: Dict[int, GuessingGame] = {}

# 注册命令
start_game = on_regex(pattern=r"^开始开口中$", priority=5)
signup = on_regex(pattern=r"^报名开口中$", priority=5)
end_signup = on_regex(pattern=r"^结束开口中报名$", priority=5)
force_end = on_regex(pattern=r"^强制结束开口中$", priority=5)
guess = on_regex(pattern=r"^猜数\s*\d+$", priority=5)

@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id in games and games[group_id].game_status != 'finished':
        await start_game.finish("游戏已经在进行中！")
        return

    games[group_id] = GuessingGame()
    await start_game.finish("开口中游戏开始！请玩家发送【报名开口中】进行报名，通过【结束开口中报名】来结束报名阶段，开始游戏。")

@signup.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games:
        await signup.finish("游戏还未开始，请先发送【开始开口中】开始游戏。")
        return
        
    game = games[group_id]
    if game.game_status != 'waiting_signup':
        await signup.finish("当前不在报名阶段！")
        return
        
    if user_id in game.players:
        await signup.finish("你已经报名了！")
        return

    # 获取玩家信息并分配编号
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    game.player_count += 1
    game.players[user_id] = {
        "nickname": user_info['nickname'],
        "number": game.player_count
    }
    
    await signup.finish(f"玩家 {user_info['nickname']} (编号 {game.player_count}) 报名成功！")

@end_signup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games:
        await end_signup.finish("游戏还未开始！")
        return
        
    game = games[group_id]
    if game.game_status != 'waiting_signup':
        await end_signup.finish("当前不在报名阶段！")
        return
        
    if len(game.players) < 2:
        await end_signup.finish("至少需要2名玩家才能开始游戏！")
        return

    # 初始化游戏
    game.init_game()
    game.game_status = 'playing'
    
    # 生成玩家列表消息
    player_list = "\n".join([f"{game.players[uid]['nickname']} (编号 {game.players[uid]['number']})" 
                           for uid in game.player_order])
    
    msg = "报名结束，游戏开始！\n"
    msg += "游戏规则：\n"
    msg += "1. 目标数字在1-100之间\n"
    msg += "2. 玩家按顺序发送【猜数 数字】进行猜测\n"
    msg += "3. 每次猜测后会更新数字范围\n"
    msg += "4. 猜中数字的玩家失败\n\n"
    msg += f"玩家顺序：\n{player_list}\n\n"
    msg += f"当前数字范围：{game.current_min} - {game.current_max}\n"
    msg += f"轮到 {game.players[game.player_order[0]]['nickname']} (编号 {game.players[game.player_order[0]]['number']}) 猜数" + '\n'
    msg += "请发送【猜数 数字】进行猜测"
    msg += "\n"
    msg += MessageSegment.at(game.player_order[0])
    await end_signup.finish(msg)

@guess.handle()
async def handle_guess(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games:
        return
        
    game = games[group_id]
    if game.game_status != 'playing':
        return
        
    if user_id not in game.players:
        await guess.finish("你不是游戏参与者！")
        return

    # 检查是否轮到该玩家
    current_player = game.player_order[game.current_player_index]
    if user_id != current_player:
        await guess.finish(f"还没轮到你！现在是 {game.players[current_player]['nickname']} (编号 {game.players[current_player]['number']}) 的回合")
        return

    # 获取猜测的数字
    args = str(event.get_message()).strip()
    try:
        guessed_number = int(args[2:].strip())
    except ValueError:
        await guess.finish("请输入有效的数字！")
        return

    # 检查数字是否在范围内
    if guessed_number < game.current_min or guessed_number > game.current_max:
        await guess.finish(f"请猜测在 {game.current_min} - {game.current_max} 范围内的数字！")
        return

    # 检查数字是否已经猜过
    if guessed_number in game.guessed_numbers:
        await guess.finish("这个数字已经被猜过了！")
        return

    game.guessed_numbers.add(guessed_number)

    if guessed_number == game.target_number:
        # 游戏结束，当前玩家失败
        game.game_status = 'finished'
        msg = f"玩家 {game.players[user_id]['nickname']} (编号 {game.players[user_id]['number']}) 猜中了数字 {guessed_number}，游戏结束！\n"
        msg += f"很遗憾，{game.players[user_id]['nickname']} 失败了！\n"
        msg += "其他玩家获胜！"
        await guess.finish(msg)
    else:
        # 更新范围
        if guessed_number < game.target_number:
            game.current_min = guessed_number + 1
            msg = f"玩家 {game.players[user_id]['nickname']} (编号 {game.players[user_id]['number']}) 猜测的数字 {guessed_number} 太小了！\n"
        else:
            game.current_max = guessed_number - 1
            msg = f"玩家 {game.players[user_id]['nickname']} (编号 {game.players[user_id]['number']}) 猜测的数字 {guessed_number} 太大了！\n"
        
        # 更新当前玩家
        game.current_player_index = (game.current_player_index + 1) % len(game.player_order)
        next_player = game.player_order[game.current_player_index]
        
        msg += f"当前范围：{game.current_min} - {game.current_max}\n"
        msg += "\n"
        msg += MessageSegment.at(next_player) + "\n"
        msg += f"轮到 {game.players[next_player]['nickname']} (编号 {game.players[next_player]['number']}) 猜数"
        await guess.finish(msg)

@force_end.handle()
async def handle_force_end(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games:
        await force_end.finish("没有正在进行的游戏！")
        return

    game = games[group_id]
    if game.game_status == 'finished':
        await force_end.finish("游戏已经结束！")
        return

    game.game_status = 'finished'
    msg = "游戏被强制结束！\n"
    if game.game_status == 'playing':
        msg += f"目标数字是：{game.target_number}"
    
    await force_end.finish(msg)

guessing_help = on_regex(pattern=r"^开口中帮助$", priority=5)

@guessing_help.handle()
async def handle_help(bot: Bot, event: GroupMessageEvent):
    msg = "开口中游戏帮助：\n"
    msg += "【游戏规则】\n"
    msg += "1. 系统会在1-100之间随机选择一个数字作为目标数字\n"
    msg += "2. 玩家轮流猜测数字，每次猜测后会更新可能的数字范围\n"
    msg += "3. 不能重复猜已经猜过的数字\n"
    msg += "4. 猜中目标数字的玩家失败，其他玩家获胜\n\n"
    msg += "【游戏命令】\n"
    msg += "1. 开始开口中：创建新游戏\n"
    msg += "2. 报名开口中：参加游戏\n"
    msg += "3. 结束开口中报名：结束报名，开始游戏\n"
    msg += "4. 猜数 数字：进行猜测（如：猜数 50）\n"
    msg += "5. 强制结束开口中：强制结束当前游戏\n"
    msg += "6. 开口中帮助：显示本帮助信息"
    
    await guessing_help.finish(msg)