"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Command, Loader2, ScrollText, Target } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { AppShell } from "@/components/app-shell";
import { TutorMessage } from "@/components/tutor-message";
import { AgentActivity } from "@/features/workspace/agent-activity";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ConfidenceGate } from "@/features/workspace/confidence-gate";
import { EngagementLock } from "@/features/workspace/engagement-lock";
import { ReflectionGate } from "@/features/workspace/reflection-gate";
import { SignalsPanel } from "@/features/workspace/signals-panel";
import { StateRail } from "@/features/workspace/state-rail";
import { StruggleTimer } from "@/features/workspace/struggle-timer";
import { TraceInspector } from "@/features/workspace/trace-inspector";
import { UnderstandingShift } from "@/features/workspace/understanding-shift";
import { PedagogicalError, api } from "@/lib/api";
import { ease, riseIn, stagger } from "@/lib/motion";
import type { Confidence, TurnRequest } from "@/lib/types";
import { STATE_LABEL, cn, narrativeOf } from "@/lib/utils";

/**
 * The workspace.
 *
 * Three deliberate absences define this screen:
 *
 *  1. **No message history.** There is one tutor message and it is the current
 *     one. A scrollback turns a dialogue into a transcript you can mine, and
 *     mining is the behaviour we are trying not to teach.
 *  2. **No chat composer.** The primary surface is a thinking canvas — a wide
 *     block for a paragraph of reasoning, where Enter makes a newline. A box
 *     that submits on Enter trains one-line answers.
 *  3. **No send button until you have committed.** Confidence first, always.
 *
 * The learner asks "explain X" and the system does not explain: it elicits. That
 * is enforced by the server's state machine — this component's job is to make
 * the request feel like an invitation rather than a refusal.
 */
