"""The state object that flows through the agent mesh for one learner turn.

Two rules keep this honest:

* ``phase`` is **read-only** to every agent. Agents propose language; only
  :mod:`app.pedagogy.state_machine` moves the session. Nothing in this graph
  writes ``phase``.
* Private keys (``challenge.expected_reasoning``, ``node.canonical_model``) are
  filtered per-agent by :func:`agent_view`, not merely "not mentioned" in a
  prompt. The Coach cannot leak a grading key it was never given.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class TurnState(TypedDict, total=False):
    # ── Inputs (immutable within a turn) ────────────────────────────────────
    phase: str
    plan: str
    """Set by the orchestrator from the deterministic session state. The mesh
    may only *downgrade* it to a refusal, never promote it."""
    learner_input: str
    node: dict[str, Any]
    chunks: list[dict[str, str]]
    profile: dict[str, Any]
    mastery: float
    scaffold_level: int
    difficulty: float
    bloom: str
    target_success: float
    active_misconceptions: list[str]
    diagnosis: dict[str, Any]
    challenge: dict[str, Any]
    expecting: str
    load_band: str
    quadrant_strategy: str

    # ── Produced by agents ──────────────────────────────────────────────────
    intent: dict[str, Any]
    new_diagnosis: dict[str, Any]
    instruction: dict[str, Any]
    new_challenge: dict[str, Any]
    evaluation: dict[str, Any]
    coach: dict[str, Any]
    reflection: dict[str, Any]
    refusal: str

    # ── Emitted ─────────────────────────────────────────────────────────────
    message: str
    guard_verdict: str
    guard_reason: str
    events: Annotated[list[dict[str, Any]], operator.add]


#: Keys an agent must never see. Absence beats instruction.
_PRIVATE_NODE_KEYS = frozenset({"canonical_model"})
_PRIVATE_CHALLENGE_KEYS = frozenset({"expected_reasoning", "acceptance_criteria"})


def agent_view(state: TurnState, *, allow_private: bool) -> dict[str, Any]:
    """Project the state down to what a given agent is permitted to know.

    The Examiner and Teacher legitimately need the expert model. The Coach and
    Synthesizer do not, and giving it to them is how paraphrased answers leak.
    """
    node = dict(state.get("node") or {})
    challenge = dict(state.get("challenge") or {})

    if not allow_private:
        for key in _PRIVATE_NODE_KEYS:
            node.pop(key, None)
        for key in _PRIVATE_CHALLENGE_KEYS:
            challenge.pop(key, None)

    return {
        "node": node,
        "challenge": challenge,
        "chunks": state.get("chunks", []),
        "diagnosis": state.get("diagnosis", {}),
        "evaluation": state.get("evaluation", {}),
        "mastery": state.get("mastery", 0.0),
        "scaffold_level": state.get("scaffold_level", 0),
        "difficulty": state.get("difficulty", 0.5),
        "bloom": state.get("bloom", "apply"),
        "active_misconceptions": state.get("active_misconceptions", []),
        "expecting": state.get("expecting", ""),
        "acceptance_criteria": challenge.get("acceptance_criteria", []),
    }


__all__ = ["TurnState", "agent_view"]
