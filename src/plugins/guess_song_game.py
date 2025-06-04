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
import re
# QQ音乐API导入
from qqmusic_api import search, song, lyric

class GameState(Enum):
    WAITING = "waiting"  # 等待开始
    SIGNUP = "signup"    # 报名阶段
    PLAYING = "playing"  # 游戏进行中
    FINISHED = "finished" # 游戏结束

class GuessMode(Enum):
    TITLE_ONLY = "title_only"  # 只猜歌名
    TITLE_AND_ARTIST = "title_and_artist"  # 歌名和歌手都要猜对

@dataclass
class Player:
    user_id: str
    nickname: str
    score: int = 0
    correct_guesses: int = 0

@dataclass
class SongInfo:
    song_id: str
    song_mid: str
    title: str
    artist: str
    album: str = ""
    duration: int = 0  # 秒
    preview_url: str = ""  # 试听链接
    lyric: str = ""  # 歌词
    play_duration: int = 30  # 播放时长（秒）
    vs: List[str] = field(default_factory=list)  # 新增

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
    guess_mode: GuessMode = GuessMode.TITLE_ONLY  # 猜歌模式
    play_duration: int = 30  # 音频播放时长（秒）

# 游戏实例存储
games: Dict[str, GuessGame] = {}

async def search_songs(keyword: str, num: int = 10) -> List[SongInfo]:
    """搜索歌曲"""
    try:
        result = await search.search_by_type(keyword=keyword, num=num)
        songs = []
        print(f"搜索到的歌曲: {len(result) if result else 0}条")
        
        if result:
            for song_data in result:
                # 直接从搜索结果提取信息
                song_info = SongInfo(
                    song_id=str(song_data.get('id', '')),
                    title=song_data.get('name', ''),
                    artist=song_data.get('singer', [{}])[0].get('name', '') if song_data.get('singer') else '未知歌手',
                    album=song_data.get('album', {}).get('name', '') if song_data.get('album') else '',
                    duration=song_data.get('interval', 0),
                    song_mid=song_data.get('mid', ''),
                    vs=song_data.get('vs', [])
                )
                
                # 只添加有效的歌曲信息
                if song_info.song_id and song_info.title and song_info.song_mid:
                    songs.append(song_info)
        
        print(f"解析后的歌曲数量: {len(songs)}")
        return songs
    except Exception as e:
        print(f"搜索歌曲失败: {e}")
        return []

async def get_song_detail(song_info: SongInfo, play_duration: int = 30) -> Optional[SongInfo]:
    """获取歌曲详细信息（歌词和试听链接）"""
    try:
        print(f"获取歌曲详情: {song_info.title} - {song_info.artist}")
        
        # 获取歌词
        lyric_text = ""
        try:
            lyric_data = await lyric.get_lyric(song_info.song_mid)
            if lyric_data and 'lyric' in lyric_data:
                raw_lyric = lyric_data['lyric']
                # 去除时间标签，提取纯歌词
                pure_lyric = re.sub(r'\[.*?\]', '', raw_lyric).strip()
                # 按行分割，去除空行
                lyric_lines = [line.strip() for line in pure_lyric.split('\n') if line.strip()]

                # 取中间两句
                if len(lyric_lines) >= 5:
                    mid = len(lyric_lines) // 2
                    lyric_text = lyric_lines[mid-2:mid+3]
                else:
                    lyric_text = lyric_lines
                
            print(f"歌词获取成功: {len(lyric_text)} 字符")
            print(f"歌词---: {lyric_text} ")
        except Exception as e:
            print(f"获取歌词失败: {e}")
        
        # 获取试听链接
        preview_url = ""
        try:
            if song_info.vs and len(song_info.vs) > 0:
                # 使用vs[0]获取试听链接
                url_result = await song.get_try_url(song_info.song_mid, song_info.vs[0])
                if url_result:
                        preview_url = url_result
            print(f"播放链接获取: {'成功' if preview_url else '失败'}")
        except Exception as e:
            print(f"获取播放链接失败: {e}")
        
        # 更新歌曲信息
        detailed_song = SongInfo(
            song_id=song_info.song_id,
            title=song_info.title,
            artist=song_info.artist,
            album=song_info.album,
            duration=song_info.duration,
            preview_url=preview_url,
            lyric=lyric_text,
            play_duration=play_duration,
            song_mid=song_info.song_mid,
            vs=song_info.vs
        )
        
        print(f"歌曲详情获取完成: {detailed_song.title} - {detailed_song.artist} - {detailed_song}")
        return detailed_song
        
    except Exception as e:
        print(f"获取歌曲详情失败: {e}")
        return None

