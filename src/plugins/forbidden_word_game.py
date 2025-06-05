'''
Author: yhl
Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-05 17:31:23
FilePath: /team-bot/jx3-team-bot/src/plugins/forbidden_word_game.py
'''
# src/plugins/forbidden_word_game.py
from nonebot import on_regex, on_command, on_message
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message, PrivateMessageEvent
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
    forbidden_word: str = ""  # 分配给该玩家的禁词
    violation_count: int = 0  # 违规次数（说了自己禁词的次数）
    score: int = -10  # 基础分数20分

@dataclass
class ForbiddenWordGame:
    group_id: str
    status: GameStatus = GameStatus.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    start_time: Optional[float] = None
    game_duration: int = 300  # 5分钟
    game_timer: Optional[asyncio.Task] = None
    used_words: Set[str] = field(default_factory=set)  # 已使用的词汇

# 游戏实例存储
games: Dict[str, ForbiddenWordGame] = {}

# 禁词词库（500个词汇）
FORBIDDEN_WORDS = [
    # 日常用词
    "你好", "谢谢", "不客气", "对不起", "没关系", "再见", "晚安", "早安", "中午好", "下午好",
    "是的", "不是", "可以", "不可以", "好的", "不好", "喜欢", "不喜欢", "想要", "不想要",
    "吃饭", "睡觉", "工作", "学习", "休息", "玩游戏", "看电影", "听音乐", "运动", "散步",
    "开心", "难过", "生气", "紧张", "兴奋", "无聊", "累了", "饿了", "渴了", "困了",
    "猜词","开口中","猜歌", "21","卧底",
    
    # 网络用语
    "哈哈", "呵呵", "嘿嘿", "嘻嘻", "哇", "哦", "啊", "嗯", "额", "呃",
    "666", "牛逼", "厉害", "赞", "棒", "强", "弱", "菜", "垃圾", "渣",
    "笑死", "绝了", "服了", "醉了", "疯了", "傻了", "懵了", "蒙了", "晕了", "崩了",
    "真的", "假的", "骗人", "认真", "开玩笑", "搞笑", "有趣", "无聊", "奇怪", "正常",

    "紫气东来", "万剑归宗", "太极无极", "两仪万象", "坐忘无我", "吞吴", 
    "风来吴山", "泉凝月", "听雷", "云飞玉皇", "风车", "蝶弄足", "左旋右转", "风袖低昂", "王母挥袂", 
    "醉舞九天", "龙翔凤舞", "剑影留痕", "剑破虚空", "剑主天地", "虎跑", "黄龙吐翠", "峰插云景", 
    "鹤归孤山", "夕照雷峰", "锻骨诀", "守如山", "啸如虎", 
    "阴性内功", "阳性内功", "混元性内功", "毒经", "补天诀", "千丝", "百足", "蟾啸", "枯残蛊", 
    "圣手织天", "冰蚕牵丝", "蛊惑众生", "夺命蛊", "天蛛引", "献祭", "化血镖", "图穷匕见", 
    "暴雨梨花针", "心无旁骛", "惊羽诀", "天罗诡道", "飞星遁影", "鬼斧神工", "千机变", "鲲鹏铁爪", 
    "光明相", "生灭予夺", "贪魔体", "驱夜断愁", "流光囚影", "生死劫", "戒火斩", "净世破魔击", 
    "降龙掌", "亢龙有悔", "龙跃于渊", "烟雨行", "笑醉狂", "酒中仙", "蜀犬吠日", "龙战于野", 
    "雪龙卷", "坚壁清野", "盾飞", "盾立", "盾猛", "盾刀", "血怒", "捍卫", 
    "项王击鼎", "破釜沉舟", "醉斩白蛇", "西楚悲歌", "上将军印", "秀明尘身", 
    "北傲诀", "莫问", "相知", "高山流水", "阳春白雪", "孤影化双", "长歌门", "孤影", "梅花三弄", 
    "江逐月天", "回梦逐光", "凌雪阁", "隐雷鞭", "血滴子", "盾壁", "孤影化双", "隐雷鞭", "千枝绽蕊", "列卦", 
    "寂洪荒", "斩无常", "金戈药篓", "银光照雪", "药宗", "灵素", "无方", "千枝绽蕊", "七叶灵芝", 
    "活络散", "逆阴阳", "龙葵", "彼针", "衍天宗", "奇门遁甲", 
    "鬼星开穴",  "斗转星移", "九字诀", "刀宗", "孤锋诀", "绝风尘", 
    "破浪三叠", "腾空剑法", "秀水剑法",  "霞流宝石", 
    "冰心诀", "云裳心经", "镇山河", "舍身", "弘法","秦始皇",

    "花萝", "818","叶英", "李承恩", "陆危楼", 
            "王遗风", "谢渊", "柳风骨", "郭炜炜", "沈剑心", "穆玄英", "莫雨", "陈月", "源明雅", 
            "多多", "阿萨辛", "令狐伤", "苏曼莎", "方乾", "东方宇轩", "曲云", "孙飞亮", "唐简", "肖药儿", 
            "高绛婷", "琴魔", "剑圣", "曹雪阳", "李复", "秋叶青", "玄晶","咕咕", "鸽子", "排骨", "金团", 
            "老板", "打工", "躺拍", "李倓", "柳静海", "王玄砚", "卢延鹤", "拓跋思南", "无名","宫傲", "独孤求败", 
            "谢云流", "康雪烛", "慕容追风",  "董先生", "雨轻尘‌", "喜雅","‌鹰眼客","赤幽明",
    
    # 情感表达
    "爱你", "想你", "恨你", "讨厌", "喜欢", "爱", "恨", "情", "心", "梦",
    "美", "丑", "帅", "漂亮", "可爱", "萌", "酷", "帅气", "美丽", "丑陋",
    "温柔", "暴躁", "善良", "邪恶", "聪明", "愚蠢", "勇敢", "胆小", "大方", "小气",
    
    # 动作词汇
    "走", "跑", "跳", "飞", "游", "爬", "坐", "站", "躺", "蹲",
    "看", "听", "说", "想", "做", "玩", "买", "卖", "给", "拿",
    "打", "踢", "推", "拉", "抱", "亲", "摸", "碰", "撞", "挤",
    
    # 时间词汇
    "今天", "明天", "昨天", "现在", "以前", "以后", "早上", "中午", "下午", "晚上",
    "春天", "夏天", "秋天", "冬天", "周一", "周二", "周三", "周四", "周五", "周六", "周日",
    "一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月",
    
    # 地点词汇
    "家", "学校", "公司", "医院", "银行", "超市", "餐厅", "电影院", "公园", "图书馆",
    
    # 食物词汇
    "米饭", "面条", "包子", "饺子", "馒头", "面包", "蛋糕", "饼干", "糖果", "巧克力",
    "苹果", "香蕉", "橙子", "葡萄", "草莓", "西瓜", "桃子", "梨", "樱桃", "柠檬",
    "鸡肉", "猪肉", "牛肉", "鱼肉", "虾", "蟹", "鸡蛋", "牛奶", "豆腐", "青菜",
    
    # 颜色词汇
    "红色", "橙色", "黄色", "绿色", "蓝色", "紫色", "黑色", "白色", "灰色", "粉色",
    "红", "橙", "黄", "绿", "蓝", "紫", "黑", "白", "灰", "粉",
    
    # 数字词汇
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "零", "百", "千", "万", "亿", "第一", "第二", "第三", "最后", "倒数",
    
    # 动物词汇
    "猫", "狗", "鸟", "鱼", "马", "牛", "羊", "猪", "鸡", "鸭",
    "老虎", "狮子", "大象", "熊猫", "猴子", "兔子", "老鼠", "蛇", "龙", "凤凰",
    
    # 物品词汇
    "手机", "电脑", "电视", "汽车", "自行车", "书", "笔", "纸", "杯子", "盘子",
    "衣服", "裤子", "鞋子", "帽子", "包", "钱", "钥匙", "眼镜", "手表", "项链",
    
    # 天气词汇
    "晴天", "阴天", "雨天", "雪天", "风", "雷", "闪电", "彩虹", "云", "太阳",
    "热", "冷", "温暖", "凉爽", "潮湿", "干燥", "舒服", "难受", "清爽", "闷热",
    
    # 学习工作
    "老师", "学生", "同学", "朋友", "同事", "老板", "员工", "客户", "医生", "护士",
    "考试", "作业", "课程", "会议", "项目", "任务", "计划", "目标", "成功", "失败",
    
    # 娱乐词汇
    "游戏", "电影", "音乐", "小说", "漫画", "动画", "综艺", "新闻", "体育", "旅游",
    "唱歌", "跳舞", "画画", "写字", "拍照", "录像", "直播", "聊天", "购物", "做饭",
    
    # 身体部位
    "头", "脸", "眼睛", "鼻子", "嘴巴", "耳朵", "脖子", "肩膀", "手", "脚",
    "胳膊", "腿", "手指", "脚趾", "心脏", "大脑", "肚子", "背", "胸", "腰",
    
    # 家庭关系
    "爸爸", "妈妈", "爷爷", "奶奶", "哥哥", "姐姐", "弟弟", "妹妹", "儿子", "女儿",
    "丈夫", "妻子", "男朋友", "女朋友", "叔叔", "阿姨", "舅舅", "姑姑", "表哥", "表姐",
    
    # 交通工具
    "飞机", "火车", "汽车", "公交车", "地铁", "出租车", "自行车", "摩托车", "船", "轮船",
    
    # 建筑物
    "房子", "楼房", "别墅", "公寓", "宿舍", "酒店", "商店", "工厂", "学校", "医院",
    
    # 自然现象
    "山", "水", "河", "湖", "海", "树", "花", "草", "石头", "土",
    "火", "冰", "雪", "雨", "风", "雷", "电", "光", "影", "声音",
    
    # 抽象概念
    "时间", "空间", "速度", "力量", "智慧", "勇气", "希望", "梦想", "理想", "现实",
    "过去", "现在", "未来", "开始", "结束", "成功", "失败", "胜利", "失败", "平等",
    
    # 网络游戏术语
    "升级", "装备", "技能", "经验", "金币", "钻石", "充值", "氪金", "肝", "佛系",
    "大佬", "萌新", "菜鸟", "高手", "神仙", "外挂", "bug", "更新", "维护", "公测",
    
    # 流行语
    "yyds", "绝绝子", "芭比Q", "栓Q", "躺平", "内卷", "摸鱼", "划水", "打工人", "社畜",
    "凡尔赛", "破防", "emo", "ptsd", "CPU", "DNA", "YYDS", "DDDD", "awsl", "xswl",

    # 剑网三相关词汇（200个）
    # 门派相关
    "纯阳", "七秀", "少林", "万花", "天策", "藏剑", "五毒", "唐门", "明教", "苍云",
    "长歌", "霸刀", "蓬莱", "凌雪", "衍天", "药宗", "刀宗", "无方", "太虚", "相知",
    "北天药宗", "万灵山庄", "段氏", "丐帮", "逍遥", "天山", "星宿", "慕容", "鸠摩智", "虚竹",
    
    # 技能招式
    "太极剑", "紫霞功", "易筋经", "洗髓经", "九阳神功", "乾坤大挪移", "降龙十八掌", "打狗棒法",
    "凌波微步", "北冥神功", "小无相功", "天山六阳掌", "生死符", "化功大法", "星宿老仙", "神木王鼎",
    "焚影圣诀", "山居剑意", "太虚剑意", "问水诀", "离经易道", "花间游", "惊羽诀", "花萝",
    "傲血战意", "铁骨衣", "分山劲", "莫问", "无我", "破苍穹", "凌海诀", "隐龙诀",
    
    # 地图场景
    "扬州", "洛阳", "成都", "长安", "稻香村", "枫华谷", "竹海", "巴陵", "荻花", "昆仑",
    "乌蒙贵", "秦岭", "雁门关", "剑冢", "天子峰", "太原", "幽州", "燕云", "大漠", "河西瀚漠",
    "江南", "江湖", "中原", "塞外",
    "蝶恋花", "梦江南", "水龙吟", "念奴娇", "满江红", "唯我独尊", 
    
    # 装备道具
    "倚天剑", "屠龙刀", "玄铁重剑", "君子剑", "淑女剑", "碧血剑", "金蛇剑", "辟邪剑谱", "葵花宝典", "九阴真经",
    "九阳真经", "太玄经", "神照经", "易筋经", "洗髓经", "龙象般若功", "小无相功", "北冥神功", "凌波微步", "天山六阳掌",
    
    # 江湖用语
    "侠客", "大侠", "少侠", "女侠", "剑客", "刀客", "枪客", "拳师", "掌门", "长老",
    "弟子", "师父", "师兄", "师姐", "师弟", "师妹", "同门", "师叔", "师伯", "师祖",
    "武林", "江湖", "武功", "内功", "外功", "轻功", "剑法", "刀法", "掌法", "拳法",
    "腿法", "指法", "爪法", "鞭法", "棍法", "枪法", "暗器", "毒功", "医术", "易容",
    "点穴", "解穴", "封穴", "推拿", "按摩", "针灸", "把脉", "诊断", "治疗", "疗伤",
    
    # 游戏术语
    "副本", "团本", "日常", "周常", "活动", "任务", "主线", "支线", "奇遇", "成就",
    "称号", "坐骑", "宠物", "外观", "时装", "染色", "强化", "精炼", "镶嵌", "附魔",
    "属性", "攻击", "防御", "血量", "内力", "命中", "闪避", "暴击", "韧性", "破防",
    "会心", "无双", "破招", "招架", "拆招", "格挡", "反击", "连击", "必杀", "绝技",
    "秘籍", "心法", "奇穴", "经脉", "修为", "境界", "等级", "经验", "声望", "威望",
    "帮派", "师门", "阵营", "势力", "联盟", "敌对", "中立", "友好", "崇拜", "仇恨",
    "PK", "PVP", "PVE", "DPS", "T", "奶妈", "输出", "坦克", "治疗", "辅助",
    "开荒", "首杀", "通关", "刷本", "刷怪", "练级", "升级", "转职", "转门派", "洗点"
]

