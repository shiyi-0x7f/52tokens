"""依赖装配：会话 → 仓储 → 服务，路由层只拿服务。"""

from typing import Annotated, cast

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collectors.page_watch import PageWatchCollector
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.kv import KeyValueStore, get_store
from app.db.session import get_session, get_sessionmaker
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
from app.domains.deals.source_repository import DealSourceRepository
from app.domains.deals.sources_admin import SourceAdminService
from app.domains.deals.watch import DealWatchService
from app.domains.deals.watch_batch import BatchCheckService
from app.domains.official.repository import OfficialRepository
from app.domains.official.service import OfficialService
from app.domains.outbound.repository import OutboundRepository
from app.domains.outbound.service import OutboundService
from app.domains.shops.admin import ShopAdminService
from app.domains.shops.repository import ShopRepository
from app.domains.shops.service import ShopService
from app.domains.shops.sync import ShopSyncService
from app.integrations.llm import llm_from_settings
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


def get_official_service(session: SessionDep) -> OfficialService:
    return OfficialService(OfficialRepository(session))


def get_shop_service(session: SessionDep) -> ShopService:
    return ShopService(ShopRepository(session))


def get_outbound_service(session: SessionDep) -> OutboundService:
    return OutboundService(
        DealRepository(session), ShopRepository(session), OutboundRepository(session)
    )


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
OutboundServiceDep = Annotated[OutboundService, Depends(get_outbound_service)]
ShopServiceDep = Annotated[ShopService, Depends(get_shop_service)]
OfficialServiceDep = Annotated[OfficialService, Depends(get_official_service)]
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


def get_source_admin_service(
    session: SessionDep, settings: SettingsDep, http: HttpDep
) -> SourceAdminService:
    repo = DealSourceRepository(session)
    watch = DealWatchService(repo, PageWatchCollector(http), llm_from_settings(http, settings))
    return SourceAdminService(repo, watch)


def get_price_admin_service(session: SessionDep) -> PriceAdminService:
    return PriceAdminService(CatalogRepository(session))


DealAdminServiceDep = Annotated[DealAdminService, Depends(get_deal_admin_service)]
PriceAdminServiceDep = Annotated[PriceAdminService, Depends(get_price_admin_service)]
SourceAdminServiceDep = Annotated[SourceAdminService, Depends(get_source_admin_service)]


def get_shop_admin_service(session: SessionDep, http: HttpDep) -> ShopAdminService:
    repo = ShopRepository(session)
    return ShopAdminService(repo, ShopSyncService(repo, http))


ShopAdminServiceDep = Annotated[ShopAdminService, Depends(get_shop_admin_service)]


def get_batch_check_service(store: StoreDep) -> BatchCheckService:
    return BatchCheckService(store)


BatchCheckServiceDep = Annotated[BatchCheckService, Depends(get_batch_check_service)]
# 后台任务在请求结束后才执行，不能用请求的会话，要自己开
SessionMakerDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]
