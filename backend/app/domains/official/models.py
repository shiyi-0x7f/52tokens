"""官方订阅地区价：ChatGPT / Claude / Gemini / Grok 各订阅档位在各国 App Store 的价格。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class OfficialPlan(TimestampMixin, Base):
    """一个订阅档位，如 ChatGPT Plus（月付）。"""

    __tablename__ = "official_plans"
    __table_args__ = (UniqueConstraint("app_slug", "plan_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_slug: Mapped[str] = mapped_column(String(40))
    app_name: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str] = mapped_column(String(60))
    plan_slug: Mapped[str] = mapped_column(String(60))
    plan_name: Mapped[str] = mapped_column(String(80))
    billing_period: Mapped[str] = mapped_column(String(20))  # monthly / annual
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    prices: Mapped[list["OfficialRegionPrice"]] = relationship(back_populates="plan")


class OfficialRegionPrice(TimestampMixin, Base):
    """某档位在某个国家 / 地区 App Store 的价格；status=missing 表示该地区没上架这个档位。"""

    __tablename__ = "official_region_prices"
    __table_args__ = (UniqueConstraint("plan_id", "country_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("official_plans.id", ondelete="CASCADE"), index=True
    )
    country_code: Mapped[str] = mapped_column(String(8))
    country_label: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(8))
    price_text: Mapped[str] = mapped_column(String(40), default="", server_default="")
    price_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # 当地货币
    cny_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # 按 fx_date 汇率折合人民币
    fx_rate_to_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    fx_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16))  # available / missing
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # 价格的核实时间

    plan: Mapped[OfficialPlan] = relationship(back_populates="prices")
