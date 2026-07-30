"""A 90-line stand-in for ``langgraph.graph``.

LangGraph is the real dependency and the shape of :mod:`app.agents.graph` is
written against its API. This module exists so that the tutor — and the whole
test suite — still runs in an environment where the dependency tree has not been
installed yet: cloning the repo and getting a working Socratic tutor should not
be gated on a package resolve.

It implements exactly the subset used: nodes, plain edges, conditional edges,
and superstep execution with concurrent frontiers. Reducer semantics are
simplified to "concatenate lists, otherwise last write wins", which matches how
:class:`~app.agents.state.TurnState` is annotated. It is not a LangGraph
replacement and is not used when LangGraph is importable.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

START = "__start__"
END = "__end__"

NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
RouterFn = Callable[[dict[str, Any]], str]


def _merge(state: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, list) and isinstance(state.get(key), list):
            state[key] = [*state[key], *value]
        else:
            state[key] = value


class CompiledGraph:
    def __init__(
        self,
        nodes: dict[str, NodeFn],
        edges: dict[str, list[str]],
        conditionals: dict[str, tuple[RouterFn, dict[str, str]]],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._conditionals = conditionals

    def _successors(self, name: str, state: dict[str, Any]) -> list[str]:
        if name in self._conditionals:
            router, mapping = self._conditionals[name]
            key = router(state)
            target = mapping.get(key)
            if target is None:
                raise KeyError(f"Conditional edge from '{name}' produced unmapped key '{key}'.")
            return [target]
        return list(self._edges.get(name, []))

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        frontier = self._successors(START, current)
        guard = 0

        while frontier:
            guard += 1
            if guard > 64:  # pragma: no cover - the mesh is a DAG by construction
                raise RuntimeError("Agent graph did not terminate.")

            frontier = [n for n in dict.fromkeys(frontier) if n != END]
            if not frontier:
                break

            updates = await asyncio.gather(*(self._nodes[name](current) for name in frontier))
            for update in updates:
                _merge(current, update or {})

            nxt: list[str] = []
            for name in frontier:
                nxt.extend(self._successors(name, current))
            frontier = nxt

        return current


class StateGraph:
    def __init__(self, _schema: Any = None) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, list[str]] = {}
        self._conditionals: dict[str, tuple[RouterFn, dict[str, str]]] = {}

    def add_node(self, name: str, fn: NodeFn) -> StateGraph:
        self._nodes[name] = fn
        return self

    def add_edge(self, source: str, target: str) -> StateGraph:
        self._edges.setdefault(source, []).append(target)
        return self

    def add_conditional_edges(
        self, source: str, router: RouterFn, mapping: dict[str, str]
    ) -> StateGraph:
        self._conditionals[source] = (router, mapping)
        return self

    def compile(self) -> CompiledGraph:
        return CompiledGraph(self._nodes, self._edges, self._conditionals)


__all__ = ["END", "START", "CompiledGraph", "StateGraph"]
