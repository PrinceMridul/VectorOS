"use client";

import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import * as React from "react";

import { cn } from "@/lib/utils";

interface MasteryRingProps {
  /** 0..1 probability of mastery. Not a completion percentage. */
  value: number;
  size?: number;
  stroke?: number;
  color?: string;
  className?: string;
  children?: React.ReactNode;
}

/**
 * Mastery as a ring that fills — never as a checkmark.
 *
 * The distinction is the product's whole position on progress: a tick says
 * "done, forever". A partially-filled ring says "this is an estimate, it can go
 * down, and it will if you leave it alone". The number underneath is a
 * probability, and the ring is drawn so that 85% still visibly has a gap in it.
 */
export function MasteryRing({
  value,
  size = 44,
  stroke = 3,
  color = "rgb(var(--accent))",
  className,
  children,
}: MasteryRingProps) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  const raw = useMotionValue(0);
  const spring = useSpring(raw, { stiffness: 120, damping: 22, mass: 0.7 });
  const offset = useTransform(spring, (v) => circumference * (1 - Math.max(0, Math.min(1, v))));

  React.useEffect(() => {
    raw.set(value);
  }, [value, raw]);

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--line))"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          style={{ strokeDashoffset: offset }}
        />
      </svg>
      {children ? (
        <div className="absolute inset-0 flex items-center justify-center">{children}</div>
      ) : null}
    </div>
  );
}

/** Horizontal variant, for dense lists where a ring would be too heavy. */
export function MasteryBar({
  value,
  color = "rgb(var(--accent))",
  className,
}: {
  value: number;
  color?: string;
  className?: string;
}) {
  return (
    <div className={cn("h-1 w-full overflow-hidden rounded-full bg-line", className)}>
      <motion.div
        className="h-full rounded-full"
        style={{ background: color }}
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      />
    </div>
  );
}
