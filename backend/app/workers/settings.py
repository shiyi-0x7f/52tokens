"""arq worker 入口：uv run arq app.workers.settings.WorkerSettings"""

from typing import Any, ClassVar

import httpx
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.tasks import run_collector

_settings = get_settings()

# 采集请求如实标明身份，不伪装浏览器
USER_AGENT = "52tokens-collector/0.1"


async def startup(ctx: dict[str, Any]) -> None:
    setup_logging(_settings)
    ctx["http"] = httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["http"].aclose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [run_collector]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = f"{_settings.redis_key_prefix}arq:queue"
    max_jobs = 4
