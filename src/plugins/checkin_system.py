from .database import NianZaiDB
from .game_score import update_player_score, get_player_score
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
import datetime
import random
import asyncio

db = NianZaiDB()
db.init_db()

# 等级配置
LEVEL_CONFIG = {
    1: {"exp_required": 0, "title": "初来乍到", "emoji": "🌱"},
    2: {"exp_required": 100, "title": "小试牛刀", "emoji": "🌿"},
    3: {"exp_required": 300, "title": "渐入佳境", "emoji": "🍀"},
    4: {"exp_required": 600, "title": "游刃有余", "emoji": "🌳"},
    5: {"exp_required": 1000, "title": "炉火纯青", "emoji": "🌲"},
    6: {"exp_required": 1500, "title": "登峰造极", "emoji": "🎋"},
    7: {"exp_required": 2100, "title": "出神入化", "emoji": "🎍"},
    8: {"exp_required": 2800, "title": "返璞归真", "emoji": "🌺"},
    9: {"exp_required": 3600, "title": "天人合一", "emoji": "🌸"},
    10: {"exp_required": 4500, "title": "超凡入圣", "emoji": "🌟"},
    11: {"exp_required": 5500, "title": "仙风道骨", "emoji": "✨"},
    12: {"exp_required": 6600, "title": "神通广大", "emoji": "💫"},
    13: {"exp_required": 7800, "title": "法力无边", "emoji": "⭐"},
    14: {"exp_required": 9100, "title": "威震八方", "emoji": "🌠"},
    15: {"exp_required": 10500, "title": "举世无双", "emoji": "👑"},
}

# 随机签到话语
CHECKIN_MESSAGES = [
    "今天也要加油哦！✨",
    "新的一天，新的开始！🌅",
    "你的坚持让人敬佩！💪",
    "每一天都是崭新的机会！🌈",
    "保持这份热情，你会走得更远！🚀",
    "今天的你依然闪闪发光！✨",
    "努力的人运气都不会太差！🍀",
    "相信自己，你比想象中更强大！💎",
    "今天又是充满希望的一天！🌻",
    "你的每一次签到都是成长的见证！📈",
    "坚持就是胜利，加油！🔥",
    "愿你今天收获满满的快乐！😊",
    "你的努力终将开花结果！🌸",
    "今天也要做最好的自己！💫",
    "每一个今天都值得被珍惜！💝",
    "你的笑容是今天最美的风景！😄",
    "保持初心，永远年轻！🌱",
    "今天的阳光因你而更加灿烂！☀️",
    "你的存在就是最好的礼物！🎁",
    "愿你的每一天都充满惊喜！🎉"
]

# 连续签到奖励配置
CONSECUTIVE_REWARDS = {
    1: {"exp": 10, "score": 5, "message": "新的开始！"},
    2: {"exp": 12, "score": 6, "message": "坚持第二天！"},
    3: {"exp": 15, "score": 8, "message": "三天连击！"},
    4: {"exp": 18, "score": 10, "message": "四天不断！"},
    5: {"exp": 22, "score": 12, "message": "五天连胜！"},
    6: {"exp": 26, "score": 15, "message": "六天坚持！"},
    7: {"exp": 30, "score": 20, "message": "一周达成！🎉"},
    14: {"exp": 50, "score": 35, "message": "两周坚持！🏆"},
    21: {"exp": 70, "score": 50, "message": "三周不懈！👑"},
    30: {"exp": 100, "score": 80, "message": "月度坚持王！🌟"},
    60: {"exp": 150, "score": 120, "message": "两月传奇！✨"},
    100: {"exp": 200, "score": 200, "message": "百日坚持！💎"},
    365: {"exp": 500, "score": 500, "message": "年度坚持王！🎊"}
}

