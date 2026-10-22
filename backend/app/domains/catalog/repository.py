"""目录域数据访问：只负责查询，不含展示规则。"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
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

    async def get_platform_id(self, slug: str) -> int | None:
        return await self.session.scalar(select(Platform.id).where(Platform.slug == slug))

    async def upsert_models(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        """按 slug 建 / 更新模型，返回 slug → id。

        已有模型只更新名称和上下文；状态、系列、简介可能被人工调整过，不覆盖。
        """
        if not rows:
            return {}
        insert_stmt = insert(AIModel).values(rows)
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={
                "name": excluded.name,
                "context_window": func.coalesce(excluded.context_window, AIModel.context_window),
                "updated_at": func.now(),
            },
        ).returning(AIModel.slug, AIModel.id)
        return {slug: id_ for slug, id_ in (await self.session.execute(stmt)).all()}

    async def upsert_prices(self, rows: list[dict[str, Any]]) -> None:
        """按 (平台, 模型) 建 / 更新价格。已有价格的发布状态可能被人工隐藏过，不覆盖。"""
        if not rows:
            return
        stmt = insert(ModelPrice).values(rows)
        keep = {"platform_id", "model_id", "status"}
        stmt = stmt.on_conflict_do_update(
            index_elements=["platform_id", "model_id"],
            set_={c: stmt.excluded[c] for c in rows[0] if c not in keep}
            | {"updated_at": func.now()},
        )
        await self.session.execute(stmt)

    async def get_model_with_prices(self, slug: str) -> AIModel | None:
        stmt = (
            select(AIModel)
            .where(AIModel.slug == slug, AIModel.status == PublishStatus.ACTIVE)
            .options(selectinload(AIModel.prices).selectinload(ModelPrice.platform))
        )
        return await self.session.scalar(stmt)
