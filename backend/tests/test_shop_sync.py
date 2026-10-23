"""卡网入库：归类、人工归类不被覆盖、没出现的标无货、采集失败不动报价。"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CollectResult
from app.collectors.shops.base import ShopItem, make_item
from app.domains.shops.models import ShopCollectorKind, ShopOffer, ShopProduct, ShopSource
from app.domains.shops.repository import ShopRepository
from app.domains.shops.sync import ShopSyncService


def _item(title: str, price: str = "99", url: str = "https://k.test/item/1") -> ShopItem:
    item = make_item(title=title, price=Decimal(price), url=url, stock=3)
    assert item is not None
    return item


def _result(*items: ShopItem, errors: list[str] | None = None) -> CollectResult[ShopItem]:
    return CollectResult[ShopItem](source_id="1", items=list(items), errors=errors or [])


async def _setup(session: AsyncSession) -> ShopSource:
    for slug in ("chatgpt-plus", "claude-pro-month", "other-product"):
        session.add(ShopProduct(slug=slug, name=slug, platform="x", product_type="x"))
    source = ShopSource(
        host="k.test",
        entry_url="https://k.test",
        base_url="https://k.test",
        collector_kind=ShopCollectorKind.KAMI,
    )
    session.add(source)
    await session.commit()
    # 带数据库默认值的列提交后未加载，异步会话里直接读会报错；生产环境的店铺都是查出来的
    await session.refresh(source)
    return source


async def _offers(session: AsyncSession) -> dict[str, ShopOffer]:
    rows = (await session.scalars(select(ShopOffer).order_by(ShopOffer.id))).all()
    return {o.title: o for o in rows}


async def _product_id(session: AsyncSession, slug: str) -> int:
    pid = await session.scalar(select(ShopProduct.id).where(ShopProduct.slug == slug))
    assert pid is not None
    return pid


def _service(session: AsyncSession) -> ShopSyncService:
    # apply 只入库不发请求，给一个不会被用到的客户端
    return ShopSyncService(ShopRepository(session), httpx.AsyncClient())


async def test_offers_are_classified_and_upserted(db_session: AsyncSession) -> None:
    source = await _setup(db_session)
    service = _service(db_session)
    now = datetime.now(UTC)

    report = await service.apply(
        source,
        _result(_item("ChatGPT Plus 成品号 独享账号"), _item("Claude Pro 月卡", url="u2")),
        now,
    )
    assert (report.status, report.offers, report.created) == ("synced", 2, 2)
    offers = await _offers(db_session)
    assert offers["ChatGPT Plus 成品号 独享账号"].product_id == await _product_id(
        db_session, "chatgpt-plus"
    )
    assert offers["Claude Pro 月卡"].product_id == await _product_id(db_session, "claude-pro-month")
    assert source.offer_count == 2
    assert source.success_at == now

    # 再同步一次：同一条更新价格，不新增
    report = await service.apply(
        source,
        _result(
            _item("ChatGPT Plus 成品号 独享账号", price="88"), _item("Claude Pro 月卡", url="u2")
        ),
        now,
    )
    assert report.created == 0
    db_session.expire_all()
    offers = await _offers(db_session)
    assert offers["ChatGPT Plus 成品号 独享账号"].price == Decimal("88.00")


async def test_manual_match_is_kept(db_session: AsyncSession) -> None:
    source = await _setup(db_session)
    service = _service(db_session)
    await service.apply(source, _result(_item("ChatGPT Plus 成品号 独享账号")), datetime.now(UTC))
    offer = (await _offers(db_session))["ChatGPT Plus 成品号 独享账号"]
    offer.product_id = await _product_id(db_session, "claude-pro-month")
    offer.match_method = "manual"
    await db_session.commit()

    await service.apply(source, _result(_item("ChatGPT Plus 成品号 独享账号")), datetime.now(UTC))
    db_session.expire_all()
    offer = (await _offers(db_session))["ChatGPT Plus 成品号 独享账号"]
    assert offer.product_id == await _product_id(db_session, "claude-pro-month")


async def test_missing_offers_go_out_of_stock_but_failure_keeps_them(
    db_session: AsyncSession,
) -> None:
    source = await _setup(db_session)
    service = _service(db_session)
    await service.apply(
        source, _result(_item("A 商品"), _item("B 商品", url="u2")), datetime.now(UTC)
    )

    # 采集失败：报价不动，只记在店铺上
    report = await service.apply(source, _result(errors=["HTTPStatusError 522"]), datetime.now(UTC))
    assert report.status == "failed"
    assert source.fail_count == 1
    assert source.last_error == "HTTPStatusError 522"
    assert all(o.in_stock for o in (await _offers(db_session)).values())

    # 采集成功但 B 没出现：B 标无货（不删除），失败计数清零
    report = await service.apply(source, _result(_item("A 商品")), datetime.now(UTC))
    assert report.gone == 1
    assert source.fail_count == 0
    assert source.last_error == ""
    db_session.expire_all()
    offers = await _offers(db_session)
    assert offers["A 商品"].in_stock is True
    assert offers["B 商品"].in_stock is False
