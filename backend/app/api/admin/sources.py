"""活动采集的监测来源。"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query

from app.api.deps import BatchCheckServiceDep, HttpDep, SessionMakerDep, SourceAdminServiceDep
from app.core.errors import AppError
from app.core.response import ApiResponse, ok
from app.domains.common import Page
from app.domains.deals.sources_admin import SourceAdminOut, SourceIn, SourceListQuery
from app.domains.deals.watch import CheckReport
from app.domains.deals.watch_batch import BatchStatus
from app.workers.tasks import run_watch_batch

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


@router.get("/check-all")
async def check_all_status(batch: BatchCheckServiceDep) -> ApiResponse[BatchStatus]:
    return ok(await batch.status())


@router.post("/check-all")
async def check_all(
    batch: BatchCheckServiceDep,
    background: BackgroundTasks,
    sessions: SessionMakerDep,
    http: HttpDep,
) -> ApiResponse[BatchStatus]:
    """后台逐个检查全部启用的来源，立即返回；进度用 GET /check-all 查询。"""
    if not await batch.acquire():
        raise AppError("CONFLICT", "已有一批检查在进行，等它跑完再试")
    background.add_task(run_watch_batch, sessions, http, batch)
    return ok(await batch.status())


@router.post("/{source_id}/check")
async def check_source(source_id: int, service: SourceAdminServiceDep) -> ApiResponse[CheckReport]:
    return ok(await service.check(source_id))
