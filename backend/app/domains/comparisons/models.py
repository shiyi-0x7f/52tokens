"""精选模型对比：后台挑选的「A vs B」组合，公开站据此生成可收录的 /models/{a}-vs-{b} 页面。

不在名单里的组合页面照样能打开，但不进 sitemap、不让搜索引擎收录，避免无数薄页面。
A、B 的顺序就是对外网址的顺序；同一对模型不分先后只能收录一次（服务层校验）。
"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, str_enum
from app.domains.catalog.models import AIModel, PublishStatus


class ModelComparison(TimestampMixin, Base):
    __tablename__ = "model_comparisons"
    __table_args__ = (
        UniqueConstraint("model_a_id", "model_b_id"),
        CheckConstraint("model_a_id <> model_b_id", name="distinct_models"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_a_id: Mapped[int] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    model_b_id: Mapped[int] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    # 人工写的导语（选型建议等），给页面增加独有内容；可留空
    intro: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[PublishStatus] = mapped_column(
        str_enum(PublishStatus), default=PublishStatus.ACTIVE, index=True
    )

    model_a: Mapped[AIModel] = relationship(foreign_keys=[model_a_id])
    model_b: Mapped[AIModel] = relationship(foreign_keys=[model_b_id])
