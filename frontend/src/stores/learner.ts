"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "@/lib/types";

/**
 * Client state only.
 *
 * Deliberately thin: mastery, session state and the learner model live on the
 * server and are read through TanStack Query. Mirroring them here would create a
 * second source of truth for numbers the product's credibility rests on, and the
 * two would drift.
 *
 * What belongs here is what the server does not care about — who is signed in on
 * this device, which graph they were last looking at, and whether the trace
 * inspector is open.
 */
interface LearnerState {
  user: User | null;
  activeGraphId: string | null;
  traceOpen: boolean;

  setUser: (user: User | null) => void;
  setActiveGraph: (graphId: string | null) => void;
  toggleTrace: () => void;
  signOut: () => void;
}

export const useLearner = create<LearnerState>()(
  persist(
    (set) => ({
      user: null,
      activeGraphId: null,
      traceOpen: false,

      setUser: (user) => set({ user }),
      setActiveGraph: (activeGraphId) => set({ activeGraphId }),
      toggleTrace: () => set((s) => ({ traceOpen: !s.traceOpen })),
      signOut: () => set({ user: null, activeGraphId: null }),
    }),
    {
      name: "vectoros.learner",
      partialize: (s) => ({ user: s.user, activeGraphId: s.activeGraphId }),
    },
  ),
);
