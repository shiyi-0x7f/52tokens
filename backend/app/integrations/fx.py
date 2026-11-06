"""汇率：以美元为基准取各币种汇率，主用 Frankfurter（欧洲央行数据），缺币种时改用 open.er-api.com。

两个来源都拿不到全部所需币种时抛 FxError，由调用方放弃本次换算（不使用不完整的汇率）。
"""

from datetime import date
from decimal import Decimal

import httpx
from loguru import logger
from pydantic import BaseModel

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
OPEN_ER_URL = "https://open.er-api.com/v6/latest/USD"
FX_TIMEOUT = 20.0


class FxError(Exception):
    pass


class FxSnapshot(BaseModel):
    """rates：1 美元可兑换多少该币种（USD = 1）。"""

    day: date
    source: str
    rates: dict[str, Decimal]

    def to_cny(self, currency: str) -> Decimal:
        """1 单位该币种折合多少人民币。"""
        return self.rates["CNY"] / self.rates[currency]

    def to_usd(self, currency: str) -> Decimal | None:
        rate = self.rates.get(currency)
        return Decimal(1) / rate if rate else None


def _missing(rates: dict[str, Decimal], wanted: set[str]) -> list[str]:
    return sorted(c for c in wanted if c not in rates)


async def _frankfurter(client: httpx.AsyncClient, wanted: set[str]) -> FxSnapshot:
    symbols = ",".join(sorted(wanted - {"USD"}))
    resp = await client.get(
        FRANKFURTER_URL, params={"base": "USD", "symbols": symbols}, timeout=FX_TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    rates = {"USD": Decimal(1)} | {k: Decimal(str(v)) for k, v in data["rates"].items()}
    if missing := _missing(rates, wanted):
        raise FxError(f"Frankfurter 缺少币种 {','.join(missing)}")
    return FxSnapshot(day=date.fromisoformat(data["date"]), source="Frankfurter", rates=rates)


async def _open_er(client: httpx.AsyncClient, wanted: set[str], today: date) -> FxSnapshot:
    resp = await client.get(OPEN_ER_URL, timeout=FX_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success":
        raise FxError(f"open.er-api.com 返回 {data.get('result')}")
    raw = data["rates"]
    rates = {"USD": Decimal(1)} | {c: Decimal(str(raw[c])) for c in wanted if c in raw}
    if missing := _missing(rates, wanted):
        raise FxError(f"open.er-api.com 缺少币种 {','.join(missing)}")
    return FxSnapshot(day=today, source="open.er-api.com", rates=rates)


async def fetch_usd_rates(
    client: httpx.AsyncClient, currencies: set[str], today: date
) -> FxSnapshot:
    wanted = set(currencies) | {"CNY", "USD"}
    try:
        return await _frankfurter(client, wanted)
    except (httpx.HTTPError, FxError, KeyError, ValueError) as exc:
        logger.warning("Frankfurter 汇率不可用，改用 open.er-api.com：{}", exc)
    try:
        return await _open_er(client, wanted, today)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise FxError(f"汇率获取失败：{exc}") from exc
