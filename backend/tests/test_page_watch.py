"""页面监测采集器与 LLM 客户端：正文提取、前端渲染页识别、JSON 解析与容错。"""

import json
from typing import Any

import httpx
import pytest

from app.collectors.base import USER_AGENT, SourceConfig
from app.collectors.page_watch import PageWatchCollector, content_hash
from app.domains.deals.extraction import Extraction
from app.integrations.llm import LlmClient, LlmError

PARAGRAPH = "新用户注册即送 100 万 tokens，有效期 90 天，可用于平台上所有文本模型的调用。" * 4

ARTICLE = f"""<html><head><title>活动</title><script>var x = 1;</script></head>
<body><nav>首页 | 产品 | 文档</nav>
<article><h1>新人福利</h1><p>{PARAGRAPH}</p><p>每日签到可领取 200 积分，积分当日有效。</p></article>
<footer>版权所有</footer></body></html>"""

SPA_SHELL = '<html><body><div id="app"></div><script src="/main.js"></script></body></html>'


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_extracts_main_text_and_identifies_itself() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, html=ARTICLE)

    async with _client(handler) as http:
        result = await PageWatchCollector(http).collect(
            SourceConfig(id="1", url="https://x.example.com/events")
        )
    assert result.ok
    snap = result.items[0]
    assert "100 万 tokens" in snap.text
    assert "var x" not in snap.text
    assert snap.content_hash == content_hash(snap.text)
    assert seen[0].headers["User-Agent"] == USER_AGENT


async def test_client_rendered_page_is_reported() -> None:
    async with _client(lambda _: httpx.Response(200, html=SPA_SHELL)) as http:
        result = await PageWatchCollector(http).collect(SourceConfig(id="1", url="https://x/"))
    assert not result.ok
    assert "前端渲染" in result.errors[0]


async def test_http_error_is_reported() -> None:
    async with _client(lambda _: httpx.Response(404)) as http:
        result = await PageWatchCollector(http).collect(SourceConfig(id="1", url="https://x/"))
    assert not result.ok
    assert "抓取失败" in result.errors[0]


# ---------- LLM ----------

DEAL = {
    "title": "新人送 100 万 tokens",
    "deal_type": "signup_credit",
    "reward_text": "100 万 tokens",
    "confidence": 0.9,
}


def _llm(content: str | None = None, status: int = 200) -> tuple[LlmClient, list[Any]]:
    bodies: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append({"auth": request.headers["Authorization"], **json.loads(request.content)})
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = LlmClient(_client(handler), base_url="https://llm/v1/", api_key="k", model="m")
    return client, bodies


async def test_llm_parses_json_and_sends_model() -> None:
    llm, bodies = _llm(json.dumps({"deals": [DEAL]}))
    out = await llm.extract(system="s", user="u", schema=Extraction)
    assert out.deals[0].reward_text == "100 万 tokens"
    assert bodies[0]["auth"] == "Bearer k"
    assert bodies[0]["model"] == "m"
    assert bodies[0]["temperature"] == 0


async def test_llm_accepts_fenced_json() -> None:
    llm, _ = _llm(f"```json\n{json.dumps({'deals': [DEAL]})}\n```")
    out = await llm.extract(system="s", user="u", schema=Extraction)
    assert len(out.deals) == 1


@pytest.mark.parametrize(
    ("content", "status"),
    [
        ('{"deals": [{"title": "x"}]}', 200),  # 缺字段
        ("不是 JSON", 200),
        (None, 200),
        ("", 500),
    ],
)
async def test_llm_errors_are_wrapped(content: str | None, status: int) -> None:
    llm, _ = _llm(content, status)
    with pytest.raises(LlmError):
        await llm.extract(system="s", user="u", schema=Extraction)
