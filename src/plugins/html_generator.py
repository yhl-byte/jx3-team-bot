'''
Date: 2025-02-18 13:33:31
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 16:14:35
FilePath: /bott/bot-dd/src/plugins/html_generator.py
'''
# src/plugins/chat_plugin/html_generator.py
from jinja2 import Environment, FileSystemLoader
from src.config import TEMPLATE_PATH, STATIC_PATH
import os

def render_html(team_box, template_name="team.html") -> str:
    # 获取模板目录
    template_dir = TEMPLATE_PATH.parent
    
    # 确保模板目录存在
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    # 加载模板
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    
    # 渲染数据
    html_content = template.render(
        team_box=team_box,
        static_path=STATIC_PATH.absolute()
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