from nonebot import on_regex, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, PrivateMessageEvent, MessageSegment
from typing import Dict, List, Optional
from .game_score import update_player_score
import random
import asyncio
import time
from enum import Enum
from dataclasses import dataclass

# 游戏状态枚举
class TicTacToeGameState(Enum):
    WAITING = "waiting"
    SIGNUP = "signup"
    MODE_SELECTION = "mode_selection"  # 新增：模式选择
    ROCK_PAPER_SCISSORS = "rock_paper_scissors"
    COIN_FLIP = "coin_flip"  # 新增：掷硬币阶段
    PLACING_PIECE = "placing_piece"
    FINISHED = "finished"

# 石头剪刀布选择
class RPSChoice(Enum):
    ROCK = "石头"
    PAPER = "布"
    SCISSORS = "剪刀"

# 新增游戏模式枚举
class GameMode(Enum):
    RPS = "rps"  # 石头剪刀布模式
    COIN = "coin"  # 硬币模式

@dataclass
class TicTacToePlayer:
    user_id: str
    nickname: str
    piece: str  # "⚪" 或 "⚫"
    rps_choice: Optional[RPSChoice] = None
    rps_submitted: bool = False
    has_heads: bool = False  # 新增：是否掷出正面


@dataclass
class TicTacToeGame:
    group_id: str
    players: Dict[str, TicTacToePlayer]
    board: List[str]  # 9个位置，空位用"⬜"表示
    current_player_id: Optional[str]
    state: TicTacToeGameState
    round_count: int
    start_time: float
    mode: Optional[GameMode] = None  # 新增：游戏模式
    winner_id: Optional[str] = None
    coin_flip_active: bool = False  # 新增：是否正在掷硬币
    
    def __post_init__(self):
        if not self.board:
            self.board = ["⬜"] * 9

# 存储所有游戏实例
games: Dict[str, TicTacToeGame] = {}

# 游戏命令
start_tic_tac_toe = on_regex(pattern=r"^(开始井字棋|井字棋游戏|tic.*tac.*toe)$", priority=5)
join_tic_tac_toe = on_regex(pattern=r"^(加入井字棋|参加井字棋)$", priority=5)
rps_choice = on_regex(pattern=r"^(石头|剪刀|布)$", priority=5)
place_piece = on_regex(pattern=r"^下棋\s*([1-9])$", priority=5)
show_board = on_regex(pattern=r"^(查看棋盘|棋盘状态)$", priority=5)
quit_tic_tac_toe = on_regex(pattern=r"^(退出井字棋|结束井字棋)$", priority=5)
select_mode = on_regex(pattern=r"^(选择模式|游戏模式)\s*([12])$", priority=5)
coin_flip = on_regex(pattern=r"^(掷|硬币|掷硬币)$", priority=5)

