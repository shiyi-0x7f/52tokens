"""价格历史：按天（北京时间）记录对外展示的价格快照，支撑价格历史图与月度报告。

同一天重复快照会覆盖当天那一行，所以每天的值等于当天最后一次快照时的状态。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelPriceDaily(Base):
    """某平台某模型的官方 API 价格当天快照。单位：每百万 tokens，原币种。"""

    __tablename__ = "model_price_history"
    __table_args__ = (UniqueConstraint("day", "platform_id", "model_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"), index=True
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    currency: Mapped[str] = mapped_column(String(8))
    input_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    cache_read_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    is_free: Mapped[bool] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ShopProductDaily(Base):
    """卡网标准商品当天的有货最低价与有货店铺数（规则与比价页一致）。"""

    __tablename__ = "shop_product_price_history"
    __table_args__ = (UniqueConstraint("day", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("shop_products.id", ondelete="CASCADE"), index=True
    )
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # 无有货报价时为空
    in_stock_shops: Mapped[int] = mapped_column(Integer)
    offer_count: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
