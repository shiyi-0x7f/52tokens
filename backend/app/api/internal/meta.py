"""站点元信息：公开站服务端用来确认后端可达、令牌有效。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.response import ApiResponse, ok

router = APIRouter(tags=["internal"])


@router.get("/meta")
async def meta(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResponse[dict[str, str]]:
    return ok({"env": settings.app_env})
