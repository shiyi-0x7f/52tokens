"""活动域数据访问。"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.catalog.models import Platform, PublishStatus
from app.domains.deals.models import Deal, DealStatus, DealType


class DealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _public(self) -> Select[Deal]:
        """已发布（含已结束）、已核实、所属平台已发布的活动。"""
        return (
            select(Deal)
            .join(Deal.platform)
            .where(
                Deal.status.in_([DealStatus.ACTIVE, DealStatus.EXPIRED]),
                Deal.confirmed_at.is_not(None),
                Platform.status == PublishStatus.ACTIVE,
            )
            .options(selectinload(Deal.platform))
        )

    async def list_public(
        self,
        *,
        deal_type: DealType | None,
        platform_slug: str | None,
        include_expired: bool,
        now: datetime,
        limit: int,
    ) -> Sequence[Deal]:
        stmt = self._public()
        if not include_expired:
            stmt = stmt.where(
                Deal.status == DealStatus.ACTIVE,
                or_(Deal.ends_at.is_(None), Deal.ends_at > now),
            )
        if deal_type is not None:
            stmt = stmt.where(Deal.deal_type == deal_type)
        if platform_slug is not None:
            stmt = stmt.where(Platform.slug == platform_slug)
        stmt = stmt.order_by(Deal.confirmed_at.desc()).limit(limit)
        return (await self.session.scalars(stmt)).all()

    async def get_public(self, slug: str) -> Deal | None:
        return await self.session.scalar(self._public().where(Deal.slug == slug))
