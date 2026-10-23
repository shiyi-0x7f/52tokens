"""短期键值存储（OAuth state、会话、app token 缓存、任务互斥锁）。

接口抽象出来，测试可换内存实现。
"""

from functools import lru_cache
from typing import Protocol

from redis.asyncio import Redis

from app.core.config import get_settings


class KeyValueStore(Protocol):
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...
    async def set_if_absent(self, key: str, value: str, ttl_seconds: int) -> bool:
        """键不存在时才写入（原子），返回是否写入成功。用作互斥锁。"""
        ...

    async def get(self, key: str) -> str | None: ...
    async def pop(self, key: str) -> str | None:
        """原子地取出并删除（state 只能用一次）。"""
        ...

    async def delete(self, key: str) -> None: ...


class RedisStore:
    def __init__(self, client: Redis, prefix: str) -> None:
        self.client = client
        self.prefix = prefix

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self.client.set(self.prefix + key, value, ex=ttl_seconds)

    async def set_if_absent(self, key: str, value: str, ttl_seconds: int) -> bool:
        return bool(await self.client.set(self.prefix + key, value, ex=ttl_seconds, nx=True))

    async def get(self, key: str) -> str | None:
        value = await self.client.get(self.prefix + key)
        return value.decode() if isinstance(value, bytes) else value

    async def pop(self, key: str) -> str | None:
        value = await self.client.getdel(self.prefix + key)
        return value.decode() if isinstance(value, bytes) else value

    async def delete(self, key: str) -> None:
        await self.client.delete(self.prefix + key)


@lru_cache
def get_store() -> KeyValueStore:
    settings = get_settings()
    return RedisStore(Redis.from_url(settings.redis_url), settings.redis_key_prefix)
