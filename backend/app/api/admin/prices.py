"""平台列表与价格的手工录入。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import PriceAdminServiceDep
from app.core.response import ApiResponse, ok
from app.domains.catalog.admin import PlatformAdminOut, PriceAdminOut, PriceIn, PriceListQuery
from app.domains.catalog.models import PublishStatus
from app.domains.common import Page

router = APIRouter(tags=["admin:catalog"])


@router.get("/platforms")
async def list_platforms(service: PriceAdminServiceDep) -> ApiResponse[list[PlatformAdminOut]]:
    return ok(await service.platforms())


@router.get("/prices")
async def list_prices(
    service: PriceAdminServiceDep, query: Annotated[PriceListQuery, Query()]
) -> ApiResponse[Page[PriceAdminOut]]:
    return ok(await service.list(query))


@router.post("/prices")
async def save_price(body: PriceIn, service: PriceAdminServiceDep) -> ApiResponse[PriceAdminOut]:
    return ok(await service.save(body))


@router.post("/prices/{price_id}/hide")
async def hide_price(price_id: int, service: PriceAdminServiceDep) -> ApiResponse[PriceAdminOut]:
    return ok(await service.set_status(price_id, PublishStatus.HIDDEN))


@router.post("/prices/{price_id}/show")
async def show_price(price_id: int, service: PriceAdminServiceDep) -> ApiResponse[PriceAdminOut]:
    return ok(await service.set_status(price_id, PublishStatus.ACTIVE))
