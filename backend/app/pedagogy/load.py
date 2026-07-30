"""An interaction-derived cognitive load heuristic (1–9).

Cognitive Load Theory says working memory is the bottleneck, and that the tutor's
job is to keep *intrinsic* load in the productive band while suppressing
*extraneous* load. We cannot read a learner's mind, so we estimate a proxy from
interaction telemetry:

    CL = 0.5 + 1.0·G + 4.5·(1 − A) + 0.1·Q + 1.0·T

    G  task difficulty (0..1)      A  recent accuracy (0..1)
    Q  interaction fatigue          T  task-type weight (recall < apply < create)

IMPORTANT — naming note: the 1–9 range and the general shape of this formula
were inspired by Paas's subjective mental-effort rating scale, but this is
**not** the Paas instrument. Paas (1992) is a self-report question — the
learner rates their own effort after a task. This is a formula computed from
behavioural signals (task difficulty, accuracy, latency, task type) with
coefficients we chose, not fit to any self-report data or validated against
one. An earlier version of this module called it "the Paas scale," which was
inaccurate and has been corrected throughout the codebase. Treat this as an
unvalidated engineering heuristic that happens to share a numeric range and a
theoretical motivation with Paas's work, not as an implementation of it.

The dominant term is ``4.5·(1 − A)`` and that is intentional: nothing loads working
memory like repeatedly failing. Latency folds into ``Q`` from both ends — long
silences suggest overload, rapid-fire retries suggest thrashing. Both are treated
as fatigue, though neither has been validated against a ground-truth load measure.

What the number is *for*: it selects the tutor's next move (see
:mod:`app.pedagogy.scaffold`). High load ⇒ decompose and slow down. Low load with
high mastery ⇒ fade support and escalate. It is never shown to the learner as a
score, because telling someone they are at 7/9 would itself add load — but that
UX argument does not substitute for validating that 7/9 means anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import AttemptKind, BloomLevel

_TASK_TYPE_WEIGHT: dict[BloomLevel, float] = {
    BloomLevel.REMEMBER: 0.2,
    BloomLevel.UNDERSTAND: 0.4,
    BloomLevel.APPLY: 0.6,
    BloomLevel.ANALYZE: 0.8,
    BloomLevel.EVALUATE: 0.9,
    BloomLevel.CREATE: 1.0,
}

#: Beyond this the learner is overloaded: decompose, do not escalate.
OVERLOAD_THRESHOLD = 6.5
#: Below this the task is too easy: fade scaffolding, raise difficulty.
UNDERLOAD_THRESHOLD = 3.0

_FAST_MS = 4_000
_SLOW_MS = 120_000


@dataclass(frozen=True, slots=True)
class LoadSignals:
    difficulty: float
    recent_accuracy: float
    turn_count: int
    bloom: BloomLevel = BloomLevel.APPLY
    latency_ms: int = 0
    consecutive_failures: int = 0


@dataclass(frozen=True, slots=True)
class LoadReading:
    value: float
    """Heuristic load estimate, 1–9, unrounded so the trend is visible over a
    session. See the module docstring — this is not the Paas instrument."""
    overloaded: bool
    underloaded: bool

    @property
    def band(self) -> str:
        if self.overloaded:
            return "overloaded"
        if self.underloaded:
            return "underloaded"
        return "productive"


def _fatigue(turn_count: int, latency_ms: int, consecutive_failures: int) -> float:
    """Interaction fatigue Q.

    Turns accumulate fatigue linearly; latency contributes from *both* tails
    (a two-minute silence and a two-second reflex retry are both bad signs);
    a failure streak is the strongest fatigue signal we have.
    """
    q = float(turn_count)
    if latency_ms >= _SLOW_MS:
        q += 4.0
    elif latency_ms and latency_ms <= _FAST_MS:
        q += 2.0
    q += 3.0 * consecutive_failures
    return q


def cognitive_load(signals: LoadSignals) -> LoadReading:
    difficulty = max(0.0, min(1.0, signals.difficulty))
    accuracy = max(0.0, min(1.0, signals.recent_accuracy))
    q = _fatigue(signals.turn_count, signals.latency_ms, signals.consecutive_failures)
    t = _TASK_TYPE_WEIGHT.get(signals.bloom, 0.6)

    raw = 0.5 + 1.0 * difficulty + 4.5 * (1.0 - accuracy) + 0.1 * q + 1.0 * t
    value = max(1.0, min(9.0, raw))

    return LoadReading(
        value=round(value, 2),
        overloaded=value >= OVERLOAD_THRESHOLD,
        underloaded=value <= UNDERLOAD_THRESHOLD,
    )


def bloom_for_attempt(kind: AttemptKind, node_ceiling: BloomLevel) -> BloomLevel:
    """Which cognitive level an attempt of this kind actually exercises.

    Capped by the node's ceiling so we never assess *create* on a concept the
    learner met four minutes ago.
    """
    target = {
        AttemptKind.PRIOR_BELIEF: BloomLevel.REMEMBER,
        AttemptKind.CHALLENGE: BloomLevel.APPLY,
        AttemptKind.COACH_REPLY: BloomLevel.UNDERSTAND,
        AttemptKind.REFLECTION: BloomLevel.EVALUATE,
    }[kind]
    return target if target.rank <= node_ceiling.rank else node_ceiling


__all__ = [
    "OVERLOAD_THRESHOLD",
    "UNDERLOAD_THRESHOLD",
    "LoadReading",
    "LoadSignals",
    "bloom_for_attempt",
    "cognitive_load",
]
