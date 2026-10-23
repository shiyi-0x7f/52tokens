"""页面解析类的店铺系统：从公开的商品列表页 HTML 里解析报价。

页面改版就会失效（报「没有采集到商品」）。
"""

import json
import re
from decimal import Decimal
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from loguru import logger

from app.collectors.registry import register
from app.collectors.shops.base import ShopCollector, ShopFetchError, ShopItem, ShopTarget, make_item
from app.collectors.shops.parse import (
    CURRENCY_PRICE_RE,
    PRICE_VALUE,
    STOCK_RE,
    SUFFIX_PRICE_RE,
    absolutize,
    clean_text,
    compact,
    integer,
    number,
    search,
    strip_html,
)

_SOLD_OUT = re.compile(r"缺货|已售罄|售罄|无货")


def _keep(items: list[ShopItem | None]) -> list[ShopItem]:
    return [i for i in items if i is not None]


@register
class OpensoraHtmlCollector(ShopCollector):
    kind: ClassVar[str] = "opensoraHtml"
    CARD: ClassVar[re.Pattern[str]] = re.compile(
        r"<img[^>]+alt=[\"']([^\"']+)[\"'][\s\S]*?<strong>\s*"
        + PRICE_VALUE
        + r"\s*</strong>[\s\S]*?库存[:：]\s*([0-9]+)[\s\S]*?"
        + r"<a[^>]+href=[\"']([^\"']*/buy/[0-9]+[^\"']*)[\"']",
        re.IGNORECASE,
    )

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        page = await self.get_text(target.entry_url)
        out: list[ShopItem | None] = []
        for m in self.CARD.finditer(page):
            heading = search(r'<h6 class="card-title[^"]*">\s*([\s\S]*?)</h6>', m.group(0))
            near = page[max(0, m.start() - 600) : m.end() + 200]
            out.append(
                make_item(
                    title=heading or m.group(1),
                    price=number(m.group(2)),
                    url=absolutize(m.group(4), target.base_url),
                    stock=integer(m.group(3)),
                    tags=compact(
                        [
                            "人工处理" if "人工处理" in near else None,
                            "自动发货" if "自动发货" in near else None,
                        ]
                    ),
                )
            )
        return _keep(out)


@register
class MakerichHtmlCollector(ShopCollector):
    kind: ClassVar[str] = "makerichHtml"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        page = await self.get_text(target.entry_url)
        out: list[ShopItem | None] = []
        for m in re.finditer(
            r"<a[^>]+href=[\"']([^\"']*(?:/item\?id=[0-9]+|/item/[^\"']+))[\"'][\s\S]*?</a>",
            page,
            re.I,
        ):
            body = strip_html(m.group(0))
            price = CURRENCY_PRICE_RE.search(body)
            if not price:
                continue
            title = re.sub(
                r"销量[:：]\s*[0-9]+", "", STOCK_RE.sub("", CURRENCY_PRICE_RE.sub("", body))
            )
            out.append(
                make_item(
                    title=title,
                    price=number(price.group(1)),
                    url=absolutize(m.group(1), target.base_url),
                    stock=integer(search(STOCK_RE, body)),
                )
            )
        return _keep(out)


@register
class BeibeiHtmlCollector(ShopCollector):
    kind: ClassVar[str] = "beibeiHtml"

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        page = await self.get_text(target.entry_url)
        out: list[ShopItem | None] = []
        for m in re.finditer(r'<article class="atelier-catalog-card[\s\S]*?</article>', page, re.I):
            body = m.group(0)
            sold_out = bool(re.search(r"sold-out|售罄|已售罄|action-disabled", body, re.I))
            href = search(r"href=[\"']([^\"']*/checkout/[^\"']+)[\"']", body) or search(
                r"href=[\"']([^\"']*/products/[^\"']+)[\"']", body
            )
            out.append(
                make_item(
                    title=search(r"<h3>([\s\S]*?)</h3>", body),
                    price=number(search(CURRENCY_PRICE_RE, body)),
                    url=absolutize(href or target.entry_url, target.base_url),
                    stock=0 if sold_out else integer(search(r"库存\s*([0-9]+)", body)),
                    disabled=sold_out,
                    tags=compact(
                        re.findall(r'<span class="atelier-pill[^"]*">([\s\S]*?)</span>', body, re.I)
                    ),
                )
            )
        return _keep(out)


