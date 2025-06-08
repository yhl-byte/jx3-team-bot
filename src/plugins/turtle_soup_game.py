import asyncio
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from nonebot import on_regex, on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.message import Message
from nonebot.matcher import Matcher
from nonebot.params import RegexGroup
from nonebot.rule import to_me

# 游戏状态枚举
class GameState(Enum):
    IDLE = "idle"  # 空闲状态
    REGISTERING = "registering"  # 报名阶段
    SELECTING_HOST = "selecting_host"  # 选择主持人阶段
    TOPIC_CONFIRMATION = "topic_confirmation"  # 确认题目阶段
    PLAYING = "playing"  # 游戏进行中
    FINISHED = "finished"  # 游戏结束

# 玩家数据结构
@dataclass
class Player:
    user_id: str
    nickname: str
    score: int = 0
    questions_asked: int = 0
    is_host: bool = False
    join_time: float = field(default_factory=time.time)

# 题目数据结构
@dataclass
class Story:
    title: str
    description: str
    truth: str
    keywords: List[str]
    difficulty: int = 1
    category: str = "推理"

# 游戏实例
@dataclass
class TurtleSoupGame:
    group_id: str
    state: GameState = GameState.IDLE
    players: Dict[str, Player] = field(default_factory=dict)
    host_candidates: Set[str] = field(default_factory=set)
    current_story: Optional[Story] = None
    host_id: Optional[str] = None
    start_time: Optional[float] = None
    game_start_time: Optional[float] = None
    host_hints_used: int = 0
    max_hints: int = 3
    host_base_score: int = 20
    hint_penalty: int = 5
    max_player_score: int = 10
    registration_end_time: Optional[float] = None
    host_selection_end_time: Optional[float] = None
    topic_confirmation_end_time: Optional[float] = None
    
    def reset(self):
        """重置游戏状态"""
        self.state = GameState.IDLE
        self.players.clear()
        self.host_candidates.clear()
        self.current_story = None
        self.host_id = None
        self.start_time = None
        self.game_start_time = None
        self.host_hints_used = 0
        self.registration_end_time = None
        self.host_selection_end_time = None
        self.topic_confirmation_end_time = None

# 全局游戏实例存储
games: Dict[str, TurtleSoupGame] = {}

