"""worker 任务。CLI（app.cli.collect）、定时任务和后台「全部检查」调用的是同一组函数。"""

from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collectors.base import SourceConfig
from app.collectors.openrouter import MODELS_URL, OpenRouterModelsCollector
from app.collectors.page_watch import PageWatchCollector
from app.collectors.registry import get_collector_class
from app.core.config import get_settings
from app.core.kv import get_store
from app.db import models as _registered_models  # noqa: F401  注册全部模型，外键才能解析
from app.db.session import get_sessionmaker
from app.domains.catalog.ingest import CatalogIngestService
from app.domains.catalog.repository import CatalogRepository
from app.domains.deals.liveness import DealLivenessService
from app.domains.deals.repository import DealRepository
from app.domains.deals.source_repository import DealSourceRepository
from app.domains.deals.watch import DealWatchService
from app.domains.deals.watch_batch import BatchCheckService, BatchSummary
from app.domains.history.repository import HistoryRepository
from app.domains.history.service import PriceHistoryService
from app.domains.shops.repository import ShopRepository
from app.domains.shops.sync import ShopSyncService
from app.integrations.llm import llm_from_settings


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


async def run_watch_batch(
    sessions: async_sessionmaker[AsyncSession], http: httpx.AsyncClient, batch: BatchCheckService
) -> BatchSummary:
    """已抢到批量检查锁后执行一批（定时任务和后台「全部检查」共用），自己开数据库会话。"""
    async with sessions() as session:
        llm = llm_from_settings(http, get_settings())
        watch = DealWatchService(DealSourceRepository(session), PageWatchCollector(http), llm)
        return await batch.run(watch)


SHOP_SYNC_LOCK = "shop_sync:running"
SHOP_SYNC_LOCK_TTL = 3 * 3600  # 进程中途挂掉时锁的兜底过期时间


async def sync_shops(ctx: dict[str, Any]) -> dict[str, Any]:
    """采集全部启用的卡网店铺并入库。已有一批在跑时跳过。"""
    store = get_store()
    if not await store.set_if_absent(
        SHOP_SYNC_LOCK, datetime.now(UTC).isoformat(), SHOP_SYNC_LOCK_TTL
    ):
        logger.info("已有一批卡网同步在进行，本次跳过")
        return {"skipped": True, "errors": []}
    try:
        async with get_sessionmaker()() as session:
            reports = await ShopSyncService(ShopRepository(session), ctx["http"]).sync_all()
    finally:
        await store.delete(SHOP_SYNC_LOCK)
    failed = [r for r in reports if r.status == "failed"]
    logger.info(
        "卡网同步完成 店铺={} 失败={} 报价={}",
        len(reports),
        len(failed),
        sum(r.offers for r in reports),
    )
    # 单个店铺的失败原因记在店铺上（后台可见），这里只给汇总
    return {
        "sources": len(reports),
        "failed": len(failed),
        "offers": sum(r.offers for r in reports),
        "created": sum(r.created for r in reports),
        "errors": [],
    }


async def check_deal_liveness(ctx: dict[str, Any]) -> dict[str, Any]:
    """回访已发布活动的官方出处，连续发现下线信号才标记结束。"""
    async with get_sessionmaker()() as session:
        report = await DealLivenessService(DealRepository(session), ctx["http"]).check_all()
    return report.model_dump() | {"errors": []}


async def snapshot_price_history(ctx: dict[str, Any]) -> dict[str, Any]:
    """把当前对外展示的价格记入当天（北京时间）的价格历史，同一天重复执行会覆盖当天的值。"""
    async with get_sessionmaker()() as session:
        service = PriceHistoryService(HistoryRepository(session), ShopRepository(session))
        report = await service.snapshot(datetime.now(UTC))
    logger.info(
        "价格历史快照完成 日期={} 模型价格={} 卡网商品={}",
        report.day,
        report.model_prices,
        report.shop_products,
    )
    return report.model_dump(mode="json") | {"errors": []}


async def watch_deal_sources(ctx: dict[str, Any]) -> dict[str, Any]:
    """检查所有启用的活动监测来源，正文有变化才调用 LLM 抽取。已有一批在跑时跳过。"""
    batch = BatchCheckService(get_store())
    if not await batch.acquire():
        logger.info("已有一批活动来源检查在进行，本次跳过")
        return {"skipped": True, "errors": []}
    summary = await run_watch_batch(get_sessionmaker(), ctx["http"], batch)
    # 单个来源的失败原因记在来源上（后台可见），这里只给汇总
    return summary.model_dump(mode="json") | {"errors": []}
