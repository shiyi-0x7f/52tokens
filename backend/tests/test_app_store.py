"""App Store 订阅价：页面解析、价格写法、档位匹配、仓库内配置合法。"""

from decimal import Decimal

import pytest

from app.collectors.app_store import (
    PlanRule,
    StoreItem,
    extract_items,
    is_expected_page,
    load_config,
    match_plan,
    parse_price_value,
)

PAIRS_HTML = """
  <div class="text-pair svelte-1gyt6l2"><span>ChatGPT Plus</span> <span>₺499,99</span></div>
  <div class="text-pair"><span>ChatGPT Plus</span> <span>₺8.999,99</span></div>
  <div class="text-pair"><span>100 Credits</span> <span>$4.00</span></div>
  <div class="text-pair"><span>Claude Pro - Monthly</span> <span>EGP 699.99</span> </div>
  <div class="text-pair"><span>Claude Max 5x - Monthly</span> <span>₦ 100,000.00</span> </div>
  <div class="text-pair"><span>Claude Pro - Monthly</span> <span>Rs 4,900.00</span> </div>
  <div class="text-pair"><span>Claude Pro - Monthly</span> <span>499.000đ</span> </div>
  <div class="text-pair"><span>Claude Pro - Monthly</span> <span>S/ 69.90</span> </div>
  <div class="text-pair"><span>ChatGPT Plus</span> <span>￦29,000</span> </div>
  <div class="text-pair"><span>ChatGPT Plus</span> <span>฿699.00</span> </div>
  <div class="text-pair"><span>ChatGPT Plus</span> <span>RM99.90</span> </div>
  <div class="text-pair"><span>ChatGPT Plus</span> <span>Rp 349ribu</span> </div>
  <div class="text-pair"><span>ChatGPT Pro 20x</span> <span>Rp 3,499juta</span> </div>
  <div class="text-pair"><span>Developer</span> <span>OpenAI OpCo, LLC</span></div>
  <div class="text-pair svelte-1gyt6l2"><span>ChatGPT Plus</span> <span>₺499,99</span></div>
"""


def test_extracts_text_pairs_skips_non_prices_and_duplicates() -> None:
    items = extract_items(PAIRS_HTML)
    assert [(i.title, i.price_text) for i in items] == [
        ("ChatGPT Plus", "₺499,99"),
        ("ChatGPT Plus", "₺8.999,99"),
        ("100 Credits", "$4.00"),
        ("Claude Pro - Monthly", "EGP 699.99"),
        ("Claude Max 5x - Monthly", "₦ 100,000.00"),
        ("Claude Pro - Monthly", "Rs 4,900.00"),
        ("Claude Pro - Monthly", "499.000đ"),
        ("Claude Pro - Monthly", "S/ 69.90"),
        ("ChatGPT Plus", "￦29,000"),
        ("ChatGPT Plus", "฿699.00"),
        ("ChatGPT Plus", "RM99.90"),
        ("ChatGPT Plus", "Rp 349ribu"),
        ("ChatGPT Pro 20x", "Rp 3,499juta"),
    ]


def test_extracts_embedded_add_ons_json() -> None:
    page = (
        '<script>{"addOns":[{"name":"SuperGrok","price":"$30.00","buyParams":"x=[1]"},'
        '{"name":"SuperGrok Heavy","price":"$300.00"}]}</script>'
        '<div class="text-pair"><span>SuperGrok</span><span>$30.00</span></div>'
    )
    assert [(i.title, i.price_value) for i in extract_items(page)] == [
        ("SuperGrok", Decimal("30.00")),
        ("SuperGrok Heavy", Decimal("300.00")),
    ]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("₺8.999,99", "8999.99"),
        ("₦ 100,000.00", "100000.00"),
        ("499.000đ", "499000"),
        ("￦29,000", "29000"),
        ("฿699.00", "699.00"),
        ("RM99.90", "99.90"),
        ("Rp 349ribu", "349000"),
        ("Rp 3,499juta", "3499000"),
        ("7,99 €", "7.99"),
        ("USD 5.99", "5.99"),
        ("1.799,00 kr", "1799.00"),
        ("99,99 zł", "99.99"),
        ("499,00 Kč", "499.00"),
        ("R 349,99", "349.99"),
        ("7 990 Ft", "7990"),
    ],
)
def test_parse_price_value(text: str, value: str) -> None:
    assert parse_price_value(text) == Decimal(value)


def test_nordic_and_central_european_prices_are_recognized() -> None:
    # 北欧 / 中欧区的页面只有内嵌 JSON，价格带 kr / zł 后缀
    page = (
        '{"addOns":[{"price":"249,00\\u00a0kr","name":"ChatGPT Plus"},'
        '{"price":"99,99 zł","name":"ChatGPT Go"}]}'
    )
    assert [(i.title, i.price_value) for i in extract_items(page)] == [
        ("ChatGPT Plus", Decimal("249.00")),
        ("ChatGPT Go", Decimal("99.99")),
    ]


def _item(title: str, price: str) -> StoreItem:
    return StoreItem(title=title, price_text=price, price_value=Decimal(price))


PLUS = PlanRule(
    slug="plus-monthly",
    name="ChatGPT Plus",
    billing_period="monthly",
    include=["ChatGPT Plus"],
    exclude=["Annual", "Pro"],
    price_band_usd=(Decimal(8), Decimal(35)),
)


def test_price_band_picks_monthly_over_same_named_annual() -> None:
    items = [
        _item("ChatGPT Plus", "200.00"),
        _item("ChatGPT Plus", "19.99"),
        _item("ChatGPT Pro 200", "200"),
    ]
    result = match_plan(items, PLUS, Decimal(1))
    assert result.status == "matched"
    assert result.item is not None and result.item.price_value == Decimal("19.99")


def test_band_uses_fx_for_local_currency() -> None:
    # 1 里拉 ≈ 0.025 美元：₺999.99 ≈ $25 在区间内，₺9999.99 ≈ $250 不在
    items = [_item("ChatGPT Plus", "9999.99"), _item("ChatGPT Plus", "999.99")]
    result = match_plan(items, PLUS, Decimal("0.025"))
    assert result.item is not None and result.item.price_value == Decimal("999.99")


def test_unmatched_and_ambiguous() -> None:
    assert match_plan([_item("100 Credits", "4")], PLUS, Decimal(1)).status == "unmatched"
    # 名称都不等于档位名、价格也相同：无法区分
    same = [_item("ChatGPT Plus (Intro)", "19.99"), _item("ChatGPT Plus Trial", "19.99")]
    loose = PLUS.model_copy(update={"price_band_usd": None})
    result = match_plan(same, loose, Decimal(1))
    assert result.status == "ambiguous"
    assert len(result.candidates) == 2


def test_expected_page_check() -> None:
    from app.collectors.app_store import AppConfig

    app = AppConfig(
        slug="chatgpt",
        name="ChatGPT",
        provider="OpenAI",
        app_store_id="123",
        app_store_slug="chatgpt",
        plans=[],
    )
    assert is_expected_page('<a href="/us/app/chatgpt/id123">', app)
    assert not is_expected_page('<a href="/us/iphone/today">', app)


def test_repository_config_is_valid() -> None:
    config = load_config()
    codes = [r.code for r in config.regions]
    assert len(codes) == len(set(codes))
    assert "NO" in codes and "US" in codes  # 挪威没被 YAML 解析成 false
    for app in config.apps:
        slugs = [p.slug for p in app.plans]
        assert len(slugs) == len(set(slugs)), app.slug
        for p in app.plans:
            assert p.price_band_usd is None or p.price_band_usd[0] < p.price_band_usd[1]
