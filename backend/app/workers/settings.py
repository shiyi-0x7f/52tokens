"""arq worker 入口：uv run arq app.workers.settings.WorkerSettings"""

from typing import Any, ClassVar

import httpx
from arq import cron
from arq.connections import RedisSettings

from app.collectors.base import USER_AGENT
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.tasks import (
    check_deal_liveness,
    run_collector,
    snapshot_price_history,
    sync_openrouter,
    sync_shops,
    watch_deal_sources,
)

_settings = get_settings()


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
    functions: ClassVar[list[Any]] = [
        run_collector,
        sync_openrouter,
        watch_deal_sources,
        check_deal_liveness,
        sync_shops,
        snapshot_price_history,
    ]
    # 每 6 小时同步一次 OpenRouter 价格（错开整点）；活动来源每 6 小时检查一次（会调用 LLM，
    # 启动时不跑）
    cron_jobs: ClassVar[list[Any]] = [
        cron(sync_openrouter, hour={0, 6, 12, 18}, minute=7, run_at_startup=True),
        cron(watch_deal_sources, hour={1, 7, 13, 19}, minute=17),
        # 每天回访一次已发布活动（连续 3 天有下线信号才自动结束）
        cron(check_deal_liveness, hour={3}, minute=27),
        # 卡网店铺每 3 小时同步一次（价格和库存变化快）
        cron(sync_shops, hour={2, 5, 8, 11, 14, 17, 20, 23}, minute=47),
        # 价格历史：跟在卡网同步之后，每 6 小时记一次；同一天覆盖，启动时也记一次，
        # 避免 worker 停过一段时间漏掉当天
        cron(snapshot_price_history, hour={3, 9, 15, 21}, minute=57, run_at_startup=True),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = f"{_settings.redis_key_prefix}arq:queue"
    max_jobs = 4
