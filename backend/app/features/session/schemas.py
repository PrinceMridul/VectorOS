"""Wire types for the tutoring loop.

Note what is *absent* from every response: ``canonical_model``,
``expected_reasoning`` and ``acceptance_criteria``. The learner's browser never
receives the grading key. A Socratic tutor whose answer is one devtools tab away
is a demo, not a product.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import Confidence, MetacognitiveQuadrant, SessionState


class StartSessionRequest(BaseModel):
    node_id: str


class TurnRequest(BaseModel):
    text: str = Field(default="", max_length=8000)
    confidence: Confidence | None = None
    """Required before a challenge attempt. The metacognitive half of the data."""
    elapsed_ms: int = Field(default=0, ge=0)
    request_guidance: bool = False
    """True ⇒ 'I'm stuck', not an attempt. Gated by the struggle floor."""


class MentalModelView(BaseModel):
    anchors: list[str] = Field(default_factory=list)
    misconceptions: list[dict] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    prior_estimate: float = 0.0
    bloom_reached: str = "remember"


class EvaluationView(BaseModel):
    correctness: float
    quadrant: MetacognitiveQuadrant
    quadrant_note: str
    error_type: str
    anchors: list[str] = Field(default_factory=list)
    misconceptions: list[dict] = Field(default_factory=list)


class ReflectionView(BaseModel):
    coverage: float
    omissions: list[str]
    passed: bool
    feedback: str


class SessionView(BaseModel):
    id: str
    graph_id: str
    node_id: str
    node_title: str
    node_one_liner: str

    state: SessionState
    message: str
    """What the tutor is currently saying. Survives refresh and device switches."""

    challenge_prompt: str | None
    scaffold_level: int
    max_scaffold_level: int
    requires_confidence: bool
    guidance_available: bool
    struggle_floor_seconds: int

    mastery: float
    mastery_before: float
    predicted_success: float
    cognitive_load: float
    load_band: str

    turn_count: int
    offload_attempts: int
    input_locked: bool
    """Anti-offload circuit tripped: the client must present a structured task."""

    mental_model: MentalModelView | None
    last_evaluation: EvaluationView | None
    reflection: ReflectionView | None
    completed: bool


class TransitionView(BaseModel):
    source: SessionState
    target: SessionState
    trigger: str


class TurnResponse(BaseModel):
    session: SessionView
    transitions: list[TransitionView]
    mastery_delta: float
    unlocked_nodes: list[str] = Field(default_factory=list)
    guard_verdict: str | None = None
    refused: bool = False


class ResolvedBelief(BaseModel):
    claim: str
    canonical: str
    severity: str
    resolved: bool
    clears: int = 0
    """Independent pieces of evidence that the learner has dropped this belief.

    Surfaced rather than hidden because "cleared once, needs one more" is both
    honest and motivating — and it makes the system's standard legible. A binary
    open/closed flag makes a learner who just answered perfectly look like they
    made no progress.
    """
    clears_required: int = 2


class UnderstandingShift(BaseModel):
    """The Understanding Shift — the closing moment of a concept.

    Two pieces of the learner's own writing, side by side: what they said they
    believed *before* any instruction, and what they could reconstruct from
    memory *after*. Between them, the misconceptions that were named and which
    of them they dislodged.

    This is only possible because of the Prior-Belief Gate. A product that
    answers first has no "before" to show — it never asked. That is the whole
    argument of VectorOS, rendered as one screen using nothing but data the
    learner produced themselves.
    """

    node_title: str
    node_one_liner: str

    before_text: str
    before_at: str
    after_text: str
    after_at: str

    beliefs: list[ResolvedBelief] = Field(default_factory=list)
    anchors_at_start: list[str] = Field(default_factory=list)
    """What they already had right when they walked in. Growth is not from zero."""

    mastery_before: float
    mastery_after: float
    prior_estimate: float

    attempts: int
    unaided_wins: int
    hints_used: int
    answer_demands_refused: int
    minutes_elapsed: float

    reflection_coverage: float
    unlocked_titles: list[str] = Field(default_factory=list)


class TraceEventView(BaseModel):
    agent: str
    model: str
    state_from: str | None
    state_to: str | None
    latency_ms: int
    tokens_in: int
    tokens_out: int
    guard_verdict: str | None
    created_at: str
    payload: dict


__all__ = [
    "EvaluationView",
    "MentalModelView",
    "ReflectionView",
    "ResolvedBelief",
    "SessionView",
    "StartSessionRequest",
    "TraceEventView",
    "TransitionView",
    "TurnRequest",
    "TurnResponse",
    "UnderstandingShift",
]
