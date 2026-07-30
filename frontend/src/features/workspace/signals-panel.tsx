"use client";

import { motion } from "framer-motion";
import { Activity, Brain, Layers, Target } from "lucide-react";
import * as React from "react";

import { MasteryRing } from "@/components/ui/mastery-ring";
import { ease } from "@/lib/motion";
import type { Session } from "@/lib/types";
import { QUADRANT_META, cn, percent } from "@/lib/utils";

const SCAFFOLD_NAMES = ["No help", "Orient", "Probe", "Structure", "Worked example"];

/**
 * The instrument panel.
 *
 * The rule for what appears here: a number is shown only if the learner could
 * *act* on it. Mastery, the diagnosed model and the scaffold rung all change
 * what they should do next. The raw cognitive-load heuristic (see
 * backend/app/pedagogy/load.py — not the Paas instrument) does not, so it is
 * rendered as a band ("productive", "overloaded") rather than as 6.8/9 — telling
 * someone their load estimate is 6.8 is itself extraneous load.
 */
export function SignalsPanel({ session }: { session: Session }) {
  const delta = session.mastery - session.mastery_before;

  return (
    <aside className="hidden w-[300px] shrink-0 flex-col gap-5 border-l border-line px-5 py-8 lg:flex">
      {/* Mastery */}
      <section>
        <Label icon={Target}>Mastery</Label>
        <div className="mt-3 flex items-center gap-4">
          <MasteryRing value={session.mastery} size={54} stroke={3.5}>
            <span className="text-[13px] font-medium tabular-nums">
              {Math.round(session.mastery * 100)}
            </span>
          </MasteryRing>
          <div className="min-w-0">
            <p className="text-[12.5px] leading-snug text-muted">
              P(you hold this concept), decaying over time.
            </p>
            {Math.abs(delta) > 0.001 && (
              <motion.p
                key={session.mastery}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn(
                  "mt-1.5 text-[12px] font-medium tabular-nums",
                  delta > 0 ? "text-state-mastered" : "text-state-alert",
                )}
              >
                {delta > 0 ? "+" : ""}
                {(delta * 100).toFixed(1)} this session
              </motion.p>
            )}
          </div>
        </div>
      </section>

      <Divider />

      {/* Load + predicted success */}
      <section>
        <Label icon={Activity}>Calibration</Label>
        <dl className="mt-3 space-y-2.5">
          <Row
            term="Next-answer odds"
            value={percent(session.predicted_success)}
            hint="Targeted at 50–80%. Higher would be boredom."
          />
          <Row
            term="Cognitive load"
            value={
              <span
                className={cn(
                  "capitalize",
                  session.load_band === "overloaded" && "text-state-alert",
                  session.load_band === "underloaded" && "text-state-progress",
                  session.load_band === "productive" && "text-state-mastered",
                )}
              >
                {session.load_band}
              </span>
            }
            hint={
              session.load_band === "overloaded"
                ? "Tasks will step down and decompose."
                : session.load_band === "underloaded"
                  ? "Difficulty will rise to restore the struggle."
                  : "You are in the productive band."
            }
          />
        </dl>
      </section>

      <Divider />

      {/* Scaffolding ladder */}
      <section>
        <Label icon={Layers}>Support</Label>
        <div className="mt-3 flex gap-1">
          {SCAFFOLD_NAMES.map((name, level) => (
            <div key={name} className="flex-1">
              <motion.div
                className={cn(
                  "h-1 rounded-full",
                  level <= session.scaffold_level ? "bg-accent" : "bg-line",
                )}
                initial={false}
                animate={{ opacity: level <= session.scaffold_level ? 1 : 0.6 }}
              />
            </div>
          ))}
        </div>
        <p className="mt-2.5 text-[12.5px] text-muted">
          {SCAFFOLD_NAMES[session.scaffold_level] ?? "No help"}
          <span className="text-faint"> · rung {session.scaffold_level} of 4</span>
        </p>
        <p className="mt-1.5 text-[11.5px] leading-relaxed text-faint">
          Support rises one rung at a time, only after you reply. There is no rung that
          gives the answer.
        </p>
      </section>

      {/* Diagnosed model */}
      {session.mental_model && (
        <>
          <Divider />
          <section>
            <Label icon={Brain}>Your model</Label>

            {session.mental_model.anchors.length > 0 && (
              <Group title="Already right">
                {session.mental_model.anchors.slice(0, 3).map((anchor, i) => (
                  <Item key={i} tone="mastered">
                    {anchor}
                  </Item>
                ))}
              </Group>
            )}

            {session.mental_model.misconceptions.length > 0 && (
              <Group title="Getting in the way">
                {session.mental_model.misconceptions.slice(0, 3).map((m, i) => (
                  <Item key={i} tone="alert">
                    {m.claim}
                  </Item>
                ))}
              </Group>
            )}

            {session.mental_model.missing.length > 0 && (
              <Group title="Not yet touched">
                {session.mental_model.missing.slice(0, 3).map((m, i) => (
                  <Item key={i} tone="muted">
                    {m}
                  </Item>
                ))}
              </Group>
            )}
          </section>
        </>
      )}

      {session.last_evaluation && (
        <>
          <Divider />
          <section>
            <Label icon={Brain}>Last attempt</Label>
            <motion.div
              key={session.turn_count}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, ease: ease.out }}
              className="mt-3 rounded-xl border border-line bg-canvas/50 p-3"
            >
              <p
                className={cn(
                  "text-[12.5px] font-medium",
                  QUADRANT_META[session.last_evaluation.quadrant].tone,
                )}
              >
                {QUADRANT_META[session.last_evaluation.quadrant].label}
              </p>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
                {QUADRANT_META[session.last_evaluation.quadrant].description}
              </p>
            </motion.div>
          </section>
        </>
      )}
    </aside>
  );
}

function Label({ icon: Icon, children }: { icon: typeof Target; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-2xs font-medium uppercase tracking-[0.14em] text-faint">
      <Icon className="h-3 w-3" strokeWidth={1.8} />
      {children}
    </div>
  );
}

function Divider() {
  return <div className="h-px bg-line" />;
}

function Row({
  term,
  value,
  hint,
}: {
  term: string;
  value: React.ReactNode;
  hint: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <dt className="text-[12.5px] text-muted">{term}</dt>
        <dd className="text-[12.5px] font-medium tabular-nums">{value}</dd>
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-faint">{hint}</p>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-3.5">
      <p className="text-[11px] font-medium uppercase tracking-wider text-faint/80">{title}</p>
      <ul className="mt-1.5 space-y-1.5">{children}</ul>
    </div>
  );
}

function Item({
  tone,
  children,
}: {
  tone: "mastered" | "alert" | "muted";
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-2">
      <span
        className={cn(
          "mt-1.5 h-1 w-1 shrink-0 rounded-full",
          tone === "mastered" && "bg-state-mastered",
          tone === "alert" && "bg-state-alert",
          tone === "muted" && "bg-faint",
        )}
      />
      <span className="text-[12px] leading-snug text-muted">{children}</span>
    </li>
  );
}
