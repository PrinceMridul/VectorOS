# Future Work

This document exists to keep three different kinds of statement from
blurring into each other, because they get conflated constantly in AI
product writing and the conflation is where trust gets lost:

- **Version 1** — built, running, and covered by the test suite today.
- **Version 2** — concrete engineering and product work with a known shape,
  not yet built.
- **Research hypotheses** — ideas we believe are worth testing, phrased as
  questions we don't know the answer to, not as features on a roadmap.

Nothing in the second or third section should be read as a claim about the
current system. See [`LIMITATIONS.md`](LIMITATIONS.md) for what "not yet
built" or "not yet validated" means in each specific case.

---

## Version 1 — implemented and tested today

Enforced by code, exercised by the automated test suite (62 backend tests,
running against the offline provider):

- Elicitation gated before instruction, with no code path around it
  (`pedagogy/state_machine.py`).
- A scaffold ladder that escalates one step at a time, only after a learner
  reply, with no step that reveals an answer (`pedagogy/scaffold.py`).
- An output guard checking generated coaching text against the private
  answer key by lexical pattern, criteria overlap, and embedding similarity,
  with a deterministic fallback on failure (`agents/guard.py`).
- Extended Bayesian Knowledge Tracing with measurement and learning-transition
  separated, confidence weighting, scaffold discounting, and continuous
  decay between sessions (`pedagogy/bkt.py`).
- Mastery gated on free recall, not on a correct answer alone
  (`pedagogy/state_machine.py::next_after_reflection`).
- A metacognitive quadrant classification (confidence × correctness) used to
  select response strategy, with blind spots (wrong-while-confident)
  prioritized for review (`pedagogy/calibration.py`).
- A misconception lifecycle requiring two independent clears before a
  belief is marked resolved (`agents/memory.py`).
- A dependency-graph curriculum with mastery-gated unlocking, not a linear
  course.
- The Understanding Shift: a closing screen assembled entirely from
  persisted learner-authored text, no generation involved
  (`session/service.py::understanding_shift`).
- A fully offline, deterministic execution path with no API key required,
  which the entire test suite runs against.
- A provider abstraction supporting Gemini, OpenAI, and Anthropic behind one
  interface, with per-agent capability-tier routing (untested against real
  traffic — see `LIMITATIONS.md` §2).
- A full session trace exposed to the learner, not just to an admin surface
  (`GET /sessions/{id}/trace`), and every tuned constant exposed at
  `GET /api/pedagogy`.

---

## Version 2 — planned engineering and product work

Ordered roughly by dependency, not by priority within each group.

### Make the safety claim testable

1. **Adversarial evaluation harness.** An LLM playing a frustrated,
   manipulative learner against the real (non-mock) pipeline, with turns-to-
   leak or turns-to-collapse recorded, compared against a prompt-only
   baseline built on the same underlying model. This is the single highest-
   priority item in this document — everything else in "Version 2" is
   ordinary product engineering; this is the item that would let the
   central architectural claim be stated as measured rather than designed.
2. **Integration tests against real providers**, run in CI on a schedule,
   covering the guard, the scaffold escalation, and the full turn loop —
   currently 0% covered (`LIMITATIONS.md` §2).

### Make the operational basics real

3. Alembic migrations; retire `create_all()` from any path that touches a
   populated database.
4. CI: lint, type-check, and test on every change, both sides of the repo.
5. Per-session and per-learner cost telemetry, aggregated from the
   `tokens_in`/`tokens_out` already recorded per agent call, with a
   configurable per-turn budget and graceful degradation when it's
   exceeded.
6. Real authentication with refresh and revocation, replacing the current
   long-lived bearer token.
7. Frontend test coverage — currently zero.

### Close the loop that's already half-built

8. **Deliver spaced-repetition reviews.** The scheduling math exists
   (`pedagogy/schedule.py`) and nothing currently acts on it outside the
   dashboard. Ship the delivery mechanism — even a daily digest would close
   this gap.
9. **Copy-on-write template graphs**, so a correction to a canonical model
   or misconception bank can reach learners who already started that goal,
   instead of only new clones.

### Extend who the product serves

10. **Instructor / cohort dashboard.** Aggregate misconception coverage
    across a group, surface what the system diagnosed for a specific
    learner, allow a human to intervene. Currently the product has no
    surface for anyone other than the individual learner.
11. **Content-authoring tooling.** The current process (hand-authoring a
    canonical model, misconception bank, probe questions, and challenge
    seeds per concept) does not scale past a handful of curricula. An
    LLM-assisted authoring pipeline with human review is the natural next
    step, but its output quality relative to hand-authored content is
    itself an open question, not an assumption to build on.

---

## Research hypotheses — not yet validated, stated as questions

These are not roadmap items with a known shape. Each is a specific,
falsifiable question we think is worth answering, phrased so that a
negative result would be a real and useful finding, not just an unmet
target.

1. **Does eliciting prior belief before instruction improve retention
   compared to instruction-first, holding the rest of the system
   constant?** This is the central premise of the entire product and it has
   not been tested. A proper test needs a randomized comparison, a delayed
   (not immediate) retention measure, and a sample larger than the
   development team.

2. **Does the three-layer enforcement architecture actually outperform a
   well-written system prompt at resisting sustained adversarial pressure,
   and by how much?** Testable today, without recruiting human subjects,
   using the adversarial harness described in Version 2 item 1. This is the
   research question in this document closest to being answerable cheaply.

3. **Are the knowledge-tracing parameters (`prior`, `learn`, `guess`,
   `slip`, `forget`) closer to correct than a naive baseline, once fit via
   expectation-maximization against real response sequences instead of
   hand-chosen?** Requires a corpus of real learner interactions that
   doesn't yet exist.

4. **Does confidence-weighted evidence improve next-response prediction
   accuracy (AUC) over standard BKT?** This is answerable today on public
   benchmark datasets (e.g. ASSISTments) without needing this product's own
   users at all, and is plausibly the most tractable near-term publishable
   result in this list.

5. **Does the cognitive-load heuristic in `pedagogy/load.py` correlate with
   anything** — self-reported effort collected via an actual Paas-style
   instrument administered alongside it, physiological load measures, or
   downstream performance? Currently unvalidated against any of these.

6. **Does gating mastery on free recall (rather than on a correct graded
   answer alone) produce better delayed retention**, and is the current
   lexical-coverage scoring method (§7 in `LIMITATIONS.md`) a good enough
   proxy for genuine understanding to be trustworthy as the gate?

7. **Does the "cognitive debt" metric predict anything real** — specifically,
   does a learner's hint-reliance score predict their unaided performance on
   a later, novel problem? This would need to be tested with a transfer task
   the current curriculum doesn't yet include.

8. **Does showing a learner the Understanding Shift change their subsequent
   behavior** — engagement, trust in the system, or willingness to sit with
   productive struggle — compared to not showing it? The screen's value as a
   product artifact (does it communicate the thesis clearly) and its value
   as a pedagogical intervention (does seeing it change behavior) are
   different claims, and only the first has been informally assessed at
   all.

---

If you are evaluating this project and have to choose one item from this
document to ask about, ask about research hypothesis 1. It's the one every
other claim in the repository ultimately rests on.
