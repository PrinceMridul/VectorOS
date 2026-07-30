"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, Clock, Layers } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { CreatorSignature } from "@/components/creator-signature";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, tokenStore } from "@/lib/api";
import { ease } from "@/lib/motion";
import type { Goal } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useLearner } from "@/stores/learner";

type Step = "name" | "goal" | "prior";

/**
 * Onboarding is three questions, one per screen.
 *
 * The last one — "what do you already know about this?" — is the product in
 * miniature: before anything is planned or shown, the system asks the learner to
 * commit to what they currently believe. It is also the first place the learner
 * discovers that this thing wants them to write, which sets the expectation for
 * every session afterwards.
 */
export function OnboardingFlow() {
  const router = useRouter();
  const setUser = useLearner((s) => s.setUser);
  const setActiveGraph = useLearner((s) => s.setActiveGraph);
  const existing = useLearner((s) => s.user);
  const existingGraph = useLearner((s) => s.activeGraphId);

  const [step, setStep] = React.useState<Step>("name");
  const [name, setName] = React.useState("");
  const [goal, setGoal] = React.useState<Goal | null>(null);
  const [prior, setPrior] = React.useState("");

  const goals = useQuery({ queryKey: ["goals"], queryFn: api.goals });

  const begin = useMutation({
    mutationFn: async () => {
      if (!goal) throw new Error("No goal selected");
      // Only mint an identity when there isn't one — adding a second goal must
      // attach to the existing learner, not fork a stranger with the same name.
      if (!tokenStore.get() || !existing) {
        const auth = await api.start(name.trim() || "Learner");
        tokenStore.set(auth.token);
        setUser(auth.user);
      }
      return api.startGoal(goal.slug, prior.trim());
    },
    onSuccess: (started) => {
      setActiveGraph(started.graph_id);
      router.push(`/graph/${started.graph_id}`);
    },
  });

  const back = () => setStep(step === "prior" ? "goal" : "name");

  /**
   * Returning here with a learner already on this device used to mint a brand
   * new one, silently orphaning their mastery, misconceptions and history. For
   * a product whose entire promise is "it remembers you", that was the single
   * most damaging bug in the flow. Offer to continue first; starting fresh
   * stays available, but as a decision rather than an accident.
   */
  if (existing && step === "name") {
    return (
      <main className="relative flex min-h-screen items-center justify-center bg-canvas px-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-grid opacity-30" />
        <Panel key="welcome-back">
          <div className="relative z-10 max-w-lg">
            <p className="text-2xs font-medium uppercase tracking-[0.18em] text-accent">
              Welcome back
            </p>
            <h1 className="mt-5 text-[clamp(1.75rem,4vw,2.5rem)] font-semibold leading-[1.1] tracking-[-0.02em]">
              {existing.display_name}, your model is where you left it.
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed text-muted">
              Mastery decays while you are away, so some concepts may have slipped
              onto your review queue. That is the system working, not a penalty.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Button
                size="lg"
                onClick={() =>
                  router.push(existingGraph ? `/graph/${existingGraph}` : "/progress")
                }
              >
                Continue learning
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button size="lg" variant="ghost" onClick={() => setStep("goal")}>
                Add another goal
              </Button>
              <button
                onClick={() => {
                  tokenStore.clear();
                  setUser(null);
                  setActiveGraph(null);
                }}
                className="rounded-md px-2 py-1 text-[13px] text-faint transition-colors hover:text-muted focus-ring"
              >
                Start as someone else
              </button>
            </div>
          </div>
        </Panel>
      </main>
    );
  }

  return (
    <main className="relative flex min-h-screen flex-col bg-canvas">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-grid opacity-30" />

      <header className="relative z-10 mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-6">
        <button
          onClick={back}
          className={cn(
            "flex items-center gap-2 rounded-md px-2 py-1 text-[13px] text-faint transition-colors focus-ring",
            step === "name" ? "pointer-events-none opacity-0" : "hover:text-ink",
          )}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>
        <div className="flex items-center gap-4">
          <div className="hidden sm:block">
            <CreatorSignature />
          </div>
          <StepDots step={step} />
        </div>
      </header>

      <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-6 pb-24">
        <AnimatePresence mode="wait">
          {step === "name" && (
            <Panel key="name">
              <Prompt
                eyebrow="First"
                title="What should the tutor call you?"
                subtitle="Everything you do from here is remembered against this name — mastery, misconceptions, and how you learn best."
              />
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && name.trim()) setStep("goal");
                }}
                placeholder="Your name"
                className="mt-10 w-full border-b border-line bg-transparent pb-3 text-[28px] font-light tracking-tight text-ink outline-none transition-colors placeholder:text-faint/60 focus:border-accent"
              />
              <Actions>
                <Button size="lg" disabled={!name.trim()} onClick={() => setStep("goal")}>
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Actions>
            </Panel>
          )}

          {step === "goal" && (
            <Panel key="goal">
              <Prompt
                eyebrow="Second"
                title={`What are you here to understand, ${
                  (existing?.display_name ?? name).split(" ")[0] || "friend"
                }?`}
                subtitle="Each of these is a dependency graph, not a playlist. You will open one concept at a time, and the next one unlocks only when the previous is genuinely held."
              />
              <div className="mt-8 space-y-2">
                {goals.isLoading
                  ? [0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="h-[86px] animate-pulse rounded-xl border border-line bg-surface/40"
                      />
                    ))
                  : goals.data?.map((g, index) => (
                      <GoalCard
                        key={g.slug}
                        goal={g}
                        index={index}
                        selected={goal?.slug === g.slug}
                        onSelect={() => setGoal(g)}
                      />
                    ))}
                {goals.isError && (
                  <p className="rounded-xl border border-state-alert/30 bg-state-alert/10 px-4 py-3 text-[13px] text-state-alert">
                    Could not reach the tutor service. Is the API running on{" "}
                    {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}?
                  </p>
                )}
              </div>
              <Actions>
                <Button size="lg" disabled={!goal} onClick={() => setStep("prior")}>
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Actions>
            </Panel>
          )}

          {step === "prior" && goal && (
            <Panel key="prior">
              <Prompt
                eyebrow="Third — and the only one that matters"
                title={`What do you already know about ${goal.title.toLowerCase()}?`}
                subtitle="Write it badly. Guess. Contradict yourself. A confused answer tells the tutor exactly where to start; a blank one tells it nothing, and it will have to find out the slow way."
              />
              <Textarea
                autoFocus
                value={prior}
                onChange={(e) => setPrior(e.target.value)}
                rows={5}
                placeholder="I think it's roughly…"
                className="mt-8 min-h-[140px] text-base"
              />
              <p className="mt-3 text-[12.5px] text-faint">
                This is never graded. It seeds your starting estimate — and every concept you
                open will ask you the same thing again, in more detail.
              </p>
              <Actions>
                <Button
                  size="lg"
                  loading={begin.isPending}
                  disabled={prior.trim().length < 8}
                  onClick={() => begin.mutate()}
                >
                  {begin.isPending ? "Building your graph" : "Build my learning graph"}
                  {!begin.isPending && <ArrowRight className="h-4 w-4" />}
                </Button>
                {prior.trim().length < 8 && (
                  <span className="text-[13px] text-faint">A sentence is enough.</span>
                )}
              </Actions>
              {begin.isError && (
                <p className="mt-4 text-[13px] text-state-alert">
                  Something went wrong starting your path. Try again.
                </p>
              )}
            </Panel>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, y: -12, filter: "blur(4px)" }}
      transition={{ duration: 0.35, ease: ease.out }}
    >
      {children}
    </motion.div>
  );
}

