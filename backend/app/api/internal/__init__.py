"""公开数据接口：只供公开站服务端经内网调用，统一要求内部令牌。

反代不得把 /internal/* 暴露到公网，见 dev_docs/architecture/data-protection.md。
"""

from fastapi import APIRouter, Depends

from app.api.internal import auth, catalog, deals, meta, outbound, shops
from app.core.security import require_internal_token

router = APIRouter(prefix="/internal/v1", dependencies=[Depends(require_internal_token)])
router.include_router(meta.router)
router.include_router(catalog.router)
router.include_router(deals.router)
router.include_router(outbound.router)
router.include_router(shops.router)
router.include_router(auth.router)
