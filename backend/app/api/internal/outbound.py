"""出站跳转（公开站 /go/* 服务端专用）：记一次点击并返回落地地址。"""

from fastapi import APIRouter

from app.api.deps import OutboundServiceDep
from app.core.response import ApiResponse, ok
from app.domains.outbound.schemas import ClickIn, RedirectOut

router = APIRouter(prefix="/outbound", tags=["internal:outbound"])


@router.post("/deals/{slug}")
async def click_deal(
    slug: str, body: ClickIn, service: OutboundServiceDep
) -> ApiResponse[RedirectOut]:
    return ok(await service.click_deal(slug, body.referer_path))


@router.post("/offers/{token}")
async def click_offer(
    token: str, body: ClickIn, service: OutboundServiceDep
) -> ApiResponse[RedirectOut]:
    return ok(await service.click_offer(token, body.referer_path))
