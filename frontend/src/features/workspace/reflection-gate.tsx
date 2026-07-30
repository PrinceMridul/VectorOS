"use client";

import { AnimatePresence, motion } from "framer-motion";
import { BookOpenCheck, EyeOff } from "lucide-react";
import * as React from "react";

import { TutorMessage } from "@/components/tutor-message";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ease, riseIn, stagger } from "@/lib/motion";
import type { Session } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The Metacognitive Gate.
 *
 * Getting the challenge right and being able to rebuild the idea are different
 * skills, and only the second one survives the week. So progression is gated on
 * free recall, scored against the expert model — and the material is genuinely
 * hidden while you write, because a summary composed with the answer on screen
 * measures reading, not retention.
 */
export function ReflectionGate({
  session,
  value,
  onChange,
  onSubmit,
  pending,
}: {
  session: Session;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  pending: boolean;
}) {
  const words = value.trim() ? value.trim().split(/\s+/).length : 0;
  const enough = words >= 12;

  return (
    <motion.div variants={stagger(0.05, 0.07)} initial="hidden" animate="show">
      <motion.div
        variants={riseIn}
        className="flex items-center gap-2 text-2xs font-medium uppercase tracking-[0.14em] text-state-review"
      >
        <BookOpenCheck className="h-3.5 w-3.5" strokeWidth={1.8} />
        Metacognitive gate
      </motion.div>

      <motion.div variants={riseIn} className="mt-5">
        <TutorMessage text={session.message} />
      </motion.div>

      <motion.div
        variants={riseIn}
        className="mt-6 flex items-center gap-2.5 rounded-xl border border-line bg-canvas/40 px-4 py-3"
      >
        <EyeOff className="h-3.5 w-3.5 shrink-0 text-faint" strokeWidth={1.8} />
        <p className="text-[12.5px] leading-relaxed text-muted">
          The explanation and your working are hidden on purpose. Retrieving it cold is the
          part that makes it stick — and it is the only honest test of whether it did.
        </p>
      </motion.div>

      <motion.div variants={riseIn} className="mt-5">
        <Textarea
          autoFocus
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          placeholder="In my own words…"
          className="min-h-[200px]"
        />
        <div className="mt-2.5 flex items-center justify-between">
          <span className="text-[12px] text-faint">
            {enough ? "That's enough to score." : `${words} words — aim for a short paragraph.`}
          </span>
          <span
            className={cn(
              "h-1 w-24 overflow-hidden rounded-full bg-line",
              enough && "bg-state-mastered/30",
            )}
          >
            <motion.span
              className={cn("block h-full rounded-full", enough ? "bg-state-mastered" : "bg-accent")}
              animate={{ width: `${Math.min(100, (words / 12) * 100)}%` }}
              transition={{ duration: 0.3, ease: ease.out }}
            />
          </span>
        </div>
      </motion.div>

      <AnimatePresence>
        {session.reflection && !session.reflection.passed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-5 rounded-xl border border-state-progress/30 bg-state-progress/[0.06] p-4">
              <p className="text-[12.5px] font-medium text-state-progress">
                Coverage {Math.round(session.reflection.coverage * 100)}% — not quite there.
              </p>
              {session.reflection.omissions.length > 0 && (
                <ul className="mt-2.5 space-y-1.5">
                  {session.reflection.omissions.slice(0, 3).map((omission, i) => (
                    <li key={i} className="flex gap-2 text-[12.5px] leading-snug text-muted">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-state-progress" />
                      {omission}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div variants={riseIn} className="mt-6 flex items-center gap-4">
        <Button size="lg" onClick={onSubmit} loading={pending} disabled={!enough}>
          Submit from memory
        </Button>
        <span className="text-[12.5px] text-faint">
          Scored against the expert model, not against your earlier answer.
        </span>
      </motion.div>
    </motion.div>
  );
}
