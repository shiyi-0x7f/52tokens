"""活动域数据访问。"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, func, or_, select
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

    # ---------- 后台：不过滤可见性 ----------

    async def get(self, deal_id: int) -> Deal | None:
        return await self.session.scalar(
            select(Deal).where(Deal.id == deal_id).options(selectinload(Deal.platform))
        )

    async def get_platform(self, platform_id: int) -> Platform | None:
        return await self.session.get(Platform, platform_id)

    async def list_all(
        self,
        *,
        status: DealStatus | None,
        platform_id: int | None,
        q: str | None,
        offset: int,
        limit: int,
    ) -> tuple[Sequence[Deal], int]:
        stmt = select(Deal).options(selectinload(Deal.platform))
        if status is not None:
            stmt = stmt.where(Deal.status == status)
        if platform_id is not None:
            stmt = stmt.where(Deal.platform_id == platform_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Deal.title.ilike(like), Deal.slug.ilike(like)))
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.session.scalars(
            stmt.order_by(Deal.updated_at.desc(), Deal.id.desc()).offset(offset).limit(limit)
        )
        return rows.all(), int(total or 0)

    async def slug_taken(self, slug: str, exclude_id: int | None = None) -> bool:
        stmt = select(Deal.id).where(Deal.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Deal.id != exclude_id)
        return await self.session.scalar(stmt) is not None

    async def add(self, deal: Deal) -> None:
        self.session.add(deal)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
