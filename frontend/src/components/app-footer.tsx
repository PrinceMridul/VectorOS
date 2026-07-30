"use client";

import * as React from "react";

import { CreatorSignature } from "@/components/creator-signature";
import { FOOTER_NOTE, VERSION } from "@/lib/creator";
import { cn } from "@/lib/utils";

/**
 * The footer.
 *
 * Rendered only on pages that have a natural bottom — the landing page and the
 * progress record. The graph is a full-height canvas and the workspace is a
 * focus surface; appending a footer to either would mean a strip of branding
 * sitting under a concept someone is mid-way through learning.
 *
 * One line on desktop, stacked on mobile, at the smallest type in the system.
 */
export function AppFooter({ className }: { className?: string }) {
  return (
    <footer
      className={cn(
        "mx-auto flex w-full max-w-6xl flex-col items-center gap-1.5 px-6 pb-10 pt-16",
        "text-center sm:flex-row sm:justify-center sm:gap-3 sm:text-left",
        className,
      )}
    >
      <span className="text-[11.5px] text-faint/80">Version {VERSION}</span>
      <Separator />
      <CreatorSignature variant="footer" />
      <Separator />
      <span className="text-[11.5px] text-faint/80">{FOOTER_NOTE}</span>
    </footer>
  );
}

function Separator() {
  return (
    <span aria-hidden className="hidden text-[11.5px] text-line sm:inline">
      ·
    </span>
  );
}
