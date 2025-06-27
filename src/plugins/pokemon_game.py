'''
@Author: AI Assistant
@Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-27 16:33:32
FilePath: /team-bot/jx3-team-bot/src/plugins/pokemon_game.py
'''
from .database import NianZaiDB
from .game_score import update_player_score,get_player_score
from nonebot.typing import T_State
from nonebot import on_command, on_regex,require
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment
import random
import asyncio
from datetime import datetime, timedelta
import time
import json
import re
# 在文件顶部添加scheduler导入
scheduler = require("nonebot_plugin_apscheduler").scheduler

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
    "普": {"emoji": "⭐", "strong_against": [], "weak_against": ["格"]},
    "鬼": { "emoji": "👽", "strong_against": ["超", "鬼"], "weak_against": ["恶"]},
    "光": { "emoji": "☀️", "strong_against": ["恶", "暗", "鬼"], "weak_against": ["暗"] },
    "暗": { "emoji": "🌚", "strong_against": ["光", "超", "妖"], "weak_against": ["光", "格"]}
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
    "烈焰君主": {"type": "火", "rarity": "神话", "base_hp": 110, "base_attack": 150, "base_defense": 100, "base_speed": 90, "evolution": None, "evolution_level": None},

    # 虫系
    "绿毛虫": {"type": "虫", "rarity": "普通", "base_hp": 45, "base_attack": 30, "base_defense": 35, "base_speed": 45, "evolution": "铁甲蛹", "evolution_level": 7},
    "铁甲蛹": {"type": "虫", "rarity": "普通", "base_hp": 50, "base_attack": 20, "base_defense": 55, "base_speed": 30, "evolution": "巴大蝶", "evolution_level": 10},
    "巴大蝶": {"type": "虫", "rarity": "稀有", "base_hp": 60, "base_attack": 45, "base_defense": 50, "base_speed": 70, "evolution": None, "evolution_level": None},

    # 毒系
    "阿柏蛇": {"type": "毒", "rarity": "普通", "base_hp": 35, "base_attack": 60, "base_defense": 44, "base_speed": 55, "evolution": "阿柏怪", "evolution_level": 22},
    "阿柏怪": {"type": "毒", "rarity": "稀有", "base_hp": 60, "base_attack": 95, "base_defense": 69, "base_speed": 80, "evolution": None, "evolution_level": None},

    # 格斗系
    "腕力": {"type": "格", "rarity": "普通", "base_hp": 70, "base_attack": 80, "base_defense": 50, "base_speed": 35, "evolution": "豪力", "evolution_level": 28},
    "豪力": {"type": "格", "rarity": "稀有", "base_hp": 80, "base_attack": 100, "base_defense": 70, "base_speed": 45, "evolution": "怪力", "evolution_level": 40},
    "怪力": {"type": "格", "rarity": "史诗", "base_hp": 90, "base_attack": 130, "base_defense": 80, "base_speed": 55, "evolution": None, "evolution_level": None},

    # 幽灵系
    "鬼斯": {"type": "鬼", "rarity": "稀有", "base_hp": 30, "base_attack": 35, "base_defense": 30, "base_speed": 80, "evolution": "鬼斯通", "evolution_level": 25},
    "鬼斯通": {"type": "鬼", "rarity": "史诗", "base_hp": 45, "base_attack": 50, "base_defense": 45, "base_speed": 95, "evolution": "耿鬼", "evolution_level": 40},
    "耿鬼": {"type": "鬼", "rarity": "传说", "base_hp": 60, "base_attack": 65, "base_defense": 60, "base_speed": 110, "evolution": None, "evolution_level": None},

    # 传说宝可梦
    "急冻鸟": {"type": "冰", "rarity": "神话", "base_hp": 90, "base_attack": 85, "base_defense": 100, "base_speed": 85, "evolution": None, "evolution_level": None},
    "闪电鸟": {"type": "电", "rarity": "神话", "base_hp": 90, "base_attack": 90, "base_defense": 85, "base_speed": 100, "evolution": None, "evolution_level": None},
    "火焰鸟": {"type": "火", "rarity": "神话", "base_hp": 90, "base_attack": 100, "base_defense": 90, "base_speed": 90, "evolution": None, "evolution_level": None},
    "超梦": {"type": "超", "rarity": "神话", "base_hp": 106, "base_attack": 110, "base_defense": 90, "base_speed": 130, "evolution": None, "evolution_level": None},
    "梦幻": {"type": "超", "rarity": "神话", "base_hp": 100, "base_attack": 100, "base_defense": 100, "base_speed": 100, "evolution": None, "evolution_level": None},

    # === 更多帕鲁系列 ===
    # 光系帕鲁
    "光明鹿": {"type": "光", "rarity": "传说", "base_hp": 95, "base_attack": 80, "base_defense": 90, "base_speed": 105, "evolution": None, "evolution_level": None},
    "圣光狮": {"type": "光", "rarity": "史诗", "base_hp": 85, "base_attack": 95, "base_defense": 85, "base_speed": 90, "evolution": None, "evolution_level": None},
    "天使兽": {"type": "光", "rarity": "神话", "base_hp": 110, "base_attack": 120, "base_defense": 100, "base_speed": 95, "evolution": None, "evolution_level": None},

    # 暗系帕鲁
    "暗夜魔": {"type": "暗", "rarity": "史诗", "base_hp": 75, "base_attack": 105, "base_defense": 70, "base_speed": 95, "evolution": None, "evolution_level": None},
    "深渊龙": {"type": "暗", "rarity": "传说", "base_hp": 100, "base_attack": 125, "base_defense": 90, "base_speed": 85, "evolution": None, "evolution_level": None},
    "虚无之王": {"type": "暗", "rarity": "神话", "base_hp": 120, "base_attack": 140, "base_defense": 95, "base_speed": 80, "evolution": None, "evolution_level": None},

    # 工作帕鲁
    "建筑鼠": {"type": "普", "rarity": "普通", "base_hp": 60, "base_attack": 50, "base_defense": 70, "base_speed": 45, "evolution": "工程师鼠", "evolution_level": 25},
    "工程师鼠": {"type": "普", "rarity": "稀有", "base_hp": 85, "base_attack": 75, "base_defense": 95, "base_speed": 60, "evolution": None, "evolution_level": None},
    "采矿猪": {"type": "地", "rarity": "普通", "base_hp": 70, "base_attack": 60, "base_defense": 80, "base_speed": 30, "evolution": "矿业大师", "evolution_level": 30},
    "矿业大师": {"type": "地", "rarity": "稀有", "base_hp": 95, "base_attack": 85, "base_defense": 105, "base_speed": 45, "evolution": None, "evolution_level": None},
    "伐木熊": {"type": "草", "rarity": "普通", "base_hp": 80, "base_attack": 75, "base_defense": 70, "base_speed": 40, "evolution": "森林之王", "evolution_level": 35},
    "森林之王": {"type": "草", "rarity": "史诗", "base_hp": 105, "base_attack": 100, "base_defense": 95, "base_speed": 55, "evolution": None, "evolution_level": None},

    # 可爱系帕鲁
    "棉花糖": {"type": "妖", "rarity": "普通", "base_hp": 55, "base_attack": 35, "base_defense": 60, "base_speed": 70, "evolution": "云朵精灵", "evolution_level": 20},
    "云朵精灵": {"type": "妖", "rarity": "稀有", "base_hp": 80, "base_attack": 60, "base_defense": 85, "base_speed": 95, "evolution": None, "evolution_level": None},
    "彩虹独角兽": {"type": "妖", "rarity": "传说", "base_hp": 90, "base_attack": 85, "base_defense": 90, "base_speed": 110, "evolution": None, "evolution_level": None},

    # 机械系帕鲁
    "机器人": {"type": "钢", "rarity": "稀有", "base_hp": 70, "base_attack": 80, "base_defense": 100, "base_speed": 50, "evolution": "超级机器人", "evolution_level": 40},
    "超级机器人": {"type": "钢", "rarity": "史诗", "base_hp": 95, "base_attack": 105, "base_defense": 125, "base_speed": 70, "evolution": None, "evolution_level": None},
    "终极战士": {"type": "钢", "rarity": "神话", "base_hp": 115, "base_attack": 130, "base_defense": 140, "base_speed": 85, "evolution": None, "evolution_level": None}
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
    "烈焰审判": {"type": "火", "power": 160, "accuracy": 80, "pp": 5, "category": "特殊"},

    # 在SKILLS_DATA字典中添加更多技能

    # 虫系技能
    "虫咬": {"type": "虫", "power": 60, "accuracy": 100, "pp": 20, "category": "物理"},
    "银色旋风": {"type": "虫", "power": 40, "accuracy": 100, "pp": 20, "category": "特殊"},
    "蝶舞": {"type": "虫", "power": 0, "accuracy": 100, "pp": 20, "category": "变化"},
    "虫鸣": {"type": "虫", "power": 90, "accuracy": 100, "pp": 10, "category": "特殊"},

    # 毒系技能
    "毒针": {"type": "毒", "power": 15, "accuracy": 100, "pp": 35, "category": "物理"},
    "毒液冲击": {"type": "毒", "power": 65, "accuracy": 100, "pp": 10, "category": "特殊"},
    "剧毒": {"type": "毒", "power": 0, "accuracy": 90, "pp": 10, "category": "变化"},
    "污泥炸弹": {"type": "毒", "power": 90, "accuracy": 100, "pp": 10, "category": "特殊"},

    # 格斗系技能
    "空手劈": {"type": "格", "power": 50, "accuracy": 100, "pp": 25, "category": "物理"},
    "爆裂拳": {"type": "格", "power": 100, "accuracy": 50, "pp": 5, "category": "物理"},
    "真气拳": {"type": "格", "power": 60, "accuracy": 100, "pp": 20, "category": "物理"},
    "近身战": {"type": "格", "power": 120, "accuracy": 100, "pp": 5, "category": "物理"},

    # 幽灵系技能
    "舔舐": {"type": "鬼", "power": 30, "accuracy": 100, "pp": 30, "category": "物理"},
    "暗影球": {"type": "鬼", "power": 80, "accuracy": 100, "pp": 15, "category": "特殊"},
    "鬼火": {"type": "鬼", "power": 0, "accuracy": 85, "pp": 15, "category": "变化"},
    "暗影偷袭": {"type": "鬼", "power": 40, "accuracy": 100, "pp": 30, "category": "物理"},

    # 光系技能（帕鲁专属）
    "圣光术": {"type": "光", "power": 80, "accuracy": 100, "pp": 15, "category": "特殊"},
    "光之审判": {"type": "光", "power": 100, "accuracy": 85, "pp": 10, "category": "特殊"},
    "治愈光环": {"type": "光", "power": 0, "accuracy": 100, "pp": 10, "category": "变化"},
    "神圣之剑": {"type": "光", "power": 90, "accuracy": 100, "pp": 15, "category": "物理"},
    "天使之翼": {"type": "光", "power": 120, "accuracy": 90, "pp": 5, "category": "物理"},

    # 暗系技能（帕鲁专属）
    "暗影束缚": {"type": "暗", "power": 60, "accuracy": 95, "pp": 20, "category": "特殊"},
    "虚无吞噬": {"type": "暗", "power": 100, "accuracy": 80, "pp": 10, "category": "特殊"},
    "黑暗领域": {"type": "暗", "power": 0, "accuracy": 100, "pp": 10, "category": "变化"},
    "深渊之门": {"type": "暗", "power": 120, "accuracy": 85, "pp": 5, "category": "特殊"},
    "末日审判": {"type": "暗", "power": 150, "accuracy": 80, "pp": 5, "category": "特殊"},

    # 工作技能（帕鲁专属）
    "建造": {"type": "普", "power": 0, "accuracy": 100, "pp": 20, "category": "变化"},
    "采集": {"type": "普", "power": 40, "accuracy": 100, "pp": 25, "category": "物理"},
    "修理": {"type": "钢", "power": 0, "accuracy": 100, "pp": 15, "category": "变化"},
    "伐木": {"type": "草", "power": 60, "accuracy": 100, "pp": 20, "category": "物理"},
    "挖矿": {"type": "地", "power": 70, "accuracy": 100, "pp": 15, "category": "物理"},

    # 传说级技能
    "创世之光": {"type": "光", "power": 200, "accuracy": 70, "pp": 5, "category": "特殊"},
    "毁灭黑洞": {"type": "暗", "power": 180, "accuracy": 75, "pp": 5, "category": "特殊"},
    "时空裂缝": {"type": "超", "power": 160, "accuracy": 80, "pp": 5, "category": "特殊"},
    "机械风暴": {"type": "钢", "power": 140, "accuracy": 85, "pp": 5, "category": "物理"}
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
evolve_pokemon = on_regex(pattern=r"^进化\s+(.+?)(?:\s+(\d+))?$", priority=5)
train_pokemon = on_regex(pattern=r"^训练\s+(.+?)(?:\s+(\d+))?$", priority=5)
learn_skill = on_regex(pattern=r"^学习技能\s+(.+)\s+(.+)$", priority=5)
battle_wild = on_regex(pattern=r"^野外战斗$", priority=5)
battle_player = on_regex(pattern=r"^挑战\s+.*$", priority=3)
accept_battle = on_regex(pattern=r"^接受挑战$", priority=5)
reject_battle = on_regex(pattern=r"^拒绝挑战$", priority=5)
pokemon_ranking = on_regex(pattern=r"^精灵排行$", priority=5)
pokemon_help = on_regex(pattern=r"^精灵帮助$", priority=5)
release_pokemon = on_regex(pattern=r"^放生\s+(.+?)(?:\s+(\d+))?$", priority=5)
pokemon_skills = on_regex(pattern=r"^精灵技能\s+(.+)$", priority=5)
put_pokemon_team = on_regex(pattern=r"^放入队伍\s+(.+)$", priority=5)
remove_pokemon_team = on_regex(pattern=r"^移出队伍\s+(.+)$", priority=5)
switch_pokemon_position = on_regex(pattern=r"^调整位置\s+(.+)\s+(\d+)$", priority=5)
continue_battle = on_regex(pattern=r"^继续战斗$", priority=5)
flee_battle = on_regex(pattern=r"^逃离战斗$", priority=5)
heal_pokemon = on_regex(pattern=r"^治疗精灵$", priority=5)
heal_specific_pokemon = on_regex(pattern=r"^治疗\s+(.+)$", priority=5)
buy_pokeballs = on_regex(pattern=r"^购买精灵球\s+(\d+)$", priority=5)
# 管理员命令 - 精灵数据迁移
migrate_pokemon_data = on_regex(pattern=r"^精灵数据迁移\s+(\d+)\s+(\d+)$", priority=5)
# 管理员命令 - 群积分奖励
group_score_reward = on_regex(pattern=r"^发放积分\s+(\d+)(?:\s+(\d+))?$", priority=5)
# 修改改名命令的正则表达式，支持可选的序号
rename_pokemon = on_regex(pattern=r"^命名\s+(.+?)(?:\s+(\d+))?\s+(.+)$", priority=5)
# 添加精灵详细列表命令
pokemon_detail_list = on_regex(pattern=r"^精灵列表\s*(.*)$", priority=5)
# 全局变量存储战斗状态
battle_requests = {}  # 存储战斗请求
active_battles = {}   # 存储进行中的战斗
# 全局变量存储野外战斗状态
wild_battle_states = {}  # 存储野外战斗状态


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
    
    # 解析精灵名和序号
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^训练\s+(.+?)(?:\s+(\d+))?$", message_text)
    if not match:
        await train_pokemon.send("请输入正确的格式：训练 精灵名 [序号]")
        return
    
    pokemon_name = match.group(1).strip()
    selected_index = match.group(2)
    
    # 查找所有匹配的精灵（支持昵称）
    all_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}') ORDER BY id ASC",
    )
    
    if not all_pokemon:
        await train_pokemon.send(f"找不到精灵'{pokemon_name}'！")
        return
    
    # 如果有多个同名精灵但没有指定序号
    if len(all_pokemon) > 1 and selected_index is None:
        message = f"找到{len(all_pokemon)}只名为'{pokemon_name}'的精灵：\n\n"
        for i, poke in enumerate(all_pokemon, 1):
            display_name = poke['nickname'] if poke['nickname'] else poke['pokemon_name']
            pokemon_data = POKEMON_DATA[poke['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            # 检查训练冷却
            last_trained = datetime.fromisoformat(poke['last_trained'])
            now = datetime.now()
            cooldown = timedelta(hours=1)
            can_train = now - last_trained >= cooldown
            status = "✅可训练" if can_train else "⏰冷却中"
            
            message += f"{i}. {rarity_emoji}{type_emoji} {display_name} (Lv.{poke['level']}) {status}\n"
            message += f"   HP: {poke['hp']}/{poke['max_hp']} | 亲密度: {poke['friendship']}\n\n"
        
        message += f"请使用：训练 {pokemon_name} [序号]\n"
        message += f"例如：训练 {pokemon_name} 1"
        
        await train_pokemon.send(message)
        return
    
    # 选择要训练的精灵
    if selected_index is not None:
        try:
            index = int(selected_index) - 1
            if index < 0 or index >= len(all_pokemon):
                await train_pokemon.send(f"序号无效！请选择1-{len(all_pokemon)}之间的序号")
                return
            pokemon = all_pokemon[index]
        except ValueError:
            await train_pokemon.send("序号必须是数字！")
            return
    else:
        # 只有一只精灵的情况
        pokemon = all_pokemon[0]
    
    # 检查训练冷却
    last_trained = datetime.fromisoformat(pokemon['last_trained'])
    now = datetime.now()
    cooldown = timedelta(hours=1)  # 1小时冷却
    
    if now - last_trained < cooldown:
        remaining = cooldown - (now - last_trained)
        minutes = int(remaining.total_seconds() / 60)
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        await train_pokemon.send(f"{display_name}还在休息中，请{minutes}分钟后再训练")
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
    
    # 解析精灵名和序号
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^进化\s+(.+?)(?:\s+(\d+))?$", message_text)
    if not match:
        await evolve_pokemon.send("请输入正确的格式：进化 精灵名 [序号]")
        return
    
    pokemon_name = match.group(1).strip()
    selected_index = match.group(2)
    
    # 查找所有匹配的精灵
    all_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}') ORDER BY id ASC",
    )
    
    if not all_pokemon:
        await evolve_pokemon.send(f"找不到精灵'{pokemon_name}'！")
        return
    
    # 如果有多个同名精灵但没有指定序号
    if len(all_pokemon) > 1 and selected_index is None:
        message = f"找到{len(all_pokemon)}只名为'{pokemon_name}'的精灵：\n\n"
        for i, poke in enumerate(all_pokemon, 1):
            display_name = poke['nickname'] if poke['nickname'] else poke['pokemon_name']
            pokemon_data = POKEMON_DATA[poke['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            # 检查进化条件
            can_evolve = True
            evolve_status = "✅可进化"
            
            if not pokemon_data['evolution']:
                can_evolve = False
                evolve_status = "❌无法进化"
            elif poke['level'] < pokemon_data['evolution_level']:
                can_evolve = False
                evolve_status = f"❌需Lv.{pokemon_data['evolution_level']}"
            elif poke['friendship'] < 80:
                can_evolve = False
                evolve_status = "❌亲密度不足"
            
            message += f"{i}. {rarity_emoji}{type_emoji} {display_name} (Lv.{poke['level']}) {evolve_status}\n"
            message += f"   HP: {poke['hp']}/{poke['max_hp']} | 亲密度: {poke['friendship']}\n\n"
        
        message += f"请使用：进化 {pokemon_name} [序号]\n"
        message += f"例如：进化 {pokemon_name} 1"
        
        await evolve_pokemon.send(message)
        return
    
    # 选择要进化的精灵
    if selected_index is not None:
        try:
            index = int(selected_index) - 1
            if index < 0 or index >= len(all_pokemon):
                await evolve_pokemon.send(f"序号无效！请选择1-{len(all_pokemon)}之间的序号")
                return
            pokemon = all_pokemon[index]
        except ValueError:
            await evolve_pokemon.send("序号必须是数字！")
            return
    else:
        # 只有一只精灵的情况
        pokemon = all_pokemon[0]
    
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    
    # 检查是否可以进化
    if not pokemon_data['evolution']:
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        await evolve_pokemon.send(f"{display_name}无法进化！")
        return
    
    if pokemon['level'] < pokemon_data['evolution_level']:
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        await evolve_pokemon.send(
            f"{display_name}需要达到Lv.{pokemon_data['evolution_level']}才能进化！\n"
            f"当前等级：Lv.{pokemon['level']}"
        )
        return
    
    # 检查亲密度
    if pokemon['friendship'] < 80:
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        await evolve_pokemon.send(
            f"{display_name}的亲密度不够！需要80以上才能进化\n"
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
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1 ORDER BY team_position ASC"
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
        # 给予默认技能
        player_skills = [{'skill_name': '撞击', 'current_pp': 35, 'max_pp': 35}]

    # 过滤掉PP为0的技能
    available_skills = [skill for skill in player_skills if skill['current_pp'] > 0]
    if not available_skills:
        await battle_wild.send("你的精灵所有技能的PP都用完了！")
        return

    # 随机选择技能
    used_skill_data = random.choice(available_skills)
    used_skill = SKILLS_DATA[used_skill_data['skill_name']]

    # 消耗PP
    if used_skill_data['skill_name'] != '撞击':
        new_pp = used_skill_data['current_pp'] - 1
        db.update('pokemon_skills', {
            'current_pp': new_pp
        }, f"pokemon_id = {team_pokemon['id']} AND skill_name = '{used_skill_data['skill_name']}'")
        
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
           # 存储战斗状态
            battle_key = f"{user_id}_{group_id}"
            wild_battle_states[battle_key] = {
                'pokemon_id': team_pokemon['id'],
                'wild_pokemon_name': wild_pokemon_name,
                'wild_level': wild_level,
                'wild_hp': wild_hp_after,
                'wild_max_hp': wild_stats['hp'],
                'pokemon_hp': new_hp
            }
            
            battle_log.append(f"\n{player_display_name}剩余HP：{new_hp}/{team_pokemon['max_hp']}")
            battle_log.append(f"野生{wild_pokemon_name}剩余HP：{wild_hp_after}/{wild_stats['hp']}")
            battle_log.append("\n⚔️ 战斗继续中...")
            battle_log.append("💡 输入'继续战斗'继续攻击，或输入'逃离战斗'结束战斗")
    
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
            f"user_id = '{trainer['user_id']}' AND group_id = '{group_id}' ORDER BY level DESC, attack DESC"
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
        "• 训练 [精灵名] [序号] - 训练精灵提升经验和亲密度\n"
        "• 进化 [精灵名] [序号] - 进化精灵到下一阶段\n"
        "• 改名 [精灵名] [序号] [新昵称] - 给精灵改名，避免同名冲突\n"
        "• 精灵列表 [精灵名] - 查看精灵详细信息，包含序号\n"
        "• 学习技能 [精灵名] [技能名] - 学习新技能\n"
        "• 精灵技能 [精灵名] - 查看精灵的技能列表\n\n"
        "👥 队伍管理：\n"
        "• 放入队伍 [精灵名] - 将精灵加入战斗队伍\n"
        "• 移出队伍 [精灵名] - 将精灵移出战斗队伍\n"
        "• 调整位置 [精灵名] [位置] - 调整精灵在队伍中的位置\n"
        "• 放生 [精灵名] [序号] - 释放精灵（不可恢复）\n\n"
        "⚔️ 战斗系统：\n"
        "• 野外战斗 - 与野生精灵战斗\n"
        "• 继续战斗 - 在战斗中继续攻击\n"
        "• 逃离战斗 - 从战斗中逃跑\n"
        "• 挑战 @用户 - 向其他训练师发起挑战\n"
        "• 接受挑战 - 接受其他训练师的挑战\n"
        "• 拒绝挑战 - 拒绝其他训练师的挑战\n\n"
        "🏥 精灵治疗：\n"
        "• 治疗精灵 - 精灵中心免费治疗（1小时冷却）\n"
        "• 治疗 [精灵名] - 消耗20积分立即治疗指定精灵\n"
        "• 精灵每小时自动恢复10%HP（不包括濒死精灵）\n\n"
        "🛒 商店系统：\n"
        "• 购买精灵球 [数量] - 用积分购买精灵球\n"
        "  - 1个精灵球 = 20积分\n"
        "  - 购买5-9个：20%概率获得1个额外精灵球\n"
        "  - 购买10-19个：30%概率获得2-3个额外精灵球\n"
        "  - 购买20个以上：50%概率获得5-8个额外精灵球\n\n"
        "📊 查询指令：\n"
        "• 精灵排行 - 查看群内训练师排行榜\n\n"
        "🌟 属性相克：\n"
        "🔥火 克 🌿草❄️冰🐛虫🗿岩\n"
        "💧水 克 🔥火🌍地🗿岩\n"
        "🌿草 克 💧水🌍地🗿岩\n"
        "⚡电 克 💧水🦅飞\n"
        "❄️冰 克 🌿草🌍地🦅飞🐉龙\n"
        "🌍地 克 🔥火⚡电🗿岩🧪毒🗡️钢\n"
        "🗿岩 克 🔥火❄️冰🦅飞🐛虫\n"
        "🦅飞 克 🌿草🗡️格🐛虫\n"
        "🧠超 克 🗡️格🧪毒\n"
        "🐛虫 克 🌿草🧠超🌑恶\n"
        "🗡️格 克 ⚪普🗿岩🗡️钢❄️冰🌑恶\n"
        "🧪毒 克 🌿草🧚妖\n"
        "👻鬼 克 🧠超👻鬼\n"
        "🐉龙 克 🐉龙\n"
        "🌑恶 克 🧠超👻鬼\n"
        "🗡️钢 克 ❄️冰🗿岩🧚妖\n"
        "🧚妖 克 🗡️格🐉龙🌑恶\n\n"
        "💡 游戏机制：\n"
        "• 精灵有5种稀有度：⚪普通、🔵稀有、🟣史诗、🟡传说、🔴神话\n"
        "• 训练师等级影响捕获成功率和精灵球上限\n"
        "• 精灵需要达到一定等级和亲密度才能进化\n"
        "• 属性相克影响战斗伤害（2倍/0.5倍）\n"
        "• 同属性技能有1.5倍伤害加成（STAB）\n"
        "• 战斗胜利可获得经验和积分奖励\n"
        "• 队伍最多可容纳6只精灵\n"
        "• 精灵球数量有上限，可通过升级提升\n"
        "• 挑战其他训练师需要双方都有可战斗精灵\n\n"
        "🎮 特殊功能：\n"
        "• 支持精灵昵称系统\n"
        "• 自动HP恢复机制\n"
        "• 店家好感度奖励系统\n"
        "• 精灵亲密度影响进化\n"
        "• 技能PP值消耗系统\n\n"
        "💰 积分获取：\n"
        "• 捕获精灵：根据稀有度获得10-200积分\n"
        "• 战斗胜利：获得经验和积分奖励\n"
        "• 训练精灵：提升经验和亲密度\n"
        "• 完成进化：获得额外积分奖励\n\n"
        "📝 使用提示：\n"
        "• 精灵名支持使用昵称\n"
        "• 战斗中可查看技能和状态\n"
        "• 合理搭配队伍属性\n"
        "• 定期治疗精灵保持状态\n"
        "• 积分不足时无法购买精灵球和治疗"
    )
    
    await pokemon_help.send(help_text)


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
        await learn_skill.send(f"技能 '{skill_name}' 不存在！")
        return
    
    # 检查精灵是否能学习这个技能（使用与显示相同的逻辑）
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    pokemon_type = pokemon_data['type']
    skill_data = SKILLS_DATA[skill_name]
    
    # 技能学习条件：技能类型匹配精灵类型，或者是通用技能
    can_learn = (
        skill_data['type'] == pokemon_type or 
        skill_data['type'] == '普' or 
        skill_name in ['撞击', '叫声', '瞪眼']
    )
    
    if not can_learn:
        await learn_skill.send(f"{pokemon['pokemon_name']} 无法学习技能：{skill_name}")
        return
    
    # 检查精灵等级要求
    required_level = skill_data.get('required_level', 1)
    if pokemon['level'] < required_level:
        await learn_skill.send(f"学习 {skill_name} 需要精灵达到 Lv.{required_level}！")
        return
    
    # 检查是否已经学会了这个技能
    existing_skills = db.fetch_all(
        'pokemon_skills',
        f"pokemon_id = {pokemon['id']} AND skill_name = '{skill_name}'"
    )
    
    if existing_skills:
        await learn_skill.send(f"{pokemon['pokemon_name']} 已经学会了 {skill_name}！")
        return
    
    # 检查技能栏是否已满
    current_skills = db.fetch_all(
        'pokemon_skills',
        f"pokemon_id = {pokemon['id']}"
    )
    
    if len(current_skills) >= 4:
        await learn_skill.send(f"{pokemon['pokemon_name']} 的技能栏已满！每只精灵最多只能学会4个技能。")
        return
    
    # 学习技能（存储到pokemon_skills表）
    db.insert('pokemon_skills', {
        'pokemon_id': pokemon['id'],
        'skill_name': skill_name,
        'current_pp': skill_data['pp'],
        'max_pp': skill_data['pp']
    })
    
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
    
    # 从pokemon_skills表获取已学会的技能
    current_skills_data = db.fetch_all(
        'pokemon_skills',
        f"pokemon_id = {pokemon['id']}"
    )
    
    current_skills = [skill['skill_name'] for skill in current_skills_data]
    
    if current_skills:
        message += "🎯 已学会的技能：\n"
        for skill_data in current_skills_data:
            skill_name = skill_data['skill_name']
            if skill_name in SKILLS_DATA:
                skill_info = SKILLS_DATA[skill_name]
                skill_type_emoji = TYPES[skill_info['type']]['emoji']
                pp_status = f"{skill_data['current_pp']}/{skill_data['max_pp']}"
                message += (
                    f"• {skill_type_emoji} {skill_name}\n"
                    f"  类型：{skill_info['type']} | 威力：{skill_info['power']} | PP：{pp_status}\n"
                    f"  命中率：{skill_info['accuracy']}% | 类别：{skill_info['category']}\n\n"
                )
    else:
        message += "🎯 已学会的技能：无\n\n"
    
    # 显示可学习的技能（基于精灵类型和等级）
    pokemon_type = pokemon_data['type']
    pokemon_level = pokemon['level']
    
    # 获取该类型精灵可以学习的技能
    learnable_skills = []
    for skill_name, skill_info in SKILLS_DATA.items():
        # 跳过已学会的技能
        if skill_name in current_skills:
            continue
            
        # 检查技能类型匹配或通用技能
        if (skill_info['type'] == pokemon_type or 
            skill_info['type'] == '一般' or 
            skill_name in ['撞击', '叫声', '瞪眼']):
            
            required_level = skill_info.get('required_level', 1)
            learnable_skills.append({
                'name': skill_name,
                'info': skill_info,
                'required_level': required_level,
                'can_learn': pokemon_level >= required_level
            })
    
    # 按等级要求排序
    learnable_skills.sort(key=lambda x: x['required_level'])
    
    if learnable_skills:
        message += "📚 可学习的技能：\n"
        for skill in learnable_skills[:10]:  # 限制显示数量
            skill_name = skill['name']
            skill_info = skill['info']
            required_level = skill['required_level']
            can_learn = skill['can_learn']
            
            skill_type_emoji = TYPES[skill_info['type']]['emoji']
            level_status = "✅" if can_learn else f"❌(需要Lv.{required_level})"
            
            message += (
                f"• {skill_type_emoji} {skill_name} {level_status}\n"
                f"  类型：{skill_info['type']} | 威力：{skill_info['power']} | PP：{skill_info['pp']}\n"
                f"  命中率：{skill_info['accuracy']}% | 类别：{skill_info['category']}\n\n"
            )
        
        if len(learnable_skills) > 10:
            message += f"... 还有 {len(learnable_skills) - 10} 个技能可学习\n\n"
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
    
    # 获取完整消息
    message = event.get_message()
    
    # 查找艾特消息段
    target_user_id = None
    target_user_name = None

    
    
    for segment in message:
        if segment.type == "at":
            target_user_id = segment.data["qq"]
            break

    # 在这里添加获取用户昵称的代码
    try:
        # 方法1：通过bot API获取用户信息
        user_info = await bot.get_stranger_info(user_id=int(target_user_id))
        target_user_name = user_info.get('nickname', f'用户{target_user_id}')
    except:
        # 方法2：如果API调用失败，使用默认格式
        target_user_name = f'用户{target_user_id}'
    
    print(target_user_id, target_user_name)

    if not target_user_id:
        await battle_player.send("请正确艾特要挑战的用户！格式：挑战 @用户名")
        return
    
    # 检查被挑战者是否是训练师
    target_trainer = db.fetch_one('pokemon_trainers', f"user_id = '{target_user_id}' AND group_id = '{group_id}'")
    if not target_trainer:
        await battle_player.send("被挑战者还不是精灵训练师！")
        return
    
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
        'target_user': target_user_name,
        'group_id': group_id,
        'timestamp': time.time()
    }
    
    message = (
        f"⚔️ 精灵训练师 {trainer['trainer_name']} 向 @{target_user_name} 发起挑战！\n\n"
        f"@{target_user_name} 请在60秒内回应：\n"
        f"• 发送 '接受挑战' 接受挑战\n"
        f"• 发送 '拒绝挑战' 拒绝挑战\n\n"
        f"💡 挑战将在60秒后自动取消"
    )
    
    await battle_player.send(message)
    
    # 60秒后自动取消挑战
    await asyncio.sleep(60)
    if battle_key in battle_requests:
        del battle_requests[battle_key]
        await battle_player.send(f"⏰ {trainer['trainer_name']} 对 @{target_user_name} 的挑战已超时取消")

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
async def handle_release_pokemon(bot: Bot, event: GroupMessageEvent, state: T_State):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    matched = state['_matched']
    pokemon_name = matched.group(1).strip()
    selected_index = matched.group(2)  # 可能为 None
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await release_pokemon.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找所有匹配的精灵（排除队伍中的）
    pokemons = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}') AND is_in_team = FALSE ORDER BY level ASC, friendship ASC"
    )
    
    if not pokemons:
        await release_pokemon.send(f"找不到可放生的精灵：{pokemon_name}")
        return
    
    # 检查是否是最后一只精灵
    total_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}'"
    )
    
    if len(total_pokemon) <= 1:
        await release_pokemon.send("不能放生最后一只精灵！")
        return
    
    # 如果指定了编号
    if selected_index:
        index = int(selected_index) - 1  # 转换为0基索引
        if index < 0 or index >= len(pokemons):
            await release_pokemon.send(f"编号无效！请选择 1-{len(pokemons)} 之间的编号")
            return
        pokemon = pokemons[index]
    # 如果只有一个匹配的精灵，直接放生
    elif len(pokemons) == 1:
        pokemon = pokemons[0]
    # 如果有多个匹配的精灵，显示列表让用户选择
    else:
        message = f"找到多个 {pokemon_name}，请选择要放生的精灵：\n\n"
        for i, poke in enumerate(pokemons, 1):
            pokemon_data = POKEMON_DATA[poke['pokemon_name']]
            display_name = poke['nickname'] if poke['nickname'] else poke['pokemon_name']
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            message += (
                f"{i}. {rarity_emoji}{type_emoji} {display_name} "
                f"(Lv.{poke['level']}, 💖{poke['friendship']})\n"
            )
        
        message += f"\n请发送：放生 {pokemon_name} [编号] 来选择要放生的精灵"
        await release_pokemon.send(message)
        return
    
    # 执行放生逻辑
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
    
    

