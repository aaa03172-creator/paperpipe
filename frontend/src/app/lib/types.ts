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
  ops_summary?: PaperNoteOpsSummary | null;
}

export interface PaperDetail extends PaperSummary {
  abstract?: string;
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

export type PaperNoteContextTraceOutcome = "loaded" | "filtered" | "resolved" | "derived" | "missing";

export interface PaperNoteContextTraceEntry {
  order: number;
  action: string;
  outcome: PaperNoteContextTraceOutcome;
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
  reference_sources: string[];
}

export interface PaperNoteContextTrace {
  available: boolean;
  summary: PaperNoteContextTraceSummary;
  trace: PaperNoteContextTraceEntry[];
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
  locator?: EvidenceHighlight | null;
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

export type OutputModeFamily = "learner" | "lab_meeting" | "project_update" | "builder_debug";

export type MeetingPackMode =
  | "journal_club"
  | "literature_update"
  | "project_progress_update"
  | "experiment_proposal";

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

export type ChartValueKind = "text" | "numeric" | "boolean";

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

export interface ChartPackResponse {
  chart_pack: ChartPack;
  markdown: string;
  data_snapshots: Record<string, string>;
  specs: Record<string, Record<string, unknown>>;
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

export interface EvidenceHighlight {
  claim_id: string;
  page: number;
  top: number;
  left: number;
  width: number;
  height: number;
  quote?: string;
  section?: string | null;
  chunk_id?: string | null;
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