async def prepare_song_queue(num_songs: int = 8, play_duration: int = 30) -> List[SongInfo]:
    """准备歌曲队列"""
    # 热门歌手和关键词
    popular_keywords = [
        # 华语男歌手
        "周杰伦", "邓紫棋", "林俊杰", "陈奕迅", "薛之谦", "毛不易", "李荣浩", "张学友",
        "王力宏", "刘德华", "张信哲", "张杰", "汪苏泷", "胡彦斌", "许嵩", "徐良",
        "庞龙", "刀郎", "凤凰传奇", "筷子兄弟", "羽泉", "水木年华", "朴树", "许巍",
        
        # 华语女歌手
        "梁静茹", "田馥甄", "蔡依林", "张韶涵", "杨丞琳", "容祖儿", "王心凌", "萧亚轩",
        "孙燕姿", "范玮琪", "S.H.E", "Twins", "那英", "王菲", "faye", "李玟",
        "张惠妹", "莫文蔚", "刘若英", "陈慧琳", "郑秀文", "杨千嬅", "关淑怡",
        
        # 乐队组合
        "五月天", "Beyond", "信乐团", "苏打绿", "南拳妈妈", "飞轮海", "F4", "SHE",
        "至上励合", "TFBOYS", "时代少年团", "九连真人", "草东没有派对",
        
        # 网络歌手
        "花粥", "陈雪凝", "隔壁老樊", "程响", "半阳", "王北车", "刘大壮", "海来阿木",
        "摩登兄弟", "阿悠悠", "小阿七", "柯柯柯啊", "要不要买菜", "房东的猫",
        
        # 音乐类型关键词
        "热门歌曲", "经典老歌", "流行音乐", "华语金曲", "抖音热歌", "网络歌曲",
        "民谣", "摇滚", "说唱", "古风", "电音", "爵士", "蓝调", "乡村音乐",
        "粤语歌", "闽南语歌", "英文歌", "日语歌", "韩语歌",
        
        # 年代关键词
        "90年代", "2000年代", "2010年代", "怀旧金曲", "经典怀旧", "老歌",
        
        # 情感主题
        "情歌", "伤感", "励志", "青春", "校园", "爱情", "分手", "思念",
        "快乐", "治愈", "温柔", "甜蜜", "浪漫", "深情",
        
        # 场景主题
        "KTV必点", "婚礼歌曲", "毕业歌", "生日歌", "新年歌", "圣诞歌",
        "运动音乐", "开车音乐", "睡前音乐", "工作音乐"
    ]
    
    all_songs = []
    
    # 从多个关键词搜索歌曲
    search_count = min(6, len(popular_keywords))
    for keyword in random.sample(popular_keywords, search_count):
        try:
            songs = await search_songs(keyword, num=3)
            all_songs.extend(songs)
            await asyncio.sleep(0.5)  # 避免请求过快
        except Exception as e:
            print(f"搜索关键词 '{keyword}' 失败: {e}")
            continue
    
    # 去重（基于歌曲ID）
    seen_ids = set()
    unique_songs = []
    for song in all_songs:
        if song.song_id not in seen_ids:
            seen_ids.add(song.song_id)
            unique_songs.append(song)
    
    # 随机选择指定数量的歌曲
    selected_songs = random.sample(unique_songs, min(num_songs, len(unique_songs)))
    
    # 获取每首歌的详细信息
    detailed_songs = []
    for song_info in selected_songs:
        try:
            detailed_song = await get_song_detail(song_info, play_duration)
            if detailed_song and detailed_song.preview_url and detailed_song.lyric:
                print(f"获取歌曲详情成功: {detailed_song.title} - {detailed_song.artist}")
                detailed_songs.append(detailed_song)
            await asyncio.sleep(0.3)  # 避免请求过快
        except Exception as e:
            print(f"获取歌曲详情失败: {e}")
            continue
    
    print(f"成功准备了 {len(detailed_songs)} 首歌曲")
    return detailed_songs


def normalize_answer(text: str) -> str:
    """标准化答案（去除空格、标点等）"""
    import re
    # 去除空格和常见标点
    normalized = re.sub(r'[\s\-_\(\)（）\[\]【】]', '', text.lower())
    return normalized

