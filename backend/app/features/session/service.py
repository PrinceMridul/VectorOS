"""The tutoring orchestrator.

This is the control plane made concrete. Read the flow of :func:`take_turn` as
the answer to "what actually stops this from becoming a chatbot":

* the **plan** for a turn is derived from the persisted session state, not from
  what the learner asked for;
* the agent mesh may only *downgrade* that plan to a refusal;
* mastery is written by :mod:`app.pedagogy.bkt` from graded evidence, never by a
  model asserting that someone understands something;
* every transition is checked against the legal edge set and recorded.

Everything the LLM produces passes through here before it reaches a database or
a learner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import memory as memory_agent
from app.agents.graph import run_turn
from app.agents.state import TurnState
from app.core.config import settings
from app.core.errors import NotFound, PedagogicalViolation
from app.core.logging import get_logger
from app.core.text import truncate
from app.db.models import (
    AgentEvent,
    Attempt,
    ConceptNode,
    Diagnosis,
    LearnerProfile,
    LearningSession,
    MasteryState,
    Misconception,
    Reflection,
    User,
)
from app.domain.enums import (
    AgentName,
    AttemptKind,
    BloomLevel,
    Intent,
    MetacognitiveQuadrant,
    MisconceptionStatus,
    NodeStatus,
    SessionState,
    Severity,
)
from app.features import retrieval
from app.features.graph import service as graph_service
from app.features.session import schemas
from app.pedagogy import bkt, calibration, load, scaffold, schedule, state_machine, zpd

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────────────────────


async def _load_session(
    db: AsyncSession, user: User, session_id: UUID, *, for_update: bool = False
) -> LearningSession:
    """Load a session, optionally taking a row lock.

    Two turns arriving together for the same session would otherwise both read
    the same state and both transition from it — double-grading one attempt, or
    advancing the state machine twice. The client guards against this, but a
    client guard is not a guarantee: a double-tap, a retried request or a second
    tab is enough. SQLite serialises writers so it does not need the lock;
    Postgres does, so mutating paths take ``FOR UPDATE``.
    """
    query = select(LearningSession).where(
        LearningSession.id == session_id, LearningSession.user_id == user.id
    )
    if for_update and settings.is_postgres:
        query = query.with_for_update()

    session = (await db.execute(query)).scalar_one_or_none()
    if session is None:
        raise NotFound("Session not found.", session_id=str(session_id))
    return session


async def _load_node(db: AsyncSession, node_id: UUID) -> ConceptNode:
    node = (
        await db.execute(select(ConceptNode).where(ConceptNode.id == node_id))
    ).scalar_one_or_none()
    if node is None:
        raise NotFound("Concept not found.", node_id=str(node_id))
    return node


async def _active_misconceptions(
    db: AsyncSession, user_id: UUID, node_id: UUID
) -> list[Misconception]:
    return list(
        (
            await db.execute(
                select(Misconception)
                .where(Misconception.user_id == user_id)
                .where(Misconception.node_id == node_id)
                .where(Misconception.status == MisconceptionStatus.ACTIVE)
                .order_by(Misconception.evidence_count.desc())
            )
        )
        .scalars()
        .all()
    )


def _node_context(node: ConceptNode) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "title": node.title,
        "one_liner": node.one_liner,
        "canonical_model": node.canonical_model,
        "misconception_bank": node.misconception_bank or [],
        "probe_seeds": node.probe_seeds or [],
        "challenge_seeds": node.challenge_seeds or [],
        "difficulty": node.difficulty,
        "bloom_ceiling": str(node.bloom_ceiling),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Starting a session
# ─────────────────────────────────────────────────────────────────────────────


def elicitation_prompt(node: ConceptNode, *, revisiting: bool) -> str:
    """The Prior-Belief Gate, in words.

    Two variants, because asking a returning learner "what do you already
    believe?" would be odd — for them the same gate is retrieval practice, which
    is the highest-yield thing they could be doing at the start of a session
    anyway.
    """
    if revisiting:
        return (
            f"Back to **{node.title}**. Before we touch anything: from memory, "
            "with nothing in front of you — what is it, and why does it work?\n\n"
            "Retrieving it cold is worth more than re-reading it ten times."
        )
    return (
        f"We're going to work on **{node.title}**.\n\n"
        "Before I explain anything: in your own words, what do you already "
        "believe this is?\n\n"
        "Guess if you have to. A wrong guess tells me more about how to teach "
        "you than a blank page does, and I would rather find out now than after "
        "an explanation that missed you."
    )


async def start_session(
    db: AsyncSession, *, user: User, node_id: UUID
) -> tuple[LearningSession, ConceptNode]:
    node = await _load_node(db, node_id)
    graph = await graph_service.load_graph(db, node.graph_id)
    if graph.owner_id not in (None, user.id):
        raise NotFound("Concept not found.", node_id=str(node_id))

    views = await graph_service.node_statuses(db, graph=graph, user_id=user.id)
    view = next(v for v in views if v.node.id == node.id)
    graph_service.ensure_unlocked(view)

    existing = (
        (
            await db.execute(
                select(LearningSession)
                .where(LearningSession.user_id == user.id, LearningSession.node_id == node.id)
                .where(LearningSession.state != SessionState.COMPLETE)
                .order_by(LearningSession.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing, node

    mastery = await graph_service.get_or_create_mastery(db, user.id, node)
    graph_service.apply_decay(mastery)

    session = LearningSession(
        user_id=user.id,
        graph_id=graph.id,
        node_id=node.id,
        state=SessionState.IDLE,
        goal=graph.goal,
        mastery_before=mastery.p_mastery,
    )
    db.add(session)
    await db.flush()

    move = state_machine.transition(
        SessionState.IDLE, SessionState.ELICIT, trigger="session_started"
    )
    session.state = move.target
    session.pending_message = elicitation_prompt(node, revisiting=mastery.prior_belief_captured)
    _record_transition(db, session, move, agent=AgentName.PLANNER)

    await db.flush()
    return session, node


def _record_transition(
    db: AsyncSession,
    session: LearningSession,
    move: state_machine.Transition,
    *,
    agent: AgentName,
) -> None:
    db.add(
        AgentEvent(
            session_id=session.id,
            user_id=session.user_id,
            agent=agent,
            model="deterministic",
            state_from=move.source,
            state_to=move.target,
            payload={"trigger": move.trigger, **{k: str(v) for k, v in move.notes.items()}},
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# The turn
# ─────────────────────────────────────────────────────────────────────────────


def _plan_for(session: LearningSession, request: schemas.TurnRequest) -> str:
    """Map the persisted state to what the agent mesh is allowed to do.

    The learner's message does not appear in this decision. That is the entire
    point: what happens next is a function of where they are in the learning
    process, not of how persuasively they asked.
    """
    if session.state is SessionState.ELICIT:
        return "elicit"
    if session.state is SessionState.REFLECT:
        return "reflect"
    if session.state in (SessionState.CHALLENGE, SessionState.ATTEMPT, SessionState.COACH):
        return "coach" if request.request_guidance else "evaluate"
    return "noop"


#: States in which an attempt is being graded, so confidence must be committed.
_CONFIDENCE_REQUIRED = frozenset({SessionState.CHALLENGE, SessionState.ATTEMPT, SessionState.COACH})

#: States a learner can legitimately submit into. Everything else is transient.
_ACCEPTS_INPUT = _CONFIDENCE_REQUIRED | {SessionState.ELICIT, SessionState.REFLECT}


def _validate(session: LearningSession, request: schemas.TurnRequest) -> None:
    if session.state is SessionState.COMPLETE:
        raise PedagogicalViolation("This session is already complete.")

    # The transient states (DIAGNOSE, INSTRUCT, EVALUATE, MASTERY) only exist
    # inside a single request. Seeing one persisted means a turn died mid-flight,
    # and silently no-op'ing would leave the learner typing into a void.
    if session.state not in _ACCEPTS_INPUT:
        raise PedagogicalViolation(
            "This session is mid-step. Reload to pick up where you left off.",
            state=str(session.state),
        )

    if request.request_guidance:
        if session.state not in state_machine.GUIDANCE_AVAILABLE:
            raise PedagogicalViolation(
                "There is nothing to be stuck on yet — answer the question in front of you.",
                state=str(session.state),
            )
        elapsed = 0.0
        if session.challenge_issued_at is not None:
            issued = session.challenge_issued_at
            issued = issued if issued.tzinfo else issued.replace(tzinfo=UTC)
            elapsed = (datetime.now(UTC) - issued).total_seconds()
        attempted = session.turn_count > 0 and session.scaffold_level > 0

        if not state_machine.guidance_unlocked(
            elapsed_seconds=max(elapsed, request.elapsed_ms / 1000.0),
            struggle_floor=settings.struggle_floor_seconds,
            attempted=attempted,
        ):
            raise PedagogicalViolation(
                "Sit with it a little longer — guidance unlocks shortly. "
                "The struggle is doing something.",
                unlocks_in_seconds=int(max(0, settings.struggle_floor_seconds - elapsed)),
            )
        return

    if not request.text.strip():
        raise PedagogicalViolation("Write something first — even a wrong guess is data.")

    # Confidence is committed *before* the answer is graded, which is what makes
    # it an honest metacognitive signal rather than hindsight.
    if request.confidence is None and session.state in _CONFIDENCE_REQUIRED:
        raise PedagogicalViolation(
            "Commit to how confident you are before submitting.",
            required="confidence",
        )


async def _build_turn_state(
    db: AsyncSession,
    *,
    session: LearningSession,
    node: ConceptNode,
    profile: LearnerProfile,
    mastery: MasteryState,
    request: schemas.TurnRequest,
    plan: str,
) -> TurnState:
    query = request.text or node.title
    chunks = await retrieval.retrieve(
        db, node_id=node.id, graph_id=session.graph_id, query=query, limit=3
    )
    active = await _active_misconceptions(db, session.user_id, node.id)

    params = _params(mastery)
    reading = _load_reading(session, node, mastery, latency_ms=request.elapsed_ms)
    target = zpd.select_target(
        mastery=mastery.p_mastery,
        params=params,
        node_difficulty=node.difficulty,
        bloom_ceiling=BloomLevel(str(node.bloom_ceiling)),
        load=reading,
        first_challenge=session.challenge_prompt is None,
    )

    challenge: dict[str, Any] = dict(session.challenge_meta or {})
    if session.challenge_prompt:
        challenge["prompt"] = session.challenge_prompt

    return TurnState(
        phase=str(session.state),
        learner_input=request.text,
        node=_node_context(node),
        chunks=[c.as_context() for c in chunks],
        profile={
            "vocabulary_tier": profile.vocabulary_tier,
            "offload_attempts": session.offload_attempts,
        },
        mastery=mastery.p_mastery,
        scaffold_level=session.scaffold_level,
        difficulty=target.difficulty,
        bloom=str(target.bloom),
        target_success=target.predicted_success,
        active_misconceptions=[m.claim for m in active],
        diagnosis=dict(session.mental_model or {}),
        challenge=challenge,
        expecting="reflection" if plan == "reflect" else "attempt",
        load_band=reading.band,
        events=[],
    )


def _params(mastery: MasteryState) -> bkt.BKTParams:
    return bkt.BKTParams(
        prior=mastery.p_mastery,
        learn=mastery.p_learn,
        guess=mastery.p_guess,
        slip=mastery.p_slip,
        forget=mastery.p_forget,
    )


def _recent_accuracy(mastery: MasteryState) -> float:
    if mastery.observations == 0:
        return 0.5
    return mastery.correct_observations / mastery.observations


def _load_reading(
    session: LearningSession,
    node: ConceptNode,
    mastery: MasteryState,
    *,
    latency_ms: int = 0,
) -> load.LoadReading:
    """Single source of truth for the cognitive-load heuristic (not the Paas
    instrument — see app.pedagogy.load for why that distinction matters).

    This was computed inline in three places — turn setup, grading, and view
    building — which is exactly the shape of bug that ships: someone adds a term
    to the formula in two of them and the number the learner sees stops matching
    the number the tutor acted on.
    """
    return load.cognitive_load(
        load.LoadSignals(
            difficulty=session.challenge_difficulty,
            recent_accuracy=_recent_accuracy(mastery),
            turn_count=session.turn_count,
            bloom=BloomLevel(str(node.bloom_ceiling)),
            latency_ms=latency_ms,
            consecutive_failures=session.consecutive_failures,
        )
    )


async def take_turn(
    db: AsyncSession, *, user: User, session_id: UUID, request: schemas.TurnRequest
) -> schemas.TurnResponse:
    session = await _load_session(db, user, session_id, for_update=True)
    node = await _load_node(db, session.node_id)
    profile = user.profile
    assert profile is not None

    mastery = await graph_service.get_or_create_mastery(db, user.id, node)
    graph_service.apply_decay(mastery)

    _validate(session, request)
    plan = _plan_for(session, request)

    # Snapshot the frontier so the client can celebrate what *this turn* opened,
    # rather than everything that happens to be reachable.
    unlocked_before = await _unlocked_ids(db, user=user, graph_id=session.graph_id)

    turn_state = await _build_turn_state(
        db,
        session=session,
        node=node,
        profile=profile,
        mastery=mastery,
        request=request,
        plan=plan,
    )
    result = await run_turn(turn_state, plan=plan)

    transitions: list[state_machine.Transition] = []
    mastery_before = mastery.p_mastery
    refused = False
    evaluation_view: schemas.EvaluationView | None = None
    reflection_view: schemas.ReflectionView | None = None

    intent = (result.get("intent") or {}).get("intent")
    if intent == Intent.ANSWER_DEMAND.value:
        refused = True
        await _handle_refusal(db, session=session, profile=profile, result=result)
    elif plan == "elicit":
        transitions += await _handle_elicit(
            db,
            session=session,
            node=node,
            profile=profile,
            mastery=mastery,
            result=result,
            request=request,
        )
    elif plan == "evaluate":
        transitions, evaluation_view = await _handle_evaluate(
            db,
            session=session,
            node=node,
            profile=profile,
            mastery=mastery,
            result=result,
            request=request,
        )
    elif plan == "coach":
        transitions += _handle_coach(db, session=session, result=result, mastery=mastery)
    elif plan == "reflect":
        transitions, reflection_view = await _handle_reflect(
            db,
            session=session,
            node=node,
            profile=profile,
            mastery=mastery,
            result=result,
            request=request,
        )

    session.turn_count += 1
    _persist_events(db, session=session, result=result)

    await db.flush()
    unlocked = sorted(
        await _unlocked_ids(db, user=user, graph_id=session.graph_id) - unlocked_before
    )

    view = await build_session_view(
        db,
        session=session,
        node=node,
        mastery=mastery,
        evaluation=evaluation_view,
        reflection=reflection_view,
    )

    return schemas.TurnResponse(
        session=view,
        transitions=[
            schemas.TransitionView(source=t.source, target=t.target, trigger=t.trigger)
            for t in transitions
        ],
        mastery_delta=round(mastery.p_mastery - mastery_before, 4),
        unlocked_nodes=unlocked,
        guard_verdict=result.get("guard_verdict"),
        refused=refused,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handlers — one per plan
# ─────────────────────────────────────────────────────────────────────────────


async def _handle_refusal(
    db: AsyncSession, *, session: LearningSession, profile: LearnerProfile, result: dict[str, Any]
) -> None:
    """Refusal & Pivot, plus the anti-offload circuit.

    The state does **not** advance. Asking for the answer is not progress
    through the material, and letting it move the session would teach exactly
    the behaviour we are trying to extinguish.
    """
    session.offload_attempts += 1
    await _apply_delta(db, session=session, profile=profile, delta=memory_agent.from_refusal())

    if session.offload_attempts >= settings.offload_lock_threshold:
        session.input_locked = True
        log.info(
            "offload_circuit_tripped",
            session_id=str(session.id),
            attempts=session.offload_attempts,
        )

    session.pending_message = result.get("message") or session.pending_message


async def _handle_elicit(
    db: AsyncSession,
    *,
    session: LearningSession,
    node: ConceptNode,
    profile: LearnerProfile,
    mastery: MasteryState,
    result: dict[str, Any],
    request: schemas.TurnRequest,
) -> list[state_machine.Transition]:
    """Prior belief → diagnosis → calibrated instruction → first challenge."""
    diagnosis = result.get("new_diagnosis") or {}

    attempt = Attempt(
        session_id=session.id,
        user_id=session.user_id,
        node_id=node.id,
        kind=AttemptKind.PRIOR_BELIEF,
        prompt=session.pending_message,
        response=request.text,
        latency_ms=request.elapsed_ms,
        scaffold_level=0,
    )
    db.add(attempt)
    await db.flush()

    db.add(
        Diagnosis(
            attempt_id=attempt.id,
            prior_estimate=diagnosis.get("prior_estimate", 0.15),
            anchors=diagnosis.get("anchors", []),
            misconceptions=diagnosis.get("misconceptions", []),
            missing=diagnosis.get("missing", []),
            bloom_reached=BloomLevel(diagnosis.get("bloom_reached", "remember")),
            vocabulary_tier=diagnosis.get("vocabulary_tier", 2),
            reasoning=diagnosis.get("reasoning", ""),
        )
    )

    # The elicitation is a *measurement*: it seeds the prior. This is the
    # difference between personalisation and a personalised-sounding greeting.
    if not mastery.prior_belief_captured:
        seeded = bkt.seed_prior(_params(mastery), diagnosis.get("prior_estimate", 0.15))
        mastery.p_mastery = seeded.prior
        mastery.prior_belief_captured = True

    # The learner is about to receive a full calibrated explanation. That is the
    # learning opportunity, so this is where the BKT transition belongs.
    mastery.p_mastery = bkt.apply_instruction(mastery.p_mastery, _params(mastery), intensity=1.0)
    mastery.last_interaction_at = datetime.now(UTC)

    await _apply_delta(
        db, session=session, profile=profile, delta=memory_agent.from_diagnosis(diagnosis)
    )

    session.mental_model = diagnosis
    challenge = result.get("new_challenge") or {}
    session.challenge_prompt = challenge.get("prompt")
    session.challenge_meta = {
        "acceptance_criteria": challenge.get("acceptance_criteria", []),
        "expected_reasoning": challenge.get("expected_reasoning", ""),
        "bloom": challenge.get("bloom", "apply"),
    }
    session.challenge_issued_at = datetime.now(UTC)
    session.scaffold_level = scaffold.reset_for_new_challenge()
    session.pending_message = result.get("message", "")
    # A new challenge invalidates the previous verdict; leaving it on screen
    # would attach last question's diagnosis to this question.
    session.last_evaluation = {}
    session.last_reflection = {}

    moves = [
        state_machine.transition(
            SessionState.ELICIT, SessionState.DIAGNOSE, trigger="prior_belief_captured"
        ),
        state_machine.transition(
            SessionState.DIAGNOSE, SessionState.INSTRUCT, trigger="diagnosis_complete"
        ),
        state_machine.transition(
            SessionState.INSTRUCT, SessionState.CHALLENGE, trigger="instruction_delivered"
        ),
    ]
    for move in moves:
        _record_transition(db, session, move, agent=AgentName.PLANNER)
    session.state = moves[-1].target
    return moves


async def _handle_evaluate(
    db: AsyncSession,
    *,
    session: LearningSession,
    node: ConceptNode,
    profile: LearnerProfile,
    mastery: MasteryState,
    result: dict[str, Any],
    request: schemas.TurnRequest,
) -> tuple[list[state_machine.Transition], schemas.EvaluationView]:
    evaluation = result.get("evaluation") or {}
    correctness = float(evaluation.get("correctness", 0.0))
    passed = correctness >= settings.challenge_pass_threshold
    confidence = request.confidence.value_float if request.confidence else None
    quadrant = calibration.classify(correctness, confidence)

    moves = [
        state_machine.transition(session.state, SessionState.ATTEMPT, trigger="attempt_submitted"),
        state_machine.transition(SessionState.ATTEMPT, SessionState.EVALUATE, trigger="grading"),
    ]

    attempt = Attempt(
        session_id=session.id,
        user_id=session.user_id,
        node_id=node.id,
        kind=AttemptKind.CHALLENGE,
        prompt=session.challenge_prompt or "",
        response=request.text,
        correctness=correctness,
        confidence=confidence,
        quadrant=quadrant,
        latency_ms=request.elapsed_ms,
        scaffold_level=session.scaffold_level,
        hint_used=session.scaffold_level > 0,
    )
    db.add(attempt)

    # ── The knowledge tracer ────────────────────────────────────────────────
    trace = bkt.update(
        mastery.p_mastery,
        _params(mastery),
        bkt.Evidence(
            correctness=correctness,
            confidence=confidence,
            scaffold_level=session.scaffold_level,
            latency_ms=request.elapsed_ms,
        ),
    )
    mastery.p_mastery = trace.p_mastery
    mastery.observations += 1
    mastery.correct_observations += 1 if passed else 0
    mastery.unaided_observations += 1 if passed and session.scaffold_level == 0 else 0
    mastery.last_interaction_at = datetime.now(UTC)
    mastery.decay_applied_at = mastery.last_interaction_at

    plan = schedule.plan_review(
        mastery=mastery.p_mastery,
        previous_interval_days=mastery.review_interval_days,
        ease=mastery.review_ease,
        was_correct=passed,
        quadrant_is_blind_spot=quadrant is MetacognitiveQuadrant.BLIND_SPOT,
    )
    mastery.review_due_at = plan.due_at
    mastery.review_interval_days = plan.interval_days
    mastery.review_ease = plan.ease

    session.consecutive_failures = 0 if correctness >= 0.5 else session.consecutive_failures + 1
    session.cognitive_load = _load_reading(
        session, node, mastery, latency_ms=request.elapsed_ms
    ).value

    await _apply_delta(
        db,
        session=session,
        profile=profile,
        delta=memory_agent.from_attempt(
            evaluation=evaluation,
            quadrant=quadrant,
            scaffold_level=session.scaffold_level,
            calibration_error=calibration.calibration_error(correctness, confidence),
        ),
    )

    target_state, trigger = state_machine.next_after_evaluation(
        correctness=correctness,
        scaffold_level=session.scaffold_level,
        max_scaffold=settings.max_scaffold_level,
        consecutive_failures=session.consecutive_failures,
    )
    move = state_machine.transition(SessionState.EVALUATE, target_state, trigger=trigger)
    moves.append(move)
    session.state = move.target

    message = result.get("message", "")
    if target_state is SessionState.REFLECT:
        message = _reflection_prompt(node, message)
    session.pending_message = message

    for m in moves:
        _record_transition(db, session, m, agent=AgentName.EXAMINER)

    view = schemas.EvaluationView(
        correctness=round(correctness, 3),
        quadrant=quadrant,
        quadrant_note=calibration.RESPONSE_STRATEGY[quadrant],
        error_type=evaluation.get("error_type", "none"),
        anchors=evaluation.get("anchors", []),
        misconceptions=evaluation.get("misconceptions", []),
    )
    session.last_evaluation = view.model_dump(mode="json")
    return moves, view


def _reflection_prompt(node: ConceptNode, prefix: str) -> str:
    ask = (
        f"Now close everything. From memory only — explain **{node.title}** as if "
        "to someone who has never met it, and say why it works.\n\n"
        "This is the part that decides whether it stuck. Getting the answer right "
        "and being able to rebuild the idea are not the same skill."
    )
    return f"{prefix}\n\n{ask}".strip() if prefix else ask


def _handle_coach(
    db: AsyncSession,
    *,
    session: LearningSession,
    result: dict[str, Any],
    mastery: MasteryState,
) -> list[state_machine.Transition]:
    """Escalate the ladder by exactly one rung."""
    session.scaffold_level = scaffold.escalate(
        current=session.scaffold_level,
        learner_replied=True,
        mastery=mastery.p_mastery,
    )
    session.pending_message = result.get("message", "")

    # A coaching move is a smaller learning opportunity than full instruction,
    # and a higher rung hands over more, so it counts for more. This is also why
    # correctness produced at a high rung is discounted in `bkt.effective_params`
    # — the estimate goes up either way, but scaffolded evidence is weaker.
    mastery.p_mastery = bkt.apply_instruction(
        mastery.p_mastery,
        _params(mastery),
        intensity=0.2 * session.scaffold_level,
    )
    mastery.last_interaction_at = datetime.now(UTC)

    move = state_machine.transition(session.state, SessionState.COACH, trigger="guidance_requested")
    session.state = move.target
    _record_transition(db, session, move, agent=AgentName.COACH)
    return [move]


async def _handle_reflect(
    db: AsyncSession,
    *,
    session: LearningSession,
    node: ConceptNode,
    profile: LearnerProfile,
    mastery: MasteryState,
    result: dict[str, Any],
    request: schemas.TurnRequest,
) -> tuple[list[state_machine.Transition], schemas.ReflectionView]:
    """The Metacognitive Gate, and mastery commit."""
    score = result.get("reflection") or {}
    coverage = float(score.get("coverage", 0.0))
    passed = coverage >= settings.reflection_pass_threshold

    db.add(
        Reflection(
            session_id=session.id,
            user_id=session.user_id,
            node_id=node.id,
            text=request.text,
            coverage=coverage,
            omissions=score.get("omissions", []),
            passed=passed,
            feedback=score.get("feedback", ""),
        )
    )
    db.add(
        Attempt(
            session_id=session.id,
            user_id=session.user_id,
            node_id=node.id,
            kind=AttemptKind.REFLECTION,
            prompt="free recall",
            response=request.text,
            correctness=coverage,
            latency_ms=request.elapsed_ms,
            scaffold_level=session.scaffold_level,
        )
    )

    # Free recall is evidence too — weaker than a graded challenge (it is
    # self-directed), so it enters the tracer at reduced scaffold weight.
    trace = bkt.update(
        mastery.p_mastery,
        _params(mastery),
        bkt.Evidence(correctness=coverage, confidence=None, scaffold_level=0),
    )
    mastery.p_mastery = trace.p_mastery
    mastery.last_interaction_at = datetime.now(UTC)

    # A passed recall is a *second, independent* piece of evidence against every
    # belief still open on this node: the learner has just rebuilt the correct
    # model unaided and from memory, without restating the wrong one. Combined
    # with a correct application earlier in the session, that meets the
    # two-clears bar in `memory.CLEARS_TO_RESOLVE`. Without this the loop never
    # closes — the only thing that could ever clear a gap was another graded
    # attempt, so a learner who understood it perfectly stayed flagged.
    if passed:
        await _apply_delta(
            db,
            session=session,
            profile=profile,
            delta=memory_agent.ProfileDelta(
                misconceptions=[
                    memory_agent.MisconceptionDelta(claim=m.claim, observed=False)
                    for m in await _active_misconceptions(db, session.user_id, node.id)
                ]
            ),
        )

    target_state, trigger = state_machine.next_after_reflection(passed=passed, coverage=coverage)
    moves = [state_machine.transition(SessionState.REFLECT, target_state, trigger=trigger)]
    session.state = target_state

    message = result.get("message", "")

    if target_state is SessionState.MASTERY:
        if mastery.p_mastery >= settings.mastery_threshold and mastery.mastered_at is None:
            mastery.mastered_at = datetime.now(UTC)
        close = state_machine.transition(
            SessionState.MASTERY, SessionState.COMPLETE, trigger="node_closed"
        )
        moves.append(close)
        session.state = close.target
        session.ended_at = datetime.now(UTC)
        session.mastery_after = mastery.p_mastery
        # Count what actually happened across the whole session, not just what
        # the opening elicitation caught. The resolved count was hardcoded to 0,
        # so the tutor's own memory of the session under-reported the learner
        # every time — the one number here that is pure good news.
        touched = list(
            (
                await db.execute(
                    select(Misconception)
                    .where(Misconception.user_id == session.user_id)
                    .where(Misconception.node_id == node.id)
                    .where(Misconception.last_seen_at >= session.created_at)
                )
            )
            .scalars()
            .all()
        )
        session.summary = memory_agent.consolidate_session(
            node_title=node.title,
            mastery_before=session.mastery_before,
            mastery_after=mastery.p_mastery,
            attempts=session.turn_count,
            misconceptions_opened=len(touched),
            misconceptions_resolved=sum(
                1 for m in touched if m.status is MisconceptionStatus.RESOLVED
            ),
            reflection_passed=True,
        )
        await _apply_delta(
            db,
            session=session,
            profile=profile,
            delta=memory_agent.ProfileDelta(session_summary=session.summary),
        )
        message = f"{message}\n\n{_closing_message(node, mastery.p_mastery)}".strip()

    session.pending_message = message
    for move in moves:
        _record_transition(db, session, move, agent=AgentName.REFLECTION)

    view = schemas.ReflectionView(
        coverage=round(coverage, 3),
        omissions=score.get("omissions", []),
        passed=passed,
        feedback=score.get("feedback", ""),
    )
    session.last_reflection = view.model_dump(mode="json")
    return moves, view


def _closing_message(node: ConceptNode, mastery: float) -> str:
    return (
        f"**{node.title}** is at {mastery:.0%} — and that number will drift down "
        "if you leave it alone, which is why it comes back on your review queue "
        "rather than getting a permanent tick."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Memory write-back
# ─────────────────────────────────────────────────────────────────────────────


async def _apply_delta(
    db: AsyncSession,
    *,
    session: LearningSession,
    profile: LearnerProfile,
    delta: memory_agent.ProfileDelta,
) -> None:
    """Apply the Memory agent's decision to the longitudinal model."""
    if delta.empty:
        return

    profile.unaided_wins += int(delta.unaided_win)
    profile.hinted_wins += int(delta.hinted_win)
    profile.hints_consumed += delta.hints_consumed
    profile.offload_attempts += int(delta.offload_attempt)

    if delta.calibration_error is not None:
        profile.calibration_samples += 1
        profile.calibration_error_sum += delta.calibration_error

    if delta.vocabulary_tier is not None:
        profile.vocabulary_tier = delta.vocabulary_tier

    if delta.pedagogy_note:
        notes = dict(profile.pedagogy_notes or {})
        observations = list(notes.get("observations", []))
        observations.append(delta.pedagogy_note)
        notes["observations"] = observations[-24:]
        profile.pedagogy_notes = notes

    if delta.session_summary:
        summaries = list(profile.session_summaries or [])
        summaries.append({"at": datetime.now(UTC).isoformat(), "summary": delta.session_summary})
        profile.session_summaries = summaries[-40:]

    for item in delta.misconceptions:
        await _upsert_misconception(db, session=session, item=item)


