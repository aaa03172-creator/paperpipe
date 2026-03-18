export type PaperUiStatus = "not_started" | "processing" | "completed" | "failed";

export type JobLifecycle = "queued" | "running" | "completed" | "failed" | "cancelled";

export type PipelineStage = "ingest" | "index" | "read" | "verify" | "completed";

export type ReasoningPersonaId = "librarian" | "researcher" | "extractor_reviewer";

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
  issues_state?: "flagged" | "clear" | "unavailable";
  latest_job_id?: string;
  latest_run_id?: string;
  updated_at?: string;
  ops_summary?: PaperNoteOpsSummary | null;
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
  shared_signals: string[];
}

export interface PaperNoteReference {
  label: string;
  url: string;
  source: "pdf" | "doi" | "zotero" | "external";
}

export interface PaperNoteContextTraceEntry {
  order: number;
  action: string;
  outcome: "loaded" | "filtered" | "resolved" | "derived" | "missing";
  detail: string;
  source_path?: string | null;
  matched_slugs: string[];
  metadata: Record<string, unknown>;
}

export interface PaperNoteContextTraceSummary {
  entry_count: number;
  source_path_count: number;
  related_count: number;
  reference_count: number;
  action_counts: Record<string, number>;
  outcome_counts: Record<string, number>;
  source_paths: string[];
  related_slugs: string[];
  reference_sources: Array<"pdf" | "doi" | "zotero" | "external" | string>;
}

export interface PaperNoteContextTrace {
  available: boolean;
  summary: PaperNoteContextTraceSummary;
  trace: PaperNoteContextTraceEntry[];
}

export interface SkillActionInfo {
  action: "extract_markdown" | "validate_citations" | "critical_appraisal";
  title: string;
  button_label: string;
  description: string;
  source_skills: string[];
  license?: string | null;
  network: "none" | "allowlist" | "full";
  sandbox?: string | null;
  secrets_required: string[];
  enabled: boolean;
  disabled_reason?: string | null;
}

export interface SkillClaimEvidence {
  id?: string | null;
  claim_id?: string | null;
  run_id?: string | null;
  text: string;
  page?: number | null;
  section?: string | null;
  source?: string | null;
  grounded?: boolean | null;
  resolution?: string | null;
  locator?: EvidenceLocator | null;
}

export interface SkillClaimCard {
  id: string;
  source_claim_id?: string | null;
  run_id?: string | null;
  claim: string;
  evidence_ids: string[];
  evidence: SkillClaimEvidence[];
  confidence?: number | null;
  tags: string[];
  outcomes: string[];
}

export interface SkillRunRecord {
  id: string;
  action: "extract_markdown" | "validate_citations" | "critical_appraisal";
  ts: string;
  status: "succeeded" | "failed" | "blocked";
  summary: string;
  artifacts: Record<string, unknown>;
  data: Record<string, unknown>;
}

export interface StructuredPaperState {
  schema_version: string;
  paper_slug: string;
  updated_at: string;
  runs: SkillRunRecord[];
  signals: Record<string, unknown>;
  claimset: SkillClaimCard[];
  entities: string[];
  mesh: string[];
  outcomes: string[];
}

export type MeetingPackMode =
  | "journal_club"
  | "literature_update"
  | "project_progress_update"
  | "experiment_proposal";

export type OutputModeFamily = "learner" | "lab_meeting" | "project_update" | "builder_debug";

export type MeetingPackStatus = "draft";

export type MeetingPackReadiness = "evidence_backed" | "background_only";

export type MeetingPackMarkdownSyncState = "in_sync" | "drifted";

export type MeetingPackRegenerateStrategy = "saved_request" | "legacy_source_items" | "unavailable";

export type MeetingPackPriority = "low" | "medium" | "high";

export type MeetingPackRetrievalOutcome = "selected" | "deduped" | "resolved" | "loaded";

export interface MeetingPackSourceSelector {
  type: string;
  ref: string;
}

export interface MeetingPackSourceItem {
  id: string;
  type: string;
  ref: string;
  title: string;
  priority: number;
  included: boolean;
}

export interface MeetingPackRetrievalTraceEntry {
  order: number;
  selector_type: string;
  selector_ref: string;
  action: string;
  outcome: MeetingPackRetrievalOutcome;
  detail: string;
  source_item_id?: string | null;
  source_path?: string | null;
  matched_paper_slugs: string[];
  metadata: Record<string, unknown>;
}

export interface MeetingPackRetrievalTraceSummary {
  entry_count: number;
  selector_count: number;
  matched_paper_count: number;
  source_path_count: number;
  action_counts: Record<string, number>;
  outcome_counts: Record<string, number>;
  matched_paper_slugs: string[];
  source_paths: string[];
}

