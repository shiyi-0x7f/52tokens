"""卡网页面 / 接口数据的清洗工具。正则统一用 [0-9]，不用 \\d（避免全角数字被当成价格）。"""

import html
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin

PRICE_VALUE = r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
CURRENCY_PRICE_RE = re.compile(rf"[¥￥]\s*{PRICE_VALUE}")
SUFFIX_PRICE_RE = re.compile(rf"{PRICE_VALUE}\s*(?:CNY|RMB|元)", re.IGNORECASE)
STOCK_RE = re.compile(r"库存\s*[:：]?\s*([0-9]+)")

_TAG = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)[\s\S]*?</\1>", re.IGNORECASE)
_SPACE = re.compile(r"\s+")
# 店铺里的打赏、测试、公告等不是可比价的商品
_NON_COMPARABLE = ["Logo", "打赏", "测试", "公告", "请查看上方店铺", "其他（直接联系客服"]


def clean_text(value: object) -> str:
    text = _TAG.sub(" ", str(value or ""))
    return _SPACE.sub(" ", html.unescape(text)).strip()


def strip_html(value: str) -> str:
    return clean_text(_SCRIPT_STYLE.sub(" ", value))


def localized(value: Any) -> str:
    """多语言字段（{"zh-CN": ..., "en-US": ...}）取中文优先。"""
    if not value:
        return ""
    if isinstance(value, dict):
        for key in ("zh-CN", "zh-TW", "en-US"):
            if value.get(key):
                return clean_text(value[key])
        return clean_text(next((v for v in value.values() if v), ""))
    return clean_text(value)


def number(value: object) -> Decimal | None:
    """宽松解析数字：去掉货币符号、千分位等非数字字符；解析不了返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    text = re.sub(r"[^0-9.\-]", "", str(value))
    if text in {"", "-", ".", "-."}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def integer(value: object) -> int | None:
    n = number(value)
    return None if n is None else int(n)


def is_non_comparable(title: str) -> bool:
    return any(k in title for k in _NON_COMPARABLE)


def absolutize(href: str | None, base_url: str) -> str:
    if not href:
        return base_url
    return urljoin(base_url + "/", html.unescape(href))


def compact(values: list[Any]) -> list[str]:
    return [t for t in (clean_text(v) for v in values if v) if t]


def search(pattern: str | re.Pattern[str], text: str, group: int = 1) -> str | None:
    m = (
        re.search(pattern, text, re.IGNORECASE)
        if isinstance(pattern, str)
        else pattern.search(text)
    )
    return m.group(group) if m else None
