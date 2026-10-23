"""活动采集：检查监测来源 → 正文有变化才调用 LLM 抽取 → 新活动进「待审核」。

规则：
- 抓取或抽取失败只记在来源上（last_error / fail_count），不动已有活动；
- 新活动一律是待审核，标明来自采集，附置信度和原文依据；
- 匹配到已发布活动时，只有高置信度才自动刷新核实时间，不改任何字段；
- 已驳回的活动也参与匹配，避免同一条线索被反复提出。
"""

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from loguru import logger
from pydantic import BaseModel

from app.collectors.base import Collector, SourceConfig
from app.collectors.page_watch import PageSnapshot
from app.domains.deals.admin import new_deal_slug
from app.domains.deals.extraction import (
    AUTO_CONFIRM_CONFIDENCE,
    MIN_CONFIDENCE,
    SYSTEM_PROMPT,
    ExistingDeal,
    ExtractedDeal,
    Extraction,
    build_user_prompt,
)
from app.domains.deals.links import normalize_space, quote_in_text
from app.domains.deals.models import Deal, DealOrigin, DealSource, DealStatus
from app.domains.deals.source_repository import DealSourceRepository
from app.integrations.llm import LlmError

# 官网写的截止日期按北京时间当天结束计
DEADLINE_TZ = ZoneInfo("Asia/Shanghai")
NO_LLM_ERROR = "未配置 SILICONFLOW_API_KEY，已跳过抽取"


class Extractor(Protocol):
    async def extract[M: BaseModel](self, *, system: str, user: str, schema: type[M]) -> M: ...


ProgressCallback = Callable[[int, int], Awaitable[None]]  # (已检查, 总数)


class CheckReport(BaseModel):
    source_id: int
    status: Literal["failed", "unchanged", "extracted"]
    created: int = 0
    reconfirmed: int = 0
    error: str = ""


def _norm(title: str) -> str:
    return "".join(title.lower().split())


def _deadline(day: date | None) -> datetime | None:
    return datetime.combine(day, time(23, 59, 59), tzinfo=DEADLINE_TZ) if day else None


class DealWatchService:
    def __init__(
        self,
        repo: DealSourceRepository,
        collector: Collector[PageSnapshot],
        llm: Extractor | None,
    ) -> None:
        self.repo = repo
        self.collector = collector
        self.llm = llm

    async def check_all(self, on_progress: ProgressCallback | None = None) -> list[CheckReport]:
        reports = []
        sources = await self.repo.list_enabled()
        for done, source in enumerate(sources, start=1):
            try:
                reports.append(await self.check(source))
            except Exception as exc:
                # 单个来源出意外不影响其他来源；完整堆栈进日志
                logger.exception("检查监测来源出错 source={}", source.id)
                await self.repo.rollback()  # 会话可能已失效，回滚后才能继续检查下一个
                reports.append(
                    CheckReport(source_id=source.id, status="failed", error=f"意外错误：{exc}")
                )
            if on_progress is not None:
                await on_progress(done, len(sources))
        return reports

    async def check(self, source: DealSource) -> CheckReport:
        now = datetime.now(UTC)
        source.checked_at = now
        result = await self.collector.collect(SourceConfig(id=str(source.id), url=source.url))
        if not result.ok:
            return await self._fail(source, "；".join(result.errors))
        snapshot = result.items[0]
        if snapshot.content_hash == source.content_hash:
            source.last_error = ""
            source.fail_count = 0
            await self.repo.commit()
            return CheckReport(source_id=source.id, status="unchanged")
        if self.llm is None:
            # 不更新 hash：配置好 key 之后还会抽取这次的内容
            return await self._fail(source, NO_LLM_ERROR)

        existing = await self.repo.platform_deals(source.platform_id)
        try:
            extraction = await self.llm.extract(
                system=SYSTEM_PROMPT,
                user=build_user_prompt(
                    platform_name=source.platform.name,
                    url=source.url,
                    text=snapshot.text,
                    existing=[
                        ExistingDeal(slug=d.slug, title=d.title, reward_text=d.reward_text)
                        for d in existing
                    ],
                ),
                schema=Extraction,
            )
        except LlmError as exc:
            return await self._fail(source, str(exc))

        created, reconfirmed = self._apply(
            source, extraction.deals, existing, now, page_text=snapshot.text
        )
        source.content_hash = snapshot.content_hash
        source.changed_at = now
        source.last_error = ""
        source.fail_count = 0
        await self.repo.commit()
        logger.info("监测来源已抽取 source={} 新增={} 刷新核实={}", source.id, created, reconfirmed)
        return CheckReport(
            source_id=source.id, status="extracted", created=created, reconfirmed=reconfirmed
        )

    async def _fail(self, source: DealSource, error: str) -> CheckReport:
        source.last_error = error[:300]
        source.fail_count += 1
        await self.repo.commit()
        logger.warning("监测来源检查失败 source={} error={}", source.id, error)
        return CheckReport(source_id=source.id, status="failed", error=source.last_error)

    def _apply(
        self,
        source: DealSource,
        items: list[ExtractedDeal],
        existing: Sequence[Deal],
        now: datetime,
        *,
        page_text: str,
    ) -> tuple[int, int]:
        by_slug = {d.slug: d for d in existing}
        titles = {_norm(d.title) for d in existing}
        created = reconfirmed = 0
        for item in items:
            if item.confidence < MIN_CONFIDENCE:
                continue
            ends_at = _deadline(item.ends_at)
            if ends_at is not None and ends_at <= now:
                continue
            match = by_slug.get(item.matches_existing or "")
            if match is not None:
                if match.status == DealStatus.ACTIVE and item.confidence >= AUTO_CONFIRM_CONFIDENCE:
                    match.confirmed_at = now
                    reconfirmed += 1
                continue
            if _norm(item.title) in titles:
                continue
            titles.add(_norm(item.title))
            self.repo.add(self._new_deal(source, item, ends_at, page_text))
            created += 1
        return created, reconfirmed

    @staticmethod
    def _new_deal(
        source: DealSource, item: ExtractedDeal, ends_at: datetime | None, page_text: str
    ) -> Deal:
        # LLM 给的原文核对过确实在页面上才对外展示（否则定位链接会落空）；依据照旧留给审核
        quote = item.evidence if quote_in_text(item.evidence, page_text) else ""
        return Deal(
            slug=new_deal_slug(source.platform.slug, item.deal_type),
            platform_id=source.platform_id,
            title=item.title.strip(),
            deal_type=item.deal_type,
            reward_text=item.reward_text.strip(),
            requirements=item.requirements,
            cycle=item.cycle,
            ends_at=ends_at,
            description=item.description.strip(),
            steps=item.steps,
            source_url=source.url,
            source_quote=normalize_space(quote),
            in_app_only=item.in_app_only,
            status=DealStatus.PENDING,
            origin=DealOrigin.COLLECTOR,
            source_id=source.id,
            extract_confidence=Decimal(str(round(item.confidence, 2))),
            extract_note=item.evidence,
        )
