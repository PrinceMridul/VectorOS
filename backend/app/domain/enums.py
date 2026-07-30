"""Shared vocabulary of the tutor kernel.

These enums are the contract between the control plane (state machine), the
generation plane (agents) and the measurement plane (pedagogy). They are
deliberately small: every value here must correspond to a decision the system
actually makes.
"""

from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    """The deterministic pedagogical state machine.

    An LLM may *never* set this value. Only :mod:`app.pedagogy.state_machine`
    may transition, and every transition is persisted for replay.
    """

    IDLE = "idle"
    """Session opened, nothing elicited yet."""

    ELICIT = "elicit"
    """The Prior-Belief Gate. We asked what the learner already believes."""

    DIAGNOSE = "diagnose"
    """Examiner is converting free text into a structured mental model."""

    INSTRUCT = "instruct"
    """Teacher speaks — calibrated to the diagnosis, never generic."""

    CHALLENGE = "challenge"
    """A ZPD-targeted task has been issued; the learner is thinking."""

    ATTEMPT = "attempt"
    """The learner is composing an answer (confidence not yet committed)."""

    EVALUATE = "evaluate"
    """Examiner is grading reasoning, not just correctness."""

    COACH = "coach"
    """One Socratic move at the current scaffold rung."""

    REFLECT = "reflect"
    """The Metacognitive Gate: articulate it or you do not pass."""

    MASTERY = "mastery"
    """Knowledge tracer commits the update."""

    COMPLETE = "complete"
    """Node closed. Trace written."""


class AttemptKind(StrEnum):
    PRIOR_BELIEF = "prior_belief"
    """Response to the Prior-Belief Gate — the most valuable data we collect."""

    CHALLENGE = "challenge"
    """A real attempt at a ZPD-targeted task."""

    COACH_REPLY = "coach_reply"
    """Answer to a Socratic probe; required before the scaffold may escalate."""

    REFLECTION = "reflection"
    """Free recall summary at the metacognitive gate."""


class Intent(StrEnum):
    """Router classification of learner input."""

    ATTEMPT = "attempt"
    QUESTION = "question"
    ANSWER_DEMAND = "answer_demand"
    """'just tell me' — triggers Refusal & Pivot and increments the offload counter."""
    REFLECTION = "reflection"
    META = "meta"
    """About the process itself ('why won't you tell me'), not the content."""
    OFF_TOPIC = "off_topic"


class Confidence(StrEnum):
    """Committed *before* submission. The metacognitive half of every attempt."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def value_float(self) -> float:
        return {"high": 0.9, "medium": 0.55, "low": 0.2}[self.value]


class MetacognitiveQuadrant(StrEnum):
    """Correctness x confidence. The single richest signal in the system."""

    AUTOMATICITY = "automaticity"
    """Correct + confident. Skill is available without occupying working memory."""

    FRAGILE = "fragile"
    """Correct + unsure. Knows more than they think; needs confirmation, not teaching."""

    BLIND_SPOT = "blind_spot"
    """Wrong + confident. Unconscious incompetence. Highest remediation priority."""

    KNOWN_GAP = "known_gap"
    """Wrong + unsure. Conscious incompetence — the healthiest failure mode."""


class BloomLevel(StrEnum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"

    @property
    def rank(self) -> int:
        return list(BloomLevel).index(self)


class NodeStatus(StrEnum):
    """Derived, never stored — computed from mastery + DAG on every read."""

    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    REVIEW_DUE = "review_due"
    MASTERED = "mastered"


class EdgeKind(StrEnum):
    PREREQUISITE = "prerequisite"
    RELATED = "related"


class MisconceptionStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def weight(self) -> float:
        return {"low": 0.25, "medium": 0.6, "high": 1.0}[self.value]


class AgentName(StrEnum):
    ROUTER = "router"
    PLANNER = "planner"
    EXAMINER = "examiner"
    TEACHER = "teacher"
    COACH = "coach"
    REFLECTION = "reflection"
    SYNTHESIZER = "synthesizer"
    MEMORY = "memory"
    GUARD = "guard"


class ModelTier(StrEnum):
    """Agents request a capability tier; deployment maps tiers to models."""

    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


class GuardVerdict(StrEnum):
    PASS = "pass"
    REWRITTEN = "rewritten"
    """Draft leaked the answer or broke move-shape; regenerated under a stricter contract."""
    FALLBACK = "fallback"
    """Regeneration also failed; a deterministic Socratic probe was substituted."""
