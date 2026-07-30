"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesInitialized,
  useNodesState,
  useReactFlow,
  type Edge,
} from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, Maximize2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { MasteryBar } from "@/components/ui/mastery-ring";
import { ConceptNodeView, type ConceptFlowNode } from "@/features/graph/concept-node";
import { api } from "@/lib/api";
import { ease, riseIn, stagger } from "@/lib/motion";
import type { LearningGraph } from "@/lib/types";
import { STATUS_COLOR, percent } from "@/lib/utils";
import { useLearner } from "@/stores/learner";

const nodeTypes = { concept: ConceptNodeView };

export function GraphView({ graphId }: { graphId: string }) {
  return (
    <ReactFlowProvider>
      <GraphViewInner graphId={graphId} />
    </ReactFlowProvider>
  );
}

function GraphViewInner({ graphId }: { graphId: string }) {
  const router = useRouter();
  const setActiveGraph = useLearner((s) => s.setActiveGraph);
  const { fitView } = useReactFlow();

  React.useEffect(() => setActiveGraph(graphId), [graphId, setActiveGraph]);

  const graph = useQuery({ queryKey: ["graph", graphId], queryFn: () => api.graph(graphId) });

  /**
   * Track which nodes were locked last time we rendered, so a node that has just
   * become reachable can bloom exactly once. Celebrating on every poll would
   * turn a meaningful event into wallpaper.
   */
  const previouslyLocked = React.useRef<Set<string> | null>(null);
  const [justUnlocked, setJustUnlocked] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    if (!graph.data) return;
    const lockedNow = new Set(
      graph.data.nodes.filter((n) => n.status === "locked").map((n) => n.id),
    );
    const before = previouslyLocked.current;
    if (before) {
      const opened = [...before].filter((id) => !lockedNow.has(id));
      if (opened.length) {
        setJustUnlocked(new Set(opened));
        const timer = window.setTimeout(() => setJustUnlocked(new Set()), 1600);
        previouslyLocked.current = lockedNow;
        return () => window.clearTimeout(timer);
      }
    }
    previouslyLocked.current = lockedNow;
    return;
  }, [graph.data]);

  const open = useMutation({
    mutationFn: (nodeId: string) => api.openSession(nodeId),
    onSuccess: (session) => router.push(`/learn/${session.id}`),
  });

  /**
   * React Flow is used in controlled mode, which means it hands *us* its
   * internal updates — including the dimension measurements it takes after
   * first paint. Those have to be applied back or every node stays
   * `visibility: hidden` and no edges ever draw, because edges need both
   * endpoints measured. Hence `useNodesState` rather than a plain `useMemo`.
   */
  const [nodes, setNodes, onNodesChange] = useNodesState<ConceptFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const openNode = React.useCallback((id: string) => open.mutate(id), [open.mutate]); // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    if (!graph.data) return;
    const built = buildFlow(graph.data, justUnlocked, openNode);
    setNodes(built.nodes);
    setEdges(built.edges);
  }, [graph.data, justUnlocked, openNode, setNodes, setEdges]);

  /**
   * Fit only once React Flow has actually measured the nodes. Firing on a
   * timer races the measurement pass and silently no-ops on slower devices,
   * leaving the learner looking at a graph scrolled off-centre.
   */
  const nodesInitialized = useNodesInitialized();
  const hasFitted = React.useRef(false);

  React.useEffect(() => {
    if (!nodesInitialized || hasFitted.current || nodes.length === 0) return;
    hasFitted.current = true;
    fitView({ padding: 0.24, duration: 700 });
  }, [nodesInitialized, nodes.length, fitView]);

  const frontier = graph.data?.nodes.find((n) => n.id === graph.data?.frontier_node_id);

  return (
    <AppShell
      right={
        <button
          onClick={() => fitView({ padding: 0.24, duration: 500 })}
          className="rounded-md p-1.5 text-faint transition-colors hover:text-ink focus-ring"
          aria-label="Fit graph to view"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      }
    >
      <div className="relative h-[calc(100vh-3.5rem)] w-full">
        {graph.isLoading && <GraphSkeleton />}

        {graph.data && (
          <>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.35}
              maxZoom={1.5}
              proOptions={{ hideAttribution: true }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              className="bg-canvas"
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={28}
                size={1}
                color="rgb(var(--line))"
              />
            </ReactFlow>

            {/* Header overlay — floats above the canvas rather than pushing it. */}
            <motion.div
              variants={stagger(0.05, 0.06)}
              initial="hidden"
              animate="show"
              className="pointer-events-none absolute left-6 top-6 max-w-md"
            >
              <motion.h1
                variants={riseIn}
                className="text-[22px] font-semibold tracking-tight text-ink"
              >
                {graph.data.title}
              </motion.h1>
              <motion.p variants={riseIn} className="mt-1.5 text-[13.5px] text-muted">
                {graph.data.goal}
              </motion.p>
              <motion.div variants={riseIn} className="mt-4 w-64">
                <div className="flex items-baseline justify-between text-2xs text-faint">
                  <span>
                    {graph.data.mastered_count} of {graph.data.total_count} held
                  </span>
                  <span className="tabular-nums">{percent(graph.data.overall_mastery)}</span>
                </div>
                <MasteryBar
                  value={graph.data.overall_mastery}
                  color="rgb(var(--accent))"
                  className="mt-2"
                />
              </motion.div>
            </motion.div>

            <AnimatePresence>
              {frontier && (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.4, ease: ease.out, delay: 0.3 }}
                  className="absolute bottom-6 left-1/2 z-10 w-[min(560px,calc(100vw-3rem))] -translate-x-1/2"
                >
                  <div className="flex items-center gap-4 rounded-2xl border border-line bg-surface/90 p-3 pl-5 shadow-lift backdrop-blur-xl">
                    <div className="min-w-0 flex-1">
                      <p className="text-2xs font-medium uppercase tracking-[0.14em] text-faint">
                        {frontier.status === "review_due"
                          ? "Due for review — retaining beats acquiring"
                          : "Next"}
                      </p>
                      <p className="mt-1 truncate text-[14px] font-medium tracking-tight">
                        {frontier.title}
                      </p>
                    </div>
                    <Button
                      onClick={() => open.mutate(frontier.id)}
                      loading={open.isPending}
                      className="shrink-0"
                    >
                      Open
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <Legend />
          </>
        )}

        {graph.isError && (
          <div className="grid h-full place-items-center">
            <p className="text-[14px] text-muted">Could not load your learning graph.</p>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function buildFlow(
  graph: LearningGraph,
  justUnlocked: Set<string>,
  onOpen: (id: string) => void,
): { nodes: ConceptFlowNode[]; edges: Edge[] } {
  const nodes: ConceptFlowNode[] = graph.nodes.map((node) => ({
    id: node.id,
    type: "concept",
    position: node.position,
    data: {
      node,
      isFrontier: node.id === graph.frontier_node_id,
      justUnlocked: justUnlocked.has(node.id),
      onOpen,
    },
    draggable: false,
  }));

  const byId = new Map(graph.nodes.map((n) => [n.id, n]));

  const edges: Edge[] = graph.edges.map((edge) => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    const satisfied = source?.status === "mastered" || source?.status === "review_due";
    // The edge into the recommended node animates — it is the path you are on.
    const live = target?.id === graph.frontier_node_id && satisfied;

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: live,
      style: {
        stroke: satisfied ? `rgb(${STATUS_COLOR.mastered} / 0.5)` : "rgb(var(--line))",
        strokeWidth: live ? 2 : 1.5,
      },
    };
  });

  return { nodes, edges };
}

function Legend() {
  const items = [
    { status: "mastered", label: "Held" },
    { status: "review_due", label: "Fading" },
    { status: "in_progress", label: "In progress" },
    { status: "available", label: "Ready" },
    { status: "locked", label: "Locked" },
  ] as const;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.6, duration: 0.5 }}
      className="absolute right-6 top-6 hidden flex-col gap-2 rounded-xl border border-line bg-surface/70 px-3.5 py-3 backdrop-blur-xl lg:flex"
    >
      {items.map(({ status, label }) => (
        <div key={status} className="flex items-center gap-2.5">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: `rgb(${STATUS_COLOR[status]})` }}
          />
          <span className="text-2xs text-muted">{label}</span>
        </div>
      ))}
    </motion.div>
  );
}

function GraphSkeleton() {
  return (
    <div className="grid h-full place-items-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-4 w-4 animate-spin text-accent" />
        <p className="text-[13px] text-faint">Laying out your dependency graph…</p>
      </div>
    </div>
  );
}
