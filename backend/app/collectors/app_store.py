"""App Store 公开页面：读取 App 在某地区的「App 内购买项目」（名称 + 当地价格），
按规则匹配到订阅档位。

- 页面地址 https://apps.apple.com/{storefront}/app/{slug}/id{id}，无需登录；
  请求头带 X-Apple-Store-Front，避免被按出口 IP 跳到别的区。
- 项目列表有两种来源：页面内嵌 JSON 的 "addOns" 数组，以及 text-pair 的 HTML 片段；两者合并去重。
- 本模块只负责抓取和解析，不入库；配置见 data/official/app_store.yaml。
"""

import asyncio
import html as html_lib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "data" / "official" / "app_store.yaml"
PAGE_TIMEOUT = 25.0
FETCH_ATTEMPTS = 3
RETRY_BASE_SECONDS = 2.0  # 第 2、3 次分别等 2、4 秒
_NOT_AVAILABLE = "<string>itemNotAvailable</string>"
# 这些状态码重试；404 表示该地区没上架这个 App，不重试
RETRY_STATUSES = {403, 408, 429}


# ---------- 配置 ----------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanRule(_Strict):
    slug: str
    name: str
    billing_period: Literal["monthly", "annual"]
    sort_order: int = 0
    include: list[str]
    exclude: list[str] = Field(default_factory=list)
    price_band_usd: tuple[Decimal, Decimal] | None = None


class AppConfig(_Strict):
    slug: str
    name: str
    provider: str
    app_store_id: str
    app_store_slug: str
    plans: list[PlanRule]


class RegionConfig(_Strict):
    code: str = Field(pattern=r"^[A-Z]{2}$")
    label: str
    storefront: str = Field(pattern=r"^[a-z]{2}$")
    storefront_id: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class AppStoreConfig(_Strict):
    apps: list[AppConfig]
    regions: list[RegionConfig]

    def currencies(self) -> set[str]:
        return {r.currency for r in self.regions}


def load_config(path: Path = CONFIG_PATH) -> AppStoreConfig:
    return AppStoreConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def page_url(app: AppConfig, region: RegionConfig) -> str:
    return (
        f"https://apps.apple.com/{region.storefront}/app/{app.app_store_slug}/id{app.app_store_id}"
    )


# ---------- 解析 ----------


class StoreItem(BaseModel):
    title: str
    price_text: str
    price_value: Decimal


_PAIR = re.compile(
    r'<div class="text-pair[^"]*"[^>]*>\s*<span>([\s\S]*?)</span>\s*<span>([\s\S]*?)</span>'
)
_TAG = re.compile(r"<[^>]+>")
# 价格写法：货币符号 / 代码在前或在后。南非兰特写作 R 349,99，北欧克朗 249,00 kr，
# 波兰 99,99 zł，捷克 499,00 Kč，匈牙利 7 990 Ft，罗马尼亚 99,99 lei
_PRICE_SHAPE = re.compile(
    r"(?:[A-Z]{3}|[$€£¥₺₱₩￦₹₪₦₫฿]|HK\$|S\$|CA\$|A\$|NT\$|S/|Rs\.?|RM|Rp|R)\s*\d"
    r"|\d[\d\s,.]*\s*(?:[A-Z]{3}|[$€£¥₺₱₩￦₹₪₦₫฿]|đ|ribu|juta|kr|zł|Kč|Ft|lei)",
    re.IGNORECASE,
)
# 印尼语缩写：349ribu = 349 千，3,499juta = 3.499 百万
_MULTIPLIERS = {"juta": Decimal(1_000_000), "ribu": Decimal(1_000)}


def _clean(text: str) -> str:
    text = text.replace("<!-- HTML_TAG_START -->", "").replace("<!-- HTML_TAG_END -->", "")
    text = html_lib.unescape(_TAG.sub("", text)).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_price_value(text: str) -> Decimal | None:
    """把各地区写法的价格转成数值：₺8.999,99 / ₦ 100,000.00 / 499.000đ / Rp 349ribu …"""
    lowered = text.lower()
    multiplier = next((m for k, m in _MULTIPLIERS.items() if k in lowered), None)
    digits = re.sub(r"\s+", "", re.sub(r"[^\d,.\s]", "", text.replace(" ", " ")))
    if not digits:
        return None
    if multiplier is not None:
        cut = max(digits.rfind(","), digits.rfind("."))
        if cut >= 0:
            number = (
                re.sub(r"[,.]", "", digits[:cut]) + "." + re.sub(r"[,.]", "", digits[cut + 1 :])
            )
        else:
            number = digits
        return _decimal(number, multiplier)

    last_comma, last_dot = digits.rfind(","), digits.rfind(".")
    decimal_sep: str | None = None
    if last_comma >= 0 and last_dot >= 0:
        decimal_sep = "," if last_comma > last_dot else "."
    elif last_comma >= 0:
        decimal_sep = "," if len(digits) - last_comma - 1 <= 2 else None
    elif last_dot >= 0:
        decimal_sep = "." if len(digits) - last_dot - 1 <= 2 else None

    if decimal_sep is None:
        number = re.sub(r"[,.]", "", digits)
    else:
        thousands = "." if decimal_sep == "," else ","
        number = digits.replace(thousands, "").replace(decimal_sep, ".")
    return _decimal(number, Decimal(1))


def _decimal(number: str, multiplier: Decimal) -> Decimal | None:
    try:
        return Decimal(number) * multiplier
    except InvalidOperation:
        return None


def _looks_like_price(text: str) -> bool:
    return parse_price_value(text) is not None and _PRICE_SHAPE.search(text) is not None


