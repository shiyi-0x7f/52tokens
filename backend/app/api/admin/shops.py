"""卡网店铺管理。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ShopAdminServiceDep
from app.core.response import ApiResponse, ok
from app.domains.common import Page
from app.domains.shops.admin import ShopSourceAdminOut, ShopSourceIn, ShopSourceListQuery
from app.domains.shops.sync import ShopSyncReport

router = APIRouter(prefix="/shop-sources", tags=["admin:shops"])


@router.get("")
async def list_shop_sources(
    service: ShopAdminServiceDep, query: Annotated[ShopSourceListQuery, Query()]
) -> ApiResponse[Page[ShopSourceAdminOut]]:
    return ok(await service.list(query))


@router.post("")
async def create_shop_source(
    body: ShopSourceIn, service: ShopAdminServiceDep
) -> ApiResponse[ShopSourceAdminOut]:
    return ok(await service.create(body))


@router.put("/{source_id}")
async def update_shop_source(
    source_id: int, body: ShopSourceIn, service: ShopAdminServiceDep
) -> ApiResponse[ShopSourceAdminOut]:
    return ok(await service.update(source_id, body))


@router.post("/{source_id}/sync")
async def sync_shop_source(
    source_id: int, service: ShopAdminServiceDep
) -> ApiResponse[ShopSyncReport]:
    """立即采集一个店铺（同步执行，ShopApi 商品多时可能要一两分钟）。"""
    return ok(await service.sync(source_id))