def check_answer(user_answer: str, correct_title: str, correct_artist: str, mode: GuessMode = GuessMode.TITLE_ONLY) -> bool:
    """检查答案是否正确"""
    user_norm = normalize_answer(user_answer)
    title_norm = normalize_answer(correct_title)
    artist_norm = normalize_answer(correct_artist)
    
    # 检查歌名匹配
    title_match = title_norm in user_norm or user_norm in title_norm
    
    if mode == GuessMode.TITLE_ONLY:
        # 只需要猜对歌名
        return title_match
    elif mode == GuessMode.TITLE_AND_ARTIST:
        # 需要同时猜对歌名和歌手
        artist_match = artist_norm in user_norm or user_norm in artist_norm
        return title_match and artist_match
    
    return title_match

# 命令处理器
guess_song_start = on_regex(pattern=r'^开始猜歌$', priority=5)
guess_song_join = on_regex(pattern=r'^报名猜歌$', priority=5)
guess_song_skip = on_regex(pattern=r'^跳过$', priority=5)
guess_song_status = on_regex(pattern=r'^猜歌状态$', priority=5)
guess_song_stop = on_regex(pattern=r'^强制结束猜歌$', priority=5)
guess_song_rules = on_regex(pattern=r'^猜歌规则$', priority=5)
guess_song_end_signup = on_regex(pattern=r'^结束猜歌报名$', priority=5)
guess_song_set_duration = on_regex(pattern=r'^设置播放时长 (\d+)$', priority=5)
guess_song_set_mode = on_regex(pattern=r'^设置猜歌模式 (\d+)$', priority=5)

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
        "🚀 发送 '结束猜歌报名' 可提前开始游戏\n"
        # "⚙️ 发送 '设置播放时长 数字' 调整播放时长\n"
        "⚙️ 发送 '设置猜歌模式 1/2' 切换模式"
    )
    
    # 300秒后开始游戏
    await asyncio.sleep(300)
    
    if group_id in games and games[group_id].state == GameState.SIGNUP:
        await start_game_process(bot, group_id)

