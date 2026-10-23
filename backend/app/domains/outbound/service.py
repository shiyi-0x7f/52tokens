"""出站跳转：解析落地地址并记录点击。落地地址每次按当前数据计算，改了推广链接立即生效。"""

from app.core.errors import AppError
from app.domains.deals.links import locate_url
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
        # 直接去官网时带上原文定位片段；推广链接落地页由对方决定，不加
        url = deal.aff_url or locate_url(deal.source_url, deal.source_quote)
        out = RedirectOut(url=url, is_promoted=deal.aff_url is not None)
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