def get_consecutive_reward(days):
    """获取连续签到奖励"""
    # 找到最大的符合条件的天数
    reward_days = [d for d in CONSECUTIVE_REWARDS.keys() if d <= days]
    if not reward_days:
        return {"exp": 10, "score": 5, "message": "继续加油！"}
    
    max_days = max(reward_days)
    base_reward = CONSECUTIVE_REWARDS[max_days].copy()
    
    # 超过基础奖励后，每天额外奖励
    if days > max_days:
        extra_days = days - max_days
        base_reward["exp"] += extra_days * 2
        base_reward["score"] += extra_days * 1
    
    return base_reward

def calculate_level(total_exp):
    """根据总经验计算等级"""
    current_level = 1
    for level, config in LEVEL_CONFIG.items():
        if total_exp >= config["exp_required"]:
            current_level = level
        else:
            break
    return current_level

def get_level_info(level):
    """获取等级信息"""
    if level in LEVEL_CONFIG:
        return LEVEL_CONFIG[level]
    else:
        # 超过最高等级的处理
        return {"exp_required": LEVEL_CONFIG[15]["exp_required"], "title": "传说中的存在", "emoji": "🌌"}

def get_next_level_exp(current_level, total_exp):
    """获取下一级所需经验"""
    next_level = current_level + 1
    if next_level in LEVEL_CONFIG:
        return LEVEL_CONFIG[next_level]["exp_required"] - total_exp
    return 0

# 命令注册
checkin = on_regex(pattern=r"^签到$", priority=5)
checkin_info = on_regex(pattern=r"^签到信息$", priority=5)
checkin_ranking = on_regex(pattern=r"^签到排行$", priority=5)
exp_ranking = on_regex(pattern=r"^经验排行$", priority=5)
level_ranking = on_regex(pattern=r"^等级排行$", priority=5)
makeup_checkin = on_regex(pattern=r"^补签$", priority=5)
buy_makeup_card = on_regex(pattern=r"^购买补签卡$", priority=5)
checkin_help = on_regex(pattern=r"^签到帮助$", priority=5)

