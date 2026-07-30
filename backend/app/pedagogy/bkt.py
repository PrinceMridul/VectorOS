"""Extended Bayesian Knowledge Tracing.

Classic BKT is a two-state HMM: the learner either knows a skill or does not,
and we observe noisy evidence through *guess* and *slip*. We keep it — not out
of nostalgia, but because a mastery claim that cannot be explained to a learner
(or an educator, or a regulator) is unshippable in education. A neural tracer
that says "0.91, trust me" is a worse product than an interpretable one that
says "0.84, because you cleared this unaided twice and last saw it 6 days ago".

Three extensions the research demands, each of which fixes a way classic BKT
lies about a person:

1. **Forgetting** (``p_forget`` + continuous time decay).
   Classic BKT assumes mastery is permanent. It is not. Without decay you can
   never schedule review, and the tutor drifts into congratulating people about
   things they have quietly lost.

2. **Confidence weighting.**
   Confidence is committed *before* submission, so it is honest. It tells us how
   noisy the observation is. Wrong-and-certain is a blind spot and should move
   mastery hard; right-and-unsure looks partly like a guess and should move it
   gently.

3. **Scaffold discounting.**
   A correct answer produced after a level-4 worked step is not the same
   evidence as one produced cold. Without this the tutor can talk a learner into
   fake mastery — precisely the cognitive-offloading failure we exist to
   prevent.

Partial credit is handled as a *mixture* of the correct and incorrect
posteriors, weighted by the graded correctness, rather than by thresholding to a
boolean. Thresholding throws away exactly the information a tutor needs.

The public surface here is deliberately a pure function set with no I/O, so it
is trivially testable and swappable — :class:`KnowledgeTracer` is the seam where
a DKT/AKT model drops in later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.core.config import settings

# Numerical guard rails: probabilities never collapse to exactly 0 or 1, because
# a hard 1.0 is unrecoverable evidence and makes the model unfalsifiable.
_EPS = 1e-6
_P_MIN, _P_MAX = 0.01, 0.995


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True, slots=True)
class BKTParams:
    """Per-learner, per-KC parameters.

    These are stored rather than global because slip and guess are properties of
    *a person on a concept*, not of the concept alone.
    """

    prior: float = 0.15
    learn: float = 0.30
    guess: float = 0.20
    slip: float = 0.10
    forget: float = 0.05

    def sanitised(self) -> BKTParams:
        return BKTParams(
            prior=_clamp(self.prior, _P_MIN, _P_MAX),
            learn=_clamp(self.learn, 0.01, 0.6),
            guess=_clamp(self.guess, 0.01, 0.45),
            slip=_clamp(self.slip, 0.01, 0.45),
            forget=_clamp(self.forget, 0.0, 0.3),
        )


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observation about one learner on one KC."""

    correctness: float
    """0..1 graded. 1.0 = canonical, 0.5 = right idea wrong execution, 0.0 = wrong model."""

    confidence: float | None = None
    """Committed before submission. ``None`` ⇒ treated as neutral (0.5)."""

    scaffold_level: int = 0
    """0..``max_scaffold_level``. How much help was in force when this was produced."""

    latency_ms: int = 0
    """Only used for load/engagement signals — never to grade."""

    @property
    def confidence_or_neutral(self) -> float:
        return 0.5 if self.confidence is None else _clamp(self.confidence, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class TraceResult:
    p_mastery: float
    p_previous: float
    delta: float
    effective_guess: float
    effective_slip: float
    predicted_correct: float
    """P(correct on the *next* attempt). This is what ZPD selection consumes."""

    @property
    def improved(self) -> bool:
        return self.delta > 0


def _noise_multiplier(confidence: float) -> float:
    """Low confidence ⇒ the observation is noisier in *both* directions.

    c=0.0 → 1.6×  (a wrong answer may be a slip; a right answer may be a guess)
    c=0.5 → 1.0×  (neutral)
    c=1.0 → 0.4×  (the learner committed; take the observation at face value)
    """
    return 1.6 - 1.2 * _clamp(confidence, 0.0, 1.0)


def effective_params(params: BKTParams, evidence: Evidence) -> tuple[float, float]:
    """Fold confidence and scaffolding into (guess, slip) for this observation."""
    params = params.sanitised()
    noise = _noise_multiplier(evidence.confidence_or_neutral)
    scaffold_ratio = _clamp(evidence.scaffold_level / max(settings.max_scaffold_level, 1), 0.0, 1.0)

    # Heavily scaffolded correctness looks more like a guess...
    guess = params.guess * noise * (1.0 + 1.4 * scaffold_ratio)
    # ...and failing *despite* help is stronger evidence of genuine non-mastery,
    # so we shrink the probability that it was a mere slip.
    slip = params.slip * noise * (1.0 - 0.5 * scaffold_ratio)

    return _clamp(guess, 0.01, 0.6), _clamp(slip, 0.01, 0.6)


def posterior(p: float, evidence: Evidence, guess: float, slip: float) -> float:
    """Bayesian update on the *current* knowledge state, before the learning step.

    Graded correctness is handled as a mixture of the two canonical posteriors
    rather than by rounding, so "right idea, wrong execution" moves the model
    the right amount instead of counting as a total failure.
    """
    p = _clamp(p, _EPS, 1 - _EPS)

    num_correct = p * (1 - slip)
    den_correct = num_correct + (1 - p) * guess
    post_correct = num_correct / den_correct if den_correct > _EPS else p

    num_incorrect = p * slip
    den_incorrect = num_incorrect + (1 - p) * (1 - guess)
    post_incorrect = num_incorrect / den_incorrect if den_incorrect > _EPS else p

    w = _clamp(evidence.correctness, 0.0, 1.0)
    return w * post_correct + (1 - w) * post_incorrect


def predict_correct(p: float, params: BKTParams) -> float:
    """P(next answer correct) given current mastery. The ZPD input."""
    params = params.sanitised()
    return _clamp(p * (1 - params.slip) + (1 - p) * params.guess, 0.0, 1.0)


def update(p: float, params: BKTParams, evidence: Evidence) -> TraceResult:
    """Observe. This is *measurement only* — it never adds learning.

    Textbook BKT folds the learning transition into the same step as the
    observation, on the grounds that every practice item is also a learning
    opportunity. That produces a result this product cannot ship: from a low
    prior, a confidently *wrong* answer makes the estimate go **up**, because the
    ``(1 − post)·learn`` term outweighs the evidence. We hit exactly that in
    testing — 0.15 → 0.44 on a wrong answer — and a mastery number that rises
    when you are wrong is worse than no number at all, because the learner will
    correctly stop believing it.

    So VectorOS separates the two. Being graded is measurement; being *taught* is
    the learning opportunity, and it is applied by :func:`apply_instruction` at
    the point where instruction actually happens. This is also the more faithful
    reading of what P(T) means: the probability of acquiring the skill at an
    opportunity to learn it, not at an opportunity to be tested on it.
    """
    params = params.sanitised()
    guess, slip = effective_params(params, evidence)

    post = posterior(p, evidence, guess, slip)
    # Forgetting still applies: time passed, and the state may have decayed.
    post = _clamp(post * (1 - params.forget), _P_MIN, _P_MAX)

    return TraceResult(
        p_mastery=post,
        p_previous=p,
        delta=post - p,
        effective_guess=guess,
        effective_slip=slip,
        predicted_correct=predict_correct(post, params),
    )


def apply_instruction(p: float, params: BKTParams, *, intensity: float = 1.0) -> float:
    """The BKT learning transition, applied where learning actually occurs.

    ``intensity`` scales the transition by how substantial the teaching was — a
    full calibrated explanation counts for more than a one-line Socratic nudge.
    It is not a free ride: this raises the *estimate*, and the next observation
    is perfectly capable of pulling it straight back down.
    """
    params = params.sanitised()
    rate = params.learn * _clamp(intensity, 0.0, 1.0)
    return _clamp(p + (1 - p) * rate, _P_MIN, _P_MAX)


def decay(p: float, last_seen: datetime | None, *, now: datetime | None = None) -> float:
    """Exponential forgetting between sessions.

    ``p ← floor + (p − floor)·2^(−Δdays / half_life)``

    The floor exists because you never fully un-learn something you once
    understood — relearning is faster than first learning, and modelling decay
    to zero would make the tutor re-teach from scratch and insult the learner.
    """
    if last_seen is None:
        return p
    now = now or datetime.now(UTC)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)

    elapsed_days = max((now - last_seen).total_seconds() / 86_400.0, 0.0)
    if elapsed_days <= 0:
        return p

    floor = settings.mastery_floor
    retention = math.pow(2.0, -elapsed_days / max(settings.mastery_half_life_days, 0.5))
    return _clamp(floor + (p - floor) * retention, floor, _P_MAX)


def seed_prior(params: BKTParams, prior_estimate: float) -> BKTParams:
    """Seed the prior from the Prior-Belief Gate.

    This is the whole point of eliciting before teaching: a learner who arrives
    with a partly-correct model does not start at the population prior. It is
    also why the elicitation is not a UX flourish — it is a measurement.
    """
    return replace(params, prior=_clamp(prior_estimate, 0.02, 0.75))


__all__ = [
    "BKTParams",
    "Evidence",
    "TraceResult",
    "apply_instruction",
    "decay",
    "effective_params",
    "posterior",
    "predict_correct",
    "seed_prior",
    "update",
]
