"use client";

import { motion } from "framer-motion";
import * as React from "react";

import type { SessionState } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * What is actually happening while the learner waits.
 *
 * A spinner says "please hold". This says "four specialists are looking at what
 * you wrote" — which is true, and is the difference the product is selling. The
 * agents listed are the ones the orchestrator really runs for the current
 * state, so this is a status display, not theatre.
 *
 * It also does honest work for the wait itself: a labelled delay reads as
 * shorter than an unlabelled one, and multi-agent turns genuinely take longer
 * than a single completion.
 */
const PIPELINES: Record<string, { agent: string; doing: string }[]> = {
  elicit: [
    { agent: "Router", doing: "reading your intent" },
    { agent: "Examiner", doing: "diagnosing your mental model" },
    { agent: "Teacher", doing: "calibrating to what you already have" },
    { agent: "Examiner", doing: "authoring a challenge at your level" },
  ],
  attempt: [
    { agent: "Router", doing: "reading your intent" },
    { agent: "Examiner", doing: "tracing your reasoning" },
    { agent: "Coach", doing: "choosing one Socratic move" },
    { agent: "Guard", doing: "checking nothing leaks the answer" },
  ],
  coach: [
    { agent: "Coach", doing: "choosing one Socratic move" },
    { agent: "Guard", doing: "checking nothing leaks the answer" },
  ],
  reflect: [
    { agent: "Reflection", doing: "scoring your recall against the expert model" },
    { agent: "Memory", doing: "updating your long-term profile" },
  ],
};

function pipelineFor(state: SessionState, requestingGuidance: boolean) {
  if (requestingGuidance) return PIPELINES.coach!;
  if (state === "elicit") return PIPELINES.elicit!;
  if (state === "reflect") return PIPELINES.reflect!;
  return PIPELINES.attempt!;
}

export function AgentActivity({
  state,
  requestingGuidance = false,
  className,
}: {
  state: SessionState;
  requestingGuidance?: boolean;
  className?: string;
}) {
  const steps = React.useMemo(
    () => pipelineFor(state, requestingGuidance),
    [state, requestingGuidance],
  );
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    setActive(0);
    const id = window.setInterval(
      () => setActive((i) => Math.min(i + 1, steps.length - 1)),
      620,
    );
    return () => window.clearInterval(id);
  }, [steps]);

  const current = steps[Math.min(active, steps.length - 1)]!;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={cn("flex items-center gap-3", className)}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-1">
        {steps.map((step, index) => (
          <motion.span
            key={`${step.agent}-${index}`}
            className={cn(
              "h-1 rounded-full",
              index <= active ? "bg-accent" : "bg-line",
            )}
            animate={{ width: index === active ? 18 : 6 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          />
        ))}
      </div>
      <motion.p
        key={`${current.agent}-${active}`}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-[12.5px] text-muted"
      >
        <span className="font-medium text-ink">{current.agent}</span>{" "}
        {current.doing}…
      </motion.p>
    </motion.div>
  );
}
