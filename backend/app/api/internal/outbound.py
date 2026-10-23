"""出站跳转（公开站 /go/* 服务端专用）。"""

from fastapi import APIRouter

from app.api.deps import OutboundServiceDep
from app.core.response import ApiResponse, ok
from app.domains.outbound.schemas import ClickIn, RedirectOut

router = APIRouter(tags=["internal:outbound"])


@router.post("/outbound/deals/{slug}")
async def click_deal(
    slug: str, body: ClickIn, service: OutboundServiceDep
) -> ApiResponse[RedirectOut]:
    return ok(await service.click_deal(slug, body.referer_path))
