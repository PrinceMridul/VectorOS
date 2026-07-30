"use client";

import { motion } from "framer-motion";
import { GitBranch, LineChart } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { CreatorSignature } from "@/components/creator-signature";
import { cn } from "@/lib/utils";
import { useLearner } from "@/stores/learner";

/**
 * The chrome. Deliberately almost nothing: a mark, two destinations, and the
 * learner's name. Navigation competing for attention with a concept you are
 * trying to hold in working memory is a real cost, not a stylistic preference.
 */
export function AppShell({
  children,
  right,
}: {
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  const pathname = usePathname();
  const user = useLearner((s) => s.user);
  const graphId = useLearner((s) => s.activeGraphId);

  const links = [
    {
      href: graphId ? `/graph/${graphId}` : "/start",
      label: "Graph",
      icon: GitBranch,
      match: "/graph",
    },
    { href: "/progress", label: "Progress", icon: LineChart, match: "/progress" },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      {/* The workspace puts a nav and a state rail before the thinking surface.
          Keyboard users should not have to tab through them every turn. */}
      <a
        href="#work"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-[13px] focus:text-white"
      >
        Skip to your work
      </a>

      <header className="sticky top-0 z-40 border-b border-line bg-canvas/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-6 px-5">
          <Link href="/" className="flex items-center gap-2.5 focus-ring rounded-md">
            <svg width="15" height="15" viewBox="0 0 14 14" fill="none" aria-hidden>
              <path
                d="M1.5 2.5 L7 11.5 L12.5 2.5"
                stroke="rgb(var(--accent))"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span className="text-[14px] font-medium tracking-tight">VectorOS</span>
          </Link>

          <nav className="flex items-center gap-1">
            {links.map(({ href, label, icon: Icon, match }) => {
              const active = pathname.startsWith(match);
              return (
                <Link
                  key={label}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors focus-ring",
                    active ? "text-ink" : "text-faint hover:text-muted",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" strokeWidth={1.7} />
                  {label}
                  {active && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-x-1 -bottom-[9px] h-px bg-accent"
                      transition={{ type: "spring", stiffness: 400, damping: 34 }}
                    />
                  )}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-4">
            {right}
            {/* Attribution lives in existing chrome rather than floating over
                the canvas — see CreatorSignature for why. Hidden below `md` so
                it never competes with the nav on a phone. */}
            <div className="hidden md:block">
              <CreatorSignature />
            </div>
            {user && (
              <span className="hidden text-[13px] text-faint sm:block">{user.display_name}</span>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1">{children}</div>
    </div>
  );
}
