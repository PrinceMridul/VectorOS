"""The learning graph: gating, frontier selection, and cloning.

The DAG is the product's promise made structural. A learner cannot open
*Backpropagation* before *Gradient Descent* — not because a rule says so, but
because :func:`node_statuses` computes ``LOCKED`` from the mastery of its
parents, and every endpoint that could start a session checks it.

That gating is mastery-learning: advancing with a 60%-understood prerequisite
compounds into a gap that surfaces four concepts later as "I'm just bad at this",
when in fact one specific earlier idea never landed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import NotFound, PedagogicalViolation
from app.db.models import ConceptNode, ContentChunk, LearningGraph, MasteryState, NodeEdge
from app.domain.enums import EdgeKind, NodeStatus
from app.pedagogy import bkt, schedule


@dataclass(frozen=True, slots=True)
class NodeView:
    node: ConceptNode
    status: NodeStatus
    mastery: float
    prerequisites: list[UUID]
    review_due_at: datetime | None
    blocked_by: list[str]


async def load_graph(db: AsyncSession, graph_id: UUID) -> LearningGraph:
    graph = (
        await db.execute(
            select(LearningGraph)
            .where(LearningGraph.id == graph_id)
            .options(selectinload(LearningGraph.nodes), selectinload(LearningGraph.edges))
        )
    ).scalar_one_or_none()
    if graph is None:
        raise NotFound("Learning graph not found.", graph_id=str(graph_id))
    return graph


async def mastery_map(
    db: AsyncSession, user_id: UUID, node_ids: list[UUID]
) -> dict[UUID, MasteryState]:
    if not node_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(MasteryState)
                .where(MasteryState.user_id == user_id)
                .where(MasteryState.node_id.in_(node_ids))
            )
        )
        .scalars()
        .all()
    )
    return {row.node_id: row for row in rows}


async def get_or_create_mastery(db: AsyncSession, user_id: UUID, node: ConceptNode) -> MasteryState:
    state = (
        await db.execute(
            select(MasteryState)
            .where(MasteryState.user_id == user_id)
            .where(MasteryState.node_id == node.id)
        )
    ).scalar_one_or_none()
    if state is None:
        state = MasteryState(user_id=user_id, node_id=node.id)
        db.add(state)
        await db.flush()
    return state


def apply_decay(state: MasteryState, *, now: datetime | None = None) -> float:
    """Age the estimate before it is read.

    Decay is applied lazily at read time rather than by a cron job: a mastery
    value is only ever *observed* in a request, and a nightly sweep over every
    learner × every KC is a lot of infrastructure to compute something an
    exponential can give exactly on demand.
    """
    now = now or datetime.now(UTC)
    anchor = state.decay_applied_at or state.last_interaction_at
    decayed = bkt.decay(state.p_mastery, anchor, now=now)
    if abs(decayed - state.p_mastery) > 1e-4:
        state.p_mastery = decayed
        state.decay_applied_at = now
    return state.p_mastery


def _status_for(
    node: ConceptNode,
    state: MasteryState | None,
    prerequisite_ids: list[UUID],
    mastery: dict[UUID, MasteryState],
    now: datetime,
) -> tuple[NodeStatus, list[str]]:
    blocked = [
        str(pid)
        for pid in prerequisite_ids
        if (mastery.get(pid).p_mastery if mastery.get(pid) else 0.0) < settings.mastery_threshold
    ]
    if blocked:
        return NodeStatus.LOCKED, blocked

    if state is None or state.observations == 0:
        return NodeStatus.AVAILABLE, []

    if state.p_mastery >= settings.mastery_threshold:
        due = state.review_due_at
        if due is not None:
            due = due if due.tzinfo else due.replace(tzinfo=UTC)
            if due <= now:
                return NodeStatus.REVIEW_DUE, []
        return NodeStatus.MASTERED, []

    return NodeStatus.IN_PROGRESS, []


async def node_statuses(db: AsyncSession, *, graph: LearningGraph, user_id: UUID) -> list[NodeView]:
    now = datetime.now(UTC)
    node_ids = [n.id for n in graph.nodes]
    mastery = await mastery_map(db, user_id, node_ids)
    for state in mastery.values():
        apply_decay(state, now=now)

    prerequisites: dict[UUID, list[UUID]] = defaultdict(list)
    for edge in graph.edges:
        if edge.kind == EdgeKind.PREREQUISITE:
            prerequisites[edge.target_id].append(edge.source_id)

    views: list[NodeView] = []
    for node in graph.nodes:
        state = mastery.get(node.id)
        status, blocked = _status_for(node, state, prerequisites[node.id], mastery, now)
        views.append(
            NodeView(
                node=node,
                status=status,
                mastery=round(state.p_mastery, 3) if state else 0.0,
                prerequisites=prerequisites[node.id],
                review_due_at=state.review_due_at if state else None,
                blocked_by=blocked,
            )
        )
    return views


def frontier(views: list[NodeView]) -> NodeView | None:
    """The single node the learner should work on next.

    Priority order is a pedagogical statement:

    1. **Overdue review** — retaining what you have beats acquiring more. A
       curriculum that only ever moves forward quietly leaks everything behind it.
    2. **Unfinished work** — closing an open concept beats opening another.
    3. **The next available node**, easiest first, so momentum is preserved.
    """
    due = [v for v in views if v.status is NodeStatus.REVIEW_DUE]
    if due:
        return max(
            due,
            key=lambda v: schedule.urgency(mastery=v.mastery, due_at=v.review_due_at),
        )

    in_progress = [v for v in views if v.status is NodeStatus.IN_PROGRESS]
    if in_progress:
        return max(in_progress, key=lambda v: v.mastery)

    available = [v for v in views if v.status is NodeStatus.AVAILABLE]
    if available:
        return min(available, key=lambda v: (v.node.difficulty, v.node.order_index))

    return None


def ensure_unlocked(view: NodeView) -> None:
    if view.status is NodeStatus.LOCKED:
        raise PedagogicalViolation(
            "This concept is still locked — its prerequisites are not yet mastered.",
            node_id=str(view.node.id),
            blocked_by=view.blocked_by,
        )


async def clone_template(
    db: AsyncSession, *, template: LearningGraph, user_id: UUID, goal: str
) -> LearningGraph:
    """Fork a template graph for a learner.

    Each learner owns their own graph rather than sharing a global curriculum,
    because the roadmap is going to diverge: nodes get inserted when a diagnosis
    reveals a missing prerequisite, and difficulty drifts per person. A shared
    curriculum with a per-user progress table cannot represent that.
    """
    clone = LearningGraph(
        owner_id=user_id,
        slug=template.slug,
        title=template.title,
        goal=goal or template.goal,
        description=template.description,
        estimated_hours=template.estimated_hours,
    )
    db.add(clone)
    await db.flush()

    id_map: dict[UUID, UUID] = {}
    for node in template.nodes:
        copy = ConceptNode(
            graph_id=clone.id,
            slug=node.slug,
            title=node.title,
            one_liner=node.one_liner,
            canonical_model=node.canonical_model,
            misconception_bank=list(node.misconception_bank or []),
            probe_seeds=list(node.probe_seeds or []),
            challenge_seeds=list(node.challenge_seeds or []),
            difficulty=node.difficulty,
            bloom_ceiling=node.bloom_ceiling,
            order_index=node.order_index,
            position_x=node.position_x,
            position_y=node.position_y,
            embedding=node.embedding,
        )
        db.add(copy)
        await db.flush()
        id_map[node.id] = copy.id

        chunks = (
            (
                await db.execute(
                    select(ContentChunk)
                    .where(ContentChunk.node_id == node.id)
                    .order_by(ContentChunk.ordinal)
                )
            )
            .scalars()
            .all()
        )
        for chunk in chunks:
            db.add(
                ContentChunk(
                    node_id=copy.id,
                    ordinal=chunk.ordinal,
                    source=chunk.source,
                    text=chunk.text,
                    embedding=chunk.embedding,
                )
            )

    for edge in template.edges:
        db.add(
            NodeEdge(
                graph_id=clone.id,
                source_id=id_map[edge.source_id],
                target_id=id_map[edge.target_id],
                kind=edge.kind,
            )
        )

    await db.flush()
    return clone


__all__ = [
    "NodeView",
    "apply_decay",
    "clone_template",
    "ensure_unlocked",
    "frontier",
    "get_or_create_mastery",
    "load_graph",
    "mastery_map",
    "node_statuses",
]
