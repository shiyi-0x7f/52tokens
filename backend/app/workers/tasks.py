"""worker 任务：按 kind 取采集器执行。结果入库在各业务域落地后接入。"""

from typing import Any

import httpx
from loguru import logger

from app.collectors.base import SourceConfig
from app.collectors.registry import get_collector_class


async def run_collector(ctx: dict[str, Any], kind: str, source: dict[str, Any]) -> dict[str, Any]:
    client: httpx.AsyncClient = ctx["http"]
    config = SourceConfig.model_validate(source)
    collector = get_collector_class(kind)(client)
    result = await collector.collect(config)
    if result.ok:
        logger.info("采集完成 kind={} source={} items={}", kind, config.id, len(result.items))
    else:
        logger.warning("采集有错误 kind={} source={} errors={}", kind, config.id, result.errors)
    return {"source_id": config.id, "items": len(result.items), "errors": result.errors}