@register
class UnicornHtmlCollector(ShopCollector):
    """列表页只有起售价，逐个进 /buy/<id> 详情页取各规格的价格。"""

    kind: ClassVar[str] = "unicornHtml"
    SKU: ClassVar[re.Pattern[str]] = re.compile(
        r"onclick=[\"']selectSku\(([\"'])((?:\\.|(?!\1).)*?)\1\s*,\s*([\"'])([0-9.,]+)\3",
        re.IGNORECASE,
    )

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        page = await self.get_text(target.entry_url)
        cards: dict[str, dict[str, Any]] = {}
        for m in re.finditer(
            r'<div class="card position-relative">[\s\S]*?'
            r'(?=<div class="col">|<!-- goods end -->|</section>|</body>)',
            page,
            re.I,
        ):
            body = m.group(0)
            stock = integer(search(STOCK_RE, body))
            sold_out = (
                bool(re.search(r"缺货|售罄|已售罄|disabled|btn-secondary", body, re.I))
                or stock == 0
            )
            href = search(
                r"<a[^>]+href=[\"']([^\"']*(?:/buy/[0-9]+|/product/[0-9]+)[^\"']*)[\"']", body
            )
            url = absolutize(href or target.entry_url, target.base_url)
            cards[url] = {
                "title": search(
                    r"<h6[^>]*class=[\"'][^\"']*card-title[^\"']*[\"'][^>]*>([\s\S]*?)</h6>", body
                ),
                "price": number(search(r"<strong>\s*([^<]+?)\s*</strong>", body)),
                "stock": 0 if sold_out else stock,
                "disabled": sold_out,
                "tags": compact(
                    [
                        "自动发货" if "自动发货" in body else None,
                        "人工处理" if "人工处理" in body else None,
                    ]
                ),
            }
        out: list[ShopItem | None] = []
        for url, card in cards.items():
            skus = await self._skus(url)
            if not skus:
                out.append(make_item(url=url, **card))
                continue
            for name, price in skus:
                out.append(
                    make_item(
                        title=f"{clean_text(card['title'])} / {name}",
                        price=price,
                        url=url,
                        stock=card["stock"],
                        disabled=card["disabled"],
                        tags=[*card["tags"], "规格价"],
                    )
                )
        return _keep(out)

    async def _skus(self, url: str) -> list[tuple[str, Any]]:
        if not re.search(r"/buy/[0-9]+", url):
            return []
        await self.pause()
        try:
            page = await self.get_text(url)
        except Exception as exc:  # 单个详情页失败不影响列表页报价（退回起售价）
            logger.info("规格详情页抓取失败，退回列表价 url={} {}", url, type(exc).__name__)
            return []
        out = []
        for m in self.SKU.finditer(page):
            name = clean_text(re.sub(r"\\(['\"\\])", r"\1", m.group(2)))
            price = number(m.group(4))
            if name and price is not None:
                out.append((name, price))
        return out


