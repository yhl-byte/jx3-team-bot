'''
Author: yhl
Date: 2024-12-19
Description: 剑网3 WebSocket 事件监听插件
'''
import asyncio
import json
import websockets
from datetime import datetime
from typing import Dict, Optional
from nonebot import on_regex, require, get_driver, get_bot
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message
from nonebot.log import logger
from ..utils.permission import require_admin_permission
from .database import NianZaiDB
from src.config import JX3_TOKEN

# 初始化数据库
db = NianZaiDB()

# WebSocket 连接配置
WS_URL = "wss://socket.jx3api.com"
token = JX3_TOKEN

# 全局变量
ws_connection = None
ws_task = None
subscribed_groups = set()  # 订阅事件的群组

# 插件名称
PLUGIN_NAME = "jx3_websocket"

# 事件类型映射
EVENT_TYPES = {
    2001: "开服报时",
    2002: "新闻资讯", 
    2003: "游戏更新",
    2004: "八卦速报",
    2005: "关隘首领",
    2006: "云丛预告"
}

# 状态检查装饰器
def check_plugin_enabled(func):
    """检查插件是否启用的装饰器"""
    async def wrapper(bot: Bot, event: GroupMessageEvent, state: T_State):
        group_id = event.group_id
        enabled = db.get_plugin_status("jx3_websocket", group_id)
        
        if not enabled:
            return
        
        return await func(bot, event, state)
    return wrapper

