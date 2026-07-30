import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { NodeStatus, Quadrant, SessionState } from "@/lib/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const percent = (value: number) => `${Math.round(value * 100)}%`;

/**
 * Mastery colour, used identically on the graph, the workspace ring and the
 * dashboard. A learner should be able to read their state from colour alone,
 * which only works if the mapping never varies by screen.
 */
export const STATUS_COLOR: Record<NodeStatus, string> = {
  locked: "var(--state-locked)",
  available: "var(--state-available)",
  in_progress: "var(--state-progress)",
  review_due: "var(--state-review)",
  mastered: "var(--state-mastered)",
};

export const STATUS_LABEL: Record<NodeStatus, string> = {
  locked: "Locked",
  available: "Ready",
  in_progress: "In progress",
  review_due: "Review due",
  mastered: "Mastered",
};

/** What the learner is being asked to do right now, in plain language. */
export const STATE_LABEL: Record<SessionState, string> = {
  idle: "Getting ready",
  elicit: "What you already believe",
  diagnose: "Reading your model",
  instruct: "Calibrated explanation",
  challenge: "Your turn",
  attempt: "Working",
  evaluate: "Checking your reasoning",
  coach: "Guided inquiry",
  reflect: "Rebuild it from memory",
  mastery: "Recording mastery",
  complete: "Closed",
};

export const QUADRANT_META: Record<
  Quadrant,
  { label: string; tone: string; description: string }
> = {
  automaticity: {
    label: "Solid",
    tone: "text-state-mastered",
    description: "Right, and you knew it. This is what mastery feels like from the inside.",
  },
  fragile: {
    label: "Underrated",
    tone: "text-state-review",
    description: "Right, but you doubted it. You know more than you think you do.",
  },
  blind_spot: {
    label: "Blind spot",
    tone: "text-state-alert",
    description: "Wrong while certain. This is the one worth your attention.",
  },
  known_gap: {
    label: "Known gap",
    tone: "text-state-progress",
    description: "Wrong, and you sensed it. The healthiest way to be wrong.",
  },
};

export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diff = then - Date.now();
  const abs = Math.abs(diff);
  const day = 86_400_000;
  const hour = 3_600_000;

  const format = (value: number, unit: string) =>
    diff < 0 ? `${value}${unit} ago` : `in ${value}${unit}`;

  if (abs < hour) return format(Math.max(1, Math.round(abs / 60_000)), "m");
  if (abs < day) return format(Math.round(abs / hour), "h");
  return format(Math.round(abs / day), "d");
}

/**
 * Minimal markdown: **bold** and paragraph breaks.
 *
 * Deliberately not a markdown engine. Tutor messages are prose with the
 * occasional emphasised term; supporting headings and bullet lists would invite
 * the model to produce lecture-shaped output, and a wall of bullets is exactly
 * the format this product exists to avoid.
 */
export function renderInline(text: string): { bold: boolean; text: string }[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part) =>
    part.startsWith("**") && part.endsWith("**")
      ? { bold: true, text: part.slice(2, -2) }
      : { bold: false, text: part },
  );
}

export const paragraphs = (text: string) =>
  text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);

/**
 * The API returns one complete utterance in `message` — instruction *and* the
 * challenge — because a CLI or SMS client has nowhere else to put the task.
 * This client pins the challenge in its own card, so showing it twice reads as
 * a bug. Strip the trailing copy and keep the narrative.
 */
export function narrativeOf(message: string, challenge: string | null): string {
  if (!challenge?.trim()) return message;
  const index = message.lastIndexOf(challenge.trim());
  return index === -1 ? message : message.slice(0, index).trim();
}
