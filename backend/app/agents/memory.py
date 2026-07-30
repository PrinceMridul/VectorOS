"""The Memory agent — deterministic, no LLM.

Its job is to decide *what a turn should change about the learner*, and it is
pure: it takes the turn's observations and returns a :class:`ProfileDelta` that
the session service applies. Keeping it side-effect-free is what makes the
system's memory testable — you can assert that a confidently-wrong answer opens
a misconception and shortens the review interval without touching a database.

Two policies live here that are easy to get wrong:

**Consolidation, not transcription.** Raw turn-by-turn dialogue is redundant and
expensive, and hoarding it is how context windows die. We keep a compact session
summary and the structured state (mastery, misconceptions, calibration) and let
the verbatim exchange age out. Forgetting the words while keeping the diagnosis
is exactly what a good human tutor does between Tuesdays.

**A gap closes slowly.** A misconception is only marked resolved after the
learner clears it on two separate occasions. One correct answer is very often a
guess, a lucky phrasing, or a memory of the last hint — and prematurely closing
a gap means the system stops watching precisely where it should be watching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.text import truncate
from app.domain.enums import MetacognitiveQuadrant, Severity

#: Consecutive clears required before a misconception is considered resolved.
CLEARS_TO_RESOLVE = 2


@dataclass(slots=True)
class MisconceptionDelta:
    claim: str
    canonical: str = ""
    severity: Severity = Severity.MEDIUM
    observed: bool = True
    """True ⇒ seen again (reinforce). False ⇒ cleared this turn."""


@dataclass(slots=True)
class ProfileDelta:
    """Everything one turn changes about the longitudinal learner model."""

    misconceptions: list[MisconceptionDelta] = field(default_factory=list)
    unaided_win: bool = False
    hinted_win: bool = False
    hints_consumed: int = 0
    offload_attempt: bool = False
    calibration_error: float | None = None
    vocabulary_tier: int | None = None
    pedagogy_note: str | None = None
    session_summary: str | None = None

    @property
    def empty(self) -> bool:
        return not (
            self.misconceptions
            or self.unaided_win
            or self.hinted_win
            or self.hints_consumed
            or self.offload_attempt
            or self.calibration_error is not None
            or self.vocabulary_tier is not None
            or self.pedagogy_note
            or self.session_summary
        )


def from_diagnosis(diagnosis: dict[str, Any]) -> ProfileDelta:
    """Prior-Belief Gate → weakness index + register calibration."""
    return ProfileDelta(
        misconceptions=[
            MisconceptionDelta(
                claim=m.get("claim", ""),
                canonical=m.get("canonical", ""),
                severity=Severity(m.get("severity", "medium")),
                observed=True,
            )
            for m in diagnosis.get("misconceptions", [])
            if m.get("claim")
        ],
        vocabulary_tier=diagnosis.get("vocabulary_tier"),
        pedagogy_note=(
            f"Arrived with: {'; '.join(diagnosis.get('anchors', [])[:2])}"
            if diagnosis.get("anchors")
            else None
        ),
    )


def from_attempt(
    *,
    evaluation: dict[str, Any],
    quadrant: MetacognitiveQuadrant,
    scaffold_level: int,
    calibration_error: float,
) -> ProfileDelta:
    """A graded attempt → the whole ledger."""
    correctness = float(evaluation.get("correctness", 0.0))
    correct = correctness >= settings.challenge_pass_threshold

    deltas = [
        MisconceptionDelta(
            claim=m.get("claim", ""),
            canonical=m.get("canonical", ""),
            severity=Severity(m.get("severity", "medium")),
            observed=True,
        )
        for m in evaluation.get("misconceptions", [])
        if m.get("claim")
    ]
    deltas += [
        MisconceptionDelta(claim=claim, observed=False)
        for claim in evaluation.get("resolved_misconceptions", [])
        if claim
    ]

    note: str | None = None
    if quadrant is MetacognitiveQuadrant.BLIND_SPOT:
        note = "Confidently wrong here — build contradiction cases, do not correct directly."
    elif quadrant is MetacognitiveQuadrant.FRAGILE:
        note = "Right but distrusted their own reasoning — confirm explicitly, do not reteach."
    elif correct and scaffold_level == 0:
        note = "Solved unaided on first pass — can take a steeper next step."

    return ProfileDelta(
        misconceptions=deltas,
        unaided_win=correct and scaffold_level == 0,
        hinted_win=correct and scaffold_level > 0,
        hints_consumed=max(0, scaffold_level),
        calibration_error=calibration_error,
        pedagogy_note=note,
    )


def from_refusal() -> ProfileDelta:
    return ProfileDelta(
        offload_attempt=True,
        pedagogy_note="Reached for the answer instead of the next step.",
    )


def consolidate_session(
    *,
    node_title: str,
    mastery_before: float,
    mastery_after: float,
    attempts: int,
    misconceptions_opened: int,
    misconceptions_resolved: int,
    reflection_passed: bool,
) -> str:
    """Level-1 trace: what a tutor would actually remember about a session.

    Deliberately terse. This is loaded into context at the start of the *next*
    session, so every word here costs tokens for the rest of the relationship.
    """
    direction = "↑" if mastery_after >= mastery_before else "↓"
    bits = [
        f"{node_title}: mastery {mastery_before:.2f}{direction}{mastery_after:.2f}",
        f"{attempts} attempt(s)",
    ]
    if misconceptions_opened:
        bits.append(f"{misconceptions_opened} new gap(s)")
    if misconceptions_resolved:
        bits.append(f"{misconceptions_resolved} cleared")
    bits.append("reflection passed" if reflection_passed else "reflection not reached")
    return truncate(" · ".join(bits), 240)


__all__ = [
    "CLEARS_TO_RESOLVE",
    "MisconceptionDelta",
    "ProfileDelta",
    "consolidate_session",
    "from_attempt",
    "from_diagnosis",
    "from_refusal",
]
