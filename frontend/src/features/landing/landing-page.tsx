"use client";

import { motion } from "framer-motion";
import { ArrowRight, Brain, GitBranch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { VectorField } from "@/features/landing/vector-field";
import { AppFooter } from "@/components/app-footer";
import { Button } from "@/components/ui/button";
import { ease, riseIn, stagger } from "@/lib/motion";
import { useLearner } from "@/stores/learner";

/**
 * The landing page has one job: make the thesis unmissable before anyone
 * clicks anything. So the largest thing on the screen is the claim, not the
 * product name, and there is exactly one call to action.
 */

const PILLARS = [
  {
    icon: Brain,
    title: "It asks before it answers",
    body: "Say “explain gradient descent” and it will not explain. It asks what you already believe, reads your model, and teaches the gap it actually finds.",
  },
  {
    icon: GitBranch,
    title: "Concepts are earned, not browsed",
    body: "Your curriculum is a dependency graph. A node stays locked until the tracer says its prerequisites are genuinely held — not merely visited.",
  },
  {
    icon: ShieldCheck,
    title: "It will not fold",
    body: "Ask for the answer three times and it still will not hand it over. The Socratic line is a state machine and an output guard, not a system prompt that gives way under pressure.",
  },
];

export function LandingPage() {
  const learner = useLearner((s) => s.user);
  const graphId = useLearner((s) => s.activeGraphId);

  // Zustand rehydrates from storage after mount, so committing to either copy
  // during SSR guarantees a flash of the wrong one for returning learners.
  const [ready, setReady] = React.useState(false);
  React.useEffect(() => setReady(true), []);

  const returning = ready && Boolean(learner);
  const destination = returning && graphId ? `/graph/${graphId}` : "/start";

  return (
    <main className="relative min-h-screen overflow-hidden bg-canvas">
      <VectorField className="pointer-events-none absolute inset-0 h-[70vh] w-full opacity-70" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-canvas/70 to-canvas" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[70vh] bg-grid opacity-[0.35]" />

      {/* Nav */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: ease.out }}
        className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-6"
      >
        {/* The creator signature used to live here, beside the wordmark. Removed:
            opening the About modal from a header trigger competed visually with
            the hero and the modal itself, and the footer already carries the
            same attribution and opens the same modal — see AppFooter. */}
        <div className="flex items-center gap-2.5">
          <Mark />
          <span className="text-[15px] font-medium tracking-tight">VectorOS</span>
        </div>
        <Link
          href={destination}
          className="rounded-md px-2 py-1 text-[13px] text-muted transition-colors hover:text-ink focus-ring"
        >
          {returning ? "Continue" : "Begin"}
        </Link>
      </motion.header>

      {/* Hero */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-24 pt-16 sm:pt-24">
        <motion.div variants={stagger(0.1, 0.09)} initial="hidden" animate="show">
          {/* The thesis, in the same words the README and ARCHITECTURE use.
              Slightly tighter tracking than the 0.2em elsewhere so the longer
              phrase still holds one line on a 375px viewport. */}
          <motion.p
            variants={riseIn}
            className="text-2xs font-medium uppercase tracking-[0.17em] text-accent"
          >
            Understanding before explanation
          </motion.p>

          <motion.h1
            variants={riseIn}
            className="mt-6 max-w-3xl text-[clamp(2.6rem,7vw,5rem)] font-semibold leading-[0.98] tracking-[-0.03em]"
          >
            An answer is not
            <br />
            an education.
          </motion.h1>

          <motion.p
            variants={riseIn}
            className="mt-8 max-w-xl text-[17px] leading-relaxed text-muted"
          >
            A chatbot resolves your question and moves on — and you end up less able than
            before you asked. VectorOS does the opposite. It makes you think first, works out
            what you actually believe, and stays with you until you can rebuild the idea
            without it.
          </motion.p>

          <motion.div variants={riseIn} className="mt-10 flex flex-wrap items-center gap-4">
            <Link href={destination}>
              <Button size="lg" className="group">
                {returning ? `Continue, ${learner?.display_name.split(" ")[0]}` : "Begin learning"}
                <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
              </Button>
            </Link>
            <span className="text-[13px] text-faint">
              {returning
                ? "Your mastery has been decaying while you were away."
                : "No sign-up. Nothing to install. Runs without an API key."}
            </span>
          </motion.div>
        </motion.div>

        {/* The interaction, shown rather than described. */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.5, ease: ease.out }}
          className="mt-24"
        >
          <ThesisDemo />
        </motion.div>

        {/* Pillars */}
        <motion.div
          variants={stagger(0.1, 0.08)}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-80px" }}
          className="mt-28 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-3"
        >
          {PILLARS.map(({ icon: Icon, title, body }) => (
            <motion.div key={title} variants={riseIn} className="group bg-canvas p-7">
              <Icon className="h-4.5 w-4.5 text-accent" strokeWidth={1.6} />
              <h3 className="mt-5 text-[15px] font-medium tracking-tight">{title}</h3>
              <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted">{body}</p>
            </motion.div>
          ))}
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto mt-28 max-w-lg text-center text-[15px] leading-relaxed text-muted"
        >
          Everything the tutor claims about you is inspectable — which agent ran, what the
          guard decided, and every state transition behind a mastery score.
        </motion.p>
      </section>

      <div className="relative z-10">
        <AppFooter />
      </div>
    </main>
  );
}

