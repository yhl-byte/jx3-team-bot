from nonebot import on_regex, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, PrivateMessageEvent, MessageSegment
from typing import Dict, List, Optional, Tuple
from .game_score import update_player_score
import random
import asyncio
import time
from enum import Enum
from dataclasses import dataclass

# 游戏状态枚举
class GomokuGameState(Enum):
    WAITING = "waiting"
    SIGNUP = "signup"
    ROCK_PAPER_SCISSORS = "rock_paper_scissors"
    PLAYING = "playing"
    FINISHED = "finished"

# 石头剪刀布选择
class RPSChoice(Enum):
    ROCK = "石头"
    PAPER = "布"
    SCISSORS = "剪刀"

@dataclass
class GomokuPlayer:
    user_id: str
    nickname: str
    piece: str  # "⚫" 或 "⚪"
    rps_choice: Optional[RPSChoice] = None
    rps_submitted: bool = False

@dataclass
class GomokuGame:
    group_id: str
    players: Dict[str, GomokuPlayer]
    board: List[List[str]]  # 9x9棋盘
    current_player_id: Optional[str]
    state: GomokuGameState
    round_count: int
    start_time: float
    winner_id: Optional[str] = None
    last_move: Optional[Tuple[int, int]] = None  # 最后一步棋的位置
    
    def __post_init__(self):
        if not self.board:
            self.board = [["⬜" for _ in range(9)] for _ in range(9)]

# 存储所有游戏实例
games: Dict[str, GomokuGame] = {}

# 游戏命令
start_gomoku = on_regex(pattern=r"^(开始五子棋|五子棋游戏|gomoku)$", priority=5)
join_gomoku = on_regex(pattern=r"^(加入五子棋|参加五子棋)$", priority=5)
rps_choice = on_regex(pattern=r"^五子棋(石头|剪刀|布)$", priority=5)
place_piece = on_regex(pattern=r"^下棋\s*([A-O])([1-9]|1[0-5])$", priority=5)
show_board = on_regex(pattern=r"^(查看棋盘|棋盘状态|五子棋棋盘)$", priority=5)
quit_gomoku = on_regex(pattern=r"^(退出五子棋|结束五子棋)$", priority=5)
gomoku_help = on_regex(pattern=r"^(五子棋帮助|五子棋说明)$", priority=5)

def check_winner(board: List[List[str]], row: int, col: int, piece: str) -> bool:
    """检查是否有玩家获胜（五子连珠）"""
    directions = [
        (0, 1),   # 水平
        (1, 0),   # 垂直
        (1, 1),   # 主对角线
        (1, -1)   # 副对角线
    ]
    
    for dr, dc in directions:
        count = 1  # 包含当前棋子
        
        # 向一个方向检查
        r, c = row + dr, col + dc
        while 0 <= r < 9 and 0 <= c < 9 and board[r][c] == piece:
            count += 1
            r, c = r + dr, c + dc
        
        # 向相反方向检查
        r, c = row - dr, col - dc
        while 0 <= r < 9 and 0 <= c < 9 and board[r][c] == piece:
            count += 1
            r, c = r - dr, c - dc
        
        if count >= 5:
            return True
    
    return False

def format_board(board: List[List[str]], last_move: Optional[Tuple[int, int]] = None) -> str:
    """格式化棋盘显示"""
    result = "  "
    # 列标签 A-O
    for i in range(9):
        result += chr(ord('A') + i) + " "
    result += "\n"
    
    for i in range(9):
        # 行标签 1-9
        result += f"{i+1:2d}"
        for j in range(9):
            piece = board[i][j]
            # 标记最后一步棋
            if last_move and last_move == (i, j):
                if piece == "⚫":
                    piece = "🔴"  # 红色标记黑棋最后一步
                elif piece == "⚪":
                    piece = "🟡"  # 黄色标记白棋最后一步
            result += piece + " "
        result += "\n"
    
    return result

def letter_to_col(letter: str) -> int:
    """将字母转换为列索引"""
    return ord(letter.upper()) - ord('A')

