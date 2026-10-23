"""测试数据工厂：默认生成「可对外展示」的数据，用参数覆盖出各种不可见情形。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.catalog.models import (
    AIModel,
    Currency,
    ModelPrice,
    Platform,
    PlatformCategory,
    PublishStatus,
)
from app.domains.deals.models import Deal, DealCycle, DealSource, DealStatus, DealType

NOW = datetime.now(UTC)


async def platform(session: AsyncSession, slug: str, **kw: Any) -> Platform:
    obj = Platform(
        slug=slug,
        name=kw.pop("name", slug.title()),
        category=kw.pop("category", PlatformCategory.LLM_API_CN),
        website_url=kw.pop("website_url", f"https://{slug}.example.com"),
        status=kw.pop("status", PublishStatus.ACTIVE),
        **kw,
    )
    session.add(obj)
    await session.flush()
    return obj


async def model(session: AsyncSession, slug: str, **kw: Any) -> AIModel:
    obj = AIModel(
        slug=slug,
        name=kw.pop("name", slug),
        family=kw.pop("family", slug.split("-")[0]),
        status=kw.pop("status", PublishStatus.ACTIVE),
        **kw,
    )
    session.add(obj)
    await session.flush()
    return obj


async def price(session: AsyncSession, plat: Platform, mdl: AIModel, **kw: Any) -> ModelPrice:
    obj = ModelPrice(
        platform_id=plat.id,
        model_id=mdl.id,
        currency=kw.pop("currency", Currency.CNY),
        input_price=kw.pop("input_price", Decimal("1.0000")),
        output_price=kw.pop("output_price", Decimal("2.0000")),
        source_url=kw.pop("source_url", f"{plat.website_url}/pricing"),
        confirmed_at=kw.pop("confirmed_at", NOW),
        status=kw.pop("status", PublishStatus.ACTIVE),
        **kw,
    )
    session.add(obj)
    await session.flush()
    return obj


async def deal(session: AsyncSession, plat: Platform, slug: str, **kw: Any) -> Deal:
    obj = Deal(
        slug=slug,
        platform_id=plat.id,
        title=kw.pop("title", f"{slug} 活动"),
        deal_type=kw.pop("deal_type", DealType.CHECKIN_POINTS),
        reward_text=kw.pop("reward_text", "+100 积分/天"),
        cycle=kw.pop("cycle", DealCycle.DAILY),
        source_url=kw.pop("source_url", f"{plat.website_url}/events"),
        confirmed_at=kw.pop("confirmed_at", NOW),
        status=kw.pop("status", DealStatus.ACTIVE),
        **kw,
    )
    session.add(obj)
    await session.flush()
    return obj


async def deal_source(session: AsyncSession, plat: Platform, **kw: Any) -> DealSource:
    obj = DealSource(
        platform_id=plat.id,
        url=kw.pop("url", f"{plat.website_url}/events"),
        label=kw.pop("label", "活动页"),
        **kw,
    )
    session.add(obj)
    await session.flush()
    return obj


def days(n: int) -> timedelta:
    return timedelta(days=n)
