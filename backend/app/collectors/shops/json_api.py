"""公开 JSON 接口类的店铺系统。"""

import json
import re
from typing import Any, ClassVar
from urllib.parse import quote, urlsplit

from app.collectors.registry import register
from app.collectors.shops.base import ShopCollector, ShopFetchError, ShopItem, ShopTarget, make_item
from app.collectors.shops.parse import absolutize, clean_text, compact, integer, localized, number

_MAX_PAGES = 10
_PAGE_SIZE = 100


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _keep(items: list[ShopItem | None]) -> list[ShopItem]:
    return [i for i in items if i is not None]


@register
class KamiCollector(ShopCollector):
    kind: ClassVar[str] = "kami"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        out: list[ShopItem | None] = []
        for page in range(1, _MAX_PAGES + 1):
            if page > 1:
                await self.pause()
            payload = await self.get_json(
                f"{target.base_url}/user/api/index/commodity?limit={_PAGE_SIZE}&page={page}"
            )
            items = _list(payload.get("data") if isinstance(payload, dict) else None)
            out += [self._item(target, i) for i in items]
            if len(items) < _PAGE_SIZE:
                break
        return _keep(out)

    @staticmethod
    def _item(target: ShopTarget, item: dict[str, Any]) -> ShopItem | None:
        stock_text = clean_text(item.get("stock"))
        stock = integer(item.get("stock"))
        if stock is None and re.search(r"已售罄|^售罄$|缺货|无货", stock_text):
            stock = 0
        hidden = integer(item.get("hide")) not in (None, 0)
        disabled = integer(item.get("status") if item.get("status") is not None else 1) != 1
        return make_item(
            title=item.get("name"),
            price=number(
                item.get("user_price") if item.get("user_price") is not None else item.get("price")
            ),
            url=f"{target.base_url}/item/{quote(str(item.get('id')))}",
            stock=stock,
            disabled=disabled or hidden,
            tags=compact(
                [
                    (item.get("category") or {}).get("name"),
                    "自动发货" if item.get("delivery_way") == 0 else None,
                ]
            ),
        )


@register
class DujiaoCollector(ShopCollector):
    """独角数卡（新版接口）：一个商品可能有多个规格，每个规格一条报价。"""

    kind: ClassVar[str] = "dujiao"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        payload = await self.get_json(f"{target.base_url}/api/v1/public/products")
        out: list[ShopItem | None] = []
        for product in _list(payload.get("data") if isinstance(payload, dict) else None):
            out += self._items(target, product)
        return _keep(out)

    @staticmethod
    def _items(target: ShopTarget, product: dict[str, Any]) -> list[ShopItem | None]:
        product_title = localized(product.get("title")) or clean_text(product.get("slug"))
        skus: list[Any] = _list(product.get("skus")) or [None]
        url = f"{target.base_url}/products/{quote(str(product.get('slug') or product.get('id')))}"
        fulfillment = product.get("fulfillment_type")
        tags = compact(
            [
                localized((product.get("category") or {}).get("name")),
                "自动发货" if fulfillment == "auto" else None,
                "人工处理" if fulfillment == "manual" else None,
            ]
        )
        out: list[ShopItem | None] = []
        for index, sku in enumerate(skus, start=1):
            s = sku or {}
            sku_title = localized(
                s.get("title") or s.get("name") or s.get("label") or s.get("spec")
            )
            if sku_title and sku_title != product_title:
                title = f"{product_title} / {sku_title}"
            elif len(skus) > 1 and sku:
                title = f"{product_title} / 规格{index}"
            else:
                title = product_title
            stock = integer(
                next(
                    (
                        v
                        for v in (
                            s.get("auto_stock_available"),
                            s.get("manual_stock_available"),
                            product.get("auto_stock_available"),
                            product.get("manual_stock_available"),
                        )
                        if v is not None
                    ),
                    None,
                )
            )
            sold_out = bool(s.get("is_sold_out", product.get("is_sold_out")))
            stock_status = str(s.get("stock_status") or product.get("stock_status") or "")
            price = (
                s.get("price_amount")
                if s.get("price_amount") is not None
                else product.get("price_amount")
            )
            out.append(
                make_item(
                    title=title,
                    price=number(price),
                    url=url,
                    stock=stock,
                    disabled=sold_out or stock_status == "out_of_stock",
                    tags=tags,
                )
            )
        return out


@register
class XiaoheiwanCollector(ShopCollector):
    kind: ClassVar[str] = "xiaoheiwan"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        products = _list(await self.get_json(f"{target.base_url}/api/products"))
        return _keep(
            [
                make_item(
                    title=p.get("name"),
                    price=number(
                        p.get("price") if p.get("price") is not None else p.get("original_price")
                    ),
                    url=f"{target.base_url}/purchase",
                    stock=integer(p.get("stock", p.get("stock_count", p.get("count")))),
                    disabled=str(p.get("status") or "").lower() != "active",
                    tags=compact([p.get("sku")]),
                )
                for p in products
            ]
        )


@register
class IkunloveApiCollector(ShopCollector):
    kind: ClassVar[str] = "ikunloveApi"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        payload = await self.get_json(f"{target.base_url}/api/shop/products")
        data = payload.get("data") if isinstance(payload, dict) else None
        out: list[ShopItem | None] = []
        for p in _list((data or {}).get("products")):
            cents = number(p.get("priceCents"))
            detail = p.get("purchaseGuideUrl") or p.get("consolePath") or p.get("tutorialPath")
            out.append(
                make_item(
                    title=p.get("title"),
                    price=None if cents is None else cents / 100,
                    url=absolutize(detail or target.entry_url, target.base_url),
                    stock=integer(p.get("stockCount")),
                    disabled=p.get("isDeleted") is True or p.get("isActive") is False,
                    tags=compact([p.get("category"), p.get("badge")]),
                )
            )
        return _keep(out)


