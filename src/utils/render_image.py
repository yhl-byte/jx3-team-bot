# '''
# Date: 2025-02-18 13:33:56
# LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
# LastEditTime: 2025-06-18 15:52:02
# FilePath: /team-bot/jx3-team-bot/src/plugins/render_image.py
# '''
from src.utils.browser_pool import browser_pool
import os
import asyncio
from tempfile import NamedTemporaryFile

async def generate_html_screenshot(html_content: str, width: int = 800) -> str:
    """优化后的截图生成函数"""
    context = await browser_pool.get_context()
    page = await context.new_page()
    try:
        # 设置超时时间
        page.set_default_timeout(30000)  # 恢复到30秒
        # 监听控制台输出（用于调试）
        page.on("console", lambda msg: print(f"Console message: {msg.type}: {msg.text}"))
        # 允许访问本地文件
        await page.route("**/*", lambda route: route.continue_())
        # 设置内容并等待网络空闲
        await page.set_content(html_content, wait_until='networkidle')
        # 等待页面渲染完成
        await page.wait_for_timeout(1000)
        
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
        
        # 获取页面实际内容高度（使用旧版本的稳定方法）
        page_height = await page.evaluate('''
            () => {
                const body = document.body;
                const html = document.documentElement;
                
                return Math.max(
                    body.scrollHeight,
                    body.offsetHeight,
                    html.clientHeight,
                    html.scrollHeight,
                    html.offsetHeight
                );
            }
        ''')
        
        print(f"页面高度: {page_height}")
        
        # 设置视口大小
        await page.set_viewport_size({"width": width, "height": page_height})
        
        # 手动创建临时文件
        tmp_file = NamedTemporaryFile(suffix='.png', delete=False)
        image_path = tmp_file.name
        tmp_file.close()  # 关闭文件句柄，但文件保留
        
        print(f"开始截图，保存到: {image_path}")
        
        # 截图
        await page.screenshot(path=image_path, full_page=True)
        
        print(f"截图完成: {image_path}")
        return image_path
        
    except Exception as e:
        print(f"截图过程中出现错误: {e}")
        raise
    finally:
        await page.close()



# from playwright.async_api import async_playwright
# import os
# from tempfile import NamedTemporaryFile
# from src.config import STATIC_PATH

# async def generate_html_screenshot(html_content: str, width: int = 800,) -> str:
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(args=['--allow-file-access-from-files', '--disable-web-security'])
#         context = await browser.new_context(bypass_csp=True)
#         page = await context.new_page()

#         # 监听控制台输出
#         page.on("console", lambda msg: print(f"Console message: {msg.type}: {msg.text}"))

#         # 设置更长的超时时间
#         page.set_default_timeout(30000)

#         # 允许访问本地文件
#         await page.route("**/*", lambda route: route.continue_())

#         await page.set_content(html_content, wait_until='networkidle')

#         # 等待页面渲染完成
#         await page.wait_for_timeout(1000)

#         # 等待所有图片加载完成
#         # await page.wait_for_selector('img', state='attached')

#         # 等待所有图片完全加载
#         await page.evaluate('''() => {
#             return Promise.all(Array.from(document.images).map(img => {
#                 if (img.complete) return Promise.resolve();
#                 return new Promise((resolve, reject) => {
#                     img.addEventListener('load', resolve);
#                     img.addEventListener('error', () => {
#                         console.error('Image failed to load:', img.src);
#                         resolve();
#                     });
#                 });
#             }));
#         }''')

#         # 设置视口大小
#         # await page.set_viewport_size({"width": width, "height": 800})
        
#         # 获取页面实际高度
#         # page_height = await page.evaluate('document.documentElement.scrollHeight')
#         # 获取页面实际内容高度（更准确的方法）
#         page_height = await page.evaluate('''
#             () => {
#                 // 获取body的实际高度
#                 const body = document.body;
#                 const html = document.documentElement;
                
#                 // 取最小的有效高度
#                 return Math.min(
#                     body.scrollHeight,
#                     body.offsetHeight,
#                     html.clientHeight,
#                     html.scrollHeight,
#                     html.offsetHeight
#                 );
#             }
#         ''')

#         # 调整视口高度为实际高度
#         await page.set_viewport_size({"width": width, "height": page_height})

#         # 保存为临时文件
#         image_path = os.path.join(os.path.dirname(__file__), 'temp.png')
#         await page.screenshot(path=image_path, full_page=True)
#         await browser.close()
#         return image_path

