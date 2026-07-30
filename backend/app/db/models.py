"""The persistent learner model.

Read this file as a pedagogical argument, not just a schema. Three ideas drive
every table:

1. **A learner is longitudinal.** Nothing here is session-scoped only; mastery,
   misconceptions and calibration accumulate across months.
2. **Every mastery claim must be auditable.** ``attempts`` stores confidence,
   latency and the scaffold level in force, so we can always answer "how much of
   this was theirs?"
3. **The expert model is data, not prompt text.** ``canonical_model`` and
   ``misconception_bank`` let the Examiner *classify* rather than free-associate,
   and let the guard detect answer leakage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.types import JSONDoc, UTCDateTime, embedding_type, enum_column
from app.domain.enums import (
    AgentName,
    AttemptKind,
    BloomLevel,
    EdgeKind,
    GuardVerdict,
    MetacognitiveQuadrant,
    MisconceptionStatus,
    SessionState,
    Severity,
)


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampedUUIDModel(Base):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class User(TimestampedUUIDModel):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, default=None)
    display_name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    profile: Mapped[LearnerProfile] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class LearnerProfile(TimestampedUUIDModel):
    """The 3D learner profile: history, weaknesses, pedagogy notes.

    Weaknesses live in their own table (``misconceptions``) because they need a
    lifecycle. What remains here is the part of the model that is about *how*
    this person learns rather than *what* they know - the notes a great human
    tutor would keep in the margin.
    """

    __tablename__ = "learner_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    vocabulary_tier: Mapped[int] = mapped_column(Integer, default=2)
    """1 concrete/plain, 2 standard, 3 technical. Drives the Teacher's register."""

    pedagogy_notes: Mapped[dict[str, Any]] = mapped_column(JSONDoc, default=dict)
    """D_r - which analogies, framings and pacing worked *for this person*."""

    session_summaries: Mapped[list[dict[str, Any]]] = mapped_column(JSONDoc, default=list)
    """D_s - consolidated session history. Raw turns are deliberately forgotten."""

    # -- Cognitive-debt ledger (learner-visible KPI) -------------------------
    unaided_wins: Mapped[int] = mapped_column(Integer, default=0)
    hinted_wins: Mapped[int] = mapped_column(Integer, default=0)
    hints_consumed: Mapped[int] = mapped_column(Integer, default=0)
    offload_attempts: Mapped[int] = mapped_column(Integer, default=0)

    # -- Calibration ledger (metacognitive accuracy) -------------------------
    calibration_samples: Mapped[int] = mapped_column(Integer, default=0)
    calibration_error_sum: Mapped[float] = mapped_column(Float, default=0.0)
    """Sum of |confidence - correctness|. Its mean is the learner's calibration error."""

    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="profile")


# ---------------------------------------------------------------------------
# Curriculum - a DAG, never a linear course
# ---------------------------------------------------------------------------


class LearningGraph(TimestampedUUIDModel):
    __tablename__ = "learning_graphs"

    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, default=None
    )
    """NULL means a template graph, cloneable by any learner."""

    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text)
    """The learner's own words for why they are here. Used in Planner framing."""
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_hours: Mapped[float] = mapped_column(Float, default=6.0)

    nodes: Mapped[list[ConceptNode]] = relationship(
        back_populates="graph", cascade="all, delete-orphan", order_by="ConceptNode.order_index"
    )
    edges: Mapped[list[NodeEdge]] = relationship(
        back_populates="graph", cascade="all, delete-orphan"
    )