async def _upsert_misconception(
    db: AsyncSession, *, session: LearningSession, item: memory_agent.MisconceptionDelta
) -> None:
    """Open, reinforce or close an entry in the weakness index.

    Closing requires two consecutive clears — see
    :data:`app.agents.memory.CLEARS_TO_RESOLVE` for why one is not enough.
    """
    if not item.claim.strip():
        return

    existing = (
        await db.execute(
            select(Misconception)
            .where(Misconception.user_id == session.user_id)
            .where(Misconception.node_id == session.node_id)
            .where(Misconception.claim == item.claim)
        )
    ).scalar_one_or_none()

    if existing is None:
        if not item.observed:
            return
        db.add(
            Misconception(
                user_id=session.user_id,
                node_id=session.node_id,
                claim=item.claim,
                canonical=item.canonical,
                severity=item.severity or Severity.MEDIUM,
            )
        )
        return

    if item.observed:
        existing.evidence_count += 1
        existing.consecutive_clears = 0
        existing.status = MisconceptionStatus.ACTIVE
        existing.resolved_at = None
        existing.last_seen_at = datetime.now(UTC)
    else:
        existing.consecutive_clears += 1
        if existing.consecutive_clears >= memory_agent.CLEARS_TO_RESOLVE:
            existing.status = MisconceptionStatus.RESOLVED
            existing.resolved_at = datetime.now(UTC)


