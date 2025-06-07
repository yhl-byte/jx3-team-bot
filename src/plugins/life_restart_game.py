from nonebot import on_regex
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
        },
        {
            'name': '剑心通明',
            'description': '你拥有剑道天赋，心如明镜，剑意通天',
            'effect': {'strength': 4, 'intelligence': 3, 'appearance': 2},
            'special': 'sword_master'
        },
        {
            'name': '江湖传说',
            'description': '你注定要在江湖中留下传说',
            'effect': {'strength': 3, 'intelligence': 2, 'appearance': 4},
            'special': 'jianghu_legend'
        },
        {
            'name': '天策血脉',
            'description': '你拥有天策府的血脉传承，天生将才',
            'effect': {'strength': 5, 'intelligence': 3, 'wealth': 2},
            'special': 'tiancefuBloodline'
        },
        {
            'name': '纯阳道体',
            'description': '你拥有纯阳宫的道体，修道天赋异禀',
            'effect': {'intelligence': 5, 'strength': 2, 'appearance': 3},
            'special': 'chunyang_dao'
        },
        {
            'name': '万花医仙',
            'description': '你拥有万花谷的医道传承，妙手回春',
            'effect': {'intelligence': 4, 'appearance': 3, 'wealth': 3},
            'special': 'wanhua_doctor'
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
        },
        {
            'name': '美食家', 
            'description': '对美食有着超凡的天赋和品味', 
            'effect': {'appearance': 1, 'wealth': 1},
            'special': 'gourmet'
        },
        {
            'name': '武术奇才', 
            'description': '天生的武术天赋，身手不凡', 
            'effect': {'strength': 2, 'appearance': 1},
            'special': 'martial_arts'
        },
        {
            'name': '音乐天才', 
            'description': '拥有绝对音感，音乐天赋异禀', 
            'effect': {'appearance': 2, 'intelligence': 1},
            'special': 'music_genius'
        },
        {
            'name': '发明家', 
            'description': '创新思维强，善于发明创造', 
            'effect': {'intelligence': 2, 'wealth': 1},
            'special': 'inventor'
        },
        {
            'name': '心理大师', 
            'description': '能够洞察人心，社交能力超强', 
            'effect': {'intelligence': 1, 'appearance': 2},
            'special': 'psychologist'
        },
        {
            'name': '剑三玩家',
            'description': '你是资深的剑网三玩家，对江湖了如指掌',
            'effect': {'intelligence': 2, 'appearance': 1, 'wealth': 1},
            'special': 'jx3_player'
        },
        {
            'name': '武学奇才',
            'description': '你在武学方面有着惊人的天赋',
            'effect': {'strength': 3, 'intelligence': 1},
            'special': 'martial_genius'
        },
        {
            'name': '琴棋书画',
            'description': '你精通琴棋书画，是个文艺青年',
            'effect': {'intelligence': 2, 'appearance': 2},
            'special': 'scholar_artist'
        },
        {
            'name': '商业头脑',
            'description': '你有着敏锐的商业嗅觉',
            'effect': {'intelligence': 2, 'wealth': 2},
            'special': 'business_mind'
        },
        {
            'name': '社交达人',
            'description': '你天生就是社交场合的焦点',
            'effect': {'appearance': 3, 'intelligence': 1},
            'special': 'social_butterfly'
        },
        {
            'name': '健身达人',
            'description': '你热爱运动，身体素质极佳',
            'effect': {'strength': 3, 'appearance': 1},
            'special': 'fitness_enthusiast'
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
        },
        {
            'name': '网红体质', 
            'description': '天生容易走红，自带流量', 
            'effect': {'appearance': 2},
            'special': 'influencer'
        },
        {
            'name': '游戏高手', 
            'description': '在各种游戏中都能快速上手', 
            'effect': {'intelligence': 1, 'appearance': 1},
            'special': 'gamer'
        },
        {
            'name': '动物朋友', 
            'description': '与动物有着特殊的亲和力', 
            'effect': {'appearance': 1, 'strength': 1},
            'special': 'animal_friend'
        },
        {
            'name': '料理达人', 
            'description': '厨艺精湛，能做出美味料理', 
            'effect': {'intelligence': 1, 'wealth': 1},
            'special': 'chef'
        },
        {
            'name': '直播天赋', 
            'description': '天生适合直播，能吸引大量观众', 
            'effect': {'appearance': 1, 'intelligence': 1},
            'special': 'streamer'
        },
        {
            'name': '游戏高手',
            'description': '你在各种游戏中都表现出色',
            'effect': {'intelligence': 1, 'appearance': 1},
            'special': 'game_master'
        },
        {
            'name': '二次元爱好者',
            'description': '你热爱动漫和二次元文化',
            'effect': {'intelligence': 1, 'appearance': 1},
            'special': 'otaku'
        },
        {
            'name': '夜猫子',
            'description': '你习惯熬夜，精神力很强',
            'effect': {'intelligence': 2, 'strength': -1},
            'special': 'night_owl'
        },
        {
            'name': '吃货',
            'description': '你对美食有着特殊的执着',
            'effect': {'appearance': 1, 'wealth': -1},
            'special': 'foodie'
        },
        {
            'name': '路痴',
            'description': '你经常迷路，但也因此发现了很多有趣的地方',
            'effect': {'intelligence': -1, 'appearance': 1},
            'special': 'directionally_challenged'
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
            'name': '悲观主义者',
            'description': '你总是往坏处想',
            'effect': {'intelligence': 1, 'appearance': -1},
            'special': 'pessimist'
        },
        {
            'name': '勤奋努力', 
            'description': '后天努力，智力+1', 
            'effect': {'intelligence': 1}
        },
        {
            'name': '懒惰',
            'description': '你比较懒惰，不喜欢运动',
            'effect': {'strength': -1, 'intelligence': 1},
            'special': 'lazy'
        },
        {
            'name': '勤奋',
            'description': '你很勤奋，愿意付出努力',
            'effect': {'intelligence': 1},
            'special': 'hardworking'
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
        {'name': '神秘梦境', 'description': '你做了一个奇怪的梦，梦见自己在修炼', 'age_range': (5, 6), 'effects': {'intelligence': 1}, 'requires': ['mystery_box']},
        {'name': '天赋觉醒', 'description': '你展现了超乎常人的能力', 'age_range': (4, 6), 'effects': {'intelligence': 2}, 'requires': ['mystery_box']},
        {'name': '捡到神秘石头', 'description': '你在路边捡到一块会发光的石头', 'age_range': (5, 8), 'effects': {'intelligence': 1}, 'special_flag': 'mysterious_stone'},
        {'name': '被动物救助', 'description': '你被困时被小动物救了出来', 'age_range': (4, 7), 'effects': {'strength': 1}, 'requires': ['animal_friend']},
        {'name': '天才儿童', 'description': '你展现出了超越年龄的智慧', 'age_range': (3, 6), 'effects': {'intelligence': 2}, 'requires': ['system_host']},
        {'name': '龙血觉醒', 'description': '你体内的龙族血脉开始觉醒', 'age_range': (5, 8), 'effects': {'strength': 2, 'appearance': 1}, 'requires': ['dragon_blood']},
        {
            'name': '初识剑网三',
            'description': '你第一次接触到剑网三这款游戏，被江湖世界深深吸引',
            'age_range': (8, 12),
            'effects': {'intelligence': 1, 'appearance': 1},
            'special_flag': 'jx3_start'
        },
        {
            'name': '武侠梦',
            'description': '你做梦梦见自己成为了江湖大侠',
            'age_range': (6, 10),
            'effects': {'strength': 1, 'intelligence': 1},
            'special_flag': 'wuxia_dream'
        },
        {
            'name': '古装剧迷',
            'description': '你迷上了古装武侠剧，对江湖充满向往',
            'age_range': (7, 12),
            'effects': {'appearance': 1, 'intelligence': 1}
        }
    ],
    'youth': [
        {'name': '考试满分', 'description': '你在一次重要考试中获得满分', 'age_range': (7, 18), 'effects': {'intelligence': 2}},
        {'name': '运动会冠军', 'description': '你在学校运动会中获得冠军', 'age_range': (7, 18), 'effects': {'strength': 2}},
        {'name': '校园霸凌', 'description': '你遭遇了校园霸凌，身心受创', 'age_range': (7, 18), 'effects': {'appearance': -1, 'strength': -1}},
        {'name': '初恋', 'description': '你遇到了人生中的初恋', 'age_range': (14, 18), 'effects': {'appearance': 1}},
        {'name': '高考状元', 'description': '你成为了省高考状元', 'age_range': (18, 18), 'effects': {'intelligence': 3}},
        {'name': '艺术特长', 'description': '你在艺术方面展现出天赋', 'age_range': (10, 18), 'effects': {'appearance': 2}},
        {'name': '编程竞赛', 'description': '你在编程竞赛中获得冠军', 'age_range': (12, 18), 'effects': {'intelligence': 2}, 'requires': ['programmer']},
        {'name': '星探发现', 'description': '你被星探发现，进入娱乐圈', 'age_range': (15, 18), 'effects': {'appearance': 2}, 'requires': ['star_potential']},
        {'name': '修仙入门', 'description': '你意外获得了修仙功法', 'age_range': (16, 18), 'effects': {'intelligence': 3, 'strength': 2}, 'requires': ['mystery_box']},
        {'name': '异世界召唤', 'description': '你被神秘力量召唤到异世界', 'age_range': (17, 18), 'effects': {'intelligence': 2, 'strength': 2}, 'special_flag': 'isekai'},
        {'name': '网络走红', 'description': '你因为一个视频在网上走红', 'age_range': (13, 18), 'effects': {'appearance': 2, 'wealth': 1}, 'requires': ['influencer']},
        {'name': '电竞冠军', 'description': '你在电竞比赛中获得冠军', 'age_range': (14, 18), 'effects': {'intelligence': 2, 'wealth': 2}, 'requires': ['gamer']},
        {'name': '音乐比赛', 'description': '你在音乐比赛中获得第一名', 'age_range': (12, 18), 'effects': {'appearance': 3}, 'requires': ['music_genius']},
        {'name': '武术大赛', 'description': '你在武术大赛中展现惊人实力', 'age_range': (15, 18), 'effects': {'strength': 3}, 'requires': ['martial_arts']},
        {'name': '发明专利', 'description': '你的发明获得了专利', 'age_range': (16, 18), 'effects': {'intelligence': 2, 'wealth': 2}, 'requires': ['inventor']},
        {'name': '时空异象', 'description': '你目睹了时空异象，获得了特殊能力', 'age_range': (17, 18), 'effects': {'intelligence': 3}, 'requires': ['time_traveler']},
        {'name': '系统升级', 'description': '你的系统进行了重大升级', 'age_range': (16, 18), 'effects': {'intelligence': 2, 'strength': 1, 'wealth': 1}, 'requires': ['system_host']},
        {
            'name': '剑网三公测',
            'description': '你参与了剑网三的公测，成为了第一批玩家',
            'age_range': (12, 18),
            'effects': {'intelligence': 2, 'appearance': 1},
            'requires': ['jx3_player'],
            'special_flag': 'jx3_beta'
        },
        {
            'name': '门派选择',
            'description': '你在剑网三中选择了自己喜欢的门派',
            'age_range': (13, 18),
            'effects': {'intelligence': 1, 'strength': 1},
            'requires': ['jx3_player']
        },
        {
            'name': '第一次JJC',
            'description': '你第一次参加剑网三的竞技场比赛',
            'age_range': (14, 18),
            'effects': {'strength': 1, 'intelligence': 1},
            'requires': ['jx3_player']
        },
        {
            'name': '帮会生活',
            'description': '你在剑网三中加入了帮会，体验了团队合作的乐趣',
            'age_range': (15, 18),
            'effects': {'appearance': 2, 'intelligence': 1},
            'requires': ['jx3_player']
        },
        {
            'name': '武学启蒙',
            'description': '你开始学习真正的武术',
            'age_range': (12, 18),
            'effects': {'strength': 2, 'intelligence': 1},
            'requires': ['martial_genius']
        },
        {
            'name': '古风音乐',
            'description': '你爱上了古风音乐，开始学习古典乐器',
            'age_range': (13, 18),
            'effects': {'appearance': 2, 'intelligence': 1},
            'requires': ['scholar_artist']
        },
        {
            'name': 'Cosplay初体验',
            'description': '你第一次尝试Cosplay剑网三角色',
            'age_range': (14, 18),
            'effects': {'appearance': 2},
            'requires': ['jx3_player', 'otaku']
        }
    ],
    'adult': [
        {'name': '大学毕业', 'description': '你顺利从大学毕业', 'age_range': (22, 22), 'effects': {'intelligence': 1}},
        {'name': '找到工作', 'description': '你找到了一份不错的工作', 'age_range': (22, 25), 'effects': {'wealth': 2}},
        {'name': '升职加薪', 'description': '你在工作中表现出色，获得升职', 'age_range': (25, 40), 'effects': {'wealth': 2}},
        {'name': '结婚', 'description': '你与心爱的人步入婚姻殿堂', 'age_range': (25, 35), 'effects': {'appearance': 1}},
        {'name': '生子', 'description': '你有了自己的孩子', 'age_range': (26, 40), 'effects': {'wealth': -1}},
        {'name': '创业成功', 'description': '你的创业项目获得成功', 'age_range': (25, 45), 'effects': {'wealth': 3}},
        {'name': '创业失败', 'description': '你的创业项目失败了', 'age_range': (25, 45), 'effects': {'wealth': -2}},
        {'name': '中年危机', 'description': '你遭遇了中年危机', 'age_range': (35, 50), 'effects': {'appearance': -1, 'strength': -1}},
        {'name': '科技巨头', 'description': '你创立了科技公司并成为巨头', 'age_range': (25, 40), 'effects': {'wealth': 5, 'intelligence': 2}, 'requires': ['programmer']},
        {'name': '商业帝国', 'description': '你建立了庞大的商业帝国', 'age_range': (30, 50), 'effects': {'wealth': 6}, 'requires': ['business_genius']},
        {'name': '国际巨星', 'description': '你成为了国际知名的超级巨星', 'age_range': (25, 40), 'effects': {'appearance': 4, 'wealth': 4}, 'requires': ['star_potential', 'acting_talent']},
        {'name': '修仙大成', 'description': '你的修为大幅提升，已非凡人', 'age_range': (30, 50), 'effects': {'intelligence': 5, 'strength': 5}, 'requires': ['mystery_box']},
        {'name': '异世界称王', 'description': '你在异世界建立了自己的王国', 'age_range': (25, 45), 'effects': {'intelligence': 3, 'strength': 3, 'wealth': 4}, 'requires': ['isekai']},
        {'name': '神秘实验', 'description': '你参与了一项神秘实验，身体发生变异', 'age_range': (25, 40), 'effects': {'strength': -3, 'intelligence': -2}, 'special_flag': 'mutation'},
        {'name': '美食节目', 'description': '你主持的美食节目大受欢迎', 'age_range': (25, 40), 'effects': {'appearance': 2, 'wealth': 3}, 'requires': ['gourmet', 'chef']},
        {'name': '直播带货', 'description': '你通过直播带货赚得盆满钵满', 'age_range': (25, 35), 'effects': {'wealth': 4}, 'requires': ['streamer', 'influencer']},
        {'name': '武林盟主', 'description': '你成为了武林盟主', 'age_range': (30, 45), 'effects': {'strength': 4, 'appearance': 2}, 'requires': ['martial_arts']},
        {'name': '心理诊所', 'description': '你开设的心理诊所生意兴隆', 'age_range': (28, 50), 'effects': {'intelligence': 2, 'wealth': 3}, 'requires': ['psychologist']},
        {'name': '发明改变世界', 'description': '你的发明改变了世界', 'age_range': (30, 50), 'effects': {'intelligence': 5, 'wealth': 6}, 'requires': ['inventor']},
        {'name': '时空管理局', 'description': '你被时空管理局招募', 'age_range': (25, 40), 'effects': {'intelligence': 4, 'strength': 2}, 'requires': ['time_traveler'], 'special_flag': 'time_agent'},
        {'name': '龙王传承', 'description': '你获得了完整的龙王传承', 'age_range': (30, 50), 'effects': {'strength': 6, 'intelligence': 3}, 'requires': ['dragon_blood'], 'special_flag': 'dragon_king'},
        {'name': '系统融合', 'description': '你与系统完全融合，获得超凡力量', 'age_range': (35, 50), 'effects': {'intelligence': 4, 'strength': 4, 'appearance': 2, 'wealth': 2}, 'requires': ['system_host'], 'special_flag': 'system_fusion'},
        {
            'name': '剑网三主播',
            'description': '你成为了知名的剑网三游戏主播',
            'age_range': (20, 35),
            'effects': {'appearance': 3, 'wealth': 3, 'intelligence': 1},
            'requires': ['jx3_player', 'social_butterfly'],
            'special_flag': 'jx3_streamer'
        },
        {
            'name': '游戏策划',
            'description': '你进入游戏公司成为了策划',
            'age_range': (22, 40),
            'effects': {'intelligence': 3, 'wealth': 2},
            'requires': ['jx3_player', 'game_master']
        },
        {
            'name': '武馆教练',
            'description': '你开设了武馆，教授传统武术',
            'age_range': (25, 45),
            'effects': {'strength': 2, 'wealth': 2, 'appearance': 1},
            'requires': ['martial_genius']
        },
        {
            'name': '古风歌手',
            'description': '你成为了知名的古风歌手',
            'age_range': (22, 40),
            'effects': {'appearance': 4, 'wealth': 3},
            'requires': ['scholar_artist']
        },
        {
            'name': '剑网三比赛冠军',
            'description': '你在剑网三官方比赛中获得冠军',
            'age_range': (20, 30),
            'effects': {'intelligence': 2, 'wealth': 3, 'appearance': 2},
            'requires': ['jx3_player'],
            'special_flag': 'jx3_champion'
        },
        {
            'name': '江湖聚会',
            'description': '你组织了大型的剑网三玩家线下聚会',
            'age_range': (25, 40),
            'effects': {'appearance': 2, 'wealth': 1, 'intelligence': 1},
            'requires': ['jx3_player', 'social_butterfly']
        },
        {
            'name': '武侠小说作家',
            'description': '你开始创作武侠小说，作品大受欢迎',
            'age_range': (25, 45),
            'effects': {'intelligence': 3, 'wealth': 3, 'appearance': 1},
            'requires': ['scholar_artist', 'wuxia_dream']
        },
        {
            'name': '古装影视制作',
            'description': '你参与了古装影视剧的制作',
            'age_range': (28, 50),
            'effects': {'intelligence': 2, 'wealth': 4, 'appearance': 2},
            'requires': ['scholar_artist']
        }
    ],
    'elder': [
        {'name': '退休', 'description': '你正式退休，开始享受晚年生活', 'age_range': (60, 65), 'effects': {'strength': -1}},
        {'name': '含饴弄孙', 'description': '你享受着与孙辈的快乐时光', 'age_range': (55, 80), 'effects': {'appearance': 1}},
        {'name': '身体不适', 'description': '年龄增长带来了健康问题', 'age_range': (50, 80), 'effects': {'strength': -2}},
        {'name': '智慧长者', 'description': '你成为了备受尊敬的智慧长者', 'age_range': (60, 80), 'effects': {'intelligence': 1}},
        {'name': '财富积累', 'description': '你的一生积累了不少财富', 'age_range': (55, 75), 'effects': {'wealth': 2}},
        {'name': '修仙飞升', 'description': '你突破了人类极限，飞升成仙', 'age_range': (60, 80), 'effects': {'intelligence': 10, 'strength': 10}, 'requires': ['mystery_box'], 'special_flag': 'ascension'},
        {'name': '世界首富', 'description': '你成为了世界首富，财富无人能及', 'age_range': (50, 70), 'effects': {'wealth': 10}, 'requires': ['business_genius'], 'special_flag': 'richest'},
        {'name': '传奇巨星', 'description': '你成为了传奇级别的超级巨星', 'age_range': (50, 70), 'effects': {'appearance': 8}, 'requires': ['star_potential'], 'special_flag': 'legend_star'},
        {'name': '时空守护者', 'description': '你成为了时空的守护者', 'age_range': (60, 80), 'effects': {'intelligence': 8}, 'requires': ['time_traveler'], 'special_flag': 'time_guardian'},
        {'name': '龙族长老', 'description': '你成为了龙族的长老', 'age_range': (55, 75), 'effects': {'strength': 8, 'intelligence': 4}, 'requires': ['dragon_blood'], 'special_flag': 'dragon_elder'},
        {'name': '系统创造者', 'description': '你成为了新系统的创造者', 'age_range': (50, 70), 'effects': {'intelligence': 10}, 'requires': ['system_host'], 'special_flag': 'system_creator'},
        {
            'name': '剑网三元老',
            'description': '你成为了剑网三社区的元老级人物',
            'age_range': (50, 70),
            'effects': {'intelligence': 2, 'appearance': 3},
            'requires': ['jx3_player'],
            'special_flag': 'jx3_veteran'
        },
        {
            'name': '武术宗师',
            'description': '你成为了一代武术宗师',
            'age_range': (55, 75),
            'effects': {'strength': 4, 'intelligence': 3, 'appearance': 2},
            'requires': ['martial_genius'],
            'special_flag': 'martial_master'
        },
        {
            'name': '文化传承者',
            'description': '你致力于传承中华传统文化',
            'age_range': (50, 80),
            'effects': {'intelligence': 4, 'appearance': 2},
            'requires': ['scholar_artist'],
            'special_flag': 'culture_inheritor'
        }
    ]
}

