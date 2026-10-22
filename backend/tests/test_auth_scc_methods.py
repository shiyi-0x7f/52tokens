"""经 SCC 的另外两种登录：微信网站应用扫码、邮箱验证码。"""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.api.deps import get_http
from app.core.config import Settings, get_settings
from app.core.kv import get_store
from tests.conftest import AUTH, INTERNAL_TOKEN
from tests.fakes import SCC_BASE, FakeUpstreams, MemoryStore


@pytest.fixture
def upstreams() -> FakeUpstreams:
    return FakeUpstreams()


@pytest.fixture
async def client(
    app: FastAPI, db_client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        app_env="test",
        internal_api_token=SecretStr(INTERNAL_TOKEN),
        scc_base_url=SCC_BASE,
        scc_app_id=7,
        scc_app_secret=SecretStr("scc-secret"),
        admin_emails="boss@example.com",
    )
    http = upstreams.client()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = MemoryStore
    app.dependency_overrides[get_http] = lambda: http
    yield db_client
    await http.aclose()


async def _post(client: httpx.AsyncClient, path: str, body: dict[str, object]) -> httpx.Response:
    return await client.post(f"/internal/v1/auth{path}", json=body, headers=AUTH)


# ---------- 微信 ----------


async def test_wechat_start_returns_scc_url_and_state(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    resp = await _post(client, "/wechat/start", {})
    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "authorize_url": "https://open.weixin.qq.com/connect/qrconnect?x=1",
        "state": "wx-state-1",
    }


async def test_wechat_callback_creates_session_without_admin(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    resp = await _post(client, "/wechat/callback", {"code": "wx-code", "state": "wx-state-1"})
    assert resp.status_code == 200, resp.json()
    data = resp.json()["data"]
    assert data["user"]["is_admin"] is False
    assert upstreams.last_bodies["wechat_login"] == {
        "app_id": 7,
        "code": "wx-code",
        "state": "wx-state-1",
    }


async def test_wechat_invalid_state_asks_to_rescan(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.responses["wechat_login"] = [httpx.Response(400, json={"detail": "无效的 state"})]
    resp = await _post(client, "/wechat/callback", {"code": "c", "state": "s"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 40003


# ---------- 邮箱验证码 ----------


async def test_email_send_requires_turnstile(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.turnstile_success = False
    resp = await _post(client, "/email/send", {"email": "a@example.com", "turnstile_token": "t"})
    assert resp.json()["code"] == 40002
    assert "email_send" not in upstreams.last_bodies  # 人机验证没过，不打扰 SCC


async def test_email_send_normalizes_email(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    resp = await _post(
        client, "/email/send", {"email": "  Alice@Example.COM ", "turnstile_token": "t"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"cooldown_seconds": 60}
    assert upstreams.last_bodies["email_send"] == {
        "app_id": 7,
        "email": "alice@example.com",
        "purpose": "login",
    }


@pytest.mark.parametrize("email", ["no-at-sign", "a@nodot", "a b@example.com"])
async def test_email_send_rejects_bad_format(client: httpx.AsyncClient, email: str) -> None:
    resp = await _post(client, "/email/send", {"email": email, "turnstile_token": "t"})
    assert resp.status_code == 422


async def test_email_send_rate_limit_passes_scc_message(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.responses["email_send"] = [
        httpx.Response(429, json={"detail": "发送过于频繁，请 42 秒后再试"})
    ]
    resp = await _post(client, "/email/send", {"email": "a@example.com", "turnstile_token": "t"})
    assert resp.status_code == 429
    assert resp.json()["message"] == "发送过于频繁，请 42 秒后再试"


async def test_email_send_failure_in_scc_is_distinguished(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    # SCC 的 SMTP 未配置 / 发信失败：返回 JSON 业务错误 502
    upstreams.responses["email_send"] = [
        httpx.Response(502, json={"detail": "邮件发送失败，请检查邮箱地址或稍后再试"})
    ]
    resp = await _post(client, "/email/send", {"email": "a@example.com", "turnstile_token": "t"})
    assert resp.status_code == 502
    assert resp.json()["code"] == 50201


async def test_gateway_502_is_generic_upstream_error(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    # 网关层 502（HTML，不是 SCC 的业务错误）按上游不可用处理
    upstreams.responses["email_send"] = [httpx.Response(502, text="<html>Bad Gateway</html>")]
    resp = await _post(client, "/email/send", {"email": "a@example.com", "turnstile_token": "t"})
    assert resp.json()["code"] == 50200


async def test_email_login_and_admin_by_verified_email(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    resp = await _post(client, "/email/login", {"email": "Boss@Example.com", "code": "123456"})
    assert resp.status_code == 200, resp.json()
    assert resp.json()["data"]["user"]["is_admin"] is True
    assert upstreams.last_bodies["email_login"]["email"] == "boss@example.com"


async def test_email_wrong_code(client: httpx.AsyncClient, upstreams: FakeUpstreams) -> None:
    upstreams.responses["email_login"] = [httpx.Response(400, json={"detail": "验证码错误"})]
    resp = await _post(client, "/email/login", {"email": "a@example.com", "code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 40004
    assert resp.json()["message"] == "验证码错误"


async def test_scc_unreachable_maps_to_upstream_error(
    client: httpx.AsyncClient, upstreams: FakeUpstreams
) -> None:
    upstreams.responses["email_login"] = [httpx.Response(500, json={"detail": "boom"})]
    resp = await _post(client, "/email/login", {"email": "a@example.com", "code": "123456"})
    assert resp.status_code == 502
