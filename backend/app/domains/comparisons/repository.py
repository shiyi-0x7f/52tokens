"""精选模型对比数据访问。"""

from collections.abc import Sequence

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.domains.catalog.models import AIModel, PublishStatus
from app.domains.comparisons.models import ModelComparison

_A = aliased(AIModel)
_B = aliased(AIModel)
_WITH_MODELS = (selectinload(ModelComparison.model_a), selectinload(ModelComparison.model_b))


def _joined() -> Select[ModelComparison]:
    return (
        select(ModelComparison)
        .join(_A, ModelComparison.model_a_id == _A.id)
        .join(_B, ModelComparison.model_b_id == _B.id)
    )


def _public() -> Select[ModelComparison]:
    """对外可见：组合已发布，且两个模型都已发布。"""
    return (
        _joined()
        .where(
            ModelComparison.status == PublishStatus.ACTIVE,
            _A.status == PublishStatus.ACTIVE,
            _B.status == PublishStatus.ACTIVE,
        )
        .options(*_WITH_MODELS)
    )


class ComparisonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_public(self, model_slug: str | None = None) -> Sequence[ModelComparison]:
        stmt = _public()
        if model_slug is not None:
            stmt = stmt.where(or_(_A.slug == model_slug, _B.slug == model_slug))
        stmt = stmt.order_by(ModelComparison.sort_order, ModelComparison.id)
        return (await self.session.scalars(stmt)).all()

    async def get_public_pair(self, slug_x: str, slug_y: str) -> ModelComparison | None:
        """按两个模型查组合，不分先后。"""
        stmt = _public().where(
            or_(
                and_(_A.slug == slug_x, _B.slug == slug_y),
                and_(_A.slug == slug_y, _B.slug == slug_x),
            )
        )
        return await self.session.scalar(stmt)

    # ---------- 后台 ----------

    async def list_all(
        self, *, q: str | None, offset: int, limit: int
    ) -> tuple[Sequence[ModelComparison], int]:
        stmt = _joined()
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    _A.slug.ilike(like),
                    _A.name.ilike(like),
                    _B.slug.ilike(like),
                    _B.name.ilike(like),
                )
            )
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.session.scalars(
            stmt.options(*_WITH_MODELS)
            .order_by(ModelComparison.sort_order, ModelComparison.id)
            .offset(offset)
            .limit(limit)
        )
        return rows.all(), int(total or 0)

    async def get(self, comparison_id: int) -> ModelComparison | None:
        return await self.session.scalar(
            select(ModelComparison)
            .where(ModelComparison.id == comparison_id)
            .options(*_WITH_MODELS)
        )

    async def pair_exists(self, a_id: int, b_id: int) -> bool:
        stmt = select(ModelComparison.id).where(
            or_(
                and_(ModelComparison.model_a_id == a_id, ModelComparison.model_b_id == b_id),
                and_(ModelComparison.model_a_id == b_id, ModelComparison.model_b_id == a_id),
            )
        )
        return await self.session.scalar(stmt) is not None

    async def get_model(self, slug: str) -> AIModel | None:
        return await self.session.scalar(select(AIModel).where(AIModel.slug == slug))

    async def search_models(self, q: str | None, limit: int) -> Sequence[AIModel]:
        stmt = select(AIModel).where(AIModel.status == PublishStatus.ACTIVE)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(AIModel.slug.ilike(like), AIModel.name.ilike(like)))
        stmt = stmt.order_by(AIModel.family, AIModel.name).limit(limit)
        return (await self.session.scalars(stmt)).all()

    def add(self, obj: ModelComparison) -> None:
        self.session.add(obj)

    async def delete(self, obj: ModelComparison) -> None:
        await self.session.delete(obj)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
