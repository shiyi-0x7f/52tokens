"""出站跳转：落地地址、点击记录、不可见活动。"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.deals.models import DealStatus
from app.domains.outbound.models import OutboundClick, OutboundTarget
from tests import factories as f
from tests.conftest import AUTH


async def _click(client: httpx.AsyncClient, slug: str, **body: str) -> httpx.Response:
    return await client.post(f"/internal/v1/outbound/deals/{slug}", json=body, headers=AUTH)


async def test_redirects_to_affiliate_link_and_records_click(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "aliyun")
    deal = await f.deal(db_session, p, "promoted", aff_url="https://aff.example.com/x")
    await db_session.commit()

    resp = await _click(db_client, "promoted", referer_path="/deals/promoted")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"url": "https://aff.example.com/x", "is_promoted": True}

    clicks = (await db_session.scalars(select(OutboundClick))).all()
    assert len(clicks) == 1
    assert clicks[0].target_type == OutboundTarget.DEAL
    assert clicks[0].target_id == deal.id
    assert clicks[0].target_url == "https://aff.example.com/x"
    assert clicks[0].is_promoted is True
    assert clicks[0].referer_path == "/deals/promoted"


async def test_without_affiliate_link_goes_to_source(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal(db_session, p, "plain", source_url="https://trae.example.com/events")
    await db_session.commit()

    data = (await _click(db_client, "plain")).json()["data"]
    assert data == {"url": "https://trae.example.com/events", "is_promoted": False}


async def test_source_link_scrolls_to_quote(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal(
        db_session, p, "quoted", source_url="https://trae.example.com/e", source_quote="签到"
    )
    await f.deal(db_session, p, "aff", aff_url="https://aff.example.com/x", source_quote="签到")
    await db_session.commit()

    quoted = (await _click(db_client, "quoted")).json()["data"]
    assert quoted["url"] == "https://trae.example.com/e#:~:text=%E7%AD%BE%E5%88%B0"
    # 推广链接不加定位片段
    assert (await _click(db_client, "aff")).json()["data"]["url"] == "https://aff.example.com/x"


async def test_hidden_deal_is_not_found_and_not_recorded(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "x")
    await f.deal(db_session, p, "pending", status=DealStatus.PENDING)
    await db_session.commit()

    assert (await _click(db_client, "pending")).status_code == 404
    assert (await _click(db_client, "missing")).status_code == 404
    assert (await db_session.scalars(select(OutboundClick))).all() == []


async def test_referer_path_length_is_validated(db_client: httpx.AsyncClient) -> None:
    resp = await _click(db_client, "any", referer_path="/" + "a" * 300)
    assert resp.status_code == 422


async def test_requires_internal_token(db_client: httpx.AsyncClient) -> None:
    resp = await db_client.post("/internal/v1/outbound/deals/any", json={})
    assert resp.status_code == 401
