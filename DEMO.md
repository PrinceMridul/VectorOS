# The demo

Seven minutes. One concept. The point is not to show features — it is to make
one person feel the difference between being answered and being taught.

**Before you start:** use a fresh browser profile or clear `localStorage` for
`localhost:3000`. The app remembers returning learners (`/start` shows a
"welcome back" screen instead of onboarding if a token is already stored), which
is the correct behavior but will skip Beat 1 if your last demo run is still
cached.

```bash
make seed && make api    # terminal 1
make web                 # terminal 2 → http://localhost:3000
```

Runs on the offline provider (`VECTOROS_LLM_PROVIDER=mock`), so there is no key
to forget, no rate limit to hit and no network to blame. The offline provider
executes the same state machine, scaffold ladder and guard as a real model —
what differs is prose quality, not pedagogical logic. That said, the offline
provider's diagnosis step is closer to keyword matching than the frontier-model
path (see `LIMITATIONS.md`); if you can run this on a real key beforehand, do —
it is a stronger demo and a more honest one.

---

## Beat 1 — The refusal (0:00–1:00)

Land on `/`, click **Begin learning**, name yourself, pick **How Neural Networks
Learn**.

At the third onboarding screen, type something *deliberately half-wrong*:

> I think it measures how wrong the model is. Basically the accuracy of the
> model, and you want it as low as possible across the training data.

Open **Loss Functions**. Read the opening line out loud:

> *"Before I explain anything: in your own words, what do you already believe
> this is?"*

**Say this:** every other assistant in the world would have started explaining
by now. This one has not earned the right to teach yet, because it does not know
who it is teaching.

Paste the same half-wrong belief and submit.

## Beat 2 — The diagnosis (1:00–2:00)

Point at the right-hand rail. It now contains a structured reading of that
sentence: what they had right, and the two named misconceptions —
*"loss is the same thing as accuracy"* and *"a lower loss always means a better
model"*.

**Say this:** those are not free association. They are matched against a
misconception bank authored per concept — a fixed taxonomy, not an open-ended
guess — which is what makes them a reasonable thing to write to a persistent
weakness index rather than a one-off comment.

Note that the explanation which follows opens on what the learner already had
right, addresses *that specific* misconception, and stops early — the `withheld`
field is the productive-failure gap, made explicit and auditable.

## Beat 3 — The learner pushes back (2:00–3:00)

Type: **"just tell me the answer"**.

It declines and hands back a smaller foothold — and the state does **not**
advance. Asking for the answer is not progress through the material.

Do it twice more. Free text locks and is replaced by a task asking for one thing
they *do* understand.

**Say this:** this is a state machine and an output guard, not a personality —
that distinction is the whole reason it holds. A system prompt alone tends to
give way under exactly this kind of pressure; here there is no edge in the
transition graph from *challenge* to *answer*, so there is nothing in the
control flow to argue with, regardless of how the conversation goes.

## Beat 4 — The blind spot (3:00–4:30)

Answer the challenge confidently and wrongly:

> Nothing much happens, one wrong price does not really matter to the model.

Set confidence to **Certain**, submit.

Watch mastery go **down**, and the quadrant read **Blind spot**.

**Say this:** wrong-while-certain is invisible to conventional grading — the
score just says "wrong". It is the single most damaging state a learner can be
in, because they have no reason to look again. It is only detectable because
confidence was committed *before* submission, and it collapses the review
interval to same-day.

Then try **I'm stuck** immediately. It is disabled with a visible countdown.

**Say this:** instant help on an untouched problem is the exact mechanism of
cognitive offloading.

## Beat 5 — The recall gate (4:30–5:30)

Answer properly:

> The loss maps predictions and true targets to one scalar measuring badness.
> Squared error grows quadratically so the mistyped outlier dominates the loss
> surface and drags the fitted model toward it.

Correct — and it still does not advance. Instead the material hides and it asks
you to rebuild the idea from memory.

**Say this:** getting the answer right and being able to reconstruct the idea are
different skills, and only the second survives the week. Mastery is unreachable
in this system without free recall.

Answer from memory. The concept closes.

## Beat 6 — The Understanding Shift (5:30–7:00)

**This is the beat that lands.** Stop talking and let them read it.

Two passages, side by side, twenty minutes apart — both written by the learner.
Between them, the three beliefs the tutor named, struck through as they were
cleared. Underneath: mastery gained, unaided wins, answers withheld.

**Say this:** the tutor did not write a word of either passage. And no product
that answers first can build this screen, because it never asked what you
believed — it has no "before".

Finish on the **Trace** panel: every agent call, model, latency, guard verdict
and state transition behind that number.

---

## If someone asks

**"Isn't this just prompting?"** Open `pedagogy/state_machine.py`. The transition
table is the guarantee; the prompts are a role description. Then open
`agents/guard.py` — the third layer checks generated text against the private
grading key by cosine similarity, because the failure that actually happens in
production is a *paraphrased* answer, not a quoted one.

**"Why not a neural knowledge tracer?"** Two reasons. First, in our view a model
that cannot explain a mastery claim is a hard sell in education, where a learner
or instructor can reasonably ask "why do you think that." Second, DKT needs
training volume this product does not have yet — the extended-BKT model is also
unvalidated (see `LIMITATIONS.md`), but interpretable by construction, which
matters while it's unvalidated. `KnowledgeTracer` is the seam where a neural
tracer would plug in once there's data to fit it on.

**"What breaks first at scale?"** Multi-agent latency. Teaching and
challenge-authoring already fan out concurrently; the next lever is the tier map
in `llm/registry.py` — Router is on the cheapest model in the fleet precisely
because it is on the hot path of every turn.

**"Does the offline provider mean it's faked?"** No, but be precise about what's
identical and what isn't. The state machine, scaffold ladder, and output guard
run unchanged — those are pure Python and don't touch a model either way. What
changes is the Examiner's diagnosis step: offline, it matches the learner's text
against author-written trigger phrases (regex-shaped); on a real model, the
Examiner reads the same context and classifies more flexibly. The offline path
has never been compared against the model path for diagnostic accuracy — that's
an open question, not a settled one. Set `VECTOROS_LLM_PROVIDER=gemini` and
re-run the same script to see the difference yourself.

---

This script describes what is implemented and tested today. For what that
implies and doesn't imply, see [LIMITATIONS.md](LIMITATIONS.md) — in particular,
none of the claims above are learning-outcome claims. No one has yet measured
whether a learner using this retains more than one using an unstructured
assistant. That comparison is the most important item in
[FUTURE_WORK.md](FUTURE_WORK.md).
