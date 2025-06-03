'''
Date: 2025-06-03 13:02:56
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-03 13:04:29
FilePath: /team-bot/jx3-team-bot/src/plugins/friend_handler.py
'''
from nonebot import on_request
from nonebot.adapters.onebot.v11 import Bot, FriendRequestEvent
from nonebot.log import logger

# 监听好友请求事件
friend_request = on_request()

@friend_request.handle()
async def handle_friend_request(bot: Bot, event: FriendRequestEvent):
    """自动同意好友请求"""
    try:
        # 自动同意好友请求
        await bot.set_friend_add_request(
            flag=event.flag,
            approve=True,  # True表示同意，False表示拒绝
            remark=""  # 可选：设置备注
        )
        logger.info(f"已自动同意用户 {event.user_id} 的好友请求")
    except Exception as e:
        logger.error(f"处理好友请求失败: {e}")


# @friend_request.handle()
# async def handle_friend_request(bot: Bot, event: FriendRequestEvent):
#     """有条件地同意好友请求"""
#     try:
#         # 可以根据需要添加条件判断
#         # 例如：检查用户ID、验证消息内容等
        
#         # 获取请求信息
#         user_id = event.user_id
#         comment = event.comment  # 验证消息
        
#         # 这里可以添加你的判断逻辑
#         should_approve = True  # 根据你的需求修改这个条件
        
#         if should_approve:
#             await bot.set_friend_add_request(
#                 flag=event.flag,
#                 approve=True,
#                 remark=f"自动添加-{user_id}"
#             )
#             logger.info(f"已自动同意用户 {user_id} 的好友请求，验证消息：{comment}")
#         else:
#             await bot.set_friend_add_request(
#                 flag=event.flag,
#                 approve=False,
#                 remark="不符合条件"
#             )
#             logger.info(f"已拒绝用户 {user_id} 的好友请求")
            
#     except Exception as e:
#         logger.error(f"处理好友请求失败: {e}")