"""活动采集：正文没变不调 LLM、新活动进待审核、匹配已有活动、各种失败只记在来源上。"""

from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import Collector, CollectResult, SourceConfig
from app.collectors.page_watch import PageSnapshot, content_hash
from app.domains.deals.models import Deal, DealOrigin, DealSource, DealStatus
from app.domains.deals.source_repository import DealSourceRepository
from app.domains.deals.watch import (
    NO_LLM_ERROR,
    CheckReport,
    DealWatchService,
    ProgressCallback,
)
from app.domains.deals.watch_batch import BatchCheckService
from app.integrations.llm import LlmError
from tests import factories as f
from tests.fakes import MemoryStore

PAGE_TEXT = "新用户注册送 100 万 tokens。每日签到送 200 积分。"


class FakeCollector(Collector[PageSnapshot]):
    kind = "fake"

    def __init__(self, text: str = PAGE_TEXT, error: str | None = None) -> None:
        super().__init__(httpx.AsyncClient())
        self.text = text
        self.error = error

    async def collect(self, source: SourceConfig) -> CollectResult[PageSnapshot]:
        result = CollectResult[PageSnapshot](source_id=source.id)
        if self.error:
            result.errors.append(self.error)
        else:
            result.items.append(
                PageSnapshot(url=source.url, text=self.text, content_hash=content_hash(self.text))
            )
        return result


class FakeLlm:
    def __init__(self, deals: list[dict[str, Any]] | None = None, fail: bool = False) -> None:
        self.deals = deals or []
        self.fail = fail
        self.prompts: list[str] = []

    async def extract[M: BaseModel](self, *, system: str, user: str, schema: type[M]) -> M:
        self.prompts.append(user)
        if self.fail:
            raise LlmError("LLM 调用失败：timeout")
        return schema.model_validate({"deals": self.deals})


def _item(title: str, **kw: Any) -> dict[str, Any]:
    return {
        "title": title,
        "deal_type": kw.pop("deal_type", "signup_credit"),
        "reward_text": kw.pop("reward_text", "100 万 tokens"),
        "confidence": kw.pop("confidence", 0.9),
        "evidence": kw.pop("evidence", "新用户注册送 100 万 tokens"),
        **kw,
    }


async def _setup(session: AsyncSession, **source_kw: Any) -> DealSource:
    p = await f.platform(session, "bailian")
    src = await f.deal_source(session, p, **source_kw)
    await session.commit()
    loaded = await DealSourceRepository(session).get(src.id)
    assert loaded is not None
    return loaded


def _service(
    session: AsyncSession, llm: FakeLlm | None, collector: FakeCollector | None = None
) -> DealWatchService:
    return DealWatchService(DealSourceRepository(session), collector or FakeCollector(), llm)


async def _deals(session: AsyncSession) -> list[Deal]:
    return list((await session.scalars(select(Deal).order_by(Deal.id))).all())


async def test_new_deals_go_to_review_queue(db_session: AsyncSession) -> None:
    src = await _setup(db_session)
    llm = FakeLlm(
        [
            _item("新人送 100 万 tokens", ends_at=str(date.today() + timedelta(days=30))),
            _item("每日签到", deal_type="checkin_points", cycle="daily", confidence=0.5),
        ]
    )
    report = await _service(db_session, llm).check(src)

    assert report.status == "extracted"
    assert report.created == 2
    deals = await _deals(db_session)
    first = deals[0]
    assert first.status == DealStatus.PENDING
    assert first.origin == DealOrigin.COLLECTOR
    assert first.source_id == src.id
    assert first.source_url == src.url
    assert first.confirmed_at is None
    assert str(first.extract_confidence) == "0.90"
    assert first.extract_note == "新用户注册送 100 万 tokens"
    assert first.slug.startswith("bailian-signup-credit-")
    assert first.ends_at is not None
    assert src.content_hash == content_hash(PAGE_TEXT)
    assert src.changed_at is not None
    assert "平台：Bailian" in llm.prompts[0]


async def test_steps_kept_and_quote_only_when_on_page(db_session: AsyncSession) -> None:
    src = await _setup(db_session)
    llm = FakeLlm(
        [
            _item(
                "新人送 tokens", evidence="新用户注册送 100 万 tokens", steps=[" 注册 ", "", "领取"]
            ),
            _item("编造原文的活动", evidence="新用户注册送 1000 万 tokens"),
        ]
    )
    await _service(db_session, llm).check(src)
    real, made_up = await _deals(db_session)
    assert real.steps == ["注册", "领取"]
    assert real.source_quote == "新用户注册送 100 万 tokens"
    assert made_up.source_quote == ""
    assert made_up.extract_note == "新用户注册送 1000 万 tokens"  # 依据仍留给审核


