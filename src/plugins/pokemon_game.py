'''
@Author: AI Assistant
@Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-27 09:56:11
FilePath: /team-bot/jx3-team-bot/src/plugins/pokemon_game.py
'''
from .database import NianZaiDB
from .game_score import update_player_score
from nonebot.typing import T_State
from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
import random
import asyncio
from datetime import datetime, timedelta
import time
import json
import math

db = NianZaiDB()
db.init_db()

# 精灵属性类型
TYPES = {
    "火": {"emoji": "🔥", "strong_against": ["草", "冰", "虫"], "weak_against": ["水", "地", "岩"]},
    "水": {"emoji": "💧", "strong_against": ["火", "地", "岩"], "weak_against": ["草", "电"]},
    "草": {"emoji": "🌿", "strong_against": ["水", "地", "岩"], "weak_against": ["火", "冰", "毒", "飞", "虫"]},
    "电": {"emoji": "⚡", "strong_against": ["水", "飞"], "weak_against": ["地"]},
    "冰": {"emoji": "❄️", "strong_against": ["草", "地", "飞", "龙"], "weak_against": ["火", "格", "岩", "钢"]},
    "格": {"emoji": "👊", "strong_against": ["普", "冰", "岩", "恶", "钢"], "weak_against": ["飞", "超", "妖"]},
    "毒": {"emoji": "☠️", "strong_against": ["草", "妖"], "weak_against": ["地", "岩", "幽", "钢"]},
    "地": {"emoji": "🌍", "strong_against": ["火", "电", "毒", "岩", "钢"], "weak_against": ["草", "冰", "水"]},
    "飞": {"emoji": "🦅", "strong_against": ["草", "格", "虫"], "weak_against": ["电", "冰", "岩"]},
    "超": {"emoji": "🔮", "strong_against": ["格", "毒"], "weak_against": ["虫", "幽", "恶"]},
    "虫": {"emoji": "🐛", "strong_against": ["草", "超", "恶"], "weak_against": ["火", "飞", "岩"]},
    "岩": {"emoji": "🗿", "strong_against": ["火", "冰", "飞", "虫"], "weak_against": ["水", "草", "格", "地", "钢"]},
    "幽": {"emoji": "👻", "strong_against": ["超", "幽"], "weak_against": ["幽", "恶"]},
    "龙": {"emoji": "🐉", "strong_against": ["龙"], "weak_against": ["冰", "龙", "妖"]},
    "恶": {"emoji": "😈", "strong_against": ["超", "幽"], "weak_against": ["格", "虫", "妖"]},
    "钢": {"emoji": "⚙️", "strong_against": ["冰", "岩", "妖"], "weak_against": ["火", "格", "地"]},
    "妖": {"emoji": "🧚", "strong_against": ["格", "龙", "恶"], "weak_against": ["毒", "钢"]},
    "普": {"emoji": "⭐", "strong_against": [], "weak_against": ["格"]}
}

