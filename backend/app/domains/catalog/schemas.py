"""目录域对外数据结构（只给公开站服务端用）。"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domains.catalog.models import Currency, PlatformCategory


class PlatformRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class PlatformOut(PlatformRef):
    category: PlatformCategory
    website_url: str
    description: str


class PriceOut(BaseModel):
    platform: PlatformRef
    currency: Currency
    input_price: Decimal | None
    output_price: Decimal | None
    cache_read_price: Decimal | None
    is_free: bool
    free_note: str
    source_url: str
    confirmed_at: datetime


class ModelSummary(BaseModel):
    slug: str
    name: str
    family: str
    context_window: int | None
    # 已核实价格中最低的输出价（同币种比较由页面处理，这里只给 CNY 最低价）
    min_output_price_cny: Decimal | None
    has_free: bool
    price_count: int


class ModelDetail(BaseModel):
    slug: str
    name: str
    family: str
    context_window: int | None
    description: str
    prices: list[PriceOut]
