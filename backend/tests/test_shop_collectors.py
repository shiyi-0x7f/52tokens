"""卡网采集器：各店铺系统的解析、异常处理（风控页、0 条商品、缺商户地址）。

HTTP 全部用 MockTransport，不访问真实店铺。
"""

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.collectors.base import USER_AGENT, SourceConfig
from app.collectors.registry import get_collector_class
from app.collectors.shops import base as shop_base
from app.collectors.shops.base import ShopItem
from app.collectors.shops.html_pages import lowest_available_spec

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shop_base, "PAGE_DELAY_SECONDS", 0)


async def _collect(kind: str, url: str, handler: Handler) -> tuple[list[ShopItem], list[str]]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await get_collector_class(kind)(http).collect(SourceConfig(id="1", url=url))
    return list(result.items), result.errors


def _routes(routes: dict[str, Any]) -> Handler:
    """按路径返回 JSON（dict / list）或文本（str）；未登记的路径 404。"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == USER_AGENT
        body = routes.get(request.url.path)
        if body is None:
            return httpx.Response(404)
        if isinstance(body, str):
            return httpx.Response(200, text=body)
        return httpx.Response(200, json=body)

    return handler


async def test_kami_paginates_and_maps_stock() -> None:
    page = [
        {
            "id": 1,
            "name": "ChatGPT Plus 月卡",
            "user_price": "99.00",
            "stock": 5,
            "category": {"name": "GPT"},
        },
        {"id": 2, "name": "Claude Pro", "price": 120, "stock": "已售罄"},
        {"id": 3, "name": "测试商品", "price": 1, "stock": 9},
        {"id": 4, "name": "隐藏的", "price": 1, "stock": 9, "hide": 1},
    ]
    items, errors = await _collect(
        "kami", "https://kami.test", _routes({"/user/api/index/commodity": {"data": page}})
    )
    assert errors == []
    assert [(i.title, i.price, i.stock, i.in_stock) for i in items] == [
        ("ChatGPT Plus 月卡", Decimal("99.00"), 5, True),
        ("Claude Pro", Decimal("120.00"), 0, False),
        ("隐藏的", Decimal("1.00"), 9, False),
    ]
    assert items[0].url == "https://kami.test/item/1"
    assert items[0].tags == ["GPT"]


async def test_dujiao_expands_skus() -> None:
    products = [
        {
            "slug": "gpt",
            "title": {"zh-CN": "GPT Plus", "en-US": "GPT Plus EN"},
            "price_amount": "10",
            "fulfillment_type": "auto",
            "skus": [
                {"title": {"zh-CN": "月卡"}, "price_amount": "99", "auto_stock_available": 3},
                {"name": "", "price_amount": "199", "is_sold_out": True},
            ],
        },
        {"slug": "solo", "title": "Gmail 老号", "price_amount": "5.5", "manual_stock_available": 0},
    ]
    items, _ = await _collect(
        "dujiao", "https://dj.test", _routes({"/api/v1/public/products": {"data": products}})
    )
    assert [(i.title, str(i.price), i.in_stock) for i in items] == [
        ("GPT Plus / 月卡", "99.00", True),
        ("GPT Plus / 规格2", "199.00", False),
        ("Gmail 老号", "5.50", False),
    ]
    assert items[0].tags == ["自动发货"]
    assert items[0].url == "https://dj.test/products/gpt"


async def test_shop_api_uses_settled_price() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        body = json.loads(request.content or b"{}")
        if path == "/shopApi/Shop/info":
            assert body["token"] == "abc"
            return httpx.Response(200, json={"code": 1, "data": {"nickname": "店"}})
        if path == "/shopApi/Shop/getUserChannel":
            return httpx.Response(
                200, json={"data": [{"id": 7, "name": "微信"}, {"id": 9, "name": "支付宝"}]}
            )
        if path == "/shopApi/Shop/categoryList":
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": [{"id": 0, "goods_count": 2}, {"id": 5, "goods_count": 1}],
                },
            )
        if path == "/shopApi/Shop/goodsList":
            goods = [
                {
                    "name": "GPT Plus 卡密",
                    "price": "100",
                    "goods_key": "k1",
                    "extend": {"stock_count": 4, "send_order": 0},
                }
            ]
            return httpx.Response(200, json={"code": 1, "data": {"list": goods}})
        if path == "/shopApi/Shop/getGoodsPrice":
            assert body["channel_id"] == 9  # 优先支付宝
            return httpx.Response(200, json={"code": 1, "data": {"total_amount": "103.5"}})
        return httpx.Response(404)

    items, errors = await _collect("shopApi", "https://pay.test/shop/abc", handler)
    assert errors == []
    assert len(items) == 1  # 只查商品数 > 0 的非 0 分类
    assert items[0].price == Decimal("103.50")
    assert items[0].url == "https://pay.test/item/k1"
    assert "自动发货" in items[0].tags


async def test_shop_api_falls_back_to_listed_price_when_quote_fails() -> None:
    """单个商品的结算价接口报错（实测 wzyp.cn 偶发 520）不连累整家店：退回标价。"""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/shopApi/Shop/info":
            return httpx.Response(200, json={"code": 1, "data": {"nickname": "店"}})
        if path == "/shopApi/Shop/categoryList":
            return httpx.Response(200, json={"code": 1, "data": [{"id": 5, "goods_count": 2}]})
        if path == "/shopApi/Shop/goodsList":
            goods = [
                {"name": "GPT Plus 卡密", "price": "100", "goods_key": "k1"},
                {"name": "Claude Pro 卡密", "price": "150", "goods_key": "k2"},
            ]
            return httpx.Response(200, json={"code": 1, "data": {"list": goods}})
        if path == "/shopApi/Shop/getGoodsPrice":
            if json.loads(request.content)["goods_key"] == "k1":
                return httpx.Response(520)
            return httpx.Response(200, json={"code": 1, "data": {"total_amount": "153"}})
        return httpx.Response(200, json={"data": []})

    items, errors = await _collect("shopApi", "https://pay.test/shop/abc", handler)
    assert errors == []
    assert sorted(i.price for i in items) == [Decimal("100.00"), Decimal("153.00")]


async def test_shop_api_requires_merchant_url() -> None:
    items, errors = await _collect("shopApi", "https://pay.test", _routes({}))
    assert items == []
    assert "/shop/<token>" in errors[0]


async def test_shop_goods_api_resolves_alias_to_shop_no() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        if request.url.path == "/shopApi/shop/detail":
            assert body == {"shop_no": "ALIAS"}
            return httpx.Response(200, json={"code": 1, "data": {"shop_no": "S100"}})
        if request.url.path == "/shopApi/goods/list":
            assert body["shop_no"] == "S100"
            goods = [
                {
                    "goods_no": "G1",
                    "name": "Plus 月卡",
                    "price": 125,
                    "stock_available_quantity": 3,
                },
                {"goods_no": "G2", "name": "Gemini 成品号", "price": "15.99"},
                {"goods_no": "G3", "name": "已售罄", "price": 1, "stock_available_quantity": 0},
                {"name": "没有编号", "price": 1},
            ]
            return httpx.Response(200, json={"code": 1, "data": {"list": goods}})
        return httpx.Response(404)

    items, errors = await _collect("shopGoodsApi", "https://www.mall.test/shop/ALIAS", handler)
    assert errors == []
    assert [(i.title, str(i.price), i.stock, i.in_stock) for i in items] == [
        ("Plus 月卡", "125.00", 3, True),
        ("Gemini 成品号", "15.99", None, True),
        ("已售罄", "1.00", 0, False),
    ]
    assert items[0].url == "https://www.mall.test/goods/G1"


async def test_shop_goods_api_missing_shop_is_error() -> None:
    routes = {"/shopApi/shop/detail": {"code": 0, "msg": "店铺不存在", "data": None}}
    items, errors = await _collect("shopGoodsApi", "https://www.mall.test/shop/X", _routes(routes))
    assert items == []
    assert "店铺信息不可用" in errors[0]
    _, errors = await _collect("shopGoodsApi", "https://www.mall.test", _routes({}))
    assert "/shop/<店铺编号>" in errors[0]


async def test_getgpt_fixed_products() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "gpt.how2cs.cn"
        return httpx.Response(200, json={"amount": 120, "claude_amount": "150"})

    items, _ = await _collect("getgptApi", "https://getgpt.test", handler)
    assert [(i.title, str(i.price)) for i in items] == [
        ("ChatGPT Plus 充值", "120.00"),
        ("Claude 充值", "150.00"),
    ]


async def test_mooncake_catalog_js() -> None:
    catalog = [{"name": "GPT", "items": [{"id": 1, "name": "Plus", "price": "88", "stock": 2}]}]
    js = f"window.MOONCAKE_CATALOG = {json.dumps(catalog)};window.x=1"
    items, _ = await _collect(
        "mooncakeCatalog", "https://mc.test", _routes({"/mooncake-official-media/catalog.js": js})
    )
    assert [(i.title, str(i.price), i.tags) for i in items] == [("Plus", "88.00", ["GPT"])]


async def test_unicorn_expands_sku_prices() -> None:
    listing = """
    <div class="card position-relative"><h6 class="card-title">Grok 会员</h6><strong>¥30</strong>
    库存：5 <a href="/buy/12">购买</a> 自动发货</div><div class="col"></div>
    <div class="card position-relative"><h6 class="card-title">售罄商品</h6><strong>9.9</strong>
    库存：0 <a href="/product/13">看看</a></div><!-- goods end -->
    """
    detail = """
    <button onclick="selectSku('月卡', '35.00')"></button>
    <button onclick="selectSku('年卡', '300')"></button>
    """
    items, _ = await _collect(
        "unicornHtml", "https://uni.test/", _routes({"/": listing, "/buy/12": detail})
    )
    assert [(i.title, str(i.price), i.in_stock) for i in items] == [
        ("Grok 会员 / 月卡", "35.00", True),
        ("Grok 会员 / 年卡", "300.00", True),
        ("售罄商品", "9.90", False),
    ]


async def test_blackcat_parses_server_action_payload() -> None:
    products = [
        {
            "id": 1,
            "name": "GPT Team",
            "category": "GPT",
            "wholesale_price": "50",
            "bulk_tiers_wholesale": '[{"unitPrice": 45}]',
            "stock_count": 3,
        },
        {"id": 2, "name": "已归档", "category": "GPT", "price": 1, "is_archived": True},
        {"id": 3, "name": "Claude", "category": "Claude", "price": 80},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["Next-Action"]
        body = '0:{"a":"$@1"}\n1:' + json.dumps({"success": True, "data": products})
        return httpx.Response(200, text=body)

    items, _ = await _collect("blackcatWholesale", "https://bc.test/blackcat?tab=GPT", handler)
    assert [(i.title, str(i.price)) for i in items] == [("GPT Team", "45.00")]
    assert items[0].url == "https://bc.test/blackcat?tab=GPT#product-1"


async def test_generic_html_cards_and_starting_price() -> None:
    listing = """
    <article><h3>Gemini Pro 一年</h3><span class="price">¥199</span>
      <a href="/product/a">详情</a>库存 8</article>
    <a class="shop-item" href="/item/b"><div class="shop-item-name">GPT Plus</div>
      <div class="shop-item-price">¥ 59</div><span>起</span></a>
    <a class="shop-item" href="/item/c"><div class="shop-item-name">Claude 起售</div>
      <div class="shop-item-price">¥ 10</div><span>起</span></a>
    """
    product = {
        "specs": [{"price": "80", "stock_available": 0}, {"price": "65", "stock_available": 2}]
    }
    flight = json.dumps([1, '"product":' + json.dumps(product)])
    detail = f"<script>self.__next_f.push({flight})</script>"
    items, _ = await _collect(
        "genericHtml",
        "https://g.test/",
        _routes({"/": listing, "/item/b": detail}),  # /item/c 详情页 404：起售价确认不了，不发布
    )
    assert [(i.title, str(i.price), i.stock) for i in items] == [
        ("Gemini Pro 一年", "199.00", 8),
        ("GPT Plus", "65.00", 2),
    ]
    assert "最低在售规格" in items[1].tags


def test_lowest_available_spec_falls_back_to_cheapest_when_all_sold_out() -> None:
    page = (
        "<script>self.__next_f.push("
        + json.dumps([1, '"product":{"specs":[{"price":"9","stock_available":0}]}'])
        + ")</script>"
    )
    assert lowest_available_spec(page) == (Decimal("9"), 0)
    assert lowest_available_spec("<html></html>") is None


async def test_challenge_page_and_empty_shop_are_errors() -> None:
    challenge = "<html><body>Just a moment... 安全验证</body></html>"
    _, errors = await _collect(
        "kami", "https://k.test", _routes({"/user/api/index/commodity": challenge})
    )
    assert "风控" in errors[0]

    _, errors = await _collect(
        "kami", "https://k.test", _routes({"/user/api/index/commodity": {"data": []}})
    )
    assert "没有采集到任何商品" in errors[0]

    _, errors = await _collect("dujiao", "https://d.test", _routes({}))
    assert "404" in errors[0]
