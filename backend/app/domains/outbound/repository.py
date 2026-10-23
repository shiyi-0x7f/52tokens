"""出站点击数据访问。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.outbound.models import OutboundClick


class OutboundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_click(self, click: OutboundClick) -> None:
        self.session.add(click)
        await self.session.commit()
