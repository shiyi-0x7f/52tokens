"""活动的录入与审核。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminDep, DealAdminServiceDep
from app.core.response import ApiResponse, ok
from app.domains.common import Page
from app.domains.deals.admin import DealAdminOut, DealIn, DealListQuery, RejectIn

router = APIRouter(prefix="/deals", tags=["admin:deals"])


@router.get("")
async def list_deals(
    service: DealAdminServiceDep, query: Annotated[DealListQuery, Query()]
) -> ApiResponse[Page[DealAdminOut]]:
    return ok(await service.list(query))


@router.get("/{deal_id}")
async def get_deal(deal_id: int, service: DealAdminServiceDep) -> ApiResponse[DealAdminOut]:
    return ok(await service.get(deal_id))


@router.post("")
async def create_deal(body: DealIn, service: DealAdminServiceDep) -> ApiResponse[DealAdminOut]:
    return ok(await service.create(body))


@router.put("/{deal_id}")
async def update_deal(
    deal_id: int, body: DealIn, service: DealAdminServiceDep
) -> ApiResponse[DealAdminOut]:
    return ok(await service.update(deal_id, body))


@router.post("/{deal_id}/publish")
async def publish_deal(
    deal_id: int, service: DealAdminServiceDep, user: AdminDep
) -> ApiResponse[DealAdminOut]:
    return ok(await service.publish(deal_id, user.id))


@router.post("/{deal_id}/reject")
async def reject_deal(
    deal_id: int, body: RejectIn, service: DealAdminServiceDep, user: AdminDep
) -> ApiResponse[DealAdminOut]:
    return ok(await service.reject(deal_id, user.id, body.reason))


@router.post("/{deal_id}/expire")
async def expire_deal(
    deal_id: int, service: DealAdminServiceDep, user: AdminDep
) -> ApiResponse[DealAdminOut]:
    return ok(await service.expire(deal_id, user.id))


@router.post("/{deal_id}/reconfirm")
async def reconfirm_deal(deal_id: int, service: DealAdminServiceDep) -> ApiResponse[DealAdminOut]:
    return ok(await service.reconfirm(deal_id))
