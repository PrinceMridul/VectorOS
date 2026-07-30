"use client";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Lock, RotateCcw, Sparkles } from "lucide-react";
import * as React from "react";

import { MasteryRing } from "@/components/ui/mastery-ring";
import { ease } from "@/lib/motion";
import type { GraphNode } from "@/lib/types";
import { STATUS_COLOR, STATUS_LABEL, cn, percent } from "@/lib/utils";

export type ConceptNodeData = {
  node: GraphNode;
  isFrontier: boolean;
  justUnlocked: boolean;
  onOpen: (nodeId: string) => void;
};

export type ConceptFlowNode = Node<ConceptNodeData, "concept">;

/**
 * A concept on the graph.
 *
 * Three things are encoded visually and none of them are decorative:
 *
 *  - **The ring** is P(mastery), so a concept at 0.6 visibly is not finished.
 *    A checkmark would claim something the model does not believe.
 *  - **The glow** marks the frontier — the one node the planner recommends,
 *    chosen from review debt first, then unfinished work, then difficulty.
 *  - **The lock** is real. Clicking does nothing, and the tooltip says which
 *    prerequisites are not yet held rather than just refusing.
 */
export function ConceptNodeView({ data, selected }: NodeProps<ConceptFlowNode>) {
  const { node, isFrontier, justUnlocked, onOpen } = data;
  const locked = node.status === "locked";
  const color = STATUS_COLOR[node.status];

  return (
    <motion.div
      initial={justUnlocked ? { scale: 0.88, opacity: 0 } : false}
      animate={{ scale: 1, opacity: 1 }}
      transition={justUnlocked ? { type: "spring", stiffness: 260, damping: 18 } : undefined}
      className="relative"
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0 !bg-line"
      />

      {/* Unlock bloom: a single expanding ring, once. Access was earned. */}
      <AnimatePresence>
        {justUnlocked && (
          <motion.span
            initial={{ scale: 0.7, opacity: 0.7 }}
            animate={{ scale: 1.9, opacity: 0 }}
            transition={{ duration: 1.1, ease: ease.out }}
            className="pointer-events-none absolute inset-0 rounded-2xl"
            style={{ boxShadow: `0 0 0 2px rgb(${color})` }}
          />
        )}
      </AnimatePresence>

      {/* Frontier breathing halo. Slow enough to read as "here", not as an alert. */}
      {isFrontier && !locked && (
        <motion.span
          className="pointer-events-none absolute -inset-1.5 rounded-[18px]"
          style={{ background: `rgb(${color} / 0.14)` }}
          animate={{ opacity: [0.4, 0.9, 0.4], scale: [0.99, 1.015, 0.99] }}
          transition={{ duration: 3.6, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      <button
        type="button"
        disabled={locked}
        onClick={() => !locked && onOpen(node.id)}
        aria-label={`${node.title} — ${STATUS_LABEL[node.status]}`}
        className={cn(
          "group relative flex w-[248px] flex-col gap-3 rounded-2xl border p-4 text-left",
          "transition-[transform,border-color,box-shadow,background-color] duration-200 focus-ring",
          locked
            ? "cursor-not-allowed border-line/70 bg-surface/30"
            : "border-line bg-surface/90 backdrop-blur-xl hover:-translate-y-0.5 hover:border-faint hover:shadow-lift",
          selected && !locked && "border-accent/60",
        )}
        style={
          isFrontier && !locked
            ? { borderColor: `rgb(${color} / 0.55)`, background: `rgb(${color} / 0.05)` }
            : undefined
        }
      >
        <div className="flex items-start gap-3">
          <MasteryRing
            value={locked ? 0 : node.mastery}
            size={38}
            stroke={2.5}
            color={`rgb(${color})`}
          >
            {locked ? (
              <Lock className="h-3.5 w-3.5 text-faint" strokeWidth={1.8} />
            ) : node.status === "mastered" ? (
              <Check className="h-3.5 w-3.5" style={{ color: `rgb(${color})` }} strokeWidth={2.4} />
            ) : node.status === "review_due" ? (
              <RotateCcw
                className="h-3.5 w-3.5"
                style={{ color: `rgb(${color})` }}
                strokeWidth={2}
              />
            ) : (
              <span className="text-[10px] font-medium tabular-nums text-muted">
                {Math.round(node.mastery * 100)}
              </span>
            )}
          </MasteryRing>

          <div className="min-w-0 flex-1">
            <h3
              className={cn(
                "truncate text-[13.5px] font-medium leading-snug tracking-tight",
                locked ? "text-faint" : "text-ink",
              )}
            >
              {node.title}
            </h3>
            <p
              className={cn(
                "mt-1 line-clamp-2 text-[11.5px] leading-snug",
                locked ? "text-faint/60" : "text-muted",
              )}
            >
              {node.one_liner}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span
            className="text-2xs font-medium uppercase tracking-[0.1em]"
            style={{ color: locked ? undefined : `rgb(${color})` }}
          >
            <span className={locked ? "text-faint/70" : undefined}>
              {isFrontier && !locked ? "Recommended" : STATUS_LABEL[node.status]}
            </span>
          </span>

          {isFrontier && !locked ? (
            <Sparkles className="h-3 w-3" style={{ color: `rgb(${color})` }} strokeWidth={1.8} />
          ) : !locked && node.mastery > 0 ? (
            <span className="text-2xs tabular-nums text-faint">{percent(node.mastery)}</span>
          ) : null}
        </div>

        {locked && node.blocked_by.length > 0 && (
          <div className="pointer-events-none absolute -bottom-1 left-1/2 z-10 w-max max-w-[220px] -translate-x-1/2 translate-y-full rounded-lg border border-line bg-raised px-2.5 py-1.5 text-2xs text-muted opacity-0 shadow-lift transition-opacity duration-200 group-hover:opacity-100">
            Master {node.blocked_by.length} prerequisite
            {node.blocked_by.length > 1 ? "s" : ""} first
          </div>
        )}
      </button>

      <Handle
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0 !bg-line"
      />
    </motion.div>
  );
}
