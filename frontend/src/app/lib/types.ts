export type PaperUiStatus = "not_started" | "processing" | "completed" | "failed";

export type JobLifecycle = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface JobCancelResponse {
  status: "cancelled";
}

export interface RuntimeReadinessCheck {
  name: string;
  status: "ok" | "warn" | "error";
  detail: string;
  path?: string | null;
}

export interface RuntimeReadinessResponse {
  status: "ok" | "degraded" | "error";
  checks: RuntimeReadinessCheck[];
}

export type RuntimeLLMMode = "local" | "cloud" | "hybrid";
export type RuntimeLLMProvider = "openai" | "anthropic" | "gemini";
export type RuntimeLLMApiKeySource = "none" | "config" | "env";
export type RuntimeLLMConnectionTestStatus = "ok" | "failed";

export interface RuntimeLLMSettingsResponse {
  mode: RuntimeLLMMode;
  provider: RuntimeLLMProvider;
  model: string;
  embedding_model?: string | null;
  api_key_configured: boolean;
  api_key_source: RuntimeLLMApiKeySource;
  api_key_masked?: string | null;
  provider_env_var: string;
  config_path: string;
  env_override_active: boolean;
}

export interface RuntimeLLMSettingsUpdateRequest {
  mode?: RuntimeLLMMode;
  provider?: RuntimeLLMProvider;
  model?: string | null;
  embedding_model?: string | null;
  api_key?: string | null;
  clear_api_key?: boolean;
}

export interface RuntimeLLMConnectionTestResponse {
  status: RuntimeLLMConnectionTestStatus;
  mode: RuntimeLLMMode;
  provider: RuntimeLLMProvider;
  model: string;
  api_key_source: RuntimeLLMApiKeySource;
  provider_env_var: string;
  latency_ms?: number | null;
  detail: string;
}

export type PipelineStage = "ingest" | "index" | "read" | "verify" | "completed";

export type ReasoningPersonaId = "librarian" | "researcher" | "extractor_reviewer";
export type PaperAccessStatusLabel = "open" | "institution_required" | "user_imported_pdf" | "unavailable";

export interface PaperAccessSummary {
  status_label: PaperAccessStatusLabel;
  open_access_url?: string | null;
  institution_access_url?: string | null;
  local_pdf_url?: string | null;
}

export interface PaperSummary {
  paper_id: string;
  note_slug?: string | null;
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
  access_summary?: PaperAccessSummary | null;
}

export interface PaperDetail extends PaperSummary {
  abstract?: string;
}

export interface PaperNoteSummary {
  slug: string;
  title: string;
  note_path: string;
  structured_state_present?: boolean;
  reading_assist_available?: boolean;
  reading_assist_locales?: string[];
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
  starred?: boolean;
  has_operator_note?: boolean;
  triage_labels?: PaperNoteOperatorTriageLabel[];
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
  available_reading_assist_note_count: number;
  available_reading_assist_locales: string[];
  items: PaperNoteSummary[];
}

export type CloudPaperPayloadClass = "local_only" | "lab_allowed" | "external_allowed";
export type CloudPaperProcessingStatus = "pending" | "running" | "ready" | "failed" | "blocked";
export type CloudPaperRole = "lab_admin" | "maintainer" | "reviewer" | "reader";
export type CloudPaperAction =
  | "read_page"
  | "read_pdf"
  | "hydrate_download"
  | "run_optional_ai"
  | "export"
  | "share"
  | "upload"
  | "delete";
export type CloudPaperHydrationStatus = "not_hydrated" | "hydrated" | "stale" | "failed" | "blocked";

export interface CloudPaperWarning {
  code: string;
  message: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
}

export interface CloudPaperPermissions {
  role: CloudPaperRole;
  can_read_page: boolean;
  can_read_pdf: boolean;
  can_hydrate: boolean;
  can_upload: boolean;
  can_delete: boolean;
  can_run_optional_ai: boolean;
  can_export: boolean;
  can_share: boolean;
}

export interface CloudPaperProvenanceSummary {
  uploaded_by: string;
  processor_name: string;
  processor_version: string;
  created_at: string;
  source_pdf_sha256: string;
}

export interface CloudPaperHydrationState {
  status: CloudPaperHydrationStatus;
  device_id?: string | null;
  local_bundle_ref?: string | null;
  hydrated_at?: string | null;
  source_pdf_sha256?: string | null;
  page_artifact_sha256?: string | null;
}

export interface CloudPaperBundlePublic {
  schema_version: "cloud_paper_bundle_public.v1";
  paper_id: string;
  lab_id: string;
  processing_status: CloudPaperProcessingStatus;
  payload_class: CloudPaperPayloadClass;
  page_schema_version?: string | null;
  run_id?: string | null;
  warnings: CloudPaperWarning[];
  permissions: CloudPaperPermissions;
  provenance_summary: CloudPaperProvenanceSummary;
  local_hydration?: CloudPaperHydrationState | null;
  allowed_actions: CloudPaperAction[];
}