# WebSocket 连接管理
class JX3WebSocketManager:
    def __init__(self):
        self.connection = None
        self.is_running = False
        self.reconnect_interval = 30  # 重连间隔（秒）
        
    async def connect(self):
        """建立 WebSocket 连接"""
        try:
            # headers = {
            #     "Authorization": f"Bearer {token}"
            # } if token else {}
            
            self.connection = await websockets.connect(
                WS_URL,
                # extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            logger.info(f"WebSocket 连接成功: {WS_URL}")
            return True
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开 WebSocket 连接"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("WebSocket 连接已断开")
    
    async def send_message(self, message: dict):
        """发送消息到 WebSocket"""
        if self.connection:
            try:
                await self.connection.send(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"发送 WebSocket 消息失败: {e}")
                return False
        return False
    
    async def listen(self):
        """监听 WebSocket 消息"""
        while self.is_running:
            try:
                if not self.connection:
                    if not await self.connect():
                        await asyncio.sleep(self.reconnect_interval)
                        continue
                
                async for message in self.connection:
                    try:
                        data = json.loads(message)
                        await self.handle_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"解析 WebSocket 消息失败: {e}")
                    except Exception as e:
                        logger.error(f"处理 WebSocket 消息失败: {e}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket 连接断开，尝试重连...")
                self.connection = None
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                logger.error(f"WebSocket 监听异常: {e}")
                await asyncio.sleep(self.reconnect_interval)
    
    async def handle_message(self, data: dict):
        """处理接收到的 WebSocket 消息"""
        try:
            action = data.get('action')
            event_data = data.get('data', {})
            
            # 根据 action 类型处理不同的消息
            if action == 2001:
                await self.handle_server_status(event_data)
            elif action == 2002:
                await self.handle_news_event(event_data)
            elif action == 2003:
                await self.handle_game_update(event_data)
            # elif action == 2004:
            #     await self.handle_gossip_news(event_data)
            # elif action == 2005:
            #     await self.handle_castle_leader(event_data)
            # elif action == 2006:
            #     await self.handle_yuncong_forecast(event_data)
            else:
                event_name = EVENT_TYPES.get(action, f"未知事件({action})")
                logger.info(f"收到事件: {event_name}")
                
        except Exception as e:
            logger.error(f"处理 WebSocket 事件失败: {e}")
    
    async def handle_server_status(self, data: dict):
        """处理开服报时事件 (action: 2001)"""
        zone = data.get('zone', '')
        server = data.get('server', '')
        status = data.get('status', 0)
        
        status_text = "开服" if status == 1 else "维护中"
        status_emoji = "🟢" if status == 1 else "🔴"
        
        message = f"{status_emoji} 开服报时\n" \
                 f"区服：{zone}\n" \
                 f"服务器：{server}\n" \
                 f"状态：{status_text}\n" \
                 f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await self.broadcast_to_groups(message)
    
    async def handle_news_event(self, data: dict):
        """处理新闻资讯事件 (action: 2002)"""
        news_class = data.get('class', '')
        title = data.get('title', '')
        url = data.get('url', '').strip('` ')
        date = data.get('date', '')
        
        message = f"📰 新闻资讯\n" \
                 f"分类：{news_class}\n" \
                 f"标题：{title}\n" \
                 f"日期：{date}\n"
        
        if url:
            message += f"链接：{url}"
        
        await self.broadcast_to_groups(message)
    
    async def handle_game_update(self, data: dict):
        """处理游戏更新事件 (action: 2003)"""
        now_version = data.get('now_version', '')
        new_version = data.get('new_version', '')
        package_num = data.get('package_num', 0)
        package_size = data.get('package_size', '')
        
        message = f"🔄 游戏更新\n" \
                 f"当前版本：{now_version}\n" \
                 f"新版本：{new_version}\n" \
                 f"更新包数量：{package_num}个\n" \
                 f"更新大小：{package_size}"
        
        await self.broadcast_to_groups(message)
    
    async def handle_gossip_news(self, data: dict):
        """处理八卦速报事件 (action: 2004)"""
        news_class = data.get('class', '')
        server = data.get('server', '')
        name = data.get('name', '')
        title = data.get('title', '')
        url = data.get('url', '').strip('` ')
        date = data.get('date', '')
        
        message = f"🔥 八卦速报\n" \
                 f"分类：{news_class}\n" \
                 f"服务器：{server}\n" \
                 f"贴吧：{name}\n" \
                 f"标题：{title}\n" \
                 f"日期：{date}\n"
        
        if url:
            message += f"链接：{url}"
        
        await self.broadcast_to_groups(message)
    
    async def handle_castle_leader(self, data: dict):
        """处理关隘首领事件 (action: 2005)"""
        server = data.get('server', '')
        castle = data.get('castle', '')
        start_timestamp = data.get('start', 0)
        
        # 转换时间戳为可读格式
        if start_timestamp:
            try:
                start_time = datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, OSError):
                start_time = "时间解析失败"
        else:
            start_time = "未知时间"
        
        message = f"⚔️ 关隘首领\n" \
                 f"服务器：{server}\n" \
                 f"关隘名称：{castle}\n" \
                 f"开始时间：{start_time}\n" \
                 f"提醒：首领即将可抢占，请做好准备！"
        
        await self.broadcast_to_groups(message)

    async def handle_yuncong_forecast(self, data: dict):
        """处理云丛预告事件 (action: 2006)"""
        name = data.get('name', '')
        site = data.get('site', '')
        desc = data.get('desc', '')
        timestamp = data.get('time', 0)
        
        # 转换时间戳为可读格式
        if timestamp:
            try:
                forecast_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, OSError):
                forecast_time = "时间解析失败"
        else:
            forecast_time = "未知时间"
        
        message = f"☁️ 云丛预告\n" \
                 f"活动名称：{name}\n" \
                 f"活动地点：{site}\n" \
                 f"活动描述：{desc}\n" \
                 f"预告时间：{forecast_time}"
        
        await self.broadcast_to_groups(message)
    
    async def broadcast_to_groups(self, message: str):
        """向订阅的群组广播消息"""
        try:
            bot = get_bot()
            for group_id in subscribed_groups:
                try:
                    await bot.send_group_msg(group_id=int(group_id), message=message)
                except Exception as e:
                    logger.error(f"向群组 {group_id} 发送消息失败: {e}")
        except Exception as e:
            logger.error(f"广播消息失败: {e}")
    
    async def start(self):
        """启动 WebSocket 监听"""
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self.listen())
            logger.info("JX3 WebSocket 监听已启动")
    
    async def stop(self):
        """停止 WebSocket 监听"""
        self.is_running = False
        await self.disconnect()
        logger.info("JX3 WebSocket 监听已停止")

# 创建 WebSocket 管理器实例
ws_manager = JX3WebSocketManager()

