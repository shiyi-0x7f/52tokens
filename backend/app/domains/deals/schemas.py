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
    # 有推广链接：页面「去参与」入口必须标「推广」；落地地址不下发，经 /go/deal/{slug} 跳转
    is_promoted: bool
    source_url: str
    in_app_only: bool
    confirmed_at: datetime
    is_expired: bool
