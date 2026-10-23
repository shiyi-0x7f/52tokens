"""官网原文定位：文本片段链接的生成与原文核对。"""

import pytest

from app.domains.deals.links import locate_url, quote_in_text

URL = "https://help.aliyun.com/zh/model-studio/new-free-quota"


def test_short_quote_is_encoded_whole() -> None:
    assert locate_url(URL, " 免费额度  有效期 90 天 ") == (
        f"{URL}#:~:text=%E5%85%8D%E8%B4%B9%E9%A2%9D%E5%BA%A6%20%E6%9C%89%E6%95%88%E6%9C%9F%2090%20%E5%A4%A9"
    )


def test_special_characters_are_escaped() -> None:
    out = locate_url(URL, "Pro-plan, 50% off & more")
    directive = out.split("#:~:text=", 1)[1]
    assert "-" not in directive
    assert "," not in directive
    assert "&" not in directive
    assert "%2D" in directive


def test_long_quote_uses_start_and_end() -> None:
    quote = "当您首次开通阿里云百炼时，平台会自动为您发放各模型的新人专属免费额度，有效期为 90 天"
    directive = locate_url(URL, quote).split("#:~:text=", 1)[1]
    start, end = directive.split(",")
    assert start and end


@pytest.mark.parametrize(
    ("url", "quote"),
    [(URL, ""), (URL, "   "), (f"{URL}#section", "免费额度")],
)
def test_returns_url_unchanged(url: str, quote: str) -> None:
    assert locate_url(url, quote) == url


def test_quote_in_text_ignores_whitespace() -> None:
    page = "规则说明\n免费额度的有效期为  90 天，\n从开通之日起计算。"
    assert quote_in_text("免费额度的有效期为 90 天，从开通之日起计算。", page) is True
    assert quote_in_text("免费额度的有效期为90天", page) is True
    assert quote_in_text("免费额度的有效期为 180 天", page) is False
    assert quote_in_text("", page) is False
