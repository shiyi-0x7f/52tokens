"""活动域对外数据结构（只给公开站服务端用）。"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.domains.catalog.schemas import PlatformRef
from app.domains.deals.models import DealCycle, DealType


class DealOut(BaseModel):
    slug: str
    title: str
    deal_type: DealType
    platform: PlatformRef
    reward_text: str
    est_value_cny: Decimal | None
    requirements: list[str]
    cycle: DealCycle
    starts_at: datetime | None
    ends_at: datetime | None
    description: str
    steps: list[str]
    # 有推广链接：页面「去参与」入口必须标「推广」；落地地址不下发，经 /go/deal/{slug} 跳转
    is_promoted: bool
    source_url: str
    # 官网原文摘录，及带 #:~:text= 片段的定位链接（打开后滚到原文）；
    # 没有原文时 source_quote 为空、source_locate_url 同 source_url
    source_quote: str
    source_locate_url: str
    in_app_only: bool
    confirmed_at: datetime
    is_expired: bool
