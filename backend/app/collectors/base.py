"""采集器插件接口：新增一种采集方式 = 新增一个 Collector 子类并注册，不改既有代码。

边界：
- 只读取公开或已授权的数据，不绕过验证码、登录墙、WAF。
- 采集失败不等于缺货 / 活动下线：失败只记入 errors，由上层决定是否重试，禁止据此批量下架旧数据。
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    """一个采集来源：例如某平台的定价页、活动页或公开接口。"""

    id: str
    url: str
    options: dict[str, Any] = Field(default_factory=dict)


class CollectResult[T](BaseModel):
    source_id: str
    items: list[T] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def ok(self) -> bool:
        return not self.errors


class Collector[T](ABC):
    kind: ClassVar[str]

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    @abstractmethod
    async def collect(self, source: SourceConfig) -> CollectResult[T]: ...
