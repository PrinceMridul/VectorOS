# VectorOS — Architecture

> **Learn by Thinking.**
> Understanding before explanation.

This document is the engineering contract for VectorOS: *what* we built and *how* the
pieces fit together. It describes the system as implemented, not as intended — every
claim below should be checkable against the code paths it cites.

For the reasoning behind these choices, see [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md).
For what this document does *not* claim — validation status, untested paths, known
gaps — see [LIMITATIONS.md](LIMITATIONS.md). For what's planned versus what's built,
see [FUTURE_WORK.md](FUTURE_WORK.md).

---

## 0. The one-sentence thesis

> A chatbot optimises for **resolution speed**. VectorOS optimises for **durable schema
> construction**, and is willing to trade user satisfaction in the next 10 seconds for
> capability in the next 10 years.

Concretely, this manifests as one non-negotiable invariant:

**The system may never emit the terminal answer to a challenge the learner has not yet
attempted.** Enforced in three independent layers (state machine → prompt contract →
output guard), because a single system prompt reliably fails to hold this line once a
learner pushes back hard enough — a pattern well documented in the Socratic-tutoring
literature and consistent with our own manual testing, though we have not yet run a
controlled comparison inside this repository (see `LIMITATIONS.md`).

---

## 1. System shape

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT — Next.js 15 (App Router)                   │
│                                                                               │
│  Landing → Goal → Calibration → Graph → Workspace → Reflection → Dashboard    │
│                                                                               │
│  Zustand (ephemeral UI + session machine mirror)                              │
│  TanStack Query (server truth, optimistic mastery)                            │
│  React Flow (learning DAG) · Framer Motion (pedagogically-motivated motion)   │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │ REST (typed client generated from OpenAPI)
┌──────────────────────────────────▼────────────────────────────────────────────┐
│                             API — FastAPI (async)                             │
│                                                                               │
│  features/                                                                    │
│    auth · goals · graph · session · turn · reflection · dashboard             │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  TUTOR KERNEL                                                        │    │
│  │                                                                      │    │
│  │  ① Deterministic Session State Machine   (pedagogical control plane)  │    │
│  │        the LLM cannot change state — only the orchestrator can        │    │
│  │                              │                                        │    │
│  │  ② LangGraph Agent Mesh      ▼           (generation plane)           │    │
│  │        Router → Planner → { Examiner ‖ Teacher ‖ Coach } →            │    │
│  │        Synthesizer → SocraticGuard → Memory                          │    │
│  │                              │                                        │    │
│  │  ③ Pedagogy Engine           ▼           (measurement plane)          │    │
│  │        BKT+forgetting · load heuristic · ZPD · metacog. quadrants ·   │    │
│  │        scaffold ladder · spaced repetition · DAG gating               │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  llm/  provider abstraction → Gemini · OpenAI · Anthropic · Mock              │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │ SQLAlchemy 2.0 async
┌──────────────────────────────────▼────────────────────────────────────────────┐
│              PostgreSQL + pgvector  (Supabase-compatible)                     │
│   identity · learning graphs · mastery · attempts · diagnoses ·               │
│   misconception index · reflections · trace forest · content chunks           │
└───────────────────────────────────────────────────────────────────────────────┘
```

Three planes, cleanly separated:

| Plane | Owner | Deterministic? | Why it is separate |
| --- | --- | --- | --- |
| **Control** | `pedagogy/state_machine.py` | Yes | LLMs drift. Pedagogy must not. |
| **Generation** | `agents/*` | No | Language is where the model earns its keep. |
| **Measurement** | `pedagogy/*` | Yes | Mastery claims must be auditable, not vibes. |

---

## 2. The heart: the Prior-Belief Gate

This is the interaction the whole product exists to protect.

Learner types: *"Explain gradient descent."*

A chatbot explains. **VectorOS refuses to explain, and instead elicits:**

```
ELICIT  →  "Before I say anything: write what you currently believe
            gradient descent is. Guessing is fine — wrong beliefs are
            the most useful thing you can give me right now."
```

The learner writes. The **Examiner** converts free text into a structured
`MentalModelDiagnosis`:

```jsonc
{
  "prior_estimate": 0.42,          // seeds the BKT prior for this learner+KC
  "anchors":       ["knows it is iterative", "connects slope to direction"],
  "misconceptions":[{ "claim": "learning rate is the number of steps",
                      "canonical": "learning rate scales step size, not count",
                      "severity": "high" }],
  "missing":       ["role of the loss surface", "why gradients point uphill"],
  "bloom_reached": "understand",
  "vocabulary_tier": 2
}
```

Only **then** does the Teacher speak — and it must:
1. name what the learner already had right (anchoring, protects motivation),
2. attack exactly the diagnosed misconception (deliberate practice, not lecture),
3. stop short of the parts the learner is about to derive (productive failure).

Everything downstream — difficulty of the first challenge, scaffold ceiling, vocabulary
tier, BKT prior — is a function of this diagnosis. **This is why the product is not a
wrapper: the explanation is causally downstream of a measurement of *this* human.**

---

## 3. The deterministic session state machine

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
  IDLE ──► ELICIT ──► DIAGNOSE ──► INSTRUCT ──► CHALLENGE ──► ATTEMPT
                                       ▲                          │
                                       │                          ▼
                                  (remediate)                 EVALUATE
                                       │                          │
                                       └──── COACH ◄──────────────┤ (incorrect)
                                              │                   │
                                              └──► ATTEMPT        │ (correct)
                                                                  ▼
                                          COMPLETE ◄── MASTERY ◄── REFLECT
```

Rules that are code, not prompt:

| Rule | Enforcement |
| --- | --- |
| No instruction before elicitation | `ELICIT` is the only legal successor of `IDLE` for an unseen node |
| No answer before attempt | `EVALUATE` unreachable without an `ATTEMPT` row |
| Confidence is mandatory | `POST /turn` rejects an attempt payload with `confidence = null` |
| Coach escalates one rung at a time | `scaffold_level` may only increase by 1, and only after a learner reply |
| No progression without recall | `MASTERY` unreachable without a passing `REFLECT` |
| No node without prerequisites | `graph.unlockable()` requires all parents ≥ `MASTERY_THRESHOLD` |

Every transition is persisted to `agent_events` with its trigger, so any mastery claim is
replayable. That is the "Trace Forest" idea, reduced to something a startup can actually
operate: an append-only event log keyed by `(session, node, agent)` at three granularities
(session summary → turn → raw agent IO).

---

## 4. Agent mesh (LangGraph)

| Agent | Model class | Responsibility | Hard constraint |
| --- | --- | --- | --- |
| **Router** | fast | Classify learner input: `attempt · question · answer_demand · reflection · meta` | Must return one enum. Cheap + hot path. |
| **Planner** | **deterministic** | Choose next node from DAG × mastery × review-debt | Pure Python (`graph/service.py::frontier`). May only select unlocked nodes. |
| **Examiner** | balanced | Diagnose mental model / grade attempt into misconception taxonomy | Never speaks to the learner |
| **Teacher** | deep | Calibrated instruction grounded in retrieved chunks | Must cite chunk ids; must not pre-empt the challenge |
| **Coach** | deep | Exactly one Socratic move at `scaffold_level` | Output ≤ 2 sentences, must end in `?` for levels 1–2 |
| **Reflection** | balanced | Score learner's own summary against KC canonical model | Returns coverage + omissions, never the summary itself |
| **Memory** | **deterministic** | Compute profile deltas, weakness lifecycle, session consolidation | Pure function; the service applies the result |
| **Synthesizer** | **deterministic** | Assemble the guarded moves into one learner-facing message | Re-generating already-guarded text would reintroduce the drift the guard just removed |

Three of the eight are deliberately **not** model calls. Planning over a DAG with
a mastery threshold is a sort, not a judgement; the weakness lifecycle is a
counter; and synthesis of already-guarded parts is concatenation. Using a model
for any of them would add latency, cost and non-determinism to decisions that
have exactly one right answer — and would make the mastery number unauditable.
A `SYNTHESIZER` prompt ships for deployments that want a smoother single voice,
but the default trusts the moves.

`Examiner`, `Teacher` and `Coach` execute **concurrently** where the state permits, because
serialised multi-agent latency compounds and engagement dies past ~4s.

### SocraticGuard (the third defence layer)

After synthesis, before emit:

1. **Leak detection** — cosine similarity between the draft and the challenge's private
   `expected_reasoning` (real embeddings against a network provider; a hashed
   bag-of-words vector offline — see `LIMITATIONS.md`), plus a fixed set of forbidden
   lexical patterns (`"the answer is"`, `"here's the solution"`, and similar), plus a
   check for whether the draft simply enumerates the private acceptance criteria.
2. **Move-shape check** — at scaffold rungs 1–2, the message must end in a question mark.
3. **Length check** — coach turns are capped; verbosity adds extraneous load.

On violation: one bounded regeneration with a stricter contract, then a deterministic
fallback question. Never a silent leak.

### Anti-offload circuit

`Router → answer_demand` triggers *Refusal & Pivot*, and increments
`session.offload_attempts`. At 3, the client **locks free-text input** and shows a
prompt asking the learner to name, in a sentence, one specific part of the problem
they *do* understand (`EngagementLock`, `POST /sessions/{id}/unlock`, minimum 4 words,
server-validated). Free text returns only after that is submitted. This is deliberately
a low bar — the goal is to interrupt the reflex of demanding an answer, not to gate the
session behind a hard task. (An earlier draft of this document described a richer
concept-map/fill-in-the-blank interaction here; that was never built. This paragraph now
describes the shipped implementation.)

---

## 5. Measurement plane

### 5.1 Bayesian Knowledge Tracing, extended

Classic BKT posterior, plus three extensions the research demands:

- **Measurement is separated from learning.** Textbook BKT applies the learning
  transition in the same step as the observation, on the grounds that every
  practice item is also a learning opportunity. That produces a result we cannot
  ship: from a low prior, a confidently *wrong* answer raises the estimate,
  because the `(1−post)·learn` term outweighs the evidence. We measured exactly
  that during development — 0.15 → 0.44 on a wrong answer. A mastery number that
  rises when you are wrong is worse than no number, because the learner will
  correctly stop believing it. So `update()` observes only, and
  `apply_instruction()` applies the transition at the point where teaching
  actually happens, scaled by how substantial that teaching was.
- **Forgetting.** `P(L_t) ← P(L_t)·(1-F)` on update, and continuous decay between
  sessions: `p ← floor + (p - floor)·2^(-Δt/half_life)`. Mastery is perishable, so
  review is schedulable.
- **Confidence weighting.** The learner's pre-submission confidence modulates the
  evidence strength. *Wrong + certain* is a blind spot: it drives mastery down harder than
  *wrong + unsure*. *Right + unsure* is treated as partly guess-like and moves mastery
  less.
- **Scaffold discounting.** A correct answer produced at scaffold level 4 is weaker
  evidence than one at level 0; effective slip/guess are adjusted by the assistance
  received. Otherwise the tutor can talk the learner into fake mastery.

### 5.2 Cognitive load heuristic (1–9)

```
CL = 0.5 + 1.0·G + 4.5·(1 − A) + 0.1·Q + 1.0·T
     G = task difficulty      A = recent accuracy
     Q = interaction fatigue  T = task-type weight
```
Latency is folded into `Q`: long silences and rapid-fire retries both raise fatigue.

**Naming note.** The 1–9 range and general shape were inspired by Paas's subjective
mental-effort rating scale, but this is a formula over behavioural telemetry with
coefficients we chose — it is **not** the Paas instrument, which is a post-task
self-report question. An earlier draft of this document called it "the Paas scale";
that was a misattribution and has been corrected here and in code (`pedagogy/load.py`).
The heuristic is unvalidated against any ground-truth load measure. See `LIMITATIONS.md`.

### 5.3 ZPD targeting

Pick the challenge whose *predicted* success probability lands in **[0.5, 0.8]**.
`p̂ = P(L)·(1−slip) + (1−P(L))·guess`, ranked against candidate difficulties.
Below the band → boredom. Above → overload. The band *is* the personalisation.

### 5.4 Metacognitive quadrants

|  | High confidence | Low confidence |
| --- | --- | --- |
| **Correct** | Conscious competence → Automaticity | *Fragile* — knows more than they think |
| **Incorrect** | **Unconscious incompetence** (blind spot, top remediation priority) | Conscious incompetence — healthy, coachable |

Blind spots are the single highest-value signal in the system and are surfaced explicitly
on the dashboard as **Calibration**.

### 5.5 Cognitive Debt

A first-class, learner-visible KPI:

```
debt = w₁·hint_dependency + w₂·offload_attempts + w₃·scaffold_reliance − w₄·unaided_wins
```

It quantifies "how much of this progress was yours". Making it visible turns the avoidance
of cognitive offloading into something a learner can optimise.

---

## 5.6 The Understanding Shift

The closing screen of every concept, and the product's signature moment.

Two passages of the learner's own writing, side by side: the Prior-Belief Gate
answer given *before any instruction*, and the free-recall answer given *after*,
with the material hidden. Between them, the misconceptions the Examiner named,
struck through as they were cleared.

Assembled entirely from the ledger (`attempts`, `reflections`, `misconceptions`,
`mastery_states`) — **nothing on it is generated**, so nothing can be
embellished. It exists only because the system asks before it answers: a product
that explains first has no "before" to show, because it never asked.

Served by `GET /api/sessions/{id}/shift`.

A note on the design: a misconception needs **two independent clears** before it
closes (one correct application *and* one correct unaided recall), so a
first-pass learner sees "cleared 1 of 2" rather than a binary failure. Making
that standard visible is better than hiding it — it teaches the learner what the
system counts as evidence.

---

## 6. Data model

```
users ─┬─ learner_profiles          (3D profile: history · weaknesses · pedagogy notes)
       ├─ learning_graphs ──┬─ concept_nodes ──┬─ node_edges (prereq DAG)
       │                    │                  ├─ content_chunks (RAG, pgvector)
       │                    │                  └─ mastery_states
       ├─ learning_sessions ──┬─ attempts ──── diagnoses
       │                      ├─ reflections
       │                      └─ agent_events  (trace forest)
       ├─ misconceptions      (weakness index, active/resolved)
       └─ review_schedule     (spaced repetition queue)
```

Key columns and their pedagogical purpose are documented inline in
`backend/app/db/models.py`. Highlights:

- `concept_nodes.canonical_model` — the expert mental model. Used by Reflection scoring
  and by SocraticGuard leak detection. **Never sent to the learner verbatim.**
- `concept_nodes.misconception_bank` — author-written wrong models with lexical
  trigger phrases; lets the Examiner classify against a fixed taxonomy rather than
  free-associate. (Distractor *generation* from this bank — producing new
  misconception-based multiple-choice options — is not implemented; the bank is
  currently read-only reference data for diagnosis.)
- `attempts.scaffold_level` + `attempts.confidence` + `attempts.latency_ms` — the three
  columns that make mastery honest.
- `agent_events` — every agent call: which agent, which model, latency, token counts,
  guard verdict, and the state transition it produced. (No prompt content or prompt
  hash is stored — only the structured payload each agent returned.)

Embeddings use `pgvector` on Postgres and degrade to a JSON column with in-process cosine
on SQLite, so the whole stack runs on a laptop with zero infrastructure.

---

## 7. Provider abstraction

```python
class LLMProvider(Protocol):
    async def complete(self, req: ChatRequest) -> ChatResponse: ...
    async def structured(self, req: ChatRequest, schema: type[T]) -> T: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- Agents never import a vendor SDK. They ask the registry for a **capability tier**
  (`fast` / `balanced` / `deep`), and deployment config maps tiers → models.
- `MockProvider` is deterministic and offline: the entire pedagogical loop, all tests, and
  a full product demo run with **no API key**. This is a deliberate decision — the
  control flow (state machine, scaffold ladder, guard) is what we are betting the
  product's integrity on, and none of it requires a specific model vendor to hold.
  Whether that control flow constitutes a defensible moat is a business claim, not an
  engineering one, and it is untested — see `LIMITATIONS.md` and `FUTURE_WORK.md`.

---

## 8. Frontend architecture

Feature-sliced, not layer-sliced:

```
src/features/{landing,onboarding,graph,workspace,reflection,dashboard}/
    components/   hooks/   api.ts   types.ts
src/components/ui/     — primitives (shadcn/ui conventions)
src/lib/               — api client, motion tokens, formatters
src/stores/            — Zustand: session machine mirror, UI state
```

Design language: Linear's density, Apple's restraint, Raycast's speed. Dark-first,
near-black canvas, a single electric accent, one typographic scale, generous negative
space, zero decorative gradients.

**Motion is pedagogical, not decorative.** Each animation encodes a learning event:

| Motion | Encodes |
| --- | --- |
| Node unlock: scale + glow bloom | Earned access — access to advanced ideas is sequential |
| Mastery ring fill | Probability, not a checkmark — knowledge is graded and perishable |
| Thinking-timer sweep before "Request guidance" unlocks | Productive struggle has a floor |
| Confidence slider resistance | Deliberate metacognitive commitment |
| Coach panel slides *in from the side*, never replacing your work | The learner's thinking stays primary |

**Anti-chat.** There is no blank chat box on the workspace by default. The primary surface
is a *thinking canvas*. The Socratic panel appears only after an attempt, or after the
struggle timer elapses. The medium dictates the behaviour: build for productivity and you
get a demand for answers.

---

## 9. What we deliberately did NOT build

- **No streaming token firehose into a chat log.** Streaming a lecture optimises the wrong
  thing.
- **No "generate me a course/textbook/video".** Passive consumption does not encode.
- **No deep-neural knowledge tracing in the MVP.** DKT/AKT need volume we do not have, and
  a neural model that cannot explain a mastery claim is unshippable in education.
  Extended-BKT is interpretable *today* and the `KnowledgeTracer` protocol makes DKT a
  drop-in later.
- **No biometrics.** Webcam cognitive-load tracking is in the research; it is a
  consent-and-trust catastrophe for a v1.

---

## 10. Repo layout

```
vectoros/
├─ README.md                ← philosophy, quick start
├─ PROJECT_OVERVIEW.md       ← what this is, for a first-time reader
├─ ARCHITECTURE.md          ← you are here
├─ DESIGN_DECISIONS.md      ← why, not just what
├─ LIMITATIONS.md           ← what is not yet true
├─ FUTURE_WORK.md           ← V1 done / V2 planned / research hypotheses
├─ DEMO.md
├─ docker-compose.yml       ← db + api + web
├─ .env.example
├─ Makefile
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/          config · logging · errors · security
│  │  ├─ db/            session · models · seed
│  │  ├─ pedagogy/      bkt · load · zpd · scaffold · schedule · state_machine
│  │  ├─ llm/           base · registry · gemini · openai · anthropic · mock
│  │  ├─ agents/        state · graph · {router,planner,examiner,teacher,coach,
│  │  │                 reflection,synthesizer,memory} · guard · prompts
│  │  └─ features/      auth · goals · graph · session · dashboard
│  └─ tests/
└─ frontend/
   └─ src/{app,features,components,lib,stores}
```
