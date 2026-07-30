"""The offline provider.

This is not a stub. It is a deliberate product decision: **the entire tutoring
loop must run with no API key, no network and no cost.** That buys three things
a startup actually needs —

* every pedagogical invariant is testable deterministically (you cannot write a
  regression test for scaffolding collapse against a stochastic endpoint),
* a new engineer clones the repo and has a working tutor in one command, and
* the demo cannot fail on stage because of someone else's rate limit.

It works by *reading the same structured context the real agents get* — the
node's canonical model, its misconception bank, the learner's actual text — and
computing over it lexically. So the offline tutor genuinely responds to what the
learner wrote: it detects real misconceptions from the bank, scores real recall
coverage, and refuses answer demands. The language is flatter than a frontier
model's. The pedagogy is identical, which is the point.
"""

from __future__ import annotations

import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.agents.schemas import (
    AttemptEvaluation,
    ChallengeDraft,
    CoachMove,
    InstructionDraft,
    IntentClassification,
    MentalModelDiagnosis,
    MisconceptionItem,
    ReflectionScore,
    SynthesisDraft,
)
from app.core.config import settings
from app.core.text import (
    content_words,
    coverage,
    hashed_embedding,
    keyphrases,
    missing_concepts,
    truncate,
)
from app.domain.enums import BloomLevel, Intent, Severity
from app.llm.base import ChatRequest, ChatResponse, LLMProvider

T = TypeVar("T", bound=BaseModel)