@guess_song_set_duration.handle()
async def set_play_duration(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    duration = int(event.get_message().extract_plain_text().split()[-1])
    
    if group_id not in games:
        await guess_song_set_duration.send("当前没有猜歌游戏！")
        return
    
    game = games[group_id]
    
    if game.state != GameState.SIGNUP:
        await guess_song_set_duration.send("只能在报名阶段设置播放时长！")
        return
    
    if duration < 10 or duration > 60:
        await guess_song_set_duration.send("播放时长必须在10-60秒之间！")
        return
    
    game.play_duration = duration
    await guess_song_set_duration.send(f"✅ 播放时长已设置为 {duration} 秒")

@guess_song_set_mode.handle()
async def set_guess_mode(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    mode_num = int(event.get_message().extract_plain_text().split()[-1])
    
    if group_id not in games:
        await guess_song_set_mode.send("当前没有猜歌游戏！")
        return
    
    game = games[group_id]
    
    if game.state != GameState.SIGNUP:
        await guess_song_set_mode.send("只能在报名阶段设置猜歌模式！")
        return
    
    if mode_num == 1:
        game.guess_mode = GuessMode.TITLE_ONLY
        await guess_song_set_mode.send("✅ 猜歌模式已设置为：只猜歌名")
    elif mode_num == 2:
        game.guess_mode = GuessMode.TITLE_AND_ARTIST
        await guess_song_set_mode.send("✅ 猜歌模式已设置为：歌名和歌手都要猜对")
    else:
        await guess_song_set_mode.send("模式编号错误！1=只猜歌名，2=歌名和歌手都要猜对")

@guess_song_join.handle()
async def join_guess_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await guess_song_join.send("当前没有猜歌游戏，发送 '开始猜歌' 开始新游戏！")
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
    
    mode_text = "只猜歌名" if game.guess_mode == GuessMode.TITLE_ONLY else "歌名和歌手都要猜对"
    
    await bot.send_group_msg(
        group_id=int(group_id), 
        message=f"🎵 猜歌游戏开始！\n"
                f"👥 参与玩家：{len(game.players)}人\n"
                f"⏰ 游戏时长：5分钟\n"
                # f"🎼 播放时长：{game.play_duration}秒/首\n"
                f"🎮 猜歌模式：{mode_text}\n"
                f"🎯 准备歌曲中..."
    )
    
    # 准备歌曲队列
    game.song_queue = await prepare_song_queue(8, game.play_duration)
    
    if not game.song_queue:
        await bot.send_group_msg(group_id=int(group_id), message="❌ 获取歌曲失败，游戏结束！")
        del games[group_id]
        return
    
    # 设置跳过投票阈值
    game.skip_threshold = max(1, len(game.players) // 2)
    
    await bot.send_group_msg(
        group_id=int(group_id), 
        message=f"✅ 歌曲准备完成！共{len(game.song_queue)}首歌\n"
                f"🗳️ 跳过投票需要{game.skip_threshold}票\n"
                f"🎵 开始第一首歌..."
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
    mode_hint = "请猜歌名！" if game.guess_mode == GuessMode.TITLE_ONLY else "请猜歌名和歌手！"
    
    # 处理歌词显示
    lyric_display = ""
    if song.lyric:
        if isinstance(song.lyric, str):
            lyric_display = song.lyric
        elif isinstance(song.lyric, (list, set)):
            lyric_display = "\n".join(str(line) for line in song.lyric)
        else:
            lyric_display = str(song.lyric)
    
   
    message_parts = [
        f"🎵 第{game.current_song_index + 1}首歌开始！\n",
        "\n💡 歌词提示：\n\n",
        lyric_display,
        f"\n\n🎯 {mode_hint}\n",
        "📝 发送 '跳过' 投票跳过"
    ]

     # 添加试听链接（如果有的话）
    if song.preview_url:
        
        # 使用CQ码创建可点击链接
        message_parts.extend([
            "\n🎧 试听链接\n",
             f"🔗 点击试听: {song.preview_url}\n\n"
        ])
    
    message = "".join(message_parts)
    
    try:
        await bot.send_group_msg(group_id=int(group_id), message=message)
    except Exception as e:
        print(f"发送消息失败: {e}")
        return
    
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
    if check_answer(message, game.current_song.title, game.current_song.artist, game.guess_mode):
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
        mode_text = "只猜歌名" if game.guess_mode == GuessMode.TITLE_ONLY else "歌名和歌手都要猜对"
        await guess_song_status.send(
            f"🎵 猜歌游戏报名中\n"
            f"👥 当前参与人数：{len(game.players)}\n"
            # f"🎼 播放时长：{game.play_duration}秒\n"
            f"🎮 猜歌模式：{mode_text}"
        )
        return
    
    if game.state != GameState.PLAYING:
        await guess_song_status.send("游戏未在进行中！")
        return
    
    # 计算剩余时间
    elapsed = time.time() - game.start_time
    remaining = max(0, 300 - elapsed)
    
    # 排序玩家
    sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
    
    mode_text = "只猜歌名" if game.guess_mode == GuessMode.TITLE_ONLY else "歌名和歌手都要猜对"
    
    status_msg = [
        f"🎵 猜歌游戏进行中\n",
        f"🎯 当前第{game.current_song_index + 1}首歌\n",
        f"⏰ 剩余时间：{int(remaining)}秒\n",
        f"🎮 猜歌模式：{mode_text}\n\n",
        "🏆 当前排行榜：\n"
    ]
    
    for i, player in enumerate(sorted_players[:5], 1):
        status_msg.append(f"{i}. {player.nickname}: {player.score}分 ({player.correct_guesses}首)\n")
    
    await guess_song_status.send("".join(status_msg))

@guess_song_stop.handle()
async def stop_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = event.user_id
    
    # 检查是否为管理员
    try:
        member_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        if member_info['role'] not in ['admin', 'owner']:
            await guess_song_stop.send("只有管理员可以强制结束游戏！")
            return
    except:
        await guess_song_stop.send("权限检查失败！")
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
        "• 支持两种猜歌模式\n"
        "• 发送 '跳过' 投票跳过当前歌曲\n\n"
        "🎮 猜歌模式：\n"
        "• 模式1：只猜歌名（默认）\n"
        "• 模式2：歌名和歌手都要猜对\n\n"
        "⚙️ 设置选项：\n"
        # "• 设置播放时长 10-60秒\n"
        "• 设置猜歌模式 1或2\n\n"
        "🏆 获胜条件：\n"
        "游戏结束时分数最高者获胜\n\n"
        "💡 提示：\n"
        "• 每首歌会提供歌手、专辑和部分歌词提示\n"
        "• 支持模糊匹配，不需要完全准确\n"
        "• 发送 '猜歌状态' 查看当前排行榜"
    )
    
    await guess_song_rules.send(rules)

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
    
    mode_text = "只猜歌名" if game.guess_mode == GuessMode.TITLE_ONLY else "歌名和歌手都要猜对"
    
    await guess_song_end_signup.send(
        f"📢 报名提前结束！\n"
        f"👥 参与玩家：{len(game.players)}人\n"
        # f"🎼 播放时长：{game.play_duration}秒\n"
        f"🎮 猜歌模式：{mode_text}\n"
        f"🎵 游戏即将开始..."
    )
    
    # 提前开始游戏
    await start_game_process(bot, group_id)