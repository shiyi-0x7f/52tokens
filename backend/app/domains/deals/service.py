"""活动域业务规则：过期判定、推广链接标注。"""

from datetime import UTC, datetime

from app.core.errors import AppError
from app.domains.catalog.schemas import PlatformRef
from app.domains.deals.models import Deal, DealStatus, DealType
from app.domains.deals.repository import DealRepository
from app.domains.deals.schemas import DealOut

MAX_LIST_LIMIT = 100


def is_expired(deal: Deal, now: datetime) -> bool:
    """状态已标为结束，或截止时间已过（不等定时任务改状态）。"""
    return deal.status == DealStatus.EXPIRED or (deal.ends_at is not None and deal.ends_at <= now)


def to_out(deal: Deal, now: datetime) -> DealOut:
    if deal.confirmed_at is None:
        raise ValueError("未核实的活动不能对外输出")  # 仓储层已过滤，正常不会走到
    return DealOut(
        slug=deal.slug,
        title=deal.title,
        deal_type=deal.deal_type,
        platform=PlatformRef.model_validate(deal.platform),
        reward_text=deal.reward_text,
        est_value_cny=deal.est_value_cny,
        requirements=list(deal.requirements),
        cycle=deal.cycle,
        starts_at=deal.starts_at,
        ends_at=deal.ends_at,
        description=deal.description,
        is_promoted=deal.aff_url is not None,
        source_url=deal.source_url,
        in_app_only=deal.in_app_only,
        confirmed_at=deal.confirmed_at,
        is_expired=is_expired(deal, now),
    )


class DealService:
    def __init__(self, repo: DealRepository) -> None:
        self.repo = repo

    async def list_deals(
        self,
        *,
        deal_type: DealType | None,
        platform_slug: str | None,
        include_expired: bool,
        limit: int,
    ) -> list[DealOut]:
        now = datetime.now(UTC)
        deals = await self.repo.list_public(
            deal_type=deal_type,
            platform_slug=platform_slug,
            include_expired=include_expired,
            now=now,
            limit=min(limit, MAX_LIST_LIMIT),
        )
        items = [to_out(d, now) for d in deals]
        # 进行中的排前面，已结束的下沉
        return sorted(items, key=lambda d: d.is_expired)

    async def get_deal(self, slug: str) -> DealOut:
        deal = await self.repo.get_public(slug)
        if deal is None:
            raise AppError("NOT_FOUND")
        return to_out(deal, datetime.now(UTC))