function Prompt({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <p className="text-2xs font-medium uppercase tracking-[0.18em] text-accent">{eyebrow}</p>
      <h1 className="mt-5 text-[clamp(1.75rem,4vw,2.5rem)] font-semibold leading-[1.1] tracking-[-0.02em]">
        {title}
      </h1>
      <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">{subtitle}</p>
    </div>
  );
}

function Actions({ children }: { children: React.ReactNode }) {
  return <div className="mt-10 flex flex-wrap items-center gap-4">{children}</div>;
}

function GoalCard({
  goal,
  index,
  selected,
  onSelect,
}: {
  goal: Goal;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3, ease: ease.out }}
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "group relative w-full overflow-hidden rounded-xl border p-5 text-left transition-all duration-200 focus-ring",
        selected
          ? "border-accent/60 bg-accent/[0.06] shadow-glow"
          : "border-line bg-surface/50 hover:border-faint hover:bg-surface",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h3 className="text-[15px] font-medium tracking-tight">{goal.title}</h3>
            <AnimatePresence>
              {selected && (
                <motion.span
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  className="grid h-4 w-4 place-items-center rounded-full bg-accent"
                >
                  <Check className="h-2.5 w-2.5 text-white" strokeWidth={3} />
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{goal.description}</p>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-4 text-2xs text-faint">
        <span className="flex items-center gap-1.5">
          <Layers className="h-3 w-3" />
          {goal.node_count} concepts
        </span>
        <span className="flex items-center gap-1.5">
          <Clock className="h-3 w-3" />~{goal.estimated_hours}h
        </span>
      </div>
    </motion.button>
  );
}

function StepDots({ step }: { step: Step }) {
  const order: Step[] = ["name", "goal", "prior"];
  const current = order.indexOf(step);
  return (
    <div className="flex items-center gap-1.5">
      {order.map((s, i) => (
        <motion.span
          key={s}
          className={cn("h-1 rounded-full", i <= current ? "bg-accent" : "bg-line")}
          animate={{ width: i === current ? 20 : 8 }}
          transition={{ duration: 0.3, ease: ease.out }}
        />
      ))}
    </div>
  );
}
