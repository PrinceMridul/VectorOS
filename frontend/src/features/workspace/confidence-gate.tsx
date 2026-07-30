"use client";

import { motion } from "framer-motion";
import * as React from "react";

import { ease } from "@/lib/motion";
import type { Confidence } from "@/lib/types";
import { cn } from "@/lib/utils";

const OPTIONS: { value: Confidence; label: string; hint: string; color: string }[] = [
  { value: "low", label: "Not sure", hint: "Guessing", color: "var(--state-progress)" },
  { value: "medium", label: "Fairly sure", hint: "Think I have it", color: "var(--accent)" },
  { value: "high", label: "Certain", hint: "I know this", color: "var(--state-mastered)" },
];

/**
 * The confidence gate.
 *
 * You cannot submit until you have committed to how sure you are. That is the
 * point: a confidence rating collected *after* seeing the result is hindsight
 * and measures nothing, whereas one collected before is the only way to detect a
 * blind spot — being wrong while certain, which is invisible to ordinary
 * grading and is where the most damaging practice errors come from.
 *
 * The friction is deliberate and is enforced server-side too; this component is
 * the humane surface of a rule the API would reject anyway.
 */
export function ConfidenceGate({
  value,
  onChange,
  disabled,
}: {
  value: Confidence | null;
  onChange: (value: Confidence) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-2xs font-medium uppercase tracking-[0.14em] text-faint">
          Before you submit
        </span>
        <span className="text-[12px] text-muted">How sure are you?</span>
      </div>

      <div
        role="radiogroup"
        aria-label="Confidence"
        className="relative inline-flex w-full max-w-md rounded-xl border border-line bg-canvas/60 p-1"
      >
        {OPTIONS.map((option) => {
          const selected = value === option.value;
          return (
            <button
              key={option.value}
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(option.value)}
              className={cn(
                "relative flex-1 rounded-lg px-3 py-2 text-center transition-colors duration-150 focus-ring",
                "disabled:cursor-not-allowed disabled:opacity-50",
                selected ? "text-ink" : "text-muted hover:text-ink",
              )}
            >
              {selected && (
                <motion.span
                  layoutId="confidence-pill"
                  className="absolute inset-0 rounded-lg border"
                  style={{
                    background: `rgb(${option.color} / 0.12)`,
                    borderColor: `rgb(${option.color} / 0.45)`,
                  }}
                  transition={{ type: "spring", stiffness: 420, damping: 32 }}
                />
              )}
              <span className="relative block text-[13px] font-medium leading-none">
                {option.label}
              </span>
              <span className="relative mt-1 block text-[11px] leading-none text-faint">
                {option.hint}
              </span>
            </button>
          );
        })}
      </div>

      <motion.p
        initial={false}
        animate={{ opacity: value ? 0 : 1 }}
        transition={{ duration: 0.2, ease: ease.out }}
        className="text-[12px] text-faint"
      >
        Committing before you see the result is what makes this measurable.
      </motion.p>
    </div>
  );
}
