"""arq worker 入口：uv run arq app.workers.settings.WorkerSettings"""

from typing import Any, ClassVar

import httpx
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.tasks import run_collector, sync_openrouter

_settings = get_settings()

# 采集请求如实标明身份，不伪装浏览器
USER_AGENT = "52tokens-collector/0.1"


def new_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


async def startup(ctx: dict[str, Any]) -> None:
    setup_logging(_settings)
    ctx["http"] = new_http_client()


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["http"].aclose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [run_collector, sync_openrouter]
    # 每 6 小时同步一次 OpenRouter 价格（错开整点）
    cron_jobs: ClassVar[list[Any]] = [
        cron(sync_openrouter, hour={0, 6, 12, 18}, minute=7, run_at_startup=True)
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = f"{_settings.redis_key_prefix}arq:queue"
    max_jobs = 4
