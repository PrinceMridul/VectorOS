"""The agents.

Each function is one node in the LangGraph mesh: it takes the shared
:class:`~app.agents.state.TurnState`, makes exactly one bounded decision, and
returns a partial state update. None of them touch the database and none of them
decide what happens next — that is the orchestrator's job. This is what makes the
mesh testable: every agent is a pure ``state -> state`` coroutine.

Latency note: the Teacher and the challenge author both depend only on the
diagnosis, so the graph fans them out concurrently. In a serial mesh the
learner would wait for both; here they wait for the slower one. Past roughly
four seconds a learner disengages, and disengagement is a pedagogical failure,
so parallelism here is a teaching decision, not an optimisation.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.agents import prompts
from app.agents.guard import GuardContext, enforce
from app.agents.schemas import (
    AttemptEvaluation,
    ChallengeDraft,
    CoachMove,
    InstructionDraft,
    IntentClassification,
    MentalModelDiagnosis,
    ReflectionScore,
)
from app.agents.state import TurnState, agent_view
from app.core.logging import get_logger
from app.core.text import truncate
from app.domain.enums import AgentName, GuardVerdict, ModelTier
from app.llm.base import ChatRequest, Message
from app.llm.registry import llm
from app.pedagogy.scaffold import rung

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


async def _ask(
    *,
    agent: AgentName,
    tier: ModelTier,
    system: str,
    user: str,
    schema: type[T],
    meta: dict[str, Any],
    temperature: float = 0.3,
) -> tuple[T, dict[str, Any]]:
    """One structured agent call plus its trace-forest event."""
    request = ChatRequest(
        system=system,
        messages=[Message("user", user)],
        tier=tier,
        temperature=temperature,
        meta=meta,
    )
    parsed, response = await llm().structured(request, schema)
    event = {
        "agent": agent.value,
        "model": response.model,
        "latency_ms": response.latency_ms,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "payload": {"output": parsed.model_dump(mode="json")},
    }
    return parsed, event


def _context_block(state: TurnState, *, allow_private: bool) -> str:
    view = agent_view(state, allow_private=allow_private)
    node = view["node"]
    lines = [
        f"CONCEPT: {node.get('title', '')} — {node.get('one_liner', '')}",
        f"LEARNER MASTERY: {view['mastery']:.2f}",
    ]
    if allow_private and node.get("canonical_model"):
        lines.append(f"EXPERT MODEL (private): {node['canonical_model']}")
    if node.get("misconception_bank"):
        known = "; ".join(m.get("claim", "") for m in node["misconception_bank"][:5])
        lines.append(f"KNOWN MISCONCEPTIONS FOR THIS CONCEPT: {known}")
    if view["active_misconceptions"]:
        lines.append(f"THIS LEARNER'S ACTIVE GAPS: {'; '.join(view['active_misconceptions'])}")
    if view["diagnosis"]:
        diagnosis = view["diagnosis"]
        lines.append(f"DIAGNOSIS — has right: {'; '.join(diagnosis.get('anchors', [])) or '—'}")
        lines.append(f"DIAGNOSIS — missing: {'; '.join(diagnosis.get('missing', [])) or '—'}")
        misconceptions = diagnosis.get("misconceptions", [])
        if misconceptions:
            lines.append(
                "DIAGNOSIS — misconceptions: "
                + "; ".join(m.get("claim", "") for m in misconceptions)
            )
    if view["chunks"]:
        lines.append("RETRIEVED MATERIAL:")
        lines += [f"  [{c['id']}] {truncate(c['text'], 600)}" for c in view["chunks"]]
    if view["challenge"].get("prompt"):
        lines.append(f"ACTIVE CHALLENGE: {view['challenge']['prompt']}")
    if state.get("quadrant_strategy"):
        lines.append(f"RESPONSE STRATEGY: {state['quadrant_strategy']}")
    return "\n".join(lines)


def _meta(state: TurnState, **extra: Any) -> dict[str, Any]:
    """Structured context for the offline provider. Network providers ignore it.

    ``learner_text`` is carried explicitly rather than left for the provider to
    recover from the prompt: the user message also contains the context block
    (including the expert model), and a provider that scraped it would end up
    diagnosing the curriculum instead of the learner.
    """
    return {
        "learner_text": state.get("learner_input", ""),
        "node": state.get("node", {}),
        "chunks": state.get("chunks", []),
        "diagnosis": state.get("diagnosis", {}),
        "evaluation": state.get("evaluation", {}),
        "challenge": state.get("challenge", {}),
        "scaffold_level": state.get("scaffold_level", 0),
        "difficulty": state.get("difficulty", 0.5),
        "bloom": state.get("bloom", "apply"),
        "expecting": state.get("expecting", ""),
        "active_misconceptions": state.get("active_misconceptions", []),
        **extra,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Agents
# ─────────────────────────────────────────────────────────────────────────────


async def route(state: TurnState) -> dict[str, Any]:
    """Classify the learner's move. Hot path, cheapest tier."""
    parsed, event = await _ask(
        agent=AgentName.ROUTER,
        tier=ModelTier.FAST,
        system=prompts.ROUTER,
        user=state.get("learner_input", ""),
        schema=IntentClassification,
        meta=_meta(state),
        temperature=0.0,
    )
    return {"intent": parsed.model_dump(mode="json"), "events": [event]}


