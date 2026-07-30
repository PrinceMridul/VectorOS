"""Learning-graph endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.core.errors import NotFound
from app.domain.enums import EdgeKind, NodeStatus
from app.features.graph.service import NodeView, frontier, load_graph, node_statuses

router = APIRouter(prefix="/graph", tags=["graph"])


class NodeOut(BaseModel):
    id: str
    slug: str
    title: str
    one_liner: str
    difficulty: float
    bloom_ceiling: str
    status: NodeStatus
    mastery: float
    position: dict[str, float]
    blocked_by: list[str]
    review_due_at: datetime | None


class EdgeOut(BaseModel):
    id: str
    source: str
    target: str
    kind: EdgeKind


class GraphOut(BaseModel):
    id: str
    title: str
    goal: str
    description: str
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    frontier_node_id: str | None
    mastered_count: int
    total_count: int
    overall_mastery: float


def _to_node_out(view: NodeView) -> NodeOut:
    return NodeOut(
        id=str(view.node.id),
        slug=view.node.slug,
        title=view.node.title,
        one_liner=view.node.one_liner,
        difficulty=view.node.difficulty,
        bloom_ceiling=str(view.node.bloom_ceiling),
        status=view.status,
        mastery=view.mastery,
        position={"x": view.node.position_x, "y": view.node.position_y},
        blocked_by=view.blocked_by,
        review_due_at=view.review_due_at,
    )


@router.get("/{graph_id}", response_model=GraphOut)
async def get_graph(graph_id: UUID, user: CurrentUser, db: DbSession) -> GraphOut:
    graph = await load_graph(db, graph_id)
    if graph.owner_id not in (None, user.id):
        raise NotFound("Learning graph not found.", graph_id=str(graph_id))

    views = await node_statuses(db, graph=graph, user_id=user.id)
    target = frontier(views)
    mastered = sum(1 for v in views if v.status in (NodeStatus.MASTERED, NodeStatus.REVIEW_DUE))

    return GraphOut(
        id=str(graph.id),
        title=graph.title,
        goal=graph.goal,
        description=graph.description,
        nodes=[_to_node_out(v) for v in views],
        edges=[
            EdgeOut(id=str(e.id), source=str(e.source_id), target=str(e.target_id), kind=e.kind)
            for e in graph.edges
        ],
        frontier_node_id=str(target.node.id) if target else None,
        mastered_count=mastered,
        total_count=len(views),
        overall_mastery=round(sum(v.mastery for v in views) / len(views) if views else 0.0, 3),
    )