# 特殊结局系统
SPECIAL_ENDINGS = {
    'ascension': {
        'name': '修仙飞升',
        'description': '你突破了人类的极限，成功飞升成仙，获得了永恒的生命！',
        'condition': lambda game: 'ascension' in game.special_flags and game.attributes['intelligence'] >= 15,
        'score_bonus': 100
    },
    'isekai_king': {
        'name': '异世界王者',
        'description': '你在异世界建立了强大的王国，成为了传说中的异世界王者！',
        'condition': lambda game: 'isekai' in game.special_flags and game.attributes['intelligence'] >= 12 and game.attributes['strength'] >= 10,
        'score_bonus': 80
    },
    'world_richest': {
        'name': '世界首富',
        'description': '你凭借卓越的商业头脑和智慧，成为了世界首富！',
        'condition': lambda game: ('richest' in game.special_flags or game.attributes['wealth'] >= 20) and game.attributes['intelligence'] >= 12,
        'score_bonus': 70
    },
    'super_star': {
        'name': '超级巨星',
        'description': '你凭借出众的颜值和演技，成为了享誉全球的超级巨星！',
        'condition': lambda game: ('legend_star' in game.special_flags or game.attributes['appearance'] >= 18) and any('star_potential' in t.get('special', '') for t in game.talents),
        'score_bonus': 60
    },
    'mutation_monster': {
        'name': '变异怪物',
        'description': '由于体质过低和神秘实验的影响，你变成了可怕的变异怪物...',
        'condition': lambda game: 'mutation' in game.special_flags and game.attributes['strength'] <= 3,
        'score_bonus': -20
    },
    'ordinary_life': {
        'name': '平凡一生',
        'description': '你度过了平凡而普通的一生，虽然没有什么特别的成就，但也算是圆满。',
        'condition': lambda game: True,  # 默认结局
        'score_bonus': 0
    },
    'time_master': {
        'name': '时空主宰',
        'description': '你掌控了时空的力量，成为了时空的主宰者！',
        'condition': lambda game: 'time_guardian' in game.special_flags and game.attributes['intelligence'] >= 20,
        'score_bonus': 120
    },
    'dragon_emperor': {
        'name': '龙皇',
        'description': '你觉醒了完整的龙族血脉，成为了至高无上的龙皇！',
        'condition': lambda game: 'dragon_elder' in game.special_flags and game.attributes['strength'] >= 20,
        'score_bonus': 110
    },
    'system_god': {
        'name': '系统之神',
        'description': '你超越了系统的限制，成为了创造系统的神！',
        'condition': lambda game: 'system_creator' in game.special_flags and sum(game.attributes.values()) >= 50,
        'score_bonus': 130
    },
    'internet_legend': {
        'name': '网络传奇',
        'description': '你在网络世界中创造了无数传奇，成为了网络时代的象征！',
        'condition': lambda game: any(talent.get('special') in ['influencer', 'streamer', 'gamer'] for talent in game.talents) and game.attributes['appearance'] >= 15 and game.attributes['wealth'] >= 15,
        'score_bonus': 75
    },
    'culinary_master': {
        'name': '料理之神',
        'description': '你的厨艺达到了神的境界，被誉为料理之神！',
        'condition': lambda game: any(talent.get('special') in ['gourmet', 'chef'] for talent in game.talents) and game.attributes['intelligence'] >= 15 and game.attributes['wealth'] >= 12,
        'score_bonus': 65
    },
    'martial_saint': {
        'name': '武道圣人',
        'description': '你的武功达到了圣人境界，开创了新的武道流派！',
        'condition': lambda game: any('martial_arts' in talent.get('special', '') for talent in game.talents) and game.attributes['strength'] >= 18,
        'score_bonus': 85
    },
    'music_deity': {
        'name': '音乐之神',
        'description': '你的音乐才华震撼世界，被誉为音乐之神！',
        'condition': lambda game: any('music_genius' in talent.get('special', '') for talent in game.talents) and game.attributes['appearance'] >= 18 and game.attributes['intelligence'] >= 12,
        'score_bonus': 80
    },
    'invention_genius': {
        'name': '发明天才',
        'description': '你的发明改变了人类文明的进程，成为了史上最伟大的发明家！',
        'condition': lambda game: any('inventor' in talent.get('special', '') for talent in game.talents) and game.attributes['intelligence'] >= 20 and game.attributes['wealth'] >= 15,
        'score_bonus': 90
    },
    'failed_experiment': {
        'name': '实验失败',
        'description': '你在追求力量的过程中失败了，变成了不人不鬼的存在...',
        'condition': lambda game: 'mutation' in game.special_flags and sum(game.attributes.values()) <= 15,
        'score_bonus': -30
    },
    'jx3_legend': {
        'name': '剑网三传奇',
        'description': '你在剑网三的世界中创造了无数传奇，成为了江湖中的不朽神话！',
        'condition': lambda game: 'jx3_veteran' in game.special_flags and 'jx3_champion' in game.special_flags and game.attributes['intelligence'] >= 15,
        'score_bonus': 95
    },
    'sword_saint': {
        'name': '剑圣',
        'description': '你的剑道修为达到了圣人境界，被誉为当世剑圣！',
        'condition': lambda game: any('sword_master' in talent.get('special', '') for talent in game.talents) and game.attributes['strength'] >= 18 and game.attributes['intelligence'] >= 15,
        'score_bonus': 100
    },
    'jianghu_overlord': {
        'name': '江湖霸主',
        'description': '你统一了江湖，成为了武林盟主，号令天下！',
        'condition': lambda game: any('jianghu_legend' in talent.get('special', '') for talent in game.talents) and game.attributes['strength'] >= 16 and game.attributes['intelligence'] >= 14 and game.attributes['appearance'] >= 12,
        'score_bonus': 105
    },
    'tiancefu_general': {
        'name': '天策上将',
        'description': '你继承了天策府的荣光，成为了一代名将！',
        'condition': lambda game: any('tiancefuBloodline' in talent.get('special', '') for talent in game.talents) and game.attributes['strength'] >= 17 and game.attributes['intelligence'] >= 13,
        'score_bonus': 90
    },
    'chunyang_immortal': {
        'name': '纯阳真仙',
        'description': '你修成了纯阳道体，得道成仙！',
        'condition': lambda game: any('chunyang_dao' in talent.get('special', '') for talent in game.talents) and game.attributes['intelligence'] >= 20,
        'score_bonus': 110
    },
    'wanhua_sage': {
        'name': '万花医圣',
        'description': '你的医术达到了圣人境界，救死扶伤，功德无量！',
        'condition': lambda game: any('wanhua_doctor' in talent.get('special', '') for talent in game.talents) and game.attributes['intelligence'] >= 18 and game.attributes['wealth'] >= 12,
        'score_bonus': 95
    },
    'gaming_emperor': {
        'name': '游戏皇帝',
        'description': '你在游戏界建立了自己的帝国，成为了游戏界的传奇人物！',
        'condition': lambda game: any(talent.get('special') in ['jx3_player', 'game_master', 'gamer'] for talent in game.talents) and game.attributes['intelligence'] >= 16 and game.attributes['wealth'] >= 15,
        'score_bonus': 85
    },
    'cultural_master': {
        'name': '文化大师',
        'description': '你在文化艺术领域取得了巨大成就，成为了一代文化大师！',
        'condition': lambda game: 'culture_inheritor' in game.special_flags and game.attributes['intelligence'] >= 17 and game.attributes['appearance'] >= 14,
        'score_bonus': 88
    },
    'martial_emperor': {
        'name': '武道皇者',
        'description': '你的武功达到了前无古人的境界，成为了武道皇者！',
        'condition': lambda game: 'martial_master' in game.special_flags and game.attributes['strength'] >= 20 and game.attributes['intelligence'] >= 15,
        'score_bonus': 115
    },
    'virtual_reality_pioneer': {
        'name': '虚拟现实先驱',
        'description': '你推动了虚拟现实技术的发展，让游戏世界与现实完美融合！',
        'condition': lambda game: any(talent.get('special') in ['jx3_player', 'programmer', 'inventor'] for talent in game.talents) and game.attributes['intelligence'] >= 18 and game.attributes['wealth'] >= 16,
        'score_bonus': 100
    }
}

