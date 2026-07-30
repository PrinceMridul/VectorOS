"""OpenAI provider."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.llm._http import post_json, require_key
from app.llm.base import ChatRequest, ChatResponse, TimedProvider

T = TypeVar("T", bound=BaseModel)

_BASE = "https://api.openai.com/v1"


class OpenAIProvider(TimedProvider):
    name = "openai"

    def __init__(self, models: dict[str, str]) -> None:
        self._models = models

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {require_key('openai')}",
            "content-type": "application/json",
        }

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return await self._timed(self._chat(request, json_mode=False))

    async def _complete_json(self, request: ChatRequest, schema: type[T]) -> ChatResponse:
        return await self._timed(self._chat(request, json_mode=True))

    async def _chat(self, request: ChatRequest, *, json_mode: bool) -> ChatResponse:
        model = self._models[request.tier.value]
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                *({"role": m.role, "content": m.content} for m in request.messages),
            ],
            "temperature": request.temperature,
            "max_completion_tokens": request.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if request.stop:
            payload["stop"] = request.stop

        data = await post_json(
            f"{_BASE}/chat/completions",
            payload=payload,
            headers=self._headers(),
            provider=self.name,
        )
        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})

        return ChatResponse(
            text=text or "",
            model=model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        data = await post_json(
            f"{_BASE}/embeddings",
            payload={"model": settings.embedding_model, "input": texts},
            headers=self._headers(),
            provider=self.name,
        )
        return [item.get("embedding", []) for item in data.get("data", [])]


__all__ = ["OpenAIProvider"]
