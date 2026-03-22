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

export interface PaperNoteSummary {
  slug: string;
  title: string;
  note_path: string;
  id?: string | null;
  aliases: string[];
  tags: string[];
  date_processed?: string | null;
  confidence?: number | null;
  status?: string | null;
  doi?: string | null;
  zotero_link?: string | null;
  updated_at?: string | null;
  pp_signals?: Record<string, unknown>;
  claim_tags?: string[];
  entities?: string[];
  mesh?: string[];
  outcomes?: string[];
  ops_summary?: PaperNoteOpsSummary | null;
}

export interface PaperNoteOpsSummary {
  state: "healthy" | "action_needed";
  label: string;
  reason: string;
  recommended_action: "none" | "repair_stats" | "open_workbench";
  latest_run_id?: string | null;
  has_claimset: boolean;
  has_stats_report: boolean;
  stats_check_count: number;
}

export interface PaperNoteListResponse {
  generated_at: string;
  index_path: string;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  available_tags: string[];
  available_statuses: string[];
  items: PaperNoteSummary[];
}

export interface PaperNoteRelated {
  slug: string;
  title: string;
  shared_tags: string[];
}

export interface PaperNoteReference {
  label: string;
  url: string;
  source: "pdf" | "doi" | "zotero" | "external";
}

export interface PaperNoteDetailResponse {
  note: PaperNoteSummary;
  frontmatter: Record<string, unknown>;
  body_markdown: string;
  related: PaperNoteRelated[];
  references: PaperNoteReference[];
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

export interface ObsidianMirrorClaim {
  claim_id: string;
  claim_type: string;
  statement: string;
  confidence: number;
  evidence_quote?: string | null;
  evidence_page?: number | null;
  limitations: string[];
}

export interface ObsidianMirrorStatCheck {
  check_id: string;
  test_type: string;
  verdict: string;
  claim_id?: string | null;
  evidence_page?: number | null;
  hypothesis?: string | null;
  notes?: string | null;
  decision_error: boolean;
}

export interface ObsidianMirror {
  paper_id: string;
  run_id: string;
  generated_markdown: string;
  has_claimset: boolean;
  has_stats_report: boolean;
  claims: ObsidianMirrorClaim[];
  stats_checks: ObsidianMirrorStatCheck[];
}

export interface ObsidianSyncResponse {
  status: string;
  file?: string | null;
  message?: string;
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

export interface StatsRepairResult {
  paper_id: string;
  run_id?: string | null;
  status: "seeded" | "planned" | "skipped";
  checks: number;
  reason: string;
}

export interface StatsRepairResponse {
  seeded: number;
  planned: number;
  skipped: number;
  total: number;
  results: StatsRepairResult[];
}

export interface EvidenceHighlight {
  claim_id: string;
  page: number;
  top: number;
  left: number;
  width: number;
  height: number;
  quote?: string;
  source?: "bbox" | "text_match" | "approx";
}

export interface NotebookClaim {
  claim_id: string;
  text: string;
  confidence: "low" | "medium" | "high";
  text_missing?: boolean;
  link_health?: "mapped" | "search_fallback" | "missing";
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
