'''
Date: 2025-03-06 17:21:21
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-05-28 17:42:09
FilePath: /team-bot/jx3-team-bot/src/plugins/undercover.py
'''
# src/plugins/undercover.py
from nonebot import on_regex, on_command, on_message, require
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message, PrivateMessageEvent
from nonebot.permission import SUPERUSER
import random
import time
import asyncio
import aiohttp
import json
from typing import Dict, List, Tuple, Set, Optional
# require('nonebot_plugin_saa')
# from nonebot_plugin_saa import enable_auto_select_bot
# enable_auto_select_bot()
# from nonebot_plugin_saa import PlatformTarget, TargetQQPrivate, TargetQQGroup, MessageFactory

# 游戏状态
class UndercoverGameStatus:
    WAITING = 0    # 等待开始
    SIGNUP = 1     # 报名中
    PLAYING = 2    # 游戏中
    VOTING = 3     # 投票中
    ENDED = 4      # 已结束

# 游戏数据
class UndercoverGame:
    def __init__(self, group_id: int):
        self.group_id = group_id
        self.status = UndercoverGameStatus.WAITING
        self.players = {}  # user_id -> {"nickname": str, "word": str, "is_undercover": bool, "eliminated": bool}
        self.current_round = 0
        self.max_rounds = 0
        self.words = ("", "")  # (普通词, 卧底词)
        self.speaking_order = []
        self.current_speaker_index = 0
        self.votes = {}  # 投票结果: voter_id -> target_id
        self.speaking_timer = None
        self.vote_timer = None
        self.player_speeches = {}  # 存储玩家发言: user_id -> [发言1, 发言2, ...]
        self.change_word_timer = None  # 换词计时器

# 存储每个群的游戏状态
games: Dict[int, UndercoverGame] = {}