export interface CloudPaperListResponse {
  schema_version: "cloud_paper_list.v1";
  items: CloudPaperBundlePublic[];
}

export type CloudPaperAuthPreflightStatus =
  | "ready"
  | "mock_mode"
  | "submission_bundle"
  | "misconfigured"
  | "dependency_missing"
  | "auth_missing"
  | "permission_denied"
  | "unavailable";
export type CloudPaperAuthPreflightCheckStatus = "ok" | "warning" | "error" | "skipped";

export interface CloudPaperAuthPreflightCheck {
  check_id: string;
  label: string;
  status: CloudPaperAuthPreflightCheckStatus;
  message: string;
  remediation?: string | null;
}

export interface CloudPaperAuthPreflightResponse {
  schema_version: "cloud_paper_auth_preflight.v1";
  status: CloudPaperAuthPreflightStatus;
  adapter: "mock" | "gcs";
  project_id?: string | null;
  firestore_collection?: string | null;
  credential_source: string;
  checks: CloudPaperAuthPreflightCheck[];
  next_action_label: string;
  setup_commands: string[];
}

export interface CloudPaperUploadIntentResponse {
  upload_intent_id: string;
  paper_id: string;
  upload_mode: "mock" | "backend_mediated" | "signed_url";
  expires_at: string;
}

export interface CloudPaperSourceUploadResponse {
  paper_id: string;
  upload_status: "upload_received";
  source_pdf_sha256: string;
  source_pdf_size_bytes: number;
  content_type: "application/pdf";
}

export interface CloudPaperSearchBlockHit {
  block_id: string;
  page: number;
  kind: "text" | "table" | "figure";
  text_snippet: string;
  payload_class: CloudPaperPayloadClass;
  metadata: Record<string, unknown>;
}

export interface CloudPaperSearchHit {
  bundle: CloudPaperBundlePublic;
  matched_blocks: CloudPaperSearchBlockHit[];
}

export interface CloudPaperSearchResponse {
  schema_version: "cloud_paper_search.v1";
  query: string;
  items: CloudPaperSearchHit[];
}

export interface CloudPaperPageBlock {
  block_id: string;
  page: number;
  kind: "text" | "table" | "figure";
  text?: string | null;
  bbox_pct?: Record<string, number> | null;
  payload_class: CloudPaperPayloadClass;
  metadata: Record<string, unknown>;
}

