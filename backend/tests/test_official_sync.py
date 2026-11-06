"""订阅地区价同步：写入规则、档位随配置增删、汇率失败整批放弃。

HTTP 全部用 MockTransport，不访问真实的 App Store 和汇率接口。
"""

from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors import app_store
from app.collectors.app_store import AppConfig, AppStoreConfig, PlanRule, RegionConfig
from app.domains.official import sync as sync_module
from app.domains.official.models import OfficialPlan, OfficialRegionPrice
from app.domains.official.repository import OfficialRepository
from app.domains.official.sync import OfficialSyncService
from app.integrations.fx import FxError

APP_ID = "6448311069"
FX = {"date": "2026-11-05", "rates": {"CNY": 7.0, "TRY": 40.0, "JPY": 150.0}}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_module, "REQUEST_GAP_SECONDS", 0)
    monkeypatch.setattr(app_store, "RETRY_BASE_SECONDS", 0)


def _config(*plans: PlanRule) -> AppStoreConfig:
    rules = plans or (
        PlanRule(
            slug="plus-monthly",
            name="ChatGPT Plus",
            billing_period="monthly",
            include=["ChatGPT Plus"],
            price_band_usd=(Decimal(8), Decimal(35)),
        ),
        PlanRule(
            slug="go-monthly",
            name="ChatGPT Go",
            billing_period="monthly",
            include=["ChatGPT Go"],
            price_band_usd=(Decimal(4), Decimal(15)),
        ),
    )
    return AppStoreConfig(
        apps=[
            AppConfig(
                slug="chatgpt",
                name="ChatGPT",
                provider="OpenAI",
                app_store_id=APP_ID,
                app_store_slug="chatgpt",
                plans=list(rules),
            )
        ],
        regions=[
            RegionConfig(
                code="US", label="美国", storefront="us", storefront_id="143441", currency="USD"
            ),
            RegionConfig(
                code="TR", label="土耳其", storefront="tr", storefront_id="143480", currency="TRY"
            ),
            RegionConfig(
                code="JP", label="日本", storefront="jp", storefront_id="143462", currency="JPY"
            ),
        ],
    )


def _page(*pairs: tuple[str, str]) -> str:
    body = "".join(
        f'<div class="text-pair"><span>{t}</span><span>{p}</span></div>' for t, p in pairs
    )
    return f'<html><a href="/app/chatgpt/id{APP_ID}"></a>{body}</html>'


def _handler(
    pages: dict[str, httpx.Response | str], fx_ok: bool = True
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.frankfurter.dev":
            return httpx.Response(200, json=FX) if fx_ok else httpx.Response(503)
        if request.url.host == "open.er-api.com":
            return httpx.Response(503)
        storefront = request.url.path.split("/")[1]
        page = pages.get(storefront, httpx.Response(404))
        return page if isinstance(page, httpx.Response) else httpx.Response(200, text=page)

    return handler


async def _run(
    session: AsyncSession,
    handler: Callable[[httpx.Request], httpx.Response],
    config: AppStoreConfig | None = None,
) -> sync_module.SyncReport:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        return await OfficialSyncService(
            OfficialRepository(session), http, config or _config()
        ).sync_all()


async def _prices(session: AsyncSession) -> dict[tuple[str, str], OfficialRegionPrice]:
    session.expire_all()
    rows = (
        await session.execute(
            select(OfficialPlan.plan_slug, OfficialRegionPrice).join(OfficialRegionPrice.plan)
        )
    ).all()
    return {(slug, p.country_code): p for slug, p in rows}


async def test_writes_available_missing_and_skips_failures(db_session: AsyncSession) -> None:
    report = await _run(
        db_session,
        _handler(
            {
                "us": _page(
                    ("ChatGPT Plus", "$19.99"), ("ChatGPT Plus", "$200.00"), ("ChatGPT Go", "$8.00")
                ),
                "tr": httpx.Response(500),  # 抓取失败：不写
                # jp 没登记 → 404：未上架
            }
        ),
    )
    prices = await _prices(db_session)

    us_plus = prices[("plus-monthly", "US")]
    assert us_plus.status == "available"
    assert us_plus.price_value == Decimal("19.99")
    assert us_plus.cny_price == Decimal("139.93")  # 19.99 × 7
    assert us_plus.fx_date is not None and str(us_plus.fx_date) == "2026-11-05"
    assert prices[("go-monthly", "US")].price_text == "$8.00"
    assert prices[("plus-monthly", "JP")].status == "missing"
    assert ("plus-monthly", "TR") not in prices
    assert (report.pages_ok, report.pages_not_found, report.pages_failed) == (1, 1, 1)
    assert any("TR" in i for i in report.issues)


NOT_AVAILABLE_PLIST = (
    '<?xml version="1.0"?><plist><dict><key>dialogId</key>'
    "<string>itemNotAvailable</string></dict></plist>"
)


async def test_item_not_available_dialog_means_missing(db_session: AsyncSession) -> None:
    report = await _run(db_session, _handler({"us": NOT_AVAILABLE_PLIST}))
    prices = await _prices(db_session)
    assert prices[("plus-monthly", "US")].status == "missing"
    assert report.pages_not_found == 3  # 美区是提示框，日本和土耳其是 404
    assert report.pages_failed == 0


async def test_failure_and_unmatched_keep_previous_price(db_session: AsyncSession) -> None:
    await _run(
        db_session,
        _handler(
            {
                "us": _page(("ChatGPT Plus", "$19.99"), ("ChatGPT Go", "$8.00")),
                "tr": _page(("ChatGPT Plus", "₺999,99")),
            }
        ),
    )
    # 第二次：美区页面改版没有 Go 了、土耳其区抓取失败
    report = await _run(
        db_session,
        _handler(
            {
                "us": _page(("ChatGPT Plus", "$21.99")),
                "tr": httpx.Response(503),
            }
        ),
    )
    prices = await _prices(db_session)
    assert prices[("plus-monthly", "US")].price_value == Decimal("21.99")
    assert prices[("go-monthly", "US")].price_text == "$8.00"  # 没匹配到 → 保留
    assert prices[("plus-monthly", "TR")].price_value == Decimal("999.99")  # 失败 → 不动
    assert prices[("go-monthly", "TR")].status == "missing"  # 原来就没有价格
    assert report.kept == 1


async def test_plans_follow_config(db_session: AsyncSession) -> None:
    await _run(db_session, _handler({"us": _page(("ChatGPT Plus", "$19.99"))}))
    only_go = _config(
        PlanRule(
            slug="go-monthly",
            name="ChatGPT Go (新)",
            billing_period="monthly",
            include=["ChatGPT Go"],
        )
    )
    report = await _run(db_session, _handler({"us": _page(("ChatGPT Go", "$8.00"))}), only_go)
    plans = (await db_session.scalars(select(OfficialPlan))).all()
    assert [(p.plan_slug, p.plan_name) for p in plans] == [("go-monthly", "ChatGPT Go (新)")]
    assert report.plans_removed == 1
    assert {k[0] for k in await _prices(db_session)} == {"go-monthly"}


async def test_fx_failure_aborts_without_writing(db_session: AsyncSession) -> None:
    with pytest.raises(FxError):
        await _run(db_session, _handler({"us": _page(("ChatGPT Plus", "$19.99"))}, fx_ok=False))
    assert (await db_session.scalars(select(OfficialPlan))).all() == []
