/**
 * Wire types, mirroring the Pydantic schemas under `backend/app/features`.
 *
 * Note what is absent and must stay absent: `canonical_model`,
 * `expected_reasoning`, `acceptance_criteria`. The grading key never crosses the
 * network, so it cannot be read out of a devtools tab. If a field like that ever
 * appears here, the Socratic guarantee has already been lost.
 */

export type SessionState =
  | "idle"
  | "elicit"
  | "diagnose"
  | "instruct"
  | "challenge"
  | "attempt"
  | "evaluate"
  | "coach"
  | "reflect"
  | "mastery"
  | "complete";

export type NodeStatus = "locked" | "available" | "in_progress" | "review_due" | "mastered";

export type Confidence = "high" | "medium" | "low";

export type Quadrant = "automaticity" | "fragile" | "blind_spot" | "known_gap";

export interface LearnerProfile {
  vocabulary_tier: number;
  unaided_wins: number;
  hinted_wins: number;
  hints_consumed: number;
  offload_attempts: number;
  cognitive_debt: number;
  cognitive_debt_label: string;
  calibration_label: string;
  calibration_error: number;
  pedagogy_notes: string[];
  session_summaries: { at: string; summary: string }[];
}

export interface User {
  id: string;
  display_name: string;
  email: string | null;
  profile: LearnerProfile;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface Goal {
  slug: string;
  title: string;
  description: string;
  estimated_hours: number;
  node_count: number;
  opening_question: string;
}

export interface StartedGoal {
  graph_id: string;
  title: string;
}

export interface GraphNode {
  id: string;
  slug: string;
  title: string;
  one_liner: string;
  difficulty: number;
  bloom_ceiling: string;
  status: NodeStatus;
  mastery: number;
  position: { x: number; y: number };
  blocked_by: string[];
  review_due_at: string | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: "prerequisite" | "related";
}

export interface LearningGraph {
  id: string;
  title: string;
  goal: string;
  description: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  frontier_node_id: string | null;
  mastered_count: number;
  total_count: number;
  overall_mastery: number;
}

export interface MisconceptionView {
  claim: string;
  canonical?: string;
  severity?: string;
}

export interface MentalModel {
  anchors: string[];
  misconceptions: MisconceptionView[];
  missing: string[];
  prior_estimate: number;
  bloom_reached: string;
}

export interface Evaluation {
  correctness: number;
  quadrant: Quadrant;
  quadrant_note: string;
  error_type: string;
  anchors: string[];
  misconceptions: MisconceptionView[];
}

export interface ReflectionResult {
  coverage: number;
  omissions: string[];
  passed: boolean;
  feedback: string;
}

export interface Session {
  id: string;
  graph_id: string;
  node_id: string;
  node_title: string;
  node_one_liner: string;
  state: SessionState;
  message: string;
  challenge_prompt: string | null;
  scaffold_level: number;
  max_scaffold_level: number;
  requires_confidence: boolean;
  guidance_available: boolean;
  struggle_floor_seconds: number;
  mastery: number;
  mastery_before: number;
  predicted_success: number;
  cognitive_load: number;
  load_band: "productive" | "overloaded" | "underloaded";
  turn_count: number;
  offload_attempts: number;
  input_locked: boolean;
  mental_model: MentalModel | null;
  last_evaluation: Evaluation | null;
  reflection: ReflectionResult | null;
  completed: boolean;
}

export interface Transition {
  source: SessionState;
  target: SessionState;
  trigger: string;
}

export interface TurnResponse {
  session: Session;
  transitions: Transition[];
  mastery_delta: number;
  unlocked_nodes: string[];
  guard_verdict: string | null;
  refused: boolean;
}

export interface TurnRequest {
  text?: string;
  confidence?: Confidence | null;
  elapsed_ms?: number;
  request_guidance?: boolean;
}

export interface ResolvedBelief {
  claim: string;
  canonical: string;
  severity: string;
  resolved: boolean;
  clears: number;
  clears_required: number;
}

export interface UnderstandingShift {
  node_title: string;
  node_one_liner: string;
  before_text: string;
  before_at: string;
  after_text: string;
  after_at: string;
  beliefs: ResolvedBelief[];
  anchors_at_start: string[];
  mastery_before: number;
  mastery_after: number;
  prior_estimate: number;
  attempts: number;
  unaided_wins: number;
  hints_used: number;
  answer_demands_refused: number;
  minutes_elapsed: number;
  reflection_coverage: number;
  unlocked_titles: string[];
}

export interface TraceEvent {
  agent: string;
  model: string;
  state_from: string | null;
  state_to: string | null;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  guard_verdict: string | null;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface ConceptProgress {
  node_id: string;
  title: string;
  graph_title: string;
  mastery: number;
  observations: number;
  unaided: number;
  review_due_at: string | null;
  overdue_days: number;
}

export interface Dashboard {
  display_name: string;
  concepts: ConceptProgress[];
  review_queue: ConceptProgress[];
  quadrants: { automaticity: number; fragile: number; blind_spot: number; known_gap: number };
  calibration_label: string;
  calibration_error: number;
  calibration_samples: number;
  cognitive_debt: number;
  cognitive_debt_label: string;
  cognitive_debt_headline: string;
  unaided_wins: number;
  hinted_wins: number;
  offload_attempts: number;
  sessions_completed: number;
  active_weaknesses: {
    claim: string;
    canonical: string;
    severity: string;
    node_title: string;
    evidence_count: number;
    status: string;
  }[];
  resolved_weaknesses: number;
  recent_summaries: { at: string; summary: string }[];
}

export interface ApiError {
  code: string;
  message: string;
  [key: string]: unknown;
}
