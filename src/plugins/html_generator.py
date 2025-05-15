'''
Date: 2025-02-18 13:33:31
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-05-15 18:09:51
FilePath: /team-bot/jx3-team-bot/src/plugins/html_generator.py
'''
# src/plugins/chat_plugin/html_generator.py
from jinja2 import Environment, FileSystemLoader
from src.config import TEMPLATE_PATH, STATIC_PATH
from datetime import datetime
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

def render_html(team_box, template_name="team.html") -> str:
    # 获取模板目录
    template_dir = TEMPLATE_PATH.parent
    
    # 确保模板目录存在
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    # 加载模板
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,
        extensions=['jinja2.ext.do'] 
        )
    template = env.get_template(template_name)
    
    # 渲染数据
    html_content = template.render(
        team_box=team_box,
        static_path=STATIC_PATH.absolute(),
        img_to_base64=img_to_base64,
        str=str 
    )
    return html_content

def render_help() -> str:
    # 获取模板目录
    template_dir = TEMPLATE_PATH.parent
    help_template = "help.html"
    
    # 确保模板目录存在
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    # 加载模板
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(help_template)
    
    # 渲染数据
    html_content = template.render(
        static_path=STATIC_PATH.absolute()
    )
    return html_content

def render_role_attribute(roleInfo) -> str:
    # 获取模板目录
    template_dir = TEMPLATE_PATH.parent
    role_attr_template = "role_attribute.html"
    
    # 确保模板目录存在
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    # 读取equipment.json文件
    equipment_path = os.path.join(STATIC_PATH, 'equipment.json')
    with open(equipment_path, 'r', encoding='utf-8') as f:
        equipment_data = json.load(f)
    
    # 加载模板
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(role_attr_template)
    
    # 渲染数据
    html_content = template.render(
        roleInfo=roleInfo,
        equipment_data=equipment_data,
        static_path=STATIC_PATH.absolute()
    )
    return html_content

def render_role_cd_record(roleInfo) -> str:
    # 获取模板目录
    template_dir = TEMPLATE_PATH.parent
    role_attr_template = "role_cd_record.html"
    
    # 确保模板目录存在
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    # 加载模板
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(role_attr_template)
    
    # 渲染数据
    html_content = template.render(
        info=roleInfo,
        static_path=STATIC_PATH.absolute()
    )
    return html_content
    
def render_role_luck(roleInfo) -> str:
    # 获取模板目录
    template_dir = TEMPLATE_PATH.parent
    role_attr_template = "role_luck.html"
    
    # 确保模板目录存在
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    # 读取luck.json文件
    luck_file_path = os.path.join(STATIC_PATH, 'lucks.json')
    with open(luck_file_path, 'r', encoding='utf-8') as f:
        luck_data = json.load(f)
    
    # 加载模板
    env = Environment(loader=FileSystemLoader(template_dir),
        autoescape=True,
        extensions=['jinja2.ext.do'] )
    template = env.get_template(role_attr_template)
    
    # 渲染数据
    html_content = template.render(
        info=roleInfo,
        format_time=format_time,
        format_date=format_date,
        format_date_month=format_date_month,
        luck_data=luck_data.get('data', []),
        static_path=STATIC_PATH.absolute()
    )
    return html_content
    
    