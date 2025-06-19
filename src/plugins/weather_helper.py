'''
Date: 2025-05-22 18:16:28
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-19 16:00:09
FilePath: /team-bot/jx3-team-bot/src/plugins/weather_helper.py
'''
# src/plugins/weather_helper.py
from nonebot import on_regex, require, get_driver
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message
import aiohttp
import json
from typing import Dict, List, Optional, Tuple
import re
import os
import yaml
import time
import jwt
from src.config import (
    QWEATHER_API_KEY, 
    QWEATHER_PRIVATE_KEY, 
    QWEATHER_PROJECT_ID, 
    QWEATHER_KEY_ID,
    QWEATHER_CITY_LOOKUP_API,
    QWEATHER_NOW_API,
    QWEATHER_3D_API
)

# 导入定时任务模块
scheduler = require("nonebot_plugin_apscheduler").scheduler

def format_private_key(key_string: str) -> str:
    """格式化私钥字符串"""
    if not key_string:
        return ""
    
    # 将\n转换为实际换行符
    return key_string.replace('\\n', '\n')

# 使用格式化后的私钥
QWEATHER_PRIVATE_KEY = format_private_key(os.getenv('QWEATHER_PRIVATE_KEY', ''))

# 和风天气API配置 - 从环境变量获取
CITY_LOOKUP_API = QWEATHER_CITY_LOOKUP_API
WEATHER_NOW_API = QWEATHER_NOW_API
WEATHER_3D_API = QWEATHER_3D_API

# 和风天气API密钥配置 - 从环境变量获取
PRIVATE_KEY = QWEATHER_PRIVATE_KEY
PROJECT_ID = QWEATHER_PROJECT_ID
KEY_ID = QWEATHER_KEY_ID
# 当前API密钥
current_api_key = ""



def validate_config():
    """验证配置是否完整"""
    required_vars = [
        'QWEATHER_PRIVATE_KEY',
        'QWEATHER_PROJECT_ID', 
        'QWEATHER_KEY_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# 在应用启动时调用验证
validate_config()

# 生成JWT令牌
def generate_api_key() -> str:
    global current_api_key
    
    payload = {
        'iat': int(time.time()) - 30,  # 发布时间提前30秒，避免时间差异问题
        'exp': int(time.time()) + 43200,  # 12小时过期
        'sub': PROJECT_ID
    }
    
    headers = {
        'kid': KEY_ID
    }
    
    try:
        # 生成JWT
        encoded_jwt = jwt.encode(payload, PRIVATE_KEY, algorithm='EdDSA', headers=headers)
        current_api_key = encoded_jwt
        print("已成功生成新的API密钥")
        return encoded_jwt
    except Exception as e:
        print(f"生成API密钥失败: {e}")
        return current_api_key if current_api_key else ""

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "weather_config.yaml")

# 默认配置
default_config = {
    "daily_push": {
        "enabled": True,
        "time": "07:00",
        "groups": [],
        "default_cities": {},  # 格式: {"群号": "城市名"}
        "subscribed_cities": {}  # 格式: {"群号": ["城市1", "城市2", ...]}
    }
}

# 加载配置
def load_config():
    if not os.path.exists(CONFIG_PATH):
        # 确保目录存在
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        # 创建默认配置文件
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True)
        return default_config
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        # 确保配置中包含subscribed_cities字段
        if 'daily_push' in config and 'subscribed_cities' not in config['daily_push']:
            config['daily_push']['subscribed_cities'] = {}
            
        return config
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return default_config

# 保存配置
def save_config(config):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False

# 全局配置变量
config = load_config()

# 天气查询命令
WeatherQuery = on_regex(pattern=r'^天气\s+(.+)$', priority=5)

@WeatherQuery.handle()
async def handle_weather_query(bot: Bot, event: MessageEvent, state: T_State):
    # 提取城市名称
    match = re.search(r'^天气\s+(.+)$', event.get_plaintext())
    if not match:
        await WeatherQuery.finish("请输入正确的格式：天气 城市名")
        return
    
    city_name = match.group(1).strip()
    
    # 查询城市ID
    city_id = await get_city_id(city_name)
    if not city_id:
        await WeatherQuery.finish(f"未找到城市 {city_name} 的信息，请检查城市名称是否正确")
        return
    
    # 查询当前天气
    current_weather = await get_current_weather(city_id)
    if not current_weather:
        await WeatherQuery.finish("获取天气信息失败，请稍后再试")
        return
    
    # 查询未来三天天气
    forecast = await get_weather_forecast(city_id)
    
    # 构建回复消息
    reply_msg = format_weather_reply(city_name, current_weather, forecast)
    
    # 如果是群消息，保存该群的默认城市
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        global config
        if 'default_cities' not in config['daily_push']:
            config['daily_push']['default_cities'] = {}
        config['daily_push']['default_cities'][group_id] = city_name
        save_config(config)
    
    await WeatherQuery.finish(message=reply_msg)

