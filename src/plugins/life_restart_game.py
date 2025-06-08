from nonebot import on_regex
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
from typing import Dict, List, Optional
from .game_score import update_player_score
import random
import asyncio
import time
from datetime import datetime, date

# 人生重开模拟器游戏状态管理
class LifeRestartGame:
    def __init__(self):
        self.user_id = None
        self.group_id = None
        self.game_status = 'waiting'  # waiting, allocating, playing, finished
        self.attributes = {
            'appearance': 0,  # 颜值
            'intelligence': 0,  # 智力
            'strength': 0,  # 体质
            'wealth': 0  # 家境
        }
        self.age = 0
        self.life_events = []
        self.current_stage = 'birth'  # birth, childhood, youth, adult, elder
        self.talents = []  # 天赋
        self.achievements = []  # 成就
        self.total_points = 20  # 初始属性点
        self.remaining_points = 20
        self.special_flags = set()  # 特殊标记
        self.final_ending = None  # 特殊结局
        
    def reset_game(self):
        """重置游戏状态"""
        self.game_status = 'waiting'
        self.attributes = {'appearance': 0, 'intelligence': 0, 'strength': 0, 'wealth': 0}
        self.age = 0
        self.life_events = []
        self.current_stage = 'birth'
        self.talents = []
        self.achievements = []
        self.remaining_points = 20
        self.special_flags = set()
        self.final_ending = None

# 全局游戏状态
games: Dict[str, LifeRestartGame] = {}
# 添加全局变量来跟踪每日游戏次数
daily_game_count: Dict[str, Dict[str, int]] = {}  # {date: {user_group_key: count}}
MAX_DAILY_GAMES = 10  # 每日最大游戏次数

# 升级版天赋系统 - 按稀有度分类
TALENTS = {
    'SSR': [  # 超稀有 0.5%
        {
            'name': '天命之子', 
            'description': '运气大幅提升，所有随机事件都倾向于好结果', 
            'effect': {'appearance': 1, 'intelligence': 1, 'strength': 1, 'wealth': 1},
            'special': 'luck_boost'
        },
        {
            'name': '神秘小盒子', 
            'description': '可能获得超能力，开启修仙之路', 
            'effect': {'intelligence': 2},
            'special': 'mystery_box'
        },
        {
            'name': '时空旅者', 
            'description': '拥有预知未来的能力，能避开所有灾难', 
            'effect': {'intelligence': 2, 'appearance': 1},
            'special': 'time_traveler'
        },
        {
            'name': '龙之血脉', 
            'description': '体内流淌着龙族血脉，拥有强大的力量', 
            'effect': {'strength': 3, 'appearance': 1},
            'special': 'dragon_blood'
        },
        {
            'name': '系统宿主', 
            'description': '获得了神秘系统的帮助，人生开挂模式', 
            'effect': {'intelligence': 1, 'strength': 1, 'appearance': 1, 'wealth': 1},
            'special': 'system_host'
        }
    ],
    'SR': [  # 稀有 4.5%
        {
            'name': '祖传药丸', 
            'description': '体质+2，寿命延长，免疫疾病', 
            'effect': {'strength': 2},
            'special': 'longevity'
        },
        {
            'name': '天生丽质', 
            'description': '颜值+2，更容易成为明星', 
            'effect': {'appearance': 2},
            'special': 'star_potential'
        },
        {
            'name': '学霸', 
            'description': '智力+2，学习能力大幅增强', 
            'effect': {'intelligence': 2},
            'special': 'study_genius'
        },
        {
            'name': '商业奇才', 
            'description': '智力+1，家境+1，商业天赋异禀', 
            'effect': {'intelligence': 1, 'wealth': 1},
            'special': 'business_genius'
        },
        {
            'name': '演艺天赋', 
            'description': '颜值+1，智力+1，表演天赋出众', 
            'effect': {'appearance': 1, 'intelligence': 1},
            'special': 'acting_talent'
        }
    ],
    'R': [  # 普通 25%
        {
            'name': '家里有矿', 
            'description': '家境+2，初始资金多', 
            'effect': {'wealth': 2}
        },
        {
            'name': '体育健将', 
            'description': '体质+1，运动天赋强', 
            'effect': {'strength': 1},
            'special': 'sports_talent'
        },
        {
            'name': '程序员', 
            'description': '智力+1，IT行业更容易成功', 
            'effect': {'intelligence': 1},
            'special': 'programmer'
        },
        {
            'name': '社交达人', 
            'description': '颜值+1，社交能力强', 
            'effect': {'appearance': 1},
            'special': 'social_master'
        },
        {
            'name': '艺术细胞', 
            'description': '颜值+1，艺术天赋', 
            'effect': {'appearance': 1},
            'special': 'artistic'
        }
    ],
    'N': [  # 普通 70%
        {
            'name': '普通人', 
            'description': '平平无奇的开始', 
            'effect': {},
            'special': 'ordinary'
        },
        {
            'name': '乐观主义者', 
            'description': '心态良好，颜值+1', 
            'effect': {'appearance': 1},
            'special': 'optimist'
        },
        {
            'name': '勤奋努力', 
            'description': '后天努力，智力+1', 
            'effect': {'intelligence': 1}
        },
        {
            'name': '身体健康', 
            'description': '体质不错，体质+1', 
            'effect': {'strength': 1}
        },
        {
            'name': '小康家庭', 
            'description': '家境还行，家境+1', 
            'effect': {'wealth': 1}
        },
        {
            'name': '好奇心强',
            'description': '对世界充满好奇，容易遇到奇遇',
            'effect': {'intelligence': 1},
            'special': 'curious'
        },
        {
            'name': '武侠迷',
            'description': '热爱武侠文化，梦想成为大侠',
            'effect': {'strength': 1},
            'special': 'wuxia_fan'
        },
        {
            'name': '体质敏感',
            'description': '对气场变化敏感，容易感知异常',
            'effect': {'intelligence': 1},
            'special': 'sensitive'
        }
    ]
}

