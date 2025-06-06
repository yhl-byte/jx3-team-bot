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
        
        # 停用词
        self.stopwords = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"
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
        keywords = [word for word in words if len(word) > 1 and word not in self.stopwords and word.isalnum()]
        return keywords
    
    def is_truth_guess(self, guess: str, truth: str, threshold: float = 0.6) -> bool:
        """判断是否猜中真相"""
        # 计算文本相似度
        similarity = self.similarity(guess.lower(), truth.lower())
        if similarity > threshold:
            return True
        
        # 关键词匹配
        guess_keywords = set(self.extract_keywords(guess))
        truth_keywords = set(self.extract_keywords(truth))
        
        if truth_keywords:
            keyword_overlap = len(guess_keywords & truth_keywords) / len(truth_keywords)
            return keyword_overlap > 0.5
        
        return False
    
    def generate_answer(self, question: str, story: Story) -> str:
        """根据问题和故事生成智能回答"""
        question_lower = question.lower()
        truth_lower = story.truth.lower()
        keywords_lower = [kw.lower() for kw in story.keywords]
        
        # 提取问题关键词
        question_keywords = set(self.extract_keywords(question))
        truth_keywords = set(self.extract_keywords(story.truth))
        story_keywords = set([kw.lower() for kw in story.keywords])
        
        # 计算关键词重叠度
        keyword_overlap = len(question_keywords & (truth_keywords | story_keywords))
        total_keywords = len(truth_keywords | story_keywords)
        overlap_ratio = keyword_overlap / total_keywords if total_keywords > 0 else 0
        
        # 检查否定词
        negative_words = {"不", "没", "非", "否", "无"}
        has_negative = any(word in question for word in negative_words)
        
        # 特殊情况处理
        if any(word in question_lower for word in ["死", "杀", "害", "伤"]):
            if any(word in truth_lower for word in ["死", "杀", "害", "伤"]):
                return "是的" if not has_negative else "不是"
            else:
                return "不是" if not has_negative else "是的"
        
        # 根据重叠度决定回答
        if overlap_ratio > 0.4:
            return "是的" if not has_negative else "不是"
        elif overlap_ratio > 0.2:
            return random.choice(["部分正确", "有关联", "接近了"])
        else:
            return random.choice(["不是", "无关", "不重要", "不对"]) if not has_negative else "是的"

# 初始化NLP处理器
nlp_processor = NLPProcessor()