@continue_battle.handle()
async def handle_continue_battle(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    battle_key = f"{user_id}_{group_id}"
    
    if battle_key not in wild_battle_states:
        await continue_battle.send("当前没有进行中的战斗！")
        return
    
    battle_state = wild_battle_states[battle_key]
    
    # 继续战斗逻辑
    team_pokemon = db.fetch_one(
        'pokemon_collection',
        f"id = {battle_state['pokemon_id']}"
    )
    
    if not team_pokemon or team_pokemon['hp'] <= 0:
        del wild_battle_states[battle_key]
        await continue_battle.send("你的精灵已经失去战斗能力！")
        return
    
    # 重新开始战斗回合
    wild_pokemon_name = battle_state['wild_pokemon_name']
    wild_level = battle_state['wild_level']
    wild_hp = battle_state['wild_hp']
    wild_max_hp = battle_state['wild_max_hp']
    
    # 获取精灵技能（修复：与初始战斗逻辑保持一致）
    player_skills = db.fetch_all('pokemon_skills', f"pokemon_id = {team_pokemon['id']}")
    if not player_skills:
        # 如果没有学会技能，给予默认技能
        player_skills = [{'skill_name': '撞击', 'current_pp': 35, 'max_pp': 35}]
    
    # 过滤掉PP为0的技能
    available_skills = [skill for skill in player_skills if skill['current_pp'] > 0]
    if not available_skills:
        await continue_battle.send("你的精灵所有技能的PP都用完了！无法继续战斗！")
        del wild_battle_states[battle_key]
        return
    
    # 随机选择可用技能
    used_skill_data = random.choice(available_skills)
    skill_name = used_skill_data['skill_name']
    
    # 消耗PP
    if used_skill_data['skill_name'] != '撞击':  # 撞击是默认技能，不消耗PP
        new_pp = used_skill_data['current_pp'] - 1
        db.update('pokemon_skills', {
            'current_pp': new_pp
        }, f"pokemon_id = {team_pokemon['id']} AND skill_name = '{skill_name}'")
    
    # 计算伤害
    wild_stats = calculate_stats(wild_pokemon_name, wild_level)
    used_skill = SKILLS_DATA.get(skill_name, SKILLS_DATA['撞击'])
    damage_to_wild = calculate_damage(team_pokemon, {'level': wild_level, 'defense': wild_stats['defense'], 'pokemon_name': wild_pokemon_name}, used_skill)
    damage_to_player = calculate_damage({'level': wild_level, 'attack': wild_stats['attack'], 'pokemon_name': wild_pokemon_name}, team_pokemon, SKILLS_DATA['撞击'])
    
    # 更新野生精灵HP
    new_wild_hp = max(0, wild_hp - damage_to_wild)
    player_hp_after = team_pokemon['hp'] - damage_to_player
    
    battle_log = []
    player_display_name = team_pokemon['nickname'] if team_pokemon['nickname'] else team_pokemon['pokemon_name']
    
    # 显示技能使用信息
    pp_info = ""
    if skill_name != '撞击':
        remaining_pp = new_pp if used_skill_data['skill_name'] != '撞击' else used_skill_data['current_pp']
        pp_info = f" (PP: {remaining_pp}/{used_skill_data['max_pp']})"
    
    battle_log.append(f"🔥 {player_display_name} 使用了 {skill_name}！{pp_info}")
    
    # 属性相克提示
    wild_pokemon_data = POKEMON_DATA[wild_pokemon_name]
    type_effectiveness = get_type_effectiveness(used_skill['type'], wild_pokemon_data['type'])
    if type_effectiveness > 1.0:
        battle_log.append("💥 效果拔群！")
    elif type_effectiveness < 1.0:
        battle_log.append("💔 效果不佳...")
    
    battle_log.append(f"💥 对野生 {wild_pokemon_name} 造成了 {damage_to_wild} 点伤害！")
    
    if new_wild_hp <= 0:
        # 野生精灵被击败，战斗胜利
        if battle_key in wild_battle_states:  # 添加安全检查
            del wild_battle_states[battle_key]
        
        # 胜利奖励逻辑
        exp_gain = wild_level * 10 + random.randint(5, 15)
        new_exp = team_pokemon['exp'] + exp_gain
        new_level = team_pokemon['level']
        
        level_up_message = ""
        exp_needed = team_pokemon['level'] * 50
        if new_exp >= exp_needed and team_pokemon['level'] < 100:
            new_level += 1
            level_up_message = f"\n🎉 {player_display_name} 升级了！Lv.{team_pokemon['level']} → Lv.{new_level}"
            
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
        trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
        db.update('pokemon_trainers', {
            'wins': trainer['wins'] + 1
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
        
        # 奖励积分
        score_gain = wild_level * 5 + random.randint(10, 20)
        await update_player_score(user_id, group_id, score_gain, "野外战斗胜利", "精灵训练师", "战斗奖励")
        
        battle_log.append(f"\n🎊 野生 {wild_pokemon_name} 被击败了！")
        battle_log.append(f"✨ 获得经验：{exp_gain}")
        battle_log.append(f"💰 获得积分：{score_gain}")
        battle_log.append(level_up_message)
        
        # 发送战斗胜利消息
        result_message = "\n".join(battle_log)
        await continue_battle.send(result_message)
        return
        
    else:
        # 野生精灵反击
        battle_log.append(f"\n🔥 野生 {wild_pokemon_name} 使用了撞击！")
        battle_log.append(f"💥 对 {player_display_name} 造成了 {damage_to_player} 点伤害！")
        
        new_hp = max(0, player_hp_after)
        db.update('pokemon_collection', {
            'hp': new_hp
        }, f"id = {team_pokemon['id']}")
        
        if new_hp <= 0:
            # 玩家失败
            del wild_battle_states[battle_key]
            trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
            db.update('pokemon_trainers', {
                'losses': trainer['losses'] + 1
            }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
            
            battle_log.append(f"\n💀 {player_display_name}失去了战斗能力！")
            battle_log.append("战斗失败...")
        else:
            # 更新战斗状态
            wild_battle_states[battle_key].update({
                'wild_hp': new_wild_hp,
                'pokemon_hp': new_hp
            })
            
            battle_log.append(f"\n{player_display_name}剩余HP：{new_hp}/{team_pokemon['max_hp']}")
            battle_log.append(f"野生{wild_pokemon_name}剩余HP：{new_wild_hp}/{wild_max_hp}")
            battle_log.append("\n⚔️ 战斗继续中...")
            battle_log.append("💡 输入'继续战斗'继续攻击，或输入'逃离战斗'结束战斗")
    
    result_message = "\n".join(battle_log)
    await continue_battle.send(result_message)

@flee_battle.handle()
async def handle_flee_battle(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    battle_key = f"{user_id}_{group_id}"
    
    if battle_key not in wild_battle_states:
        await flee_battle.send("当前没有进行中的战斗！")
        return
    
    battle_state = wild_battle_states[battle_key]
    del wild_battle_states[battle_key]
    
    team_pokemon = db.fetch_one(
        'pokemon_collection',
        f"id = {battle_state['pokemon_id']}"
    )
    
    player_display_name = team_pokemon['nickname'] if team_pokemon['nickname'] else team_pokemon['pokemon_name']
    wild_pokemon_name = battle_state['wild_pokemon_name']
    
    message = (
        f"🏃‍♂️ {player_display_name} 成功逃离了战斗！\n"
        f"野生 {wild_pokemon_name} 回到了森林深处..."
    )
    
    await flee_battle.send(message)

@heal_pokemon.handle()
async def handle_heal_pokemon(bot: Bot, event: GroupMessageEvent):
    """治疗所有精灵（精灵中心）"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    # 检查是否是精灵训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await heal_pokemon.send("你还不是精灵训练师！")
        return
    
    # 检查冷却时间（每小时可以免费治疗一次）
    last_heal = trainer.get('last_heal_time', 0)
    current_time = int(time.time())
    cooldown = 3600  # 1小时冷却
    
    if current_time - last_heal < cooldown:
        remaining = cooldown - (current_time - last_heal)
        minutes = remaining // 60
        await heal_pokemon.send(f"精灵中心治疗冷却中，还需等待 {minutes} 分钟")
        return
    
    # 获取所有受伤的精灵
    injured_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND hp < max_hp"
    )
    
    if not injured_pokemon:
        await heal_pokemon.send("你的精灵都很健康，不需要治疗！")
        return
    
    # 治疗所有精灵
    healed_count = 0
    for pokemon in injured_pokemon:
        db.update('pokemon_collection', {
            'hp': pokemon['max_hp']
        }, f"id = {pokemon['id']}")
        healed_count += 1
    
    # 更新最后治疗时间
    db.update('pokemon_trainers', {
        'last_heal_time': current_time
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    message = (
        f"🏥 精灵中心治疗完成！\n\n"
        f"✨ 治疗了 {healed_count} 只精灵\n"
        f"💖 所有精灵已恢复满血！\n\n"
        f"⏰ 下次免费治疗：1小时后"
    )
    
    await heal_pokemon.send(message)

@heal_specific_pokemon.handle()
async def handle_heal_specific_pokemon(bot: Bot, event: GroupMessageEvent):
    """治疗指定精灵（消耗积分）"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    matched = re.match(r"^治疗\s+(.+)$", event.get_plaintext())
    if not matched:
        return
    
    pokemon_name = matched.group(1).strip()
    
    # 检查是否是精灵训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await heal_specific_pokemon.send("你还不是精灵训练师！")
        return
    
    # 查找精灵
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}')"
    )
    
    if not pokemon:
        await heal_specific_pokemon.send(f"找不到精灵：{pokemon_name}")
        return
    
    if pokemon['hp'] >= pokemon['max_hp']:
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        await heal_specific_pokemon.send(f"{display_name} 已经满血了！")
        return
    
    # 计算治疗费用
    heal_cost = 20  # 每次治疗20积分
    
    # 检查积分
    player_score = await get_player_score(user_id, group_id)
    if not player_score or player_score['total_score'] < heal_cost:
        await heal_specific_pokemon.send(f"积分不足！治疗需要 {heal_cost} 积分")
        return
    
    # 扣除积分并治疗
    db.update('pokemon_collection', {
        'hp': pokemon['max_hp']
    }, f"id = {pokemon['id']}")
    
    await update_player_score(user_id, group_id, -heal_cost, "精灵治疗", "精灵训练师", "治疗费用")
    
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    message = (
        f"🏥 治疗完成！\n\n"
        f"✨ {display_name} 已恢复满血！\n"
        f"💰 消耗积分：{heal_cost}"
    )
    
    await heal_specific_pokemon.send(message)

async def natural_hp_recovery(user_id: str, group_id: str):
    """自然HP恢复（每小时恢复10%）"""
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        return
    
    last_recovery = trainer.get('last_recovery_time', 0)
    current_time = int(time.time())
    hours_passed = (current_time - last_recovery) // 3600
    
    if hours_passed >= 1:
        # 获取所有受伤的精灵
        injured_pokemon = db.fetch_all(
            'pokemon_collection',
            f"user_id = '{user_id}' AND group_id = '{group_id}' AND hp < max_hp AND hp > 0"
        )
        
        for pokemon in injured_pokemon:
            # 每小时恢复10%最大HP
            recovery_amount = max(1, int(pokemon['max_hp'] * 0.1 * hours_passed))
            new_hp = min(pokemon['max_hp'], pokemon['hp'] + recovery_amount)
            
            db.update('pokemon_collection', {
                'hp': new_hp
            }, f"id = {pokemon['id']}")
        
        # 更新最后恢复时间
        db.update('pokemon_trainers', {
            'last_recovery_time': current_time
        }, f"user_id = '{user_id}' AND group_id = '{group_id}'")

@put_pokemon_team.handle()
async def handle_put_pokemon_team(event: GroupMessageEvent, state: T_State):
    """处理放入队伍命令"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    matched = state['_matched']
    pokemon_name = matched.group(1).strip()

    # 检查是否是训练师
    trainer = db.fetch_one(
        'pokemon_trainers',
        f"user_id = '{user_id}' AND group_id = '{group_id}'"
    )
    
    if not trainer:
        await put_pokemon_team.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找所有匹配的精灵（不在队伍中的）
    matching_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}') AND is_in_team = 0"
    )

    if not matching_pokemon:
        await put_pokemon_team.send(f"找不到可放入队伍的精灵：{pokemon_name}")
        return

    # 如果有多个匹配的精灵，选择第一个
    pokemon = matching_pokemon[0]

    if len(matching_pokemon) > 1:
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        await put_pokemon_team.send(f"找到多个 {pokemon_name}，已选择第一个：{display_name}")
    
    # 检查队伍是否已满
    team_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1"
    )
    
    if len(team_pokemon) >= 6:
        await put_pokemon_team.send("队伍已满！最多只能携带6只精灵。")
        return
    
    # 计算新的队伍位置
    new_position = len(team_pokemon) + 1
    
    # 更新精灵状态
    try:
        db.update('pokemon_collection', {
            'is_in_team': True,
            'team_position': new_position
        }, f"id = {pokemon['id']}")
        
        display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
        pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
        type_emoji = TYPES[pokemon_data['type']]['emoji']
        rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
        
        await put_pokemon_team.send(
            f"✅ {rarity_emoji}{type_emoji} {display_name} 已加入队伍！\n"
            f"📍 队伍位置：{new_position}"
        )
    except Exception as e:
        await put_pokemon_team.send(f"放入队伍失败：{str(e)}")
        return

@remove_pokemon_team.handle()
async def handle_remove_pokemon_team(event: GroupMessageEvent, state: T_State):
    """处理移出队伍命令"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    matched = state['_matched']
    pokemon_name = matched.group(1).strip()
    
    # 检查是否是训练师
    trainer = db.fetch_one(
        'pokemon_trainers',
        f"user_id = '{user_id}' AND group_id = '{group_id}'"
    )
    
    if not trainer:
        await remove_pokemon_team.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 查找指定精灵
    pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}') AND is_in_team = 1"
    )
    
    if not pokemon:
        await remove_pokemon_team.send(f"队伍中找不到精灵：{pokemon_name}")
        return
    
    # 检查是否是最后一只队伍精灵
    team_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1"
    )
    
    if len(team_pokemon) <= 1:
        await remove_pokemon_team.send("队伍中至少要保留一只精灵！")
        return
    
    old_position = pokemon['team_position']
    
    # 移出队伍
    db.update('pokemon_collection', {
        'is_in_team': False,
        'team_position': None
    }, f"id = {pokemon['id']}")
    
    # 重新排列队伍位置
    remaining_team = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1 ORDER BY team_position ASC"
    )
    
    for i, team_pokemon in enumerate(remaining_team, 1):
        db.update('pokemon_collection', {
            'team_position': i
        }, f"id = {team_pokemon['id']}")
    
    display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    type_emoji = TYPES[pokemon_data['type']]['emoji']
    rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
    
    await remove_pokemon_team.send(
        f"✅ {rarity_emoji}{type_emoji} {display_name} 已移出队伍！\n"
        f"📦 已放入精灵盒子"
    )