async def diagnose(state: TurnState) -> dict[str, Any]:
    """The Prior-Belief Gate. Everything downstream is calibrated from this."""
    parsed, event = await _ask(
        agent=AgentName.EXAMINER,
        tier=ModelTier.BALANCED,
        system=prompts.EXAMINER_DIAGNOSE,
        user=(
            f"{_context_block(state, allow_private=True)}\n\n"
            f"LEARNER'S PRIOR BELIEF (unaided, before any instruction):\n"
            f"{state.get('learner_input', '')}"
        ),
        schema=MentalModelDiagnosis,
        meta=_meta(state),
    )
    payload = parsed.model_dump(mode="json")
    # Downstream nodes in this same turn read `diagnosis`, so publish to both.
    return {"new_diagnosis": payload, "diagnosis": payload, "events": [event]}


async def instruct(state: TurnState) -> dict[str, Any]:
    """Teach — but only what the diagnosis says this person is missing."""
    parsed, event = await _ask(
        agent=AgentName.TEACHER,
        tier=ModelTier.DEEP,
        system=prompts.TEACHER,
        user=(
            f"{_context_block(state, allow_private=True)}\n\n"
            f"VOCABULARY TIER: {state.get('diagnosis', {}).get('vocabulary_tier', 2)}\n"
            "Write the calibrated explanation now. Stop before the final inference."
        ),
        schema=InstructionDraft,
        meta=_meta(state),
        temperature=0.5,
    )
    return {"instruction": parsed.model_dump(mode="json"), "events": [event]}


async def author_challenge(state: TurnState) -> dict[str, Any]:
    """Author a task calibrated to the learner's ZPD."""
    system = prompts.CHALLENGE.format(
        target_success=state.get("target_success", 0.65),
        bloom=state.get("bloom", "apply"),
    )
    parsed, event = await _ask(
        agent=AgentName.EXAMINER,
        tier=ModelTier.BALANCED,
        system=system,
        user=(
            f"{_context_block(state, allow_private=True)}\n\n"
            f"DIFFICULTY: {state.get('difficulty', 0.5):.2f} (0=trivial, 1=expert)\n"
            "Author the challenge now."
        ),
        schema=ChallengeDraft,
        meta=_meta(state),
        temperature=0.6,
    )
    return {"new_challenge": parsed.model_dump(mode="json"), "events": [event]}


async def evaluate(state: TurnState) -> dict[str, Any]:
    """Grade the reasoning, not the string."""
    parsed, event = await _ask(
        agent=AgentName.EXAMINER,
        tier=ModelTier.BALANCED,
        system=prompts.EXAMINER_EVALUATE,
        user=(
            f"{_context_block(state, allow_private=True)}\n\n"
            f"ACCEPTANCE CRITERIA (private): "
            f"{'; '.join(state.get('challenge', {}).get('acceptance_criteria', []))}\n"
            f"EXPECTED REASONING (private): "
            f"{state.get('challenge', {}).get('expected_reasoning', '')}\n\n"
            f"LEARNER'S ATTEMPT:\n{state.get('learner_input', '')}"
        ),
        schema=AttemptEvaluation,
        meta=_meta(
            state, acceptance_criteria=state.get("challenge", {}).get("acceptance_criteria", [])
        ),
        temperature=0.1,
    )
    payload = parsed.model_dump(mode="json")
    return {"evaluation": payload, "events": [event]}


async def coach(state: TurnState) -> dict[str, Any]:
    """One Socratic move, at the assigned rung, guarded on the way out.

    Note the Coach runs on a view with the grading key *removed*. It cannot leak
    what it was never shown; the guard then catches the case where it
    reconstructs the answer from the material anyway.
    """
    level = int(state.get("scaffold_level", 1))
    step = rung(level)
    system = prompts.COACH.format(level=step.level, name=step.name, contract=step.contract)
    user = (
        f"{_context_block(state, allow_private=False)}\n\n"
        f"WHAT THEY JUST WROTE:\n{state.get('learner_input', '')}\n\n"
        f"DIAGNOSED ERROR: {state.get('evaluation', {}).get('error_type', 'unknown')}\n"
        "Make your one move."
    )

    parsed, event = await _ask(
        agent=AgentName.COACH,
        tier=ModelTier.DEEP,
        system=system,
        user=user,
        schema=CoachMove,
        meta=_meta(state),
        temperature=0.6,
    )

    async def regenerate(instruction: str) -> str:
        retry, _ = await _ask(
            agent=AgentName.COACH,
            tier=ModelTier.DEEP,
            system=f"{system}\n\n{instruction}",
            user=user,
            schema=CoachMove,
            meta=_meta(state),
            temperature=0.2,
        )
        return retry.message

    node = state.get("node", {})
    seeds = node.get("probe_seeds") or []
    result = await enforce(
        parsed.message,
        GuardContext(
            expected_reasoning=state.get("challenge", {}).get("expected_reasoning", ""),
            acceptance_criteria=tuple(state.get("challenge", {}).get("acceptance_criteria", [])),
            scaffold_level=level,
            fallback_probe=seeds[0] if seeds else "Which step here are you least sure about?",
        ),
        regenerate=regenerate,
    )

    event["guard_verdict"] = result.verdict.value
    return {
        "coach": {"message": result.text, "targets": parsed.targets},
        "guard_verdict": result.verdict.value,
        "guard_reason": result.reason,
        "events": [event],
    }