# 精灵数据库
POKEMON_DATA = {
    # 火系
    "小火龙": {"type": "火", "rarity": "普通", "base_hp": 39, "base_attack": 52, "base_defense": 43, "base_speed": 65, "evolution": "火恐龙", "evolution_level": 16},
    "火恐龙": {"type": "火", "rarity": "稀有", "base_hp": 58, "base_attack": 64, "base_defense": 58, "base_speed": 80, "evolution": "喷火龙", "evolution_level": 36},
    "喷火龙": {"type": "火", "rarity": "史诗", "base_hp": 78, "base_attack": 84, "base_defense": 78, "base_speed": 100, "evolution": None, "evolution_level": None},
    
    # 水系
    "杰尼龟": {"type": "水", "rarity": "普通", "base_hp": 44, "base_attack": 48, "base_defense": 65, "base_speed": 43, "evolution": "卡咪龟", "evolution_level": 16},
    "卡咪龟": {"type": "水", "rarity": "稀有", "base_hp": 59, "base_attack": 63, "base_defense": 80, "base_speed": 58, "evolution": "水箭龟", "evolution_level": 36},
    "水箭龟": {"type": "水", "rarity": "史诗", "base_hp": 79, "base_attack": 83, "base_defense": 100, "base_speed": 78, "evolution": None, "evolution_level": None},
    
    # 草系
    "妙蛙种子": {"type": "草", "rarity": "普通", "base_hp": 45, "base_attack": 49, "base_defense": 49, "base_speed": 45, "evolution": "妙蛙草", "evolution_level": 16},
    "妙蛙草": {"type": "草", "rarity": "稀有", "base_hp": 60, "base_attack": 62, "base_defense": 63, "base_speed": 60, "evolution": "妙蛙花", "evolution_level": 32},
    "妙蛙花": {"type": "草", "rarity": "史诗", "base_hp": 80, "base_attack": 82, "base_defense": 83, "base_speed": 80, "evolution": None, "evolution_level": None},
    
    # 电系
    "皮卡丘": {"type": "电", "rarity": "稀有", "base_hp": 35, "base_attack": 55, "base_defense": 40, "base_speed": 90, "evolution": "雷丘", "evolution_level": 25},
    "雷丘": {"type": "电", "rarity": "史诗", "base_hp": 60, "base_attack": 90, "base_defense": 55, "base_speed": 110, "evolution": None, "evolution_level": None},
    
    # 超能力系
    "凯西": {"type": "超", "rarity": "稀有", "base_hp": 25, "base_attack": 20, "base_defense": 15, "base_speed": 90, "evolution": "勇基拉", "evolution_level": 16},
    "勇基拉": {"type": "超", "rarity": "史诗", "base_hp": 40, "base_attack": 35, "base_defense": 30, "base_speed": 105, "evolution": "胡地", "evolution_level": 40},
    "胡地": {"type": "超", "rarity": "传说", "base_hp": 55, "base_attack": 50, "base_defense": 45, "base_speed": 120, "evolution": None, "evolution_level": None},
    
    # 龙系
    "迷你龙": {"type": "龙", "rarity": "史诗", "base_hp": 41, "base_attack": 64, "base_defense": 45, "base_speed": 50, "evolution": "哈克龙", "evolution_level": 30},
    "哈克龙": {"type": "龙", "rarity": "传说", "base_hp": 61, "base_attack": 84, "base_defense": 65, "base_speed": 70, "evolution": "快龙", "evolution_level": 55},
    "快龙": {"type": "龙", "rarity": "神话", "base_hp": 91, "base_attack": 134, "base_defense": 95, "base_speed": 80, "evolution": None, "evolution_level": None},
    
    # 其他精灵
    "波波": {"type": "飞", "rarity": "普通", "base_hp": 40, "base_attack": 45, "base_defense": 40, "base_speed": 56, "evolution": "比比鸟", "evolution_level": 18},
    "比比鸟": {"type": "飞", "rarity": "稀有", "base_hp": 63, "base_attack": 60, "base_defense": 55, "base_speed": 71, "evolution": "大比鸟", "evolution_level": 36},
    "大比鸟": {"type": "飞", "rarity": "史诗", "base_hp": 83, "base_attack": 80, "base_defense": 75, "base_speed": 101, "evolution": None, "evolution_level": None},
    
    "小拳石": {"type": "岩", "rarity": "普通", "base_hp": 40, "base_attack": 80, "base_defense": 100, "base_speed": 20, "evolution": "隆隆石", "evolution_level": 25},
    "隆隆石": {"type": "岩", "rarity": "稀有", "base_hp": 55, "base_attack": 95, "base_defense": 115, "base_speed": 35, "evolution": "隆隆岩", "evolution_level": 40},
    "隆隆岩": {"type": "岩", "rarity": "史诗", "base_hp": 80, "base_attack": 120, "base_defense": 130, "base_speed": 45, "evolution": None, "evolution_level": None},

    # === 帕鲁系列 ===
    # 火系帕鲁
    "炎煌": {"type": "火", "rarity": "稀有", "base_hp": 70, "base_attack": 85, "base_defense": 60, "base_speed": 75, "evolution": "炎煌王", "evolution_level": 35},
    "炎煌王": {"type": "火", "rarity": "史诗", "base_hp": 95, "base_attack": 115, "base_defense": 80, "base_speed": 90, "evolution": None, "evolution_level": None},
    "火绒狐": {"type": "火", "rarity": "普通", "base_hp": 50, "base_attack": 60, "base_defense": 45, "base_speed": 80, "evolution": "九尾狐", "evolution_level": 28},
    "九尾狐": {"type": "火", "rarity": "史诗", "base_hp": 75, "base_attack": 90, "base_defense": 70, "base_speed": 110, "evolution": None, "evolution_level": None},
    
    # 水系帕鲁
    "冲浪鸭": {"type": "水", "rarity": "普通", "base_hp": 55, "base_attack": 50, "base_defense": 55, "base_speed": 65, "evolution": "冲浪王", "evolution_level": 30},
    "冲浪王": {"type": "水", "rarity": "稀有", "base_hp": 80, "base_attack": 75, "base_defense": 80, "base_speed": 85, "evolution": None, "evolution_level": None},
    "水灵": {"type": "水", "rarity": "史诗", "base_hp": 85, "base_attack": 70, "base_defense": 90, "base_speed": 95, "evolution": None, "evolution_level": None},
    
    # 草系帕鲁
    "草莓兽": {"type": "草", "rarity": "普通", "base_hp": 60, "base_attack": 45, "base_defense": 60, "base_speed": 50, "evolution": "草莓王", "evolution_level": 25},
    "草莓王": {"type": "草", "rarity": "稀有", "base_hp": 85, "base_attack": 70, "base_defense": 85, "base_speed": 70, "evolution": None, "evolution_level": None},
    "花冠龙": {"type": "草", "rarity": "传说", "base_hp": 100, "base_attack": 95, "base_defense": 100, "base_speed": 85, "evolution": None, "evolution_level": None},
    
    # 电系帕鲁
    "雷鸣鸟": {"type": "电", "rarity": "稀有", "base_hp": 65, "base_attack": 95, "base_defense": 50, "base_speed": 120, "evolution": None, "evolution_level": None},
    "电击猫": {"type": "电", "rarity": "普通", "base_hp": 45, "base_attack": 65, "base_defense": 40, "base_speed": 85, "evolution": "雷电猫", "evolution_level": 22},
    "雷电猫": {"type": "电", "rarity": "稀有", "base_hp": 70, "base_attack": 90, "base_defense": 65, "base_speed": 110, "evolution": None, "evolution_level": None},
    
    # 冰系帕鲁
    "冰雪狼": {"type": "冰", "rarity": "稀有", "base_hp": 75, "base_attack": 80, "base_defense": 70, "base_speed": 90, "evolution": "冰霜狼王", "evolution_level": 40},
    "冰霜狼王": {"type": "冰", "rarity": "史诗", "base_hp": 100, "base_attack": 105, "base_defense": 95, "base_speed": 105, "evolution": None, "evolution_level": None},
    "企鹅君": {"type": "冰", "rarity": "普通", "base_hp": 65, "base_attack": 55, "base_defense": 70, "base_speed": 45, "evolution": "企鹅王", "evolution_level": 32},
    "企鹅王": {"type": "冰", "rarity": "稀有", "base_hp": 90, "base_attack": 80, "base_defense": 95, "base_speed": 65, "evolution": None, "evolution_level": None},
    
    # 地面系帕鲁
    "挖掘鼠": {"type": "地", "rarity": "普通", "base_hp": 50, "base_attack": 70, "base_defense": 80, "base_speed": 35, "evolution": "钻地王", "evolution_level": 28},
    "钻地王": {"type": "地", "rarity": "稀有", "base_hp": 75, "base_attack": 95, "base_defense": 105, "base_speed": 50, "evolution": None, "evolution_level": None},
    "岩石巨人": {"type": "地", "rarity": "史诗", "base_hp": 110, "base_attack": 100, "base_defense": 130, "base_speed": 30, "evolution": None, "evolution_level": None},
    
    # 飞行系帕鲁
    "风翼鸟": {"type": "飞", "rarity": "稀有", "base_hp": 60, "base_attack": 75, "base_defense": 50, "base_speed": 115, "evolution": "暴风鹰", "evolution_level": 35},
    "暴风鹰": {"type": "飞", "rarity": "史诗", "base_hp": 85, "base_attack": 100, "base_defense": 75, "base_speed": 140, "evolution": None, "evolution_level": None},
    "彩虹鸟": {"type": "飞", "rarity": "传说", "base_hp": 90, "base_attack": 85, "base_defense": 80, "base_speed": 125, "evolution": None, "evolution_level": None},
    
    # 恶系帕鲁
    "暗影狼": {"type": "恶", "rarity": "史诗", "base_hp": 80, "base_attack": 110, "base_defense": 70, "base_speed": 100, "evolution": None, "evolution_level": None},
    "魅影猫": {"type": "恶", "rarity": "稀有", "base_hp": 55, "base_attack": 85, "base_defense": 55, "base_speed": 95, "evolution": None, "evolution_level": None},
    
    # 钢系帕鲁
    "机械兽": {"type": "钢", "rarity": "史诗", "base_hp": 85, "base_attack": 90, "base_defense": 120, "base_speed": 60, "evolution": None, "evolution_level": None},
    "铁甲犀": {"type": "钢", "rarity": "稀有", "base_hp": 90, "base_attack": 85, "base_defense": 110, "base_speed": 40, "evolution": None, "evolution_level": None},
    
    # 妖精系帕鲁
    "月兔": {"type": "妖", "rarity": "稀有", "base_hp": 70, "base_attack": 60, "base_defense": 65, "base_speed": 85, "evolution": "月神兔", "evolution_level": 35},
    "月神兔": {"type": "妖", "rarity": "传说", "base_hp": 95, "base_attack": 85, "base_defense": 90, "base_speed": 110, "evolution": None, "evolution_level": None},
    "星光精灵": {"type": "妖", "rarity": "史诗", "base_hp": 75, "base_attack": 70, "base_defense": 80, "base_speed": 100, "evolution": None, "evolution_level": None},
    
    # 传说级帕鲁
    "天空之王": {"type": "龙", "rarity": "神话", "base_hp": 120, "base_attack": 140, "base_defense": 110, "base_speed": 95, "evolution": None, "evolution_level": None},
    "深海霸主": {"type": "水", "rarity": "神话", "base_hp": 130, "base_attack": 120, "base_defense": 120, "base_speed": 80, "evolution": None, "evolution_level": None},
    "烈焰君主": {"type": "火", "rarity": "神话", "base_hp": 110, "base_attack": 150, "base_defense": 100, "base_speed": 90, "evolution": None, "evolution_level": None}
}

