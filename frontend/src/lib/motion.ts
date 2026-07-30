import type { Transition, Variants } from "framer-motion";

/**
 * Motion tokens.
 *
 * Every animation in VectorOS encodes a learning event. That is the test a new
 * animation has to pass before it ships: if you cannot say what it *means*, it
 * is decoration and it goes.
 *
 *   node unlock bloom    →  access to advanced ideas is earned, not browsed
 *   mastery ring fill    →  knowledge is graded and perishable, not a checkmark
 *   struggle timer sweep →  productive failure has a floor
 *   confidence detent    →  committing to a belief should feel deliberate
 *   coach panel slide-in →  your thinking stays primary; help arrives beside it
 *
 * Durations sit in the 150–450ms band: fast enough to feel like a native tool,
 * slow enough that a state change is legible rather than a flicker.
 */

export const ease = {
  /** Default. Decisive out, soft landing. */
  out: [0.16, 1, 0.3, 1] as const,
  /** For things entering and settling — dialogs, panels. */
  spring: { type: "spring", stiffness: 380, damping: 34, mass: 0.9 } as Transition,
  /** For something that has just been earned. Slight overshoot reads as reward. */
  reward: { type: "spring", stiffness: 260, damping: 18, mass: 0.8 } as Transition,
};

export const durations = {
  micro: 0.15,
  base: 0.28,
  slow: 0.45,
};

/** Page-level entrance. Content rises a few pixels; nothing slides across. */
export const pageIn: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: durations.base, ease: ease.out },
  },
};

/** Parent for staggered lists. Stagger implies reading order. */
export const stagger = (delayChildren = 0.04, staggerChildren = 0.05): Variants => ({
  hidden: {},
  show: { transition: { delayChildren, staggerChildren } },
});

export const riseIn: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: durations.base, ease: ease.out } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: durations.slow, ease: ease.out } },
};

/** The tutor speaking. Slightly slower than UI motion — this is someone talking. */
export const tutorMessage: Variants = {
  hidden: { opacity: 0, y: 10, filter: "blur(6px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.5, ease: ease.out },
  },
  exit: { opacity: 0, y: -6, transition: { duration: durations.micro } },
};

/** A concept becoming reachable. The only place overshoot is allowed. */
export const unlockBloom: Variants = {
  hidden: { scale: 0.9, opacity: 0 },
  show: { scale: 1, opacity: 1, transition: ease.reward },
};

/** Side panel: arrives *next to* the learner's work, never on top of it. */
export const panelIn: Variants = {
  hidden: { opacity: 0, x: 24 },
  show: { opacity: 1, x: 0, transition: ease.spring },
  exit: { opacity: 0, x: 16, transition: { duration: durations.micro } },
};

export const modalIn: Variants = {
  hidden: { opacity: 0, scale: 0.97, y: 12 },
  show: { opacity: 1, scale: 1, y: 0, transition: ease.spring },
  exit: { opacity: 0, scale: 0.98, y: 8, transition: { duration: durations.micro } },
};