@checkin.handle()
async def handle_checkin(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    today = datetime.date.today().isoformat()
    
    # 检查今天是否已经签到
    existing_checkin = db.fetch_one('checkin_records', 
                                   'user_id = ? AND group_id = ? AND checkin_date = ?', 
                                   (user_id, group_id, today))
    
    if existing_checkin:
        await checkin.finish("您今天已经签到过了！明天再来吧~ 😊")
        return
    
    # 获取用户信息
    try:
        user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id)
        nickname = user_info['nickname']
        avatar_url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    except:
        nickname = f"用户{user_id}"
        avatar_url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    
    # 获取或创建用户等级信息
    user_level_info = db.fetch_one('user_levels', 'user_id = ? AND group_id = ?', (user_id, group_id))
    
    if not user_level_info:
        # 新用户
        consecutive_days = 1
        total_checkin_days = 1
        total_exp = 0
        current_level = 1
        makeup_cards = 0
    else:
        # 检查连续签到
        last_checkin = user_level_info['last_checkin_date']
        if last_checkin:
            last_date = datetime.datetime.strptime(last_checkin, '%Y-%m-%d').date()
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            
            if last_date == yesterday:
                # 连续签到
                consecutive_days = user_level_info['consecutive_days'] + 1
            else:
                # 断签了
                consecutive_days = 1
        else:
            consecutive_days = 1
        
        total_checkin_days = user_level_info['total_checkin_days'] + 1
        total_exp = user_level_info['total_exp']
        current_level = user_level_info['current_level']
        makeup_cards = user_level_info['makeup_cards']
    
    # 计算奖励
    reward = get_consecutive_reward(consecutive_days)
    exp_gained = reward["exp"]
    score_gained = reward["score"]
    
    # 随机额外奖励（10%概率）
    if random.random() < 0.1:
        bonus_exp = random.randint(5, 15)
        bonus_score = random.randint(3, 10)
        exp_gained += bonus_exp
        score_gained += bonus_score
        bonus_message = f"\n🎁 幸运加成：+{bonus_exp}经验 +{bonus_score}积分！"
    else:
        bonus_message = ""
    
    # 更新经验和等级
    new_total_exp = total_exp + exp_gained
    new_level = calculate_level(new_total_exp)
    level_up = new_level > current_level
    
    # 等级提升奖励
    if level_up:
        level_bonus_score = (new_level - current_level) * 20
        score_gained += level_bonus_score
        level_up_message = f"\n🎉 恭喜升级！{current_level}级 → {new_level}级！额外获得{level_bonus_score}积分！"
    else:
        level_up_message = ""
    
    # 记录签到
    db.insert('checkin_records', {
        'user_id': user_id,
        'group_id': group_id,
        'checkin_date': today,
        'exp_gained': exp_gained,
        'score_gained': score_gained,
        'consecutive_days': consecutive_days
    })
    
    # 更新用户等级信息
    if user_level_info:
        db.update('user_levels', {
            'total_exp': new_total_exp,
            'current_level': new_level,
            'last_checkin_date': today,
            'consecutive_days': consecutive_days,
            'total_checkin_days': total_checkin_days,
            'updated_at': datetime.datetime.now().isoformat()
        }, f'user_id = "{user_id}" AND group_id = "{group_id}"')
    else:
        db.insert('user_levels', {
            'user_id': user_id,
            'group_id': group_id,
            'total_exp': new_total_exp,
            'current_level': new_level,
            'makeup_cards': makeup_cards,
            'last_checkin_date': today,
            'consecutive_days': consecutive_days,
            'total_checkin_days': total_checkin_days
        })
    
    # 更新积分系统
    await update_player_score(user_id, group_id, score_gained, "签到系统", "签到者", "每日签到")
    
    # 获取今日签到排名
    today_checkins = db.fetch_all('checkin_records', f'group_id = "{group_id}" AND checkin_date = "{today}"')
    checkin_rank = len(today_checkins)
    
    # 获取等级信息
    level_info = get_level_info(new_level)
    next_level_exp = get_next_level_exp(new_level, new_total_exp)
    
    # 随机话语
    random_message = random.choice(CHECKIN_MESSAGES)
    
    # 构建消息
    message_parts = []
    message_parts.append(MessageSegment.image(avatar_url))  # 用户头像
    
    msg = f"✅ 签到成功！\n\n"
    msg += f"👤 {nickname}\n"
    msg += f"📅 {datetime.date.today().strftime('%Y年%m月%d日')}\n"
    msg += f"🏆 今日第 {checkin_rank} 个签到\n\n"
    
    msg += f"📊 本次收获：\n"
    msg += f"   💫 经验：+{exp_gained}\n"
    msg += f"   💰 积分：+{score_gained}\n\n"
    
    msg += f"🔥 连续签到：{consecutive_days} 天\n"
    msg += f"📈 累计签到：{total_checkin_days} 天\n\n"
    
    msg += f"⭐ 当前等级：{level_info['emoji']} {new_level}级 - {level_info['title']}\n"
    msg += f"💫 总经验：{new_total_exp}\n"
    if next_level_exp > 0:
        msg += f"🎯 距离下级：{next_level_exp} 经验\n\n"
    else:
        msg += f"🌟 已达最高等级！\n\n"
    
    msg += f"💝 {random_message}"
    msg += bonus_message
    msg += level_up_message
    
    message_parts.append(MessageSegment.text(msg))
    
    await checkin.finish(Message(message_parts))

