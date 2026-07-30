"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Gauge,
  Loader2,
  RotateCcw,
  Scale,
} from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { AppShell } from "@/components/app-shell";
import { AppFooter } from "@/components/app-footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MasteryBar } from "@/components/ui/mastery-ring";
import { api } from "@/lib/api";
import { ease, riseIn, stagger } from "@/lib/motion";
import { QUADRANT_META, cn, percent, relativeTime } from "@/lib/utils";

/**
 * Progress.
 *
 * Not a chart wall. Four things, each of which should change what the learner
 * does in the next ten minutes:
 *
 *  - what is **fading** and needs retrieval before it goes,
 *  - where they are **wrong while certain**, which they cannot see themselves,
 *  - how well their confidence **predicts** their correctness,
 *  - and how much of the progress was **theirs**.
 *
 * Streaks, XP and time-on-task are deliberately absent. They measure attendance,
 * and rewarding attendance is how a learning product quietly becomes a game
 * about opening the app.
 */
export function DashboardView() {
  const router = useRouter();
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });

  const open = useMutation({
    mutationFn: (nodeId: string) => api.openSession(nodeId),
    onSuccess: (session) => router.push(`/learn/${session.id}`),
  });

  if (dashboard.isLoading) {
    return (
      <AppShell>
        <div className="grid h-[60vh] place-items-center">
          <Loader2 className="h-4 w-4 animate-spin text-accent" />
        </div>
      </AppShell>
    );
  }

  if (!dashboard.data) {
    return (
      <AppShell>
        <div className="grid h-[60vh] place-items-center">
          <p className="text-[14px] text-muted">Nothing recorded yet.</p>
        </div>
      </AppShell>
    );
  }

  const data = dashboard.data;
  const totalQuadrants =
    data.quadrants.automaticity +
    data.quadrants.fragile +
    data.quadrants.blind_spot +
    data.quadrants.known_gap;

  return (
    <AppShell>
      <motion.div
        variants={stagger(0.05, 0.07)}
        initial="hidden"
        animate="show"
        className="mx-auto w-full max-w-5xl px-6 py-10"
      >
        <motion.header variants={riseIn}>
          <h1 className="text-[28px] font-semibold tracking-[-0.02em]">
            {data.display_name}&rsquo;s record
          </h1>
          <p className="mt-2 max-w-xl text-[14px] leading-relaxed text-muted">
            {data.sessions_completed === 0
              ? "Nothing closed yet. These numbers fill in as you work."
              : `${data.sessions_completed} concept${data.sessions_completed > 1 ? "s" : ""} closed. Every number here is reconstructable from your session traces.`}
          </p>
        </motion.header>

        {/* Headline metrics */}
        <motion.div variants={riseIn} className="mt-9 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-3">
          <Metric
            icon={Scale}
            label="Cognitive debt"
            value={percent(data.cognitive_debt)}
            tone={
              data.cognitive_debt <= 0.25
                ? "mastered"
                : data.cognitive_debt <= 0.5
                  ? "accent"
                  : "alert"
            }
            caption={data.cognitive_debt_headline}
          />
          <Metric
            icon={Gauge}
            label="Calibration"
            value={data.calibration_label}
            tone={data.calibration_label === "well calibrated" ? "mastered" : "accent"}
            caption={
              data.calibration_samples < 4
                ? "Needs a few more graded attempts before this means anything."
                : `Your confidence misses your accuracy by ${Math.round(data.calibration_error * 100)} points on average.`
            }
          />
          <Metric
            icon={AlertTriangle}
            label="Blind spots"
            value={String(data.quadrants.blind_spot)}
            tone={data.quadrants.blind_spot > 0 ? "alert" : "mastered"}
            caption={
              data.quadrants.blind_spot > 0
                ? "Answers you were sure about and got wrong. These are scheduled first."
                : "Nothing you were confidently wrong about. Rare, and good."
            }
          />
        </motion.div>

        {/* Review queue */}
        {data.review_queue.length > 0 && (
          <motion.section variants={riseIn} className="mt-10">
            <SectionHeading
              icon={RotateCcw}
              title="Fading"
              subtitle="Retrieval before it decays. Retaining beats acquiring."
            />
            <div className="mt-4 space-y-2">
              {data.review_queue.map((concept, index) => (
                <motion.button
                  key={concept.node_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05, duration: 0.3, ease: ease.out }}
                  onClick={() => open.mutate(concept.node_id)}
                  className="group flex w-full items-center gap-4 rounded-xl border border-state-review/25 bg-state-review/[0.05] p-4 text-left transition-all hover:border-state-review/50 focus-ring"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-medium tracking-tight">
                      {concept.title}
                    </p>
                    <p className="mt-0.5 text-[12px] text-muted">
                      {concept.graph_title} · due {relativeTime(concept.review_due_at)}
                    </p>
                  </div>
                  <span className="text-[12.5px] tabular-nums text-state-review">
                    {percent(concept.mastery)}
                  </span>
                  <ArrowRight className="h-4 w-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-state-review" />
                </motion.button>
              ))}
            </div>
          </motion.section>
        )}

        <div className="mt-10 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
          {/* Concept mastery */}
          <motion.section variants={riseIn}>
            <SectionHeading
              title="Concepts"
              subtitle="Probability you hold it, not lessons completed."
            />
            <div className="mt-4 space-y-3.5">
              {data.concepts.length === 0 && (
                <p className="text-[13.5px] text-faint">
                  Open a concept from your graph to start the record.
                </p>
              )}
              {data.concepts.map((concept, index) => (
                <motion.div
                  key={concept.node_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: index * 0.03 }}
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="truncate text-[13.5px] text-ink">{concept.title}</span>
                    <span className="shrink-0 text-[12px] tabular-nums text-muted">
                      {percent(concept.mastery)}
                      {concept.unaided > 0 && (
                        <span className="ml-2 text-faint">{concept.unaided} unaided</span>
                      )}
                    </span>
                  </div>
                  <MasteryBar
                    value={concept.mastery}
                    color={
                      concept.mastery >= 0.85
                        ? "rgb(var(--state-mastered))"
                        : concept.mastery >= 0.4
                          ? "rgb(var(--accent))"
                          : "rgb(var(--state-progress))"
                    }
                    className="mt-2"
                  />
                </motion.div>
              ))}
            </div>
          </motion.section>

          {/* Metacognitive quadrants */}
          <motion.section variants={riseIn}>
            <SectionHeading
              title="How you are wrong"
              subtitle="Correctness against the confidence you committed beforehand."
            />
            <div className="mt-4 grid grid-cols-2 gap-2">
              {(
                [
                  ["automaticity", data.quadrants.automaticity],
                  ["fragile", data.quadrants.fragile],
                  ["blind_spot", data.quadrants.blind_spot],
                  ["known_gap", data.quadrants.known_gap],
                ] as const
              ).map(([key, count]) => {
                const meta = QUADRANT_META[key];
                const share = totalQuadrants ? count / totalQuadrants : 0;
                return (
                  <div
                    key={key}
                    className="rounded-xl border border-line bg-surface/50 p-3.5"
                  >
                    <div className="flex items-baseline justify-between">
                      <span className={cn("text-[12.5px] font-medium", meta.tone)}>
                        {meta.label}
                      </span>
                      <span className="text-[15px] font-semibold tabular-nums">{count}</span>
                    </div>
                    <MasteryBar
                      value={share}
                      color={`rgb(${
                        key === "automaticity"
                          ? "var(--state-mastered)"
                          : key === "fragile"
                            ? "var(--state-review)"
                            : key === "blind_spot"
                              ? "var(--state-alert)"
                              : "var(--state-progress)"
                      })`}
                      className="mt-2.5"
                    />
                    <p className="mt-2 text-[11px] leading-snug text-faint">{meta.description}</p>
                  </div>
                );
              })}
            </div>
          </motion.section>
        </div>

        {/* Clearing every open misconception is the single best thing that can
            appear here, and rendering it as an absent section threw that away. */}
        {data.active_weaknesses.length === 0 && data.resolved_weaknesses > 0 && (
          <motion.section variants={riseIn} className="mt-10">
            <div className="flex items-center gap-3 rounded-xl border border-state-mastered/25 bg-state-mastered/[0.05] px-5 py-4">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-state-mastered/30 bg-state-mastered/10">
                <Check className="h-3.5 w-3.5 text-state-mastered" strokeWidth={2.4} />
              </span>
              <div>
                <p className="text-[14px] font-medium tracking-tight text-state-mastered">
                  No open misconceptions
                </p>
                <p className="mt-0.5 text-[12.5px] text-muted">
                  {data.resolved_weaknesses} cleared — each one twice, on separate
                  occasions. Nothing currently obstructing you.
                </p>
              </div>
            </div>
          </motion.section>
        )}

        {/* Weakness index */}
        {data.active_weaknesses.length > 0 && (
          <motion.section variants={riseIn} className="mt-10">
            <SectionHeading
              title="Open misconceptions"
              subtitle={`Tracked until you clear each one twice. ${data.resolved_weaknesses} resolved so far.`}
            />
            <div className="mt-4 space-y-2">
              {data.active_weaknesses.map((weakness, index) => (
                <motion.div
                  key={`${weakness.claim}-${index}`}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.04 }}
                  className="rounded-xl border border-line bg-surface/40 p-4"
                >
                  <div className="flex flex-wrap items-center gap-2.5">
                    <Badge
                      tone={
                        weakness.severity === "high"
                          ? "alert"
                          : weakness.severity === "medium"
                            ? "progress"
                            : "neutral"
                      }
                    >
                      {weakness.severity}
                    </Badge>
                    <span className="text-[12px] text-faint">{weakness.node_title}</span>
                    {weakness.evidence_count > 1 && (
                      <span className="text-[11.5px] text-faint">
                        seen {weakness.evidence_count}×
                      </span>
                    )}
                  </div>
                  <p className="mt-2.5 text-[13.5px] leading-relaxed text-ink">
                    “{weakness.claim}”
                  </p>
                  {weakness.canonical && (
                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">
                      {weakness.canonical}
                    </p>
                  )}
                </motion.div>
              ))}
            </div>
          </motion.section>
        )}

        {/* Session memory */}
        {data.recent_summaries.length > 0 && (
          <motion.section variants={riseIn} className="mt-10">
            <SectionHeading
              title="What the tutor remembers"
              subtitle="Consolidated session notes. The verbatim exchange is deliberately forgotten."
            />
            <ul className="mt-4 space-y-2">
              {[...data.recent_summaries].reverse().map((entry, index) => (
                <li
                  key={index}
                  className="flex gap-3 rounded-lg border border-line/60 bg-surface/30 px-4 py-3"
                >
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                  <div className="min-w-0">
                    <p className="font-mono text-[12px] leading-relaxed text-muted">
                      {entry.summary}
                    </p>
                    <p className="mt-1 text-[11px] text-faint">{relativeTime(entry.at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </motion.section>
        )}

        <motion.div variants={riseIn} className="mt-14 flex justify-center">
          <Button variant="ghost" onClick={() => router.back()}>
            Back to work
          </Button>
        </motion.div>
      </motion.div>

      {/* The record is the one in-app page you scroll to the end of, so it is
          the one that gets a footer. */}
      <AppFooter />
    </AppShell>
  );
}

function SectionHeading({
  icon: Icon,
  title,
  subtitle,
}: {
  icon?: typeof Gauge;
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5 text-faint" strokeWidth={1.8} />}
        <h2 className="text-[15px] font-medium tracking-tight">{title}</h2>
      </div>
      <p className="mt-1 text-[12.5px] text-muted">{subtitle}</p>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  caption,
  tone,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  caption: string;
  tone: "mastered" | "accent" | "alert";
}) {
  return (
    <div className="bg-canvas p-6">
      <div className="flex items-center gap-2 text-2xs font-medium uppercase tracking-[0.14em] text-faint">
        <Icon className="h-3 w-3" strokeWidth={1.8} />
        {label}
      </div>
      <p
        className={cn(
          "mt-4 text-[26px] font-semibold capitalize leading-none tracking-tight tabular-nums",
          tone === "mastered" && "text-state-mastered",
          tone === "accent" && "text-accent",
          tone === "alert" && "text-state-alert",
        )}
      >
        {value}
      </p>
      <p className="mt-3 text-[12.5px] leading-relaxed text-muted">{caption}</p>
    </div>
  );
}
