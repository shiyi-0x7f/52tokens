"""把 data/seed/*.yaml 幂等导入数据库（按 slug / URL upsert，重复执行结果不变）。

用法：uv run python -m app.cli.seed [种子目录]

种子数据是人工核实后的「数据即代码」：改动走 git 审查。价格和活动必须带
confirmed_at（核实时间），没有核实时间的条目导入后保持草稿 / 待审核，不会对外展示。
"""

import asyncio
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import REPO_ROOT, get_settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.domains.catalog.models import (
    AIModel,
    Currency,
    ModelPrice,
    Platform,
    PlatformCategory,
    PublishStatus,
)
from app.domains.deals.models import Deal, DealCycle, DealSource, DealStatus, DealType
from app.domains.shops.models import ShopCollectorKind, ShopProduct, ShopSource

DEFAULT_SEED_DIR = REPO_ROOT / "data" / "seed"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlatformSeed(_Strict):
    slug: str
    name: str
    category: PlatformCategory
    website_url: str
    description: str = ""
    status: PublishStatus = PublishStatus.DRAFT


class ModelSeed(_Strict):
    slug: str
    name: str
    family: str
    context_window: int | None = None
    description: str = ""
    status: PublishStatus = PublishStatus.DRAFT


class PriceSeed(_Strict):
    platform: str
    model: str
    currency: Currency = Currency.CNY
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    cache_read_price: Decimal | None = None
    is_free: bool = False
    free_note: str = ""
    source_url: str
    confirmed_at: datetime | None = None
    status: PublishStatus = PublishStatus.DRAFT


class DealSeed(_Strict):
    slug: str
    platform: str
    title: str
    deal_type: DealType
    reward_text: str
    est_value_cny: Decimal | None = None
    requirements: list[str] = []
    cycle: DealCycle = DealCycle.ONCE
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    description: str = ""
    steps: list[str] = []
    source_url: str
    source_quote: str = ""
    aff_url: str | None = None
    in_app_only: bool = False
    confirmed_at: datetime | None = None
    status: DealStatus = DealStatus.PENDING


class SourceSeed(_Strict):
    platform: str
    url: str
    label: str = ""
    enabled: bool = True


class ShopProductSeed(_Strict):
    slug: str
    name: str
    platform: str
    product_type: str
    spec: str = ""
    summary: str = ""
    aliases: list[str] = []
    sort_order: int = 0
    status: PublishStatus = PublishStatus.ACTIVE


class ShopSourceSeed(_Strict):
    host: str
    base_url: str
    collector_kind: ShopCollectorKind
    name: str = ""
    enabled: bool = True


def _load(seed_dir: Path, name: str) -> list[dict[str, Any]]:
    path = seed_dir / f"{name}.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"{path} 顶层必须是列表")
    return data


async def _upsert(
    session: AsyncSession, model: Any, rows: list[dict[str, Any]], key: list[str]
) -> None:
    if not rows:
        return
    stmt = insert(model).values(rows)
    update_cols: dict[str, Any] = {c: stmt.excluded[c] for c in rows[0] if c not in key}
    update_cols["updated_at"] = func.now()
    await session.execute(stmt.on_conflict_do_update(index_elements=key, set_=update_cols))


async def _id_map(session: AsyncSession, model: Any) -> dict[str, int]:
    return {slug: id_ for slug, id_ in (await session.execute(select(model.slug, model.id))).all()}


async def seed(session: AsyncSession, seed_dir: Path = DEFAULT_SEED_DIR) -> dict[str, int]:
    platforms = [PlatformSeed.model_validate(r) for r in _load(seed_dir, "platforms")]
    models = [ModelSeed.model_validate(r) for r in _load(seed_dir, "models")]
    prices = [PriceSeed.model_validate(r) for r in _load(seed_dir, "prices")]
    deals = [DealSeed.model_validate(r) for r in _load(seed_dir, "deals")]
    sources = [SourceSeed.model_validate(r) for r in _load(seed_dir, "deal_sources")]
    shop_products = [ShopProductSeed.model_validate(r) for r in _load(seed_dir, "shop_products")]
    shop_sources = [ShopSourceSeed.model_validate(r) for r in _load(seed_dir, "shop_sources")]

    await _upsert(session, Platform, [p.model_dump() for p in platforms], ["slug"])
    await _upsert(session, AIModel, [m.model_dump() for m in models], ["slug"])
    platform_ids = await _id_map(session, Platform)
    model_ids = await _id_map(session, AIModel)

    def ref(ids: dict[str, int], slug: str, kind: str) -> int:
        if slug not in ids:
            raise ValueError(f"引用了不存在的{kind}：{slug}")
        return ids[slug]

    price_rows = []
    for p in prices:
        row = p.model_dump(exclude={"platform", "model"})
        row["platform_id"] = ref(platform_ids, p.platform, "平台")
        row["model_id"] = ref(model_ids, p.model, "模型")
        price_rows.append(row)
    await _upsert(session, ModelPrice, price_rows, ["platform_id", "model_id"])

    deal_rows = []
    for d in deals:
        row = d.model_dump(exclude={"platform"})
        row["platform_id"] = ref(platform_ids, d.platform, "平台")
        deal_rows.append(row)
    await _upsert(session, Deal, deal_rows, ["slug"])

    # 监测来源按 URL upsert；检查状态（正文 hash、上次检查、错误）不在种子里，不会被覆盖
    source_rows = []
    for s in sources:
        row = s.model_dump(exclude={"platform"})
        row["platform_id"] = ref(platform_ids, s.platform, "平台")
        source_rows.append(row)
    await _upsert(session, DealSource, source_rows, ["url"])

    # 卡网：商品按 slug、店铺按域名 upsert；店铺的采集状态不在种子里，不会被覆盖
    await _upsert(session, ShopProduct, [p.model_dump() for p in shop_products], ["slug"])
    await _upsert(session, ShopSource, [s.model_dump() for s in shop_sources], ["host"])

    await session.commit()
    return {
        "platforms": len(platforms),
        "models": len(models),
        "prices": len(prices),
        "deals": len(deals),
        "deal_sources": len(sources),
        "shop_products": len(shop_products),
        "shop_sources": len(shop_sources),
    }


async def _main(seed_dir: Path) -> None:
    async with get_sessionmaker()() as session:
        counts = await seed(session, seed_dir)
    logger.info("种子数据导入完成 {}", counts)


if __name__ == "__main__":
    setup_logging(get_settings())
    asyncio.run(_main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED_DIR))
