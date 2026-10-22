from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.accounts.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_from_scc(
        self,
        *,
        scc_user_id: int,
        nickname: str,
        email: str | None,
        avatar_url: str | None,
        auth_provider: str,
        is_admin: bool,
        now: datetime,
    ) -> User:
        """按 scc_user_id 建 / 更新本地用户；管理员身份只升不降（手动降级在后台做）。"""
        values = {
            "scc_user_id": scc_user_id,
            "nickname": nickname,
            "email": email,
            "avatar_url": avatar_url,
            "auth_provider": auth_provider,
            "is_admin": is_admin,
            "last_login_at": now,
        }
        insert_stmt = insert(User).values(values)
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["scc_user_id"],
            set_={
                "nickname": excluded.nickname,
                "email": excluded.email,
                "avatar_url": excluded.avatar_url,
                "auth_provider": excluded.auth_provider,
                "is_admin": User.is_admin | excluded.is_admin,
                "last_login_at": excluded.last_login_at,
                "updated_at": now,
            },
        ).returning(User)
        user: User = (await self.session.execute(stmt)).scalar_one()
        await self.session.commit()
        return user

    async def get(self, user_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id))
