<div align="center">

# VectorOS

**Understanding before explanation.**

</div>

---

## The idea

When someone asks a question, most software tries to answer it as fast and as
well as possible. That is the right goal for almost every kind of software.

We think it is the wrong goal for a tutor.

If a system answers before the learner has committed to what they think the
answer is, two things are lost. First, the system never finds out what the
learner actually believes — so whatever it says next is generic, calibrated to
nobody in particular. Second, the learner never does the part of the work that
research on learning consistently identifies as where retention comes from:
retrieving, guessing, committing, being wrong, and then having the gap between
what they believed and what is true made visible to them.

So VectorOS is built around one rule, enforced in code rather than requested in
a prompt: **the system asks what you believe before it tells you anything.**
Everything else in this repository — the diagnosis step, the difficulty
targeting, the refusal to hand over answers, the gate that requires you to
recall an idea from memory before it counts as learned — exists to make that
one rule hold under pressure and to make its consequences visible.

This is a working implementation of that idea, not a finished product and not
a validated one. What follows describes exactly what exists, what has been
tested, and what has not.

---

## The interaction

You ask: *"Explain gradient descent."*

VectorOS does not explain. It asks a question back:

> *"Before I explain anything: in your own words, what do you already believe
> this is? Guess if you have to — a wrong guess tells me more about how to
> teach you than a blank page does."*

You answer — badly, half-right, whatever it actually is. That answer is parsed
into a structured diagnosis: what you already have right, which specific
misconceptions are present, what's missing. Only then does the system speak,
and what it says is shaped by that diagnosis, not generic.

If you later type *"just tell me the answer,"* it declines — not with a canned
refusal, but by naming something you're already close to and handing you a
smaller question instead. Do that three times and free-text input locks until
you write one sentence about a part of the problem you *do* understand. This
is not a system prompt asking a model to be patient. It's a state machine with
no transition from *"challenge issued"* to *"answer given,"* checked at the
control-flow level, with an output filter behind it that rejects generated
text if it's too semantically close to the private answer key. Prompts still
do real work here — they're what makes the tutor sound like a person and not
a form — but the guarantee that it won't fold under pressure does not come
from asking the model nicely. See
[`pedagogy/state_machine.py`](backend/app/pedagogy/state_machine.py) and
[`agents/guard.py`](backend/app/agents/guard.py).

When you finally answer correctly, the system still doesn't move on. It hides
the material and asks you to explain the idea back, from memory, in your own
words — because getting an answer right and being able to reconstruct the idea
unaided are different skills, and only the interaction loop enforces that the
second one is what counts.

## The Understanding Shift

This is the moment the whole design is for, and the one artifact in this
repository that we think is genuinely worth your time.

When a concept closes, VectorOS shows you two passages of your own writing,
side by side:

- **What you believed** — the answer you gave before any instruction, at the
  very first question.
- **What you can now reconstruct** — the answer you gave from memory, at the
  end, with every explanation hidden.

Between them: the specific beliefs the system identified as wrong, struck
through as you demonstrated — twice, independently, not once — that you no
longer held them.

**Neither passage is generated.** Both are retrieved verbatim from the
interaction log and rendered as-is. There is no LLM call anywhere in the code
path that builds this screen
([`session/service.py::understanding_shift`](backend/app/features/session/service.py)).
It is a database query wearing a good interface.

We think this is the clearest demonstration of the thesis available: **a
system that answers first has no "before" to show, because it never asked.**
This screen is not possible to build without the elicitation step existing
upstream of everything else. That's the whole argument, made visible instead
of argued.

---

## What is actually implemented (and tested)

- A deterministic state machine gates every legal transition a session can
  make — there is no code path from an unattempted challenge to the answer.
  [`pedagogy/state_machine.py`](backend/app/pedagogy/state_machine.py)
- A scaffolding ladder that can only rise one step at a time, only after the
  learner replies, with no step that reveals the answer.
  [`pedagogy/scaffold.py`](backend/app/pedagogy/scaffold.py)
