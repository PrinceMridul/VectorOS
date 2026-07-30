"""Create the schema and load the template curricula.

Idempotent: re-running updates authored content in place rather than
duplicating graphs, so editing a misconception bank and re-seeding is a normal
part of the authoring loop.

Run with ``python -m app.db.seed``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import configure_logging, get_logger
from app.db.models import ConceptNode, ContentChunk, LearningGraph, NodeEdge
from app.db.seed_data import CURRICULA
from app.db.session import SessionFactory, init_db
from app.domain.enums import BloomLevel, EdgeKind
from app.features.retrieval import backfill_embeddings

log = get_logger(__name__)

#: React Flow canvas spacing. Layered left-to-right so prerequisite direction is
#: legible at a glance — the graph should read as a path, not a constellation.
_COLUMN_GAP = 300.0
_ROW_GAP = 190.0


async def _upsert_graph(db: AsyncSession, spec: dict[str, Any]) -> LearningGraph:
    graph = (
        await db.execute(
            select(LearningGraph)
            .where(LearningGraph.slug == spec["slug"], LearningGraph.owner_id.is_(None))
            .options(selectinload(LearningGraph.nodes), selectinload(LearningGraph.edges))
        )
    ).scalar_one_or_none()

    if graph is None:
        graph = LearningGraph(slug=spec["slug"], owner_id=None)
        db.add(graph)

    graph.title = spec["title"]
    graph.goal = spec["goal"]
    graph.description = spec["description"]
    graph.estimated_hours = spec["estimated_hours"]
    await db.flush()
    return graph


async def _upsert_node(
    db: AsyncSession, graph: LearningGraph, spec: dict[str, Any], order: int
) -> ConceptNode:
    node = (
        await db.execute(
            select(ConceptNode).where(
                ConceptNode.graph_id == graph.id, ConceptNode.slug == spec["slug"]
            )
        )
    ).scalar_one_or_none()

    if node is None:
        node = ConceptNode(graph_id=graph.id, slug=spec["slug"])
        db.add(node)

    column, row = spec["position"]
    node.title = spec["title"]
    node.one_liner = spec["one_liner"]
    node.canonical_model = spec["canonical_model"]
    node.misconception_bank = spec["misconception_bank"]
    node.probe_seeds = spec["probe_seeds"]
    node.challenge_seeds = spec["challenge_seeds"]
    node.difficulty = spec["difficulty"]
    node.bloom_ceiling = BloomLevel(spec["bloom_ceiling"])
    node.order_index = order
    node.position_x = column * _COLUMN_GAP
    node.position_y = row * _ROW_GAP
    node.embedding = None  # re-embed after content edits
    await db.flush()

    existing = (
        (await db.execute(select(ContentChunk).where(ContentChunk.node_id == node.id)))
        .scalars()
        .all()
    )
    for chunk in existing:
        await db.delete(chunk)

    for ordinal, text in enumerate(spec["chunks"]):
        db.add(
            ContentChunk(
                node_id=node.id,
                ordinal=ordinal,
                source=f"VectorOS Core Curriculum · {spec['title']}",
                text=text,
            )
        )
    return node


async def seed(db: AsyncSession) -> None:
    for spec in CURRICULA:
        graph = await _upsert_graph(db, spec)
        nodes: dict[str, ConceptNode] = {}
        for order, node_spec in enumerate(spec["nodes"]):
            nodes[node_spec["slug"]] = await _upsert_node(db, graph, node_spec, order)

        existing_edges = (
            (await db.execute(select(NodeEdge).where(NodeEdge.graph_id == graph.id)))
            .scalars()
            .all()
        )
        for edge in existing_edges:
            await db.delete(edge)
        await db.flush()

        for source, target in spec["edges"]:
            db.add(
                NodeEdge(
                    graph_id=graph.id,
                    source_id=nodes[source].id,
                    target_id=nodes[target].id,
                    kind=EdgeKind.PREREQUISITE,
                )
            )

        log.info("seeded_graph", slug=spec["slug"], nodes=len(nodes), edges=len(spec["edges"]))

    await db.flush()
    embedded = await backfill_embeddings(db)
    log.info("embeddings_backfilled", count=embedded)


async def main() -> None:
    configure_logging()
    await init_db()
    async with SessionFactory() as db:
        await seed(db)
        await db.commit()
    log.info("seed_complete", curricula=len(CURRICULA))


if __name__ == "__main__":
    asyncio.run(main())
