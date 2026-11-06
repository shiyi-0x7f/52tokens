"""种子导入：幂等、可更新、引用校验、仓库内种子文件本身合法。"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.seed import DEFAULT_SEED_DIR, seed
from app.domains.catalog.models import ModelPrice, Platform, PublishStatus
from app.domains.deals.models import Deal, DealSource
from app.domains.shops.models import ShopProduct

PLATFORMS = """
- slug: bailian
  name: 阿里云百炼
  category: llm_api_cn
  website_url: https://www.aliyun.com/product/bailian
  status: active
"""

MODELS = """
- slug: qwen3-30b-a3b
  name: Qwen3-30B-A3B
  family: qwen
  status: active
"""

PRICES = """
- platform: bailian
  model: qwen3-30b-a3b
  input_price: "0.7"
  output_price: "2.8"
  source_url: https://help.aliyun.com/pricing
  confirmed_at: 2026-10-22T10:00:00+08:00
  status: active
"""

DEALS = """
- slug: bailian-newcomer
  platform: bailian
  title: 新人每个模型送 100 万 tokens
  deal_type: signup_credit
  reward_text: 100 万 tokens / 模型
  source_url: https://www.aliyun.com/product/bailian
"""


def _write(tmp: Path, **files: str) -> Path:
    for name, content in files.items():
        (tmp / f"{name}.yaml").write_text(content, encoding="utf-8")
    return tmp


async def _count(session: AsyncSession, model: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def test_seed_is_idempotent_and_updates(tmp_path: Path, db_session: AsyncSession) -> None:
    seed_dir = _write(tmp_path, platforms=PLATFORMS, models=MODELS, prices=PRICES, deals=DEALS)
    first = await seed(db_session, seed_dir)
    assert first == {
        "platforms": 1,
        "models": 1,
        "prices": 1,
        "deals": 1,
        "deal_sources": 0,
        "shop_products": 0,
        "shop_sources": 0,
    }

    await seed(db_session, seed_dir)
    assert await _count(db_session, Platform) == 1
    assert await _count(db_session, ModelPrice) == 1

    _write(tmp_path, platforms=PLATFORMS.replace("阿里云百炼", "百炼"))
    await seed(db_session, seed_dir)
    db_session.expire_all()
    plat = await db_session.scalar(select(Platform).where(Platform.slug == "bailian"))
    assert plat is not None
    assert plat.name == "百炼"


async def test_deal_without_status_stays_pending(tmp_path: Path, db_session: AsyncSession) -> None:
    await seed(db_session, _write(tmp_path, platforms=PLATFORMS, deals=DEALS))
    deal = await db_session.scalar(select(Deal))
    assert deal is not None
    assert deal.status == "pending"
    assert deal.confirmed_at is None


SOURCES = """
- platform: bailian
  url: https://help.aliyun.com/zh/model-studio/new-free-quota
  label: 新人免费额度文档
"""


async def test_sources_upsert_by_url_keeps_check_state(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    seed_dir = _write(tmp_path, platforms=PLATFORMS, deal_sources=SOURCES)
    await seed(db_session, seed_dir)
    source = await db_session.scalar(select(DealSource))
    assert source is not None
    assert source.enabled is True
    source.content_hash = "abc"
    await db_session.commit()

    _write(tmp_path, deal_sources=SOURCES.replace("新人免费额度文档", "免费额度"))
    await seed(db_session, seed_dir)
    db_session.expire_all()
    assert await _count(db_session, DealSource) == 1
    source = await db_session.scalar(select(DealSource))
    assert source is not None
    assert source.label == "免费额度"
    assert source.content_hash == "abc"


async def test_unknown_reference_is_rejected(tmp_path: Path, db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="不存在的模型"):
        await seed(db_session, _write(tmp_path, platforms=PLATFORMS, prices=PRICES))


async def test_repository_seed_files_are_valid(db_session: AsyncSession) -> None:
    counts = await seed(db_session, DEFAULT_SEED_DIR)
    assert counts["platforms"] > 0
    assert counts["shop_products"] > 0
    assert counts["shop_sources"] > 0
    # 重复导入幂等
    again = await seed(db_session, DEFAULT_SEED_DIR)
    assert again == counts
    # 帮人绕过实名验证的商品照样参与归类，但不对外展示
    kyc = await db_session.scalar(
        select(ShopProduct).where(ShopProduct.slug == "identity-verification")
    )
    assert kyc is not None
    assert kyc.status == PublishStatus.HIDDEN
    # 仓库种子里的平台只放核实过的名称和官网，要么发布，要么明确下线（如已停服），不留草稿
    drafts = await db_session.scalar(
        select(func.count()).select_from(Platform).where(Platform.status == PublishStatus.DRAFT)
    )
    assert drafts == 0
