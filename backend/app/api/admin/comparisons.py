"""精选模型对比名单维护。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ComparisonAdminServiceDep
from app.core.response import ApiResponse, ok
from app.domains.catalog.admin import ModelBrief
from app.domains.catalog.models import PublishStatus
from app.domains.common import Page
from app.domains.comparisons.schemas import (
    ComparisonAdminOut,
    ComparisonIn,
    ComparisonListQuery,
    ComparisonUpdate,
    ModelSearchQuery,
)

router = APIRouter(tags=["admin:comparisons"])


@router.get("/models")
async def search_models(
    service: ComparisonAdminServiceDep, query: Annotated[ModelSearchQuery, Query()]
) -> ApiResponse[list[ModelBrief]]:
    """按名称或 slug 搜索已发布的模型（选择对比模型用）。"""
    return ok(await service.search_models(query.q))


@router.get("/model-comparisons")
async def list_comparisons(
    service: ComparisonAdminServiceDep, query: Annotated[ComparisonListQuery, Query()]
) -> ApiResponse[Page[ComparisonAdminOut]]:
    return ok(await service.list_page(query))


@router.post("/model-comparisons")
async def create_comparison(
    body: ComparisonIn, service: ComparisonAdminServiceDep
) -> ApiResponse[ComparisonAdminOut]:
    return ok(await service.create(body))


@router.put("/model-comparisons/{comparison_id}")
async def update_comparison(
    comparison_id: int, body: ComparisonUpdate, service: ComparisonAdminServiceDep
) -> ApiResponse[ComparisonAdminOut]:
    return ok(await service.update(comparison_id, body))


@router.post("/model-comparisons/{comparison_id}/hide")
async def hide_comparison(
    comparison_id: int, service: ComparisonAdminServiceDep
) -> ApiResponse[ComparisonAdminOut]:
    return ok(await service.set_status(comparison_id, PublishStatus.HIDDEN))


@router.post("/model-comparisons/{comparison_id}/show")
async def show_comparison(
    comparison_id: int, service: ComparisonAdminServiceDep
) -> ApiResponse[ComparisonAdminOut]:
    return ok(await service.set_status(comparison_id, PublishStatus.ACTIVE))


@router.delete("/model-comparisons/{comparison_id}")
async def delete_comparison(
    comparison_id: int, service: ComparisonAdminServiceDep
) -> ApiResponse[None]:
    await service.delete(comparison_id)
    return ok(None)
