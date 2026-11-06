"""精选模型对比：对外查询与后台维护。"""

from app.core.errors import AppError
from app.domains.catalog.admin import ModelBrief
from app.domains.catalog.models import AIModel, PublishStatus
from app.domains.common import Page
from app.domains.comparisons.models import ModelComparison
from app.domains.comparisons.repository import ComparisonRepository
from app.domains.comparisons.schemas import (
    ComparisonAdminOut,
    ComparisonIn,
    ComparisonListQuery,
    ComparisonOut,
    ComparisonUpdate,
)

MODEL_SEARCH_LIMIT = 20


class ComparisonService:
    """公开站用：只返回组合与两个模型都已发布的。"""

    def __init__(self, repo: ComparisonRepository) -> None:
        self.repo = repo

    async def list_pairs(self, model_slug: str | None = None) -> list[ComparisonOut]:
        return [ComparisonOut.model_validate(c) for c in await self.repo.list_public(model_slug)]

    async def get_pair(self, slug_x: str, slug_y: str) -> ComparisonOut:
        """两个模型不分先后；返回的顺序是收录时的网址顺序，公开站据此跳转到规范网址。"""
        pair = await self.repo.get_public_pair(slug_x, slug_y)
        if pair is None:
            raise AppError("NOT_FOUND", "没有收录这组对比")
        return ComparisonOut.model_validate(pair)


class ComparisonAdminService:
    def __init__(self, repo: ComparisonRepository) -> None:
        self.repo = repo

    async def list_page(self, query: ComparisonListQuery) -> Page[ComparisonAdminOut]:
        rows, total = await self.repo.list_all(
            q=query.q, offset=query.offset, limit=query.page_size
        )
        return Page(
            items=[ComparisonAdminOut.model_validate(c) for c in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def search_models(self, q: str | None) -> list[ModelBrief]:
        rows = await self.repo.search_models(q, MODEL_SEARCH_LIMIT)
        return [ModelBrief.model_validate(m) for m in rows]

    async def _model(self, slug: str) -> AIModel:
        model = await self.repo.get_model(slug)
        if model is None:
            raise AppError("BAD_REQUEST", f"模型不存在：{slug}")
        return model

    async def _get(self, comparison_id: int) -> ModelComparison:
        obj = await self.repo.get(comparison_id)
        if obj is None:
            raise AppError("NOT_FOUND", "对比不存在")
        return obj

    async def _out(self, comparison_id: int) -> ComparisonAdminOut:
        return ComparisonAdminOut.model_validate(await self._get(comparison_id))

    async def create(self, data: ComparisonIn) -> ComparisonAdminOut:
        a = await self._model(data.model_a_slug)
        b = await self._model(data.model_b_slug)
        if await self.repo.pair_exists(a.id, b.id):
            raise AppError("CONFLICT", "这两个模型的对比已经收录过了")
        obj = ModelComparison(
            model_a_id=a.id,
            model_b_id=b.id,
            intro=data.intro.strip(),
            sort_order=data.sort_order,
            status=PublishStatus.ACTIVE,
        )
        self.repo.add(obj)
        await self.repo.flush()
        obj_id = obj.id
        await self.repo.commit()
        return await self._out(obj_id)

    async def update(self, comparison_id: int, data: ComparisonUpdate) -> ComparisonAdminOut:
        obj = await self._get(comparison_id)
        obj.intro = data.intro.strip()
        obj.sort_order = data.sort_order
        await self.repo.commit()
        return await self._out(comparison_id)

    async def set_status(self, comparison_id: int, status: PublishStatus) -> ComparisonAdminOut:
        obj = await self._get(comparison_id)
        obj.status = status
        await self.repo.commit()
        return await self._out(comparison_id)

    async def delete(self, comparison_id: int) -> None:
        await self.repo.delete(await self._get(comparison_id))
        await self.repo.commit()