@start_tic_tac_toe.handle()
async def handle_start_tic_tac_toe(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 检查是否已有游戏在进行
    if group_id in games and games[group_id].state != TicTacToeGameState.FINISHED:
        await start_tic_tac_toe.finish("当前群已有井字棋游戏在进行中！")
    
    # 创建新游戏
    game = TicTacToeGame(
        group_id=group_id,
        players={},
        board=["⬜"] * 9,
        current_player_id=None,
        state=TicTacToeGameState.SIGNUP,
        round_count=0,
        start_time=time.time()
    )
    
    games[group_id] = game
    
    message = (
        "🎮 井字棋竞猜游戏开始！\n"
        "📝 游戏规则：\n"
        "1️⃣ 需要2名玩家参与\n"
        "2️⃣ 通过石头剪刀布竞猜决定谁下棋\n"
        "3️⃣ 私聊机器人发送：石头/剪刀/布\n"
        "4️⃣ 胜者在群内输入：下棋 [1-9]\n"
        "5️⃣ 三子连线获胜！\n\n"
        "棋盘位置：\n"
        "1️⃣2️⃣3️⃣\n"
        "4️⃣5️⃣6️⃣\n"
        "7️⃣8️⃣9️⃣\n\n"
        "💡 发送 '加入井字棋' 参与游戏"
    )
    
    await start_tic_tac_toe.send(message)

@join_tic_tac_toe.handle()
async def handle_join_tic_tac_toe(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 检查游戏是否存在
    if group_id not in games:
        await join_tic_tac_toe.finish("当前没有井字棋游戏，请先发送 '开始井字棋' 创建游戏")
    
    game = games[group_id]
    
    # 检查游戏状态
    if game.state != TicTacToeGameState.SIGNUP:
        await join_tic_tac_toe.finish("游戏已开始，无法加入")
    
    # 检查是否已加入
    if user_id in game.players:
        await join_tic_tac_toe.finish("你已经加入了游戏")
    
    # 检查人数限制
    if len(game.players) >= 2:
        await join_tic_tac_toe.finish("游戏人数已满（2人）")
    
    # 分配棋子
    piece = "⚪" if len(game.players) == 0 else "⚫"
    
    # 加入游戏
    player = TicTacToePlayer(
        user_id=user_id,
        nickname=nickname,
        piece=piece
    )
    
    game.players[user_id] = player
    
    # 给参与游戏的玩家加分
    await update_player_score(user_id, group_id, 5, 'tic_tac_toe', None, 'participation')
    
    message = f"✅ {nickname} 加入游戏，执{piece}棋"
    
    # 如果人数够了，进入模式选择
    if len(game.players) == 2:
        game.state = TicTacToeGameState.MODE_SELECTION
        message += ("\n\n🎮 请选择游戏模式：\n"
                   "1️⃣ 石头剪刀布模式（发送：选择模式 1）\n"
                   "2️⃣ 硬币竞速模式（发送：选择模式 2）\n\n"
                   "💡 硬币模式：两人同时掷硬币，先掷到正面的下棋！")
    
    await join_tic_tac_toe.send(message)

@select_mode.handle()
async def handle_select_mode(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        return
    
    game = games[group_id]
    
    if game.state != TicTacToeGameState.MODE_SELECTION:
        return
    
    # 只有参与游戏的玩家可以选择模式
    if user_id not in game.players:
        await select_mode.finish("只有游戏参与者可以选择模式")
    
    import re
    match = re.match(r"^(选择模式|游戏模式)\s*([12])$", event.get_plaintext())
    if not match:
        return
    
    mode_choice = match.group(2)
    
    if mode_choice == "1":
        game.mode = GameMode.RPS
        game.state = TicTacToeGameState.ROCK_PAPER_SCISSORS
        message = ("🎯 已选择石头剪刀布模式！\n\n"
                  "📝 游戏规则：\n"
                  "• 每轮通过石头剪刀布决定谁下棋\n"
                  "• 私聊机器人发送：石头/剪刀/布\n\n"
                  "🎮 请两位玩家私聊机器人发送：石头/剪刀/布")
    else:
        game.mode = GameMode.COIN
        game.state = TicTacToeGameState.COIN_FLIP
        message = ("🪙 已选择硬币竞速模式！\n\n"
                  "📝 游戏规则：\n"
                  "• 两人同时在群里掷硬币\n"
                  "• 先掷到正面的玩家下棋\n"
                  "• 正面概率：30%\n"
                  "• 发送：掷 或 硬币\n\n"
                  f"{get_board_display(game.board)}\n\n"
                  "🎮 开始掷硬币！发送：掷")
    
    await select_mode.send(message)

@coin_flip.handle()
async def handle_coin_flip(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await coin_flip.finish("当前没有进行中的井字棋游戏")
    
    game = games[group_id]
    
    # 检查游戏状态
    if game.state != TicTacToeGameState.COIN_FLIP:
        await coin_flip.finish("当前不是掷硬币阶段")
    
    players = list(game.players.values())
    player1, player2 = players[0], players[1]

    # 检查是否是游戏玩家
    if user_id not in [player1.user_id, player2.user_id]:
        await coin_flip.finish("只有游戏玩家才能掷硬币")
    
    player = game.players[user_id]
    
    # 掷硬币（30%概率正面）
    is_heads = random.random() < 0.3
    result_emoji = "🟡" if is_heads else "⚫"
    result_text = "正面" if is_heads else "反面"
    
    if is_heads:
        # 掷到正面，获得下棋权
        player.has_heads = True
        message = (f"🪙 {player.nickname} 掷硬币：{result_emoji} {result_text}\n\n"
                  f"🎉 {player.nickname} 掷到正面，获得下棋权！\n\n"
                  f"{get_board_display(game.board)}\n\n"
                  f"📍 请 {player.nickname} 下棋，发送：下棋 [1-9]")
        
        await bot.send_group_msg(
            group_id=int(group_id),
            message=MessageSegment.text(message) + MessageSegment.at(int(user_id))
        )
    else:
        # 掷到反面，继续掷硬币
        message = f"🪙 {player.nickname} 掷硬币：{result_emoji} {result_text}，继续掷硬币！"
        await coin_flip.send(message)

@rps_choice.handle()
async def handle_rps_choice(bot: Bot, event: PrivateMessageEvent):
    user_id = str(event.user_id)
    choice_text = event.get_plaintext().strip()
    
    # 查找用户所在的游戏
    user_game = None
    user_group_id = None
    for group_id, game in games.items():
        if user_id in game.players and game.state == TicTacToeGameState.ROCK_PAPER_SCISSORS:
            user_game = game
            user_group_id = group_id
            break
    
    if not user_game:
        await rps_choice.finish("你当前没有参加进行中的井字棋游戏，或游戏不在竞猜阶段")
    
    player = user_game.players[user_id]
    
    # 检查是否已提交
    if player.rps_submitted:
        await rps_choice.finish("你已经提交过选择了，请等待对手")
    
    # 设置选择
    if choice_text == "石头":
        player.rps_choice = RPSChoice.ROCK
    elif choice_text == "剪刀":
        player.rps_choice = RPSChoice.SCISSORS
    elif choice_text == "布":
        player.rps_choice = RPSChoice.PAPER
    else:
        await rps_choice.finish("请发送：石头、剪刀 或 布")
    
    player.rps_submitted = True
    await rps_choice.send(f"✅ 你选择了{choice_text}，等待对手选择...")
    
    # 检查是否都提交了
    all_submitted = all(p.rps_submitted for p in user_game.players.values())
    if all_submitted:
        await process_rps_result(bot, user_group_id, user_game)

async def process_rps_result(bot: Bot, group_id: str, game: TicTacToeGame):
    """处理石头剪刀布结果"""
    players = list(game.players.values())
    player1, player2 = players[0], players[1]
    
    choice1, choice2 = player1.rps_choice, player2.rps_choice
    
    # 判断胜负
    winner = None
    if choice1 == choice2:
        result_text = "平局！重新开始竞猜"
    elif (
        (choice1 == RPSChoice.ROCK and choice2 == RPSChoice.SCISSORS) or
        (choice1 == RPSChoice.SCISSORS and choice2 == RPSChoice.PAPER) or
        (choice1 == RPSChoice.PAPER and choice2 == RPSChoice.ROCK)
    ):
        winner = player1
        result_text = f"🎉 {player1.nickname} 获胜！"
    else:
        winner = player2
        result_text = f"🎉 {player2.nickname} 获胜！"
    
    # 重置提交状态
    for player in game.players.values():
        player.rps_submitted = False
        player.rps_choice = None
    
    message = (
        f"🎯 石头剪刀布结果：\n"
        f"👤 {player1.nickname}：{choice1.value}\n"
        f"👤 {player2.nickname}：{choice2.value}\n\n"
        f"{result_text}"
    )
    
    if winner:
        game.current_player_id = winner.user_id
        game.state = TicTacToeGameState.PLACING_PIECE
        game.round_count += 1
        
        board_display = get_board_display(game.board)
        message += f"\n\n{board_display}\n\n📍 @{winner.nickname} 请下棋，发送：下棋 [1-9]"
        
        # 发送消息并@获胜者
        await bot.send_group_msg(
            group_id=int(group_id),
            message=MessageSegment.text(message) + MessageSegment.at(int(winner.user_id))
        )
    else:
        message += "\n\n🔄 请重新私聊机器人发送：石头/剪刀/布"
        await bot.send_group_msg(group_id=int(group_id), message=message)

@place_piece.handle()
async def handle_place_piece(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 检查游戏是否存在
    if group_id not in games:
        return
    
    game = games[group_id]
    
    # 检查游戏状态
    if game.state not in [TicTacToeGameState.PLACING_PIECE, TicTacToeGameState.COIN_FLIP]:
        return
    
    # 检查是否是游戏玩家
    if user_id not in game.players:
        return
    
    player = game.players[user_id]
    
    # 在掷硬币模式下，检查该玩家是否掷出了正面
    if game.mode == GameMode.COIN and game.state == TicTacToeGameState.COIN_FLIP:
        if not player.has_heads:
            await place_piece.finish("你还没有掷出正面，无法下棋！请先掷硬币")
    elif game.state == TicTacToeGameState.PLACING_PIECE:
        # 石头剪刀布模式下，检查是否轮到该玩家
        if game.current_player_id != user_id:
            await place_piece.finish("现在不是你的回合")
    
    # 解析位置
    import re
    match = re.match(r"^下棋\s*([1-9])$", event.get_plaintext())
    if not match:
        await place_piece.finish("请发送：下棋 [1-9]")
    
    position = int(match.group(1)) - 1  # 转换为0-8的索引
    
    # 检查位置是否可用
    if game.board[position] != "⬜":
        await place_piece.finish("该位置已被占用，请选择其他位置")
    
    # 下棋
    game.board[position] = player.piece
    
    # 在掷硬币模式下，下棋后重置该玩家的正面状态
    if game.mode == GameMode.COIN:
        player.has_heads = False
    
    # 检查是否获胜
    if check_winner(game.board, player.piece):
        game.state = TicTacToeGameState.FINISHED
        game.winner_id = user_id
        
        # 给获胜者加分
        await update_player_score(user_id, group_id, 20, 'tic_tac_toe', None, 'winner')
        
        board_display = get_board_display(game.board)
        message = (
            f"🎉 游戏结束！\n\n"
            f"{board_display}\n\n"
            f"🏆 恭喜 {player.nickname} 获胜！\n"
            f"🎁 奖励：参与+5分，获胜+20分"
        )
        
        await place_piece.send(message)
        return
    
    # 检查是否平局
    if "⬜" not in game.board:
        game.state = TicTacToeGameState.FINISHED
        
        board_display = get_board_display(game.board)
        message = (
            f"🤝 游戏结束！\n\n"
            f"{board_display}\n\n"
            f"⚖️ 平局！\n"
            f"🎁 奖励：参与+5分"
        )
        
        await place_piece.send(message)
        return
    
    # 继续游戏，根据模式进入不同阶段
    board_display = get_board_display(game.board)
    base_message = f"✅ {player.nickname} 在位置{position + 1}下了{player.piece}\n\n{board_display}\n\n"
    
    if game.mode == GameMode.RPS:
        # 石头剪刀布模式
        game.state = TicTacToeGameState.ROCK_PAPER_SCISSORS
        message = base_message + "🎯 请两位玩家私聊机器人发送：石头/剪刀/布"
    else:
        # 硬币模式 - 重置所有玩家的正面状态，继续掷硬币
        for p in game.players.values():
            p.has_heads = False
        game.state = TicTacToeGameState.COIN_FLIP
        message = base_message + "🪙 继续掷硬币！发送：掷"
    
    await place_piece.send(message)

@show_board.handle()
async def handle_show_board(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await show_board.finish("当前没有进行中的井字棋游戏")
    
    game = games[group_id]
    
    if game.state == TicTacToeGameState.SIGNUP:
        await show_board.finish("游戏还未开始，等待玩家加入")
    
    board_display = get_board_display(game.board)
    players_info = "\n".join([f"👤 {p.nickname}：{p.piece}" for p in game.players.values()])
    
    # 显示游戏模式
    mode_info = ""
    if game.mode == GameMode.RPS:
        mode_info = "🎯 石头剪刀布模式"
    elif game.mode == GameMode.COIN:
        mode_info = "🪙 硬币竞速模式（30%正面概率）"
    
    current_state = ""
    if game.state == TicTacToeGameState.MODE_SELECTION:
        current_state = "🎮 等待选择游戏模式"
    elif game.state == TicTacToeGameState.ROCK_PAPER_SCISSORS:
        current_state = "🎯 等待玩家私聊竞猜"
    elif game.state == TicTacToeGameState.COIN_FLIP:
        current_state = "🪙 等待玩家掷硬币"
    elif game.state == TicTacToeGameState.PLACING_PIECE:
        current_player = game.players[game.current_player_id]
        current_state = f"📍 等待 {current_player.nickname} 下棋"
    elif game.state == TicTacToeGameState.FINISHED:
        if game.winner_id:
            winner = game.players[game.winner_id]
            current_state = f"🏆 {winner.nickname} 获胜"
        else:
            current_state = "⚖️ 平局"
    
    message = (
        f"🎮 井字棋游戏状态\n\n"
        f"{board_display}\n\n"
        f"👥 玩家信息：\n{players_info}\n\n"
        f"🎯 游戏模式：{mode_info}\n"
        f"📊 当前状态：{current_state}"
    )
    await show_board.send(message)

@quit_tic_tac_toe.handle()
async def handle_quit_tic_tac_toe(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await quit_tic_tac_toe.finish("当前没有进行中的井字棋游戏")
    
    # 检查权限（群管理员或游戏参与者可以结束游戏）
    game = games[group_id]
    is_player = user_id in game.players
    
    try:
        member_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        is_admin = member_info.get('role') in ['admin', 'owner']
    except:
        is_admin = False
    
    if not (is_player or is_admin):
        await quit_tic_tac_toe.finish("只有游戏参与者或群管理员可以结束游戏")
    
    # 结束游戏
    del games[group_id]
    await quit_tic_tac_toe.send("🎮 井字棋游戏已结束")

def get_board_display(board: List[str]) -> str:
    """获取棋盘显示"""
    display_board = []
    for i, cell in enumerate(board):
        if cell == "⬜":
            display_board.append(f"{i + 1}️⃣")
        else:
            display_board.append(cell)
    
    return (
        f"{display_board[0]}{display_board[1]}{display_board[2]}\n"
        f"{display_board[3]}{display_board[4]}{display_board[5]}\n"
        f"{display_board[6]}{display_board[7]}{display_board[8]}"
    )

def check_winner(board: List[str], piece: str) -> bool:
    """检查是否获胜"""
    # 获胜条件：横、竖、斜线三子连线
    win_conditions = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # 横线
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # 竖线
        [0, 4, 8], [2, 4, 6]              # 斜线
    ]
    
    for condition in win_conditions:
        if all(board[i] == piece for i in condition):
            return True
    
    return False

# 定期清理已结束的游戏
async def cleanup_finished_tic_tac_toe_games():
    """清理已结束的游戏"""
    while True:
        try:
            current_time = time.time()
            to_remove = []
            
            for group_id, game in games.items():
                # 清理超过1小时的已结束游戏
                if (game.state == TicTacToeGameState.FINISHED and 
                    current_time - game.start_time > 3600):
                    to_remove.append(group_id)
            
            for group_id in to_remove:
                if group_id in games:
                    del games[group_id]
            
            await asyncio.sleep(300)  # 每5分钟清理一次
        except Exception as e:
            print(f"清理井字棋游戏时出错: {e}")
            await asyncio.sleep(300)

# 启动清理任务
from nonebot import get_driver
driver = get_driver()

@driver.on_startup
async def start_tic_tac_toe_cleanup():
    """在bot启动时开始清理任务"""
    asyncio.create_task(cleanup_finished_tic_tac_toe_games())