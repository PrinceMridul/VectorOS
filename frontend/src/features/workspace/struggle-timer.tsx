"use client";

import { motion } from "framer-motion";
import { LifeBuoy } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * The struggle floor.
 *
 * "Request guidance" is unavailable for the first stretch after a challenge
 * appears. Instant help on an untouched problem is the exact mechanism of
 * cognitive offloading — the learner never activates prior knowledge, so nothing
 * has anywhere to attach.
 *
 * The countdown is shown rather than hidden, and the copy names what the wait is
 * *for*. A disabled button with no explanation reads as a bug; a visible timer
 * that says "the struggle is doing something" reads as a stance.
 */
export function StruggleTimer({
  seconds,
  startedAt,
  unlocked,
  onRequest,
  pending,
}: {
  seconds: number;
  startedAt: number;
  unlocked: boolean;
  onRequest: () => void;
  pending?: boolean;
}) {
  const [remaining, setRemaining] = React.useState(() =>
    Math.max(0, seconds - Math.floor((Date.now() - startedAt) / 1000)),
  );

  React.useEffect(() => {
    setRemaining(Math.max(0, seconds - Math.floor((Date.now() - startedAt) / 1000)));
    const id = window.setInterval(() => {
      setRemaining(Math.max(0, seconds - Math.floor((Date.now() - startedAt) / 1000)));
    }, 500);
    return () => window.clearInterval(id);
  }, [seconds, startedAt]);

  const ready = unlocked || remaining <= 0;
  const progress = 1 - remaining / Math.max(seconds, 1);

  return (
    <button
      onClick={onRequest}
      disabled={!ready || pending}
      className={cn(
        "group flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors focus-ring",
        ready
          ? "text-muted hover:bg-raised/70 hover:text-ink"
          : "cursor-not-allowed text-faint/70",
      )}
      title={
        ready
          ? "Ask for one Socratic nudge"
          : "Guidance unlocks once you have sat with the problem"
      }
    >
      <span className="relative grid h-5 w-5 place-items-center">
        {ready ? (
          <LifeBuoy className="h-3.5 w-3.5" strokeWidth={1.8} />
        ) : (
          <svg width="20" height="20" viewBox="0 0 20 20" className="-rotate-90" aria-hidden>
            <circle cx="10" cy="10" r="8" fill="none" stroke="rgb(var(--line))" strokeWidth="2" />
            <motion.circle
              cx="10"
              cy="10"
              r="8"
              fill="none"
              stroke="rgb(var(--accent))"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={2 * Math.PI * 8}
              animate={{ strokeDashoffset: 2 * Math.PI * 8 * (1 - progress) }}
              transition={{ duration: 0.5, ease: "linear" }}
            />
          </svg>
        )}
      </span>
      {ready ? "I'm stuck — one nudge" : `Guidance in ${remaining}s`}
    </button>
  );
}
