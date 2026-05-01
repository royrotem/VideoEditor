/**
 * Wire-format types mirroring the backend's Pydantic schemas.
 *
 * Kept in this module so every part of the frontend imports from one
 * place; if a backend schema gains a field it lands here and TypeScript
 * surfaces every consumer that needs to react.
 */

export type AssetStatus = "uploaded" | "analyzing" | "ready" | "failed";
export type SessionStatus = "active" | "closed";
export type MessageRole = "user" | "agent" | "system";
export type JobStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type Project = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type Asset = {
  id: string;
  project_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  status: AssetStatus;
  created_at: string;
};

export type AssetCreated = {
  asset: Asset;
  preview_url: string;
  preview_url_ttl_seconds: number;
};

export type PresignedUrl = {
  url: string;
  ttl_seconds: number;
};

export type Session = {
  id: string;
  project_id: string;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  session_id: string;
  role: MessageRole;
  agent_name: string | null;
  content: string;
  created_at: string;
};

export type StartSessionResponse = {
  session: Session;
  user_message: Message;
  assistant_message: Message;
};

export type AssistantReply = {
  user_message: Message;
  assistant_message: Message;
  converged: boolean;
};

// --- BriefPlan + EditDecisionList ---
//
// The frontend treats the EDL as opaque - it ferries the planner's
// output to the render endpoint without inspecting it. We keep the
// shape here as a record so the type-system rejects accidental
// mutations.

export type BriefPlan = {
  title: string;
  intent: string;
  target_duration_seconds: number;
  style_notes: string[];
  music_direction: string | null;
  pacing: "slow" | "medium" | "fast";
};

export type EditDecisionList = Record<string, unknown>;

export type RenderJob = {
  id: string;
  project_id: string;
  edl_version_id: string;
  status: JobStatus;
  output_bucket: string | null;
  output_key: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};
