'''
Date: 2025-02-18 13:33:31
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-26 22:57:23
FilePath: /team-bot/jx3-team-bot/src/utils/html_generator.py
'''
# src/plugins/chat_plugin/html_generator.py
from jinja2 import Environment, FileSystemLoader
from src.utils.template_manager import template_manager
from src.config import STATIC_PATH
from datetime import datetime
import time
import base64
import json
from pathlib import Path
import os
import re

def img_to_base64(img_path: str) -> str:
    """将本地图片转换为base64字符串"""
    return base64.b64encode(Path(img_path).read_bytes()).decode()

def format_time(time_str):
    """将时间字符串格式化为年月日时分秒格式"""
    # 尝试解析各种可能的时间格式
    try:
        # 尝试解析时间戳
        if isinstance(time_str, (int, float)) or (isinstance(time_str, str) and time_str.isdigit()):
            dt = datetime.fromtimestamp(float(time_str))
            return dt.strftime('%Y.%m.%d %H:%M:%S')
        
        # 尝试解析ISO格式
        if isinstance(time_str, str):
            # 移除可能的毫秒部分
            time_str = re.sub(r'\.\d+', '', time_str)
            # 替换Z为+00:00
            time_str = time_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(time_str)
            return dt.strftime('%Y.%m.%d. %H:%M:%S')
    except:
        # 如果解析失败，返回原始字符串
        return time_str

def format_date(time_str):
    """将时间字符串格式化为年月日格式"""
    # 尝试解析各种可能的时间格式
    try:
        # 尝试解析时间戳
        if isinstance(time_str, (int, float)) or (isinstance(time_str, str) and time_str.isdigit()):
            dt = datetime.fromtimestamp(float(time_str))
            return dt.strftime('%Y.%m.%d')
        
        # 尝试解析ISO格式
        if isinstance(time_str, str):
            # 移除可能的毫秒部分
            time_str = re.sub(r'\.\d+', '', time_str)
            # 替换Z为+00:00
            time_str = time_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(time_str)
            return dt.strftime('%Y.%.m%d')
    except:
        # 如果解析失败，返回原始字符串
        return time_str

def format_date_month(time_str):
    """将时间字符串格式化为月日格式"""
    # 尝试解析各种可能的时间格式
    try:
        # 尝试解析时间戳
        if isinstance(time_str, (int, float)) or (isinstance(time_str, str) and time_str.isdigit()):
            dt = datetime.fromtimestamp(float(time_str))
            return dt.strftime('%m月%d')
        
        # 尝试解析ISO格式
        if isinstance(time_str, str):
            # 移除可能的毫秒部分
            time_str = re.sub(r'\.\d+', '', time_str)
            # 替换Z为+00:00
            time_str = time_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(time_str)
            return dt.strftime('%m月%d')
    except:
        # 如果解析失败，返回原始字符串
        return time_str

def timestamp_to_relative_time(timestamp):
    """
    将时间戳转换为距离当前时间的描述性时间。
    
    参数:
        timestamp (int): 时间戳（单位：秒）
    
    返回:
        str: 距离当前时间的描述性时间，如“22秒前”、“1分钟前”等
    """
    # 获取当前时间的时间戳
    current_timestamp = int(time.time())
    
    # 计算时间差
    time_diff = current_timestamp - timestamp
    
    # 根据时间差返回不同的描述
    if time_diff < 60:  # 小于1分钟
        return f"{time_diff}秒前"
    elif time_diff < 3600:  # 小于1小时
        minutes = time_diff // 60
        return f"{minutes}分钟前"
    elif time_diff < 86400:  # 小于1天
        hours = time_diff // 3600
        return f"{hours}小时前"
    else:
        days = time_diff // 86400
        return f"{days}天前"