@register
class GetgptApiCollector(ShopCollector):
    """固定几款充值服务，价格来自店铺前端调用的价格接口。"""

    kind: ClassVar[str] = "getgptApi"
    PRICE_API: ClassVar[str] = "https://gpt.how2cs.cn/api/order/prices"
    PRODUCTS: ClassVar[list[tuple[str, str, str]]] = [
        ("ChatGPT Plus 充值", "gptplus_amount", "/plus-price"),
        ("ChatGPT Pro 充值", "gptpro_amount", "/gptpro"),
        ("ChatGPT Pro Lite 充值", "gptprolite_amount", "/gptpro"),
        ("ChatGPT Team / Business 充值", "team_amount", "/price"),
        ("Claude 充值", "claude_amount", "/"),
    ]

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        payload = await self.get_json(self.PRICE_API)
        if not isinstance(payload, dict):
            raise ShopFetchError("价格接口结构变化")
        out: list[ShopItem | None] = []
        for title, key, path in self.PRODUCTS:
            value = payload.get(key)
            if key == "gptplus_amount" and value is None:
                value = payload.get("amount")
            out.append(
                make_item(title=title, price=number(value), url=absolutize(path, target.base_url))
            )
        return _keep(out)


@register
class PublicProductsApiCollector(ShopCollector):
    kind: ClassVar[str] = "publicProductsApi"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        payload = await self.get_json(f"{target.base_url}/api/products")
        if isinstance(payload, list):
            products = payload
        elif isinstance(payload, dict):
            products = _list(payload.get("products")) or _list(
                (payload.get("data") or {}).get("products")
            )
        else:
            products = []
        return _keep([self._item(target, p) for p in products if isinstance(p, dict)])

    @staticmethod
    def _item(target: ShopTarget, p: dict[str, Any]) -> ShopItem | None:
        def first(*keys: str) -> Any:
            return next((p[k] for k in keys if p.get(k) is not None), None)

        hidden = (
            p.get("is_hidden") is True or p.get("hidden") is True or p.get("isVisible") is False
        )
        raw_tags = [
            t if isinstance(t, str) else (t or {}).get("text") or (t or {}).get("name")
            for t in _list(p.get("tags"))
        ]
        pid = p.get("id") or p.get("slug") or p.get("key")
        if not pid:
            url = target.entry_url
        elif (urlsplit(target.base_url).hostname or "").removeprefix("www.") == "catcard.uk":
            url = f"{target.base_url}/#product-{quote(str(pid))}"
        else:
            url = f"{target.base_url}/#{quote(str(pid))}"
        return make_item(
            title=first("display_name", "displayName", "name", "productName", "title"),
            price=number(first("price_cny", "priceCny", "price", "amount")),
            url=url,
            stock=integer(first("stock", "stock_count", "stockCount")),
            disabled=hidden or integer(first("status")) == 0,
            tags=compact(
                [
                    first("project_title", "projectTitle", "project"),
                    first("group_name", "groupName"),
                    first("delivery_label", "deliveryLabel"),
                    first("product_type", "productType"),
                    *raw_tags,
                ]
            ),
        )


@register
class ShopUserProductsApiCollector(ShopCollector):
    kind: ClassVar[str] = "shopUserProductsApi"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        out: list[ShopItem | None] = []
        for page in range(1, _MAX_PAGES + 1):
            if page > 1:
                await self.pause()
            payload = await self.get_json(
                f"{target.base_url}/shop/user/products?page={page}&size={_PAGE_SIZE}&productName="
            )
            data = payload.get("data") if isinstance(payload, dict) else None
            records = _list((data or {}).get("records"))
            for p in records:
                visible = integer(p.get("isVisible") if p.get("isVisible") is not None else 1)
                status = integer(p.get("status") if p.get("status") is not None else 1)
                out.append(
                    make_item(
                        title=p.get("productName") or p.get("name") or p.get("title"),
                        price=number(
                            p.get("price") if p.get("price") is not None else p.get("salePrice")
                        ),
                        url=f"{target.base_url}/product/{quote(str(p.get('id')))}",
                        stock=integer(p.get("stock")),
                        disabled=visible != 1 or status != 1,
                        tags=compact(
                            [
                                p.get("category"),
                                p.get("cardType"),
                                "热门" if p.get("isHot") else None,
                            ]
                        ),
                    )
                )
            if len(records) < _PAGE_SIZE:
                break
        return _keep(out)


@register
class MooncakeCatalogCollector(ShopCollector):
    """商品目录写在一个 JS 文件里：window.MOONCAKE_CATALOG = [...]。"""

    kind: ClassVar[str] = "mooncakeCatalog"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        js = await self.get_text(f"{target.base_url}/mooncake-official-media/catalog.js")
        m = re.search(r"window\.MOONCAKE_CATALOG\s*=\s*([\s\S]*?);\s*(?:window\.|$)", js)
        if not m:
            raise ShopFetchError("商品目录数据不存在")
        try:
            categories = json.loads(m.group(1))
        except ValueError:
            raise ShopFetchError("商品目录 JSON 解析失败") from None
        out: list[ShopItem | None] = []
        for category in _list(categories):
            name = clean_text(category.get("name"))
            for item in _list(category.get("items")):
                out.append(
                    make_item(
                        title=item.get("name"),
                        price=number(item.get("price")),
                        url=f"{target.base_url}/#item-{quote(str(item.get('id')))}",
                        stock=integer(item.get("stock")),
                        tags=compact([name, "自动发货" if item.get("delivery_way") == 0 else None]),
                    )
                )
        return _keep(out)
