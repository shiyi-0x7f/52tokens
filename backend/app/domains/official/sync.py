"""官方订阅地区价同步：按 data/official/app_store.yaml 抓取各 App 在各地区 App Store 的
档位价格并入库。

写入规则（失败不等于没上架，见 collectors/base.py 的边界）：
- 页面抓取 / 解析失败：该 App 该地区的数据一律不动；
- App Store 返回 404：该地区没上架这个 App，各档位标为 missing；
- 页面正常、档位匹配到唯一价格：写入当地价、按当天汇率折合的人民币价，fetched_at 记为本次；
- 页面正常但没匹配到：原来有价格的保持不动（可能是临时改名，避免误删），原来没有的标为 missing；
- 匹配到多个且无法区分：不写入，计入报告待人工核实。
汇率拿不到时整批放弃，已有数据不变。
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from app.collectors.app_store import (
    AppConfig,
    AppStoreConfig,
    RegionConfig,
    RegionPage,
    fetch_region,
    match_plan,
)
from app.domains.official.repository import OfficialRepository
from app.integrations.fx import FxSnapshot, fetch_usd_rates

# 对 App Store 保持克制：短时间请求太密会被 403 限流（实测连续两轮约 400 次请求即触发）。
# 2 并发 + 每槽间隔 1 秒，一轮约 200 个页面 3 分钟左右
CONCURRENCY = 2
REQUEST_GAP_SECONDS = 1.0
MAX_REPORTED_ISSUES = 30
CENT = Decimal("0.01")
FX_PLACES = Decimal("0.00000001")


class SyncReport(BaseModel):
    fx_source: str = ""
    fx_date: str = ""
    plans: int = 0
    plans_removed: int = 0
    pages_ok: int = 0
    pages_not_found: int = 0
    pages_failed: int = 0
    available: int = 0
    missing: int = 0
    kept: int = 0  # 没匹配到、保留原价格的
    ambiguous: int = 0
    issues: list[str] = Field(default_factory=list)  # 失败 / 待核实明细（截断）

    def note(self, text: str) -> None:
        if len(self.issues) < MAX_REPORTED_ISSUES:
            self.issues.append(text)


class OfficialSyncService:
    def __init__(
        self, repo: OfficialRepository, client: httpx.AsyncClient, config: AppStoreConfig
    ) -> None:
        self.repo = repo
        self.client = client
        self.config = config

    async def _fetch_all(self) -> list[tuple[AppConfig, RegionConfig, RegionPage]]:
        slots = asyncio.Semaphore(CONCURRENCY)

        async def one(
            app: AppConfig, region: RegionConfig
        ) -> tuple[AppConfig, RegionConfig, RegionPage]:
            async with slots:
                page = await fetch_region(self.client, app, region)
                await asyncio.sleep(REQUEST_GAP_SECONDS)
                return app, region, page

        return await asyncio.gather(
            *(one(a, r) for a in self.config.apps for r in self.config.regions)
        )

    async def _sync_plans(self, report: SyncReport) -> dict[tuple[str, str], int]:
        rows = [
            {
                "app_slug": app.slug,
                "app_name": app.name,
                "provider": app.provider,
                "plan_slug": plan.slug,
                "plan_name": plan.name,
                "billing_period": plan.billing_period,
                "sort_order": plan.sort_order,
            }
            for app in self.config.apps
            for plan in app.plans
        ]
        ids = await self.repo.upsert_plans(rows)
        report.plans = len(ids)
        report.plans_removed = await self.repo.delete_plans_except(set(ids))
        return ids

    async def sync_all(self) -> SyncReport:
        report = SyncReport()
        now = datetime.now(UTC)
        fx = await fetch_usd_rates(self.client, self.config.currencies(), now.date())
        report.fx_source, report.fx_date = fx.source, fx.day.isoformat()
        pages = await self._fetch_all()  # 先抓完再写库，避免长时间占着事务

        plan_ids = await self._sync_plans(report)
        had_price = await self.repo.available_keys()
        rows: list[dict[str, Any]] = []
        for app, region, page in pages:
            rows.extend(self._rows(app, region, page, fx, now, plan_ids, had_price, report))
        await self.repo.upsert_prices(rows)
        await self.repo.commit()
        return report

    def _rows(
        self,
        app: AppConfig,
        region: RegionConfig,
        page: RegionPage,
        fx: FxSnapshot,
        now: datetime,
        plan_ids: dict[tuple[str, str], int],
        had_price: set[tuple[int, str]],
        report: SyncReport,
    ) -> list[dict[str, Any]]:
        where = f"{app.slug}/{region.code}"
        if page.status == "failed":
            report.pages_failed += 1
            report.note(f"{where} 抓取失败：{page.error}")
            logger.warning("App Store 抓取失败 {} {}：{}", where, page.url, page.error)
            return []
        base = {
            "country_code": region.code,
            "country_label": region.label,
            "currency": region.currency,
            "source_url": page.url,
            "fetched_at": now,
        }
        missing = base | {
            "price_text": "",
            "price_value": None,
            "cny_price": None,
            "fx_rate_to_cny": None,
            "fx_date": None,
            "status": "missing",
        }
        if page.status == "not_found":
            report.pages_not_found += 1
            report.missing += len(app.plans)
            return [missing | {"plan_id": plan_ids[(app.slug, p.slug)]} for p in app.plans]

        report.pages_ok += 1
        to_cny = fx.to_cny(region.currency)
        out: list[dict[str, Any]] = []
        for plan in app.plans:
            plan_id = plan_ids[(app.slug, plan.slug)]
            result = match_plan(page.items, plan, fx.to_usd(region.currency))
            if result.status == "matched" and result.item is not None:
                report.available += 1
                value = result.item.price_value
                out.append(
                    base
                    | {
                        "plan_id": plan_id,
                        "price_text": result.item.price_text,
                        "price_value": value.quantize(CENT),
                        "cny_price": (value * to_cny).quantize(CENT),
                        "fx_rate_to_cny": to_cny.quantize(FX_PLACES),
                        "fx_date": fx.day,
                        "status": "available",
                    }
                )
            elif result.status == "ambiguous":
                report.ambiguous += 1
                options = "；".join(f"{c.title} {c.price_text}" for c in result.candidates)
                report.note(f"{where}/{plan.slug} 匹配到多个价格，待核实：{options}")
            elif (plan_id, region.code) in had_price:
                report.kept += 1
                report.note(f"{where}/{plan.slug} 没匹配到，保留原价格")
            else:
                report.missing += 1
                out.append(missing | {"plan_id": plan_id})
        return out