def timestamp_to_datetime(timestamp):
        """将时间戳转换为日期时间格式"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(timestamp, str) and timestamp.isdigit():
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return timestamp
        except:
            return timestamp

    # 添加价格格式化过滤器
def format_price_currency(price):
    if price == 0:
        return "0铜"
    
    # 计算钻、金、银、铜的数量
    z = price // 100000000  # 1钻 = 100000000铜
    gold = (price % 100000000) // 10000  # 1金 = 10000铜
    silver = (price % 10000) // 100  # 1银 = 100铜
    copper = price % 100  # 剩余为铜
    
    result = []
    if z > 0:
        result.append(f"{z}砖")
    if gold > 0:
        result.append(f"{gold}金")
    if silver > 0:
        result.append(f"{silver}银")
    if copper > 0:
        result.append(f"{copper}铜")
    
    return "".join(result) if result else "0铜"

def item_type_name(item_type):
    """物品类型名称映射"""
    type_map = {
        1: "武器",
        2: "防具", 
        3: "饰品",
        4: "药品",
        5: "材料",
        6: "武器",
        7: "装备",
        8: "饰品",
        9: "宝石",
        10: "其他"
    }
    return type_map.get(item_type, "未知")

def quality_color(quality):
    """品质颜色映射"""
    color_map = {
        1: "#9CA3AF",  # 灰色
        2: "#10B981",  # 绿色
        3: "#3B82F6",  # 蓝色
        4: "#8B5CF6",  # 紫色
        5: "#F59E0B",  # 橙色
        6: "#EF4444"   # 红色
    }
    return color_map.get(quality, "#6B7280")

def quality_name(quality):
    """品质名称映射"""
    name_map = {
        1: "破损",
        2: "普通",
        3: "优秀",
        4: "精良",
        5: "卓越",
        6: "完美"
    }
    return name_map.get(quality, "未知")

# 统一的渲染函数
def render_html(template_name: str, **kwargs) -> str:
    """
    统一的HTML模板渲染函数
    
    Args:
        template_name: 模板文件名
        **kwargs: 传递给模板的参数
    
    Returns:
        str: 渲染后的HTML内容
    """
    return template_manager.render_template(
        template_name,
        # 通用的辅助函数
        img_to_base64=img_to_base64,
        format_time=format_time,
        format_date=format_date,
        format_date_month=format_date_month,
        timestamp_to_datetime=timestamp_to_datetime,
        timestamp_to_relative_time=timestamp_to_relative_time,
        format_price_currency=format_price_currency,
        item_type_name=item_type_name,
        quality_color=quality_color,
        quality_name=quality_name,
        str=str,
        # 用户传入的参数
        **kwargs
    )

# 简化后的具体渲染函数（保持向后兼容）
def render_team_html(team_box, template_name="team.html") -> str:
    return render_html(template_name, team_box=team_box)

def render_game_help() -> str:
    return render_html("games_help.html")

def render_bot_help() -> str:
    return render_html("help_guide.html")

def render_team_help() -> str:
    return render_html("team_help.html")

def render_role_attribute(roleInfo) -> str:
    # 读取equipment.json文件
    equipment_path = os.path.join(STATIC_PATH, 'equipment.json')
    with open(equipment_path, 'r', encoding='utf-8') as f:
        equipment_data = json.load(f)
    
    return render_html(
        "role_attribute.html",
        roleInfo=roleInfo,
        equipment_data=equipment_data
    )

def render_role_cd_record(roleInfo) -> str:
    return render_html("role_cd_record.html", info=roleInfo)

def render_role_luck(roleInfo) -> str:
    # 读取luck.json文件
    luck_file_path = os.path.join(STATIC_PATH, 'lucks.json')
    with open(luck_file_path, 'r', encoding='utf-8') as f:
        luck_data = json.load(f)
    
    return render_html(
        "role_luck.html",
        info=roleInfo,
        luck_data=luck_data.get('data', [])
    )

def render_sandbox_html(info, template_name="sand_box.html") -> str:
    return render_html(
        template_name,
        info=info,
        maps=info.get('data', [])
    )

def render_blacklist_html(records) -> str:
    return render_html(
        "blacklist.html",
        records=records,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

def render_xuanjing_html(records):
    """渲染玄晶榜单HTML"""
    title = "玄晶榜单"
    sort_info = f"按价格降序排列 · 共 {len(records)} 条记录"
    
    # 格式化记录数据
    formatted_records = []
    for record in records:
        formatted_record = {
            'date': record['date'],
            'participants': record['participants'],
            'price': record['price_display'],
            'remark': record.get('remark', ''),
            'id': record['id']
        }
        formatted_records.append(formatted_record)
    
    return render_html(
        "xuanjing.html",
        title=title,
        sort_info=sort_info,
        records=formatted_records
    )

def render_trade_records_html(record):
    """渲染物价查询HTML"""
    return render_html("trade_records.html", data=record)

def render_role_achievement_html(record):
    """渲染成就查询HTML"""
    return render_html("role_achievement.html", data=record)

def render_diary_achievement_html(record):
    """渲染资历分布HTML"""
    return render_html("diary_achievement.html", data=record)

def render_member_recruit_html(record):
    """渲染招募信息HTML"""
    return render_html("member_recruit.html", data=record)

def render_auction_html(record):
    """渲染交易行HTML"""
    return render_html("auction.html", data=record)

def render_black_book_html(record):
    """渲染副本掉落HTML"""
    return render_html(
        "black_book.html",
        boss_data=record
    )

def render_baizhan_html(data):
    """渲染角色百战HTML"""
    print('角色百战', data)
    return render_html(
        "baizhan_template.html",
        **data,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        get_color_class=lambda n: f'color-{n}' # 将函数传给模板
    )

def render_gold_price_html(data):
    """渲染金价查询HTML"""
    print('金价数据', data)
    return render_html(
        "gold_price_template.html",
        data=data,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

def render_mountain_pass_html(data):
    """渲染关隘BOSS HTML"""
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    current_timestamp = int(time.time())
    
    return render_html(
        "mountain_pass_template.html",
        data=data,
        current_time=current_time,
        current_timestamp=current_timestamp
    )

def render_daily_prediction_html(data):
    """渲染关隘BOSS HTML"""
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    return render_html(
        "daily_prediction_template.html",
        data=data,
        current_time=current_time,
    )