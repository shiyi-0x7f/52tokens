"""卡网采集器：每种店铺系统一个插件，kind 与 ShopCollectorKind 一一对应。"""

from app.collectors.shops import html_pages, json_api, shop_api

__all__ = ["html_pages", "json_api", "shop_api"]