class ConceptNode(TimestampedUUIDModel):
    """A Knowledge Component."""

    __tablename__ = "concept_nodes"
    __table_args__ = (UniqueConstraint("graph_id", "slug", name="uq_node_slug_per_graph"),)

    graph_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_graphs.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    one_liner: Mapped[str] = mapped_column(Text)
    """Shown on the graph. Deliberately not an explanation - a *label*."""

    canonical_model: Mapped[str] = mapped_column(Text)
    """The expert mental model. Never sent to the learner verbatim: it is the
    grading key for Reflection and the leak target for SocraticGuard."""

    misconception_bank: Mapped[list[dict[str, Any]]] = mapped_column(JSONDoc, default=list)
    """[{claim, canonical, severity, triggers}] - empirically common wrong models."""

    probe_seeds: Mapped[list[str]] = mapped_column(JSONDoc, default=list)
    """Deterministic Socratic fallbacks, used when the guard rejects a draft twice."""

    challenge_seeds: Mapped[list[str]] = mapped_column(JSONDoc, default=list)
    """Authored tasks ordered easiest to hardest. The ZPD selector indexes into
    these when generation is unavailable, so the tutor degrades to *a good
    human-written challenge* rather than to nothing."""

    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    """0..1 intrinsic load. Feeds both ZPD selection and the cognitive-load
    heuristic (see app.pedagogy.load — not the validated Paas instrument)."""

    bloom_ceiling: Mapped[BloomLevel] = mapped_column(
        enum_column(BloomLevel), default=BloomLevel.APPLY
    )
    """Highest cognitive level this node may assess. Prevents 'create' tasks on
    a concept the learner has only just met."""

    order_index: Mapped[int] = mapped_column(Integer, default=0)
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)

    embedding: Mapped[list[float] | None] = mapped_column(embedding_type(), default=None)

    graph: Mapped[LearningGraph] = relationship(back_populates="nodes")
    chunks: Mapped[list[ContentChunk]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class NodeEdge(TimestampedUUIDModel):
    __tablename__ = "node_edges"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "kind", name="uq_edge"),
        Index("ix_edge_target", "target_id"),
    )

    graph_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_graphs.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID] = mapped_column(ForeignKey("concept_nodes.id", ondelete="CASCADE"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("concept_nodes.id", ondelete="CASCADE"))
    kind: Mapped[EdgeKind] = mapped_column(enum_column(EdgeKind), default=EdgeKind.PREREQUISITE)

    graph: Mapped[LearningGraph] = relationship(back_populates="edges")


class ContentChunk(TimestampedUUIDModel):
    """Grounding material for the Teacher. Citations are non-negotiable: a tutor
    that cannot say where a claim came from is not trustworthy."""

    __tablename__ = "content_chunks"

    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(200), default="VectorOS Core Curriculum")
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(embedding_type(), default=None)

    node: Mapped[ConceptNode] = relationship(back_populates="chunks")


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


class MasteryState(TimestampedUUIDModel):
    """Output of the knowledge tracer. Per-learner, per-KC, and *perishable*."""

    __tablename__ = "mastery_states"
    __table_args__ = (UniqueConstraint("user_id", "node_id", name="uq_mastery_user_node"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True
    )

    p_mastery: Mapped[float] = mapped_column(Float, default=0.15)

    # Per-learner BKT parameters. Stored (not global constants) because slip and
    # guess are properties of a *person on a concept*, not of the concept.
    p_learn: Mapped[float] = mapped_column(Float, default=0.30)
    p_guess: Mapped[float] = mapped_column(Float, default=0.20)
    p_slip: Mapped[float] = mapped_column(Float, default=0.10)
    p_forget: Mapped[float] = mapped_column(Float, default=0.05)

    observations: Mapped[int] = mapped_column(Integer, default=0)
    correct_observations: Mapped[int] = mapped_column(Integer, default=0)
    unaided_observations: Mapped[int] = mapped_column(Integer, default=0)
    """Correct answers produced at scaffold level 0. The only fully honest evidence."""

    prior_belief_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    """Has this learner passed the Prior-Belief Gate for this node?"""

    last_interaction_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    decay_applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    mastered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    review_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    review_interval_days: Mapped[float] = mapped_column(Float, default=1.0)
    review_ease: Mapped[float] = mapped_column(Float, default=2.3)


class LearningSession(TimestampedUUIDModel):
    __tablename__ = "learning_sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    graph_id: Mapped[UUID] = mapped_column(ForeignKey("learning_graphs.id", ondelete="CASCADE"))
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True
    )

    state: Mapped[SessionState] = mapped_column(
        enum_column(SessionState), default=SessionState.IDLE
    )
    goal: Mapped[str] = mapped_column(Text, default="")

    scaffold_level: Mapped[int] = mapped_column(Integer, default=0)
    """Monotonically non-decreasing within a challenge; reset when a new challenge issues."""

    offload_attempts: Mapped[int] = mapped_column(Integer, default=0)
    input_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    """Set when the anti-offload circuit trips. The client swaps to a structured task."""

    cognitive_load: Mapped[float] = mapped_column(Float, default=3.0)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    challenge_prompt: Mapped[str | None] = mapped_column(Text, default=None)
    challenge_issued_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    challenge_difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    challenge_meta: Mapped[dict[str, Any]] = mapped_column(JSONDoc, default=dict)
    """Private grading key for the active challenge: acceptance criteria and
    expected reasoning. Never serialised to the client - the guard checks
    generated text against it, and the API would leak it in a network tab."""

    mental_model: Mapped[dict[str, Any]] = mapped_column(JSONDoc, default=dict)
    """Latest diagnosis snapshot, so every subsequent turn stays calibrated to it."""

    pending_message: Mapped[str] = mapped_column(Text, default="")
    """The tutor's current message, so a refresh or a second device resumes
    exactly where the learner was. Sessions must survive leaving the tab."""

    last_evaluation: Mapped[dict[str, Any]] = mapped_column(JSONDoc, default=dict)
    """Client-safe view of the last graded attempt (correctness, quadrant, the
    misconceptions surfaced). Persisted rather than returned once, so closing
    the laptop does not erase the diagnosis — 'it remembers you' has to survive
    a page reload before it can survive a fortnight."""

    last_reflection: Mapped[dict[str, Any]] = mapped_column(JSONDoc, default=dict)
    """Coverage and omissions from the most recent metacognitive gate attempt."""

    mastery_before: Mapped[float] = mapped_column(Float, default=0.0)
    mastery_after: Mapped[float | None] = mapped_column(Float, default=None)
    summary: Mapped[str] = mapped_column(Text, default="")
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    attempts: Mapped[list[Attempt]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Attempt.created_at"
    )


