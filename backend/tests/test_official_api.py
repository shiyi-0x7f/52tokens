"""官方订阅地区价：最便宜地区、相对美区百分比、未上架地区。"""

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.official.models import OfficialPlan, OfficialRegionPrice
from tests.conftest import AUTH

FETCHED = datetime(2026, 7, 24, 5, 52, tzinfo=UTC)


def _price(
    plan: OfficialPlan, code: str, label: str, cny: str | None, status: str = "available"
) -> OfficialRegionPrice:
    return OfficialRegionPrice(
        plan_id=plan.id,
        country_code=code,
        country_label=label,
        currency="X",
        price_text=f"{label} 价",
        price_value=None if cny is None else Decimal(cny),
        cny_price=None if cny is None else Decimal(cny),
        fx_date=date(2026, 7, 24),
        source_url=f"https://apps.apple.com/{code.lower()}/app/chatgpt/id1",
        status=status,
        fetched_at=FETCHED,
    )


async def _setup(session: AsyncSession) -> None:
    plan = OfficialPlan(
        app_slug="chatgpt",
        app_name="ChatGPT",
        provider="OpenAI",
        plan_slug="plus-monthly",
        plan_name="ChatGPT Plus",
        billing_period="monthly",
    )
    session.add(plan)
    await session.flush()
    session.add_all(
        [
            _price(plan, "US", "美国", "135.66"),
            _price(plan, "TR", "土耳其", "67.83"),
            _price(plan, "NG", "尼日利亚", "40.00"),
            _price(plan, "CN", "中国大陆", None, status="missing"),
        ]
    )
    await session.commit()


async def test_list_shows_us_and_cheapest(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    await _setup(db_session)
    data = (await db_client.get("/internal/v1/official-plans", headers=AUTH)).json()["data"]
    plan = data[0]
    assert plan["plan_name"] == "ChatGPT Plus"
    assert plan["us"]["cny_price"] == "135.66"
    assert plan["cheapest"]["country_label"] == "尼日利亚"
    assert plan["cheapest"]["vs_us_percent"] == 29
    assert plan["region_count"] == 3


async def test_detail_sorted_with_missing_regions(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    await _setup(db_session)
    resp = await db_client.get("/internal/v1/official-plans/chatgpt/plus-monthly", headers=AUTH)
    data = resp.json()["data"]
    assert [p["country_code"] for p in data["prices"]] == ["NG", "TR", "US"]
    assert [p["vs_us_percent"] for p in data["prices"]] == [29, 50, 100]
    assert data["missing_regions"] == ["中国大陆"]
    assert data["fetched_at"].startswith("2026-07-24")

    missing = await db_client.get("/internal/v1/official-plans/chatgpt/nope", headers=AUTH)
    assert missing.status_code == 404
