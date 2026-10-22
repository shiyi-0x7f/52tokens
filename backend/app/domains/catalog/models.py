"""目录域：平台、模型、官方 API 价格。"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, str_enum


class PlatformCategory(StrEnum):
    LLM_API_CN = "llm_api_cn"
    LLM_API_GLOBAL = "llm_api_global"
    CODING_TOOL = "coding_tool"
    MEDIA_TOOL = "media_tool"
    CLOUD = "cloud"


class PublishStatus(StrEnum):
    DRAFT = "draft"  # 待核实，不对外展示
    ACTIVE = "active"
    HIDDEN = "hidden"


class Platform(TimestampMixin, Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[PlatformCategory] = mapped_column(str_enum(PlatformCategory), index=True)
    website_url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PublishStatus] = mapped_column(
        str_enum(PublishStatus), default=PublishStatus.DRAFT, index=True
    )

    prices: Mapped[list["ModelPrice"]] = relationship(back_populates="platform")


class AIModel(TimestampMixin, Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    family: Mapped[str] = mapped_column(String(40), index=True)  # deepseek / qwen / glm ...
    context_window: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PublishStatus] = mapped_column(
        str_enum(PublishStatus), default=PublishStatus.DRAFT, index=True
    )

    prices: Mapped[list["ModelPrice"]] = relationship(back_populates="model")


class Currency(StrEnum):
    CNY = "CNY"
    USD = "USD"


class ModelPrice(TimestampMixin, Base):
    """某平台对某模型的官方 API 价格。单位：每百万 tokens，原币种存储。"""

    __tablename__ = "model_prices"
    __table_args__ = (UniqueConstraint("platform_id", "model_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"), index=True
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    currency: Mapped[Currency] = mapped_column(str_enum(Currency), default=Currency.CNY)
    input_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    cache_read_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    free_note: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str] = mapped_column(String(500))
    # 最近一次从官网核实的时间；为空表示从未核实，不对外展示
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[PublishStatus] = mapped_column(
        str_enum(PublishStatus), default=PublishStatus.DRAFT, index=True
    )

    platform: Mapped[Platform] = relationship(back_populates="prices")
    model: Mapped[AIModel] = relationship(back_populates="prices")
