'''
Date: 2025-02-18 13:33:56
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-11 16:15:54
FilePath: /team-bot/jx3-team-bot/src/plugins/render_image.py
'''
from playwright.async_api import async_playwright
import os
from tempfile import NamedTemporaryFile
from src.config import STATIC_PATH

async def generate_html_screenshot(html_content: str, width: int = 800,) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--allow-file-access-from-files', '--disable-web-security'])
        context = await browser.new_context(bypass_csp=True)
        page = await context.new_page()

        # 监听控制台输出
        page.on("console", lambda msg: print(f"Console message: {msg.type}: {msg.text}"))

        # 设置更长的超时时间
        page.set_default_timeout(30000)

        # 允许访问本地文件
        await page.route("**/*", lambda route: route.continue_())

        await page.set_content(html_content, wait_until='networkidle')

        # 等待页面渲染完成
        await page.wait_for_timeout(1000)

        # 等待所有图片加载完成
        # await page.wait_for_selector('img', state='attached')

        # 等待所有图片完全加载
        await page.evaluate('''() => {
            return Promise.all(Array.from(document.images).map(img => {
                if (img.complete) return Promise.resolve();
                return new Promise((resolve, reject) => {
                    img.addEventListener('load', resolve);
                    img.addEventListener('error', () => {
                        console.error('Image failed to load:', img.src);
                        resolve();
                    });
                });
            }));
        }''')

        # 设置视口大小
        # await page.set_viewport_size({"width": width, "height": 800})
        
        # 获取页面实际高度
        page_height = await page.evaluate('document.documentElement.scrollHeight')

        # 调整视口高度为实际高度
        await page.set_viewport_size({"width": width, "height": page_height})

        # 保存为临时文件
        image_path = os.path.join(os.path.dirname(__file__), 'temp.png')
        await page.screenshot(path=image_path, full_page=True)
        await browser.close()
        return image_path

