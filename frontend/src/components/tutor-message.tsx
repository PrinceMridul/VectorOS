"use client";

import { motion } from "framer-motion";
import * as React from "react";

import { tutorMessage } from "@/lib/motion";
import { cn, paragraphs, renderInline } from "@/lib/utils";

/**
 * The tutor speaking.
 *
 * Not a chat bubble — there is no avatar, no timestamp, no "assistant" label,
 * and no message history stacking beneath it. There is one message, it is the
 * current one, and it reads as prose on the page. Bubbles imply a transcript you
 * can scroll back through and mine for answers; this implies a person who has
 * just said something to you.
 */
export function TutorMessage({
  text,
  className,
  tone = "default",
}: {
  text: string;
  className?: string;
  tone?: "default" | "refusal" | "coach";
}) {
  const blocks = React.useMemo(() => paragraphs(text), [text]);

  return (
    <motion.div
      key={text}
      variants={tutorMessage}
      initial="hidden"
      animate="show"
      exit="exit"
      className={cn(
        "prose-tutor",
        tone === "refusal" && "text-ink",
        tone === "coach" && "text-ink",
        className,
      )}
    >
      {blocks.map((block, index) => (
        <p key={index} className={index > 0 ? "mt-4" : undefined}>
          {renderInline(block).map((part, i) =>
            part.bold ? (
              <strong key={i}>{part.text}</strong>
            ) : (
              <React.Fragment key={i}>{part.text}</React.Fragment>
            ),
          )}
        </p>
      ))}
    </motion.div>
  );
}
