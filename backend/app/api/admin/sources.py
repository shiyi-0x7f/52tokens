"""活动采集的监测来源。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SourceAdminServiceDep
from app.core.response import ApiResponse, ok
from app.domains.common import Page
from app.domains.deals.sources_admin import SourceAdminOut, SourceIn, SourceListQuery
from app.domains.deals.watch import CheckReport

router = APIRouter(prefix="/sources", tags=["admin:sources"])


@router.get("")
async def list_sources(
    service: SourceAdminServiceDep, query: Annotated[SourceListQuery, Query()]
) -> ApiResponse[Page[SourceAdminOut]]:
    return ok(await service.list(query))


@router.post("")
async def create_source(
    body: SourceIn, service: SourceAdminServiceDep
) -> ApiResponse[SourceAdminOut]:
    return ok(await service.create(body))


@router.put("/{source_id}")
async def update_source(
    source_id: int, body: SourceIn, service: SourceAdminServiceDep
) -> ApiResponse[SourceAdminOut]:
    return ok(await service.update(source_id, body))


@router.delete("/{source_id}")
async def delete_source(source_id: int, service: SourceAdminServiceDep) -> ApiResponse[None]:
    await service.delete(source_id)
    return ok(None)


@router.post("/{source_id}/check")
async def check_source(source_id: int, service: SourceAdminServiceDep) -> ApiResponse[CheckReport]:
    return ok(await service.check(source_id))