@start_gomoku.handle()
async def handle_start_gomoku(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 检查是否已有游戏在进行
    if group_id in games and games[group_id].state != GomokuGameState.FINISHED:
        await start_gomoku.finish("当前群已有五子棋游戏在进行中！")
    
    # 创建新游戏
    game = GomokuGame(
        group_id=group_id,
        players={},
        board=[["⬜" for _ in range(9)] for _ in range(9)],
        current_player_id=None,
        state=GomokuGameState.SIGNUP,
        round_count=0,
        start_time=time.time()
    )
    
    games[group_id] = game
    
    msg = f"🎮 五子棋游戏开始招募！\n"
    msg += f"发起人：{nickname}\n"
    msg += f"需要2名玩家参与\n"
    msg += f"发送【加入五子棋】参与游戏\n"
    msg += f"发送【五子棋帮助】查看游戏说明"
    
    await start_gomoku.finish(msg)

@join_gomoku.handle()
async def handle_join_gomoku(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await join_gomoku.finish("当前没有五子棋游戏，发送【开始五子棋】创建游戏！")
    
    game = games[group_id]
    
    if game.state != GomokuGameState.SIGNUP:
        await join_gomoku.finish("游戏已开始，无法加入！")
    
    if user_id in game.players:
        await join_gomoku.finish("您已经加入了游戏！")
    
    if len(game.players) >= 2:
        await join_gomoku.finish("游戏人数已满！")
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 分配棋子颜色
    piece = "⚫" if len(game.players) == 0 else "⚪"
    
    player = GomokuPlayer(
        user_id=user_id,
        nickname=nickname,
        piece=piece
    )
    
    game.players[user_id] = player
    
    msg = f"✅ {nickname} 加入游戏！棋子：{piece}\n"
    
    if len(game.players) == 2:
        # 开始石头剪刀布决定先手
        game.state = GomokuGameState.ROCK_PAPER_SCISSORS
        msg += "\n🎲 人数已满，开始石头剪刀布决定先手！\n"
        msg += "请两位玩家私聊发送【五子棋石头|剪刀|布】"
        
        # 设置30秒超时
        asyncio.create_task(rps_timeout(bot,group_id))
    else:
        msg += f"等待第2位玩家加入... ({len(game.players)}/2)"
    
    await join_gomoku.finish(msg)

async def rps_timeout(bot: Bot,group_id: str):
    """石头剪刀布超时处理"""
    await asyncio.sleep(30)
    
    if group_id not in games:
        return
    
    game = games[group_id]
    if game.state != GomokuGameState.ROCK_PAPER_SCISSORS:
        return
    
    # 检查是否有玩家未提交
    unsubmitted = [p for p in game.players.values() if not p.rps_submitted]
    
    if unsubmitted:
        # 随机选择先手
        first_player = random.choice(list(game.players.values()))
        game.current_player_id = first_player.user_id
        game.state = GomokuGameState.PLAYING
        
        msg = f"⏰ 石头剪刀布超时！随机选择 {first_player.nickname} 先手\n"
        msg += f"当前轮到：{first_player.nickname} {first_player.piece}\n"
        msg += "发送【下棋 位置】下棋，如：下棋 H8\n"
        msg += "发送【查看棋盘】查看当前棋盘"
        # 修复消息发送方式
        await bot.send_group_msg(group_id=int(group_id), message=msg)
        
@rps_choice.handle()
async def handle_rps_choice(bot: Bot, event: PrivateMessageEvent):
   # 需要从私聊消息中获取用户所在的游戏群组
    user_id = str(event.user_id)
    choice_text = event.get_plaintext().strip()
    
    # 查找用户参与的游戏
    game_group_id = None
    for group_id, game in games.items():
        if user_id in game.players and game.state == GomokuGameState.ROCK_PAPER_SCISSORS:
            game_group_id = group_id
            break
    
    if not game_group_id:
        await rps_choice.finish("您当前没有参与五子棋游戏或不在石头剪刀布阶段")
    
    game = games[game_group_id]
    game = games[group_id]
    
    if game.state != GomokuGameState.ROCK_PAPER_SCISSORS:
        return
    
    if user_id not in game.players:
        return
    
    player = game.players[user_id]
    
    if player.rps_submitted:
        await rps_choice.finish("您已经提交过选择了！")
    
    # 解析选择
    choice_map = {"石头": RPSChoice.ROCK, "剪刀": RPSChoice.SCISSORS, "布": RPSChoice.PAPER}
    choice = choice_map.get(choice_text)
    
    if not choice:
        return
    
    player.rps_choice = choice
    player.rps_submitted = True
    
    await rps_choice.finish(f"✅ 您选择了{choice_text}！")
    
    # 检查是否所有玩家都已提交
    if all(p.rps_submitted for p in game.players.values()):
        await determine_first_player(bot, game)

async def determine_first_player(bot: Bot, game: GomokuGame):
    """根据石头剪刀布结果决定先手"""
    players = list(game.players.values())
    p1, p2 = players[0], players[1]
    
    # 判断胜负
    def rps_winner(choice1: RPSChoice, choice2: RPSChoice) -> int:
        if choice1 == choice2:
            return 0  # 平局
        elif (choice1 == RPSChoice.ROCK and choice2 == RPSChoice.SCISSORS) or \
             (choice1 == RPSChoice.SCISSORS and choice2 == RPSChoice.PAPER) or \
             (choice1 == RPSChoice.PAPER and choice2 == RPSChoice.ROCK):
            return 1  # 玩家1胜
        else:
            return 2  # 玩家2胜
    
    result = rps_winner(p1.rps_choice, p2.rps_choice)
    
    msg = f"🎲 石头剪刀布结果：\n"
    msg += f"{p1.nickname}：{p1.rps_choice.value}\n"
    msg += f"{p2.nickname}：{p2.rps_choice.value}\n\n"
    
    if result == 0:
        # 平局，重新开始
        for player in game.players.values():
            player.rps_choice = None
            player.rps_submitted = False
        msg += "🤝 平局！请重新选择"
        asyncio.create_task(rps_timeout(bot, game.group_id))
    else:
        # 决出胜负
        winner = p1 if result == 1 else p2
        game.current_player_id = winner.user_id
        game.state = GomokuGameState.PLAYING
        
        msg += f"🏆 {winner.nickname} 获胜！先手下棋\n"
        msg += f"当前轮到：{winner.nickname} {winner.piece}\n"
        msg += "发送【下棋 位置】下棋，如：下棋 H8\n"
        msg += "发送【查看棋盘】查看当前棋盘"
    
    await bot.send_group_msg(group_id=int(game.group_id), message=msg)

@place_piece.handle()
async def handle_place_piece(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        return
    
    game = games[group_id]
    
    if game.state != GomokuGameState.PLAYING:
        return
    
    if user_id not in game.players:
        return
    
    if game.current_player_id != user_id:
        current_player = game.players[game.current_player_id]
        await place_piece.finish(f"现在是 {current_player.nickname} 的回合！")
    
    # 解析位置
    import re
    match = re.match(r"^下棋\s*([A-O])([1-9]|1[0-5])$", event.get_plaintext().strip())
    if not match:
        await place_piece.finish("位置格式错误！请使用如：下棋 H8")
    
    col_letter, row_str = match.groups()
    col = letter_to_col(col_letter)
    row = int(row_str) - 1
    
    # 检查位置是否有效
    if not (0 <= row < 9 and 0 <= col < 9):
        await place_piece.finish("位置超出棋盘范围！")
    
    if game.board[row][col] != "⬜":
        await place_piece.finish("该位置已有棋子！")
    
    # 下棋
    current_player = game.players[user_id]
    game.board[row][col] = current_player.piece
    game.last_move = (row, col)
    game.round_count += 1
    
    # 检查是否获胜
    if check_winner(game.board, row, col, current_player.piece):
        game.winner_id = user_id
        game.state = GomokuGameState.FINISHED
        
        # 更新积分
        for player_id, player in game.players.items():
            base_score = 5  # 参与分
            if player_id == game.winner_id:
                base_score += 25  # 获胜奖励
                await update_player_score(player_id, group_id, base_score, "五子棋", "获胜者", "胜利")
            else:
                await update_player_score(player_id, group_id, base_score, "五子棋", "参与者", "失败")
        
        msg = f"🎉 游戏结束！{current_player.nickname} 获胜！\n\n"
        msg += format_board(game.board, game.last_move)
        msg += f"\n🏆 {current_player.nickname} 获得30分（参与5分+获胜25分）\n"
        msg += f"😔 对手获得5分（参与分）"
        
        await place_piece.finish(msg)
    
    # 检查是否平局（棋盘满了）
    if all(game.board[i][j] != "⬜" for i in range(9) for j in range(9)):
        game.state = GomokuGameState.FINISHED
        
        # 平局积分
        for player_id, player in game.players.items():
            await update_player_score(player_id, group_id, 10, "五子棋", "参与者", "平局")
        
        msg = f"🤝 游戏结束！平局！\n\n"
        msg += format_board(game.board, game.last_move)
        msg += "\n🎯 双方各获得10分（平局奖励）"
        
        await place_piece.finish(msg)
    
    # 切换玩家
    other_players = [p for p in game.players.keys() if p != user_id]
    game.current_player_id = other_players[0]
    next_player = game.players[game.current_player_id]
    
    msg = f"✅ {current_player.nickname} 下棋 {col_letter}{row_str}\n"
    msg += f"轮到：{next_player.nickname} {next_player.piece}\n\n"
    msg += format_board(game.board, game.last_move)
    
    await place_piece.finish(msg)

@show_board.handle()
async def handle_show_board(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await show_board.finish("当前没有五子棋游戏进行中！")
    
    game = games[group_id]
    
    if game.state == GomokuGameState.SIGNUP:
        msg = f"🎮 五子棋游戏招募中...\n"
        msg += f"当前玩家：{len(game.players)}/2\n"
        for player in game.players.values():
            msg += f"- {player.nickname} {player.piece}\n"
        await show_board.finish(msg)
    
    elif game.state == GomokuGameState.ROCK_PAPER_SCISSORS:
        await show_board.finish("正在进行石头剪刀布决定先手...")
    
    elif game.state in [GomokuGameState.PLAYING, GomokuGameState.FINISHED]:
        msg = ""
        if game.state == GomokuGameState.PLAYING:
            current_player = game.players[game.current_player_id]
            msg += f"当前轮到：{current_player.nickname} {current_player.piece}\n"
        elif game.state == GomokuGameState.FINISHED and game.winner_id:
            winner = game.players[game.winner_id]
            msg += f"🏆 游戏结束！{winner.nickname} 获胜！\n"
        
        msg += f"\n回合数：{game.round_count}\n\n"
        msg += format_board(game.board, game.last_move)
        
        await show_board.finish(msg)

@quit_gomoku.handle()
async def handle_quit_gomoku(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await quit_gomoku.finish("当前没有五子棋游戏进行中！")
    
    game = games[group_id]
    
    if user_id not in game.players:
        await quit_gomoku.finish("您没有参与当前游戏！")
    
    player = game.players[user_id]
    
    if game.state == GomokuGameState.SIGNUP:
        # 报名阶段可以直接退出
        del game.players[user_id]
        msg = f"❌ {player.nickname} 退出了游戏"
        
        if len(game.players) == 0:
            del games[group_id]
            msg += "\n游戏已取消"
        
        await quit_gomoku.finish(msg)
    
    else:
        # 游戏进行中，认输
        other_players = [p for p in game.players.values() if p.user_id != user_id]
        if other_players:
            winner = other_players[0]
            game.winner_id = winner.user_id
            game.state = GomokuGameState.FINISHED
            
            # 更新积分
            await update_player_score(winner.user_id, group_id, 30, "五子棋", "获胜者", "对手认输")
            await update_player_score(user_id, group_id, 0, "五子棋", "认输者", "认输")
            
            msg = f"🏳️ {player.nickname} 认输！\n"
            msg += f"🏆 {winner.nickname} 获胜！\n"
            msg += f"\n{winner.nickname} 获得30分（对手认输奖励）"
            
            await quit_gomoku.finish(msg)

@gomoku_help.handle()
async def handle_gomoku_help(bot: Bot, event: GroupMessageEvent):
    help_text = """🎮 五子棋游戏说明

📋 游戏规则：
• 两人对战，轮流下棋
• 率先连成5子者获胜
• 可横、竖、斜连成5子

🎯 游戏命令：
• 开始五子棋 - 创建游戏
• 加入五子棋 - 参与游戏
• 下棋 位置 - 下棋（如：下棋 H8）
• 查看棋盘 - 查看当前棋盘
• 退出五子棋 - 退出/认输
• 五子棋帮助 - 查看此说明

📍 位置说明：
• 列用字母A-O表示（共9列）
• 行用数字1-9表示（共9行）
• 如：A1是左上角，O9是右下角

🏆 积分规则：
• 参与游戏：5分
• 获胜：额外25分
• 平局：10分
• 对手认输：30分

💡 提示：
• 游戏开始前通过石头剪刀布决定先手
• ⚫黑棋先手，⚪白棋后手
• 最后一步棋会用🔴或🟡标记"""
    
    await gomoku_help.finish(help_text)