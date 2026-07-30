"""The agent mesh, wired as a LangGraph.

```
                          ┌────────┐
                START ──► │ router │
                          └───┬────┘
        ┌────────────┬────────┼──────────┬─────────────┐
        ▼            ▼        ▼          ▼             ▼
   ┌─────────┐  ┌────────┐ ┌──────┐ ┌─────────┐  ┌──────────┐
   │ refuse  │  │diagnose│ │ eval │ │  coach  │  │ reflect  │
   └────┬────┘  └───┬────┘ └──┬───┘ └────┬────┘  └────┬─────┘
        │      ┌────┴────┐    │ (wrong)  │            │
        │      ▼         ▼    └───────►──┘            │
        │  ┌───────┐ ┌─────────┐                      │
        │  │instruct│ │challenge│                     │
        │  └───┬───┘ └────┬────┘                      │
        │      └────┬─────┘                           │
        └───────────┴──────► ┌────────────┐ ◄─────────┘
                             │ synthesize │
                             └──────┬─────┘
                                    ▼
                                   END
```

Two structural decisions worth naming:

**The fan-out after ``diagnose``.** Teaching and authoring the challenge both
depend on the diagnosis and on nothing else, so they run concurrently. Serial,
the learner waits for the sum; parallel, for the max. Engagement collapses past
about four seconds, and a disengaged learner learns nothing, so this is a
pedagogical decision that happens to look like an optimisation.

**``route`` cannot be overridden by the model.** The orchestrator writes a
``plan`` into the state before invoking, derived from the deterministic session
state. The Router agent may only *downgrade* that plan to ``refuse``. There is
no model output that promotes a turn to a more generous branch — a learner who
argues well gets a better refusal, not an answer.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.agents import nodes
from app.agents.state import TurnState
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.enums import Intent

log = get_logger(__name__)

try:  # pragma: no cover - exercised by whichever path the environment provides
    from langgraph.graph import END, START, StateGraph

    USING_LANGGRAPH = True
except ImportError:  # pragma: no cover
    from app.agents._minigraph import END, START, StateGraph

    USING_LANGGRAPH = False


#: What the orchestrator may ask the mesh to do this turn.
PLANS = ("elicit", "evaluate", "coach", "reflect", "instruct_only", "noop")


def _route(state: dict[str, Any]) -> str:
    intent = (state.get("intent") or {}).get("intent")

    # The one override the model is allowed: a demand for the answer short-
    # circuits every other branch, whatever the session state was expecting.
    if intent == Intent.ANSWER_DEMAND.value:
        return "refuse"

    plan = state.get("plan", "noop")
    if plan == "elicit":
        return "diagnose"
    if plan == "evaluate":
        return "evaluate"
    if plan == "coach":
        return "coach"
    if plan == "reflect":
        return "reflect"
    return "synthesize"


def _after_evaluate(state: dict[str, Any]) -> str:
    """Coach only when the attempt actually needs coaching.

    A correct attempt that gets 'coached' anyway teaches the learner that the
    tutor is not really listening, which is how they stop reading it.
    """
    correctness = float((state.get("evaluation") or {}).get("correctness", 0.0))
    return "coach" if correctness < settings.challenge_pass_threshold else "synthesize"


def build_graph() -> Any:
    graph = StateGraph(TurnState)

    graph.add_node("router", nodes.route)
    graph.add_node("refuse", nodes.refuse)
    graph.add_node("diagnose", nodes.diagnose)
    graph.add_node("instruct", nodes.instruct)
    graph.add_node("challenge", nodes.author_challenge)
    graph.add_node("evaluate", nodes.evaluate)
    graph.add_node("coach", nodes.coach)
    graph.add_node("reflect", nodes.score_reflection)
    graph.add_node("synthesize", nodes.synthesize)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route,
        {
            "refuse": "refuse",
            "diagnose": "diagnose",
            "evaluate": "evaluate",
            "coach": "coach",
            "reflect": "reflect",
            "synthesize": "synthesize",
        },
    )

    # Fan-out: instruction and challenge depend on the diagnosis, not each other.
    graph.add_edge("diagnose", "instruct")
    graph.add_edge("diagnose", "challenge")
    graph.add_edge("instruct", "synthesize")
    graph.add_edge("challenge", "synthesize")

    graph.add_conditional_edges(
        "evaluate", _after_evaluate, {"coach": "coach", "synthesize": "synthesize"}
    )
    graph.add_edge("coach", "synthesize")
    graph.add_edge("reflect", "synthesize")
    graph.add_edge("refuse", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


@lru_cache(maxsize=1)
def tutor_graph() -> Any:
    compiled = build_graph()
    log.info("agent_mesh_ready", runtime="langgraph" if USING_LANGGRAPH else "builtin")
    return compiled


async def run_turn(state: TurnState, *, plan: str) -> TurnState:
    """Execute one learner turn through the mesh."""
    if plan not in PLANS:
        raise ValueError(f"Unknown plan '{plan}'.")
    payload: dict[str, Any] = {**state, "plan": plan, "events": list(state.get("events", []))}
    result = await tutor_graph().ainvoke(payload)
    return result  # type: ignore[no-any-return]


__all__ = ["PLANS", "USING_LANGGRAPH", "build_graph", "run_turn", "tutor_graph"]
