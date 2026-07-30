"use client";

import * as React from "react";

import { AboutBuilder } from "@/components/about-builder";
import { ATTRIBUTION, CREATOR } from "@/lib/creator";
import { cn } from "@/lib/utils";

/**
 * The creator signature.
 *
 * Placed inside existing chrome — a header slot or a footer row — never as a
 * floating badge pinned over the canvas. A fixed-position mark would collide
 * with the graph's frontier card, the workspace signals panel and the state
 * rail, and more importantly it would read as a watermark on a surface someone
 * is trying to think on.
 *
 * On narrow screens the full sentence collapses to just the name: the
 * attribution should never be the thing that wraps a header onto two lines.
 */
export function CreatorSignature({
  variant = "inline",
  className,
}: {
  variant?: "inline" | "footer";
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const close = React.useCallback(() => setOpen(false), []);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={ATTRIBUTION}
        className={cn(
          "rounded-md transition-colors focus-ring",
          variant === "inline"
            ? "px-1.5 py-1 text-[12.5px] text-faint hover:text-muted"
            : "text-[11.5px] text-faint hover:text-muted",
          className,
        )}
      >
        <span className="hidden sm:inline">
          Designed &amp; built by <span className="text-muted">{CREATOR.name}</span>
        </span>
        <span className="sm:hidden">{CREATOR.name}</span>
      </button>

      <AboutBuilder open={open} onClose={close} />
    </>
  );
}
