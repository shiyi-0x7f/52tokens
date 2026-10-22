"""活动（公开站服务端专用）。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DealServiceDep
from app.core.response import ApiResponse, ok
from app.domains.deals.models import DealType
from app.domains.deals.schemas import DealOut
from app.domains.deals.service import MAX_LIST_LIMIT

router = APIRouter(tags=["internal:deals"])


@router.get("/deals")
async def list_deals(
    service: DealServiceDep,
    deal_type: DealType | None = None,
    platform: str | None = None,
    include_expired: bool = False,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = 50,
) -> ApiResponse[list[DealOut]]:
    return ok(
        await service.list_deals(
            deal_type=deal_type,
            platform_slug=platform,
            include_expired=include_expired,
            limit=limit,
        )
    )


@router.get("/deals/{slug}")
async def get_deal(slug: str, service: DealServiceDep) -> ApiResponse[DealOut]:
    return ok(await service.get_deal(slug))
