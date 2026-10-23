"""卡网比价域：标准商品、卡网店铺、店铺报价。

边界（见 roadmap 决策记录）：只罗列公开报价，不认证、不推荐、不担保任何商家；
对外的「有货最低价」只显示价格和有货家数，不出现商家名；卡网商家不进任何付费位。
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, str_enum
from app.domains.catalog.models import PublishStatus


class ShopCollectorKind(StrEnum):
    """店铺系统类型，对应一种采集方式。"""

    KAMI = "kami"
    DUJIAO = "dujiao"  # 独角数卡
    SHOP_API = "shopApi"
    XIAOHEIWAN = "xiaoheiwan"
    OPENSORA_HTML = "opensoraHtml"
    MAKERICH_HTML = "makerichHtml"
    BEIBEI_HTML = "beibeiHtml"
    IKUNLOVE_API = "ikunloveApi"
    GETGPT_API = "getgptApi"
    PUBLIC_PRODUCTS_API = "publicProductsApi"
    SHOP_USER_PRODUCTS_API = "shopUserProductsApi"
    UNICORN_HTML = "unicornHtml"
    MOONCAKE_CATALOG = "mooncakeCatalog"
    BLACKCAT_WHOLESALE = "blackcatWholesale"
    GENERIC_HTML = "genericHtml"


class ShopProduct(TimestampMixin, Base):
    """标准商品：把各店铺五花八门的标题归到同一个商品下比价。"""

    __tablename__ = "shop_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    platform: Mapped[str] = mapped_column(String(40), index=True)  # ChatGPT / Claude / 邮箱 …
    product_type: Mapped[str] = mapped_column(String(40))  # 订阅/会员、成品账号 …
    spec: Mapped[str] = mapped_column(String(200), default="", server_default="")
    summary: Mapped[str] = mapped_column(String(500), default="", server_default="")
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list, server_default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # hidden：照样参与归类（准确识别出来），但不对外展示
    status: Mapped[PublishStatus] = mapped_column(
        str_enum(PublishStatus), default=PublishStatus.ACTIVE, index=True
    )


class ShopSource(TimestampMixin, Base):
    """一个卡网店铺，按店铺地址唯一。

    多数店铺系统一个域名就是一家店（entry_url = base_url）；ShopApi 这类多商户平台同一域名下
    有很多商户，entry_url 是具体商户的 /shop/<token> 地址。
    """

    __tablename__ = "shop_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[str] = mapped_column(String(120), index=True)
    entry_url: Mapped[str] = mapped_column(String(300), unique=True)
    name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    base_url: Mapped[str] = mapped_column(String(300))
    collector_kind: Mapped[ShopCollectorKind] = mapped_column(str_enum(ShopCollectorKind))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(String(300), default="", server_default="")
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    offer_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class ShopOffer(TimestampMixin, Base):
    """店铺的一条公开报价（一个商品 / 规格）。按（店铺, 店铺内商品键）upsert。"""

    __tablename__ = "shop_offers"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("shop_sources.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(200))  # 店铺内的商品 / 规格标识
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500))
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # 人民币，含可推算的手续费
    currency: Mapped[str] = mapped_column(String(8), default="CNY", server_default="CNY")
    stock: Mapped[int | None] = mapped_column(Integer)  # None = 店铺没公开库存
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 店铺给的分类名、「自动发货」等标签：归类时作辅助信息
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, server_default="{}")
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("shop_products.id", ondelete="SET NULL"), index=True
    )
    # 归类方式：rule（规则自动）/ manual（后台人工指定，不被自动归类覆盖）
    match_method: Mapped[str] = mapped_column(String(16), default="rule", server_default="rule")
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # 最近一次采集到它的时间：采集成功但没再出现 → 视为下架（不删除）
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    source: Mapped[ShopSource] = relationship()
    product: Mapped[ShopProduct | None] = relationship()
