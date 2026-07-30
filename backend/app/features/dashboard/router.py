"""Progress dashboard.

Not a chart wall. Four numbers, each of which should change what the learner
does next:

* **Mastery** — probabilistic and decaying, so progress reads as something you
  hold rather than something you collected.
* **Calibration** — how well their confidence predicts their correctness. Most
  learners have never seen this measured about themselves, and it is the single
  most actionable thing here.
* **Blind spots** — wrong while certain. Ranked first because they are invisible
  to the learner by definition.
* **Cognitive debt** — how much of the progress was actually theirs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.db.models import (
    Attempt,
    ConceptNode,
    LearningGraph,
    LearningSession,
    MasteryState,
    Misconception,
)
from app.domain.enums import MetacognitiveQuadrant, MisconceptionStatus
from app.features.graph.service import apply_decay
from app.pedagogy import schedule
from app.pedagogy.calibration import CalibrationSummary, cognitive_debt

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ConceptProgress(BaseModel):
    node_id: str
    title: str
    graph_title: str
    mastery: float
    observations: int
    unaided: int
    review_due_at: datetime | None
    overdue_days: float


class QuadrantCounts(BaseModel):
    automaticity: int = 0
    fragile: int = 0
    blind_spot: int = 0
    known_gap: int = 0


class WeaknessView(BaseModel):
    claim: str
    canonical: str
    severity: str
    node_title: str
    evidence_count: int
    status: str


class DashboardView(BaseModel):
    display_name: str
    concepts: list[ConceptProgress]
    review_queue: list[ConceptProgress]
    quadrants: QuadrantCounts
    calibration_label: str
    calibration_error: float
    calibration_samples: int
    cognitive_debt: float
    cognitive_debt_label: str
    cognitive_debt_headline: str
    unaided_wins: int
    hinted_wins: int
    offload_attempts: int
    sessions_completed: int
    active_weaknesses: list[WeaknessView]
    resolved_weaknesses: int
    recent_summaries: list[dict] = Field(default_factory=list)


@router.get("", response_model=DashboardView)
async def dashboard(user: CurrentUser, db: DbSession) -> DashboardView:
    profile = user.profile
    assert profile is not None
    now = datetime.now(UTC)

    rows = (
        await db.execute(
            select(MasteryState, ConceptNode, LearningGraph)
            .join(ConceptNode, ConceptNode.id == MasteryState.node_id)
            .join(LearningGraph, LearningGraph.id == ConceptNode.graph_id)
            .where(MasteryState.user_id == user.id)
        )
    ).all()

    concepts: list[ConceptProgress] = []
    for state, node, graph in rows:
        apply_decay(state, now=now)
        due = state.review_due_at
        overdue = 0.0
        if due is not None:
            due = due if due.tzinfo else due.replace(tzinfo=UTC)
            overdue = max(0.0, (now - due).total_seconds() / 86_400.0)
        concepts.append(
            ConceptProgress(
                node_id=str(node.id),
                title=node.title,
                graph_title=graph.title,
                mastery=round(state.p_mastery, 3),
                observations=state.observations,
                unaided=state.unaided_observations,
                review_due_at=state.review_due_at,
                overdue_days=round(overdue, 2),
            )
        )

    concepts.sort(key=lambda c: -c.mastery)

    # Interleaved, urgency-ranked: never three questions on one concept in a row.
    queue_items = [
        schedule.ReviewItem(
            node_id=c.node_id,
            due_at=c.review_due_at or now,
            mastery=c.mastery,
            urgency=schedule.urgency(mastery=c.mastery, due_at=c.review_due_at, now=now),
        )
        for c in concepts
        if c.overdue_days > 0
    ]
    ordered = schedule.build_review_queue(queue_items, limit=6)
    by_id = {c.node_id: c for c in concepts}
    review_queue = [by_id[key] for item in ordered if (key := str(item.node_id)) in by_id]

    quadrant_rows = (
        await db.execute(
            select(Attempt.quadrant, func.count())
            .where(Attempt.user_id == user.id, Attempt.quadrant.is_not(None))
            .group_by(Attempt.quadrant)
        )
    ).all()
    counts = QuadrantCounts()
    for quadrant, count in quadrant_rows:
        if quadrant == MetacognitiveQuadrant.AUTOMATICITY:
            counts.automaticity = count
        elif quadrant == MetacognitiveQuadrant.FRAGILE:
            counts.fragile = count
        elif quadrant == MetacognitiveQuadrant.BLIND_SPOT:
            counts.blind_spot = count
        elif quadrant == MetacognitiveQuadrant.KNOWN_GAP:
            counts.known_gap = count

    weaknesses = (
        await db.execute(
            select(Misconception, ConceptNode)
            .join(ConceptNode, ConceptNode.id == Misconception.node_id)
            .where(Misconception.user_id == user.id)
            .order_by(Misconception.status, Misconception.evidence_count.desc())
        )
    ).all()
    active = [
        WeaknessView(
            claim=m.claim,
            canonical=m.canonical,
            severity=str(m.severity),
            node_title=node.title,
            evidence_count=m.evidence_count,
            status=str(m.status),
        )
        for m, node in weaknesses
        if m.status == MisconceptionStatus.ACTIVE
    ]
    resolved = sum(1 for m, _ in weaknesses if m.status == MisconceptionStatus.RESOLVED)

    completed = (
        await db.execute(
            select(func.count())
            .select_from(LearningSession)
            .where(LearningSession.user_id == user.id, LearningSession.ended_at.is_not(None))
        )
    ).scalar_one()

    debt = cognitive_debt(
        unaided_wins=profile.unaided_wins,
        hinted_wins=profile.hinted_wins,
        hints_consumed=profile.hints_consumed,
        offload_attempts=profile.offload_attempts,
    )
    mean_error = (
        profile.calibration_error_sum / profile.calibration_samples
        if profile.calibration_samples
        else 0.0
    )
    summary = CalibrationSummary(
        samples=profile.calibration_samples,
        mean_error=round(mean_error, 3),
        overconfidence=round(
            (counts.blind_spot - counts.fragile) / max(profile.calibration_samples, 1), 3
        ),
        blind_spots=counts.blind_spot,
    )

    return DashboardView(
        display_name=user.display_name,
        concepts=concepts,
        review_queue=review_queue,
        quadrants=counts,
        calibration_label=summary.label,
        calibration_error=summary.mean_error,
        calibration_samples=summary.samples,
        cognitive_debt=debt.score,
        cognitive_debt_label=debt.label,
        cognitive_debt_headline=debt.headline,
        unaided_wins=profile.unaided_wins,
        hinted_wins=profile.hinted_wins,
        offload_attempts=profile.offload_attempts,
        sessions_completed=completed,
        active_weaknesses=active[:10],
        resolved_weaknesses=resolved,
        recent_summaries=(profile.session_summaries or [])[-6:],
    )
