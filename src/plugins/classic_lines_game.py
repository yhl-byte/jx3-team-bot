'''
Author: yhl
Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-05 10:09:17
FilePath: /team-bot/jx3-team-bot/src/plugins/classic_lines_game.py
'''
# src/plugins/classic_lines_game.py
from nonebot import on_regex, on_command, on_message
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message
import random
import time
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from .game_score import update_player_score

# 游戏状态
class GameStatus(Enum):
    WAITING = "waiting"    # 等待开始
    SIGNUP = "signup"      # 报名中
    PLAYING = "playing"    # 游戏中
    ENDED = "ended"        # 已结束

@dataclass
class Player:
    user_id: str
    nickname: str
    score: int = 0
    correct_count: int = 0

@dataclass
class Question:
    line: str          # 台词
    work: str          # 作品名
    category: str      # 分类（电影/电视剧/动漫等）
    difficulty: int    # 难度等级 1-5

@dataclass
class ClassicLinesGame:
    group_id: str
    status: GameStatus = GameStatus.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    current_question: Optional[Question] = None
    question_queue: List[Question] = field(default_factory=list)
    current_question_index: int = 0
    start_time: Optional[float] = None
    question_start_time: Optional[float] = None
    game_duration: int = 180  # 3分钟
    question_timeout: int = 30  # 每题30秒超时
    skip_votes: Set[str] = field(default_factory=set)
    skip_threshold: int = 2   # 跳过投票阈值
    answered: bool = False
    game_timer: Optional[asyncio.Task] = None
    question_timer: Optional[asyncio.Task] = None

# 游戏实例存储
games: Dict[str, ClassicLinesGame] = {}

