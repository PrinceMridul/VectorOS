"""Anthropic provider.

Used for the tiers where reasoning quality matters most — Coach and Synthesizer
— because holding a Socratic line under a frustrated learner's pressure is
exactly a "follow negative constraints precisely" problem.

Anthropic has no JSON mode, so structured output uses assistant **prefill**:
seeding the reply with ``{`` forces the model to continue a JSON object rather
than open with prose. Combined with a stop sequence this is as reliable as a
native JSON mode and costs nothing extra.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.errors import ProviderError
from app.llm._http import post_json, require_key
from app.llm.base import ChatRequest, ChatResponse, TimedProvider

T = TypeVar("T", bound=BaseModel)

_BASE = "https://api.anthropic.com/v1"
_VERSION = "2023-06-01"


class AnthropicProvider(TimedProvider):
    name = "anthropic"

    def __init__(self, models: dict[str, str]) -> None:
        self._models = models

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": require_key("anthropic"),
            "anthropic-version": _VERSION,
            "content-type": "application/json",
        }

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return await self._timed(self._messages(request, prefill=None))

    async def _complete_json(self, request: ChatRequest, schema: type[T]) -> ChatResponse:
        response = await self._timed(self._messages(request, prefill="{"))
        # The prefilled brace is not echoed back by the API; restore it so the
        # shared parser sees a complete object.
        if not response.text.lstrip().startswith("{"):
            response.text = "{" + response.text
        return response

    async def _messages(self, request: ChatRequest, *, prefill: str | None) -> ChatResponse:
        model = self._models[request.tier.value]

        messages: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]
        if not messages:
            raise ProviderError("Anthropic requires at least one message.", provider=self.name)
        if prefill:
            messages.append({"role": "assistant", "content": prefill})

        payload: dict[str, Any] = {
            "model": model,
            "system": request.system,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop_sequences"] = request.stop

        data = await post_json(
            f"{_BASE}/messages",
            payload=payload,
            headers=self._headers(),
            provider=self.name,
        )
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        usage = data.get("usage", {})

        return ChatResponse(
            text=text,
            model=model,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderError(
            "Anthropic does not serve embeddings. "
            "Set VECTOROS_EMBEDDING_PROVIDER to gemini, openai or mock.",
            provider=self.name,
        )


__all__ = ["AnthropicProvider"]
