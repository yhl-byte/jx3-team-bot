'''
Date: 2025-02-18 13:33:31
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-05-08 15:11:30
FilePath: /team-bot/jx3-team-bot/src/plugins/html_generator.py
'''
# src/plugins/chat_plugin/html_generator.py
from jinja2 import Environment, FileSystemLoader
from src.config import TEMPLATE_PATH, STATIC_PATH
import base64
from pathlib import Path
import os

def img_to_base64(img_path: str) -> str:
    """将本地图片转换为base64字符串"""
    return base64.b64encode(Path(img_path).read_bytes()).decode()

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
    
    # 加载模板
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(role_attr_template)
    
    # 渲染数据
    html_content = template.render(
        roleInfo=roleInfo,
        static_path=STATIC_PATH.absolute()
    )
    return html_content

    