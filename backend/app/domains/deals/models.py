"""活动域：签到积分、注册赠送、免费额度、折扣等。"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, str_enum
from app.domains.catalog.models import Platform


class DealType(StrEnum):
    CHECKIN_POINTS = "checkin_points"  # 每日签到领积分
    SIGNUP_CREDIT = "signup_credit"  # 注册赠送
    FREE_QUOTA = "free_quota"  # 长期免费额度
    INVITE_REWARD = "invite_reward"  # 邀请奖励
    DISCOUNT = "discount"  # 限时折扣 / 优惠码
    STUDENT = "student"  # 学生 / 教育优惠
    TRIAL = "trial"  # 试用
    EVENT = "event"  # 活动 / 抽奖 / 比赛


class DealCycle(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    MONTHLY = "monthly"
    ONGOING = "ongoing"


class DealStatus(StrEnum):
    PENDING = "pending"  # 待审核，不对外展示
    ACTIVE = "active"
    EXPIRED = "expired"  # 已结束：页面保留，下沉到「已结束」
    REJECTED = "rejected"


class Deal(TimestampMixin, Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    deal_type: Mapped[DealType] = mapped_column(str_enum(DealType), index=True)
    reward_text: Mapped[str] = mapped_column(String(100))  # 展示用，如「+200 积分/天」
    # 折合人民币估值：算法须公开，算不出来就留空，不夸大
    est_value_cny: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    requirements: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    cycle: Mapped[DealCycle] = mapped_column(str_enum(DealCycle), default=DealCycle.ONCE)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(500))
    aff_url: Mapped[str | None] = mapped_column(String(500))  # 有值即推广链接，页面必须标注
    in_app_only: Mapped[bool] = mapped_column(Boolean, default=False)  # 只能在客户端里查看
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[DealStatus] = mapped_column(
        str_enum(DealStatus), default=DealStatus.PENDING, index=True
    )
    # 审核留痕：最近一次发布 / 驳回 / 下线的操作人和时间
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str] = mapped_column(String(200), default="", server_default="")

    platform: Mapped[Platform] = relationship()
