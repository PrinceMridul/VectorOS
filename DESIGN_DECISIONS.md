# Design Decisions

This document explains *why* the system is built the way it is — including
one place where we built it a different way first, found it produced a wrong
result, and changed it. Each entry states the decision, the alternative we
didn't take, and how confident we actually are in the choice. Where the
answer is "we think this is right but haven't measured it," we say so; see
[`LIMITATIONS.md`](LIMITATIONS.md) for the complete accounting.

---

## 1. Elicit before instructing, enforced in the state machine

**Decision.** A new concept can only be entered through `ELICIT` —
[`pedagogy/state_machine.py`](backend/app/pedagogy/state_machine.py) has no
transition from `IDLE` to `INSTRUCT`. The learner must answer "what do you
already believe this is" before any explanation is generated.

**Alternative considered.** Elicit as a UX nicety — a friendly opening
question the interface asks, with the model free to explain regardless of
whether it was answered. This is what most "Socratic" chatbot wrappers do:
the elicitation is conversational decoration, not a gate.

**Why we didn't do that.** If elicitation is optional, it will be skipped
under pressure — a learner who says "just explain it" will get an
explanation, and the entire downstream chain (diagnosis, targeted
instruction, the Understanding Shift) has nothing to work from. Making it a
hard state-machine edge means there is no configuration, prompt, or user
pressure that produces an explanation without a prior belief on record.

**Confidence.** High that the mechanism does what it says (this is a
transition table, it's easy to verify). Untested that eliciting first
produces measurably better outcomes than explaining first — see
`LIMITATIONS.md`.

---

## 2. Three independent enforcement layers instead of one system prompt

**Decision.** The refusal to hand over answers is enforced by three separate
mechanisms that don't share a failure mode: the state machine (no legal
transition to "answer"), the scaffold ladder (help escalates one step at a
time and never reaches "give the solution"), and an output guard (checks
generated text against the private answer key by lexical pattern, criteria
overlap, and embedding similarity, regardless of what the model was asked to
do).

**Alternative considered.** A single well-written system prompt: *"Never
give the answer directly; guide with questions instead."* This is simpler,
cheaper, and is what most Socratic-tutor prototypes actually ship.

**Why we didn't do that.** A prompt is an instruction the model is free to
weigh against other pressure in the conversation — a frustrated, insistent
learner is exactly the kind of pressure model training tends to resolve in
favor of being helpful. We observed this failure mode ourselves during
development and it's consistent with published findings on Socratic-tutor
degradation under sustained pressure (see the citation trail in the research
material this project started from). A prompt is necessary — it's what makes
the tutor's language sound like a person rather than a form — but we do not
rely on the model *choosing* to comply for the guarantee to hold. The guard
is what catches the case the state machine and scaffold miss: a technically
legal move (say, a rung-1 orienting question) whose actual generated text
still leaks the answer because it was persuasive enough to talk the model
into it.

**Confidence.** High that these three layers are structurally independent
(verified by reading the code — none of them call into each other). Low—to—
none on how well they perform against a real, sustained adversarial
conversation with a frontier model, because that test has not been run. This
is the single most important open validation gap in the project; see
`FUTURE_WORK.md`.

---

## 3. Separating measurement from the learning transition in knowledge tracing

**Decision.** [`pedagogy/bkt.py`](backend/app/pedagogy/bkt.py) has two
functions where standard Bayesian Knowledge Tracing has one: `update()`,
which only observes and never increases the probability of learning, and
`apply_instruction()`, which applies the "you may have learned something"
transition, called only at the point where teaching actually happens.

**What we tried first.** The textbook formulation, which folds both steps
into a single update: every observation is treated as *both* evidence about
current mastery *and* an opportunity to learn, in the same step.

