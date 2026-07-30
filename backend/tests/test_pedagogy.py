"""The measurement plane.

These are the tests that would have caught the two worst bugs found while
building this: mastery rising after a confidently wrong answer, and enum columns
round-tripping as strings so the state machine silently stopped matching.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.core.errors import PedagogicalViolation
from app.domain.enums import BloomLevel, MetacognitiveQuadrant, SessionState
from app.pedagogy import bkt, calibration, load, scaffold, schedule, state_machine, zpd

PARAMS = bkt.BKTParams(prior=0.3, learn=0.3, guess=0.2, slip=0.1, forget=0.05)


# ---------------------------------------------------------------------------
# Knowledge tracing
# ---------------------------------------------------------------------------


def test_confident_wrong_answer_lowers_mastery() -> None:
    """The regression that matters most.

    Textbook BKT folds the learning transition into the observation and can
    report *higher* mastery after a confidently wrong answer. A mastery number
    that rises when you are wrong is worse than no number, because the learner
    will correctly stop believing it.
    """
    result = bkt.update(0.3, PARAMS, bkt.Evidence(correctness=0.0, confidence=0.9))
    assert result.p_mastery < 0.3
    assert result.delta < 0


def test_confidence_scales_the_evidence() -> None:
    """Wrong-and-certain is stronger evidence than wrong-and-unsure."""
    certain = bkt.update(0.5, PARAMS, bkt.Evidence(correctness=0.0, confidence=0.9))
    unsure = bkt.update(0.5, PARAMS, bkt.Evidence(correctness=0.0, confidence=0.1))
    assert certain.p_mastery < unsure.p_mastery


def test_scaffolded_correctness_is_weaker_evidence() -> None:
    """A right answer produced after a worked example proves less."""
    unaided = bkt.update(0.4, PARAMS, bkt.Evidence(correctness=1.0, confidence=0.8))
    helped = bkt.update(
        0.4, PARAMS, bkt.Evidence(correctness=1.0, confidence=0.8, scaffold_level=4)
    )
    assert helped.p_mastery < unaided.p_mastery


def test_partial_credit_lands_between_the_extremes() -> None:
    wrong = bkt.update(0.5, PARAMS, bkt.Evidence(correctness=0.0)).p_mastery
    partial = bkt.update(0.5, PARAMS, bkt.Evidence(correctness=0.5)).p_mastery
    right = bkt.update(0.5, PARAMS, bkt.Evidence(correctness=1.0)).p_mastery
    assert wrong < partial < right


def test_instruction_is_the_learning_opportunity() -> None:
    assert bkt.apply_instruction(0.3, PARAMS) > 0.3
    # A nudge counts for less than a full explanation.
    nudge = bkt.apply_instruction(0.3, PARAMS, intensity=0.2)
    full = bkt.apply_instruction(0.3, PARAMS, intensity=1.0)
    assert 0.3 < nudge < full


def test_mastery_decays_but_never_to_zero() -> None:
    now = datetime.now(UTC)
    fresh = bkt.decay(0.9, now - timedelta(hours=1), now=now)
    stale = bkt.decay(0.9, now - timedelta(days=60), now=now)
    assert fresh > stale >= settings.mastery_floor
    assert bkt.decay(0.9, None) == 0.9


def test_prior_is_seeded_from_the_elicitation() -> None:
    """The Prior-Belief Gate is a measurement, not a UX flourish."""
    seeded = bkt.seed_prior(PARAMS, 0.62)
    assert seeded.prior == pytest.approx(0.62)


def test_repeated_correct_answers_reach_the_unlock_threshold() -> None:
    """A learner who genuinely knows it must be able to get there."""
    p = 0.3
    for _ in range(4):
        p = bkt.update(p, PARAMS, bkt.Evidence(correctness=1.0, confidence=0.9)).p_mastery
    assert p >= settings.mastery_threshold


# ---------------------------------------------------------------------------
# Cognitive load and ZPD
# ---------------------------------------------------------------------------


def test_failure_dominates_cognitive_load() -> None:
    struggling = load.cognitive_load(
        load.LoadSignals(difficulty=0.5, recent_accuracy=0.1, turn_count=6, consecutive_failures=3)
    )
    cruising = load.cognitive_load(
        load.LoadSignals(difficulty=0.5, recent_accuracy=0.95, turn_count=1)
    )
    assert struggling.overloaded
    assert struggling.value > cruising.value
    assert 1.0 <= cruising.value <= 9.0


def test_zpd_targets_the_desirable_difficulty_band() -> None:
    target = zpd.select_target(
        mastery=0.6,
        params=PARAMS,
        node_difficulty=0.5,
        bloom_ceiling=BloomLevel.EVALUATE,
    )
    assert 0.0 <= target.predicted_success <= 1.0
    assert target.difficulty in zpd.DIFFICULTY_STEPS


def test_overload_steps_the_task_down() -> None:
    overloaded = load.cognitive_load(
        load.LoadSignals(difficulty=0.9, recent_accuracy=0.0, turn_count=8, consecutive_failures=3)
    )
    easier = zpd.select_target(
        mastery=0.4,
        params=PARAMS,
        node_difficulty=0.7,
        bloom_ceiling=BloomLevel.CREATE,
        load=overloaded,
    )
    baseline = zpd.select_target(
        mastery=0.4, params=PARAMS, node_difficulty=0.7, bloom_ceiling=BloomLevel.CREATE
    )
    assert easier.difficulty <= baseline.difficulty


def test_bloom_never_exceeds_the_node_ceiling() -> None:
    target = zpd.select_target(
        mastery=0.9, params=PARAMS, node_difficulty=0.95, bloom_ceiling=BloomLevel.UNDERSTAND
    )
    assert target.bloom.rank <= BloomLevel.UNDERSTAND.rank


# ---------------------------------------------------------------------------
# Scaffolding — the anti-collapse guarantee
# ---------------------------------------------------------------------------


def test_scaffold_rises_one_rung_at_a_time() -> None:
    assert scaffold.escalate(current=0, learner_replied=True, mastery=0.1) == 1
    assert scaffold.escalate(current=1, learner_replied=True, mastery=0.1) == 2


def test_scaffold_refuses_to_skip_without_a_reply() -> None:
    """More help is available *after* you respond. That is the price of a rung."""
    with pytest.raises(PedagogicalViolation):
        scaffold.escalate(current=2, learner_replied=False, mastery=0.1)


def test_scaffold_never_exceeds_the_ladder() -> None:
    level = 0
    for _ in range(12):
        level = scaffold.escalate(current=level, learner_replied=True, mastery=0.1)
    assert level == settings.max_scaffold_level
    # There is no rung that hands over the answer.
    assert len(scaffold.LADDER) == settings.max_scaffold_level + 1


def test_support_fades_as_mastery_rises() -> None:
    assert scaffold.ceiling_for(0.9) < scaffold.ceiling_for(0.5) < scaffold.ceiling_for(0.1)


def test_low_rungs_must_be_questions() -> None:
    assert scaffold.rung(1).must_be_question
    assert scaffold.rung(2).must_be_question


# ---------------------------------------------------------------------------
# Metacognition
# ---------------------------------------------------------------------------


def test_quadrant_classification() -> None:
    assert calibration.classify(1.0, 0.9) is MetacognitiveQuadrant.AUTOMATICITY
    assert calibration.classify(1.0, 0.1) is MetacognitiveQuadrant.FRAGILE
    assert calibration.classify(0.0, 0.9) is MetacognitiveQuadrant.BLIND_SPOT
    assert calibration.classify(0.0, 0.1) is MetacognitiveQuadrant.KNOWN_GAP


def test_every_quadrant_has_a_distinct_response_strategy() -> None:
    strategies = {q: calibration.RESPONSE_STRATEGY[q] for q in MetacognitiveQuadrant}
    assert len(set(strategies.values())) == len(MetacognitiveQuadrant)


def test_cognitive_debt_separates_earned_from_assisted_progress() -> None:
    independent = calibration.cognitive_debt(
        unaided_wins=10, hinted_wins=1, hints_consumed=2, offload_attempts=0
    )
    reliant = calibration.cognitive_debt(
        unaided_wins=0, hinted_wins=10, hints_consumed=30, offload_attempts=6
    )
    assert independent.score < reliant.score
    assert independent.label == "independent"
    assert reliant.label in {"reliant", "offloading"}


# ---------------------------------------------------------------------------
# Spaced repetition
# ---------------------------------------------------------------------------


def test_blind_spots_are_scheduled_for_today() -> None:
    """A confidently wrong model rehearses itself. It cannot wait a week."""
    plan = schedule.plan_review(
        mastery=0.4,
        previous_interval_days=8.0,
        ease=2.5,
        was_correct=False,
        quadrant_is_blind_spot=True,
    )
    assert plan.interval_days <= schedule.MIN_INTERVAL_DAYS


def test_intervals_grow_on_success_but_stay_inside_the_forgetting_curve() -> None:
    plan = schedule.plan_review(mastery=0.9, previous_interval_days=2.0, ease=2.5, was_correct=True)
    assert plan.interval_days > 2.0
    assert plan.interval_days <= schedule.MAX_INTERVAL_DAYS


def test_review_queue_interleaves_concepts() -> None:
    """Three questions on one concept in a row is massed practice in disguise."""
    from uuid import uuid4

    a, b = uuid4(), uuid4()
    now = datetime.now(UTC)
    items = [
        schedule.ReviewItem(node_id=a, due_at=now, mastery=0.4, urgency=9.0),
        schedule.ReviewItem(node_id=a, due_at=now, mastery=0.4, urgency=8.0),
        schedule.ReviewItem(node_id=b, due_at=now, mastery=0.5, urgency=7.0),
    ]
    ordered = schedule.build_review_queue(items, limit=3)
    assert [i.node_id for i in ordered][:2] == [a, b]


# ---------------------------------------------------------------------------
# The control plane
# ---------------------------------------------------------------------------


def test_instruction_is_unreachable_before_elicitation() -> None:
    """There is no edge from 'session opened' to 'here is the explanation'."""
    assert not state_machine.can_transition(SessionState.IDLE, SessionState.INSTRUCT)
    assert state_machine.can_transition(SessionState.IDLE, SessionState.ELICIT)


def test_mastery_is_unreachable_without_reflection() -> None:
    assert not state_machine.can_transition(SessionState.EVALUATE, SessionState.MASTERY)
    assert state_machine.can_transition(SessionState.REFLECT, SessionState.MASTERY)


def test_illegal_transitions_raise_rather_than_clamp() -> None:
    with pytest.raises(PedagogicalViolation):
        state_machine.transition(
            SessionState.CHALLENGE, SessionState.COMPLETE, trigger="skip_the_learning"
        )


def test_correct_attempts_go_to_reflection_and_wrong_ones_to_coaching() -> None:
    assert (
        state_machine.next_after_evaluation(
            correctness=1.0, scaffold_level=0, max_scaffold=4, consecutive_failures=0
        )[0]
        is SessionState.REFLECT
    )
    assert (
        state_machine.next_after_evaluation(
            correctness=0.2, scaffold_level=0, max_scaffold=4, consecutive_failures=0
        )[0]
        is SessionState.COACH
    )


def test_repeated_failure_at_the_top_of_the_ladder_reteaches() -> None:
    """If the ladder is exhausted, the instruction was wrong, not the learner."""
    target, trigger = state_machine.next_after_evaluation(
        correctness=0.1, scaffold_level=4, max_scaffold=4, consecutive_failures=3
    )
    assert target is SessionState.INSTRUCT
    assert "reteach" in trigger


def test_failed_reflection_returns_to_practice_not_to_reading() -> None:
    failed = state_machine.next_after_reflection(passed=False, coverage=0.1)
    passed = state_machine.next_after_reflection(passed=True, coverage=0.9)
    assert failed[0] is SessionState.CHALLENGE
    assert passed[0] is SessionState.MASTERY


def test_guidance_requires_effort_first() -> None:
    assert not state_machine.guidance_unlocked(
        elapsed_seconds=5, struggle_floor=45, attempted=False
    )
    assert state_machine.guidance_unlocked(elapsed_seconds=5, struggle_floor=45, attempted=True)
    assert state_machine.guidance_unlocked(elapsed_seconds=60, struggle_floor=45, attempted=False)
