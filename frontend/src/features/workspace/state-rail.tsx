"use client";

import { motion } from "framer-motion";
import * as React from "react";

import type { SessionState } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The pedagogical state machine, made visible.
 *
 * Most tutoring products hide their control flow, which is why they feel like a
 * chat with a personality. Showing it does two things: the learner always knows
 * what is being asked of them right now, and the guarantee becomes legible —
 * you can see that "explain" sits *after* "what you believe", and that mastery
 * sits after recall, not after a correct answer.
 */
const STEPS: { states: SessionState[]; label: string; note: string }[] = [
  {
    states: ["idle", "elicit", "diagnose"],
    label: "Elicit",
    note: "What you already believe",
  },
  { states: ["instruct"], label: "Teach", note: "Calibrated to your model" },
  { states: ["challenge", "attempt", "evaluate"], label: "Apply", note: "Your turn" },
  { states: ["coach"], label: "Coach", note: "One question at a time" },
  { states: ["reflect"], label: "Recall", note: "Rebuild it unaided" },
  { states: ["mastery", "complete"], label: "Commit", note: "Mastery updated" },
];

export function StateRail({ state }: { state: SessionState }) {
  const activeIndex = STEPS.findIndex((s) => s.states.includes(state));

  return (
    <nav
      aria-label="Session progress"
      className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-[188px] shrink-0 flex-col gap-1 border-r border-line px-4 py-8 xl:flex"
    >
      <p className="mb-4 px-2 text-2xs font-medium uppercase tracking-[0.14em] text-faint">
        This session
      </p>

      {STEPS.map((step, index) => {
        const active = index === activeIndex;
        const done = index < activeIndex;

        return (
          <div key={step.label} className="relative flex gap-3 px-2 py-2">
            <div className="flex flex-col items-center">
              <motion.span
                className={cn(
                  "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                  active ? "bg-accent" : done ? "bg-state-mastered" : "bg-line",
                )}
                animate={active ? { scale: [1, 1.5, 1], opacity: [1, 0.6, 1] } : { scale: 1 }}
                transition={active ? { duration: 2.4, repeat: Infinity } : undefined}
              />
              {index < STEPS.length - 1 && (
                <span
                  className={cn(
                    "mt-1.5 w-px flex-1",
                    done ? "bg-state-mastered/40" : "bg-line",
                  )}
                />
              )}
            </div>

            <div className="min-w-0 pb-3">
              <p
                className={cn(
                  "text-[13px] leading-none tracking-tight transition-colors",
                  active ? "font-medium text-ink" : done ? "text-muted" : "text-faint",
                )}
              >
                {step.label}
              </p>
              <motion.p
                initial={false}
                animate={{ opacity: active ? 1 : 0, height: active ? "auto" : 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden text-[11.5px] leading-snug text-muted"
              >
                <span className="block pt-1.5">{step.note}</span>
              </motion.p>
            </div>
          </div>
        );
      })}

      <p className="mt-auto px-2 text-[11px] leading-relaxed text-faint/70">
        These transitions are enforced in the backend, not suggested in a prompt.
      </p>
    </nav>
  );
}
