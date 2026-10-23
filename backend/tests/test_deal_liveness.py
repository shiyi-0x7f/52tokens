"""活动存活检查：截止即结束、硬信号连续 3 次才结束、网络问题不算下线、原文仍在则刷新核实时间。"""

from collections.abc import Callable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.deals.liveness import EXPIRE_AFTER_FAILS, DealLivenessService
from app.domains.deals.models import Deal, DealStatus
from app.domains.deals.repository import DealRepository
from tests import factories as f

QUOTE = "每日签到可获得 200 积分"
PAGE = f"<html><body><article><p>{'活动规则说明。' * 40}{QUOTE}。</p></article></body></html>"
NO_QUOTE_PAGE = f"<html><body><article><p>{'活动规则说明。' * 40}</p></article></body></html>"


def _service(
    session: AsyncSession, handler: Callable[[httpx.Request], httpx.Response]
) -> DealLivenessService:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DealLivenessService(DealRepository(session), http)


def _page(html: str, status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _: httpx.Response(status, html=html)


async def _deal(session: AsyncSession, **kw: object) -> Deal:
    p = await f.platform(session, "trae")
    deal = await f.deal(session, p, "checkin", confirmed_at=f.NOW - f.days(10), **kw)
    await session.commit()
    return deal


async def test_quote_still_on_page_refreshes_confirmed_at(db_session: AsyncSession) -> None:
    deal = await _deal(db_session, source_quote=QUOTE, liveness_fail_count=2, liveness_issue="x")
    assert await _service(db_session, _page(PAGE)).check(deal) == "alive"
    assert deal.confirmed_at is not None and deal.confirmed_at > f.NOW
    assert (deal.liveness_fail_count, deal.liveness_issue) == (0, "")
    assert deal.liveness_checked_at is not None


async def test_without_quote_only_confirms_reachable(db_session: AsyncSession) -> None:
    deal = await _deal(db_session)
    old = deal.confirmed_at
    assert await _service(db_session, _page(NO_QUOTE_PAGE)).check(deal) == "reachable"
    assert deal.confirmed_at == old


async def test_past_deadline_expires_without_fetching(db_session: AsyncSession) -> None:
    deal = await _deal(db_session, ends_at=f.NOW - f.days(1))

    def boom(_: httpx.Request) -> httpx.Response:
        raise AssertionError("不应抓取")

    assert await _service(db_session, boom).check(deal) == "expired_by_date"
    assert deal.status == DealStatus.EXPIRED
    assert deal.liveness_issue == "已过截止时间"


async def test_gone_page_expires_only_after_repeated_signals(db_session: AsyncSession) -> None:
    deal = await _deal(db_session)
    service = _service(db_session, _page("", status=404))
    for i in range(1, EXPIRE_AFTER_FAILS):
        assert await service.check(deal) == "suspect"
        assert deal.liveness_fail_count == i
        assert deal.status == DealStatus.ACTIVE
    assert await service.check(deal) == "expired"
    assert deal.status == DealStatus.EXPIRED
    assert "HTTP 404" in deal.liveness_issue
    assert deal.reviewed_by_id is None and deal.reviewed_at is not None


async def test_missing_quote_is_a_signal(db_session: AsyncSession) -> None:
    deal = await _deal(db_session, source_quote=QUOTE)
    assert await _service(db_session, _page(NO_QUOTE_PAGE)).check(deal) == "suspect"
    assert deal.liveness_issue == "官网原文已不在页面上"


async def test_uncertain_responses_do_not_count(db_session: AsyncSession) -> None:
    deal = await _deal(db_session, source_quote=QUOTE, liveness_fail_count=2)

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    for handler in (
        timeout,
        _page("", status=503),
        _page("", status=403),
        _page("<html><body>Just a moment...</body></html>"),  # 验证页：正文太短
    ):
        assert await _service(db_session, handler).check(deal) == "skipped"
    assert deal.liveness_fail_count == 2
    assert deal.status == DealStatus.ACTIVE


async def test_check_all_only_active_and_reports(db_session: AsyncSession) -> None:
    p = await f.platform(db_session, "trae")
    await f.deal(db_session, p, "live", source_quote=QUOTE)
    await f.deal(db_session, p, "ended", ends_at=f.NOW - f.days(1))
    await f.deal(db_session, p, "pending", status=DealStatus.PENDING)
    await f.deal(db_session, p, "old", status=DealStatus.EXPIRED)
    await db_session.commit()

    report = await _service(db_session, _page(PAGE)).check_all()
    assert (report.checked, report.alive, report.expired) == (2, 1, 1)
