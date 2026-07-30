"""Tutoring endpoints.

One verb does the work: ``POST /sessions/{id}/turn``. There is deliberately no
``/explain``, no ``/hint`` and no ``/answer`` — endpoints shape behaviour, and an
endpoint named ``/answer`` would eventually be called.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.db.models import AgentEvent
from app.features.session import schemas, service

router = APIRouter(prefix="/sessions", tags=["sessions"])


class UnlockRequest(BaseModel):
    proof: str = Field(max_length=1000)


@router.post("", response_model=schemas.SessionView)
async def start(
    payload: schemas.StartSessionRequest, user: CurrentUser, db: DbSession
) -> schemas.SessionView:
    session, node = await service.start_session(db, user=user, node_id=UUID(payload.node_id))
    from app.features.graph.service import apply_decay, get_or_create_mastery

    mastery = await get_or_create_mastery(db, user.id, node)
    apply_decay(mastery)
    return await service.build_session_view(db, session=session, node=node, mastery=mastery)


@router.get("/{session_id}", response_model=schemas.SessionView)
async def get(session_id: UUID, user: CurrentUser, db: DbSession) -> schemas.SessionView:
    return await service.get_session_view(db, user=user, session_id=session_id)


@router.post("/{session_id}/turn", response_model=schemas.TurnResponse)
async def turn(
    session_id: UUID, payload: schemas.TurnRequest, user: CurrentUser, db: DbSession
) -> schemas.TurnResponse:
    return await service.take_turn(db, user=user, session_id=session_id, request=payload)


@router.post("/{session_id}/unlock", response_model=schemas.SessionView)
async def unlock(
    session_id: UUID, payload: UnlockRequest, user: CurrentUser, db: DbSession
) -> schemas.SessionView:
    """Re-open free text after the anti-offload circuit tripped."""
    await service.unlock_input(db, user=user, session_id=session_id, proof=payload.proof)
    return await service.get_session_view(db, user=user, session_id=session_id)


@router.get("/{session_id}/shift", response_model=schemas.UnderstandingShift)
async def shift(session_id: UUID, user: CurrentUser, db: DbSession) -> schemas.UnderstandingShift:
    """The Understanding Shift.

    What the learner believed before any instruction, beside what they could
    rebuild from memory afterwards — in both cases their own words, recovered
    from the ledger rather than generated. Only a system that asks before it
    answers has a "before" to show.
    """
    return await service.understanding_shift(db, user=user, session_id=session_id)


@router.get("/{session_id}/trace", response_model=list[schemas.TraceEventView])
async def trace(session_id: UUID, user: CurrentUser, db: DbSession) -> list[schemas.TraceEventView]:
    """The trace forest for one session.

    Exposed deliberately. A system that claims someone has mastered something
    owes them the evidence — which agent ran, on which model, what the guard
    decided, and every state transition that produced the number.
    """
    events = (
        (
            await db.execute(
                select(AgentEvent)
                .where(AgentEvent.session_id == session_id, AgentEvent.user_id == user.id)
                .order_by(AgentEvent.created_at)
            )
        )
        .scalars()
        .all()
    )

    return [
        schemas.TraceEventView(
            agent=str(e.agent),
            model=e.model,
            state_from=str(e.state_from) if e.state_from else None,
            state_to=str(e.state_to) if e.state_to else None,
            latency_ms=e.latency_ms,
            tokens_in=e.tokens_in,
            tokens_out=e.tokens_out,
            guard_verdict=str(e.guard_verdict) if e.guard_verdict else None,
            created_at=e.created_at.isoformat(),
            payload=e.payload or {},
        )
        for e in events
    ]
