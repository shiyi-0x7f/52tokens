"""52tokens 会话：随机令牌 → 用户 ID，存在键值存储里。

令牌只以 SHA-256 摘要作为存储键，存储泄露也拿不到可用令牌。
登录编排（AuthService）和后台鉴权都通过这里读写会话，后者不需要依赖第三方登录。
"""

import hashlib
import secrets

from app.core.errors import AppError
from app.core.kv import KeyValueStore
from app.domains.accounts.models import User
from app.domains.accounts.repository import UserRepository
from app.domains.accounts.schemas import UserOut


def session_key(token: str) -> str:
    return f"session:{hashlib.sha256(token.encode()).hexdigest()}"


class SessionService:
    def __init__(self, store: KeyValueStore, users: UserRepository, ttl_days: int) -> None:
        self.store = store
        self.users = users
        self.ttl_seconds = ttl_days * 86400

    async def open(self, user: User) -> str:
        token = secrets.token_urlsafe(32)
        await self.store.set(session_key(token), str(user.id), self.ttl_seconds)
        return token

    async def get_user(self, token: str) -> UserOut:
        user_id = await self.store.get(session_key(token))
        if user_id is None:
            raise AppError("UNAUTHORIZED")
        user = await self.users.get(int(user_id))
        if user is None:
            await self.store.delete(session_key(token))
            raise AppError("UNAUTHORIZED")
        return UserOut.model_validate(user)

    async def close(self, token: str) -> None:
        await self.store.delete(session_key(token))