# 扩展的人生事件系统
LIFE_EVENTS = {
    'childhood': [
        {'name': '学会走路', 'description': '你学会了走路，父母很高兴', 'age_range': (1, 2), 'effects': {'strength': 1}},
        {'name': '第一次说话', 'description': '你说出了第一个词，是"妈妈"', 'age_range': (1, 2), 'effects': {'intelligence': 1}},
        {'name': '幼儿园表演', 'description': '你在幼儿园表演中表现出色', 'age_range': (3, 6), 'effects': {'appearance': 1}},
        {'name': '生病住院', 'description': '你生了一场大病，体质有所下降', 'age_range': (3, 6), 'effects': {'strength': -1}},
        {'name': '获得奖状', 'description': '你在幼儿园获得了第一张奖状', 'age_range': (4, 6), 'effects': {'intelligence': 1}},
        
        # SSR天赋专属事件
        {'name': '神秘梦境', 'description': '你做了一个奇怪的梦，梦见自己在修炼', 'age_range': (5, 6), 'effects': {'intelligence': 1}, 'requires': ['mystery_box']},
        {'name': '天赋觉醒', 'description': '你展现了超乎常人的能力', 'age_range': (4, 6), 'effects': {'intelligence': 2}, 'requires': ['mystery_box']},
        {'name': '龙血觉醒', 'description': '你体内的龙族血脉开始觉醒', 'age_range': (5, 8), 'effects': {'strength': 2, 'appearance': 1}, 'requires': ['dragon_blood']},
        {'name': '天才儿童', 'description': '你展现出了超越年龄的智慧', 'age_range': (3, 6), 'effects': {'intelligence': 2}, 'requires': ['system_host']},
        {'name': '时空异象', 'description': '你感知到了时空的波动', 'age_range': (5, 6), 'effects': {'intelligence': 1}, 'requires': ['time_traveler']},
        
        # 普通天赋修仙路线
        {'name': '捡到古书', 'description': '你在路边捡到一本古老的书籍', 'age_range': (5, 8), 'effects': {'intelligence': 1}, 'requires': ['curious'], 'special_flag': 'ancient_book'},
        {'name': '武侠梦', 'description': '你做梦梦见自己成为了江湖大侠', 'age_range': (6, 10), 'effects': {'strength': 1}, 'requires': ['wuxia_fan'], 'special_flag': 'wuxia_dream'},
        {'name': '气感初现', 'description': '你感觉到身体里有股奇怪的力量', 'age_range': (6, 8), 'effects': {'strength': 1}, 'requires': ['sensitive'], 'special_flag': 'qi_sense'},
        
        # 基础事件
        {'name': '学习新技能', 'description': '你学会了一项新技能', 'age_range': (3, 6), 'effects': {'intelligence': 1}},
        {'name': '交到好朋友', 'description': '你交到了一个好朋友', 'age_range': (4, 6), 'effects': {'appearance': 1}},
        {'name': '帮助他人', 'description': '你帮助了需要帮助的人', 'age_range': (5, 6), 'effects': {'appearance': 1}},
        {'name': '参加比赛', 'description': '你参加了一个小比赛', 'age_range': (5, 6), 'effects': {'strength': 1}},
        {'name': '读书学习', 'description': '你认真读书学习', 'age_range': (3, 6), 'effects': {'intelligence': 1}}
    ],
    'youth': [
        {'name': '考试满分', 'description': '你在一次重要考试中获得满分', 'age_range': (7, 18), 'effects': {'intelligence': 2}},
        {'name': '运动会冠军', 'description': '你在学校运动会中获得冠军', 'age_range': (7, 18), 'effects': {'strength': 2}},
        {'name': '校园霸凌', 'description': '你遭遇了校园霸凌，身心受创', 'age_range': (7, 18), 'effects': {'appearance': -1, 'strength': -1}},
        {'name': '初恋', 'description': '你遇到了人生中的初恋', 'age_range': (14, 18), 'effects': {'appearance': 1}},
        {'name': '高考状元', 'description': '你成为了省高考状元', 'age_range': (18, 18), 'effects': {'intelligence': 3}},
        
        # SSR天赋专属事件
        {'name': '修仙入门', 'description': '你意外获得了修仙功法', 'age_range': (16, 18), 'effects': {'intelligence': 3, 'strength': 2}, 'requires': ['mystery_box'], 'special_flag': 'cultivation_start'},
        {'name': '异世界召唤', 'description': '你被神秘力量召唤到异世界', 'age_range': (17, 18), 'effects': {'intelligence': 2, 'strength': 2}, 'requires': ['system_host'], 'special_flag': 'isekai'},
        {'name': '龙族传承', 'description': '你获得了龙族的传承记忆', 'age_range': (16, 18), 'effects': {'strength': 3, 'intelligence': 2}, 'requires': ['dragon_blood'], 'special_flag': 'dragon_heritage'},
        {'name': '时空穿越', 'description': '你第一次成功穿越时空', 'age_range': (17, 18), 'effects': {'intelligence': 3}, 'requires': ['time_traveler'], 'special_flag': 'time_travel'},
        
        # 普通天赋修仙路线
        {'name': '古书解读', 'description': '你终于读懂了那本古书的内容', 'age_range': (12, 16), 'effects': {'intelligence': 2}, 'requires_flag': ['ancient_book'], 'special_flag': 'basic_cultivation'},
        {'name': '武学启蒙', 'description': '你开始学习真正的武术', 'age_range': (12, 18), 'effects': {'strength': 2}, 'requires_flag': ['wuxia_dream'], 'special_flag': 'martial_training'},
        {'name': '内力觉醒', 'description': '你体内的气感越来越强烈', 'age_range': (14, 18), 'effects': {'strength': 2, 'intelligence': 1}, 'requires_flag': ['qi_sense'], 'special_flag': 'inner_power'},
        
        # 基础事件
        {'name': '艺术特长', 'description': '你在艺术方面展现出天赋', 'age_range': (10, 18), 'effects': {'appearance': 2}},
        {'name': '编程竞赛', 'description': '你在编程竞赛中获得冠军', 'age_range': (12, 18), 'effects': {'intelligence': 2}, 'requires': ['programmer']},
        {'name': '星探发现', 'description': '你被星探发现，进入娱乐圈', 'age_range': (15, 18), 'effects': {'appearance': 2}, 'requires': ['star_potential']}
    ],
    'adult': [
        {'name': '大学毕业', 'description': '你顺利从大学毕业', 'age_range': (22, 24), 'effects': {'intelligence': 1}},
        {'name': '找到工作', 'description': '你找到了一份不错的工作', 'age_range': (22, 26), 'effects': {'wealth': 1}},
        {'name': '结婚', 'description': '你与心爱的人结婚了', 'age_range': (25, 35), 'effects': {'appearance': 1}},
        {'name': '生子', 'description': '你有了自己的孩子', 'age_range': (26, 40), 'effects': {'wealth': -1, 'appearance': 1}},
        {'name': '升职加薪', 'description': '你在工作中表现出色，获得升职', 'age_range': (25, 50), 'effects': {'wealth': 2}},
        {'name': '创业成功', 'description': '你的创业项目获得成功', 'age_range': (25, 40), 'effects': {'wealth': 3, 'intelligence': 1}},
        
        # SSR天赋专属事件
        {'name': '修仙飞升', 'description': '你修炼有成，准备飞升仙界', 'age_range': (30, 50), 'effects': {'intelligence': 5, 'strength': 5}, 'requires': ['mystery_box'], 'special_flag': 'ascension'},
        {'name': '异世界王者', 'description': '你在异世界成为了王者', 'age_range': (30, 50), 'effects': {'strength': 4, 'intelligence': 3, 'wealth': 4}, 'requires': ['system_host'], 'special_flag': 'isekai_king'},
        {'name': '龙皇觉醒', 'description': '你觉醒了龙皇血脉', 'age_range': (35, 55), 'effects': {'strength': 6, 'appearance': 3}, 'requires': ['dragon_blood'], 'special_flag': 'dragon_emperor'},
        {'name': '时空守护者', 'description': '你成为了时空的守护者', 'age_range': (40, 60), 'effects': {'intelligence': 5, 'strength': 3}, 'requires': ['time_traveler'], 'special_flag': 'time_guardian'},
        
        # 普通天赋修仙路线
        {'name': '凡人飞升', 'description': '你通过不懈努力，终于突破凡人极限', 'age_range': (35, 55), 'effects': {'intelligence': 3, 'strength': 3}, 'requires_flag': ['basic_cultivation'], 'special_flag': 'mortal_ascension'},
        {'name': '武林盟主', 'description': '你成为了武林盟主', 'age_range': (30, 50), 'effects': {'strength': 4, 'appearance': 2}, 'requires_flag': ['martial_training'], 'special_flag': 'martial_leader'},
        {'name': '气功大师', 'description': '你的内力修为达到了大师级别', 'age_range': (35, 55), 'effects': {'strength': 3, 'intelligence': 2}, 'requires_flag': ['inner_power'], 'special_flag': 'qigong_master'},
        
        # 基础事件
        {'name': '买房', 'description': '你买了人生中第一套房子', 'age_range': (25, 40), 'effects': {'wealth': 1}},
        {'name': '投资理财', 'description': '你开始学习投资理财', 'age_range': (25, 50), 'effects': {'intelligence': 1, 'wealth': 1}},
        {'name': '健身塑形', 'description': '你开始注重身体健康', 'age_range': (25, 45), 'effects': {'strength': 1, 'appearance': 1}}
    ],
    'elder': [
        {'name': '退休', 'description': '你到了退休的年龄', 'age_range': (60, 65), 'effects': {'wealth': -1}},
        {'name': '含饴弄孙', 'description': '你享受着天伦之乐', 'age_range': (55, 75), 'effects': {'appearance': 1}},
        {'name': '身体衰老', 'description': '年龄让你的身体开始衰老', 'age_range': (65, 80), 'effects': {'strength': -1}},
        {'name': '智慧长者', 'description': '你成为了受人尊敬的智慧长者', 'age_range': (65, 80), 'effects': {'intelligence': 1}},
        {'name': '慈善事业', 'description': '你投身于慈善事业', 'age_range': (60, 80), 'effects': {'appearance': 2, 'wealth': -1}},
        
        # 特殊结局前置事件
        {'name': '仙界使者', 'description': '仙界派使者来接你', 'age_range': (70, 90), 'effects': {}, 'requires_flag': ['ascension']},
        {'name': '异世界召唤', 'description': '异世界再次召唤你', 'age_range': (70, 90), 'effects': {}, 'requires_flag': ['isekai_king']},
        {'name': '龙族归宿', 'description': '龙族邀请你回归龙界', 'age_range': (70, 90), 'effects': {}, 'requires_flag': ['dragon_emperor']},
        {'name': '时空使命', 'description': '你接到了新的时空守护使命', 'age_range': (70, 90), 'effects': {}, 'requires_flag': ['time_guardian']},
        
        # 普通修仙结局
        {'name': '修仙大师', 'description': '你被尊为修仙界的大师', 'age_range': (70, 90), 'effects': {'intelligence': 2}, 'requires_flag': ['mortal_ascension']},
        {'name': '武学传说', 'description': '你的武学成就成为传说', 'age_range': (70, 90), 'effects': {'strength': 2}, 'requires_flag': ['martial_leader']},
        {'name': '气功宗师', 'description': '你成为了气功界的宗师', 'age_range': (70, 90), 'effects': {'strength': 1, 'intelligence': 1}, 'requires_flag': ['qigong_master']},
        
        # 基础事件
        {'name': '回忆往昔', 'description': '你回忆起了年轻时的美好时光', 'age_range': (65, 80), 'effects': {'appearance': 1}},
        {'name': '传授经验', 'description': '你向年轻人传授人生经验', 'age_range': (60, 80), 'effects': {'intelligence': 1}}
    ]
}

