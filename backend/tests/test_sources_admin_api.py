"""后台监测来源：增删改查、URL 去重、改地址清 hash、立即检查。"""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_http
from app.domains.deals.models import DealOrigin
from tests import factories as f
from tests.conftest import CSRF
from tests.fakes import MemoryStore


@pytest.fixture(autouse=True)
async def page_http(app: FastAPI) -> AsyncIterator[None]:
    """测试客户端不跑 lifespan，没有共享 http 客户端：换成返回一个正文足够长的静态页。"""
    text = "每日签到送 200 积分，积分当天有效。" * 20
    html = f"<html><body><article><p>{text}</p></article></body></html>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, html=html))
    ) as http:
        app.dependency_overrides[get_http] = lambda: http
        yield


async def test_source_crud(db_session: AsyncSession, admin: httpx.AsyncClient) -> None:
    p = await f.platform(db_session, "trae")
    q = await f.platform(db_session, "qoder")
    await db_session.commit()

    body = {"platform_id": p.id, "url": "https://www.trae.ai/events", "label": " 活动页 "}
    created = (await admin.post("/api/admin/sources", json=body, headers=CSRF)).json()["data"]
    assert created["platform"]["slug"] == "trae"
    assert created["label"] == "活动页"
    assert created["enabled"] is True

    dup = await admin.post("/api/admin/sources", json=body, headers=CSRF)
    assert dup.status_code == 409

    listed = (await admin.get("/api/admin/sources", params={"platform_id": p.id})).json()["data"]
    assert listed["total"] == 1

    updated = (
        await admin.put(
            f"/api/admin/sources/{created['id']}",
            json=body | {"platform_id": q.id, "enabled": False},
            headers=CSRF,
        )
    ).json()["data"]
    assert updated["platform"]["slug"] == "qoder"
    assert updated["enabled"] is False

    deleted = await admin.delete(f"/api/admin/sources/{created['id']}", headers=CSRF)
    assert deleted.status_code == 200
    assert (await admin.get("/api/admin/sources")).json()["data"]["total"] == 0


async def test_source_validation(db_session: AsyncSession, admin: httpx.AsyncClient) -> None:
    p = await f.platform(db_session, "trae")
    await db_session.commit()
    bad_url = await admin.post(
        "/api/admin/sources", json={"platform_id": p.id, "url": "ftp://x"}, headers=CSRF
    )
    assert bad_url.status_code == 422
    no_platform = await admin.post(
        "/api/admin/sources",
        json={"platform_id": 9999, "url": "https://x.example.com"},
        headers=CSRF,
    )
    assert no_platform.status_code == 400
    missing = await admin.post("/api/admin/sources/9999/check", headers=CSRF)
    assert missing.status_code == 404


async def test_check_now_without_llm_key_reports_reason(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    src = await f.deal_source(db_session, p)
    await db_session.commit()

    report = (await admin.post(f"/api/admin/sources/{src.id}/check", headers=CSRF)).json()["data"]
    assert report["status"] == "failed"
    assert "SILICONFLOW_API_KEY" in report["error"]

    listed = (await admin.get("/api/admin/sources")).json()["data"]["items"][0]
    assert listed["fail_count"] == 1
    assert listed["checked_at"] is not None


async def test_deal_admin_shows_origin(db_session: AsyncSession, admin: httpx.AsyncClient) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal(db_session, p, "collected", origin=DealOrigin.COLLECTOR, extract_note="原文")
    await db_session.commit()
    item = (await admin.get("/api/admin/deals", params={"status": "active"})).json()["data"][
        "items"
    ][0]
    assert item["origin"] == "collector"
    assert item["extract_note"] == "原文"


async def test_sources_require_admin(db_client: httpx.AsyncClient, store: MemoryStore) -> None:
    assert (await db_client.get("/api/admin/sources")).status_code == 401
