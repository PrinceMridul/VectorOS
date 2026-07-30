/**
 * Creator and project identity.
 *
 * Kept in one place so attribution text appears in exactly one file rather than
 * being scattered across a header, a footer and a modal — three copies of a
 * name is three chances for them to drift.
 */

export const VERSION = "1.0";

export const CREATOR = {
  name: "Prince Mridul",
  /** Rendered as a single line separated by interpuncts, not as three badges. */
  roles: ["AI Engineer", "Machine Learning", "AI Research"],

  /** Two lines by design — the break is the rhythm of the sentence. */
  quote: [
    "I believe AI shouldn't just answer questions.",
    "It should help people build mental models.",
  ],

  statement:
    "I'm interested in building AI systems that don't just generate answers, but help " +
    "people construct durable mental models.",

  education: {
    degree: "B.Tech",
    institution: "Delhi Technological University",
  },

  researchInterests: [
    "AI-native Learning",
    "Trustworthy AI",
    "Learning Systems",
    "Computer Vision",
    "Large Language Models",
  ],

  projects: [
    { name: "VectorOS", note: "this project" },
    { name: "Industrial OCR using YOLOv8 + PARSeq" },
    { name: "LLM Evaluation Framework" },
  ] as const,

  links: [
    { kind: "github", label: "GitHub", href: "https://github.com/PrinceMridul" },
    { kind: "linkedin", label: "LinkedIn", href: "https://www.linkedin.com/in/prince-mridul/" },
    { kind: "email", label: "Email", href: "mailto:princeomania21@gmail.com" },
  ] as const,
} as const;

export const ATTRIBUTION = `Designed & built by ${CREATOR.name}`;

/**
 * The origin note.
 *
 * The disclaimer in the final paragraph is load-bearing, not boilerplate: this
 * project cites Andrew Ng's announcement as its starting point, and saying so
 * without also saying "not affiliated" would let a reader infer an endorsement
 * that does not exist.
 */
export const PROJECT_ORIGIN = {
  lead: "This project began with one question after reading Andrew Ng's LearnVector announcement:",
  question: "Can an AI understand what a learner believes before it starts teaching?",
  body: "VectorOS is an independent exploration of that question.",
  disclaimer:
    "It is inspired by the philosophy behind LearnVector but is not affiliated with " +
    "LearnVector or DeepLearning.AI.",
} as const;

export const FOOTER_NOTE = "Inspired by Andrew Ng's LearnVector announcement.";
