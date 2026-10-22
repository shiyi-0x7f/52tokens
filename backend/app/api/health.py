"""健康检查：保持轻量，不查数据库，供容器与反代 30s 探测。"""

from fastapi import APIRouter

from app.core.response import ApiResponse, ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> ApiResponse[dict[str, str]]:
    return ok({"status": "ok"})