# 词库API
async def fetch_word_pairs() -> List[Tuple[str, str]]:
    """从网络获取谁是卧底词库"""
    try:
        async with aiohttp.ClientSession() as session:
            # 这里使用一个示例API，实际使用时请替换为可用的API
            async with session.get('https://api.example.com/undercover/words') as response:
                if response.status == 200:
                    data = await response.json()
                    return data['word_pairs']
    except Exception as e:
        print(f"获取词库失败: {e}")
    
    # 如果API获取失败，使用内置词库
    return [
        ("苹果", "梨"),
        ("可乐", "雪碧"),
        ("篮球", "鼠标"),
        ("电脑", "手机"),
        ("眼睛", "耳朵"),
        ("电影", "电视剧"),
        ("老师", "教授"),
        ("警察", "保安"),
        ("医生", "护士"),
        ("飞机", "直升机"),
        ("汽车", "自行车"),
        ("西瓜", "哈密瓜"),
        ("钢琴", "吉他"),
        ("猫", "老虎"),
        ("金刚狼", "黑寡妇"),
        ("甄嬛传", "芈月传"),
        ("哈利波特", "伏地魔"),
        ("蜘蛛侠", "蜘蛛精"),
        ("高跟鞋", "增高鞋"),
        ("汉堡包", "肉夹馍"),
        ("古筝", "古琴"),
        ("王者荣耀", "英雄联盟"),
        ("眉毛", "胡须"),
        ("海豹", "海象"),
        ("孔雀", "凤凰"),
        ("京剧", "越剧"),
        ("星巴克", "瑞幸"),
        ("微信", "QQ"),
        ("抖音", "快手"),
        ("饺子", "包子"),
        ("火锅", "麻辣烫"),
        ("剑三", "逆水寒"),
        ("麻将", "扑克"),
        ("支付宝", "微信支付"),
        ("淘宝", "京东"),
        ("小米", "华为"),
        ("海底捞", "小龙坎"),
        ("肯德基", "麦当劳"),
        ("必胜客", "达美乐"),
        ("喜茶", "奈雪的茶"),
        ("咖啡", "奶茶"),
        ("地铁", "公交"),
        ("滴滴", "花小猪"),
        ("支付宝", "云闪付"),
        ("知乎", "小红书"),
        ("B站", "抖音"),
        ("爱情", "友情"),
        ("螺蛳粉", "酸辣粉"),
        ("奶茶", "椰奶"),
        ("香菜", "折耳根"),
        ("保安", "保镖"),
        ("敦煌壁画", "埃及金字塔"),
        ("京剧脸谱", "日本浮世绘"),
        ("人工智能", "仿生机器人"),
        ("柯南", "福尔摩斯"),
        ("中央空调", "暖男"),
        ("大众", "五菱"),
        ("泡面", "方便面"),
        ("小龙虾", "大闸蟹"),
        ("粽子", "咸鸭蛋"),
        ("春节", "元宵节"),
        ("指甲刀", "美工刀"),
        ("蚊子", "苍蝇"),
        ("美瞳", "隐形眼镜"),
        ("电饭煲", "高压锅"),
        ("空调", "电风扇"),
        ("火车", "高铁"),
        ("剑网三", "天刀"),
        ("原神", "崩坏星穹铁道"),
        ("米哈游", "网易"),
        ("外卖", "堂食"),
        ("KTV", "录音棚"),
        ("健身房", "体育馆"),
        ("超市", "便利店"),
        ("电影院", "剧场"),
        ("动漫", "漫画"),
        ("漫展", "游戏展"),
        ("笔记本", "平板"),
        ("卫生巾", "护垫"),
        ("煎饼果子", "鸡蛋灌饼"),
        ("大黄蜂", "小蜜蜂"),
        ("政教处", "教导处"),
        ("九阴白骨爪", "降龙十八掌"),
        ("葵花宝典", "辟邪剑谱"),
        ("dota", "lol"),
        ("童话", "寓言"),
        ("那英", "王菲"),
        ("同学", "同桌"),
        ("张韶涵", "张含韵"),
        ("橙子", "橘子"),
        ("婚纱", "喜服"),
        ("森马", "以纯"),
        ("皇帝", "太子"),
        ("辣椒", "芥末"),
        ("董永", "许仙"),
        ("金庸", "古龙"),
        ("酒吧", "茶楼"),
        ("狄仁杰", "包青天"),
        ("魔术师", "魔法师"),
        ("泡泡糖", "棒棒糖"),
        ("铁观音", "碧螺春"),
        ("牛肉干", "猪肉脯"),
        ("前女友", "前男友"),
        ("双胞胎", "龙凤胎"),
        ("富二代", "高富帅"),
        ("神雕侠侣", "天龙八部"),
        ("拉面", "刀削面"),
        ("奥利奥", "趣多多"),
        ("早餐", "宵夜"),
        ("相亲", "联谊"),
        ("加班", "值班"),
        ("年终奖", "绩效奖"),
        ("请假条", "辞职信"),
        ("结婚", "订婚"),
        ("恋爱", "暗恋"),
        ("表白", "告白"),
        ("失恋", "分手"),
        ("男朋友", "备胎"),
        ("女朋友", "闺蜜"),
        ("相亲角", "婚介所"),
        ("催婚", "催生"),
        ("丈母娘", "婆婆"),
        ("岳父", "公公"),
        ("AA制", "请客"),
        ("网红", "明星"),
        ("键盘侠", "网络喷子"),
        ("南京条约", "马关条约"),
        ("赤壁之战", "官渡之战"),
        ("贞观之治", "开元盛世"),
        ("文景之治", "康乾盛世"),
        ("郑和下西洋", "张骞出使西域"),
        ("香港", "澳门"),
        ("武则天", "慈禧"),
        ("朱元璋", "朱棣"),
        ("秦始皇", "汉武帝"),
        ("康熙", "乾隆"),
        ("雍正", "嘉庆"),
        ("速度与激情", "极品飞车"),
        ("盗梦空间", "黑客帝国"),
        ("阿甘正传", "楚门的世界"),
        ("霍比特人", "魔戒"),
        ("仙剑奇侠传", "古剑奇谭"),
        ("武林外传", "家有儿女"),
        ("大长今", "宫"),
        ("傲娇", "病娇"),
        ("天然呆", "三无少女"),
        ("元气少女", "御姐"),
        ("中二病", "社恐"),
        ("吃货", "宅女"),
        ("灌篮高手", "排球少年"),
        ("钢之炼金术师", "魔法禁书目录"),
        ("鬼灭之刃", "咒术回战"),
        ("进击的巨人", "东京喰种"),
        ("刀剑神域", "鬼滅之刃"),
        ("魔卡少女樱", "美少女战士"),
        ("银魂", "齐木楠雄的灾难"),
        ("穿越", "重生"),
        ("皇子", "王爷"),
        ("公主", "格格"),
        ("侠客", "刺客"),
        ("剑客", "刀客"),
        ("书生", "才子"),
        ("丫鬟", "侍女"),
        ("捕快", "衙役"),
        ("将军", "元帅"),
        ("宰相", "丞相"),
        ("才女", "佳人"),
        ("富商", "大户"),
        ("道士", "和尚"),
        ("仙女", "妖精"),
        ("南派三叔", "天下霸唱"),
        ("诛仙", "斗破苍穹"),
        ("盗墓笔记", "鬼吹灯"),
        ("三体", "流浪地球"),
        ("围城", "平凡的世界"),
        ("莫言", "余华"),
        ("令狐冲", "杨过"),
        ("郭靖", "张无忌"),
        ("段誉", "萧峰"),
        ("黄蓉", "小龙女"),
        ("王语嫣", "赵敏"),
        ("东方不败", "任我行"),
        ("岳不群", "左冷禅"),
        ("风清扬", "独孤求败"),
        ("洪七公", "黄药师"),
        ("林黛玉", "薛宝钗"),
        ("贾宝玉", "贾探春"),
        ("孙悟空", "猪八戒"),
        ("刘备", "曹操"),
        ("诸葛亮", "司马懿"),
        ("关羽", "张飞"),
        ("武松", "鲁智深"),
        ("宋江", "林冲"),
        ("潘金莲", "西门庆"),
        ("李逵", "李鬼"),
        ("叶修", "苏沐橙"),
        ("唐三", "萧炎"),
        ("故宫", "颐和园"),
        ("充电宝", "充电器")
    ]

