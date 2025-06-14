'''
Date: 2025-02-18 13:28:30
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-05-26 09:50:51
FilePath: /team-bot/jx3-team-bot/src/config.py
'''
import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).parent.parent / "src"

# 数据库路径
DATABASE_PATH = BASE_DIR / "data" / "team_record.db"

# HTML 模板路径
TEMPLATE_PATH = BASE_DIR / "templates" / "team.html"

# 静态资源路径
STATIC_PATH = BASE_DIR / "static"

# 和风天气 API 密钥
QWEATHER_API_KEY = 'eyJhbGciOiJFZERTQSIsImtpZCI6IlRIUE40QzlSTVkifQ.eyJzdWIiOiI0Rjg3S1EzUDNVIiwiaWF0IjoxNzQ4MjI0MTc4LCJleHAiOjIwNjM1ODQxNzh9.f_m_jMozW8RDECOO34lUrtDrov2A5JSH4sDSPkMTjh3ka7FhagBe101QzJ7JeyXIYrobzuktreuNkXjWT8hICw'