def _persist_events(db: AsyncSession, *, session: LearningSession, result: dict[str, Any]) -> None:
    """Level-3 trace: every agent call, with its guard verdict."""
    for event in result.get("events", []):
        db.add(
            AgentEvent(
                session_id=session.id,
                user_id=session.user_id,
                agent=AgentName(event.get("agent", "memory")),
                model=event.get("model", ""),
                payload=event.get("payload", {}),
                latency_ms=event.get("latency_ms", 0),
                tokens_in=event.get("tokens_in", 0),
                tokens_out=event.get("tokens_out", 0),
                guard_verdict=event.get("guard_verdict"),
            )
        )


async def _unlocked_ids(db: AsyncSession, *, user: User, graph_id: UUID) -> set[str]:
    graph = await graph_service.load_graph(db, graph_id)
    views = await graph_service.node_statuses(db, graph=graph, user_id=user.id)
    return {str(v.node.id) for v in views if v.status is not NodeStatus.LOCKED}


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────


async def build_session_view(
    db: AsyncSession,
    *,
    session: LearningSession,
    node: ConceptNode,
    mastery: MasteryState,
    evaluation: schemas.EvaluationView | None = None,
    reflection: schemas.ReflectionView | None = None,
) -> schemas.SessionView:
    elapsed = 0.0
    if session.challenge_issued_at is not None:
        issued = session.challenge_issued_at
        issued = issued if issued.tzinfo else issued.replace(tzinfo=UTC)
        elapsed = (datetime.now(UTC) - issued).total_seconds()

    reading = _load_reading(session, node, mastery)

    model = session.mental_model or {}
    # Fall back to the persisted snapshots so a reload resumes with the same
    # diagnosis on screen, not just the same prompt.
    if evaluation is None and session.last_evaluation:
        evaluation = schemas.EvaluationView.model_validate(session.last_evaluation)
    if reflection is None and session.last_reflection:
        reflection = schemas.ReflectionView.model_validate(session.last_reflection)

    return schemas.SessionView(
        id=str(session.id),
        graph_id=str(session.graph_id),
        node_id=str(node.id),
        node_title=node.title,
        node_one_liner=node.one_liner,
        state=session.state,
        message=session.pending_message,
        challenge_prompt=session.challenge_prompt,
        scaffold_level=session.scaffold_level,
        max_scaffold_level=settings.max_scaffold_level,
        requires_confidence=session.state
        in (SessionState.CHALLENGE, SessionState.ATTEMPT, SessionState.COACH),
        guidance_available=state_machine.guidance_unlocked(
            elapsed_seconds=elapsed,
            struggle_floor=settings.struggle_floor_seconds,
            attempted=session.scaffold_level > 0,
        )
        and session.state in state_machine.GUIDANCE_AVAILABLE,
        struggle_floor_seconds=settings.struggle_floor_seconds,
        mastery=round(mastery.p_mastery, 3),
        mastery_before=round(session.mastery_before, 3),
        predicted_success=round(bkt.predict_correct(mastery.p_mastery, _params(mastery)), 3),
        cognitive_load=reading.value,
        load_band=reading.band,
        turn_count=session.turn_count,
        offload_attempts=session.offload_attempts,
        input_locked=session.input_locked,
        mental_model=(
            schemas.MentalModelView(
                anchors=model.get("anchors", []),
                misconceptions=model.get("misconceptions", []),
                missing=model.get("missing", []),
                prior_estimate=model.get("prior_estimate", 0.0),
                bloom_reached=model.get("bloom_reached", "remember"),
            )
            if model
            else None
        ),
        last_evaluation=evaluation,
        reflection=reflection,
        completed=session.state is SessionState.COMPLETE,
    )


