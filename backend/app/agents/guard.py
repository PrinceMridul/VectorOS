"""SocraticGuard — the last line before a token reaches the learner.

Layer three of the anti-collapse defence. The state machine decides *what kind*
of move is legal; the scaffold ladder decides *how much* help is legal; the guard
verifies that the text actually produced obeys both.

It exists because the two upstream layers constrain the model's *situation*, not
its *output*. A Coach correctly placed at rung 1 can still write "the answer is
that the learning rate overshoots" if the learner's message was emotionally
persuasive enough. Nothing in the prompt stack reliably prevents that. A
similarity check against the private grading key does.

Three independent checks, cheapest first:

1. **Lexical** — microseconds, catches the blunt cases.
2. **Criteria overlap** — has the draft simply enumerated the grading key?
3. **Semantic** — cosine against the private ``expected_reasoning``. This is the
   one that catches a *paraphrased* answer, which is the failure mode that
   actually happens in production.

Plus a **move-shape** check: at rungs 1–2 the move must be a question. A "probe"
that ends in a period is an explanation wearing a probe's clothes.

On violation: one bounded regeneration under a stricter contract, then a
deterministic authored probe from the node's ``probe_seeds``. The system degrades
to *asking something sensible*, never to leaking. A tutor that occasionally says
something slightly generic is fine. A tutor that occasionally hands over the
answer is not a tutor.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.core.text import content_words, sentences
from app.db.types import cosine_similarity
from app.domain.enums import GuardVerdict
from app.llm.registry import embedder

log = get_logger(__name__)

_LEAK_PATTERNS = re.compile(
    r"\b(the (correct )?(answer|solution) is|here'?s the (answer|solution)|"
    r"the result is therefore|to solve (this|it),? you|"
    r"in short,? (the answer|it'?s)|so the final answer)\b",
    re.IGNORECASE,
)

#: Rung ≤ this must end in a question mark.
_QUESTION_RUNGS = 2
#: Sentence budget per rung. Verbosity is extraneous load.
_SENTENCE_BUDGET = {0: 2, 1: 2, 2: 2, 3: 3, 4: 8}

_STRICTER = (
    "That draft leaked the solution or broke its move shape. Rewrite it. "
    "You may not state, paraphrase, or strongly imply the conclusion. "
    "Ask the single question that would let the learner reach it themselves."
)


@dataclass(frozen=True, slots=True)
class GuardResult:
    text: str
    verdict: GuardVerdict
    reason: str = ""

    @property
    def clean(self) -> bool:
        return self.verdict is GuardVerdict.PASS


@dataclass(frozen=True, slots=True)
class GuardContext:
    expected_reasoning: str = ""
    """Private grading key for the *active* challenge. The leak target."""
    acceptance_criteria: tuple[str, ...] = ()
    scaffold_level: int = 0
    enforce_question: bool | None = None
    """Override the rung-derived shape rule (e.g. the refusal pivot must ask)."""
    sentence_budget: int | None = None
    """Override the rung-derived length cap. The refusal pivot legitimately needs
    three sentences (acknowledge, reason, foothold) at a rung that allows two."""
    fallback_probe: str = "Which part of your reasoning are you least sure about?"


async def _semantic_leak(draft: str, expected: str) -> float:
    if not expected.strip() or not draft.strip():
        return 0.0
    try:
        vectors = await embedder().embed([draft, expected])
    except Exception as exc:  # noqa: BLE001 - degrade to lexical, never fail open loudly
        log.warning("guard_embedding_unavailable", error=str(exc))
        return 0.0
    if len(vectors) < 2:
        return 0.0
    return cosine_similarity(vectors[0], vectors[1])


def _criteria_overlap(draft: str, criteria: tuple[str, ...]) -> float:
    if not criteria:
        return 0.0
    words = set(content_words(draft))
    hits = sum(1 for c in criteria if all(w in words for w in content_words(c)))
    return hits / len(criteria)


async def _violations(draft: str, ctx: GuardContext) -> list[str]:
    found: list[str] = []

    if _LEAK_PATTERNS.search(draft):
        found.append("lexical_answer_pattern")

    # A rung-4 worked analogy is *meant* to demonstrate the structure, so the
    # criteria bar is relaxed there; the semantic check still applies.
    threshold = 0.9 if ctx.scaffold_level >= 4 else 0.75
    if _criteria_overlap(draft, ctx.acceptance_criteria) >= threshold:
        found.append("acceptance_criteria_enumerated")

    similarity = await _semantic_leak(draft, ctx.expected_reasoning)
    if similarity >= settings.guard_leak_similarity:
        found.append(f"semantic_leak:{similarity:.2f}")

    must_ask = (
        ctx.enforce_question
        if ctx.enforce_question is not None
        else ctx.scaffold_level <= _QUESTION_RUNGS and ctx.scaffold_level > 0
    )
    if must_ask and not draft.rstrip().endswith("?"):
        found.append("move_shape_not_a_question")

    budget = ctx.sentence_budget or _SENTENCE_BUDGET.get(ctx.scaffold_level, 4)
    if len(sentences(draft)) > budget:
        found.append("over_budget")

    return found


async def enforce(
    draft: str,
    ctx: GuardContext,
    *,
    regenerate: Callable[[str], Awaitable[str]] | None = None,
) -> GuardResult:
    problems = await _violations(draft, ctx)
    if not problems:
        return GuardResult(text=draft.strip(), verdict=GuardVerdict.PASS)

    log.warning("guard_violation", problems=problems, scaffold_level=ctx.scaffold_level)

    if regenerate is not None:
        try:
            second = await regenerate(_STRICTER)
        except Exception as exc:  # noqa: BLE001 - fall through to the safe probe
            log.warning("guard_regeneration_failed", error=str(exc))
        else:
            if not await _violations(second, ctx):
                return GuardResult(
                    text=second.strip(),
                    verdict=GuardVerdict.REWRITTEN,
                    reason=",".join(problems),
                )

    return GuardResult(
        text=ctx.fallback_probe,
        verdict=GuardVerdict.FALLBACK,
        reason=",".join(problems),
    )


__all__ = ["GuardContext", "GuardResult", "enforce"]
