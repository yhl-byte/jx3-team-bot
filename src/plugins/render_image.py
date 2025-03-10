'''
Date: 2025-02-18 13:33:56
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-05 14:25:53
FilePath: /bott/bot-dd/src/plugins/render_image.py
'''
# src/plugins/chat_plugin/render_image.py
import os
from tempfile import NamedTemporaryFile
from src.config import STATIC_PATH
import imgkit

def html_to_image(html_content: str) -> str:
    # 临时文件保存图片
    with NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        output_path = tmp_file.name
    
    # 配置选项（解决中文乱码）
    options = {
        "encoding": "UTF-8",
        "enable-local-file-access": None,  # 允许加载本地 CSS
        "no-stop-slow-scripts": "",
        "javascript-delay": 1000
    }
    
    # 生成图片
    imgkit.from_string(
        html_content,
        output_path,
        options=options,
        # css=str(STATIC_PATH / "styles.css")
    )
    return output_path