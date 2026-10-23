"""卡网标题归类：fixtures/shop_titles.json 逐条回归，外加文本工具的边界行为。"""

import json
from pathlib import Path

import pytest
import yaml

from app.core.config import REPO_ROOT
from app.domains.shops.classify import OTHER, classify_title
from app.domains.shops.classify.text import normalize_title, rx

CASES = json.loads((Path(__file__).parent / "fixtures" / "shop_titles.json").read_text("utf-8"))


@pytest.mark.parametrize(("title", "expected"), [(c["title"], c["expected"]) for c in CASES])
def test_title_is_classified(title: str, expected: str) -> None:
    assert classify_title(title) == expected


def test_every_result_is_a_seeded_product() -> None:
    seed = yaml.safe_load((REPO_ROOT / "data" / "seed" / "shop_products.yaml").read_text("utf-8"))
    slugs = {p["slug"] for p in seed}
    assert OTHER in slugs
    assert {c["expected"] for c in CASES} <= slugs


def test_word_boundary_is_ascii_like_js() -> None:
    # 中文不算单词字符：「买puls会员」里的 puls 两侧是边界
    assert normalize_title("买puls会员") == "买plus会员"
    assert rx(r"\bgo\b").search("chatgpt go月卡") is not None
    assert rx(r"\bgo\b").search("gopay") is None
    # 全角数字不算 \d
    assert rx(r"\d").search("１２") is None


def test_normalize_title() -> None:
    assert normalize_title("【ChatGPT】Plus｜月卡（质保）") == "chatgpt plus 月卡 质保"
    assert normalize_title("SuperGrok × 2") == "super grok x 2"


def test_context_helps_only_when_title_is_vague() -> None:
    assert classify_title("Plus") == OTHER
    assert classify_title("Plus", context="ChatGPT") == "chatgpt-plus"
