"""价格历史数据访问。"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.catalog.models import AIModel, ModelPrice, Platform, PublishStatus
from app.domains.history.models import ModelPriceDaily, ShopProductDaily


class HistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def public_model_prices(self) -> Sequence[ModelPrice]:
        """对外展示的官方 API 价格：与 catalog.service 的展示规则一致
        （价格已发布且已核实、平台与模型都已发布）。"""
        stmt = (
            select(ModelPrice)
            .join(ModelPrice.platform)
            .join(ModelPrice.model)
            .where(
                ModelPrice.status == PublishStatus.ACTIVE,
                ModelPrice.confirmed_at.is_not(None),
                Platform.status == PublishStatus.ACTIVE,
                AIModel.status == PublishStatus.ACTIVE,
            )
            .options(selectinload(ModelPrice.platform), selectinload(ModelPrice.model))
        )
        return (await self.session.scalars(stmt)).all()

    async def upsert_model_prices(self, rows: list[dict[str, Any]]) -> None:
        await self._upsert(ModelPriceDaily, rows, ["day", "platform_id", "model_id"])

    async def upsert_shop_products(self, rows: list[dict[str, Any]]) -> None:
        await self._upsert(ShopProductDaily, rows, ["day", "product_id"])

    async def _upsert(
        self,
        table: type[ModelPriceDaily] | type[ShopProductDaily],
        rows: list[dict[str, Any]],
        keys: list[str],
    ) -> None:
        """同一天再次快照时覆盖当天的值。"""
        if not rows:
            return
        stmt = insert(table).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=keys,
            set_={c: stmt.excluded[c] for c in rows[0] if c not in keys}
            | {"recorded_at": func.now()},
        )
        await self.session.execute(stmt)

    async def commit(self) -> None:
        await self.session.commit()
