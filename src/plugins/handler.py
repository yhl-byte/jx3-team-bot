'''
Date: 2025-02-18 13:34:16
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-11 14:16:59
FilePath: /team-bot/jx3-team-bot/src/plugins/handler.py
'''
# src/plugins/chat_plugin/handler.py
from nonebot import on_message,on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message,GroupMessageEvent
from .html_generator import render_game_help
from .render_image import generate_html_screenshot
from ..utils.index import path_to_base64
from src.config import STATIC_PATH
import os


# # 游戏中心帮助
GameHelp = on_regex(pattern=r'^(游戏帮助|游戏大厅)$',priority=1)
@GameHelp.handle()
async def handle_game_help(bot: Bot, event: GroupMessageEvent, state: T_State):

    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成游戏帮助信息，请稍候...")
    
    # 生成帮助页面内容
    html_content = render_game_help()
    
    # 转换为图片
    image_path = await generate_html_screenshot(html_content, 1920)
    
    # 发送图片
    await GameHelp.finish(MessageSegment.image(path_to_base64(image_path)))
    
    # 清理临时文件
    os.unlink(image_path)

