/* Typed client for the SpeakFill API. All calls are same-origin (Caddy routes /api/*). */

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(`API ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = null;
      }
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

/* ---------------- types (mirror the backend shapes) ---------------- */

export interface TemplateSummary {
  id: string;
  name: Record<string, string>;
  version: number;
  field_count: number;
}

export interface FieldOption {
  key: string;
  label: string;
}

export interface CurrentField {
  key: string;
  ord: number;
  type: string;
  required: boolean;
  prompt_text: string;
  prompt_hint: string;
  options: FieldOption[] | null;
}

export interface NewSession {
  session_id: string;
  template_id: string;
  template_version: number;
  language: string;
  status: string;
  current_field: CurrentField;
  total_fields: number;
}

export interface AnswerState {
  key: string;
  ord: number;
  confirmed: boolean;
  pending: boolean;
  value: unknown;
  source: string | null;
}

export interface SessionState {
  session_id: string;
  template_id: string;
  template_version: number;
  language: string;
  status: string;
  blocked: boolean;
  current_ord: number;
  current_field: CurrentField | null;
  answers: AnswerState[];
}

export interface AnswerResult {
  transcript: string;
  value: unknown;
  readable: string;
  confidence: number;
  needs_clarify: boolean;
  clarify_reason: string | null;
  attempt: number;
  max_attempts: number;
  typed_nudge: boolean;
  next_prompt: string;
  prompt_audio_url: string | null;
  audio_error?: string;
}

export interface ConfirmResult {
  accepted: boolean;
  status: string;
  blocked?: boolean;
  message?: string;
  current_field?: CurrentField;
  attempt_next?: number;
  next_prompt?: string;
  prompt_audio_url?: string | null;
}

export interface JobResult {
  job_id: string;
  session_id: string;
  kind: string;
  status: string;
  result: { fields: unknown[]; unknown: unknown[]; next_ord: number } | null;
  error: string | null;
}

export interface ReviewField {
  key: string;
  ord: number;
  label: string;
  type: string;
  value: unknown;
  readable: string | null;
  source: string | null;
  confirmed: boolean;
}

export interface Review {
  session_id: string;
  template: { id: string; name: Record<string, string>; version: number };
  language: string;
  status: string;
  blocked: boolean;
  block_reasons: string[];
  fields: ReviewField[];
  readback_script: string;
  readback_audio_url: string | null;
  audio_error?: string;
  can_export: boolean;
}

export interface ExportResult {
  submission_id: string;
  pdf_url: string;
  share_text: string;
}

/* ---------------- calls ---------------- */

export const api = {
  templates: () => req<TemplateSummary[]>("/api/templates"),

  createSession: (template_id: string, language: string) =>
    req<NewSession>("/api/sessions", json({ template_id, language })),

  getSession: (id: string) => req<SessionState>(`/api/sessions/${id}`),

  answerText: (id: string, text: string) =>
    req<AnswerResult>(`/api/sessions/${id}/answer`, json({ text })),

  answerAudio: (id: string, blob: Blob) => {
    const form = new FormData();
    form.append("audio", blob, "clip.webm");
    return req<AnswerResult>(`/api/sessions/${id}/answer`, { method: "POST", body: form });
  },

  confirm: (id: string, accepted: boolean) =>
    req<ConfirmResult>(`/api/sessions/${id}/confirm`, json({ accepted })),

  confirmAudio: (id: string, blob: Blob) => {
    const form = new FormData();
    form.append("audio", blob, "clip.webm");
    return req<ConfirmResult>(`/api/sessions/${id}/confirm`, { method: "POST", body: form });
  },

  goto: (id: string, ord: number) =>
    req<{ session_id: string; status: string; current_field: CurrentField }>(
      `/api/sessions/${id}/goto`,
      json({ ord })
    ),

  restart: (id: string) =>
    req<{ session_id: string; status: string; current_field: CurrentField }>(
      `/api/sessions/${id}/restart`,
      json({})
    ),

  promptAudio: (templateId: string, ord: number, language: string) =>
    req<{ audio_url: string; text: string }>(
      `/api/audio/prompt/${templateId}/${ord}?language=${language}`
    ),

  uploadPhoto: (id: string, file: Blob) => {
    const form = new FormData();
    form.append("photo", file, "form.png");
    return req<{ job_id: string; status: string }>(`/api/sessions/${id}/photo`, {
      method: "POST",
      body: form,
    });
  },

  getJob: (jobId: string) => req<JobResult>(`/api/jobs/${jobId}`),

  getReview: (id: string) => req<Review>(`/api/sessions/${id}/review`),

  exportSession: (id: string) => req<ExportResult>(`/api/sessions/${id}/export`, json({})),

  submitFeedback: (session_id: string, country: string, rating: number, comment?: string) =>
    req<{ id: number; session_id: string }>(
      "/api/feedback",
      json({ session_id, country, rating, comment: comment || null })
    ),
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail as Record<string, unknown> | null;
    if (d && typeof d === "object") {
      if (typeof d.message === "string") return d.message;
      if (typeof d.detail === "string") return d.detail;
    }
    return `Request failed (${e.status})`;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}
