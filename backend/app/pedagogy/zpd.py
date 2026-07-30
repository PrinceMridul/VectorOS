"""Zone of Proximal Development targeting.

The personalisation in VectorOS is not "tone" or "learning style". It is this:
**we choose the difficulty at which this learner will succeed 50–80% of the
time.** Below the band you get boredom and no encoding; above it you get
overload and learned helplessness. The band is where learning velocity peaks.

We already have a calibrated predictor of success — the BKT forward model — so
difficulty selection is a search, not a guess: pick the difficulty whose
predicted success probability lands nearest the centre of the band, subject to
the node's Bloom ceiling and the learner's current cognitive load.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.domain.enums import BloomLevel
from app.pedagogy.bkt import BKTParams, predict_correct
from app.pedagogy.load import LoadReading

#: Difficulty ladder we can actually author challenges at.
DIFFICULTY_STEPS: tuple[float, ...] = (0.2, 0.35, 0.5, 0.65, 0.8, 0.95)


@dataclass(frozen=True, slots=True)
class ZPDTarget:
    difficulty: float
    bloom: BloomLevel
    predicted_success: float
    rationale: str

    @property
    def in_band(self) -> bool:
        return settings.zpd_target_low <= self.predicted_success <= settings.zpd_target_high


def _difficulty_penalty(difficulty: float, mastery: float) -> float:
    """A harder task lowers the effective success probability.

    Mastery is measured on the node's *nominal* difficulty; a task above that is
    a partial extrapolation. This keeps the search honest without pretending we
    have per-item IRT parameters we have not earned yet.
    """
    return 1.0 - 0.55 * max(0.0, difficulty - mastery)


def _bloom_for(difficulty: float, ceiling: BloomLevel) -> BloomLevel:
    ladder = [
        (0.25, BloomLevel.UNDERSTAND),
        (0.45, BloomLevel.APPLY),
        (0.7, BloomLevel.ANALYZE),
        (0.9, BloomLevel.EVALUATE),
        (1.01, BloomLevel.CREATE),
    ]
    chosen = next(level for bound, level in ladder if difficulty < bound)
    return chosen if chosen.rank <= ceiling.rank else ceiling


def select_target(
    *,
    mastery: float,
    params: BKTParams,
    node_difficulty: float,
    bloom_ceiling: BloomLevel,
    load: LoadReading | None = None,
    first_challenge: bool = False,
) -> ZPDTarget:
    """Choose the next challenge's difficulty and cognitive level."""
    base_success = predict_correct(mastery, params)
    centre = (settings.zpd_target_low + settings.zpd_target_high) / 2

    # An overloaded learner does not need a cleverer question, they need a
    # smaller one. Bias the target upward in success probability.
    if load and load.overloaded:
        centre = settings.zpd_target_high
    elif load and load.underloaded:
        centre = settings.zpd_target_low

    # Productive failure: the *first* encounter with a node is deliberately
    # above the comfort line. Failing here is the mechanism, not a bug — it
    # activates prior knowledge and primes the learner for instruction.
    if first_challenge:
        centre = min(centre, settings.zpd_target_low + 0.05)

    candidates = [d for d in DIFFICULTY_STEPS if abs(d - node_difficulty) <= 0.46] or list(
        DIFFICULTY_STEPS
    )

    best = min(
        candidates,
        key=lambda d: abs(base_success * _difficulty_penalty(d, mastery) - centre),
    )
    predicted = base_success * _difficulty_penalty(best, mastery)

    if load and load.overloaded:
        rationale = "Cognitive load is high — stepping the task down and decomposing."
    elif load and load.underloaded:
        rationale = "This is landing too easily — raising difficulty to restore the struggle."
    elif first_challenge:
        rationale = "First encounter: a deliberately hard task, to surface what is missing."
    else:
        rationale = "Calibrated to the 50–80% success band."

    return ZPDTarget(
        difficulty=best,
        bloom=_bloom_for(best, bloom_ceiling),
        predicted_success=round(predicted, 3),
        rationale=rationale,
    )


__all__ = ["DIFFICULTY_STEPS", "ZPDTarget", "select_target"]