# 插件开关控制命令
JX3WSPluginControl = on_regex(pattern=r'^剑三推送\s*(开启|关闭|状态)$', priority=1)
@JX3WSPluginControl.handle()
async def handle_ws_plugin_control(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, JX3WSPluginControl):
        return
    
    matched = state["_matched"]
    if matched:
        action = matched.group(1)  # "开启"、"关闭" 或 "状态"
        group_id = str(event.group_id)
        
        if action == "开启":
            success = db.set_plugin_status("jx3_websocket", event.group_id, True)
            if success:
                subscribed_groups.add(group_id)
                if not ws_manager.is_running:
                    await ws_manager.start()
                msg = "剑三推送功能已开启\n将接收：开服报时、新闻资讯、游戏更新、八卦速报、关隘首领、云丛预告"
            else:
                msg = "开启剑三推送功能失败，请稍后重试"
        elif action == "关闭":
            success = db.set_plugin_status("jx3_websocket", event.group_id, False)
            if success:
                subscribed_groups.discard(group_id)
                if not subscribed_groups and ws_manager.is_running:
                    await ws_manager.stop()
                msg = "剑三推送功能已关闭"
            else:
                msg = "关闭剑三推送功能失败，请稍后重试"
        else:  # 状态
            enabled = db.get_plugin_status("jx3_websocket", event.group_id)
            status = "开启" if enabled else "关闭"
            ws_status = "运行中" if ws_manager.is_running else "已停止"
            msg = f"当前剑三推送功能状态：{status}\nWebSocket状态：{ws_status}"
        
        await JX3WSPluginControl.finish(message=Message(msg))

# 事件类型过滤设置
EventFilter = on_regex(pattern=r'^推送设置\s*(开服|新闻|更新|八卦)\s*(开启|关闭)$', priority=1)
@EventFilter.handle()
async def handle_event_filter(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, EventFilter):
        return
    
    matched = state["_matched"]
    if matched:
        event_type = matched.group(1)  # "开服"、"新闻"、"更新"、"八卦"
        action = matched.group(2)  # "开启"、"关闭"
        group_id = str(event.group_id)
        
        # 这里可以扩展为更细粒度的事件过滤控制
        # 暂时只提供提示信息
        event_name_map = {
            "开服": "开服报时",
            "新闻": "新闻资讯", 
            "更新": "游戏更新",
            "八卦": "八卦速报",
            "关隘": "关隘首领",
            "云丛": "云丛预告"
        }
        
        event_name = event_name_map.get(event_type, event_type)
        status = "开启" if action == "开启" else "关闭"
        
        msg = f"已{status}{event_name}推送\n(注：当前版本暂不支持单独事件过滤，此功能将在后续版本中实现)"
        
        await EventFilter.finish(message=Message(msg))

# WebSocket 连接状态查询
WSStatus = on_regex(pattern=r'^推送状态$', priority=1)
@WSStatus.handle()
@check_plugin_enabled
async def handle_ws_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    connection_status = "已连接" if ws_manager.connection else "未连接"
    running_status = "运行中" if ws_manager.is_running else "已停止"
    subscribed_count = len(subscribed_groups)
    
    msg = f"📡 WebSocket 状态\n" \
          f"连接状态：{connection_status}\n" \
          f"运行状态：{running_status}\n" \
          f"订阅群组：{subscribed_count}个\n" \
          f"支持事件：{', '.join(EVENT_TYPES.values())}"
    
    await WSStatus.finish(message=Message(msg))

# 手动重连 WebSocket
WSReconnect = on_regex(pattern=r'^重连推送$', priority=1)
@WSReconnect.handle()
async def handle_ws_reconnect(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查管理员权限
    if not await require_admin_permission(bot, event.group_id, event.user_id, WSReconnect):
        return
    
    try:
        await ws_manager.disconnect()
        if await ws_manager.connect():
            msg = "✅ WebSocket 重连成功"
        else:
            msg = "❌ WebSocket 重连失败"
    except Exception as e:
        msg = f"❌ 重连过程中发生错误：{str(e)}"
    
    await WSReconnect.finish(message=Message(msg))

# 获取驱动器，用于在启动时初始化
driver = get_driver()

@driver.on_startup
async def startup():
    """机器人启动时的初始化"""
    logger.info("JX3 WebSocket 插件已加载")
    # 加载已订阅的群组
    try:
        enabled_groups = db.get_enabled_groups("jx3_websocket")
        for group_id in enabled_groups:
            subscribed_groups.add(str(group_id))
        
        if subscribed_groups:
            logger.info(f"已加载 {len(subscribed_groups)} 个订阅群组: {list(subscribed_groups)}")
            # 如果有订阅群组，启动 WebSocket 连接
            await ws_manager.start()
            logger.info("WebSocket 连接已启动")
        else:
            logger.info("暂无订阅群组，WebSocket 连接待命")
    except Exception as e:
        logger.error(f"加载订阅群组失败: {e}")

@driver.on_shutdown
async def shutdown():
    """机器人关闭时的清理"""
    if ws_manager.is_running:
        await ws_manager.stop()
    logger.info("JX3 WebSocket 插件已卸载")