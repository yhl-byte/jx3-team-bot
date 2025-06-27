'''
@Author: AI Assistant
@Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-27 11:30:47
FilePath: /team-bot/jx3-team-bot/src/plugins/cultivation_game.py
'''
from .database import NianZaiDB
from .game_score import update_player_score
from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
import random
import asyncio
from datetime import datetime, timedelta
import json
import math

db = NianZaiDB()
db.init_db()

# 修仙境界配置
REALMS = {
    1: {"name": "凡人", "emoji": "👤", "max_exp": 100, "power_base": 10},
    2: {"name": "练气期", "emoji": "🌬️", "max_exp": 300, "power_base": 25},
    3: {"name": "筑基期", "emoji": "🏗️", "max_exp": 600, "power_base": 50},
    4: {"name": "结丹期", "emoji": "💊", "max_exp": 1200, "power_base": 100},
    5: {"name": "元婴期", "emoji": "👶", "max_exp": 2500, "power_base": 200},
    6: {"name": "化神期", "emoji": "🧙", "max_exp": 5000, "power_base": 400},
    7: {"name": "炼虚期", "emoji": "🌌", "max_exp": 10000, "power_base": 800},
    8: {"name": "合体期", "emoji": "🔮", "max_exp": 20000, "power_base": 1600},
    9: {"name": "大乘期", "emoji": "⚡", "max_exp": 40000, "power_base": 3200},
    10: {"name": "渡劫期", "emoji": "⛈️", "max_exp": 80000, "power_base": 6400},
    11: {"name": "仙人", "emoji": "🧚", "max_exp": 999999, "power_base": 12800}
}

# 副本配置
DUNGEONS = {
    "新手洞穴": {
        "level_req": 1,
        "monsters": [
            {"name": "野兔", "hp": 20, "attack": 5, "exp": 10, "score": 2},
            {"name": "野狼", "hp": 40, "attack": 8, "exp": 20, "score": 5}
        ],
        "boss": {"name": "洞穴之王", "hp": 100, "attack": 15, "exp": 50, "score": 20},
        "rewards": ["破旧的剑", "草药", "铜币"]
    },
    "幽暗森林": {
        "level_req": 3,
        "monsters": [
            {"name": "毒蜘蛛", "hp": 80, "attack": 15, "exp": 30, "score": 8},
            {"name": "树妖", "hp": 120, "attack": 20, "exp": 45, "score": 12}
        ],
        "boss": {"name": "森林守护者", "hp": 300, "attack": 35, "exp": 120, "score": 50},
        "rewards": ["精铁剑", "灵草", "银币"]
    },
    "烈焰山谷": {
        "level_req": 5,
        "monsters": [
            {"name": "火蜥蜴", "hp": 200, "attack": 30, "exp": 60, "score": 15},
            {"name": "岩浆兽", "hp": 300, "attack": 40, "exp": 80, "score": 20}
        ],
        "boss": {"name": "炎魔王", "hp": 800, "attack": 70, "exp": 250, "score": 100},
        "rewards": ["烈焰刀", "火灵珠", "金币"]
    },
    "冰雪秘境": {
        "level_req": 7,
        "monsters": [
            {"name": "冰霜狼", "hp": 400, "attack": 50, "exp": 100, "score": 25},
            {"name": "雪怪", "hp": 600, "attack": 65, "exp": 150, "score": 35}
        ],
        "boss": {"name": "冰雪女王", "hp": 1500, "attack": 120, "exp": 500, "score": 200},
        "rewards": ["寒冰剑", "冰心", "灵石"]
    },
    "天劫雷池": {
        "level_req": 9,
        "monsters": [
            {"name": "雷灵", "hp": 800, "attack": 80, "exp": 200, "score": 50},
            {"name": "雷兽", "hp": 1200, "attack": 100, "exp": 300, "score": 75}
        ],
        "boss": {"name": "雷神", "hp": 3000, "attack": 200, "exp": 1000, "score": 500},
        "rewards": ["雷神锤", "雷珠", "仙石"]
    }
}

