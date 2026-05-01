/**
 * Typed HTTP client for the AI Video Editor backend.
 *
 * All requests go through `/api/*`, which `next.config.mjs` rewrites
 * to the backend host. That keeps CORS out of the way in development
 * and lets a deployed frontend share an origin with the API.
 *
 * Functions in this module are thin: they parse JSON or throw an
 * `ApiError` carrying the backend's error envelope. Pages compose
 * them; nothing here owns React state or rendering.
 */

import type {
  Asset,
  AssetCreated,
  Message,
  PresignedUrl,
  Project,
  RenderJob,
  Session,
  StartSessionResponse,
  AssistantReply,
  BriefPlan,
  EditDecisionList,
} from "./types";

/** Error thrown when the backend responds with `{ error: { code, message } }`. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
};

/**
 * Low-level fetch wrapper used by every endpoint in this module.
 *
 * Three responsibilities only: prepend `/api`, JSON-encode/decode,
 * translate the backend's structured error body into an
 * {@link ApiError}. Anything endpoint-specific (path templating,
 * payload shape) belongs to the wrappers below.
 */
async function request<T>(
  path: string,
  { method = "GET", body, formData, signal }: RequestOptions = {},
): Promise<T> {
  const headers: HeadersInit = {};
  let payload: BodyInit | undefined;

  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    headers["content-type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: payload,
    signal,
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as
      | { error?: { code?: string; message?: string } }
      | null;
    const code = errorBody?.error?.code ?? "http_error";
    const message = errorBody?.error?.message ?? response.statusText;
    throw new ApiError(response.status, code, message);
  }

  // 204 No Content: nothing to parse.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Projects -------------------------------------------------------------

export const projectsApi = {
  list: (signal?: AbortSignal) =>
    request<Project[]>("/projects", { signal }),
  get: (id: string, signal?: AbortSignal) =>
    request<Project>(`/projects/${id}`, { signal }),
  create: (input: { name: string; description?: string | null }) =>
    request<Project>("/projects", { method: "POST", body: input }),
};

// --- Assets ---------------------------------------------------------------

export const assetsApi = {
  list: (projectId: string, signal?: AbortSignal) =>
    request<Asset[]>(`/projects/${projectId}/assets`, { signal }),
  upload: (projectId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<AssetCreated>(`/projects/${projectId}/assets`, {
      method: "POST",
      formData: fd,
    });
  },
  reanalyze: (projectId: string, assetId: string) =>
    request<Asset>(`/projects/${projectId}/assets/${assetId}/analyze`, {
      method: "POST",
    }),
  presignedUrl: (
    projectId: string,
    assetId: string,
    ttlSeconds = 3600,
    signal?: AbortSignal,
  ) =>
    request<PresignedUrl>(
      `/projects/${projectId}/assets/${assetId}/url?ttl_seconds=${ttlSeconds}`,
      { signal },
    ),
};

// --- Sessions / chat ------------------------------------------------------

export const sessionsApi = {
  start: (projectId: string, brief: string) =>
    request<StartSessionResponse>(`/projects/${projectId}/sessions`, {
      method: "POST",
      body: { brief },
    }),
  list: (projectId: string, signal?: AbortSignal) =>
    request<Session[]>(`/projects/${projectId}/sessions`, { signal }),
  messages: (sessionId: string, signal?: AbortSignal) =>
    request<Message[]>(`/sessions/${sessionId}/messages`, { signal }),
  send: (sessionId: string, content: string) =>
    request<AssistantReply>(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: { content },
    }),
  extractBrief: (sessionId: string) =>
    request<BriefPlan>(`/sessions/${sessionId}/extract-brief`, {
      method: "POST",
    }),
};

// --- Planning -------------------------------------------------------------

export const planningApi = {
  /** Turn a BriefPlan into an EDL via the Editing Planner agent. */
  planEdit: (
    projectId: string,
    brief: BriefPlan,
    previousEdl?: EditDecisionList | null,
  ) =>
    request<EditDecisionList>(`/projects/${projectId}/plan-edit`, {
      method: "POST",
      body: { brief, previous_edl: previousEdl ?? null },
    }),
};

// --- Render ---------------------------------------------------------------

export const renderApi = {
  submit: (
    projectId: string,
    edl: EditDecisionList,
    sessionId?: string | null,
  ) =>
    request<RenderJob>(`/projects/${projectId}/render`, {
      method: "POST",
      body: { edl, session_id: sessionId ?? null },
    }),
  list: (projectId: string, signal?: AbortSignal) =>
    request<RenderJob[]>(`/projects/${projectId}/render-jobs`, { signal }),
  get: (jobId: string, signal?: AbortSignal) =>
    request<RenderJob>(`/render-jobs/${jobId}`, { signal }),
  outputUrl: (jobId: string, ttlSeconds = 3600, signal?: AbortSignal) =>
    request<PresignedUrl>(
      `/render-jobs/${jobId}/output-url?ttl_seconds=${ttlSeconds}`,
      { signal },
    ),
};

// Exposed for unit tests that want to exercise the wrapper directly.
export const __internal = { request };
