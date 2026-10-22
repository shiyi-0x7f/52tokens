"""worker 任务。CLI（app.cli.collect）和定时任务调用的是同一组函数。"""

from typing import Any

import httpx
from loguru import logger

from app.collectors.base import SourceConfig
from app.collectors.openrouter import MODELS_URL, OpenRouterModelsCollector
from app.collectors.registry import get_collector_class
from app.db.session import get_sessionmaker
from app.domains.catalog.ingest import CatalogIngestService
from app.domains.catalog.repository import CatalogRepository


async def run_collector(ctx: dict[str, Any], kind: str, source: dict[str, Any]) -> dict[str, Any]:
    """通用调试入口：只采集不入库，返回条数和错误。"""
    client: httpx.AsyncClient = ctx["http"]
    config = SourceConfig.model_validate(source)
    collector = get_collector_class(kind)(client)
    result = await collector.collect(config)
    if result.ok:
        logger.info("采集完成 kind={} source={} items={}", kind, config.id, len(result.items))
    else:
        logger.warning("采集有错误 kind={} source={} errors={}", kind, config.id, result.errors)
    return {"source_id": config.id, "items": len(result.items), "errors": result.errors}


async def sync_openrouter(ctx: dict[str, Any]) -> dict[str, Any]:
    """采集 OpenRouter 模型价格并入库。采集失败时不动已有数据。"""
    collector = OpenRouterModelsCollector(ctx["http"])
    result = await collector.collect(SourceConfig(id="openrouter-models", url=MODELS_URL))
    if not result.ok:
        logger.warning("OpenRouter 采集失败，已有数据保持不变：{}", result.errors)
        return {"ingested": 0, "errors": result.errors}
    async with get_sessionmaker()() as session:
        service = CatalogIngestService(CatalogRepository(session))
        count = await service.ingest_openrouter(result.items, result.fetched_at)
    return {"ingested": count, "errors": []}
