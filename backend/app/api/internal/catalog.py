"""平台与模型价格（公开站服务端专用）。"""

from fastapi import APIRouter

from app.api.deps import CatalogServiceDep
from app.core.response import ApiResponse, ok
from app.domains.catalog.models import PlatformCategory
from app.domains.catalog.schemas import ModelDetail, ModelSummary, PlatformOut

router = APIRouter(tags=["internal:catalog"])


@router.get("/platforms")
async def list_platforms(
    service: CatalogServiceDep, category: PlatformCategory | None = None
) -> ApiResponse[list[PlatformOut]]:
    return ok(await service.list_platforms(category))


@router.get("/platforms/{slug}")
async def get_platform(slug: str, service: CatalogServiceDep) -> ApiResponse[PlatformOut]:
    return ok(await service.get_platform(slug))


@router.get("/models")
async def list_models(service: CatalogServiceDep) -> ApiResponse[list[ModelSummary]]:
    return ok(await service.list_models())


@router.get("/models/{slug}")
async def get_model(slug: str, service: CatalogServiceDep) -> ApiResponse[ModelDetail]:
    return ok(await service.get_model(slug))