@checkin_info.handle()
async def handle_checkin_info(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 获取用户信息
    try:
        user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id)
        nickname = user_info['nickname']
    except:
        nickname = f"用户{user_id}"
    
    # 获取用户等级信息
    user_level_info = db.fetch_one('user_levels', 'user_id = ? AND group_id = ?', (user_id, group_id))
    
    if not user_level_info:
        await checkin_info.finish("您还没有签到过，快来签到吧！")
        return
    
    # 获取积分信息
    score_info = await get_player_score(user_id, group_id)
    total_score = score_info['total_score'] if score_info else 0
    
    # 检查今天是否已签到
    today = datetime.date.today().isoformat()
    today_checkin = db.fetch_one('checkin_records', 
                                'user_id = ? AND group_id = ? AND checkin_date = ?', 
                                (user_id, group_id, today))
    
    # 获取等级信息
    current_level = user_level_info['current_level']
    total_exp = user_level_info['total_exp']
    level_info = get_level_info(current_level)
    next_level_exp = get_next_level_exp(current_level, total_exp)
    
    msg = f"📋 {nickname} 的签到信息\n\n"
    msg += f"⭐ 等级：{level_info['emoji']} {current_level}级 - {level_info['title']}\n"
    msg += f"💫 总经验：{total_exp}\n"
    if next_level_exp > 0:
        msg += f"🎯 距离下级：{next_level_exp} 经验\n"
    else:
        msg += f"🌟 已达最高等级！\n"
    
    msg += f"💰 总积分：{total_score}\n"
    msg += f"🔥 连续签到：{user_level_info['consecutive_days']} 天\n"
    msg += f"📈 累计签到：{user_level_info['total_checkin_days']} 天\n"
    msg += f"🎫 补签卡：{user_level_info['makeup_cards']} 张\n\n"
    
    if today_checkin:
        msg += f"✅ 今日已签到\n"
        msg += f"📅 签到时间：{today_checkin['created_at'][:19]}\n"
    else:
        msg += f"❌ 今日未签到\n"
    
    if user_level_info['last_checkin_date']:
        msg += f"📅 上次签到：{user_level_info['last_checkin_date']}"
    
    await checkin_info.finish(msg)

@checkin_ranking.handle()
async def handle_checkin_ranking(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 获取今日签到排行
    today = datetime.date.today().isoformat()
    today_checkins = db.fetch_all('checkin_records', 
                                 f'group_id = "{group_id}" AND checkin_date = "{today}" ORDER BY created_at')
    
    if not today_checkins:
        await checkin_ranking.finish("今天还没有人签到呢！")
        return
    
    msg = f"📅 今日签到排行榜 ({datetime.date.today().strftime('%m月%d日')})\n\n"
    
    for i, checkin in enumerate(today_checkins[:10], 1):
        try:
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(checkin['user_id']))
            nickname = user_info['nickname']
        except:
            nickname = f"用户{checkin['user_id']}"
        
        # 获取用户等级信息
        user_level_info = db.fetch_one('user_levels', 'user_id = ? AND group_id = ?', 
                                      (checkin['user_id'], group_id))
        
        if user_level_info:
            level_info = get_level_info(user_level_info['current_level'])
            level_display = f"{level_info['emoji']}{user_level_info['current_level']}级"
            consecutive = user_level_info['consecutive_days']
        else:
            level_display = "🌱1级"
            consecutive = 1
        
        # 排名图标
        if i == 1:
            rank_emoji = "🥇"
        elif i == 2:
            rank_emoji = "🥈"
        elif i == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{i}."
        
        
        msg += f"{rank_emoji} {nickname} {level_display}\n"
        msg += f"    🔥{consecutive}天连签 \n\n"
    
    await checkin_ranking.finish(msg)

@exp_ranking.handle()
async def handle_exp_ranking(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 获取经验排行
    rankings = db.fetch_all('user_levels', 
                           f'group_id = "{group_id}" ORDER BY total_exp DESC LIMIT 10')
    
    if not rankings:
        await exp_ranking.finish("暂无经验排行数据！")
        return
    
    msg = "💫 经验排行榜\n\n"
    
    for i, user_data in enumerate(rankings, 1):
        try:
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(user_data['user_id']))
            nickname = user_info['nickname']
        except:
            nickname = f"用户{user_data['user_id']}"
        
        level_info = get_level_info(user_data['current_level'])
        
        # 排名图标
        if i == 1:
            rank_emoji = "🥇"
        elif i == 2:
            rank_emoji = "🥈"
        elif i == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{i}."
        
        msg += f"{rank_emoji} {nickname}\n"
        msg += f"    {level_info['emoji']}{user_data['current_level']}级 - {level_info['title']}\n"
        msg += f"    💫{user_data['total_exp']}经验 🔥{user_data['consecutive_days']}天连签\n\n"
    
    await exp_ranking.finish(msg)

