"""The scaffolding ladder — Cognitive Apprenticeship, made mechanical.

An LLM asked to "be Socratic" will hold the line for three turns and then, under
a frustrated learner's pressure, hand over the answer. This is *scaffolding
collapse*, and it is the single most important failure mode to engineer around.
A system prompt cannot fix it, because the pressure is applied at inference time
and the model's own training rewards helpfulness.

So the escalation is not a prompt instruction. It is an integer on a database
row, with two invariants enforced in Python:

* the level may only rise by **one rung at a time**, and
* only **after the learner has produced a reply** to the previous rung.

The learner can therefore always get more help — patience is a feature, and
withholding help from someone genuinely stuck is cruelty, not pedagogy — but
they can never *jump* to the answer, and every rung costs them a turn of
thinking. Rung 5 does not exist. There is no state in which this system emits
the terminal answer to an unattempted challenge.

Fading is the mirror image: as mastery rises the *ceiling* drops, so a learner
who has demonstrated competence is no longer offered training wheels they have
outgrown. That is the "gradual release of responsibility" — Guide → Collaborator
→ Peer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.errors import PedagogicalViolation
from app.pedagogy.load import LoadReading


@dataclass(frozen=True, slots=True)
class Rung:
    level: int
    name: str
    persona: str
    contract: str
    """Injected verbatim into the Coach prompt. The behavioural spec for this rung."""
    must_be_question: bool


LADDER: tuple[Rung, ...] = (
    Rung(
        level=0,
        name="silence",
        persona="peer",
        contract=(
            "Say nothing that helps. Acknowledge the attempt is in progress and "
            "restate the goal in one line. The learner has not earned a hint yet "
            "and does not need one."
        ),
        must_be_question=False,
    ),
    Rung(
        level=1,
        name="orient",
        persona="peer",
        contract=(
            "Ask ONE orienting question that points at the *region* of the problem "
            "where the learner's reasoning went astray, without naming the error. "
            "Example shape: 'Which part of your reasoning are you least sure about?' "
            "Maximum two sentences. Must end in a question mark."
        ),
        must_be_question=True,
    ),
    Rung(
        level=2,
        name="probe",
        persona="collaborator",
        contract=(
            "Ask ONE targeted question that isolates the specific faulty step, "
            "quoting the learner's own words back to them. Do not state the correct "
            "idea; make them confront the contradiction. Maximum two sentences. "
            "Must end in a question mark."
        ),
        must_be_question=True,
    ),
    Rung(
        level=3,
        name="structure",
        persona="guide",
        contract=(
            "Give a STRUCTURAL hint: name the framework, the relevant principle, or "
            "the sub-question to answer first — but never apply it to this problem. "
            "Hand them the tool, not the result. Maximum three sentences."
        ),
        must_be_question=False,
    ),
    Rung(
        level=4,
        name="model",
        persona="guide",
        contract=(
            "Work ONE analogous example end to end — a *different* instance of the "
            "same structure — then hand the original problem straight back. Never "
            "solve the learner's actual problem. End by asking them to apply it."
        ),
        must_be_question=False,
    ),
)


def rung(level: int) -> Rung:
    return LADDER[max(0, min(level, settings.max_scaffold_level))]


def ceiling_for(mastery: float) -> int:
    """Fading: what the learner is *allowed* to receive, given demonstrated skill.

    A learner at 0.8 mastery being offered a worked example is being told the
    system does not believe them.
    """
    if mastery >= 0.8:
        return 1
    if mastery >= 0.6:
        return 2
    if mastery >= 0.35:
        return 3
    return settings.max_scaffold_level


def escalate(
    *,
    current: int,
    learner_replied: bool,
    mastery: float,
    load: LoadReading | None = None,
) -> int:
    """Advance the ladder by exactly one rung, or refuse.

    Raises :class:`PedagogicalViolation` rather than silently clamping, because a
    client trying to skip rungs is either a bug or an attempt to game the tutor,
    and both deserve to be loud.
    """
    if current < 0:
        raise PedagogicalViolation("Scaffold level cannot be negative.", level=current)

    if not learner_replied and current > 0:
        raise PedagogicalViolation(
            "More guidance is available after you respond to the current question.",
            scaffold_level=current,
        )

    ceiling = ceiling_for(mastery)
    # Genuine overload overrides fading: someone drowning gets the ladder back.
    if load and load.overloaded:
        ceiling = settings.max_scaffold_level

    return min(current + 1, ceiling, settings.max_scaffold_level)


def reset_for_new_challenge() -> int:
    return 0


__all__ = ["LADDER", "Rung", "ceiling_for", "escalate", "reset_for_new_challenge", "rung"]
