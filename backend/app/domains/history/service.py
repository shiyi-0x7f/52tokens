"""价格历史快照：把当前对外展示的价格按天落一行。

- 官方 API 价格：每个对外展示的（平台, 模型）一行；
- 卡网：每个对外展示的标准商品一行，有货最低价直接复用比价页规则（ShopService），保证一致。
"""

from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel

from app.domains.history.repository import HistoryRepository
from app.domains.shops.repository import ShopRepository
from app.domains.shops.service import ShopService

# 站点面向国内用户，「哪一天」按北京时间算；用固定偏移，不依赖系统时区库
BEIJING = timezone(timedelta(hours=8))


def beijing_day(now: datetime) -> date:
    return now.astimezone(BEIJING).date()


class SnapshotReport(BaseModel):
    day: date
    model_prices: int
    shop_products: int


class PriceHistoryService:
    def __init__(self, repo: HistoryRepository, shops: ShopRepository) -> None:
        self.repo = repo
        self.shops = shops

    async def snapshot(self, now: datetime) -> SnapshotReport:
        day = beijing_day(now)
        prices = await self.repo.public_model_prices()
        await self.repo.upsert_model_prices(
            [
                {
                    "day": day,
                    "platform_id": p.platform_id,
                    "model_id": p.model_id,
                    "currency": p.currency.value,
                    "input_price": p.input_price,
                    "output_price": p.output_price,
                    "cache_read_price": p.cache_read_price,
                    "is_free": p.is_free,
                }
                for p in prices
            ]
        )
        products = await ShopService(self.shops).list_products()
        ids = await self.shops.product_ids_by_slug()
        await self.repo.upsert_shop_products(
            [
                {
                    "day": day,
                    "product_id": ids[s.slug],
                    "min_price": s.min_price,
                    "in_stock_shops": s.in_stock_shops,
                    "offer_count": s.offer_count,
                }
                for s in products
            ]
        )
        await self.repo.commit()
        return SnapshotReport(day=day, model_prices=len(prices), shop_products=len(products))
