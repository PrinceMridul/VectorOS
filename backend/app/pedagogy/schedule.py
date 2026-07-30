"""Spaced repetition, driven by the mastery model rather than a card deck.

Conventional SRS schedules *items*. VectorOS schedules *knowledge components*,
and it derives the interval from the same BKT state that gates progression — so
review is not a separate feature bolted on, it is the forgetting term of the
model made actionable.

The target is to surface a concept when predicted retention crosses ~0.85, i.e.
just *before* it decays. Reviewing earlier wastes the learner's time (the most
valuable thing they have); reviewing later means relearning from scratch.

Interleaving matters as much as spacing: a review queue that serves three
questions on the same concept in a row is massed practice wearing a costume.
:func:`build_review_queue` therefore alternates across nodes.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import settings

#: Retention level at which we want the learner to see the concept again.
REVIEW_TRIGGER_RETENTION = 0.85

MIN_INTERVAL_DAYS = 0.5
MAX_INTERVAL_DAYS = 180.0


@dataclass(frozen=True, slots=True)
class ReviewPlan:
    due_at: datetime
    interval_days: float
    ease: float
    reason: str


def next_interval(
    *,
    mastery: float,
    previous_interval_days: float,
    ease: float,
    was_correct: bool,
    quadrant_is_blind_spot: bool = False,
) -> tuple[float, float]:
    """Return ``(interval_days, ease)``.

    Ease adapts like SM-2, but two VectorOS-specific rules apply:

    * A **blind spot** (wrong while confident) collapses the interval to same-day.
      A confidently-wrong model is actively harmful and rehearses itself.
    * The interval is additionally bounded by the *decay* implied by current
      mastery, so a shaky concept cannot be pushed far out by a lucky streak.
    """
    if quadrant_is_blind_spot:
        return MIN_INTERVAL_DAYS, max(1.3, ease - 0.35)

    if not was_correct:
        return MIN_INTERVAL_DAYS, max(1.3, ease - 0.2)

    ease = min(2.9, ease + 0.1)
    interval = max(previous_interval_days, MIN_INTERVAL_DAYS) * ease

    # Ceiling implied by the forgetting curve: the number of days until this
    # mastery level decays to the review trigger.
    floor = settings.mastery_floor
    if mastery > floor:
        target = max(REVIEW_TRIGGER_RETENTION * mastery, floor + 1e-3)
        ratio = (target - floor) / (mastery - floor)
        decay_bound = -settings.mastery_half_life_days * math.log2(max(ratio, 1e-6))
        interval = min(interval, max(decay_bound, MIN_INTERVAL_DAYS))

    return min(interval, MAX_INTERVAL_DAYS), ease


def plan_review(
    *,
    mastery: float,
    previous_interval_days: float,
    ease: float,
    was_correct: bool,
    quadrant_is_blind_spot: bool = False,
    now: datetime | None = None,
) -> ReviewPlan:
    now = now or datetime.now(UTC)
    interval, new_ease = next_interval(
        mastery=mastery,
        previous_interval_days=previous_interval_days,
        ease=ease,
        was_correct=was_correct,
        quadrant_is_blind_spot=quadrant_is_blind_spot,
    )

    if quadrant_is_blind_spot:
        reason = "Confidently wrong — this needs revisiting today, before it sets."
    elif not was_correct:
        reason = "Missed — scheduling a short-interval retry."
    else:
        reason = f"On track — next retrieval in {interval:.1f} days, just before it fades."

    return ReviewPlan(
        due_at=now + timedelta(days=interval),
        interval_days=round(interval, 2),
        ease=round(new_ease, 3),
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class ReviewItem:
    node_id: Hashable
    """Only ever compared for equality, so callers may key by UUID or by the
    string form they already hold. Demanding a UUID here forced casts at every
    call site and bought nothing."""

    due_at: datetime
    mastery: float
    urgency: float


def build_review_queue(items: Sequence[ReviewItem], *, limit: int = 8) -> list[ReviewItem]:
    """Order the queue by urgency, then **interleave** across concepts.

    Massed repetition of one node feels productive and is not: interleaving
    forces discrimination between concepts and is what makes knowledge
    transferable rather than cue-bound.
    """
    ranked = sorted(items, key=lambda i: (-i.urgency, i.due_at))

    interleaved: list[ReviewItem] = []
    seen_last: Hashable = None
    pool = list(ranked)
    while pool and len(interleaved) < limit:
        pick = next((i for i in pool if i.node_id != seen_last), pool[0])
        pool.remove(pick)
        interleaved.append(pick)
        seen_last = pick.node_id
    return interleaved


def urgency(*, mastery: float, due_at: datetime | None, now: datetime | None = None) -> float:
    """How badly this needs review right now.

    Overdue *and* fragile ranks highest. A concept at 0.9 mastery that is one day
    overdue is less urgent than one at 0.6 that is one day overdue.
    """
    if due_at is None:
        return 0.0
    now = now or datetime.now(UTC)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)

    overdue_days = (now - due_at).total_seconds() / 86_400.0
    if overdue_days < 0:
        return 0.0
    fragility = 1.0 - max(0.0, min(1.0, mastery))
    return round(min(overdue_days, 30.0) * (0.4 + fragility), 3)


__all__ = [
    "MAX_INTERVAL_DAYS",
    "MIN_INTERVAL_DAYS",
    "REVIEW_TRIGGER_RETENTION",
    "ReviewItem",
    "ReviewPlan",
    "build_review_queue",
    "next_interval",
    "plan_review",
    "urgency",
]
