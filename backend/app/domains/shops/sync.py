"""卡网采集入库：抓取店铺 → 归类 → upsert 报价。

规则：
- 报价按（店铺, 店铺内商品标识）upsert，每次按标题重新归类；
  后台人工指定过的（match_method=manual）不覆盖；
- 采集成功但这次没出现的报价标为无货（不删除）；
- 采集失败只记在店铺上（last_error / fail_count），报价一律不动（采集失败 ≠ 下架）。
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

import httpx
from loguru import logger
from pydantic import BaseModel

from app.collectors.base import CollectResult, SourceConfig
from app.collectors.registry import get_collector_class
from app.collectors.shops.base import ShopItem
from app.domains.shops.classify import classify_title
from app.domains.shops.models import ShopOffer, ShopSource
from app.domains.shops.repository import ShopRepository


class ShopSyncReport(BaseModel):
    source_id: int
    status: Literal["synced", "failed"]
    offers: int = 0
    created: int = 0
    gone: int = 0  # 这次没出现、标为无货的
    error: str = ""


class ShopSyncService:
    def __init__(self, repo: ShopRepository, http: httpx.AsyncClient) -> None:
        self.repo = repo
        self.http = http

    async def sync_all(self) -> list[ShopSyncReport]:
        reports = []
        for source in await self.repo.list_enabled_sources():
            source_id = source.id  # 出错后会话失效，不能再读对象属性
            try:
                reports.append(await self.sync(source))
            except Exception as exc:
                await self.repo.rollback()
                logger.exception("卡网店铺同步出错 source={}", source_id)
                reports.append(
                    ShopSyncReport(source_id=source_id, status="failed", error=str(exc)[:300])
                )
        return reports

    async def sync(self, source: ShopSource) -> ShopSyncReport:
        collector = get_collector_class(source.collector_kind.value)(self.http)
        result = await collector.collect(
            SourceConfig(
                id=str(source.id), url=source.entry_url, options={"base_url": source.base_url}
            )
        )
        return await self.apply(source, result, datetime.now(UTC))

    async def apply(
        self, source: ShopSource, result: CollectResult[ShopItem], now: datetime
    ) -> ShopSyncReport:
        source.checked_at = now
        if not result.ok:
            source.last_error = "；".join(result.errors)[:300]
            source.fail_count += 1
            await self.repo.commit()
            logger.warning("卡网店铺采集失败 source={} {}", source.entry_url, source.last_error)
            return ShopSyncReport(source_id=source.id, status="failed", error=source.last_error)

        created, gone = await self._upsert(source.id, result.items, now)
        source.success_at = now
        source.last_error = ""
        source.fail_count = 0
        source.offer_count = len(result.items)
        await self.repo.commit()
        return ShopSyncReport(
            source_id=source.id,
            status="synced",
            offers=len(result.items),
            created=created,
            gone=gone,
        )

    async def _upsert(
        self, source_id: int, items: Sequence[ShopItem], now: datetime
    ) -> tuple[int, int]:
        products = await self.repo.product_ids_by_slug()
        existing = await self.repo.offers_for_source(source_id)
        created = 0
        for item in items:
            offer = existing.get(item.external_id)
            if offer is None:
                offer = ShopOffer(
                    source_id=source_id, external_id=item.external_id, first_seen_at=now
                )
                self.repo.add(offer)
                created += 1
            offer.title = item.title
            offer.url = item.url
            offer.price = item.price
            offer.stock = item.stock
            offer.in_stock = item.in_stock
            offer.tags = item.tags
            offer.last_seen_at = now
            if offer.match_method != "manual":
                offer.match_method = "rule"
                offer.product_id = products.get(classify_title(item.title, " ".join(item.tags)))
        seen = {i.external_id for i in items}
        gone = 0
        for external_id, offer in existing.items():
            if external_id not in seen and offer.in_stock:
                offer.in_stock = False
                gone += 1
        return created, gone
