'''
Date: 2025-02-18 13:28:30
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-20 17:05:08
FilePath: /team-bot/jx3-team-bot/src/config.py
'''
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量 - 这行很重要！
load_dotenv()

# 基础路径
BASE_DIR = Path(__file__).parent.parent / "src"

# 数据库路径
DATABASE_PATH = Path(__file__).parent.parent / "data" / "nianzai.db"

# HTML 模板路径
TEMPLATE_PATH = BASE_DIR / "templates"

# 静态资源路径
STATIC_PATH = BASE_DIR / "static"

# JX3 API 配置
JX3_AUTHORIZATION = os.getenv('JX3_AUTHORIZATION')
JX3_COOKIES = os.getenv('JX3_COOKIES')
JX3_TOKEN = os.getenv('JX3_TOKEN')
JX3_TICKET = os.getenv('JX3_TICKET')

# 和风天气 API 配置
QWEATHER_API_KEY = os.getenv('QWEATHER_API_KEY')
QWEATHER_PRIVATE_KEY = os.getenv('QWEATHER_PRIVATE_KEY')
QWEATHER_PROJECT_ID = os.getenv('QWEATHER_PROJECT_ID')
QWEATHER_KEY_ID = os.getenv('QWEATHER_KEY_ID')
QWEATHER_CITY_LOOKUP_API = os.getenv('QWEATHER_CITY_LOOKUP_API', 'https://mv6hewd2ar.re.qweatherapi.com/geo/v2/city/lookup')
QWEATHER_NOW_API = os.getenv('QWEATHER_NOW_API', 'https://mv6hewd2ar.re.qweatherapi.com/v7/weather/now')
QWEATHER_3D_API = os.getenv('QWEATHER_3D_API', 'https://mv6hewd2ar.re.qweatherapi.com/v7/weather/3d')

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = os.getenv('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')