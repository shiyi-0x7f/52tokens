"""采集器框架：注册、分派、失败不抛异常。"""

from typing import ClassVar

import httpx
import pytest

from app.collectors.base import Collector, CollectResult, SourceConfig
from app.collectors.registry import get_collector_class, register, registered_kinds
from app.workers.tasks import run_collector


@register
class EchoCollector(Collector[str]):
    kind: ClassVar[str] = "test_echo"

    async def collect(self, source: SourceConfig) -> CollectResult[str]:
        resp = await self.client.get(source.url)
        if resp.status_code != 200:
            return CollectResult(source_id=source.id, errors=[f"HTTP {resp.status_code}"])
        return CollectResult(source_id=source.id, items=[resp.text])


def _client(status: int, text: str = "") -> httpx.AsyncClient:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text=text))
    return httpx.AsyncClient(transport=transport)


def test_registry_lookup() -> None:
    assert "test_echo" in registered_kinds()
    assert get_collector_class("test_echo") is EchoCollector
    with pytest.raises(ValueError, match="未知"):
        get_collector_class("nope")


def test_duplicate_kind_rejected() -> None:
    with pytest.raises(ValueError, match="重复"):

        @register
        class Another(Collector[str]):
            kind: ClassVar[str] = "test_echo"

            async def collect(self, source: SourceConfig) -> CollectResult[str]:
                return CollectResult(source_id=source.id)


async def test_run_collector_success() -> None:
    async with _client(200, "hello") as http:
        result = await run_collector(
            {"http": http}, "test_echo", {"id": "s1", "url": "https://example.com"}
        )
    assert result == {"source_id": "s1", "items": 1, "errors": []}


async def test_run_collector_failure_is_reported_not_raised() -> None:
    async with _client(503) as http:
        result = await run_collector(
            {"http": http}, "test_echo", {"id": "s1", "url": "https://example.com"}
        )
    assert result["items"] == 0
    assert result["errors"] == ["HTTP 503"]
