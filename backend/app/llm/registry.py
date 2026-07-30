"""Provider registry and capability-tier routing.

Agents call ``llm().structured(request, Schema)`` and never learn which vendor
answered. Two knobs live here:

* **tier → model**, so cost/latency can be tuned per agent without code changes;
* **chat provider ≠ embedding provider**, because the best reasoning model and
  the best embedding model are frequently not from the same vendor (Anthropic
  ships no embeddings at all).
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider

log = get_logger(__name__)


def _model_map() -> dict[str, str]:
    return {
        "fast": settings.model_fast,
        "balanced": settings.model_balanced,
        "deep": settings.model_deep,
    }


def _build(kind: str) -> LLMProvider:
    models = _model_map()
    if kind == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider(models)
    if kind == "openai":
        from app.llm.openai import OpenAIProvider

        return OpenAIProvider(models)
    if kind == "anthropic":
        from app.llm.anthropic import AnthropicProvider

        return AnthropicProvider(models)
    return MockProvider()


@lru_cache(maxsize=1)
def llm() -> LLMProvider:
    provider = _build(settings.llm_provider)
    log.info("llm_provider_ready", provider=provider.name, **_model_map())
    return provider


@lru_cache(maxsize=1)
def embedder() -> LLMProvider:
    """Embeddings may come from a different vendor than chat."""
    if settings.embedding_provider == settings.llm_provider:
        return llm()
    provider = _build(settings.embedding_provider)
    log.info("embedding_provider_ready", provider=provider.name, model=settings.embedding_model)
    return provider


def reset_providers() -> None:
    """Test seam — drop the cached singletons after mutating settings."""
    llm.cache_clear()
    embedder.cache_clear()


__all__ = ["embedder", "llm", "reset_providers"]