- An output filter that checks generated coaching text against the private
  answer key by lexical pattern, criteria overlap, and embedding similarity,
  with a deterministic fallback question if it fails.
  [`agents/guard.py`](backend/app/agents/guard.py)
- A knowledge-tracing model (extended Bayesian Knowledge Tracing) that treats
  *being tested* and *being taught* as separate events — a distinction we
  added after finding, during our own testing, that the standard formulation
  can raise a mastery estimate immediately following a confidently wrong
  answer. [`pedagogy/bkt.py`](backend/app/pedagogy/bkt.py)
- Mastery that decays over time rather than being asserted permanent, and
  progression gated on free recall rather than on a correct answer alone.
- Confidence collected *before* an answer is graded, which is what makes it
  possible to detect the case ordinary grading cannot see: being wrong while
  certain.
- The full pedagogical loop — diagnosis, coaching, knowledge tracing, the
  output guard — runs offline and deterministically with no API key, which is
  also what the automated test suite exercises (62 backend tests, currently
  passing; see [`LIMITATIONS.md`](LIMITATIONS.md) for what that coverage does
  and does not include).

```bash
git clone <this repo> && cd vectoros
make install && make seed
make api      # http://localhost:8000
make web      # http://localhost:3000
```

## What is not yet true

We would rather you find this out from us than notice it yourself.

- **No one has measured whether this produces better learning outcomes than
  the alternative.** There is no control group, no pre/post instrument, no
  learner other than the people who built it. The interaction design is
  motivated by learning-science research; it has not been validated in this
  implementation.
- **The claim that this resists conversational pressure better than a
  prompt-only tutor has not been tested against a real adversarial
  conversation with a frontier model.** The architecture is built to make
  that resistance structural rather than requested — but "structural"
  describes the mechanism, not a measured result.
- **The knowledge-tracing parameters are not fit to data.** They're
  reasonable starting values with a documented rationale, not values learned
  from learner responses.
- **The cognitive-load estimate is a heuristic we built, not a validated
  psychometric instrument** — see the note in
  [`pedagogy/load.py`](backend/app/pedagogy/load.py) if you're familiar with
  Paas's mental-effort scale, which this is related to but is not.
- **Content is hand-authored and small** — three learning graphs, seventeen
  concepts. The architecture is built to scale; the curriculum-authoring
  process is not, yet.

The complete, unflattering list is in [`LIMITATIONS.md`](LIMITATIONS.md). We
wrote it ourselves and we'd rather it be too long than too short.

---

## Reading this repository

| Document | What it's for |
| --- | --- |
| [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | What this is, in plain terms, before the architecture |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the system is built, with citations to code |
| [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) | Why it's built this way, including the mistakes we found and fixed |
| [`LIMITATIONS.md`](LIMITATIONS.md) | What is not yet validated, tested, or true |
| [`FUTURE_WORK.md`](FUTURE_WORK.md) | What's shipped, what's planned, and what's an untested hypothesis — kept separate |
| [`DEMO.md`](DEMO.md) | A seven-minute walkthrough script |

## Development

```bash
make check     # lint + typecheck + tests, both sides
make test      # backend suite
make up        # full stack in Docker (Postgres + pgvector)
```

The test suite encodes product invariants as executable assertions — mastery
falls after a confidently wrong answer, the scaffold ladder cannot skip a
rung, instruction is unreachable before elicitation, the private answer key
never reaches the client. What it does not yet cover is listed in
[`LIMITATIONS.md`](LIMITATIONS.md), most importantly: the real LLM provider
integrations (Gemini, OpenAI, Anthropic) have close to no automated test
coverage today, because development so far has run almost entirely on the
offline provider.

## Configuration

Every value has a working default; `.env` is optional. See
[`.env.example`](.env.example) for the full set, or `GET /api/pedagogy` on a
running instance for every tuned constant the system is currently using.

---

<div align="center">
<sub>A vertical slice, not a finished product. See LIMITATIONS.md before drawing conclusions from it.</sub>
</div>