# Learners ask for the answer in remarkably consistent ways.
_ANSWER_DEMAND = re.compile(
    r"\b(just (tell|give|show)|give me the (answer|solution|code)|what'?s the answer|"
    r"tell me the answer|solve (it|this) for me|stop asking|do it for me|"
    r"i don'?t want to (think|try)|skip (this|it)|answer it)\b",
    re.IGNORECASE,
)
_ADVERSARIAL = re.compile(
    r"\b(ignore (all |your )?(previous|prior) instructions|you are now|disregard your|"
    r"system prompt|jailbreak|pretend you are|act as (an? )?(unrestricted|normal))\b",
    re.IGNORECASE,
)
_META = re.compile(
    r"\b(why (won'?t|can'?t) you|why do you keep asking|this is (annoying|frustrating)|"
    r"stop (being|with) the socratic)\b",
    re.IGNORECASE,
)


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        last = request.messages[-1].content if request.messages else ""
        if request.meta.get("kind") == "refusal_pivot":
            text = _refusal(request.meta)
        else:
            text = truncate(last, 400)
        return ChatResponse(
            text=text,
            model="mock-prose",
            tokens_in=len(content_words(request.system + last)),
            tokens_out=len(content_words(text)),
            provider=self.name,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [hashed_embedding(t, settings.embedding_dim) for t in texts]

    async def structured(self, request: ChatRequest, schema: type[T]) -> tuple[T, ChatResponse]:
        handler = _HANDLERS.get(schema.__name__)
        if handler is None:  # pragma: no cover - every agent schema is registered
            return schema(), _response(schema.__name__)
        # Read the learner's words from the structured field, never from the
        # prompt: the prompt also carries the expert model, and scraping it would
        # diagnose the curriculum rather than the person.
        learner_text = request.meta.get("learner_text")
        if learner_text is None:
            learner_text = _learner_text(request)
        result = handler(request.meta, learner_text)
        return result, _response(schema.__name__)  # type: ignore[return-value]


def _response(schema_name: str) -> ChatResponse:
    return ChatResponse(
        text=f"<structured:{schema_name}>",
        model="mock-structured",
        tokens_in=0,
        tokens_out=0,
        provider="mock",
    )


def _learner_text(request: ChatRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content
    return ""


def _node(meta: dict[str, Any]) -> dict[str, Any]:
    return meta.get("node") or {}


# ─────────────────────────────────────────────────────────────────────────────
# Handlers — one per agent contract
# ─────────────────────────────────────────────────────────────────────────────


def _classify_intent(meta: dict[str, Any], text: str) -> IntentClassification:
    if _ADVERSARIAL.search(text):
        return IntentClassification(
            intent=Intent.ANSWER_DEMAND, adversarial=True, reasoning="Prompt-injection pattern."
        )
    if _ANSWER_DEMAND.search(text):
        return IntentClassification(
            intent=Intent.ANSWER_DEMAND, reasoning="Explicit request for the solution."
        )
    if _META.search(text):
        return IntentClassification(intent=Intent.META, reasoning="Question about the method.")
    if meta.get("expecting") == "reflection":
        return IntentClassification(intent=Intent.REFLECTION, reasoning="At the reflection gate.")
    if text.strip().endswith("?") and len(content_words(text)) < 25:
        return IntentClassification(intent=Intent.QUESTION, reasoning="Short interrogative.")
    if not text.strip():
        return IntentClassification(intent=Intent.OFF_TOPIC, reasoning="Empty input.")
    return IntentClassification(intent=Intent.ATTEMPT, reasoning="Substantive content.")


#: Words that invert a trigger. "a proxy, *not* accuracy" states the correction.
_NEGATION = re.compile(
    r"\b(not|isn'?t|is n'?t|aren'?t|never|no|rather than|instead of|unlike|"
    r"as opposed to|doesn'?t|does not|don'?t|differs? from|unrelated to)\b",
    re.IGNORECASE,
)
_NEGATION_WINDOW = 60


def _triggered(text: str, trigger: str) -> bool:
    """Is the trigger present *and not being contradicted*?

    The naive version of this caused a real bug: a learner writing "it is a
    differentiable proxy, not accuracy" — which is exactly the correct model —
    was flagged as holding the belief that loss *is* accuracy, and had their
    mastery capped for saying the right thing. Naming a concept is not the same
    as believing it, and a diagnostic that cannot tell the difference punishes
    precisely the learners who are articulating a correction.
    """
    lowered = text.lower()
    for match in re.finditer(re.escape(trigger.lower()), lowered):
        window = lowered[max(0, match.start() - _NEGATION_WINDOW) : match.start()]
        if _NEGATION.search(window):
            continue
        return True
    return False


def _match_bank(node: dict[str, Any], text: str) -> list[MisconceptionItem]:
    """Detect known wrong models by lexical trigger.

    The bank is authored per node, so this is genuine classification against a
    curriculum rather than free association — the same job the frontier model
    does, with a blunter instrument. It is deliberately biased toward *missing* a
    misconception rather than inventing one: a false positive writes a gap into
    the learner's permanent record and caps their mastery, which is a far more
    expensive mistake than a miss the next attempt will catch.
    """
    found: list[MisconceptionItem] = []
    haystack = set(content_words(text))

    for entry in node.get("misconception_bank", []):
        # If they have articulated the correction, they do not hold the claim.
        if coverage(entry.get("canonical", ""), text) >= 0.45:
            continue

        triggers = [t for t in entry.get("triggers", []) if t]
        if any(_triggered(text, trigger) for trigger in triggers):
            found.append(_to_item(entry))
            continue

        # Fallback: near-verbatim restatement of the claim. Requires a
        # distinctive claim, or short claims match almost anything.
        claim_words = set(content_words(entry.get("claim", "")))
        if len(claim_words) >= 4 and len(claim_words & haystack) / len(claim_words) >= 0.8:
            found.append(_to_item(entry))

    return found[:3]


def _to_item(entry: dict[str, Any]) -> MisconceptionItem:
    return MisconceptionItem(
        claim=entry.get("claim", ""),
        canonical=entry.get("canonical", ""),
        severity=Severity(entry.get("severity", "medium")),
    )


def _anchors(node: dict[str, Any], text: str, misconceptions: list[MisconceptionItem]) -> list[str]:
    """What the learner genuinely had right, in their own words.

    Anchoring is powerful precisely because the learner trusts it — the Teacher
    opens with "start from what you already had right" — so a false anchor
    actively reinforces a wrong belief. This has to be conservative twice over:

    * drop any clause carrying the vocabulary of a detected misconception, and
    * drop any clause containing the *trigger phrase* that fired one.

    The second rule is not redundant. "You want it as low as possible" shares no
    words with the claim "a lower loss always means a better model", yet it is
    the exact phrase that identified it — so a claim-word check alone happily
    quoted the misconception back as an achievement.

    Returning nothing is a valid and honest answer.
    """
    canonical_terms = set(keyphrases(node.get("canonical_model", ""), limit=20))
    contaminated = {word for m in misconceptions for word in content_words(m.claim)}

    detected = {m.claim for m in misconceptions}
    triggers = [
        trigger.lower()
        for entry in node.get("misconception_bank", [])
        if entry.get("claim") in detected
        for trigger in entry.get("triggers", [])
        if trigger
    ]

    found: list[str] = []
    for clause in re.split(r"[.;,:]|\band\b|\bbut\b|\bso\b", text):
        clause = clause.strip()
        lowered = clause.lower()
        words = set(content_words(clause))
        if len(words) < 2 or not (words & canonical_terms) or (words & contaminated):
            continue
        if any(trigger in lowered for trigger in triggers):
            continue
        phrase = truncate(clause, 80)
        if phrase not in found:
            found.append(phrase)
    return found[:3]


def _diagnose(meta: dict[str, Any], text: str) -> MentalModelDiagnosis:
    node = _node(meta)
    canonical = node.get("canonical_model", "")
    cover = coverage(canonical, text)
    misconceptions = _match_bank(node, text)
    anchors = _anchors(node, text, misconceptions)

    words = len(content_words(text))
    if words < 4:
        prior, bloom = 0.05, BloomLevel.REMEMBER
    else:
        penalty = 0.12 * sum(m.severity.weight for m in misconceptions)
        prior = max(0.03, min(0.75, cover * 0.85 - penalty))
        bloom = (
            BloomLevel.APPLY
            if cover > 0.5 and words > 40
            else BloomLevel.UNDERSTAND
            if cover > 0.25
            else BloomLevel.REMEMBER
        )

    return MentalModelDiagnosis(
        prior_estimate=round(prior, 3),
        anchors=anchors,
        misconceptions=misconceptions,
        missing=missing_concepts(canonical, text),
        bloom_reached=bloom,
        vocabulary_tier=3 if words > 60 else 2 if words > 15 else 1,
        reasoning=f"Lexical coverage of canonical model {cover:.2f} over {words} content words.",
    )


def _instruct(meta: dict[str, Any], text: str) -> InstructionDraft:
    node = _node(meta)
    diagnosis = meta.get("diagnosis") or {}
    anchors: list[str] = diagnosis.get("anchors", [])
    misconceptions: list[dict[str, Any]] = diagnosis.get("misconceptions", [])
    chunks: list[dict[str, str]] = meta.get("chunks", [])

    parts: list[str] = []
    if anchors:
        parts.append(f"Start from what you already had right: {anchors[0]} That part holds.")
    else:
        parts.append(
            f"Let's build {node.get('title', 'this concept')} from the ground up — "
            "your description gave me a clear picture of where to start."
        )

    if misconceptions:
        first = misconceptions[0]
        parts.append(
            f'One thing to re-examine: you treated it as "{first.get("claim", "")}". '
            f"{first.get('canonical', '')}"
        )

    if chunks:
        parts.append(chunks[0]["text"].strip())

    parts.append(
        "I am deliberately stopping here rather than finishing the picture — "
        "the next part is yours to work out."
    )

    return InstructionDraft(
        message="\n\n".join(parts),
        citations=[c["id"] for c in chunks[:2]],
        addressed_misconceptions=[m.get("claim", "") for m in misconceptions],
        withheld=node.get("probe_seeds", [])[:1],
    )


def _challenge(meta: dict[str, Any], text: str) -> ChallengeDraft:
    node = _node(meta)
    difficulty = float(meta.get("difficulty", node.get("difficulty", 0.5)))
    seeds: list[str] = node.get("challenge_seeds") or node.get("probe_seeds") or []
    index = min(int(difficulty * len(seeds)), len(seeds) - 1) if seeds else -1

    prompt = (
        seeds[index]
        if index >= 0
        else f"Work through a case where {node.get('title', 'this idea')} decides the outcome, "
        "and show your reasoning step by step."
    )
    return ChallengeDraft(
        prompt=prompt,
        acceptance_criteria=keyphrases(node.get("canonical_model", ""), limit=5),
        expected_reasoning=node.get("canonical_model", ""),
        bloom=BloomLevel(meta.get("bloom", BloomLevel.APPLY)),
    )


def _evaluate(meta: dict[str, Any], text: str) -> AttemptEvaluation:
    node = _node(meta)
    criteria: list[str] = meta.get("acceptance_criteria") or keyphrases(
        node.get("canonical_model", ""), limit=5
    )
    haystack = set(content_words(text))
    hits = sum(1 for c in criteria if c in haystack)
    criteria_score = hits / len(criteria) if criteria else 0.0

    # Two independent readings: did they hit the specific criteria, and did they
    # reconstruct the model at all. Taking the max means a strong answer phrased
    # differently from the key is not punished for word choice — grading the
    # reasoning, not the string, is the whole point of the Examiner.
    correctness = max(criteria_score, coverage(node.get("canonical_model", ""), text))

    misconceptions = _match_bank(node, text)
    if misconceptions:
        correctness = min(correctness, 0.4)

    if len(content_words(text)) < 3:
        correctness = 0.0
        error_type = "incomplete"
    elif misconceptions:
        error_type = "misconception"
    elif correctness >= 0.85:
        error_type = "none"
    elif correctness >= 0.5:
        error_type = "incomplete"
    else:
        error_type = "prerequisite_gap"

    active: list[str] = meta.get("active_misconceptions", [])
    still_present = {m.claim for m in misconceptions}
    resolved = (
        [claim for claim in active if claim not in still_present] if correctness >= 0.7 else []
    )

    return AttemptEvaluation(
        correctness=round(min(1.0, correctness), 3),
        error_type=error_type,
        anchors=[c for c in criteria if c in haystack][:3],
        misconceptions=misconceptions,
        resolved_misconceptions=resolved,
        reasoning_trace=f"Matched {hits}/{len(criteria) or 1} acceptance criteria.",
    )


def _coach(meta: dict[str, Any], text: str) -> CoachMove:
    node = _node(meta)
    level = int(meta.get("scaffold_level", 1))
    seeds: list[str] = node.get("probe_seeds", [])
    evaluation = meta.get("evaluation") or {}
    misconceptions: list[dict[str, Any]] = evaluation.get("misconceptions", [])

    correctness = float(evaluation.get("correctness", 0.0))

    if level <= 1:
        # Near-miss and wrong model need different moves at the same rung: one is
        # a nudge to finish, the other a nudge to re-examine.
        if correctness >= 0.5:
            message = "You have most of this — which part of it are you least sure about?"
        elif seeds:
            message = seeds[0]
        else:
            message = "Which step in what you just wrote are you least sure about?"
    elif level == 2:
        if misconceptions:
            claim = misconceptions[0].get("claim", "")
            message = (
                f"You are leaning on the idea that {claim} — "
                "what would happen if that were not true?"
            )
        else:
            message = (
                seeds[min(1, len(seeds) - 1)]
                if seeds
                else "Where does your reasoning first assume something you have not checked?"
            )
    elif level == 3:
        message = (
            f"The principle you need here is the one behind {node.get('title', 'this concept')}: "
            f"{truncate(node.get('one_liner', ''), 160)} Apply it to your own case."
        )
    else:
        # Rung 4 works an *analogous* case, never the learner's own.
        analogue = truncate(node.get("one_liner", ""), 220)
        message = (
            f"Here is the same structure in a different setting. {analogue} "
            "Now run the same moves on your own problem."
        )

    return CoachMove(
        message=message,
        targets=misconceptions[0].get("claim", "") if misconceptions else "unverified assumption",
    )


def _score_reflection(meta: dict[str, Any], text: str) -> ReflectionScore:
    canonical = _node(meta).get("canonical_model", "")
    cover = coverage(canonical, text)
    omissions = missing_concepts(canonical, text, limit=4)
    if cover >= settings.reflection_pass_threshold:
        feedback = "You reconstructed the core of it from memory — that is the real test."
    elif omissions:
        # Point at the gap; do not re-teach it. The gap is the next thing they
        # will work on, and handing it over now would spend it for nothing.
        pointers = "; ".join(o.rstrip(".") for o in omissions[:2])
        feedback = f"Close, but two things did not surface: {pointers}."
    else:
        feedback = "Say more — a summary this short does not exercise recall."
    return ReflectionScore(coverage=cover, omissions=omissions, feedback=feedback)


def _refusal(meta: dict[str, Any]) -> str:
    """Refusal & Pivot, offline.

    Escalates the *foothold*, not the lecture: asking twice gets you an easier
    question, never a repeat of the policy. Repeating a refusal is how a learner
    becomes an adversary of the tutor.
    """
    node = _node(meta)
    seeds: list[str] = node.get("probe_seeds", [])
    attempts = int(meta.get("offload_attempts", 0))
    index = min(attempts, max(len(seeds) - 1, 0))
    foothold = (
        seeds[index]
        if seeds
        else f"What is the very first thing you would check about {node.get('title', 'this')}?"
    )
    opener = (
        "Not yet — you have more of this than you think."
        if attempts == 0
        else "Still no, and I will make it smaller instead."
    )
    return f"{opener} Handing it over now would cost you the part that actually sticks. {foothold}"


def _synthesise(meta: dict[str, Any], text: str) -> SynthesisDraft:
    parts = [p for p in meta.get("parts", []) if p]
    return SynthesisDraft(message="\n\n".join(parts) if parts else text)


_HANDLERS: dict[str, Any] = {
    "IntentClassification": _classify_intent,
    "MentalModelDiagnosis": _diagnose,
    "InstructionDraft": _instruct,
    "ChallengeDraft": _challenge,
    "AttemptEvaluation": _evaluate,
    "CoachMove": _coach,
    "ReflectionScore": _score_reflection,
    "SynthesisDraft": _synthesise,
}


__all__ = ["MockProvider"]