function Mark() {
  return (
    <div className="relative grid h-7 w-7 place-items-center rounded-lg border border-line bg-raised">
      <motion.span
        className="absolute inset-0 rounded-lg bg-accent/20 blur-md"
        animate={{ opacity: [0.35, 0.75, 0.35] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
        <path
          d="M1.5 2.5 L7 11.5 L12.5 2.5"
          stroke="rgb(var(--accent))"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

/**
 * A side-by-side of what every other tool does and what this one does. It is the
 * fastest way to communicate the product, and it is honest — the left column is
 * a fair description of a good chatbot, not a strawman.
 */
function ThesisDemo() {
  const [step, setStep] = React.useState(0);

  React.useEffect(() => {
    const id = window.setInterval(() => setStep((s) => (s + 1) % 3), 2800);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-2">
      <div className="bg-canvas p-8">
        <div className="text-2xs font-medium uppercase tracking-[0.14em] text-faint">
          Every other assistant
        </div>
        <p className="mt-6 text-[15px] text-muted">“Explain gradient descent.”</p>
        <div className="mt-5 space-y-2.5">
          {[100, 92, 76].map((w, i) => (
            <motion.div
              key={i}
              className="h-2.5 rounded-full bg-line"
              style={{ width: `${w}%` }}
              animate={{ opacity: [0.4, 0.85, 0.4] }}
              transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.12 }}
            />
          ))}
        </div>
        <p className="mt-6 text-[13px] leading-relaxed text-faint">
          Fluent, immediate, and gone. You read it, you nod, and two weeks later you cannot
          reconstruct a line of it.
        </p>
      </div>

      <div className="relative bg-surface/60 p-8">
        <div className="absolute inset-0 bg-gradient-to-br from-accent/[0.07] to-transparent" />
        <div className="relative">
          <div className="text-2xs font-medium uppercase tracking-[0.14em] text-accent">
            VectorOS
          </div>
          <p className="mt-6 text-[15px] text-muted">“Explain gradient descent.”</p>

          <motion.p
            key={step}
            initial={{ opacity: 0, y: 8, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.5, ease: ease.out }}
            className="mt-5 text-[15px] leading-relaxed text-ink"
          >
            {
              [
                "Before I explain anything — in your own words, what do you already believe it is?",
                "Guess if you have to. A wrong guess tells me more than a blank page does.",
                "I would rather find out now than after an explanation that missed you.",
              ][step]
            }
          </motion.p>

          <div className="mt-6 flex items-center gap-2">
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="h-1 rounded-full bg-accent"
                animate={{ width: i === step ? 22 : 6, opacity: i === step ? 1 : 0.3 }}
                transition={{ duration: 0.4, ease: ease.out }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