# 开始游戏命令（支持自定义时长）
start_game = on_regex(pattern=r'^开始害你在心口难开(?:\s+(\d+)分钟?)?$', priority=1)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id in games and games[group_id].status != GameStatus.ENDED:
        await start_game.finish(message="当前已有游戏在进行中，请等待结束后再开始新游戏")
        return
    
    # 解析游戏时长
    message_text = str(event.get_message()).strip()
    import re
    match = re.match(r'^开始害你在心口难开(?:\s+(\d+)分钟?)?$', message_text)
    
    game_duration = 300  # 默认5分钟
    if match and match.group(1):
        custom_duration = int(match.group(1))
        if 1 <= custom_duration <= 30:  # 限制1-30分钟
            game_duration = custom_duration * 60
        else:
            await start_game.finish(message="游戏时长必须在1-30分钟之间")
            return
    
    # 创建新游戏
    games[group_id] = ForbiddenWordGame(group_id=group_id, status=GameStatus.SIGNUP, game_duration=game_duration)
    
    duration_text = f"{game_duration // 60}分钟"
    
    msg = "🚫 害你在心口难开游戏开始报名！\n\n"
    msg += "🎮 游戏规则：\n"
    msg += "• 每位玩家会被分配一个禁词\n"
    msg += "• 机器人会私聊告诉你其他人的禁词\n"
    msg += f"• 游戏时间{duration_text}，在群聊中正常聊天\n"
    msg += "• 说了自己禁词的玩家会被扣分\n\n"
    msg += "💰 积分规则：\n"
    msg += "• 基础参与分：-10分\n"
    msg += "• 每说一次自己的禁词：-5分\n\n"
    msg += "📝 发送 '报名害你' 或 '报名禁词' 参加游戏\n"
    msg += "⏰ 300秒后自动开始游戏，或发送 '开始禁词游戏' 立即开始"
    
    await start_game.send(message=msg)
    
    # 30秒后自动开始游戏
    await asyncio.sleep(300)
    if group_id in games and games[group_id].status == GameStatus.SIGNUP:
        await start_playing(bot, group_id)