# 装备配置
EQUIPMENT = {
    "破旧的剑": {"type": "weapon", "attack": 5, "rarity": "普通"},
    "精铁剑": {"type": "weapon", "attack": 15, "rarity": "优秀"},
    "烈焰刀": {"type": "weapon", "attack": 30, "rarity": "稀有"},
    "寒冰剑": {"type": "weapon", "attack": 50, "rarity": "史诗"},
    "雷神锤": {"type": "weapon", "attack": 80, "rarity": "传说"},
    "草药": {"type": "consumable", "effect": "hp", "value": 50},
    "灵草": {"type": "consumable", "effect": "hp", "value": 100},
    "火灵珠": {"type": "accessory", "attack": 10, "rarity": "稀有"},
    "冰心": {"type": "accessory", "defense": 20, "rarity": "史诗"},
    "雷珠": {"type": "accessory", "attack": 25, "defense": 15, "rarity": "传说"}
}

# 技能配置
SKILLS = {
    "基础剑法": {"level_req": 1, "damage_mult": 1.2, "cost": 10, "cooldown": 0},
    "烈焰斩": {"level_req": 3, "damage_mult": 1.5, "cost": 20, "cooldown": 1},
    "冰霜术": {"level_req": 5, "damage_mult": 1.8, "cost": 30, "cooldown": 2},
    "雷电术": {"level_req": 7, "damage_mult": 2.2, "cost": 50, "cooldown": 3},
    "天劫神雷": {"level_req": 9, "damage_mult": 3.0, "cost": 100, "cooldown": 5}
}

# 注册命令
start_cultivation = on_regex(pattern=r"^开始修仙$", priority=5)
check_status = on_regex(pattern=r"^修仙状态$", priority=5)
cultivate = on_regex(pattern=r"^修炼$", priority=5)
enter_dungeon = on_regex(pattern=r"^进入副本\s*(.*)$", priority=5)
check_dungeons = on_regex(pattern=r"^副本列表$", priority=5)
check_inventory = on_regex(pattern=r"^背包$", priority=5)
equip_item = on_regex(pattern=r"^装备\s+(.+)$", priority=5)
learn_skill = on_regex(pattern=r"^学习技能\s+(.+)$", priority=5)
check_skills = on_regex(pattern=r"^技能列表$", priority=5)
cultivation_ranking = on_regex(pattern=r"^修仙排行$", priority=5)
cultivation_help = on_regex(pattern=r"^修仙帮助$", priority=5)
reset_cultivation = on_regex(pattern=r"^重新修仙$", priority=5)


def get_realm_info(level: int) -> dict:
    """获取境界信息"""
    return REALMS.get(level, REALMS[11])

def calculate_power(cultivator: dict) -> int:
    """计算战力"""
    realm_info = get_realm_info(cultivator['realm_level'])
    base_power = realm_info['power_base']
    
    # 装备加成
    weapon_bonus = 0
    accessory_bonus = 0
    
    if cultivator['equipped_weapon'] and cultivator['equipped_weapon'] in EQUIPMENT:
        weapon_bonus = EQUIPMENT[cultivator['equipped_weapon']].get('attack', 0)
    
    if cultivator['equipped_accessory'] and cultivator['equipped_accessory'] in EQUIPMENT:
        accessory_bonus = EQUIPMENT[cultivator['equipped_accessory']].get('attack', 0)
    
    return base_power + weapon_bonus + accessory_bonus + cultivator['attack']

async def restore_mp(user_id: str, group_id: str):
    """恢复法力值"""
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        return
    
    # 计算时间差
    last_cultivation = datetime.fromisoformat(cultivator['last_cultivation'])
    now = datetime.now()
    hours_passed = (now - last_cultivation).total_seconds() / 3600
    
    if hours_passed >= 1:  # 每小时恢复法力
        mp_restore = min(int(hours_passed) * 10, cultivator['max_mp'] - cultivator['mp'])
        if mp_restore > 0:
            db.update('cultivators', {
                'mp': cultivator['mp'] + mp_restore
            }, f"user_id = '{user_id}' AND group_id = '{group_id}'")

