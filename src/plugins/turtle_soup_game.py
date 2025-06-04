import asyncio
import random
import time
import re
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum

from nonebot import on_regex, on_command, on_message,get_driver
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, MessageSegment
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, ArgPlainText
from nonebot.adapters.onebot.v11.message import Message
from .game_score import update_player_score

# NLP相关导入
import jieba
from difflib import SequenceMatcher
from collections import Counter

# 游戏状态枚举
class GameState(Enum):
    WAITING = "waiting"      # 等待开始
    SIGNUP = "signup"        # 报名阶段
    STORY_TELLING = "story"  # 出题阶段
    PLAYING = "playing"      # 游戏进行中
    FINISHED = "finished"    # 游戏结束

# 问题类型枚举
class QuestionType(Enum):
    YES_NO = "yes_no"        # 是否问题
    OPEN = "open"            # 开放问题
    GUESS = "guess"          # 猜测答案

@dataclass
class Player:
    user_id: str
    nickname: str
    score: int = 0
    questions_asked: int = 0
    correct_guesses: int = 0
    is_storyteller: bool = False

@dataclass
class Question:
    player_id: str
    content: str
    question_type: QuestionType
    timestamp: float
    answered: bool = False
    answer: str = ""

@dataclass
class Story:
    title: str
    scenario: str  # 情景描述
    truth: str     # 真相
    keywords: List[str]  # 关键词
    difficulty: int = 1  # 难度等级 1-5
    category: str = "经典"  # 分类

@dataclass
class TurtleSoupGame:
    group_id: str
    state: GameState = GameState.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    storyteller_id: Optional[str] = None
    current_story: Optional[Story] = None
    questions: List[Question] = field(default_factory=list)
    start_time: Optional[float] = None
    game_duration: int = 1800  # 30分钟
    question_timeout: int = 300  # 5分钟问题超时
    last_activity: float = 0
    hints_given: int = 0
    max_hints: int = 3
    solved: bool = False
    timeout_task: Optional[asyncio.Task] = None

# 游戏实例存储
games: Dict[str, TurtleSoupGame] = {}

# NLP工具类
class NLPProcessor:
    def __init__(self):
        # 预定义关键词库
        self.yes_keywords = {
            "是", "对", "正确", "没错", "确实", "当然", "肯定", "是的", "对的", 
            "yes", "true", "right", "correct", "absolutely", "definitely"
        }
        
        self.no_keywords = {
            "不是", "不对", "错误", "不", "否", "没有", "不是的", "错了", "不对的",
            "no", "false", "wrong", "incorrect", "nope", "negative"
        }
        
        self.question_patterns = [
            r".*是否.*", r".*是不是.*", r".*有没有.*", r".*会不会.*",
            r".*能不能.*", r".*可不可以.*", r".*要不要.*", r".*需不需要.*",
            r".*吗[？?]?$", r".*呢[？?]?$", r".*么[？?]?$"
        ]
        
        self.guess_keywords = {
            "答案是", "真相是", "我猜", "应该是", "可能是", "估计是", 
            "我觉得", "我认为", "我想", "会不会是", "是不是"
        }
    
    def segment_text(self, text: str) -> List[str]:
        """分词"""
        return list(jieba.cut(text))
    
    def is_yes_answer(self, text: str) -> bool:
        """判断是否为肯定回答"""
        words = set(self.segment_text(text.lower()))
        return bool(words & self.yes_keywords)
    
    def is_no_answer(self, text: str) -> bool:
        """判断是否为否定回答"""
        words = set(self.segment_text(text.lower()))
        return bool(words & self.no_keywords)
    
    def is_question(self, text: str) -> bool:
        """判断是否为问题"""
        # 检查问号
        if '？' in text or '?' in text:
            return True
        
        # 检查问题模式
        for pattern in self.question_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def is_guess(self, text: str) -> bool:
        """判断是否为猜测"""
        for keyword in self.guess_keywords:
            if keyword in text:
                return True
        return False
    
    def classify_question(self, text: str) -> QuestionType:
        """分类问题类型"""
        if self.is_guess(text):
            return QuestionType.GUESS
        elif self.is_question(text):
            return QuestionType.YES_NO
        else:
            return QuestionType.OPEN
    
    def similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        words = self.segment_text(text)
        # 过滤停用词和标点
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [word for word in words if len(word) > 1 and word not in stopwords and word.isalnum()]
        return keywords

