import asyncio
import random
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from nonebot import on_command, on_message,on_regex
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, MessageSegment
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, ArgPlainText
from nonebot.adapters.onebot.v11.message import Message

# QQ音乐API导入
from qqmusic_api import search, song

class GameState(Enum):
    WAITING = "waiting"  # 等待开始
    SIGNUP = "signup"    # 报名阶段
    PLAYING = "playing"  # 游戏进行中
    FINISHED = "finished" # 游戏结束

@dataclass
class Player:
    user_id: str
    nickname: str
    score: int = 0
    correct_guesses: int = 0

@dataclass
class SongInfo:
    song_id: str
    title: str
    artist: str
    album: str = ""
    duration: int = 0  # 秒
    preview_url: str = ""  # 试听链接
    lyric: str = ""  # 歌词

@dataclass
class GuessGame:
    group_id: str
    state: GameState = GameState.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    current_song: Optional[SongInfo] = None
    song_queue: List[SongInfo] = field(default_factory=list)
    current_song_index: int = 0
    start_time: Optional[float] = None
    song_start_time: Optional[float] = None
    game_duration: int = 300  # 5分钟
    song_timeout: int = 60    # 每首歌1分钟超时
    skip_votes: Set[str] = field(default_factory=set)
    skip_threshold: int = 2   # 跳过投票阈值
    correct_guessed: bool = False
    timeout_task: Optional[asyncio.Task] = None
    game_task: Optional[asyncio.Task] = None

# 游戏实例存储
games: Dict[str, GuessGame] = {}

# QQ音乐API相关函数
async def search_songs(keyword: str, num: int = 10) -> List[SongInfo]:
    """搜索歌曲"""
    try:
        result = await search.search_by_type(keyword=keyword, num=num, type_=0)  # type_=0表示搜索歌曲
        songs = []
        
        if result and 'data' in result and 'song' in result['data'] and 'list' in result['data']['song']:
            for song_data in result['data']['song']['list']:
                song_info = SongInfo(
                    song_id=str(song_data.get('songid', '')),
                    title=song_data.get('songname', ''),
                    artist=', '.join([singer.get('name', '') for singer in song_data.get('singer', [])]),
                    album=song_data.get('albumname', ''),
                    duration=song_data.get('interval', 0)
                )
                songs.append(song_info)
        
        return songs
    except Exception as e:
        print(f"搜索歌曲失败: {e}")
        return []

async def get_song_detail(song_id: str) -> Optional[SongInfo]:
    """获取歌曲详细信息"""
    try:
        # 获取歌曲信息
        song_info = await song.get_song_info(song_id)
        if not song_info:
            return None
            
        # 获取歌词
        lyric_info = await song.get_song_lyric(song_id)
        lyric_text = ""
        if lyric_info and 'lyric' in lyric_info:
            lyric_text = lyric_info['lyric']
        
        # 获取播放链接
        play_url = await song.get_song_url(song_id)
        preview_url = play_url.get('url', '') if play_url else ''
        
        return SongInfo(
            song_id=song_id,
            title=song_info.get('songname', ''),
            artist=', '.join([singer.get('name', '') for singer in song_info.get('singer', [])]),
            album=song_info.get('albumname', ''),
            duration=song_info.get('interval', 0),
            preview_url=preview_url,
            lyric=lyric_text
        )
    except Exception as e:
        print(f"获取歌曲详情失败: {e}")
        return None

async def prepare_song_queue(num_songs: int = 8) -> List[SongInfo]:
    """准备歌曲队列"""
    # 热门歌手和关键词
    popular_keywords = [
        "周杰伦", "邓紫棋", "林俊杰", "陈奕迅", "薛之谦", "毛不易", "李荣浩", "张学友",
        "王力宏", "刘德华", "张信哲", "五月天", "Beyond", "梁静茹", "田馥甄", "蔡依林",
        "热门歌曲", "经典老歌", "流行音乐", "华语金曲"
    ]
    
    all_songs = []
    
    # 从多个关键词搜索歌曲
    for keyword in random.sample(popular_keywords, min(5, len(popular_keywords))):
        songs = await search_songs(keyword, 3)
        all_songs.extend(songs)
    
    # 随机选择指定数量的歌曲
    if len(all_songs) >= num_songs:
        selected_songs = random.sample(all_songs, num_songs)
    else:
        selected_songs = all_songs
    
    # 获取详细信息
    detailed_songs = []
    for song_info in selected_songs:
        detailed = await get_song_detail(song_info.song_id)
        if detailed:
            detailed_songs.append(detailed)
    
    return detailed_songs

