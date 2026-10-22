"""目录接口：只展示已发布 + 已核实的价格，平台下线时价格一并隐藏。"""

from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.catalog.models import Currency, PlatformCategory, PublishStatus
from tests import factories as f
from tests.conftest import AUTH


async def test_models_list_applies_visibility_rules(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    ds = await f.platform(db_session, "deepseek")
    sf = await f.platform(db_session, "siliconflow")
    hidden_plat = await f.platform(db_session, "hiddenco", status=PublishStatus.DRAFT)

    v3 = await f.model(db_session, "deepseek-v3")
    await f.price(db_session, ds, v3, output_price=Decimal("3.0000"))
    await f.price(db_session, sf, v3, output_price=Decimal("2.5000"))
    await f.price(db_session, hidden_plat, v3, output_price=Decimal("0.1000"))  # 平台未发布

    unconfirmed = await f.model(db_session, "qwen-unconfirmed")
    await f.price(db_session, ds, unconfirmed, confirmed_at=None)  # 未核实

    drafted = await f.model(db_session, "glm-draft-price")
    await f.price(db_session, ds, drafted, status=PublishStatus.DRAFT)  # 价格未发布

    draft_model = await f.model(db_session, "kimi-draft", status=PublishStatus.DRAFT)
    await f.price(db_session, ds, draft_model)  # 模型未发布
    await db_session.commit()

    resp = await db_client.get("/internal/v1/models", headers=AUTH)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert [m["slug"] for m in items] == ["deepseek-v3"]
    assert items[0]["price_count"] == 2
    assert Decimal(items[0]["min_output_price_cny"]) == Decimal("2.5")


async def test_min_price_ignores_other_currencies_and_flags_free(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    a = await f.platform(db_session, "a")
    b = await f.platform(db_session, "b")
    m = await f.model(db_session, "glm-flash")
    await f.price(db_session, a, m, currency=Currency.USD, output_price=Decimal("0.1000"))
    await f.price(
        db_session, b, m, is_free=True, input_price=None, output_price=None, free_note="限 30 并发"
    )
    await db_session.commit()

    item = (await db_client.get("/internal/v1/models", headers=AUTH)).json()["data"][0]
    assert item["min_output_price_cny"] is None
    assert item["has_free"] is True


async def test_model_detail_sorts_free_first_then_cheapest(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    pricey = await f.platform(db_session, "pricey")
    cheap = await f.platform(db_session, "cheap")
    free = await f.platform(db_session, "free")
    m = await f.model(db_session, "qwen-30b")
    await f.price(db_session, pricey, m, output_price=Decimal("9.0000"))
    await f.price(db_session, cheap, m, output_price=Decimal("1.0000"))
    await f.price(db_session, free, m, is_free=True, output_price=None)
    await db_session.commit()

    resp = await db_client.get("/internal/v1/models/qwen-30b", headers=AUTH)
    assert resp.status_code == 200
    assert [p["platform"]["slug"] for p in resp.json()["data"]["prices"]] == [
        "free",
        "cheap",
        "pricey",
    ]


async def test_model_detail_not_found_for_unknown_or_draft(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    await f.model(db_session, "draft-model", status=PublishStatus.DRAFT)
    await db_session.commit()
    for slug in ("nope", "draft-model"):
        resp = await db_client.get(f"/internal/v1/models/{slug}", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["code"] == 40400


async def test_platforms_filter_by_category(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    await f.platform(db_session, "trae", category=PlatformCategory.CODING_TOOL)
    await f.platform(db_session, "bailian")
    await f.platform(db_session, "draftco", status=PublishStatus.DRAFT)
    await db_session.commit()

    all_items = (await db_client.get("/internal/v1/platforms", headers=AUTH)).json()["data"]
    assert {p["slug"] for p in all_items} == {"trae", "bailian"}
    coding = (
        await db_client.get(
            "/internal/v1/platforms", params={"category": "coding_tool"}, headers=AUTH
        )
    ).json()["data"]
    assert [p["slug"] for p in coding] == ["trae"]


async def test_catalog_requires_internal_token(db_client: httpx.AsyncClient) -> None:
    assert (await db_client.get("/internal/v1/models")).status_code == 401