@switch_pokemon_position.handle()
async def handle_switch_pokemon_position(event: GroupMessageEvent, state: T_State):
    """处理调整位置命令"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    matched = state['_matched']
    pokemon_name = matched.group(1).strip()
    new_position = int(matched.group(2).strip())
    
    # 检查是否是训练师
    trainer = db.fetch_one(
        'pokemon_trainers',
        f"user_id = '{user_id}' AND group_id = '{group_id}'"
    )
    
    if not trainer:
        await switch_pokemon_position.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 获取队伍精灵
    team_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND is_in_team = 1 ORDER BY team_position ASC"
    )
    
    if not team_pokemon:
        await switch_pokemon_position.send("队伍中没有精灵！")
        return
    
    # 验证新位置
    if new_position < 1 or new_position > len(team_pokemon):
        await switch_pokemon_position.send(f"位置无效！请输入1-{len(team_pokemon)}之间的数字。")
        return
    
    # 查找要调整的精灵
    target_pokemon = None
    for pokemon in team_pokemon:
        if pokemon['pokemon_name'] == pokemon_name or pokemon['nickname'] == pokemon_name:
            target_pokemon = pokemon
            break
    
    if not target_pokemon:
        await switch_pokemon_position.send(f"队伍中找不到精灵：{pokemon_name}")
        return
    
    old_position = target_pokemon['team_position']
    
    if old_position == new_position:
        display_name = target_pokemon['nickname'] if target_pokemon['nickname'] else target_pokemon['pokemon_name']
        await switch_pokemon_position.send(f"{display_name} 已经在位置 {new_position} 了！")
        return
    
    # 调整位置逻辑
    if old_position < new_position:
        # 向后移动：中间的精灵向前移动
        for pokemon in team_pokemon:
            if old_position < pokemon['team_position'] <= new_position:
                db.update('pokemon_collection', {
                    'team_position': pokemon['team_position'] - 1
                }, f"id = {pokemon['id']}")
    else:
        # 向前移动：中间的精灵向后移动
        for pokemon in team_pokemon:
            if new_position <= pokemon['team_position'] < old_position:
                db.update('pokemon_collection', {
                    'team_position': pokemon['team_position'] + 1
                }, f"id = {pokemon['id']}")
    
    # 更新目标精灵位置
    db.update('pokemon_collection', {
        'team_position': new_position
    }, f"id = {target_pokemon['id']}")
    
    display_name = target_pokemon['nickname'] if target_pokemon['nickname'] else target_pokemon['pokemon_name']
    pokemon_data = POKEMON_DATA[target_pokemon['pokemon_name']]
    type_emoji = TYPES[pokemon_data['type']]['emoji']
    rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
    
    await switch_pokemon_position.send(
        f"✅ {rarity_emoji}{type_emoji} {display_name} 位置调整完成！\n"
        f"📍 {old_position} → {new_position}"
    )

@buy_pokeballs.handle()
async def handle_buy_pokeballs(bot: Bot, event: GroupMessageEvent):
    """积分购买精灵球"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    matched = re.match(r"^购买精灵球\s+(\d+)$", event.get_plaintext())
    if not matched:
        return
    
    try:
        quantity = int(matched.group(1))
    except ValueError:
        await buy_pokeballs.send("请输入有效的数量！")
        return
    
    if quantity <= 0:
        await buy_pokeballs.send("购买数量必须大于0！")
        return
    
    if quantity > 50:
        await buy_pokeballs.send("单次最多购买50个精灵球！")
        return
    
    # 检查是否是精灵训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = '{user_id}' AND group_id = '{group_id}'")
    if not trainer:
        await buy_pokeballs.send("你还不是精灵训练师！请先发送'开始精灵之旅'")
        return
    
    # 计算费用（每个精灵球20积分）
    cost_per_ball = 20
    total_cost = quantity * cost_per_ball
    
    # 检查积分
    
    score_info = await get_player_score(user_id, group_id)
    if not score_info:
        await buy_pokeballs.send("获取积分信息失败！")
        return
    
    current_score = score_info['total_score']
    if current_score < total_cost:
        await buy_pokeballs.send(f"积分不足！\n需要：{total_cost}积分\n当前：{current_score}积分")
        return
    
    # 计算店家好感度奖励
    bonus_balls = 0
    bonus_message = ""
    
    if quantity >= 20:  # 购买20个以上
        # 20%概率获得额外奖励
        if random.randint(1, 100) <= 20:
            bonus_balls = random.randint(2, 5)  # 随机2-5个额外精灵球
            bonus_message = f"\n\n🎁 店家看你顺眼，额外赠送了{bonus_balls}个精灵球！"
    elif quantity >= 10:  # 购买10-19个
        # 15%概率获得额外奖励
        if random.randint(1, 100) <= 15:
            bonus_balls = random.randint(1, 3)  # 随机1-3个额外精灵球
            bonus_message = f"\n\n🎁 店家心情不错，额外赠送了{bonus_balls}个精灵球！"
    elif quantity >= 5:  # 购买5-9个
        # 10%概率获得额外奖励
        if random.randint(1, 100) <= 10:
            bonus_balls = random.randint(1, 2)  # 随机1-2个额外精灵球
            bonus_message = f"\n\n🎁 店家微笑着额外给了你{bonus_balls}个精灵球！"
    
    # 扣除积分并增加精灵球
    await update_player_score(user_id, group_id, -total_cost, "购买精灵球", "精灵训练师", "商店购买")
    
    total_balls_received = quantity + bonus_balls
    new_pokeballs = trainer['pokeballs'] + total_balls_received
    db.update('pokemon_trainers', {
        'pokeballs': new_pokeballs
    }, f"user_id = '{user_id}' AND group_id = '{group_id}'")
    
    message = (
        f"🛒 购买成功！\n\n"
        f"⚾ 购买数量：{quantity}个精灵球\n"
        f"💰 消耗积分：{total_cost}\n"
    )
    
    if bonus_balls > 0:
        message += f"🎁 额外获得：{bonus_balls}个精灵球\n"
        message += f"⚾ 总共获得：{total_balls_received}个精灵球\n"
    
    message += (
        f"⚾ 当前精灵球：{new_pokeballs}个\n"
        f"💰 剩余积分：{current_score - total_cost}"
    )
    
    message += bonus_message
    
    await buy_pokeballs.send(message)