# 初始化NLP处理器
nlp_processor = NLPProcessor()

# 海龟汤题库
STORY_DATABASE = [
    Story(
        title="电梯惊魂",
        scenario="一个男人住在20楼，每天早上坐电梯下楼上班。晚上回来时，如果有其他人在电梯里，他就坐到20楼；如果只有他一个人，他就坐到10楼，然后走楼梯上去。为什么？",
        truth="因为这个男人是侏儒，够不到20楼的按钮，只能按到10楼。但如果有其他人在，他可以请别人帮忙按20楼。",
        keywords=["身高", "侏儒", "按钮", "够不到", "电梯"],
        difficulty=2,
        category="经典"
    ),
    Story(
        title="半夜敲门",
        scenario="一个女人半夜听到敲门声，透过猫眼看到一个男人。她没有开门，第二天发现那个男人死在门口。为什么她不救他？",
        truth="因为那个男人是背对着门的，正常情况下透过猫眼应该看到他的脸，但她看到的是后脑勺，说明男人已经死了，是有人故意摆放的。",
        keywords=["猫眼", "背对", "后脑勺", "死亡", "摆放"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="沙漠死亡",
        scenario="一个男人在沙漠中死去，身边有一个包裹，包裹没有打开。救援队发现他时，发现如果他打开包裹，就不会死。包裹里是什么？",
        truth="包裹里是降落伞。这个男人是跳伞时降落伞没有打开而摔死的，不是在沙漠中渴死的。",
        keywords=["降落伞", "跳伞", "摔死", "没打开"],
        difficulty=2,
        category="经典"
    ),
    Story(
        title="绿衣男子",
        scenario="一个穿绿衣服的男子从30楼跳下来，却没有受伤，也没有任何保护措施。为什么？",
        truth="因为他跳进了游泳池。30楼指的是游泳池的深度30米，不是建筑物的30楼。",
        keywords=["游泳池", "深度", "水", "跳水"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="餐厅悲剧",
        scenario="一个男人在餐厅点了海鸥肉，吃了一口就哭了，然后自杀了。为什么？",
        truth="这个男人曾经在海上遇难，同伴告诉他吃的是海鸥肉才活下来。现在他发现真正的海鸥肉味道不是这样的，意识到当时吃的是同伴的肉。",
        keywords=["海难", "同伴", "人肉", "欺骗", "真相"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="雨夜归人",
        scenario="一个男人雨夜开车回家，看到路边有三个人在等车：一个是快死的老人，一个是救过他命的医生，一个是他的梦中情人。车只能坐一个人，他应该载谁？",
        truth="他把车钥匙给医生，让医生载老人去医院，自己陪梦中情人等下一班车。",
        keywords=["车钥匙", "医生", "老人", "医院", "陪伴"],
        difficulty=3,
        category="智力"
    )
]

# 游戏命令注册
start_game = on_regex(pattern=r"^开始海龟汤$", priority=5)
signup = on_regex(pattern=r"^报名海龟汤$", priority=5)
end_signup = on_regex(pattern=r"^结束海龟汤报名$", priority=5)
# 移除出题者相关命令
# be_storyteller = on_regex(pattern=r"^我来出题$", priority=5)
# start_story = on_regex(pattern=r"^开始出题$", priority=5)
start_story = on_regex(pattern=r"^开始游戏$", priority=5)  # 改为开始游戏
change_story = on_regex(pattern=r"^换题$", priority=5)  # 新增换题命令
end_game = on_regex(pattern=r"^结束海龟汤$", priority=5)
game_status = on_regex(pattern=r"^海龟汤状态$", priority=5)
game_hint = on_regex(pattern=r"^海龟汤提示$", priority=5)
game_rules = on_regex(pattern=r"^海龟汤规则$", priority=5)

# 消息处理器（用于处理游戏中的问答）
question_handler = on_message(priority=10)

@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id in games and games[group_id].state != GameState.FINISHED:
        await start_game.finish("海龟汤游戏已经在进行中！")
    
    games[group_id] = TurtleSoupGame(group_id=group_id)
    games[group_id].state = GameState.SIGNUP
    
    await start_game.finish(
        "🐢 海龟汤游戏开始！\n"
        "📝 请发送【报名海龟汤】参与游戏\n"
        "🎮 发送【开始游戏】开始游戏（机器人出题）\n"
        "📋 发送【海龟汤规则】查看游戏规则"
    )

@signup.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await signup.finish("游戏还未开始，请先发送【开始海龟汤】")
    
    game = games[group_id]
    if game.state != GameState.SIGNUP:
        await signup.finish("当前不在报名阶段！")
    
    if user_id in game.players:
        await signup.finish("你已经报名了！")
    
    # 获取玩家信息
    user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
    nickname = user_info.get('nickname', f'玩家{user_id}')
    
    game.players[user_id] = Player(user_id=user_id, nickname=nickname)
    
    # 添加参与游戏基础分
    await update_player_score(user_id, group_id, 5, 'turtle_soup', None, 'participation')
    
    await signup.finish(f"🎯 玩家 {nickname} 报名成功！当前玩家数：{len(game.players)}")

# @be_storyteller.handle()
# async def handle_be_storyteller(bot: Bot, event: GroupMessageEvent):
#     group_id = str(event.group_id)
#     user_id = str(event.user_id)
    
#     if group_id not in games:
#         await be_storyteller.finish("游戏还未开始！")
    
#     game = games[group_id]
#     if game.state != GameState.SIGNUP:
#         await be_storyteller.finish("当前不在报名阶段！")
    
#     if user_id not in game.players:
#         await be_storyteller.finish("请先报名参加游戏！")
    
#     if game.storyteller_id:
#         await be_storyteller.finish(f"已经有出题者了：{game.players[game.storyteller_id].nickname}")
    
#     game.storyteller_id = user_id
#     game.players[user_id].is_storyteller = True
    
#     await be_storyteller.finish(
#         f"📚 {game.players[user_id].nickname} 成为出题者！\n"
#         "🎲 发送【开始出题】开始游戏，系统将随机选择题目\n"
#         "⏰ 或等待更多玩家报名"
#     )

@start_story.handle()
async def handle_start_story(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await start_story.finish("游戏还未开始！")
    
    game = games[group_id]
    if game.state != GameState.SIGNUP:
        await start_story.finish("游戏不在报名阶段！")
    
    if len(game.players) < 1:  # 改为至少1名玩家
        await start_story.finish("至少需要1名玩家才能开始游戏！")
    
    # 机器人作为出题者，不需要设置storyteller_id
    game.storyteller_id = None
    
    # 随机选择题目
    game.current_story = random.choice(STORY_DATABASE)
    game.state = GameState.PLAYING
    game.start_time = time.time()
    game.last_activity = time.time()
    
    # 设置游戏超时
    game.timeout_task = asyncio.create_task(game_timeout(group_id))
    
    await start_story.finish(
        f"🎭 海龟汤开始！\n\n"
        f"📖 题目：{game.current_story.title}\n"
        f"📝 情景：{game.current_story.scenario}\n\n"
        f"🤔 请玩家们提问来推理出真相！\n"
        f"🤖 出题者：机器人\n"
        f"⏰ 游戏时长：{game.game_duration // 60}分钟\n"
        f"🔍 发送【海龟汤提示】获取提示（限{game.max_hints}次）\n"
        f"🔄 发送【换题】更换题目"
    )

# 新增换题命令处理
@change_story.handle()
async def handle_change_story(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await change_story.finish("当前没有进行中的游戏！")
    
    game = games[group_id]
    if game.state != GameState.PLAYING:
        await change_story.finish("游戏不在进行中！")
    
    # 检查是否是游戏参与者
    if user_id not in game.players:
        await change_story.finish("只有游戏参与者才能换题！")
    
    # 避免重复题目
    available_stories = [story for story in STORY_DATABASE if story.title != game.current_story.title]
    
    if not available_stories:
        await change_story.finish("没有更多题目可以更换了！")
    
    # 重置游戏状态
    old_title = game.current_story.title
    game.current_story = random.choice(available_stories)
    game.questions.clear()
    game.hints_given = 0
    game.start_time = time.time()
    game.last_activity = time.time()
    game.solved = False
    
    # 重置玩家问题计数
    for player in game.players.values():
        player.questions_asked = 0
    
    await change_story.finish(
        f"🔄 题目已更换！\n\n"
        f"📖 新题目：{game.current_story.title}\n"
        f"📝 情景：{game.current_story.scenario}\n\n"
        f"🤔 请继续提问推理真相！\n"
        f"💡 提示次数已重置：0/{game.max_hints}"
    )

async def handle_question(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    message = str(event.get_message()).strip()
    
    if group_id not in games:
        return
    
    game = games[group_id]
    if game.state != GameState.PLAYING:
        return
    
    if user_id not in game.players:
        return
    
    # 机器人作为出题者，自动回答问题
    player = game.players[user_id]
    
    # 检查是否是猜测答案
    guess_keywords = ["答案是", "真相是", "我猜", "应该是", "是不是"]
    is_guess = any(keyword in message for keyword in guess_keywords)
    
    if is_guess:
        await handle_guess_attempt(bot, event, game, message)
        return
    
    # 处理普通问题
    question_type = nlp_processor.classify_question(message)
    
    question = Question(
        player_id=user_id,
        content=message,
        question_type=question_type,
        timestamp=time.time()
    )
    
    game.questions.append(question)
    player.questions_asked += 1
    game.last_activity = time.time()
    
    # 机器人自动回答
    answer = await generate_auto_answer(game, message)
    question.answered = True
    question.answer = answer
    
    # 分析回答类型
    if nlp_processor.is_yes_answer(answer):
        response_emoji = "✅"
    elif nlp_processor.is_no_answer(answer):
        response_emoji = "❌"
    else:
        response_emoji = "💭"
    
    await bot.send_group_msg(
        group_id=int(group_id),
        message=f"{response_emoji} 机器人回答：{answer}\n\n"
               f"📝 {player.nickname} 的问题：{message}"
    )

# 新增自动回答生成函数
async def generate_auto_answer(game: TurtleSoupGame, question: str) -> str:
    """根据问题和真相生成自动回答"""
    story = game.current_story
    
    # 简单的关键词匹配逻辑
    question_lower = question.lower()
    truth_lower = story.truth.lower()
    keywords_lower = [kw.lower() for kw in story.keywords]
    
    # 检查问题中是否包含关键词
    has_keywords = any(kw in question_lower for kw in keywords_lower)
    
    # 检查问题中是否包含真相的关键部分
    truth_words = jieba.lcut(truth_lower)
    question_words = jieba.lcut(question_lower)
    
    overlap = len(set(truth_words) & set(question_words))
    overlap_ratio = overlap / len(truth_words) if truth_words else 0
    
    # 根据重叠度和关键词匹配决定回答
    if overlap_ratio > 0.3 or has_keywords:
        return random.choice(["是的", "对", "正确", "没错"])
    elif any(word in question_lower for word in ["不", "没", "非", "否"]):
        # 如果问题是否定形式，需要反向判断
        if overlap_ratio > 0.2:
            return random.choice(["不是", "不对", "错误"])
        else:
            return random.choice(["是的", "对", "正确"])
    else:
        return random.choice(["不是", "不对", "无关", "不重要"])

async def handle_player_question(bot: Bot, event: GroupMessageEvent, game: TurtleSoupGame, message: str):
    user_id = str(event.user_id)
    player = game.players[user_id]
    
    # 更新活动时间
    game.last_activity = time.time()
    
    # 使用NLP分析问题类型
    question_type = nlp_processor.classify_question(message)
    
    # 创建问题记录
    question = Question(
        player_id=user_id,
        content=message,
        question_type=question_type,
        timestamp=time.time()
    )
    game.questions.append(question)
    player.questions_asked += 1
    
    # 检查是否为猜测答案
    if question_type == QuestionType.GUESS:
        await handle_guess_attempt(bot, event, game, message, player)
    else:
        # 普通问题，等待出题者回答
        storyteller = game.players[game.storyteller_id]
        await bot.send_group_msg(
            group_id=int(game.group_id),
            message=f"❓ {player.nickname} 问：{message}\n\n@{storyteller.nickname} 请回答（是/否/无关）"
        )

async def handle_guess_attempt(bot: Bot, event: GroupMessageEvent, game: TurtleSoupGame, message: str, player: Player):
    """处理猜测答案"""
    # 提取猜测内容
    guess_content = message
    for keyword in nlp_processor.guess_keywords:
        if keyword in message:
            guess_content = message.split(keyword, 1)[-1].strip()
            break
    
    # 计算与真相的相似度
    similarity = nlp_processor.similarity(guess_content, game.current_story.truth)
    
    if similarity > 0.7:  # 相似度阈值
        # 猜对了！
        game.solved = True
        game.state = GameState.FINISHED
        player.correct_guesses += 1
        
        # 取消超时任务
        if game.timeout_task:
            game.timeout_task.cancel()
        
        # 计算奖励分数
        time_bonus = max(0, 100 - int((time.time() - game.start_time) / 60) * 5)
        question_penalty = min(50, player.questions_asked * 2)
        final_score = 100 + time_bonus - question_penalty
        
        await update_player_score(player.user_id, game.group_id, final_score, 'turtle_soup', None, 'win')
        
        await bot.send_group_msg(
            group_id=int(game.group_id),
            message=f"🎉 恭喜 {player.nickname} 猜对了！\n\n"
                   f"💡 真相：{game.current_story.truth}\n\n"
                   f"🏆 获得分数：{final_score}\n"
                   f"⏰ 用时：{int((time.time() - game.start_time) / 60)}分钟\n"
                   f"❓ 提问次数：{player.questions_asked}"
        )
    else:
        # 猜错了
        await bot.send_group_msg(
            group_id=int(game.group_id),
            message=f"❌ {player.nickname} 的猜测不正确，请继续提问推理！"
        )

async def handle_storyteller_response(bot: Bot, event: GroupMessageEvent, game: TurtleSoupGame, message: str):
    """处理出题者的回答"""
    if not game.questions:
        return
    
    # 获取最后一个未回答的问题
    last_question = None
    for q in reversed(game.questions):
        if not q.answered:
            last_question = q
            break
    
    if not last_question:
        return
    
    # 标记问题已回答
    last_question.answered = True
    last_question.answer = message
    
    # 分析回答类型
    if nlp_processor.is_yes_answer(message):
        response_emoji = "✅"
    elif nlp_processor.is_no_answer(message):
        response_emoji = "❌"
    else:
        response_emoji = "💭"
    
    player = game.players[last_question.player_id]
    await bot.send_group_msg(
        group_id=int(game.group_id),
        message=f"{response_emoji} 出题者回答：{message}\n\n"
               f"📝 {player.nickname} 的问题：{last_question.content}"
    )

@game_hint.handle()
async def handle_game_hint(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await game_hint.finish("当前没有进行中的游戏！")
    
    game = games[group_id]
    if game.state != GameState.PLAYING:
        await game_hint.finish("游戏不在进行中！")
    
    if game.hints_given >= game.max_hints:
        await game_hint.finish(f"提示次数已用完！（{game.hints_given}/{game.max_hints}）")
    
    game.hints_given += 1
    
    # 根据提示次数给出不同程度的提示
    if game.hints_given == 1:
        hint = f"🔍 提示1：关键词包含：{', '.join(game.current_story.keywords[:2])}"
    elif game.hints_given == 2:
        hint = f"🔍 提示2：这是一个{game.current_story.category}类型的题目，难度{game.current_story.difficulty}星"
    else:
        hint = f"🔍 提示3：关键词：{', '.join(game.current_story.keywords)}"
    
    await game_hint.finish(f"{hint}\n\n剩余提示次数：{game.max_hints - game.hints_given}")

@game_status.handle()
async def handle_game_status(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await game_status.finish("当前没有进行中的游戏！")
    
    game = games[group_id]
    
    if game.state == GameState.SIGNUP:
        status_msg = f"📋 游戏状态：报名中\n👥 玩家数量：{len(game.players)}\n"
        if game.storyteller_id:
            status_msg += f"📚 出题者：{game.players[game.storyteller_id].nickname}"
    elif game.state == GameState.PLAYING:
        elapsed = int((time.time() - game.start_time) / 60)
        remaining = max(0, game.game_duration // 60 - elapsed)
        status_msg = (
            f"🎮 游戏状态：进行中\n"
            f"📖 题目：{game.current_story.title}\n"
            f"👥 玩家数量：{len(game.players)}\n"
            f"❓ 问题数量：{len(game.questions)}\n"
            f"⏰ 已用时间：{elapsed}分钟\n"
            f"⏳ 剩余时间：{remaining}分钟\n"
            f"💡 已用提示：{game.hints_given}/{game.max_hints}"
        )
    else:
        status_msg = "游戏已结束"
    
    await game_status.finish(status_msg)

@game_rules.handle()
async def handle_game_rules(bot: Bot, event: GroupMessageEvent):
    rules = (
        "🐢 海龟汤游戏规则\n\n"
        "📝 游戏流程：\n"
        "1. 发送【开始海龟汤】开始游戏\n"
        "2. 发送【报名海龟汤】参与游戏\n"
        "3. 发送【开始游戏】开始游戏（机器人出题）\n\n"
        "🎯 游戏玩法：\n"
        "• 机器人会给出一个奇怪的情景\n"
        "• 玩家通过提问来推理真相\n"
        "• 机器人会自动回答：是/否/无关\n"
        "• 猜出真相的玩家获胜\n\n"
        "💡 提问技巧：\n"
        "• 多问是否问题（是/否）\n"
        "• 从大方向开始缩小范围\n"
        "• 注意关键词和细节\n"
        "• 可以使用【海龟汤提示】获取提示\n"
        "• 可以使用【换题】更换题目\n\n"
        "🏆 计分规则：\n"
        "• 参与游戏：+5分\n"
        "• 猜对真相：+100分+时间奖励-提问惩罚\n"
        "• 时间奖励：每分钟-5分\n"
        "• 提问惩罚：每次提问-2分"
    )
    
    await game_rules.finish(rules)

@end_game.handle()
async def handle_end_game(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await end_game.finish("当前没有进行中的游戏！")
    
    game = games[group_id]
    
    # 检查权限（出题者或管理员可以结束游戏）
    if user_id != game.storyteller_id:
        member_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        if member_info.get('role') not in ['admin', 'owner']:
            await end_game.finish("只有出题者或群管理员可以结束游戏！")
    
    # 取消超时任务
    if game.timeout_task:
        game.timeout_task.cancel()
    
    game.state = GameState.FINISHED
    
    # 显示游戏总结
    if game.current_story:
        summary = (
            f"🎭 海龟汤游戏结束！\n\n"
            f"📖 题目：{game.current_story.title}\n"
            f"💡 真相：{game.current_story.truth}\n\n"
            f"📊 游戏统计：\n"
            f"👥 参与玩家：{len(game.players)}人\n"
            f"❓ 总提问数：{len(game.questions)}个\n"
            f"⏰ 游戏时长：{int((time.time() - game.start_time) / 60)}分钟"
        )
        
        if game.solved:
            winner = None
            for player in game.players.values():
                if player.correct_guesses > 0:
                    winner = player
                    break
            if winner:
                summary += f"\n🏆 获胜者：{winner.nickname}"
    else:
        summary = "游戏已结束！"
    
    await end_game.finish(summary)

async def game_timeout(group_id: str):
    """游戏超时处理"""
    try:
        await asyncio.sleep(games[group_id].game_duration)
        
        if group_id in games and games[group_id].state == GameState.PLAYING:
            game = games[group_id]
            game.state = GameState.FINISHED
            
            # 这里需要bot实例，实际使用时需要从全局获取
            # await bot.send_group_msg(
            #     group_id=int(group_id),
            #     message=f"⏰ 游戏时间到！\n\n💡 真相：{game.current_story.truth}"
            # )
    except asyncio.CancelledError:
        pass

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
                    current_time - game.last_activity > 3600):
                    to_remove.append(group_id)
            
            for group_id in to_remove:
                del games[group_id]
            
            await asyncio.sleep(300)  # 每5分钟清理一次
        except Exception as e:
            print(f"清理游戏时出错: {e}")
            await asyncio.sleep(300)

driver = get_driver()

@driver.on_startup
async def start_cleanup():
    """在bot启动时开始清理任务"""
    asyncio.create_task(cleanup_finished_games())