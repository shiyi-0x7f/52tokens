"""出站跳转：公开站 /go/* 的每次点击记一条，用于出站点击与推广转化统计。"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, str_enum


class OutboundTarget(StrEnum):
    DEAL = "deal"


class OutboundClick(Base):
    __tablename__ = "outbound_clicks"
    __table_args__ = (Index("ix_outbound_clicks_target", "target_type", "target_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 不建外键：跳转对象可能来自不同的表，点击记录也不随对象删除
    target_type: Mapped[OutboundTarget] = mapped_column(str_enum(OutboundTarget))
    target_id: Mapped[int] = mapped_column(Integer)
    # 点击当时的落地地址和是否推广（之后改了推广链接也能区分归因）
    target_url: Mapped[str] = mapped_column(String(500))
    is_promoted: Mapped[bool] = mapped_column(Boolean)
    # 从站内哪个页面点出去的；不记 IP / UA
    referer_path: Mapped[str] = mapped_column(String(200), default="", server_default="")
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
