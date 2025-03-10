'''
Date: 2025-02-18 13:28:30
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 09:11:57
FilePath: /bott/bot-dd/src/config.py
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