"""Goal selection — "plans a path with you".

Choosing a goal forks a template graph into a graph the learner owns. From that
moment the roadmap is theirs: nodes can be inserted when a diagnosis exposes a
missing prerequisite, and difficulty drifts per person. Sharing one global
curriculum with a progress table cannot express that, which is why this is a
clone and not a foreign key.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.errors import NotFound
from app.db.models import LearningGraph
from app.features.graph.service import clone_template

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalView(BaseModel):
    slug: str
    title: str
    description: str
    estimated_hours: float
    node_count: int
    opening_question: str


class StartGoalRequest(BaseModel):
    motivation: str = Field(
        default="",
        max_length=600,
        description="Why the learner is here, in their words. Used to frame sessions.",
    )


class StartedGoal(BaseModel):
    graph_id: str
    title: str


#: Asked before the first node opens. It is a measurement, not an icebreaker:
#: the answer seeds vocabulary tier and framing for the whole path.
_OPENING_QUESTION = "Before we plan anything — what do you already believe about {topic}?"


@router.get("", response_model=list[GoalView])
async def list_goals(db: DbSession) -> list[GoalView]:
    templates = (
        (
            await db.execute(
                select(LearningGraph)
                .where(LearningGraph.owner_id.is_(None))
                .options(selectinload(LearningGraph.nodes))
                .order_by(LearningGraph.title)
            )
        )
        .scalars()
        .all()
    )

    return [
        GoalView(
            slug=graph.slug,
            title=graph.title,
            description=graph.description,
            estimated_hours=graph.estimated_hours,
            node_count=len(graph.nodes),
            opening_question=_OPENING_QUESTION.format(topic=graph.title.lower()),
        )
        for graph in templates
    ]


@router.post("/{slug}/start", response_model=StartedGoal)
async def start_goal(
    slug: str, payload: StartGoalRequest, user: CurrentUser, db: DbSession
) -> StartedGoal:
    template = (
        await db.execute(
            select(LearningGraph)
            .where(LearningGraph.slug == slug, LearningGraph.owner_id.is_(None))
            .options(selectinload(LearningGraph.nodes), selectinload(LearningGraph.edges))
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFound("No such learning goal.", slug=slug)

    existing = (
        await db.execute(
            select(LearningGraph).where(
                LearningGraph.owner_id == user.id, LearningGraph.slug == slug
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return StartedGoal(graph_id=str(existing.id), title=existing.title)

    clone = await clone_template(
        db, template=template, user_id=user.id, goal=payload.motivation or template.goal
    )
    return StartedGoal(graph_id=str(clone.id), title=clone.title)


@router.get("/mine", response_model=list[StartedGoal])
async def my_goals(user: CurrentUser, db: DbSession) -> list[StartedGoal]:
    graphs = (
        (
            await db.execute(
                select(LearningGraph)
                .where(LearningGraph.owner_id == user.id)
                .order_by(LearningGraph.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [StartedGoal(graph_id=str(g.id), title=g.title) for g in graphs]