def get_lyric_hint(lyric: str, reveal_ratio: float = 0.3) -> str:
    """获取歌词提示（部分遮挡）"""
    if not lyric:
        return "暂无歌词"
    
    # 简单处理歌词，去除时间标记
    import re
    clean_lyric = re.sub(r'\[\d+:\d+\.\d+\]', '', lyric)
    lines = [line.strip() for line in clean_lyric.split('\n') if line.strip()]
    
    if not lines:
        return "暂无歌词"
    
    # 选择前几行作为提示
    hint_lines = lines[:3]
    
    # 部分遮挡
    masked_lines = []
    for line in hint_lines:
        if len(line) > 10:
            reveal_count = int(len(line) * reveal_ratio)
            masked = line[:reveal_count] + "*" * (len(line) - reveal_count)
            masked_lines.append(masked)
        else:
            masked_lines.append(line)
    
    return "\n".join(masked_lines)

def normalize_answer(text: str) -> str:
    """标准化答案（去除空格、标点等）"""
    import re
    # 去除空格和常见标点
    normalized = re.sub(r'[\s\-_\(\)（）\[\]【】]', '', text.lower())
    return normalized

def check_answer(user_answer: str, correct_title: str, correct_artist: str) -> bool:
    """检查答案是否正确"""
    user_norm = normalize_answer(user_answer)
    title_norm = normalize_answer(correct_title)
    artist_norm = normalize_answer(correct_artist)
    
    # 检查是否包含歌名或歌手名
    return (title_norm in user_norm or user_norm in title_norm or 
            artist_norm in user_norm or user_norm in artist_norm)

# 命令处理器 on_regex(pattern=r'^猜歌\s+(.+)$', priority=1)
guess_song_start = on_regex(pattern=r'^开始猜歌\s+(.+)$', priority=5)
guess_song_join = on_regex(pattern=r'^报名猜歌\s+(.+)$', priority=5)
guess_song_skip = on_regex(pattern=r'^跳过\s+(.+)$', priority=5)
guess_song_status = on_regex(pattern=r'^猜歌状态\s+(.+)$', priority=5)
guess_song_stop = on_regex(pattern=r'^强制结束猜歌\s+(.+)$', priority=5)
guess_song_rules = on_regex(pattern=r'^猜歌规则\s+(.+)$', priority=5)
guess_song_end_signup = on_regex(pattern=r'^结束猜歌报名\s+(.+)$', priority=5)

# 消息处理器（用于猜歌）
guess_handler = on_message(priority=10)

@guess_song_start.handle()
async def start_guess_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id in games and games[group_id].state != GameState.WAITING:
        await guess_song_start.send("当前群组已有猜歌游戏在进行中！")
        return
    
    # 创建新游戏
    game = GuessGame(group_id=group_id, state=GameState.SIGNUP)
    games[group_id] = game
    
    await guess_song_start.send(
        "🎵 猜歌游戏开始报名！\n"
        "📝 发送 '报名猜歌' 来参与游戏\n"
        "⏰ 报名时间：5min\n"
        "🎯 游戏时长：5分钟\n"
        "💡 发送 '猜歌规则' 查看详细规则\n"
        "🚀 发送 '结束猜歌报名' 可提前开始游戏"
    )
    
    # 300秒后开始游戏
    await asyncio.sleep(300)
    
    if group_id in games and games[group_id].state == GameState.SIGNUP:
        await start_game_process(bot, group_id)

@guess_song_join.handle()
async def join_guess_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await guess_song_join.send("当前没有猜歌游戏，发送 '猜歌' 开始新游戏！")
        return
    
    game = games[group_id]
    
    if game.state != GameState.SIGNUP:
        await guess_song_join.send("游戏已开始，无法加入！")
        return
    
    if user_id in game.players:
        await guess_song_join.send("你已经参加了游戏！")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('card') or user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    game.players[user_id] = Player(user_id=user_id, nickname=nickname)
    
    await guess_song_join.send(f"🎉 {nickname} 成功加入猜歌游戏！当前参与人数：{len(game.players)}")

