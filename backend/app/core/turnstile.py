"""Cloudflare Turnstile 服务端校验：前端表单拿到的 token 必须经这里核验后才算通过。"""

import httpx
from loguru import logger

from app.core.errors import AppError

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(
    client: httpx.AsyncClient,
    *,
    secret: str,
    token: str | None,
    remote_ip: str | None = None,
) -> None:
    """校验失败抛 TURNSTILE_FAILED；Cloudflare 不可达抛 UPSTREAM_ERROR。"""
    if not token:
        raise AppError("TURNSTILE_FAILED")
    form = {"secret": secret, "response": token}
    if remote_ip:
        form["remoteip"] = remote_ip
    try:
        resp = await client.post(SITEVERIFY_URL, data=form, timeout=10.0)
        resp.raise_for_status()
        result = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Turnstile siteverify 调用失败: {}", exc)
        raise AppError("UPSTREAM_ERROR") from exc
    if not result.get("success"):
        logger.info("Turnstile 未通过: {}", result.get("error-codes"))
        raise AppError("TURNSTILE_FAILED")
