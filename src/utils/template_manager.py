from jinja2 import Environment, FileSystemLoader
from src.config import TEMPLATE_PATH, STATIC_PATH
from typing import Dict, Any
import os

class TemplateManager:
    _instance = None
    _env = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._env is None:
            template_dir = TEMPLATE_PATH.parent
            if not os.path.exists(template_dir):
                os.makedirs(template_dir)
            
            self._env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=True,
                extensions=['jinja2.ext.do'],
                cache_size=100,  # 启用模板缓存
                auto_reload=False  # 生产环境关闭自动重载
            )
    
    def render_template(self, template_name: str, **kwargs) -> str:
        """渲染模板的统一接口"""
        template = self._env.get_template(template_name)
        return template.render(
            static_path=STATIC_PATH.absolute(),
            **kwargs
        )

# 全局实例
template_manager = TemplateManager()