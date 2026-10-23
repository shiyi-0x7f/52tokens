"""后台接口：只给后台 SPA 用（同域，经 nginx 反代 /api/admin/*）。

统一要求管理员会话；写操作还要带 X-Requested-With: 52tokens-admin 请求头（防 CSRF）。
"""

from fastapi import APIRouter, Depends

from app.api.admin import deals, me, prices, sources
from app.api.deps import require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
router.include_router(me.router)
router.include_router(deals.router)
router.include_router(prices.router)
router.include_router(sources.router)
