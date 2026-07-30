"""Portable column types.

VectorOS must run two ways with the same code:

* ``sqlite+aiosqlite`` — a laptop, zero infrastructure, so a new engineer or an
  investor demo is one command away.
* ``postgresql+asyncpg`` with **pgvector** — production / Supabase, where ANN
  search over content chunks is done in the database.

Rather than fork the models, embeddings and JSON documents are declared once
with dialect variants.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine

from app.core.config import settings


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware timestamps on every backend.

    SQLite has no timestamp type and hands back naive datetimes, so the same code
    that computes a forgetting curve correctly on Postgres silently compares
    aware to naive and raises — or worse, is patched with a ``replace(tzinfo=UTC)``
    at each of a dozen call sites, one of which will eventually be missed.
    Normalising in the mapper means every ``datetime`` in the domain is aware, and
    the decay maths has one fewer way to be wrong.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


#: JSON everywhere, JSONB (indexable, binary) on Postgres.
JSONDoc: TypeEngine[Any] = JSON().with_variant(JSONB(), "postgresql")


def enum_column(enum_cls: type[Enum]) -> SAEnum:
    """Store an enum as its *value*, and load it back as the enum.

    Declaring these as bare ``String`` columns is a trap that bit us: a value
    round-trips as ``str``, so ``session.state is SessionState.ELICIT`` silently
    becomes false after a reload and the state machine stops matching. Since the
    control plane is built on identity comparisons against these enums, the
    coercion has to happen in the mapper.

    ``native_enum=False`` keeps this portable — a VARCHAR plus a CHECK constraint
    on both SQLite and Postgres — so adding a state does not require a Postgres
    ``ALTER TYPE`` migration.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
    )


def embedding_type() -> TypeEngine[Any]:
    """``vector(dim)`` on Postgres, a JSON float array elsewhere."""
    base: TypeEngine[Any] = JSON()
    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:  # pragma: no cover - pgvector is an optional runtime dep
        return base
    return base.with_variant(Vector(settings.embedding_dim), "postgresql")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """In-process fallback for the SQLite path.

    Postgres uses the ``<=>`` operator with an ivfflat/hnsw index instead; this
    exists so the pedagogy is testable without infrastructure.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