class Attempt(TimestampedUUIDModel):
    """The immutable ledger. One row per act of thinking."""

    __tablename__ = "attempts"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True
    )

    kind: Mapped[AttemptKind] = mapped_column(enum_column(AttemptKind))
    prompt: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text)

    correctness: Mapped[float | None] = mapped_column(Float, default=None)
    """0..1 - partial credit is the point. Binary grading destroys diagnosis."""

    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    """Committed *before* submission. Required for CHALLENGE attempts."""

    quadrant: Mapped[MetacognitiveQuadrant | None] = mapped_column(
        enum_column(MetacognitiveQuadrant), default=None
    )
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    scaffold_level: Mapped[int] = mapped_column(Integer, default=0)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[LearningSession] = relationship(back_populates="attempts")
    diagnosis: Mapped[Diagnosis | None] = relationship(
        back_populates="attempt", uselist=False, cascade="all, delete-orphan"
    )


class Diagnosis(TimestampedUUIDModel):
    """Structured output of the Examiner. The reason this is not a chatbot."""

    __tablename__ = "diagnoses"

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), unique=True, index=True
    )

    prior_estimate: Mapped[float] = mapped_column(Float, default=0.15)
    anchors: Mapped[list[str]] = mapped_column(JSONDoc, default=list)
    """What the learner already had right. Teaching starts here, always."""
    misconceptions: Mapped[list[dict[str, Any]]] = mapped_column(JSONDoc, default=list)
    missing: Mapped[list[str]] = mapped_column(JSONDoc, default=list)
    bloom_reached: Mapped[BloomLevel] = mapped_column(
        enum_column(BloomLevel), default=BloomLevel.REMEMBER
    )
    vocabulary_tier: Mapped[int] = mapped_column(Integer, default=2)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    """Examiner's private trace. Never shown - this is the tutor thinking."""

    attempt: Mapped[Attempt] = relationship(back_populates="diagnosis")


class Misconception(TimestampedUUIDModel):
    """D_w - the weakness index, with a lifecycle.

    A misconception is only ``RESOLVED`` after the learner clears it twice on
    separate occasions. One lucky answer does not close a gap.
    """

    __tablename__ = "misconceptions"
    __table_args__ = (Index("ix_misconception_user_status", "user_id", "status"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True
    )

    claim: Mapped[str] = mapped_column(Text)
    canonical: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[Severity] = mapped_column(enum_column(Severity), default=Severity.MEDIUM)
    status: Mapped[MisconceptionStatus] = mapped_column(
        enum_column(MisconceptionStatus), default=MisconceptionStatus.ACTIVE
    )
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    consecutive_clears: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class Reflection(TimestampedUUIDModel):
    """The Metacognitive Gate. Free recall, scored against the expert model."""

    __tablename__ = "reflections"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("concept_nodes.id", ondelete="CASCADE"))

    text: Mapped[str] = mapped_column(Text)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    omissions: Mapped[list[str]] = mapped_column(JSONDoc, default=list)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str] = mapped_column(Text, default="")


class AgentEvent(TimestampedUUIDModel):
    """The Trace Forest, reduced to something a startup can operate.

    Level 1 = session summary (``LearningSession.summary``)
    Level 2 = state transitions (``state_from`` -> ``state_to``)
    Level 3 = raw agent IO (this table's ``payload``)
    """

    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_event_session_created", "session_id", "created_at"),)

    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True, default=None
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    agent: Mapped[AgentName] = mapped_column(enum_column(AgentName))
    model: Mapped[str] = mapped_column(String(80), default="")
    state_from: Mapped[SessionState | None] = mapped_column(enum_column(SessionState), default=None)
    state_to: Mapped[SessionState | None] = mapped_column(enum_column(SessionState), default=None)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONDoc, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    guard_verdict: Mapped[GuardVerdict | None] = mapped_column(
        enum_column(GuardVerdict), default=None
    )