# 技能数据库
SKILLS_DATA = {
    "撞击": {"type": "普", "power": 40, "accuracy": 100, "pp": 35, "category": "物理"},
    "火花": {"type": "火", "power": 40, "accuracy": 100, "pp": 25, "category": "特殊"},
    "喷射火焰": {"type": "火", "power": 90, "accuracy": 100, "pp": 15, "category": "特殊"},
    "水枪": {"type": "水", "power": 40, "accuracy": 100, "pp": 25, "category": "特殊"},
    "水炮": {"type": "水", "power": 110, "accuracy": 80, "pp": 5, "category": "特殊"},
    "藤鞭": {"type": "草", "power": 45, "accuracy": 100, "pp": 25, "category": "物理"},
    "飞叶快刀": {"type": "草", "power": 55, "accuracy": 95, "pp": 25, "category": "物理"},
    "电击": {"type": "电", "power": 40, "accuracy": 100, "pp": 30, "category": "特殊"},
    "十万伏特": {"type": "电", "power": 90, "accuracy": 100, "pp": 15, "category": "特殊"},
    "念力": {"type": "超", "power": 50, "accuracy": 100, "pp": 25, "category": "特殊"},
    "精神强念": {"type": "超", "power": 90, "accuracy": 100, "pp": 10, "category": "特殊"},
    "翅膀攻击": {"type": "飞", "power": 60, "accuracy": 100, "pp": 35, "category": "物理"},
    "岩石投掷": {"type": "岩", "power": 50, "accuracy": 90, "pp": 15, "category": "物理"},
    "龙息": {"type": "龙", "power": 60, "accuracy": 100, "pp": 20, "category": "特殊"},
    "龙之波动": {"type": "龙", "power": 85, "accuracy": 100, "pp": 10, "category": "特殊"},
    # === 帕鲁专属技能 ===
    # 火系技能
    "烈焰冲击": {"type": "火", "power": 75, "accuracy": 95, "pp": 15, "category": "物理"},
    "炎爆术": {"type": "火", "power": 120, "accuracy": 85, "pp": 5, "category": "特殊"},
    "火焰漩涡": {"type": "火", "power": 35, "accuracy": 85, "pp": 15, "category": "特殊"},
    "狐火": {"type": "火", "power": 65, "accuracy": 100, "pp": 20, "category": "特殊"},
    "地狱烈焰": {"type": "火", "power": 100, "accuracy": 90, "pp": 10, "category": "特殊"},
    
    # 水系技能
    "冲浪": {"type": "水", "power": 90, "accuracy": 100, "pp": 15, "category": "特殊"},
    "水流爆破": {"type": "水", "power": 80, "accuracy": 95, "pp": 10, "category": "特殊"},
    "治愈之水": {"type": "水", "power": 0, "accuracy": 100, "pp": 10, "category": "变化"},
    "深海冲击": {"type": "水", "power": 110, "accuracy": 80, "pp": 5, "category": "物理"},
    "水龙卷": {"type": "水", "power": 70, "accuracy": 90, "pp": 15, "category": "特殊"},
    
    # 草系技能
    "种子机关枪": {"type": "草", "power": 25, "accuracy": 100, "pp": 30, "category": "物理"},
    "花瓣舞": {"type": "草", "power": 120, "accuracy": 100, "pp": 10, "category": "特殊"},
    "草之誓约": {"type": "草", "power": 80, "accuracy": 100, "pp": 10, "category": "特殊"},
    "甜香": {"type": "草", "power": 0, "accuracy": 100, "pp": 20, "category": "变化"},
    "森林诅咒": {"type": "草", "power": 60, "accuracy": 95, "pp": 15, "category": "特殊"},
    
    # 电系技能
    "雷电风暴": {"type": "电", "power": 110, "accuracy": 70, "pp": 10, "category": "特殊"},
    "电磁炮": {"type": "电", "power": 120, "accuracy": 50, "pp": 5, "category": "特殊"},
    "闪电爪": {"type": "电", "power": 70, "accuracy": 100, "pp": 15, "category": "物理"},
    "电光一闪": {"type": "电", "power": 40, "accuracy": 100, "pp": 30, "category": "物理"},
    "雷鸣": {"type": "电", "power": 85, "accuracy": 90, "pp": 15, "category": "特殊"},
    
    # 冰系技能
    "冰锥": {"type": "冰", "power": 60, "accuracy": 100, "pp": 20, "category": "特殊"},
    "暴风雪": {"type": "冰", "power": 110, "accuracy": 70, "pp": 5, "category": "特殊"},
    "冰霜之牙": {"type": "冰", "power": 65, "accuracy": 95, "pp": 15, "category": "物理"},
    "极光束": {"type": "冰", "power": 65, "accuracy": 100, "pp": 20, "category": "特殊"},
    "绝对零度": {"type": "冰", "power": 200, "accuracy": 30, "pp": 5, "category": "特殊"},
    
    # 地面系技能
    "地震": {"type": "地", "power": 100, "accuracy": 100, "pp": 10, "category": "物理"},
    "挖洞": {"type": "地", "power": 80, "accuracy": 100, "pp": 10, "category": "物理"},
    "沙暴": {"type": "地", "power": 0, "accuracy": 100, "pp": 10, "category": "变化"},
    "岩崩": {"type": "地", "power": 75, "accuracy": 90, "pp": 10, "category": "物理"},
    "大地之力": {"type": "地", "power": 90, "accuracy": 100, "pp": 10, "category": "特殊"},
    
    # 飞行系技能
    "空气斩": {"type": "飞", "power": 75, "accuracy": 95, "pp": 15, "category": "特殊"},
    "暴风": {"type": "飞", "power": 110, "accuracy": 70, "pp": 10, "category": "特殊"},
    "羽毛舞": {"type": "飞", "power": 0, "accuracy": 100, "pp": 15, "category": "变化"},
    "神鸟猛击": {"type": "飞", "power": 140, "accuracy": 90, "pp": 5, "category": "物理"},
    "顺风": {"type": "飞", "power": 0, "accuracy": 100, "pp": 15, "category": "变化"},
    
    # 恶系技能
    "暗影爪": {"type": "恶", "power": 70, "accuracy": 100, "pp": 15, "category": "物理"},
    "恶之波动": {"type": "恶", "power": 80, "accuracy": 100, "pp": 15, "category": "特殊"},
    "挑衅": {"type": "恶", "power": 0, "accuracy": 100, "pp": 20, "category": "变化"},
    "暗袭要害": {"type": "恶", "power": 70, "accuracy": 100, "pp": 15, "category": "物理"},
    "黑暗爆破": {"type": "恶", "power": 100, "accuracy": 85, "pp": 10, "category": "特殊"},
    
    # 钢系技能
    "金属爪": {"type": "钢", "power": 50, "accuracy": 95, "pp": 35, "category": "物理"},
    "加农光炮": {"type": "钢", "power": 80, "accuracy": 100, "pp": 10, "category": "特殊"},
    "铁壁": {"type": "钢", "power": 0, "accuracy": 100, "pp": 15, "category": "变化"},
    "钢翼": {"type": "钢", "power": 70, "accuracy": 90, "pp": 25, "category": "物理"},
    "流星拳": {"type": "钢", "power": 90, "accuracy": 90, "pp": 10, "category": "物理"},
    
    # 妖精系技能
    "月光": {"type": "妖", "power": 0, "accuracy": 100, "pp": 10, "category": "变化"},
    "魅惑之声": {"type": "妖", "power": 40, "accuracy": 100, "pp": 15, "category": "特殊"},
    "月爆": {"type": "妖", "power": 95, "accuracy": 100, "pp": 15, "category": "特殊"},
    "嬉闹": {"type": "妖", "power": 90, "accuracy": 90, "pp": 10, "category": "物理"},
    "星光爆发": {"type": "妖", "power": 80, "accuracy": 100, "pp": 15, "category": "特殊"},
    
    # 传说级技能
    "天空裂斩": {"type": "龙", "power": 150, "accuracy": 90, "pp": 5, "category": "物理"},
    "深渊咆哮": {"type": "水", "power": 140, "accuracy": 85, "pp": 5, "category": "特殊"},
    "烈焰审判": {"type": "火", "power": 160, "accuracy": 80, "pp": 5, "category": "特殊"}
}

# 稀有度配置
RARITY_CONFIG = {
    "普通": {"emoji": "⚪", "catch_rate": 50, "score_base": 10},
    "稀有": {"emoji": "🔵", "catch_rate": 25, "score_base": 25},
    "史诗": {"emoji": "🟣", "catch_rate": 10, "score_base": 50},
    "传说": {"emoji": "🟡", "catch_rate": 3, "score_base": 100},
    "神话": {"emoji": "🔴", "catch_rate": 1, "score_base": 200}
}

# 注册命令
start_pokemon = on_regex(pattern=r"^开始精灵之旅$", priority=5)
catch_pokemon = on_regex(pattern=r"^捕捉精灵$", priority=5)
check_pokemon_team = on_regex(pattern=r"^精灵队伍$", priority=5)
check_pokemon_box = on_regex(pattern=r"^精灵盒子$", priority=5)
evolve_pokemon = on_regex(pattern=r"^进化\s+(.+)$", priority=5)
train_pokemon = on_regex(pattern=r"^训练\s+(.+)$", priority=5)
learn_skill = on_regex(pattern=r"^学习技能\s+(.+)\s+(.+)$", priority=5)
battle_wild = on_regex(pattern=r"^野外战斗$", priority=5)
battle_player = on_regex(pattern=r"^挑战\s+@(.+)$", priority=5)
accept_battle = on_regex(pattern=r"^接受挑战$", priority=5)
reject_battle = on_regex(pattern=r"^拒绝挑战$", priority=5)
pokemon_ranking = on_regex(pattern=r"^精灵排行$", priority=5)
pokemon_help = on_regex(pattern=r"^精灵帮助$", priority=5)
release_pokemon = on_regex(pattern=r"^放生\s+(.+)$", priority=5)
pokemon_skills = on_regex(pattern=r"^精灵技能\s+(.+)$", priority=5)

# 全局变量存储战斗状态
battle_requests = {}  # 存储战斗请求
active_battles = {}   # 存储进行中的战斗


def calculate_stats(pokemon_name: str, level: int) -> dict:
    """计算精灵属性"""
    base_stats = POKEMON_DATA[pokemon_name]
    
    # 简化的属性计算公式
    hp = int((base_stats['base_hp'] * 2 * level) / 100) + level + 10
    attack = int((base_stats['base_attack'] * 2 * level) / 100) + 5
    defense = int((base_stats['base_defense'] * 2 * level) / 100) + 5
    speed = int((base_stats['base_speed'] * 2 * level) / 100) + 5
    
    return {
        'hp': hp,
        'max_hp': hp,
        'attack': attack,
        'defense': defense,
        'speed': speed
    }

