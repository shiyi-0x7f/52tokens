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

    # ---------- 后台：不过滤发布状态 ----------

    async def list_all_platforms(self) -> Sequence[Platform]:
        return (await self.session.scalars(select(Platform).order_by(Platform.name))).all()

    async def get_platform(self, platform_id: int) -> Platform | None:
        return await self.session.get(Platform, platform_id)

    async def get_model_by_slug(self, slug: str) -> AIModel | None:
        return await self.session.scalar(select(AIModel).where(AIModel.slug == slug))

    async def get_price(self, price_id: int) -> ModelPrice | None:
        return await self.session.scalar(
            select(ModelPrice)
            .where(ModelPrice.id == price_id)
            .options(selectinload(ModelPrice.platform), selectinload(ModelPrice.model))
        )

    async def get_price_for(self, platform_id: int, model_id: int) -> ModelPrice | None:
        return await self.session.scalar(
            select(ModelPrice).where(
                ModelPrice.platform_id == platform_id, ModelPrice.model_id == model_id
            )
        )

    async def list_prices(
        self, *, platform_id: int | None, q: str | None, offset: int, limit: int
    ) -> tuple[Sequence[ModelPrice], int]:
        stmt = (
            select(ModelPrice)
            .join(ModelPrice.model)
            .options(selectinload(ModelPrice.platform), selectinload(ModelPrice.model))
        )
        if platform_id is not None:
            stmt = stmt.where(ModelPrice.platform_id == platform_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(AIModel.name.ilike(like) | AIModel.slug.ilike(like))
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.session.scalars(
            stmt.order_by(ModelPrice.updated_at.desc(), ModelPrice.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return rows.all(), int(total or 0)

    def add(self, obj: AIModel | ModelPrice) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

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
