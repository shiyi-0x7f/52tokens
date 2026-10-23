"""卡网比价数据访问。"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shops.models import ShopOffer, ShopProduct, ShopSource


class ShopRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_enabled_sources(self) -> Sequence[ShopSource]:
        stmt = select(ShopSource).where(ShopSource.enabled.is_(True)).order_by(ShopSource.id)
        return (await self.session.scalars(stmt)).all()

    async def get_source(self, source_id: int) -> ShopSource | None:
        return await self.session.get(ShopSource, source_id)

    async def product_ids_by_slug(self) -> dict[str, int]:
        rows = await self.session.execute(select(ShopProduct.slug, ShopProduct.id))
        return {slug: pid for slug, pid in rows.all()}

    async def offers_for_source(self, source_id: int) -> dict[str, ShopOffer]:
        rows = await self.session.scalars(select(ShopOffer).where(ShopOffer.source_id == source_id))
        return {o.external_id: o for o in rows.all()}

    def add(self, obj: ShopOffer) -> None:
        self.session.add(obj)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
