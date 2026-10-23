"""官方订阅地区价（公开站服务端专用）。"""

from fastapi import APIRouter

from app.api.deps import OfficialServiceDep
from app.core.response import ApiResponse, ok
from app.domains.official.service import OfficialPlanDetail, OfficialPlanSummary

router = APIRouter(tags=["internal:official"])


@router.get("/official-plans")
async def list_official_plans(
    service: OfficialServiceDep,
) -> ApiResponse[list[OfficialPlanSummary]]:
    return ok(await service.list_plans())


@router.get("/official-plans/{app_slug}/{plan_slug}")
async def get_official_plan(
    app_slug: str, plan_slug: str, service: OfficialServiceDep
) -> ApiResponse[OfficialPlanDetail]:
    return ok(await service.get_plan(app_slug, plan_slug))
