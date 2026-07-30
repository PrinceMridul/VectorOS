"""Shared HTTP plumbing for network providers.

We talk to vendor REST APIs directly rather than pulling in three SDKs. Each SDK
brings its own auth model, retry policy, telemetry and transitive dependency
tree, and we would still need this abstraction on top. One shared client with
one retry policy is less code and far more predictable latency — which matters,
because tutoring latency is a pedagogical constraint, not just an ops metric.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger

log = get_logger(__name__)

_client: httpx.AsyncClient | None = None

#: Transient by definition — retrying anything else just burns the learner's time.
_RETRYABLE = {408, 429, 500, 502, 503, 504}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def post_json(
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    provider: str,
) -> dict[str, Any]:
    last_error: str = ""
    for attempt in range(settings.llm_max_retries + 1):
        try:
            response = await client().post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            last_error = str(exc)
        else:
            if response.status_code < 400:
                return response.json()
            last_error = f"{response.status_code}: {response.text[:400]}"
            if response.status_code not in _RETRYABLE:
                break

        if attempt < settings.llm_max_retries:
            await asyncio.sleep(0.4 * (2**attempt))

    log.error("provider_request_failed", provider=provider, error=last_error)
    raise ProviderError(f"{provider} request failed.", provider=provider, detail=last_error)


def require_key(provider: str) -> str:
    key = settings.api_key_for(provider)
    if not key:
        raise ProviderError(
            f"No API key configured for '{provider}'. "
            "Set the key, or run with VECTOROS_LLM_PROVIDER=mock.",
            provider=provider,
        )
    return key


__all__ = ["client", "close_client", "post_json", "require_key"]
