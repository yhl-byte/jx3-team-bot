from nonebot import on_command, on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment, PrivateMessageEvent
from typing import Dict, List
from .game_score import update_player_score
import random
import asyncio

# 游戏状态管理
class DescribeGuessGame:
    def __init__(self):
        self.players = {}  # 玩家信息 {user_id: {"nickname": str, "number": int, "correct_guesses": int}}
        self.game_status = 'waiting_signup'  # 游戏状态：waiting_signup, waiting_describer, playing, finished
        self.describer_id = None  # 描述者ID
        self.describer_candidates = []  # 申请当描述者的玩家
        self.player_count = 0  # 玩家计数（用于分配编号）
        self.timer = None  # 用于计时的变量
        self.current_word = None  # 当前需要描述的词汇
        self.game_start_time = None  # 游戏开始时间
        self.word_change_count = 0  # 换词次数
        self.max_word_changes = 3   # 最大换词次数
        self.current_word_guessed = False  # 当前词汇是否已被猜
        self.word_list = [
            "苹果", "电脑", "汽车", "书本", "手机", "咖啡", "音乐", "电影", "足球", "猫咪",
            "太阳", "月亮", "星星", "海洋", "山峰", "花朵", "蝴蝶", "彩虹", "雪花", "火焰",
            "钢琴", "吉他", "画笔", "相机", "眼镜", "帽子", "鞋子", "背包", "钥匙", "钱包",
            "冰淇淋", "巧克力", "蛋糕", "面包", "牛奶", "果汁", "茶叶", "米饭", "面条", "饺子",
            "医生", "老师", "警察", "厨师", "司机", "画家", "歌手", "演员", "作家", "程序员",
            "肖申克的救赎", "教父", "阿甘正传", "泰坦尼克号", "盗梦空间", "辛德勒的名单", 
            "指环王", "蝙蝠侠", "搏击俱乐部", "飞越疯人院", "忠犬八公的故事", 
            "美丽人生", "机器人总动员", "寻梦环游记", "活着", "霸王别姬", "千与千寻", "这个杀手不太冷", 
            "怦然心动", "楚门的世界", "罗马假日", "乱世佳人", "音乐之声", "狮子王", "当幸福来敲门", 
            "闻香识女人", "拯救大兵瑞恩", "星际穿越", "绿皮书", "三傻大闹宝莱坞", "熔炉", "辩护人", 
            "釜山行", "寄生虫", "调音师", "海上钢琴师", "V字仇杀队", "死亡诗社", "勇敢的心", 
            "角斗士", "燃情岁月", "剪刀手爱德华", "大话西游之大圣娶亲", "无间道", "让子弹飞", 
            "我不是药神", "哪吒之魔童降世", "流浪地球", "战狼","成龙", "李连杰", "周润发", "刘德华",
            "梁朝伟", "张国荣", "梅艳芳", "王菲", "周杰伦", "林俊杰", "邓紫棋", "蔡依林", "陈奕迅", 
            "孙燕姿", "薛之谦", "华晨宇", "易烊千玺", "王俊凯", "王源", "迪丽热巴", "杨幂", "赵丽颖", 
            "肖战", "王一博", "吴京", "徐峥", "黄渤", "沈腾", "马丽", "贾玲", "葛优", "巩俐", "章子怡", 
            "周迅", "汤唯", "舒淇", "彭于晏", "胡歌", "霍建华", "赵又廷", "高圆圆", "刘亦菲", "范冰冰", 
            "李冰冰", "甄子丹", "古天乐", "郭富城", "黎明", "张学友", "黎姿","稻香村", "纯阳", "万花", 
            "七秀", "少林", "天策", "藏剑", "五毒", "唐门", "明教", "丐帮", "苍云", "长歌", "霸刀", 
            "蓬莱", "凌雪阁", "衍天宗", "北天药宗", "刀宗", "龙门荒漠", "洛阳", "成都", "扬州", 
            "瞿塘峡", "战宝迦兰", "烛龙殿", "大明宫", "狼神殿","浩气盟", "恶人谷", "PVE", "PVP", 
            "帮会", "师徒", "亲传", "监本", "侠义值", "威望", "江湖贡献", "装备", "精炼", "附魔", "插旗", "竞技场",
            "故宫", "长城", "兵马俑", "泰山", "黄山", "桂林山水", "西湖", "上海外滩", "乐山大佛", 
            "都江堰", "张家界", "九寨沟", "布达拉宫", "颐和园", "天坛", "鼓浪屿", "丽江古城", "三亚湾", 
            "敦煌莫高窟", "壶口瀑布","龙珠", "海贼王", "火影忍者", "死神", "名侦探柯南", "哆啦A梦",
            "灌篮高手", "圣斗士星矢", "美少女战士", "新世纪福音战士", "攻壳机动队", "钢之炼金术师", 
            "进击的巨人", "你的名字", "千与千寻", "幽灵公主", "天空之城", "蜡笔小新", "樱桃小丸子", 
            "精灵宝可梦","地铁", "公交", "出租车","咖啡馆", "酒店", "医院", "学校", "警察局", 
            "消防局", "邮局", "银行","紫气东来", "万剑归宗", "太极无极", "两仪万象", "坐忘无我", "吞吴", 
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
            "冰心诀", "云裳心经", "镇山河", "舍身", "弘法"
        ]  # 词汇库
        
    def get_random_word(self):
        return random.choice(self.word_list)
        
    def reset_game(self):
        for player_id in self.players:
            self.players[player_id]["correct_guesses"] = 0
        self.current_word = None
        self.word_change_count = 0
        self.current_word_guessed = False
        self.game_start_time = None