@register
class BlackcatWholesaleCollector(ShopCollector):
    """Next.js 站点：商品数据由一个 Server Action 返回（POST 页面 + next-action 头）。"""

    kind: ClassVar[str] = "blackcatWholesale"
    DEFAULT_ACTION: ClassVar[str] = "00fc36c4f4551a0ad0887d0946a6c93bc94960dfaf"
    MAX_ITEMS: ClassVar[int] = 200

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        products = await self._products(target)
        tab = self._tab(target.entry_url)
        out: list[ShopItem | None] = []
        for p in products:
            if (
                p.get("is_archived") is True
                or p.get("active") is False
                or p.get("is_active") is False
            ):
                continue
            if p.get("is_wholesale_active") is False:
                continue
            category = clean_text(p.get("category"))
            if tab and category.lower() != tab.lower():
                continue
            raw_stock = integer(p.get("stock_count", p.get("stockCount", p.get("stock"))))
            out.append(
                make_item(
                    title=p.get("wholesale_name") or p.get("name") or p.get("title"),
                    price=self._price(p),
                    url=self._url(target, p, category),
                    stock=raw_stock if raw_stock is not None and raw_stock >= 0 else None,
                    disabled=raw_stock == 0,
                    tags=compact(
                        [
                            category,
                            p.get("badge"),
                            "自动发货" if p.get("delivery_type") == "static" else None,
                            p.get("delivery_category"),
                        ]
                    ),
                )
            )
        return _keep(out)[: self.MAX_ITEMS]

    async def _products(self, target: ShopTarget) -> list[dict[str, Any]]:
        resp = await self._action(target, self.DEFAULT_ACTION)
        if resp.status_code == 404:
            action = await self._discover_action(target)
            if action and action != self.DEFAULT_ACTION:
                resp = await self._action(target, action)
        resp.raise_for_status()
        payload = self._action_data(resp.text)
        if payload.get("success") is False:
            raise ShopFetchError(
                clean_text(payload.get("error") or payload.get("message")) or "商品接口失败"
            )
        data = payload.get("data")
        if not isinstance(data, list):
            raise ShopFetchError("商品接口没有返回商品列表")
        return [p for p in data if isinstance(p, dict)]

    async def _action(self, target: ShopTarget, action_id: str) -> Any:
        return await self.client.post(
            target.entry_url,
            content="[]",
            headers={
                **self.headers,
                "Accept": "text/x-component",
                "Content-Type": "text/plain;charset=UTF-8",
                "Next-Action": action_id,
                "Origin": target.base_url,
                "Referer": target.entry_url,
            },
        )

    async def _discover_action(self, target: ShopTarget) -> str | None:
        """Action id 随站点重新构建而变：从页面引用的 JS 包里找。"""
        page = await self.get_text(target.entry_url)
        scripts = re.findall(r"<script[^>]+src=[\"']([^\"']+\.js)[\"']", page, re.I)[:24]
        for src in scripts:
            await self.pause()
            try:
                chunk = await self.get_text(absolutize(src, target.base_url))
            except Exception as exc:  # 个别 JS 取不到不影响继续找
                logger.info("JS 包抓取失败 src={} {}", src, type(exc).__name__)
                continue
            i = chunk.find("fetchWholesaleProductsAction")
            if i >= 0 and (
                m := re.search(
                    r"[\"']([a-f0-9]{40,64})[\"']", chunk[max(0, i - 500) : i + 100], re.I
                )
            ):
                return m.group(1)
        return None

    @staticmethod
    def _action_data(text: str) -> dict[str, Any]:
        for line in text.splitlines():
            _, sep, raw = line.partition(":")
            raw = raw.strip()
            if not sep or not raw.startswith("{"):
                continue
            try:
                payload = json.loads(raw)
            except ValueError:
                continue
            if isinstance(payload, dict) and ("data" in payload or "success" in payload):
                return payload
        raise ShopFetchError("商品接口响应里没有数据")

    @staticmethod
    def _tab(url: str) -> str:
        tab = clean_text(parse_qs(urlsplit(url).query).get("tab", [""])[0])
        return "" if tab.lower() == "all" else tab

    @staticmethod
    def _price(p: dict[str, Any]) -> Any:
        tiers = p.get("bulk_tiers_wholesale")
        if isinstance(tiers, str):
            try:
                tiers = json.loads(tiers)
            except ValueError:
                tiers = None
        prices = [
            number(t.get("unitPrice", t.get("unit_price", t.get("price"))))
            for t in (tiers if isinstance(tiers, list) else [])
            if isinstance(t, dict)
        ]
        valid = [x for x in prices if x is not None]
        return min(valid) if valid else number(p.get("wholesale_price", p.get("price")))

    @staticmethod
    def _url(target: ShopTarget, p: dict[str, Any], category: str) -> str:
        parts = urlsplit(target.entry_url)
        query = parse_qs(parts.query)
        if category and "tab" not in query:
            query["tab"] = [category]
        fragment = f"product-{p['id']}" if p.get("id") else parts.fragment
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), fragment)
        )