def _json_array_after(text: str, key: str, start: int) -> tuple[str, int] | None:
    """从 start 起找 key 后面的 JSON 数组，按括号配对截出来（字符串里的括号不算）。"""
    at = text.find(key, start)
    if at < 0:
        return None
    begin = text.find("[", text.find(":", at + len(key)) + 1)
    if begin < 0:
        return None
    depth, in_str, escaped = 0, False, False
    for i in range(begin, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[begin : i + 1], i + 1
    return None


def _add_on_items(page: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    while (found := _json_array_after(page, '"addOns"', pos)) is not None:
        raw, pos = found
        try:
            add_ons = json.loads(raw)
        except json.JSONDecodeError:
            continue  # 内嵌数据不完整时退回 text-pair
        for a in add_ons if isinstance(add_ons, list) else []:
            if isinstance(a, dict):
                out.append((_clean(str(a.get("name", ""))), _clean(str(a.get("price", "")))))
    return out


def extract_items(page: str) -> list[StoreItem]:
    """页面里的 App 内购买项目，按（名称, 价格）去重，保持出现顺序。"""
    pairs = _add_on_items(page) + [(_clean(t), _clean(p)) for t, p in _PAIR.findall(page)]
    seen: set[tuple[str, str]] = set()
    items: list[StoreItem] = []
    for title, price_text in pairs:
        if not title or (title, price_text) in seen or not _looks_like_price(price_text):
            continue
        value = parse_price_value(price_text)
        if value is None:
            continue
        seen.add((title, price_text))
        items.append(StoreItem(title=title, price_text=price_text, price_value=value))
    return items


def is_expected_page(page: str, app: AppConfig) -> bool:
    """确认拿到的是这个 App 的详情页，而不是被跳转到的首页 / 别的区。"""
    app_id = app.app_store_id
    has_app = any(
        marker in page
        for marker in (
            f'"id":"{app_id}"',
            f'"adamId":"{app_id}"',
            f"appAdamId={app_id}",
            f"/id{app_id}",
        )
    )
    return has_app and "/iphone/today" not in page and '"pageType":"Today"' not in page


# ---------- 匹配 ----------


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[()（）\-_·,，.。/]", " ", text.lower())).strip()


class Match(BaseModel):
    status: Literal["matched", "unmatched", "ambiguous"]
    item: StoreItem | None = None
    candidates: list[StoreItem] = Field(default_factory=list)


def match_plan(items: list[StoreItem], rule: PlanRule, usd_per_unit: Decimal | None) -> Match:
    """usd_per_unit：1 单位当地货币折合多少美元，用于判断价格是否落在档位的美元区间内。"""
    include = [_norm(t) for t in rule.include]
    exclude = [_norm(t) for t in rule.exclude]
    scored: list[tuple[int, bool, Decimal | None, StoreItem]] = []
    for item in items:
        title = _norm(item.title)
        if not all(t in title for t in include) or any(t in title for t in exclude):
            continue
        usd = item.price_value * usd_per_unit if usd_per_unit is not None else None
        band = rule.price_band_usd
        in_band = band is None or usd is None or band[0] <= usd <= band[1]
        score = len(include) * 10 + (4 if in_band else -4) + (3 if title == _norm(rule.name) else 0)
        scored.append((score, in_band, usd, item))
    if not scored:
        return Match(status="unmatched")

    pool = [s for s in scored if s[1]] or scored
    best = max(s[0] for s in pool)
    tied = [s for s in pool if s[0] == best]
    if len(tied) == 1:
        return Match(status="matched", item=tied[0][3])
    priced = sorted((s for s in tied if s[2] is not None), key=lambda s: s[2] or 0)
    if priced and (len(priced) == 1 or priced[0][2] != priced[1][2]):
        return Match(status="matched", item=priced[0][3])
    return Match(status="ambiguous", candidates=[s[3] for s in tied])


# ---------- 抓取 ----------


class RegionPage(BaseModel):
    """一个 App 在一个地区的抓取结果。"""

    status: Literal["ok", "not_found", "failed"]
    url: str
    items: list[StoreItem] = Field(default_factory=list)
    error: str = ""


async def fetch_region(
    client: httpx.AsyncClient, app: AppConfig, region: RegionConfig
) -> RegionPage:
    url = page_url(app, region)
    headers = {
        "X-Apple-Store-Front": f"{region.storefront_id},29",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_error = ""
    for attempt in range(FETCH_ATTEMPTS):
        if attempt:
            await asyncio.sleep(RETRY_BASE_SECONDS * 2 ** (attempt - 1))
        try:
            resp = await client.get(url, headers=headers, timeout=PAGE_TIMEOUT)
        except httpx.HTTPError as exc:
            last_error = f"请求失败：{type(exc).__name__} {exc}".strip()
            continue
        # 没上架：不带区域头时是 404，带区域头时是 200 + itemNotAvailable 的提示（plist）
        if resp.status_code == 404 or _NOT_AVAILABLE in resp.text[:4000]:
            return RegionPage(status="not_found", url=url)
        if resp.status_code in RETRY_STATUSES or resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}"
            continue
        if resp.status_code != 200:
            return RegionPage(status="failed", url=url, error=f"HTTP {resp.status_code}")
        if not is_expected_page(resp.text, app):
            return RegionPage(status="failed", url=url, error="返回的不是该 App 的详情页")
        items = extract_items(resp.text)
        if not items:
            return RegionPage(status="failed", url=url, error="页面里没有解析到 App 内购买项目")
        return RegionPage(status="ok", url=url, items=items)
    return RegionPage(status="failed", url=url, error=last_error or "重试后仍失败")
