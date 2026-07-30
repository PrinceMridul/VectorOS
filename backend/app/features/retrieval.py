"""Grounding retrieval.

Every claim the Teacher makes must be traceable to authored material. This is
not an accuracy nicety — "you cannot always trust what a chatbot tells you" is
the reason learners distrust AI tutors, and a confidently wrong explanation in
an educational product does more damage than in any other domain, because the
learner has no way to detect it.

Retrieval is scoped **to the current concept node first**, then widened to the
graph. A tutor that answers a question about gradient descent with material
about regularisation is technically retrieving and pedagogically useless.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.text import truncate
from app.db.models import ConceptNode, ContentChunk
from app.db.types import cosine_similarity
from app.llm.registry import embedder

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    id: str
    text: str
    source: str
    score: float

    def as_context(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text, "source": self.source}


async def embed_text(text: str) -> list[float]:
    vectors = await embedder().embed([text])
    return vectors[0] if vectors else []


async def retrieve(
    db: AsyncSession,
    *,
    node_id: UUID,
    graph_id: UUID,
    query: str,
    limit: int = 3,
) -> list[RetrievedChunk]:
    """Node-local chunks ranked by similarity, widened to the graph if thin."""
    local = (
        (
            await db.execute(
                select(ContentChunk)
                .where(ContentChunk.node_id == node_id)
                .order_by(ContentChunk.ordinal)
            )
        )
        .scalars()
        .all()
    )

    candidates = list(local)
    if len(candidates) < limit:
        sibling_ids = (
            (await db.execute(select(ConceptNode.id).where(ConceptNode.graph_id == graph_id)))
            .scalars()
            .all()
        )
        extra = (
            (
                await db.execute(
                    select(ContentChunk)
                    .where(ContentChunk.node_id.in_(sibling_ids))
                    .where(ContentChunk.node_id != node_id)
                    .limit(24)
                )
            )
            .scalars()
            .all()
        )
        candidates.extend(extra)

    if not candidates:
        return []

    if settings.is_postgres:
        ranked = await _rank_pgvector(db, candidates, query, node_id, limit)
        if ranked is not None:
            return ranked

    return await _rank_in_process(candidates, query, node_id, limit)


async def _rank_pgvector(
    db: AsyncSession,
    candidates: list[ContentChunk],
    query: str,
    node_id: UUID,
    limit: int,
) -> list[RetrievedChunk] | None:
    """ANN search in the database. Returns ``None`` to fall back."""
    vector = await embed_text(query)
    if not vector:
        return None
    try:
        rows = (
            (
                await db.execute(
                    select(ContentChunk)
                    .where(ContentChunk.id.in_([c.id for c in candidates]))
                    .order_by(ContentChunk.embedding.cosine_distance(vector))  # type: ignore[attr-defined]
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    except Exception as exc:  # noqa: BLE001 - e.g. embeddings not yet backfilled
        log.warning("pgvector_rank_failed", error=str(exc))
        return None

    # Node-local material always outranks graph-wide material of similar score.
    rows.sort(key=lambda c: (c.node_id != node_id, c.ordinal))
    return [
        RetrievedChunk(id=str(c.id), text=c.text, source=c.source, score=1.0) for c in rows[:limit]
    ]


async def _rank_in_process(
    candidates: list[ContentChunk], query: str, node_id: UUID, limit: int
) -> list[RetrievedChunk]:
    vector = await embed_text(query)
    scored: list[tuple[bool, float, ContentChunk]] = []
    for chunk in candidates:
        embedding = chunk.embedding or []
        score = cosine_similarity(vector, list(embedding)) if embedding and vector else 0.0
        scored.append((chunk.node_id != node_id, score, chunk))

    # Locality dominates similarity. A lexically similar chunk about a *different*
    # concept is the worst kind of retrieval result: plausible, on-topic-sounding,
    # and quietly teaching the wrong lesson. Sibling material is a last resort.
    scored.sort(key=lambda row: (row[0], -row[1], row[2].ordinal))
    return [
        RetrievedChunk(
            id=str(chunk.id),
            text=truncate(chunk.text, 900),
            source=chunk.source,
            score=round(score, 4),
        )
        for _remote, score, chunk in scored[:limit]
    ]


async def backfill_embeddings(db: AsyncSession) -> int:
    """Embed any chunk or node that does not yet have a vector."""
    chunks = (
        (await db.execute(select(ContentChunk).where(ContentChunk.embedding.is_(None))))
        .scalars()
        .all()
    )
    nodes = (
        (await db.execute(select(ConceptNode).where(ConceptNode.embedding.is_(None))))
        .scalars()
        .all()
    )

    if chunks:
        vectors = await embedder().embed([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors, strict=False):
            chunk.embedding = vector
    if nodes:
        vectors = await embedder().embed(
            [f"{n.title}. {n.one_liner} {n.canonical_model}" for n in nodes]
        )
        for node, vector in zip(nodes, vectors, strict=False):
            node.embedding = vector

    await db.flush()
    return len(chunks) + len(nodes)


__all__ = ["RetrievedChunk", "backfill_embeddings", "embed_text", "retrieve"]
