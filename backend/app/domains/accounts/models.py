"""账号域：52tokens 本地用户。身份真源在 SCC，这里以 scc_user_id 关联。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scc_user_id: Mapped[int] = mapped_column(Integer, unique=True)
    nickname: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    auth_provider: Mapped[str] = mapped_column(String(20))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