@register
class GenericHtmlCollector(ShopCollector):
    kind: ClassVar[str] = "genericHtml"
    MAX_ITEMS: ClassVar[int] = 200

    async def fetch(self, target: ShopTarget) -> list[ShopItem]:
        page = await self.get_text(target.entry_url)
        cards = generic_cards(target, page)
        if cards:
            return _keep([await self._resolve_starting_price(c) for c in cards])[: self.MAX_ITEMS]
        return single_product_page(target, page)

    async def _resolve_starting_price(self, item: ShopItem) -> ShopItem | None:
        """标「起」的卡片价是起售价：进详情页取最低的在售规格；确认不了就不发布。"""
        if "起售价" not in item.tags:
            return item
        await self.pause()
        try:
            spec = lowest_available_spec(await self.get_text(item.url))
        except Exception as exc:  # 详情页失败：起售价没法确认，宁可不发布
            logger.info("起售价详情页抓取失败，不发布 url={} {}", item.url, type(exc).__name__)
            return None
        if spec is None:
            return None
        price, stock = spec
        price = price.quantize(Decimal("0.01"))
        return item.model_copy(
            update={
                "price": price,
                "stock": stock,
                "in_stock": stock > 0,
                "tags": [*item.tags, "最低在售规格"],
            }
        )


# ---------- 通用 HTML 解析 ----------

_PRICE_CLASSES = [
    "df-product-price",
    "shop-item-price",
    "product-price",
    "price",
    "amount",
    "money",
]
_TITLE_CLASSES = ["df-product-name", "shop-item-name", "product-title", "product-name", "title"]
_DETAIL_PATH = re.compile(r"/(?:product|products|checkout|buy|item|goods|post)/[^/?#]+", re.I)
_DETAIL_PATH_ID = re.compile(r"/(?:product|products|checkout|buy|item|goods|post)/?$", re.I)


def generic_cards(target: ShopTarget, page: str) -> list[ShopItem]:
    out: list[ShopItem | None] = []
    for card in _extract_cards(page):
        price = _card_price(card)
        title = _card_title(card)
        url = next(
            (
                absolutize(h, target.base_url)
                for h in re.findall(r"href=[\"']([^\"']+)[\"']", card, re.I)
                if _is_detail_href(h)
            ),
            None,
        )
        if price is None or not title or not url:
            continue
        context = strip_html(card)
        stock = integer(
            search(r"库存\s*[:：]?\s*([0-9]+)", context) or search(r"([0-9]+)\s*件现货", context)
        )
        sold_out = bool(_SOLD_OUT.search(context)) or stock == 0
        tags = _card_tags(card)
        out.append(
            make_item(
                title=title,
                price=price,
                url=url,
                stock=0 if sold_out else stock,
                disabled=sold_out,
                tags=list(
                    dict.fromkeys(
                        [
                            *tags,
                            *compact(
                                [
                                    "自动发货" if "自动发货" in context else None,
                                    "人工处理" if "人工" in context else None,
                                ]
                            ),
                        ]
                    )
                ),
            )
        )
    return _keep(out)


def _extract_cards(page: str) -> list[str]:
    cards: list[str] = []
    seen: set[str] = set()

    def add(card: str) -> None:
        if card not in seen:
            seen.add(card)
            cards.append(card)

    for m in re.finditer(r"<article\b[\s\S]*?</article>", page, re.I):
        add(m.group(0))
    for m in re.finditer(
        r"<a\b(?=[^>]*class=[\"'][^\"']*(?:df-product-card|shop-item)[^\"']*[\"'])[\s\S]*?</a>",
        page,
        re.I,
    ):
        add(m.group(0))
    for card in _balanced_elements(page, "div", ["group/card"]):
        add(card)
    for m in re.finditer(r"<a\b([^>]*)>[\s\S]*?</a>", page, re.I):
        href = search(r"\bhref=[\"']([^\"']+)[\"']", m.group(1)) or ""
        if _is_detail_href(href) and _card_price(m.group(0)) is not None:
            add(m.group(0))
    return cards


def _balanced_elements(page: str, tag: str, class_fragments: list[str]) -> list[str]:
    out: list[str] = []
    start, depth = -1, 0
    for m in re.finditer(rf"</?{tag}\b[^>]*>", page, re.I):
        closing = m.group(0).startswith("</")
        if start < 0:
            if closing:
                continue
            classes = search(r"\bclass=[\"']([^\"']+)[\"']", m.group(0)) or ""
            if any(f in classes for f in class_fragments):
                start, depth = m.start(), 1
            continue
        depth += -1 if closing else 1
        if depth == 0:
            out.append(page[start : m.end()])
            start = -1
    return out