async def get_session_view(
    db: AsyncSession, *, user: User, session_id: UUID
) -> schemas.SessionView:
    session = await _load_session(db, user, session_id)
    node = await _load_node(db, session.node_id)
    mastery = await graph_service.get_or_create_mastery(db, user.id, node)
    graph_service.apply_decay(mastery)
    return await build_session_view(db, session=session, node=node, mastery=mastery)


async def understanding_shift(
    db: AsyncSession, *, user: User, session_id: UUID
) -> schemas.UnderstandingShift:
    """Assemble the closing moment of a concept.

    Everything here is recovered from the ledger — the learner's own prior-belief
    text, their own recall text, the misconceptions the Examiner named, and which
    of those they cleared. Nothing is generated, so nothing can be embellished.
    """
    session = await _load_session(db, user, session_id)
    node = await _load_node(db, session.node_id)

    attempts = list(
        (
            await db.execute(
                select(Attempt).where(Attempt.session_id == session.id).order_by(Attempt.created_at)
            )
        )
        .scalars()
        .all()
    )

    before = next((a for a in attempts if a.kind is AttemptKind.PRIOR_BELIEF), None)
    reflection = (
        (
            await db.execute(
                select(Reflection)
                .where(Reflection.session_id == session.id)
                .order_by(Reflection.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    if before is None or reflection is None:
        raise PedagogicalViolation(
            "This concept has no before-and-after yet — the shift appears once you "
            "have cleared the recall gate.",
            session_id=str(session.id),
        )

    # Every belief this session touched, not only the ones the opening
    # elicitation caught: a misconception surfaced by a failed attempt halfway
    # through is exactly the kind of thing the learner should see themselves
    # having dislodged.
    touched = list(
        (
            await db.execute(
                select(Misconception)
                .where(Misconception.user_id == user.id, Misconception.node_id == node.id)
                .where(Misconception.last_seen_at >= session.created_at)
                .order_by(Misconception.severity.desc(), Misconception.created_at)
            )
        )
        .scalars()
        .all()
    )
    beliefs = [
        schemas.ResolvedBelief(
            claim=m.claim,
            canonical=m.canonical,
            severity=str(m.severity),
            resolved=m.status is MisconceptionStatus.RESOLVED,
            clears=m.consecutive_clears,
            clears_required=memory_agent.CLEARS_TO_RESOLVE,
        )
        for m in touched
    ]

    challenges = [a for a in attempts if a.kind is AttemptKind.CHALLENGE]
    ended = session.ended_at or datetime.now(UTC)
    started = session.created_at
    minutes = max((ended - started).total_seconds() / 60.0, 0.0)

    graph = await graph_service.load_graph(db, session.graph_id)
    views = await graph_service.node_statuses(db, graph=graph, user_id=user.id)
    unlocked = [
        v.node.title
        for v in views
        if v.status is NodeStatus.AVAILABLE and v.node.id != node.id and v.mastery == 0.0
    ]

    return schemas.UnderstandingShift(
        node_title=node.title,
        node_one_liner=node.one_liner,
        before_text=before.response,
        before_at=before.created_at.isoformat(),
        after_text=reflection.text,
        after_at=reflection.created_at.isoformat(),
        beliefs=beliefs,
        anchors_at_start=(session.mental_model or {}).get("anchors", []),
        mastery_before=round(session.mastery_before, 3),
        mastery_after=round(session.mastery_after or session.mastery_before, 3),
        prior_estimate=round((session.mental_model or {}).get("prior_estimate", 0.0), 3),
        attempts=len(challenges),
        unaided_wins=sum(
            1
            for a in challenges
            if (a.correctness or 0) >= settings.challenge_pass_threshold and a.scaffold_level == 0
        ),
        hints_used=max((a.scaffold_level for a in challenges), default=0),
        answer_demands_refused=session.offload_attempts,
        minutes_elapsed=round(minutes, 1),
        reflection_coverage=round(reflection.coverage, 3),
        unlocked_titles=unlocked[:4],
    )


async def unlock_input(db: AsyncSession, *, user: User, session_id: UUID, proof: str) -> bool:
    """Re-open free text after the learner proves cognitive engagement.

    The anti-offload circuit does not punish; it *redirects*. To get the keyboard
    back the learner must produce thought — here, naming a concrete part of the
    problem. It is a low bar on purpose: the goal is to interrupt the demand
    reflex, not to lock anyone out of their own session.
    """
    session = await _load_session(db, user, session_id, for_update=True)
    if len(proof.split()) < 4:
        raise PedagogicalViolation(
            "Name one specific part of the problem you understand, in a sentence."
        )
    session.input_locked = False
    session.offload_attempts = 0
    db.add(
        AgentEvent(
            session_id=session.id,
            user_id=user.id,
            agent=AgentName.MEMORY,
            model="deterministic",
            payload={"kind": "engagement_proof", "text": truncate(proof, 300)},
        )
    )
    return True


__all__ = [
    "build_session_view",
    "elicitation_prompt",
    "get_session_view",
    "start_session",
    "take_turn",
    "understanding_shift",
    "unlock_input",
]
