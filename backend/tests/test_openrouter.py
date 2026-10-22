"""OpenRouter 采集：解析规则与入库（幂等、免费版合并、不覆盖人工调整）。"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import SourceConfig
from app.collectors.openrouter import (
    DEFAULT_VENDOR_FAMILIES,
    OpenRouterModelsCollector,
    parse_models,
)
from app.domains.catalog.ingest import CatalogIngestService
from app.domains.catalog.models import AIModel, ModelPrice, PublishStatus
from app.domains.catalog.repository import CatalogRepository
from tests import factories as f


def _m(model_id: str, prompt: str, completion: str, **kw: Any) -> dict[str, Any]:
    return {
        "id": model_id,
        "name": kw.pop("name", f"Vendor: {model_id.split('/')[-1]}"),
        "context_length": kw.pop("context_length", 131072),
        "architecture": {"output_modalities": kw.pop("outputs", ["text"])},
        "pricing": {"prompt": prompt, "completion": completion} | kw.pop("pricing", {}),
        **kw,
    }


PAYLOAD = {
    "data": [
        _m(
            "deepseek/deepseek-v4.1-flash",
            "0.00000027",
            "0.0000011",
            name="DeepSeek: DeepSeek V4.1 Flash",
            pricing={"input_cache_read": "0.00000007"},
        ),
        _m(
            "deepseek/deepseek-v4.1-flash:free",
            "0",
            "0",
            name="DeepSeek: DeepSeek V4.1 Flash (free)",
        ),
        _m("z-ai/glm-5-air:free", "0", "0", name="Z.AI: GLM 5 Air (free)"),
        _m("~openai/gpt-latest", "0.000001", "0.000004"),  # 别名，跳过
        _m("openrouter/auto", "-1", "-1"),  # 不在白名单
        _m("openai/gpt-router", "-1", "-1"),  # 动态计价，跳过
        _m("openai/gpt-image-2", "0.000005", "0.00004", outputs=["image"]),  # 非文本
        _m("google/lyria-3-pro", "0", "0", outputs=["text", "audio"]),  # 输出不只是文本
        _m("anthropic/claude-haiku-5.5:batch", "0.0000005", "0.0000025"),  # 批处理计价
        _m("google/gemma-4-31b", "0.0000001", "0.0000002", name="Google: Gemma 4 31B"),
        _m("someco/tiny-model", "0.0000001", "0.0000001"),  # 不在白名单
    ]
}


def test_parse_applies_rules_and_merges_free_variant() -> None:
    items = {i.model_id: i for i in parse_models(PAYLOAD, DEFAULT_VENDOR_FAMILIES)}
    assert set(items) == {
        "deepseek/deepseek-v4.1-flash",
        "z-ai/glm-5-air",
        "google/gemma-4-31b",
    }
    assert items["google/gemma-4-31b"].family == "gemma"  # 不归到 gemini

    ds = items["deepseek/deepseek-v4.1-flash"]
    assert ds.slug == "deepseek-v4-1-flash"
    assert ds.name == "DeepSeek V4.1 Flash"
    assert ds.family == "deepseek"
    assert ds.input_price == Decimal("0.2700")
    assert ds.output_price == Decimal("1.1000")
    assert ds.cache_read_price == Decimal("0.0700")
    assert ds.has_paid and ds.has_free

    glm = items["z-ai/glm-5-air"]
    assert glm.family == "glm"
    assert glm.name == "GLM 5 Air"
    assert not glm.has_paid and glm.has_free
    assert glm.output_price is None


async def test_collector_reports_empty_result_as_error() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []}))
    async with httpx.AsyncClient(transport=transport) as http:
        result = await OpenRouterModelsCollector(http).collect(
            SourceConfig(id="s", url="https://x")
        )
    assert not result.ok  # 格式变了解析不出东西：按失败处理，不能当成全部下架


async def test_collector_http_error() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    async with httpx.AsyncClient(transport=transport) as http:
        result = await OpenRouterModelsCollector(http).collect(
            SourceConfig(id="s", url="https://x")
        )
    assert result.errors == ["HTTP 503"]


async def test_ingest_is_idempotent_and_keeps_manual_status(db_session: AsyncSession) -> None:
    await f.platform(db_session, "openrouter")
    await db_session.commit()
    items = parse_models(PAYLOAD, DEFAULT_VENDOR_FAMILIES)
    service = CatalogIngestService(CatalogRepository(db_session))

    first = datetime(2026, 10, 22, tzinfo=UTC)
    assert await service.ingest_openrouter(items, first) == 3

    # 人工把一个模型隐藏、改了系列后，再次采集不应覆盖
    model = await db_session.scalar(select(AIModel).where(AIModel.slug == "glm-5-air"))
    assert model is not None
    model.status = PublishStatus.HIDDEN
    model.family = "zhipu"
    await db_session.commit()

    second = datetime(2026, 10, 23, tzinfo=UTC)
    await service.ingest_openrouter(items, second)
    db_session.expire_all()

    models = (await db_session.scalars(select(AIModel).order_by(AIModel.slug))).all()
    assert [m.slug for m in models] == ["deepseek-v4-1-flash", "gemma-4-31b", "glm-5-air"]
    assert models[2].status == PublishStatus.HIDDEN
    assert models[2].family == "zhipu"

    prices = (await db_session.scalars(select(ModelPrice))).all()
    assert len(prices) == 3
    assert all(p.confirmed_at == second for p in prices)
    ds_price = next(p for p in prices if p.model_id == models[0].id)
    assert ds_price.is_free is True
    assert ds_price.free_note == "另有 :free 免费版，有请求频率上限"
    assert ds_price.source_url == "https://openrouter.ai/deepseek/deepseek-v4.1-flash"