**Why we changed it.** We found, while testing this in development, that the
textbook formulation can raise a learner's mastery estimate immediately
after a confidently wrong answer — from a low starting point, the "you might
have learned something" term in the update can outweigh the "you were wrong"
evidence. We measured this directly: 0.15 → 0.44 following a wrong,
high-confidence response. A mastery number that goes up when a learner is
wrong is worse than having no number, because it's the kind of error a
learner can personally verify is false, and once distrust starts, no other
number the system produces will be believed either. Splitting measurement
from the learning transition removed this failure mode.

**Confidence.** High that this fixes the specific failure mode described
(it's covered by an automated test —
`tests/test_pedagogy.py::test_confident_wrong_answer_lowers_mastery`). No
confidence that the *resulting* parameters produce accurate mastery
estimates in an absolute sense — they're not fit to any real response data.
This is the clearest example in the repository of "we found and fixed a
correctness bug" without that fix implying the surrounding model is
validated.

---

## 4. Confidence collected before grading, not after

**Decision.** Every graded attempt requires a confidence rating committed
*before* the system evaluates correctness
([`features/session/schemas.py::TurnRequest`], enforced server-side in
`session/service.py`). This feeds two things: the knowledge tracer (a wrong
answer given with high confidence is stronger evidence of a real gap than
one given while guessing) and the metacognitive quadrant classification
(correctness × confidence, where wrong-and-confident is flagged as a "blind
spot" — the case ordinary grading can't see, because the score just says
"wrong" either way).

**Alternative considered.** Ask for confidence after showing the result
("how confident were you, looking back?"), which is far more common in
practice because it doesn't add friction before submission.

**Why we didn't do that.** Confidence collected after the outcome is known
is contaminated by the outcome — people's stated retrospective confidence
shifts toward whatever the answer turned out to be. Collecting it first is
the only way the number means what it's supposed to mean.

**Confidence.** High that pre-commitment produces a cleaner signal than
post-hoc rating — this is a well-established point in the metacognition
literature, not something we're claiming as our own finding. No validation
yet that our specific quadrant thresholds (0.6 for "confident," matching
the correctness pass threshold) are the right cut points.

---

## 5. A misconception needs two independent clears to close

**Decision.** [`agents/memory.py::CLEARS_TO_RESOLVE = 2`] — a diagnosed
misconception is marked resolved only after the learner demonstrates it's
gone on two separate occasions (one graded application, one free recall),
not one.

**Alternative considered.** Close it on the first correct answer that
contradicts it.

**Why we didn't do that.** One correct answer is frequently a guess, a
lucky phrasing, or an artifact of a hint given two turns earlier. Closing
the gap on the first sign of it is the more satisfying UX and the less
honest one.

**Confidence.** Medium. The *reasoning* is sound; the specific number (two,
not three) is a judgment call we have not validated against real data on
how often a single correct answer is later contradicted.

---

## 6. Mastery is gated on free recall, not on a correct answer

**Decision.** [`pedagogy/state_machine.py::next_after_reflection`] — a
correct answer to a challenge routes to `REFLECT`, not to `MASTERY`.
`MASTERY` is reachable only after the learner explains the concept from
memory, with the material hidden, and that explanation is scored against
the expert model.

**Why.** Answering a question correctly and being able to reconstruct the
underlying idea unaided are different skills; the first can be achieved by
pattern-matching against a recently-seen example. Gating on the second is
the more expensive design — it costs the learner more time and costs the
product a worse "time to green checkmark" metric — and we made that trade
deliberately.

**Confidence.** High on the pedagogical reasoning (this is a standard
distinction in the learning-science literature — free recall as a stronger
retention signal than recognition or cued recall). No confidence yet that
our specific scoring method (lexical concept-coverage against the reference
model, `reflection_pass_threshold = 0.6`) is a good instrument for measuring
it. See `LIMITATIONS.md`.

---

## 7. Three of eight agents are deterministic, not LLM calls