def get_random_talent():
    """根据稀有度随机获取天赋"""
    rand = random.random()
    if rand < 0.005:  # 0.5% SSR
        rarity = 'SSR'
    elif rand < 0.05:  # 4.5% SR
        rarity = 'SR'
    elif rand < 0.3:  # 25% R
        rarity = 'R'
    else:  # 70% N
        rarity = 'N'
    
    return random.choice(TALENTS[rarity]), rarity

def check_event_requirements(event, game):
    """检查事件是否满足触发条件"""
    if 'requires' not in event:
        return True
    
    for requirement in event['requires']:
        # 检查天赋要求
        if not any(requirement in talent.get('special', '') for talent in game.talents):
            # 检查特殊标记要求
            if requirement not in game.special_flags:
                return False
    return True

def determine_final_ending(game):
    """确定最终结局"""
    for ending_key, ending in SPECIAL_ENDINGS.items():
        if ending_key != 'ordinary_life' and ending['condition'](game):
            return ending_key
    return 'ordinary_life'

# 注册命令
start_life = on_regex(pattern=r"^人生重开$", priority=5)
allocate_points = on_regex(pattern=r"^分配属性\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$", priority=5)
start_simulation = on_regex(pattern=r"^开始模拟$", priority=5)
life_summary = on_regex(pattern=r"^人生总结$", priority=5)
# 添加查询剩余次数的命令
check_remaining = on_regex(pattern=r'^人生次数$', priority=1)

