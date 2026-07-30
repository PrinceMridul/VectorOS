"""Metacognition: the four quadrants, and Cognitive Debt.

Two measurements that no chatbot can make, because both require the learner to
commit to a belief *before* seeing the outcome.

**Quadrants.** Correctness × confidence. The interesting cell is wrong-and-certain:
*unconscious incompetence*, the blind spot. It is invisible to conventional
grading (the score just says "wrong") and it is where the most damaging practice
errors come from, because the learner has no reason to look again. VectorOS
prioritises blind spots above every other remediation target.

**Cognitive Debt.** The learner-visible answer to "how much of this progress was
actually mine?" Making it a number turns the avoidance of cognitive offloading
into something a person can optimise, which is the only way a virtue survives
contact with a product.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.domain.enums import MetacognitiveQuadrant

CONFIDENT_THRESHOLD = 0.6
"""Above this, the learner has committed. 'Medium' (0.55) counts as hedging."""


def classify(
    correctness: float, confidence: float | None, *, correct_threshold: float | None = None
) -> MetacognitiveQuadrant:
    """Place an attempt in the correctness x confidence grid.

    The correctness bar defaults to the same threshold the state machine uses to
    call an attempt correct. Two different bars would produce the incoherent
    result of an attempt being 'automaticity' on the dashboard while the tutor
    routes it to remediation.
    """
    bar = settings.challenge_pass_threshold if correct_threshold is None else correct_threshold
    correct = correctness >= bar
    confident = (confidence or 0.5) >= CONFIDENT_THRESHOLD

    if correct and confident:
        return MetacognitiveQuadrant.AUTOMATICITY
    if correct:
        return MetacognitiveQuadrant.FRAGILE
    if confident:
        return MetacognitiveQuadrant.BLIND_SPOT
    return MetacognitiveQuadrant.KNOWN_GAP


#: How the tutor should *respond* to each quadrant. Same correctness, different
#: pedagogy — this is what "adapts to how you learn" means concretely.
RESPONSE_STRATEGY: dict[MetacognitiveQuadrant, str] = {
    MetacognitiveQuadrant.AUTOMATICITY: (
        "Confirm briefly and escalate. Do not over-praise — affirmation fatigue is real, "
        "and this learner has earned harder work, which is the real reward."
    ),
    MetacognitiveQuadrant.FRAGILE: (
        "They were right but did not trust it. Name explicitly what they got right and why "
        "their reasoning was sound. The gap here is confidence, not knowledge — do not reteach."
    ),
    MetacognitiveQuadrant.BLIND_SPOT: (
        "Wrong while certain. Do NOT correct directly — a confident wrong model resists being "
        "told. Construct a case where their own model visibly fails, and let them observe the "
        "contradiction themselves."
    ),
    MetacognitiveQuadrant.KNOWN_GAP: (
        "Wrong and they know it. This is the healthiest failure mode: they are receptive. "
        "Move straight to targeted scaffolding, and say that noticing the gap was the hard part."
    ),
}


@dataclass(frozen=True, slots=True)
class CalibrationSummary:
    samples: int
    mean_error: float
    """Mean |confidence − correctness|. Lower is better-calibrated."""
    overconfidence: float
    """Signed: positive ⇒ systematically overrates themselves."""
    blind_spots: int

    @property
    def label(self) -> str:
        if self.samples < 4:
            return "calibrating"
        if self.mean_error < 0.2:
            return "well calibrated"
        if self.overconfidence > 0.15:
            return "overconfident"
        if self.overconfidence < -0.15:
            return "underconfident"
        return "developing"


def calibration_error(correctness: float, confidence: float | None) -> float:
    return abs((confidence if confidence is not None else 0.5) - correctness)


@dataclass(frozen=True, slots=True)
class CognitiveDebt:
    score: float
    """0..1. 0 = every win was earned unaided; 1 = the system did the thinking."""
    unaided_wins: int
    hinted_wins: int
    hints_consumed: int
    offload_attempts: int

    @property
    def label(self) -> str:
        if self.score <= 0.25:
            return "independent"
        if self.score <= 0.5:
            return "supported"
        if self.score <= 0.75:
            return "reliant"
        return "offloading"

    @property
    def headline(self) -> str:
        return {
            "independent": "You are doing the thinking. This is what durable learning looks like.",
            "supported": "You are using help well — asking after trying, not instead of trying.",
            "reliant": "You are leaning on hints early. Try sitting with the problem 60s longer.",
            "offloading": "Most of your wins arrived with help. Let's rebuild some unaided reps.",
        }[self.label]


def cognitive_debt(
    *,
    unaided_wins: int,
    hinted_wins: int,
    hints_consumed: int,
    offload_attempts: int,
) -> CognitiveDebt:
    """Weighted reliance ratio, bounded to 0..1.

    Hints are not sinful — asking for help after real effort is expert
    behaviour. What the score penalises is help that *replaced* thinking:
    hint-heavy wins, and outright demands for the answer.
    """
    total_wins = unaided_wins + hinted_wins
    if total_wins == 0 and hints_consumed == 0 and offload_attempts == 0:
        return CognitiveDebt(0.0, 0, 0, 0, 0)

    reliance = hinted_wins / total_wins if total_wins else 0.0
    hint_density = hints_consumed / max(total_wins, 1) / 4.0  # 4 = full ladder
    demand_penalty = min(offload_attempts * 0.08, 0.3)

    score = 0.5 * reliance + 0.3 * min(hint_density, 1.0) + demand_penalty
    return CognitiveDebt(
        score=round(max(0.0, min(1.0, score)), 3),
        unaided_wins=unaided_wins,
        hinted_wins=hinted_wins,
        hints_consumed=hints_consumed,
        offload_attempts=offload_attempts,
    )


__all__ = [
    "CONFIDENT_THRESHOLD",
    "RESPONSE_STRATEGY",
    "CalibrationSummary",
    "CognitiveDebt",
    "calibration_error",
    "classify",
    "cognitive_debt",
]
