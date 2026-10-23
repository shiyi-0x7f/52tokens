"""活动后台：录入、编辑与审核（发布 / 驳回 / 下线 / 重新核实）。

规则：
- 新建的活动一律是「待审核」，发布时才写入核实时间 confirmed_at；
- 发布、驳回、下线都记录操作人和时间；
- 推广链接（aff_url）只能由后台填写，页面会自动标注「推广」；
- 已发布过的活动不允许改 slug（会让已收录的页面 404）。
"""

import secrets
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.core.errors import AppError
from app.domains.catalog.models import Platform
from app.domains.common import Page, PageQuery
from app.domains.deals.models import Deal, DealCycle, DealOrigin, DealStatus, DealType
from app.domains.deals.repository import DealRepository

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$"


def new_deal_slug(platform_slug: str, deal_type: DealType) -> str:
    """自动生成的 slug：平台 + 类型 + 随机后缀。"""
    return f"{platform_slug}-{deal_type.value.replace('_', '-')}-{secrets.token_hex(3)}"


class PlatformBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str


class DealIn(BaseModel):
    """新建 / 编辑活动。slug 留空时自动生成。"""

    platform_id: int
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN)
    title: str = Field(min_length=2, max_length=200)
    deal_type: DealType
    reward_text: str = Field(min_length=1, max_length=100)
    est_value_cny: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    requirements: list[str] = Field(default_factory=list, max_length=8)
    cycle: DealCycle = DealCycle.ONCE
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    description: str = Field(default="", max_length=2000)
    source_url: HttpUrl
    aff_url: HttpUrl | None = None
    in_app_only: bool = False

    @field_validator("requirements")
    @classmethod
    def _clean_requirements(cls, value: list[str]) -> list[str]:
        items = [v.strip() for v in value if v.strip()]
        if any(len(v) > 40 for v in items):
            raise ValueError("每项门槛不超过 40 个字")
        return items


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class DealAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    platform: PlatformBrief
    title: str
    deal_type: DealType
    reward_text: str
    est_value_cny: Decimal | None
    requirements: list[str]
    cycle: DealCycle
    starts_at: datetime | None
    ends_at: datetime | None
    description: str
    source_url: str
    aff_url: str | None
    in_app_only: bool
    status: DealStatus
    confirmed_at: datetime | None
    reviewed_at: datetime | None
    reject_reason: str
    origin: DealOrigin
    extract_confidence: Decimal | None
    extract_note: str
    created_at: datetime
    updated_at: datetime


class DealListQuery(PageQuery):
    status: DealStatus | None = None
    platform_id: int | None = None
    q: str | None = Field(default=None, max_length=50)


class DealAdminService:
    def __init__(self, repo: DealRepository) -> None:
        self.repo = repo

    async def _deal(self, deal_id: int) -> Deal:
        deal = await self.repo.get(deal_id)
        if deal is None:
            raise AppError("NOT_FOUND", "活动不存在")
        return deal

    async def _platform(self, platform_id: int) -> Platform:
        platform = await self.repo.get_platform(platform_id)
        if platform is None:
            raise AppError("BAD_REQUEST", "平台不存在")
        return platform

    async def _out(self, deal_id: int) -> DealAdminOut:
        return DealAdminOut.model_validate(await self._deal(deal_id))

    async def list(self, query: DealListQuery) -> Page[DealAdminOut]:
        rows, total = await self.repo.list_all(
            status=query.status,
            platform_id=query.platform_id,
            q=query.q,
            offset=query.offset,
            limit=query.page_size,
        )
        return Page(
            items=[DealAdminOut.model_validate(d) for d in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def get(self, deal_id: int) -> DealAdminOut:
        return await self._out(deal_id)

    @staticmethod
    def _apply(deal: Deal, data: DealIn) -> None:
        if data.ends_at and data.starts_at and data.ends_at <= data.starts_at:
            raise AppError("BAD_REQUEST", "截止时间必须晚于开始时间")
        deal.platform_id = data.platform_id
        deal.title = data.title.strip()
        deal.deal_type = data.deal_type
        deal.reward_text = data.reward_text.strip()
        deal.est_value_cny = data.est_value_cny
        deal.requirements = data.requirements
        deal.cycle = data.cycle
        deal.starts_at = data.starts_at
        deal.ends_at = data.ends_at
        deal.description = data.description.strip()
        deal.source_url = str(data.source_url)
        deal.aff_url = str(data.aff_url) if data.aff_url else None
        deal.in_app_only = data.in_app_only

    async def create(self, data: DealIn) -> DealAdminOut:
        platform = await self._platform(data.platform_id)
        slug = data.slug or new_deal_slug(platform.slug, data.deal_type)
        if await self.repo.slug_taken(slug):
            raise AppError("CONFLICT", "slug 已被占用")
        deal = Deal(slug=slug, status=DealStatus.PENDING)
        self._apply(deal, data)
        await self.repo.add(deal)
        await self.repo.commit()
        return await self._out(deal.id)

    async def update(self, deal_id: int, data: DealIn) -> DealAdminOut:
        deal = await self._deal(deal_id)
        await self._platform(data.platform_id)
        if data.slug and data.slug != deal.slug:
            if deal.confirmed_at is not None:
                raise AppError("BAD_REQUEST", "已发布过的活动不能修改 slug")
            if await self.repo.slug_taken(data.slug, exclude_id=deal_id):
                raise AppError("CONFLICT", "slug 已被占用")
            deal.slug = data.slug
        self._apply(deal, data)
        await self.repo.commit()
        return await self._out(deal_id)

    async def _review(
        self, deal: Deal, status: DealStatus, reviewer_id: int, *, reason: str = ""
    ) -> DealAdminOut:
        now = datetime.now(UTC)
        deal.status = status
        deal.reviewed_by_id = reviewer_id
        deal.reviewed_at = now
        deal.reject_reason = reason
        if status == DealStatus.ACTIVE:
            deal.confirmed_at = now
        await self.repo.commit()
        return await self._out(deal.id)

    async def publish(self, deal_id: int, reviewer_id: int) -> DealAdminOut:
        deal = await self._deal(deal_id)
        if deal.ends_at is not None and deal.ends_at <= datetime.now(UTC):
            raise AppError("BAD_REQUEST", "活动已过截止时间，不能发布")
        return await self._review(deal, DealStatus.ACTIVE, reviewer_id)

    async def reject(self, deal_id: int, reviewer_id: int, reason: str) -> DealAdminOut:
        deal = await self._deal(deal_id)
        return await self._review(deal, DealStatus.REJECTED, reviewer_id, reason=reason.strip())

    async def expire(self, deal_id: int, reviewer_id: int) -> DealAdminOut:
        deal = await self._deal(deal_id)
        if deal.status != DealStatus.ACTIVE:
            raise AppError("BAD_REQUEST", "只有已发布的活动可以标记结束")
        return await self._review(deal, DealStatus.EXPIRED, reviewer_id)

    async def reconfirm(self, deal_id: int) -> DealAdminOut:
        """已发布的活动重新去官网核实一遍：只刷新核实时间。"""
        deal = await self._deal(deal_id)
        if deal.status != DealStatus.ACTIVE:
            raise AppError("BAD_REQUEST", "只有已发布的活动可以重新核实")
        deal.confirmed_at = datetime.now(UTC)
        await self.repo.commit()
        return await self._out(deal_id)