# 存储每个群的游戏实例
games: Dict[int, DescribeGuessGame] = {}

# 开始游戏命令
start_game = on_regex(pattern=r"^开始猜词$", priority=5)
@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id in games and games[group_id].game_status != 'finished':
        await start_game.finish("游戏已经在进行中！")
        return

    games[group_id] = DescribeGuessGame()
    
    await start_game.finish("《我来描述你来猜》游戏开始！\n请玩家发送【报名猜词】进行报名，至少需要2名玩家。\n通过【结束猜词报名】来结束报名阶段。")

# 玩家报名
signup = on_regex(pattern=r"^报名猜词$", priority=5)
@signup.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_signup':
        return
        
    game = games[group_id]
    if user_id in game.players:
        await signup.finish(f"您已经报名过了，您的编号是 {game.players[user_id]['number']}")
        return
    
    game.player_count += 1
    game.players[user_id] = {"number": game.player_count, "correct_guesses": 0}
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    game.players[user_id]["nickname"] = user_info['nickname']
    
    # 添加参与游戏基础分
    await update_player_score(str(user_id), str(group_id), 5, 'describe_guess', None, 'participation')
    
    msg = (
        MessageSegment.at(user_id) + '\n' + 
        Message(f"【{user_info['nickname']}】报名成功！您的编号是 {game.player_count}")
    )
    await signup.finish(message=Message(msg))

# 结束报名
end_signup = on_regex(pattern=r"^结束猜词报名$", priority=5)
@end_signup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_signup':
        return
        
    game = games[group_id]
    if len(game.players) < 2:
        await end_signup.finish("至少需要2名玩家才能开始游戏！")
        return
    
    game.game_status = 'waiting_describer'
    
    player_list = "\n".join([f"{info['number']}. {info['nickname']}" for user_id, info in game.players.items()])
    
    await end_signup.send(
        f"报名结束！共有 {len(game.players)} 名玩家参与：\n{player_list}\n\n" +
        "现在开始竞选描述者！\n" +
        "想要当描述者的玩家请发送【竞选】\n" +
        "30秒后将自动选择描述者并开始游戏。"
    )
    
    # 30秒后自动选择描述者
    game.timer = asyncio.create_task(asyncio.sleep(30))
    try:
        await game.timer
        await auto_select_describer(bot, group_id)
    except asyncio.CancelledError:
        pass  # 计时器被取消，不做处理

