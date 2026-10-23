"""轻量 OpenAI 兼容 Chat 客户端（硅基流动）：只做「文本 → JSON → Pydantic 模型」这一件事。"""

import re

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError

from app.core.config import Settings

# 有的模型不理会 response_format，仍把 JSON 包在 ```json 代码块里
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LlmError(Exception):
    """调用失败或返回内容不符合约定的结构。"""


def _strip_fence(content: str) -> str:
    match = _FENCE.match(content.strip())
    return match.group(1) if match else content.strip()


def llm_from_settings(http: httpx.AsyncClient, settings: Settings) -> "LlmClient | None":
    """没配置 key 时返回 None，由调用方决定跳过。"""
    api_key = settings.siliconflow_api_key.get_secret_value()
    if not api_key:
        return None
    return LlmClient(
        http,
        base_url=settings.siliconflow_base_url,
        api_key=api_key,
        model=settings.llm_extract_model,
    )


class LlmClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 45.0,
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def extract[M: BaseModel](self, *, system: str, user: str, schema: type[M]) -> M:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = await self.http.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LlmError(f"LLM 调用失败：{exc}") from exc
        if not isinstance(content, str):
            raise LlmError("LLM 返回内容为空")
        try:
            return schema.model_validate_json(_strip_fence(content))
        except ValidationError as exc:
            logger.warning("LLM 返回结构不符：{}", content[:500])
            raise LlmError(f"LLM 返回结构不符：{exc.error_count()} 处错误") from exc
