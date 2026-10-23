"""卡网比价数据访问。"""

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.catalog.models import PublishStatus
from app.domains.shops.models import ShopCollectorKind, ShopOffer, ShopProduct, ShopSource


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

    # ---------- 后台 ----------

    async def list_sources(
        self,
        *,
        kind: ShopCollectorKind | None,
        state: str | None,
        q: str | None,
        offset: int,
        limit: int,
    ) -> tuple[Sequence[ShopSource], int]:
        stmt = select(ShopSource)
        if kind is not None:
            stmt = stmt.where(ShopSource.collector_kind == kind)
        if state == "ok":
            stmt = stmt.where(ShopSource.checked_at.is_not(None), ShopSource.last_error == "")
        elif state == "failed":
            stmt = stmt.where(ShopSource.last_error != "")
        elif state == "unchecked":
            stmt = stmt.where(ShopSource.checked_at.is_(None))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(ShopSource.host.ilike(like), ShopSource.name.ilike(like)))
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.session.scalars(
            stmt.order_by(ShopSource.offer_count.desc(), ShopSource.id).offset(offset).limit(limit)
        )
        return rows.all(), int(total or 0)

    async def entry_url_taken(self, entry_url: str, exclude_id: int | None = None) -> bool:
        stmt = select(ShopSource.id).where(ShopSource.entry_url == entry_url)
        if exclude_id is not None:
            stmt = stmt.where(ShopSource.id != exclude_id)
        return await self.session.scalar(stmt) is not None

    def add_source(self, source: ShopSource) -> None:
        self.session.add(source)

    # ---------- 对外 ----------

    async def list_public_products(self, *, exclude: str) -> Sequence[ShopProduct]:
        stmt = (
            select(ShopProduct)
            .where(ShopProduct.status == PublishStatus.ACTIVE, ShopProduct.slug != exclude)
            .order_by(ShopProduct.sort_order, ShopProduct.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def get_public_product(self, slug: str) -> ShopProduct | None:
        return await self.session.scalar(
            select(ShopProduct).where(
                ShopProduct.slug == slug, ShopProduct.status == PublishStatus.ACTIVE
            )
        )

    async def public_offers(self, product_ids: list[int]) -> Sequence[ShopOffer]:
        """这些商品下可展示的报价：店铺启用、报价未隐藏、有价格。"""
        if not product_ids:
            return []
        stmt = (
            select(ShopOffer)
            .join(ShopOffer.source)
            .where(
                ShopOffer.product_id.in_(product_ids),
                ShopOffer.hidden.is_(False),
                ShopOffer.price.is_not(None),
                ShopSource.enabled.is_(True),
            )
            .options(selectinload(ShopOffer.source))
        )
        return (await self.session.scalars(stmt)).all()

    def add(self, obj: ShopOffer) -> None:
        self.session.add(obj)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, obj: ShopSource) -> None:
        await self.session.refresh(obj)
