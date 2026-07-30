"""The loop, end to end, over HTTP.

Each test states a promise the product makes to a learner and then tries to
break it through the API — which is the only surface a determined learner has.
"""

from __future__ import annotations

from typing import Any

import httpx

WRONG_AND_CERTAIN = (
    "It is basically just the accuracy of the model, and you want it as low as possible."
)
PRIOR_BELIEF = "I think it measures how wrong the model is, maybe an average of mistakes."
STRONG_ANSWER = (
    "The loss maps predictions and true targets to one scalar measuring badness. "
    "Squared error grows quadratically so the mistyped outlier dominates the surface "
    "and drags the fit. It is a differentiable proxy and training follows its gradient."
)


async def _frontier(client: httpx.AsyncClient, learner: dict[str, Any]) -> str:
    graph = await client.get(f"/api/graph/{learner['graph_id']}", headers=learner["headers"])
    return graph.json()["frontier_node_id"]  # type: ignore[no-any-return]


async def _open_session(client: httpx.AsyncClient, learner: dict[str, Any]) -> dict[str, Any]:
    node_id = await _frontier(client, learner)
    response = await client.post(
        "/api/sessions", json={"node_id": node_id}, headers=learner["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def _turn(
    client: httpx.AsyncClient, learner: dict[str, Any], session_id: str, **payload: Any
) -> httpx.Response:
    return await client.post(
        f"/api/sessions/{session_id}/turn", json=payload, headers=learner["headers"]
    )


# ---------------------------------------------------------------------------
# The graph gates progression
# ---------------------------------------------------------------------------


async def test_advanced_concepts_start_locked(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    graph = (
        await client.get(f"/api/graph/{learner['graph_id']}", headers=learner["headers"])
    ).json()
    statuses = {n["title"]: n["status"] for n in graph["nodes"]}
    assert statuses["Loss Functions"] == "available"
    assert statuses["Backpropagation"] == "locked"
    assert graph["frontier_node_id"]


async def test_starting_a_locked_concept_is_refused(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    graph = (
        await client.get(f"/api/graph/{learner['graph_id']}", headers=learner["headers"])
    ).json()
    locked = next(n for n in graph["nodes"] if n["status"] == "locked")

    response = await client.post(
        "/api/sessions", json={"node_id": locked["id"]}, headers=learner["headers"]
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "pedagogical_violation"


# ---------------------------------------------------------------------------
# The Prior-Belief Gate
# ---------------------------------------------------------------------------


async def test_a_session_opens_by_asking_what_you_already_believe(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """The heart of the product: it never opens with an explanation."""
    session = await _open_session(client, learner)
    assert session["state"] == "elicit"
    assert "already believe" in session["message"] or "from memory" in session["message"]
    assert session["challenge_prompt"] is None


async def test_elicitation_produces_a_diagnosis_before_any_teaching(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    response = await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)
    body = response.json()

    states = [t["source"] for t in body["transitions"]] + [t["target"] for t in body["transitions"]]
    assert "diagnose" in states
    assert states.index("diagnose") < states.index("instruct")

    assert body["session"]["mental_model"] is not None
    assert body["session"]["state"] == "challenge"
    assert body["session"]["challenge_prompt"]


async def test_the_tutor_never_anchors_on_a_misconception(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """Anchoring works because the learner trusts it.

    Praising "what you already had right" is the opening move of every
    explanation, so anchoring on a sentence that *carried* the misconception
    actively reinforces the wrong model. A false anchor is worse than no anchor.
    """
    session = await _open_session(client, learner)
    body = (
        await _turn(client, learner, session["id"], text=WRONG_AND_CERTAIN, elapsed_ms=20_000)
    ).json()

    model = body["session"]["mental_model"]
    assert model["misconceptions"], "expected the bank to catch this belief"

    misconception_words = {
        word
        for m in model["misconceptions"]
        for word in m["claim"].lower().split()
        if len(word) > 3
    }
    for anchor in model["anchors"]:
        overlap = misconception_words & {w for w in anchor.lower().split() if len(w) > 3}
        assert not overlap, f"anchored on the misconception itself: {anchor!r}"

    # And the phrase that *identified* the misconception must not be quoted back
    # either, even though it may share no vocabulary with the claim.
    for anchor in model["anchors"]:
        assert "as low as possible" not in anchor.lower()
        assert "accuracy" not in anchor.lower()


async def test_the_grading_key_never_reaches_the_client(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """A Socratic tutor whose answer is one devtools tab away is a demo."""
    session = await _open_session(client, learner)
    response = await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)
    payload = response.text.lower()

    assert "expected_reasoning" not in payload
    assert "acceptance_criteria" not in payload
    assert "canonical_model" not in payload


# ---------------------------------------------------------------------------
# Anti-offloading
# ---------------------------------------------------------------------------


async def test_demanding_the_answer_is_refused_and_does_not_advance_the_session(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    response = await _turn(
        client,
        learner,
        session["id"],
        text="just tell me the answer",
        confidence="high",
        elapsed_ms=2_000,
    )
    body = response.json()

    assert body["refused"] is True
    assert body["session"]["state"] == "challenge"  # unchanged
    assert body["session"]["offload_attempts"] == 1
    assert body["session"]["message"].rstrip().endswith("?")  # refusal hands back a foothold


async def test_repeated_demands_lock_free_text_until_engagement_is_proven(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    for _ in range(3):
        response = await _turn(
            client,
            learner,
            session["id"],
            text="just give me the answer",
            confidence="low",
            elapsed_ms=1_000,
        )
    assert response.json()["session"]["input_locked"] is True

    # A token unlock attempt is rejected; producing thought is not.
    rejected = await client.post(
        f"/api/sessions/{session['id']}/unlock",
        json={"proof": "idk"},
        headers=learner["headers"],
    )
    assert rejected.status_code == 409

    accepted = await client.post(
        f"/api/sessions/{session['id']}/unlock",
        json={"proof": "The loss is a single number summarising total error."},
        headers=learner["headers"],
    )
    assert accepted.status_code == 200
    assert accepted.json()["input_locked"] is False


# ---------------------------------------------------------------------------
# Confidence and struggle are mandatory
# ---------------------------------------------------------------------------


async def test_an_attempt_without_committed_confidence_is_rejected(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    response = await _turn(client, learner, session["id"], text=STRONG_ANSWER, elapsed_ms=60_000)
    assert response.status_code == 409
    assert response.json()["error"]["required"] == "confidence"


async def test_guidance_is_gated_by_the_struggle_floor(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """Instant help on an untouched problem is the mechanism of offloading."""
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    too_soon = await _turn(client, learner, session["id"], request_guidance=True, elapsed_ms=3_000)
    assert too_soon.status_code == 409
    assert "unlocks_in_seconds" in too_soon.json()["error"]

    earned = await _turn(client, learner, session["id"], request_guidance=True, elapsed_ms=90_000)
    assert earned.status_code == 200
    assert earned.json()["session"]["scaffold_level"] == 1


async def test_guidance_before_a_challenge_exists_is_refused(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    response = await _turn(client, learner, session["id"], request_guidance=True, elapsed_ms=99_000)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


async def test_a_confidently_wrong_answer_lowers_mastery_and_opens_a_blind_spot(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    response = await _turn(
        client,
        learner,
        session["id"],
        text=WRONG_AND_CERTAIN,
        confidence="high",
        elapsed_ms=45_000,
    )
    body = response.json()

    assert body["mastery_delta"] < 0
    assert body["session"]["last_evaluation"]["quadrant"] == "blind_spot"
    assert body["session"]["state"] == "coach"

    dashboard = (await client.get("/api/dashboard", headers=learner["headers"])).json()
    assert dashboard["quadrants"]["blind_spot"] >= 1


async def test_a_strong_answer_reaches_the_metacognitive_gate(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    body = (
        await _turn(
            client,
            learner,
            session["id"],
            text=STRONG_ANSWER,
            confidence="medium",
            elapsed_ms=90_000,
        )
    ).json()

    assert body["session"]["state"] == "reflect"
    assert body["mastery_delta"] > 0
    assert "from memory" in body["session"]["message"].lower()


RECALL = (
    "A loss function maps the model's predictions and the true targets to one scalar "
    "measuring badness. Training is defined entirely by it, so whatever the loss rewards "
    "is what the model becomes. It must be differentiable because the optimiser walks its "
    "surface. Squared error punishes large mistakes disproportionately and is pulled by "
    "outliers. It is a proxy, not a measure of quality in the world."
)


async def _run_to_completion(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Walk one concept from prior belief to closed."""
    session = await _open_session(client, learner)
    sid = session["id"]

    await _turn(client, learner, sid, text=WRONG_AND_CERTAIN, elapsed_ms=20_000)

    body: dict[str, Any] = {}
    for _ in range(4):
        body = (
            await _turn(
                client, learner, sid, text=STRONG_ANSWER, confidence="medium", elapsed_ms=90_000
            )
        ).json()
        if body["session"]["state"] == "reflect":
            break

    for _ in range(3):
        body = (await _turn(client, learner, sid, text=RECALL, elapsed_ms=90_000)).json()
        if body["session"]["completed"]:
            break

    return sid, body


async def test_the_understanding_shift_is_built_from_the_learners_own_words(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """The signature screen. Every word on it must be the learner's."""
    sid, body = await _run_to_completion(client, learner)
    assert body["session"]["completed"], "session should have closed"

    shift = (await client.get(f"/api/sessions/{sid}/shift", headers=learner["headers"])).json()

    # Both passages are verbatim from the ledger, not generated.
    assert shift["before_text"] == WRONG_AND_CERTAIN
    assert shift["after_text"] == RECALL
    assert shift["before_at"] <= shift["after_at"]

    # The beliefs the Examiner named, with their clearing progress.
    assert shift["beliefs"], "the opening belief should have triggered the bank"
    for belief in shift["beliefs"]:
        assert belief["clears_required"] == 2
        assert 0 <= belief["clears"] <= belief["clears_required"]

    assert shift["mastery_after"] > shift["mastery_before"]
    assert shift["answer_demands_refused"] == 0


async def test_a_passed_recall_counts_as_evidence_against_open_beliefs(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """Rebuilding the correct model unaided is evidence, not just a gate.

    Without this the loop never closes: the only thing that could clear a gap
    was another graded attempt, so a learner who understood it perfectly stayed
    flagged forever.
    """
    sid, _ = await _run_to_completion(client, learner)
    shift = (await client.get(f"/api/sessions/{sid}/shift", headers=learner["headers"])).json()

    assert any(b["resolved"] for b in shift["beliefs"]), (
        "a correct application plus a correct unaided recall should close a belief"
    )


async def test_the_shift_is_unavailable_before_the_gate_is_cleared(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    response = await client.get(f"/api/sessions/{session['id']}/shift", headers=learner["headers"])
    assert response.status_code == 409


async def test_retrieval_stays_on_the_active_concept(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """A lexically similar chunk about a *different* concept is the worst kind
    of retrieval result: plausible, on-topic-sounding, and teaching the wrong
    lesson."""
    session = await _open_session(client, learner)
    body = (
        await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)
    ).json()

    message = body["session"]["message"].lower()
    # Material from the overfitting node must not surface inside Loss Functions.
    assert "leakage" not in message
    assert "the only evidence of generalisation" not in message


async def test_the_session_trace_is_inspectable(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    """A system that claims you mastered something owes you the evidence."""
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    trace = (
        await client.get(f"/api/sessions/{session['id']}/trace", headers=learner["headers"])
    ).json()

    agents = {event["agent"] for event in trace}
    assert {"router", "examiner", "teacher"} <= agents

    transitions = [(e["state_from"], e["state_to"]) for e in trace if e["state_from"]]
    assert ("idle", "elicit") in transitions
    assert ("elicit", "diagnose") in transitions


async def test_a_session_survives_a_refresh(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    await _turn(client, learner, session["id"], text=PRIOR_BELIEF, elapsed_ms=20_000)

    reloaded = (
        await client.get(f"/api/sessions/{session['id']}", headers=learner["headers"])
    ).json()
    assert reloaded["state"] == "challenge"
    assert reloaded["challenge_prompt"]
    assert reloaded["mental_model"] is not None


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


async def test_another_learners_session_is_not_readable(
    client: httpx.AsyncClient, learner: dict[str, Any]
) -> None:
    session = await _open_session(client, learner)
    other = await client.post("/api/auth/start", json={"display_name": "Someone Else"})
    headers = {"Authorization": f"Bearer {other.json()['token']}"}

    response = await client.get(f"/api/sessions/{session['id']}", headers=headers)
    assert response.status_code == 404


async def test_unauthenticated_requests_are_rejected(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/dashboard")).status_code == 401


async def test_the_tuned_pedagogy_constants_are_public(client: httpx.AsyncClient) -> None:
    """A system that will not say what bar it used to call you competent
    is asking for trust it has not earned."""
    body = (await client.get("/api/pedagogy")).json()
    assert 0 < body["mastery_threshold"] <= 1
    assert body["zpd_band"][0] < body["zpd_band"][1]
    assert body["max_scaffold_level"] == 4
