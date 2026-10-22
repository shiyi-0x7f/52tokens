import os

# 必须在导入 app 之前设置：测试不读本机 .env.dev
os.environ["APP_ENV"] = "test"
os.environ["INTERNAL_API_TOKEN"] = "test-internal-token"

from collections.abc import AsyncIterator

import httpx
import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import REPO_ROOT
from app.db import models as _registered_models  # noqa: F401  注册全部模型
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

INTERNAL_TOKEN = "test-internal-token"
AUTH = {"X-Internal-Token": INTERNAL_TOKEN}


def _test_database_url() -> str:
    """CI 用 TEST_DATABASE_URL；本地沿用 .env.dev 的账号，换成独立的 tokens52_test 库。"""
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    base = dotenv_values(REPO_ROOT / ".env.dev").get("DATABASE_URL")
    if not base:
        raise RuntimeError("需要 TEST_DATABASE_URL 或 .env.dev 中的 DATABASE_URL")
    return base.rsplit("/", 1)[0] + "/tokens52_test"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


async def _client_for(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client_for(app):
        yield c


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_test_database_url(), poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
async def db_client(app: FastAPI, db_engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """接口请求使用测试库。"""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async for c in _client_for(app):
        yield c