# 经典台词题库
CLASSIC_LINES = [
    # 电影类
    Question("生活就像一盒巧克力，你永远不知道下一颗是什么味道。", "阿甘正传", "电影", 2),
    Question("我会回来的！", "终结者", "电影", 1),
    Question("愿原力与你同在。", "星球大战", "电影", 2),
    Question("我是你爸爸！", "星球大战", "电影", 1),
    Question("我看到了，我征服了，我来了。", "角斗士", "电影", 3),
    Question("今晚，我们在地狱用餐！", "斯巴达300勇士", "电影", 3),
    Question("你好，我叫福雷斯特，福雷斯特·甘。", "阿甘正传", "电影", 2),
    Question("我想做一个好人。", "无间道", "电影", 2),
    Question("做人如果没有梦想，跟咸鱼有什么分别？", "少林足球", "电影", 2),
    Question("曾经有一份真诚的爱情放在我面前，我没有珍惜。", "大话西游", "电影", 1),
    
    # 电视剧类
    Question("我胡汉三又回来了！", "闪闪的红星", "电视剧", 3),
    Question("额滴神啊！", "武林外传", "电视剧", 1),
    Question("子曾经曰过。", "武林外传", "电视剧", 2),
    Question("我错了，我真的错了，我从一开始就不应该嫁过来。", "大宅门", "电视剧", 3),
    Question("臣妾做不到啊！", "甄嬛传", "电视剧", 1),
    Question("贱人就是矫情。", "甄嬛传", "电视剧", 2),
    Question("你是我的眼，带我领略四季的变换。", "还珠格格", "电视剧", 2),
    Question("山无棱，天地合，乃敢与君绝。", "还珠格格", "电视剧", 3),
    Question("我要这天，再遮不住我眼，要这地，再埋不了我心。", "悟空传", "电视剧", 4),
    Question("若我成佛，天下无魔，若我成魔，佛奈我何。", "悟空传", "电视剧", 4),
    
    # 动漫类
    Question("我要成为海贼王的男人！", "海贼王", "动漫", 1),
    Question("我要成为火影！", "火影忍者", "动漫", 1),
    Question("真相只有一个！", "名侦探柯南", "动漫", 1),
    Question("燃烧吧，我的小宇宙！", "圣斗士星矢", "动漫", 2),
    Question("我是要成为海贼王的男人！", "海贼王", "动漫", 1),
    Question("这就是青春啊！", "火影忍者", "动漫", 2),
    Question("人类的赞歌就是勇气的赞歌！", "JOJO的奇妙冒险", "动漫", 3),
    Question("欧拉欧拉欧拉！", "JOJO的奇妙冒险", "动漫", 2),
    Question("木大木大木大！", "JOJO的奇妙冒险", "动漫", 2),
    Question("我不要做人类了，JOJO！", "JOJO的奇妙冒险", "动漫", 3),
    
    # 经典国产剧
    Question("你是我的小呀小苹果。", "小苹果", "歌曲", 1),
    Question("葫芦娃，葫芦娃，一根藤上七朵花。", "葫芦兄弟", "动画", 1),
    Question("黑猫警长，黑猫警长，森林公民向你致敬。", "黑猫警长", "动画", 2),
    Question("一休哥，一休哥，聪明的一休哥。", "聪明的一休", "动画", 2),
    Question("大头儿子，小头爸爸。", "大头儿子小头爸爸", "动画", 1),
    Question("我们是害虫，我们是害虫。", "黑猫警长", "动画", 3),
    Question("马兰花，马兰花，风吹雨打都不怕。", "马兰花", "童话剧", 3),
    Question("孙悟空，孙悟空，本领真是大。", "西游记", "电视剧", 2),
    Question("白龙马，蹄朝西，驮着唐三藏跟着仨徒弟。", "西游记", "电视剧", 2),
    Question("敢问路在何方，路在脚下。", "西游记", "电视剧", 2),
    
    # 经典综艺
    Question("真香！", "变形计", "综艺", 1),
    Question("我不要你觉得，我要我觉得。", "中餐厅", "综艺", 2),
    Question("雨女无瓜。", "巴啦啦小魔仙", "电视剧", 2),
    Question("要你寡。", "巴啦啦小魔仙", "电视剧", 2),
    Question("古娜拉黑暗之神，呜呼啦呼，黑魔变身！", "巴啦啦小魔仙", "电视剧", 3),
    Question("我命由我不由天！", "哪吒之魔童降世", "电影", 2),
    Question("若命运不公，就和它斗到底！", "哪吒之魔童降世", "电影", 3),
    Question("我是小妖怪，逍遥又自在。", "哪吒之魔童降世", "电影", 2),
    
    # 更多经典台词
    Question("我可以接受失败，但绝对不能接受放弃。", "乔丹名言", "体育", 3),
    Question("生命诚可贵，爱情价更高，若为自由故，两者皆可抛。", "裴多菲诗歌", "文学", 4),
    Question("天生我材必有用，千金散尽还复来。", "将进酒", "古诗", 3),
    Question("路漫漫其修远兮，吾将上下而求索。", "离骚", "古诗", 4),
    Question("人生自古谁无死，留取丹心照汗青。", "过零丁洋", "古诗", 3),
    Question("海内存知己，天涯若比邻。", "送杜少府之任蜀州", "古诗", 3),
    Question("会当凌绝顶，一览众山小。", "望岳", "古诗", 3),
    Question("落红不是无情物，化作春泥更护花。", "己亥杂诗", "古诗", 4),
    Question("问君能有几多愁，恰似一江春水向东流。", "虞美人", "古诗", 4),
    Question("我要把这个提议给他一个无法拒绝的条件。", "教父", "电影", 3),
    Question("坦白说，亲爱的，我一点也不在乎。", "乱世佳人", "电影", 3),
    Question("我看见死人了。", "第六感", "电影", 2),
    Question("我是世界之王！", "泰坦尼克号", "电影", 2),
    Question("没有人把宝贝放在角落里。", "热舞", "电影", 3),
    Question("我感觉需要速度。", "壮志凌云", "电影", 2),
    Question("你不能处理真相！", "好人寥寥", "电影", 3),
    Question("我会找到你，我会杀了你。", "飓风营救", "电影", 2),
    Question("为什么这么严肃？", "蝙蝠侠：黑暗骑士", "电影", 2),
    Question("我是钢铁侠。", "钢铁侠", "电影", 1),
    Question("复仇者，集合！", "复仇者联盟", "电影", 1),
    Question("我可以做这一整天。", "美国队长", "电影", 2),
    Question("我是格鲁特。", "银河护卫队", "电影", 1),
    Question("瓦坎达万岁！", "黑豹", "电影", 2),
    Question("我爱你三千遍。", "复仇者联盟：终局之战", "电影", 2),
    Question("现实往往令人失望。", "复仇者联盟：无限战争", "电影", 2),
    Question("我注定要做这件事。", "复仇者联盟：终局之战", "电影", 3),
    Question("这不是你的错。", "心灵捕手", "电影", 3),
    Question("我看到了死人。", "第六感", "电影", 2),
    Question("你完成了我。", "甜心先生", "电影", 3),
    
    # 更多中国电影
    Question("我要这铁棒有何用！", "大话西游", "电影", 2),
    Question("爱你一万年。", "大话西游", "电影", 1),
    Question("我的意中人是个盖世英雄。", "大话西游", "电影", 2),
    Question("他好像一条狗啊。", "大话西游", "电影", 2),
    Question("左脚踩右脚。", "功夫", "电影", 2),
    Question("天下武功，唯快不破。", "功夫", "电影", 2),
    Question("还有谁！", "功夫", "电影", 1),
    Question("我要打十个！", "叶问", "电影", 2),
    Question("我要学功夫！", "功夫熊猫", "电影", 1),
    Question("昨天是历史，明天是谜团，但今天是礼物。", "功夫熊猫", "电影", 3),
    Question("师父，我准备好了。", "功夫熊猫", "电影", 2),
    Question("内心的平静。", "功夫熊猫", "电影", 2),
    Question("你的故事可能没有一个如此美好的开端，但这并不能决定你是谁。", "功夫熊猫2", "电影", 4),
    Question("我们都有过去，但过去不能定义我们。", "功夫熊猫3", "电影", 3),
    Question("做人要厚道。", "手机", "电影", 2),
    Question("21世纪什么最贵？人才！", "天下无贼", "电影", 2),
    Question("我最烦你们这些打劫的了，一点技术含量都没有。", "天下无贼", "电影", 3),
    Question("开好车的，不一定是好人。", "天下无贼", "电影", 2),
    Question("人心散了，队伍不好带啊。", "天下无贼", "电影", 3),
    Question("黎叔很生气，后果很严重。", "天下无贼", "电影", 2),
    
    # 更多电视剧台词
    Question("我还是从前那个少年，没有一丝丝改变。", "少年", "歌曲", 2),
    Question("你是我的神。", "来自星星的你", "电视剧", 2),
    Question("都教授，我爱你。", "来自星星的你", "电视剧", 2),
    Question("我的心脏只为你跳动。", "太阳的后裔", "电视剧", 3),
    Question("你是我的阳光。", "太阳的后裔", "电视剧", 2),
    Question("欧巴，撒浪嘿。", "韩剧通用", "电视剧", 1),
    Question("阿尼哈塞呦。", "韩剧通用", "电视剧", 1),
    Question("康桑密达。", "韩剧通用", "电视剧", 1),
    Question("我是你的女人。", "甄嬛传", "电视剧", 2),
    Question("皇上，您还记得大明湖畔的夏雨荷吗？", "还珠格格", "电视剧", 2),
    Question("容嬷嬷，你又拿针扎我！", "还珠格格", "电视剧", 2),
    Question("小燕子，你怎么可以这样对我！", "还珠格格", "电视剧", 2),
    Question("格格，您就饶了奴才吧！", "还珠格格", "电视剧", 2),
    Question("我要回家！", "还珠格格", "电视剧", 1),
    Question("紫薇，你怎么了紫薇！", "还珠格格", "电视剧", 2),
    Question("尔康，你不要走！", "还珠格格", "电视剧", 2),
    Question("我不是针对你，我是说在座的各位都是垃圾。", "中华小当家", "动漫", 3),
    Question("这个味道，是妈妈的味道。", "中华小当家", "动漫", 2),
    Question("料理是爱心。", "中华小当家", "动漫", 2),
    Question("我要成为特级厨师！", "中华小当家", "动漫", 2),
    
    # 更多动漫台词
    Question("我要成为最强的忍者！", "火影忍者", "动漫", 1),
    Question("我绝对不会放弃！", "火影忍者", "动漫", 2),
    Question("我要保护重要的人！", "火影忍者", "动漫", 2),
    Question("忍者的世界，没有后悔这两个字。", "火影忍者", "动漫", 3),
    Question("我要超越火影！", "火影忍者", "动漫", 2),
    Question("这就是我的忍道！", "火影忍者", "动漫", 2),
    Question("我要成为海贼王！", "海贼王", "动漫", 1),
    Question("我的伙伴，我来救你了！", "海贼王", "动漫", 2),
    Question("我要找到ONE PIECE！", "海贼王", "动漫", 2),
    Question("我要成为世界第一的剑豪！", "海贼王", "动漫", 2),
    Question("我要画出世界地图！", "海贼王", "动漫", 2),
    Question("我要成为勇敢的海上战士！", "海贼王", "动漫", 2),
    Question("我要找到ALL BLUE！", "海贼王", "动漫", 3),
    Question("我要治好所有的病！", "海贼王", "动漫", 2),
    Question("我要成为有用的人！", "海贼王", "动漫", 2),
    Question("我要看遍世界的历史！", "海贼王", "动漫", 2),
    Question("我要成为音乐家！", "海贼王", "动漫", 2),
    Question("我要重新与拉布相遇！", "海贼王", "动漫", 3),
    Question("我要帮助路飞成为海贼王！", "海贼王", "动漫", 2),
    Question("橡胶橡胶，火箭炮！", "海贼王", "动漫", 2),
    
    # 龙珠系列
    Question("我要变得更强！", "龙珠", "动漫", 1),
    Question("龟派气功波！", "龙珠", "动漫", 1),
    Question("我是超级赛亚人！", "龙珠", "动漫", 2),
    Question("这还不是我的最终形态！", "龙珠", "动漫", 2),
    Question("我要保护地球！", "龙珠", "动漫", 2),
    Question("召唤神龙吧！", "龙珠", "动漫", 2),
    Question("我要收集七颗龙珠！", "龙珠", "动漫", 2),
    Question("界王拳！", "龙珠", "动漫", 2),
    Question("元气弹！", "龙珠", "动漫", 2),
    Question("瞬间移动！", "龙珠", "动漫", 2),
    
    # 死神系列
    Question("我要保护所有人！", "死神", "动漫", 2),
    Question("卍解！", "死神", "动漫", 2),
    Question("月牙天冲！", "死神", "动漫", 2),
    Question("我要成为最强的死神！", "死神", "动漫", 2),
    Question("我要救出露琪亚！", "死神", "动漫", 2),
    Question("这就是我的斩魄刀！", "死神", "动漫", 2),
    Question("我要保护空座町！", "死神", "动漫", 3),
    Question("始解！", "死神", "动漫", 2),
    Question("我是代理死神！", "死神", "动漫", 2),
    Question("我要变强！", "死神", "动漫", 1),
    
    # 进击的巨人
    Question("我要杀光所有巨人！", "进击的巨人", "动漫", 2),
    Question("献出你的心脏！", "进击的巨人", "动漫", 2),
    Question("人类的反击开始了！", "进击的巨人", "动漫", 2),
    Question("我要看看墙外的世界！", "进击的巨人", "动漫", 2),
    Question("自由！", "进击的巨人", "动漫", 2),
    Question("我要保护人类！", "进击的巨人", "动漫", 2),
    Question("这个世界很残酷。", "进击的巨人", "动漫", 2),
    Question("我要夺回玛利亚之墙！", "进击的巨人", "动漫", 3),
    Question("我是进击的巨人！", "进击的巨人", "动漫", 2),
    Question("战斗！战斗！", "进击的巨人", "动漫", 1),
    
    # 鬼灭之刃
    Question("我要变强，保护妹妹！", "鬼灭之刃", "动漫", 2),
    Question("水之呼吸，一之型！", "鬼灭之刃", "动漫", 2),
    Question("我要成为鬼杀队的一员！", "鬼灭之刃", "动漫", 2),
    Question("我要让妹妹变回人类！", "鬼灭之刃", "动漫", 2),
    Question("全集中！", "鬼灭之刃", "动漫", 2),
    Question("我绝对不会让任何人死去！", "鬼灭之刃", "动漫", 2),
    Question("雷之呼吸，一之型，霹雳一闪！", "鬼灭之刃", "动漫", 3),
    Question("炎之呼吸！", "鬼灭之刃", "动漫", 2),
    Question("我要斩断这个悲伤的连锁！", "鬼灭之刃", "动漫", 3),
    Question("即使是鬼，也曾经是人。", "鬼灭之刃", "动漫", 3),
    
    # 咒术回战
    Question("我要拯救所有人！", "咒术回战", "动漫", 2),
    Question("我要成为最强的咒术师！", "咒术回战", "动漫", 2),
    Question("领域展开！", "咒术回战", "动漫", 2),
    Question("我是最强的！", "咒术回战", "动漫", 2),
    Question("咒术师的使命就是驱除咒灵！", "咒术回战", "动漫", 3),
    Question("我要保护同伴！", "咒术回战", "动漫", 2),
    Question("这就是我的咒术！", "咒术回战", "动漫", 2),
    Question("我要变得更强！", "咒术回战", "动漫", 1),
    Question("我不会让任何人死去！", "咒术回战", "动漫", 2),
    Question("咒力全开！", "咒术回战", "动漫", 2),
    # 古诗词名句
    Question("床前明月光，疑是地上霜。", "静夜思", "古诗", 1),
    Question("举头望明月，低头思故乡。", "静夜思", "古诗", 2),
    Question("春眠不觉晓，处处闻啼鸟。", "春晓", "古诗", 2),
    Question("夜来风雨声，花落知多少。", "春晓", "古诗", 2),
    Question("白日依山尽，黄河入海流。", "登鹳雀楼", "古诗", 2),
    Question("欲穷千里目，更上一层楼。", "登鹳雀楼", "古诗", 2),
    Question("两个黄鹂鸣翠柳，一行白鹭上青天。", "绝句", "古诗", 3),
    Question("窗含西岭千秋雪，门泊东吴万里船。", "绝句", "古诗", 3),
    Question("锄禾日当午，汗滴禾下土。", "悯农", "古诗", 1),
    Question("谁知盘中餐，粒粒皆辛苦。", "悯农", "古诗", 2),
    Question("离离原上草，一岁一枯荣。", "赋得古原草送别", "古诗", 2),
    Question("野火烧不尽，春风吹又生。", "赋得古原草送别", "古诗", 2),
    Question("慈母手中线，游子身上衣。", "游子吟", "古诗", 2),
    Question("临行密密缝，意恐迟迟归。", "游子吟", "古诗", 3),
    Question("谁言寸草心，报得三春晖。", "游子吟", "古诗", 3),
    Question("红豆生南国，春来发几枝。", "相思", "古诗", 2),
    Question("愿君多采撷，此物最相思。", "相思", "古诗", 3),
    Question("独在异乡为异客，每逢佳节倍思亲。", "九月九日忆山东兄弟", "古诗", 3),
    Question("遥知兄弟登高处，遍插茱萸少一人。", "九月九日忆山东兄弟", "古诗", 4),
    Question("君不见黄河之水天上来，奔流到海不复回。", "将进酒", "古诗", 3),
    
    # 更多古诗词
    Question("大江东去，浪淘尽，千古风流人物。", "念奴娇·赤壁怀古", "古诗", 4),
    Question("江山如画，一时多少豪杰。", "念奴娇·赤壁怀古", "古诗", 3),
    Question("人生如梦，一尊还酹江月。", "念奴娇·赤壁怀古", "古诗", 4),
    Question("明月几时有，把酒问青天。", "水调歌头", "古诗", 3),
    Question("不知天上宫阙，今夕是何年。", "水调歌头", "古诗", 3),
    Question("但愿人长久，千里共婵娟。", "水调歌头", "古诗", 3),
    Question("十年生死两茫茫，不思量，自难忘。", "江城子", "古诗", 4),
    Question("千里孤坟，无处话凄凉。", "江城子", "古诗", 4),
    Question("相顾无言，惟有泪千行。", "江城子", "古诗", 4),
    Question("料得年年肠断处，明月夜，短松冈。", "江城子", "古诗", 5),
    Question("寻寻觅觅，冷冷清清，凄凄惨惨戚戚。", "声声慢", "古诗", 4),
    Question("梧桐更兼细雨，到黄昏、点点滴滴。", "声声慢", "古诗", 4),
    Question("这次第，怎一个愁字了得！", "声声慢", "古诗", 4),
    Question("昨夜雨疏风骤，浓睡不消残酒。", "如梦令", "古诗", 3),
    Question("试问卷帘人，却道海棠依旧。", "如梦令", "古诗", 4),
    Question("知否，知否，应是绿肥红瘦。", "如梦令", "古诗", 3),
    Question("花自飘零水自流，一种相思，两处闲愁。", "一剪梅", "古诗", 4),
    Question("此情无计可消除，才下眉头，却上心头。", "一剪梅", "古诗", 4),
    Question("莫道不销魂，帘卷西风，人比黄花瘦。", "醉花阴", "古诗", 4),
    Question("东篱把酒黄昏后，有暗香盈袖。", "醉花阴", "古诗", 4),
    Question("我的心里只有你没有他。", "心里只有你没有他", "歌曲", 2),
    Question("爱你一万年。", "爱你一万年", "歌曲", 1),
    Question("月亮代表我的心。", "月亮代表我的心", "歌曲", 1),
    Question("甜蜜蜜，你笑得甜蜜蜜。", "甜蜜蜜", "歌曲", 1),
    Question("小城故事多，充满喜和乐。", "小城故事", "歌曲", 2),
    Question("我只在乎你，心甘情愿感染你的气息。", "我只在乎你", "歌曲", 2),
    Question("千言万语，说不完我对你的情意。", "千言万语", "歌曲", 2),
    Question("路边的野花不要采。", "路边的野花不要采", "歌曲", 1),
    Question("外面的世界很精彩。", "外面的世界", "歌曲", 1),
    Question("我的中国心。", "我的中国心", "歌曲", 1),
    Question("龙的传人。", "龙的传人", "歌曲", 1),
    Question("明天会更好。", "明天会更好", "歌曲", 1),
    Question("爱拼才会赢。", "爱拼才会赢", "歌曲", 1),
    Question("真心英雄。", "真心英雄", "歌曲", 1),
    Question("朋友一生一起走。", "朋友", "歌曲", 1),
    Question("那些年我们一起追的女孩。", "那些年", "歌曲", 2),
    Question("青春不留白。", "青春不留白", "歌曲", 2),
    Question("我们不一样。", "我们不一样", "歌曲", 1),
    Question("成都，带不走的只有你。", "成都", "歌曲", 2),
    Question("南山南，北海北。", "南山南", "歌曲", 2),
    
    # 经典童谣
    Question("两只老虎，两只老虎，跑得快。", "两只老虎", "童谣", 1),
    Question("小兔子乖乖，把门儿开开。", "小兔子乖乖", "童谣", 1),
    Question("一闪一闪亮晶晶，满天都是小星星。", "小星星", "童谣", 1),
    Question("世上只有妈妈好。", "世上只有妈妈好", "童谣", 1),
    Question("我爱北京天安门。", "我爱北京天安门", "童谣", 1),
    Question("让我们荡起双桨。", "让我们荡起双桨", "童谣", 1),
    Question("小燕子，穿花衣。", "小燕子", "童谣", 1),
    Question("春天在哪里呀，春天在哪里。", "春天在哪里", "童谣", 1),
    Question("蜗牛与黄鹂鸟。", "蜗牛与黄鹂鸟", "童谣", 1),
    Question("采蘑菇的小姑娘。", "采蘑菇的小姑娘", "童谣", 1),
    Question("小红帽。", "小红帽", "童谣", 1),
    Question("三个和尚。", "三个和尚", "童谣", 1),
    Question("小马过河。", "小马过河", "童谣", 1),
    Question("龟兔赛跑。", "龟兔赛跑", "童谣", 1),
    Question("小猫钓鱼。", "小猫钓鱼", "童谣", 1),
    Question("小蝌蚪找妈妈。", "小蝌蚪找妈妈", "童谣", 1),
    Question("丑小鸭。", "丑小鸭", "童谣", 1),
    Question("白雪公主。", "白雪公主", "童谣", 1),
    Question("灰姑娘。", "灰姑娘", "童谣", 1),
    Question("睡美人。", "睡美人", "童谣", 1),
    # 经典广告词
    Question("今年过节不收礼，收礼只收脑白金。", "脑白金广告", "广告", 2),
    Question("好迪真好，大家好才是真的好。", "好迪广告", "广告", 2),
    Question("钻石恒久远，一颗永流传。", "钻石广告", "广告", 2),
    Question("Just do it.", "耐克广告", "广告", 2),
    Question("I'm lovin' it.", "麦当劳广告", "广告", 2),
    Question("Think different.", "苹果广告", "广告", 2),
    Question("Impossible is nothing.", "阿迪达斯广告", "广告", 3),
    Question("The best or nothing.", "奔驰广告", "广告", 3),
    Question("Connecting people.", "诺基亚广告", "广告", 2),
    Question("Innovation for a better world.", "飞利浦广告", "广告", 3),
    Question("味道好极了！", "雀巢广告", "广告", 1),
    Question("农夫山泉有点甜。", "农夫山泉广告", "广告", 1),
    Question("怕上火，喝王老吉。", "王老吉广告", "广告", 1),
    Question("充电五分钟，通话两小时。", "OPPO广告", "广告", 2),
    Question("年轻，就要醒着拼。", "红牛广告", "广告", 2),
    Question("你的能量超乎你想象。", "红牛广告", "广告", 2),
    Question("困了累了喝红牛。", "红牛广告", "广告", 1),
    Question("妈妈再也不用担心我的学习。", "步步高广告", "广告", 2),
    Question("哪里不会点哪里。", "步步高广告", "广告", 1),
    Question("So easy，妈妈再也不用担心我的学习了。", "步步高广告", "广告", 2),
    # 经典游戏台词
    Question("All your base are belong to us.", "Zero Wing", "游戏", 4),
    Question("The cake is a lie.", "传送门", "游戏", 3),
    Question("Would you kindly?", "生化奇兵", "游戏", 3),
    Question("War never changes.", "辐射", "游戏", 3),
    Question("A man chooses, a slave obeys.", "生化奇兵", "游戏", 4),
    Question("Stay awhile and listen.", "暗黑破坏神", "游戏", 3),
    Question("You face Jaraxxus!", "炉石传说", "游戏", 3),
    Question("I need healing!", "守望先锋", "游戏", 2),
    Question("Heroes never die!", "守望先锋", "游戏", 2),
    Question("It's high noon.", "守望先锋", "游戏", 2),
    Question("Nerf this!", "守望先锋", "游戏", 2),
    Question("Justice rains from above!", "守望先锋", "游戏", 3),
    Question("Fire in the hole!", "守望先锋", "游戏", 2),
    Question("Cheers love, the cavalry's here!", "守望先锋", "游戏", 3),
    Question("Experience tranquility.", "守望先锋", "游戏", 3),
    Question("Die! Die! Die!", "守望先锋", "游戏", 2),
    Question("Ryuu ga waga teki wo kurau!", "守望先锋", "游戏", 4),
    Question("Hammer down!", "守望先锋", "游戏", 2),
    Question("I've got you in my sights.", "守望先锋", "游戏", 2),
    Question("Winky face!", "守望先锋", "游戏", 2),
    
    # 更多游戏台词
    Question("Waaagh!", "战锤40K", "游戏", 2),
    Question("For the Emperor!", "战锤40K", "游戏", 3),
    Question("Blood for the Blood God!", "战锤40K", "游戏", 3),
    Question("In the grim darkness of the far future, there is only war.", "战锤40K", "游戏", 4),
    Question("The Emperor protects.", "战锤40K", "游戏", 3),
    Question("Purge the heretics!", "战锤40K", "游戏", 3),
    Question("For the Greater Good!", "战锤40K", "游戏", 3),
    Question("Knowledge is power, guard it well.", "战锤40K", "游戏", 4),
    Question("An open mind is like a fortress with its gates unbarred.", "战锤40K", "游戏", 4),
    Question("Blessed is the mind too small for doubt.", "战锤40K", "游戏", 4),
    
    # 经典书籍名言
    Question("To be or not to be, that is the question.", "哈姆雷特", "文学", 4),
    Question("All animals are equal, but some animals are more equal than others.", "动物农场", "文学", 4),
    Question("It was the best of times, it was the worst of times.", "双城记", "文学", 4),
    Question("Big Brother is watching you.", "1984", "文学", 3),
    Question("War is peace. Freedom is slavery. Ignorance is strength.", "1984", "文学", 4),
    Question("All happy families are alike; each unhappy family is unhappy in its own way.", "安娜·卡列尼娜", "文学", 5),
    Question("Call me Ishmael.", "白鲸", "文学", 3),
    Question("It is a truth universally acknowledged...", "傲慢与偏见", "文学", 4),
    Question("In a hole in the ground there lived a hobbit.", "霍比特人", "文学", 3),
    Question("One ring to rule them all.", "指环王", "文学", 3),
    
    # 更多中文经典文学
    Question("满纸荒唐言，一把辛酸泪。", "红楼梦", "文学", 4),
    Question("都云作者痴，谁解其中味？", "红楼梦", "文学", 4),
    Question("假作真时真亦假，无为有处有还无。", "红楼梦", "文学", 4),
    Question("机关算尽太聪明，反算了卿卿性命。", "红楼梦", "文学", 4),
    Question("花谢花飞花满天，红消香断有谁怜？", "红楼梦", "文学", 4),
    Question("一朝春尽红颜老，花落人亡两不知。", "红楼梦", "文学", 4),
    Question("滚滚长江东逝水，浪花淘尽英雄。", "三国演义", "文学", 3),
    Question("是非成败转头空，青山依旧在，几度夕阳红。", "三国演义", "文学", 4),
    Question("古今多少事，都付笑谈中。", "三国演义", "文学", 3),
    Question("天下大势，分久必合，合久必分。", "三国演义", "文学", 3),

    Question("我会找到你，我会杀了你。", "飓风营救", "电影", 2),
    Question("Houston，我们有麻烦了。", "阿波罗13号", "电影", 3),
    Question("我看见死人了。", "第六感", "电影", 2),
    Question("没有人把宝贝放在角落里。", "热舞", "电影", 3),
    Question("我感觉需要速度。", "壮志凌云", "电影", 2),
    Question("你不能处理真相！", "好人寥寥", "电影", 3),
    Question("我是世界之王！", "泰坦尼克号", "电影", 1),
    Question("向无限和更远的地方！", "玩具总动员", "电影", 2),
    Question("我们需要一艘更大的船。", "大白鲨", "电影", 3),
    Question("我不是一个聪明人，但我知道什么是爱。", "阿甘正传", "电影", 2),
    Question("我要让他一个无法拒绝的提议。", "教父", "电影", 3),
    Question("毕竟，明天又是新的一天。", "乱世佳人", "电影", 3),
    Question("我们永远拥有巴黎。", "卡萨布兰卡", "电影", 4),
    Question("这里是约翰尼！", "闪灵", "电影", 2),
    Question("我觉得我们不在堪萨斯了。", "绿野仙踪", "电影", 3),
    Question("我要把他一个他无法拒绝的提议。", "教父", "电影", 3),
    Question("我们来这里是为了踢屁股和嚼泡泡糖...而我的泡泡糖用完了。", "他们活着", "电影", 4),
    Question("我要报仇！", "杀死比尔", "电影", 2),
    Question("我是你的父亲。", "星球大战", "电影", 1),
    Question("我们要去需要道路的地方。", "回到未来", "电影", 3),
    
    # 经典中国电影台词
    Question("我养你啊！", "喜剧之王", "电影", 1),
    Question("我要这天，再遮不住我眼。", "大话西游", "电影", 3),
    Question("一万年太久，只争朝夕。", "大话西游", "电影", 4),
    Question("我的意中人是个盖世英雄。", "大话西游", "电影", 2),
    Question("我猜中了前头，可是我猜不着这结局。", "大话西游", "电影", 3),
    Question("人生如戏，全靠演技。", "喜剧之王", "电影", 2),
    Question("我不是针对你，我是说在座的各位都是垃圾。", "古惑仔", "电影", 2),
    Question("出来混，迟早要还的。", "无间道", "电影", 1),
    Question("给我一个机会。", "无间道", "电影", 1),
    Question("我想知道，怎样才能让一个女人死心塌地爱上我？", "东邪西毒", "电影", 3),
    Question("人最痛苦的事，莫过于被人误解。", "霸王别姬", "电影", 3),
    Question("不疯魔不成活。", "霸王别姬", "电影", 2),
    Question("我本是男儿郎，又不是女娇娥。", "霸王别姬", "电影", 3),
    Question("师父说，人要往前看，千万不要回头。", "霸王别姬", "电影", 3),
    Question("我要这铁棒有何用！", "大圣归来", "电影", 2),
    
    # 经典电视剧台词
    Question("我要代表月亮消灭你！", "美少女战士", "动漫", 1),
    Question("我的忍道就是不会放弃！", "火影忍者", "动漫", 2),
    Question("我要成为更强的人！", "龙珠", "动漫", 1),
    Question("这就是我的忍道！", "火影忍者", "动漫", 2),
    Question("我绝对不会原谅你！", "龙珠", "动漫", 1),
    Question("我要保护重要的人！", "火影忍者", "动漫", 2),
    Question("我要变得更强！", "龙珠", "动漫", 1),
    Question("这就是青春！", "火影忍者", "动漫", 1),
    Question("我要超越极限！", "我的英雄学院", "动漫", 2),
    Question("Plus Ultra！", "我的英雄学院", "动漫", 2),
    
    # 经典国产电视剧
    Question("你是风儿我是沙，缠缠绵绵到天涯。", "还珠格格", "电视剧", 2),
    Question("天地良心，我紫薇真的没有骗你们！", "还珠格格", "电视剧", 2),
    Question("我还是从前那个少年，没有一丝丝改变。", "少年", "歌曲", 1),
    Question("容嬷嬷，你又拿针扎我！", "还珠格格", "电视剧", 1),
    Question("皇阿玛，您还记得大明湖畔的夏雨荷吗？", "还珠格格", "电视剧", 1),
    Question("我错了，我真的错了，我从一开始就不应该嫁过来。", "大宅门", "电视剧", 3),
    Question("我胡汉三又回来了！", "闪闪的红星", "电视剧", 3),
    Question("为了新中国，冲啊！", "董存瑞", "电影", 2),
    Question("同志们，为了胜利，向我开炮！", "英雄儿女", "电影", 3),
    Question("我是中国人民的儿子，我深情地爱着我的祖国和人民。", "邓小平", "电视剧", 4),
    
    # 武侠剧经典台词
    Question("侠之大者，为国为民。", "射雕英雄传", "电视剧", 3),
    Question("十步杀一人，千里不留行。", "侠客行", "小说", 4),
    Question("飞雪连天射白鹿，笑书神侠倚碧鸳。", "金庸作品", "小说", 4),
    Question("此情可待成追忆，只是当时已惘然。", "神雕侠侣", "电视剧", 4),
    Question("问世间情为何物，直教人生死相许。", "神雕侠侣", "电视剧", 3),
    Question("他强由他强，清风拂山岗。", "倚天屠龙记", "小说", 3),
    Question("武功再高，也怕菜刀。", "武林外传", "电视剧", 2),
    Question("葵花宝典，欲练神功，必先自宫。", "笑傲江湖", "小说", 3),
    Question("独孤求败，纵横江湖三十余载，杀尽仇寇，败尽英雄。", "神雕侠侣", "小说", 4),
    Question("桃花影落飞神剑，碧海潮生按玉箫。", "射雕英雄传", "小说", 4),
    
    # 动漫经典台词
    Question("我要成为海贼王！", "海贼王", "动漫", 1),
    Question("我是要成为海贼王的男人！", "海贼王", "动漫", 1),
    Question("我的伙伴绝对不会死！", "海贼王", "动漫", 2),
    Question("我要保护我的伙伴！", "海贼王", "动漫", 2),
    Question("我绝对不会让任何人死去！", "海贼王", "动漫", 2),
    Question("这就是我的正义！", "海贼王", "动漫", 2),
    Question("我要变得更强，强到没有人能够打败我！", "海贼王", "动漫", 2),
    Question("我的梦想是成为世界第一的剑豪！", "海贼王", "动漫", 2),
    Question("我要成为勇敢的海上战士！", "海贼王", "动漫", 2),
    Question("我要找到ALL BLUE！", "海贼王", "动漫", 2),
    
    # 宫斗剧经典台词
    Question("臣妾做不到啊！", "甄嬛传", "电视剧", 1),
    Question("贱人就是矫情。", "甄嬛传", "电视剧", 1),
    Question("小主吉祥。", "甄嬛传", "电视剧", 1),
    Question("皇上，您还记得大明湖畔的夏雨荷吗？", "还珠格格", "电视剧", 1),
    Question("本宫乏了。", "甄嬛传", "电视剧", 1),
    Question("姐姐，你好毒啊！", "甄嬛传", "电视剧", 2),
    Question("皇上，臣妾有罪。", "甄嬛传", "电视剧", 2),
    Question("这就是命。", "甄嬛传", "电视剧", 1),
    Question("我要你助我一臂之力。", "甄嬛传", "电视剧", 2),
    Question("你若安好，便是晴天。", "甄嬛传", "电视剧", 2),
    
    # 科幻电影台词
    Question("我会回来的。", "终结者", "电影", 1),
    Question("抵抗是徒劳的。", "星际迷航", "电影", 2),
    Question("这不是你要找的机器人。", "星球大战", "电影", 3),
    Question("愿原力与你同在。", "星球大战", "电影", 2),
    Question("我感觉到了原力的扰动。", "星球大战", "电影", 3),
    Question("这是一个陷阱！", "星球大战", "电影", 2),
    Question("我有一种不好的预感。", "星球大战", "电影", 2),
    Question("做还是不做，没有尝试。", "星球大战", "电影", 3),
    Question("恐惧导致愤怒，愤怒导致仇恨，仇恨导致痛苦。", "星球大战", "电影", 4),
    Question("我们需要去的地方，不需要道路。", "回到未来", "电影", 3),
    
    # 恐怖电影台词
    Question("他们来了！", "活死人之夜", "电影", 2),
    Question("我看见死人了。", "第六感", "电影", 2),
    Question("这里是约翰尼！", "闪灵", "电影", 2),
    Question("我们都在这里疯狂地漂浮。", "小丑回魂", "电影", 3),
    Question("你想玩游戏吗？", "电锯惊魂", "电影", 2),
    Question("我想玩一个游戏。", "电锯惊魂", "电影", 2),
    Question("游戏结束。", "电锯惊魂", "电影", 1),
    Question("你不能杀死恶魔。", "万圣节", "电影", 2),
    Question("他在你身后！", "黑色星期五", "电影", 1),
    Question("不要上楼！", "恐怖电影通用", "电影", 1),
    
    # 爱情电影台词
    Question("你好，我叫福雷斯特·甘。", "阿甘正传", "电影", 2),
    Question("我爱你，不是因为你是谁，而是因为我在你面前可以是谁。", "爱情电影", "电影", 3),
    Question("爱意味着永远不必说对不起。", "爱情故事", "电影", 3),
    Question("我希望我能退出你。", "断背山", "电影", 3),
    Question("没有人把宝贝放在角落里。", "热舞", "电影", 3),
    Question("你让我想成为一个更好的人。", "尽善尽美", "电影", 3),
    Question("我会找到你的。", "最后的莫希干人", "电影", 2),
    Question("你有我，我有你。", "泰坦尼克号", "电影", 2),
    Question("我永远不会放手，杰克。", "泰坦尼克号", "电影", 2),
    Question("我们永远拥有巴黎。", "卡萨布兰卡", "电影", 4),
    
    # 动作电影台词
    Question("我会找到你，我会杀了你。", "飓风营救", "电影", 2),
    Question("我有一套特殊的技能。", "飓风营救", "电影", 2),
    Question("我感觉需要速度。", "壮志凌云", "电影", 2),
    Question("我要报仇！", "杀死比尔", "电影", 2),
    Question("我是不可阻挡的力量。", "动作电影通用", "电影", 2),
    Question("这次是私人恩怨。", "动作电影通用", "电影", 2),
    Question("我太老了，不适合这个。", "致命武器", "电影", 2),
    Question("我会回来的。", "终结者", "电影", 1),
    Question("直到最后一滴血。", "第一滴血", "电影", 2),
    Question("我是法律！", "特警判官", "电影", 2),
    
    # 喜剧电影台词
    Question("我要做一个好人。", "喜剧之王", "电影", 2),
    Question("做人如果没有梦想，跟咸鱼有什么分别？", "少林足球", "电影", 2),
    Question("我养你啊！", "喜剧之王", "电影", 1),
    Question("人生如戏，全靠演技。", "喜剧之王", "电影", 2),
    Question("我是一个演员。", "喜剧之王", "电影", 1),
    Question("努力！奋斗！", "喜剧之王", "电影", 1),
    Question("我不是在教你诈，我是在教你认清现实。", "喜剧电影", "电影", 3),
    Question("笑一笑，十年少。", "喜剧通用", "电影", 1),
    Question("开心就好。", "喜剧通用", "电影", 1),
    Question("人生苦短，及时行乐。", "喜剧哲理", "电影", 2),
    
    # 经典小说台词
    Question("这是最好的时代，也是最坏的时代。", "双城记", "小说", 4),
    Question("生存还是毁灭，这是一个问题。", "哈姆雷特", "小说", 4),
    Question("人人生而平等。", "独立宣言", "文献", 3),
    Question("我思故我在。", "方法论", "哲学", 4),
    Question("知识就是力量。", "培根名言", "哲学", 3),
    Question("天生我材必有用。", "将进酒", "古诗", 3),
    Question("路漫漫其修远兮，吾将上下而求索。", "离骚", "古诗", 4),
    Question("人生自古谁无死，留取丹心照汗青。", "过零丁洋", "古诗", 3),
    Question("海内存知己，天涯若比邻。", "送杜少府之任蜀州", "古诗", 3),
    Question("会当凌绝顶，一览众山小。", "望岳", "古诗", 3),
    
    # 网络流行语和表情包
    Question("我太难了。", "网络流行语", "网络", 1),
    Question("真香！", "变形计", "综艺", 1),
    Question("我不要你觉得，我要我觉得。", "中餐厅", "综艺", 2),
    Question("好嗨哟！", "网络流行语", "网络", 1),
    Question("雨女无瓜。", "巴啦啦小魔仙", "电视剧", 2),
    Question("要你寡。", "巴啦啦小魔仙", "电视剧", 2),
    Question("我命由我不由天！", "哪吒之魔童降世", "电影", 2),
    Question("若命运不公，就和它斗到底！", "哪吒之魔童降世", "电影", 3),
    Question("我是小妖怪，逍遥又自在。", "哪吒之魔童降世", "电影", 2),
    Question("打败你的不是天真，是无鞋。", "网络流行语", "网络", 2),
    
    # 经典动画台词
    Question("葫芦娃，葫芦娃，一根藤上七朵花。", "葫芦兄弟", "动画", 1),
    Question("黑猫警长，黑猫警长。", "黑猫警长", "动画", 1),
    Question("一休哥，一休哥。", "聪明的一休", "动画", 1),
    Question("大头儿子，小头爸爸。", "大头儿子小头爸爸", "动画", 1),
    Question("我们是害虫，我们是害虫。", "黑猫警长", "动画", 2),
    Question("马兰花，马兰花，风吹雨打都不怕。", "马兰花", "童话", 2),
    Question("白龙马，蹄朝西。", "西游记", "动画", 2),
    Question("敢问路在何方，路在脚下。", "西游记", "电视剧", 2),
    Question("师父，师父！", "西游记", "电视剧", 1),
    Question("俺老孙来也！", "西游记", "电视剧", 1),
    
    # 更多经典台词
    Question("我可以接受失败，但绝对不能接受放弃。", "乔丹名言", "体育", 3),
    Question("生命诚可贵，爱情价更高。", "裴多菲诗歌", "文学", 4),
    Question("落红不是无情物，化作春泥更护花。", "己亥杂诗", "古诗", 4),
    Question("问君能有几多愁，恰似一江春水向东流。", "虞美人", "古诗", 4),
    Question("山重水复疑无路，柳暗花明又一村。", "游山西村", "古诗", 3),
    Question("春风得意马蹄疾，一日看尽长安花。", "登科后", "古诗", 3),
    Question("人生得意须尽欢，莫使金樽空对月。", "将进酒", "古诗", 3),
    Question("安能摧眉折腰事权贵，使我不得开心颜。", "梦游天姥吟留别", "古诗", 4),
    Question("长风破浪会有时，直挂云帆济沧海。", "行路难", "古诗", 3),
    Question("我劝天公重抖擞，不拘一格降人才。", "己亥杂诗", "古诗", 4)
]

