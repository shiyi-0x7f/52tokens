"""监测来源后台：登记要盯的官方页面、查看检查结果、手动立即检查。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.core.errors import AppError
from app.domains.common import Page, PageQuery
from app.domains.deals.admin import PlatformBrief
from app.domains.deals.models import DealSource
from app.domains.deals.source_repository import DealSourceRepository
from app.domains.deals.watch import CheckReport, DealWatchService


class SourceIn(BaseModel):
    platform_id: int
    url: HttpUrl
    label: str = Field(default="", max_length=60)
    enabled: bool = True


class SourceAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: PlatformBrief
    url: str
    label: str
    enabled: bool
    checked_at: datetime | None
    changed_at: datetime | None
    last_error: str
    fail_count: int
    created_at: datetime


class SourceListQuery(PageQuery):
    platform_id: int | None = None


class SourceAdminService:
    def __init__(self, repo: DealSourceRepository, watch: DealWatchService) -> None:
        self.repo = repo
        self.watch = watch

    async def _source(self, source_id: int) -> DealSource:
        source = await self.repo.get(source_id)
        if source is None:
            raise AppError("NOT_FOUND", "监测来源不存在")
        return source

    async def _out(self, source_id: int) -> SourceAdminOut:
        return SourceAdminOut.model_validate(await self._source(source_id))

    async def _check_input(self, data: SourceIn, exclude_id: int | None = None) -> str:
        if await self.repo.get_platform(data.platform_id) is None:
            raise AppError("BAD_REQUEST", "平台不存在")
        url = str(data.url)
        if await self.repo.url_taken(url, exclude_id):
            raise AppError("CONFLICT", "这个页面已经在监测列表里")
        return url

    async def list(self, query: SourceListQuery) -> Page[SourceAdminOut]:
        rows, total = await self.repo.list_all(
            platform_id=query.platform_id, offset=query.offset, limit=query.page_size
        )
        return Page(
            items=[SourceAdminOut.model_validate(s) for s in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def create(self, data: SourceIn) -> SourceAdminOut:
        url = await self._check_input(data)
        source = DealSource(
            platform_id=data.platform_id, url=url, label=data.label.strip(), enabled=data.enabled
        )
        self.repo.add(source)
        await self.repo.commit()
        return await self._out(source.id)

    async def update(self, source_id: int, data: SourceIn) -> SourceAdminOut:
        source = await self._source(source_id)
        url = await self._check_input(data, exclude_id=source_id)
        if url != source.url or data.platform_id != source.platform_id:
            # 换了页面：清掉 hash，下次检查重新抽取
            source.content_hash = None
            source.changed_at = None
            source.last_error = ""
            source.fail_count = 0
        source.platform_id = data.platform_id
        source.url = url
        source.label = data.label.strip()
        source.enabled = data.enabled
        await self.repo.commit()
        return await self._out(source_id)

    async def delete(self, source_id: int) -> None:
        """删除来源；由它采集到的活动保留（source_id 置空）。"""
        await self.repo.delete(await self._source(source_id))
        await self.repo.commit()

    async def check(self, source_id: int) -> CheckReport:
        return await self.watch.check(await self._source(source_id))
