"""精选模型对比（公开站服务端专用）。"""

from fastapi import APIRouter, Query

from app.api.deps import ComparisonServiceDep
from app.core.response import ApiResponse, ok
from app.domains.comparisons.schemas import ComparisonOut

router = APIRouter(tags=["internal:comparisons"])


@router.get("/model-comparisons")
async def list_comparisons(
    service: ComparisonServiceDep,
    model: str | None = Query(default=None, max_length=80),
) -> ApiResponse[list[ComparisonOut]]:
    """全部已收录的组合；带 model 时只返回含该模型的（模型页「相关对比」）。"""
    return ok(await service.list_pairs(model))


@router.get("/model-comparisons/{slug_x}/{slug_y}")
async def get_comparison(
    slug_x: str, slug_y: str, service: ComparisonServiceDep
) -> ApiResponse[ComparisonOut]:
    """两个模型不分先后，返回收录时的顺序（规范网址）。"""
    return ok(await service.get_pair(slug_x, slug_y))
