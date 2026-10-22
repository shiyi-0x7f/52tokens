"""依赖装配：会话 → 仓储 → 服务，路由层只拿服务。"""

from typing import Annotated, cast

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.kv import KeyValueStore, get_store
from app.db.session import get_session
from app.domains.accounts.repository import UserRepository
from app.domains.accounts.service import AuthService
from app.domains.catalog.repository import CatalogRepository
from app.domains.catalog.service import CatalogService
from app.domains.deals.repository import DealRepository
from app.domains.deals.service import DealService
from app.integrations.scc import SccClient

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[KeyValueStore, Depends(get_store)]


def get_http(request: Request) -> httpx.AsyncClient:
    """出站 HTTP 客户端：应用级共享，生命周期见 app.main.lifespan。"""
    return cast(httpx.AsyncClient, request.app.state.http)


HttpDep = Annotated[httpx.AsyncClient, Depends(get_http)]


def get_catalog_service(session: SessionDep) -> CatalogService:
    return CatalogService(CatalogRepository(session))


def get_deal_service(session: SessionDep) -> DealService:
    return DealService(DealRepository(session))


def get_auth_service(
    session: SessionDep, settings: SettingsDep, store: StoreDep, http: HttpDep
) -> AuthService:
    scc = SccClient(
        http,
        store,
        base_url=settings.scc_base_url,
        app_id=settings.scc_app_id,
        app_secret=settings.scc_app_secret.get_secret_value(),
    )
    return AuthService(
        settings=settings, store=store, http=http, users=UserRepository(session), scc=scc
    )


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
DealServiceDep = Annotated[DealService, Depends(get_deal_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
