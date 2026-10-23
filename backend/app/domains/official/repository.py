"""官方订阅地区价数据访问。"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.official.models import OfficialPlan


class OfficialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_plans(self) -> Sequence[OfficialPlan]:
        stmt = (
            select(OfficialPlan)
            .options(selectinload(OfficialPlan.prices))
            .order_by(OfficialPlan.sort_order, OfficialPlan.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def get_plan(self, app_slug: str, plan_slug: str) -> OfficialPlan | None:
        return await self.session.scalar(
            select(OfficialPlan)
            .where(OfficialPlan.app_slug == app_slug, OfficialPlan.plan_slug == plan_slug)
            .options(selectinload(OfficialPlan.prices))
        )
