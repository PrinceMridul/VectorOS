"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, Github, Linkedin, Mail, X } from "lucide-react";
import * as React from "react";

import { CREATOR, PROJECT_ORIGIN } from "@/lib/creator";
import { modalIn } from "@/lib/motion";

/**
 * About the Builder.
 *
 * Restraint is the whole brief here. The temptation with a panel like this is to
 * reach for the portfolio vocabulary — avatar, skill meters, badge soup, a wall
 * of logos — and every one of those would make the product look less serious,
 * not more. So: one column, one accent, plain rows, and nothing that competes
 * with the learning surface underneath it.
 *
 * Reuses the existing `modalIn` variant and palette tokens rather than
 * introducing a new visual language for a secondary surface.
 */

const LINK_ICON = {
  github: Github,
  linkedin: Linkedin,
  email: Mail,
} as const;

export function AboutBuilder({ open, onClose }: { open: boolean; onClose: () => void }) {
  const panelRef = React.useRef<HTMLDivElement | null>(null);
  const closeRef = React.useRef<HTMLButtonElement | null>(null);
  const restoreRef = React.useRef<HTMLElement | null>(null);

  // `onClose` is typically an inline arrow from the caller, so a fresh identity
  // arrives on every render. Depending on it directly made this effect tear
  // down and re-run continuously — which unbound the Escape handler and undid
  // the scroll lock a frame after setting it. Hold it in a ref and key the
  // effect purely on `open`.
  const onCloseRef = React.useRef(onClose);
  React.useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // Escape to close, Tab cycles inside the dialog, focus returns to whatever
  // opened it. A modal that strands keyboard focus behind the overlay is worse
  // than no modal.
  React.useEffect(() => {
    if (!open) return;

    restoreRef.current = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => closeRef.current?.focus(), 40);

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;

      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;

      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKey);

    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      restoreRef.current?.focus?.();
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="absolute inset-0 bg-canvas/70 backdrop-blur-sm"
            aria-hidden
          />

          <motion.div
            ref={panelRef}
            variants={modalIn}
            initial="hidden"
            animate="show"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-builder-title"
            className="relative flex max-h-[calc(100vh-3rem)] w-full max-w-[520px] flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-lift"
          >
            <header className="flex items-center justify-between border-b border-line px-6 py-4">
              <h2
                id="about-builder-title"
                className="text-2xs font-medium uppercase tracking-[0.14em] text-faint"
              >
                About the Builder
              </h2>
              <button
                ref={closeRef}
                onClick={onClose}
                aria-label="Close"
                className="-mr-1.5 rounded-md p-1.5 text-faint transition-colors hover:text-ink focus-ring"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="overflow-y-auto px-6 py-6">
              {/* Identity */}
              <h3 className="text-[19px] font-semibold tracking-[-0.01em]">{CREATOR.name}</h3>
              <p className="mt-1.5 text-[12.5px] text-muted">
                {CREATOR.roles.join(" · ")}
              </p>

              {/* The quote. A single accent rule — the only ornament in the panel. */}
              <blockquote className="mt-6 border-l-2 border-accent/50 pl-4">
                {CREATOR.quote.map((line) => (
                  <span key={line} className="block text-[14px] leading-[1.6] text-ink">
                    {line}
                  </span>
                ))}
              </blockquote>

              <p className="mt-5 text-[13.5px] leading-relaxed text-muted">
                {CREATOR.statement}
              </p>

              <p className="mt-5 text-[12.5px] text-faint">
                <span className="text-muted">{CREATOR.education.degree}</span>
                {" · "}
                {CREATOR.education.institution}
              </p>

              {/* Research interests — a wrapped line, not a row of chips. */}
              <section className="mt-7">
                <SectionLabel>Research Interests</SectionLabel>
                <p className="mt-2.5 text-[13px] leading-[1.75] text-muted">
                  {CREATOR.researchInterests.join(" · ")}
                </p>
              </section>

              {/* Projects — vertical, because each is a distinct thing. */}
              <section className="mt-6">
                <SectionLabel>Selected Projects</SectionLabel>
                <ul className="mt-2.5 space-y-2">
                  {CREATOR.projects.map((project) => (
                    <li key={project.name} className="flex items-baseline gap-2.5">
                      <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-accent/70" />
                      <span className="text-[13px] leading-snug text-ink">{project.name}</span>
                      {"note" in project && project.note && (
                        // Sibling rather than nested, so a screen reader reads
                        // "VectorOS — this project" instead of "VectorOSthis".
                        <span className="text-[11.5px] text-faint">— {project.note}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              {/* Links */}
              <section className="mt-7 flex flex-wrap gap-2">
                {CREATOR.links.map((link) => {
                  const Icon = LINK_ICON[link.kind];
                  const external = link.kind !== "email";
                  return (
                    <a
                      key={link.kind}
                      href={link.href}
                      {...(external
                        ? { target: "_blank", rel: "noreferrer noopener" }
                        : {})}
                      className="group inline-flex items-center gap-2 rounded-lg border border-line bg-raised/50 px-3 py-2 text-[12.5px] text-muted transition-colors hover:border-faint hover:text-ink focus-ring"
                    >
                      <Icon className="h-3.5 w-3.5" strokeWidth={1.7} />
                      {link.label}
                      {external && (
                        <ArrowUpRight
                          className="h-3 w-3 text-faint transition-transform duration-200 group-hover:-translate-y-px group-hover:translate-x-px"
                          strokeWidth={1.8}
                        />
                      )}
                    </a>
                  );
                })}
              </section>

              {/* Project origin — deliberately quieter than everything above it. */}
              <div className="mt-7 border-t border-line pt-6">
                <SectionLabel>Project Origin</SectionLabel>
                <p className="mt-2.5 text-[12.5px] leading-relaxed text-faint">
                  {PROJECT_ORIGIN.lead}
                </p>
                <p className="mt-3 text-[13px] leading-relaxed text-muted">
                  {PROJECT_ORIGIN.question}
                </p>
                <p className="mt-3 text-[12.5px] leading-relaxed text-faint">
                  {PROJECT_ORIGIN.body}
                </p>
                <p className="mt-3 text-[12px] leading-relaxed text-faint/80">
                  {PROJECT_ORIGIN.disclaimer}
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-2xs font-medium uppercase tracking-[0.14em] text-faint">{children}</p>
  );
}