# 海龟汤题库
STORIES = [
    Story(
        title="电梯惊魂",
        description="一个男人住在20楼，每天上班时都坐电梯到1楼，下班回来时坐电梯到10楼然后走楼梯回家。但是雨天时，他会直接坐电梯到20楼。为什么？",
        truth="因为这个男人是侏儒，够不到20楼的按钮，只能按到10楼的按钮。雨天时他有雨伞，可以用雨伞按到20楼的按钮。",
        keywords=["侏儒", "矮", "身高", "按钮", "够不到", "雨伞", "工具"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="半夜敲门",
        description="一个女人半夜听到敲门声，透过猫眼看到一个男人说：'对不起，我走错了。'女人立刻报警了。为什么？",
        truth="因为如果真的走错了，那个男人应该是背对着门离开的，而不是面对着门说话。面对着门说话说明他知道里面有人，很可能是想骗开门。",
        keywords=["背对", "面对", "门", "方向", "骗", "走错", "猫眼"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="草地上的尸体",
        description="在一片草地中央发现了一具男尸，死者身边没有任何凶器，但身上有一个包。警察判断这是自杀。为什么？",
        truth="死者是跳伞时降落伞没有打开摔死的，包里装的是没有打开的降落伞。",
        keywords=["跳伞", "降落伞", "没打开", "摔死", "高空", "包"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="水中的女人",
        description="一个女人在水中死亡，身边有很多碎玻璃，但她不是被玻璃割死的，也不是溺水而死。她是怎么死的？",
        truth="女人是在鱼缸里的金鱼，鱼缸被打破了，金鱼缺水而死。",
        keywords=["金鱼", "鱼缸", "缺水", "打破", "动物", "宠物"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="满身是血的男人",
        description="一个男人满身是血地从房间里走出来，但他没有受伤，房间里也没有其他人。这是怎么回事？",
        truth="这个男人是医生或兽医，刚刚完成了一台手术。",
        keywords=["医生", "兽医", "手术", "血", "工作", "职业"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="绿衣服的男人",
        description="一个穿绿衣服的男人走进咖啡厅，点了一杯咖啡。喝了一口后立刻死了。咖啡没有毒，他也没有过敏。为什么？",
        truth="这个男人是色盲，分不清红绿灯，穿绿衣服是为了让别人提醒他。但在咖啡厅里没人提醒，他意识到自己闯了红灯，心脏病发作而死。",
        keywords=["色盲", "红绿灯", "心脏病", "闯红灯", "提醒", "绿衣服"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="镜子里的男人",
        description="一个男人每天早上都要照镜子，但有一天他照镜子时吓死了。镜子没有坏，他的样子也没有变化。为什么？",
        truth="这个男人是吸血鬼，镜子里看不到自己的影像。那天他忘记了自己是吸血鬼，看到镜子里没有自己被吓死了。",
        keywords=["吸血鬼", "影像", "反射", "忘记", "身份", "超自然"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="电话亭里的死人",
        description="一个男人在电话亭里被发现死亡，电话亭的玻璃全部破碎，地上有很多水。他不是被玻璃割死的，也不是溺水。怎么死的？",
        truth="电话亭在海边，涨潮时海水淹没了电话亭，男人被困在里面，因为水压太大无法推开门，最后窒息而死。",
        keywords=["海边", "涨潮", "海水", "水压", "窒息", "困住", "推不开"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="餐厅悲剧",
        description="一个男人在餐厅点了海鸥肉，吃了一口就哭了，然后自杀了。为什么？",
        truth="这个男人曾经在海上遇难，同伴告诉他吃的是海鸥肉才活下来。现在他发现真正的海鸥肉味道不是这样的，意识到当时吃的是同伴的肉。",
        keywords=["海难", "同伴", "人肉", "欺骗", "真相"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="雨夜归人1",
        description="一个男人雨夜开车回家，看到路边有三个人在等车：一个是快死的老人，一个是救过他命的医生，一个是他的梦中情人。车只能坐一个人，他应该载谁？",
        truth="他把车钥匙给医生，让医生载老人去医院，自己陪梦中情人等下一班车。",
        keywords=["车钥匙", "医生", "老人", "医院", "陪伴"],
        difficulty=3,
        category="智力"
    ),
    Story(
        title="雨夜归人2",
        description="一个女人雨夜回家，发现门口有一双湿鞋。她立刻报警了。为什么？",
        truth="因为她独居，而且刚从外面回来，门口不应该有其他人的鞋子，说明有人进入了她的家。",
        keywords=["独居", "湿鞋", "入侵", "危险", "陌生人"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="沙漠死亡",
        description="一个男人在沙漠中死去，身体有一个包裹，包裹没有打开。救援队发现他时，发现如果他打开包裹，就不会死。包裹里是什么？",
        truth="包裹里是降落伞。这个男人是跳伞时降落伞没有打开而摔死的，不是在沙漠中渴死的。",
        keywords=["降落伞", "跳伞", "摔死", "没打开"],
        difficulty=2,
        category="经典"
    ),
    Story(
        title="镜子之谜",
        description="一个女人每天早上照镜子都会哭，但她的容貌很美丽，身体也很健康。为什么她会哭？",
        truth="因为她是盲人，每天照镜子是为了确认自己还活着，但她永远看不到自己的样子，所以会哭。",
        keywords=["盲人", "看不到", "确认", "活着", "永远"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="完美的犯罪",
        description="一个男人杀死了他的妻子，警察来调查时，他正在做饭。警察没有发现任何证据，但还是逮捕了他。为什么？",
        truth="因为他在做饭时用的是妻子的肉。警察发现他做的菜里有人肉。",
        keywords=["人肉", "做饭", "妻子", "证据", "发现"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="时间停止",
        description="一个男人看了一眼手表后就死了，但手表没有任何毒性或危险。为什么？",
        truth="因为他是潜水员，看手表发现氧气即将耗尽，但已经来不及上浮，最终窒息而死。",
        keywords=["潜水员", "氧气", "耗尽", "上浮", "窒息"],
        difficulty=3,
        category="悬疑"
    ),
    Story(
        title="无声的呼救1",
        description="一个女人在电话里说'我很好，一切都很正常'，但接电话的人立即报警了。为什么？",
        truth="因为这个女人是哑巴，她不可能说话。有人在威胁她，强迫她说这些话。",
        keywords=["哑巴", "不能说话", "威胁", "强迫", "危险"],
        difficulty=2,
        category="悬疑"
    ),
    Story(
        title="无声的呼救2",
        description="一个哑巴在火灾中被困，但他没有呼救，最后被救出时已经死了。为什么？",
        truth="他不是被火烧死的，而是被浓烟窒息而死。哑巴无法呼救，但可以敲击求救，他没有这样做是因为已经昏迷了。",
        keywords=["哑巴", "火灾", "窒息", "浓烟", "昏迷"],
        difficulty=2,
        category="推理"
    ),
    Story(
        title="最后的晚餐",
        description="一个男人在餐厅吃完最后一口饭后就死了，但食物没有毒，他也没有噎到。为什么？",
        truth="因为他是死刑犯，这是他的最后一餐。吃完后就被执行死刑了。",
        keywords=["死刑犯", "最后一餐", "执行", "死刑", "监狱"],
        difficulty=2,
        category="悲伤"
    ),
    Story(
        title="黑暗中的真相",
        description="一个男人在完全黑暗的房间里，没有任何光源，但他知道房间里有一个死人。他是怎么知道的？",
        truth="因为他闻到了尸体腐烂的味道。",
        keywords=["尸体", "腐烂", "味道", "嗅觉", "死亡"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="生日礼物",
        description="一个女孩收到生日礼物后立即自杀了，礼物是一个很普通的音乐盒。为什么？",
        truth="因为音乐盒播放的是她死去母亲最喜欢的歌，这让她想起了痛苦回忆，无法承受而自杀。",
        keywords=["音乐盒", "母亲", "死去", "回忆", "痛苦"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="雪夜追踪",
        description="警察在雪地里追踪一个罪犯，发现脚印突然消失了，但周围没有任何可以隐藏的地方。罪犯去哪了？",
        truth="罪犯倒着走，脚印看起来像是朝相反方向的，警察追错了方向。",
        keywords=["倒着走", "脚印", "相反", "方向", "欺骗"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="无头骑士",
        description="一个骑士骑马经过一座桥，桥的另一端有人看到他没有头。但骑士本人并没有死。这是怎么回事？",
        truth="因为桥很低，骑士为了通过桥而低头，从另一端看起来就像没有头一样。",
        keywords=["低头", "桥", "很低", "通过", "视觉"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="医生的诊断",
        description="一个医生看了病人一眼就说他会在午夜死去，结果真的应验了。医生是怎么知道的？",
        truth="因为病人是医生的仇人，医生计划在午夜杀死他。",
        keywords=["仇人", "计划", "杀死", "预谋", "报复"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="消失的新娘",
        description="一个新娘在婚礼当天消失了，一年后在她的婚纱里发现了她的尸体。她是怎么死的？",
        truth="她在玩捉迷藏时躲进了一个古老的箱子里，箱子自动锁上了，她被困死在里面。",
        keywords=["捉迷藏", "箱子", "锁上", "困死", "窒息"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="画家的杰作",
        description="一个画家画了一幅自画像，画完后就自杀了。但这幅画看起来很普通，没有任何特殊之处。为什么他要自杀？",
        truth="因为画家是盲人，他画的自画像其实是一片空白，这让他意识到自己永远无法看到自己的作品。",
        keywords=["盲人", "空白", "看不到", "作品", "绝望"],
        difficulty=4,
        category="悲伤"
    ),
    Story(
        title="深夜来电",
        description="一个男人深夜接到电话，对方什么都没说就挂了。第二天他就死了。为什么？",
        truth="因为他是盲人，靠听声音辨别方向。电话铃声让他误以为是门铃，走向门口时从楼梯上摔下来死了。",
        keywords=["盲人", "听声音", "门铃", "楼梯", "摔死"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="完美的谎言",
        description="一个女人告诉警察她的丈夫是自杀的，警察相信了。但实际上她是kill死了丈夫。她是怎么做到的？",
        truth="她在丈夫睡觉时在他手上绑了一块冰，冰融化后绳子松开，看起来像是自己开枪自杀。",
        keywords=["冰", "融化", "绳子", "开枪", "伪装"],
        difficulty=4,
        category="犯罪"
    ),
    Story(
        title="孤岛求生",
        description="一个男人被困在孤岛上，岛上有充足的食物和水，但他还是死了。为什么？",
        truth="因为他看到远处有船经过，生起火堆求救，但风向改变，烟雾遮挡了他的视线，他没看到船已经改变航向来救他，绝望中自杀了。",
        keywords=["求救", "火堆", "烟雾", "船", "绝望"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="魔术师的秘密",
        description="一个魔术师在表演中真的消失了，观众以为是魔术，但他再也没有出现。他去哪了？",
        truth="他掉进了舞台下的陷阱里，被机关夹死了。观众以为这是魔术的一部分。",
        keywords=["陷阱", "机关", "夹死", "舞台", "意外"],
        difficulty=2,
        category="悬疑"
    ),
    Story(
        title="记忆碎片",
        description="一个男人失忆了，医生告诉他可以恢复记忆，但他拒绝了。为什么？",
        truth="因为他是杀人犯，失忆让他忘记了自己的罪行，他不想记起这些痛苦的事情。",
        keywords=["杀人犯", "罪行", "忘记", "痛苦", "逃避"],
        difficulty=3,
        category="心理"
    ),
    Story(
        title="最后的电话",
        description="一个女人给她的朋友打电话说'我要死了'，朋友以为她在开玩笑。第二天女人真的死了。为什么朋友不相信？",
        truth="因为女人经常开这种玩笑，朋友已经习惯了。但这次她是认真的，她患了绝症。",
        keywords=["开玩笑", "习惯", "绝症", "认真", "误解"],
        difficulty=2,
        category="悲伤"
    ),
    Story(
        title="双胞胎之谜",
        description="一对双胞胎兄弟，哥哥杀死了弟弟，但警察无法逮捕他。为什么？",
        truth="因为他们是连体双胞胎，逮捕哥哥就等于杀死他，这在法律上是不被允许的。",
        keywords=["连体", "双胞胎", "法律", "不允许", "困境"],
        difficulty=4,
        category="法律"
    ),
    Story(
        title="沉默的证人",
        description="一个哑巴目击了一起谋杀案，但他无法告诉警察凶手是谁。最后凶手还是被抓住了。为什么？",
        truth="因为哑巴用手语描述了凶手的特征，警察找了手语翻译员。",
        keywords=["手语", "描述", "特征", "翻译员", "沟通"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="时光倒流",
        description="一个男人声称他能预知未来，并准确预测了几起事件。但实际上他不能预知未来。他是怎么做到的？",
        truth="因为他是时间旅行者，从未来回到了过去，所以知道将要发生的事情。",
        keywords=["时间旅行", "未来", "过去", "知道", "科幻"],
        difficulty=5,
        category="科幻"
    ),
    Story(
        title="无声的音乐",
        description="一个聋人在音乐会上哭了，但他听不到任何声音。为什么他会哭？",
        truth="因为他通过振动感受音乐，想起了失去听力前最喜欢的歌曲。",
        keywords=["聋人", "振动", "感受", "失去", "回忆"],
        difficulty=2,
        category="感人"
    ),
    Story(
        title="完美的复仇",
        description="一个男人花了十年时间策划复仇，但在复仇成功的那一刻，但他却原谅了仇人。为什么？",
        truth="因为他发现仇人已经失明了，和他一样成了残疾人，他觉得仇人已经受到了足够的惩罚。",
        keywords=["失明", "残疾", "惩罚", "足够", "同情"],
        difficulty=3,
        category="感人"
    ),
    Story(
        title="神秘的房间",
        description="一个房间里有一个死人，房间从内部锁着，没有其他出入口，也没有自杀的工具。他是怎么死的？",
        truth="他是被冰锥杀死的，冰锥融化后消失了，所以找不到凶器。",
        keywords=["冰锥", "融化", "消失", "凶器", "密室"],
        difficulty=4,
        category="推理"
    ),
    Story(
        title="最后的愿望",
        description="一个即将死去的老人最后的愿望是吃一个苹果，家人给了他苹果，但他吃了一口就死了。苹果没有毒。为什么？",
        truth="因为老人没有牙齿，苹果太硬了，他被噎死了。",
        keywords=["没有牙齿", "太硬", "噎死", "老人", "意外"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="雨中的秘密",
        description="一个男人在雨中走路，但他没有被雨淋湿。他没有雨伞，也没有躲在任何地方。为什么？",
        truth="因为他是秃头，雨水直接从他的头上滑落，没有被头发吸收。",
        keywords=["秃头", "滑落", "头发", "吸收", "光滑"],
        difficulty=1,
        category="简单"
    ),
    Story(
        title="永恒的等待",
        description="一个女人在车站等了一个人50年，但那个人永远不会来了。她为什么还在等？",
        truth="因为她患了阿尔茨海默病，每天都忘记那个人已经死了，重新开始等待。",
        keywords=["阿尔茨海默", "忘记", "死了", "重新", "疾病"],
        difficulty=3,
        category="悲伤"
    ),
    Story(
        title="数字的诅咒",
        description="一个数学家看到数字13就会死，但13只是一个普通的数字。为什么？",
        truth="因为他有严重的恐惧症，看到13就会心脏病发作。",
        keywords=["恐惧症", "心脏病", "发作", "心理", "疾病"],
        difficulty=2,
        category="心理"
    ),
    Story(
        title="影子的秘密",
        description="一个男人害怕自己的影子，每当看到影子就会尖叫。为什么？",
        truth="因为他的影子里隐藏着他杀死的人的灵魂，只有他能看到。",
        keywords=["灵魂", "杀死", "隐藏", "看到", "超自然"],
        difficulty=4,
        category="超自然"
    ),
    Story(
        title="最后的舞蹈",
        description="一个舞蹈家在舞台上跳完最后一支舞后就死了，但她没有生病，也没有受伤。为什么？",
        truth="因为她跳的是死亡之舞，这是她为自己准备的葬礼舞蹈，跳完后服毒自杀了。",
        keywords=["死亡之舞", "葬礼", "服毒", "自杀", "仪式"],
        difficulty=4,
        category="艺术"
    ),
    Story(
        title="无声的呐喊",
        description="一个男人在梦中大声呼救，但现实中他一点声音都没有发出。为什么没人救他？",
        truth="因为他被活埋了，在棺材里窒息而死，人们以为他已经死了。",
        keywords=["活埋", "棺材", "窒息", "死了", "误判"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="记忆的重量",
        description="一个男人每次想起某个记忆就会变重一点，最后被压死了。这是怎么回事？",
        truth="他每次想起杀死的人就会在身上放一块石头，最后被石头压死了，这是他的自我惩罚。",
        keywords=["石头", "压死", "自我惩罚", "杀死", "负罪感"],
        difficulty=4,
        category="心理"
    ),
    Story(
        title="光明与黑暗",
        description="一个盲人重见光明后立即自杀了。为什么？",
        truth="因为他看到了自己杀死的人的尸体就在边，原来他一直和尸体生活在一起。",
        keywords=["重见光明", "尸体", "边", "一直", "恐怖"],
        difficulty=5,
        category="恐怖"
    ),
    Story(
        title="时间的礼物",
        description="一个男人收到了一块停止的手表作为礼物，他看了一眼就知道自己会在什么时候死。为什么？",
        truth="因为手表停在了他出生的时间，这意味着他的生命即将结束，回到起点。",
        keywords=["停止", "出生时间", "生命", "结束", "起点"],
        difficulty=4,
        category="哲学"
    ),
    Story(
        title="最后的笑容",
        description="一个小丑摘下面具后就死了，但面具没有毒性。为什么？",
        truth="因为面具下面是他腐烂的脸，他其实早就死了，是面具让他看起来还活着。",
        keywords=["腐烂", "早就死了", "面具", "活着", "假象"],
        difficulty=5,
        category="超自然"
    ),
    Story(
        title="声音的陷阱",
        description="一个音乐家听到了世界上最美的音乐，然后就死了。音乐没有任何危险。为什么？",
        truth="因为那是天堂的音乐，只有死人才能听到，他听到音乐说明他已经死了。",
        keywords=["天堂", "音乐", "死人", "听到", "已经死了"],
        difficulty=4,
        category="超自然"
    ),
    Story(
        title="永恒的惩罚",
        description="一个男人被判处永生，但他认为这是最残酷的惩罚。为什么？",
        truth="因为他必须永远活着看着自己所爱的人一个个死去，承受无尽的痛苦。",
        keywords=["永生", "所爱的人", "死去", "无尽", "痛苦"],
        difficulty=3,
        category="哲学"
    ),
    Story(
        title="镜中世界",
        description="一个女人看着镜子，镜子里的自己做了不同的动作。她没有疯，镜子也没有坏。为什么？",
        truth="因为镜子里是她的双胞胎姐妹，她们长得一模一样，姐妹在镜子后面模仿她。",
        keywords=["双胞胎", "姐妹", "一模一样", "后面", "模仿"],
        difficulty=2,
        category="智力"
    ),
    Story(
        title="最后的晚餐",
        description="一群人在荒岛上，食物只够一个人吃。他们决定抽签决定谁能活下来，但最后所有人都死了。为什么？",
        truth="因为他们抽签的纸条上都写着死，没有人想独自活下来承受孤独。",
        keywords=["抽签", "都写着死", "独自", "孤独", "不想"],
        difficulty=3,
        category="人性"
    ),
    Story(
        title="深夜访客",
        description="一个男人深夜听到敲门声，开门后发现是邻居，邻居说：'你的灯还亮着。'男人立刻关门报警。为什么？",
        truth="因为那个邻居已经死了很久了，不可能来敲门。这可能是有人冒充邻居想要进入他的家。",
        keywords=["邻居", "死人", "冒充", "深夜", "危险"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="照片的秘密",
        description="一个女人看到自己的照片后立刻逃跑了。照片没有被修改过，她的样子也没有变化。为什么？",
        truth="照片是在她不知情的情况下被偷拍的，说明有人在跟踪她，她意识到自己处于危险中。",
        keywords=["偷拍", "跟踪", "危险", "逃跑", "监视"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="电梯里的陌生人",
        description="一个女人进电梯时看到里面有个男人，她立刻退出来等下一班。为什么？",
        truth="那个男人按了所有楼层的按钮，这是绑架犯常用的手段，为了延长在电梯里的时间。",
        keywords=["电梯", "按钮", "绑架", "手段", "危险"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="停车场惊魂",
        description="一个女人在停车场发现自己车上有张纸条，看了后立刻报警。纸条上写着'你的车很漂亮'。为什么？",
        truth="纸条放在雨刷下面，但今天没有下雨，说明有人故意放的。这可能是跟踪者留下的信号。",
        keywords=["纸条", "雨刷", "跟踪", "信号", "危险"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="婴儿的哭声",
        description="一个女人深夜听到门外有婴儿哭声，但她没有开门。第二天发现门口有血迹。为什么？",
        truth="这是犯罪分子的陷阱，用录音模拟婴儿哭声引人开门。血迹可能是其他受害者留下的。",
        keywords=["婴儿", "哭声", "陷阱", "录音", "血迹"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="消失的室友",
        description="一个女大学生发现室友三天没回来，但室友的东西都在，手机也在充电。为什么她很担心？",
        truth="因为室友从来不会不带手机出门，而且她的钱包和钥匙也都在，说明她可能遇到了意外。",
        keywords=["室友", "失踪", "手机", "钱包", "意外"],
        difficulty=2,
        category="推理"
    ),
    Story(
        title="地下室的声音",
        description="一个男人搬进新房子后，每晚都听到地下室有奇怪的声音。他报警了。为什么？",
        truth="因为这房子没有地下室，声音可能来自被困在墙壁或地板下的人。",
        keywords=["地下室", "声音", "被困", "墙壁", "救援"],
        difficulty=4,
        category="恐怖"
    ),
    Story(
        title="ATM机前的男人",
        description="一个女人在ATM机前看到一个男人一直在按键但没有取钱，她立刻离开了。为什么？",
        truth="那个男人可能在ATM机上安装了读卡器，假装使用ATM来掩盖自己的行为。",
        keywords=["ATM", "读卡器", "诈骗", "盗刷", "犯罪"],
        difficulty=3,
        category="推理"
    ),
    Story(
        title="公交车上的座位",
        description="一个女人上公交车时发现只有最后一排有空座，但她宁愿站着。为什么？",
        truth="因为最后一排坐着几个可疑的男人，他们一直在盯着她看，她感觉不安全。",
        keywords=["公交车", "可疑", "盯着", "不安全", "直觉"],
        difficulty=2,
        category="推理"
    ),
    Story(
        title="网购的包裹",
        description="一个女人收到一个她没有订购的包裹，里面是一件衣服。她立刻报警了。为什么？",
        truth="这可能是跟踪狂寄来的，说明对方知道她的地址、尺码等个人信息，她处于被监视的危险中。",
        keywords=["包裹", "跟踪狂", "个人信息", "监视", "危险"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="咖啡店的陌生人",
        description="一个女人在咖啡店里发现有个男人一直在看她，她换了三次座位，那个男人也跟着换。她报警了。为什么？",
        truth="这明显是跟踪行为，那个男人可能是跟踪狂或者有其他恶意企图。",
        keywords=["跟踪", "换座位", "恶意", "跟踪狂", "危险"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="酒店房间的发现",
        description="一个女人入住酒店后发现床下有个手机在录像，她立刻报警。这是为什么？",
        truth="有人在房间里安装了偷拍设备，这是严重的隐私侵犯和犯罪行为。",
        keywords=["酒店", "偷拍", "录像", "隐私", "犯罪"],
        difficulty=1,
        category="恐怖"
    ),
    Story(
        title="电话里的呼吸声",
        description="一个女人接电话时只听到呼吸声，没有人说话。这种情况持续了一周。她报警了。为什么？",
        truth="这是骚扰电话的一种形式，可能是跟踪狂或者有恶意的人在试探她的作息时间。",
        keywords=["骚扰电话", "呼吸声", "跟踪", "作息", "恶意"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="社交媒体的点赞",
        description="一个女人发现有人给她三年前的照片点赞，她立刻删除了所有社交媒体账号。为什么？",
        truth="有人在翻看她的历史记录，这可能是跟踪行为的开始，她感到了威胁。",
        keywords=["社交媒体", "历史记录", "跟踪", "威胁", "删除"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="出租车司机",
        description="一个女人上出租车后发现司机把中控锁锁上了，她立刻要求下车。为什么？",
        truth="锁上中控锁意味着她无法自己开门逃脱，这可能是绑架的前兆。",
        keywords=["出租车", "中控锁", "绑架", "逃脱", "危险"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="快递员的异常",
        description="一个女人发现快递员总是在她下班时间准时出现，她开始怀疑。为什么？",
        truth="真正的快递员不会这么准确地掌握她的作息时间，这个人可能是冒充的，在监视她。",
        keywords=["快递员", "作息时间", "冒充", "监视", "怀疑"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="健身房的跟随",
        description="一个女人在健身房发现总有个男人在她附近锻炼，她换器械他也换。她报告了教练。为什么？",
        truth="这是明显的跟踪行为，那个男人可能有不良企图，在健身房这种相对私密的环境中更加危险。",
        keywords=["健身房", "跟踪", "换器械", "不良企图", "危险"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="邻居的关心",
        description="一个女人的新邻居总是问她什么时候上班下班，她觉得不对劲。为什么？",
        truth="正常的邻居不会这么详细地询问作息时间，这可能是在踩点，准备实施犯罪。",
        keywords=["邻居", "作息时间", "踩点", "犯罪", "不对劲"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="修理工的借口",
        description="一个男人说是来修水管的，但女主人没有报修。她没有开门。为什么？",
        truth="这是入室抢劫犯常用的借口，冒充修理工来试探家里是否有人，然后实施犯罪。",
        keywords=["修理工", "借口", "入室抢劫", "冒充", "犯罪"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="超市里的跟踪",
        description="一个女人在超市购物时发现有个男人一直跟着她，她故意绕了几圈，那个男人还在跟着。她求助了保安。为什么？",
        truth="这是明显的跟踪行为，那个男人可能想要了解她的购物习惯或者等她到停车场时实施犯罪。",
        keywords=["超市", "跟踪", "购物习惯", "停车场", "犯罪"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="陌生人的帮助",
        description="一个女人的车胎爆了，有个男人主动来帮忙。她拒绝了并叫了拖车。为什么？",
        truth="在偏僻的地方，陌生人的主动帮助可能是陷阱，她选择更安全的方式求助。",
        keywords=["车胎", "陌生人", "帮助", "陷阱", "安全"],
        difficulty=2,
        category="推理"
    ),
    Story(
        title="电梯里的镜子",
        description="一个女人进电梯时注意到镜子里有个男人在她身后做手势，她立刻按了紧急按钮。为什么？",
        truth="那个男人可能在向外面的同伙发信号，准备在电梯里或者她出电梯时实施犯罪。",
        keywords=["电梯", "镜子", "手势", "同伙", "信号"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="深夜的敲门声",
        description="一个女人深夜听到敲门声，声音很轻很有节奏。她没有开门并报了警。为什么？",
        truth="正常人深夜敲门会比较急促，轻而有节奏的敲门可能是在试探家里是否有人，这是踩点行为。",
        keywords=["深夜", "敲门声", "节奏", "试探", "踩点"],
        difficulty=3,
        category="恐怖"
    ),
    Story(
        title="公园里的摄影师",
        description="一个女人在公园里发现有人在拍她，她上前质问，那人说在拍风景。她还是报警了。为什么？",
        truth="如果真的在拍风景，相机镜头不会一直对着她。这可能是偷拍行为或者跟踪的开始。",
        keywords=["公园", "摄影师", "偷拍", "风景", "跟踪"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="网约车的路线",
        description="一个女人发现网约车司机没有按照导航走，而是走了一条偏僻的路。她立刻下车了。为什么？",
        truth="司机故意走偏僻路线可能有恶意企图，比如绑架或抢劫，她及时察觉并脱离了危险。",
        keywords=["网约车", "路线", "偏僻", "恶意", "绑架"],
        difficulty=2,
        category="恐怖"
    ),
    Story(
        title="图书馆的窥视",
        description="一个女学生在图书馆学习时发现有个男人一直在看她，她换了几次座位都是如此。她告诉了管理员。为什么？",
        truth="这是跟踪和骚扰行为，在图书馆这种安静的环境中，持续的注视会让人感到威胁和不安。",
        keywords=["图书馆", "窥视", "换座位", "骚扰", "威胁"],
        difficulty=2,
        category="恐怖"
    )
]

# 工具函数
def get_game(group_id: str) -> TurtleSoupGame:
    """获取或创建游戏实例"""
    if group_id not in games:
        games[group_id] = TurtleSoupGame(group_id=group_id)
    return games[group_id]

def is_truth_match(guess: str, story: Story) -> bool:
    """检查猜测是否匹配真相"""
    guess_lower = guess.lower().strip()
    truth_lower = story.truth.lower()
    
    # 直接文本匹配（去除标点符号）
    import re
    guess_clean = re.sub(r'[^\w\s]', '', guess_lower)
    truth_clean = re.sub(r'[^\w\s]', '', truth_lower)
    
    # 如果猜测包含真相的主要内容
    if len(guess_clean) > 10 and guess_clean in truth_clean:
        return True
    
    # 关键词匹配 - 需要匹配大部分关键词
    matched_keywords = 0
    for keyword in story.keywords:
        if keyword.lower() in guess_lower:
            matched_keywords += 1
    
    # 如果匹配了超过一半的关键词，认为猜中
    return matched_keywords >= len(story.keywords) * 0.6

def calculate_time_bonus(game_duration: float) -> int:
    """根据游戏时长计算时间奖励"""
    if game_duration < 300:  # 5分钟内
        return 5
    elif game_duration < 600:  # 10分钟内
        return 3
    elif game_duration < 1200:  # 20分钟内
        return 1
    else:
        return 0

# 命令处理器
start_game = on_regex(pattern=r"^(开始海龟汤|海龟汤)$", priority=5)
register_game = on_regex(pattern=r"^(报名海龟汤|参加海龟汤|加入海龟汤)$", priority=5)
end_registration = on_regex(pattern=r"^结束海龟汤报名$", priority=5)
run_for_host = on_regex(pattern=r"^(竞选主持人|我要当主持人|主持人)$", priority=5)
change_topic = on_regex(pattern=r"^(换题|更换题目|换个题目)$", priority=5)
keep_topic = on_regex(pattern=r"^(不换|保持|就这个)$", priority=5)
hint_command = on_regex(pattern=r"^(提示|hint)$", priority=5)
end_game = on_regex(pattern=r"^强制结束海龟汤$", priority=5)
status_command = on_regex(pattern=r"^海龟汤状态$", priority=5)

# 消息处理器
message_handler = on_message()

@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    print("start_game")
    """开始游戏"""
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    if game.state != GameState.IDLE:
        await start_game.send("游戏已经在进行中了！")
        return
    
    game.reset()
    game.state = GameState.REGISTERING
    game.start_time = time.time()
    game.registration_end_time = time.time() + 300  # 300秒报名时间
    
    await start_game.send(
        "🐢 海龟汤游戏开始！\n"
        "📝 请在300秒内发送'报名海龟汤'参加游戏\n"
        "⏰ 报名时间：300秒"
    )
    
    # 60秒后自动结束报名
    await asyncio.sleep(300)
    if game.state == GameState.REGISTERING:
        await auto_end_registration(bot, group_id)

@register_game.handle()
async def handle_register(bot: Bot, event: GroupMessageEvent):
    """处理报名"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    game = get_game(group_id)
    
    if game.state != GameState.REGISTERING:
        return
    
    if user_id in game.players:
        await register_game.send("你已经报名了！")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('card') or user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    game.players[user_id] = Player(user_id=user_id, nickname=nickname)
    
    await register_game.send(f"✅ {nickname} 报名成功！当前报名人数：{len(game.players)}")

@end_registration.handle()
async def handle_end_registration(bot: Bot, event: GroupMessageEvent):
    """手动结束报名"""
    group_id = str(event.group_id)
    await auto_end_registration(bot, group_id)

async def auto_end_registration(bot: Bot, group_id: str):
    """自动结束报名"""
    game = get_game(group_id)
    
    if game.state != GameState.REGISTERING:
        return
    
    if len(game.players) < 2:
        await bot.send_group_msg(
            group_id=int(group_id),
            message="报名人数不足（至少需要2人），游戏取消。"
        )
        game.reset()
        return
    
    game.state = GameState.SELECTING_HOST
    game.host_selection_end_time = time.time() + 30  # 30秒选择主持人时间
    
    player_list = "\n".join([f"{i+1}. {player.nickname}" for i, player in enumerate(game.players.values())])
    
    await bot.send_group_msg(
        group_id=int(group_id),
        message=f"📋 报名结束！参与玩家：\n{player_list}\n\n"
                f"🎯 现在开始选择主持人\n"
                f"💡 发送'竞选主持人'参与竞选\n"
                f"⏰ 30秒后将从竞选者中随机选择（无竞选者则从所有玩家中随机选择）"
    )
    
    # 30秒后自动选择主持人
    await asyncio.sleep(30)
    if game.state == GameState.SELECTING_HOST:
        await auto_select_host(bot, group_id)

@run_for_host.handle()
async def handle_run_for_host(bot: Bot, event: GroupMessageEvent):
    """竞选主持人"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    game = get_game(group_id)
    
    if game.state != GameState.SELECTING_HOST:
        return
    
    if user_id not in game.players:
        await run_for_host.send("你还没有报名参加游戏！")
        return
    
    if user_id in game.host_candidates:
        await run_for_host.send("你已经竞选过了！")
        return
    
    game.host_candidates.add(user_id)
    player = game.players[user_id]
    
    await run_for_host.send(f"🎯 {player.nickname} 竞选主持人！当前竞选人数：{len(game.host_candidates)}")

async def auto_select_host(bot: Bot, group_id: str):
    """自动选择主持人"""
    game = get_game(group_id)
    
    if game.state != GameState.SELECTING_HOST:
        return
    
    # 从竞选者中选择，如果没有竞选者则从所有玩家中选择
    candidates = list(game.host_candidates) if game.host_candidates else list(game.players.keys())
    
    if not candidates:
        await bot.send_group_msg(
            group_id=int(group_id),
            message="没有可选的主持人，游戏取消。"
        )
        game.reset()
        return
    
    # 随机选择主持人
    game.host_id = random.choice(candidates)
    host = game.players[game.host_id]
    host.is_host = True
    
    # 随机选择题目
    game.current_story = random.choice(STORIES)
    
    # 发送题目给主持人
    try:
        await bot.send_private_msg(
            user_id=int(game.host_id),
            message=f"🎯 你被选为主持人！\n\n"
                   f"📖 题目：{game.current_story.title}\n"
                   f"📝 描述：{game.current_story.description}\n\n"
                   f"🔍 真相：{game.current_story.truth}\n\n"
                   f"🔑 关键词：{', '.join(game.current_story.keywords)}\n\n"
                   f"💡 你有{game.max_hints}次提示机会，超过后每次提示扣{game.hint_penalty}分\n"
                   f"🏆 基础分数：{game.host_base_score}分"
        )
    except:
        await bot.send_group_msg(
            group_id=int(group_id),
            message=f"无法私聊主持人 {host.nickname}，请确保机器人可以私聊你。游戏取消。"
        )
        game.reset()
        return
    
    # 在群里公布主持人和题目
    game.state = GameState.TOPIC_CONFIRMATION
    game.topic_confirmation_end_time = time.time() + 30  # 30秒确认时间
    
    await bot.send_group_msg(
        group_id=int(group_id),
        message=f"🎯 主持人：{host.nickname}\n\n"
               f"📖 题目：{game.current_story.title}\n"
               f"📝 {game.current_story.description}\n\n"
               f"❓ 是否换题？\n"
               f"💡 发送'换题'更换题目，发送'不换'开始游戏\n"
               f"⏰ 30秒后自动开始游戏"
    )
    
    # 30秒后自动开始游戏
    await asyncio.sleep(30)
    if game.state == GameState.TOPIC_CONFIRMATION:
        await start_playing(bot, group_id)

@change_topic.handle()
async def handle_change_topic(bot: Bot, event: GroupMessageEvent):
    """换题"""
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    if game.state != GameState.TOPIC_CONFIRMATION:
        return
    
    # 重新选择题目
    game.current_story = random.choice(STORIES)
    
    # 发送新题目给主持人
    try:
        await bot.send_private_msg(
            user_id=int(game.host_id),
            message=f"🔄 题目已更换！\n\n"
                   f"📖 新题目：{game.current_story.title}\n"
                   f"📝 描述：{game.current_story.description}\n\n"
                   f"🔍 真相：{game.current_story.truth}\n\n"
                   f"🔑 关键词：{', '.join(game.current_story.keywords)}"
        )
    except:
        pass
    
    # 在群里公布新题目
    await change_topic.send(
        f"🔄 题目已更换！\n\n"
        f"📖 新题目：{game.current_story.title}\n"
        f"📝 {game.current_story.description}\n\n"
        f"❓ 是否再次换题？\n"
        f"💡 发送'换题'继续更换，发送'不换'开始游戏"
    )

@keep_topic.handle()
async def handle_keep_topic(bot: Bot, event: GroupMessageEvent):
    """保持题目，开始游戏"""
    group_id = str(event.group_id)
    await start_playing(bot, group_id)

async def start_playing(bot: Bot, group_id: str):
    """开始游戏"""
    game = get_game(group_id)
    
    if game.state != GameState.TOPIC_CONFIRMATION:
        return
    
    game.state = GameState.PLAYING
    game.game_start_time = time.time()
    
    host = game.players[game.host_id]
    player_list = [p.nickname for p in game.players.values() if not p.is_host]
    
    await bot.send_group_msg(
        group_id=int(group_id),
        message=f"🎮 游戏开始！\n\n"
               f"🎯 主持人：{host.nickname}\n"
               f"👥 玩家：{', '.join(player_list)}\n\n"
               f"📖 题目：{game.current_story.title}\n"
               f"📝 {game.current_story.description}\n\n"
               f"💡 规则说明：\n"
               f"• 玩家可以提问，主持人回答是/否\n"
               f"• 直接说出答案可获得分数\n"
               f"• 主持人可发送'提示'给出提示（限{game.max_hints}次）\n"
               f"• 发送'结束游戏'结束当前游戏\n\n"
               f"🏆 开始推理吧！"
    )

@hint_command.handle()
async def handle_hint(bot: Bot, event: GroupMessageEvent):
    """主持人给出提示"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    game = get_game(group_id)
    
    if game.state != GameState.PLAYING:
        return
    
    if user_id != game.host_id:
        await hint_command.send("只有主持人可以给出提示！")
        return
    
    game.host_hints_used += 1
    
    # 根据提示次数给出不同的提示
    hints = [
        f"💡 提示1：注意关键词 '{random.choice(game.current_story.keywords[:2])}'\n",
        f"💡 提示2：这个故事的关键在于 '{random.choice(game.current_story.keywords[2:4])}'\n",
        f"💡 提示3：答案与 '{random.choice(game.current_story.keywords[-2:])}' 有关\n"
    ]
    
    hint_text = ""
    if game.host_hints_used <= len(hints):
        hint_text = hints[game.host_hints_used - 1]
    else:
        hint_text = f"💡 额外提示：{random.choice(game.current_story.keywords)}\n"
    
    penalty_text = ""
    if game.host_hints_used > game.max_hints:
        penalty_text = f"⚠️ 超出免费提示次数，主持人扣{game.hint_penalty}分\n"
    
    await hint_command.send(
        f"{hint_text}"
        f"{penalty_text}"
        f"📊 已使用提示：{game.host_hints_used}次"
    )

@end_game.handle()
async def handle_end_game(bot: Bot, event: GroupMessageEvent):
    """结束游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    game = get_game(group_id)
    
    if game.state not in [GameState.PLAYING, GameState.TOPIC_CONFIRMATION]:
        await end_game.send("当前没有进行中的游戏！")
        return
    
    # 只有主持人或管理员可以结束游戏
    if user_id != game.host_id:
        try:
            member_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
            if member_info.get('role') not in ['admin', 'owner']:
                await end_game.send("只有主持人或管理员可以结束游戏！")
                return
        except:
            await end_game.send("只有主持人或管理员可以结束游戏！")
            return
    
    await finish_game(bot, group_id, "游戏被手动结束")

@status_command.handle()
async def handle_status(bot: Bot, event: GroupMessageEvent):
    """查看游戏状态"""
    group_id = str(event.group_id)
    game = get_game(group_id)
    
    if game.state == GameState.IDLE:
        await status_command.send("当前没有进行中的游戏。发送'开始海龟汤'开始新游戏！")
        return
    
    status_text = f"🎮 游戏状态：{game.state.value}\n\n"
    
    if game.state == GameState.REGISTERING:
        remaining_time = max(0, int(game.registration_end_time - time.time()))
        status_text += f"📝 报名阶段\n"
        status_text += f"👥 已报名：{len(game.players)}人\n"
        status_text += f"⏰ 剩余时间：{remaining_time}秒\n"
        if game.players:
            player_list = "\n".join([f"  • {player.nickname}" for player in game.players.values()])
            status_text += f"\n报名玩家：\n{player_list}"
    
    elif game.state == GameState.SELECTING_HOST:
        remaining_time = max(0, int(game.host_selection_end_time - time.time()))
        status_text += f"🎯 选择主持人阶段\n"
        status_text += f"👑 竞选人数：{len(game.host_candidates)}人\n"
        status_text += f"⏰ 剩余时间：{remaining_time}秒\n"
        if game.host_candidates:
            candidate_list = "\n".join([f"  • {game.players[uid].nickname}" for uid in game.host_candidates])
            status_text += f"\n竞选者：\n{candidate_list}"
    
    elif game.state in [GameState.TOPIC_CONFIRMATION, GameState.PLAYING]:
        if game.host_id:
            host = game.players[game.host_id]
            status_text += f"🎯 主持人：{host.nickname}\n"
        
        if game.current_story:
            status_text += f"📖 题目：{game.current_story.title}\n"
        
        if game.state == GameState.PLAYING and game.game_start_time:
            game_duration = int(time.time() - game.game_start_time)
            status_text += f"⏰ 游戏时长：{game_duration // 60}分{game_duration % 60}秒\n"
            status_text += f"💡 已用提示：{game.host_hints_used}次\n\n"
            
            # 显示玩家积分
            status_text += "📊 当前积分：\n"
            for player in game.players.values():
                if player.is_host:
                    current_score = game.host_base_score - max(0, game.host_hints_used - game.max_hints) * game.hint_penalty
                    status_text += f"  👑 {player.nickname}：{current_score}分（主持人）\n"
                else:
                    status_text += f"  👤 {player.nickname}：{player.score}分\n"
    
    await status_command.send(status_text)

@message_handler.handle()
async def handle_message(bot: Bot, event: GroupMessageEvent):
    """处理游戏中的消息"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    message = str(event.get_message()).strip()
    
    game = get_game(group_id)
    
    # 只在游戏进行中处理消息
    if game.state != GameState.PLAYING:
        return
    
    # 忽略机器人自己的消息和过短的消息
    if user_id == str(bot.self_id) or len(message) < 2:
        return
    
    # 忽略命令消息
    if message.startswith(('开始', '报名', '结束', '竞选', '换题', '不换', '提示', '状态')):
        return
    
    # 检查是否是参与游戏的玩家
    if user_id not in game.players:
        return
    
    player = game.players[user_id]
    
    # 主持人的消息不参与答案判断
    if player.is_host:
        return
    
    # 检查是否猜中答案
    if is_truth_match(message, game.current_story):
        await handle_correct_answer(bot, group_id, user_id, message)
    else:
        # 记录玩家提问
        player.questions_asked += 1
        
        # 检查是否包含关键词（给予小分奖励）
        for keyword in game.current_story.keywords:
            if keyword.lower() in message.lower() and player.score < game.max_player_score:
                player.score += 1
                await bot.send_group_msg(
                    group_id=int(group_id),
                    message=f"💡 {player.nickname} 提到了关键信息，获得1分！当前积分：{player.score}"
                )
                break

async def handle_correct_answer(bot: Bot, group_id: str, user_id: str, answer: str):
    """处理正确答案"""
    game = get_game(group_id)
    player = game.players[user_id]
    
    # 计算游戏时长
    game_duration = time.time() - game.game_start_time
    time_bonus = calculate_time_bonus(game_duration)
    
    # 给予玩家分数
    player.score = min(game.max_player_score, player.score + 5 + time_bonus)
    
    await finish_game(bot, group_id, f"{player.nickname} 猜中了答案！", user_id)

async def finish_game(bot: Bot, group_id: str, reason: str, winner_id: Optional[str] = None):
    """结束游戏并显示结果"""
    game = get_game(group_id)
    
    if game.state not in [GameState.PLAYING, GameState.TOPIC_CONFIRMATION]:
        return
    
    game.state = GameState.FINISHED
    
    # 计算最终分数
    final_scores = []
    
    for player in game.players.values():
        if player.is_host:
            # 主持人分数计算
            final_score = game.host_base_score - max(0, game.host_hints_used - game.max_hints) * game.hint_penalty
            if game.game_start_time:
                game_duration = time.time() - game.game_start_time
                time_bonus = calculate_time_bonus(game_duration)
                final_score += time_bonus
        else:
            final_score = player.score
            if winner_id and player.user_id == winner_id and game.game_start_time:
                game_duration = time.time() - game.game_start_time
                time_bonus = calculate_time_bonus(game_duration)
                final_score += time_bonus
        
        final_scores.append((player.nickname, final_score, player.is_host))
    
    # 按分数排序
    final_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 生成结果消息
    result_text = f"🎮 游戏结束！\n\n"
    result_text += f"📝 结束原因：{reason}\n\n"
    
    if game.current_story:
        result_text += f"📖 题目：{game.current_story.title}\n"
        result_text += f"🔍 答案：{game.current_story.truth}\n\n"
    
    if game.game_start_time:
        total_duration = int(time.time() - game.game_start_time)
        result_text += f"⏰ 游戏时长：{total_duration // 60}分{total_duration % 60}秒\n\n"
    
    result_text += "🏆 最终排名：\n"
    for i, (nickname, score, is_host) in enumerate(final_scores):
        role = "👑" if is_host else "👤"
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "🏅"
        result_text += f"{medal} {role} {nickname}：{score}分\n"
    
    await bot.send_group_msg(group_id=int(group_id), message=result_text)
    
    # 重置游戏
    game.reset()