# 管理员用户ID列表（请根据实际情况修改）
ADMIN_USERS = ["939225853"]  # 请替换为实际的管理员QQ号

@migrate_pokemon_data.handle()
async def handle_migrate_pokemon_data(bot: Bot, event: GroupMessageEvent):
    """迁移精灵数据从源群到目标群"""
    user_id = str(event.user_id)
    
    # 检查管理员权限
    if user_id not in ADMIN_USERS:
        await migrate_pokemon_data.send("❌ 权限不足，只有管理员可以使用此命令")
        return
    
    try:
        # 解析命令参数
        match = re.match(r"^精灵数据迁移\s+(\d+)\s+(\d+)$", event.get_plaintext())
        if not match:
            await migrate_pokemon_data.send("❌ 命令格式错误\n正确格式：精灵数据迁移 源群号 目标群号")
            return
            
        source_group = match.group(1)
        target_group = match.group(2)
        
        if source_group == target_group:
            await migrate_pokemon_data.send("❌ 源群和目标群不能相同")
            return
        
        # 检查源群是否有数据
        source_trainers = db.fetch_all('pokemon_trainers', f"group_id = '{source_group}'")
        if not source_trainers:
            await migrate_pokemon_data.send(f"❌ 源群 {source_group} 没有精灵训练师数据")
            return
        
        # 开始迁移数据
        migrated_count = 0
        
        # 迁移训练师数据
        for trainer in source_trainers:
            # 检查目标群是否已存在该用户
            existing = db.fetch_one('pokemon_trainers', 
                                  f"user_id = '{trainer['user_id']}' AND group_id = '{target_group}'")
            if existing:
                # 如果已存在，跳过或合并数据（这里选择跳过）
                continue
                
            # 更新训练师的群号 - 使用 update 方法
            db.update(
                'pokemon_trainers',
                {'group_id': target_group},
                f"user_id = '{trainer['user_id']}' AND group_id = '{source_group}'"
            )
            
            # 迁移该用户的精灵数据 - 使用 update 方法
            db.update(
                'pokemon_collection',
                {'group_id': target_group},
                f"user_id = '{trainer['user_id']}' AND group_id = '{source_group}'"
            )
            
            migrated_count += 1
        
        await migrate_pokemon_data.send(
            f"✅ 精灵数据迁移完成！\n"
            f"📊 从群 {source_group} 迁移到群 {target_group}\n"
            f"👥 成功迁移 {migrated_count} 位训练师的数据"
        )
        
    except Exception as e:
        await migrate_pokemon_data.send(f"❌ 迁移失败：{str(e)}")

