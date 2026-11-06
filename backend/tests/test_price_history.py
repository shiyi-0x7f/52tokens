"""价格历史快照：只记对外展示的价格，同一天覆盖，跨天新增；卡网最低价与比价页规则一致。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.catalog.models import PublishStatus
from app.domains.history.models import ModelPriceDaily, ShopProductDaily
from app.domains.history.repository import HistoryRepository
from app.domains.history.service import PriceHistoryService, beijing_day
from app.domains.shops.models import ShopCollectorKind, ShopOffer, ShopProduct, ShopSource
from app.domains.shops.repository import ShopRepository
from tests import factories as f

NOW = datetime.now(UTC)


def _service(session: AsyncSession) -> PriceHistoryService:
    return PriceHistoryService(HistoryRepository(session), ShopRepository(session))


async def _model_rows(session: AsyncSession) -> list[ModelPriceDaily]:
    return list(
        (await session.scalars(select(ModelPriceDaily).order_by(ModelPriceDaily.day))).all()
    )


async def _shop_rows(session: AsyncSession) -> list[ShopProductDaily]:
    return list((await session.scalars(select(ShopProductDaily))).all())


async def _shop_product(session: AsyncSession, slug: str) -> ShopProduct:
    p = ShopProduct(slug=slug, name=slug, platform="ChatGPT", product_type="订阅/会员")
    session.add(p)
    await session.flush()
    return p


async def _shop_offer(
    session: AsyncSession, host: str, product: ShopProduct, price: str, **kw: Any
) -> None:
    src = ShopSource(
        host=host,
        entry_url=f"https://{host}",
        base_url=f"https://{host}",
        collector_kind=ShopCollectorKind.KAMI,
    )
    session.add(src)
    await session.flush()
    session.add(
        ShopOffer(
            source_id=src.id,
            product_id=product.id,
            external_id=f"{host}-{price}",
            title=kw.pop("title", f"{product.slug} {price}"),
            url=f"https://{host}/item/1",
            price=Decimal(price),
            last_seen_at=kw.pop("last_seen_at", NOW),
            **kw,
        )
    )
    await session.flush()


def test_beijing_day_crosses_midnight() -> None:
    # UTC 16:30 已是北京时间次日 00:30
    assert str(beijing_day(datetime(2026, 11, 5, 16, 30, tzinfo=UTC))) == "2026-11-06"
    assert str(beijing_day(datetime(2026, 11, 5, 15, 59, tzinfo=UTC))) == "2026-11-05"


async def test_records_only_public_model_prices(db_session: AsyncSession) -> None:
    plat = await f.platform(db_session, "ds")
    hidden_plat = await f.platform(db_session, "gone", status=PublishStatus.HIDDEN)
    m = await f.model(db_session, "deepseek-v3")
    draft_model = await f.model(db_session, "draft-model", status=PublishStatus.DRAFT)
    await f.price(db_session, plat, m, input_price=Decimal("2"), output_price=Decimal("8"))
    await f.price(db_session, hidden_plat, m)  # 平台下线
    await f.price(db_session, plat, draft_model)  # 模型未发布
    other = await f.model(db_session, "qwen-max")
    await f.price(db_session, plat, other, confirmed_at=None)  # 未核实

    report = await _service(db_session).snapshot(NOW)

    rows = await _model_rows(db_session)
    assert report.model_prices == 1
    assert [(r.model_id, r.input_price, r.output_price) for r in rows] == [
        (m.id, Decimal("2.0000"), Decimal("8.0000"))
    ]
    assert rows[0].day == beijing_day(NOW)
    assert rows[0].currency == "CNY"


async def test_same_day_overwrites_next_day_appends(db_session: AsyncSession) -> None:
    plat = await f.platform(db_session, "ds")
    m = await f.model(db_session, "deepseek-v3")
    price = await f.price(db_session, plat, m, input_price=Decimal("2"))
    service = _service(db_session)

    await service.snapshot(NOW)
    price.input_price = Decimal("1.5")
    await db_session.flush()
    await service.snapshot(NOW)  # 同一天：覆盖
    rows = await _model_rows(db_session)
    assert [r.input_price for r in rows] == [Decimal("1.5000")]

    await service.snapshot(NOW + timedelta(days=1))  # 次日：新增一行
    rows = await _model_rows(db_session)
    assert [r.input_price for r in rows] == [Decimal("1.5000"), Decimal("1.5000")]
    assert rows[1].day - rows[0].day == timedelta(days=1)


async def test_shop_min_price_follows_comparison_rules(db_session: AsyncSession) -> None:
    plus = await _shop_product(db_session, "chatgpt-plus")
    await _shop_offer(db_session, "a.shop", plus, "120")
    await _shop_offer(db_session, "b.shop", plus, "99")
    await _shop_offer(db_session, "c.shop", plus, "20", title="ChatGPT Plus 拼车")  # 拼车不计
    await _shop_offer(db_session, "d.shop", plus, "80", in_stock=False)  # 无货不计
    await _shop_offer(  # 超过 48 小时没采集到，不计
        db_session, "e.shop", plus, "70", last_seen_at=NOW - timedelta(hours=72)
    )
    empty = await _shop_product(db_session, "claude-pro")
    await _shop_offer(db_session, "f.shop", empty, "150", in_stock=False)

    report = await _service(db_session).snapshot(NOW)

    rows = {r.product_id: r for r in await _shop_rows(db_session)}
    assert report.shop_products == 2
    assert rows[plus.id].min_price == Decimal("99.00")
    assert rows[plus.id].in_stock_shops == 2
    assert rows[plus.id].offer_count == 5
    assert rows[empty.id].min_price is None
    assert rows[empty.id].in_stock_shops == 0