# 开始游戏命令
StartGame = on_regex(pattern=r'^开始谁是卧底$', priority=1)
@StartGame.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    # 检查是否已有游戏在进行
    if group_id in games and games[group_id].status != UndercoverGameStatus.WAITING and games[group_id].status != UndercoverGameStatus.ENDED:
        await StartGame.finish(message="游戏已经在进行中，请等待当前游戏结束")
        return
    
    # 创建新游戏
    games[group_id] = UndercoverGame(group_id)
    games[group_id].status = UndercoverGameStatus.SIGNUP
    
    await StartGame.finish(message="谁是卧底游戏开始报名！请想参加的玩家发送「报名卧底」。发送「结束报名」开始游戏。")
    
    # 300秒后自动结束报名
    await asyncio.sleep(300)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.SIGNUP:
        if len(games[group_id].players) < 3:
            await bot.send_group_msg(group_id=group_id, message="报名人数不足3人，游戏取消")
            del games[group_id]
        else:
            await start_game_process(bot, group_id)


# 报名命令
SignupGame = on_regex(pattern=r'^报名卧底$', priority=1)
@SignupGame.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.SIGNUP:
        await SignupGame.finish(message="当前没有谁是卧底游戏正在报名")
        return
    
    if user_id in games[group_id].players:
        await SignupGame.finish(message="你已经报名了")
        return
    
    # 添加玩家
    games[group_id].players[user_id] = {
        "nickname": event.sender.nickname,
        "user_id": event.user_id,
        "word": "",
        "is_undercover": False,
        "eliminated": False,
        "code": len(games[group_id].players) + 1  # 为每个玩家分配一个编号，从1开始
    }

    msg = (
            MessageSegment.at(event.user_id) + 
            Message(f"{event.sender.nickname} (编号:{len(games[group_id].players)})报名成功！当前已有 {len(games[group_id].players)} 人报名")
    )
    await SignupGame.finish(message=Message(msg))
    
    # await SignupGame.finish(message=f"{event.sender.nickname} (编号:{len(games[group_id].players)})报名成功！当前已有 {len(games[group_id].players)} 人报名")

# 结束报名命令
EndSignup = on_regex(pattern=r'^结束报名$', priority=1)
@EndSignup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.SIGNUP:
        await EndSignup.finish(message="当前没有谁是卧底游戏正在报名")
        return
    
    if len(games[group_id].players) < 3:
        await EndSignup.finish(message="报名人数不足3人，无法开始游戏")
        return
    
    await start_game_process(bot, group_id)