export interface CloudPaperPageArtifactPublic {
  schema_version: "cloud_page_artifact_public.v1";
  paper_id: string;
  run_id: string;
  page_schema_version: string;
  source_pdf_sha256: string;
  blocks: CloudPaperPageBlock[];
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperDerivedArtifactSourceLocator {
  page: number;
  source_pdf_sha256: string;
  block_id?: string | null;
  bbox_pct?: Record<string, number> | null;
}

export interface CloudPaperDerivedArtifactOcrBlock {
  ocr_block_id: string;
  text: string;
  confidence: number;
  source: CloudPaperDerivedArtifactSourceLocator;
  payload_class: CloudPaperPayloadClass;
  metadata: Record<string, unknown>;
}

export interface CloudPaperDerivedArtifactTable {
  table_id: string;
  page: number;
  caption?: string | null;
  columns: string[];
  rows: string[][];
  confidence: number;
  source: CloudPaperDerivedArtifactSourceLocator;
  payload_class: CloudPaperPayloadClass;
  metadata: Record<string, unknown>;
}

export interface CloudPaperDerivedArtifactFigure {
  figure_id: string;
  page: number;
  caption?: string | null;
  bbox_pct?: Record<string, number> | null;
  image_available: boolean;
  image_route?: string | null;
  confidence: number;
  source: CloudPaperDerivedArtifactSourceLocator;
  payload_class: CloudPaperPayloadClass;
  metadata: Record<string, unknown>;
}

export interface CloudPaperDerivedArtifactFigureAnalysis {
  analysis_id: string;
  figure_id: string;
  page: number;
  summary: string;
  confidence: number;
  source: CloudPaperDerivedArtifactSourceLocator;
  payload_class: CloudPaperPayloadClass;
  metadata: Record<string, unknown>;
}

export interface CloudPaperDerivedArtifactsResponse {
  schema_version: "cloud_paper_derived_artifacts.v1";
  paper_id: string;
  run_id: string;
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  ocr_blocks: CloudPaperDerivedArtifactOcrBlock[];
  tables: CloudPaperDerivedArtifactTable[];
  figures: CloudPaperDerivedArtifactFigure[];
  figure_analyses: CloudPaperDerivedArtifactFigureAnalysis[];
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperDownstreamArtifactCandidate {
  candidate_id: string;
  kind: "ocr_text" | "table" | "figure" | "figure_analysis";
  paper_id: string;
  run_id: string;
  payload_class: CloudPaperPayloadClass;
  canonical_status: "derived_noncanonical";
  allowed_lanes: Array<"meeting_pack" | "chart_pack" | "image_evidence" | "method_comparison" | "obsidian_export">;
  source: CloudPaperDerivedArtifactSourceLocator;
  title: string;
  text?: string | null;
  table_columns: string[];
  table_rows: string[][];
  image_route?: string | null;
  confidence?: number | null;
  provenance_summary: CloudPaperProvenanceSummary;
}

export type CloudPaperDownstreamLane =
  | "meeting_pack"
  | "chart_pack"
  | "image_evidence"
  | "method_comparison"
  | "obsidian_export";
export type CloudPaperDownstreamReviewStatus = "review_pending" | "review_approved" | "review_rejected";

export interface CloudPaperDownstreamAdapterResponse {
  schema_version: "cloud_paper_downstream_adapter.v1";
  paper_id: string;
  run_id: string;
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  candidates: CloudPaperDownstreamArtifactCandidate[];
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperDownstreamHandoffSummary {
  downstream_adapter: CloudPaperDownstreamAdapterResponse;
  selected_table_candidate?: CloudPaperDownstreamArtifactCandidate | null;
  selected_figure_candidate?: CloudPaperDownstreamArtifactCandidate | null;
  meeting_pack_context: {
    schema_version: "meeting_pack_cloud_derived_context.v1";
    readiness: "background_only";
    items: Array<{ support_type: "background"; canonical_status: "derived_noncanonical"; evidence_refs: string[] }>;
  };
  chart_table_snapshot: {
    source_ref: { source_kind: "cloud_derived_table"; table_id?: string | null };
    rows: Array<Record<string, string | number | boolean | null>>;
    warnings: Array<{ code: string; message: string; severity?: string }>;
  } | null;
  image_evidence_request: {
    source_ref: { source_kind: "external_image_ref"; external_ref?: string | null; local_path?: string | null };
    linked_claim_refs: unknown[];
    warnings: Array<{ code: string; message: string; severity?: string }>;
  } | null;
  method_comparison_context: {
    schema_version: "method_comparison_cloud_derived_context.v1";
    readiness: "background_only";
    items: Array<{ comparison_cell_status: "missing"; canonical_status: "derived_noncanonical"; evidence_refs: unknown[] }>;
  };
  obsidian_section_markdown: string;
}

export interface CloudPaperObsidianExportResponse {
  schema_version: "cloud_paper_obsidian_export.v1";
  paper_id: string;
  run_id: string;
  artifact_id: string;
  export_status: "prepared";
  canonical_status: "derived_noncanonical";
  review_status: "review_pending";
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  section_markers: {
    start: string;
    end: string;
  };
  section_markdown: string;
  note_markdown: string;
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperRegisteredDownstreamArtifact {
  artifact_id: string;
  lane: CloudPaperDownstreamLane;
  candidate_ids: string[];
  candidate_count: number;
  canonical_status: "derived_noncanonical";
  review_status: CloudPaperDownstreamReviewStatus;
  review_events: Array<{
    event_id: string;
    artifact_id: string;
    review_status: Exclude<CloudPaperDownstreamReviewStatus, "review_pending">;
    reviewer_role: "lab_admin" | "maintainer" | "reviewer" | "reader";
    reviewed_at: string;
    reviewer_note_recorded: boolean;
  }>;
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
}

export interface CloudPaperDownstreamArtifactRegistrationResponse {
  schema_version: "cloud_paper_downstream_artifact_registration.v1";
  paper_id: string;
  run_id: string;
  registration_status: "registered";
  canonical_status: "derived_noncanonical";
  review_status: CloudPaperDownstreamReviewStatus;
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  registered_artifacts: CloudPaperRegisteredDownstreamArtifact[];
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperDownstreamArtifactRegistryResponse {
  schema_version: "cloud_paper_downstream_artifact_registry.v1";
  paper_id: string;
  run_id: string;
  registry_status: "empty" | "available";
  canonical_status: "derived_noncanonical";
  review_status: CloudPaperDownstreamReviewStatus;
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  registrations: CloudPaperDownstreamArtifactRegistrationResponse[];
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperDownstreamPromotionBlocker {
  code: "registry_empty" | "review_pending" | "review_rejected";
  message: string;
  artifact_id?: string | null;
  lane?: CloudPaperDownstreamLane | null;
}

export interface CloudPaperDownstreamPromotionReadinessResponse {
  schema_version: "cloud_paper_downstream_promotion_readiness.v1";
  paper_id: string;
  run_id: string;
  promotion_status: "eligible" | "blocked";
  eligible: boolean;
  canonical_status: "derived_noncanonical";
  review_status: CloudPaperDownstreamReviewStatus;
  total_artifact_count: number;
  approved_artifact_count: number;
  pending_artifact_count: number;
  rejected_artifact_count: number;
  blockers: CloudPaperDownstreamPromotionBlocker[];
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface CloudPaperDownstreamPromotionPlanItem {
  artifact_id: string;
  lane: CloudPaperDownstreamLane;
  candidate_ids: string[];
  candidate_count: number;
  review_status: "review_approved";
  canonical_status: "derived_noncanonical";
  promotion_action: "prepare_canonical_state_promotion";
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
}

export interface CloudPaperDownstreamPromotionPlanResponse {
  schema_version: "cloud_paper_downstream_promotion_plan.v1";
  paper_id: string;
  run_id: string;
  plan_status: "ready" | "blocked";
  dry_run: true;
  mutation_applied: false;
  promotion_target: "canonical_structured_state";
  canonical_status: "derived_noncanonical";
  review_status: CloudPaperDownstreamReviewStatus;
  total_artifact_count: number;
  approved_artifact_count: number;
  pending_artifact_count: number;
  rejected_artifact_count: number;
  blockers: CloudPaperDownstreamPromotionBlocker[];
  promotion_items: CloudPaperDownstreamPromotionPlanItem[];
  source_pdf_sha256: string;
  payload_class: CloudPaperPayloadClass;
  warnings: CloudPaperWarning[];
  provenance_summary: CloudPaperProvenanceSummary;
}

export interface PaperNotesHomeContext {
  saved_notes: number;
  structured_notes: number;
  latest_note_updated_at?: string | null;
  note_context_limited: boolean;
  note_slug_by_paper_id: Record<string, string>;
  marker_summary: PaperNotesHomeMarkerSummary;
}

export interface HomeWorkspaceSummary {
  saved_notes: number;
  structured_notes: number;
  needs_review: number;
  blocked: number;
  latest_note_updated_at?: string | null;
  note_context_limited: boolean;
}

export interface PaperNotesHomeMarkerSummary {
  marked_papers: number;
  note_backed_papers: number;
  starred: number;
  triage_counts: Record<PaperNoteOperatorTriageLabel, number>;
}

export interface PaperNoteImportResponse {
  paper_id: string;
  slug: string;
  title: string;
  note_path: string;
  pdf_url: string;
  doi?: string | null;
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

export interface PaperNoteSectionNavigatorItem {
  key: string;
  label: string;
  outline_id?: string | null;
  outline_order?: number | null;
  claim_count: number;
  evidence_count: number;
  representative_claim_id?: string | null;
  representative_evidence_id?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  matched_to_outline: boolean;
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
  action: "extract_markdown" | "validate_citations" | "critical_appraisal" | "deep_read";
  ts: string;
  status: "succeeded" | "failed" | "blocked";
  summary: string;
  artifacts: Record<string, unknown>;
  data: Record<string, unknown>;
}

export type AppraisalCheckStatus = "pass" | "warn" | "fail" | "not_run";
export type AppraisalConcernSeverity = "info" | "warn" | "fail";

export interface CriticalAppraisalCheck {
  code: string;
  label: string;
  status: AppraisalCheckStatus;
  detail: string;
}

export interface CriticalAppraisalConcern {
  code: string;
  title: string;
  detail: string;
  severity: AppraisalConcernSeverity;
  claim_ids: string[];
  evidence_ids: string[];
  source_artifacts: string[];
}

export interface CriticalAppraisalQuestion {
  code: string;
  question: string;
  rationale: string;
  claim_ids: string[];
  evidence_ids: string[];
}

export interface CriticalAppraisalReport {
  schema_version: string;
  layer: "review_gate";
  canonical_status: "non_canonical";
  label: string;
  summary: string;
  claim_count: number;
  evidence_count: number;
  avg_confidence: number;
  verified_checks: number;
  inconsistent_checks: number;
  checks: CriticalAppraisalCheck[];
  concerns: CriticalAppraisalConcern[];
  questions: CriticalAppraisalQuestion[];
  warnings: string[];
  source_artifacts: string[];
}

export type ReadingAssistBlockKind = "one_line_summary" | "abstract" | "critical_analysis";

export interface ReadingAssistProvenance {
  source_field: string;
  source_locale: string;
  translator?: string | null;
  model?: string | null;
  version?: string | null;
}

export interface ReadingAssistBlock {
  kind: ReadingAssistBlockKind;
  text: string;
  source_heading?: string | null;
  provenance?: ReadingAssistProvenance | null;
}

export interface ReadingAssistPayload {
  locale: string;
  canonical_locale: string;
  machine_translated: boolean;
  partial: boolean;
  blocks: ReadingAssistBlock[];
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
  reading_assists?: ReadingAssistPayload[];
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

export interface MethodComparisonCreateRequest {
  comparison_id?: string;
  title?: string;
  paper_ids: string[];
  field_ids: MethodComparisonFieldId[];
  notes?: string | null;
  created_at?: string | null;
}

export type ChartSourceKind = "stats_report" | "document_table";

export type ChartTemplateId =
  | "stats_check_status_counts"
  | "reported_vs_computed_p_scatter"
  | "table_numeric_bar"
  | "table_numeric_line";

export type ChartWarningSeverity = "info" | "warning" | "error";

export type ChartFilterOp = "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in";

export type ChartSortDirection = "asc" | "desc";

export type ChartTransformKind = "field_mapping" | "filter" | "sort" | "coerce_numeric";

export type ChartArtifactKind = "data_csv" | "spec_json" | "render_png" | "render_svg";

export type ChartScalar = string | number | boolean;

export interface ChartSourceRef {
  source_kind: ChartSourceKind;
  paper_id: string;
  run_id: string;
  table_id?: string | null;
  source_label?: string | null;
}

export interface ChartFieldMapping {
  target_field: string;
  source_field: string;
  label?: string | null;
}

export interface ChartFilter {
  field: string;
  op: ChartFilterOp;
  value: ChartScalar | ChartScalar[];
}

export interface ChartSort {
  field: string;
  direction: ChartSortDirection;
}

export interface ChartTransform {
  kind: ChartTransformKind;
  description: string;
  field?: string | null;
  value?: ChartScalar | ChartScalar[] | null;
}

export interface ChartWarning {
  code: string;
  severity: ChartWarningSeverity;
  message: string;
}

export interface ChartArtifactRef {
  kind: ChartArtifactKind;
  path: string;
  mime_type?: string | null;
}

export interface ChartRenderEnv {
  engine: string;
  version: string;
  notes?: string | null;
}

export interface ChartDefinition {
  chart_id: string;
  title: string;
  template_id: ChartTemplateId;
  source_ref: ChartSourceRef;
  field_mappings: ChartFieldMapping[];
  filters: ChartFilter[];
  sort?: ChartSort | null;
  transforms: ChartTransform[];
  warnings: ChartWarning[];
  data_snapshot_ref?: ChartArtifactRef | null;
  spec_ref?: ChartArtifactRef | null;
  render_refs: ChartArtifactRef[];
}

export interface ChartPackRequestSnapshot {
  chart_pack_id?: string | null;
  title?: string | null;
  notes?: string | null;
  created_at?: string | null;
  charts: Array<{
    chart_id?: string | null;
    title?: string | null;
    template_id: ChartTemplateId;
    source_ref: ChartSourceRef;
    field_mappings: ChartFieldMapping[];
    filters: ChartFilter[];
    sort?: ChartSort | null;
  }>;
}

export interface ChartPack {
  chart_pack_id: string;
  title: string;
  created_at: string;
  generated_at?: string | null;
  charts: ChartDefinition[];
  source_items: ChartSourceRef[];
  generation_request?: ChartPackRequestSnapshot | null;
  render_env?: ChartRenderEnv | null;
  caution_notes: string[];
  warnings: ChartWarning[];
}

export type ChartPackGateStatus = "pass" | "warn" | "fail";

export interface ChartPackQualityGateCheck {
  name: string;
  status: ChartPackGateStatus;
  detail: string;
}

export interface ChartPackQualityGate {
  schema_version: string;
  workflow: "chart_pack";
  chart_pack_id: string;
  overall_status: ChartPackGateStatus;
  bundle_ready: boolean;
  handoff_ready: boolean;
  reason_codes: string[];
  checks: ChartPackQualityGateCheck[];
}

export interface ChartPackResponse {
  chart_pack: ChartPack;
  markdown: string;
  data_snapshots: Record<string, string>;
  specs: Record<string, Record<string, unknown>>;
  quality_gate?: ChartPackQualityGate | null;
}

export interface ChartPackListItem {
  chart_pack_id: string;
  title: string;
  created_at: string;
  generated_at?: string | null;
  chart_count: number;
  warning_count: number;
}

export interface ChartPackListResponse {
  items: ChartPackListItem[];
  total: number;
}

export type ProtocolSourceKind = "paper_derived" | "internal_adaptation" | "mixed";

export type ProtocolValidationStatus =
  | "unreviewed"
  | "draft"
  | "reviewed"
  | "verified_by_user"
  | "deprecated";

export type ProtocolVersionStatus = "draft" | "active" | "deprecated";

export interface ProtocolDraftSourceSummary {
  note_slug: string;
  paper_id?: string | null;
  note_path?: string | null;
  structured_state_path?: string | null;
  run_id?: string | null;
  claim_count: number;
  evidence_count: number;
  used_note_body: boolean;
  used_structured_state: boolean;
  used_claimset: boolean;
}

export type ProtocolAttachmentArtifactFamily = "protocol_attachment";

export type ProtocolAttachmentLayer = "raw_source";

export type ProtocolAttachmentSourceKind = "uploaded_file";

export type ProtocolAttachmentExtractionStatus = "succeeded" | "failed";

export type ProtocolAttachmentArtifactKind = "source_file" | "extracted_markdown";

export interface ProtocolAttachmentArtifactRef {
  kind: ProtocolAttachmentArtifactKind;
  path: string;
}

export interface ProtocolAttachmentWarning {
  code: string;
  message: string;
}

export interface ProtocolEvidenceRef {
  paper_slug: string;
  claim_id?: string | null;
  evidence_id?: string | null;
  run_id?: string | null;
  locator?: EvidenceLocator | null;
}

export interface ProtocolVersionSummary {
  version_id: string;
  version_number: number;
  status: ProtocolVersionStatus;
  created_at: string;
  change_reason?: string | null;
  source_ref_count: number;
}

export interface ProtocolCard {
  protocol_id: string;
  title: string;
  purpose?: string | null;
  context?: string | null;
  source_kind: ProtocolSourceKind;
  linked_paper_ids: string[];
  linked_note_slugs: string[];
  current_version_id?: string | null;
  validation_status: ProtocolValidationStatus;
  created_at: string;
  updated_at: string;
  version_summaries: ProtocolVersionSummary[];
}

export interface ProtocolVersion {
  version_id: string;
  protocol_id: string;
  version_number: number;
  key_steps_summary: string[];
  materials: string[];
  equipment: string[];
  critical_conditions: string[];
  readouts: string[];
  cautions: string[];
  content_snapshot: string;
  change_reason?: string | null;
  status: ProtocolVersionStatus;
  created_by: string;
  created_at: string;
  source_refs: ProtocolEvidenceRef[];
  note?: string | null;
}

export interface ProtocolCardResponse {
  protocol_card: ProtocolCard;
  versions: ProtocolVersion[];
  markdown: string;
}

export interface ProtocolCardListItem {
  protocol_id: string;
  title: string;
  source_kind: ProtocolSourceKind;
  validation_status: ProtocolValidationStatus;
  updated_at: string;
  version_count: number;
  current_version_id?: string | null;
  linked_paper_count: number;
  linked_note_count: number;
}

export interface ProtocolCardListResponse {
  items: ProtocolCardListItem[];
  total: number;
}

export interface ProtocolVersionRequestSnapshot {
  version_id?: string | null;
  version_number: number;
  key_steps_summary: string[];
  materials: string[];
  equipment: string[];
  critical_conditions: string[];
  readouts: string[];
  cautions: string[];
  content_snapshot: string;
  change_reason?: string | null;
  status: ProtocolVersionStatus;
  created_by: string;
  created_at?: string | null;
  source_refs: ProtocolEvidenceRef[];
  note?: string | null;
}

export interface ProtocolCardRequestSnapshot {
  protocol_id?: string | null;
  title: string;
  purpose?: string | null;
  context?: string | null;
  source_kind: ProtocolSourceKind;
  linked_paper_ids: string[];
  linked_note_slugs: string[];
  current_version_id?: string | null;
  validation_status: ProtocolValidationStatus;
  versions: ProtocolVersionRequestSnapshot[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProtocolAttachmentBundle {
  attachment_bundle_id: string;
  artifact_family: ProtocolAttachmentArtifactFamily;
  layer: ProtocolAttachmentLayer;
  source_kind: ProtocolAttachmentSourceKind;
  title: string;
  source_filename: string;
  media_type?: string | null;
  byte_size: number;
  sha1: string;
  note_slug?: string | null;
  paper_id?: string | null;
  run_id?: string | null;
  created_at: string;
  source_ref: ProtocolAttachmentArtifactRef;
  extracted_markdown_ref?: ProtocolAttachmentArtifactRef | null;
  extraction_engine?: string | null;
  extraction_status: ProtocolAttachmentExtractionStatus;
  extracted_markdown_excerpt?: string | null;
  warnings: ProtocolAttachmentWarning[];
}

export interface ProtocolAttachmentDraftResponse {
  attachment_bundle: ProtocolAttachmentBundle;
  draft: ProtocolCardRequestSnapshot;
  paper_source_summary?: ProtocolDraftSourceSummary | null;
  warnings: ProtocolAttachmentWarning[];
}

export type PaperSynthesisCanonicalStatus = "non_canonical";

export type PaperSynthesisReadiness = "evidence_backed" | "background_only" | "mixed";

export type PaperSynthesisFreshness = "current" | "stale" | "unknown";

export type PaperSynthesisLineageSourceKind = "structured_state" | "claimset_resolved" | "run_meta";

export type PaperSynthesisReviewArtifactKind = "quality_gate" | "acceptance_contract" | "visual_evidence_ledger";

export interface PaperSynthesisLineageSummary {
  minimum_required_source_kinds: PaperSynthesisLineageSourceKind[];
  present_required_source_kinds: PaperSynthesisLineageSourceKind[];
  review_artifact_kinds: PaperSynthesisReviewArtifactKind[];
  answer_route: "canonical_state_then_upstream_evidence";
}

export type PaperSynthesisSourceKind =
  | PaperSynthesisLineageSourceKind
  | PaperSynthesisReviewArtifactKind
  | "document_artifact"
  | "paper_note_state";

export interface PaperSynthesisSourceRef {
  kind: PaperSynthesisSourceKind;
  paper_slug: string;
  run_id?: string | null;
  path?: string | null;
  note?: string | null;
}

export interface PaperSynthesisListItem {
  synthesis_id: string;
  paper_slug: string;
  title: string;
  updated_at: string;
  artifact_family: "paper_synthesis";
  template_kind: "paper" | "project" | "meeting" | "decision" | "concept";
  canonical_status: PaperSynthesisCanonicalStatus;
  readiness: PaperSynthesisReadiness;
  freshness: PaperSynthesisFreshness;
  warning_count: number;
  source_ref_count: number;
  evidence_ref_count: number;
  lineage_summary: PaperSynthesisLineageSummary;
}

export interface PaperSynthesisListResponse {
  items: PaperSynthesisListItem[];
  total: number;
}

export interface PaperSynthesisManifest {
  synthesis_id: string;
  paper_slug: string;
  title: string;
  created_at: string;
  updated_at: string;
  artifact_family: "paper_synthesis";
  template_kind: "paper" | "project" | "meeting" | "decision" | "concept";
  layer: "compiled_knowledge";
  canonical_status: PaperSynthesisCanonicalStatus;
  readiness: PaperSynthesisReadiness;
  freshness: PaperSynthesisFreshness;
  summary?: string | null;
  source_refs: PaperSynthesisSourceRef[];
  warnings: string[];
  uncertainty_notes: string[];
  lineage_summary: PaperSynthesisLineageSummary;
}

export type ImageSourceKind = "local_file" | "external_image_ref";

export type ImageWarningSeverity = "info" | "warning" | "error";

export type ImageDerivedOutputKind =
  | "thumbnail"
  | "representative_crop"
  | "overlay"
  | "measurement_export"
  | "other";

export type ImageHandoffTargetKind = "napari" | "omero" | "other_local_viewer";

export type ChecksumAlgorithm = "md5" | "sha1" | "sha256" | "sha512";

export type ImageArtifactKind = "view_state_json" | "handoff_json" | "derived_file";

export interface ImageChecksum {
  algorithm: ChecksumAlgorithm;
  value: string;
}

export interface ImageSourceRef {
  source_kind: ImageSourceKind;
  local_path?: string | null;
  external_ref?: string | null;
  source_label?: string | null;
}

export interface ImageMetadata {
  filename?: string | null;
  source_size_bytes?: number | null;
  width_px?: number | null;
  height_px?: number | null;
  channel_count?: number | null;
  z_slices?: number | null;
  t_slices?: number | null;
  modality?: string | null;
  acquisition_note?: string | null;
  source_created_at?: string | null;
}

export interface ImageViewport {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ImageChannelRange {
  channel_id: string;
  min_value?: number | null;
  max_value?: number | null;
}

export interface ImageViewState {
  active_channels: string[];
  intensity_ranges: ImageChannelRange[];
  z_index?: number | null;
  t_index?: number | null;
  zoom_level?: number | null;
  viewport?: ImageViewport | null;
  visible_overlays: string[];
  selected_region_labels: string[];
  note?: string | null;
}

export interface ImageArtifactRef {
  kind: ImageArtifactKind;
  path: string;
  mime_type?: string | null;
}

export interface ImageDerivedOutput {
  derived_output_id: string;
  kind: ImageDerivedOutputKind;
  source_image_evidence_id: string;
  created_by: string;
  created_at: string;
  tool_name: string;
  tool_version?: string | null;
  bundle_ref?: ImageArtifactRef | null;
  external_ref?: string | null;
  view_state_ref?: ImageArtifactRef | null;
  note?: string | null;
}

export interface ImageClaimLink {
  claim_id: string;
  note?: string | null;
}

export interface ImageArtifactLink {
  artifact_kind: string;
  artifact_id: string;
  note?: string | null;
}

export interface ImageHandoffTarget {
  target: ImageHandoffTargetKind;
  openable_ref: string;
  view_state_ref?: ImageArtifactRef | null;
  notes?: string | null;
}

export interface ImageWarning {
  code: string;
  severity: ImageWarningSeverity;
  message: string;
}

export interface ImageEvidence {
  image_evidence_id: string;
  title: string;
  created_at: string;
  paper_id?: string | null;
  paper_slug?: string | null;
  source_ref: ImageSourceRef;
  content_format: string;
  checksum?: ImageChecksum | null;
  metadata: ImageMetadata;
  view_state_ref?: ImageArtifactRef | null;
  handoff_ref?: ImageArtifactRef | null;
  derived_outputs: ImageDerivedOutput[];
  linked_claim_refs: ImageClaimLink[];
  linked_artifact_refs: ImageArtifactLink[];
  warnings: ImageWarning[];
}

export interface ImageEvidenceResponse {
  image_evidence: ImageEvidence;
  view_state?: ImageViewState | null;
  handoff_targets: ImageHandoffTarget[];
}

export interface ImageEvidenceListItem {
  image_evidence_id: string;
  title: string;
  paper_id?: string | null;
  paper_slug?: string | null;
  content_format: string;
  created_at: string;
  derived_output_count: number;
  warning_count: number;
  has_view_state: boolean;
  has_handoff: boolean;
}

export interface ImageEvidenceListResponse {
  items: ImageEvidenceListItem[];
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
  section_navigator?: PaperNoteSectionNavigatorItem[];
  reading_assist?: PaperNoteReadingAssist | null;
  operator_state: PaperNoteOperatorState;
  available_actions: SkillActionInfo[];
}

export type PaperNoteOperatorTriageLabel =
  | "revisit"
  | "needs_verification"
  | "experiment_relevant";

export interface PaperNoteOperatorState {
  note_slug: string;
  paper_id: string;
  layer: "raw_memory";
  canonical_status: "non_canonical";
  paper_note_text?: string | null;
  starred: boolean;
  triage_labels: PaperNoteOperatorTriageLabel[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PaperNoteOperatorStateUpdateRequest {
  paper_note_text?: string | null;
  starred: boolean;
  triage_labels: PaperNoteOperatorTriageLabel[];
}

export interface PaperNoteReadingAssistBlock {
  kind: ReadingAssistBlockKind;
  label: string;
  canonical_text?: string | null;
  translated_text: string;
  source_field: string;
  source_heading?: string | null;
  source_locale: string;
  translator?: string | null;
  model?: string | null;
  version?: string | null;
}

export interface PaperNoteReadingAssist {
  locale: string;
  canonical_locale: string;
  machine_translated: boolean;
  partial: boolean;
  blocks: PaperNoteReadingAssistBlock[];
}

export interface PaperNoteStructuredStateLookupResponse {
  paper_id: string;
  slug: string;
  note_path: string;
  note?: PaperNoteSummary | null;
  pdf_url?: string | null;
  doi_url?: string | null;
  structured_state?: StructuredPaperState | null;
  operator_state?: PaperNoteOperatorState | null;
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
  requested_parser_backend?: "fitz_pdfplumber" | "docling" | null;
  parser_backend?: "fitz_pdfplumber" | "docling" | null;
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

export interface PrivacyPreflightFinding {
  finding_id: string;
  kind: string;
  severity: string;
  action: string;
  message: string;
  label?: string | null;
  source_surface?: string | null;
  detector?: string | null;
  reason?: string | null;
  text_preview?: string | null;
  start?: number | null;
  end?: number | null;
  metadata?: Record<string, unknown>;
}

export interface PrivacyPreflightManualReviewItem {
  review_id: string;
  severity: string;
  reason: string;
  message: string;
  source_surface?: string | null;
  finding_ids: string[];
  recommended_action: string;
}

export interface PrivacyPreflightSummary {
  detector_spans: number;
  deterministic_spans: number;
  preserve_conflicts: number;
  false_negative_risks: number;
  unexpected_predictions: number;
  manual_review_records: number;
  manual_review_reasons: number;
}

export interface PrivacyPreflightResponse {
  schema_version: string;
  mode: string;
  status: string;
  rollback_flag: string;
  payload_class: string;
  scope: string;
  redaction_applied: boolean;
  mutation_applied: boolean;
  findings: PrivacyPreflightFinding[];
  manual_review: PrivacyPreflightManualReviewItem[];
  summary: PrivacyPreflightSummary;
  input_refs: string[];
  source_surfaces: string[];
  metadata: Record<string, unknown>;
}

export interface RunInferenceLaneSummary {
  selected_backend: string;
  payload_class: string;
  redaction_applied: boolean;
  provider_name?: string | null;
  provider_model?: string | null;
  privacy_preflight?: PrivacyPreflightResponse | null;
}

export interface RunInferenceSummary {
  selected_backend: string;
  payload_class: string;
  redaction_applied: boolean;
  lanes: Record<string, RunInferenceLaneSummary>;
}

export interface ArtifactBundle {
  paper_id: string;
  run_id: string;
  inference_summary?: RunInferenceSummary | null;
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
