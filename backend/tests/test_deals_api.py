"""活动接口：可见性、过期下沉、推广链接标注、筛选。"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.catalog.models import PublishStatus
from app.domains.deals.models import DealStatus, DealType
from tests import factories as f
from tests.conftest import AUTH


async def _slugs(client: httpx.AsyncClient, **params: str) -> list[str]:
    resp = await client.get("/internal/v1/deals", params=params, headers=AUTH)
    assert resp.status_code == 200
    return [d["slug"] for d in resp.json()["data"]]


async def test_hidden_deals_are_not_listed(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    draft_plat = await f.platform(db_session, "draftco", status=PublishStatus.DRAFT)
    await f.deal(db_session, p, "visible")
    await f.deal(db_session, p, "pending", status=DealStatus.PENDING)
    await f.deal(db_session, p, "rejected", status=DealStatus.REJECTED)
    await f.deal(db_session, p, "unconfirmed", confirmed_at=None)
    await f.deal(db_session, draft_plat, "on-draft-platform")
    await db_session.commit()

    assert await _slugs(db_client) == ["visible"]


async def test_expired_excluded_by_default_and_sunk_when_included(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "qoder")
    await f.deal(db_session, p, "ended-by-status", status=DealStatus.EXPIRED)
    await f.deal(db_session, p, "ended-by-date", ends_at=f.NOW - f.days(1))
    await f.deal(
        db_session, p, "running", ends_at=f.NOW + f.days(3), confirmed_at=f.NOW - f.days(2)
    )
    await db_session.commit()

    assert await _slugs(db_client) == ["running"]
    with_expired = await _slugs(db_client, include_expired="true")
    assert with_expired[0] == "running"
    assert set(with_expired[1:]) == {"ended-by-status", "ended-by-date"}


async def test_affiliate_link_is_flagged(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "aliyun")
    await f.deal(db_session, p, "plain")
    await f.deal(db_session, p, "promoted", aff_url="https://aff.example.com/x")
    await db_session.commit()

    plain = (await db_client.get("/internal/v1/deals/plain", headers=AUTH)).json()["data"]
    assert plain["is_promoted"] is False

    assert plain["link_host"] == "aliyun.example.com"

    promoted = (await db_client.get("/internal/v1/deals/promoted", headers=AUTH)).json()["data"]
    assert promoted["is_promoted"] is True
    assert promoted["link_host"] == "aff.example.com"
    # 推广链接不随活动数据下发，只能经出站跳转拿到
    assert "https://aff.example.com/x" not in str(promoted)


async def test_detail_includes_steps_and_locate_url(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal(db_session, p, "guided", steps=["打开客户端", "点签到"], source_quote="每日签到")
    await f.deal(db_session, p, "bare")
    await db_session.commit()

    guided = (await db_client.get("/internal/v1/deals/guided", headers=AUTH)).json()["data"]
    assert guided["steps"] == ["打开客户端", "点签到"]
    assert guided["source_quote"] == "每日签到"
    assert guided["source_locate_url"].startswith(guided["source_url"] + "#:~:text=")

    bare = (await db_client.get("/internal/v1/deals/bare", headers=AUTH)).json()["data"]
    assert bare["steps"] == []
    assert bare["source_locate_url"] == bare["source_url"]


async def test_filters_by_type_and_platform(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    trae = await f.platform(db_session, "trae")
    bailian = await f.platform(db_session, "bailian")
    await f.deal(db_session, trae, "trae-checkin")
    await f.deal(db_session, bailian, "bailian-signup", deal_type=DealType.SIGNUP_CREDIT)
    await db_session.commit()

    assert await _slugs(db_client, deal_type="signup_credit") == ["bailian-signup"]
    assert await _slugs(db_client, platform="trae") == ["trae-checkin"]


async def test_deal_detail_not_found_when_hidden(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "x")
    await f.deal(db_session, p, "pending", status=DealStatus.PENDING)
    await db_session.commit()
    resp = await db_client.get("/internal/v1/deals/pending", headers=AUTH)
    assert resp.status_code == 404


async def test_list_limit_is_validated(db_client: httpx.AsyncClient) -> None:
    resp = await db_client.get("/internal/v1/deals", params={"limit": "1000"}, headers=AUTH)
    assert resp.status_code == 422
