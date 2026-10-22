"""采集器插件。新增采集器后在这里导入一次，模块里的 @register 才会生效。"""

from app.collectors import openrouter

__all__ = ["openrouter"]
