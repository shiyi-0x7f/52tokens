"""卡网比价对外规则：哪些商品 / 报价可以展示，有货最低价怎么算。

- 只展示 active 的商品（不含「其他商品」和下线的商品）；报价来自启用的店铺且未被隐藏；
- 近 FRESH_HOURS 小时采集到过的报价才算新鲜：有货最低价与有货店铺数只算新鲜、有货、
  且没被标记（拼车 / 价格待核实）的；被标记的照常展示，只是不决定最低价；
- 排序：可比的有货报价按价格从低到高，其后被标记的，再后无货，最后是可能已失效的。
"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import median

from app.core.errors import AppError
from app.domains.shops.models import ShopOffer, ShopProduct
from app.domains.shops.repository import ShopRepository
from app.domains.shops.schemas import ShopOfferOut, ShopProductDetail, ShopProductSummary

FRESH_HOURS = 48
OTHER_PRODUCT = "other-product"
MAX_OFFERS = 100


# 拼车 / 多人共享：和独享号没法比价，照常展示但不参与最低价
_SHARED_ACCESS = re.compile(
    r"拼车|团购|拼团|车位|多人共享|多人共用|多人车|车友|车队|家庭车|团号|共享车"
    r"|(?:[二两双三四五六七八九十]|[2-9]|[1-9][0-9])人(?:车|共享|共用|位)"
)
# 有 OUTLIER_MIN_OFFERS 条以上可比报价时，低于中位数这个比例的视为占位价 / 异常价
OUTLIER_RATIO = Decimal("0.3")
OUTLIER_MIN_OFFERS = 3
FLAG_SHARED = "拼车"
FLAG_OUTLIER = "价格待核实"


def _is_fresh(offer: ShopOffer, now: datetime) -> bool:
    return offer.last_seen_at >= now - timedelta(hours=FRESH_HOURS)


def _flags(offers: Sequence[ShopOffer], now: datetime) -> dict[int, list[str]]:
    """给新鲜有货的报价打标记：拼车、价格异常。被标记的不参与最低价。"""
    flags: dict[int, list[str]] = {}
    live = [o for o in offers if o.in_stock and o.price is not None and _is_fresh(o, now)]
    comparable = []
    for o in live:
        if _SHARED_ACCESS.search(o.title):
            flags[o.id] = [FLAG_SHARED]
        else:
            comparable.append(o)
    if len(comparable) >= OUTLIER_MIN_OFFERS:
        floor = median(o.price for o in comparable if o.price is not None) * OUTLIER_RATIO
        for o in comparable:
            if o.price is not None and o.price < floor:
                flags[o.id] = [FLAG_OUTLIER]
    return flags


def _summary_fields(
    product: ShopProduct, offers: Sequence[ShopOffer], now: datetime, flags: dict[int, list[str]]
) -> dict[str, object]:
    eligible = [
        o
        for o in offers
        if o.in_stock and o.price is not None and _is_fresh(o, now) and o.id not in flags
    ]
    return {
        "slug": product.slug,
        "name": product.name,
        "platform": product.platform,
        "product_type": product.product_type,
        "spec": product.spec,
        "min_price": min((o.price for o in eligible if o.price is not None), default=None),
        "in_stock_shops": len({o.source_id for o in eligible}),
        "offer_count": len(offers),
    }


def _sort_key(offer: ShopOffer, now: datetime, flags: dict[int, list[str]]) -> tuple[int, object]:
    """可比的有货报价按价格排前面，其后是拼车 / 价格待核实的，再后无货，最后可能已失效的。"""
    if not _is_fresh(offer, now):
        return (3, offer.price)
    if not offer.in_stock:
        return (2, offer.price)
    return (1 if offer.id in flags else 0, offer.price)


class ShopService:
    def __init__(self, repo: ShopRepository) -> None:
        self.repo = repo

    async def list_products(self) -> list[ShopProductSummary]:
        now = datetime.now(UTC)
        products = await self.repo.list_public_products(exclude=OTHER_PRODUCT)
        offers = await self.repo.public_offers([p.id for p in products])
        by_product: dict[int, list[ShopOffer]] = {}
        for o in offers:
            if o.product_id is not None:
                by_product.setdefault(o.product_id, []).append(o)
        out = []
        for p in products:
            rows = by_product.get(p.id)
            if rows:
                fields = _summary_fields(p, rows, now, _flags(rows, now))
                out.append(ShopProductSummary.model_validate(fields))
        return out

    async def get_product(self, slug: str) -> ShopProductDetail:
        product = await self.repo.get_public_product(slug)
        if product is None or product.slug == OTHER_PRODUCT:
            raise AppError("NOT_FOUND")
        now = datetime.now(UTC)
        rows = await self.repo.public_offers([product.id])
        flags = _flags(rows, now)
        offers = sorted(rows, key=lambda o: _sort_key(o, now, flags))
        return ShopProductDetail.model_validate(
            {
                **_summary_fields(product, offers, now, flags),
                "summary": product.summary,
                "offers": [
                    ShopOfferOut(
                        title=o.title,
                        price=o.price,
                        stock=o.stock,
                        in_stock=o.in_stock,
                        url=o.url,
                        shop=o.source.host,
                        tags=list(o.tags),
                        flags=flags.get(o.id, []),
                        last_seen_at=o.last_seen_at,
                        is_fresh=_is_fresh(o, now),
                    )
                    for o in offers[:MAX_OFFERS]
                    if o.price is not None
                ],
            }
        )
