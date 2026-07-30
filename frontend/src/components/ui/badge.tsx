import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badge = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-2xs font-medium " +
    "tracking-wide whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "border-line bg-raised/60 text-muted",
        accent: "border-accent/30 bg-accent/10 text-accent",
        mastered: "border-state-mastered/30 bg-state-mastered/10 text-state-mastered",
        progress: "border-state-progress/30 bg-state-progress/10 text-state-progress",
        review: "border-state-review/30 bg-state-review/10 text-state-review",
        alert: "border-state-alert/30 bg-state-alert/10 text-state-alert",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badge> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)} {...props} />;
}