@start_cultivation.handle()
async def handle_start_cultivation(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否已开始修仙
    existing = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if existing:
        await start_cultivation.send("你已经踏上修仙之路了！使用'修仙状态'查看当前境界")
        return
    
    # 创建修仙者
    db.insert('cultivators', {
        'user_id': user_id,
        'group_id': group_id
    })
    
    # 给予初始装备
    db.insert('cultivation_inventory', {
        'user_id': user_id,
        'group_id': group_id,
        'item_name': '破旧的剑',
        'quantity': 1
    })
    
    # 学习基础技能
    db.insert('cultivation_skills', {
        'user_id': user_id,
        'group_id': group_id,
        'skill_name': '基础剑法'
    })
    
    # 奖励积分
    await update_player_score(user_id, group_id, 50, "开始修仙", "修仙者", "入门奖励")
    
    await start_cultivation.send(
        "🌟 恭喜你踏上修仙之路！\n"
        "👤 当前境界：凡人\n"
        "⚔️ 获得装备：破旧的剑\n"
        "📚 学会技能：基础剑法\n"
        "💰 获得50积分奖励！\n\n"
        "使用'修仙帮助'查看更多指令"
    )

@check_status.handle()
async def handle_check_status(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    await restore_mp(user_id, group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await check_status.send("你还未开始修仙！使用'开始修仙'踏上修仙之路")
        return
    
    realm_info = get_realm_info(cultivator['realm_level'])
    power = calculate_power(cultivator)
    
    # 计算下一境界所需经验
    next_realm_exp = realm_info['max_exp'] if cultivator['realm_level'] < 11 else "已达巅峰"
    
    message = (
        f"{realm_info['emoji']} 修仙状态 {realm_info['emoji']}\n\n"
        f"🏆 境界：{realm_info['name']} (Lv.{cultivator['realm_level']})\n"
        f"⭐ 经验：{cultivator['exp']}/{next_realm_exp}\n"
        f"❤️ 生命：{cultivator['hp']}/{cultivator['max_hp']}\n"
        f"💙 法力：{cultivator['mp']}/{cultivator['max_mp']}\n"
        f"⚔️ 攻击：{cultivator['attack']}\n"
        f"🛡️ 防御：{cultivator['defense']}\n"
        f"💪 战力：{power}\n"
        f"🎮 战斗次数：{cultivator['total_battles']}\n\n"
    )
    
    # 显示装备
    if cultivator['equipped_weapon']:
        weapon_info = EQUIPMENT.get(cultivator['equipped_weapon'], {})
        message += f"⚔️ 武器：{cultivator['equipped_weapon']} (+{weapon_info.get('attack', 0)}攻击)\n"
    else:
        message += "⚔️ 武器：无\n"
    
    if cultivator['equipped_accessory']:
        acc_info = EQUIPMENT.get(cultivator['equipped_accessory'], {})
        message += f"💎 饰品：{cultivator['equipped_accessory']}\n"
    else:
        message += "💎 饰品：无\n"
    
    await check_status.send(message.strip())

@cultivate.handle()
async def handle_cultivate(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await cultivate.send("你还未开始修仙！使用'开始修仙'踏上修仙之路")
        return
    
    # 检查修炼冷却
    last_cultivation = datetime.fromisoformat(cultivator['last_cultivation'])
    now = datetime.now()
    cooldown = timedelta(minutes=30)  # 30分钟冷却
    
    if now - last_cultivation < cooldown:
        remaining = cooldown - (now - last_cultivation)
        minutes = int(remaining.total_seconds() / 60)
        await cultivate.send(f"修炼需要时间沉淀，请{minutes}分钟后再试")
        return
    
    # 修炼效果
    realm_info = get_realm_info(cultivator['realm_level'])
    base_exp = random.randint(10, 25)
    bonus_exp = cultivator['realm_level'] * 2
    total_exp = base_exp + bonus_exp
    
    # 随机事件
    events = [
        {"type": "normal", "message": "你静心修炼，感悟颇深", "exp_mult": 1.0},
        {"type": "good", "message": "你突然顿悟，修为大增！", "exp_mult": 1.5},
        {"type": "excellent", "message": "天降异象，你获得了天地灵气加持！", "exp_mult": 2.0},
        {"type": "bad", "message": "修炼时走火入魔，进展缓慢...", "exp_mult": 0.5}
    ]
    
    event_weights = [70, 20, 5, 5]  # 概率权重
    event = random.choices(events, weights=event_weights)[0]
    
    final_exp = int(total_exp * event['exp_mult'])
    new_exp = cultivator['exp'] + final_exp
    
    # 检查突破
    breakthrough = False
    new_realm = cultivator['realm_level']
    score_gain = random.randint(5, 15)
    
    if new_exp >= realm_info['max_exp'] and cultivator['realm_level'] < 11:
        new_realm += 1
        new_exp = 0
        breakthrough = True
        score_gain += 50  # 突破奖励
        
        # 提升属性
        new_max_hp = cultivator['max_hp'] + 20
        new_max_mp = cultivator['max_mp'] + 10
        new_attack = cultivator['attack'] + 5
        new_defense = cultivator['defense'] + 3
        
        db.update('cultivators', {
            'realm_level': new_realm,
            'exp': new_exp,
            'max_hp': new_max_hp,
            'hp': new_max_hp,  # 突破时恢复满血
            'max_mp': new_max_mp,
            'mp': new_max_mp,  # 突破时恢复满法力
            'attack': new_attack,
            'defense': new_defense,
            'last_cultivation': now.isoformat()
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    else:
        db.update('cultivators', {
            'exp': new_exp,
            'last_cultivation': now.isoformat()
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 更新积分
    await update_player_score(user_id, group_id, score_gain, "修炼", "修仙者", event['type'])
    
    message = (
        f"🧘 {event['message']}\n"
        f"⭐ 获得经验：{final_exp}\n"
        f"💰 获得积分：{score_gain}\n"
    )
    
    if breakthrough:
        new_realm_info = get_realm_info(new_realm)
        message += (
            f"\n🎉 恭喜突破到{new_realm_info['emoji']} {new_realm_info['name']}！\n"
            f"📈 属性全面提升！\n"
            f"❤️ 生命值：{cultivator['max_hp']} → {new_max_hp}\n"
            f"💙 法力值：{cultivator['max_mp']} → {new_max_mp}\n"
            f"⚔️ 攻击力：{cultivator['attack']} → {new_attack}\n"
            f"🛡️ 防御力：{cultivator['defense']} → {new_defense}"
        )
    
    await cultivate.send(message)

@check_dungeons.handle()
async def handle_check_dungeons(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await check_dungeons.send("你还未开始修仙！使用'开始修仙'踏上修仙之路")
        return
    
    message = "🏰 副本列表 🏰\n\n"
    
    for dungeon_name, dungeon_info in DUNGEONS.items():
        status = "✅" if cultivator['realm_level'] >= dungeon_info['level_req'] else "❌"
        message += (
            f"{status} {dungeon_name}\n"
            f"   要求境界：Lv.{dungeon_info['level_req']}\n"
            f"   奖励：{', '.join(dungeon_info['rewards'])}\n\n"
        )
    
    message += "使用'进入副本 副本名'挑战副本"
    await check_dungeons.send(message)

@enter_dungeon.handle()
async def handle_enter_dungeon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await enter_dungeon.send("你还未开始修仙！使用'开始修仙'踏上修仙之路")
        return
    
    # 解析副本名
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^进入副本\s*(.*)$", message_text)
    dungeon_name = match.group(1).strip() if match and match.group(1).strip() else None
    
    if not dungeon_name:
        await enter_dungeon.send("请指定副本名称！使用'副本列表'查看可用副本")
        return
    
    if dungeon_name not in DUNGEONS:
        await enter_dungeon.send(f"副本'{dungeon_name}'不存在！使用'副本列表'查看可用副本")
        return
    
    dungeon = DUNGEONS[dungeon_name]
    
    # 检查境界要求
    if cultivator['realm_level'] < dungeon['level_req']:
        await enter_dungeon.send(f"境界不足！需要达到Lv.{dungeon['level_req']}才能进入{dungeon_name}")
        return
    
    # 检查生命值
    if cultivator['hp'] < cultivator['max_hp'] * 0.3:
        await enter_dungeon.send("生命值过低，无法进入副本！请先休息恢复")
        return
    
    # 开始战斗
    player_power = calculate_power(cultivator)
    total_exp = 0
    total_score = 0
    battle_log = []
    
    # 战斗小怪
    for monster in dungeon['monsters']:
        monster_hp = monster['hp']
        battle_log.append(f"🔥 遭遇 {monster['name']}！")
        
        # 简化战斗计算
        damage_to_monster = max(1, player_power - monster['hp'] // 10)
        damage_to_player = max(1, monster['attack'] - cultivator['defense'])
        
        rounds = math.ceil(monster_hp / damage_to_monster)
        player_damage_taken = rounds * damage_to_player
        
        if cultivator['hp'] <= player_damage_taken:
            # 战斗失败
            db.update('cultivators', {
                'hp': max(1, cultivator['hp'] - player_damage_taken // 2),
                'total_battles': cultivator['total_battles'] + 1
            }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
            
            await enter_dungeon.send(
                f"💀 在{dungeon_name}中战败了！\n"
                f"被{monster['name']}击败，损失部分生命值\n"
                f"请休息后再来挑战"
            )
            return
        
        # 战斗胜利
        cultivator['hp'] -= player_damage_taken
        total_exp += monster['exp']
        total_score += monster['score']
        battle_log.append(f"✅ 击败了 {monster['name']}！")
    
    # 挑战BOSS
    boss = dungeon['boss']
    battle_log.append(f"\n👹 最终BOSS：{boss['name']}出现！")
    
    boss_damage_to_player = max(1, boss['attack'] - cultivator['defense'])
    boss_rounds = math.ceil(boss['hp'] / player_power)
    boss_damage_taken = boss_rounds * boss_damage_to_player
    
    if cultivator['hp'] <= boss_damage_taken:
        # BOSS战失败
        db.update('cultivators', {
            'hp': max(1, cultivator['hp'] - boss_damage_taken // 2),
            'total_battles': cultivator['total_battles'] + 1
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        await enter_dungeon.send(
            f"💀 被{boss['name']}击败了！\n"
            f"虽然击败了所有小怪，但在BOSS面前败北\n"
            f"获得了{total_exp}经验和{total_score}积分作为安慰奖"
        )
        
        # 给予部分奖励
        if total_score > 0:
            await update_player_score(user_id, group_id, total_score, f"{dungeon_name}副本", "修仙者", "失败奖励")
        
        return
    
    # 完全胜利
    cultivator['hp'] -= boss_damage_taken
    total_exp += boss['exp']
    total_score += boss['score']
    battle_log.append(f"🏆 击败了BOSS {boss['name']}！")
    
    # 随机掉落装备
    dropped_item = random.choice(dungeon['rewards'])
    
    # 更新数据库
    new_exp = cultivator['exp'] + total_exp
    realm_info = get_realm_info(cultivator['realm_level'])
    
    # 检查升级
    breakthrough = False
    new_realm = cultivator['realm_level']
    
    if new_exp >= realm_info['max_exp'] and cultivator['realm_level'] < 11:
        new_realm += 1
        new_exp = 0
        breakthrough = True
        total_score += 100  # 突破额外奖励
    
    db.update('cultivators', {
        'exp': new_exp,
        'realm_level': new_realm,
        'hp': cultivator['hp'],
        'total_battles': cultivator['total_battles'] + 1
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 添加装备到背包
    existing_item = db.fetch_one('cultivation_inventory', 
                                f"user_id = ? AND group_id = ? AND item_name = ?", 
                                (user_id, group_id, dropped_item))
    if existing_item:
        db.update('cultivation_inventory', {
            'quantity': existing_item['quantity'] + 1
        }, f"user_id = '{user_id}' AND group_id = '{group_id}' AND item_name = '{dropped_item}'")
    else:
        db.insert('cultivation_inventory', {
            'user_id': user_id,
            'group_id': group_id,
            'item_name': dropped_item,
            'quantity': 1
        })
    
    # 记录战斗
    db.insert('cultivation_battles', {
        'user_id': user_id,
        'group_id': group_id,
        'dungeon_name': dungeon_name,
        'monster_name': boss['name'],
        'result': '胜利',
        'exp_gained': total_exp,
        'score_gained': total_score
    })
    
    # 更新积分
    await update_player_score(user_id, group_id, total_score, f"{dungeon_name}副本", "修仙者", "胜利奖励")
    
    # 构建结果消息
    result_message = "\n".join(battle_log)
    result_message += (
        f"\n\n🎉 副本通关成功！\n"
        f"⭐ 获得经验：{total_exp}\n"
        f"💰 获得积分：{total_score}\n"
        f"🎁 获得装备：{dropped_item}\n"
        f"❤️ 剩余生命：{cultivator['hp']}/{cultivator['max_hp']}"
    )
    
    if breakthrough:
        new_realm_info = get_realm_info(new_realm)
        result_message += f"\n\n🎊 恭喜突破到{new_realm_info['emoji']} {new_realm_info['name']}！"
    
    await enter_dungeon.send(result_message)

@check_inventory.handle()
async def handle_check_inventory(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await check_inventory.send("你还未开始修仙！使用'开始修仙'踏上修仙之路")
        return
    
    items = db.fetch_all('cultivation_inventory', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    if not items:
        await check_inventory.send("背包空空如也...")
        return
    
    message = "🎒 修仙背包 🎒\n\n"
    
    # 按类型分组显示
    weapons = []
    accessories = []
    consumables = []
    others = []
    
    for item in items:
        item_name = item['item_name']
        quantity = item['quantity']
        
        if item_name in EQUIPMENT:
            equipment_info = EQUIPMENT[item_name]
            if equipment_info['type'] == 'weapon':
                weapons.append(f"⚔️ {item_name} x{quantity} (+{equipment_info.get('attack', 0)}攻击)")
            elif equipment_info['type'] == 'accessory':
                accessories.append(f"💎 {item_name} x{quantity}")
            elif equipment_info['type'] == 'consumable':
                consumables.append(f"🧪 {item_name} x{quantity} (恢复{equipment_info.get('value', 0)}生命)")
        else:
            others.append(f"📦 {item_name} x{quantity}")
    
    if weapons:
        message += "武器：\n" + "\n".join(weapons) + "\n\n"
    if accessories:
        message += "饰品：\n" + "\n".join(accessories) + "\n\n"
    if consumables:
        message += "消耗品：\n" + "\n".join(consumables) + "\n\n"
    if others:
        message += "其他：\n" + "\n".join(others) + "\n\n"
    
    message += "使用'装备 物品名'来装备物品"
    
    await check_inventory.send(message.strip())

@equip_item.handle()
async def handle_equip_item(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await equip_item.send("你还未开始修仙！使用'开始修仙'踏上修仙之路")
        return
    
    # 解析物品名
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^装备\s+(.+)$", message_text)
    if not match:
        await equip_item.send("请输入正确的格式：装备 物品名")
        return
    
    item_name = match.group(1).strip()
    
    # 检查背包中是否有该物品
    item = db.fetch_one('cultivation_inventory', 
                       f"user_id = ? AND group_id = ? AND item_name = ?", 
                       (user_id, group_id, item_name))
    if not item:
        await equip_item.send(f"背包中没有'{item_name}'")
        return
    
    # 检查是否为装备
    if item_name not in EQUIPMENT:
        await equip_item.send(f"'{item_name}'不是装备！")
        return
    
    equipment_info = EQUIPMENT[item_name]
    
    if equipment_info['type'] == 'weapon':
        # 装备武器
        old_weapon = cultivator['equipped_weapon']
        db.update('cultivators', {
            'equipped_weapon': item_name
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        message = f"⚔️ 成功装备武器：{item_name}\n"
        if old_weapon:
            message += f"替换了原来的：{old_weapon}"
        
    elif equipment_info['type'] == 'accessory':
        # 装备饰品
        old_accessory = cultivator['equipped_accessory']
        db.update('cultivators', {
            'equipped_accessory': item_name
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        message = f"💎 成功装备饰品：{item_name}\n"
        if old_accessory:
            message += f"替换了原来的：{old_accessory}"
    
    elif equipment_info['type'] == 'consumable':
        # 使用消耗品
        heal_value = equipment_info.get('value', 0)
        new_hp = min(cultivator['max_hp'], cultivator['hp'] + heal_value)
        hp_restored = new_hp - cultivator['hp']
        
        db.update('cultivators', {
            'hp': new_hp
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        # 减少物品数量
        if item['quantity'] > 1:
            db.update('cultivation_inventory', {
                'quantity': item['quantity'] - 1
            }, f"user_id = '{user_id}' AND group_id = '{group_id}' AND item_name = '{item_name}'")
        else:
            db.delete('cultivation_inventory', 
                     f"user_id = '{user_id}' AND group_id = '{group_id}' AND item_name = '{item_name}'")
        
        message = f"🧪 使用了{item_name}，恢复了{hp_restored}点生命值！"
    
    else:
        await equip_item.send(f"'{item_name}'无法装备！")
        return
    
    await equip_item.send(message)

@cultivation_ranking.handle()
async def handle_cultivation_ranking(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 获取群内修仙者排行（按境界和经验排序）
    cultivators = db.fetch_all(
        'cultivators', 
        f"group_id = '{group_id}' ORDER BY realm_level DESC, exp DESC", 
    )
    
    if not cultivators:
        await cultivation_ranking.send("本群还没有人开始修仙呢！")
        return
    
    message = "🏆 修仙排行榜 🏆\n\n"
    
    for i, cultivator in enumerate(cultivators, 1):
        realm_info = get_realm_info(cultivator['realm_level'])
        power = calculate_power(cultivator)
        
        # 获取用户昵称
        try:
            user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(cultivator['user_id']))
            nickname = user_info.get('card') or user_info.get('nickname', f"用户{cultivator['user_id']}")
        except:
            nickname = f"用户{cultivator['user_id']}"
        
        message += (
            f"{i}. {realm_info['emoji']} {nickname}\n"
            f"   境界：{realm_info['name']} (Lv.{cultivator['realm_level']})\n"
            f"   战力：{power}\n"
            f"   战斗：{cultivator['total_battles']}次\n\n"
        )
    
    await cultivation_ranking.send(message.strip())

@cultivation_help.handle()
async def handle_cultivation_help(bot: Bot, event: GroupMessageEvent):
    help_text = (
        "⚡ 修仙系统帮助 ⚡\n\n"
        "📋 基础指令：\n"
        "• 开始修仙 - 踏上修仙之路\n"
        "• 修仙状态 - 查看当前境界和属性\n"
        "• 修炼 - 提升修为（30分钟冷却）\n"
        "• 重新修仙 - 重置修仙进度\n\n"
        "🏰 副本系统：\n"
        "• 副本列表 - 查看所有副本\n"
        "• 进入副本 [副本名] - 挑战副本\n\n"
        "🎒 装备系统：\n"
        "• 背包 - 查看背包物品\n"
        "• 装备 [物品名] - 装备武器/饰品或使用消耗品\n\n"
        "📊 查询指令：\n"
        "• 修仙排行 - 查看群内修仙排行榜\n\n"
        "🌟 境界系统：\n"
        "👤 凡人 → 🌬️ 练气期 → 🏗️ 筑基期 → 💊 结丹期\n"
        "👶 元婴期 → 🧙 化神期 → 🌌 炼虚期 → 🔮 合体期\n"
        "⚡ 大乘期 → ⛈️ 渡劫期 → 🧚 仙人\n\n"
        "💡 游戏机制：\n"
        "• 修炼可获得经验值和积分奖励\n"
        "• 突破境界时属性全面提升\n"
        "• 副本挑战可获得装备和大量奖励\n"
        "• 装备可以提升战斗力\n"
        "• 生命值过低时无法进入副本\n"
        "• 法力值每小时自动恢复"
    )
    
    await cultivation_help.send(help_text)

@reset_cultivation.handle()
async def handle_reset_cultivation(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    cultivator = db.fetch_one('cultivators', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not cultivator:
        await reset_cultivation.send("你还未开始修仙！")
        return
    
    # 计算重置奖励（根据境界给予积分）
    reset_bonus = cultivator['realm_level'] * 20 + cultivator['total_battles'] * 2
    
    # 删除所有相关数据
    db.delete('cultivators', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    db.delete('cultivation_inventory', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    db.delete('cultivation_skills', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    # 奖励积分
    await update_player_score(user_id, group_id, reset_bonus, "重新修仙", "修仙者", "重置奖励")
    
    realm_info = get_realm_info(cultivator['realm_level'])
    await reset_cultivation.send(
        f"🔄 修仙之路重新开始！\n"
        f"告别了{realm_info['emoji']} {realm_info['name']}的境界\n"
        f"💰 获得{reset_bonus}积分作为重修奖励\n\n"
        f"使用'开始修仙'重新踏上修仙之路！"
    )