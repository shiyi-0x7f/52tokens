"""内部服务令牌：公开数据接口只接受公开站服务端（内网）带令牌调用。"""

import hmac
from typing import Annotated

from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.core.errors import AppError


async def require_internal_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.internal_api_token.get_secret_value()
    # 未配置令牌时一律拒绝，避免误部署成公开接口
    if not expected or not x_internal_token:
        raise AppError("UNAUTHORIZED")
    if not hmac.compare_digest(x_internal_token.encode(), expected.encode()):
        raise AppError("UNAUTHORIZED")
