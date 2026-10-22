"""采集结果入库：OpenRouter 模型价格 → ai_models + model_prices。

采集成功但某模型不在列表里时不删除、不下架（采集失败 ≠ 下架），
新鲜度由 confirmed_at 体现。
"""

from datetime import datetime
from typing import Any

from loguru import logger

from app.collectors.openrouter import OpenRouterModel
from app.core.errors import AppError
from app.domains.catalog.models import Currency, PublishStatus
from app.domains.catalog.repository import CatalogRepository

OPENROUTER_PLATFORM = "openrouter"


def _free_note(item: OpenRouterModel) -> str:
    if item.has_free and item.has_paid:
        return "另有 :free 免费版，有请求频率上限"
    if item.has_free:
        return "免费版，有请求频率上限"
    return ""


class CatalogIngestService:
    def __init__(self, repo: CatalogRepository) -> None:
        self.repo = repo

    async def ingest_openrouter(self, items: list[OpenRouterModel], now: datetime) -> int:
        platform_id = await self.repo.get_platform_id(OPENROUTER_PLATFORM)
        if platform_id is None:
            raise AppError("NOT_FOUND", "平台 openrouter 未收录，先导入种子数据")

        # 同一批里 slug 重复时 Postgres 的 upsert 会报错：保留第一个并记录
        unique: dict[str, OpenRouterModel] = {}
        for item in items:
            if item.slug in unique:
                logger.warning(
                    "OpenRouter slug 冲突，跳过 {}（已有 {}）",
                    item.model_id,
                    unique[item.slug].model_id,
                )
                continue
            unique[item.slug] = item
        items = list(unique.values())

        model_rows: list[dict[str, Any]] = [
            {
                "slug": item.slug,
                "name": item.name,
                "family": item.family,
                "context_window": item.context_window,
                "description": "",
                "status": PublishStatus.ACTIVE,
            }
            for item in items
        ]
        model_ids = await self.repo.upsert_models(model_rows)

        price_rows: list[dict[str, Any]] = []
        for item in items:
            price_rows.append(
                {
                    "platform_id": platform_id,
                    "model_id": model_ids[item.slug],
                    "currency": Currency.USD,
                    "input_price": item.input_price,
                    "output_price": item.output_price,
                    "cache_read_price": item.cache_read_price,
                    "is_free": item.has_free,
                    "free_note": _free_note(item),
                    "source_url": f"https://openrouter.ai/{item.model_id}",
                    "confirmed_at": now,
                    "status": PublishStatus.ACTIVE,
                }
            )
        await self.repo.upsert_prices(price_rows)
        await self.repo.session.commit()
        logger.info("OpenRouter 入库完成：{} 个模型", len(items))
        return len(items)
