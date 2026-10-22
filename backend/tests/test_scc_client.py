"""SCC 客户端：app token 缓存、失效重试、错误映射。"""

import httpx
import pytest

from app.core.errors import AppError
from app.integrations.google_oauth import GoogleIdentity
from app.integrations.scc import SccClient
from tests.fakes import SCC_BASE, FakeUpstreams, MemoryStore

IDENTITY = GoogleIdentity(
    sub="s1", email="a@gmail.com", email_verified=True, name="A", picture=None
)


def _client(up: FakeUpstreams, store: MemoryStore, app_id: int | None = 7) -> SccClient:
    return SccClient(up.client(), store, base_url=SCC_BASE, app_id=app_id, app_secret="sec")


async def test_app_token_is_cached_between_logins() -> None:
    up, store = FakeUpstreams(), MemoryStore()
    scc = _client(up, store)
    user = await scc.federated_login(IDENTITY)
    await scc.federated_login(IDENTITY)
    assert user.user_id == 42
    assert up.calls == {"google_token": 0, "scc_token": 1, "scc_login": 2}
    assert up.last_login_body["provider"] == "google"
    assert up.last_login_body["subject"] == "s1"


async def test_rejected_app_token_is_refreshed_once() -> None:
    up, store = FakeUpstreams(), MemoryStore()
    up.scc_login_responses = [httpx.Response(401, json={"detail": "expired"})]
    user = await _client(up, store).federated_login(IDENTITY)
    assert user.user_id == 42
    assert up.calls["scc_token"] == 2
    assert up.calls["scc_login"] == 2


@pytest.mark.parametrize(
    ("status", "error"),
    [(403, "FORBIDDEN"), (409, "CONFLICT"), (500, "UPSTREAM_ERROR")],
)
async def test_error_mapping(status: int, error: str) -> None:
    up, store = FakeUpstreams(), MemoryStore()
    up.scc_login_responses = [httpx.Response(status, json={"detail": "x"})]
    with pytest.raises(AppError) as exc:
        await _client(up, store).federated_login(IDENTITY)
    assert exc.value.error.name == error


async def test_missing_app_credentials_is_service_unavailable() -> None:
    with pytest.raises(AppError) as exc:
        await _client(FakeUpstreams(), MemoryStore(), app_id=None).federated_login(IDENTITY)
    assert exc.value.error.name == "SERVICE_UNAVAILABLE"
