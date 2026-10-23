"""ShopGoodsApi 多商户平台（如 16688）：店铺地址是具体商户的 /shop/<店铺编号或别名>。

先查店铺详情把别名换成店铺编号，再一次拿全店商品（接口不分页）。
注意：平台裸域名会 301 到 www，POST 被重定向后会变成 GET 丢掉请求体，店铺地址要直接用 www 域名。
"""

from typing import Any, ClassVar

from app.collectors.registry import register
from app.collectors.shops.base import ShopCollector, ShopFetchError, ShopItem, ShopTarget, make_item
from app.collectors.shops.parse import integer, number
from app.collectors.shops.shop_api import shop_token


def _ok(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("code") == 1


@register
class ShopGoodsApiCollector(ShopCollector):
    kind: ClassVar[str] = "shopGoodsApi"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        code = shop_token(target.entry_url)
        if not code:
            raise ShopFetchError(
                "多商户平台需要具体商户的店铺地址（/shop/<店铺编号>），请在后台补充"
            )
        base = target.base_url
        shop_url = f"{base}/shop/{code}"

        detail = await self.post_json(f"{base}/shopApi/shop/detail", {"shop_no": code}, shop_url)
        shop_no = (detail.get("data") or {}).get("shop_no") if _ok(detail) else None
        if not shop_no:
            raise ShopFetchError("店铺信息不可用（店铺不存在或已关闭）")

        await self.pause()
        listing = await self.post_json(
            f"{base}/shopApi/goods/list", {"shop_no": shop_no, "sort": "default"}, shop_url
        )
        goods = (listing.get("data") or {}).get("list") if _ok(listing) else None
        if not isinstance(goods, list):
            raise ShopFetchError("商品列表接口返回异常")
        return [item for g in goods if (item := self._item(base, g))]

    @staticmethod
    def _item(base: str, g: dict[str, Any]) -> ShopItem | None:
        goods_no = g.get("goods_no")
        if not goods_no:
            return None
        return make_item(
            title=g.get("name"),
            price=number(g.get("price")),
            url=f"{base}/goods/{goods_no}",
            stock=integer(g.get("stock_available_quantity")),
        )