# 开始游戏命令
start_game = on_regex(pattern=r'^开始台词$', priority=1)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 检查是否已有游戏在进行
    if group_id in games and games[group_id].status != GameStatus.WAITING and games[group_id].status != GameStatus.ENDED:
        await start_game.finish(message="台词大挑战游戏已经在进行中，请等待当前游戏结束")
        return
    
    # 创建新游戏
    games[group_id] = ClassicLinesGame(group_id=group_id)
    games[group_id].status = GameStatus.SIGNUP
    
    await start_game.finish(message="🎭 经典台词大挑战开始报名！\n请想参加的玩家发送「报名台词」或「jump」。\n发送「结束台词报名」开始游戏。\n⏰ 300秒后自动结束报名")
    
    # 300秒后自动结束报名
    await asyncio.sleep(300)
    
    if group_id in games and games[group_id].status == GameStatus.SIGNUP:
        if len(games[group_id].players) < 1:
            await bot.send_group_msg(group_id=int(group_id), message="报名人数不足，游戏取消")
            del games[group_id]
        else:
            await start_game_process(bot, group_id)

# 报名命令
signup_game = on_regex(pattern=r'^(报名台词|jump)$', priority=1)
@signup_game.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games or games[group_id].status != GameStatus.SIGNUP:
        await signup_game.finish(message="当前没有台词大挑战游戏正在报名")
        return
    
    if user_id in games[group_id].players:
        await signup_game.finish(message="你已经报名了")
        return
    
    # 添加玩家
    games[group_id].players[user_id] = Player(
        user_id=user_id,
        nickname=event.sender.nickname or f"玩家{len(games[group_id].players) + 1}"
    )
    
    msg = (
        MessageSegment.at(event.user_id) + 
        Message(f" {event.sender.nickname} 报名成功！当前已有 {len(games[group_id].players)} 人报名")
    )
    await signup_game.finish(message=Message(msg))