async def refuse(state: TurnState) -> dict[str, Any]:
    """Refusal & Pivot.

    The learner demanded the answer. We decline and immediately hand back a
    smaller foothold, because a refusal without a next move is just a wall — and
    a wall is what turns a learner into an adversary of the tutor.
    """
    request = ChatRequest(
        system=prompts.REFUSAL_PIVOT,
        messages=[
            Message(
                "user",
                f"{_context_block(state, allow_private=False)}\n\n"
                f"THEY SAID: {state.get('learner_input', '')}\n"
                f"TIMES THEY HAVE ASKED FOR THE ANSWER THIS SESSION: "
                f"{state.get('profile', {}).get('offload_attempts', 0)}",
            )
        ],
        tier=ModelTier.DEEP,
        temperature=0.6,
        meta=_meta(
            state,
            kind="refusal_pivot",
            offload_attempts=state.get("profile", {}).get("offload_attempts", 0),
        ),
    )
    response = await llm().complete(request)

    node = state.get("node", {})
    seeds = node.get("probe_seeds") or []
    fallback = (
        "I'm not going to hand this over — you're closer than you think. "
        f"{seeds[0] if seeds else 'What is the very first thing you would check?'}"
    )
    text = response.text.strip() or fallback

    result = await enforce(
        text,
        GuardContext(
            expected_reasoning=state.get("challenge", {}).get("expected_reasoning", ""),
            acceptance_criteria=tuple(state.get("challenge", {}).get("acceptance_criteria", [])),
            scaffold_level=1,
            enforce_question=True,
            # Acknowledge, give one situated reason, hand back a smaller foothold.
            sentence_budget=3,
            fallback_probe=fallback,
        ),
    )

    event = {
        "agent": AgentName.COACH.value,
        "model": response.model,
        "latency_ms": response.latency_ms,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "payload": {"kind": "refusal_pivot"},
        "guard_verdict": result.verdict.value,
    }
    return {"refusal": result.text, "guard_verdict": result.verdict.value, "events": [event]}


async def score_reflection(state: TurnState) -> dict[str, Any]:
    """The Metacognitive Gate. Free recall, scored against the expert model."""
    parsed, event = await _ask(
        agent=AgentName.REFLECTION,
        tier=ModelTier.BALANCED,
        system=prompts.REFLECTION,
        user=(
            f"{_context_block(state, allow_private=True)}\n\n"
            f"LEARNER'S SUMMARY, WRITTEN FROM MEMORY:\n{state.get('learner_input', '')}"
        ),
        schema=ReflectionScore,
        meta=_meta(state),
        temperature=0.2,
    )
    return {"reflection": parsed.model_dump(mode="json"), "events": [event]}


async def synthesize(state: TurnState) -> dict[str, Any]:
    """Merge the parallel outputs into the one message the learner sees.

    Deterministic assembly rather than a model call: the parts are already
    guarded and ordered, and re-generating them through another model would
    reintroduce exactly the drift the guard just removed — while adding latency
    to the hot path. The Synthesizer prompt exists for the deployments that want
    a smoother voice; the default is to trust the moves.
    """
    parts: list[str] = []

    if state.get("refusal"):
        parts.append(state["refusal"])
    else:
        if state.get("instruction"):
            parts.append(state["instruction"].get("message", ""))
        if state.get("new_challenge"):
            parts.append(state["new_challenge"].get("prompt", ""))
        if state.get("coach"):
            parts.append(state["coach"].get("message", ""))
        if state.get("reflection"):
            parts.append(state["reflection"].get("feedback", ""))

    message = "\n\n".join(p.strip() for p in parts if p and p.strip())
    event = {
        "agent": AgentName.SYNTHESIZER.value,
        "model": "deterministic",
        "payload": {"parts": len(parts)},
        "guard_verdict": state.get("guard_verdict", GuardVerdict.PASS.value),
    }
    return {"message": message, "events": [event]}


__all__ = [
    "author_challenge",
    "coach",
    "diagnose",
    "evaluate",
    "instruct",
    "refuse",
    "route",
    "score_reflection",
    "synthesize",
]
