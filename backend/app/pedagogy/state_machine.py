"""The pedagogical control plane.

This module is the reason VectorOS is not a wrapper.

Everything an LLM produces is a *suggestion about language*. What actually
happens next — whether the learner is taught, challenged, coached or gated — is
decided here, by a deterministic transition table that no model output can
influence. The model writes the sentences; this file decides which kind of
sentence is legal.

That inversion is what makes the guardrails hold under pressure. A frustrated
learner can argue with a prompt. They cannot argue with a state machine that has
no edge from ``CHALLENGE`` to "here is the answer", because that edge does not
exist.

Every transition is recorded with its trigger, so any mastery claim the system
makes months later is replayable back to the acts of thinking that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.core.errors import PedagogicalViolation
from app.domain.enums import SessionState as S

#: The legal edges. Anything not listed here is, by construction, impossible.
TRANSITIONS: dict[S, frozenset[S]] = {
    # A brand-new node can only begin one way: by asking what you already believe.
    S.IDLE: frozenset({S.ELICIT}),
    S.ELICIT: frozenset({S.DIAGNOSE}),
    S.DIAGNOSE: frozenset({S.INSTRUCT}),
    # Teaching is always followed by doing. There is no "read more" edge.
    S.INSTRUCT: frozenset({S.CHALLENGE}),
    S.CHALLENGE: frozenset({S.ATTEMPT, S.COACH}),
    S.ATTEMPT: frozenset({S.EVALUATE}),
    # After grading: correct → reflect, incorrect → coach, badly wrong → reteach.
    S.EVALUATE: frozenset({S.COACH, S.REFLECT, S.CHALLENGE, S.INSTRUCT}),
    S.COACH: frozenset({S.ATTEMPT, S.COACH, S.CHALLENGE, S.INSTRUCT}),
    # Mastery is unreachable without passing the metacognitive gate.
    S.REFLECT: frozenset({S.MASTERY, S.CHALLENGE, S.COACH}),
    S.MASTERY: frozenset({S.COMPLETE, S.CHALLENGE}),
    S.COMPLETE: frozenset(),
}

#: States in which the learner is expected to be producing thought. The client
#: shows the thinking canvas, not a chat box.
LEARNER_TURN: frozenset[S] = frozenset({S.ELICIT, S.CHALLENGE, S.ATTEMPT, S.COACH, S.REFLECT})

#: States in which free-text guidance requests are meaningful at all.
GUIDANCE_AVAILABLE: frozenset[S] = frozenset({S.CHALLENGE, S.ATTEMPT, S.COACH})


@dataclass(frozen=True, slots=True)
class Transition:
    source: S
    target: S
    trigger: str
    notes: dict[str, object] = field(default_factory=dict)


def can_transition(source: S, target: S) -> bool:
    return target in TRANSITIONS.get(source, frozenset())


def transition(source: S, target: S, *, trigger: str, **notes: object) -> Transition:
    """Move the session, or refuse loudly.

    We raise rather than clamp because an illegal transition means either a bug
    or a client trying to skip the parts that constitute the learning. Both
    should be visible, never silently absorbed.
    """
    if not can_transition(source, target):
        raise PedagogicalViolation(
            f"Illegal pedagogical transition {source} → {target}.",
            source=str(source),
            target=str(target),
            trigger=trigger,
            allowed=sorted(str(s) for s in TRANSITIONS.get(source, frozenset())),
        )
    return Transition(source=source, target=target, trigger=trigger, notes=notes)


def next_after_evaluation(
    *,
    correctness: float,
    scaffold_level: int,
    max_scaffold: int,
    consecutive_failures: int,
    pass_threshold: float | None = None,
) -> tuple[S, str]:
    """Where a graded attempt sends the learner.

    The ordering encodes a pedagogical priority: coach before re-teaching, and
    re-teach before repeating the same challenge. Repeating an identical task at
    an unchanged mastery level is the definition of an unproductive loop.
    """
    threshold = settings.challenge_pass_threshold if pass_threshold is None else pass_threshold

    if correctness >= threshold:
        return S.REFLECT, "correct"

    if correctness >= 0.5:
        return S.COACH, "partially_correct"

    # Repeated total failure at the top of the ladder means the *instruction*
    # was wrong, not the learner. Go back and re-teach with a new framing.
    if consecutive_failures >= 2 and scaffold_level >= max_scaffold:
        return S.INSTRUCT, "reteach_after_repeated_failure"

    return S.COACH, "incorrect"


def next_after_reflection(*, passed: bool, coverage: float) -> tuple[S, str]:
    """The Metacognitive Gate.

    Correct answers are not proof of understanding — a learner can pattern-match
    their way to right answers and retain nothing. Free recall against the expert
    model is the check, and failing it sends you back to *practice*, not to
    re-reading, because re-reading is what feels like learning and is not.
    """
    if passed:
        return S.MASTERY, "reflection_passed"
    if coverage >= 0.35:
        return S.COACH, "reflection_partial"
    return S.CHALLENGE, "reflection_failed"


def guidance_unlocked(*, elapsed_seconds: float, struggle_floor: int, attempted: bool) -> bool:
    """Has the learner earned a hint?

    Either they have already produced an attempt (effort demonstrated), or they
    have sat with the problem past the struggle floor. Instant help on an
    untouched problem is the exact mechanism of cognitive offloading.
    """
    return attempted or elapsed_seconds >= struggle_floor


__all__ = [
    "GUIDANCE_AVAILABLE",
    "LEARNER_TURN",
    "TRANSITIONS",
    "Transition",
    "can_transition",
    "guidance_unlocked",
    "next_after_evaluation",
    "next_after_reflection",
    "transition",
]
