'''
Date: 2025-06-20 09:00:25
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-20 13:36:13
FilePath: /team-bot/jx3-team-bot/src/utils/render_context.py
'''
import asyncio
from contextlib import asynccontextmanager
from src.utils.browser_pool import browser_pool
from src.utils.render_image import generate_html_screenshot
import os

@asynccontextmanager
async def render_context():
    """渲染上下文管理器，自动清理资源"""
    temp_files = []
    try:
        yield temp_files
    finally:
        # 清理临时文件
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass

async def render_and_cleanup(html_content: str, width: int = 800) -> str:
    """渲染并返回图片路径，不再自动清理"""
    print("开始渲染...")
    try:
        print("调用 generate_html_screenshot...")
        image_path = await generate_html_screenshot(html_content, width)
        print(f"生成图片路径: {image_path}")
        return image_path
    except Exception as e:
        print(f"渲染过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        raise