'''
@Author: AI Assistant
@Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-27 09:42:28
FilePath: /team-bot/jx3-team-bot/src/plugins/virtual_pet.py
'''
from .database import NianZaiDB
from .game_score import update_player_score
from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
import random
import asyncio
from datetime import datetime, timedelta
import json

db = NianZaiDB()
db.init_db()

# 宠物类型配置
PET_TYPES = {
    "猫咪": {"emoji": "🐱", "base_hunger": 50, "base_happiness": 60, "base_cleanliness": 70},
    "小狗": {"emoji": "🐶", "base_hunger": 60, "base_happiness": 70, "base_cleanliness": 50},
    "兔子": {"emoji": "🐰", "base_hunger": 40, "base_happiness": 50, "base_cleanliness": 80},
    "小鸟": {"emoji": "🐦", "base_hunger": 30, "base_happiness": 80, "base_cleanliness": 60},
    "仓鼠": {"emoji": "🐹", "base_hunger": 35, "base_happiness": 65, "base_cleanliness": 75}
}

# 宠物状态描述
STATUS_DESCRIPTIONS = {
    "hunger": {
        (0, 20): "饿得不行了",
        (21, 40): "有点饿",
        (41, 70): "还好",
        (71, 90): "很饱",
        (91, 100): "吃得很撑"
    },
    "happiness": {
        (0, 20): "非常沮丧",
        (21, 40): "有点不开心",
        (41, 70): "还好",
        (71, 90): "很开心",
        (91, 100): "超级开心"
    },
    "cleanliness": {
        (0, 20): "脏兮兮的",
        (21, 40): "有点脏",
        (41, 70): "还算干净",
        (71, 90): "很干净",
        (91, 100): "一尘不染"
    }
}

# 随机事件
RANDOM_EVENTS = [
    {"type": "good", "message": "你的宠物找到了一个小玩具！", "happiness": 10, "score": 5},
    {"type": "good", "message": "你的宠物学会了新技能！", "exp": 15, "score": 8},
    {"type": "bad", "message": "你的宠物不小心弄脏了自己...", "cleanliness": -15},
    {"type": "bad", "message": "你的宠物有点想家了...", "happiness": -10},
    {"type": "neutral", "message": "你的宠物在安静地休息。", "hunger": -5}
]

# 注册命令
create_pet = on_regex(pattern=r"^领养宠物\s*(猫咪|小狗|兔子|小鸟|仓鼠)?$", priority=5)
check_pet = on_regex(pattern=r"^查看宠物$", priority=5)
feed_pet = on_regex(pattern=r"^喂食$", priority=5)
play_pet = on_regex(pattern=r"^陪玩$", priority=5)
clean_pet = on_regex(pattern=r"^清洁$", priority=5)
rename_pet = on_regex(pattern=r"^改名\s+(.+)$", priority=5)
pet_ranking = on_regex(pattern=r"^宠物排行$", priority=5)
pet_help = on_regex(pattern=r"^宠物帮助$", priority=5)
release_pet = on_regex(pattern=r"^放生宠物$", priority=5)


def get_status_description(status_type: str, value: int) -> str:
    """获取状态描述"""
    for (min_val, max_val), desc in STATUS_DESCRIPTIONS[status_type].items():
        if min_val <= value <= max_val:
            return desc
    return "未知状态"

def calculate_level_exp(level: int) -> int:
    """计算升级所需经验"""
    return level * 100

def get_pet_emoji_by_level(pet_type: str, level: int) -> str:
    """根据等级获取宠物表情"""
    base_emoji = PET_TYPES[pet_type]["emoji"]
    if level >= 20:
        return f"👑{base_emoji}"  # 王者级别
    elif level >= 15:
        return f"⭐{base_emoji}"  # 明星级别
    elif level >= 10:
        return f"💎{base_emoji}"  # 钻石级别
    elif level >= 5:
        return f"🏆{base_emoji}"  # 金牌级别
    else:
        return base_emoji

