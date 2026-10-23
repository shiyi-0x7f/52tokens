"""官方订阅地区价对外规则：只比有价格的地区；人民币价按快照当天汇率折算，不做实时换算。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.core.errors import AppError
from app.domains.official.models import OfficialPlan, OfficialRegionPrice
from app.domains.official.repository import OfficialRepository

US = "US"


class RegionPriceOut(BaseModel):
    country_code: str
    country_label: str
    currency: str
    price_text: str
    cny_price: Decimal | None
    # 相对美区的人民币价格百分比（美区 = 100）；美区或本地区没有价格时为 None
    vs_us_percent: int | None
    source_url: str
    fx_date: date | None


class OfficialPlanSummary(BaseModel):
    app_slug: str
    app_name: str
    provider: str
    plan_slug: str
    plan_name: str
    billing_period: str
    us: RegionPriceOut | None
    cheapest: RegionPriceOut | None
    region_count: int  # 有价格的地区数
    fetched_at: datetime | None  # 最近一次核实时间


class OfficialPlanDetail(OfficialPlanSummary):
    prices: list[RegionPriceOut]  # 按人民币价从低到高
    missing_regions: list[str]  # 该档位没上架的地区


def _available(plan: OfficialPlan) -> list[OfficialRegionPrice]:
    rows = [p for p in plan.prices if p.status == "available" and p.cny_price is not None]
    return sorted(rows, key=lambda p: (p.cny_price, p.country_code))


def _out(p: OfficialRegionPrice, us_cny: Decimal | None) -> RegionPriceOut:
    pct = None
    if us_cny and p.cny_price is not None:
        pct = round(p.cny_price / us_cny * 100)
    return RegionPriceOut(
        country_code=p.country_code,
        country_label=p.country_label,
        currency=p.currency,
        price_text=p.price_text,
        cny_price=p.cny_price,
        vs_us_percent=pct,
        source_url=p.source_url,
        fx_date=p.fx_date,
    )


def _summary(plan: OfficialPlan) -> dict[str, object]:
    rows = _available(plan)
    us = next((p for p in rows if p.country_code == US), None)
    us_cny = us.cny_price if us else None
    return {
        "app_slug": plan.app_slug,
        "app_name": plan.app_name,
        "provider": plan.provider,
        "plan_slug": plan.plan_slug,
        "plan_name": plan.plan_name,
        "billing_period": plan.billing_period,
        "us": _out(us, us_cny) if us else None,
        "cheapest": _out(rows[0], us_cny) if rows else None,
        "region_count": len(rows),
        "fetched_at": max((p.fetched_at for p in plan.prices), default=None),
    }


class OfficialService:
    def __init__(self, repo: OfficialRepository) -> None:
        self.repo = repo

    async def list_plans(self) -> list[OfficialPlanSummary]:
        return [
            OfficialPlanSummary.model_validate(_summary(p)) for p in await self.repo.list_plans()
        ]

    async def get_plan(self, app_slug: str, plan_slug: str) -> OfficialPlanDetail:
        plan = await self.repo.get_plan(app_slug, plan_slug)
        if plan is None:
            raise AppError("NOT_FOUND")
        summary = _summary(plan)
        us = summary["us"]
        us_cny = us.cny_price if isinstance(us, RegionPriceOut) else None
        return OfficialPlanDetail.model_validate(
            summary
            | {
                "prices": [_out(p, us_cny) for p in _available(plan)],
                "missing_regions": sorted(
                    p.country_label for p in plan.prices if p.status != "available"
                ),
            }
        )
