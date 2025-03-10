'''
Date: 2025-03-06 13:17:27
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 13:17:46
FilePath: /bott/bot-dd/src/utils/auth.py
'''
from nonebot.adapters.onebot.v11 import Bot, Message

async def check_admin_permission(bot: Bot, group_id: int, user_id: int) -> bool:
    """
    检查用户是否为群管理员
    :param bot: Bot 实例
    :param group_id: 群号
    :param user_id: 用户 QQ 号
    :return: 是否为管理员
    """
    admins = await bot.get_group_member_list(group_id=group_id)
    return any(
        admin["user_id"] == user_id and 
        (admin["role"] in ["admin", "owner"]) 
        for admin in admins
    )

async def require_admin_permission(bot: Bot, group_id: int, user_id: int, handler) -> bool:
    """
    权限检查装饰器
    :param bot: Bot 实例
    :param group_id: 群号
    :param user_id: 用户 QQ 号
    :param handler: 处理器实例
    :return: 是否继续执行
    """
    if not await check_admin_permission(bot, group_id, user_id):
        await handler.finish(message=Message("您不是管理员，没有权限执行此操作"))
        return False
    return True