# 竞选描述者
apply_describer = on_regex(pattern=r"^(登基|竞选|夺嫡)$", priority=5)
@apply_describer.handle()
async def handle_apply_describer(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'waiting_describer':
        return
        
    game = games[group_id]
    if user_id not in game.players:
        await apply_describer.finish("您还没有报名参加游戏！")
        return
        
    if user_id in game.describer_candidates:
        await apply_describer.finish("您已经申请过了！")
        return
    
    game.describer_candidates.append(user_id)
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    
    msg = (
        MessageSegment.at(user_id) + '\n' + 
        Message(f"【{user_info['nickname']}】申请成为描述者！")
    )
    await apply_describer.finish(message=Message(msg))

# 自动选择描述者
async def auto_select_describer(bot: Bot, group_id: int):
    if group_id not in games:
        return
        
    game = games[group_id]
    if game.game_status != 'waiting_describer':
        return
    
    # 选择描述者
    if game.describer_candidates:
        # 从申请者中随机选择
        game.describer_id = random.choice(game.describer_candidates)
        describer_info = game.players[game.describer_id]
        await bot.send_group_msg(
            group_id=group_id,
            message=f"描述者已选定：【{describer_info['nickname']}】\n游戏即将开始！"
        )
    else:
        # 随机选择一名玩家
        game.describer_id = random.choice(list(game.players.keys()))
        describer_info = game.players[game.describer_id]
        await bot.send_group_msg(
            group_id=group_id,
            message=f"无人申请描述者，随机选定：【{describer_info['nickname']}】\n游戏即将开始！"
        )
    
    # 开始游戏
    await start_describing_game(bot, group_id)

# 开始描述游戏
async def start_describing_game(bot: Bot, group_id: int):
    game = games[group_id]
    game.game_status = 'playing'
    game.reset_game()
    game.current_word = game.get_random_word()
    game.game_start_time = asyncio.get_event_loop().time()
    
    # 私聊发送词汇给描述者
    await bot.send_private_msg(
        user_id=game.describer_id,
        message=f"【{game.current_word}】\n您是本轮的描述者！这是需要描述的词汇！\n" +
                "请在群里用文字描述这个词汇，让其他玩家猜出来。\n" +
                "注意：不能直接说出词汇中的任何字和谐音词！\n" +
                "游戏时长5分钟，加油！"
    )
    
    # 群里通知游戏开始
    describer_info = game.players[game.describer_id]
    await bot.send_group_msg(
        group_id=group_id,
        message=f"游戏开始！\n描述者：【{describer_info['nickname']}】\n\n" +
                "其他玩家请根据描述者的描述来猜词！\n" +
                "猜词格式：【猜词】+您的答案\n" +
                "游戏时长：5分钟\n" +
                "\n描述者开始描述吧！"
    )
    
    # 设置5分钟计时器
    game.timer = asyncio.create_task(asyncio.sleep(300))  # 5分钟
    try:
        await game.timer
        await end_describing_game(bot, group_id)
    except asyncio.CancelledError:
        pass  # 计时器被取消，不做处理

# 猜词处理
guess_word = on_regex(pattern=r"^猜词.+$", priority=5)
@guess_word.handle()
async def handle_guess_word(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    
    # 描述者不能猜词
    if user_id == game.describer_id:
        await guess_word.finish("描述者不能猜词哦！")
        return
        
    # 检查是否是参与游戏的玩家
    if user_id not in game.players:
        return
    
    # 提取猜测的词汇
    guess_text = event.get_plaintext().replace("猜词", "", 1).strip()
    
    if not guess_text:
        await guess_word.finish("请在【猜词】后面写上您的答案！")
        return
    
    user_info = game.players[user_id]
    
    # 检查是否猜对且当前词汇未被猜中
    if guess_text == game.current_word and not game.current_word_guessed:
        # 标记当前词汇已被猜中，防止其他玩家重复猜中
        game.current_word_guessed = True
        
        game.players[user_id]["correct_guesses"] += 1
        
        msg = (
            MessageSegment.at(user_id) + '\n' + 
            Message(f"🎉 恭喜【{user_info['nickname']}】猜对了！\n" +
                   f"答案就是：{game.current_word}\n" +
                   f"您本轮已猜对 {game.players[user_id]['correct_guesses']} 个词！")
        )
        await guess_word.send(message=Message(msg))
        
        # 更换新词汇
        game.current_word = game.get_random_word()
        
        # 私聊发送新词汇给描述者
        await bot.send_private_msg(
            user_id=game.describer_id,
            message=f"【{game.current_word}】\n 有人猜对了！这是 新的词汇\n继续描述吧！"
        )
        
        await bot.send_group_msg(
            group_id=group_id,
            message="描述者请继续描述下一个词汇！"
        )
        game.current_word_guessed = False  # 重置新词汇的猜中状态
    elif guess_text == game.current_word and game.current_word_guessed:
        # 词汇已被其他玩家猜中，给出提示
        await guess_word.finish("很遗憾，这个词汇刚刚已经被其他玩家猜中了！请等待下一个词汇。")
    else:
        # 猜错了，不做特殊处理，让游戏继续
        pass

# 结束游戏
async def end_describing_game(bot: Bot, group_id: int):
    if group_id not in games:
        return
        
    game = games[group_id]
    if game.game_status != 'playing':
        return
    
    game.game_status = 'finished'
    
    # 取消计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    # 统计结果
    describer_info = game.players[game.describer_id]
    total_correct = sum(player["correct_guesses"] for player_id, player in game.players.items() if player_id != game.describer_id)
    
    # 计算分数并更新
    describer_score = total_correct * 5
    
    # 更新描述者分数
    await update_player_score(str(game.describer_id), str(group_id), describer_score, 'describe_guess', None, 'describer')
    
    result_msg = f"🎮 游戏结束！\n\n📊 本轮结果：\n"
    result_msg = f"当前词汇是：【{game.current_word}】\n"
    result_msg += f"👑 描述者：【{describer_info['nickname']}】\n"
    result_msg += f"💰 描述者得分：{describer_score}分 (共{total_correct}次猜对 × 5分)\n\n"
    result_msg += "🏆 猜词玩家得分：\n"
    
    # 更新猜词玩家分数并显示结果
    for player_id, player_info in game.players.items():
        if player_id != game.describer_id:
            player_score = player_info["correct_guesses"] * 5
            await update_player_score(str(player_id), str(group_id), player_score, 'describe_guess', None, 'guesser')
            result_msg += f"  【{player_info['nickname']}】：{player_info['correct_guesses']}个词 → {player_score}分\n"
    
    result_msg += "\n感谢大家的参与！🎉"
    
    await bot.send_group_msg(group_id=group_id, message=result_msg)
    
    # 清理游戏数据
    del games[group_id]

# 强制结束游戏
force_end = on_regex(pattern=r"^强制结束猜词$", priority=5)
@force_end.handle()
async def handle_force_end(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    # 检查是否为管理员（这里简化处理，实际可以加入权限检查）
    member_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    if member_info['role'] not in ['admin', 'owner']:
        await force_end.finish("只有管理员可以强制结束游戏！")
        return
    
    if group_id not in games:
        await force_end.finish("当前没有进行中的游戏！")
        return
    
    game = games[group_id]
    
    # 取消计时器
    if game.timer and not game.timer.done():
        game.timer.cancel()
    
    if game.game_status == 'playing':
        await end_describing_game(bot, group_id)
    else:
        del games[group_id]
        await force_end.finish("游戏已被强制结束！")

# 游戏帮助
describe_help = on_regex(pattern=r"^猜词帮助$", priority=5)
@describe_help.handle()
async def handle_describe_help(bot: Bot, event: GroupMessageEvent):
    help_text = """
🎮 《我来描述你来猜》游戏帮助

📋 游戏规则：
1. 多人报名参与，至少需要2名玩家
2. 竞选描述者，无人竞选则随机选择
3. 描述者通过文字描述词汇，不能说出词汇中的字和谐音
4. 其他玩家根据描述猜词
5. 游戏时长5分钟
6. 描述者可以主动换词，每局最多3次

💰 计分规则：
• 猜对一词：+5分
• 描述者：根据本轮猜对次数 × 5分
• 参与游戏：+5分

🎯 游戏命令：
• 开始猜词 - 开始游戏
• 报名猜词 - 报名参与
• 结束猜词报名 - 结束报名阶段
• 登基|竞选|夺嫡 - 申请当描述者
• 猜词+答案 - 猜测词汇
• 换词语 - 描述者主动换词（限3次）
• 强制结束猜词 - 管理员强制结束
• 描述猜词帮助 - 查看帮助

🎉 快来体验有趣的描述猜词游戏吧！
"""
    await describe_help.finish(help_text)

# 描述者换词
change_word = on_regex(pattern=r"^换词语$", priority=5)
@change_word.handle()
async def handle_change_word(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].game_status != 'playing':
        return
        
    game = games[group_id]
    
    # 检查是否为当前描述者
    if user_id != game.describer_id:
        await change_word.finish("只有当前描述者可以换词！")
        return
    
    # 检查换词次数限制
    if game.word_change_count >= game.max_word_changes:
        await change_word.finish(f"换词次数已达上限（{game.max_word_changes}次）！")
        return
    
    # 换词逻辑
    old_word = game.current_word
    game.current_word = game.get_random_word()
    game.word_change_count += 1
    game.current_word_guessed = False  # 重置新词汇的猜中状态
    
    # 确保新词与旧词不同
    while game.current_word == old_word:
        game.current_word = game.get_random_word()
    
    # 私聊发送新词汇给描述者
    await bot.send_private_msg(
        user_id=game.describer_id,
        message=f"换词成功！\n新的词汇是：【{game.current_word}】\n\n" +
                f"剩余换词次数：{game.max_word_changes - game.word_change_count}次\n" +
                "继续描述吧！"
    )
    
    # 群里通知换词（不显示具体词汇）
    describer_info = game.players[game.describer_id]
    remaining_changes = game.max_word_changes - game.word_change_count
    
    msg = (
        MessageSegment.at(user_id) + '\n' + 
        Message(f"【{describer_info['nickname']}】选择了换词！\n" +
               f"剩余换词次数：{remaining_changes}次\n" +
               "请继续根据新的描述来猜词！")
    )
    await change_word.finish(message=Message(msg))