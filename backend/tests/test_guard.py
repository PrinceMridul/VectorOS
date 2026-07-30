"""SocraticGuard.

The property under test is not "the guard usually works". It is that there is no
path through it that emits the answer. A tutor that leaks 1% of the time trains
learners to keep pushing until it does.
"""

from __future__ import annotations

from app.agents.guard import GuardContext, enforce
from app.domain.enums import GuardVerdict

EXPECTED = (
    "Squared error grows quadratically, so the mistyped outlier dominates the loss "
    "and drags the fitted line toward it."
)
CRITERIA = ("squared error", "outlier", "dominates")
FALLBACK = "Which step are you least sure about?"


def ctx(**overrides: object) -> GuardContext:
    base = {
        "expected_reasoning": EXPECTED,
        "acceptance_criteria": CRITERIA,
        "scaffold_level": 1,
        "fallback_probe": FALLBACK,
    }
    base.update(overrides)
    return GuardContext(**base)  # type: ignore[arg-type]


async def test_a_clean_socratic_probe_passes() -> None:
    result = await enforce("Which part of your reasoning are you least sure about?", ctx())
    assert result.clean
    assert result.verdict is GuardVerdict.PASS


async def test_lexical_answer_patterns_are_caught() -> None:
    result = await enforce(
        "The answer is that the outlier dominates the squared error term.", ctx()
    )
    assert not result.clean
    assert "lexical_answer_pattern" in result.reason


async def test_enumerating_the_grading_key_is_a_leak() -> None:
    """Paraphrasing the criteria back is the failure mode that actually happens."""
    result = await enforce(
        "Consider how squared error behaves, how an outlier behaves, and what dominates.",
        ctx(),
    )
    assert not result.clean


async def test_a_statement_at_a_question_rung_is_rejected() -> None:
    """A 'probe' ending in a full stop is an explanation wearing a probe's clothes."""
    result = await enforce("Think about your loop condition carefully.", ctx(scaffold_level=2))
    assert not result.clean
    assert "move_shape_not_a_question" in result.reason


async def test_verbosity_is_treated_as_cognitive_load() -> None:
    rambling = " ".join(f"Sentence number {i} about the topic?" for i in range(8))
    result = await enforce(rambling, ctx())
    assert not result.clean


async def test_a_violation_degrades_to_an_authored_probe_never_to_a_leak() -> None:
    result = await enforce("The answer is obvious: the outlier dominates.", ctx())
    assert result.verdict is GuardVerdict.FALLBACK
    assert result.text == FALLBACK


async def test_regeneration_is_accepted_when_it_complies() -> None:
    async def regenerate(_: str) -> str:
        return "What happens to the total when one term is squared and large?"

    result = await enforce(
        "The answer is that the outlier dominates.", ctx(), regenerate=regenerate
    )
    assert result.verdict is GuardVerdict.REWRITTEN
    assert result.text.endswith("?")


async def test_a_failing_regeneration_still_cannot_leak() -> None:
    async def regenerate(_: str) -> str:
        return "Here's the solution: the outlier dominates the squared error."

    result = await enforce(
        "The answer is that the outlier dominates.", ctx(), regenerate=regenerate
    )
    assert result.verdict is GuardVerdict.FALLBACK
    assert "outlier dominates" not in result.text


async def test_a_raising_regeneration_still_cannot_leak() -> None:
    async def regenerate(_: str) -> str:
        raise RuntimeError("provider exploded")

    result = await enforce(
        "The answer is that the outlier dominates.", ctx(), regenerate=regenerate
    )
    assert result.verdict is GuardVerdict.FALLBACK
    assert result.text == FALLBACK


async def test_the_worked_analogy_rung_is_allowed_more_room() -> None:
    """Rung 4 demonstrates an analogous case; it needs sentences to do that."""
    long_move = (
        "Take a different case entirely: three people rate a film 4, 4 and 5. "
        "Now one person types 50 by mistake. "
        "The mean moves a long way even though only one value changed. "
        "Run those same three steps on your own problem."
    )
    result = await enforce(long_move, ctx(scaffold_level=4))
    assert result.clean
