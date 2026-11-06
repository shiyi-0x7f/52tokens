"""卡网店铺后台：查看采集状态、登记店铺（含多商户平台的具体商户地址）、启停、立即采集。"""

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.collectors.shops.base import ShopFetchError
from app.collectors.shops.shop_api import item_key, resolve_item_shop, shop_token
from app.core.errors import AppError
from app.domains.common import Page, PageQuery
from app.domains.shops.models import ShopCollectorKind, ShopSource
from app.domains.shops.repository import ShopRepository
from app.domains.shops.sync import ShopSyncReport, ShopSyncService


class ShopSourceIn(BaseModel):
    # 店铺地址；多商户平台填具体商户的 /shop/<token>，ShopApi 平台也可以填商品链接 /item/<key>
    entry_url: HttpUrl
    collector_kind: ShopCollectorKind
    name: str = Field(default="", max_length=80)
    enabled: bool = True


class ShopSourceAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    host: str
    entry_url: str
    name: str
    collector_kind: ShopCollectorKind
    enabled: bool
    checked_at: datetime | None
    success_at: datetime | None
    last_error: str
    fail_count: int
    offer_count: int


class ShopSourceListQuery(PageQuery):
    collector_kind: ShopCollectorKind | None = None
    state: Literal["ok", "failed", "unchecked"] | None = None
    q: str | None = Field(default=None, max_length=50)


class ShopAdminService:
    def __init__(self, repo: ShopRepository, sync: ShopSyncService) -> None:
        self.repo = repo
        self.sync_service = sync

    async def _source(self, source_id: int) -> ShopSource:
        source = await self.repo.get_source(source_id)
        if source is None:
            raise AppError("NOT_FOUND", "店铺不存在")
        return source

    async def list(self, query: ShopSourceListQuery) -> Page[ShopSourceAdminOut]:
        rows, total = await self.repo.list_sources(
            kind=query.collector_kind,
            state=query.state,
            q=query.q,
            offset=query.offset,
            limit=query.page_size,
        )
        return Page(
            items=[ShopSourceAdminOut.model_validate(s) for s in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    @staticmethod
    def _apply(source: ShopSource, data: ShopSourceIn) -> None:
        url = str(data.entry_url).rstrip("/")
        parts = urlsplit(url)
        source.entry_url = url
        source.base_url = f"{parts.scheme}://{parts.netloc}"
        source.host = (parts.hostname or "").lower()
        source.collector_kind = data.collector_kind
        source.name = data.name.strip()
        source.enabled = data.enabled

    async def _normalize(self, data: ShopSourceIn) -> ShopSourceIn:
        """多商户平台只给了商品链接时，换成所属商户的店铺地址。"""
        url = str(data.entry_url)
        if (
            data.collector_kind != ShopCollectorKind.SHOP_API
            or shop_token(url)
            or not item_key(url)
        ):
            return data
        try:
            shop_url = await resolve_item_shop(self.sync_service.http, url)
        except (ShopFetchError, httpx.HTTPError) as exc:
            raise AppError("BAD_REQUEST", f"没能从商品链接找到所属店铺：{exc}") from exc
        return data.model_copy(update={"entry_url": HttpUrl(shop_url)})

    async def create(self, data: ShopSourceIn) -> ShopSourceAdminOut:
        data = await self._normalize(data)
        if await self.repo.entry_url_taken(str(data.entry_url).rstrip("/")):
            raise AppError("CONFLICT", "这个店铺地址已经登记过")
        source = ShopSource()
        self._apply(source, data)
        self.repo.add_source(source)
        await self.repo.commit()
        await self.repo.refresh(source)  # 带数据库默认值的列（失败次数等）提交后需重新加载
        return ShopSourceAdminOut.model_validate(source)

    async def update(self, source_id: int, data: ShopSourceIn) -> ShopSourceAdminOut:
        source = await self._source(source_id)
        data = await self._normalize(data)
        if await self.repo.entry_url_taken(str(data.entry_url).rstrip("/"), exclude_id=source_id):
            raise AppError("CONFLICT", "这个店铺地址已经登记过")
        self._apply(source, data)
        await self.repo.commit()
        return ShopSourceAdminOut.model_validate(source)

    async def sync(self, source_id: int) -> ShopSyncReport:
        return await self.sync_service.sync(await self._source(source_id))
