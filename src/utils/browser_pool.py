import asyncio
import logging
from typing import Optional
import atexit
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BrowserPool:
    _instance: Optional['BrowserPool'] = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _playwright: Optional[Playwright] = None
    _lock: asyncio.Lock = asyncio.Lock()  # 类级别初始化锁
    _initializing: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = asyncio.Lock()  # 确保锁只初始化一次
            cls._instance._initializing = False
        return cls._instance

    async def get_browser(self) -> Browser:
        logger.info("进入 get_browser 方法")
        logger.info(f"_browser 是否为 None: {self._browser is None}")
        logger.info(f"_initializing: {self._initializing}")

        # 如果浏览器已经存在，直接返回
        if self._browser is not None:
            logger.info("浏览器已存在，直接返回")
            return self._browser

        # 如果正在初始化，等待初始化完成
        if self._initializing:
            logger.info("正在初始化中，等待...")
            while self._initializing and self._browser is None:
                await asyncio.sleep(0.1)
            if self._browser is not None:
                return self._browser

        # 尝试获取锁
        lock_acquired = False
        try:
            logger.info("尝试获取锁")
            await asyncio.wait_for(self._lock.acquire(), timeout=10.0)  # 增加超时时间到 60 秒
            lock_acquired = True
            logger.info("成功获取锁")
        except asyncio.TimeoutError:
            logger.error("获取锁超时，可能存在死锁")
            raise Exception("获取锁超时，请重试")

        try:
            # 双重检查
            if self._browser is None:
                logger.info("开始初始化浏览器")
                self._initializing = True
                try:
                    # 保存 playwright 实例的引用
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(
                        args=['--allow-file-access-from-files', '--disable-web-security'],
                        headless=True
                    )
                    atexit.register(self._cleanup_sync)
                    logger.info("浏览器初始化完成")
                except Exception as e:
                    logger.error(f"启动浏览器失败: {e}")
                    self._browser = None
                    raise
                finally:
                    self._initializing = False
        finally:
            # 释放锁
            if lock_acquired and self._lock.locked():
                self._lock.release()
                logger.info("锁已释放")

        return self._browser

    async def get_context(self) -> BrowserContext:
        # 首先确保浏览器已经初始化
        browser = await self.get_browser()

        # 然后在锁的保护下创建上下文
        if self._context is None:
            lock_acquired = False
            try:
                await asyncio.wait_for(self._lock.acquire(), timeout=10.0)
                lock_acquired = True
                
                # 双重检查，防止在等待锁的过程中，其他协程已经创建了上下文
                if self._context is None:
                    self._context = await browser.new_context(bypass_csp=True)
                    
            except asyncio.TimeoutError:
                print("获取上下文锁超时")
                # 超时后重置锁可能不是最佳策略，但这里保留以防万一
                self._lock = asyncio.Lock()
                raise Exception("获取浏览器上下文超时，请重试")
            finally:
                if lock_acquired:
                    self._lock.release()
                    
        return self._context

    def _cleanup_sync(self):
        """同步清理函数，用于 atexit"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.close())
        except Exception as e:
            logger.error(f"同步清理失败: {e}")

    async def close(self):
        """异步清理函数"""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.error(f"清理浏览器资源时出错: {e}")
            raise

# 全局实例
browser_pool = BrowserPool()