def get_type_effectiveness(attacker_type: str, defender_type: str) -> float:
    """计算属性相克倍率"""
    if defender_type in TYPES[attacker_type]['strong_against']:
        return 2.0  # 效果拔群
    elif defender_type in TYPES[attacker_type]['weak_against']:
        return 0.5  # 效果不佳
    else:
        return 1.0  # 普通效果

def calculate_damage(attacker_pokemon: dict, defender_pokemon: dict, skill: dict) -> int:
    """计算伤害"""
    # 基础伤害计算
    level = attacker_pokemon['level']
    attack_stat = attacker_pokemon['attack']
    defense_stat = defender_pokemon['defense']
    power = skill['power']
    
    # 简化的伤害公式
    damage = ((((2 * level + 10) / 250) * (attack_stat / defense_stat) * power) + 2)
    
    # 属性相克
    attacker_type = POKEMON_DATA[attacker_pokemon['pokemon_name']]['type']
    defender_type = POKEMON_DATA[defender_pokemon['pokemon_name']]['type']
    type_effectiveness = get_type_effectiveness(skill['type'], defender_type)
    
    # STAB (Same Type Attack Bonus)
    stab = 1.5 if skill['type'] == attacker_type else 1.0
    
    # 随机因子
    random_factor = random.uniform(0.85, 1.0)
    
    final_damage = int(damage * type_effectiveness * stab * random_factor)
    return max(1, final_damage)

@start_pokemon.handle()
async def handle_start_pokemon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否已开始
    existing = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if existing:
        await start_pokemon.send("你已经是精灵训练师了！使用'精灵队伍'查看你的精灵")
        return
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        trainer_name = user_info.get('card') or user_info.get('nickname', f"训练师{user_id}")
    except:
        trainer_name = f"训练师{user_id}"
    
    # 创建训练师
    db.insert('pokemon_trainers', {
        'user_id': user_id,
        'group_id': group_id,
        'trainer_name': trainer_name
    })
    
    # 随机给予初始精灵
    starter_pokemon = random.choice(["小火龙", "杰尼龟", "妙蛙种子"])
    stats = calculate_stats(starter_pokemon, 5)
    
    pokemon_id = db.insert('pokemon_collection', {
        'user_id': user_id,
        'group_id': group_id,
        'pokemon_name': starter_pokemon,
        'level': 5,
        'hp': stats['hp'],
        'max_hp': stats['max_hp'],
        'attack': stats['attack'],
        'defense': stats['defense'],
        'speed': stats['speed'],
        'is_in_team': True,
        'team_position': 1
    })
    
    # 学习初始技能
    if starter_pokemon == "小火龙":
        initial_skills = ["撞击", "火花"]
    elif starter_pokemon == "杰尼龟":
        initial_skills = ["撞击", "水枪"]
    else:  # 妙蛙种子
        initial_skills = ["撞击", "藤鞭"]
    
    for skill_name in initial_skills:
        skill_data = SKILLS_DATA[skill_name]
        db.insert('pokemon_skills', {
            'pokemon_id': pokemon_id,
            'skill_name': skill_name,
            'current_pp': skill_data['pp'],
            'max_pp': skill_data['pp']
        })
    
    # 奖励积分
    await update_player_score(user_id, group_id, 100, "开始精灵之旅", "精灵训练师", "新手奖励")
    
    pokemon_type = POKEMON_DATA[starter_pokemon]['type']
    type_emoji = TYPES[pokemon_type]['emoji']
    
    await start_pokemon.send(
        f"🎉 欢迎成为精灵训练师！\n"
        f"👤 训练师：{trainer_name}\n"
        f"{type_emoji} 初始精灵：{starter_pokemon} (Lv.5)\n"
        f"📚 学会技能：{', '.join(initial_skills)}\n"
        f"⚾ 精灵球：10个\n"
        f"💰 获得100积分奖励！\n\n"
        f"使用'精灵帮助'查看更多指令"
    )

