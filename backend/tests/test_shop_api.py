"""卡网比价对外接口：可见性、有货最低价只算新鲜有货报价、排序、外层不出现商家名。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.catalog.models import PublishStatus
from app.domains.shops.models import ShopCollectorKind, ShopOffer, ShopProduct, ShopSource
from tests.conftest import AUTH

NOW = datetime.now(UTC)


async def _product(session: AsyncSession, slug: str, **kw: Any) -> ShopProduct:
    p = ShopProduct(
        slug=slug, name=kw.pop("name", slug), platform="ChatGPT", product_type="订阅/会员", **kw
    )
    session.add(p)
    await session.flush()
    return p


async def _source(session: AsyncSession, host: str, **kw: Any) -> ShopSource:
    s = ShopSource(
        host=host,
        entry_url=f"https://{host}",
        base_url=f"https://{host}",
        collector_kind=ShopCollectorKind.KAMI,
        **kw,
    )
    session.add(s)
    await session.flush()
    return s


async def _offer(
    session: AsyncSession, src: ShopSource, product: ShopProduct, price: str, **kw: Any
) -> None:
    session.add(
        ShopOffer(
            source_id=src.id,
            product_id=product.id,
            external_id=kw.pop("external_id", f"{src.host}-{price}"),
            title=kw.pop("title", f"{product.slug} {price}"),
            url=f"https://{src.host}/item/1",
            price=Decimal(price),
            last_seen_at=kw.pop("last_seen_at", NOW),
            **kw,
        )
    )
    await session.flush()


async def test_list_and_lowest_in_stock_price(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    plus = await _product(db_session, "chatgpt-plus", sort_order=10)
    claude = await _product(db_session, "claude-pro-month", sort_order=20)
    empty = await _product(db_session, "chatgpt-go")  # 没有报价：不出现在列表
    other = await _product(db_session, "other-product")
    kyc = await _product(db_session, "identity-verification", status=PublishStatus.HIDDEN)
    a = await _source(db_session, "a.test")
    b = await _source(db_session, "b.test")
    off = await _source(db_session, "off.test", enabled=False)

    await _offer(db_session, a, plus, "99")
    await _offer(db_session, b, plus, "80", in_stock=False)  # 无货不算
    await _offer(db_session, b, plus, "60", last_seen_at=NOW - timedelta(days=3))  # 不新鲜不算
    await _offer(db_session, b, plus, "120")
    await _offer(db_session, off, plus, "1")  # 停用店铺不展示
    await _offer(db_session, a, plus, "2", hidden=True)  # 隐藏报价不展示
    await _offer(db_session, a, claude, "150")
    for p in (other, kyc):
        await _offer(db_session, a, p, "5", external_id=p.slug)
    assert empty.id
    await db_session.commit()

    data = (await db_client.get("/internal/v1/shop-products", headers=AUTH)).json()["data"]
    assert [p["slug"] for p in data] == ["chatgpt-plus", "claude-pro-month"]
    plus_row = data[0]
    assert plus_row["min_price"] == "99.00"
    assert plus_row["in_stock_shops"] == 2
    assert plus_row["offer_count"] == 4
    assert "a.test" not in str(plus_row)  # 外层不出现商家


async def test_sensitive_words_are_replaced_in_public_text(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    plus = await _product(
        db_session, "chatgpt-plus", spec="已/未接码", summary="购买前核对接码状态"
    )
    a = await _source(db_session, "a.test")
    await _offer(db_session, a, plus, "60", title="GPT Plus 成品号 未接码 质保首登")
    await db_session.commit()

    item = (await db_client.get("/internal/v1/shop-products", headers=AUTH)).json()["data"][0]
    assert item["spec"] == "已/未手机验证"
    detail = (await db_client.get("/internal/v1/shop-products/chatgpt-plus", headers=AUTH)).json()[
        "data"
    ]
    assert detail["summary"] == "购买前核对手机验证状态"
    assert detail["offers"][0]["title"] == "GPT Plus 成品号 未手机验证 质保首登"
    assert "接码" not in str(detail)


async def test_detail_orders_offers(db_session: AsyncSession, db_client: httpx.AsyncClient) -> None:
    plus = await _product(db_session, "chatgpt-plus", summary="说明")
    a = await _source(db_session, "a.test")
    await _offer(db_session, a, plus, "60", last_seen_at=NOW - timedelta(days=3))
    await _offer(db_session, a, plus, "50", in_stock=False)
    await _offer(db_session, a, plus, "99")
    await _offer(db_session, a, plus, "88")
    await db_session.commit()

    data = (await db_client.get("/internal/v1/shop-products/chatgpt-plus", headers=AUTH)).json()[
        "data"
    ]
    assert data["summary"] == "说明"
    assert data["min_price"] == "88.00"
    assert [(o["price"], o["in_stock"], o["is_fresh"]) for o in data["offers"]] == [
        ("88.00", True, True),
        ("99.00", True, True),
        ("50.00", False, True),
        ("60.00", True, False),
    ]
    # 店铺只给代号，同一店铺代号相同；页面数据里不出现域名
    assert data["offers"][0]["shop"].startswith("店铺 ")
    assert len({o["shop"] for o in data["offers"]}) == 1
    # 测试工厂的 external_id 拼了域名（真实数据是哈希），所以只检查展示字段
    assert all("a.test" not in o["shop"] + o["title"] for o in data["offers"])


async def test_urls_and_domains_are_removed_from_public_text(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    plus = await _product(db_session, "chatgpt-plus")
    a = await _source(db_session, "a.test")
    await _offer(
        db_session,
        a,
        plus,
        "60",
        title="GPT Plus 官网faka.example.shop 下单（https://x.example.com/buy）质保",
        tags=["www.example.top 专区"],
    )
    await db_session.commit()

    offer = (await db_client.get("/internal/v1/shop-products/chatgpt-plus", headers=AUTH)).json()[
        "data"
    ]["offers"][0]
    assert offer["title"] == "GPT Plus 官网 下单 质保"
    assert offer["tags"] == ["专区"]


async def test_shared_access_and_outlier_prices_do_not_set_lowest(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    plus = await _product(db_session, "chatgpt-plus")
    a = await _source(db_session, "a.test")
    b = await _source(db_session, "b.test")
    await _offer(db_session, a, plus, "50", title="ChatGPT Plus-拼车（三人车）")
    await _offer(db_session, a, plus, "1", title="Plus 自助充值")  # 占位价
    await _offer(db_session, b, plus, "100", title="Plus 独享 A")
    await _offer(db_session, b, plus, "110", title="Plus 独享 B", external_id="b2")
    await _offer(db_session, a, plus, "120", title="Plus 独享 C", external_id="a3")
    await db_session.commit()

    data = (await db_client.get("/internal/v1/shop-products/chatgpt-plus", headers=AUTH)).json()[
        "data"
    ]
    assert data["min_price"] == "100.00"
    assert data["in_stock_shops"] == 2
    assert [(o["title"], o["flags"]) for o in data["offers"]] == [
        ("Plus 独享 A", []),
        ("Plus 独享 B", []),
        ("Plus 独享 C", []),
        ("Plus 自助充值", ["价格待核实"]),
        ("ChatGPT Plus-拼车（三人车）", ["拼车"]),
    ]


async def test_detail_not_found_for_hidden_other_or_unknown(
    db_session: AsyncSession, db_client: httpx.AsyncClient
) -> None:
    await _product(db_session, "other-product")
    await _product(db_session, "identity-verification", status=PublishStatus.HIDDEN)
    await db_session.commit()
    for slug in ("other-product", "identity-verification", "missing"):
        resp = await db_client.get(f"/internal/v1/shop-products/{slug}", headers=AUTH)
        assert resp.status_code == 404