async def start_game_process(bot: Bot, group_id: str):
    """开始游戏流程"""
    game = games[group_id]
    
    if len(game.players) < 1:
        await bot.send_group_msg(group_id=int(group_id), message="参与人数不足，游戏取消！")
        del games[group_id]
        return
    
    game.state = GameState.PLAYING
    game.start_time = time.time()
    
    await bot.send_group_msg(
        group_id=int(group_id), 
        message=f"🎵 猜歌游戏开始！参与玩家：{len(game.players)}人\n⏰ 游戏时长：5分钟\n🎯 准备歌曲中..."
    )
    
    # 准备歌曲队列
    game.song_queue = await prepare_song_queue(8)
    
    if not game.song_queue:
        await bot.send_group_msg(group_id=int(group_id), message="❌ 获取歌曲失败，游戏结束！")
        del games[group_id]
        return
    
    # 设置跳过投票阈值
    game.skip_threshold = max(1, len(game.players) // 2)
    
    await bot.send_group_msg(
        group_id=int(group_id), 
        message=f"✅ 歌曲准备完成！共{len(game.song_queue)}首歌\n🗳️ 跳过投票需要{game.skip_threshold}票\n🎵 开始第一首歌..."
    )
    
    # 开始播放第一首歌
    await play_next_song(bot, group_id)
    
    # 设置游戏总时长定时器
    game.game_task = asyncio.create_task(game_timer(bot, group_id))

async def play_next_song(bot: Bot, group_id: str):
    """播放下一首歌"""
    game = games[group_id]
    
    if game.current_song_index >= len(game.song_queue):
        await end_game(bot, group_id, "所有歌曲播放完毕！")
        return
    
    game.current_song = game.song_queue[game.current_song_index]
    game.song_start_time = time.time()
    game.correct_guessed = False
    game.skip_votes.clear()
    
    song = game.current_song
    
    # 构建消息
    message_parts = [
        f"🎵 第{game.current_song_index + 1}首歌开始！\n",
        f"🎤 歌手：{song.artist}\n",
        f"💿 专辑：{song.album}\n" if song.album else "",
        f"⏱️ 时长：{song.duration}秒\n" if song.duration else "",
        "\n💡 歌词提示：\n",
        get_lyric_hint(song.lyric),
        "\n\n🎯 请猜歌名！发送 '跳过' 投票跳过"
    ]
    
    message = "".join(message_parts)
    
    # 如果有试听链接，添加音频消息
    if song.preview_url:
        try:
            audio_msg = MessageSegment.record(song.preview_url)
            await bot.send_group_msg(group_id=int(group_id), message=[audio_msg, message])
        except:
            await bot.send_group_msg(group_id=int(group_id), message=message)
    else:
        await bot.send_group_msg(group_id=int(group_id), message=message)
    
    # 设置歌曲超时
    if game.timeout_task:
        game.timeout_task.cancel()
    
    game.timeout_task = asyncio.create_task(song_timeout(bot, group_id))

async def song_timeout(bot: Bot, group_id: str):
    """歌曲超时处理"""
    await asyncio.sleep(60)  # 1分钟超时
    
    if group_id not in games:
        return
    
    game = games[group_id]
    
    if game.state != GameState.PLAYING or game.correct_guessed:
        return
    
    song = game.current_song
    await bot.send_group_msg(
        group_id=int(group_id), 
        message=f"⏰ 时间到！\n🎵 正确答案：{song.title}\n🎤 演唱者：{song.artist}\n\n准备下一首歌..."
    )
    
    game.current_song_index += 1
    await asyncio.sleep(3)
    await play_next_song(bot, group_id)

async def game_timer(bot: Bot, group_id: str):
    """游戏总时长计时器"""
    await asyncio.sleep(300)  # 5分钟
    
    if group_id in games and games[group_id].state == GameState.PLAYING:
        await end_game(bot, group_id, "游戏时间结束！")

@guess_song_skip.handle()
async def skip_song(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games or games[group_id].state != GameState.PLAYING:
        return
    
    game = games[group_id]
    
    if user_id not in game.players:
        await guess_song_skip.send("你没有参与游戏！")
        return
    
    if user_id in game.skip_votes:
        await guess_song_skip.send("你已经投过跳过票了！")
        return
    
    game.skip_votes.add(user_id)
    player = game.players[user_id]
    
    await guess_song_skip.send(
        f"🗳️ {player.nickname} 投票跳过！\n"
        f"当前票数：{len(game.skip_votes)}/{game.skip_threshold}"
    )
    
    if len(game.skip_votes) >= game.skip_threshold:
        if game.timeout_task:
            game.timeout_task.cancel()
        
        song = game.current_song
        await bot.send_group_msg(
            group_id=int(group_id), 
            message=f"⏭️ 跳过成功！\n🎵 答案：{song.title}\n🎤 演唱者：{song.artist}\n\n准备下一首歌..."
        )
        
        game.current_song_index += 1
        await asyncio.sleep(3)
        await play_next_song(bot, group_id)

@guess_handler.handle()
async def handle_guess(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    message = str(event.get_message()).strip()
    
    if group_id not in games or games[group_id].state != GameState.PLAYING:
        return
    
    game = games[group_id]
    
    if user_id not in game.players or game.correct_guessed:
        return
    
    if not game.current_song:
        return
    
    # 检查答案
    if check_answer(message, game.current_song.title, game.current_song.artist):
        game.correct_guessed = True
        
        if game.timeout_task:
            game.timeout_task.cancel()
        
        # 更新分数
        player = game.players[user_id]
        player.score += 10
        player.correct_guesses += 1
        
        song = game.current_song
        await bot.send_group_msg(
            group_id=int(group_id), 
            message=f"🎉 恭喜 {player.nickname} 答对了！\n"
                   f"🎵 歌名：{song.title}\n"
                   f"🎤 演唱者：{song.artist}\n"
                   f"🏆 获得10分！当前分数：{player.score}\n\n"
                   f"准备下一首歌..."
        )
        
        game.current_song_index += 1
        await asyncio.sleep(3)
        await play_next_song(bot, group_id)

@guess_song_status.handle()
async def show_game_status(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await guess_song_status.send("当前没有进行中的猜歌游戏！")
        return
    
    game = games[group_id]
    
    if game.state == GameState.SIGNUP:
        await guess_song_status.send(f"🎵 猜歌游戏报名中\n👥 当前参与人数：{len(game.players)}")
        return
    
    if game.state != GameState.PLAYING:
        await guess_song_status.send("游戏未在进行中！")
        return
    
    # 计算剩余时间
    elapsed = time.time() - game.start_time
    remaining = max(0, 300 - elapsed)
    
    # 排序玩家
    sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
    
    status_msg = [
        f"🎵 猜歌游戏进行中\n",
        f"🎯 当前第{game.current_song_index + 1}首歌\n",
        f"⏰ 剩余时间：{int(remaining)}秒\n\n",
        "🏆 当前排行榜：\n"
    ]
    
    for i, player in enumerate(sorted_players[:5], 1):
        status_msg.append(f"{i}. {player.nickname}: {player.score}分 ({player.correct_guesses}首)\n")
    
    await guess_song_status.send("".join(status_msg))

@guess_song_stop.handle()
async def stop_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = event.user_id
    
    # 检查是否为管理员（这里简化处理，实际可以加入权限检查）
    member_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    if member_info['role'] not in ['admin', 'owner']:
        await force_end.finish("只有管理员可以强制结束游戏！")
        return
    
    if group_id not in games:
        await guess_song_stop.send("当前没有进行中的猜歌游戏！")
        return
    
    await end_game(bot, group_id, "游戏被管理员终止！")

async def end_game(bot: Bot, group_id: str, reason: str):
    """结束游戏"""
    if group_id not in games:
        return
    
    game = games[group_id]
    game.state = GameState.FINISHED
    
    # 取消所有定时任务
    if game.timeout_task:
        game.timeout_task.cancel()
    if game.game_task:
        game.game_task.cancel()
    
    # 生成最终排行榜
    sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
    
    result_msg = [
        f"🎵 猜歌游戏结束！\n",
        f"📝 结束原因：{reason}\n\n",
        "🏆 最终排行榜：\n"
    ]
    
    for i, player in enumerate(sorted_players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
        result_msg.append(f"{medal} {i}. {player.nickname}: {player.score}分 ({player.correct_guesses}首正确)\n")
    
    if not sorted_players:
        result_msg.append("暂无参与者\n")
    
    result_msg.append("\n感谢大家的参与！🎉")
    
    await bot.send_group_msg(group_id=int(group_id), message="".join(result_msg))
    
    # 清理游戏数据
    del games[group_id]

@guess_song_rules.handle()
async def show_rules(bot: Bot, event: GroupMessageEvent):
    rules = (
        "🎵 猜歌游戏规则\n\n"
        "📝 游戏流程：\n"
        "1. 发送 '开始猜歌' 开始游戏\n"
        "2. 发送 '报名猜歌' 报名参与\n"
        "3. 5min报名时间结束后开始游戏\n\n"
        "🎯 游戏规则：\n"
        "• 游戏总时长：5分钟\n"
        "• 每首歌最长1分钟\n"
        "• 答对一首歌得10分\n"
        "• 可以猜歌名或歌手名\n"
        "• 发送 '跳过' 投票跳过当前歌曲\n\n"
        "🏆 获胜条件：\n"
        "游戏结束时分数最高者获胜\n\n"
        "💡 提示：\n"
        "• 每首歌会提供歌手、专辑和部分歌词提示\n"
        "• 支持模糊匹配，不需要完全准确\n"
        "• 发送 '猜歌状态' 查看当前排行榜"
    )
    
    await guess_song_rules.send(rules)

# 新增：结束报名命令处理器
@guess_song_end_signup.handle()
async def end_signup_early(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await guess_song_end_signup.send("当前没有猜歌游戏！")
        return
    
    game = games[group_id]
    
    if game.state != GameState.SIGNUP:
        await guess_song_end_signup.send("当前不在报名阶段！")
        return
    
    if len(game.players) < 1:
        await guess_song_end_signup.send("至少需要1名玩家才能开始游戏！")
        return
    
    await guess_song_end_signup.send(
        f"📢 报名提前结束！\n"
        f"👥 参与玩家：{len(game.players)}人\n"
        f"🎵 游戏即将开始..."
    )
    
    # 提前开始游戏
    await start_game_process(bot, group_id)