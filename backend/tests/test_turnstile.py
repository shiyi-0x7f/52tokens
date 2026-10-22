"""Turnstile 校验：成功、失败、缺 token、上游不可达。"""

import json

import httpx
import pytest

from app.core.errors import AppError
from app.core.turnstile import verify_turnstile


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_success_passes_secret_and_ip() -> None:
    seen: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen.update(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, json={"success": True})

    async with _client(httpx.MockTransport(handle)) as client:
        await verify_turnstile(client, secret="s", token="t", remote_ip="1.2.3.4")
    assert seen == {"secret": "s", "response": "t", "remoteip": "1.2.3.4"}


async def test_rejected_token_raises() -> None:
    body = json.dumps({"success": False, "error-codes": ["invalid-input-response"]})
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text=body))
    async with _client(transport) as client:
        with pytest.raises(AppError) as exc:
            await verify_turnstile(client, secret="s", token="bad")
    assert exc.value.error.name == "TURNSTILE_FAILED"


async def test_missing_token_raises_without_calling_cloudflare() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        raise AssertionError("不应调用 Cloudflare")

    async with _client(httpx.MockTransport(handle)) as client:
        with pytest.raises(AppError) as exc:
            await verify_turnstile(client, secret="s", token=None)
    assert exc.value.error.name == "TURNSTILE_FAILED"


async def test_upstream_error_maps_to_upstream_code() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(502))
    async with _client(transport) as client:
        with pytest.raises(AppError) as exc:
            await verify_turnstile(client, secret="s", token="t")
    assert exc.value.error.name == "UPSTREAM_ERROR"
