export type PaperUiStatus = "not_started" | "processing" | "completed" | "failed";

export type JobLifecycle = "queued" | "running" | "completed" | "failed" | "cancelled";

export type PipelineStage = "ingest" | "index" | "read" | "verify" | "completed";

export interface PaperSummary {
  paper_id: string;
  title: string;
  authors?: string;
  year?: number;
  pdf_exists?: boolean;
  pdf_path?: string;
  status?: PaperUiStatus;
  issues?: number;
  issues_label?: string;
  latest_job_id?: string;
  latest_run_id?: string;
  updated_at?: string;
}

export interface PaperDetail extends PaperSummary {
  abstract?: string;
}

export interface JobStatus {
  job_id: string;
  paper_id?: string;
  run_id?: string;
  persona_id?: string;
  status: JobLifecycle;
  progress: number;
  stage?: string;
  error_message?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface TimelineEvent {
  event: "log" | "done" | "status" | "error";
  source: "job_log" | "synthetic" | "sse";
  ts?: string;
  stage?: string;
  progress?: number;
  level?: string;
  message?: string;
  raw?: string;
}

export interface TimelineResponse {
  run_id: string;
  job_id?: string;
  paper_id?: string;
  events: TimelineEvent[];
}

export interface ArtifactFileEntry {
  exists: boolean;
  path?: string | null;
  data?: unknown;
}

export interface ArtifactBundle {
  paper_id: string;
  run_id: string;
  files: Record<string, ArtifactFileEntry>;
}

export interface PersonaOption {
  id: string;
  title: string;
  enabled: boolean;
  source: "builtin" | "yaml";
  notes?: string;
}

export interface PersonaListResponse {
  personas: PersonaOption[];
}

export interface JobEnqueueResponse {
  job_id: string;
  run_id?: string | null;
  status: "queued";
}

export interface EvidenceHighlight {
  claim_id: string;
  page: number;
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface NotebookClaim {
  claim_id: string;
  text: string;
  confidence: "low" | "medium" | "high";
}

export interface NotebookArtifact {
  claims: NotebookClaim[];
  highlights: EvidenceHighlight[];
  agent_plan: string[];
  sandbox_code: string;
  verdict: {
    label: string;
    detail: string;
    level: "pass" | "caution" | "fail";
  };
}

export interface ApiResult<T> {
  data: T;
  isMock: boolean;
  reason?: string;
}
