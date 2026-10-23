"""依赖装配：会话 → 仓储 → 服务，路由层只拿服务。"""

from typing import Annotated, cast

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.kv import KeyValueStore, get_store
from app.db.session import get_session
from app.domains.accounts.repository import UserRepository
from app.domains.accounts.schemas import UserOut
from app.domains.accounts.service import AuthService
from app.domains.accounts.sessions import SessionService
from app.domains.catalog.admin import PriceAdminService
from app.domains.catalog.repository import CatalogRepository
from app.domains.catalog.service import CatalogService
from app.domains.deals.admin import DealAdminService
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


def get_session_service(
    session: SessionDep, settings: SettingsDep, store: StoreDep
) -> SessionService:
    return SessionService(store, UserRepository(session), settings.session_ttl_days)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


def get_auth_service(
    session: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    http: HttpDep,
    sessions: SessionServiceDep,
) -> AuthService:
    scc = SccClient(
        http,
        store,
        base_url=settings.scc_base_url,
        app_id=settings.scc_app_id,
        app_secret=settings.scc_app_secret.get_secret_value(),
    )
    return AuthService(
        settings=settings,
        store=store,
        http=http,
        users=UserRepository(session),
        sessions=sessions,
        scc=scc,
    )


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
DealServiceDep = Annotated[DealService, Depends(get_deal_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# ---------- 后台 ----------

# 后台 SPA 的写请求必须带这个头。浏览器跨站表单 / 图片请求带不了自定义头，配合
# SameSite=Lax 的会话 Cookie 防 CSRF
ADMIN_CSRF_HEADER = "X-Requested-With"
ADMIN_CSRF_VALUE = "52tokens-admin"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def require_admin(
    request: Request, sessions: SessionServiceDep, settings: SettingsDep
) -> UserOut:
    if (
        request.method not in _SAFE_METHODS
        and request.headers.get(ADMIN_CSRF_HEADER) != ADMIN_CSRF_VALUE
    ):
        raise AppError("FORBIDDEN", "缺少后台请求标记")
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AppError("UNAUTHORIZED")
    user = await sessions.get_user(token)
    if not user.is_admin:
        raise AppError("FORBIDDEN", "需要管理员权限")
    return user


AdminDep = Annotated[UserOut, Depends(require_admin)]


def get_deal_admin_service(session: SessionDep) -> DealAdminService:
    return DealAdminService(DealRepository(session))


def get_price_admin_service(session: SessionDep) -> PriceAdminService:
    return PriceAdminService(CatalogRepository(session))


DealAdminServiceDep = Annotated[DealAdminService, Depends(get_deal_admin_service)]
PriceAdminServiceDep = Annotated[PriceAdminService, Depends(get_price_admin_service)]
