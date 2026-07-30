"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium " +
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 " +
    "focus-ring disabled:pointer-events-none disabled:opacity-40 active:translate-y-px " +
    "select-none",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-white shadow-[0_1px_0_0_rgb(255_255_255/0.18)_inset] " +
          "hover:bg-accent/90 hover:shadow-glow",
        secondary: "bg-raised text-ink border border-line hover:border-faint hover:bg-raised/80",
        ghost: "text-muted hover:text-ink hover:bg-raised/70",
        outline: "border border-line text-ink hover:border-accent/60 hover:text-accent",
        danger: "bg-state-alert/15 text-state-alert border border-state-alert/30 hover:bg-state-alert/25",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-[15px]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(button({ variant, size }), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