@group_score_reward.handle()
async def handle_group_score_reward(bot: Bot, event: GroupMessageEvent):
    """给指定群或当前群的所有用户增加积分"""
    user_id = str(event.user_id)
    
    # 检查管理员权限
    if user_id not in ADMIN_USERS:
        await group_score_reward.send("❌ 权限不足，只有管理员可以使用此命令")
        return
    
    try:
        # 解析命令参数
        match = re.match(r"^发放积分\s+(\d+)(?:\s+(\d+))?$", event.get_plaintext())
        if not match:
            await group_score_reward.send(
                "❌ 命令格式错误\n"
                "正确格式：\n"
                "发放积分 积分数量 (给当前群发放)\n"
                "发放积分 积分数量 群号 (给指定群发放)"
            )
            return
            
        reward_amount = int(match.group(1))
        target_group = match.group(2) if match.group(2) else str(event.group_id)
        current_group = str(event.group_id)
        
        if reward_amount <= 0:
            await group_score_reward.send("❌ 积分数量必须大于0")
            return
        
        if reward_amount > 10000:
            await group_score_reward.send("❌ 单次奖励积分不能超过10000")
            return
        
        # 获取目标群内所有精灵训练师
        trainers = db.fetch_all('pokemon_trainers', f"group_id = '{target_group}'")
        
        if not trainers:
            group_info = f"群 {target_group}" if target_group != current_group else "本群"
            await group_score_reward.send(f"❌ {group_info}暂无精灵训练师")
            return
        
        # 给所有训练师增加积分
        rewarded_count = 0
        for trainer in trainers:
            try:
                await update_player_score(
                    trainer['user_id'], 
                    target_group, 
                    reward_amount, 
                    "群积分奖励", 
                    "管理员", 
                    "群体奖励"
                )
                rewarded_count += 1
            except Exception as e:
                print(f"给用户 {trainer['user_id']} 增加积分失败: {e}")
                continue
        
        # 构建回复消息
        group_info = f"群 {target_group}" if target_group != current_group else "本群"
        await group_score_reward.send(
            f"🎉 积分发放完成！\n"
            f"🎯 目标群组：{group_info}\n"
            f"💰 每人获得：{reward_amount} 积分\n"
            f"👥 成功发放：{rewarded_count} 位训练师\n"
            f"📝 奖励原因：管理员群体奖励"
        )
        
    except Exception as e:
        await group_score_reward.send(f"❌ 积分奖励发放失败：{str(e)}")


