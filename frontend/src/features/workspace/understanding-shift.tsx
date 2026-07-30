"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, CircleDashed, Loader2, Quote, Sparkles, X } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { ease } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * The Understanding Shift.
 *
 * The signature moment of the product, and the one screen no competitor can
 * build: two blocks of the learner's own writing, twenty minutes apart. On the
 * left, what they said they believed before they were told anything. On the
 * right, what they could reconstruct from memory with the material hidden.
 *
 * Nothing on this screen is generated. Every word is theirs, recovered from the
 * ledger. The tutor's only contribution is the middle column — the beliefs it
 * named, struck through as they were dislodged.
 *
 * A product that answers first has no "before" to show, because it never asked.
 * That is the entire argument, and here it is as one screen.
 */
export function UnderstandingShift({
  sessionId,
  graphId,
}: {
  sessionId: string;
  graphId: string;
}) {
  const shift = useQuery({
    queryKey: ["shift", sessionId],
    queryFn: () => api.shift(sessionId),
    retry: false,
  });

  /** Reveal in three beats: before → the beliefs → after. */
  const [beat, setBeat] = React.useState(0);
  React.useEffect(() => {
    if (!shift.data) return;
    const timers = [
      window.setTimeout(() => setBeat(1), 900),
      window.setTimeout(() => setBeat(2), 2000),
      window.setTimeout(() => setBeat(3), 3200),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, [shift.data]);

  if (shift.isLoading) {
    return (
      <div className="grid min-h-[50vh] place-items-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-4 w-4 animate-spin text-accent" />
          <p className="text-[13px] text-faint">Reading back what you wrote…</p>
        </div>
      </div>
    );
  }

  // A completed session always has a passed reflection, so this is a
  // belt-and-braces path — but "concept closed" must never render as a blank
  // screen because one panel could not be assembled.
  if (shift.isError || !shift.data) {
    return (
      <div className="py-10 text-center">
        <h2 className="text-[24px] font-semibold tracking-tight">Concept closed.</h2>
        <p className="mx-auto mt-3 max-w-sm text-[14px] leading-relaxed text-muted">
          Your mastery estimate is updated and this concept is now on your review
          schedule.
        </p>
        <Link href={`/graph/${graphId}`} className="mt-8 inline-block">
          <Button size="lg">
            Back to the graph
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    );
  }

  const data = shift.data;
  const gained = data.mastery_after - data.mastery_before;
  const cleared = data.beliefs.filter((b) => b.resolved).length;

  return (
    <div className="py-4">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: ease.out }}
        className="text-center"
      >
        <p className="text-2xs font-medium uppercase tracking-[0.2em] text-accent">
          Your understanding, {data.minutes_elapsed >= 1 ? `${data.minutes_elapsed} minutes` : "moments"} apart
        </p>
        <h2 className="mt-4 text-[clamp(1.7rem,3.4vw,2.4rem)] font-semibold leading-tight tracking-[-0.02em]">
          You did not read this.
          <br />
          <span className="text-muted">You rebuilt it.</span>
        </h2>
        <p className="mx-auto mt-4 max-w-lg text-[14px] leading-relaxed text-muted">
          Both passages below are yours. The tutor never wrote either one — it only
          asked, and then refused to answer until you had.
        </p>
      </motion.div>

      {/* The diff */}
      <div className="mt-12 grid gap-4 lg:grid-cols-[1fr_auto_1fr]">
        <Passage
          show={beat >= 1}
          label="Before any instruction"
          timestamp={data.before_at}
          text={data.before_text}
          tone="before"
          delay={0}
        />

        {/* The middle column: what the tutor actually contributed. */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: beat >= 2 ? 1 : 0 }}
          transition={{ duration: 0.5, ease: ease.out }}
          className="flex flex-col items-center justify-center gap-3 py-2 lg:w-[220px] lg:py-0"
        >
          {data.beliefs.length > 0 ? (
            <div className="w-full space-y-2">
              <p className="text-center text-2xs font-medium uppercase tracking-[0.14em] text-faint">
                Beliefs it named
              </p>
              {data.beliefs.slice(0, 4).map((belief, index) => {
                // Three states, not two. A belief cleared once is real progress
                // and must not be rendered as failure — but it is not closed
                // either, because one correct answer is very often a guess.
                const partial = !belief.resolved && belief.clears > 0;
                return (
                  <motion.div
                    key={belief.claim}
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={beat >= 2 ? { opacity: 1, scale: 1 } : {}}
                    transition={{ delay: 0.1 + index * 0.12, ...ease.reward }}
                    className={cn(
                      "flex items-start gap-2 rounded-lg border px-2.5 py-2",
                      belief.resolved
                        ? "border-state-mastered/30 bg-state-mastered/[0.07]"
                        : partial
                          ? "border-state-progress/30 bg-state-progress/[0.06]"
                          : "border-state-alert/25 bg-state-alert/[0.06]",
                    )}
                  >
                    <span className="mt-0.5 shrink-0">
                      {belief.resolved ? (
                        <Check className="h-3 w-3 text-state-mastered" strokeWidth={2.6} />
                      ) : partial ? (
                        <CircleDashed className="h-3 w-3 text-state-progress" strokeWidth={2.2} />
                      ) : (
                        <X className="h-3 w-3 text-state-alert" strokeWidth={2.6} />
                      )}
                    </span>
                    <span className="min-w-0">
                      <span
                        className={cn(
                          "block text-[11.5px] leading-snug",
                          belief.resolved ? "text-muted line-through decoration-1" : "text-ink",
                        )}
                      >
                        {belief.claim}
                      </span>
                      {partial && (
                        <span className="mt-1 block text-[10.5px] leading-snug text-state-progress">
                          cleared {belief.clears} of {belief.clears_required} — one more
                          unaided pass and it closes
                        </span>
                      )}
                    </span>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="text-center">
              <p className="text-2xs font-medium uppercase tracking-[0.14em] text-faint">
                No misconceptions found
              </p>
              <p className="mt-2 text-[11.5px] leading-snug text-muted">
                You arrived with a clean model. The work here was depth, not repair.
              </p>
            </div>
          )}

          <motion.div
            initial={{ opacity: 0, scaleX: 0 }}
            animate={beat >= 2 ? { opacity: 1, scaleX: 1 } : {}}
            transition={{ duration: 0.6, ease: ease.out }}
            className="hidden h-px w-full origin-left bg-gradient-to-r from-transparent via-accent/40 to-transparent lg:block"
          />
        </motion.div>

        <Passage
          show={beat >= 3}
          label="From memory, material hidden"
          timestamp={data.after_at}
          text={data.after_text}
          tone="after"
          delay={0}
        />
      </div>

      {/* The receipts */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={beat >= 3 ? { opacity: 1, y: 0 } : {}}
        transition={{ delay: 0.4, duration: 0.5, ease: ease.out }}
        className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-4"
      >
        <Stat
          value={`${Math.round(data.mastery_after * 100)}%`}
          label="Mastery"
          sub={gained >= 0 ? `+${Math.round(gained * 100)} this session` : "decayed"}
          tone="mastered"
        />
        <Stat
          value={String(data.unaided_wins)}
          label="Unaided"
          sub={
            data.hints_used === 0
              ? "no hints taken"
              : `reached rung ${data.hints_used} of 4`
          }
          tone={data.hints_used === 0 ? "mastered" : "accent"}
        />
        <Stat
          value={String(cleared)}
          label="Beliefs cleared"
          sub={
            data.beliefs.length
              ? `of ${data.beliefs.length} named`
              : "none to clear"
          }
          tone="accent"
        />
        <Stat
          value={String(data.answer_demands_refused)}
          label="Answers withheld"
          sub={
            data.answer_demands_refused > 0
              ? "and you got there anyway"
              : "you never asked"
          }
          tone="accent"
        />
      </motion.div>

      {data.unlocked_titles.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={beat >= 3 ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.6, duration: 0.5 }}
          className="mt-6 flex flex-wrap items-center justify-center gap-2"
        >
          <Sparkles className="h-3.5 w-3.5 text-accent" strokeWidth={1.8} />
          <span className="text-[13px] text-muted">Now reachable:</span>
          {data.unlocked_titles.map((title) => (
            <span
              key={title}
              className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-[12.5px] text-accent"
            >
              {title}
            </span>
          ))}
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0 }}
        animate={beat >= 3 ? { opacity: 1 } : {}}
        transition={{ delay: 0.8, duration: 0.5 }}
        className="mt-12 flex items-center justify-center gap-3"
      >
        <Link href={`/graph/${graphId}`}>
          <Button size="lg">
            Back to the graph
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
        <Link href="/progress">
          <Button size="lg" variant="ghost">
            See the record
          </Button>
        </Link>
      </motion.div>
    </div>
  );
}

function Passage({
  show,
  label,
  timestamp,
  text,
  tone,
  delay,
}: {
  show: boolean;
  label: string;
  timestamp: string;
  text: string;
  tone: "before" | "after";
  delay: number;
}) {
  const words = text.trim().split(/\s+/).length;

  return (
    <AnimatePresence>
      {show && (
        <motion.figure
          initial={{ opacity: 0, y: 16, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.65, delay, ease: ease.out }}
          className={cn(
            "relative overflow-hidden rounded-2xl border p-6",
            tone === "before"
              ? "border-line bg-surface/40"
              : "border-state-mastered/25 bg-state-mastered/[0.04]",
          )}
        >
          {tone === "after" && (
            <motion.span
              className="pointer-events-none absolute -inset-px rounded-2xl"
              style={{ boxShadow: "0 0 60px -20px rgb(var(--state-mastered) / 0.5)" }}
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
            />
          )}

          <figcaption className="relative flex items-baseline justify-between gap-3">
            <span
              className={cn(
                "text-2xs font-medium uppercase tracking-[0.14em]",
                tone === "before" ? "text-faint" : "text-state-mastered",
              )}
            >
              {label}
            </span>
            <span className="text-[11px] tabular-nums text-faint">
              {new Date(timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </figcaption>

          <Quote
            className={cn(
              "relative mt-4 h-4 w-4",
              tone === "before" ? "text-faint/50" : "text-state-mastered/50",
            )}
            strokeWidth={1.6}
          />

          <blockquote
            className={cn(
              "relative mt-2 text-[14.5px] leading-[1.7]",
              tone === "before" ? "text-muted" : "text-ink",
            )}
          >
            {text}
          </blockquote>

          <p className="relative mt-4 text-[11px] tabular-nums text-faint">{words} words</p>
        </motion.figure>
      )}
    </AnimatePresence>
  );
}

/**
 * Numbers are rendered at their true value from the first frame, and only the
 * *card* animates in.
 *
 * A count-up looked good and was a mistake: springs are driven by
 * requestAnimationFrame, so in a backgrounded tab the mastery figure sat at 0%
 * indefinitely. On the one screen whose entire job is to be believed, a number
 * that is briefly — or permanently — wrong costs more than the flourish was
 * worth. Reduced-motion users get the identical result for free.
 */
function Stat({
  value,
  label,
  sub,
  tone,
}: {
  value: React.ReactNode;
  label: string;
  sub: string;
  tone: "mastered" | "accent";
}) {
  return (
    <div className="bg-canvas px-5 py-4 text-center">
      <p
        className={cn(
          "text-[22px] font-semibold leading-none tabular-nums",
          tone === "mastered" ? "text-state-mastered" : "text-accent",
        )}
      >
        {value}
      </p>
      <p className="mt-2 text-2xs font-medium uppercase tracking-[0.12em] text-faint">{label}</p>
      <p className="mt-1 text-[11.5px] leading-snug text-muted">{sub}</p>
    </div>
  );
}
