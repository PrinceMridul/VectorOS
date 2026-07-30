"""Provider-agnostic LLM interface.

Agents never import a vendor SDK and never name a model. They ask for a
*capability tier* (`fast` / `balanced` / `deep`) and get whatever the deployment
has mapped to it. Three reasons this is worth the indirection:

1. **The pedagogy is the moat, not the model.** If swapping Gemini for Claude
   requires touching an agent, the agent is coupled to the wrong thing.
2. **Cost and latency are pedagogical constraints.** Multi-agent tutoring
   compounds latency, and engagement dies past ~4 seconds. Being able to route
   the hot-path Router to a cheap fast model while the Coach uses a deep one is
   a product lever, not an ops detail.
3. **Offline determinism.** :class:`~app.llm.mock.MockProvider` implements this
   same protocol, so the entire tutoring loop — and every test — runs with no
   API key and no network.

Structured output is a first-class operation rather than "prompt it and hope":
the Examiner returning malformed JSON is a *pedagogical* failure, so parsing,
repair and validation live here once instead of in every agent.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.domain.enums import ModelTier

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

Role = Literal["system", "user", "assistant"]

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


@dataclass(slots=True)
class Message:
    role: Role
    content: str


@dataclass(slots=True)
class ChatRequest:
    system: str
    messages: list[Message]
    tier: ModelTier = ModelTier.BALANCED
    temperature: float = 0.4
    max_tokens: int = 1024
    stop: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    """Structured context for the *offline* provider. Network providers ignore it.

    This keeps the mock genuinely useful (it can diagnose against the real
    canonical model) without leaking a test seam into production prompts.
    """


@dataclass(slots=True)
class ChatResponse:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    provider: str = ""


class LLMProvider(ABC):
    """The seam. Everything above this line is pedagogy; below it is plumbing."""

    name: str = "base"

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    # ── Structured output ───────────────────────────────────────────────────
    async def structured(self, request: ChatRequest, schema: type[T]) -> tuple[T, ChatResponse]:
        """Return a validated model instance.

        Default implementation: JSON-schema in the system prompt, then parse with
        one bounded repair attempt. Providers with native constrained decoding
        override :meth:`_complete_json` to make the first attempt near-certain.
        """
        contract = _schema_contract(schema)
        primed = ChatRequest(
            system=f"{request.system}\n\n{contract}",
            messages=list(request.messages),
            tier=request.tier,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            meta={**request.meta, "schema": schema.__name__},
        )

        response = await self._complete_json(primed, schema)
        parsed = _try_parse(response.text, schema)
        if parsed is not None:
            return parsed, response

        # One repair round. Two would be latency we cannot spend on a hot path;
        # callers own the deterministic fallback (see agents/guard.py).
        repair = ChatRequest(
            system=primed.system,
            messages=[
                *primed.messages,
                Message("assistant", response.text[:2000]),
                Message(
                    "user",
                    "That was not valid JSON for the required schema. "
                    "Reply with the JSON object only — no prose, no code fence.",
                ),
            ],
            tier=primed.tier,
            temperature=0.0,
            max_tokens=primed.max_tokens,
            meta=primed.meta,
        )
        retry = await self._complete_json(repair, schema)
        parsed = _try_parse(retry.text, schema)
        if parsed is None:
            raise ProviderError(
                f"{self.name} could not produce valid {schema.__name__}.",
                provider=self.name,
            )
        return parsed, retry

    async def _complete_json(self, request: ChatRequest, schema: type[T]) -> ChatResponse:
        """Hook for providers with native JSON/constrained decoding."""
        return await self.complete(request)


def _schema_contract(schema: type[BaseModel]) -> str:
    return (
        "Respond with a single JSON object and nothing else. No prose, no code fence.\n"
        "It must validate against this JSON Schema:\n"
        f"{json.dumps(schema.model_json_schema(), separators=(',', ':'))}"
    )


def _try_parse(text: str, schema: type[T]) -> T | None:
    for candidate in _json_candidates(text):
        try:
            return schema.model_validate_json(candidate)
        except ValidationError:
            try:
                return schema.model_validate(json.loads(candidate))
            except (ValidationError, json.JSONDecodeError):
                continue
        except json.JSONDecodeError:
            continue
    return None


def _json_candidates(text: str) -> list[str]:
    """Extract plausible JSON payloads, most-likely first."""
    text = text.strip()
    candidates: list[str] = []
    if text.startswith(("{", "[")):
        candidates.append(text)
    candidates.extend(m.group(1) for m in _JSON_BLOCK.finditer(text))
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    return candidates


class TimedProvider(LLMProvider):
    """Mixin that stamps latency onto every response for the trace forest."""

    async def _timed(self, coro: Any) -> ChatResponse:
        started = time.perf_counter()
        response: ChatResponse = await coro
        response.latency_ms = int((time.perf_counter() - started) * 1000)
        response.provider = self.name
        return response


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "LLMProvider",
    "Message",
    "Role",
    "TimedProvider",
]
