"""监测来源数据访问。"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.catalog.models import Platform
from app.domains.deals.models import Deal, DealSource

# 交给 LLM 对照的已收录活动条数上限（控制 prompt 长度）
EXISTING_DEALS_LIMIT = 50


class DealSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, source_id: int) -> DealSource | None:
        # populate_existing：改了 platform_id 之后，关联的 platform 要按新值重新加载
        return await self.session.scalar(
            select(DealSource)
            .where(DealSource.id == source_id)
            .options(selectinload(DealSource.platform))
            .execution_options(populate_existing=True)
        )

    async def list_enabled(self) -> Sequence[DealSource]:
        stmt = (
            select(DealSource)
            .where(DealSource.enabled.is_(True))
            .options(selectinload(DealSource.platform))
            .order_by(DealSource.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def list_all(
        self, *, platform_id: int | None, offset: int, limit: int
    ) -> tuple[Sequence[DealSource], int]:
        stmt = select(DealSource).options(selectinload(DealSource.platform))
        if platform_id is not None:
            stmt = stmt.where(DealSource.platform_id == platform_id)
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.session.scalars(
            stmt.order_by(DealSource.id.desc()).offset(offset).limit(limit)
        )
        return rows.all(), int(total or 0)

    async def url_taken(self, url: str, exclude_id: int | None = None) -> bool:
        stmt = select(DealSource.id).where(DealSource.url == url)
        if exclude_id is not None:
            stmt = stmt.where(DealSource.id != exclude_id)
        return await self.session.scalar(stmt) is not None

    async def get_platform(self, platform_id: int) -> Platform | None:
        return await self.session.get(Platform, platform_id)

    async def platform_deals(self, platform_id: int) -> Sequence[Deal]:
        """该平台已收录的活动（含待审核、已驳回：避免重复提出已被驳回的线索）。"""
        stmt = (
            select(Deal)
            .where(Deal.platform_id == platform_id)
            .order_by(Deal.updated_at.desc())
            .limit(EXISTING_DEALS_LIMIT)
        )
        return (await self.session.scalars(stmt)).all()

    def add(self, obj: DealSource | Deal) -> None:
        self.session.add(obj)

    async def delete(self, source: DealSource) -> None:
        await self.session.delete(source)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
