"use client";

import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { KeyRound } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PedagogicalError, api } from "@/lib/api";
import { modalIn } from "@/lib/motion";
import type { Session } from "@/lib/types";

/**
 * The anti-offload circuit, surfaced.
 *
 * After three demands for the answer the API locks free text. This screen is
 * what the learner gets instead — and it is deliberately not a punishment or a
 * cooldown. It asks for one concrete thing they *do* understand about the
 * problem, which is a low bar and is meant to be: the goal is to interrupt the
 * reflex of asking, not to lock anyone out of their own session.
 */
export function EngagementLock({
  session,
  onUnlocked,
}: {
  session: Session;
  onUnlocked: (session: Session) => void;
}) {
  const [proof, setProof] = React.useState("");

  const unlock = useMutation({
    mutationFn: () => api.unlockInput(session.id, proof),
    onSuccess: onUnlocked,
  });

  const error =
    unlock.error instanceof PedagogicalError ? unlock.error.message : null;

  return (
    <motion.div
      variants={modalIn}
      initial="hidden"
      animate="show"
      className="rounded-2xl border border-state-progress/30 bg-state-progress/[0.06] p-6"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-state-progress/30 bg-state-progress/10">
          <KeyRound className="h-3.5 w-3.5 text-state-progress" strokeWidth={1.8} />
        </span>
        <div>
          <h3 className="text-[15px] font-medium tracking-tight">
            Let&rsquo;s reset this for a second.
          </h3>
          <p className="mt-2 max-w-prose text-[13.5px] leading-relaxed text-muted">
            You have asked for the answer a few times, and I keep saying no — which is
            annoying, and I would rather not just repeat myself. So: tell me one part of this
            problem you <em>do</em> understand. Any part. Then the keyboard comes back and we
            carry on from there.
          </p>
        </div>
      </div>

      <Textarea
        autoFocus
        value={proof}
        onChange={(e) => setProof(e.target.value)}
        rows={3}
        placeholder="One thing I'm sure about here is…"
        className="mt-5"
      />

      {error && <p className="mt-2.5 text-[12.5px] text-state-alert">{error}</p>}

      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={() => unlock.mutate()}
          loading={unlock.isPending}
          disabled={proof.trim().split(/\s+/).length < 4}
        >
          Continue
        </Button>
        <span className="text-[12.5px] text-faint">A sentence is enough.</span>
      </div>
    </motion.div>
  );
}