# 结束报名命令
end_signup = on_regex(pattern=r'^结束台词报名$', priority=1)
@end_signup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games or games[group_id].status != GameStatus.SIGNUP:
        await end_signup.finish(message="当前没有台词大挑战游戏正在报名")
        return
    
    if len(games[group_id].players) < 1:
        await end_signup.finish(message="报名人数不足，无法开始游戏")
        return
    
    await start_game_process(bot, group_id)

# 开始游戏流程
async def start_game_process(bot: Bot, group_id: str):
    game = games[group_id]
    game.status = GameStatus.PLAYING
    game.start_time = time.time()
    
    # 随机选择题目
    game.question_queue = random.sample(CLASSIC_LINES, min(20, len(CLASSIC_LINES)))
    game.current_question_index = 0
    
    await bot.send_group_msg(
        group_id=int(group_id), 
        message=f"🎭 台词大挑战开始！\n⏰ 游戏时长：3分钟\n👥 参与玩家：{len(game.players)}人\n\n准备好了吗？第一题即将开始..."
    )
    
    # 设置游戏计时器
    game.game_timer = asyncio.create_task(game_timer(bot, group_id))
    
    # 开始第一题
    await asyncio.sleep(3)
    await next_question(bot, group_id)

# 下一题
async def next_question(bot: Bot, group_id: str):
    game = games[group_id]
    
    # 检查游戏是否应该结束
    if game.status != GameStatus.PLAYING:
        return
    
    if game.current_question_index >= len(game.question_queue):
        await end_game(bot, group_id, "题目已全部完成")
        return
    
    # 获取当前题目
    game.current_question = game.question_queue[game.current_question_index]
    game.question_start_time = time.time()
    game.answered = False
    game.skip_votes.clear()
    
    # 发送题目
    question_msg = f"📝 第 {game.current_question_index + 1} 题\n\n💬 台词：{game.current_question.line}\n\n📚 类别：{game.current_question.category}\n\n🎯 请猜出这句台词出自哪部作品⏰ 30秒答题时间\n💡 发送 'next' 可发起跳过投票"
    
    await bot.send_group_msg(group_id=int(group_id), message=question_msg)
    
    # 设置题目计时器
    if game.question_timer:
        game.question_timer.cancel()
    game.question_timer = asyncio.create_task(question_timer(bot, group_id))