async def test_unchanged_page_skips_llm(db_session: AsyncSession) -> None:
    src = await _setup(db_session, content_hash=content_hash(PAGE_TEXT), fail_count=2)
    llm = FakeLlm([_item("x 活动")])
    report = await _service(db_session, llm).check(src)
    assert report.status == "unchanged"
    assert llm.prompts == []
    assert src.fail_count == 0
    assert src.checked_at is not None


async def test_noise_expired_and_duplicates_are_skipped(db_session: AsyncSession) -> None:
    src = await _setup(db_session)
    await f.deal(
        db_session, src.platform, "known", title="新人 送 100万tokens", status=DealStatus.PENDING
    )
    await db_session.commit()
    llm = FakeLlm(
        [
            _item("低置信度", confidence=0.1),
            _item("已结束的活动", ends_at=str(date.today() - timedelta(days=1))),
            _item("新人送 100万tokens"),  # 与已收录的只差空格
            _item("同一批里的重复"),
            _item("同一批里的 重复"),
        ]
    )
    report = await _service(db_session, llm).check(src)
    assert report.created == 1
    assert [d.title for d in await _deals(db_session)] == ["新人 送 100万tokens", "同一批里的重复"]


async def test_matching_existing_deal(db_session: AsyncSession) -> None:
    src = await _setup(db_session)
    old = f.NOW - f.days(10)
    await f.deal(db_session, src.platform, "live", confirmed_at=old)
    await f.deal(db_session, src.platform, "unsure", confirmed_at=old)
    await f.deal(
        db_session, src.platform, "rejected", status=DealStatus.REJECTED, confirmed_at=None
    )
    await db_session.commit()
    llm = FakeLlm(
        [
            _item("改了措辞的同一活动", matches_existing="live", confidence=0.95),
            _item("不太确定", matches_existing="unsure", confidence=0.6),
            _item("被驳回过的", matches_existing="rejected", confidence=0.99),
        ]
    )
    report = await _service(db_session, llm).check(src)

    assert (report.created, report.reconfirmed) == (0, 1)
    by_slug = {d.slug: d for d in await _deals(db_session)}
    assert by_slug["live"].confirmed_at is not None and by_slug["live"].confirmed_at > old
    assert by_slug["live"].title == "live 活动"  # 不改字段
    assert by_slug["unsure"].confirmed_at == old
    assert by_slug["rejected"].status == DealStatus.REJECTED
    assert "rejected" in llm.prompts[0]


async def test_without_llm_key_keeps_hash_for_retry(db_session: AsyncSession) -> None:
    src = await _setup(db_session)
    report = await _service(db_session, None).check(src)
    assert report.status == "failed"
    assert report.error == NO_LLM_ERROR
    assert src.content_hash is None
    assert src.fail_count == 1


async def test_fetch_and_llm_failures_are_recorded(db_session: AsyncSession) -> None:
    src = await _setup(db_session)
    fetch_fail = FakeCollector(error="抓取失败：timeout")
    report = await _service(db_session, FakeLlm(), fetch_fail).check(src)
    assert report.status == "failed"
    assert src.last_error == "抓取失败：timeout"

    report = await _service(db_session, FakeLlm(fail=True)).check(src)
    assert report.status == "failed"
    assert src.fail_count == 2
    assert src.content_hash is None
    assert await _deals(db_session) == []


async def test_batch_lock_is_released_even_on_error(db_session: AsyncSession) -> None:
    store = MemoryStore()
    batch = BatchCheckService(store)
    assert await batch.acquire()
    assert not await batch.acquire()

    class Boom(DealWatchService):
        async def check_all(self, on_progress: ProgressCallback | None = None) -> list[CheckReport]:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await batch.run(Boom(DealSourceRepository(db_session), FakeCollector(), None))
    assert (await batch.status()).running is None
    assert await batch.acquire()


async def test_check_all_reports_progress(db_session: AsyncSession) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal_source(db_session, p, url="https://a.example.com")
    await f.deal_source(db_session, p, url="https://b.example.com")
    await db_session.commit()
    seen: list[tuple[int, int]] = []

    async def on_progress(done: int, total: int) -> None:
        seen.append((done, total))

    await _service(db_session, FakeLlm()).check_all(on_progress)
    assert seen == [(1, 2), (2, 2)]


async def test_check_all_only_enabled(db_session: AsyncSession) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal_source(db_session, p, url="https://a.example.com")
    await f.deal_source(db_session, p, url="https://b.example.com", enabled=False)
    await db_session.commit()
    reports = await _service(db_session, FakeLlm([_item("新活动")])).check_all()
    assert len(reports) == 1
    assert reports[0].created == 1