# 开始游戏流程
async def start_game_process(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = UndercoverGameStatus.PLAYING
    
   # 获取词库并分配词语和身份
    await assign_words_and_roles(bot, group_id)
    
    # 发送换词提示
    change_word_msg = f"词语已分配完成，是否需要更换词语和身份？\n发送「换词」重新分配，发送「不换词」开始游戏。\n30秒后将自动开始游戏。"
    await bot.send_group_msg(group_id=group_id, message=change_word_msg)
    
    # 设置换词计时器
    if game.change_word_timer:
        game.change_word_timer.cancel()
    game.change_word_timer = asyncio.create_task(change_word_timer(bot, group_id))

# 分配词语和身份
async def assign_words_and_roles(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 获取词库
    word_pairs = await fetch_word_pairs()
    chosen_pair = random.choice(word_pairs)
    game.words = chosen_pair
    
    # 决定谁是卧底
    player_ids = list(game.players.keys())
    num_players = len(player_ids)
    
    # 根据人数决定卧底数量
    num_undercovers = 1
    if num_players >= 6:
        num_undercovers = 2
    if num_players >= 9:
        num_undercovers = 3
    
    # 随机选择卧底
    undercover_indices = random.sample(range(num_players), num_undercovers)
    
    # 分配词语
    for i, player_id in enumerate(player_ids):
        is_undercover = i in undercover_indices
        game.players[player_id]["is_undercover"] = is_undercover
        game.players[player_id]["word"] = game.words[1] if is_undercover else game.words[0]
    
    # 决定发言顺序
    game.speaking_order = player_ids.copy()
    random.shuffle(game.speaking_order)
    game.current_speaker_index = 0
    game.current_round = 1
    
    # 发送游戏开始消息
    await bot.send_group_msg(group_id=group_id, message=f"游戏开始！共有{num_players}名玩家，其中{num_undercovers}名卧底。我已经私聊告知大家各自的词语，请查看。")
    
    # 私聊发送词语
    failed_users = []
    for player_id, player_info in game.players.items():
        try:
            await bot.send_private_msg(user_id=player_id, message=f"你的词语是：{player_info['word']}")
        except Exception as e:
            print(f"向玩家 {player_id} 发送私聊失败: {e}")
            failed_users.append(player_id)
    
    # 如果有私聊发送失败的用户，提醒他们添加机器人为好友
    if failed_users:
        reminder_msg = "部分玩家无法接收私聊消息。请通过私聊机器人发送「查询身份」来获取你的身份牌。"
        await bot.send_group_msg(group_id=group_id, message=reminder_msg)
        await asyncio.sleep(5)

# 换词计时器
async def change_word_timer(bot: Bot, group_id: int):
    await asyncio.sleep(30)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.PLAYING:
        game = games[group_id]
        if game.change_word_timer and not game.change_word_timer.cancelled():
            await bot.send_group_msg(group_id=group_id, message="时间到，开始游戏！")
            # 开始第一轮发言
            await start_speaking_round(bot, group_id)

# 换词命令
ChangeWord = on_regex(pattern=r'^换词$', priority=1)
@ChangeWord.handle()
async def handle_change_word(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.PLAYING:
        await ChangeWord.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    game = games[group_id]
    
    # 检查是否是游戏参与者
    if user_id not in game.players:
        await ChangeWord.finish(message="只有游戏参与者才能发起换词")
        return
    
    # 检查是否在换词阶段
    if not game.change_word_timer or game.change_word_timer.cancelled():
        await ChangeWord.finish(message="当前不在换词阶段")
        return
    
    # 取消计时器
    game.change_word_timer.cancel()
    
    await bot.send_group_msg(group_id=group_id, message="正在重新分配词语和身份...")
    
    # 重新分配词语和身份
    await assign_words_and_roles(bot, group_id)
    
    # 重新发送换词提示
    change_word_msg = f"词语已重新分配，是否需要更换词语和身份？\n发送「换词」重新分配，发送「不换词」开始游戏。\n30秒后将自动开始游戏。"
    await bot.send_group_msg(group_id=group_id, message=change_word_msg)
    
    # 重新设置换词计时器
    game.change_word_timer = asyncio.create_task(change_word_timer(bot, group_id))

# 不换词命令
KeepWord = on_regex(pattern=r'^不换词$', priority=1)
@KeepWord.handle()
async def handle_keep_word(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.PLAYING:
        await KeepWord.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    game = games[group_id]
    
    # 检查是否是游戏参与者
    if user_id not in game.players:
        await KeepWord.finish(message="只有游戏参与者才能决定是否换词")
        return
    
    # 检查是否在换词阶段
    if not game.change_word_timer or game.change_word_timer.cancelled():
        await KeepWord.finish(message="当前不在换词阶段")
        return
    
    # 取消计时器
    game.change_word_timer.cancel()
    
    await bot.send_group_msg(group_id=group_id, message="开始游戏！")
    
    # 开始第一轮发言
    await start_speaking_round(bot, group_id)

# 添加新的命令处理器用于私聊查询身份
QueryIdentity = on_regex(pattern=r'^查询身份$', priority=1)
@QueryIdentity.handle()
async def handle_query_identity(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    
    # 查找用户所在的游戏
    user_game = None
    user_group_id = None
    for group_id, game in games.items():
        if user_id in game.players and game.status == UndercoverGameStatus.PLAYING:
            user_game = game
            user_group_id = group_id
            break
    
    if not user_game:
        await QueryIdentity.finish(message="你当前没有参加任何进行中的谁是卧底游戏")
        return
    
    # 发送身份信息
    player_info = user_game.players[user_id]
    await QueryIdentity.finish(message=f"你的词语是：{player_info['word']}")

# 开始一轮发言
async def start_speaking_round(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查游戏是否应该结束
    if should_end_game(game):
        await end_game(bot, group_id)
        return
    
    await bot.send_group_msg(group_id=group_id, message=f"第 {game.current_round} 轮发言开始！")
    
    # 开始第一个人发言
    await next_player_speak(bot, group_id)

# 下一个玩家发言
async def next_player_speak(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否所有人都发言完毕
    if game.current_speaker_index >= len(game.speaking_order):
        # 一轮结束，开始投票
        game.current_speaker_index = 0
        game.status = UndercoverGameStatus.VOTING
        game.votes = {}
        result_msg = ""

        # 添加本轮发言记录
        result_msg += f"\n【第 {game.current_round} 轮发言记录】\n"
        for i, player_id in enumerate(game.speaking_order):
            player_info = game.players[player_id]
            if not player_info["eliminated"]:
                player_speech = "未发言"
                if player_id in game.player_speeches and len(game.player_speeches[player_id]) >= game.current_round:
                    player_speech = game.player_speeches[player_id][game.current_round - 1]
                result_msg += f"{player_info['code']}号 {player_info['nickname']}: ({player_speech})\n"

        result_msg += "\n【玩家列表】\n"
    
        for player_id, player_info in game.players.items():
            status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
            result_msg += f"编号：【{player_info['code']}】{player_info['nickname']}： {status}\n"
        
        await bot.send_group_msg(group_id=group_id, message=f"本轮发言结束，开始投票！请发送「投票 玩家昵称|编号」进行投票。60秒后投票结束。{result_msg}")
        
        # 设置投票计时器
        if game.vote_timer:
            game.vote_timer.cancel()
        game.vote_timer = asyncio.create_task(vote_timer(bot, group_id))
        return
    
    # 获取当前发言人
    current_speaker_id = game.speaking_order[game.current_speaker_index]
    current_speaker = game.players[current_speaker_id]
    
    # 检查玩家是否已被淘汰
    if current_speaker["eliminated"]:
        game.current_speaker_index += 1
        await next_player_speak(bot, group_id)
        return
    
    msg = (
        MessageSegment.at(current_speaker['user_id']) + 
        Message(f"请 {current_speaker['code']} 号玩家 - {current_speaker['nickname']} 发言（请以【发言】开头），60秒后结束。")
    )
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 设置发言计时器
    if game.speaking_timer:
        game.speaking_timer.cancel()
    game.speaking_timer = asyncio.create_task(speaking_timer(bot, group_id))

# 发言计时器
async def speaking_timer(bot: Bot, group_id: int):
    await asyncio.sleep(60)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.PLAYING:
        game = games[group_id]
        current_speaker_id = game.speaking_order[game.current_speaker_index]
        current_speaker = game.players[current_speaker_id]
        
        await bot.send_group_msg(
            group_id=group_id, 
            message=f"{current_speaker['nickname']} 超时未发言！请记得以【发言】开头进行发言。"
        )
        
        # 移动到下一个发言人
        game.current_speaker_index += 1
        await next_player_speak(bot, group_id)

# 投票计时器
async def vote_timer(bot: Bot, group_id: int):
    await asyncio.sleep(60)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.VOTING:
        await end_voting(bot, group_id)

# 处理投票
VoteCommand = on_regex(pattern=r'^投票\s+(.+)$', priority=1)
@VoteCommand.handle()
async def handle_vote(bot: Bot, event: MessageEvent, state: T_State):
    user_id = event.user_id
    
    # 查找用户所在的游戏
    user_game = None
    user_group_id = None
    for group_id, game in games.items():
        if user_id in game.players and game.status == UndercoverGameStatus.VOTING and not game.players[user_id]["eliminated"]:
            user_game = game
            user_group_id = group_id
            break
    if not user_game:
        await VoteCommand.finish(message="你没有参加任何正在投票的谁是卧底游戏")
        return
    
    # 获取投票目标
    vote_target = state["_matched"].group(1).strip()
    target_id = None
    
    # 支持通过编号或昵称进行投票
    try:
        # 尝试将输入解析为编号
        target_code = int(vote_target)
        # 通过编号查找玩家
        for pid, pinfo in user_game.players.items():
            if pinfo["code"] == target_code and not pinfo["eliminated"]:
                target_id = pid
                break
    except ValueError:
        # 如果不是编号，则按昵称查找
        for pid, pinfo in user_game.players.items():
            if pinfo["nickname"] == vote_target and not pinfo["eliminated"]:
                target_id = pid
                break
    
    if not target_id:
        await VoteCommand.finish(message=f"找不到玩家 {vote_target}，请确认玩家昵称或编号是否正确")
        return
    
    if target_id == user_id:
        await VoteCommand.finish(message="不能投票给自己")
        return
    
    # 记录投票
    user_game.votes[user_id] = target_id
    
    # 获取被投票玩家的昵称
    target_nickname = user_game.players[target_id]["nickname"]
    target_code = user_game.players[target_id]["code"]
    
    await VoteCommand.finish(message=f"{user_game.players[user_id]['nickname']} 投票给了 {target_code}号玩家 {target_nickname}")
    
    # 检查是否所有存活玩家都已投票
    alive_players = [pid for pid, pinfo in user_game.players.items() if not pinfo["eliminated"]]
    if all(pid in user_game.votes for pid in alive_players):
        # 如果所有存活玩家都已投票，立即结束投票
        if user_game.vote_timer:
            user_game.vote_timer.cancel()
        await end_voting(bot, user_group_id)

# 结束投票
async def end_voting(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = UndercoverGameStatus.PLAYING
    
       # 统计投票结果
    vote_count = {}
    for target_id in game.votes.values():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1
    
    # 找出得票最多的玩家
    max_votes = 0
    eliminated_player_id = None
    
    for player_id, votes in vote_count.items():
        if votes > max_votes:
            max_votes = votes
            eliminated_player_id = player_id
    
    
    # 处理平票情况
    tied_players = [pid for pid, votes in vote_count.items() if votes == max_votes]
    if len(tied_players) > 1:
        # 平票随机选择一人
        eliminated_player_id = random.choice(tied_players)
    
    if eliminated_player_id:
        # 标记玩家为已淘汰
        game.players[eliminated_player_id]["eliminated"] = True
        eliminated_player = game.players[eliminated_player_id]

        result_msg = ""
        result_msg += "\n【玩家列表】\n"
        
        for player_id, player_info in game.players.items():
            status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
            result_msg += f"编号：【{player_info['code']}】{player_info['nickname']}： {status}\n"
        
        # 发送淘汰消息
        await bot.send_group_msg(group_id=group_id, message=f"投票结束，{eliminated_player['nickname']} 被淘汰！{result_msg}")
        
        # 检查游戏是否结束
        if should_end_game(game):
            await end_game(bot, group_id)
            return
        
        # 进入下一轮
        game.current_round += 1
        #  # 统计存活的卧底和平民数量
        # alive_undercovers = 0
        # alive_civilians = 0
        
        # for player_id, player_info in game.players.items():
        #     if not player_info["eliminated"]:
        #         if player_info["is_undercover"]:
        #             alive_undercovers += 1
        #         else:
        #             alive_civilians += 1
        # # 如果只剩下2名平民和1名卧底，进入最终投票
        # if alive_civilians == 2 and alive_undercovers == 1:
        #     # 所有轮次结束，进入最终投票
        #     await final_vote(bot, group_id)
        #     return
        # if game.current_round > game.max_rounds:
        #     # 所有轮次结束，进入最终投票
        #     await final_vote(bot, group_id)
        #     return
        
        # 开始新一轮发言
        await start_speaking_round(bot, group_id)
    else:
        result_msg = ""
        result_msg += "\n【玩家列表】\n"
        
        for player_id, player_info in game.players.items():
            status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
            result_msg += f"编号：【{player_info['code']}】{player_info['nickname']}： {status}\n"
        # 没有人被淘汰，继续游戏
        await bot.send_group_msg(group_id=group_id, message=f"本轮没有人被淘汰，继续游戏！{result_msg}")
        game.current_round += 1
        await start_speaking_round(bot, group_id)

# 最终投票
async def final_vote(bot: Bot, group_id: int):
    game = games[group_id]
    
    await bot.send_group_msg(group_id=group_id, message="所有轮次已结束，进入最终投票！请发送「投票 玩家昵称」进行最终投票。30秒后投票结束。")
    
    game.status = UndercoverGameStatus.VOTING
    game.votes = {}
    
    # 设置投票计时器
    if game.vote_timer:
        game.vote_timer.cancel()
    game.vote_timer = asyncio.create_task(vote_timer(bot, group_id))

# 检查游戏是否应该结束
def should_end_game(game: UndercoverGame) -> bool:
    # 统计存活的卧底和平民数量
    alive_undercovers = 0
    alive_civilians = 0
    
    for player_id, player_info in game.players.items():
        if not player_info["eliminated"]:
            if player_info["is_undercover"]:
                alive_undercovers += 1
            else:
                alive_civilians += 1

    # 如果卧底全部被淘汰，平民胜利
    if alive_undercovers == 0:
        return True
    
    # 如果卧底数量大于等于平民数量，卧底胜利
    if alive_undercovers >= alive_civilians:
        return True
    
    return False

# 结束游戏
async def end_game(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = UndercoverGameStatus.ENDED
    
    # 统计存活的卧底和平民数量
    alive_undercovers = 0
    alive_civilians = 0
    
    for player_id, player_info in game.players.items():
        if not player_info["eliminated"]:
            if player_info["is_undercover"]:
                alive_undercovers += 1
            else:
                alive_civilians += 1
    
    # 确定胜利方
    if alive_undercovers == 0:
        winner = "平民"
    else:
        winner = "卧底"
    
    # 生成游戏结果消息
    result_msg = f"游戏结束！{winner}获胜！\n\n"
    result_msg += f"平民词语：{game.words[0]}\n"
    result_msg += f"卧底词语：{game.words[1]}\n\n"
    result_msg += "玩家身份：\n"
    
    for player_id, player_info in game.players.items():
        role = "卧底" if player_info["is_undercover"] else "平民"
        status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
        result_msg += f"{player_info['nickname']}：{role} {status}\n"
    
    await bot.send_group_msg(group_id=group_id, message=result_msg)
    
    # 清理游戏数据
    if group_id in games:
        del games[group_id]

# 强制结束游戏命令
ForceEndGame = on_regex(pattern=r'^结束谁是卧底$', priority=1)
@ForceEndGame.handle()
async def handle_force_end_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games:
        await ForceEndGame.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    # 检查是否是管理员
    admins = await bot.get_group_member_list(group_id=event.group_id)
    user_id = event.user_id
    is_admin = any(
        admin["user_id"] == user_id and 
        (admin["role"] in ["admin", "owner"]) 
        for admin in admins
    )
    
    if not is_admin:
        await ForceEndGame.finish(message="只有管理员才能强制结束游戏")
        return
    
    if games[group_id].status != UndercoverGameStatus.ENDED:
        await end_game(bot, group_id)
    else:
        await ForceEndGame.finish(message="游戏已经结束")

# 查看游戏状态命令
CheckGameStatus = on_regex(pattern=r'^谁是卧底状态$', priority=1)
@CheckGameStatus.handle()
async def handle_game_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games:
        await CheckGameStatus.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    game = games[group_id]
    status_text = ""
    
    if game.status == UndercoverGameStatus.WAITING:
        status_text = "等待开始"
    elif game.status == UndercoverGameStatus.SIGNUP:
        status_text = "报名中"
    elif game.status == UndercoverGameStatus.PLAYING:
        status_text = f"游戏进行中，第{game.current_round}轮"
    elif game.status == UndercoverGameStatus.VOTING:
        status_text = "投票中"
    elif game.status == UndercoverGameStatus.ENDED:
        status_text = "已结束"
    
    player_count = len(game.players)
    alive_count = sum(1 for p in game.players.values() if not p["eliminated"])
    
    msg = f"谁是卧底游戏状态：{status_text}\n"
    msg += f"玩家数量：{player_count}人，存活：{alive_count}人\n"
    
    if game.status == UndercoverGameStatus.PLAYING or game.status == UndercoverGameStatus.VOTING:
        msg += "存活玩家：\n"
        for player_id, player_info in game.players.items():
            if not player_info["eliminated"]:
                msg += f"- {player_info['nickname']}\n"
    
    await CheckGameStatus.finish(message=msg)

# 谁是卧底游戏帮助命令
UndercoverHelp = on_regex(pattern=r'^谁是卧底帮助$', priority=1)
@UndercoverHelp.handle()
async def handle_undercover_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    help_msg = """谁是卧底游戏指令说明：
1. 开始谁是卧底 - 开始一局新游戏并进入报名阶段
2. 报名卧底 - 报名参加游戏
3. 结束报名 - 提前结束报名阶段并开始游戏
4. 投票 玩家昵称|编号 - 在投票阶段通过私聊投票淘汰可疑玩家
5. 谁是卧底状态 - 查看当前游戏状态
6. 结束谁是卧底 - 强制结束当前游戏（仅管理员可用）
7. 谁是卧底帮助 - 显示此帮助信息
8. 发言 内容 - 在发言阶段发言

游戏规则：
1. 每位玩家会收到一个词语，其中大多数人收到相同的词（平民），少数人收到不同的词（卧底）
2. 每轮游戏中，所有玩家轮流描述自己拿到的词语，但不能直接说出该词
3. 每轮结束后进行投票，票数最多的玩家将被淘汰
4. 如果所有卧底被淘汰，平民获胜；如果卧底数量大于等于平民数量，卧底获胜
"""
    await UndercoverHelp.finish(message=help_msg)

# 添加发言命令处理
Speaking = on_regex(pattern=r'^发言\s*(.*)$', priority=1)
@Speaking.handle()
async def handle_speak_message(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    # 检查是否在游戏中且轮到该玩家发言
    if group_id not in games or games[group_id].status != UndercoverGameStatus.PLAYING:
        return
    
    game = games[group_id]
    # if game.current_speaker_index >= len(game.speaking_order):
    #     return
    # 检查是否轮到该玩家发言
    if game.current_speaker_index >= len(game.speaking_order) or game.speaking_order[game.current_speaker_index] != user_id:
        return
        
    # 获取发言内容
    speech_content = state["_matched"].group(1).strip()
    if not speech_content:
        await SpeakCommand.finish(message="发言内容不能为空")
        return

    current_speaker_id = game.speaking_order[game.current_speaker_index]
    if user_id != current_speaker_id:
        return

    # 记录发言
    if user_id not in game.player_speeches:
        game.player_speeches[user_id] = []
    game.player_speeches[user_id].append(speech_content)
    
    # 取消发言计时器
    if game.speaking_timer:
        game.speaking_timer.cancel()
    
    # 移动到下一个发言人
    game.current_speaker_index += 1

    # await SpeakCommand.finish(message=f"{game.players[user_id]['nickname']} 发言完毕")

    await next_player_speak(bot, group_id)