async def get_city_id(city_name: str) -> Optional[str]:
    """查询城市ID"""
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "location": city_name,
                "range": "cn"  # 限定在中国范围内搜索
            }
            headers = {
                "Authorization": f"Bearer {current_api_key}"
            }
            async with session.get(CITY_LOOKUP_API, params=params, headers=headers) as response:
                print(response)
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get("code") != "200" or not data.get("location"):
                    return None
                
                # 返回第一个匹配的城市ID
                return data["location"][0]["id"]
    except Exception as e:
        print(f"获取城市ID失败: {e}")
        return None

async def get_current_weather(city_id: str) -> Optional[Dict]:
    """查询当前天气"""
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "location": city_id
            }
            headers = {
                "Authorization": f"Bearer {current_api_key}"
            }
            async with session.get(WEATHER_NOW_API, params=params, headers=headers) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get("code") != "200":
                    return None
                
                return data.get("now")
    except Exception as e:
        print(f"获取当前天气失败: {e}")
        return None

async def get_weather_forecast(city_id: str) -> Optional[List[Dict]]:
    """查询未来三天天气预报"""
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "location": city_id
            }
            headers = {
                "Authorization": f"Bearer {current_api_key}"
            }
            async with session.get(WEATHER_3D_API, params=params, headers=headers) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get("code") != "200":
                    return None
                
                return data.get("daily")
    except Exception as e:
        print(f"获取天气预报失败: {e}")
        return None

def format_weather_reply(city_name: str, current: Dict, forecast: Optional[List[Dict]]) -> Message:
    """格式化天气回复消息"""
    # 当前天气信息
    current_temp = current.get("temp", "未知")
    current_feel = current.get("feelsLike", "未知")
    current_weather = current.get("text", "未知")
    current_wind_dir = current.get("windDir", "未知")
    current_wind_scale = current.get("windScale", "未知")
    current_humidity = current.get("humidity", "未知")
    
    reply = f"【{city_name}天气信息】\n"
    reply += f"当前天气: {current_weather}\n"
    reply += f"当前温度: {current_temp}°C (体感温度: {current_feel}°C)\n"
    reply += f"风向: {current_wind_dir} {current_wind_scale}级\n"
    reply += f"湿度: {current_humidity}%\n"
    
    # 未来天气预报
    if forecast and len(forecast) > 0:
        reply += "\n【未来天气预报】\n"
        for i, day in enumerate(forecast[:3]):  # 最多显示3天
            date = day.get("fxDate", "未知日期")
            day_weather = day.get("textDay", "未知")
            night_weather = day.get("textNight", "未知")
            temp_min = day.get("tempMin", "未知")
            temp_max = day.get("tempMax", "未知")
            
            day_label = "今天" if i == 0 else "明天" if i == 1 else "后天"
            reply += f"{day_label}({date}): {day_weather}转{night_weather}, {temp_min}°C~{temp_max}°C\n"
    
    # 添加提示信息
    reply += "\n数据来源: 和风天气"
    
    return Message(reply)

# 帮助命令
WeatherHelp = on_regex(pattern=r'^天气帮助$', priority=5)
@WeatherHelp.handle()
async def handle_weather_help(bot: Bot, event: MessageEvent, state: T_State):
    help_msg = (
        "【天气查询使用帮助】\n"
        "1. 查询天气: 发送 '天气 城市名' (例如: 天气 北京)\n"
        "2. 支持全国城市、区县、乡镇等地区的天气查询\n"
        "3. 每天早上7点会自动推送天气信息\n"
        "4. 设置定时推送: 发送 '设置天气推送 开启/关闭'\n"
        "5. 订阅城市: 发送 '订阅城市 城市名'\n"
        "6. 取消订阅: 发送 '取消订阅 城市名'\n"
        "7. 查看订阅: 发送 '查看订阅'\n"
        "8. 数据来源: 和风天气\n"
        "9. 如有问题请联系管理员"
    )
    await WeatherHelp.finish(message=help_msg)

