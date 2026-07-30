# Project Overview

**Thesis: understanding before explanation.** A system should know what a
learner already believes before it tells them anything — and it should not
count a concept as learned until the learner can reconstruct it unaided. Every
design decision described in this repository exists in service of one or the
other half of that sentence.

This document is for a reader who wants to understand what VectorOS is before
deciding whether the architecture is worth their time. It says nothing that
isn't said elsewhere in the repository; it exists to say it first, plainly,
without code.

## The problem, as we see it

Large language models are very good at answering questions. For a learner,
that turns out to be a mixed blessing. Being given a correct, well-explained
answer feels like progress, and it is progress — on the task in front of you.
It is not the same thing as building the ability to do it again unaided, and
there is a real body of research suggesting the two can move in opposite
directions: fluent, immediate answers can raise performance on the task at
hand while lowering unaided performance afterward, because the effortful part
of learning — retrieving, guessing, being wrong, closing the gap yourself —
never happens.

Most AI tutoring products keep the chatbot's core behavior (resolve the
question, quickly, well) and add pedagogy around the edges: a system prompt
asking it to be "Socratic," a progress bar, a streak counter. We think that
keeps the part of the design that causes the problem and decorates around it.

## The bet

VectorOS is built on a different premise: **the system should not answer a
question until it knows what the learner already believes about it, and it
should not consider a concept learned until the learner can reconstruct it
without help.**

Both halves are enforced structurally, not requested via a system prompt:

- **Before instruction:** every new concept opens with a question about what
  the learner already believes, and the answer to that question determines
  everything that follows — what gets explained, in what register, at what
  difficulty. There is no code path that reaches an explanation without
  passing through this step first.
- **Before mastery:** a concept is not marked learned because the learner
  answered a question correctly. It requires a second, independent
  demonstration — free recall of the idea, from memory, with the material
  hidden — because answering correctly and being able to explain something
  unaided are measurably different skills.

Everything else in the codebase exists in service of these two constraints:
a scaffolding system that gives help gradually rather than all at once, a
knowledge-tracing model that estimates what a learner actually holds (and
lets that estimate decay over time, because memory does), and an output
filter that stops generated text from leaking an answer even when the
upstream logic intended something more restrained.

## What the product is, concretely

A learner picks a goal (currently: one of three small curricula — neural
network training dynamics, statistical reasoning, or distributed systems
intuition). Within a goal, concepts are arranged as a dependency graph rather
than a linear course; a concept is locked until its prerequisites are
genuinely held, not merely visited.

Opening a concept starts a session that moves through a fixed sequence:
elicit prior belief → diagnose it → teach the specific gap → issue a task
calibrated to be hard enough to matter and easy enough to be attemptable →
grade the reasoning, not just the answer → coach toward the answer without
giving it → require free recall → update the mastery estimate.

At the end, the learner sees the **Understanding Shift** — their own
before-and-after writing, side by side, with nothing generated. This is
described in detail in the [README](README.md) and is the artifact we would
point you to first if you only have a few minutes.

## What kind of thing this is, honestly

This is a working vertical slice of an idea, built to test whether the idea
is buildable and whether the resulting interaction feels like what we
intended. It is not:

- a validated learning intervention (no outcome study exists — see
  [`LIMITATIONS.md`](LIMITATIONS.md)),
- a content platform (seventeen hand-authored concepts, not a catalogue),
- or a finished product (no real authentication, no billing, no
  multi-tenant model, no instructor-facing surface).

It is a specific, checkable claim about how a tutoring system's control flow
should be structured, implemented far enough to interact with and to
evaluate on its own terms — including the parts of the claim we have not yet
been able to test.

## Who this is for

Three different readers will get different value from this repository, and
we've tried to write for each rather than force one narrative on all three:

- **If you want to *use* it:** run `make install && make seed && make api`
  and `make web`, then read [`DEMO.md`](DEMO.md).
- **If you want to understand *why* it's built this way:**
  [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) covers the reasoning, including
  places where an earlier, more obvious approach turned out to be wrong.
- **If you want to evaluate the claim it's making:** start with
  [`LIMITATIONS.md`](LIMITATIONS.md), not the architecture doc. Knowing what
  hasn't been shown is more useful than reading what has been built, if
  you're deciding whether to trust the thesis.