export interface MeetingPackKeyPoint {
  label: string;
  text: string;
  evidence_refs: string[];
  uncertainty_note?: string | null;
}

export interface MeetingPackConsensus {
  label: string;
  summary: string;
  consensus_type: string;
  source_item_ids: string[];
  outlier_source_item_ids: string[];
  evidence_refs: string[];
}

export interface MeetingPackConflict {
  label: string;
  summary: string;
  conflict_type: string;
  source_item_ids: string[];
  evidence_refs: string[];
}

export interface MeetingPackOnePageSummary {
  overview: string;
  key_points: MeetingPackKeyPoint[];
  consensus_points: MeetingPackConsensus[];
  conflicts: MeetingPackConflict[];
  uncertainties: string[];
}

export interface MeetingPackSlide {
  slide_title: string;
  purpose: string;
  bullets: string[];
  evidence_refs: string[];
  caution_notes: string[];
}

export interface MeetingPackSpeakerNote {
  slide_index: number;
  text: string;
  evidence_refs: string[];
}

export interface MeetingPackQuestion {
  question: string;
  rationale: string;
  evidence_refs: string[];
}

export interface MeetingPackExpectedQuestion {
  question: string;
  suggested_response: string;
  evidence_refs: string[];
}

export interface MeetingPackNextStep {
  action: string;
  why: string;
  priority: MeetingPackPriority;
  evidence_refs: string[];
}

export interface MeetingPackEvidenceRef {
  id: string;
  paper_slug: string;
  claim_id?: string | null;
  evidence_id?: string | null;
  run_id?: string | null;
  support_type: string;
  note?: string | null;
}

export interface MeetingPackRequestSnapshot {
  mode: MeetingPackMode;
  title?: string | null;
  source_items: MeetingPackSourceSelector[];
  max_slides: number;
}

export interface MeetingPackMarkdownSync {
  status: MeetingPackMarkdownSyncState;
  stored_markdown_sha1: string;
  rendered_markdown_sha1: string;
  note?: string | null;
}

export interface MeetingPackValidation {
  pack_id: string;
  readiness: MeetingPackReadiness;
  markdown_sync: MeetingPackMarkdownSync;
  can_regenerate: boolean;
  regenerate_strategy: MeetingPackRegenerateStrategy;
  warnings: string[];
}

export interface MeetingPackListItem {
  pack_id: string;
  title: string;
  mode: MeetingPackMode;
  output_mode_family: OutputModeFamily;
  created_at: string;
  readiness: MeetingPackReadiness;
  source_count: number;
  slide_count: number;
  trace_entry_count: number;
  primary_source_title?: string | null;
  has_generation_request: boolean;
  regenerated_from_pack_id?: string | null;
}

export interface MeetingPack {
  id: string;
  mode: MeetingPackMode;
  output_mode_family: OutputModeFamily;
  title: string;
  created_at: string;
  status: MeetingPackStatus;
  readiness: MeetingPackReadiness;
  generation_request?: MeetingPackRequestSnapshot | null;
  regenerated_from_pack_id?: string | null;
  source_items: MeetingPackSourceItem[];
  retrieval_trace: MeetingPackRetrievalTraceEntry[];
  one_page_summary: MeetingPackOnePageSummary;
  slides: MeetingPackSlide[];
  speaker_notes: MeetingPackSpeakerNote[];
  discussion_questions: MeetingPackQuestion[];
  expected_questions: MeetingPackExpectedQuestion[];
  next_steps: MeetingPackNextStep[];
  evidence_refs: MeetingPackEvidenceRef[];
}

export interface MeetingPackResponse {
  pack: MeetingPack;
  markdown?: string | null;
  markdown_sync?: MeetingPackMarkdownSync | null;
}

export interface MeetingPackValidationResponse {
  validation: MeetingPackValidation;
}

export interface MeetingPackTraceResponse {
  pack_id: string;
  available: boolean;
  summary: MeetingPackRetrievalTraceSummary;
  trace: MeetingPackRetrievalTraceEntry[];
}

export interface MeetingPackListResponse {
  generated_at: string;
  total: number;
  items: MeetingPackListItem[];
}

export interface EvidenceLocator {
  page?: number | null;
  span: number[];
  section?: string | null;
  chunk_id?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  bbox_pdf?: number[] | null;
  bbox_pct?: Record<string, number> | null;
  table_id?: string | null;
  cell_id?: string | null;
  source?: string | null;
}

export type MethodComparisonFieldId =
  | "intervention"
  | "comparator"
  | "duration_or_timepoint"
  | "primary_readout"
  | "sample_size";

export type MethodComparisonValueKind = "text" | "numeric" | "duration" | "categorical";