# 特殊结局系统
SPECIAL_ENDINGS = {
    'ascension': {
        'name': '修仙飞升',
        'description': '你修炼有成，成功飞升仙界，获得永生',
        'requirements': {'special_flags': ['ascension'], 'intelligence': 15},
        'score_bonus': 50
    },
    'isekai_king': {
        'name': '异世界王者',
        'description': '你在异世界建立了强大的王国，成为传说中的王者',
        'requirements': {'special_flags': ['isekai_king'], 'strength': 15},
        'score_bonus': 45
    },
    'dragon_emperor': {
        'name': '龙皇',
        'description': '你觉醒了完整的龙皇血脉，统治龙族',
        'requirements': {'special_flags': ['dragon_emperor'], 'strength': 18},
        'score_bonus': 48
    },
    'time_guardian': {
        'name': '时空主宰',
        'description': '你成为了时空的主宰，守护着多元宇宙的平衡',
        'requirements': {'special_flags': ['time_guardian'], 'intelligence': 20},
        'score_bonus': 55
    },
    'mortal_ascension': {
        'name': '凡人飞升',
        'description': '你以凡人之身突破极限，证明了努力的力量',
        'requirements': {'special_flags': ['mortal_ascension'], 'intelligence': 12},
        'score_bonus': 35
    },
    'martial_leader': {
        'name': '武林传说',
        'description': '你成为了武林中的传奇人物，武学成就无人能及',
        'requirements': {'special_flags': ['martial_leader'], 'strength': 15},
        'score_bonus': 30
    },
    'qigong_master': {
        'name': '气功宗师',
        'description': '你的气功修为达到了前无古人的高度',
        'requirements': {'special_flags': ['qigong_master'], 'strength': 12, 'intelligence': 10},
        'score_bonus': 28
    },
    'billionaire': {
        'name': '世界首富',
        'description': '你通过商业成就积累了巨额财富，成为世界首富',
        'requirements': {'wealth': 20},
        'score_bonus': 40
    },
    'superstar': {
        'name': '超级巨星',
        'description': '你成为了享誉全球的超级巨星',
        'requirements': {'appearance': 18},
        'score_bonus': 35
    },
    'genius': {
        'name': '天才科学家',
        'description': '你的智慧推动了人类文明的进步',
        'requirements': {'intelligence': 22},
        'score_bonus': 38
    },
    'ordinary': {
        'name': '平凡一生',
        'description': '你过着平凡而充实的一生，虽然普通但也很幸福',
        'requirements': {},
        'score_bonus': 10
    }
}