@rename_pokemon.handle()
async def handle_rename_pokemon(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await rename_pokemon.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    # 解析精灵名、序号和新昵称
    message_text = str(event.message).strip()
    import re
    match = re.match(r"^改名\s+(.+?)(?:\s+(\d+))?\s+(.+)$", message_text)
    if not match:
        await rename_pokemon.send("请输入正确的格式：改名 精灵名 [序号] 新昵称")
        return
    
    pokemon_name = match.group(1).strip()
    selected_index = match.group(2)
    new_name = match.group(3).strip()
    
    # 验证新昵称长度
    if len(new_name) > 10:
        await rename_pokemon.send("昵称长度不能超过10个字符！")
        return
    
    if len(new_name) < 1:
        await rename_pokemon.send("昵称不能为空！")
        return
    
    # 查找所有匹配的精灵
    all_pokemon = db.fetch_all(
        'pokemon_collection',
        f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name = '{pokemon_name}' OR nickname = '{pokemon_name}') ORDER BY id ASC",
    )
    
    if not all_pokemon:
        await rename_pokemon.send(f"找不到精灵'{pokemon_name}'！")
        return
    
    # 如果有多个同名精灵但没有指定序号
    if len(all_pokemon) > 1 and selected_index is None:
        message = f"找到{len(all_pokemon)}只名为'{pokemon_name}'的精灵：\n\n"
        for i, poke in enumerate(all_pokemon, 1):
            display_name = poke['nickname'] if poke['nickname'] else poke['pokemon_name']
            pokemon_data = POKEMON_DATA[poke['pokemon_name']]
            type_emoji = TYPES[pokemon_data['type']]['emoji']
            rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
            
            message += f"{i}. {rarity_emoji}{type_emoji} {display_name} (Lv.{poke['level']})\n"
            message += f"   HP: {poke['hp']}/{poke['max_hp']} | 亲密度: {poke['friendship']}\n\n"
        
        message += f"请使用：改名 {pokemon_name} [序号] {new_name}\n"
        message += f"例如：改名 {pokemon_name} 1 {new_name}"
        
        await rename_pokemon.send(message)
        return
    
    # 选择要改名的精灵
    if selected_index is not None:
        try:
            index = int(selected_index) - 1
            if index < 0 or index >= len(all_pokemon):
                await rename_pokemon.send(f"序号无效！请选择1-{len(all_pokemon)}之间的序号")
                return
            pokemon = all_pokemon[index]
        except ValueError:
            await rename_pokemon.send("序号必须是数字！")
            return
    else:
        # 只有一只精灵的情况
        pokemon = all_pokemon[0]
    
    # 检查新昵称是否与现有精灵重复
    existing_pokemon = db.fetch_one(
        'pokemon_collection',
        f"user_id = ? AND group_id = ? AND (pokemon_name = ? OR nickname = ?) AND id != ?",
        (user_id, group_id, new_name, new_name, pokemon['id'])
    )
    
    if existing_pokemon:
        await rename_pokemon.send(f"昵称'{new_name}'已被其他精灵使用，请选择其他名字！")
        return
    
    # 更新昵称
    db.update('pokemon_collection', {
        'nickname': new_name
    }, f"id = {pokemon['id']}")
    
    pokemon_data = POKEMON_DATA[pokemon['pokemon_name']]
    type_emoji = TYPES[pokemon_data['type']]['emoji']
    rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
    old_display_name = pokemon['nickname'] if pokemon['nickname'] else pokemon['pokemon_name']
    
    await rename_pokemon.send(
        f"✅ 改名成功！\n"
        f"{rarity_emoji}{type_emoji} {old_display_name} → {new_name}\n"
        f"Lv.{pokemon['level']} | HP: {pokemon['hp']}/{pokemon['max_hp']}\n"
        f"现在可以使用'{new_name}'来操作这只精灵了！"
    )

