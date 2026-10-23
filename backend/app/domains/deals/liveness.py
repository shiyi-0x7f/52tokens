"""活动存活检查：定时回访已发布活动的官方出处，发现下线就下沉到「已结束」。

误判（把还在的活动标成结束）比晚几天下沉代价大，所以：
- 截止时间已过：直接标记结束；
- 「硬信号」——页面 404 / 410，或存的官网原文已不在页面上——连续 EXPIRE_AFTER_FAILS 次才自动结束，
  之前只在后台提示「疑似下线」；
- 网络错误、超时、5xx、403 等不算下线（抓取失败 ≠ 活动下线），不累计次数；
- 页面正常且原文还在：刷新核实时间（confirmed_at），公开站显示的新鲜度是真实的。
"""

from datetime import UTC, datetime
from typing import Literal

import httpx
from loguru import logger
from pydantic import BaseModel

from app.collectors.base import USER_AGENT
from app.collectors.page_watch import MIN_TEXT_LENGTH, extract_text
from app.domains.deals.links import quote_in_text
from app.domains.deals.models import Deal, DealStatus
from app.domains.deals.repository import DealRepository

EXPIRE_AFTER_FAILS = 3
GONE_STATUS = {404, 410}

Outcome = Literal["expired_by_date", "alive", "reachable", "suspect", "expired", "skipped"]


class LivenessReport(BaseModel):
    checked: int = 0
    alive: int = 0  # 原文仍在，已刷新核实时间
    reachable: int = 0  # 页面能打开（没有原文可对照）
    suspect: int = 0  # 有下线信号，次数未到
    expired: int = 0  # 本次标记为已结束（含截止时间已过）
    skipped: int = 0  # 网络错误等，不下结论


class DealLivenessService:
    def __init__(self, repo: DealRepository, http: httpx.AsyncClient) -> None:
        self.repo = repo
        self.http = http

    async def check_all(self) -> LivenessReport:
        report = LivenessReport()
        for deal in await self.repo.list_for_liveness():
            slug = deal.slug  # 出错后会话失效，不能再读对象属性
            try:
                outcome = await self.check(deal)
            except Exception:
                await self.repo.rollback()
                logger.exception("存活检查出错 deal={}", slug)
                outcome = "skipped"
            report.checked += 1
            if outcome == "expired_by_date":
                report.expired += 1
            else:
                setattr(report, outcome, getattr(report, outcome) + 1)
        logger.info("活动存活检查完成 {}", report.model_dump())
        return report

    async def check(self, deal: Deal) -> Outcome:
        now = datetime.now(UTC)
        deal.liveness_checked_at = now
        if deal.ends_at is not None and deal.ends_at <= now:
            return await self._expire(deal, now, "已过截止时间", by_date=True)

        issue = await self._probe(deal)
        if issue is None:
            # 页面正常：有原文且还在 → 刷新核实时间；没有原文只能说明页面能打开
            deal.liveness_issue = ""
            deal.liveness_fail_count = 0
            outcome: Outcome = "reachable"
            if deal.source_quote:
                deal.confirmed_at = now
                outcome = "alive"
            await self.repo.commit()
            return outcome
        if issue == "":
            await self.repo.commit()  # 不下结论，只记检查时间
            return "skipped"

        deal.liveness_issue = issue
        deal.liveness_fail_count += 1
        if deal.liveness_fail_count >= EXPIRE_AFTER_FAILS:
            return await self._expire(deal, now, issue)
        await self.repo.commit()
        logger.info("活动疑似下线 deal={} 第 {} 次：{}", deal.slug, deal.liveness_fail_count, issue)
        return "suspect"

    async def _probe(self, deal: Deal) -> str | None:
        """None = 页面正常；"" = 不确定（网络错误等）；其他 = 下线信号的描述。"""
        try:
            resp = await self.http.get(
                deal.source_url, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            )
        except httpx.HTTPError as exc:
            logger.info("存活检查抓取失败 deal={} {}", deal.slug, type(exc).__name__)
            return ""
        if resp.status_code in GONE_STATUS:
            return f"官方页面已不存在（HTTP {resp.status_code}）"
        if resp.status_code >= 400:
            return ""
        if deal.source_quote:
            text = extract_text(resp.text)
            if len(text) < MIN_TEXT_LENGTH:
                return ""  # 验证页 / 前端渲染壳：拿不到正文，不能据此判断原文没了
            if not quote_in_text(deal.source_quote, text):
                return "官网原文已不在页面上"
        return None

    async def _expire(
        self, deal: Deal, now: datetime, reason: str, *, by_date: bool = False
    ) -> Outcome:
        deal.status = DealStatus.EXPIRED
        deal.reviewed_by_id = None  # 系统操作
        deal.reviewed_at = now
        deal.liveness_issue = reason
        await self.repo.commit()
        logger.info("活动已自动标记结束 deal={} 原因：{}", deal.slug, reason)
        return "expired_by_date" if by_date else "expired"