def get_random_talent():
    """根据稀有度随机获取天赋"""
    rand = random.random()
    if rand < 0.005:  # 0.5%
        rarity = 'SSR'
    elif rand < 0.05:  # 4.5%
        rarity = 'SR'
    elif rand < 0.3:  # 25%
        rarity = 'R'
    else:  # 70%
        rarity = 'N'
    
    return random.choice(TALENTS[rarity])

def check_event_requirements(event, game):
    """检查事件触发条件"""
    # 检查天赋要求
    if 'requires' in event:
        talent_specials = {talent.get('special', '') for talent in game.talents}
        required_specials = set(event['requires'])
        if not required_specials.intersection(talent_specials):
            return False
    
    # 检查特殊标记要求
    if 'requires_flag' in event:
        required_flags = set(event['requires_flag'])
        if not required_flags.intersection(game.special_flags):
            return False
    
    return True

def determine_final_ending(game):
    """确定最终结局（按优先级）"""
    # 按优先级检查特殊结局
    priority_endings = [
        'time_guardian', 'ascension', 'dragon_emperor', 'isekai_king',
        'mortal_ascension', 'martial_leader', 'qigong_master',
        'genius', 'billionaire', 'superstar'
    ]
    
    for ending_key in priority_endings:
        ending = SPECIAL_ENDINGS[ending_key]
        requirements = ending['requirements']
        
        # 检查特殊标记要求
        if 'special_flags' in requirements:
            required_flags = set(requirements['special_flags'])
            if not required_flags.intersection(game.special_flags):
                continue
        
        # 检查属性要求
        meets_requirements = True
        for attr, min_value in requirements.items():
            if attr != 'special_flags' and game.attributes.get(attr, 0) < min_value:
                meets_requirements = False
                break
        
        if meets_requirements:
            return ending_key
    
    return 'ordinary'