export function Workspace({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient();

  const session = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.session(sessionId),
  });

  const [draft, setDraft] = React.useState("");
  const [confidence, setConfidence] = React.useState<Confidence | null>(null);
  const [traceOpen, setTraceOpen] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [refused, setRefused] = React.useState(false);

  /** Reset the clock whenever the tutor says something new. */
  const message = session.data?.message ?? "";
  const startedAtRef = React.useRef(Date.now());
  const canvasRef = React.useRef<HTMLTextAreaElement | null>(null);

  React.useEffect(() => {
    startedAtRef.current = Date.now();
    // Put the caret back on the thinking surface after every tutor turn, so a
    // keyboard user is never stranded at the top of the page mid-session.
    canvasRef.current?.focus();
  }, [message]);

  const turn = useMutation({
    mutationFn: (payload: TurnRequest) =>
      api.turn(sessionId, { ...payload, elapsed_ms: Date.now() - startedAtRef.current }),
    onSuccess: (result) => {
      queryClient.setQueryData(["session", sessionId], result.session);
      queryClient.invalidateQueries({ queryKey: ["graph", result.session.graph_id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });

      setRefused(result.refused);
      setNotice(null);

      // Keep the learner's words only when the tutor pushed back without
      // grading them; a graded attempt deserves a clean surface for the next one.
      if (!result.refused) {
        setDraft("");
        setConfidence(null);
      }
    },
    onError: (error) => {
      setNotice(
        error instanceof PedagogicalError
          ? error.message
          : "Something went wrong. Your work is safe — try again.",
      );
    },
  });

  const data = session.data;

  // Derived up here rather than beside the JSX, so the keyboard handler below
  // does not close over a binding declared later in the function body.
  const needsConfidence = Boolean(data?.requires_confidence) && !confidence;
  const canSubmit = Boolean(data) && draft.trim().length > 2 && !needsConfidence && !turn.isPending;

  const submit = React.useCallback(() => {
    if (!data) return;
    const payload: TurnRequest = { text: draft };
    if (data.requires_confidence) payload.confidence = confidence;
    turn.mutate(payload);
  }, [data, draft, confidence, turn]);

  // Cmd/Ctrl+Enter submits. A plain Enter must stay a newline — see the note
  // at the top of this file: a box that submits on Enter teaches one-line answers.
  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        if (canSubmit) submit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canSubmit, submit]);

  if (session.isLoading || !data) {
    return (
      <AppShell>
        <div className="grid h-[calc(100vh-3.5rem)] place-items-center">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            <p className="text-[13px] text-faint">Opening your session…</p>
          </div>
        </div>
      </AppShell>
    );
  }

  const isReflect = data.state === "reflect";
  const isComplete = data.completed;
  const wordCount = draft.trim() ? draft.trim().split(/\s+/).length : 0;

  return (
    <AppShell
      right={
        <button
          onClick={() => setTraceOpen(true)}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12.5px] text-faint transition-colors hover:text-ink focus-ring"
        >
          <ScrollText className="h-3.5 w-3.5" strokeWidth={1.7} />
          Trace
        </button>
      }
    >
      <div className="mx-auto flex w-full max-w-[1600px]">
        <StateRail state={data.state} />

        <main id="work" className="min-w-0 flex-1 px-6 py-8 sm:px-10">
          <div className="mx-auto max-w-2xl">
            {/* Concept header */}
            <motion.div variants={stagger()} initial="hidden" animate="show">
              <motion.div variants={riseIn} className="flex items-center gap-3">
                <Link
                  href={`/graph/${data.graph_id}`}
                  className="flex items-center gap-1.5 rounded-md py-1 pr-2 text-[12.5px] text-faint transition-colors hover:text-ink focus-ring"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Graph
                </Link>
                <span className="h-3 w-px bg-line" />
                <span className="text-2xs font-medium uppercase tracking-[0.14em] text-accent">
                  {STATE_LABEL[data.state]}
                </span>
              </motion.div>

              <motion.h1
                variants={riseIn}
                className="mt-3 text-[26px] font-semibold leading-tight tracking-[-0.02em]"
              >
                {data.node_title}
              </motion.h1>
              <motion.p variants={riseIn} className="mt-1.5 text-[14px] text-muted">
                {data.node_one_liner}
              </motion.p>
            </motion.div>

            <div className="mt-9">
              <AnimatePresence mode="wait">
                {isComplete ? (
                  <UnderstandingShift
                    key="shift"
                    sessionId={sessionId}
                    graphId={data.graph_id}
                  />
                ) : data.input_locked ? (
                  <EngagementLock
                    key="locked"
                    session={data}
                    onUnlocked={(next) =>
                      queryClient.setQueryData(["session", sessionId], next)
                    }
                  />
                ) : isReflect ? (
                  <ReflectionGate
                    key="reflect"
                    session={data}
                    value={draft}
                    onChange={setDraft}
                    onSubmit={submit}
                    pending={turn.isPending}
                  />
                ) : (
                  <motion.div key={`work-${data.turn_count}`}>
                    {/* What the tutor is saying right now, minus the challenge
                        itself — that gets its own pinned card below.
                        `aria-live` matters here: the whole interface is one
                        changing message, and a screen-reader user who is not
                        told it changed has lost the product. */}
                    <div role="status" aria-live="polite" aria-atomic="true">
                      <AnimatePresence mode="wait">
                        <TutorMessage
                          key={data.message}
                          text={narrativeOf(data.message, data.challenge_prompt)}
                          tone={refused ? "refusal" : "default"}
                        />
                      </AnimatePresence>
                    </div>

                    {/* The active challenge, pinned so it does not scroll away
                        while the learner is answering it. */}
                    {data.challenge_prompt && data.state !== "elicit" && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.15, ease: ease.out }}
                        className="mt-7 rounded-2xl border border-accent/25 bg-accent/[0.05] p-5"
                      >
                        <div className="flex items-center gap-2 text-2xs font-medium uppercase tracking-[0.14em] text-accent">
                          <Target className="h-3 w-3" strokeWidth={2} />
                          Challenge
                        </div>
                        <p className="mt-3 text-[15px] leading-relaxed text-ink">
                          {data.challenge_prompt}
                        </p>
                      </motion.div>
                    )}

                    {/* The thinking canvas. */}
                    <motion.div
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4, delay: 0.25, ease: ease.out }}
                      className="mt-7"
                    >
                      <div className="mb-2.5 flex items-baseline justify-between">
                        <span className="text-2xs font-medium uppercase tracking-[0.14em] text-faint">
                          {data.state === "elicit" ? "What you already believe" : "Your reasoning"}
                        </span>
                        <span className="text-[11.5px] tabular-nums text-faint">
                          {wordCount > 0 ? `${wordCount} words` : ""}
                        </span>
                      </div>

                      <Textarea
                        ref={canvasRef}
                        autoFocus
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={data.state === "elicit" ? 6 : 7}
                        placeholder={
                          data.state === "elicit"
                            ? "I think it's roughly… (a guess is genuinely useful here)"
                            : "Work it through — show the steps, not just the conclusion…"
                        }
                        className="min-h-[176px]"
                      />
                    </motion.div>

                    {/* Confidence, then submit. Never the other way round. */}
                    <AnimatePresence>
                      {data.requires_confidence && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="overflow-hidden"
                        >
                          <div className="pt-6">
                            <ConfidenceGate
                              value={confidence}
                              onChange={setConfidence}
                              disabled={turn.isPending}
                            />
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <div className="mt-7 flex flex-wrap items-center gap-4">
                      <Button
                        size="lg"
                        onClick={submit}
                        loading={turn.isPending}
                        disabled={!canSubmit}
                      >
                        {data.state === "elicit" ? "This is what I think" : "Submit reasoning"}
                      </Button>

                      {data.state !== "elicit" && (
                        <StruggleTimer
                          seconds={data.struggle_floor_seconds}
                          startedAt={startedAtRef.current}
                          unlocked={data.guidance_available}
                          pending={turn.isPending}
                          onRequest={() => turn.mutate({ request_guidance: true })}
                        />
                      )}

                      <AnimatePresence>
                        {turn.isPending && (
                          <AgentActivity
                            state={data.state}
                            requestingGuidance={turn.variables?.request_guidance}
                          />
                        )}
                      </AnimatePresence>

                      <span className="ml-auto hidden items-center gap-1 text-[11.5px] text-faint sm:flex">
                        <Command className="h-3 w-3" />
                        <span>+ Enter to submit</span>
                      </span>
                    </div>

                    <AnimatePresence>
                      {notice && (
                        <motion.p
                          initial={{ opacity: 0, y: -4 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className={cn(
                            "mt-4 rounded-lg border px-3.5 py-2.5 text-[13px] leading-relaxed",
                            "border-state-progress/30 bg-state-progress/[0.07] text-state-progress",
                          )}
                        >
                          {notice}
                        </motion.p>
                      )}
                    </AnimatePresence>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </main>

        <SignalsPanel session={data} />
      </div>

      <TraceInspector
        sessionId={sessionId}
        open={traceOpen}
        onClose={() => setTraceOpen(false)}
        turnCount={data.turn_count}
      />
    </AppShell>
  );
}
