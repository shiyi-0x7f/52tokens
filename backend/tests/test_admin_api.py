"""后台接口：鉴权（会话 + 管理员 + CSRF 头）、活动审核流程、价格手工录入。"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests import factories as f
from tests.conftest import AUTH, CSRF
from tests.conftest import login as _login
from tests.fakes import MemoryStore


def _deal_body(platform_id: int, **over: Any) -> dict[str, Any]:
    return {
        "platform_id": platform_id,
        "title": "每日签到送积分",
        "deal_type": "checkin_points",
        "reward_text": "+200 积分/天",
        "cycle": "daily",
        "requirements": [" 需登录 ", ""],
        "source_url": "https://www.trae.ai/events",
        "in_app_only": True,
    } | over


# ---------- 鉴权 ----------


async def test_requires_session(db_client: httpx.AsyncClient, store: MemoryStore) -> None:
    resp = await db_client.get("/api/admin/me")
    assert resp.status_code == 401


async def test_non_admin_is_forbidden(
    db_session: AsyncSession, db_client: httpx.AsyncClient, store: MemoryStore
) -> None:
    await _login(db_session, store, db_client, admin=False)
    resp = await db_client.get("/api/admin/me")
    assert resp.status_code == 403


async def test_write_requires_csrf_header(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    await db_session.commit()
    resp = await admin.post("/api/admin/deals", json=_deal_body(p.id))
    assert resp.status_code == 403
    assert (await admin.get("/api/admin/me")).json()["data"]["is_admin"] is True


# ---------- 活动审核流程 ----------


async def test_deal_review_flow_makes_deal_public(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "trae")
    await db_session.commit()

    created = (await admin.post("/api/admin/deals", json=_deal_body(p.id), headers=CSRF)).json()
    deal = created["data"]
    assert deal["status"] == "pending"
    assert deal["confirmed_at"] is None
    assert deal["requirements"] == ["需登录"]
    assert deal["slug"].startswith("trae-checkin-points-")

    # 待审核时公开接口看不到
    public = await admin.get("/internal/v1/deals", headers=AUTH)
    assert public.json()["data"] == []

    published = (await admin.post(f"/api/admin/deals/{deal['id']}/publish", headers=CSRF)).json()[
        "data"
    ]
    assert published["status"] == "active"
    assert published["confirmed_at"] is not None
    assert published["reviewed_at"] is not None

    public = (await admin.get("/internal/v1/deals", headers=AUTH)).json()["data"]
    assert [d["slug"] for d in public] == [deal["slug"]]

    expired = (await admin.post(f"/api/admin/deals/{deal['id']}/expire", headers=CSRF)).json()
    assert expired["data"]["status"] == "expired"


async def test_reject_records_reason_and_list_filters(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "qoder")
    await db_session.commit()
    deal_id = (await admin.post("/api/admin/deals", json=_deal_body(p.id), headers=CSRF)).json()[
        "data"
    ]["id"]
    await admin.post("/api/admin/deals", json=_deal_body(p.id, title="另一个活动"), headers=CSRF)

    rejected = await admin.post(
        f"/api/admin/deals/{deal_id}/reject", json={"reason": "官网找不到这个活动"}, headers=CSRF
    )
    assert rejected.json()["data"]["reject_reason"] == "官网找不到这个活动"

    pending = (await admin.get("/api/admin/deals", params={"status": "pending"})).json()["data"]
    assert pending["total"] == 1
    assert pending["items"][0]["title"] == "另一个活动"
    searched = (await admin.get("/api/admin/deals", params={"q": "另一个"})).json()["data"]
    assert searched["total"] == 1


async def test_cannot_publish_past_deadline_or_rename_published(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "x")
    await db_session.commit()
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    old = (
        await admin.post("/api/admin/deals", json=_deal_body(p.id, ends_at=past), headers=CSRF)
    ).json()["data"]
    resp = await admin.post(f"/api/admin/deals/{old['id']}/publish", headers=CSRF)
    assert resp.status_code == 400

    live = (await admin.post("/api/admin/deals", json=_deal_body(p.id), headers=CSRF)).json()
    live_id = live["data"]["id"]
    await admin.post(f"/api/admin/deals/{live_id}/publish", headers=CSRF)
    resp = await admin.put(
        f"/api/admin/deals/{live_id}", json=_deal_body(p.id, slug="new-slug-1"), headers=CSRF
    )
    assert resp.status_code == 400


async def test_deal_validation(db_session: AsyncSession, admin: httpx.AsyncClient) -> None:
    p = await f.platform(db_session, "x")
    await db_session.commit()
    bad_url = await admin.post(
        "/api/admin/deals", json=_deal_body(p.id, source_url="javascript:alert(1)"), headers=CSRF
    )
    assert bad_url.status_code == 422
    no_platform = await admin.post("/api/admin/deals", json=_deal_body(9999), headers=CSRF)
    assert no_platform.status_code == 400


# ---------- 价格录入 ----------


async def test_save_price_creates_model_and_publishes(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    p = await f.platform(db_session, "deepseek")
    await db_session.commit()
    body = {
        "platform_id": p.id,
        "model_slug": "deepseek-chat",
        "model_name": "DeepSeek V3",
        "family": "deepseek",
        "currency": "CNY",
        "input_price": "2",
        "output_price": "8",
        "source_url": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing",
    }
    saved = (await admin.post("/api/admin/prices", json=body, headers=CSRF)).json()["data"]
    assert saved["status"] == "active"
    assert saved["confirmed_at"] is not None
    assert saved["model"]["name"] == "DeepSeek V3"

    # 同一（平台, 模型）再次保存是更新而不是新增
    again = (
        await admin.post("/api/admin/prices", json=body | {"output_price": "3"}, headers=CSRF)
    ).json()["data"]
    assert again["id"] == saved["id"]

    public = (await admin.get("/internal/v1/models/deepseek-chat", headers=AUTH)).json()["data"]
    assert public["prices"][0]["output_price"] == "3.0000"

    hidden = (await admin.post(f"/api/admin/prices/{saved['id']}/hide", headers=CSRF)).json()
    assert hidden["data"]["status"] == "hidden"
    assert (await admin.get("/internal/v1/models/deepseek-chat", headers=AUTH)).status_code == 200


async def test_price_validation(db_session: AsyncSession, admin: httpx.AsyncClient) -> None:
    p = await f.platform(db_session, "kimi")
    await db_session.commit()
    base = {"platform_id": p.id, "model_slug": "kimi-k2", "source_url": "https://x.com"}
    missing_price = await admin.post("/api/admin/prices", json=base, headers=CSRF)
    assert missing_price.status_code == 422
    new_model_without_name = await admin.post(
        "/api/admin/prices",
        json=base | {"input_price": "1", "output_price": "2"},
        headers=CSRF,
    )
    assert new_model_without_name.status_code == 400
