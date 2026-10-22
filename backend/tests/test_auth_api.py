"""登录全流程：start → Google 回调 → SCC 联合登录 → 本地会话；以及各种失败路径。"""

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.api.deps import get_http
from app.core.config import Settings, get_settings
from app.core.kv import get_store
from tests.conftest import AUTH, INTERNAL_TOKEN
from tests.fakes import GOOGLE_CLIENT_ID, SCC_BASE, FakeUpstreams, MemoryStore


@pytest.fixture
def upstreams() -> FakeUpstreams:
    return FakeUpstreams()


@pytest.fixture
async def auth_client(
    app: FastAPI, db_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        app_env="test",
        internal_api_token=SecretStr(INTERNAL_TOKEN),
        google_client_id=GOOGLE_CLIENT_ID,
        google_client_secret=SecretStr("gsecret"),
        google_redirect_uri="https://52tokens.test/auth/google/callback",
        scc_base_url=SCC_BASE,
        scc_app_id=7,
        scc_app_secret=SecretStr("scc-secret"),
        admin_emails="boss@gmail.com",
    )
    store = MemoryStore()
    http = upstreams.client()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_http] = lambda: http
    yield db_client
    await http.aclose()


async def _login(
    client: httpx.AsyncClient, up: FakeUpstreams, next_path: str = "/"
) -> dict[str, Any]:
    start = await client.post(
        "/internal/v1/auth/google/start", json={"next": next_path}, headers=AUTH
    )
    assert start.status_code == 200
    query = parse_qs(urlparse(start.json()["data"]["authorize_url"]).query)
    up.nonce = query["nonce"][0]
    resp = await client.post(
        "/internal/v1/auth/google/callback",
        json={"code": "auth-code", "state": query["state"][0]},
        headers=AUTH,
    )
    return {"resp": resp, "state": query["state"][0]}


async def test_full_login_creates_session(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    result = await _login(auth_client, upstreams, next_path="/deals?type=student")
    body = result["resp"].json()
    assert result["resp"].status_code == 200, body
    data = body["data"]
    assert data["next"] == "/deals?type=student"
    assert data["user"]["nickname"] == "Alice"
    assert data["user"]["is_admin"] is False

    session = await auth_client.get(
        "/internal/v1/auth/session", headers=AUTH | {"X-Session-Token": data["session_token"]}
    )
    assert session.status_code == 200
    assert session.json()["data"]["id"] == data["user"]["id"]


async def test_relogin_reuses_local_user(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    first = (await _login(auth_client, upstreams))["resp"].json()["data"]["user"]["id"]
    second = (await _login(auth_client, upstreams))["resp"].json()["data"]["user"]["id"]
    assert first == second


async def test_admin_email_gets_admin_flag(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.id_token_claims = {"email": "Boss@gmail.com"}
    upstreams.scc_login_responses = [upstreams.scc_user(user_id=99, email="boss@gmail.com")]
    data = (await _login(auth_client, upstreams))["resp"].json()["data"]
    assert data["user"]["is_admin"] is True


async def test_unverified_admin_email_is_not_admin(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.id_token_claims = {"email": "boss@gmail.com", "email_verified": False}
    data = (await _login(auth_client, upstreams))["resp"].json()["data"]
    assert data["user"]["is_admin"] is False


async def test_state_cannot_be_replayed(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    result = await _login(auth_client, upstreams)
    replay = await auth_client.post(
        "/internal/v1/auth/google/callback",
        json={"code": "auth-code", "state": result["state"]},
        headers=AUTH,
    )
    assert replay.status_code == 400
    assert replay.json()["code"] == 40003


async def test_rejected_google_code_asks_to_relogin(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.google_status = 400
    resp = (await _login(auth_client, upstreams))["resp"]
    assert resp.json()["code"] == 40003
    assert upstreams.calls["scc_login"] == 0


async def test_logout_invalidates_session(
    auth_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    token = (await _login(auth_client, upstreams))["resp"].json()["data"]["session_token"]
    headers = AUTH | {"X-Session-Token": token}
    assert (
        await auth_client.delete("/internal/v1/auth/session", headers=headers)
    ).status_code == 200
    assert (await auth_client.get("/internal/v1/auth/session", headers=headers)).status_code == 401


@pytest.mark.parametrize("bad_next", ["//evil.com", "https://evil.com", "evil"])
async def test_open_redirect_is_rejected(auth_client: httpx.AsyncClient, bad_next: str) -> None:
    resp = await auth_client.post(
        "/internal/v1/auth/google/start", json={"next": bad_next}, headers=AUTH
    )
    assert resp.status_code == 422


async def test_session_requires_token(auth_client: httpx.AsyncClient) -> None:
    assert (await auth_client.get("/internal/v1/auth/session", headers=AUTH)).status_code == 401
