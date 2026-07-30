"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Grow with content rather than scrolling inside a fixed box. */
  autoGrow?: boolean;
}

/**
 * The thinking surface.
 *
 * Deliberately not a chat composer: no send-on-Enter, no attachment tray, no
 * placeholder inviting you to "ask anything". Enter makes a new line, because
 * this is a place to write a paragraph of reasoning, and a box that submits when
 * you press Enter teaches you to write one line.
 */
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, autoGrow = true, onChange, ...props }, ref) => {
    const inner = React.useRef<HTMLTextAreaElement | null>(null);

    const resize = React.useCallback(() => {
      const el = inner.current;
      if (!el || !autoGrow) return;
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    }, [autoGrow]);

    React.useEffect(resize, [resize, props.value]);

    return (
      <textarea
        ref={(node) => {
          inner.current = node;
          if (typeof ref === "function") ref(node);
          else if (ref) ref.current = node;
        }}
        onChange={(event) => {
          resize();
          onChange?.(event);
        }}
        className={cn(
          "w-full resize-none rounded-xl border border-line bg-canvas/60 px-4 py-3",
          "text-[15px] leading-relaxed text-ink placeholder:text-faint",
          "transition-colors focus-ring focus-visible:border-accent/50",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";
