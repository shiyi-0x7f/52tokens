"""ShopApi 多商户平台（链动小铺 wzyp.cn 等）：同一域名下有很多商户，店铺地址必须是具体商户的
/shop/<token>；只有商品链接 /item/<goods_key> 时，可用 resolve_item_shop 反查所属店铺。

价格取平台结算接口给出的实付金额（含支付手续费），拿不到时退回标价。
注意：wzyp.cn 前面有阿里云 WAF，机房 / 代理 IP 发出的请求会被要求滑块验证（返回验证页，
这里按失败处理、不尝试绕过）；家宽等普通出口 IP 可以正常访问公开接口。
"""

import re
from typing import Any, ClassVar
from urllib.parse import unquote, urlsplit

import httpx
from loguru import logger

from app.collectors.registry import register
from app.collectors.shops.base import (
    ShopCollector,
    ShopFetchError,
    ShopItem,
    ShopTarget,
    base_url_of,
    make_item,
)
from app.collectors.shops.parse import clean_text, compact, integer, number

_MAX_PAGES = 10
_PAGE_SIZE = 100
_SHOP_TOKEN = re.compile(r"/shop/([^/?#]+)")
_ITEM_KEY = re.compile(r"/item/([^/?#]+)")


def shop_token(url: str) -> str | None:
    m = _SHOP_TOKEN.search(urlsplit(url).path)
    return unquote(m.group(1)) if m else None


def item_key(url: str) -> str | None:
    m = _ITEM_KEY.search(urlsplit(url).path)
    return unquote(m.group(1)) if m else None


async def resolve_item_shop(client: httpx.AsyncClient, url: str) -> str:
    """商品链接 → 所属商户的店铺地址（公开商品详情接口里的 user.token）。"""
    key = item_key(url)
    if not key:
        raise ShopFetchError("不是商品链接（/item/<goods_key>）")
    base = base_url_of(url)
    detail = await ShopApiCollector(client).post_json(
        f"{base}/shopApi/Shop/goodsInfo", {"goods_key": key, "trade_no": ""}, url
    )
    if not _ok(detail):
        message = detail.get("msg") if isinstance(detail, dict) else None
        raise ShopFetchError(f"商品详情不可用：{clean_text(message) or '未知原因'}")
    token = ((detail.get("data") or {}).get("user") or {}).get("token")
    if not token:
        raise ShopFetchError("商品详情里没有店铺信息")
    return f"{base}/shop/{token}"


def _ok(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("code") == 1


@register
class ShopApiCollector(ShopCollector):
    kind: ClassVar[str] = "shopApi"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        token = shop_token(target.entry_url)
        if not token:
            raise ShopFetchError("多商户平台需要具体商户的店铺地址（/shop/<token>），请在后台补充")
        base = target.base_url
        shop_url = f"{base}/shop/{token}"

        info = await self.post_json(
            f"{base}/shopApi/Shop/info", {"token": token, "category_key": ""}, shop_url
        )
        if not _ok(info) or not info.get("data"):
            raise ShopFetchError("店铺信息不可用（店铺不存在或已关闭）")
        if integer(info["data"].get("custom_status")) == 0:
            raise ShopFetchError(f"店铺已打烊：{clean_text(info['data'].get('custom_status_msg'))}")

        channel_id = await self._channel_id(base, token, shop_url)
        categories = await self.post_json(
            f"{base}/shopApi/Shop/categoryList",
            {"token": token, "goods_type": "card", "category_key": ""},
            shop_url,
        )
        rows = categories.get("data") if _ok(categories) else []
        rows = rows if isinstance(rows, list) else []
        ids = [
            int(c["id"])
            for c in rows
            if (integer(c.get("goods_count")) or 0) > 0 and integer(c.get("id"))
        ]
        if not ids and any(integer(c.get("id")) == 0 for c in rows):
            ids = [0]

        out: list[ShopItem] = []
        for category_id in ids:
            for page in range(1, _MAX_PAGES + 1):
                await self.pause()
                listing = await self.post_json(
                    f"{base}/shopApi/Shop/goodsList",
                    {
                        "token": token,
                        "keywords": "",
                        "category_id": category_id,
                        "goods_type": "card",
                        "current": page,
                        "pageSize": _PAGE_SIZE,
                    },
                    shop_url,
                )
                goods = (listing.get("data") or {}).get("list") if _ok(listing) else None
                if not isinstance(goods, list) or not goods:
                    break
                for g in goods:
                    if item := await self._item(base, shop_url, g, channel_id):
                        out.append(item)
                if len(goods) < _PAGE_SIZE:
                    break
        return out

    async def _channel_id(self, base: str, token: str, referer: str) -> int:
        """结算价随支付渠道不同：优先支付宝，否则第一个可用渠道。"""
        payload = await self.post_json(
            f"{base}/shopApi/Shop/getUserChannel", {"token": token}, referer
        )
        channels = payload.get("data") if isinstance(payload, dict) else None
        channels = channels if isinstance(channels, list) else []
        active = [
            c
            for c in channels
            if integer(c.get("status") if c.get("status") is not None else 1) == 1
            and integer(c.get("custom_status") if c.get("custom_status") is not None else 1) == 1
        ] or channels
        keys = ("name", "title", "channel_name", "pay_name", "code", "type")
        preferred = next(
            (
                c
                for c in active
                if re.search("支付宝|alipay", " ".join(str(c.get(k) or "") for k in keys), re.I)
            ),
            active[0] if active else None,
        )
        return integer((preferred or {}).get("id")) or 0

    async def _item(
        self, base: str, shop_url: str, g: dict[str, Any], channel_id: int
    ) -> ShopItem | None:
        listed = number(g.get("price") if g.get("price") is not None else g.get("real_price"))
        goods_key = g.get("goods_key")
        url = g.get("link") or (f"{base}/item/{goods_key}" if goods_key else shop_url)
        price = listed
        if goods_key and listed is not None:
            await self.pause()
            try:
                quote = await self.post_json(
                    f"{base}/shopApi/Shop/getGoodsPrice",
                    {
                        "goods_key": goods_key,
                        "quantity": 1,
                        "coupon_code": "",
                        "channel_id": channel_id,
                    },
                    url,
                )
            except (httpx.HTTPError, ShopFetchError) as exc:
                # 单个商品的结算价查询失败（如 520）不连累整家店铺：退回标价
                logger.debug("结算价查询失败，用标价 {} {}", url, exc)
                quote = None
            total = number((quote.get("data") or {}).get("total_amount")) if _ok(quote) else None
            price = total if total is not None else listed
        extend = g.get("extend") or {}
        return make_item(
            title=g.get("name"),
            price=price,
            url=url,
            stock=integer(extend.get("stock_count")),
            disabled=integer(g.get("status") if g.get("status") is not None else 1) != 1,
            tags=compact(
                [
                    (g.get("category") or {}).get("name"),
                    "卡密" if g.get("goods_type") == "card" else None,
                    "自动发货" if extend.get("send_order") == 0 else None,
                ]
            ),
        )
