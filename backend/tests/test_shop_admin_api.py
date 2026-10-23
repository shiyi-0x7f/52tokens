"""后台卡网店铺：登记（含多商户地址）、去重、筛选、立即采集。"""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import get_http
from app.collectors.shops import base as shop_base
from tests.conftest import CSRF
from tests.fakes import MemoryStore


@pytest.fixture(autouse=True)
async def shop_http(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """测试客户端不跑 lifespan：换成一个返回 Kami 商品列表的假店铺。"""
    monkeypatch.setattr(shop_base, "PAGE_DELAY_SECONDS", 0)
    goods = [{"id": 1, "name": "ChatGPT Plus 成品号 独享账号", "price": "99", "stock": 3}]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/api/index/commodity":
            return httpx.Response(200, json={"data": goods})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_http] = lambda: http
        yield


async def test_register_merchant_and_sync(admin: httpx.AsyncClient) -> None:
    body = {"entry_url": "https://kami.test/", "collector_kind": "kami", "name": " 店 "}
    created = (await admin.post("/api/admin/shop-sources", json=body, headers=CSRF)).json()["data"]
    assert created["entry_url"] == "https://kami.test"
    assert created["host"] == "kami.test"
    assert created["fail_count"] == 0

    dup = await admin.post("/api/admin/shop-sources", json=body, headers=CSRF)
    assert dup.status_code == 409

    report = (
        await admin.post(f"/api/admin/shop-sources/{created['id']}/sync", headers=CSRF)
    ).json()["data"]
    assert (report["status"], report["offers"]) == ("synced", 1)

    ok_rows = (await admin.get("/api/admin/shop-sources", params={"state": "ok"})).json()["data"]
    assert ok_rows["total"] == 1
    assert ok_rows["items"][0]["offer_count"] == 1


async def test_multi_merchant_platform_allows_several_shops_per_host(
    admin: httpx.AsyncClient,
) -> None:
    for token in ("a", "b"):
        body = {"entry_url": f"https://pay.test/shop/{token}", "collector_kind": "shopApi"}
        resp = await admin.post("/api/admin/shop-sources", json=body, headers=CSRF)
        assert resp.status_code == 200
    rows = (await admin.get("/api/admin/shop-sources", params={"q": "pay.test"})).json()["data"]
    assert rows["total"] == 2


async def test_failed_sync_is_reported(admin: httpx.AsyncClient) -> None:
    body = {"entry_url": "https://dj.test", "collector_kind": "dujiao"}  # 假店铺没有独角数卡接口
    created = (await admin.post("/api/admin/shop-sources", json=body, headers=CSRF)).json()["data"]
    report = (
        await admin.post(f"/api/admin/shop-sources/{created['id']}/sync", headers=CSRF)
    ).json()["data"]
    assert report["status"] == "failed"
    failed = (await admin.get("/api/admin/shop-sources", params={"state": "failed"})).json()["data"]
    assert failed["items"][0]["fail_count"] == 1


async def test_requires_admin(db_client: httpx.AsyncClient, store: MemoryStore) -> None:
    assert (await db_client.get("/api/admin/shop-sources")).status_code == 401
