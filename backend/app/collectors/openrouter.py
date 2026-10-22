"""OpenRouter 公开模型列表：https://openrouter.ai/api/v1/models（无需鉴权）。

只取事实数据（名称、上下文、价格），不转载模型简介。价格原始单位是「美元 / token」，
这里换算成「美元 / 百万 tokens」。`xxx:free` 免费版与付费版合并为同一个模型。
"""

from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel

from app.collectors.base import Collector, CollectResult, SourceConfig
from app.collectors.registry import register

MODELS_URL = "https://openrouter.ai/api/v1/models"
PER_MILLION = Decimal(1_000_000)
FREE_SUFFIX = ":free"
# 批处理计价（异步、延迟高）与普通调用不可比，混进来会让「最低价」失真
SKIPPED_SUFFIXES = (":batch",)
# 同一厂商下的不同系列：按模型名前缀细分（如 google/gemma-* 不是 Gemini）
PREFIX_FAMILIES: dict[str, str] = {"gemma": "gemma"}

# 厂商前缀 → 模型系列。只收这些主流厂商，避免生成大量低价值页面
DEFAULT_VENDOR_FAMILIES: dict[str, str] = {
    "deepseek": "deepseek",
    "qwen": "qwen",
    "z-ai": "glm",
    "moonshotai": "kimi",
    "minimax": "minimax",
    "google": "gemini",
    "anthropic": "claude",
    "openai": "gpt",
    "meta-llama": "llama",
    "mistralai": "mistral",
    "x-ai": "grok",
}


class OpenRouterModel(BaseModel):
    """一个模型在 OpenRouter 上的价格（美元 / 百万 tokens）。"""

    model_id: str  # 去掉 :free 后的 OpenRouter id，如 deepseek/deepseek-v4.1-flash
    slug: str
    name: str
    family: str
    context_window: int | None
    input_price: Decimal | None
    output_price: Decimal | None
    cache_read_price: Decimal | None
    has_paid: bool
    has_free: bool


def _per_million(raw: Any) -> Decimal | None:
    """单 token 美元价 → 每百万；缺失或负数（动态计价）返回 None。"""
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    if value < 0:
        return None
    return (value * PER_MILLION).quantize(Decimal("0.0001"))


def _slug(model_id: str) -> str:
    """deepseek/deepseek-v4.1-flash → deepseek-v4-1-flash（去掉厂商前缀，非字母数字转 -）。"""
    base = model_id.split("/", 1)[-1].lower()
    out = "".join(ch if ch.isalnum() else "-" for ch in base)
    return "-".join(part for part in out.split("-") if part)[:80]


def _clean_name(name: str) -> str:
    """'DeepSeek: DeepSeek V4.1 Flash (free)' → 'DeepSeek V4.1 Flash'"""
    name = name.split(": ", 1)[-1]
    return name.removesuffix(" (free)").strip()[:120]


def _is_text_model(item: dict[str, Any]) -> bool:
    """只收纯文本输出的模型；图像 / 音频生成模型的计价方式不同，不放在一起比。"""
    outputs = (item.get("architecture") or {}).get("output_modalities") or ["text"]
    return list(outputs) == ["text"]


def _family(model_id: str, vendor_families: dict[str, str]) -> str | None:
    vendor, _, base = model_id.partition("/")
    family = vendor_families.get(vendor)
    if family is None:
        return None
    for prefix, prefix_family in PREFIX_FAMILIES.items():
        if base.startswith(prefix):
            return prefix_family
    return family


def parse_models(payload: dict[str, Any], vendor_families: dict[str, str]) -> list[OpenRouterModel]:
    merged: dict[str, OpenRouterModel] = {}
    for item in payload.get("data", []):
        raw_id = str(item.get("id", ""))
        # ~ 开头是「始终指向最新版」的别名，和真实模型重复
        if not raw_id or raw_id.startswith("~") or "/" not in raw_id:
            continue
        if raw_id.endswith(SKIPPED_SUFFIXES):
            continue
        family = _family(raw_id, vendor_families)
        if family is None or not _is_text_model(item):
            continue

        is_free_variant = raw_id.endswith(FREE_SUFFIX)
        model_id = raw_id.removesuffix(FREE_SUFFIX)
        pricing = item.get("pricing") or {}
        prompt = _per_million(pricing.get("prompt"))
        completion = _per_million(pricing.get("completion"))
        if prompt is None or completion is None:
            continue  # 动态计价 / 价格缺失，无法比较

        current = merged.get(model_id)
        paid = not is_free_variant and (prompt > 0 or completion > 0)
        free = is_free_variant or (prompt == 0 and completion == 0)
        if current is None:
            current = OpenRouterModel(
                model_id=model_id,
                slug=_slug(model_id),
                name=_clean_name(str(item.get("name") or model_id)),
                family=family,
                context_window=item.get("context_length"),
                input_price=None,
                output_price=None,
                cache_read_price=None,
                has_paid=False,
                has_free=False,
            )
            merged[model_id] = current
        if paid:
            current.input_price = prompt
            current.output_price = completion
            current.cache_read_price = _per_million(pricing.get("input_cache_read"))
            current.has_paid = True
            # 付费版的名称不带 (free)，优先用它
            current.name = _clean_name(str(item.get("name") or model_id))
        if free:
            current.has_free = True
    return list(merged.values())


@register
class OpenRouterModelsCollector(Collector[OpenRouterModel]):
    kind: ClassVar[str] = "openrouter_models"

    async def collect(self, source: SourceConfig) -> CollectResult[OpenRouterModel]:
        vendor_families = source.options.get("vendor_families", DEFAULT_VENDOR_FAMILIES)
        try:
            resp = await self.client.get(source.url, timeout=30.0)
        except httpx.HTTPError as exc:
            return CollectResult(source_id=source.id, errors=[f"请求失败: {exc}"])
        if resp.status_code != 200:
            return CollectResult(source_id=source.id, errors=[f"HTTP {resp.status_code}"])
        try:
            items = parse_models(resp.json(), vendor_families)
        except ValueError as exc:
            return CollectResult(source_id=source.id, errors=[f"解析失败: {exc}"])
        if not items:
            # 一个都没解析出来多半是接口格式变了：按失败处理，不能当成「全部下架」
            return CollectResult(source_id=source.id, errors=["没有解析出任何模型"])
        return CollectResult(source_id=source.id, items=items)
