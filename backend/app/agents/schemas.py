"""Structured contracts between agents.

Every agent boundary is typed. This is the difference between a multi-agent
system and a group chat between prompts: the Examiner does not hand the Teacher
a paragraph of prose to reinterpret, it hands over a
:class:`MentalModelDiagnosis` with named misconceptions that the Teacher must
address and the Memory agent can write to the weakness index.

A field exists here only if some downstream component *consumes* it. Anything
the system merely finds interesting belongs in the trace log, not in a schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import BloomLevel, Intent, Severity


class MisconceptionItem(BaseModel):
    claim: str = Field(description="The learner's wrong belief, stated in their own terms.")
    canonical: str = Field(default="", description="The correct model this displaces.")
    severity: Severity = Severity.MEDIUM


class IntentClassification(BaseModel):
    """Router output. Hot path — must stay cheap."""

    intent: Intent
    adversarial: bool = Field(
        default=False,
        description="True when the learner is trying to jailbreak the tutor into answering.",
    )
    reasoning: str = ""


class MentalModelDiagnosis(BaseModel):
    """Output of the Prior-Belief Gate. The measurement the whole product turns on."""

    prior_estimate: float = Field(
        default=0.15, ge=0.0, le=1.0, description="P(already knows this) seeded into BKT."
    )
    anchors: list[str] = Field(
        default_factory=list, description="What they already have right. Teaching starts here."
    )
    misconceptions: list[MisconceptionItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    bloom_reached: BloomLevel = BloomLevel.REMEMBER
    vocabulary_tier: int = Field(default=2, ge=1, le=3)
    reasoning: str = Field(default="", description="Private. Never shown to the learner.")


class InstructionDraft(BaseModel):
    """Teacher output. Calibrated to a diagnosis, never generic."""

    message: str
    citations: list[str] = Field(
        default_factory=list, description="Chunk ids grounding every claim made."
    )
    addressed_misconceptions: list[str] = Field(default_factory=list)
    withheld: list[str] = Field(
        default_factory=list,
        description="What was deliberately NOT explained, because the learner is about "
        "to derive it. Productive failure made explicit and auditable.",
    )


class ChallengeDraft(BaseModel):
    """A ZPD-targeted task."""

    prompt: str
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="What a correct response must contain."
    )
    expected_reasoning: str = Field(
        default="", description="Private grading key. Guard treats this as leak-forbidden."
    )
    bloom: BloomLevel = BloomLevel.APPLY


class AttemptEvaluation(BaseModel):
    """Examiner output on a real attempt.

    ``correctness`` is graded, not binary: 'right idea, wrong execution' is a
    completely different pedagogical situation from 'wrong model', and collapsing
    them to a boolean destroys the diagnosis.
    """

    correctness: float = Field(ge=0.0, le=1.0)
    error_type: str = Field(
        default="none",
        description="none | slip | prerequisite_gap | misconception | incomplete",
    )
    anchors: list[str] = Field(default_factory=list)
    misconceptions: list[MisconceptionItem] = Field(default_factory=list)
    resolved_misconceptions: list[str] = Field(
        default_factory=list, description="Previously-active claims this attempt disproves."
    )
    reasoning_trace: str = Field(default="", description="Private. The tutor thinking.")


class CoachMove(BaseModel):
    """Exactly one Socratic move at the current rung. Never two."""

    message: str
    targets: str = Field(default="", description="The specific faulty step being probed.")


class ReflectionScore(BaseModel):
    """The Metacognitive Gate. Scored against the node's canonical model."""

    coverage: float = Field(ge=0.0, le=1.0)
    omissions: list[str] = Field(default_factory=list)
    feedback: str = ""


class SynthesisDraft(BaseModel):
    """Final learner-facing message, merged from the parallel agent outputs."""

    message: str


__all__ = [
    "AttemptEvaluation",
    "ChallengeDraft",
    "CoachMove",
    "InstructionDraft",
    "IntentClassification",
    "MentalModelDiagnosis",
    "MisconceptionItem",
    "ReflectionScore",
    "SynthesisDraft",
]