@pokemon_detail_list.handle()
async def handle_pokemon_detail_list(bot: Bot, event: GroupMessageEvent, state: T_State):
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    matched = state['_matched']
    
    filter_name = matched.group(1).strip() if matched.group(1) else None
    
    # 检查是否是训练师
    trainer = db.fetch_one('pokemon_trainers', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not trainer:
        await pokemon_detail_list.send("你还不是精灵训练师！使用'开始精灵之旅'成为训练师")
        return
    
    # 获取精灵列表
    if filter_name:
        pokemon_list = db.fetch_all(
            'pokemon_collection',
            f"user_id = '{user_id}' AND group_id = '{group_id}' AND (pokemon_name LIKE '{filter_name}' OR nickname LIKE '{filter_name}') ORDER BY pokemon_name, id ASC",
        )
    else:
        pokemon_list = db.fetch_all(
            'pokemon_collection',
            f"user_id = '{user_id}' AND group_id = '{group_id}' ORDER BY pokemon_name, id ASC",
        )
    
    if not pokemon_list:
        message = "你还没有精灵！" if not filter_name else f"没有找到包含'{filter_name}'的精灵！"
        await pokemon_detail_list.send(message)
        return
    
    # 按精灵名分组
    grouped_pokemon = {}
    for pokemon in pokemon_list:
        key = pokemon['pokemon_name']
        if key not in grouped_pokemon:
            grouped_pokemon[key] = []
        grouped_pokemon[key].append(pokemon)
    
    message = f"📋 精灵详细列表 (共{len(pokemon_list)}只)\n\n"
    
    for pokemon_name, pokemon_group in grouped_pokemon.items():
        pokemon_data = POKEMON_DATA[pokemon_name]
        type_emoji = TYPES[pokemon_data['type']]['emoji']
        rarity_emoji = RARITY_CONFIG[pokemon_data['rarity']]['emoji']
        
        if len(pokemon_group) == 1:
            # 只有一只，正常显示
            poke = pokemon_group[0]
            display_name = poke['nickname'] if poke['nickname'] else poke['pokemon_name']
            team_status = "🔥" if poke['is_in_team'] else "📦"
            
            message += f"{team_status} {rarity_emoji}{type_emoji} {display_name} (Lv.{poke['level']})\n"
            message += f"   HP: {poke['hp']}/{poke['max_hp']} | 亲密度: {poke['friendship']}\n\n"
        else:
            # 多只同名精灵，显示序号
            message += f"{rarity_emoji}{type_emoji} {pokemon_name} (共{len(pokemon_group)}只):\n"
            for i, poke in enumerate(pokemon_group, 1):
                display_name = poke['nickname'] if poke['nickname'] else f"{poke['pokemon_name']}#{i}"
                team_status = "🔥" if poke['is_in_team'] else "📦"
                
                message += f"  {i}. {team_status} {display_name} (Lv.{poke['level']})\n"
                message += f"     HP: {poke['hp']}/{poke['max_hp']} | 亲密度: {poke['friendship']}\n"
            message += "\n"
    
    message += "\n💡 提示：\n"
    message += "• 🔥 = 队伍中，📦 = 仓库中\n"
    message += "• 改名格式：改名 精灵名 [序号] 新昵称\n"
    message += "• 查看指定精灵：精灵列表 精灵名"
    
    await pokemon_detail_list.send(message)

# 在文件末尾添加定时任务
@scheduler.scheduled_job("interval", hours=1, id="pokemon_hp_recovery")
async def scheduled_hp_recovery():
    """定时执行精灵HP自然恢复"""
    # 获取所有训练师
    trainers = db.fetch_all('pokemon_trainers', "1=1")
    
    for trainer in trainers:
        try:
            await natural_hp_recovery(trainer['user_id'], trainer['group_id'])
        except Exception as e:
            print(f"精灵HP恢复失败 - 用户:{trainer['user_id']}, 群:{trainer['group_id']}, 错误:{e}")