def generate_stage_events(game, stage_name, start_age, end_age):
    """生成阶段事件"""
    stage_events = []
    available_events = LIFE_EVENTS.get(stage_name, []).copy()
    
    # 确保每个阶段有足够的事件
    target_events = random.randint(3, 6)
    special_events_count = 0
    max_special_events = 2
    
    for _ in range(target_events):
        if not available_events:
            break
        
        # 分层筛选事件
        valid_events = []
        
        # 1. 优先选择特殊天赋事件（限制数量）
        if special_events_count < max_special_events:
            special_events = [
                e for e in available_events 
                if (start_age <= e['age_range'][1] and end_age >= e['age_range'][0] 
                    and ('requires' in e or 'requires_flag' in e) 
                    and check_event_requirements(e, game))
            ]
            if special_events:
                valid_events = special_events
                special_events_count += 1
        
        # 2. 选择基础事件
        if not valid_events:
            basic_events = [
                e for e in available_events 
                if (start_age <= e['age_range'][1] and end_age >= e['age_range'][0] 
                    and 'requires' not in e and 'requires_flag' not in e)
            ]
            if basic_events:
                valid_events = basic_events
        
        # 3. 兜底：放宽年龄限制
        if not valid_events:
            fallback_events = [
                e for e in available_events 
                if ((start_age - 2) <= e['age_range'][1] and (end_age + 2) >= e['age_range'][0])
            ]
            if fallback_events:
                valid_events = fallback_events
        
        if not valid_events:
            continue
        
        # 选择事件并应用
        event = random.choice(valid_events)
        event_age = random.randint(
            max(start_age, event['age_range'][0]), 
            min(end_age, event['age_range'][1])
        )
        
        # 应用事件效果
        effects = event.get('effects', {})
        for attr, change in effects.items():
            game.attributes[attr] = max(0, game.attributes[attr] + change)
        
        # 添加特殊标记
        if 'special_flag' in event:
            game.special_flags.add(event['special_flag'])
        
        stage_events.append((event_age, event))
        available_events.remove(event)
    
    # 确保最少事件数量
    while len(stage_events) < 2 and available_events:
        event = random.choice(available_events)
        event_age = random.randint(start_age, end_age)
        stage_events.append((event_age, event))
        available_events.remove(event)
    
    return stage_events