@level_ranking.handle()
async def handle_level_ranking(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 获取等级排行
    rankings = db.fetch_all('user_levels', 
                           f'group_id = "{group_id}" ORDER BY current_level DESC, total_exp DESC LIMIT 10')
    
    if not rankings:
        await level_ranking.finish("暂无等级排行数据！")
        return
    
    msg = "👑 等级排行榜\n\n"
    
    for i, user_data in enumerate(rankings, 1):
        try:
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(user_data['user_id']))
            nickname = user_info['nickname']
        except:
            nickname = f"用户{user_data['user_id']}"
        
        level_info = get_level_info(user_data['current_level'])
        
        # 排名图标
        if i == 1:
            rank_emoji = "🥇"
        elif i == 2:
            rank_emoji = "🥈"
        elif i == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{i}."
        
        msg += f"{rank_emoji} {nickname}\n"
        msg += f"    {level_info['emoji']}{user_data['current_level']}级 - {level_info['title']}\n"
        msg += f"    📈{user_data['total_checkin_days']}天签到 🔥{user_data['consecutive_days']}天连签\n\n"
    
    await level_ranking.finish(msg)

@makeup_checkin.handle()
async def handle_makeup_checkin(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 获取用户等级信息
    user_level_info = db.fetch_one('user_levels', 'user_id = ? AND group_id = ?', (user_id, group_id))
    
    if not user_level_info:
        await makeup_checkin.finish("您还没有签到过，无法使用补签功能！")
        return
    
    if user_level_info['makeup_cards'] <= 0:
        await makeup_checkin.finish("您没有补签卡！可以通过【购买补签卡】获取。")
        return
    
    # 检查昨天是否已经签到
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    yesterday_checkin = db.fetch_one('checkin_records', 
                                    'user_id = ? AND group_id = ? AND checkin_date = ?', 
                                    (user_id, group_id, yesterday))
    
    if yesterday_checkin:
        await makeup_checkin.finish("昨天您已经签到过了，无需补签！")
        return
    
    # 检查今天是否已经签到
    today = datetime.date.today().isoformat()
    today_checkin = db.fetch_one('checkin_records', 
                                'user_id = ? AND group_id = ? AND checkin_date = ?', 
                                (user_id, group_id, today))
    
    if not today_checkin:
        await makeup_checkin.finish("请先完成今日签到，再使用补签功能！")
        return
    
    # 使用补签卡
    consecutive_days = user_level_info['consecutive_days']
    
    # 补签奖励（减半）
    reward = get_consecutive_reward(consecutive_days)
    exp_gained = reward["exp"] // 2
    score_gained = reward["score"] // 2
    
    # 记录补签
    db.insert('checkin_records', {
        'user_id': user_id,
        'group_id': group_id,
        'checkin_date': yesterday,
        'exp_gained': exp_gained,
        'score_gained': score_gained,
        'consecutive_days': consecutive_days
    })
    
    # 更新用户信息
    new_total_exp = user_level_info['total_exp'] + exp_gained
    new_level = calculate_level(new_total_exp)
    new_makeup_cards = user_level_info['makeup_cards'] - 1
    new_total_checkin_days = user_level_info['total_checkin_days'] + 1
    
    db.update('user_levels', {
        'total_exp': new_total_exp,
        'current_level': new_level,
        'makeup_cards': new_makeup_cards,
        'total_checkin_days': new_total_checkin_days,
        'updated_at': datetime.datetime.now().isoformat()
    }, f'user_id = "{user_id}" AND group_id = "{group_id}"')
    
    # 更新积分
    await update_player_score(user_id, group_id, score_gained, "签到系统", "补签者", "补签")
    
    msg = f"✅ 补签成功！\n\n"
    msg += f"📅 补签日期：{yesterday}\n"
    msg += f"💫 获得经验：{exp_gained}\n"
    msg += f"💰 获得积分：{score_gained}\n"
    msg += f"🎫 剩余补签卡：{new_makeup_cards} 张\n\n"
    msg += f"💡 补签奖励为正常签到的50%"
    
    await makeup_checkin.finish(msg)

@buy_makeup_card.handle()
async def handle_buy_makeup_card(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 补签卡价格
    card_price = 100  # 100积分一张
    
    # 检查积分
    score_info = await get_player_score(user_id, group_id)
    if not score_info or score_info['total_score'] < card_price:
        current_score = score_info['total_score'] if score_info else 0
        await buy_makeup_card.finish(f"积分不足！补签卡价格：{card_price}积分，您当前积分：{current_score}")
        return
    
    # 获取或创建用户等级信息
    user_level_info = db.fetch_one('user_levels', 'user_id = ? AND group_id = ?', (user_id, group_id))
    
    if not user_level_info:
        await buy_makeup_card.finish("您还没有签到过，请先签到！")
        return
    
    # 扣除积分
    await update_player_score(user_id, group_id, -card_price, "签到系统", "购买者", "购买补签卡")
    
    # 增加补签卡
    new_makeup_cards = user_level_info['makeup_cards'] + 1
    db.update('user_levels', {
        'makeup_cards': new_makeup_cards,
        'updated_at': datetime.datetime.now().isoformat()
    }, f'user_id = "{user_id}" AND group_id = "{group_id}"')
    
    msg = f"✅ 购买成功！\n\n"
    msg += f"💰 消耗积分：{card_price}\n"
    msg += f"🎫 获得补签卡：1 张\n"
    msg += f"🎫 当前补签卡：{new_makeup_cards} 张\n\n"
    msg += f"💡 补签卡可以补签昨天的签到记录"
    
    await buy_makeup_card.finish(msg)

@checkin_help.handle()
async def handle_checkin_help(bot: Bot, event: GroupMessageEvent):
    help_msg = "📋 签到系统帮助\n\n"
    help_msg += "🔸 基础命令：\n"
    help_msg += "• 签到 - 每日签到\n"
    help_msg += "• 签到信息 - 查看个人签到信息\n"
    help_msg += "• 签到排行 - 今日签到排行榜\n"
    help_msg += "• 经验排行 - 经验排行榜\n"
    help_msg += "• 等级排行 - 等级排行榜\n"
    help_msg += "• 补签 - 使用补签卡补签昨天\n"
    help_msg += "• 购买补签卡 - 花费100积分购买补签卡\n\n"
    
    help_msg += "🔸 奖励机制：\n"
    help_msg += "• 每日签到获得经验和积分\n"
    help_msg += "• 连续签到天数越多，奖励越丰厚\n"
    help_msg += "• 10%概率获得幸运加成\n"
    help_msg += "• 升级时获得额外积分奖励\n\n"
    
    help_msg += "🔸 等级系统：\n"
    help_msg += "• 通过签到获得经验提升等级\n"
    help_msg += "• 等级越高，称号越炫酷\n"
    help_msg += "• 最高15级，超越后成为传说\n\n"
    
    help_msg += "🔸 连续签到奖励：\n"
    help_msg += "• 1天：10经验 + 5积分\n"
    help_msg += "• 7天：30经验 + 20积分\n"
    help_msg += "• 30天：100经验 + 80积分\n"
    help_msg += "• 100天：200经验 + 200积分\n"
    help_msg += "• 365天：500经验 + 500积分\n\n"
    
    help_msg += "🔸 补签系统：\n"
    help_msg += "• 补签卡价格：100积分/张\n"
    help_msg += "• 只能补签昨天的记录\n"
    help_msg += "• 补签奖励为正常签到的50%\n\n"
    
    help_msg += "💡 提示：坚持每日签到，成为签到王者！"
    
    await checkin_help.finish(help_msg)