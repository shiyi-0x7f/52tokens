"""卡网采集器基类：每种店铺系统一个子类，只负责把公开商品列表解析成 ShopItem。

边界：只读公开商品列表（不下单、不登录），不绕过验证码、风控页、加密页；采集请求如实标明身份。
一次采集一个商品都没拿到按失败处理：店铺改版或接口异常时不能被误判成「全部下架」。
"""

import asyncio
import hashlib
import json
from abc import abstractmethod
from decimal import Decimal
from typing import Any, ClassVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from app.collectors.base import USER_AGENT, Collector, CollectResult, SourceConfig
from app.collectors.shops.parse import clean_text, is_non_comparable

PAGE_DELAY_SECONDS = 0.5  # 同一店铺翻页 / 逐个查详情之间的间隔，避免给店铺压力
_CHALLENGE_HINTS = ("<html", "<script", "captcha", "verify", "challenge", "验证", "风控", "安全")


class ShopFetchError(Exception):
    """店铺返回了非预期内容（风控页、接口报错、结构变化等）。"""


class ShopTarget(BaseModel):
    base_url: str  # https://host
    entry_url: str  # 店铺地址；多商户平台是具体商户页


class ShopItem(BaseModel):
    external_id: str  # 店铺内稳定标识：链接 + 标题的哈希
    title: str
    url: str
    price: Decimal
    stock: int | None = None
    in_stock: bool = True
    tags: list[str] = Field(default_factory=list)


def make_item(
    *,
    title: object,
    price: Decimal | None,
    url: str,
    stock: int | None = None,
    disabled: bool = False,
    tags: list[str] | None = None,
) -> ShopItem | None:
    """标准化一条报价；没标题、没价格、非比价商品（打赏 / 测试等）返回 None。"""
    text = clean_text(title)
    if not text or price is None or price < 0 or is_non_comparable(text):
        return None
    digest = hashlib.sha1(f"{url}\n{text}".encode(), usedforsecurity=False).hexdigest()
    return ShopItem(
        external_id=digest,
        title=text[:300],
        url=url[:500],
        price=price.quantize(Decimal("0.01")),
        stock=stock,
        in_stock=not disabled and (stock is None or stock > 0),
        tags=[t[:60] for t in (tags or [])][:8],
    )


def base_url_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class ShopCollector(Collector[ShopItem]):
    kind: ClassVar[str]
    headers: ClassVar[dict[str, str]] = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }

    async def collect(self, source: SourceConfig) -> CollectResult[ShopItem]:
        result = CollectResult[ShopItem](source_id=source.id)
        target = ShopTarget(
            base_url=str(source.options.get("base_url") or base_url_of(source.url)).rstrip("/"),
            entry_url=source.url,
        )
        try:
            items = await self.fetch(target)
        except (httpx.HTTPError, ShopFetchError) as exc:
            result.errors.append(f"{type(exc).__name__} {exc}".strip()[:300])
            return result
        # 同一店铺里重复的报价（同链接同标题）只留一条
        result.items = list({i.external_id: i for i in items}.values())
        if not result.items:
            result.errors.append("没有采集到任何商品（店铺可能改版、关店或接口异常）")
        return result

    @abstractmethod
    async def fetch(self, target: ShopTarget) -> list[ShopItem]: ...

    # ---------- 请求工具 ----------

    async def pause(self) -> None:
        await asyncio.sleep(PAGE_DELAY_SECONDS)

    async def get_text(self, url: str, **kw: Any) -> str:
        resp = await self.client.get(url, headers=self.headers, follow_redirects=True, **kw)
        resp.raise_for_status()
        return resp.text

    async def get_json(self, url: str) -> Any:
        return self._parse_json(await self.get_text(url), url)

    async def post_json(self, url: str, body: Any, referer: str) -> Any:
        resp = await self.client.post(
            url,
            json=body,
            headers={**self.headers, "Referer": referer, "Accept": "application/json"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        return self._parse_json(resp.text, url)

    @staticmethod
    def _parse_json(text: str, url: str) -> Any:
        try:
            return json.loads(text)
        except ValueError:
            lowered = text[:2000].lower()
            if any(h in lowered for h in _CHALLENGE_HINTS):
                raise ShopFetchError(f"{url} 返回了验证或风控页面") from None
            raise ShopFetchError(f"{url} 返回了非 JSON 内容") from None
