"""手动触发采集并入库：uv run python -m app.cli.collect openrouter|deals|liveness|shops"""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.settings import new_http_client
from app.workers.tasks import (
    check_deal_liveness,
    sync_openrouter,
    sync_shops,
    watch_deal_sources,
)

JOBS: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]] = {
    "openrouter": sync_openrouter,
    "deals": watch_deal_sources,
    "liveness": check_deal_liveness,
    "shops": sync_shops,
}


async def _main(name: str) -> int:
    async with new_http_client() as http:
        result = await JOBS[name]({"http": http})
    logger.info("{} 结果：{}", name, result)
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    setup_logging(get_settings())
    if len(sys.argv) != 2 or sys.argv[1] not in JOBS:
        logger.error("用法：python -m app.cli.collect <{}>", "|".join(JOBS))
        sys.exit(2)
    sys.exit(asyncio.run(_main(sys.argv[1])))