export type MethodComparisonCellStatus = "explicit" | "inferred" | "missing" | "conflict";

export interface MethodComparisonEvidenceRef {
  paper_slug: string;
  claim_id?: string | null;
  evidence_id?: string | null;
  run_id?: string | null;
  locator?: EvidenceLocator | null;
}

export interface MethodComparisonColumn {
  field_id: MethodComparisonFieldId;
  label: string;
  value_kind: MethodComparisonValueKind;
}

export interface MethodComparisonCell {
  field_id: MethodComparisonFieldId;
  value?: string | number | null;
  normalized_value?: string | number | null;
  status: MethodComparisonCellStatus;
  note?: string | null;
  evidence_refs: MethodComparisonEvidenceRef[];
}

export interface MethodComparisonRow {
  paper_id: string;
  paper_slug?: string | null;
  citekey?: string | null;
  title: string;
  cells: MethodComparisonCell[];
}

export interface MethodComparisonSourceSummary {
  source_priority: string[];
  note?: string | null;
  source_paper_count: number;
  note_backed_paper_count: number;
  operator_override_count: number;
}

export interface MethodComparison {
  comparison_id: string;
  title: string;
  created_at: string;
  generated_at?: string | null;
  paper_ids: string[];
  columns: MethodComparisonColumn[];
  rows: MethodComparisonRow[];
  source_summary: MethodComparisonSourceSummary;
  warnings: string[];
}

export interface MethodComparisonResponse {
  comparison: MethodComparison;
  csv_text: string;
  markdown: string;
}

export interface MethodComparisonListItem {
  comparison_id: string;
  title: string;
  created_at: string;
  generated_at?: string | null;
  paper_count: number;
  field_count: number;
  warning_count: number;
}

export interface MethodComparisonListResponse {
  items: MethodComparisonListItem[];
  total: number;
}

export interface PaperNoteDetailResponse {
  note: PaperNoteSummary;
  frontmatter: Record<string, unknown>;
  body_markdown: string;
  related: PaperNoteRelated[];
  references: PaperNoteReference[];
  context_trace?: PaperNoteContextTrace | null;
  structured_state?: StructuredPaperState | null;
  available_actions: SkillActionInfo[];
}

export interface PaperNoteStructuredStateLookupResponse {
  paper_id: string;
  slug: string;
  note_path: string;
  structured_state?: StructuredPaperState | null;
}

export interface SkillRunResponse {
  slug: string;
  note_path: string;
  structured_path: string;
  run: SkillRunRecord;
  state: StructuredPaperState;
  frontmatter_pp: Record<string, unknown>;
}

export interface JobStatus {
  job_id: string;
  paper_id?: string;
  run_id?: string;
  persona_id?: string;
  reasoning_persona?: ReasoningPersonaId | null;
  profile_id?: string | null;
  run_verify?: number | null;
  clean_reindex?: number | null;
  status: JobLifecycle;
  progress: number;
  stage?: string;
  error_message?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  artifact_dir?: string | null;
  log_path?: string | null;
  bootstrap_meta_path?: string | null;
  similar_feedback_count?: number | null;
  persona_applied?: boolean | null;
  artifact_document_written?: boolean | null;
  artifact_index_written?: boolean | null;
  artifact_claimset_written?: boolean | null;
  artifact_claimset_resolved_written?: boolean | null;
  artifact_stats_written?: boolean | null;
  claimset_readiness?: "unknown" | "ready" | "not_ready" | null;
  claimset_ready?: boolean | null;
  claimset_claim_count?: number | null;
  claimset_grounded_span_count?: number | null;
  claimset_unresolved_span_count?: number | null;
  claimset_readiness_reason?: string | null;
  claimset_readiness_badge?: string | null;
  claimset_ops_action?: string | null;
  claimset_ops_alert?: boolean | null;
  claimset_ops_note?: string | null;
}

export interface TimelineEvent {
  event: "log" | "done" | "status" | "error";
  source: "job_log" | "synthetic" | "sse" | "db_event" | "user_action";
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
  evidence_chunk_id?: string | null;
  evidence_grounded?: boolean | null;
  evidence_resolution?: string | null;
  limitations: string[];
}

export interface ObsidianMirrorStatCheck {
  check_id: string;
  test_type: string;
  verdict: string;
  claim_id?: string | null;
  evidence_page?: number | null;
  evidence_chunk_id?: string | null;
  evidence_grounded?: boolean | null;
  evidence_resolution?: string | null;
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
  kind: "compatibility" | "reasoning_persona" | "profile";
  source: "builtin" | "yaml";
  notes?: string;
  schedule?: string;
  query_focus?: string;
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
