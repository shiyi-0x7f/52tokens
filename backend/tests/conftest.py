import os

# 必须在导入 app 之前设置：测试不读本机 .env.dev
os.environ["APP_ENV"] = "test"
os.environ["INTERNAL_API_TOKEN"] = "test-internal-token"

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app

INTERNAL_TOKEN = "test-internal-token"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
