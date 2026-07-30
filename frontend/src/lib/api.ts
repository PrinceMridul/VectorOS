/**
 * The API client.
 *
 * One design note worth calling out: `PedagogicalError` is a first-class error
 * type rather than a generic 409. The backend refuses requests that would break
 * a learning invariant — an attempt with no committed confidence, a hint asked
 * for three seconds in — and the UI needs to render those as *the tutor talking*,
 * not as a failure. "Sit with it a little longer" is not an error state.
 */

import type {
  AuthResponse,
  ApiError,
  Dashboard,
  Goal,
  LearningGraph,
  Session,
  StartedGoal,
  TraceEvent,
  TurnRequest,
  TurnResponse,
  UnderstandingShift,
  User,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "vectoros.token";

export class PedagogicalError extends Error {
  constructor(
    message: string,
    readonly detail: ApiError,
  ) {
    super(message);
    this.name = "PedagogicalError";
  }

  /** Seconds until "Request guidance" unlocks, when the struggle floor blocked it. */
  get unlocksIn(): number | null {
    const value = this.detail.unlocks_in_seconds;
    return typeof value === "number" ? value : null;
  }
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
  },
  set(token: string) {
    window.localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    window.localStorage.removeItem(TOKEN_KEY);
  },
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (response.ok) {
    return (await response.json()) as T;
  }

  let detail: ApiError = { code: "unknown", message: response.statusText };
  try {
    const body = (await response.json()) as { error?: ApiError; detail?: unknown };
    if (body.error) detail = body.error;
    else if (typeof body.detail === "string") detail = { code: "error", message: body.detail };
  } catch {
    /* non-JSON error body; the status line is all we have */
  }

  if (response.status === 409) {
    throw new PedagogicalError(detail.message, detail);
  }
  if (response.status === 401) {
    tokenStore.clear();
  }
  throw new ApiRequestError(detail.message, response.status);
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  // -- identity --------------------------------------------------------------
  start: (displayName: string) =>
    post<AuthResponse>("/api/auth/start", { display_name: displayName }),
  me: () => request<User>("/api/auth/me"),

  // -- planning --------------------------------------------------------------
  goals: () => request<Goal[]>("/api/goals"),
  myGoals: () => request<StartedGoal[]>("/api/goals/mine"),
  startGoal: (slug: string, motivation: string) =>
    post<StartedGoal>(`/api/goals/${slug}/start`, { motivation }),

  // -- the graph -------------------------------------------------------------
  graph: (graphId: string) => request<LearningGraph>(`/api/graph/${graphId}`),

  // -- the loop --------------------------------------------------------------
  openSession: (nodeId: string) => post<Session>("/api/sessions", { node_id: nodeId }),
  session: (sessionId: string) => request<Session>(`/api/sessions/${sessionId}`),
  turn: (sessionId: string, payload: TurnRequest) =>
    post<TurnResponse>(`/api/sessions/${sessionId}/turn`, payload),
  unlockInput: (sessionId: string, proof: string) =>
    post<Session>(`/api/sessions/${sessionId}/unlock`, { proof }),
  trace: (sessionId: string) => request<TraceEvent[]>(`/api/sessions/${sessionId}/trace`),
  shift: (sessionId: string) => request<UnderstandingShift>(`/api/sessions/${sessionId}/shift`),

  // -- reflection on the whole record ---------------------------------------
  dashboard: () => request<Dashboard>("/api/dashboard"),
};
