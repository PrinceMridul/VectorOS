"""Google Gemini provider."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.llm._http import post_json, require_key
from app.llm.base import ChatRequest, ChatResponse, TimedProvider

T = TypeVar("T", bound=BaseModel)

_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(TimedProvider):
    name = "gemini"

    def __init__(self, models: dict[str, str]) -> None:
        self._models = models

    def _model(self, request: ChatRequest) -> str:
        return self._models[request.tier.value]

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return await self._timed(self._generate(request, json_mode=False))

    async def _complete_json(self, request: ChatRequest, schema: type[T]) -> ChatResponse:
        # Native constrained decoding: makes the first parse near-certain, which
        # removes a repair round-trip from the hot path.
        return await self._timed(self._generate(request, json_mode=True))

    async def _generate(self, request: ChatRequest, *, json_mode: bool) -> ChatResponse:
        model = self._model(request)
        key = require_key("gemini")

        generation: dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
        }
        if json_mode:
            generation["responseMimeType"] = "application/json"
        if request.stop:
            generation["stopSequences"] = request.stop

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in request.messages
            ],
            "generationConfig": generation,
        }

        data = await post_json(
            f"{_BASE}/models/{model}:generateContent?key={key}",
            payload=payload,
            headers={"content-type": "application/json"},
            provider=self.name,
        )

        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata", {})

        return ChatResponse(
            text=text,
            model=model,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        key = require_key("gemini")
        model = settings.embedding_model
        data = await post_json(
            f"{_BASE}/models/{model}:batchEmbedContents?key={key}",
            payload={
                "requests": [
                    {"model": f"models/{model}", "content": {"parts": [{"text": text}]}}
                    for text in texts
                ]
            },
            headers={"content-type": "application/json"},
            provider=self.name,
        )
        return [item.get("values", []) for item in data.get("embeddings", [])]


__all__ = ["GeminiProvider"]
