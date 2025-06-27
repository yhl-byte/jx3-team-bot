'''
Date: 2025-02-18 13:34:16
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-27 10:07:48
FilePath: /team-bot/jx3-team-bot/src/plugins/handler.py
'''
# src/plugins/chat_plugin/handler.py
from nonebot import on_message,on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message,GroupMessageEvent
from ..utils.permission import require_admin_permission
from src.utils.html_generator import render_game_help,render_bot_help
from src.utils.render_context import render_and_cleanup
from ..utils.index import path_to_base64
from src.config import STATIC_PATH
from .database import NianZaiDB  # 添加数据库导入
import os


# 添加数据库实例
db = NianZaiDB()
db.init_db()


# 定义所有游戏插件
GAME_PLUGINS = {
    "jx3_api": "剑三助手",
    "jx3_team": "开团功能", 
    "werewolf": "狼人杀",
    "gomoku_game": "五子棋",
    "tic_tac_toe_game": "井字棋",
    "russian_roulette": "俄罗斯轮盘",
    "classic_lines_game": "经典台词",
    "guess_song_game": "猜歌游戏",
    "bottle_sort_game": "瓶子排序",
    "forbidden_word_game": "禁词游戏",
    "life_restart_game": "人生重开",
    "guessing_game": "开口中",
    "describe_and_guess": "猜词游戏",
    "blackjack": "21点",
    "turtle_soup_game": "海龟汤",
    "undercover": "谁是卧底",
    "xuanjing_record": "玄晶记录",
    "blacklist_record": "黑本记录",
    "weather_helper": "天气助手",
    "game_score": "积分系统",
    "simple_dice": "掷骰子",
    "deepseek_ai": "AI对话助手"
}

# 插件管理命令
PluginManager = on_regex(pattern=r'^插件管理(?:\s+(\S+))?(?:\s+(开启|关闭|状态))?$', priority=1)
@PluginManager.handle()
async def handle_plugin_manager(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, PluginManager):
        return
    
    matched = state["_matched"]
    plugin_name = matched.group(1) if matched else None
    action = matched.group(2) if matched else None
    group_id = event.group_id
    
    if not plugin_name and not action:
        # 显示所有插件状态
        all_status = db.get_all_plugin_status(group_id)
        msg_lines = ["📋 插件状态列表："]
        
        for plugin_id, plugin_display_name in GAME_PLUGINS.items():
            status = "✅开启" if all_status.get(plugin_id, True) else "❌关闭"
            msg_lines.append(f"• {plugin_display_name}：{status}")
        
        msg_lines.append("\n💡 使用方法：")
        msg_lines.append("插件管理 [插件名] [开启/关闭/状态]")
        msg_lines.append("例如：插件管理 剑三助手 开启")
        
        msg = "\n".join(msg_lines)
        await PluginManager.finish(message=Message(msg))
    
    # 查找插件ID
    plugin_id = None
    for pid, pname in GAME_PLUGINS.items():
        if plugin_name == pname or plugin_name == pid:
            plugin_id = pid
            break
    
    if not plugin_id:
        available_plugins = "、".join(GAME_PLUGINS.values())
        msg = f"❌ 未找到插件：{plugin_name}\n\n可用插件：{available_plugins}"
        await PluginManager.finish(message=Message(msg))
    
    plugin_display_name = GAME_PLUGINS[plugin_id]
    
    if not action or action == "状态":
        # 查询状态
        enabled = db.get_plugin_status(plugin_id, group_id)
        status = "✅开启" if enabled else "❌关闭"
        msg = f"📊 {plugin_display_name} 当前状态：{status}"
    elif action == "开启":
        success = db.set_plugin_status(plugin_id, group_id, True)
        if success:
            msg = f"✅ {plugin_display_name} 已开启"
        else:
            msg = f"❌ 开启 {plugin_display_name} 失败，请稍后重试"
    elif action == "关闭":
        success = db.set_plugin_status(plugin_id, group_id, False)
        if success:
            msg = f"❌ {plugin_display_name} 已关闭"
        else:
            msg = f"❌ 关闭 {plugin_display_name} 失败，请稍后重试"
    
    await PluginManager.finish(message=Message(msg))

# 游戏插件入口
GamePluginEntry = on_regex(pattern=r'^(游戏插件|插件列表)$', priority=1)
@GamePluginEntry.handle()
async def handle_game_plugin_entry(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    all_status = db.get_all_plugin_status(group_id)
    
    enabled_plugins = []
    disabled_plugins = []
    
    for plugin_id, plugin_display_name in GAME_PLUGINS.items():
        if all_status.get(plugin_id, True):
            enabled_plugins.append(plugin_display_name)
        else:
            disabled_plugins.append(plugin_display_name)
    
    msg_lines = ["🎮 游戏插件中心"]
    
    if enabled_plugins:
        msg_lines.append("\n✅ 已启用插件：")
        msg_lines.extend([f"• {name}" for name in enabled_plugins])
    
    if disabled_plugins:
        msg_lines.append("\n❌ 已禁用插件：")
        msg_lines.extend([f"• {name}" for name in disabled_plugins])
    
    msg_lines.append("\n💡 管理员可使用 '插件管理' 命令进行管理")
    msg_lines.append("📖 使用 '游戏帮助' 查看详细说明")
    
    msg = "\n".join(msg_lines)
    await GamePluginEntry.finish(message=Message(msg))

# # 游戏中心帮助
GameHelp = on_regex(pattern=r'^(游戏帮助|游戏大厅)$',priority=1)
@GameHelp.handle()
async def handle_game_help(bot: Bot, event: GroupMessageEvent, state: T_State):

    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成游戏帮助信息，请稍候...")
    # try:
    #     # 构建图片路径
    #     image_path = os.path.join(STATIC_PATH, 'game-help.png')
        
    #     # 检查文件是否存在
    #     if not os.path.exists(image_path):
    #         await GameHelp.finish(message="❌ 游戏大厅图片文件不存在")
    #         return
        
    #     # 发送图片
    #     await GameHelp.send(MessageSegment.image(path_to_base64(image_path)))
        
    # except Exception as e:
    #     print(f"发送加速图片失败: {e}")
    #     await GameHelp.finish(message="❌ 发送游戏大厅图片失败")
    
    # 生成帮助页面内容
    html_content = render_game_help()
    # 转换为图片
    image_path = await render_and_cleanup(html_content, 1920)
    
    try:
        # 发送图片
        await GameHelp.finish(MessageSegment.image(path_to_base64(image_path)))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
    
# 加速命令
NianZaiHelp = on_regex(pattern=r'^帮助$', priority=1)
@NianZaiHelp.handle()
async def handle_bot_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    """发送年崽帮助图片"""
    # 发送处理提示
    processing_msg = await bot.send(event=event, message="正在生成年崽帮助信息，请稍候...")
    try:
        # 构建图片路径
        image_path = os.path.join(STATIC_PATH, 'help.png')
        
        # 检查文件是否存在
        if not os.path.exists(image_path):
            await NianZaiHelp.finish(message="❌ 年崽帮助图片文件不存在")
            return
        
        # 发送图片
        await NianZaiHelp.send(MessageSegment.image(path_to_base64(image_path)))
        
    except Exception as e:
        print(f"发送加速图片失败: {e}")
        await NianZaiHelp.finish(message="❌ 发送年崽帮助图片失败")