# 题目计时器
async def question_timer(bot: Bot, group_id: str):
    await asyncio.sleep(30)  # 30秒超时
    
    if group_id in games and games[group_id].status == GameStatus.PLAYING and not games[group_id].answered:
        game = games[group_id]
        await bot.send_group_msg(
            group_id=int(group_id), 
            message=f"⏰ 时间到！\n正确答案是：{game.current_question.work}\n分类：{game.current_question.category}"
        )
        
        # 进入下一题
        game.current_question_index += 1
        await asyncio.sleep(2)
        await next_question(bot, group_id)

# 游戏计时器
async def game_timer(bot: Bot, group_id: str):
    await asyncio.sleep(180)  # 3分钟
    
    if group_id in games and games[group_id].status == GameStatus.PLAYING:
        await end_game(bot, group_id, "游戏时间结束")

# 处理答案
answer_handler = on_message(priority=10)
@answer_handler.handle()
async def handle_answer(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    message = str(event.get_message()).strip()
    
    # 检查是否在游戏中
    if group_id not in games or games[group_id].status != GameStatus.PLAYING:
        return
    
    game = games[group_id]
    
    # 检查是否是参与者
    if user_id not in game.players:
        return
    
    # 检查是否已经有人答对
    if game.answered:
        return
    
    # 处理跳过投票
    if message.lower() == "next":
        await handle_skip_vote(bot, event, game)
        return
    
    # 检查答案
    if game.current_question and check_answer(message, game.current_question.work):
        game.answered = True
        
        # 取消题目计时器
        if game.question_timer:
            game.question_timer.cancel()
        
        # 计算得分
        time_bonus = max(0, 10 - int(time.time() - game.question_start_time) // 3)  # 最高10分，每3秒减1分
        difficulty_bonus = game.current_question.difficulty  # 难度1-4分
        base_score = 3  # 基础分降低到3分
        total_score = base_score + time_bonus + difficulty_bonus
        
        # 更新玩家分数
        game.players[user_id].score += total_score
        game.players[user_id].correct_count += 1
        
        # 发送正确消息
        msg = (
            MessageSegment.at(event.user_id) + 
            Message(f" 回答正确！🎉\n\n📝 答案：{game.current_question.work}\n🏆 获得积分：{total_score}分\n⏰ 用时奖励：{time_bonus}分\n⭐ 难度奖励：{difficulty_bonus}分")
        )
        await bot.send_group_msg(group_id=int(group_id), message=Message(msg))
        
        # 进入下一题
        game.current_question_index += 1
        await asyncio.sleep(3)
        await next_question(bot, group_id)

# 检查答案
def check_answer(user_answer: str, correct_answer: str) -> bool:
    """检查用户答案是否正确"""
    # 移除空格和标点符号，转换为小写进行比较
    import re
    
    def normalize(text: str) -> str:
        # 移除空格、标点符号
        text = re.sub(r'[\s\W]+', '', text)
        return text.lower()
    
    user_normalized = normalize(user_answer)
    correct_normalized = normalize(correct_answer)
    
    # 完全匹配
    if user_normalized == correct_normalized:
        return True
    
    # 包含匹配（用户答案包含正确答案或正确答案包含用户答案）
    if len(user_normalized) >= 2 and len(correct_normalized) >= 2:
        if user_normalized in correct_normalized or correct_normalized in user_normalized:
            return True
    
    return False

# 处理跳过投票
async def handle_skip_vote(bot: Bot, event: GroupMessageEvent, game: ClassicLinesGame):
    user_id = str(event.user_id)
    
    if user_id in game.skip_votes:
        return
    
    game.skip_votes.add(user_id)
    
    # 计算跳过阈值（单人游戏时1票即可，多人游戏时至少2人或参与人数的一半）
    if len(game.players) == 1:
        threshold = 1
    else:
        threshold = max(2, len(game.players) // 2)
    
    if len(game.skip_votes) >= threshold:
        # 跳过当前题目
        if game.question_timer:
            game.question_timer.cancel()
        
        await bot.send_group_msg(
            group_id=int(game.group_id), 
            message=f"⏭️ 题目已跳过\n正确答案是：{game.current_question.work}\n分类：{game.current_question.category}"
        )
        
        # 进入下一题
        game.current_question_index += 1
        await asyncio.sleep(2)
        await next_question(bot, game.group_id)
    else:
        msg = (
            MessageSegment.at(event.user_id) + 
            Message(f" 发起跳过投票 ({len(game.skip_votes)}/{threshold})")
        )
        await bot.send_group_msg(group_id=int(game.group_id), message=Message(msg))

# 结束游戏
async def end_game(bot: Bot, group_id: str, reason: str = ""):
    game = games[group_id]
    game.status = GameStatus.ENDED
    
    # 取消所有计时器
    if game.game_timer:
        game.game_timer.cancel()
    if game.question_timer:
        game.question_timer.cancel()
    
    # 计算最终排名
    sorted_players = sorted(game.players.values(), key=lambda p: (p.score, p.correct_count), reverse=True)
    
    # 更新积分
    try:
        for i, player in enumerate(sorted_players):
            # 排名奖励
            rank_bonus = 0
            if i == 0 and len(sorted_players) > 1:  # 第一名
                rank_bonus = 8
            elif i == 1 and len(sorted_players) > 2:  # 第二名
                rank_bonus = 5
            elif i == 2 and len(sorted_players) > 3:  # 第三名
                rank_bonus = 3
            
            # 参与奖励
            participation_bonus = 5
            
            # 答题奖励（已在答题时给予）
            total_bonus = rank_bonus + participation_bonus
            
            if total_bonus > 0:
                await update_player_score(
                    player.user_id,
                    group_id,
                    total_bonus,
                    'classic_lines',
                    f'第{i+1}名' if rank_bonus > 0 else '参与奖励',
                    'game_end'
                )
    except Exception as e:
        print(f"更新积分时出错：{str(e)}")
    
    # 生成结果消息
    result_msg = f"🎭 台词大挑战结束！\n{reason}\n\n🏆 最终排名：\n"
    
    for i, player in enumerate(sorted_players[:10]):  # 只显示前10名
        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        result_msg += f"{rank_emoji} {player.nickname}：{player.score}分 ({player.correct_count}题正确)\n"
    
    if len(sorted_players) > 10:
        result_msg += f"\n... 还有 {len(sorted_players) - 10} 名玩家\n"
    
    result_msg += f"\n📊 游戏统计：\n"
    result_msg += f"• 总题数：{game.current_question_index}题\n"
    result_msg += f"• 参与人数：{len(game.players)}人\n"
    
    if game.start_time:
        game_duration = int(time.time() - game.start_time)
        result_msg += f"• 游戏时长：{game_duration//60}分{game_duration%60}秒\n"
    
    await bot.send_group_msg(group_id=int(group_id), message=result_msg)
    
    # 清理游戏数据
    if group_id in games:
        del games[group_id]

# 强制结束游戏命令
force_end_game = on_regex(pattern=r'^强制结束台词$', priority=1)
@force_end_game.handle()
async def handle_force_end_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await force_end_game.finish(message="当前没有进行中的台词大挑战游戏")
        return
    
    # 检查是否是管理员
    try:
        admins = await bot.get_group_member_list(group_id=event.group_id)
        user_id = event.user_id
        is_admin = any(
            admin["user_id"] == user_id and 
            (admin["role"] in ["admin", "owner"]) 
            for admin in admins
        )
        
        if not is_admin:
            await force_end_game.finish(message="只有管理员才能强制结束游戏")
            return
    except:
        pass  # 如果获取管理员列表失败，允许任何人结束游戏
    
    if games[group_id].status != GameStatus.ENDED:
        await end_game(bot, group_id, "游戏被管理员强制结束")
    else:
        await force_end_game.finish(message="游戏已经结束")

# 查看游戏状态命令
check_game_status = on_regex(pattern=r'^台词状态$', priority=1)
@check_game_status.handle()
async def handle_game_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await check_game_status.finish(message="当前没有进行中的台词大挑战游戏")
        return
    
    game = games[group_id]
    status_text = ""
    
    if game.status == GameStatus.WAITING:
        status_text = "等待开始"
    elif game.status == GameStatus.SIGNUP:
        status_text = "报名中"
    elif game.status == GameStatus.PLAYING:
        status_text = f"游戏进行中，第{game.current_question_index + 1}题"
    elif game.status == GameStatus.ENDED:
        status_text = "已结束"
    
    player_count = len(game.players)
    
    msg = f"🎭 台词大挑战状态：{status_text}\n"
    msg += f"👥 玩家数量：{player_count}人\n"
    
    if game.status == GameStatus.PLAYING:
        if game.start_time:
            elapsed = int(time.time() - game.start_time)
            remaining = max(0, 180 - elapsed)
            msg += f"⏰ 剩余时间：{remaining//60}分{remaining%60}秒\n"
        
        if game.current_question:
            msg += f"📝 当前题目：{game.current_question.line[:20]}...\n"
        
        # 显示当前排名
        sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
        msg += "\n🏆 当前排名：\n"
        for i, player in enumerate(sorted_players[:5]):  # 只显示前5名
            msg += f"{i+1}. {player.nickname}：{player.score}分\n"
    
    await check_game_status.finish(message=msg)

# 台词大挑战帮助命令
lines_help = on_regex(pattern=r'^台词帮助$', priority=1)
@lines_help.handle()
async def handle_lines_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    help_msg = """🎭 经典台词大挑战指令说明：

🎮 游戏指令：
• 开始台词 - 开始新游戏并进入报名阶段
• 报名台词 / jump - 报名参加游戏
• 结束台词报名 - 提前结束报名阶段并开始游戏
• next - 在游戏中发起跳过当前题目的投票
• 台词状态 - 查看当前游戏状态
• 强制结束台词 - 强制结束当前游戏（仅管理员）
• 台词帮助 - 显示此帮助信息

🎯 游戏规则：
• 游戏时长：3分钟
• 每题答题时间：30秒
• 机器人会发出经典台词，玩家需要猜出作品名
• 答对可获得积分，用时越短奖励越高
• 发送 'next' 可发起跳过投票（需要多人同意）

🏆 积分规则：
• 答对基础分：10分
• 用时奖励：最高30分（答题越快奖励越高）
• 难度奖励：根据题目难度给予2-10分
• 排名奖励：第1名+20分，第2名+15分，第3名+10分
• 参与奖励：+5分

📚 题目类型：
• 电影经典台词
• 电视剧经典台词  
• 动漫经典台词
• 经典歌曲
• 古诗词名句
• 综艺
• 等等...
"""
    await lines_help.finish(message=help_msg)