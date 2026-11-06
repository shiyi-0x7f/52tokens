"""卡网比价对外数据结构（只给公开站服务端用）。"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ShopProductSummary(BaseModel):
    slug: str
    name: str
    platform: str
    product_type: str
    spec: str
    # 有货最低价与有货店铺数：只算新鲜（近 48 小时采集到）、有货、不是拼车或异常价的报价；
    # 外层不出现商家名
    min_price: Decimal | None
    in_stock_shops: int
    offer_count: int


class ShopOfferOut(BaseModel):
    title: str  # 店铺原标题
    price: Decimal
    stock: int | None
    in_stock: bool
    # 跳转标识：页面链接到 /go/offer/{token}，经过渡页提示后再去店铺；店铺链接本身不下发
    token: str
    shop: str  # 店铺代号（如「店铺 7F3A」），不含域名；对外页面不出现店铺网址
    tags: list[str]
    # 「拼车」「价格待核实」：照常展示，但不参与有货最低价
    flags: list[str]
    last_seen_at: datetime
    is_fresh: bool  # 近 48 小时采集到过；否则可能已失效，不参与最低价


class ShopProductDetail(ShopProductSummary):
    summary: str
    offers: list[ShopOfferOut]