# 命令定义
start_life = on_regex(pattern="^人生重开$", priority=5)
allocate_points = on_regex(pattern=r"^分配属性\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$", priority=5)
start_simulation = on_regex(pattern="^开始模拟$""", priority=5)
life_summary = on_regex(pattern="^人生总结$""", priority=5)

@start_life.handle()
async def handle_start_life(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    game_key = f"{group_id}_{user_id}"
    
    # 检查每日游戏次数限制
    today = date.today().isoformat()
    if today not in daily_game_count:
        daily_game_count[today] = {}
    
    user_today_count = daily_game_count[today].get(game_key, 0)
    if user_today_count >= MAX_DAILY_GAMES:
        await start_life.finish(f"今日游戏次数已达上限({MAX_DAILY_GAMES}次)，请明天再来！")
        return
    
    # 更新游戏次数
    daily_game_count[today][game_key] = user_today_count + 1
    
    # 创建新游戏或重置现有游戏
    if game_key in games:
        games[game_key].reset_game()
    else:
        games[game_key] = LifeRestartGame()
    
    game = games[game_key]
    game.user_id = user_id
    game.group_id = group_id
    
    # 随机分配天赋
    talent = get_random_talent()
    game.talents = [talent]
    
    # 应用天赋效果
    for attr, bonus in talent.get('effect', {}).items():
        game.attributes[attr] += bonus
    
    # 添加天赋特殊标记
    if 'special' in talent:
        game.special_flags.add(talent['special'])
    
    game.game_status = 'allocating'
    
    message = f"🎮 人生重开模拟器\n\n"
    message += f"🌟 你的天赋：{talent['name']}\n"
    message += f"📝 {talent['description']}\n\n"
    
    if talent.get('effect'):
        message += f"💫 天赋效果：\n"
        for attr, bonus in talent['effect'].items():
            attr_name = {'appearance': '颜值', 'intelligence': '智力', 'strength': '体质', 'wealth': '家境'}[attr]
            message += f"   {attr_name} {'+' if bonus > 0 else ''}{bonus}\n"
        message += "\n"
    
    message += f"📊 当前属性：\n"
    message += f"👤 颜值：{game.attributes['appearance']}\n"
    message += f"🧠 智力：{game.attributes['intelligence']}\n"
    message += f"💪 体质：{game.attributes['strength']}\n"
    message += f"💰 家境：{game.attributes['wealth']}\n\n"
    message += f"🎯 你有{game.remaining_points}点属性可以分配\n"
    message += f"请发送：分配属性 颜值 智力 体质 家境\n"
    message += f"例如：分配属性 2 3 1 4"
    
    await start_life.finish(message)

@allocate_points.handle()
async def handle_allocate_points(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    game_key = f"{group_id}_{user_id}"
    
    if game_key not in games:
        await allocate_points.finish("请先发送【人生重开】开始游戏！")
        return
    
    game = games[game_key]
    if game.game_status != 'allocating':
        await allocate_points.finish("当前不在属性分配阶段！")
        return
    
    # 解析属性分配
    import re
    match = re.match(r"^分配属性\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$", event.get_plaintext())
    if not match:
        await allocate_points.finish("格式错误！请使用：分配属性 颜值 智力 体质 家境")
        return
    
    points = [int(match.group(i)) for i in range(1, 5)]
    total_allocated = sum(points)
    
    if total_allocated != game.remaining_points:
        await allocate_points.finish(f"属性点分配错误！你有{game.remaining_points}点可分配，但你分配了{total_allocated}点")
        return
    
    # 应用属性分配
    attrs = ['appearance', 'intelligence', 'strength', 'wealth']
    for i, attr in enumerate(attrs):
        game.attributes[attr] += points[i]
    
    game.remaining_points = 0
    game.game_status = 'playing'
    
    message = f"✅ 属性分配完成！\n\n"
    message += f"📊 最终属性：\n"
    message += f"👤 颜值：{game.attributes['appearance']}\n"
    message += f"🧠 智力：{game.attributes['intelligence']}\n"
    message += f"💪 体质：{game.attributes['strength']}\n"
    message += f"💰 家境：{game.attributes['wealth']}\n\n"
    message += f"发送【开始模拟】开始你的人生旅程！"
    
    await allocate_points.finish(message)

@start_simulation.handle()
async def handle_start_simulation(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    game_key = f"{group_id}_{user_id}"
    
    if game_key not in games:
        await start_simulation.finish("请先发送【人生重开】开始游戏！")
        return
    
    game = games[game_key]
    if game.game_status != 'playing':
        await start_simulation.finish("请先完成属性分配！")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 开始人生模拟
    message = f"🎬 {nickname} 的人生开始了...\n\n"
    
    # 模拟人生各个阶段
    stages = [
        ('childhood', 1, 6),
        ('youth', 7, 18),
        ('adult', 19, 60),
        ('elder', 61, 80)
    ]
    
    for stage_name, start_age, end_age in stages:
        stage_events = generate_stage_events(game, stage_name, start_age, end_age)
        game.life_events.extend(stage_events)
    
    # 按年龄排序所有事件
    game.life_events.sort(key=lambda x: x[0])
    
    # 显示人生历程（前12个重要事件）
    for age, event in game.life_events[:12]:
        message += f"📅 {age}岁：{event['description']}\n"
    
    if len(game.life_events) > 12:
        message += f"\n... 还有{len(game.life_events) - 12}个人生事件\n"
    
    # 计算最终年龄
    final_age = random.randint(70, 95)
    if any('longevity' in talent.get('special', '') for talent in game.talents):
        final_age += random.randint(10, 20)
    
    game.age = final_age
    
    # 确定特殊结局
    ending_key = determine_final_ending(game)
    game.final_ending = ending_key
    ending = SPECIAL_ENDINGS[ending_key]
    
    message += f"\n⚰️ 你在{final_age}岁时的人生结局：\n"
    message += f"🎯 {ending['name']}\n"
    message += f"📖 {ending['description']}\n\n"
    
    message += f"📊 最终属性：\n"
    message += f"👤 颜值：{game.attributes['appearance']}\n"
    message += f"🧠 智力：{game.attributes['intelligence']}\n"
    message += f"💪 体质：{game.attributes['strength']}\n"
    message += f"💰 家境：{game.attributes['wealth']}\n\n"
    
    # 计算人生评分
    total_score = sum(game.attributes.values()) + final_age // 10 + ending['score_bonus']
    
    if total_score >= 100:
        rating = "🏆 传奇人生"
        score_bonus = 50
    elif total_score >= 80:
        rating = "🥇 精彩人生"
        score_bonus = 30
    elif total_score >= 60:
        rating = "🥈 成功人生"
        score_bonus = 20
    elif total_score >= 40:
        rating = "🥉 普通人生"
        score_bonus = 15
    elif total_score >= 20:
        rating = "😐 平凡人生"
        score_bonus = 10
    else:
        rating = "😢 悲惨人生"
        score_bonus = 5
    
    message += f"🎯 人生评价：{rating}\n"
    message += f"📈 综合评分：{total_score}分\n"
    message += f"🏆 游戏获得积分{score_bonus}分\n\n"
    message += f"发送【人生总结】查看详细总结"
    
    # 更新积分
    await update_player_score(user_id, group_id, score_bonus, 'life_restart', None, rating)
    
    game.game_status = 'finished'
    
    await start_simulation.finish(message)

@life_summary.handle()
async def handle_life_summary(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    game_key = f"{group_id}_{user_id}"
    
    if game_key not in games:
        await life_summary.finish("请先完成一次人生模拟！")
        return
    
    game = games[game_key]
    if game.game_status != 'finished':
        await life_summary.finish("请先完成人生模拟！")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    message = f"📋 {nickname} 的人生总结\n\n"
    message += f"🌟 天赋：{game.talents[0]['name']}\n"
    message += f"⏰ 享年：{game.age}岁\n"
    
    if game.final_ending:
        ending = SPECIAL_ENDINGS[game.final_ending]
        message += f"🎯 最终结局：{ending['name']}\n\n"
    
    message += f"📚 人生大事记：\n"
    for age, event in game.life_events:
        message += f"• {age}岁：{event['name']}\n"
    
    message += f"\n📊 最终属性：\n"
    message += f"👤 颜值：{game.attributes['appearance']}\n"
    message += f"🧠 智力：{game.attributes['intelligence']}\n"
    message += f"💪 体质：{game.attributes['strength']}\n"
    message += f"💰 家境：{game.attributes['wealth']}\n\n"
    
    total_score = sum(game.attributes.values()) + game.age // 10
    if game.final_ending:
        total_score += SPECIAL_ENDINGS[game.final_ending]['score_bonus']
    
    message += f"🎯 综合评分：{total_score}分\n\n"
    message += f"想要重新体验人生吗？发送【人生重开】开始新的人生！"
    
    await life_summary.finish(message)