**Decision.** `Planner`, `Memory`, and `Synthesizer` are pure Python
functions, not model calls, despite being described as "agents" alongside
`Router`, `Examiner`, `Teacher`, `Coach`, and `Reflection`.

**Why.** Choosing the next concept from a mastery-gated dependency graph is
a sort, not a judgment call. Updating the weakness index from a graded
attempt is a state-lifecycle transition with a fixed rule. Assembling
already-guarded text fragments into one message is concatenation, and
running it back through a model would reintroduce exactly the drift the
guard exists to remove — while adding latency and cost to a decision that
has one correct answer. Using a model for any of these would make the
mastery number harder to audit for no corresponding benefit.

**Confidence.** High. This isn't a hedge — it's closer to an engineering
default than a hypothesis (don't call a model when a function will do), and
we'd defend it without qualification.

---

## 8. Offline, deterministic execution is a first-class path, not a fallback

**Decision.** `MockProvider` implements the same interface as the real LLM
providers and reproduces the full pedagogical loop — diagnosis, coaching,
scoring — using structured lexical matching against the same authored
content instead of a model call. All 62 automated backend tests run against
it, and the entire product can be demonstrated with no API key.

**Why.** Testing pedagogical invariants (does mastery fall after a
confidently wrong answer? does the scaffold ladder refuse to skip a rung?)
against a live, non-deterministic model would make those tests flaky by
construction. Determinism was worth more to us here than realism.

**The cost of this decision, stated plainly.** The offline path is not a
lightweight stand-in for the real thing in every respect — its diagnosis
step is closer to keyword-triggered matching than to the kind of flexible
classification a real model performs, and this difference has never been
formally measured. Every demo, and nearly every hour of internal testing, has
run against the offline path. This is the most consequential trade-off in
`LIMITATIONS.md` and we'd rather name it here than let it be discovered.

---

## 9. No chat log; a thinking canvas instead

**Decision.** The workspace has no scrolling message history and no
persistent input box that invites a running conversation. There is one
current tutor message and one large text area for the learner's reasoning.

**Why.** A chat log is a UI that implies "ask me anything, I'll respond
immediately" — and interfaces train behavior. We wanted the default gesture
to be *write a paragraph of reasoning*, not *type a question and wait*.

**Confidence.** This is a product design bet, stated as one. We have not
tested it against a conventional chat UI on the same backend to see whether
the interface itself changes learner behavior, though that would be a
straightforward thing to test.

---

## 10. The Understanding Shift is retrieved, never generated

**Decision.** [`session/service.py::understanding_shift`] assembles the
closing screen entirely from persisted rows — the learner's original
prior-belief text, their final free-recall text, and the misconception
lifecycle in between. There is no LLM call in this code path.

**Why.** This screen's entire credibility depends on both passages being
verifiably the learner's own words. A generated summary of "what you used to
think" would be a paraphrase we produced, and paraphrase is exactly the
category of failure the output guard elsewhere in the system exists to
prevent. Consistency demanded that this screen hold itself to the same
standard.

**Confidence.** High that the implementation matches this description — it's
a straightforward thing to verify by reading the function. This is the one
design decision in the document we'd stand behind without any hedge at all.

---

## What we'd reconsider if we rebuilt this

- **`_minigraph.py`**, a hand-rolled fallback orchestrator for environments
  without LangGraph installed. It exists so the project runs before `pip
  install` finishes, and it has effectively no test coverage of its own. In
  hindsight, a hard dependency on LangGraph would have been the simpler,
  more honest choice.
- **The offline provider's misconception matching** being regex-based was a
  reasonable MVP choice; if content scale grows past a few dozen concepts,
  it will not.
- **Naming the cognitive-load heuristic after the Paas scale** in early
  drafts of this documentation. It wasn't the Paas instrument, and the name
  implied a validation status the formula doesn't have. Corrected throughout
  the codebase and docs; see `pedagogy/load.py` for the current, accurate
  description.