def _is_detail_href(href: str) -> bool:
    href = clean_text(href)
    if not href or re.match(r"^(?:javascript:|#)", href, re.I):
        return False
    parts = urlsplit(href)
    if _DETAIL_PATH.search(parts.path):
        return True
    query = parse_qs(parts.query)
    if _DETAIL_PATH_ID.search(parts.path) and query.get("id"):
        return True
    host = (parts.hostname or "").removeprefix("www.")
    if (
        host == "woaimaihao.com"
        and re.match(r"^/[a-z0-9]+(?:-[a-z0-9]+)*/?$", parts.path, re.I)
        and not re.match(
            r"^/(?:login|products?|orders?|blog|tutorials?|redeem|accounts?|cart|checkout|chatgpt|claude|gemini|grok)/?$",
            parts.path,
            re.I,
        )
    ):
        return True
    return any(
        query.get(k)
        for k in ("post", "product", "product_id", "goods", "goods_id", "item", "item_id")
    )


def _class_text(card: str, classes: list[str]) -> str:
    pattern = "|".join(re.escape(c) for c in classes)
    return clean_text(
        search(rf"<[^>]+class=[\"'][^\"']*(?:{pattern})[^\"']*[\"'][^>]*>([\s\S]*?)</[^>]+>", card)
    )


def _card_price(card: str) -> Any:
    for text in (_class_text(card, _PRICE_CLASSES), strip_html(card)):
        for pattern in (CURRENCY_PRICE_RE, SUFFIX_PRICE_RE):
            if m := pattern.search(text):
                return number(m.group(1))
    return None


def _title_key(value: str) -> str:
    text = re.sub(r"[（(]\s*购买\s*[）)]", "", clean_text(value))
    text = re.sub(r"立即购买|查看详情|购买", "", text)
    return re.sub(r"[\s|｜·,，。.!！?？:：;；_-]+", "", text).lower()


def _card_title(card: str) -> str:
    highlight = clean_text(
        search(
            r"<p[^>]+class=[\"'][^\"']*(?:highlight|subtitle|summary|description)[^\"']*[\"'][^>]*>([\s\S]*?)</p>",
            card,
        )
    )
    paragraphs = [
        clean_text(body)
        for attrs, body in re.findall(r"<p([^>]*)>([\s\S]*?)</p>", card, re.I)
        if not re.search(
            r"class=[\"'][^\"']*(?:highlight|subtitle|summary|price|stock|badge)[^\"']*[\"']",
            attrs,
            re.I,
        )
    ]
    description = next((p for p in paragraphs if p and p != highlight), "")
    primary = (
        _class_text(card, _TITLE_CLASSES)
        or clean_text(search(r"\btitle=[\"']([^\"']+)[\"']", card))
        or clean_text(search(r"<h[1-4][^>]*>([\s\S]*?)</h[1-4]>", card))
        or clean_text(search(r"<img[^>]+alt=[\"']([^\"']+)[\"']", card))
        or _card_title_from_text(card)
    )
    parts: list[str] = []
    for part in compact([primary, highlight, description]):
        key = _title_key(part)
        if key and not any((k := _title_key(p)) == key or key in k or k in key for p in parts):
            parts.append(part)
    return " ".join(parts)[:180]


def _card_title_from_text(card: str) -> str:
    text = strip_html(card)
    positions = [m.start() for p in (CURRENCY_PRICE_RE, SUFFIX_PRICE_RE) if (m := p.search(text))]
    if m := re.search(r"\bPRICE\s+[0-9]", text, re.I):
        positions.append(m.start())
    head = clean_text(text[: min(positions) if positions else len(text)])
    head = re.split(r"\s+(?:库存|销量|已售)\s*[:：]?", head)[0]
    head = re.sub(r"^(?:缺货|已售罄|售罄|自动发货|人工发货|手工发货)\s*", "", head)
    head = re.sub(r"\s*(?:自动发货|人工发货|手工发货)\s*$", "", head)
    head = re.sub(r"[（(]\s*购买\s*[）)]\s*$", "", head)
    return re.sub(r"\s*(?:立即购买|查看详情|购买)\s*$", "", head).strip()[:180]


