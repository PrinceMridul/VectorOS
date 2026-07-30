"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import * as React from "react";

import { panelIn } from "@/lib/motion";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const AGENT_COLOR: Record<string, string> = {
  router: "var(--faint)",
  planner: "var(--accent)",
  examiner: "var(--state-review)",
  teacher: "var(--state-mastered)",
  coach: "var(--state-progress)",
  reflection: "var(--state-review)",
  synthesizer: "var(--accent)",
  memory: "var(--faint)",
  guard: "var(--state-alert)",
};

/**
 * The trace forest for this session.
 *
 * Deliberately shipped to the learner, not buried in an admin tool. A system
 * that asserts you have mastered something owes you the evidence: which agent
 * ran, on which model, what the output guard decided, and every state
 * transition behind the number. It is also the fastest way to show that the
 * Socratic behaviour is architecture rather than a personality.
 */
export function TraceInspector({
  sessionId,
  open,
  onClose,
  turnCount,
}: {
  sessionId: string;
  open: boolean;
  onClose: () => void;
  turnCount: number;
}) {
  const trace = useQuery({
    queryKey: ["trace", sessionId, turnCount],
    queryFn: () => api.trace(sessionId),
    enabled: open,
  });

  const totalLatency =
    trace.data?.reduce((sum, event) => sum + event.latency_ms, 0) ?? 0;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-canvas/60 backdrop-blur-sm"
          />
          <motion.aside
            variants={panelIn}
            initial="hidden"
            animate="show"
            exit="exit"
            className="fixed right-0 top-0 z-50 flex h-full w-[min(460px,100vw)] flex-col border-l border-line bg-surface"
            role="dialog"
            aria-label="Session trace"
          >
            <header className="flex items-start justify-between border-b border-line px-5 py-4">
              <div>
                <h2 className="text-[14px] font-medium tracking-tight">Session trace</h2>
                <p className="mt-1 text-[12px] text-faint">
                  {trace.data?.length ?? 0} events · {totalLatency}ms of model time
                </p>
              </div>
              <button
                onClick={onClose}
                className="rounded-md p-1.5 text-faint transition-colors hover:text-ink focus-ring"
                aria-label="Close trace"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              {trace.isLoading && <p className="text-[13px] text-faint">Loading trace…</p>}

              <ol className="space-y-0">
                {trace.data?.map((event, index) => (
                  <li key={index} className="relative flex gap-3 pb-4">
                    <div className="flex flex-col items-center">
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{
                          background: `rgb(${AGENT_COLOR[event.agent] ?? "var(--faint)"})`,
                        }}
                      />
                      {index < (trace.data?.length ?? 0) - 1 && (
                        <span className="mt-1 w-px flex-1 bg-line" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                        <span
                          className="text-[12.5px] font-medium capitalize"
                          style={{
                            color: `rgb(${AGENT_COLOR[event.agent] ?? "var(--muted)"})`,
                          }}
                        >
                          {event.agent}
                        </span>
                        {event.state_from && (
                          <span className="font-mono text-[11px] text-faint">
                            {event.state_from} → {event.state_to}
                          </span>
                        )}
                        {event.latency_ms > 0 && (
                          <span className="text-[11px] tabular-nums text-faint">
                            {event.latency_ms}ms
                          </span>
                        )}
                        {event.guard_verdict && (
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                              event.guard_verdict === "pass"
                                ? "bg-state-mastered/10 text-state-mastered"
                                : "bg-state-alert/10 text-state-alert",
                            )}
                          >
                            guard: {event.guard_verdict}
                          </span>
                        )}
                      </div>

                      <p className="mt-0.5 text-[11px] text-faint">
                        {event.model}
                        {event.tokens_in > 0 && ` · ${event.tokens_in}→${event.tokens_out} tok`}
                      </p>

                      {typeof event.payload?.trigger === "string" && (
                        <p className="mt-1 font-mono text-[11px] text-muted">
                          {event.payload.trigger}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <footer className="border-t border-line px-5 py-3">
              <p className="text-[11.5px] leading-relaxed text-faint">
                Every mastery number this session produced is reconstructable from this log.
              </p>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
