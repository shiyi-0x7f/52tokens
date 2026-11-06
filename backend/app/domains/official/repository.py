"""官方订阅地区价数据访问。"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.official.models import OfficialPlan, OfficialRegionPrice

# 一条 INSERT 的参数个数有上限，大批量分批写
_BATCH = 200


class OfficialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_plans(self) -> Sequence[OfficialPlan]:
        stmt = (
            select(OfficialPlan)
            .options(selectinload(OfficialPlan.prices))
            .order_by(OfficialPlan.sort_order, OfficialPlan.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def get_plan(self, app_slug: str, plan_slug: str) -> OfficialPlan | None:
        return await self.session.scalar(
            select(OfficialPlan)
            .where(OfficialPlan.app_slug == app_slug, OfficialPlan.plan_slug == plan_slug)
            .options(selectinload(OfficialPlan.prices))
        )

    # ---------- 采集同步 ----------

    async def upsert_plans(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
        """按（应用, 档位）建 / 更新档位，返回（应用, 档位）→ id。"""
        base = insert(OfficialPlan).values(rows)
        keys = {"app_slug", "plan_slug"}
        stmt = base.on_conflict_do_update(
            index_elements=list(keys),
            set_={c: base.excluded[c] for c in rows[0] if c not in keys}
            | {"updated_at": func.now()},
        ).returning(OfficialPlan.app_slug, OfficialPlan.plan_slug, OfficialPlan.id)
        return {(a, p): i for a, p, i in (await self.session.execute(stmt)).all()}

    async def delete_plans_except(self, keep: set[tuple[str, str]]) -> int:
        """删除配置里已经没有的档位（地区价随外键级联删除），返回删除数。"""
        stmt = delete(OfficialPlan)
        if keep:
            stmt = stmt.where(tuple_(OfficialPlan.app_slug, OfficialPlan.plan_slug).not_in(keep))
        result = await self.session.execute(stmt.returning(OfficialPlan.id))
        return len(result.all())

    async def available_keys(self) -> set[tuple[int, str]]:
        """当前有价格的（档位 id, 地区代码）。"""
        rows = await self.session.execute(
            select(OfficialRegionPrice.plan_id, OfficialRegionPrice.country_code).where(
                OfficialRegionPrice.status == "available"
            )
        )
        return {(plan_id, code) for plan_id, code in rows.all()}

    async def upsert_prices(self, rows: list[dict[str, Any]]) -> None:
        keys = {"plan_id", "country_code"}
        for i in range(0, len(rows), _BATCH):
            chunk = rows[i : i + _BATCH]
            stmt = insert(OfficialRegionPrice).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=list(keys),
                set_={c: stmt.excluded[c] for c in chunk[0] if c not in keys}
                | {"updated_at": func.now()},
            )
            await self.session.execute(stmt)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