@check_remaining.handle()
async def handle_check_remaining(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    game_key = f"{group_id}_{user_id}"
    
    today = str(date.today())
    current_count = daily_game_count.get(today, {}).get(game_key, 0)
    remaining = MAX_DAILY_GAMES - current_count
    
    await check_remaining.finish(f"🎮 今日剩余游戏次数：{remaining}/{MAX_DAILY_GAMES}")

@start_life.handle()
async def handle_start_life(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    game_key = f"{group_id}_{user_id}"

    # 检查每日游戏次数
    today = str(date.today())
    if today not in daily_game_count:
        daily_game_count[today] = {}
    
    current_count = daily_game_count[today].get(game_key, 0)
    if current_count >= MAX_DAILY_GAMES:
        await start_life.finish(f"⚠️ 今日游戏次数已达上限（{MAX_DAILY_GAMES}次），请明天再来体验人生重开！")
        return

    # 游戏开始时增加计数
    daily_game_count[today][game_key] = current_count + 1
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 初始化游戏
    game_key = f"{group_id}_{user_id}"
    games[game_key] = LifeRestartGame()
    game = games[game_key]
    game.user_id = user_id
    game.group_id = group_id
    game.game_status = 'allocating'
    
    # 随机分配天赋
    talent, rarity = get_random_talent()
    game.talents.append(talent)
    
    # 应用天赋效果
    for attr, value in talent['effect'].items():
        game.attributes[attr] += value
        game.remaining_points -= value
    
    # 稀有度显示
    rarity_display = {
        'SSR': '✨✨✨ SSR ✨✨✨',
        'SR': '⭐⭐ SR ⭐⭐',
        'R': '⭐ R ⭐',
        'N': 'N'
    }
    
    message = f"🎭 {nickname} 的人生重开模拟器\n\n"
    message += f"🌟 获得天赋：{talent['name']} [{rarity_display[rarity]}]\n"
    message += f"📝 {talent['description']}\n\n"
    message += f"📊 当前属性：\n"
    message += f"👤 颜值：{game.attributes['appearance']}\n"
    message += f"🧠 智力：{game.attributes['intelligence']}\n"
    message += f"💪 体质：{game.attributes['strength']}\n"
    message += f"💰 家境：{game.attributes['wealth']}\n\n"
    message += f"🎯 剩余属性点：{game.remaining_points}\n\n"
    message += f"请使用【分配属性 颜值 智力 体质 家境】来分配剩余属性点\n"
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
        stage_events = []
        
        # 每个阶段随机发生2-5个事件
        num_events = random.randint(2, 5)
        available_events = LIFE_EVENTS.get(stage_name, [])
        
        for _ in range(num_events):
            if not available_events:
                break
                
            # 选择符合年龄范围和条件的事件
            valid_events = [e for e in available_events 
                          if start_age <= e['age_range'][1] and end_age >= e['age_range'][0] 
                          and check_event_requirements(e, game)]
            
            if not valid_events:
                # 如果没有特殊事件，从基础事件中选择
                valid_events = [e for e in available_events 
                              if start_age <= e['age_range'][1] and end_age >= e['age_range'][0] 
                              and 'requires' not in e]
            
            if not valid_events:
                continue
                
            event = random.choice(valid_events)
            event_age = random.randint(max(start_age, event['age_range'][0]), min(end_age, event['age_range'][1]))
            
            # 应用事件效果
            for attr, change in event['effects'].items():
                game.attributes[attr] = max(0, game.attributes[attr] + change)
            
            # 添加特殊标记
            if 'special_flag' in event:
                game.special_flags.add(event['special_flag'])
            
            stage_events.append((event_age, event))
            available_events.remove(event)  # 避免重复事件
        
        # 按年龄排序事件
        stage_events.sort(key=lambda x: x[0])
        
        # 添加到人生事件列表
        for age, event in stage_events:
            game.life_events.append((age, event))
    
    # 显示人生历程
    game.life_events.sort(key=lambda x: x[0])
    
    for age, event in game.life_events[:12]:  # 显示前12个重要事件
        message += f"📅 {age}岁：{event['description']}\n"
    
    if len(game.life_events) > 12:
        message += f"\n... 还有{len(game.life_events) - 12}个人生事件\n"
    
    # 计算最终属性和年龄
    final_age = random.randint(70, 95)
    # 长寿天赋效果
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