def _card_tags(card: str) -> list[str]:
    block = (
        search(
            r"<div[^>]+class=[\"'][^\"']*(?:tags|category|badge)[^\"']*[\"'][^>]*>([\s\S]*?)</div>",
            card,
        )
        or ""
    )
    tags = compact(re.findall(r"<span[^>]*>([\s\S]*?)</span>", block, re.I))[:4]
    if re.search(r">(?:\s|<!--.*?-->)*起(?:\s|<!--.*?-->)*<", card, re.I | re.S):
        tags.append("起售价")
    return tags


def lowest_available_spec(page: str) -> tuple[Any, int] | None:
    """Next.js 商品详情页：从 Flight 数据里取 product.specs，返回最低在售规格的（价格, 库存）。"""
    product = _next_flight_value(page, "product")
    specs = product.get("specs") if isinstance(product, dict) else None
    if not isinstance(specs, list) or not specs:
        return None
    rows = [
        (number(s.get("price")), integer(s.get("stock_available")))
        for s in specs
        if isinstance(s, dict)
    ]
    available = sorted((p, n) for p, n in rows if p is not None and n is not None and n > 0)
    if available:
        return available[0]
    prices = [p for p, _ in rows if p is not None]
    return (min(prices), 0) if prices else None


def _next_flight_value(page: str, key: str) -> Any:
    chunks = []
    for body in re.findall(r"<script[^>]*>([\s\S]*?)</script>", page, re.I):
        m = re.match(r"^\s*self\.__next_f\.push\(([\s\S]*)\)\s*$", body)
        if not m:
            continue
        try:
            chunk = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(chunk, list) and len(chunk) > 1 and isinstance(chunk[1], str):
            chunks.append(chunk[1])
    payload = "\n".join(chunks)
    marker = f'"{key}":'
    offset = 0
    while (i := payload.find(marker, offset)) >= 0:
        start = re.search(r"[\[{]", payload[i + len(marker) :])
        if not start:
            return None
        value = _balanced_json(payload, i + len(marker) + start.start())
        if value:
            try:
                return json.loads(value)
            except ValueError:
                pass
        offset = i + len(marker)
    return None


def _balanced_json(text: str, start: int) -> str | None:
    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth, quoted, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
        elif ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def single_product_page(target: ShopTarget, page: str) -> list[ShopItem]:
    """不是列表页时：只在明确是单商品页（URL 像详情页且价格不超过 2 个）时取一条。"""
    text = re.sub(r"\s+", " ", strip_html(page)).strip()
    prices = list(re.finditer(rf"[¥￥]\s*{PRICE_VALUE}", text))
    path = urlsplit(target.entry_url).path
    if (
        not (len(prices) <= 2 and re.search(r"/(?:product|products|goods|item)/", path, re.I))
        or not prices
    ):
        return []
    page_title = clean_text(search(r"<title[^>]*>([\s\S]*?)</title>", page))
    page_title = re.split(r"\s*(?:购买\s*\||\|\s*购买|-\s*购买|_\s*购买)\s*", page_title)[0]
    page_title = re.sub(
        r"\s*[|-]\s*(?:office\s*365|发卡|小店|商城|商店).*$", "", page_title, flags=re.I
    ).strip()
    first = prices[0]
    context = text[: first.end() + 260]
    stock = integer(search(r"库存\s*[:：]?\s*([0-9]+)", context))
    if not page_title or re.search(r"合计|支付|订单|充值金额|余额|声明|举证|预览", page_title):
        return []
    sold_out = bool(_SOLD_OUT.search(context)) or stock == 0
    item = make_item(
        title=page_title[:140],
        price=number(first.group(1)),
        url=target.entry_url.split("#")[0],
        stock=0 if sold_out else stock,
        disabled=sold_out,
        tags=compact(
            [
                "自动发货" if "自动发货" in context else None,
                "人工处理" if "人工" in context else None,
            ]
        ),
    )
    if item is None:
        raise ShopFetchError("单商品页解析不到有效报价")
    return [item]