# 设置天气推送命令
WeatherPushSetting = on_regex(pattern=r'^设置天气推送\s+(开启|关闭)$', priority=5)
@WeatherPushSetting.handle()
async def handle_weather_push_setting(bot: Bot, event: MessageEvent, state: T_State):
    if not isinstance(event, GroupMessageEvent):
        await WeatherPushSetting.finish("此命令只能在群聊中使用")
        return
    
    match = re.search(r'^设置天气推送\s+(开启|关闭)$', event.get_plaintext())
    if not match:
        await WeatherPushSetting.finish("请输入正确的格式：设置天气推送 开启/关闭")
        return
    
    action = match.group(1)
    group_id = str(event.group_id)
    
    global config
    if 'groups' not in config['daily_push']:
        config['daily_push']['groups'] = []
    
    if action == "开启":
        if group_id not in config['daily_push']['groups']:
            config['daily_push']['groups'].append(group_id)
            save_config(config)
            await WeatherPushSetting.finish("已开启每日天气推送，每天早上7点将自动推送天气信息")
        else:
            await WeatherPushSetting.finish("本群已开启每日天气推送")
    else:  # 关闭
        if group_id in config['daily_push']['groups']:
            config['daily_push']['groups'].remove(group_id)
            save_config(config)
            await WeatherPushSetting.finish("已关闭每日天气推送")
        else:
            await WeatherPushSetting.finish("本群未开启每日天气推送")

# 设置默认城市命令
SetDefaultCity = on_regex(pattern=r'^设置默认城市\s+(.+)$', priority=5)
@SetDefaultCity.handle()
async def handle_set_default_city(bot: Bot, event: MessageEvent, state: T_State):
    if not isinstance(event, GroupMessageEvent):
        await SetDefaultCity.finish("此命令只能在群聊中使用")
        return
    
    match = re.search(r'^设置默认城市\s+(.+)$', event.get_plaintext())
    if not match:
        await SetDefaultCity.finish("请输入正确的格式：设置默认城市 城市名")
        return
    
    city_name = match.group(1).strip()
    group_id = str(event.group_id)
    
    # 验证城市是否存在
    city_id = await get_city_id(city_name)
    if not city_id:
        await SetDefaultCity.finish(f"未找到城市 {city_name} 的信息，请检查城市名称是否正确")
        return
    
    global config
    if 'default_cities' not in config['daily_push']:
        config['daily_push']['default_cities'] = {}
    
    config['daily_push']['default_cities'][group_id] = city_name
    save_config(config)
    
    await SetDefaultCity.finish(f"已将本群默认城市设置为：{city_name}")

# 订阅城市命令
SubscribeCity = on_regex(pattern=r'^订阅城市\s+(.+)$', priority=5)
@SubscribeCity.handle()
async def handle_subscribe_city(bot: Bot, event: MessageEvent, state: T_State):
    if not isinstance(event, GroupMessageEvent):
        await SubscribeCity.finish("此命令只能在群聊中使用")
        return
    
    match = re.search(r'^订阅城市\s+(.+)$', event.get_plaintext())
    if not match:
        await SubscribeCity.finish("请输入正确的格式：订阅城市 城市名")
        return
    
    city_name = match.group(1).strip()
    group_id = str(event.group_id)
    
    # 验证城市是否存在
    city_id = await get_city_id(city_name)
    if not city_id:
        await SubscribeCity.finish(f"未找到城市 {city_name} 的信息，请检查城市名称是否正确")
        return
    
    global config
    if 'subscribed_cities' not in config['daily_push']:
        config['daily_push']['subscribed_cities'] = {}
    
    if group_id not in config['daily_push']['subscribed_cities']:
        config['daily_push']['subscribed_cities'][group_id] = []
    
    # 检查是否已订阅
    if city_name in config['daily_push']['subscribed_cities'][group_id]:
        await SubscribeCity.finish(f"本群已订阅 {city_name} 的天气信息")
        return
    
    # 添加订阅
    config['daily_push']['subscribed_cities'][group_id].append(city_name)
    save_config(config)
    
    # 确保群已开启推送
    if group_id not in config['daily_push']['groups']:
        config['daily_push']['groups'].append(group_id)
        save_config(config)
    
    await SubscribeCity.finish(f"已订阅 {city_name} 的天气信息，每天早上7点将自动推送")