@catch_pokemon.handle()
async def handle_catch_pokemon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await catch_pokemon.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    if trainer['pokeballs'] <= 0:
        await catch_pokemon.send("你没有精灵球了！通过战斗获得更多精灵球")
        return
    
    # 随机遇到精灵
    available_pokemon = list(POKEMON_DATA.keys())
    weights = []
    
    for pokemon_name in available_pokemon:
        rarity = POKEMON_DATA[pokemon_name]['rarity']
        # 根据稀有度设置权重
        if rarity == "普通":
            weights.append(50)
        elif rarity == "稀有":
            weights.append(25)
        elif rarity == "史诗":
            weights.append(15)
        elif rarity == "传说":
            weights.append(8)
        else:  # 神话
            weights.append(2)
    
    wild_pokemon = random.choices(available_pokemon, weights=weights)[0]
    pokemon_data = POKEMON_DATA[wild_pokemon]
    rarity_config = RARITY_CONFIG[pokemon_data['rarity']]
    
    # 计算捕获成功率
    base_catch_rate = rarity_config['catch_rate']
    trainer_level_bonus = trainer['level'] * 2
    final_catch_rate = min(95, base_catch_rate + trainer_level_bonus)
    
    # 尝试捕获
    catch_success = random.randint(1, 100) <= final_catch_rate
    
    # 消耗精灵球
    db.update('pokemon_trainers', {
        'pokeballs': trainer['pokeballs'] - 1
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    pokemon_type = pokemon_data['type']
    type_emoji = TYPES[pokemon_type]['emoji']
    rarity_emoji = rarity_config['emoji']
    
    if catch_success:
        # 捕获成功
        level = random.randint(1, min(trainer['level'] + 5, 20))
        stats = calculate_stats(wild_pokemon, level)
        
        pokemon_id = db.insert('pokemon_collection', {
            'user_id': user_id,
            'group_id': group_id,
            'pokemon_name': wild_pokemon,
            'level': level,
            'hp': stats['hp'],
            'max_hp': stats['max_hp'],
            'attack': stats['attack'],
            'defense': stats['defense'],
            'speed': stats['speed']
        })
        
        # 学习基础技能
        basic_skill = "撞击"
        skill_data = SKILLS_DATA[basic_skill]
        db.insert('pokemon_skills', {
            'pokemon_id': pokemon_id,
            'skill_name': basic_skill,
            'current_pp': skill_data['pp'],
            'max_pp': skill_data['pp']
        })
        
        # 奖励积分和经验
        score_reward = rarity_config['score_base']
        exp_reward = score_reward // 2
        
        new_exp = trainer['exp'] + exp_reward
        new_level = trainer['level']
        
        # 检查训练师升级
        level_up = False
        exp_needed = trainer['level'] * 100
        if new_exp >= exp_needed:
            new_level += 1
            new_exp = 0
            level_up = True
            score_reward += 50  # 升级奖励
            
            # 升级奖励精灵球
            new_pokeballs = trainer['pokeballs'] + 5
            db.update('pokemon_trainers', {
                'level': new_level,
                'exp': new_exp,
                'pokeballs': new_pokeballs
            }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        else:
            db.update('pokemon_trainers', {
                'exp': new_exp
            }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        await update_player_score(user_id, group_id, score_reward, "捕获精灵", "精灵训练师", f"捕获{pokemon_data['rarity']}精灵")
        
        message = (
            f"🎉 捕获成功！\n"
            f"{rarity_emoji} {type_emoji} {wild_pokemon} (Lv.{level})\n"
            f"稀有度：{pokemon_data['rarity']}\n"
            f"⭐ 获得经验：{exp_reward}\n"
            f"💰 获得积分：{score_reward}\n"
            f"⚾ 剩余精灵球：{trainer['pokeballs'] - 1}"
        )
        
        if level_up:
            message += f"\n\n🎊 训练师升级到Lv.{new_level}！获得5个精灵球！"
        
    else:
        # 捕获失败
        message = (
            f"💔 捕获失败...\n"
            f"{rarity_emoji} {type_emoji} {wild_pokemon}逃跑了！\n"
            f"成功率：{final_catch_rate}%\n"
            f"⚾ 剩余精灵球：{trainer['pokeballs'] - 1}\n\n"
            f"提升训练师等级可以增加捕获成功率！"
        )
    
    await catch_pokemon.send(message)

@check_pokemon_team.handle()
async def handle_check_pokemon_team(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await check_pokemon_team.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    team_pokemon = db.fetch_all(
        'pokemon_collection', 
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1 ORDER BY team_position ASC",
    )
    
    message = f"👤 训练师：{trainer['trainer_name']} (Lv.{trainer['level']})\n"
    message += f"⭐ 经验：{trainer['exp']}/{trainer['level'] * 100}\n"
    message += f"⚾ 精灵球：{trainer['pokeballs']}\n"
    message += f"🏆 战绩：{trainer['wins']}胜{trainer['losses']}负\n\n"
    
    if not team_pokemon:
        message += "队伍中没有精灵！"
    else:
        message += "🎒 精灵队伍：\n\n"
        
        for i, pokemon in enumerate(team_pokemon, 1):
            pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            # 获取技能
            skills = db.fetch_all('pokemon_skills', f"pokemon_id = {pokemon['id']}")
            skill_names = [skill['skill_name'] for skill in skills]
            
            display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
            
            message += (
                f"{i}. {rarity_emoji} {type_emoji} {display_name} (Lv.{pokemon['level']})\n"
                f"   ❤️ HP: {pokemon['hp']}/{pokemon['max_hp']}\n"
                f"   ⚔️ 攻击: {pokemon['attack']} 🛡️ 防御: {pokemon['defense']} ⚡ 速度: {pokemon['speed']}\n"
                f"   💝 亲密度: {pokemon['friendship']}/100\n"
                f"   📚 技能: {', '.join(skill_names)}\n\n"
            )
    
    await check_pokemon_team.send(message.strip())

@train_pokemon.handle()
async def handle_train_pokemon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await train_pokemon.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    # 解析精灵名
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^训练\s+(.+)$", message_text)
    if not match:
        await train_pokemon.send("请输入正确的格式：训练 精灵名")
        return
    
    pokemon_name = match.group(1).strip()
    
    # 查找精灵（支持昵称）
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = ? AND group_id = ? AND (pokemon_name = ? OR nickname = ?)",
        (user_id, group_id, pokemon_name, pokemon_name)
    )
    
    if not pokemon:
        await train_pokemon.send(f"找不到精灵'{pokemon_name}'！")
        return
    
    # 检查训练冷却
    last_trained = datetime.fromisoformat(pokemon['last_trained'])
    now = datetime.now()
    cooldown = timedelta(hours=1)  # 1小时冷却
    
    if now - last_trained < cooldown:
        remaining = cooldown - (now - last_trained)
        minutes = int(remaining.total_seconds() / 60)
        await train_pokemon.send(f"{pokemon_name}还在休息中，请{minutes}分钟后再训练")
        return
    
    # 训练效果
    base_exp = random.randint(20, 40)
    friendship_gain = random.randint(1, 3)
    score_gain = random.randint(5, 15)
    
    new_exp = pokemon['exp'] + base_exp
    new_friendship = min(100, pokemon['friendship'] + friendship_gain)
    
    # 检查升级
    level_up = False
    new_level = pokemon['level']
    exp_needed = pokemon['level'] * 50
    
    if new_exp >= exp_needed and pokemon['level'] < 100:
        new_level += 1
        new_exp = 0
        level_up = True
        score_gain += 25  # 升级奖励
        
        # 重新计算属性
        new_stats = calculate_stats(pokemon['pokemon_name'], new_level)
        
        db.update('pokemon_collection', {
            'level': new_level,
            'exp': new_exp,
            'max_hp': new_stats['max_hp'],
            'hp': new_stats['hp'],  # 升级时恢复满血
            'attack': new_stats['attack'],
            'defense': new_stats['defense'],
            'speed': new_stats['speed'],
            'friendship': new_friendship,
            'last_trained': now.isoformat()
        }, f"id = {pokemon['id']}")
    else:
        db.update('pokemon_collection', {
            'exp': new_exp,
            'friendship': new_friendship,
            'last_trained': now.isoformat()
        }, f"id = {pokemon['id']}")
    
    # 更新积分
    await update_player_score(user_id, group_id, score_gain, "训练精灵", "精灵训练师", "训练奖励")
    
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    type_emoji = TYPES[pokemon_data['type']]['emoji']
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    
    message = (
        f"🏃 训练了{display_name}！\n"
        f"{type_emoji} 获得经验：{base_exp}\n"
        f"💝 亲密度：{pokemon['friendship']} → {new_friendship}\n"
        f"💰 获得积分：{score_gain}"
    )
    
    if level_up:
        message += f"\n\n🎉 {display_name}升级到了Lv.{new_level}！\n属性全面提升！"
    
    await train_pokemon.send(message)

@evolve_pokemon.handle()
async def handle_evolve_pokemon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await evolve_pokemon.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    # 解析精灵名
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^进化\s+(.+)$", message_text)
    if not match:
        await evolve_pokemon.send("请输入正确的格式：进化 精灵名")
        return
    
    pokemon_name = match.group(1).strip()
    
    # 查找精灵
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = ? AND group_id = ? AND (pokemon_name = ? OR nickname = ?)",
        (user_id, group_id, pokemon_name, pokemon_name)
    )
    
    if not pokemon:
        await evolve_pokemon.send(f"找不到精灵'{pokemon_name}'！")
        return
    
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    
    # 检查是否可以进化
    if not pokemon_data['evolution']:
        await evolve_pokemon.send(f"{pokemon['pokemon_name']}无法进化！")
        return
    
    if pokemon['level'] < pokemon_data['evolution_level']:
        await evolve_pokemon.send(
            f"{pokemon['pokemon_name']}需要达到Lv.{pokemon_data['evolution_level']}才能进化！\n"
            f"当前等级：Lv.{pokemon['level']}"
        )
        return
    
    # 检查亲密度
    if pokemon['friendship'] < 80:
        await evolve_pokemon.send(
            f"{pokemon['pokemon_name']}的亲密度不够！需要80以上才能进化\n"
            f"当前亲密度：{pokemon['friendship']}/100"
        )
        return
    
    # 进化
    evolved_name = pokemon_data['evolution']
    new_stats = calculate_stats(evolved_name, pokemon['level'])
    
    db.update('pokemon_collection', {
        'pokemon_name': evolved_name,
        'max_hp': new_stats['max_hp'],
        'hp': new_stats['hp'],
        'attack': new_stats['attack'],
        'defense': new_stats['defense'],
        'speed': new_stats['speed']
    }, f"id = {pokemon['id']}")
    
    # 奖励积分
    evolved_data = POKEMON_DATA[evolved_name]
    score_reward = RARITY_CONFIG[evolved_data['rarity']]['score_base']
    await update_player_score(user_id, group_id, score_reward, "精灵进化", "精灵训练师", "进化奖励")
    
    old_type_emoji = TYPES[pokemon_data['type']]['emoji']
    new_type_emoji = TYPES[evolved_data['type']]['emoji']
    
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    
    await evolve_pokemon.send(
        f"✨ 进化成功！\n"
        f"{old_type_emoji} {display_name} 进化成了 {new_type_emoji} {evolved_name}！\n"
        f"🎉 属性大幅提升！\n"
        f"💰 获得{score_reward}积分奖励！"
    )

@battle_wild.handle()
async def handle_battle_wild(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await battle_wild.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    # 获取队伍中的第一只精灵
    team_pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1",
        order_by="team_position ASC"
    )
    
    if not team_pokemon:
        await battle_wild.send("队伍中没有精灵！")
        return
    
    if team_pokemon['hp'] <= 0:
        await battle_wild.send("你的精灵已经失去战斗能力！请先治疗")
        return
    
    # 随机遇到野生精灵
    wild_pokemon_name = random.choice(list(POKEMON_DATA.keys()))
    wild_level = random.randint(max(1, trainer['level'] - 3), trainer['level'] + 3)
    wild_stats = calculate_stats(wild_pokemon_name, wild_level)
    
    # 简化的战斗计算
    player_pokemon_data = POKEMON_DATA[team_pokemon['pokemon_name']]
    wild_pokemon_data = POKEMON_DATA[wild_pokemon_name]
    
    # 获取玩家精灵的技能
    player_skills = db.fetch_all('pokemon_skills', f"pokemon_id = {team_pokemon['id']}")
    if not player_skills:
        await battle_wild.send("你的精灵没有学会任何技能！")
        return
    
    # 随机选择技能
    used_skill_data = random.choice(player_skills)
    used_skill = SKILLS_DATA[used_skill_data['skill_name']]
    
    # 计算伤害
    damage_to_wild = calculate_damage(team_pokemon, {'level': wild_level, 'defense': wild_stats['defense'], 'pokemon_name': wild_pokemon_name}, used_skill)
    damage_to_player = calculate_damage({'level': wild_level, 'attack': wild_stats['attack'], 'pokemon_name': wild_pokemon_name}, team_pokemon, SKILLS_DATA['撞击'])
    
    # 判断胜负
    wild_hp_after = wild_stats['hp'] - damage_to_wild
    player_hp_after = team_pokemon['hp'] - damage_to_player
    
    battle_log = []
    battle_log.append(f"🔥 遭遇野生的{wild_pokemon_name} (Lv.{wild_level})！")
    
    player_display_name = team_pokemon['nickname'] if team_pokemon['nickname'] else team_pokemon['pokemon_name']
    battle_log.append(f"⚔️ {player_display_name}使用了{used_skill_data['skill_name']}！")
    
    # 属性相克提示
    type_effectiveness = get_type_effectiveness(used_skill['type'], wild_pokemon_data['type'])
    if type_effectiveness > 1.0:
        battle_log.append("💥 效果拔群！")
    elif type_effectiveness < 1.0:
        battle_log.append("💔 效果不佳...")
    
    battle_log.append(f"造成了{damage_to_wild}点伤害！")
    
    if wild_hp_after <= 0:
        # 玩家胜利
        exp_gain = random.randint(15, 30) + wild_level
        score_gain = random.randint(10, 20)
        
        # 更新精灵经验
        new_exp = team_pokemon['exp'] + exp_gain
        new_level = team_pokemon['level']
        
        # 检查升级
        level_up = False
        exp_needed = team_pokemon['level'] * 50
        if new_exp >= exp_needed and team_pokemon['level'] < 100:
            new_level += 1
            new_exp = 0
            level_up = True
            score_gain += 25
            
            # 重新计算属性
            new_stats = calculate_stats(team_pokemon['pokemon_name'], new_level)
            
            db.update('pokemon_collection', {
                'level': new_level,
                'exp': new_exp,
                'max_hp': new_stats['max_hp'],
                'attack': new_stats['attack'],
                'defense': new_stats['defense'],
                'speed': new_stats['speed']
            }, f"id = {team_pokemon['id']}")
        else:
            db.update('pokemon_collection', {
                'exp': new_exp
            }, f"id = {team_pokemon['id']}")
        
        # 更新训练师战绩
        db.update('pokemon_trainers', {
            'wins': trainer['wins'] + 1
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        # 记录战斗
        db.insert('pokemon_battles', {
            'trainer1_id': user_id,
            'group_id': group_id,
            'battle_type': '野外战斗',
            'winner_id': user_id,
            'exp_gained': exp_gain,
            'score_gained': score_gain
        })
        
        await update_player_score(user_id, group_id, score_gain, "野外战斗", "精灵训练师", "胜利奖励")
        
        battle_log.append(f"\n🏆 {wild_pokemon_name}被击败了！")
        battle_log.append(f"⭐ 获得经验：{exp_gain}")
        battle_log.append(f"💰 获得积分：{score_gain}")
        
        if level_up:
            battle_log.append(f"\n🎉 {player_display_name}升级到了Lv.{new_level}！")
        
    else:
        # 野生精灵反击
        battle_log.append(f"\n{wild_pokemon_name}使用了撞击！")
        battle_log.append(f"造成了{damage_to_player}点伤害！")
        
        new_hp = max(0, player_hp_after)
        db.update('pokemon_collection', {
            'hp': new_hp
        }, f"id = {team_pokemon['id']}")
        
        if new_hp <= 0:
            # 玩家失败
            db.update('pokemon_trainers', {
                'losses': trainer['losses'] + 1
            }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
            
            battle_log.append(f"\n💀 {player_display_name}失去了战斗能力！")
            battle_log.append("战斗失败...")
        else:
            battle_log.append(f"\n{player_display_name}剩余HP：{new_hp}/{team_pokemon['max_hp']}")
            battle_log.append("战斗继续...")
    
    result_message = "\n".join(battle_log)
    await battle_wild.send(result_message)

@pokemon_ranking.handle()
async def handle_pokemon_ranking(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 获取群内训练师排行（按等级和胜场排序）
    trainers = db.fetch_all(
        'pokemon_trainers',
        f"group_id = '{group_id}' ORDER BY level DESC, wins DESC LIMIT 50"
    )
    
    if not trainers:
        await pokemon_ranking.send("本群还没有精灵训练师呢！")
        return
    
    message = "🏆 精灵训练师排行榜 🏆\n\n"
    
    for i, trainer in enumerate(trainers, 1):
        # 获取训练师的最强精灵
        strongest_pokemon = db.fetch_one(
            'pokemon_collection',
            f"user_id = '{trainer['user_id']}' AND group_id = '{group_id}'",
            order_by="level DESC, attack DESC"
        )
        
        pokemon_info = ""
        if strongest_pokemon:
            pokemon_data = POKEMON_DATA[strongest_pokemon['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            pokemon_info = f"{rarity_emoji}{type_emoji} {strongest_pokemon['pokemon_name']} (Lv.{strongest_pokemon['level']})"
        
        message += (
            f"{i}. {trainer['trainer_name']} (Lv.{trainer['level']})\n"
            f"   🏆 战绩：{trainer['wins']}胜{trainer['losses']}负\n"
            f"   🌟 最强精灵：{pokemon_info}\n\n"
        )
    
    await pokemon_ranking.send(message.strip())

@pokemon_help.handle()
async def handle_pokemon_help(bot: Bot, event: GroupMessageEvent):
    help_text = (
        "⚡ 精灵系统帮助 ⚡\n\n"
        "📋 基础指令：\n"
        "• 开始精灵之旅 - 成为精灵训练师\n"
        "• 精灵队伍 - 查看队伍中的精灵\n"
        "• 精灵盒子 - 查看所有收集的精灵\n\n"
        "🎯 捕获系统：\n"
        "• 捕捉精灵 - 随机遇到并捕获野生精灵\n\n"
        "🏃 培养系统：\n"
        "• 训练 [精灵名] - 训练精灵提升经验和亲密度\n"
        "• 进化 [精灵名] - 精灵进化（需要等级和亲密度）\n"
        "• 学习技能 [精灵名] [技能名] - 学习新技能\n\n"
        "⚔️ 战斗系统：\n"
        "• 野外战斗 - 与野生精灵战斗\n"
        "• 挑战 @用户 - 向其他训练师发起挑战\n"
        "• 接受挑战 - 接受其他训练师的挑战\n"
        "• 拒绝挑战 - 拒绝其他训练师的挑战\n\n"
        "📊 查询指令：\n"
        "• 精灵排行 - 查看群内训练师排行榜\n\n"
        "🌟 属性相克：\n"
        "🔥火 克 🌿草❄️冰🐛虫\n"
        "💧水 克 🔥火🌍地🗿岩\n"
        "🌿草 克 💧水🌍地🗿岩\n"
        "⚡电 克 💧水🦅飞\n"
        "❄️冰 克 🌿草🌍地🦅飞🐉龙\n\n"
        "💡 游戏机制：\n"
        "• 精灵有5种稀有度：普通、稀有、史诗、传说、神话\n"
        "• 训练师等级影响捕获成功率\n"
        "• 精灵需要达到一定等级和亲密度才能进化\n"
        "• 属性相克影响战斗伤害\n"
        "• 同属性技能有1.5倍伤害加成\n"
        "• 战斗胜利可获得经验和积分奖励"
    )
    
    await pokemon_help.send(help_text)

# 在文件末尾添加以下两个函数

@check_pokemon_box.handle()
async def handle_check_pokemon_box(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await check_pokemon_box.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 获取所有精灵（包括队伍中和盒子中的）
    all_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' ORDER BY is_in_team DESC, level DESC, pokemon_name ASC"
    )
    
    if not all_pokemon:
        await check_pokemon_box.send("你还没有任何精灵！快去捕捉一些吧！")
        return
    
    # 分类显示
    team_pokemon = [p for p in all_pokemon if p['is_in_team']]
    box_pokemon = [p for p in all_pokemon if not p['is_in_team']]
    
    message = f"📦 {trainer['trainer_name']} 的精灵盒子\n\n"
    
    # 显示队伍精灵
    if team_pokemon:
        message += "⚡ 当前队伍：\n"
        for i, pokemon in enumerate(team_pokemon, 1):
            pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
            hp_status = f"{pokemon['hp']}/{pokemon['max_hp']}"
            
            message += (
                f"{i}. {rarity_emoji}{type_emoji} {display_name} (Lv.{pokemon['level']})\n"
                f"   ❤️ HP: {hp_status} | 💪 攻击: {pokemon['attack']} | 🛡️ 防御: {pokemon['defense']}\n"
                f"   ⚡ 速度: {pokemon['speed']} | 💖 亲密度: {pokemon['friendship']}\n\n"
            )
    
    # 显示盒子精灵
    if box_pokemon:
        message += "📦 精灵盒子：\n"
        for pokemon in box_pokemon:
            pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
            hp_status = f"{pokemon['hp']}/{pokemon['max_hp']}"
            
            message += (
                f"• {rarity_emoji}{type_emoji} {display_name} (Lv.{pokemon['level']})\n"
                f"  ❤️ HP: {hp_status} | 💖 亲密度: {pokemon['friendship']}\n"
            )
    
    message += f"\n📊 总计：{len(all_pokemon)} 只精灵 | 队伍：{len(team_pokemon)}/6 | 盒子：{len(box_pokemon)}"
    
    await check_pokemon_box.send(message)

@learn_skill.handle()
async def handle_learn_skill(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    message_text = str(event.get_message()).strip()
    
    # 解析命令参数
    parts = message_text.split()
    if len(parts) < 3:
        await learn_skill.send("请输入：学习技能 [精灵名] [技能名]")
        return
    
    pokemon_name = parts[1]
    skill_name = parts[2]
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await learn_skill.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找精灵（支持昵称和原名）
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}')"
    )
    
    if not pokemon:
        await learn_skill.send(f"找不到精灵：{pokemon_name}")
        return
    
    # 检查技能是否存在
    if skill_name not in SKILLS_DATA:
        # 显示可学习的技能列表
        pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
        learnable_skills = pokemon_data.get('learnable_skills', [])
        
        if learnable_skills:
            skills_text = "\n".join([f"• {skill}" for skill in learnable_skills])
            message = f"技能 '{skill_name}' 不存在！\n\n{pokemon['pokemon_name']} 可学习的技能：\n{skills_text}"
        else:
            message = f"技能 '{skill_name}' 不存在！\n\n{pokemon['pokemon_name']} 暂无可学习的技能。"
        
        await learn_skill.send(message)
        return
    
    # 检查精灵是否能学习这个技能
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    learnable_skills = pokemon_data.get('learnable_skills', [])
    
    if skill_name not in learnable_skills:
        await learn_skill.send(f"{pokemon['pokemon_name']} 无法学习技能：{skill_name}")
        return
    
    # 检查精灵等级要求（某些技能需要一定等级）
    skill_data = SKILLS_DATA[skill_name]
    required_level = skill_data.get('required_level', 1)
    
    if pokemon['level'] < required_level:
        await learn_skill.send(f"学习 {skill_name} 需要精灵达到 Lv.{required_level}！")
        return
    
    # 检查精灵已知技能
    current_skills = []
    for i in range(1, 5):
        skill = pokemon.get(f'skill_{i}')
        if skill:
            current_skills.append(skill)
    
    # 检查是否已经学会了这个技能
    if skill_name in current_skills:
        await learn_skill.send(f"{pokemon['pokemon_name']} 已经学会了 {skill_name}！")
        return
    
    # 检查技能栏是否已满
    if len(current_skills) >= 4:
        await learn_skill.send(f"{pokemon['pokemon_name']} 的技能栏已满！每只精灵最多只能学会4个技能。")
        return
    
    # 学习技能
    skill_slot = f'skill_{len(current_skills) + 1}'
    db.update('pokemon_collection', {
        skill_slot: skill_name
    }, f"id = {pokemon['id']}")
    
    # 奖励积分
    score_gain = random.randint(5, 15)
    await update_player_score(user_id, group_id, score_gain, "学习技能", "精灵训练师", "技能学习奖励")
    
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    skill_type_emoji = TYPES[skill_data['type']]['emoji']
    
    message = (
        f"🎉 {display_name} 学会了新技能！\n\n"
        f"{skill_type_emoji} {skill_name}\n"
        f"类型：{skill_data['type']} | 威力：{skill_data['power']} | PP：{skill_data['pp']}\n"
        f"命中率：{skill_data['accuracy']}% | 类别：{skill_data['category']}\n\n"
        f"💰 获得积分：{score_gain}"
    )
    
    await learn_skill.send(message)


# 修改精灵技能回调函数以适配正则匹配
@pokemon_skills.handle()
async def handle_pokemon_skills(bot: Bot, event: GroupMessageEvent, state: T_State):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    matched = state['_matched']
   
    pokemon_name = matched.group(1).strip()
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await pokemon_skills.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找精灵（支持昵称和原名）
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}')"
    )
    
    if not pokemon:
        await pokemon_skills.send(f"找不到精灵：{pokemon_name}")
        return
    
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    type_emoji = TYPES[pokemon_data['type']]['emoji']
    rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
    
    message = f"⚡ {rarity_emoji}{type_emoji} {display_name} (Lv.{pokemon['level']}) 的技能信息\n\n"
    
    # 显示已学会的技能
    current_skills = []
    for i in range(1, 5):
        skill = pokemon.get(f'skill_{i}')
        if skill:
            current_skills.append(skill)
    
    if current_skills:
        message += "🎯 已学会的技能：\n"
        for skill in current_skills:
            skill_data = SKILLS_DATA[skill]
            skill_type_emoji = TYPES[skill_data['type']]['emoji']
            message += (
                f"• {skill_type_emoji} {skill}\n"
                f"  类型：{skill_data['type']} | 威力：{skill_data['power']} | PP：{skill_data['pp']}\n"
                f"  命中率：{skill_data['accuracy']}% | 类别：{skill_data['category']}\n\n"
            )
    else:
        message += "🎯 已学会的技能：无\n\n"
    
    # 显示可学习的技能
    learnable_skills = pokemon_data.get('learnable_skills', [])
    if learnable_skills:
        message += "📚 可学习的技能：\n"
        for skill in learnable_skills:
            if skill in current_skills:
                continue  # 跳过已学会的技能
            
            if skill in SKILLS_DATA:
                skill_data = SKILLS_DATA[skill]
                skill_type_emoji = TYPES[skill_data['type']]['emoji']
                required_level = skill_data.get('required_level', 1)
                
                # 检查是否满足等级要求
                level_status = "✅" if pokemon['level'] >= required_level else f"❌(需要Lv.{required_level})"
                
                message += (
                    f"• {skill_type_emoji} {skill} {level_status}\n"
                    f"  类型：{skill_data['type']} | 威力：{skill_data['power']} | PP：{skill_data['pp']}\n"
                    f"  命中率：{skill_data['accuracy']}% | 类别：{skill_data['category']}\n\n"
                )
    else:
        message += "📚 可学习的技能：暂无\n\n"
    
    message += f"💡 技能栏：{len(current_skills)}/4\n"
    message += "💡 使用 '学习技能 [精灵名] [技能名]' 来学习新技能"
    
    await pokemon_skills.send(message)

# 挑战玩家回调函数
@battle_player.handle()
async def handle_battle_player(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 从正则匹配中获取被挑战者
    match = battle_player.pattern.match(str(event.get_message()).strip())
    if not match:
        await battle_player.send("请输入：挑战 @用户名")
        return
    
    target_user = match.group(1).strip()
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await battle_player.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 检查是否有队伍中的精灵
    team_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1 AND hp > 0"
    )
    
    if not team_pokemon:
        await battle_player.send("你的队伍中没有可战斗的精灵！")
        return
    
    # 检查是否已有战斗请求
    battle_key = f"{group_id}_{user_id}"
    if battle_key in battle_requests:
        await battle_player.send("你已经发起了挑战请求，请等待对方回应！")
        return
    
    # 存储战斗请求
    battle_requests[battle_key] = {
        'challenger_id': user_id,
        'challenger_name': trainer['trainer_name'],
        'target_user': target_user,
        'group_id': group_id,
        'timestamp': time.time()
    }
    
    message = (
        f"⚔️ 精灵训练师 {trainer['trainer_name']} 向 @{target_user} 发起挑战！\n\n"
        f"@{target_user} 请在60秒内回应：\n"
        f"• 发送 '接受挑战' 接受挑战\n"
        f"• 发送 '拒绝挑战' 拒绝挑战\n\n"
        f"💡 挑战将在60秒后自动取消"
    )
    
    await battle_player.send(message)
    
    # 60秒后自动取消挑战
    await asyncio.sleep(60)
    if battle_key in battle_requests:
        del battle_requests[battle_key]
        await battle_player.send(f"⏰ {trainer['trainer_name']} 对 @{target_user} 的挑战已超时取消")

# 接受挑战回调函数
@accept_battle.handle()
async def handle_accept_battle(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await accept_battle.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找针对当前用户的挑战请求
    target_battle = None
    target_key = None
    
    for battle_key, battle_info in battle_requests.items():
        if (battle_info['group_id'] == group_id and 
            battle_info['target_user'] == trainer['trainer_name']):
            target_battle = battle_info
            target_key = battle_key
            break
    
    if not target_battle:
        await accept_battle.send("没有找到针对你的挑战请求！")
        return
    
    # 检查是否有队伍中的精灵
    team_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1 AND hp > 0"
    )
    
    if not team_pokemon:
        await accept_battle.send("你的队伍中没有可战斗的精灵！")
        return
    
    challenger_id = target_battle['challenger_id']
    challenger_name = target_battle['challenger_name']
    
    # 获取挑战者的精灵
    challenger_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{challenger_id}' AND group_id = '{group_id}' AND is_in_team = 1 AND hp > 0"
    )
    
    if not challenger_pokemon:
        await accept_battle.send(f"{challenger_name} 的队伍中没有可战斗的精灵，挑战取消！")
        del battle_requests[target_key]
        return
    
    # 移除战斗请求
    del battle_requests[target_key]
    
    # 开始战斗
    player1_pokemon = challenger_pokemon[0]
    player2_pokemon = team_pokemon[0]
    
    # 简化的战斗逻辑
    battle_log = []
    battle_log.append(f"⚔️ 精灵对战开始！")
    battle_log.append(f"{challenger_name} 的 {player1_pokemon['pokemon_name']} VS {trainer['trainer_name']} 的 {player2_pokemon['pokemon_name']}")
    
    # 计算伤害（简化版）
    damage1 = random.randint(player1_pokemon['attack'] // 2, player1_pokemon['attack'])
    damage2 = random.randint(player2_pokemon['attack'] // 2, player2_pokemon['attack'])
    
    # 判断胜负
    if player1_pokemon['speed'] >= player2_pokemon['speed']:
        # 挑战者先攻
        p2_hp_after = max(0, player2_pokemon['hp'] - damage1)
        battle_log.append(f"{player1_pokemon['pokemon_name']} 先攻，造成 {damage1} 点伤害！")
        
        if p2_hp_after > 0:
            p1_hp_after = max(0, player1_pokemon['hp'] - damage2)
            battle_log.append(f"{player2_pokemon['pokemon_name']} 反击，造成 {damage2} 点伤害！")
            
            if p1_hp_after <= 0:
                winner_id = user_id
                winner_name = trainer['trainer_name']
                loser_id = challenger_id
                loser_name = challenger_name
            elif p2_hp_after <= 0:
                winner_id = challenger_id
                winner_name = challenger_name
                loser_id = user_id
                loser_name = trainer['trainer_name']
            else:
                # 根据剩余HP判断
                if p1_hp_after >= p2_hp_after:
                    winner_id = challenger_id
                    winner_name = challenger_name
                    loser_id = user_id
                    loser_name = trainer['trainer_name']
                else:
                    winner_id = user_id
                    winner_name = trainer['trainer_name']
                    loser_id = challenger_id
                    loser_name = challenger_name
        else:
            winner_id = challenger_id
            winner_name = challenger_name
            loser_id = user_id
            loser_name = trainer['trainer_name']
    else:
        # 接受者先攻
        p1_hp_after = max(0, player1_pokemon['hp'] - damage2)
        battle_log.append(f"{player2_pokemon['pokemon_name']} 先攻，造成 {damage2} 点伤害！")
        
        if p1_hp_after > 0:
            p2_hp_after = max(0, player2_pokemon['hp'] - damage1)
            battle_log.append(f"{player1_pokemon['pokemon_name']} 反击，造成 {damage1} 点伤害！")
            
            if p2_hp_after <= 0:
                winner_id = challenger_id
                winner_name = challenger_name
                loser_id = user_id
                loser_name = trainer['trainer_name']
            elif p1_hp_after <= 0:
                winner_id = user_id
                winner_name = trainer['trainer_name']
                loser_id = challenger_id
                loser_name = challenger_name
            else:
                # 根据剩余HP判断
                if p1_hp_after >= p2_hp_after:
                    winner_id = challenger_id
                    winner_name = challenger_name
                    loser_id = user_id
                    loser_name = trainer['trainer_name']
                else:
                    winner_id = user_id
                    winner_name = trainer['trainer_name']
                    loser_id = challenger_id
                    loser_name = challenger_name
        else:
            winner_id = user_id
            winner_name = trainer['trainer_name']
            loser_id = challenger_id
            loser_name = challenger_name
    
    battle_log.append(f"\n🏆 {winner_name} 获得胜利！")
    
    # 更新战绩
    db.update('pokemon_trainers', {
        'wins': db.fetch_one('pokemon_trainers', f"user_id = '{winner_id}' AND group_id = '{group_id}'")['wins'] + 1
    }, f"user_id = '{winner_id}' AND group_id = '{group_id}'")
    
    db.update('pokemon_trainers', {
        'losses': db.fetch_one('pokemon_trainers', f"user_id = '{loser_id}' AND group_id = '{group_id}'")['losses'] + 1
    }, f"user_id = '{loser_id}' AND group_id = '{group_id}'")
    
    # 记录战斗
    db.insert('pokemon_battles', {
        'trainer1_id': challenger_id,
        'trainer2_id': user_id,
        'group_id': group_id,
        'battle_type': '玩家对战',
        'winner_id': winner_id,
        'exp_gained': 0,
        'score_gained': 30
    })
    
    # 奖励积分
    await update_player_score(winner_id, group_id, 30, "玩家对战", "精灵训练师", "胜利奖励")
    await update_player_score(loser_id, group_id, 10, "玩家对战", "精灵训练师", "参与奖励")
    
    result_message = "\n".join(battle_log)
    result_message += "\n\n💰 胜者获得30积分，败者获得10积分！"
    
    await accept_battle.send(result_message)

# 拒绝挑战回调函数
@reject_battle.handle()
async def handle_reject_battle(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await reject_battle.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找针对当前用户的挑战请求
    target_battle = None
    target_key = None
    
    for battle_key, battle_info in battle_requests.items():
        if (battle_info['group_id'] == group_id and 
            battle_info['target_user'] == trainer['trainer_name']):
            target_battle = battle_info
            target_key = battle_key
            break
    
    if not target_battle:
        await reject_battle.send("没有找到针对你的挑战请求！")
        return
    
    challenger_name = target_battle['challenger_name']
    
    # 移除战斗请求
    del battle_requests[target_key]
    
    await reject_battle.send(f"❌ {trainer['trainer_name']} 拒绝了 {challenger_name} 的挑战！")

# 放生精灵回调函数
@release_pokemon.handle()
async def handle_release_pokemon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 从正则匹配中获取精灵名
    match = release_pokemon.pattern.match(str(event.get_message()).strip())
    if not match:
        await release_pokemon.send("请输入：放生 [精灵名]")
        return
    
    pokemon_name = match.group(1).strip()
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await release_pokemon.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找精灵（支持昵称和原名）
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}')"
    )
    
    if not pokemon:
        await release_pokemon.send(f"找不到精灵：{pokemon_name}")
        return
    
    # 检查是否是队伍中的精灵
    if pokemon['is_in_team']:
        await release_pokemon.send("不能放生队伍中的精灵！请先将其移出队伍。")
        return
    
    # 检查是否是最后一只精灵
    total_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}'"
    )
    
    if len(total_pokemon) <= 1:
        await release_pokemon.send("不能放生最后一只精灵！")
        return
    
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    type_emoji = TYPES[pokemon_data['type']]['emoji']
    rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
    
    # 根据精灵稀有度和等级给予补偿积分
    rarity_bonus = RARITY_CONFIG[pokemon_data['rarity']]['score_bonus']
    level_bonus = pokemon['level'] * 2
    friendship_bonus = pokemon['friendship'] // 10
    total_score = rarity_bonus + level_bonus + friendship_bonus
    
    # 删除精灵
    db.delete('pokemon_collection', f"id = {pokemon['id']}")
    
    # 奖励积分
    await update_player_score(user_id, group_id, total_score, "放生精灵", "精灵训练师", "放生补偿")
    
    message = (
        f"💔 {display_name} 被放生了...\n\n"
        f"{rarity_emoji}{type_emoji} {pokemon['pokemon_name']} (Lv.{pokemon['level']})\n"
        f"💖 亲密度：{pokemon['friendship']}\n\n"
        f"💰 获得补偿积分：{total_score}\n"
        f"  • 稀有度奖励：{rarity_bonus}\n"
        f"  • 等级奖励：{level_bonus}\n"
        f"  • 亲密度奖励：{friendship_bonus}\n\n"
        f"🌟 {display_name} 回到了大自然，祝它生活愉快！"
    )
    
    await release_pokemon.send(message)