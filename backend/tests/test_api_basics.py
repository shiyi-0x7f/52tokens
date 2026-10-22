"""接口基础契约：健康检查、统一响应体、错误码、内部令牌。"""

import httpx
from fastapi import FastAPI

from app.core.errors import AppError, code
from tests.conftest import INTERNAL_TOKEN


async def test_health_returns_ok_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"code": 0, "message": "成功", "data": {"status": "ok"}}


async def test_unknown_route_uses_not_found_code(client: httpx.AsyncClient) -> None:
    resp = await client.get("/no-such-route")
    assert resp.status_code == 404
    assert resp.json()["code"] == code("NOT_FOUND").code


async def test_internal_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/internal/v1/meta")
    assert resp.status_code == 401
    assert resp.json()["code"] == code("UNAUTHORIZED").code


async def test_internal_rejects_wrong_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/internal/v1/meta", headers={"X-Internal-Token": "wrong"})
    assert resp.status_code == 401


async def test_internal_accepts_valid_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/internal/v1/meta", headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert resp.status_code == 200
    assert resp.json()["data"] == {"env": "test"}


async def test_app_error_and_unhandled_error(app: FastAPI, client: httpx.AsyncClient) -> None:
    @app.get("/boom/app")
    async def boom_app() -> None:
        raise AppError("CONFLICT", "已存在")

    @app.get("/boom/unhandled")
    async def boom_unhandled() -> None:
        raise RuntimeError("secret detail")

    resp = await client.get("/boom/app")
    assert resp.status_code == 409
    assert resp.json() == {"code": code("CONFLICT").code, "message": "已存在", "data": None}

    resp = await client.get("/boom/unhandled")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == code("INTERNAL_ERROR").code
    assert "secret detail" not in body["message"]


async def test_validation_error_envelope(app: FastAPI, client: httpx.AsyncClient) -> None:
    @app.get("/needs-int")
    async def needs_int(n: int) -> int:
        return n

    resp = await client.get("/needs-int", params={"n": "abc"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == code("VALIDATION_ERROR").code
    assert body["data"][0]["loc"] == ["query", "n"]