# 报名命令
signup_game = on_regex(pattern=r'^(报名害你|报名禁词)$', priority=1)
@signup_game.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games:
        await signup_game.finish(message="当前没有进行中的害你在心口难开游戏，发送 '开始害你在心口难开' 开始新游戏")
        return
    
    if games[group_id].status != GameStatus.SIGNUP:
        await signup_game.finish(message="当前游戏不在报名阶段")
        return
    
    if user_id in games[group_id].players:
        await signup_game.finish(message="你已经报名了")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('card') or user_info.get('nickname', f"用户{user_id}")
    except:
        nickname = f"用户{user_id}"
    
    # 添加玩家
    games[group_id].players[user_id] = Player(user_id=user_id, nickname=nickname)
    
    player_count = len(games[group_id].players)
    await signup_game.send(message=f"✅ {nickname} 报名成功！当前玩家数：{player_count}人")

# 立即开始游戏命令
start_playing_cmd = on_regex(pattern=r'^结束禁词报名$', priority=1)
@start_playing_cmd.handle()
async def handle_start_playing(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await start_playing_cmd.finish(message="当前没有进行中的害你在心口难开游戏")
        return
    
    if games[group_id].status != GameStatus.SIGNUP:
        await start_playing_cmd.finish(message="当前游戏不在报名阶段")
        return
    
    await start_playing(bot, group_id)

# 开始游戏逻辑
async def start_playing(bot: Bot, group_id: str):
    game = games[group_id]
    
    if len(game.players) < 2:
        await bot.send_group_msg(group_id=int(group_id), message="参与人数不足2人，游戏取消")
        del games[group_id]
        return
    
    # 分配禁词
    available_words = [word for word in FORBIDDEN_WORDS if word not in game.used_words]
    if len(available_words) < len(game.players):
        available_words = FORBIDDEN_WORDS.copy()  # 如果词汇不够，重新使用所有词汇
        game.used_words.clear()
    
    selected_words = random.sample(available_words, len(game.players))
    
    for i, (user_id, player) in enumerate(game.players.items()):
        player.forbidden_word = selected_words[i]
        game.used_words.add(selected_words[i])
    
    # 私聊发送其他人的禁词
    for user_id, player in game.players.items():
        other_players_words = []
        for other_user_id, other_player in game.players.items():
            if other_user_id != user_id:
                other_players_words.append(f"{other_player.nickname}：{other_player.forbidden_word}")
        
        private_msg = "🚫 害你在心口难开 - 其他玩家的禁词：\n\n"
        private_msg += "\n".join(other_players_words)
        # private_msg += f"\n\n⚠️ 你的禁词是：{player.forbidden_word}\n"
        # private_msg += "记住不要在群里说出你的禁词哦！"
        
        try:
            await bot.send_private_msg(user_id=int(user_id), message=private_msg)
        except:
            # 如果私聊失败，在群里提醒
            await bot.send_group_msg(group_id=int(group_id), 
                                   message=f"⚠️ 无法向 {player.nickname} 发送私聊消息，请确保已添加机器人为好友")
    
    # 更新游戏状态
    game.status = GameStatus.PLAYING
    game.start_time = time.time()
    
    # 发送游戏开始消息
    duration_text = f"{game.game_duration // 60}分钟"
    msg = "🎮 害你在心口难开游戏开始！\n\n"
    msg += f"👥 参与玩家：{len(game.players)}人\n"
    msg += f"⏰ 游戏时间：{duration_text}\n\n"
    msg += "📝 已私聊发送其他玩家的禁词\n"
    msg += "💬 现在开始自由聊天，注意不要说出自己的禁词！\n\n"
    msg += "参与玩家：" + "、".join([p.nickname for p in game.players.values()])
    
    await bot.send_group_msg(group_id=int(group_id), message=msg)
    
    # 设置游戏计时器
    game.game_timer = asyncio.create_task(game_timer(bot, group_id))

# 游戏计时器
async def game_timer(bot: Bot, group_id: str):
    if group_id in games:
        await asyncio.sleep(games[group_id].game_duration)  # 使用自定义时长
        if group_id in games and games[group_id].status == GameStatus.PLAYING:
            await end_game(bot, group_id)

# 监听群消息，检测禁词
message_monitor = on_message(priority=10)
@message_monitor.handle()
async def handle_message_monitor(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    if group_id not in games or games[group_id].status != GameStatus.PLAYING:
        return
    
    if user_id not in games[group_id].players:
        return
    
    game = games[group_id]
    player = game.players[user_id]
    message_text = str(event.get_message()).strip()
    
    # 检查是否说了自己的禁词
    if player.forbidden_word in message_text:
        player.violation_count += 1
        player.score -= 5
        
        # # 发送提醒消息
        # msg = f"💥 {player.nickname} 说了禁词 '{player.forbidden_word}'！\n"
        # msg += f"扣除5分，当前得分：{player.score}分"
        
        # await bot.send_group_msg(group_id=int(group_id), message=msg)
    # 检查消息字数，超过3个字加1分
    if len(message_text) > 3:
        player.score += 1

# 结束游戏
async def end_game(bot: Bot, group_id: str, reason: str = "游戏时间结束"):
    if group_id not in games:
        return
    
    game = games[group_id]
    game.status = GameStatus.ENDED
    
    if game.game_timer:
        game.game_timer.cancel()
    
    # 计算最终分数并更新数据库
    final_scores = []
    for user_id, player in game.players.items():
        final_score = player.score
        final_scores.append((player, final_score))
        
        # 更新数据库分数
        await update_player_score(
            user_id=user_id,
            group_id=group_id,
            score_change=final_score,
            game_type="害你在心口难开",
            game_result=f"违规{player.violation_count}次"
        )
    
    # 按分数排序
    final_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 发送结算消息
    msg = f"🏁 害你在心口难开游戏结束！\n\n"
    msg += f"📊 {reason}\n\n"
    msg += "🏆 最终排名：\n"
    
    for i, (player, score) in enumerate(final_scores):
        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        msg += f"{rank_emoji} {player.nickname}：{score}分（违规{player.violation_count}次）\n"
    
    msg += "\n📝 禁词公布：\n"
    for player in game.players.values():
        msg += f"{player.nickname}：{player.forbidden_word}\n"
    
    await bot.send_group_msg(group_id=int(group_id), message=msg)
    
    # 清理游戏数据
    del games[group_id]

# 强制结束游戏命令
force_end_game = on_regex(pattern=r'^强制结束禁词$', priority=1)
@force_end_game.handle()
async def handle_force_end_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await force_end_game.finish(message="当前没有进行中的害你在心口难开游戏")
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

check_game_status = on_regex(pattern=r'^禁词状态$', priority=1)
@check_game_status.handle()
async def handle_game_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await check_game_status.finish(message="当前没有进行中的害你在心口难开游戏")
        return
    
    game = games[group_id]
    status_text = ""
    
    if game.status == GameStatus.WAITING:
        status_text = "等待开始"
    elif game.status == GameStatus.SIGNUP:
        status_text = "报名中"
    elif game.status == GameStatus.PLAYING:
        status_text = "游戏进行中"
    elif game.status == GameStatus.ENDED:
        status_text = "已结束"
    
    player_count = len(game.players)
    
    msg = f"🚫 害你在心口难开状态：{status_text}\n"
    msg += f"👥 玩家数量：{player_count}人\n"
    
    if game.status == GameStatus.PLAYING:
        if game.start_time:
            elapsed = int(time.time() - game.start_time)
            remaining = max(0, game.game_duration - elapsed)
            msg += f"⏰ 剩余时间：{remaining//60}分{remaining%60}秒\n"
        
        # 显示当前分数
        sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
        msg += "\n💰 当前分数：\n"
        for i, player in enumerate(sorted_players):
            msg += f"{i+1}. {player.nickname}：{player.score}分（违规{player.violation_count}次）\n"
    
    await check_game_status.finish(message=msg)

# 设置游戏时长命令
set_game_duration = on_regex(pattern=r'^设置禁词时长\s+(\d+)分钟?$', priority=1)
@set_game_duration.handle()
async def handle_set_duration(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = str(event.group_id)
    
    if group_id not in games:
        await set_game_duration.finish(message="当前没有进行中的害你在心口难开游戏")
        return
    
    if games[group_id].status != GameStatus.SIGNUP:
        await set_game_duration.finish(message="只能在报名阶段设置游戏时长")
        return
    
    # 解析时长
    message_text = str(event.get_message()).strip()
    import re
    match = re.match(r'^设置禁词时长\s+(\d+)分钟?$', message_text)
    
    if not match:
        await set_game_duration.finish(message="格式错误，请使用：设置禁词时长 X分钟")
        return
    
    duration_minutes = int(match.group(1))
    
    if not (1 <= duration_minutes <= 30):
        await set_game_duration.finish(message="游戏时长必须在1-30分钟之间")
        return
    
    # 更新游戏时长
    games[group_id].game_duration = duration_minutes * 60
    
    await set_game_duration.finish(message=f"✅ 游戏时长已设置为 {duration_minutes} 分钟")

# 私聊查询禁词命令
check_forbidden_words = on_regex(pattern=r'^查询禁词$', priority=1)
@check_forbidden_words.handle()
async def handle_check_forbidden_words(bot: Bot, event: MessageEvent, state: T_State):
    user_id = str(event.user_id)
    
    # 检查是否是私聊
    if not isinstance(event, PrivateMessageEvent):
        return
    
    # 查找用户参与的游戏
    user_game = None
    user_group_id = None
    
    for group_id, game in games.items():
        if user_id in game.players and game.status == GameStatus.PLAYING:
            user_game = game
            user_group_id = group_id
            break
    
    if not user_game:
        await check_forbidden_words.finish(message="你当前没有参与任何进行中的害你在心口难开游戏")
        return
    
    # 获取其他玩家的禁词
    other_players_words = []
    for other_user_id, other_player in user_game.players.items():
        if other_user_id != user_id:
            other_players_words.append(f"{other_player.nickname}：{other_player.forbidden_word}")
    
    if not other_players_words:
        await check_forbidden_words.finish(message="当前游戏中没有其他玩家")
        return
    
    # 发送禁词信息
    player = user_game.players[user_id]
    private_msg = "🚫 害你在心口难开 - 其他玩家的禁词：\n\n"
    private_msg += "\n".join(other_players_words)
    # private_msg += f"\n\n⚠️ 你的禁词是：{player.forbidden_word}\n"
    # private_msg += "记住不要在群里说出你的禁词哦！"
    
    await check_forbidden_words.finish(message=private_msg)

# 害你在心口难开帮助命令
forbidden_help = on_regex(pattern=r'^禁词帮助$', priority=1)
@forbidden_help.handle()
async def handle_forbidden_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    help_msg = """🚫 害你在心口难开指令说明：

🎮 游戏指令：
• 开始害你在心口难开 [X分钟] - 开始新游戏（可选择时长1-30分钟，默认5分钟）
• 报名害你 / 报名禁词 - 报名参加游戏
• 开始禁词游戏 - 提前结束报名阶段并开始游戏
• 设置禁词时长 X分钟 - 在报名阶段设置游戏时长
• 禁词状态 - 查看当前游戏状态
• 强制结束禁词 - 强制结束当前游戏（仅管理员）
• 禁词帮助 - 显示此帮助信息

📱 私聊指令：
• 查询禁词 - 私聊机器人查询其他玩家的禁词（适用于无法接收私聊的情况）

🎯 游戏规则：
• 游戏时长：可自定义1-30分钟（默认5分钟）
• 每位玩家会被分配一个禁词
• 机器人会私聊告诉你其他人的禁词
• 在群聊中正常聊天，但不能说出自己的禁词
• 说了自己禁词会被扣分并公开提醒
• 如果无法接收私聊，可以私聊机器人发送"查询禁词"获取信息

💰 积分规则：
• 基础参与分 -10分
• 每说一次自己的禁词：-5分
• 每说一句超过3个字的话：+1分
• 最终得分会记录到个人积分系统

📝 使用示例：
• 开始害你在心口难开 - 开始5分钟游戏
• 开始害你在心口难开 10分钟 - 开始10分钟游戏
• 设置禁词时长 15分钟 - 设置游戏时长为15分钟

🎮 词汇类型：
• 日常用语、网络用语、情感表达
• 剑网三门派、技能、地图、NPC
• 游戏术语、江湖用语等
• 总计700+个词汇供随机分配

📝 游戏技巧：
• 记住其他人的禁词，可以引导他们说出来
• 小心不要说出自己的禁词
• 可以用同义词或谐音来表达意思
• 观察其他人的聊天内容，寻找机会
"""
    await forbidden_help.finish(message=help_msg)