# 扩展的海龟汤题库
STORY_DATABASE = [
    # 经典题目
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
        scenario="一个男人在沙漠中死去，身体有一个包裹，包裹没有打开。救援队发现他时，发现如果他打开包裹，就不会死。包裹里是什么？",
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
    ),
    
    # 新增题目
    Story(
        title="镜子之谜",
        scenario="一个女人每天早上照镜子都会哭，但她的容貌很美丽，身体也很健康。为什么她会哭？",
        truth="因为她是盲人，每天照镜子是为了确认自己还活着，但她永远看不到自己的样子，所以会哭。",
        keywords=["盲人", "看不到", "确认", "活着", "永远"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="完美的犯罪",
        scenario="一个男人杀死了他的妻子，警察来调查时，他正在做饭。警察没有发现任何证据，但还是逮捕了他。为什么？",
        truth="因为他在做饭时用的是妻子的肉。警察发现他做的菜里有人肉。",
        keywords=["人肉", "做饭", "妻子", "证据", "发现"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="时间停止",
        scenario="一个男人看了一眼手表后就死了，但手表没有任何毒性或危险。为什么？",
        truth="因为他是潜水员，看手表发现氧气即将耗尽，但已经来不及上浮，最终窒息而死。",
        keywords=["潜水员", "氧气", "耗尽", "上浮", "窒息"],
        difficulty=3,
        category="悬疑"
    ),
    Story(
        title="无声的呼救",
        scenario="一个女人在电话里说'我很好，一切都很正常'，但接电话的人立即报警了。为什么？",
        truth="因为这个女人是哑巴，她不可能说话。有人在威胁她，强迫她说这些话。",
        keywords=["哑巴", "不能说话", "威胁", "强迫", "危险"],
        difficulty=2,
        category="悬疑"
    ),
    Story(
        title="最后的晚餐",
        scenario="一个男人在餐厅吃完最后一口饭后就死了，但食物没有毒，他也没有噎到。为什么？",
        truth="因为他是死刑犯，这是他的最后一餐。吃完后就被执行死刑了。",
        keywords=["死刑犯", "最后一餐", "执行", "死刑", "监狱"],
        difficulty=2,
        category="悲伤"
    ),
    Story(
        title="黑暗中的真相",
        scenario="一个男人在完全黑暗的房间里，没有任何光源，但他知道房间里有一个死人。他是怎么知道的？",
        truth="因为他闻到了尸体腐烂的味道。",
        keywords=["尸体", "腐烂", "味道", "嗅觉", "死亡"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="生日礼物",
        scenario="一个女孩收到生日礼物后立即自杀了，礼物是一个很普通的音乐盒。为什么？",
        truth="因为音乐盒播放的是她死去母亲最喜欢的歌，这让她想起了痛苦回忆，无法承受而自杀。",
        keywords=["音乐盒", "母亲", "死去", "回忆", "痛苦"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="雪夜追踪",
        scenario="警察在雪地里追踪一个罪犯，发现脚印突然消失了，但周围没有任何可以隐藏的地方。罪犯去哪了？",
        truth="罪犯倒着走，脚印看起来像是朝相反方向的，警察追错了方向。",
        keywords=["倒着走", "脚印", "相反", "方向", "欺骗"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="无头骑士",
        scenario="一个骑士骑马经过一座桥，桥的另一端有人看到他没有头。但骑士本人并没有死。这是怎么回事？",
        truth="因为桥很低，骑士为了通过桥而低头，从另一端看起来就像没有头一样。",
        keywords=["低头", "桥", "很低", "通过", "视觉"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="医生的诊断",
        scenario="一个医生看了病人一眼就说他会在午夜死去，结果真的应验了。医生是怎么知道的？",
        truth="因为病人是医生的仇人，医生计划在午夜杀死他。",
        keywords=["仇人", "计划", "杀死", "预谋", "报复"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="消失的新娘",
        scenario="一个新娘在婚礼当天消失了，一年后在她的婚纱里发现了她的尸体。她是怎么死的？",
        truth="她在玩捉迷藏时躲进了一个古老的箱子里，箱子自动锁上了，她被困死在里面。",
        keywords=["捉迷藏", "箱子", "锁上", "困死", "窒息"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="画家的杰作",
        scenario="一个画家画了一幅自画像，画完后就自杀了。但这幅画看起来很普通，没有任何特殊之处。为什么他要自杀？",
        truth="因为画家是盲人，他画的自画像其实是一片空白，这让他意识到自己永远无法看到自己的作品。",
        keywords=["盲人", "空白", "看不到", "作品", "绝望"],
        difficulty=4,
        category="悲伤"
    ),
    Story(
        title="深夜来电",
        scenario="一个男人深夜接到电话，对方什么都没说就挂了。第二天他就死了。为什么？",
        truth="因为他是盲人，靠听声音辨别方向。电话铃声让他误以为是门铃，走向门口时从楼梯上摔下来死了。",
        keywords=["盲人", "听声音", "门铃", "楼梯", "摔死"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="完美的谎言",
        scenario="一个女人告诉警察她的丈夫是自杀的，警察相信了。但实际上她是kill死了丈夫。她是怎么做到的？",
        truth="她在丈夫睡觉时在他手上绑了一块冰，冰融化后绳子松开，看起来像是自己开枪自杀。",
        keywords=["冰", "融化", "绳子", "开枪", "伪装"],
        difficulty=4,
        category="犯罪"
    ),
    Story(
        title="孤岛求生",
        scenario="一个男人被困在孤岛上，岛上有充足的食物和水，但他还是死了。为什么？",
        truth="因为他看到远处有船经过，生起火堆求救，但风向改变，烟雾遮挡了他的视线，他没看到船已经改变航向来救他，绝望中自杀了。",
        keywords=["求救", "火堆", "烟雾", "船", "绝望"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="魔术师的秘密",
        scenario="一个魔术师在表演中真的消失了，观众以为是魔术，但他再也没有出现。他去哪了？",
        truth="他掉进了舞台下的陷阱里，被机关夹死了。观众以为这是魔术的一部分。",
        keywords=["陷阱", "机关", "夹死", "舞台", "意外"],
        difficulty=2,
        category="悬疑"
    ),
    Story(
        title="记忆碎片",
        scenario="一个男人失忆了，医生告诉他可以恢复记忆，但他拒绝了。为什么？",
        truth="因为他是杀人犯，失忆让他忘记了自己的罪行，他不想记起这些痛苦的事情。",
        keywords=["杀人犯", "罪行", "忘记", "痛苦", "逃避"],
        difficulty=3,
        category="心理"
    ),
    Story(
        title="最后的电话",
        scenario="一个女人给她的朋友打电话说'我要死了'，朋友以为她在开玩笑。第二天女人真的死了。为什么朋友不相信？",
        truth="因为女人经常开这种玩笑，朋友已经习惯了。但这次她是认真的，她患了绝症。",
        keywords=["开玩笑", "习惯", "绝症", "认真", "误解"],
        difficulty=2,
        category="悲伤"
    ),
    Story(
        title="双胞胎之谜",
        scenario="一对双胞胎兄弟，哥哥杀死了弟弟，但警察无法逮捕他。为什么？",
        truth="因为他们是连体双胞胎，逮捕哥哥就等于杀死他，这在法律上是不被允许的。",
        keywords=["连体", "双胞胎", "法律", "不允许", "困境"],
        difficulty=4,
        category="法律"
    ),
    Story(
        title="沉默的证人",
        scenario="一个哑巴目击了一起谋杀案，但他无法告诉警察凶手是谁。最后凶手还是被抓住了。为什么？",
        truth="因为哑巴用手语描述了凶手的特征，警察找了手语翻译员。",
        keywords=["手语", "描述", "特征", "翻译员", "沟通"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="时光倒流",
        scenario="一个男人声称他能预知未来，并准确预测了几起事件。但实际上他不能预知未来。他是怎么做到的？",
        truth="因为他是时间旅行者，从未来回到了过去，所以知道将要发生的事情。",
        keywords=["时间旅行", "未来", "过去", "知道", "科幻"],
        difficulty=5,
        category="科幻"
    ),
    Story(
        title="无声的音乐",
        scenario="一个聋人在音乐会上哭了，但他听不到任何声音。为什么他会哭？",
        truth="因为他通过振动感受音乐，想起了失去听力前最喜欢的歌曲。",
        keywords=["聋人", "振动", "感受", "失去", "回忆"],
        difficulty=2,
        category="感人"
    ),
    Story(
        title="完美的复仇",
        scenario="一个男人花了十年时间策划复仇，但在复仇成功的那一刻，但他却原谅了仇人。为什么？",
        truth="因为他发现仇人已经失明了，和他一样成了残疾人，他觉得仇人已经受到了足够的惩罚。",
        keywords=["失明", "残疾", "惩罚", "足够", "同情"],
        difficulty=3,
        category="感人"
    ),
    Story(
        title="神秘的房间",
        scenario="一个房间里有一个死人，房间从内部锁着，没有其他出入口，也没有自杀的工具。他是怎么死的？",
        truth="他是被冰锥杀死的，冰锥融化后消失了，所以找不到凶器。",
        keywords=["冰锥", "融化", "消失", "凶器", "密室"],
        difficulty=4,
        category="推理"
    ),
    Story(
        title="最后的愿望",
        scenario="一个即将死去的老人最后的愿望是吃一个苹果，家人给了他苹果，但他吃了一口就死了。苹果没有毒。为什么？",
        truth="因为老人没有牙齿，苹果太硬了，他被噎死了。",
        keywords=["没有牙齿", "太硬", "噎死", "老人", "意外"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="雨中的秘密",
        scenario="一个男人在雨中走路，但他没有被雨淋湿。他没有雨伞，也没有躲在任何地方。为什么？",
        truth="因为他是秃头，雨水直接从他的头上滑落，没有被头发吸收。",
        keywords=["秃头", "滑落", "头发", "吸收", "光滑"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="永恒的等待",
        scenario="一个女人在车站等了一个人50年，但那个人永远不会来了。她为什么还在等？",
        truth="因为她患了阿尔茨海默病，每天都忘记那个人已经死了，重新开始等待。",
        keywords=["阿尔茨海默", "忘记", "死了", "重新", "疾病"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="数字的诅咒",
        scenario="一个数学家看到数字13就会死，但13只是一个普通的数字。为什么？",
        truth="因为他有严重的恐惧症，看到13就会心脏病发作。",
        keywords=["恐惧症", "心脏病", "发作", "心理", "疾病"],
        difficulty=2,
        category="心理"
    ),
    Story(
        title="影子的秘密",
        scenario="一个男人害怕自己的影子，每当看到影子就会尖叫。为什么？",
        truth="因为他的影子里隐藏着他杀死的人的灵魂，只有他能看到。",
        keywords=["灵魂", "杀死", "隐藏", "看到", "超自然"],
        difficulty=4,
        category="超自然"
    ),
    Story(
        title="最后的舞蹈",
        scenario="一个舞蹈家在舞台上跳完最后一支舞后就死了，但她没有生病，也没有受伤。为什么？",
        truth="因为她跳的是死亡之舞，这是她为自己准备的葬礼舞蹈，跳完后服毒自杀了。",
        keywords=["死亡之舞", "葬礼", "服毒", "自杀", "仪式"],
        difficulty=4,
        category="艺术"
    ),
    Story(
        title="无声的呐喊",
        scenario="一个男人在梦中大声呼救，但现实中他一点声音都没有发出。为什么没人救他？",
        truth="因为他被活埋了，在棺材里窒息而死，人们以为他已经死了。",
        keywords=["活埋", "棺材", "窒息", "死了", "误判"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="记忆的重量",
        scenario="一个男人每次想起某个记忆就会变重一点，最后被压死了。这是怎么回事？",
        truth="他每次想起杀死的人就会在身上放一块石头，最后被石头压死了，这是他的自我惩罚。",
        keywords=["石头", "压死", "自我惩罚", "杀死", "负罪感"],
        difficulty=4,
        category="心理"
    ),
    Story(
        title="光明与黑暗",
        scenario="一个盲人重见光明后立即自杀了。为什么？",
        truth="因为他看到了自己杀死的人的尸体就在边，原来他一直和尸体生活在一起。",
        keywords=["重见光明", "尸体", "边", "一直", "恐怖"],
        difficulty=5,
        category="恐怖"
    ),
    Story(
        title="时间的礼物",
        scenario="一个男人收到了一块停止的手表作为礼物，他看了一眼就知道自己会在什么时候死。为什么？",
        truth="因为手表停在了他出生的时间，这意味着他的生命即将结束，回到起点。",
        keywords=["停止", "出生时间", "生命", "结束", "起点"],
        difficulty=4,
        category="哲学"
    ),
    Story(
        title="最后的笑容",
        scenario="一个小丑摘下面具后就死了，但面具没有毒性。为什么？",
        truth="因为面具下面是他腐烂的脸，他其实早就死了，是面具让他看起来还活着。",
        keywords=["腐烂", "早就死了", "面具", "活着", "假象"],
        difficulty=5,
        category="超自然"
    ),
    Story(
        title="声音的陷阱",
        scenario="一个音乐家听到了世界上最美的音乐，然后就死了。音乐没有任何危险。为什么？",
        truth="因为那是天堂的音乐，只有死人才能听到，他听到音乐说明他已经死了。",
        keywords=["天堂", "音乐", "死人", "听到", "已经死了"],
        difficulty=4,
        category="超自然"
    ),
    Story(
        title="永恒的惩罚",
        scenario="一个男人被判处永生，但他认为这是最残酷的惩罚。为什么？",
        truth="因为他必须永远活着看着自己所爱的人一个个死去，承受无尽的痛苦。",
        keywords=["永生", "所爱的人", "死去", "无尽", "痛苦"],
        difficulty=3,
        category="哲学"
    ),
    Story(
        title="镜中世界",
        scenario="一个女人看着镜子，镜子里的自己做了不同的动作。她没有疯，镜子也没有坏。为什么？",
        truth="因为镜子里是她的双胞胎姐妹，她们长得一模一样，姐妹在镜子后面模仿她。",
        keywords=["双胞胎", "姐妹", "一模一样", "后面", "模仿"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="最后的晚餐",
        scenario="一群人在荒岛上，食物只够一个人吃。他们决定抽签决定谁能活下来，但最后所有人都死了。为什么？",
        truth="因为他们抽签的纸条上都写着死，没有人想独自活下来承受孤独。",
        keywords=["抽签", "都写着死", "独自", "孤独", "不想"],
        difficulty=3,
        category="人性"
    )
]


# 游戏命令注册
start_game = on_regex(pattern=r"^(开始海龟汤|开始海|海龟汤)$", priority=5)
signup = on_regex(pattern=r"^(报名海龟汤|报名海|加入海龟汤)$", priority=5)
start_story = on_regex(pattern=r"^(结束报名|开始游戏|开始出题)$", priority=5)
change_story = on_regex(pattern=r"^(换题|更换题目|下一题)$", priority=5)
end_game = on_regex(pattern=r"^(强制结束|结束游戏|结束海龟汤)$", priority=5)
game_status = on_regex(pattern=r"^(海龟汤状态|游戏状态|海状态)$", priority=5)
game_hint = on_regex(pattern=r"^(海龟汤提示|海提示|提示)$", priority=5)
game_rules = on_regex(pattern=r"^(海龟汤规则|海规则|游戏规则)$", priority=5)

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
        "📋 发送【海龟汤规则】查看游戏规则\n"
        f"📚 题库共有 {len(STORY_DATABASE)} 道题目等你挑战！"
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
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'玩家{user_id}')
    except:
        nickname = f'玩家{user_id}'
    
    game.players[user_id] = Player(user_id=user_id, nickname=nickname)
    
    # 添加参与游戏基础分
    await update_player_score(user_id, group_id, 5, 'turtle_soup', None, 'participation')
    
    await signup.finish(f"🎯 玩家 {nickname} 报名成功！当前玩家数：{len(game.players)}")

@start_story.handle()
async def handle_start_story(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await start_story.finish("游戏还未开始！")
    
    game = games[group_id]
    if game.state != GameState.SIGNUP:
        await start_story.finish("游戏不在报名阶段！")
    
    if len(game.players) < 1:
        await start_story.finish("至少需要1名玩家才能开始游戏！")
    
    # 机器人作为出题者
    game.storyteller_id = None
    
    # 随机选择题目
    game.current_story = random.choice(STORY_DATABASE)
    game.state = GameState.PLAYING
    game.start_time = time.time()
    game.last_activity = time.time()
    
    # 设置游戏超时
    game.timeout_task = asyncio.create_task(game_timeout(bot, group_id))
    
    difficulty_stars = "⭐" * game.current_story.difficulty
    await start_story.finish(
        f"🎭 海龟汤开始！\n\n"
        f"📖 题目：{game.current_story.title}\n"
        f"📝 情景：{game.current_story.scenario}\n\n"
        f"🤔 请玩家们提问来推理出真相！\n"
        f"🤖 出题者：智能机器人\n"
        f"📊 难度：{difficulty_stars} ({game.current_story.difficulty}/5)\n"
        f"🏷️ 分类：{game.current_story.category}\n"
        f"⏰ 游戏时长：{game.game_duration // 60}分钟\n"
        f"🔍 发送【提示】获取提示（限{game.max_hints}次）\n"
        f"🔄 发送【换题】更换题目"
    )

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
    
    difficulty_stars = "⭐" * game.current_story.difficulty
    await change_story.finish(
        f"🔄 题目已更换！\n\n"
        f"📖 新题目：{game.current_story.title}\n"
        f"📝 情景：{game.current_story.scenario}\n\n"
        f"📊 难度：{difficulty_stars} ({game.current_story.difficulty}/5)\n"
        f"🏷️ 分类：{game.current_story.category}\n"
        f"🤔 请继续提问推理真相！\n"
        f"💡 提示次数已重置：0/{game.max_hints}"
    )

@question_handler.handle()
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
    
    # 过滤命令和特殊消息
    if message.startswith(('/', '!', '。', '！', '？')) or len(message) < 2:
        return
    
    # 过滤常见的非游戏消息
    filter_words = ['哈哈', '呵呵', '嗯嗯', '好的', '知道了', '明白', '收到']
    if any(word in message for word in filter_words) and len(message) < 5:
        return
    
    player = game.players[user_id]
    print(11111, nlp_processor.is_guess(message))
    # 检查是否是猜测答案
    if nlp_processor.is_guess(message):
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
    answer = nlp_processor.generate_answer(message, game.current_story)
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
        message=f"❓ {player.nickname}：{message}\n"
               f"{response_emoji} 机器人：{answer}"
    )

async def handle_guess_attempt(bot: Bot, event: GroupMessageEvent, game: TurtleSoupGame, message: str):
    """处理猜测答案"""
    user_id = str(event.user_id)
    player = game.players[user_id]
    
    # 提取猜测内容
    guess_content = message
    for keyword in nlp_processor.guess_keywords:
        if keyword in message:
            guess_content = message.split(keyword, 1)[-1].strip()
            break
    
    # 使用改进的真相判断
    if nlp_processor.is_truth_guess(guess_content, game.current_story.truth):
        # 猜对了！
        await handle_guess_success(bot, game, player)
    else:
        # 猜错了
        await bot.send_group_msg(
            group_id=int(game.group_id),
            message=f"❌ {player.nickname} 的猜测不正确，请继续提问推理！\n"
                   f"💭 猜测内容：{guess_content}"
        )

async def handle_guess_success(bot: Bot, game: TurtleSoupGame, player: Player):
    """处理猜测成功"""
    game.solved = True
    game.state = GameState.FINISHED
    player.correct_guesses += 1
    
    # 取消超时任务
    if game.timeout_task:
        game.timeout_task.cancel()
    
    # 计算奖励分数
    base_score = 100
    time_bonus = max(0, 50 - int((time.time() - game.start_time) / 60) * 2)
    question_penalty = min(30, player.questions_asked * 1)
    difficulty_bonus = game.current_story.difficulty * 10
    final_score = base_score + time_bonus - question_penalty + difficulty_bonus
    
    await update_player_score(player.user_id, game.group_id, final_score, 'turtle_soup', None, 'win')
    
    # 游戏时长
    game_duration = int((time.time() - game.start_time) / 60)
    
    await bot.send_group_msg(
        group_id=int(game.group_id),
        message=f"🎉 恭喜 {player.nickname} 猜对了！\n\n"
               f"💡 真相：{game.current_story.truth}\n\n"
               f"🏆 获得分数：{final_score}\n"
               f"📊 分数构成：\n"
               f"   • 基础分：{base_score}\n"
               f"   • 时间奖励：+{time_bonus}\n"
               f"   • 提问惩罚：-{question_penalty}\n"
               f"   • 难度奖励：+{difficulty_bonus}\n"
               f"⏰ 用时：{game_duration}分钟\n"
               f"❓ 提问次数：{player.questions_asked}\n"
               f"🏷️ 题目分类：{game.current_story.category}"
    )
    
    # 立即清理游戏数据
    del games[game.group_id]

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
        status_msg = f"📋 游戏状态：报名中\n👥 玩家数量：{len(game.players)}"
    elif game.state == GameState.PLAYING:
        elapsed = int((time.time() - game.start_time) / 60)
        remaining = max(0, game.game_duration // 60 - elapsed)
        difficulty_stars = "⭐" * game.current_story.difficulty
        status_msg = (
            f"🎮 游戏状态：进行中\n"
            f"📖 题目：{game.current_story.title}\n"
            f"📊 难度：{difficulty_stars} ({game.current_story.difficulty}/5)\n"
            f"🏷️ 分类：{game.current_story.category}\n"
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
        "• 可以使用【提示】获取提示\n"
        "• 可以使用【换题】更换题目\n\n"
        "🏆 计分规则：\n"
        "• 参与游戏：+5分\n"
        "• 猜对真相：+100分+时间奖励-提问惩罚+难度奖励\n"
        "• 时间奖励：每分钟-5分\n"
        "• 提问惩罚：每次提问-2分\n"
        "• 难度奖励：难度星级×10分\n\n"
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
    
    # 立即清理游戏数据
    del games[group_id]
    await end_game.finish(summary)

async def game_timeout(bot: Bot, group_id: str):
    """游戏超时处理"""
    try:
        # 在开始时就获取游戏时长，避免后续访问已删除的游戏
        if group_id not in games:
            return
        
        game_duration = games[group_id].game_duration
        await asyncio.sleep(game_duration)
        
        # 检查游戏是否仍然存在且正在进行
        if group_id in games and games[group_id].state == GameState.PLAYING:
            game = games[group_id]
            game.state = GameState.FINISHED
            
            await bot.send_group_msg(
                group_id=int(group_id),
                message=f"⏰ 游戏时间到！\n\n💡 真相：{game.current_story.truth}"
            )
            # 立即清理游戏数据
            del games[group_id]
    except asyncio.CancelledError:
        pass
    except KeyError:
        # 游戏已被删除，静默处理
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