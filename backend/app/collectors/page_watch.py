"""页面变更监测：抓取官方页面 → 提取正文 → 算 hash。正文没变就不必再交给 LLM。

只抓静态 HTML。前端渲染的页面拿不到正文，报「正文过短」，由后台换成文档页 / 公告页等静态地址。
"""

import hashlib
import re
from typing import ClassVar

import httpx
import trafilatura
from pydantic import BaseModel

from app.collectors.base import USER_AGENT, Collector, CollectResult, SourceConfig
from app.collectors.registry import register

MIN_TEXT_LENGTH = 200
# 交给 LLM 的正文上限（字符）：活动信息通常在页面前部，截断控制费用
MAX_TEXT_LENGTH = 12_000
_BLANK_LINES = re.compile(r"\n\s*\n+")


class PageSnapshot(BaseModel):
    url: str
    text: str
    content_hash: str


def extract_text(html: str) -> str:
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    return _BLANK_LINES.sub("\n\n", text).strip()[:MAX_TEXT_LENGTH]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@register
class PageWatchCollector(Collector[PageSnapshot]):
    kind: ClassVar[str] = "page_watch"

    async def collect(self, source: SourceConfig) -> CollectResult[PageSnapshot]:
        result = CollectResult[PageSnapshot](source_id=source.id)
        try:
            # 显式带上：后台「立即检查」用的是 API 进程共享的客户端，默认不跟随重定向
            resp = await self.client.get(
                source.url, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            result.errors.append(f"抓取失败：{exc}")
            return result
        text = extract_text(resp.text)
        if len(text) < MIN_TEXT_LENGTH:
            result.errors.append(
                f"正文过短（{len(text)} 字），可能是前端渲染的页面，请换成静态的文档页或公告页"
            )
            return result
        result.items.append(
            PageSnapshot(url=str(resp.url), text=text, content_hash=content_hash(text))
        )
        return result
