"""Test fixtures.

The environment is configured *before* ``app`` is imported, because settings are
read once at import time. Each test run gets its own throwaway SQLite file and
the deterministic offline provider, so the whole suite — including the full
tutoring loop — runs with no network and no API key.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="vectoros-tests-"))
os.environ["VECTOROS_DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["VECTOROS_LLM_PROVIDER"] = "mock"
os.environ["VECTOROS_EMBEDDING_PROVIDER"] = "mock"
os.environ["VECTOROS_SECRET_KEY"] = "test-secret"

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.db.seed import seed  # noqa: E402
from app.db.session import SessionFactory, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
async def seeded() -> AsyncIterator[None]:
    await init_db()
    async with SessionFactory() as db:
        await seed(db)
        await db.commit()
    yield


@pytest.fixture
async def client(seeded: None) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def learner(client: httpx.AsyncClient) -> dict[str, str]:
    """A registered learner with the neural-networks graph started."""
    response = await client.post("/api/auth/start", json={"display_name": "Test Learner"})
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    started = await client.post(
        "/api/goals/how-neural-networks-learn/start",
        json={"motivation": "testing"},
        headers=headers,
    )
    return {"headers": headers, "graph_id": started.json()["graph_id"]}  # type: ignore[dict-item]
