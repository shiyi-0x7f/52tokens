"""目录域数据访问：只负责查询，不含展示规则。"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.catalog.models import (
    AIModel,
    ModelPrice,
    Platform,
    PlatformCategory,
    PublishStatus,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_platforms(self, category: PlatformCategory | None = None) -> Sequence[Platform]:
        stmt = select(Platform).where(Platform.status == PublishStatus.ACTIVE)
        if category is not None:
            stmt = stmt.where(Platform.category == category)
        return (await self.session.scalars(stmt.order_by(Platform.name))).all()

    async def list_models_with_prices(self) -> Sequence[AIModel]:
        stmt = (
            select(AIModel)
            .where(AIModel.status == PublishStatus.ACTIVE)
            .options(selectinload(AIModel.prices).selectinload(ModelPrice.platform))
            .order_by(AIModel.family, AIModel.name)
        )
        return (await self.session.scalars(stmt)).all()

    async def get_model_with_prices(self, slug: str) -> AIModel | None:
        stmt = (
            select(AIModel)
            .where(AIModel.slug == slug, AIModel.status == PublishStatus.ACTIVE)
            .options(selectinload(AIModel.prices).selectinload(ModelPrice.platform))
        )
        return await self.session.scalar(stmt)
