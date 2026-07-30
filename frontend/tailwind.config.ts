import type { Config } from "tailwindcss";

/**
 * The design system, in one place.
 *
 * Colours are declared as CSS variables in `globals.css` and referenced here, so
 * the palette can shift between themes without any component knowing.
 *
 * The `state` scale is not decoration — each colour maps to a mastery state and
 * is used consistently on the graph, the workspace and the dashboard, so a
 * learner can read their own progress by colour alone.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        raised: "rgb(var(--raised) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        faint: "rgb(var(--faint) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        "accent-soft": "rgb(var(--accent-soft) / <alpha-value>)",
        state: {
          locked: "rgb(var(--state-locked) / <alpha-value>)",
          available: "rgb(var(--state-available) / <alpha-value>)",
          progress: "rgb(var(--state-progress) / <alpha-value>)",
          mastered: "rgb(var(--state-mastered) / <alpha-value>)",
          review: "rgb(var(--state-review) / <alpha-value>)",
          alert: "rgb(var(--state-alert) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        lift: "0 1px 0 0 rgb(255 255 255 / 0.04) inset, 0 8px 30px -12px rgb(0 0 0 / 0.6)",
        glow: "0 0 0 1px rgb(var(--accent) / 0.35), 0 0 40px -8px rgb(var(--accent) / 0.45)",
      },
      keyframes: {
        breathe: {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.03)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        breathe: "breathe 3.5s ease-in-out infinite",
        shimmer: "shimmer 2.2s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
