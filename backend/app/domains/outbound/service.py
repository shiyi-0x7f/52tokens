"""出站跳转：解析落地地址并记录点击。落地地址每次按当前数据计算，改了推广链接立即生效。"""

from app.core.errors import AppError
from app.domains.deals.repository import DealRepository
from app.domains.outbound.models import OutboundClick, OutboundTarget
from app.domains.outbound.repository import OutboundRepository
from app.domains.outbound.schemas import RedirectOut


class OutboundService:
    def __init__(self, deals: DealRepository, clicks: OutboundRepository) -> None:
        self.deals = deals
        self.clicks = clicks

    async def click_deal(self, slug: str, referer_path: str) -> RedirectOut:
        deal = await self.deals.get_public(slug)
        if deal is None:
            raise AppError("NOT_FOUND")
        out = RedirectOut(url=deal.aff_url or deal.source_url, is_promoted=deal.aff_url is not None)
        await self.clicks.add_click(
            OutboundClick(
                target_type=OutboundTarget.DEAL,
                target_id=deal.id,
                target_url=out.url,
                is_promoted=out.is_promoted,
                referer_path=referer_path,
            )
        )
        return out
