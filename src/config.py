'''
Date: 2025-02-18 13:28:30
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-19 16:09:45
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
DATABASE_PATH = BASE_DIR / "data" / "team_record.db"

# HTML 模板路径
TEMPLATE_PATH = BASE_DIR / "templates" / "team.html"

# 静态资源路径
STATIC_PATH = BASE_DIR / "static"

# # 和风天气 API 密钥
# QWEATHER_API_KEY = 'eyJhbGciOiJFZERTQSIsImtpZCI6IlRIUE40QzlSTVkifQ.eyJzdWIiOiI0Rjg3S1EzUDNVIiwiaWF0IjoxNzQ4MjI0MTc4LCJleHAiOjIwNjM1ODQxNzh9.f_m_jMozW8RDECOO34lUrtDrov2A5JSH4sDSPkMTjh3ka7FhagBe101QzJ7JeyXIYrobzuktreuNkXjWT8hICw'

# # DeepSeek API 配置
# DEEPSEEK_API_KEY = 'sk-354771830e3145509014461cf8427e66'  # 请替换为你的DeepSeek API密钥
# DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

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