async def decay_pet_status(user_id: str, group_id: str):
    """宠物状态自然衰减"""
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        return
    
    # 计算时间差
    last_interaction = datetime.fromisoformat(pet['last_interaction'])
    now = datetime.now()
    hours_passed = (now - last_interaction).total_seconds() / 3600
    
    if hours_passed < 1:  # 1小时内不衰减
        return
    
    # 计算衰减量
    decay_rate = min(int(hours_passed), 24)  # 最多按24小时计算
    
    new_hunger = max(0, pet['hunger'] - decay_rate * 2)
    new_happiness = max(0, pet['happiness'] - decay_rate * 1)
    new_cleanliness = max(0, pet['cleanliness'] - decay_rate * 1)
    
    db.update('virtual_pets', {
        'hunger': new_hunger,
        'happiness': new_happiness,
        'cleanliness': new_cleanliness
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")

async def trigger_random_event(user_id: str, group_id: str) -> str:
    """触发随机事件"""
    if random.random() > 0.15:  # 15%概率触发
        return None
    
    event = random.choice(RANDOM_EVENTS)
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    
    if not pet:
        return None
    
    updates = {}
    score_gain = 0
    
    # 应用事件效果
    if 'hunger' in event:
        updates['hunger'] = max(0, min(100, pet['hunger'] + event['hunger']))
    if 'happiness' in event:
        updates['happiness'] = max(0, min(100, pet['happiness'] + event['happiness']))
    if 'cleanliness' in event:
        updates['cleanliness'] = max(0, min(100, pet['cleanliness'] + event['cleanliness']))
    if 'exp' in event:
        new_exp = pet['exp'] + event['exp']
        level_up_exp = calculate_level_exp(pet['level'])
        if new_exp >= level_up_exp:
            updates['level'] = pet['level'] + 1
            updates['exp'] = new_exp - level_up_exp
        else:
            updates['exp'] = new_exp
    if 'score' in event:
        score_gain = event['score']
    
    if updates:
        db.update('virtual_pets', updates, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    if score_gain > 0:
        await update_player_score(user_id, group_id, score_gain, "宠物随机事件", "宠物主人", "随机奖励")
    
    return event['message']

@create_pet.handle()
async def handle_create_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否已有宠物
    existing_pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if existing_pet:
        await create_pet.send(f"你已经有一只宠物了！使用'查看宠物'来查看你的{existing_pet['pet_name']}")
        return
    
    # 解析宠物类型
    message_text = str(event.message).strip()
    pet_type = None
    for ptype in PET_TYPES.keys():
        if ptype in message_text:
            pet_type = ptype
            break
    
    if not pet_type:
        pet_type = random.choice(list(PET_TYPES.keys()))
    
    # 生成随机名字
    pet_names = ["小可爱", "毛球", "小乖", "糖糖", "豆豆", "花花", "球球", "咪咪", "汪汪", "跳跳"]
    pet_name = random.choice(pet_names)
    
    # 创建宠物
    pet_config = PET_TYPES[pet_type]
    db.insert('virtual_pets', {
        'user_id': user_id,
        'group_id': group_id,
        'pet_name': pet_name,
        'pet_type': pet_type,
        'hunger': pet_config['base_hunger'],
        'happiness': pet_config['base_happiness'],
        'cleanliness': pet_config['base_cleanliness']
    })
    
    # 奖励积分
    await update_player_score(user_id, group_id, 20, "领养宠物", "宠物主人", "领养奖励")
    
    emoji = PET_TYPES[pet_type]["emoji"]
    await create_pet.send(
        f"🎉 恭喜你领养了一只{pet_type}！\n"
        f"{emoji} 名字：{pet_name}\n"
        f"📊 初始状态：\n"
        f"  🍖 饱食度：{pet_config['base_hunger']}\n"
        f"  😊 快乐度：{pet_config['base_happiness']}\n"
        f"  🛁 清洁度：{pet_config['base_cleanliness']}\n"
        f"💰 获得20积分奖励！\n\n"
        f"使用'宠物帮助'查看更多指令"
    )

@check_pet.handle()
async def handle_check_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 先进行状态衰减
    await decay_pet_status(user_id, group_id)
    
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        await check_pet.send("你还没有宠物呢！使用'领养宠物'来领养一只吧~")
        return
    
    # 触发随机事件
    event_msg = await trigger_random_event(user_id, group_id)
    
    # 重新获取宠物信息（可能被随机事件修改）
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    
    emoji = get_pet_emoji_by_level(pet['pet_type'], pet['level'])
    level_up_exp = calculate_level_exp(pet['level'])
    
    hunger_desc = get_status_description("hunger", pet['hunger'])
    happiness_desc = get_status_description("happiness", pet['happiness'])
    cleanliness_desc = get_status_description("cleanliness", pet['cleanliness'])
    
    # 计算健康度
    health = (pet['hunger'] + pet['happiness'] + pet['cleanliness']) // 3
    
    message = (
        f"{emoji} {pet['pet_name']} (Lv.{pet['level']})\n"
        f"🏥 健康度：{health}/100\n"
        f"🍖 饱食度：{pet['hunger']}/100 ({hunger_desc})\n"
        f"😊 快乐度：{pet['happiness']}/100 ({happiness_desc})\n"
        f"🛁 清洁度：{pet['cleanliness']}/100 ({cleanliness_desc})\n"
        f"⭐ 经验值：{pet['exp']}/{level_up_exp}\n"
        f"🎮 互动次数：{pet['total_interactions']}\n"
    )
    
    if event_msg:
        message += f"\n🎲 随机事件：{event_msg}"
    
    # 添加状态提示
    if health < 30:
        message += "\n⚠️ 你的宠物状态很差，快来照顾它吧！"
    elif health > 80:
        message += "\n✨ 你的宠物状态很好！"
    
    await check_pet.send(message)

@feed_pet.handle()
async def handle_feed_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    await decay_pet_status(user_id, group_id)
    
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        await feed_pet.send("你还没有宠物呢！使用'领养宠物'来领养一只吧~")
        return
    
    if pet['hunger'] >= 90:
        await feed_pet.send(f"{pet['pet_name']}已经很饱了，不需要喂食！")
        return
    
    # 喂食效果
    hunger_gain = random.randint(15, 25)
    happiness_gain = random.randint(3, 8)
    exp_gain = random.randint(5, 10)
    score_gain = random.randint(2, 5)
    
    new_hunger = min(100, pet['hunger'] + hunger_gain)
    new_happiness = min(100, pet['happiness'] + happiness_gain)
    new_exp = pet['exp'] + exp_gain
    
    # 检查升级
    level_up = False
    new_level = pet['level']
    level_up_exp = calculate_level_exp(pet['level'])
    
    if new_exp >= level_up_exp:
        new_level += 1
        new_exp -= level_up_exp
        level_up = True
        score_gain += 10  # 升级额外奖励
    
    # 更新数据库
    db.update('virtual_pets', {
        'hunger': new_hunger,
        'happiness': new_happiness,
        'exp': new_exp,
        'level': new_level,
        'total_interactions': pet['total_interactions'] + 1,
        'last_interaction': datetime.now().isoformat()
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 记录互动
    db.insert('pet_interactions', {
        'user_id': user_id,
        'group_id': group_id,
        'interaction_type': '喂食',
        'result': f"饱食度+{hunger_gain}, 快乐度+{happiness_gain}, 经验+{exp_gain}",
        'score_gained': score_gain
    })
    
    # 更新积分
    await update_player_score(user_id, group_id, score_gain, "宠物喂食", "宠物主人", "喂食奖励")
    
    foods = ["美味的小鱼干", "香甜的胡萝卜", "新鲜的蔬菜", "营养丰富的宠物粮", "可口的小零食"]
    food = random.choice(foods)
    
    emoji = get_pet_emoji_by_level(pet['pet_type'], new_level)
    
    message = (
        f"🍽️ 你给{pet['pet_name']}喂了{food}\n"
        f"{emoji} 饱食度：{pet['hunger']} → {new_hunger}\n"
        f"😊 快乐度：{pet['happiness']} → {new_happiness}\n"
        f"⭐ 经验值：+{exp_gain}\n"
        f"💰 获得{score_gain}积分！"
    )
    
    if level_up:
        message += f"\n🎉 恭喜！{pet['pet_name']}升级到了Lv.{new_level}！"
    
    await feed_pet.send(message)

@play_pet.handle()
async def handle_play_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    await decay_pet_status(user_id, group_id)
    
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        await play_pet.send("你还没有宠物呢！使用'领养宠物'来领养一只吧~")
        return
    
    if pet['happiness'] >= 95:
        await play_pet.send(f"{pet['pet_name']}已经很开心了，先让它休息一下吧！")
        return
    
    # 陪玩效果
    happiness_gain = random.randint(15, 25)
    hunger_loss = random.randint(3, 8)
    exp_gain = random.randint(8, 15)
    score_gain = random.randint(3, 6)
    
    new_happiness = min(100, pet['happiness'] + happiness_gain)
    new_hunger = max(0, pet['hunger'] - hunger_loss)
    new_exp = pet['exp'] + exp_gain
    
    # 检查升级
    level_up = False
    new_level = pet['level']
    level_up_exp = calculate_level_exp(pet['level'])
    
    if new_exp >= level_up_exp:
        new_level += 1
        new_exp -= level_up_exp
        level_up = True
        score_gain += 10
    
    # 更新数据库
    db.update('virtual_pets', {
        'happiness': new_happiness,
        'hunger': new_hunger,
        'exp': new_exp,
        'level': new_level,
        'total_interactions': pet['total_interactions'] + 1,
        'last_interaction': datetime.now().isoformat()
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 记录互动
    db.insert('pet_interactions', {
        'user_id': user_id,
        'group_id': group_id,
        'interaction_type': '陪玩',
        'result': f"快乐度+{happiness_gain}, 饱食度-{hunger_loss}, 经验+{exp_gain}",
        'score_gained': score_gain
    })
    
    # 更新积分
    await update_player_score(user_id, group_id, score_gain, "宠物陪玩", "宠物主人", "陪玩奖励")
    
    activities = ["玩球", "捉迷藏", "跑步", "玩玩具", "学新技能", "晒太阳"]
    activity = random.choice(activities)
    
    emoji = get_pet_emoji_by_level(pet['pet_type'], new_level)
    
    message = (
        f"🎮 你和{pet['pet_name']}一起{activity}\n"
        f"{emoji} 快乐度：{pet['happiness']} → {new_happiness}\n"
        f"🍖 饱食度：{pet['hunger']} → {new_hunger}\n"
        f"⭐ 经验值：+{exp_gain}\n"
        f"💰 获得{score_gain}积分！"
    )
    
    if level_up:
        message += f"\n🎉 恭喜！{pet['pet_name']}升级到了Lv.{new_level}！"
    
    await play_pet.send(message)

@clean_pet.handle()
async def handle_clean_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    await decay_pet_status(user_id, group_id)
    
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        await clean_pet.send("你还没有宠物呢！使用'领养宠物'来领养一只吧~")
        return
    
    if pet['cleanliness'] >= 95:
        await clean_pet.send(f"{pet['pet_name']}已经很干净了，不需要清洁！")
        return
    
    # 清洁效果
    cleanliness_gain = random.randint(20, 30)
    happiness_gain = random.randint(5, 10)
    exp_gain = random.randint(3, 8)
    score_gain = random.randint(2, 4)
    
    new_cleanliness = min(100, pet['cleanliness'] + cleanliness_gain)
    new_happiness = min(100, pet['happiness'] + happiness_gain)
    new_exp = pet['exp'] + exp_gain
    
    # 检查升级
    level_up = False
    new_level = pet['level']
    level_up_exp = calculate_level_exp(pet['level'])
    
    if new_exp >= level_up_exp:
        new_level += 1
        new_exp -= level_up_exp
        level_up = True
        score_gain += 10
    
    # 更新数据库
    db.update('virtual_pets', {
        'cleanliness': new_cleanliness,
        'happiness': new_happiness,
        'exp': new_exp,
        'level': new_level,
        'total_interactions': pet['total_interactions'] + 1,
        'last_interaction': datetime.now().isoformat()
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 记录互动
    db.insert('pet_interactions', {
        'user_id': user_id,
        'group_id': group_id,
        'interaction_type': '清洁',
        'result': f"清洁度+{cleanliness_gain}, 快乐度+{happiness_gain}, 经验+{exp_gain}",
        'score_gained': score_gain
    })
    
    # 更新积分
    await update_player_score(user_id, group_id, score_gain, "宠物清洁", "宠物主人", "清洁奖励")
    
    clean_methods = ["洗澡", "梳毛", "刷牙", "修剪指甲", "清理耳朵"]
    method = random.choice(clean_methods)
    
    emoji = get_pet_emoji_by_level(pet['pet_type'], new_level)
    
    message = (
        f"🛁 你给{pet['pet_name']}{method}\n"
        f"{emoji} 清洁度：{pet['cleanliness']} → {new_cleanliness}\n"
        f"😊 快乐度：{pet['happiness']} → {new_happiness}\n"
        f"⭐ 经验值：+{exp_gain}\n"
        f"💰 获得{score_gain}积分！"
    )
    
    if level_up:
        message += f"\n🎉 恭喜！{pet['pet_name']}升级到了Lv.{new_level}！"
    
    await clean_pet.send(message)

@rename_pet.handle()
async def handle_rename_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        await rename_pet.send("你还没有宠物呢！使用'领养宠物'来领养一只吧~")
        return
    
    # 解析新名字
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^改名\s+(.+)$", message_text)
    if not match:
        await rename_pet.send("请输入正确的格式：改名 新名字")
        return
    
    new_name = match.group(1).strip()
    if len(new_name) > 10:
        await rename_pet.send("宠物名字不能超过10个字符！")
        return
    
    old_name = pet['pet_name']
    
    # 更新名字
    db.update('virtual_pets', {
        'pet_name': new_name
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    emoji = get_pet_emoji_by_level(pet['pet_type'], pet['level'])
    await rename_pet.send(f"{emoji} 成功将宠物名字从'{old_name}'改为'{new_name}'！")

@pet_ranking.handle()
async def handle_pet_ranking(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 获取群内宠物排行（按等级和经验排序）
    pets = db.fetch_all(
        'virtual_pets', 
        f"group_id = '{group_id}' ORDER BY level DESC, exp DESC LIMIT 50",
    )
    
    if not pets:
        await pet_ranking.send("本群还没有人养宠物呢！")
        return
    
    message = "🏆 本群宠物排行榜 🏆\n\n"
    
    for i, pet in enumerate(pets, 1):
        emoji = get_pet_emoji_by_level(pet['pet_type'], pet['level'])
        health = (pet['hunger'] + pet['happiness'] + pet['cleanliness']) // 3
        
        # 获取用户昵称（这里简化处理）
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(pet['user_id']))
        nickname = user_info.get('card') or user_info.get('nickname', f"用户{pet['user_id']}")
        
        message += (
            f"{i}. {emoji} {pet['pet_name']} (Lv.{pet['level']})\n"
            f"   主人：{nickname}\n"
            f"   健康度：{health}/100\n"
            f"   互动次数：{pet['total_interactions']}\n\n"
        )
    
    await pet_ranking.send(message.strip())

@release_pet.handle()
async def handle_release_pet(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    pet = db.fetch_one('virtual_pets', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not pet:
        await release_pet.send("你还没有宠物呢！")
        return
    
    # 计算放生奖励
    level_bonus = pet['level'] * 5
    interaction_bonus = min(pet['total_interactions'], 100) // 10
    total_bonus = level_bonus + interaction_bonus + 10
    
    # 删除宠物
    db.delete('virtual_pets', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 奖励积分
    await update_player_score(user_id, group_id, total_bonus, "放生宠物", "宠物主人", "放生奖励")
    
    emoji = PET_TYPES[pet['pet_type']]["emoji"]
    await release_pet.send(
        f"😢 你放生了{pet['pet_name']}...\n"
        f"{emoji} 它会在大自然中快乐生活的！\n"
        f"💰 获得{total_bonus}积分作为纪念\n\n"
        f"感谢你的陪伴！可以重新'领养宠物'哦~"
    )

@pet_help.handle()
async def handle_pet_help(bot: Bot, event: GroupMessageEvent):
    help_text = (
        "🐾 电子宠物系统帮助 🐾\n\n"
        "📋 基础指令：\n"
        "• 领养宠物 [类型] - 领养一只宠物（猫咪/小狗/兔子/小鸟/仓鼠）\n"
        "• 查看宠物 - 查看宠物状态\n"
        "• 改名 [新名字] - 给宠物改名\n"
        "• 放生宠物 - 放生宠物（获得积分奖励）\n\n"
        "🎮 互动指令：\n"
        "• 喂食 - 增加饱食度和快乐度\n"
        "• 陪玩 - 增加快乐度和经验值\n"
        "• 清洁 - 增加清洁度和快乐度\n\n"
        "📊 查询指令：\n"
        "• 宠物排行 - 查看群内宠物排行榜\n\n"
        "💡 游戏机制：\n"
        "• 宠物状态会随时间自然衰减\n"
        "• 互动可获得经验值和积分奖励\n"
        "• 升级时获得额外积分奖励\n"
        "• 15%概率触发随机事件\n"
        "• 健康度 = (饱食度+快乐度+清洁度)/3\n\n"
        "🏆 等级系统：\n"
        "• Lv.1-4: 普通宠物\n"
        "• Lv.5-9: 🏆 金牌宠物\n"
        "• Lv.10-14: 💎 钻石宠物\n"
        "• Lv.15-19: ⭐ 明星宠物\n"
        "• Lv.20+: 👑 王者宠物"
    )
    
    await pet_help.send(help_text)