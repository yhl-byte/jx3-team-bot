from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.typing import T_State
from src.utils.permission import require_admin_permission
import re

# 禁言命令处理器
ban_member = on_regex(pattern=r'^禁言\s*(@\d+|\d+)\s*(\d+)?分钟?$', priority=1)

@ban_member.handle()
async def handle_ban_member(bot: Bot, event: GroupMessageEvent, state: T_State):
    """禁言群成员"""
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, ban_member):
        return
    
    matched = state["_matched"]
    if matched:
        try:
            # 解析用户ID和禁言时长
            user_mention = matched.group(1)
            duration_str = matched.group(2)
            
            # 提取用户ID
            if user_mention.startswith('@'):
                user_id = int(user_mention[1:])
            else:
                user_id = int(user_mention)
            
            # 设置禁言时长（默认5分钟）
            duration_minutes = int(duration_str) if duration_str else 5
            duration_seconds = duration_minutes * 60
            
            # 限制禁言时长（最长30天）
            max_duration = 30 * 24 * 60 * 60  # 30天
            if duration_seconds > max_duration:
                await ban_member.finish("禁言时长不能超过30天")
                return
            
            # 执行禁言
            await bot.set_group_ban(
                group_id=event.group_id,
                user_id=user_id,
                duration=duration_seconds
            )
            
            # 获取用户信息
            try:
                user_info = await bot.get_group_member_info(
                    group_id=event.group_id,
                    user_id=user_id
                )
                username = user_info.get('card') or user_info.get('nickname', str(user_id))
            except:
                username = str(user_id)
            
            msg = f"已将 {username} 禁言 {duration_minutes} 分钟"
            await ban_member.finish(message=Message(msg))
            
        except ValueError:
            await ban_member.finish("用户ID格式错误")
        except Exception as e:
            await ban_member.finish(f"禁言失败：{str(e)}")

# 解除禁言命令
unban_member = on_regex(pattern=r'^解除禁言\s*(@\d+|\d+)$', priority=1)

@unban_member.handle()
async def handle_unban_member(bot: Bot, event: GroupMessageEvent, state: T_State):
    """解除群成员禁言"""
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, unban_member):
        return
    
    matched = state["_matched"]
    if matched:
        try:
            # 解析用户ID
            user_mention = matched.group(1)
            if user_mention.startswith('@'):
                user_id = int(user_mention[1:])
            else:
                user_id = int(user_mention)
            
            # 解除禁言（设置禁言时长为0）
            await bot.set_group_ban(
                group_id=event.group_id,
                user_id=user_id,
                duration=0
            )
            
            # 获取用户信息
            try:
                user_info = await bot.get_group_member_info(
                    group_id=event.group_id,
                    user_id=user_id
                )
                username = user_info.get('card') or user_info.get('nickname', str(user_id))
            except:
                username = str(user_id)
            
            msg = f"已解除 {username} 的禁言"
            await unban_member.finish(message=Message(msg))
            
        except ValueError:
            await unban_member.finish("用户ID格式错误")
        except Exception as e:
            await unban_member.finish(f"解除禁言失败：{str(e)}")