# 取消订阅命令
UnsubscribeCity = on_regex(pattern=r'^取消订阅\s+(.+)$', priority=5)
@UnsubscribeCity.handle()
async def handle_unsubscribe_city(bot: Bot, event: MessageEvent, state: T_State):
    if not isinstance(event, GroupMessageEvent):
        await UnsubscribeCity.finish("此命令只能在群聊中使用")
        return
    
    match = re.search(r'^取消订阅\s+(.+)$', event.get_plaintext())
    if not match:
        await UnsubscribeCity.finish("请输入正确的格式：取消订阅 城市名")
        return
    
    city_name = match.group(1).strip()
    group_id = str(event.group_id)
    
    global config
    if ('subscribed_cities' not in config['daily_push'] or 
        group_id not in config['daily_push']['subscribed_cities'] or
        city_name not in config['daily_push']['subscribed_cities'][group_id]):
        await UnsubscribeCity.finish(f"本群未订阅 {city_name} 的天气信息")
        return
    
    # 移除订阅
    config['daily_push']['subscribed_cities'][group_id].remove(city_name)
    save_config(config)
    
    await UnsubscribeCity.finish(f"已取消订阅 {city_name} 的天气信息")

# 查看订阅命令
ViewSubscriptions = on_regex(pattern=r'^查看订阅$', priority=5)
@ViewSubscriptions.handle()
async def handle_view_subscriptions(bot: Bot, event: MessageEvent, state: T_State):
    if not isinstance(event, GroupMessageEvent):
        await ViewSubscriptions.finish("此命令只能在群聊中使用")
        return
    
    group_id = str(event.group_id)
    
    global config
    if ('subscribed_cities' not in config['daily_push'] or 
        group_id not in config['daily_push']['subscribed_cities'] or
        not config['daily_push']['subscribed_cities'][group_id]):
        
        # 检查是否有默认城市
        default_city = config['daily_push'].get('default_cities', {}).get(group_id)
        if default_city:
            await ViewSubscriptions.finish(f"本群当前默认城市为：{default_city}\n未订阅其他城市的天气信息")
        else:
            await ViewSubscriptions.finish("本群未订阅任何城市的天气信息")
        return
    
    # 构建订阅列表
    subscribed_cities = config['daily_push']['subscribed_cities'][group_id]
    default_city = config['daily_push'].get('default_cities', {}).get(group_id, "")
    
    reply = "【本群订阅的城市】\n"
    for i, city in enumerate(subscribed_cities, 1):
        is_default = " (默认城市)" if city == default_city else ""
        reply += f"{i}. {city}{is_default}\n"
    
    if default_city and default_city not in subscribed_cities:
        reply += f"\n默认城市: {default_city}"
    
    push_status = "已开启" if group_id in config['daily_push'].get('groups', []) else "未开启"
    reply += f"\n\n推送状态: {push_status}"
    
    await ViewSubscriptions.finish(reply)

# 定时刷新API密钥（每12小时）
@scheduler.scheduled_job("interval", hours=12)
async def refresh_api_key():
    generate_api_key()
    print("已定时刷新API密钥")

# 定时推送天气信息
@scheduler.scheduled_job("cron", hour=7, minute=0)
async def daily_weather_push():
    global config
    if not config['daily_push']['enabled']:
        return
    
    bot = get_driver().bots.get(list(get_driver().bots)[0])
    if not bot:
        print("未找到可用的Bot实例")
        return
    
    for group_id in config['daily_push']['groups']:
        # 获取该群订阅的城市列表
        subscribed_cities = config['daily_push'].get('subscribed_cities', {}).get(group_id, [])
        
        # 如果没有订阅城市，使用默认城市
        if not subscribed_cities:
            default_city = config['daily_push'].get('default_cities', {}).get(group_id)
            if default_city:
                subscribed_cities = [default_city]
            else:
                continue
        
        # 为每个订阅的城市推送天气
        for city_name in subscribed_cities:
            # 查询城市ID
            city_id = await get_city_id(city_name)
            if not city_id:
                continue
            
            # 查询当前天气
            current_weather = await get_current_weather(city_id)
            if not current_weather:
                continue
            
            # 查询未来三天天气
            forecast = await get_weather_forecast(city_id)
            
            # 构建推送消息
            push_msg = f"【每日天气推送】\n今天是{forecast[0]['fxDate'] if forecast else '今天'}，为您带来{city_name}的天气信息：\n\n"
            push_msg += format_weather_reply(city_name, current_weather, forecast).extract_plain_text()
            
            try:
                await bot.send_group_msg(group_id=int(group_id), message=push_msg)
                print(f"已向群 {group_id} 推送 {city_name} 的天气信息")
            except Exception as e:
                print(f"向群 {group_id} 推送 {city_name} 的天气信息失败: {e}")

# 初始化
driver = get_driver()
@driver.on_startup
async def init_weather():
    global config
    config = load_config()
    # 初始化生成API密钥
    generate_api_key()
    print("天气助手插件已加载")