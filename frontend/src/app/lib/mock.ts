import type {
  ArtifactBundle,
  ChartPackListItem,
  ChartPackListResponse,
  ChartPackRequestSnapshot,
  ChartPackResponse,
  ChartTemplateId,
  ChartWarning,
  CloudPaperBundlePublic,
  CloudPaperDerivedArtifactsResponse,
  CloudPaperDownstreamArtifactRegistryResponse,
  CloudPaperDownstreamArtifactCandidate,
  CloudPaperDownstreamArtifactRegistrationResponse,
  CloudPaperDownstreamHandoffSummary,
  CloudPaperDownstreamLane,
  CloudPaperDownstreamPromotionPlanResponse,
  CloudPaperDownstreamPromotionReadinessResponse,
  CloudPaperDownstreamReviewStatus,
  CloudPaperHydrationState,
  CloudPaperListResponse,
  CloudPaperObsidianExportResponse,
  CloudPaperPageArtifactPublic,
  CloudPaperSearchResponse,
  ImageEvidenceListResponse,
  ImageEvidenceResponse,
  EvidenceHighlight,
  JobEnqueueResponse,
  JobStatus,
  MethodComparison,
  MethodComparisonCell,
  MethodComparisonCreateRequest,
  MethodComparisonFieldId,
  MethodComparisonListResponse,
  MethodComparisonListItem,
  MethodComparisonRow,
  MethodComparisonResponse,
  MethodComparisonValueKind,
  MeetingPackListResponse,
  MeetingPackListItem,
  MeetingPackMode,
  MeetingPackRequestSnapshot,
  MeetingPackResponse,
  PaperNoteContextTrace,
  MeetingPackTraceResponse,
  MeetingPackValidationResponse,
  OutputModeFamily,
  NotebookClaim,
  NotebookArtifact,
  ObsidianMirror,
  PaperDetail,
  PaperNoteDetailResponse,
  PaperNotesHomeContext,
  PaperNoteListResponse,
  PaperNoteOperatorState,
  PaperNoteOperatorStateUpdateRequest,
  PaperNoteSectionNavigatorItem,
  PaperNoteOperatorTriageLabel,
  PaperNoteReference,
  PaperNoteRelated,
  PaperNoteSummary,
  PaperSummary,
  PersonaListResponse,
  ProtocolCardListItem,
  ProtocolCardRequestSnapshot,
  ProtocolCardListResponse,
  ProtocolCardResponse,
  StructuredPaperState,
  TimelineResponse,
} from "./types";
import { buildBestHighlightMap, getClaimLinkState, isClaimTextMissing } from "./claimGuard";
import { hasPaperOperatorNoteText } from "./paperOperatorState";
import { expandPaperIdCandidates } from "./paperNoteOps";

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const SAMPLE_PDF = "/sample.pdf";
const MOCK_GENERATED_CHART_PACKS = new Map<string, ChartPackResponse>();
const MOCK_GENERATED_CHART_PACK_ORDER: string[] = [];
const MOCK_GENERATED_MEETING_PACKS = new Map<string, MeetingPackResponse>();
const MOCK_GENERATED_MEETING_PACK_ORDER: string[] = [];
const MOCK_GENERATED_METHOD_COMPARISONS = new Map<string, MethodComparisonResponse>();
const MOCK_GENERATED_METHOD_COMPARISON_ORDER: string[] = [];
const MOCK_GENERATED_PROTOCOL_CARDS = new Map<string, ProtocolCardResponse>();
const MOCK_GENERATED_PROTOCOL_CARD_ORDER: string[] = [];
const MOCK_CLOUD_PAPER_CREATED_AT = "2026-05-30T01:02:03Z";

function buildMockCloudPaper(
  paperId: string,
  processingStatus: CloudPaperBundlePublic["processing_status"],
  options?: { warningCode?: string },
): CloudPaperBundlePublic {
  const canRead = processingStatus === "ready";
  return {
    schema_version: "cloud_paper_bundle_public.v1",
    paper_id: paperId,
    lab_id: "lab_001",
    processing_status: processingStatus,
    payload_class: "local_only",
    page_schema_version: canRead ? "cloud_page_artifact.v1" : null,
    run_id: `run_${paperId}`,
    warnings: options?.warningCode
      ? [
          {
            code: options.warningCode,
            message: `Mock cloud paper is ${processingStatus}.`,
            severity: "high",
          },
        ]
      : [],
    permissions: {
      role: "reader",
      can_read_page: canRead,
      can_read_pdf: false,
      can_hydrate: false,
      can_upload: false,
      can_delete: false,
      can_run_optional_ai: false,
      can_export: false,
      can_share: false,
    },
    provenance_summary: {
      uploaded_by: "mock_user",
      processor_name: "paperpipe-mock-cloud-page-worker",
      processor_version: "0.1.0",
      created_at: MOCK_CLOUD_PAPER_CREATED_AT,
      source_pdf_sha256: "a".repeat(64),
    },
    local_hydration: {
      status: "not_hydrated",
      device_id: null,
      local_bundle_ref: null,
      hydrated_at: null,
      source_pdf_sha256: "a".repeat(64),
      page_artifact_sha256: canRead ? "b".repeat(64) : null,
    },
    allowed_actions: canRead ? ["read_page"] : [],
  };
}

function formatMockChartPackTimestamp(value: Date): string {
  return value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function buildMockChartPackId(): string {
  return `chartpack_${formatMockChartPackTimestamp(new Date())}_${Math.random().toString(36).slice(2, 8)}`;
}

function formatMeetingPackModeLabel(value: MeetingPackMode): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const GENERIC_BROWSER_MEETING_PACK_TITLE = "Browser generated meeting draft";

function normalizeRequestedMeetingPackTitle(
  title: string | null | undefined,
  sourceRef: string,
): string | undefined {
  const normalizedTitle = title?.trim();
  if (!normalizedTitle) {
    return undefined;
  }
  if (normalizedTitle.toLowerCase() === GENERIC_BROWSER_MEETING_PACK_TITLE.toLowerCase()) {
    return sourceRef;
  }
  return normalizedTitle;
}

function outputModeFamilyForMeetingPackMode(mode: MeetingPackMode): OutputModeFamily {
  if (mode === "journal_club" || mode === "literature_update") {
    return "lab_meeting";
  }
  if (mode === "project_progress_update") {
    return "project_update";
  }
  return "builder_debug";
}

function formatMockMeetingPackTimestamp(value: Date): string {
  return value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function formatMockMethodComparisonTimestamp(value: Date): string {
  return value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function buildMockMeetingPackId(mode: MeetingPackMode): string {
  return `meetingpack_${formatMockMeetingPackTimestamp(new Date())}_${mode}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function buildMockMethodComparisonId(): string {
  return `methodcmp_${formatMockMethodComparisonTimestamp(new Date())}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function formatMockProtocolCardTimestamp(value: Date): string {
  return value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function buildMockProtocolCardId(): string {
  return `protocol_${formatMockProtocolCardTimestamp(new Date())}_${Math.random().toString(36).slice(2, 8)}`;
}

function buildMeetingPackListItem(response: MeetingPackResponse): MeetingPackListItem {
  const primarySource = response.pack.source_items.find((item) => item.type === "paper_slug");
  return {
    pack_id: response.pack.id,
    title: response.pack.title,
    mode: response.pack.mode,
    output_mode_family: response.pack.output_mode_family,
    created_at: response.pack.created_at,
    readiness: response.pack.readiness,
    source_count: response.pack.source_items.length,
    slide_count: response.pack.slides.length,
    trace_entry_count: response.pack.retrieval_trace.length,
    primary_source_title: primarySource?.title ?? response.pack.source_items[0]?.title ?? null,
    has_generation_request: Boolean(response.pack.generation_request),
    regenerated_from_pack_id: response.pack.regenerated_from_pack_id ?? null,
  };
}

function buildProtocolCardListItem(response: ProtocolCardResponse): ProtocolCardListItem {
  return {
    protocol_id: response.protocol_card.protocol_id,
    title: response.protocol_card.title,
    source_kind: response.protocol_card.source_kind,
    validation_status: response.protocol_card.validation_status,
    updated_at: response.protocol_card.updated_at,
    version_count: response.protocol_card.version_summaries.length,
    current_version_id: response.protocol_card.current_version_id ?? null,
    linked_paper_count: response.protocol_card.linked_paper_ids.length,
    linked_note_count: response.protocol_card.linked_note_slugs.length,
  };
}

function buildChartPackListItem(response: ChartPackResponse): ChartPackListItem {
  return {
    chart_pack_id: response.chart_pack.chart_pack_id,
    title: response.chart_pack.title,
    created_at: response.chart_pack.created_at,
    generated_at: response.chart_pack.generated_at ?? null,
    chart_count: response.chart_pack.charts.length,
    warning_count: response.chart_pack.warnings.length,
  };
}

function defaultMockChartTitle(templateId: ChartTemplateId): string {
  if (templateId === "reported_vs_computed_p_scatter") {
    return "Reported vs computed p scatter";
  }
  if (templateId === "table_numeric_bar") {
    return "Numeric table bar chart";
  }
  if (templateId === "table_numeric_line") {
    return "Numeric table line chart";
  }
  return "Verification status counts";
}

function buildMockChartPackWarnings(templateId: ChartTemplateId): ChartWarning[] {
  if (templateId === "reported_vs_computed_p_scatter") {
    return [
      {
        code: "stats_p_pairs_skipped",
        severity: "warning",
        message: "Skipped approximate reported p values while building this scatter snapshot.",
      },
    ];
  }
  return [];
}

function buildMockChartPackCsv(templateId: ChartTemplateId): string {
  if (templateId === "reported_vs_computed_p_scatter") {
    return ["reported_p,computed_p", "0.01,0.009", "0.05,0.051"].join("\n");
  }
  return ["status,value", "review,1", "verified,4"].join("\n");
}

function buildMockChartPackSpec(
  chartId: string,
  title: string,
  templateId: ChartTemplateId,
  warnings: ChartWarning[],
) {
  if (templateId === "reported_vs_computed_p_scatter") {
    return {
      chart_id: chartId,
      title,
      template_id: templateId,
      mark: "point",
      encoding: { x: "reported_p", y: "computed_p" },
      row_count: 2,
      warnings,
    };
  }
  return {
    chart_id: chartId,
    title,
    template_id: templateId,
    mark: "bar",
    encoding: { x: "status", y: "value" },
    row_count: 2,
    warnings,
  };
}

const MOCK_METHOD_COMPARISON_FIELD_SPECS: Record<
  MethodComparisonFieldId,
  { label: string; value_kind: MethodComparisonValueKind }
> = {
  intervention: { label: "Intervention", value_kind: "text" },
  comparator: { label: "Comparator", value_kind: "text" },
  duration_or_timepoint: { label: "Duration / Timepoint", value_kind: "duration" },
  primary_readout: { label: "Primary Readout", value_kind: "categorical" },
  sample_size: { label: "Sample Size", value_kind: "numeric" },
};

function buildMethodComparisonListItem(response: MethodComparisonResponse): MethodComparisonListItem {
  return {
    comparison_id: response.comparison.comparison_id,
    title: response.comparison.title,
    created_at: response.comparison.created_at,
    generated_at: response.comparison.generated_at ?? response.comparison.created_at,
    paper_count: response.comparison.paper_ids.length,
    field_count: response.comparison.columns.length,
    warning_count: response.comparison.warnings.length,
  };
}

function buildMockMethodComparisonCsv(comparison: MethodComparison): string {
  const header = ["paper_id", "title", ...comparison.columns.map((column) => column.field_id)];
  const lines = [header.join(",")];
  for (const row of comparison.rows) {
    const values = comparison.columns.map((column) => {
      const cell = row.cells.find((entry) => entry.field_id === column.field_id);
      const text = String(cell?.value ?? "");
      return `"${text.replaceAll('"', '""')}"`;
    });
    lines.push([`"${row.paper_id}"`, `"${row.title.replaceAll('"', '""')}"`, ...values].join(","));
  }
  return lines.join("\n");
}

function buildMockMethodComparisonMarkdown(comparison: MethodComparison): string {
  const header = ["Paper", ...comparison.columns.map((column) => column.label)];
  const divider = header.map(() => "---");
  const rows = comparison.rows.map((row) => {
    const values = comparison.columns.map((column) => {
      const cell = row.cells.find((entry) => entry.field_id === column.field_id);
      return String(cell?.value ?? "-");
    });
    return `| ${[row.title, ...values].join(" | ")} |`;
  });

  return [
    `# ${comparison.title}`,
    "",
    `- Comparison ID: \`${comparison.comparison_id}\``,
    `- Papers: ${comparison.paper_ids.length}`,
    `- Fields: ${comparison.columns.length}`,
    "",
    `| ${header.join(" | ")} |`,
    `| ${divider.join(" | ")} |`,
    ...rows,
  ].join("\n");
}

function resolveMockComparisonPaperTitle(paperId: string): string {
  return MOCK_PAPERS.find((paper) => paper.paper_id === paperId)?.title ?? paperId;
}

function resolveMockComparisonPaperSlug(paperId: string): string | null {
  return MOCK_PAPER_NOTES.find((note) => note.id === paperId)?.slug ?? null;
}

function buildSyntheticMethodComparisonCell(
  paperId: string,
  fieldId: MethodComparisonFieldId,
  rowIndex: number,
): MethodComparisonCell {
  const paperSlug = resolveMockComparisonPaperSlug(paperId) ?? paperId;
  const baseLocator = {
    page: rowIndex + 1,
    span: [24 + rowIndex * 8, 72 + rowIndex * 8] as [number, number],
    chunk_id: `chunk-${String(rowIndex + 1).padStart(2, "0")}`,
    source: "claimset.resolved.json",
  };

  if (fieldId === "sample_size") {
    if (rowIndex % 2 === 1) {
      return {
        field_id: fieldId,
        value: null,
        normalized_value: null,
        status: "missing",
        note: null,
        evidence_refs: [],
      };
    }
    const sampleSize = 48 + rowIndex * 12;
    return {
      field_id: fieldId,
      value: sampleSize,
      normalized_value: sampleSize,
      status: "explicit",
      note: null,
      evidence_refs: [
        {
          paper_slug: paperSlug,
          claim_id: `${paperId}-sample-size`,
          evidence_id: `${paperId}-sample-size-evidence`,
          run_id: `run-${rowIndex + 1}`,
          locator: baseLocator,
        },
      ],
    };
  }

  if (fieldId === "comparator" && rowIndex % 2 === 1) {
    return {
      field_id: fieldId,
      value: "Comparator requires manual review",
      normalized_value: "comparator requires manual review",
      status: "conflict",
      note: "Mock-generated comparison keeps one comparator cell in conflict so the review path stays visible.",
      evidence_refs: [
        {
          paper_slug: paperSlug,
          claim_id: `${paperId}-comparator-a`,
          evidence_id: `${paperId}-comparator-a-evidence`,
          run_id: `run-${rowIndex + 1}`,
          locator: baseLocator,
        },
        {
          paper_slug: paperSlug,
          claim_id: `${paperId}-comparator-b`,
          evidence_id: `${paperId}-comparator-b-evidence`,
          run_id: `run-${rowIndex + 1}`,
          locator: {
            ...baseLocator,
            page: baseLocator.page + 1,
            chunk_id: `${baseLocator.chunk_id}-b`,
          },
        },
      ],
    };
  }

  const defaultTextByField: Record<MethodComparisonFieldId, string | number> = {
    intervention: `${resolveMockComparisonPaperTitle(paperId)} intervention`,
    comparator: `${resolveMockComparisonPaperTitle(paperId)} comparator`,
    duration_or_timepoint: `${8 + rowIndex * 4} weeks`,
    primary_readout: rowIndex % 2 === 0 ? "Primary endpoint trend" : "Derived assay outcome",
    sample_size: 0,
  };
  const value = defaultTextByField[fieldId];
  return {
    field_id: fieldId,
    value,
    normalized_value: value,
    status: fieldId === "primary_readout" ? "inferred" : "explicit",
    note:
      fieldId === "primary_readout"
        ? "Mock-generated from claimset-style evidence so the derived-cell review state stays visible."
        : null,
    evidence_refs: [
      {
        paper_slug: paperSlug,
        claim_id: `${paperId}-${fieldId}`,
        evidence_id: `${paperId}-${fieldId}-evidence`,
        run_id: `run-${rowIndex + 1}`,
        locator: baseLocator,
      },
    ],
  };
}

function buildMockMethodComparisonRow(
  paperId: string,
  fieldIds: MethodComparisonFieldId[],
  rowIndex: number,
): MethodComparisonRow {
  const seededRow = MOCK_METHOD_COMPARISON_RESPONSE.comparison.rows.find((row) => row.paper_id === paperId);
  if (seededRow) {
    return {
      ...deepClone(seededRow),
      cells: fieldIds
        .map((fieldId) => seededRow.cells.find((cell) => cell.field_id === fieldId))
        .filter((cell): cell is MethodComparisonCell => Boolean(cell))
        .map((cell) => deepClone(cell)),
    };
  }

  return {
    paper_id: paperId,
    paper_slug: resolveMockComparisonPaperSlug(paperId),
    title: resolveMockComparisonPaperTitle(paperId),
    cells: fieldIds.map((fieldId) => buildSyntheticMethodComparisonCell(paperId, fieldId, rowIndex)),
  };
}

function buildMeetingPackTraceSummary(response: MeetingPackResponse): MeetingPackTraceResponse["summary"] {
  const matchedPaperSlugs = Array.from(
    new Set(response.pack.retrieval_trace.flatMap((entry) => entry.matched_paper_slugs)),
  );
  const sourcePaths = Array.from(
    new Set(
      response.pack.retrieval_trace
        .map((entry) => entry.source_path)
        .filter((value): value is string => Boolean(value)),
    ),
  );

  return {
    entry_count: response.pack.retrieval_trace.length,
    selector_count: response.pack.source_items.length,
    matched_paper_count: matchedPaperSlugs.length,
    source_path_count: sourcePaths.length,
    action_counts: response.pack.retrieval_trace.reduce<Record<string, number>>((counts, entry) => {
      counts[entry.action] = (counts[entry.action] ?? 0) + 1;
      return counts;
    }, {}),
    outcome_counts: response.pack.retrieval_trace.reduce<Record<string, number>>((counts, entry) => {
      counts[entry.outcome] = (counts[entry.outcome] ?? 0) + 1;
      return counts;
    }, {}),
    matched_paper_slugs: matchedPaperSlugs,
    source_paths: sourcePaths,
  };
}

function buildMeetingPackTraceResponse(response: MeetingPackResponse): MeetingPackTraceResponse {
  return {
    pack_id: response.pack.id,
    available: response.pack.retrieval_trace.length > 0,
    summary: buildMeetingPackTraceSummary(response),
    trace: deepClone(response.pack.retrieval_trace),
  };
}

function buildMeetingPackValidationResponse(response: MeetingPackResponse): MeetingPackValidationResponse {
  return {
    validation: {
      pack_id: response.pack.id,
      readiness: response.pack.readiness,
      markdown_sync: deepClone(
        response.markdown_sync ?? {
          status: "in_sync",
          stored_markdown_sha1: "a".repeat(40),
          rendered_markdown_sha1: "a".repeat(40),
          note: null,
        },
      ),
      can_regenerate: true,
      regenerate_strategy: "saved_request",
      warnings:
        response.pack.readiness === "background_only"
          ? ["This draft uses background context only. Recheck canonical evidence before reuse."]
          : [],
    },
  };
}

const MOCK_PAPERS: PaperDetail[] = [
  {
    paper_id: "paper-2023-imaging",
    title: "Deep Learning for Medical Imaging Outcome Prediction",
    authors: "Smith et al.",
    year: 2023,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "processing",
    issues: 3,
    issues_label: "⚠️ 3 Stats Errors",
    issues_state: "flagged",
    latest_job_id: "job-001",
    latest_run_id: "run-001",
    updated_at: "2026-02-24T09:15:00Z",
    abstract: "Prospective cohort analysis with multi-center imaging outcomes.",
  },
  {
    paper_id: "paper-2024-glucose",
    title: "Ketogenic Intervention and Glucose Variability: Randomized Trial",
    authors: "Lee et al.",
    year: 2024,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "completed",
    issues: 0,
    issues_label: "No critical issues",
    issues_state: "clear",
    latest_job_id: "job-002",
    latest_run_id: "run-002",
    updated_at: "2026-02-24T07:33:00Z",
    abstract: "12-week RCT comparing ketogenic intervention vs standard care.",
  },
  {
    paper_id: "paper-2025-nutrition",
    title: "Nutrition Adherence Signals in Longitudinal Telemetry",
    authors: "Park et al.",
    year: 2025,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "failed",
    issues: 2,
    issues_label: "⚠️ 2 Data Drift Alerts",
    issues_state: "flagged",
    latest_job_id: "job-003",
    latest_run_id: "run-003",
    updated_at: "2026-02-23T20:42:00Z",
    abstract: "Observational telemetry study with adherence cohorts.",
  },
  {
    paper_id: "paper-2022-omics",
    title: "Systems Omics Review for Metabolic Resilience",
    authors: "Choi et al.",
    year: 2022,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "not_started",
    issues: 0,
    issues_label: "Not analyzed",
    issues_state: "unavailable",
    updated_at: "2026-02-22T12:09:00Z",
    abstract: "Narrative review across metabolomics and transcriptomics cohorts.",
  },
  {
    paper_id: "paper-2026-ambiguous",
    title: "Adaptive Intervention Signals with Ambiguous Evidence Anchors",
    authors: "Han et al.",
    year: 2026,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "completed",
    issues: 1,
    issues_label: "⚠️ 1 Mapping Ambiguity",
    issues_state: "flagged",
    latest_job_id: "job-004",
    latest_run_id: "run-004",
    updated_at: "2026-02-21T09:05:00Z",
    abstract: "Synthetic scenario for validating claim-to-highlight disambiguation logic.",
  },
  {
    paper_id: "paper-2026-notebook-normalized",
    title: "Notebook Anchor Normalization Fixture",
    authors: "Fixture Team",
    year: 2026,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "completed",
    issues: 0,
    issues_label: "No critical issues",
    issues_state: "clear",
    latest_job_id: "job-005",
    latest_run_id: "run-005",
    updated_at: "2026-02-25T03:25:00Z",
    abstract: "Validates notebook artifact normalization for zero-based pages and 0-1 bbox values.",
  },
];

const MOCK_JOBS: Record<string, JobStatus[]> = {
  "paper-2023-imaging": [
    {
      job_id: "job-001",
      paper_id: "paper-2023-imaging",
      run_id: "run-001",
      persona_id: "researcher",
      reasoning_persona: "researcher",
      status: "running",
      progress: 62,
      stage: "read",
      created_at: "2026-02-24T09:12:00Z",
      started_at: "2026-02-24T09:12:30Z",
    },
  ],
  "paper-2024-glucose": [
    {
      job_id: "job-002",
      paper_id: "paper-2024-glucose",
      run_id: "run-002",
      persona_id: "default",
      status: "completed",
      progress: 100,
      stage: "completed",
      created_at: "2026-02-24T07:10:00Z",
      started_at: "2026-02-24T07:10:10Z",
      finished_at: "2026-02-24T07:12:40Z",
    },
  ],
  "paper-2025-nutrition": [
    {
      job_id: "job-003",
      paper_id: "paper-2025-nutrition",
      run_id: "run-003",
      persona_id: "default",
      status: "failed",
      progress: 79,
      stage: "verify",
      error_message: "Table normalization mismatch at table_03",
      created_at: "2026-02-23T20:40:00Z",
      started_at: "2026-02-23T20:40:20Z",
      finished_at: "2026-02-23T20:43:01Z",
    },
  ],
  "paper-2022-omics": [],
  "paper-2026-ambiguous": [
    {
      job_id: "job-004",
      paper_id: "paper-2026-ambiguous",
      run_id: "run-004",
      persona_id: "metabolism_review",
      reasoning_persona: "extractor_reviewer",
      profile_id: "metabolism_review",
      status: "completed",
      progress: 100,
      stage: "completed",
      created_at: "2026-02-21T08:59:00Z",
      started_at: "2026-02-21T08:59:10Z",
      finished_at: "2026-02-21T09:03:21Z",
    },
  ],
  "paper-2026-notebook-normalized": [
    {
      job_id: "job-005",
      paper_id: "paper-2026-notebook-normalized",
      run_id: "run-005",
      persona_id: "default",
      status: "completed",
      progress: 100,
      stage: "completed",
      created_at: "2026-02-25T03:22:00Z",
      started_at: "2026-02-25T03:22:08Z",
      finished_at: "2026-02-25T03:25:00Z",
    },
  ],
};

const PLACEHOLDER_NOTEBOOK: NotebookArtifact = {
  claims: [
    {
      claim_id: "claim-1",
      text: "① Placeholder PDF is active, so this panel is demonstrating viewer layout rather than source evidence.",
      confidence: "high",
    },
    {
      claim_id: "claim-2",
      text: "② Claim selection, trace panels, and highlight behavior remain interactive in fallback mode.",
      confidence: "medium",
    },
    {
      claim_id: "claim-3",
      text: "③ To validate grounded evidence spans, load the backend and open a paper with a local PDF path.",
      confidence: "low",
    },
    {
      claim_id: "claim-4",
      text: "④ Placeholder highlights are only for UI calibration and should not be reused as scientific evidence.",
      confidence: "medium",
    },
  ],
  highlights: [
    { claim_id: "claim-1", page: 1, top: 24, left: 11, width: 75, height: 10, source: "bbox" },
    { claim_id: "claim-2", page: 1, top: 36, left: 11, width: 75, height: 10, source: "bbox" },
    { claim_id: "claim-3", page: 1, top: 48, left: 11, width: 75, height: 10, source: "bbox" },
    { claim_id: "claim-4", page: 1, top: 60, left: 11, width: 75, height: 10, source: "bbox" },
  ],
  agent_plan: [
    "Load a placeholder notebook so the workbench can stay explorable without backend data.",
    "Keep claim selection and highlight focus interactive for UI review.",
    "Expose the artifact and provenance layout even when source evidence is unavailable.",
    "Tell the user that grounded evidence requires a real backend PDF path.",
  ],
  sandbox_code: [
    "# Placeholder execution preview",
    "print({",
    "  'mode': 'mock_fallback',",
    "  'source_evidence': False,",
    "  'message': 'Run the backend to inspect grounded PDF evidence.'",
    "})",
  ].join("\n"),
  verdict: {
    label: "Preview",
    detail: "Fallback notebook is active. Load the backend to inspect grounded source evidence.",
    level: "caution",
  },
};

const EMPTY_NOTEBOOK: NotebookArtifact = {
  claims: [],
  highlights: [],
  agent_plan: [
    "Artifact not generated yet.",
    "Run Deep Read to create claimset and stats report.",
  ],
  sandbox_code: "# Sandbox Execution (read-only)\n# No execution output yet.",
  verdict: {
    label: "Pending",
    detail: "No artifact has been generated for this paper yet.",
    level: "caution",
  },
};

const NOTEBOOK_BY_PAPER: Record<string, NotebookArtifact> = {
  "paper-2023-imaging": PLACEHOLDER_NOTEBOOK,
  "paper-2024-glucose": {
    ...PLACEHOLDER_NOTEBOOK,
    verdict: {
      label: "Preview",
      detail: "Fallback notebook is active. The PDF panel is using a placeholder, not source evidence.",
      level: "caution",
    },
  },
  "paper-2025-nutrition": {
    ...PLACEHOLDER_NOTEBOOK,
    claims: [
      ...PLACEHOLDER_NOTEBOOK.claims.slice(0, 2),
      {
        claim_id: "claim-3",
        text: "Claim text missing",
        confidence: "low",
      },
      ...PLACEHOLDER_NOTEBOOK.claims.slice(3),
    ],
    highlights: [
      PLACEHOLDER_NOTEBOOK.highlights[0],
      { claim_id: "claim-2", page: 4, top: 0, left: 0, width: 0, height: 0 },
      { claim_id: "claim-3", page: 5, top: 0, left: 0, width: 0, height: 0 },
      ...PLACEHOLDER_NOTEBOOK.highlights.slice(3),
    ],
    verdict: {
      label: "Fail",
      detail: "Verifier failed due to unresolved schema mismatch in telemetry summary table.",
      level: "fail",
    },
  },
  "paper-2022-omics": PLACEHOLDER_NOTEBOOK,
  "paper-2026-ambiguous": {
    ...PLACEHOLDER_NOTEBOOK,
    claims: [
      {
        claim_id: "claim-1",
        text: "① Early intervention improved glucose variability during the initial follow-up window.",
        confidence: "high",
      },
      {
        claim_id: "claim-2",
        text: "② Effect size remained moderate after subgroup split adjustment.",
        confidence: "medium",
      },
      {
        claim_id: "claim-3",
        text: "③ No severe adverse events were observed in the cohort.",
        confidence: "medium",
      },
    ],
    highlights: [
      { claim_id: "claim-1", page: 4, top: 0, left: 0, width: 0, height: 0, source: "text_match" },
      { claim_id: "claim-1", page: 1, top: 24, left: 11, width: 75, height: 10, source: "bbox" },
      { claim_id: "claim-2", page: 2, top: 42, left: 11, width: 75, height: 10, source: "bbox" },
      { claim_id: "claim-3", page: 3, top: 58, left: 11, width: 72, height: 10, source: "bbox" },
    ],
    verdict: {
      label: "Caution",
      detail: "Evidence links require disambiguation when stats checks point to shared pages.",
      level: "caution",
    },
  },
  "paper-2026-notebook-normalized": {
    claims: [
      {
        claim_id: "claim-a",
        text: "① Primary outcome window is highlighted on the first page.",
        confidence: "high",
      },
      {
        claim_id: "claim-b",
        text: "② Secondary response region appears on the next page.",
        confidence: "medium",
      },
    ],
    highlights: [
      { claim_id: "claim-a", page: 0, top: 0.12, left: 0.08, width: 0.42, height: 0.2, source: "bbox" },
      { claim_id: "claim-b", page: 1, top: 336, left: 540, width: 340, height: 308, source: "bbox" },
    ],
    agent_plan: [
      "Read notebook artifact directly from bundle.",
      "Normalize page indexing and bbox scale before rendering.",
      "Confirm claim switch updates page and highlight box.",
    ],
    sandbox_code: "# Notebook normalization fixture\n# Zero-based page + 0-1 bbox values.",
    verdict: {
      label: "Pass",
      detail: "Notebook anchor normalization completed successfully.",
      level: "pass",
    },
  },
};

export interface MockPaperNoteQuery {
  q?: string;
  tag?: string;
  tags?: string[];
  status?: string;
  starred?: boolean;
  triageLabel?: PaperNoteOperatorTriageLabel;
  structuredOnly?: boolean;
  hasReadingAssist?: boolean;
  readingAssistLocale?: string;
  sortBy?: "date_processed" | "confidence";
  sortOrder?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}

const MOCK_PAPER_NOTES: PaperNoteSummary[] = [
  {
    slug: "ketogenicInterventionGlucoseVariability2024",
    title: "Ketogenic Intervention and Glucose Variability: Randomized Trial",
    note_path: "Inbox/PaperPipe/ketogenicInterventionGlucoseVariability2024.md",
    structured_state_present: true,
    id: "paper-2024-glucose",
    aliases: ["Ketogenic glucose trial"],
    tags: ["ketogenic", "glucose", "trial"],
    date_processed: "2026-02-24T07:33:00Z",
    confidence: 0.91,
    status: "reviewed",
    doi: "10.1000/mock-keto-2024",
    zotero_link: "zotero://select/library/items/mock-keto-2024",
    updated_at: "2026-02-24T07:33:00Z",
    pp_signals: {
      has_claimset: true,
      claim_count: 4,
      evidence_count: 4,
      citation_count: 12,
      last_appraisal: "Ready for journal club",
      last_status: "completed",
    },
    claim_tags: ["glucose variability", "diet intervention"],
    entities: ["ketogenic intervention", "continuous glucose monitoring"],
    mesh: ["Randomized Controlled Trial"],
    outcomes: ["Glucose variability"],
    ops_summary: {
      state: "healthy",
      label: "Healthy",
      reason: "ClaimSet and stats snapshot are available.",
      recommended_action: "none",
      latest_run_id: "run-002",
      has_claimset: true,
      has_stats_report: true,
      stats_check_count: 2,
    },
    starred: true,
    has_operator_note: true,
    triage_labels: ["experiment_relevant"],
  },
  {
    slug: "adaptiveInterventionSignalsAmbiguous2026",
    title: "Adaptive Intervention Signals with Ambiguous Evidence Anchors",
    note_path: "Inbox/PaperPipe/adaptiveInterventionSignalsAmbiguous2026.md",
    structured_state_present: true,
    reading_assist_available: true,
    reading_assist_locales: ["ko", "ja"],
    id: "paper-2026-ambiguous",
    aliases: ["Ambiguous evidence anchor fixture"],
    tags: ["evidence", "mapping", "review"],
    date_processed: "2026-02-21T09:05:00Z",
    confidence: 0.63,
    status: "needs_review",
    doi: null,
    zotero_link: null,
    updated_at: "2026-02-21T09:05:00Z",
    pp_signals: {
      has_claimset: true,
      claim_count: 3,
      evidence_count: 4,
      has_reading_assists: true,
      reading_assist_count: 2,
      reading_assist_locales: ["ko", "ja"],
      last_appraisal: "Needs evidence disambiguation",
      last_status: "completed",
    },
    claim_tags: ["ambiguous mapping", "evidence review"],
    entities: ["subgroup analysis", "evidence locator"],
    mesh: ["Cohort Studies"],
    outcomes: ["Intervention response"],
    ops_summary: {
      state: "action_needed",
      label: "Action needed",
      reason: "Evidence links require manual review before reuse.",
      recommended_action: "open_workbench",
      latest_run_id: "run-004",
      has_claimset: true,
      has_stats_report: true,
      stats_check_count: 2,
    },
    starred: false,
    has_operator_note: true,
    triage_labels: ["needs_verification", "revisit"],
  },
  {
    slug: "deepLearningImagingOutcomePrediction2023",
    title: "Deep Learning for Medical Imaging Outcome Prediction",
    note_path: "Inbox/PaperPipe/deepLearningImagingOutcomePrediction2023.md",
    structured_state_present: false,
    id: "paper-2023-imaging",
    aliases: ["Imaging outcome prediction"],
    tags: ["imaging", "prediction", "qa"],
    date_processed: "2026-02-24T09:15:00Z",
    confidence: 0.58,
    status: "processing",
    doi: "10.1000/mock-imaging-2023",
    zotero_link: "zotero://select/library/items/mock-imaging-2023",
    updated_at: "2026-02-24T09:15:00Z",
    pp_signals: {
      has_claimset: false,
      claim_count: 0,
      evidence_count: 0,
      last_appraisal: "Stats repair still pending",
      last_status: "processing",
    },
    claim_tags: [],
    entities: ["medical imaging"],
    mesh: ["Deep Learning"],
    outcomes: ["Outcome prediction"],
    ops_summary: {
      state: "action_needed",
      label: "Action needed",
      reason: "Saved note checks are missing or empty.",
      recommended_action: "repair_stats",
      latest_run_id: "run-001",
      has_claimset: false,
      has_stats_report: false,
      stats_check_count: 0,
    },
    starred: false,
    has_operator_note: false,
    triage_labels: [],
  },
];

function stripLeadingCounter(text: string): string {
  return text.replace(/^[^A-Za-z0-9]+\s*/u, "").trim();
}

function confidenceScore(value: NotebookClaim["confidence"]): number {
  if (value === "high") {
    return 0.9;
  }
  if (value === "medium") {
    return 0.65;
  }
  return 0.35;
}

function buildMockAdaptiveReadingAssistPayloads() {
  return [
    {
      locale: "ko",
      canonical_locale: "en",
      machine_translated: true,
      partial: true,
      blocks: [
        {
          kind: "one_line_summary" as const,
          text: "적응형 중재 신호는 유망하지만, 저장된 근거 앵커가 아직 모호해서 바로 재사용하긴 이르다.",
          source_heading: "One-Line Summary",
          provenance: {
            source_field: "one_line_summary",
            source_locale: "en",
            translator: "mock-fallback",
            model: "mock-translation-v1",
            version: "2026-04-04",
          },
        },
        {
          kind: "abstract" as const,
          text: "이 노트는 적응형 중재 결과를 빠르게 훑도록 돕지만, 근거 위치 매핑이 완전히 정리되기 전까지는 해석보다 검증이 우선이라는 점을 강조한다.",
          source_heading: "Abstract",
          provenance: {
            source_field: "abstract",
            source_locale: "en",
            translator: "mock-fallback",
            model: "mock-translation-v1",
            version: "2026-04-04",
          },
        },
        {
          kind: "critical_analysis" as const,
          text: "저장된 evidence span 가운데 일부는 여전히 ambiguous match 상태다. 따라서 downstream artifact를 만들기 전에 Workbench에서 locator와 quote 연결을 먼저 확인해야 한다.",
          source_heading: "Critical Analysis",
          provenance: {
            source_field: "critical_analysis",
            source_locale: "en",
            translator: "mock-fallback",
            model: "mock-translation-v1",
            version: "2026-04-04",
          },
        },
      ],
    },
    {
      locale: "ja",
      canonical_locale: "en",
      machine_translated: true,
      partial: true,
      blocks: [
        {
          kind: "one_line_summary" as const,
          text: "適応的介入シグナルは有望だが、保存済みの根拠アンカーはまだ曖昧で、そのまま再利用するには早い。",
          source_heading: "One-Line Summary",
          provenance: {
            source_field: "one_line_summary",
            source_locale: "en",
            translator: "mock-fallback-ja",
            model: "mock-translation-v2",
            version: "2026-04-08",
          },
        },
        {
          kind: "abstract" as const,
          text: "このノートは適応的介入の結果を素早く把握できるよう助けるが、根拠位置のマッピングが完全に整理されるまでは、解釈より検証が優先されることを強調する。",
          source_heading: "Abstract",
          provenance: {
            source_field: "abstract",
            source_locale: "en",
            translator: "mock-fallback-ja",
            model: "mock-translation-v2",
            version: "2026-04-08",
          },
        },
        {
          kind: "critical_analysis" as const,
          text: "保存済みの evidence span の一部は依然として ambiguous match の状態にある。したがって downstream artifact を作る前に、Workbench で locator と quote の対応を先に確認すべきだ。",
          source_heading: "Critical Analysis",
          provenance: {
            source_field: "critical_analysis",
            source_locale: "en",
            translator: "mock-fallback-ja",
            model: "mock-translation-v2",
            version: "2026-04-08",
          },
        },
      ],
    },
  ];
}

function buildMockStructuredState(note: PaperNoteSummary): StructuredPaperState {
  const paperId = note.id ?? note.slug;
  const paper = MOCK_PAPERS.find((item) => item.paper_id === paperId) ?? null;
  const runId = paper?.latest_run_id ?? `run-${note.slug}`;
  const notebook = NOTEBOOK_BY_PAPER[paperId] ?? PLACEHOLDER_NOTEBOOK;
  const bestHighlightsByClaim = buildBestHighlightMap(notebook.highlights);
  const noteSignals = note.pp_signals ?? {};
  const readingAssists =
    note.slug === "adaptiveInterventionSignalsAmbiguous2026"
      ? buildMockAdaptiveReadingAssistPayloads()
      : [];
  const claimset = notebook.claims.map((claim, claimIndex) => {
    const primaryHighlight = bestHighlightsByClaim.get(claim.claim_id);
    const sectionLabel = resolveMockEvidenceSectionLabel(note, claimIndex);
    const pageIndex = primaryHighlight ? Math.max(primaryHighlight.page - 1, 0) : undefined;
    return {
      id: claim.claim_id,
      source_claim_id: claim.claim_id,
      run_id: runId,
      claim: stripLeadingCounter(claim.text),
      evidence_ids: primaryHighlight ? [`${claim.claim_id}-evidence-1`] : [],
      evidence: primaryHighlight
        ? [
            {
              id: `${claim.claim_id}-evidence-1`,
              claim_id: claim.claim_id,
              run_id: runId,
              text: stripLeadingCounter(primaryHighlight.quote ?? claim.text),
              page: pageIndex,
              section: sectionLabel,
              bboxPct:
                primaryHighlight.width > 0 && primaryHighlight.height > 0
                  ? {
                      left: primaryHighlight.left,
                      top: primaryHighlight.top,
                      width: primaryHighlight.width,
                      height: primaryHighlight.height,
                    }
                  : undefined,
              source: primaryHighlight.source ?? "bbox",
              grounded: primaryHighlight.source === "bbox" ? true : null,
              resolution: primaryHighlight.source === "bbox" ? "MOCK_BBOX" : primaryHighlight.source === "text_match" ? "MOCK_TEXT_MATCH" : null,
              locator:
                typeof pageIndex === "number"
                  ? {
                      page: pageIndex,
                      span: [0, 0],
                      section: sectionLabel,
                    }
                  : {
                      span: [0, 0],
                      section: sectionLabel,
                    },
            },
          ]
        : [],
      confidence: confidenceScore(claim.confidence),
      tags: note.claim_tags ?? [],
      outcomes: note.outcomes ?? [],
    };
  });
  const sectionSummary = buildMockRuntimeSectionSummary(claimset);
  const usesPartialSectionSignal = note.slug === "adaptiveInterventionSignalsAmbiguous2026";
  const sectionNavigationSignalStatus =
    usesPartialSectionSignal ? "warn" : sectionSummary.length > 0 ? "pass" : "warn";
  const sectionNavigationSignalDetail = usesPartialSectionSignal
    ? `claimset_section_count=${sectionSummary.length}, summary_present=true`
    : `claimset_section_count=${sectionSummary.length}, summary_present=${
        sectionSummary.length > 0 ? "true" : "false"
      }`;

  return {
    schema_version: "mock-1",
    paper_slug: note.slug,
    updated_at: note.updated_at ?? note.date_processed ?? new Date().toISOString(),
    runs: [
      {
        id: runId,
        action: "deep_read",
        ts: note.updated_at ?? note.date_processed ?? new Date().toISOString(),
        status: note.ops_summary?.state === "action_needed" ? "blocked" : "succeeded",
        summary: notebook.verdict.detail,
        artifacts: {
          structured_path: `.pp/${note.slug}/state.json`,
          write_scope: {
            structured_state: true,
            frontmatter_pp: true,
            markdown_summary: false,
          },
        },
        data: {
          source: "mock_fallback",
          section_summary: sectionSummary,
          section_count: sectionSummary.length,
          section_navigation_signal_status: sectionNavigationSignalStatus,
          section_navigation_signal_detail: sectionNavigationSignalDetail,
        },
      },
    ],
    signals: {
      has_claimset: noteSignals.has_claimset === true,
      claim_count: typeof noteSignals.claim_count === "number" ? noteSignals.claim_count : notebook.claims.length,
      evidence_count: typeof noteSignals.evidence_count === "number" ? noteSignals.evidence_count : notebook.highlights.length,
      section_count: typeof noteSignals.section_count === "number" ? noteSignals.section_count : sectionSummary.length,
      quality_gate_section_navigation_signal: sectionNavigationSignalStatus,
      citation_count: typeof noteSignals.citation_count === "number" ? noteSignals.citation_count : 0,
      last_appraisal: typeof noteSignals.last_appraisal === "string" ? noteSignals.last_appraisal : null,
      last_status: typeof noteSignals.last_status === "string" ? noteSignals.last_status : note.status ?? null,
    },
    claimset,
    entities: note.entities ?? [],
    mesh: note.mesh ?? [],
    outcomes: note.outcomes ?? [],
    reading_assists: readingAssists,
  };
}

function buildMockContextTrace(note: PaperNoteSummary): PaperNoteContextTrace {
  const referenceSources = ["pdf"];
  if (note.doi) {
    referenceSources.push("doi");
  }
  if (note.zotero_link) {
    referenceSources.push("zotero");
  }
  return {
    available: true,
    summary: {
      entry_count: 2,
      source_path_count: 2,
      related_count: 1,
      reference_count: referenceSources.length,
      action_counts: {
        note_loaded: 1,
        structured_state_loaded: 1,
      },
      outcome_counts: {
        loaded: 2,
      },
      source_paths: [note.note_path, `.pp/${note.slug}/state.json`],
      related_slugs: MOCK_PAPER_NOTES.filter((item) => item.slug !== note.slug)
        .slice(0, 1)
        .map((item) => item.slug),
      reference_sources: referenceSources,
    },
    trace: [
      {
        order: 1,
        action: "note_loaded",
        outcome: "loaded",
        detail: "Loaded paper note from mock fallback dataset.",
        source_path: note.note_path,
        matched_slugs: [],
        metadata: {
          source: "mock_fallback",
        },
      },
      {
        order: 2,
        action: "structured_state_loaded",
        outcome: "loaded",
        detail: "Loaded canonical structured state from mock fallback sidecar.",
        source_path: `.pp/${note.slug}/state.json`,
        matched_slugs: [note.slug],
        metadata: {
          source: "mock_fallback",
        },
      },
    ],
  };
}

function buildMockBodyMarkdown(note: PaperNoteSummary): string {
  if (note.slug === "adaptiveInterventionSignalsAmbiguous2026") {
    return [
      `# ${note.title}`,
      "",
      "> **One-Line Summary**",
      "> Adaptive intervention signals look promising, but the saved evidence anchors are still ambiguous.",
      "",
      "## Abstract",
      "This note keeps a short canonical abstract close to the saved review state so the reader can understand the paper quickly without confusing translation support for evidence truth.",
      "",
      "## Critical Analysis",
      "- Saved evidence spans still require manual review before downstream reuse.",
      "- Ambiguous locator matches should be resolved in Workbench before exporting or summarizing the note elsewhere.",
      "",
      "## What to do next",
      "- Open the workbench to inspect ambiguous evidence links and confirm the canonical source spans.",
    ].join("\n");
  }

  const structuredState = buildMockStructuredState(note);
  const claimPreview = structuredState.claimset.slice(0, 3).map((claim) => `- ${claim.claim}`).join("\n");
  return [
    `# ${note.title}`,
    "",
    "## Why this note matters",
    `${note.title} is surfaced in fallback mode so the note viewer still demonstrates how saved notes, structured state, and workbench handoff fit together.`,
    "",
    "## Structured signals",
    claimPreview || "- Structured claims are not available yet.",
    "",
    "## What to do next",
    note.ops_summary?.recommended_action === "repair_stats"
      ? "- Repair stats before trusting downstream summaries."
      : "- Open the workbench to validate evidence links and downstream artifacts.",
  ].join("\n");
}

function buildMockPaperOperatorState(note: PaperNoteSummary): PaperNoteOperatorState {
  const paperId = note.id ?? note.slug;
  let paperNoteText: string | null = null;
  if (note.slug === "ketogenicInterventionGlucoseVariability2024") {
    paperNoteText = "Useful for experiment framing. Reopen before protocol planning.";
  } else if (note.slug === "adaptiveInterventionSignalsAmbiguous2026") {
    paperNoteText = "Needs manual evidence review before I trust or reuse the saved anchors.";
  }
  return {
    note_slug: note.slug,
    paper_id: paperId,
    layer: "raw_memory",
    canonical_status: "non_canonical",
    paper_note_text: paperNoteText,
    starred: note.starred === true,
    triage_labels: [...(note.triage_labels ?? [])],
    created_at: note.updated_at ?? note.date_processed ?? null,
    updated_at: note.updated_at ?? note.date_processed ?? null,
  };
}

function buildFallbackPaperNoteSummary(slug: string): PaperNoteSummary {
  return {
    slug,
    title: "Fallback paper note",
    note_path: `Inbox/PaperPipe/${slug}.md`,
    structured_state_present: false,
    aliases: [],
    tags: [],
  };
}

function buildMockAdaptiveReadingAssistDetail(locale?: string | null): PaperNoteDetailResponse["reading_assist"] | null {
  const canonicalOneLine =
    "Adaptive intervention signals look promising, but the saved evidence anchors are still ambiguous.";
  const canonicalAbstract =
    "This note keeps a short canonical abstract close to the saved review state so the reader can understand the paper quickly without confusing translation support for evidence truth.";
  const canonicalCriticalAnalysis =
    "- Saved evidence spans still require manual review before downstream reuse.\n- Ambiguous locator matches should be resolved in Workbench before exporting or summarizing the note elsewhere.";
  const payloads = buildMockAdaptiveReadingAssistPayloads();
  const normalizedLocale = locale?.trim().toLowerCase() ?? "";
  const selected =
    payloads.find((payload) => payload.locale === normalizedLocale) ??
    payloads.find((payload) => payload.locale === "ko") ??
    payloads[0] ??
    null;

  if (!selected) {
    return null;
  }

  return {
    locale: selected.locale,
    canonical_locale: selected.canonical_locale,
    machine_translated: selected.machine_translated,
    partial: selected.partial,
    blocks: selected.blocks.map((block) => ({
      kind: block.kind,
      label:
        block.kind === "one_line_summary"
          ? "One-Line Summary"
          : block.kind === "critical_analysis"
            ? "Critical Analysis"
            : "Abstract",
      canonical_text:
        block.kind === "one_line_summary"
          ? canonicalOneLine
          : block.kind === "critical_analysis"
            ? canonicalCriticalAnalysis
            : canonicalAbstract,
      translated_text: block.text,
      source_field: block.provenance.source_field,
      source_heading: block.source_heading,
      source_locale: block.provenance.source_locale,
      translator: block.provenance.translator,
      model: block.provenance.model,
      version: block.provenance.version,
    })),
  };
}

function slugifyMockHeading(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[`*_~[\](){}<>]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function extractMockOutlineItems(markdown: string, noteTitle?: string | null) {
  const normalizedTitle = noteTitle?.trim();
  const seen = new Map<string, number>();
  const items: Array<{ id: string; label: string; order: number }> = [];
  for (const rawLine of markdown.split(/\r?\n/)) {
    const match = rawLine.match(/^(#{1,6})\s+(.+)$/);
    if (!match) {
      continue;
    }
    const level = match[1]?.length ?? 0;
    const label = match[2]?.trim() ?? "";
    if (!label || level < 2 || label === normalizedTitle) {
      continue;
    }
    const baseId = slugifyMockHeading(label);
    if (!baseId) {
      continue;
    }
    const nextCount = (seen.get(baseId) ?? 0) + 1;
    seen.set(baseId, nextCount);
    items.push({
      id: nextCount === 1 ? baseId : `${baseId}-${nextCount}`,
      label,
      order: items.length,
    });
  }
  return items;
}

function normalizeMockSectionKey(value: string | null | undefined): string {
  const normalized = value?.trim() ?? "";
  if (!normalized) {
    return "";
  }
  return slugifyMockHeading(normalized) || normalized.toLowerCase();
}

function resolveMockEvidenceSectionLabel(note: PaperNoteSummary, claimIndex: number): string {
  if (note.slug === "adaptiveInterventionSignalsAmbiguous2026") {
    const labels = ["Abstract", "Critical Analysis", "What to do next"];
    return labels[Math.min(claimIndex, labels.length - 1)] ?? "Critical Analysis";
  }
  return "Structured signals";
}

function buildMockRuntimeSectionSummary(
  claimset: StructuredPaperState["claimset"],
): Array<{
  key: string;
  label: string;
  claim_count: number;
  evidence_count: number;
  representative_claim_id: string | null;
  representative_evidence_id: string | null;
  page_start: number | null;
  page_end: number | null;
}> {
  const sections = new Map<
    string,
    {
      key: string;
      label: string;
      claim_count: number;
      evidence_count: number;
      representative_claim_id: string | null;
      representative_evidence_id: string | null;
      pages: number[];
    }
  >();

  for (const claim of claimset ?? []) {
    const claimSectionKeys = new Set<string>();
    for (const evidence of claim.evidence ?? []) {
      const sectionLabel = evidence.locator?.section?.trim() || evidence.section?.trim() || "";
      if (!sectionLabel) {
        continue;
      }
      const key = normalizeMockSectionKey(sectionLabel);
      if (!key) {
        continue;
      }
      const next =
        sections.get(key) ?? {
          key,
          label: sectionLabel,
          claim_count: 0,
          evidence_count: 0,
          representative_claim_id: null,
          representative_evidence_id: null,
          pages: [],
        };

      if (!claimSectionKeys.has(key)) {
        next.claim_count += 1;
        claimSectionKeys.add(key);
      }
      next.evidence_count += 1;
      if (!next.representative_claim_id) {
        next.representative_claim_id = claim.id;
      }
      if (!next.representative_evidence_id) {
        next.representative_evidence_id = evidence.id ?? null;
      }
      if (typeof evidence.page === "number" && Number.isFinite(evidence.page)) {
        next.pages.push(evidence.page);
      }
      sections.set(key, next);
    }
  }

  return Array.from(sections.values())
    .map((item) => {
      const uniquePages = Array.from(new Set(item.pages)).sort((left, right) => left - right);
      return {
        key: item.key,
        label: item.label,
        claim_count: item.claim_count,
        evidence_count: item.evidence_count,
        representative_claim_id: item.representative_claim_id,
        representative_evidence_id: item.representative_evidence_id,
        page_start: uniquePages[0] ?? null,
        page_end: uniquePages.length > 0 ? uniquePages[uniquePages.length - 1] : null,
      };
    })
    .sort((left, right) => {
      if (left.evidence_count !== right.evidence_count) {
        return right.evidence_count - left.evidence_count;
      }
      if (left.claim_count !== right.claim_count) {
        return right.claim_count - left.claim_count;
      }
      return left.label.localeCompare(right.label);
    });
}

function buildMockSectionNavigator(
  note: PaperNoteSummary,
  bodyMarkdown: string,
  structuredState: StructuredPaperState | null,
): PaperNoteSectionNavigatorItem[] {
  if (!structuredState) {
    return [];
  }

  const outlineByKey = new Map(
    extractMockOutlineItems(bodyMarkdown, note.title).map((item) => [
      normalizeMockSectionKey(item.label),
      { id: item.id, label: item.label, order: item.order },
    ]),
  );
  const runtimeSummary =
    Array.isArray(structuredState.runs?.[0]?.data?.section_summary) && structuredState.runs[0]?.data?.section_summary.length > 0
      ? structuredState.runs[0].data.section_summary
      : buildMockRuntimeSectionSummary(structuredState.claimset ?? []);
  const items: PaperNoteSectionNavigatorItem[] = [];
  for (const item of runtimeSummary) {
      const key = normalizeMockSectionKey(typeof item.key === "string" ? item.key : typeof item.label === "string" ? item.label : "");
      const label = typeof item.label === "string" ? item.label.trim() : "";
      if (!key || !label) {
        continue;
      }
      const outlineMatch = outlineByKey.get(key);
      items.push({
        key,
        label: outlineMatch?.label ?? label,
        outline_id: outlineMatch?.id ?? null,
        outline_order: outlineMatch?.order ?? null,
        claim_count: typeof item.claim_count === "number" ? item.claim_count : 0,
        evidence_count: typeof item.evidence_count === "number" ? item.evidence_count : 0,
        representative_claim_id:
          typeof item.representative_claim_id === "string" ? item.representative_claim_id : null,
        representative_evidence_id:
          typeof item.representative_evidence_id === "string" ? item.representative_evidence_id : null,
        page_start: typeof item.page_start === "number" ? item.page_start : null,
        page_end: typeof item.page_end === "number" ? item.page_end : null,
        matched_to_outline: Boolean(outlineMatch),
      });
    }

  return items.sort((left, right) => {
      if (left.matched_to_outline !== right.matched_to_outline) {
        return left.matched_to_outline ? -1 : 1;
      }
      if ((left.outline_order ?? Number.MAX_SAFE_INTEGER) !== (right.outline_order ?? Number.MAX_SAFE_INTEGER)) {
        return (left.outline_order ?? Number.MAX_SAFE_INTEGER) - (right.outline_order ?? Number.MAX_SAFE_INTEGER);
      }
      if (left.evidence_count !== right.evidence_count) {
        return right.evidence_count - left.evidence_count;
      }
      if (left.claim_count !== right.claim_count) {
        return right.claim_count - left.claim_count;
      }
      return left.label.localeCompare(right.label);
    });
}

function buildMockPaperNoteDetail(
  note: PaperNoteSummary,
  options?: { readingAssistLocale?: string | null },
): PaperNoteDetailResponse {
  const readingAssist =
    note.slug === "adaptiveInterventionSignalsAmbiguous2026"
      ? buildMockAdaptiveReadingAssistDetail(options?.readingAssistLocale)
      : null;
  const related: PaperNoteRelated[] = MOCK_PAPER_NOTES.filter((item) => item.slug !== note.slug)
    .slice(0, 2)
    .map((item) => ({
      slug: item.slug,
      title: item.title,
      shared_tags: item.tags.slice(0, 2).filter((tag) => note.tags.includes(tag)),
      shared_signals: (item.outcomes ?? []).slice(0, 1),
    }));

  const references: PaperNoteReference[] = [
    {
      label: "Open placeholder PDF",
      url: SAMPLE_PDF,
      source: "pdf" as const,
    },
  ];
  if (note.doi) {
    references.push({
      label: `DOI ${note.doi}`,
      url: `https://doi.org/${note.doi}`,
      source: "doi" as const,
    });
  }
  if (note.zotero_link) {
    references.push({
      label: "Open in Zotero",
      url: note.zotero_link,
      source: "zotero" as const,
    });
  }

  const bodyMarkdown = buildMockBodyMarkdown(note);
  const structuredState = note.structured_state_present ? buildMockStructuredState(note) : null;

  return {
    note,
    frontmatter: {
      id: note.id,
      aliases: note.aliases,
      tags: note.tags,
      date_processed: note.date_processed,
      confidence: note.confidence,
      status: note.status,
      doi: note.doi,
    },
    body_markdown: bodyMarkdown,
    related,
    references,
    context_trace: buildMockContextTrace(note),
    structured_state: structuredState,
    section_navigator: buildMockSectionNavigator(note, bodyMarkdown, structuredState),
    reading_assist: readingAssist,
    operator_state: buildMockPaperOperatorState(note),
    available_actions: [],
  };
}

const MOCK_PAPER_NOTE_DETAILS: Record<string, PaperNoteDetailResponse> = Object.fromEntries(
  MOCK_PAPER_NOTES.map((note) => [note.slug, buildMockPaperNoteDetail(note)]),
);

function parseMockQueryTerms(value: string): string[] {
  const pattern = /"([^"]+)"|(\S+)/g;
  const terms: string[] = [];
  for (const match of value.matchAll(pattern)) {
    const raw = (match[1] ?? match[2] ?? "").trim().toLowerCase();
    if (raw) {
      terms.push(raw.replace(/\s+/g, " "));
    }
  }
  return terms;
}

function buildMockPaperNoteHaystack(note: PaperNoteSummary): string {
  const signals = note.pp_signals ?? {};
  const lastAppraisal = typeof signals.last_appraisal === "string" ? signals.last_appraisal : "";
  return [
    note.slug,
    note.title,
    note.id ?? "",
    ...note.aliases,
    ...note.tags,
    ...(note.claim_tags ?? []),
    ...(note.entities ?? []),
    ...(note.mesh ?? []),
    ...(note.outcomes ?? []),
    lastAppraisal,
  ]
    .join(" ")
    .toLowerCase();
}

function filterMockPaperNotes(params?: MockPaperNoteQuery): PaperNoteSummary[] {
  const queryTerms = parseMockQueryTerms(params?.q ?? "");
  const selectedTags = Array.from(new Set([params?.tag, ...(params?.tags ?? [])].filter((value): value is string => Boolean(value))));
  const normalizedStatus = params?.status?.trim().toLowerCase() ?? "";
  const starredOnly = params?.starred === true;
  const triageLabel = params?.triageLabel ?? null;
  const hasReadingAssist = params?.hasReadingAssist === true;
  const targetReadingAssistLocale = params?.readingAssistLocale?.trim().toLowerCase() ?? "";

  return MOCK_PAPER_NOTES.filter((note) => {
    const haystack = buildMockPaperNoteHaystack(note);
    if (queryTerms.length > 0 && !queryTerms.every((term) => haystack.includes(term))) {
      return false;
    }
    if (selectedTags.length > 0 && !selectedTags.some((tag) => note.tags.some((value) => value.toLowerCase() === tag.toLowerCase()))) {
      return false;
    }
    if (normalizedStatus && (note.status ?? "").toLowerCase() !== normalizedStatus) {
      return false;
    }
    if (starredOnly && note.starred !== true) {
      return false;
    }
    if (triageLabel && !(note.triage_labels ?? []).includes(triageLabel)) {
      return false;
    }
    if (params?.structuredOnly && !note.structured_state_present && (note.claim_tags?.length ?? 0) === 0 && (note.outcomes?.length ?? 0) === 0) {
      return false;
    }
    if (hasReadingAssist) {
      const available = note.reading_assist_available === true || (note.reading_assist_locales?.length ?? 0) > 0;
      if (!available) {
        return false;
      }
    }
    if (targetReadingAssistLocale) {
      const locales = (note.reading_assist_locales ?? [])
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean);
      if (!locales.includes(targetReadingAssistLocale)) {
        return false;
      }
    }
    return true;
  });
}

function sortMockPaperNotes(notes: PaperNoteSummary[], params?: MockPaperNoteQuery): PaperNoteSummary[] {
  const sortBy = params?.sortBy ?? "date_processed";
  const sortOrder = params?.sortOrder ?? "desc";
  const sorted = [...notes].sort((left, right) => {
    if (sortBy === "confidence") {
      return (left.confidence ?? -1) - (right.confidence ?? -1);
    }
    const leftValue = left.date_processed ? Date.parse(left.date_processed) : 0;
    const rightValue = right.date_processed ? Date.parse(right.date_processed) : 0;
    return leftValue - rightValue;
  });
  return sortOrder === "asc" ? sorted : sorted.reverse();
}

function buildDocumentArtifactFromNotebook(notebook: NotebookArtifact): Record<string, unknown> {
  const rawPages = notebook.highlights
    .map((item) => Math.round(item.page))
    .filter((page) => Number.isFinite(page) && page >= 0);
  const uniqueRawPages = Array.from(new Set(rawPages));
  const zeroBased = uniqueRawPages.some((page) => page === 0);
  const pageIndexes =
    uniqueRawPages.length > 0
      ? uniqueRawPages.map((page) => (zeroBased ? page : Math.max(page - 1, 0)))
      : [0];

  return {
    pages: pageIndexes.map((pageIndex) => ({
      page_index: pageIndex,
      width: 1000,
      height: 1400,
      blocks: [],
    })),
  };
}

function toArtifactBundle(paperId: string, runId: string, notebook: NotebookArtifact): ArtifactBundle {
  return {
    paper_id: paperId,
    run_id: runId,
    inference_summary: {
      selected_backend: "local",
      payload_class: "local_only",
      redaction_applied: false,
      lanes: {
        reader: {
          selected_backend: "local",
          payload_class: "local_only",
          redaction_applied: false,
          provider_name: "mock-local",
          provider_model: "llama3:8b",
        },
      },
    },
    files: {
      claimset_resolved: {
        exists: true,
        path: `storage/artifacts/${paperId}/${runId}/claimset.resolved.json`,
        data: {
          paper_id: paperId,
          run_id: runId,
          claims: notebook.claims.map((claim) => ({
            claim_id: claim.claim_id,
            claim_text: claim.text,
            confidence: claim.confidence,
            evidence: [{ page: notebook.highlights.find((h) => h.claim_id === claim.claim_id)?.page ?? 1 }],
          })),
        },
      },
      stats_report: {
        exists: true,
        path: `storage/artifacts/${paperId}/${runId}/stats_report.json`,
        data: {
          checks: [
            { check_id: "check-1", hypothesis: "Primary endpoint difference", verdict: notebook.verdict.level === "fail" ? "fail" : "pass" },
            { check_id: "check-2", hypothesis: "N consistency", verdict: notebook.verdict.level === "pass" ? "pass" : "warning" },
          ],
        },
      },
      run_meta: {
        exists: true,
        path: `storage/artifacts/${paperId}/${runId}/run_meta.json`,
        data: {
          models_used: ["llama3:8b", "openhermes2.5-mistral"],
          tool_policy_version: "v3.0",
        },
      },
      evidence_grounding_scorecard: {
        exists: true,
        path: `storage/artifacts/${paperId}/${runId}/evidence_grounding_scorecard.json`,
        data: {
          schema_version: "evidence_grounding_scorecard.v1",
          layer: "review_gate_artifact",
          canonical_status: "non_canonical",
          readiness_status: "warn",
          reason_codes: ["missing_p0_gold_metrics", "accepted_corrections_not_replayable"],
          recommended_next_action: "review_proxy_warnings_before_promotion",
          runtime_proxy_metrics: {
            grounded_evidence_ratio: { status: "available", value: 0.6 },
            page_coverage_ratio: { status: "available", value: 0.3 },
            correction_feedback_link_rate: { status: "available", value: 0 },
            review_burden_per_paper: { status: "available", value: 1 },
          },
        },
      },
      document_artifact: {
        exists: true,
        path: `storage/artifacts/${paperId}/${runId}/document.json`,
        data: buildDocumentArtifactFromNotebook(notebook),
      },
      notebook: {
        exists: true,
        data: notebook,
      },
    },
  };
}

const MOCK_TIMELINES: Record<string, TimelineResponse> = {
  "run-001": {
    run_id: "run-001",
    job_id: "job-001",
    paper_id: "paper-2023-imaging",
    events: [
      {
        event: "log",
        source: "job_log",
        ts: "2026-02-24T09:12:35Z",
        stage: "ingest",
        level: "INFO",
        message: "PDF text extraction complete (12 pages).",
      },
      {
        event: "log",
        source: "job_log",
        ts: "2026-02-24T09:13:00Z",
        stage: "index",
        level: "INFO",
        message: "Chunks indexed (164 records).",
      },
      {
        event: "status",
        source: "synthetic",
        ts: "2026-02-24T09:13:28Z",
        stage: "read",
        progress: 62,
        level: "INFO",
        message: "reader running",
      },
    ],
  },
  "run-002": {
    run_id: "run-002",
    job_id: "job-002",
    paper_id: "paper-2024-glucose",
    events: [
      {
        event: "log",
        source: "job_log",
        ts: "2026-02-24T07:10:22Z",
        stage: "verify",
        level: "INFO",
        message: "All checks passed.",
      },
      {
        event: "done",
        source: "synthetic",
        ts: "2026-02-24T07:12:40Z",
        stage: "completed",
        progress: 100,
        level: "INFO",
        message: "completed",
      },
    ],
  },
  "run-003": {
    run_id: "run-003",
    job_id: "job-003",
    paper_id: "paper-2025-nutrition",
    events: [
      {
        event: "error",
        source: "job_log",
        ts: "2026-02-23T20:42:50Z",
        stage: "verify",
        level: "ERROR",
        message: "Verifier schema mismatch detected.",
      },
      {
        event: "done",
        source: "synthetic",
        ts: "2026-02-23T20:43:01Z",
        stage: "failed",
        progress: 79,
        level: "ERROR",
        message: "failed",
      },
    ],
  },
  "run-004": {
    run_id: "run-004",
    job_id: "job-004",
    paper_id: "paper-2026-ambiguous",
    events: [
      {
        event: "log",
        source: "user_action",
        ts: "2026-02-21T08:59:12Z",
        stage: "deepread_enqueued",
        level: "INFO",
        message: "User queued deep read",
      },
      {
        event: "log",
        source: "job_log",
        ts: "2026-02-21T09:00:02Z",
        stage: "read",
        level: "INFO",
        message: "Anchor candidates resolved for 3 claims.",
      },
      {
        event: "log",
        source: "job_log",
        ts: "2026-02-21T09:01:18Z",
        stage: "verify",
        level: "INFO",
        message: "Stats checks generated with page-level overlap.",
      },
      {
        event: "done",
        source: "synthetic",
        ts: "2026-02-21T09:03:21Z",
        stage: "completed",
        progress: 100,
        level: "INFO",
        message: "completed",
      },
    ],
  },
  "run-005": {
    run_id: "run-005",
    job_id: "job-005",
    paper_id: "paper-2026-notebook-normalized",
    events: [
      {
        event: "log",
        source: "job_log",
        ts: "2026-02-25T03:23:10Z",
        stage: "read",
        level: "INFO",
        message: "Notebook artifact loaded for normalization check.",
      },
      {
        event: "done",
        source: "synthetic",
        ts: "2026-02-25T03:25:00Z",
        stage: "completed",
        progress: 100,
        level: "INFO",
        message: "completed",
      },
    ],
  },
};

const MOCK_MEETING_PACK_ID = "meetingpack_20260317T090000Z_journal_club_mock1234";
const MOCK_MEETING_PACK_RESPONSE: MeetingPackResponse = {
  pack: {
    id: MOCK_MEETING_PACK_ID,
    mode: "journal_club",
    output_mode_family: "lab_meeting",
    title: "SCFA journal club debug draft",
    created_at: "2026-03-17T09:00:00Z",
    status: "draft",
    readiness: "evidence_backed",
    generation_request: {
      mode: "journal_club",
      title: "SCFA journal club debug draft",
      source_items: [
        { type: "paper_slug", ref: "wenzelShortchainFattyAcids2020" },
        { type: "project_note", ref: "Projects/SCFA.md" },
      ],
      max_slides: 6,
    },
    regenerated_from_pack_id: null,
    source_items: [
      {
        id: "src_01",
        type: "paper_slug",
        ref: "wenzelShortchainFattyAcids2020",
        title: "wenzelShortchainFattyAcids2020",
        priority: 1,
        included: true,
      },
      {
        id: "src_02",
        type: "project_note",
        ref: "Projects/SCFA.md",
        title: "SCFA project",
        priority: 3,
        included: true,
      },
    ],
    retrieval_trace: [
      {
        order: 1,
        selector_type: "paper_slug",
        selector_ref: "wenzelShortchainFattyAcids2020",
        action: "selector_selected",
        outcome: "selected",
        detail: "Direct structured paper selector accepted.",
        source_item_id: "src_01",
        source_path: null,
        matched_paper_slugs: [],
        metadata: {},
      },
      {
        order: 2,
        selector_type: "paper_slug",
        selector_ref: "wenzelShortchainFattyAcids2020",
        action: "paper_state_loaded",
        outcome: "loaded",
        detail: "Loaded canonical structured paper state from the paper sidecar.",
        source_item_id: "src_01",
        source_path: ".pp/wenzelShortchainFattyAcids2020/state.json",
        matched_paper_slugs: ["wenzelShortchainFattyAcids2020"],
        metadata: {
          loaded_count: 1,
          reused_count: 0,
        },
      },
      {
        order: 3,
        selector_type: "project_note",
        selector_ref: "Projects/SCFA.md",
        action: "selector_selected",
        outcome: "selected",
        detail: "Note selector accepted for context-based source resolution.",
        source_item_id: "src_02",
        source_path: "Projects/SCFA.md",
        matched_paper_slugs: [],
        metadata: {},
      },
      {
        order: 4,
        selector_type: "project_note",
        selector_ref: "Projects/SCFA.md",
        action: "note_links_resolved",
        outcome: "resolved",
        detail: "Resolved linked paper slugs from note frontmatter/body only.",
        source_item_id: "src_02",
        source_path: "Projects/SCFA.md",
        matched_paper_slugs: ["wenzelShortchainFattyAcids2020"],
        metadata: {},
      },
      {
        order: 5,
        selector_type: "project_note",
        selector_ref: "Projects/SCFA.md",
        action: "paper_states_loaded",
        outcome: "loaded",
        detail: "Resolved 1 paper slug(s) from the note selector; loaded 0 new state(s) and reused 1 existing state(s).",
        source_item_id: "src_02",
        source_path: "Projects/SCFA.md",
        matched_paper_slugs: ["wenzelShortchainFattyAcids2020"],
        metadata: {
          loaded_slugs: [],
          reused_slugs: ["wenzelShortchainFattyAcids2020"],
        },
      },
    ],
    one_page_summary: {
      overview: "This draft focuses on the SCFA paper with project-note framing added for discussion setup.",
      key_points: [
        {
          label: "Main finding",
          text: "The selected paper reports reduced inflammatory signaling.",
          evidence_refs: ["evref_01"],
          uncertainty_note: "Magnitude language should be rechecked before presenting.",
        },
      ],
      consensus_points: [],
      conflicts: [],
      uncertainties: ["Project note framing should not override structured claim/evidence truth."],
    },
    slides: [
      {
        slide_title: "Why this paper matters",
        purpose: "Frame the paper and the discussion target",
        bullets: [
          "SCFA intervention is discussed against inflammatory pathway outcomes.",
          "Project-note context sharpens the lab discussion target.",
        ],
        evidence_refs: ["evref_01"],
        caution_notes: ["Trace explains source loading, not scientific certainty."],
      },
      {
        slide_title: "Study design and methods",
        purpose: "Summarize what was studied and how",
        bullets: ["Structured state was loaded from the canonical paper sidecar."],
        evidence_refs: ["evref_01"],
        caution_notes: [],
      },
    ],
    speaker_notes: [
      {
        slide_index: 1,
        text: "Open with the claim/evidence core before mentioning project framing.",
        evidence_refs: ["evref_01"],
      },
    ],
    discussion_questions: [
      {
        question: "Which selector contributed context versus canonical evidence?",
        rationale: "Trace separation should remain explicit during discussion.",
        evidence_refs: ["evref_01"],
      },
    ],
    expected_questions: [
      {
        question: "Was the note used as a source of truth?",
        suggested_response: "No. The note only shaped framing while the canonical evidence came from state.json.",
        evidence_refs: ["evref_01"],
      },
    ],
    next_steps: [
      {
        action: "Re-verify the pack if selector inputs change.",
        why: "Regenerate availability depends on current selector resolution.",
        priority: "medium",
        evidence_refs: ["evref_01"],
      },
    ],
    evidence_refs: [
      {
        id: "evref_01",
        paper_slug: "wenzelShortchainFattyAcids2020",
        claim_id: "claim_abc123",
        evidence_id: "evidence_def456",
        run_id: "skill-20260317T090000Z-critical_appraisal",
        support_type: "direct",
        note: "Primary evidence reference for the draft overview.",
      },
    ],
  },
  markdown: [
    "# SCFA journal club debug draft",
    "",
    "## One-page Summary",
    "",
    "This draft focuses on the SCFA paper with project-note framing added for discussion setup.",
    "",
    "## Slide Outline",
    "",
    "1. Why this paper matters",
    "2. Study design and methods",
  ].join("\n"),
  markdown_sync: {
    status: "in_sync",
    stored_markdown_sha1: "a".repeat(40),
    rendered_markdown_sha1: "a".repeat(40),
    note: null,
  },
};

const MOCK_MEETING_PACK_TRACE_RESPONSE: MeetingPackTraceResponse = {
  pack_id: MOCK_MEETING_PACK_ID,
  available: true,
  summary: {
    entry_count: 5,
    selector_count: 2,
    matched_paper_count: 1,
    source_path_count: 2,
    action_counts: {
      selector_selected: 2,
      paper_state_loaded: 1,
      note_links_resolved: 1,
      paper_states_loaded: 1,
    },
    outcome_counts: {
      selected: 2,
      loaded: 2,
      resolved: 1,
    },
    matched_paper_slugs: ["wenzelShortchainFattyAcids2020"],
    source_paths: [
      ".pp/wenzelShortchainFattyAcids2020/state.json",
      "Projects/SCFA.md",
    ],
  },
  trace: MOCK_MEETING_PACK_RESPONSE.pack.retrieval_trace,
};

const MOCK_MEETING_PACK_VALIDATION_RESPONSE: MeetingPackValidationResponse = {
  validation: {
    pack_id: MOCK_MEETING_PACK_ID,
    readiness: "evidence_backed",
    markdown_sync: {
      status: "in_sync",
      stored_markdown_sha1: "a".repeat(40),
      rendered_markdown_sha1: "a".repeat(40),
      note: null,
    },
    can_regenerate: true,
    regenerate_strategy: "saved_request",
    warnings: [],
  },
};

const MOCK_MEETING_PACK_LIST_RESPONSE: MeetingPackListResponse = {
  generated_at: "2026-03-17T09:05:00Z",
  total: 3,
  items: [
    {
      pack_id: MOCK_MEETING_PACK_ID,
      title: "SCFA journal club debug draft",
      mode: "journal_club",
      output_mode_family: "lab_meeting",
      created_at: "2026-03-17T09:00:00Z",
      readiness: "evidence_backed",
      source_count: 2,
      slide_count: 2,
      trace_entry_count: 5,
      primary_source_title: "wenzelShortchainFattyAcids2020",
      has_generation_request: true,
      regenerated_from_pack_id: null,
    },
    {
      pack_id: "meetingpack_20260317T001512345Z_journal_club_mocksourceaware",
      title: "Browser generated meeting draft",
      mode: "journal_club",
      output_mode_family: "lab_meeting",
      created_at: "2026-03-17T00:15:12.345Z",
      readiness: "evidence_backed",
      source_count: 1,
      slide_count: 4,
      trace_entry_count: 0,
      primary_source_title: "SCFA journal club debug draft",
      has_generation_request: true,
      regenerated_from_pack_id: null,
    },
    {
      pack_id: "meetingpack_20260316T173000Z_experiment_proposal_mock5678",
      title: "Butyrate follow-up proposal draft",
      mode: "experiment_proposal",
      output_mode_family: "builder_debug",
      created_at: "2026-03-16T17:30:00Z",
      readiness: "background_only",
      source_count: 1,
      slide_count: 2,
      trace_entry_count: 0,
      primary_source_title: "butyratePilotStudy2025",
      has_generation_request: false,
      regenerated_from_pack_id: MOCK_MEETING_PACK_ID,
    },
  ],
};

const MOCK_METHOD_COMPARISON_ID = "methodcmp_20260318T010000Z_mock1234";
const MOCK_METHOD_COMPARISON_RESPONSE: MethodComparisonResponse = {
  comparison: {
    comparison_id: MOCK_METHOD_COMPARISON_ID,
    title: "Ketogenic vs coaching intervention comparison",
    created_at: "2026-03-18T01:00:00Z",
    generated_at: "2026-03-18T01:04:00Z",
    paper_ids: ["paper-2024-glucose", "paper-2025-nutrition"],
    columns: [
      { field_id: "intervention", label: "Intervention", value_kind: "text" },
      { field_id: "comparator", label: "Comparator", value_kind: "text" },
      { field_id: "duration_or_timepoint", label: "Duration / Timepoint", value_kind: "duration" },
      { field_id: "primary_readout", label: "Primary Readout", value_kind: "categorical" },
      { field_id: "sample_size", label: "Sample Size", value_kind: "numeric" },
    ],
    rows: [
      {
        paper_id: "paper-2024-glucose",
        paper_slug: "leeKetogenicIntervention2024",
        title: "Ketogenic Intervention and Glucose Variability: Randomized Trial",
        cells: [
          {
            field_id: "intervention",
            value: "Ketogenic diet protocol",
            normalized_value: "ketogenic diet protocol",
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "leeKetogenicIntervention2024",
                claim_id: "claim-intervention",
                evidence_id: "ev-intervention",
                run_id: "run-002",
                locator: { page: 2, span: [120, 171], chunk_id: "chunk-02", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "comparator",
            value: "Standard care diet",
            normalized_value: "standard care diet",
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "leeKetogenicIntervention2024",
                claim_id: "claim-comparator",
                evidence_id: "ev-comparator",
                run_id: "run-002",
                locator: { page: 2, span: [172, 216], chunk_id: "chunk-02", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "duration_or_timepoint",
            value: "12 weeks",
            normalized_value: "12 weeks",
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "leeKetogenicIntervention2024",
                claim_id: "claim-duration",
                evidence_id: "ev-duration",
                run_id: "run-002",
                locator: { page: 3, span: [40, 66], chunk_id: "chunk-04", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "primary_readout",
            value: "Continuous glucose variability",
            normalized_value: "continuous glucose variability",
            status: "inferred",
            note: "Derived from endpoint wording across two resolved claims.",
            evidence_refs: [
              {
                paper_slug: "leeKetogenicIntervention2024",
                claim_id: "claim-readout",
                evidence_id: "ev-readout",
                run_id: "run-002",
                locator: { page: 4, span: [18, 92], chunk_id: "chunk-06", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "sample_size",
            value: 82,
            normalized_value: 82,
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "leeKetogenicIntervention2024",
                claim_id: "claim-sample-size",
                evidence_id: "ev-sample-size",
                run_id: "run-002",
                locator: { page: 1, span: [208, 226], chunk_id: "chunk-01", source: "claimset.resolved.json" },
              },
            ],
          },
        ],
      },
      {
        paper_id: "paper-2025-nutrition",
        paper_slug: "parkNutritionAdherence2025",
        title: "Nutrition Adherence Signals in Longitudinal Telemetry",
        cells: [
          {
            field_id: "intervention",
            value: "Telemetry-guided nutrition coaching",
            normalized_value: "telemetry-guided nutrition coaching",
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "parkNutritionAdherence2025",
                claim_id: "claim-intervention",
                evidence_id: "ev-intervention",
                run_id: "run-003",
                locator: { page: 2, span: [96, 148], chunk_id: "chunk-03", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "comparator",
            value: "Usual care vs self-managed logging",
            normalized_value: "usual care vs self-managed logging",
            status: "conflict",
            note: "Resolved claims disagree on whether the baseline arm was usual care or logging-only self management.",
            evidence_refs: [
              {
                paper_slug: "parkNutritionAdherence2025",
                claim_id: "claim-comparator-a",
                evidence_id: "ev-comparator-a",
                run_id: "run-003",
                locator: { page: 3, span: [15, 58], chunk_id: "chunk-05", source: "claimset.resolved.json" },
              },
              {
                paper_slug: "parkNutritionAdherence2025",
                claim_id: "claim-comparator-b",
                evidence_id: "ev-comparator-b",
                run_id: "run-003",
                locator: { page: 5, span: [10, 61], chunk_id: "chunk-08", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "duration_or_timepoint",
            value: "24 weeks",
            normalized_value: "24 weeks",
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "parkNutritionAdherence2025",
                claim_id: "claim-duration",
                evidence_id: "ev-duration",
                run_id: "run-003",
                locator: { page: 2, span: [149, 175], chunk_id: "chunk-03", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "primary_readout",
            value: "Adherence trajectory",
            normalized_value: "adherence trajectory",
            status: "explicit",
            note: null,
            evidence_refs: [
              {
                paper_slug: "parkNutritionAdherence2025",
                claim_id: "claim-readout",
                evidence_id: "ev-readout",
                run_id: "run-003",
                locator: { page: 4, span: [75, 126], chunk_id: "chunk-06", source: "claimset.resolved.json" },
              },
            ],
          },
          {
            field_id: "sample_size",
            value: null,
            normalized_value: null,
            status: "missing",
            note: null,
            evidence_refs: [],
          },
        ],
      },
    ],
    source_summary: {
      source_priority: ["claimset.resolved.json", "document_artifact", "paper_note_state"],
      note: "v0 viewer reflects the claimset-only generation lane. Missing cells mean no deterministic resolved claim was available.",
      source_paper_count: 2,
      note_backed_paper_count: 0,
      operator_override_count: 0,
    },
    warnings: [
      "Comparator cell for paper-2025-nutrition remains conflict-backed and should be reviewed before downstream reuse.",
    ],
  },
  csv_text: [
    "paper_id,title,intervention,comparator,duration_or_timepoint,primary_readout,sample_size",
    "\"paper-2024-glucose\",\"Ketogenic Intervention and Glucose Variability: Randomized Trial\",\"Ketogenic diet protocol\",\"Standard care diet\",\"12 weeks\",\"Continuous glucose variability\",\"82\"",
    "\"paper-2025-nutrition\",\"Nutrition Adherence Signals in Longitudinal Telemetry\",\"Telemetry-guided nutrition coaching\",\"Usual care vs self-managed logging\",\"24 weeks\",\"Adherence trajectory\",\"\"",
  ].join("\n"),
  markdown: [
    "# Ketogenic vs coaching intervention comparison",
    "",
    "| Paper | Intervention | Comparator | Duration / Timepoint | Primary Readout | Sample Size |",
    "| --- | --- | --- | --- | --- | --- |",
    "| Ketogenic Intervention and Glucose Variability: Randomized Trial | Ketogenic diet protocol | Standard care diet | 12 weeks | Continuous glucose variability | 82 |",
    "| Nutrition Adherence Signals in Longitudinal Telemetry | Telemetry-guided nutrition coaching | Usual care vs self-managed logging | 24 weeks | Adherence trajectory | - |",
  ].join("\n"),
};

const MOCK_METHOD_COMPARISON_LIST_RESPONSE: MethodComparisonListResponse = {
  total: 2,
  items: [
    {
      comparison_id: MOCK_METHOD_COMPARISON_ID,
      title: "Ketogenic vs coaching intervention comparison",
      created_at: "2026-03-18T01:00:00Z",
      generated_at: "2026-03-18T01:04:00Z",
      paper_count: 2,
      field_count: 5,
      warning_count: 1,
    },
    {
      comparison_id: "methodcmp_20260317T222000Z_mock5678",
      title: "Imaging outcome assay comparison",
      created_at: "2026-03-17T22:20:00Z",
      generated_at: "2026-03-17T22:21:00Z",
      paper_count: 3,
      field_count: 4,
      warning_count: 0,
    },
  ],
};

const MOCK_CHART_PACK_ID = "chartpack_20260320T120000Z_mock1234";
const MOCK_SECONDARY_CHART_PACK_ID = "chartpack_20260319T221500Z_mock5678";
const MOCK_CHART_PACK_RESPONSE: ChartPackResponse = {
  chart_pack: {
    chart_pack_id: MOCK_CHART_PACK_ID,
    title: "Verification and measurement chart pack",
    created_at: "2026-03-20T12:00:00Z",
    generated_at: "2026-03-20T12:03:00Z",
    charts: [
      {
        chart_id: "chart_01_reported-vs-computed-p-scatter",
        title: "Verification scatter",
        template_id: "reported_vs_computed_p_scatter",
        source_ref: {
          source_kind: "stats_report",
          paper_id: "paper-2024-glucose",
          run_id: "run-002",
          source_label: "stats_report.json",
        },
        field_mappings: [
          { target_field: "reported_p", source_field: "reported_p" },
          { target_field: "computed_p", source_field: "computed_p" },
        ],
        filters: [],
        sort: { field: "reported_p", direction: "asc" },
        transforms: [
          { kind: "field_mapping", description: "Mapped reported_p -> reported_p.", field: "reported_p" },
          { kind: "field_mapping", description: "Mapped computed_p -> computed_p.", field: "computed_p" },
          { kind: "sort", description: "Sorted rows by reported_p ascending.", field: "reported_p" },
        ],
        warnings: [
          {
            code: "stats_report.approximate_pair_skipped",
            severity: "warning",
            message: "Approximate reported p values were skipped from the scatter snapshot.",
          },
        ],
        data_snapshot_ref: {
          kind: "data_csv",
          path: "data/chart_01_reported-vs-computed-p-scatter.csv",
          mime_type: "text/csv",
        },
        spec_ref: {
          kind: "spec_json",
          path: "specs/chart_01_reported-vs-computed-p-scatter.json",
          mime_type: "application/json",
        },
        render_refs: [
          {
            kind: "render_svg",
            path: "renders/chart_01_reported-vs-computed-p-scatter.svg",
            mime_type: "image/svg+xml",
          },
        ],
      },
      {
        chart_id: "chart_02_table-numeric-line",
        title: "Measurement line",
        template_id: "table_numeric_line",
        source_ref: {
          source_kind: "document_table",
          paper_id: "paper-2025-nutrition",
          run_id: "run-003",
          table_id: "tbl-002",
          source_label: "document_artifact_v2.json",
        },
        field_mappings: [
          { target_field: "group", source_field: "Group" },
          { target_field: "measurement", source_field: "Measurement" },
        ],
        filters: [],
        sort: { field: "group", direction: "asc" },
        transforms: [
          { kind: "field_mapping", description: "Mapped Group -> group.", field: "group" },
          { kind: "field_mapping", description: "Mapped Measurement -> measurement.", field: "measurement" },
          { kind: "coerce_numeric", description: "Coerced Measurement values to numeric.", field: "measurement" },
        ],
        warnings: [],
        data_snapshot_ref: {
          kind: "data_csv",
          path: "data/chart_02_table-numeric-line.csv",
          mime_type: "text/csv",
        },
        spec_ref: {
          kind: "spec_json",
          path: "specs/chart_02_table-numeric-line.json",
          mime_type: "application/json",
        },
        render_refs: [
          {
            kind: "render_svg",
            path: "renders/chart_02_table-numeric-line.svg",
            mime_type: "image/svg+xml",
          },
        ],
      },
    ],
    source_items: [
      {
        source_kind: "stats_report",
        paper_id: "paper-2024-glucose",
        run_id: "run-002",
        source_label: "stats_report.json",
      },
      {
        source_kind: "document_table",
        paper_id: "paper-2025-nutrition",
        run_id: "run-003",
        table_id: "tbl-002",
        source_label: "document_artifact_v2.json",
      },
    ],
    generation_request: {
      chart_pack_id: MOCK_CHART_PACK_ID,
      title: "Verification and measurement chart pack",
      charts: [
        {
          title: "Verification scatter",
          template_id: "reported_vs_computed_p_scatter",
          source_ref: {
            source_kind: "stats_report",
            paper_id: "paper-2024-glucose",
            run_id: "run-002",
            source_label: "stats_report.json",
          },
          field_mappings: [
            { target_field: "reported_p", source_field: "reported_p" },
            { target_field: "computed_p", source_field: "computed_p" },
          ],
          filters: [],
          sort: { field: "reported_p", direction: "asc" },
        },
        {
          title: "Measurement line",
          template_id: "table_numeric_line",
          source_ref: {
            source_kind: "document_table",
            paper_id: "paper-2025-nutrition",
            run_id: "run-003",
            table_id: "tbl-002",
            source_label: "document_artifact_v2.json",
          },
          field_mappings: [
            { target_field: "group", source_field: "Group" },
            { target_field: "measurement", source_field: "Measurement" },
          ],
          filters: [],
          sort: { field: "group", direction: "asc" },
        },
      ],
    },
    render_env: {
      engine: "chart_pack_template_renderer",
      version: "v0",
      notes: "Deterministic template-driven spec builder over saved artifact snapshots.",
    },
    caution_notes: [
      "Some charts include warning states; inspect source lineage before reuse.",
      "Reported/computed p charts include only exact numeric pairs and skip approximate values.",
      "Document-table charts rely on saved table structure and explicit numeric coercion only.",
    ],
    warnings: [
      {
        code: "stats_report.approximate_pair_skipped",
        severity: "warning",
        message: "Approximate reported p values were skipped from the scatter snapshot.",
      },
    ],
  },
  data_snapshots: {
    "chart_01_reported-vs-computed-p-scatter": [
      "reported_p,computed_p",
      "0.01,0.009",
      "0.05,0.04",
      "0.20,0.18",
    ].join("\n"),
    "chart_02_table-numeric-line": [
      "group,measurement",
      "Baseline,4.1",
      "Week 6,3.4",
      "Week 12,2.8",
    ].join("\n"),
  },
  specs: {
    "chart_01_reported-vs-computed-p-scatter": {
      chart_id: "chart_01_reported-vs-computed-p-scatter",
      title: "Verification scatter",
      template_id: "reported_vs_computed_p_scatter",
      mark: "point",
      encoding: { x: "reported_p", y: "computed_p" },
      row_count: 3,
      warnings: [
        {
          code: "stats_report.approximate_pair_skipped",
          severity: "warning",
          message: "Approximate reported p values were skipped from the scatter snapshot.",
        },
      ],
    },
    "chart_02_table-numeric-line": {
      chart_id: "chart_02_table-numeric-line",
      title: "Measurement line",
      template_id: "table_numeric_line",
      mark: "line",
      encoding: { x: "group", y: "measurement" },
      row_count: 3,
      warnings: [],
    },
  },
  markdown: [
    "# Verification and measurement chart pack",
    "",
    "- Chart Pack ID: chartpack_20260320T120000Z_mock1234",
    "- Charts: 2",
    "",
    "## Charts",
    "### Verification scatter",
    "- Template: reported_vs_computed_p_scatter",
    "- Data snapshot: data/chart_01_reported-vs-computed-p-scatter.csv",
    "",
    "| reported_p | computed_p |",
    "| --- | --- |",
    "| 0.01 | 0.009 |",
    "| 0.05 | 0.04 |",
    "| 0.20 | 0.18 |",
  ].join("\n"),
  quality_gate: {
    schema_version: "2026-04-17.chart-pack-handoff.v1",
    workflow: "chart_pack",
    chart_pack_id: MOCK_CHART_PACK_ID,
    overall_status: "warn",
    bundle_ready: true,
    handoff_ready: false,
    reason_codes: ["CHART_WARNING_PRESENT"],
    checks: [
      { name: "source_items_persisted", status: "pass", detail: "true" },
      { name: "data_snapshot_refs_complete", status: "pass", detail: "true" },
      { name: "spec_refs_complete", status: "pass", detail: "true" },
      { name: "markdown_synced_at_write", status: "pass", detail: "in_sync" },
      { name: "artifact_brief_review", status: "warn", detail: "CHART_WARNING_PRESENT" },
      { name: "warning_state_requires_review", status: "warn", detail: "true" },
    ],
  },
};

const MOCK_SECONDARY_CHART_PACK_RESPONSE: ChartPackResponse = {
  chart_pack: {
    chart_pack_id: MOCK_SECONDARY_CHART_PACK_ID,
    title: "Status count review pack",
    created_at: "2026-03-19T22:15:00Z",
    generated_at: "2026-03-19T22:16:00Z",
    charts: [
      {
        chart_id: "chart_01_stats-check-status-counts",
        title: "Verification status counts",
        template_id: "stats_check_status_counts",
        source_ref: {
          source_kind: "stats_report",
          paper_id: "paper-2023-imaging",
          run_id: "run-001",
          source_label: "stats_report.json",
        },
        field_mappings: [
          { target_field: "status", source_field: "status" },
          { target_field: "value", source_field: "count" },
        ],
        filters: [],
        sort: { field: "status", direction: "asc" },
        transforms: [
          { kind: "field_mapping", description: "Mapped status -> status.", field: "status" },
          { kind: "field_mapping", description: "Mapped count -> value.", field: "value" },
          { kind: "sort", description: "Sorted rows by status ascending.", field: "status" },
        ],
        warnings: [],
        data_snapshot_ref: {
          kind: "data_csv",
          path: "data/chart_01_stats-check-status-counts.csv",
          mime_type: "text/csv",
        },
        spec_ref: {
          kind: "spec_json",
          path: "specs/chart_01_stats-check-status-counts.json",
          mime_type: "application/json",
        },
        render_refs: [
          {
            kind: "render_svg",
            path: "renders/chart_01_stats-check-status-counts.svg",
            mime_type: "image/svg+xml",
          },
        ],
      },
    ],
    source_items: [
      {
        source_kind: "stats_report",
        paper_id: "paper-2023-imaging",
        run_id: "run-001",
        source_label: "stats_report.json",
      },
    ],
    generation_request: {
      chart_pack_id: MOCK_SECONDARY_CHART_PACK_ID,
      title: "Status count review pack",
      charts: [
        {
          title: "Verification status counts",
          template_id: "stats_check_status_counts",
          source_ref: {
            source_kind: "stats_report",
            paper_id: "paper-2023-imaging",
            run_id: "run-001",
            source_label: "stats_report.json",
          },
          field_mappings: [
            { target_field: "status", source_field: "status" },
            { target_field: "value", source_field: "count" },
          ],
          filters: [],
          sort: { field: "status", direction: "asc" },
        },
      ],
    },
    render_env: {
      engine: "chart_pack_template_renderer",
      version: "v0",
      notes: "Deterministic template-driven spec builder over saved artifact snapshots.",
    },
    caution_notes: [],
    warnings: [],
  },
  data_snapshots: {
    "chart_01_stats-check-status-counts": [
      "status,value",
      "inconsistent,1",
      "verified,3",
    ].join("\n"),
  },
  specs: {
    "chart_01_stats-check-status-counts": {
      chart_id: "chart_01_stats-check-status-counts",
      title: "Verification status counts",
      template_id: "stats_check_status_counts",
      mark: "bar",
      encoding: { x: "status", y: "value" },
      row_count: 2,
      warnings: [],
    },
  },
  markdown: [
    "# Status count review pack",
    "",
    "- Chart Pack ID: chartpack_20260319T221500Z_mock5678",
    "- Charts: 1",
    "",
    "## Charts",
    "### Verification status counts",
    "- Template: stats_check_status_counts",
    "- Data snapshot: data/chart_01_stats-check-status-counts.csv",
    "",
    "| status | value |",
    "| --- | --- |",
    "| inconsistent | 1 |",
    "| verified | 3 |",
  ].join("\n"),
  quality_gate: {
    schema_version: "2026-04-17.chart-pack-handoff.v1",
    workflow: "chart_pack",
    chart_pack_id: MOCK_SECONDARY_CHART_PACK_ID,
    overall_status: "pass",
    bundle_ready: true,
    handoff_ready: true,
    reason_codes: [],
    checks: [
      { name: "source_items_persisted", status: "pass", detail: "true" },
      { name: "data_snapshot_refs_complete", status: "pass", detail: "true" },
      { name: "spec_refs_complete", status: "pass", detail: "true" },
      { name: "markdown_synced_at_write", status: "pass", detail: "in_sync" },
      { name: "artifact_brief_review", status: "pass", detail: "pass" },
      { name: "warning_state_requires_review", status: "pass", detail: "false" },
    ],
  },
};

const MOCK_CHART_PACK_LIST_RESPONSE: ChartPackListResponse = {
  total: 2,
  items: [
    {
      chart_pack_id: MOCK_CHART_PACK_ID,
      title: "Verification and measurement chart pack",
      created_at: "2026-03-20T12:00:00Z",
      generated_at: "2026-03-20T12:03:00Z",
      chart_count: 2,
      warning_count: 1,
    },
    {
      chart_pack_id: MOCK_SECONDARY_CHART_PACK_ID,
      title: "Status count review pack",
      created_at: "2026-03-19T22:15:00Z",
      generated_at: "2026-03-19T22:16:00Z",
      chart_count: 1,
      warning_count: 0,
    },
  ],
};

const MOCK_IMAGE_EVIDENCE_ID = "imageev_20260322_mock1234";
const MOCK_SECONDARY_IMAGE_EVIDENCE_ID = "imageev_20260322_mock5678";

const MOCK_IMAGE_EVIDENCE_RESPONSE: ImageEvidenceResponse = {
  image_evidence: {
    image_evidence_id: MOCK_IMAGE_EVIDENCE_ID,
    title: "Representative hippocampal ROI image",
    created_at: "2026-03-22T12:00:00Z",
    paper_id: "paper-2024-glucose",
    paper_slug: "leeKetogenicIntervention2024",
    source_ref: {
      source_kind: "local_file",
      local_path: "/Users/jangseongjin/mock-data/imaging/hippocampus-alpha.tif",
      source_label: "Microscope Alpha",
    },
    content_format: "image/tiff",
    checksum: {
      algorithm: "sha256",
      value: "5d13cf76594395ffcbb55215b508b1a82032a1cdc9eaeadd2ffa046b6e30e96e",
    },
    metadata: {
      filename: "hippocampus-alpha.tif",
      source_size_bytes: 248832,
      width_px: 512,
      height_px: 512,
      channel_count: 2,
      modality: "fluorescence",
      acquisition_note: "Single representative crop from the hippocampal ROI workflow.",
      source_created_at: "2026-03-21T09:10:00Z",
    },
    view_state_ref: {
      kind: "view_state_json",
      path: "view_state.json",
      mime_type: "application/json",
    },
    handoff_ref: {
      kind: "handoff_json",
      path: "handoff.json",
      mime_type: "application/json",
    },
    derived_outputs: [
      {
        derived_output_id: "thumb_hippocampus",
        kind: "thumbnail",
        source_image_evidence_id: MOCK_IMAGE_EVIDENCE_ID,
        created_by: "operator",
        created_at: "2026-03-22T12:05:00Z",
        tool_name: "napari",
        tool_version: "0.5",
        bundle_ref: {
          kind: "derived_file",
          path: "derivatives/thumb_hippocampus.png",
          mime_type: "image/png",
        },
        view_state_ref: {
          kind: "view_state_json",
          path: "view_state.json",
          mime_type: "application/json",
        },
        note: "Representative thumbnail for downstream pack review.",
      },
      {
        derived_output_id: "overlay_signal",
        kind: "overlay",
        source_image_evidence_id: MOCK_IMAGE_EVIDENCE_ID,
        created_by: "operator",
        created_at: "2026-03-22T12:07:00Z",
        tool_name: "napari",
        external_ref: "omero://dataset/42/image/7/overlay/1",
        note: "Overlay kept in external imaging system; bundle stores only lineage.",
      },
    ],
    linked_claim_refs: [
      {
        claim_id: "claim-2024-hippocampus-1",
        note: "Representative image only; not full-stack validation.",
      },
    ],
    linked_artifact_refs: [
      {
        artifact_kind: "meeting_pack",
        artifact_id: "meetingpack_20260322_mock1234",
        note: "Used in the representative-image slide draft.",
      },
    ],
    warnings: [
      {
        code: "REPRESENTATIVE_ONLY",
        severity: "warning",
        message: "Bundle captures a representative crop rather than the full acquisition stack.",
      },
    ],
  },
  view_state: {
    active_channels: ["GFP", "DAPI"],
    intensity_ranges: [
      { channel_id: "GFP", min_value: 10, max_value: 220 },
      { channel_id: "DAPI", min_value: 5, max_value: 180 },
    ],
    z_index: 4,
    zoom_level: 2.2,
    viewport: { x: 16, y: 24, width: 144, height: 144 },
    visible_overlays: ["scale_bar", "roi_outline"],
    selected_region_labels: ["hippocampus-roi"],
    note: "Saved operator viewport for reuse in note and slide review.",
  },
  handoff_targets: [
    {
      target: "napari",
      openable_ref: "/Users/jangseongjin/mock-data/imaging/hippocampus-alpha.tif",
      view_state_ref: {
        kind: "view_state_json",
        path: "view_state.json",
      },
      notes: "Open with saved viewport and channel intensities.",
    },
  ],
};

const MOCK_SECONDARY_IMAGE_EVIDENCE_RESPONSE: ImageEvidenceResponse = {
  image_evidence: {
    image_evidence_id: MOCK_SECONDARY_IMAGE_EVIDENCE_ID,
    title: "OMERO brightfield plate image",
    created_at: "2026-03-22T11:20:00Z",
    paper_id: "paper-2025-nutrition",
    paper_slug: "parkNutritionAdherence2025",
    source_ref: {
      source_kind: "external_image_ref",
      external_ref: "omero://dataset/42/image/7",
      source_label: "OMERO image 7",
    },
    content_format: "image/png",
    metadata: {
      filename: "plate-image-7.png",
      width_px: 1024,
      height_px: 768,
      modality: "brightfield",
      acquisition_note: "External reference only; no local raw path registered.",
    },
    derived_outputs: [],
    linked_claim_refs: [],
    linked_artifact_refs: [],
    warnings: [],
  },
  handoff_targets: [
    {
      target: "omero",
      openable_ref: "omero://dataset/42/image/7",
      notes: "Open in OMERO for channel and annotation context.",
    },
  ],
};

const MOCK_IMAGE_EVIDENCE_LIST_RESPONSE: ImageEvidenceListResponse = {
  total: 2,
  items: [
    {
      image_evidence_id: MOCK_IMAGE_EVIDENCE_ID,
      title: "Representative hippocampal ROI image",
      paper_id: "paper-2024-glucose",
      paper_slug: "leeKetogenicIntervention2024",
      content_format: "image/tiff",
      created_at: "2026-03-22T12:00:00Z",
      derived_output_count: 2,
      warning_count: 1,
      has_view_state: true,
      has_handoff: true,
    },
    {
      image_evidence_id: MOCK_SECONDARY_IMAGE_EVIDENCE_ID,
      title: "OMERO brightfield plate image",
      paper_id: "paper-2025-nutrition",
      paper_slug: "parkNutritionAdherence2025",
      content_format: "image/png",
      created_at: "2026-03-22T11:20:00Z",
      derived_output_count: 0,
      warning_count: 0,
      has_view_state: false,
      has_handoff: true,
    },
  ],
};

const MOCK_PROTOCOL_CARD_ID = "protocol_20260323T010000Z_mock1234";
const MOCK_SECONDARY_PROTOCOL_CARD_ID = "protocol_20260322T213000Z_mock5678";

const MOCK_PROTOCOL_CARD_RESPONSE: ProtocolCardResponse = {
  protocol_card: {
    protocol_id: MOCK_PROTOCOL_CARD_ID,
    title: "Primary cortical assay protocol",
    purpose: "Track response patterns across the cortical assay lane before downstream meeting-pack reuse.",
    context: "Mixed paper-derived and operator-adapted assay summary for bounded review only.",
    source_kind: "mixed",
    linked_paper_ids: ["paper-2024-glucose", "paper-2025-nutrition"],
    linked_note_slugs: ["leeKetogenicIntervention2024", "parkNutritionAdherence2025"],
    current_version_id: "protver_cortical_assay_v2",
    validation_status: "draft",
    created_at: "2026-03-23T01:00:00Z",
    updated_at: "2026-03-23T01:20:00Z",
    version_summaries: [
      {
        version_id: "protver_cortical_assay_v1",
        version_number: 1,
        status: "draft",
        created_at: "2026-03-23T01:00:00Z",
        change_reason: "Initial paper-derived capture from saved claims.",
        source_ref_count: 1,
      },
      {
        version_id: "protver_cortical_assay_v2",
        version_number: 2,
        status: "active",
        created_at: "2026-03-23T01:20:00Z",
        change_reason: "Clarified media timing and readout naming after note reconciliation.",
        source_ref_count: 2,
      },
    ],
  },
  versions: [
    {
      version_id: "protver_cortical_assay_v1",
      protocol_id: MOCK_PROTOCOL_CARD_ID,
      version_number: 1,
      key_steps_summary: ["Seed cortical cells", "Apply ketogenic intervention"],
      materials: ["DMEM", "FBS"],
      equipment: ["CO2 incubator"],
      critical_conditions: ["37 C", "5% CO2"],
      readouts: ["Glucose variability"],
      cautions: ["Keep cell density below confluence."],
      content_snapshot: "Step 1: seed cortical cells.\nStep 2: apply ketogenic intervention.\nStep 3: measure glucose variability.",
      change_reason: "Initial paper-derived capture from saved claims.",
      status: "draft",
      created_by: "operator",
      created_at: "2026-03-23T01:00:00Z",
      source_refs: [
        {
          paper_slug: "leeKetogenicIntervention2024",
          claim_id: "claim-001",
          evidence_id: "ev-001",
          run_id: "run-002",
          locator: { page: 4, span: [20, 72], chunk_id: "chunk-11", source: "claimset.resolved.json" },
        },
      ],
      note: "Initial draft kept close to paper wording.",
    },
    {
      version_id: "protver_cortical_assay_v2",
      protocol_id: MOCK_PROTOCOL_CARD_ID,
      version_number: 2,
      key_steps_summary: ["Seed cortical cells", "Refresh media after baseline", "Apply ketogenic intervention"],
      materials: ["DMEM", "FBS", "Ketone supplement"],
      equipment: ["CO2 incubator", "Plate reader"],
      critical_conditions: ["37 C", "5% CO2", "12 week window alignment for downstream comparison"],
      readouts: ["Glucose variability", "Adherence trajectory handoff note"],
      cautions: ["Do not merge operator adaptation with paper truth downstream without citation."],
      content_snapshot:
        "Step 1: seed cortical cells.\nStep 2: refresh media after baseline acquisition.\nStep 3: apply ketogenic intervention.\nStep 4: record glucose variability and note downstream adherence context separately.",
      change_reason: "Clarified media timing and readout naming after note reconciliation.",
      status: "active",
      created_by: "operator",
      created_at: "2026-03-23T01:20:00Z",
      source_refs: [
        {
          paper_slug: "leeKetogenicIntervention2024",
          claim_id: "claim-002",
          evidence_id: "ev-002",
          run_id: "run-002",
          locator: { page: 5, span: [12, 68], chunk_id: "chunk-15", source: "claimset.resolved.json" },
        },
        {
          paper_slug: "parkNutritionAdherence2025",
          claim_id: "claim-018",
          evidence_id: "ev-018",
          run_id: "run-003",
          locator: { page: 3, span: [88, 146], chunk_id: "chunk-07", source: "claimset.resolved.json" },
        },
      ],
      note: "Current review snapshot; still draft because no verified wet-lab confirmation exists.",
    },
  ],
  markdown: [
    "# Primary cortical assay protocol",
    "",
    "- Protocol ID: `protocol_20260323T010000Z_mock1234`",
    "- Source kind: `mixed`",
    "- Validation status: `draft`",
    "- Current version: `protver_cortical_assay_v2`",
    "",
    "## Purpose",
    "",
    "Track response patterns across the cortical assay lane before downstream meeting-pack reuse.",
    "",
    "## Versions",
    "",
    "### v2 `protver_cortical_assay_v2`",
    "",
    "- Status: `active`",
    "- Created by: `operator`",
    "- Source refs: `2`",
  ].join("\n"),
};

const MOCK_SECONDARY_PROTOCOL_CARD_RESPONSE: ProtocolCardResponse = {
  protocol_card: {
    protocol_id: MOCK_SECONDARY_PROTOCOL_CARD_ID,
    title: "Reference brightfield stain workflow",
    purpose: "Keep a clean user-verified brightfield stain reference for repeated note linking.",
    context: "Paper-derived only and explicitly kept as a verified-by-user reference snapshot.",
    source_kind: "paper_derived",
    linked_paper_ids: ["paper-2023-imaging"],
    linked_note_slugs: ["paper-2023-imaging-note"],
    current_version_id: "protver_brightfield_reference_v1",
    validation_status: "verified_by_user",
    created_at: "2026-03-22T21:30:00Z",
    updated_at: "2026-03-22T21:45:00Z",
    version_summaries: [
      {
        version_id: "protver_brightfield_reference_v1",
        version_number: 1,
        status: "active",
        created_at: "2026-03-22T21:30:00Z",
        change_reason: "Approved as stable reference snapshot.",
        source_ref_count: 1,
      },
    ],
  },
  versions: [
    {
      version_id: "protver_brightfield_reference_v1",
      protocol_id: MOCK_SECONDARY_PROTOCOL_CARD_ID,
      version_number: 1,
      key_steps_summary: ["Prepare brightfield stain", "Capture baseline plate image"],
      materials: ["Brightfield stain"],
      equipment: ["Microscope"],
      critical_conditions: ["Baseline capture only"],
      readouts: ["Plate image"],
      cautions: [],
      content_snapshot: "Step 1: prepare brightfield stain.\nStep 2: capture baseline plate image.",
      change_reason: "Approved as stable reference snapshot.",
      status: "active",
      created_by: "operator",
      created_at: "2026-03-22T21:30:00Z",
      source_refs: [
        {
          paper_slug: "paper-2023-imaging-note",
          claim_id: "claim-101",
          evidence_id: "ev-101",
          run_id: "run-001",
          locator: { page: 2, span: [10, 61], chunk_id: "chunk-04", source: "claimset.resolved.json" },
        },
      ],
      note: "Stable reference card for note-level reuse.",
    },
  ],
  markdown: [
    "# Reference brightfield stain workflow",
    "",
    "- Protocol ID: `protocol_20260322T213000Z_mock5678`",
    "- Source kind: `paper_derived`",
    "- Validation status: `verified_by_user`",
    "- Current version: `protver_brightfield_reference_v1`",
  ].join("\n"),
};

const MOCK_PROTOCOL_CARD_LIST_RESPONSE: ProtocolCardListResponse = {
  total: 2,
  items: [
    {
      protocol_id: MOCK_PROTOCOL_CARD_ID,
      title: "Primary cortical assay protocol",
      source_kind: "mixed",
      validation_status: "draft",
      updated_at: "2026-03-23T01:20:00Z",
      version_count: 2,
      current_version_id: "protver_cortical_assay_v2",
      linked_paper_count: 2,
      linked_note_count: 2,
    },
    {
      protocol_id: MOCK_SECONDARY_PROTOCOL_CARD_ID,
      title: "Reference brightfield stain workflow",
      source_kind: "paper_derived",
      validation_status: "verified_by_user",
      updated_at: "2026-03-22T21:45:00Z",
      version_count: 1,
      current_version_id: "protver_brightfield_reference_v1",
      linked_paper_count: 1,
      linked_note_count: 1,
    },
  ],
};

export function getMockHealth(): { status: string; version: string } {
  return { status: "ok", version: "mock-3.0" };
}

function paperNoteIdVariants(value?: string | null): string[] {
  const text = value?.trim() ?? "";
  if (!text) {
    return [];
  }

  const variants: string[] = [];
  const append = (candidate: string) => {
    const normalized = candidate.trim();
    if (normalized && !variants.includes(normalized)) {
      variants.push(normalized);
    }
  };

  append(text);
  append(text.replaceAll(":", ""));
  if (text.includes(":")) {
    const suffix = text.split(":", 2)[1]?.trim() ?? "";
    append(suffix);
    append(suffix.replaceAll(":", ""));
  } else if (text.startsWith("zotero")) {
    for (const candidate of expandPaperIdCandidates(text)) {
      append(candidate);
    }
  }

  return variants;
}

export function getMockPaperNotesIndex(params?: MockPaperNoteQuery): PaperNoteListResponse {
  const baseFiltered = filterMockPaperNotes({
    ...params,
    hasReadingAssist: false,
    readingAssistLocale: undefined,
  });
  const filtered = sortMockPaperNotes(filterMockPaperNotes(params), params);
  const pageSize = Math.max(1, Math.round(params?.pageSize ?? 30));
  const requestedPage = Math.max(1, Math.round(params?.page ?? 1));
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const page = Math.min(requestedPage, totalPages);
  const start = (page - 1) * pageSize;
  const availableTags = Array.from(new Set(MOCK_PAPER_NOTES.flatMap((note) => note.tags))).sort((left, right) => left.localeCompare(right));
  const availableStatuses = Array.from(new Set(MOCK_PAPER_NOTES.map((note) => note.status ?? "").filter((value) => value.length > 0))).sort((left, right) => left.localeCompare(right));
  const availableReadingAssistNoteCount = baseFiltered.filter(
    (note) => note.reading_assist_available === true || (note.reading_assist_locales?.length ?? 0) > 0,
  ).length;
  const availableReadingAssistLocales = Array.from(
    new Set(
      baseFiltered.flatMap((note) =>
        (note.reading_assist_locales ?? []).map((value) => value.trim().toLowerCase()).filter(Boolean),
      ),
    ),
  ).sort((left, right) => left.localeCompare(right));

  return {
    generated_at: new Date().toISOString(),
    index_path: "mock://paper_notes_index.json",
    total,
    page,
    page_size: pageSize,
    total_pages: totalPages,
    available_tags: availableTags,
    available_statuses: availableStatuses,
    available_reading_assist_note_count: availableReadingAssistNoteCount,
    available_reading_assist_locales: availableReadingAssistLocales,
    items: deepClone(filtered.slice(start, start + pageSize)),
  };
}

export function getMockCloudPapers(): CloudPaperListResponse {
  return {
    schema_version: "cloud_paper_list.v1",
    items: [
      buildMockCloudPaper("paper_mock_ready", "ready"),
      buildMockCloudPaper("paper_mock_running", "running"),
      buildMockCloudPaper("paper_mock_failed", "failed", { warningCode: "MOCK_FAILED" }),
    ],
  };
}

export function getMockCloudPaper(paperId: string): CloudPaperBundlePublic {
  const existing = getMockCloudPapers().items.find((item) => item.paper_id === paperId);
  if (existing) {
    return deepClone(existing);
  }
  return buildMockCloudPaper(paperId, "ready");
}

export function hydrateMockCloudPaper(paperId: string): CloudPaperHydrationState {
  return {
    status: "hydrated",
    device_id: null,
    local_bundle_ref: null,
    hydrated_at: new Date().toISOString(),
    source_pdf_sha256: "a".repeat(64),
    page_artifact_sha256: paperId.trim() ? "b".repeat(64) : null,
  };
}

export function getMockCloudPaperPage(paperId: string): CloudPaperPageArtifactPublic {
  return {
    schema_version: "cloud_page_artifact_public.v1",
    paper_id: paperId,
    run_id: `run_${paperId}`,
    page_schema_version: "cloud_page_artifact.v1",
    source_pdf_sha256: "a".repeat(64),
    blocks: [
      {
        block_id: "block_001",
        page: 1,
        kind: "text",
        text: "Mock processed page text for cloud paper API contract verification.",
        bbox_pct: { left: 0.1, top: 0.1, width: 0.8, height: 0.2 },
        payload_class: "local_only",
        metadata: { section: "abstract" },
      },
    ],
    warnings: [],
    provenance_summary: {
      uploaded_by: "mock_user",
      processor_name: "paperpipe-mock-cloud-page-worker",
      processor_version: "0.1.0",
      created_at: MOCK_CLOUD_PAPER_CREATED_AT,
      source_pdf_sha256: "a".repeat(64),
    },
  };
}

export function getMockCloudPaperDerivedArtifacts(paperId: string): CloudPaperDerivedArtifactsResponse {
  const sourcePdfSha256 = "a".repeat(64);
  const noDownstreamCandidates = paperId === "paper_mock_no_downstream_candidates";
  return {
    schema_version: "cloud_paper_derived_artifacts.v1",
    paper_id: paperId,
    run_id: `run_${paperId}`,
    source_pdf_sha256: sourcePdfSha256,
    payload_class: "local_only",
    ocr_blocks: [
      {
        ocr_block_id: "ocr_001",
        text: "Mock OCR text recovered from a rendered cloud PDF page.",
        confidence: 0.91,
        source: {
          page: 1,
          source_pdf_sha256: sourcePdfSha256,
          block_id: "block_001",
          bbox_pct: { left: 0.1, top: 0.1, width: 0.8, height: 0.2 },
        },
        payload_class: "local_only",
        metadata: { engine: "mock-ocr" },
      },
    ],
    tables: noDownstreamCandidates
      ? []
      : [
          {
            table_id: "table_001",
            page: 2,
            caption: "Mock reconstructed table from cloud PDF layout.",
            columns: ["Group", "N"],
            rows: [["Control", "10"], ["Treatment", "12"]],
            confidence: 0.82,
            source: { page: 2, source_pdf_sha256: sourcePdfSha256 },
            payload_class: "local_only",
            metadata: {},
          },
        ],
    figures: noDownstreamCandidates
      ? []
      : [
          {
            figure_id: "figure_001",
            page: 3,
            caption: "Mock figure crop from rendered cloud PDF page.",
            bbox_pct: { left: 0.1, top: 0.1, width: 0.7, height: 0.5 },
            image_available: true,
            image_route: `/api/cloud/papers/${paperId}/figures/figure_001/image`,
            confidence: 0.77,
            source: { page: 3, source_pdf_sha256: sourcePdfSha256 },
            payload_class: "local_only",
            metadata: {},
          },
        ],
    figure_analyses: noDownstreamCandidates
      ? []
      : [
          {
            analysis_id: "figure_analysis_001",
            figure_id: "figure_001",
            page: 3,
            summary: "Mock figure analysis placeholder derived from a server-side figure crop.",
            confidence: 0.7,
            source: { page: 3, source_pdf_sha256: sourcePdfSha256 },
            payload_class: "local_only",
            metadata: {},
          },
        ],
    warnings: [],
    provenance_summary: {
      uploaded_by: "mock_user",
      processor_name: "paperpipe-mock-derived-artifact-worker",
      processor_version: "0.1.0",
      created_at: MOCK_CLOUD_PAPER_CREATED_AT,
      source_pdf_sha256: sourcePdfSha256,
    },
  };
}

export function getMockCloudPaperDownstreamHandoff(paperId: string): CloudPaperDownstreamHandoffSummary {
  const derived = getMockCloudPaperDerivedArtifacts(paperId);
  const provenance = derived.provenance_summary;
  const tableArtifact = derived.tables[0] ?? null;
  const figureArtifact = derived.figures[0] ?? null;
  const figureAnalysis = derived.figure_analyses[0] ?? null;
  const candidates: CloudPaperDownstreamArtifactCandidate[] = [
    {
      candidate_id: "ocr_001",
      kind: "ocr_text",
      paper_id: derived.paper_id,
      run_id: derived.run_id,
      payload_class: derived.payload_class,
      canonical_status: "derived_noncanonical",
      allowed_lanes: ["meeting_pack", "method_comparison", "obsidian_export"],
      source: derived.ocr_blocks[0].source,
      title: "OCR block ocr_001",
      text: derived.ocr_blocks[0].text,
      table_columns: [],
      table_rows: [],
      confidence: derived.ocr_blocks[0].confidence,
      provenance_summary: provenance,
    },
  ];
  if (tableArtifact) {
    candidates.push({
      candidate_id: tableArtifact.table_id,
      kind: "table",
      paper_id: derived.paper_id,
      run_id: derived.run_id,
      payload_class: derived.payload_class,
      canonical_status: "derived_noncanonical",
      allowed_lanes: ["chart_pack", "meeting_pack", "method_comparison", "obsidian_export"],
      source: tableArtifact.source,
      title: tableArtifact.caption ?? `Table ${tableArtifact.table_id}`,
      text: tableArtifact.caption,
      table_columns: tableArtifact.columns,
      table_rows: tableArtifact.rows,
      confidence: tableArtifact.confidence,
      provenance_summary: provenance,
    });
  }
  if (figureArtifact) {
    candidates.push({
      candidate_id: figureArtifact.figure_id,
      kind: "figure",
      paper_id: derived.paper_id,
      run_id: derived.run_id,
      payload_class: derived.payload_class,
      canonical_status: "derived_noncanonical",
      allowed_lanes: ["image_evidence", "meeting_pack", "obsidian_export"],
      source: figureArtifact.source,
      title: figureArtifact.caption ?? `Figure ${figureArtifact.figure_id}`,
      text: figureArtifact.caption,
      table_columns: [],
      table_rows: [],
      image_route: figureArtifact.image_route,
      confidence: figureArtifact.confidence,
      provenance_summary: provenance,
    });
  }
  if (figureAnalysis && figureArtifact) {
    candidates.push({
      candidate_id: figureAnalysis.analysis_id,
      kind: "figure_analysis",
      paper_id: derived.paper_id,
      run_id: derived.run_id,
      payload_class: derived.payload_class,
      canonical_status: "derived_noncanonical",
      allowed_lanes: ["image_evidence", "meeting_pack", "obsidian_export"],
      source: figureAnalysis.source,
      title: `Analysis for ${figureAnalysis.figure_id}`,
      text: figureAnalysis.summary,
      table_columns: [],
      table_rows: [],
      image_route: figureArtifact.image_route,
      confidence: figureAnalysis.confidence,
      provenance_summary: provenance,
    });
  }
  const selectedTableCandidate = candidates.find((candidate) => candidate.kind === "table") ?? null;
  const selectedFigureCandidate = candidates.find((candidate) => candidate.kind === "figure") ?? null;
  return {
    downstream_adapter: {
      schema_version: "cloud_paper_downstream_adapter.v1",
      paper_id: derived.paper_id,
      run_id: derived.run_id,
      source_pdf_sha256: derived.source_pdf_sha256,
      payload_class: derived.payload_class,
      candidates,
      warnings: [],
      provenance_summary: provenance,
    },
    selected_table_candidate: selectedTableCandidate,
    selected_figure_candidate: selectedFigureCandidate,
    meeting_pack_context: {
      schema_version: "meeting_pack_cloud_derived_context.v1",
      readiness: "background_only",
      items: [
        { support_type: "background", canonical_status: "derived_noncanonical", evidence_refs: [] },
        { support_type: "background", canonical_status: "derived_noncanonical", evidence_refs: [] },
      ],
    },
    chart_table_snapshot: selectedTableCandidate
      ? {
          source_ref: { source_kind: "cloud_derived_table", table_id: selectedTableCandidate.candidate_id },
          rows: [{ Group: "Control", N: 10 }, { Group: "Treatment", N: 12 }],
          warnings: [
            {
              code: "cloud_derived_noncanonical",
              severity: "warning",
              message: "This chart snapshot is derived from server-side table reconstruction, not canonical structured evidence.",
            },
          ],
        }
      : null,
    image_evidence_request: selectedFigureCandidate
      ? {
          source_ref: {
            source_kind: "external_image_ref",
            external_ref: `/api/cloud/papers/${paperId}/figures/${selectedFigureCandidate.candidate_id}/image`,
            local_path: null,
          },
          linked_claim_refs: [],
          warnings: [
            {
              code: "cloud_derived_noncanonical",
              severity: "warning",
              message: "This Image Evidence request uses a cloud-derived figure crop, not canonical structured evidence.",
            },
          ],
        }
      : null,
    method_comparison_context: {
      schema_version: "method_comparison_cloud_derived_context.v1",
      readiness: "background_only",
      items: [
        { comparison_cell_status: "missing", canonical_status: "derived_noncanonical", evidence_refs: [] },
        { comparison_cell_status: "missing", canonical_status: "derived_noncanonical", evidence_refs: [] },
      ],
    },
    obsidian_section_markdown: [
      `<!-- paperpipe:cloud-derived:start paper_id=${paperId} run_id=run_${paperId} -->`,
      "## Cloud-Derived Context",
      "- Canonical status: derived_noncanonical",
      "<!-- paperpipe:cloud-derived:end -->",
    ].join("\n"),
  };
}

export function prepareMockCloudPaperObsidianExport(
  paperId: string,
  existingMarkdown = "",
): CloudPaperObsidianExportResponse {
  const handoff = getMockCloudPaperDownstreamHandoff(paperId);
  const sectionMarkdown = handoff.obsidian_section_markdown.trim() + "\n";
  const noteMarkdown = replaceMockCloudDerivedSection(existingMarkdown, sectionMarkdown);
  return {
    schema_version: "cloud_paper_obsidian_export.v1",
    paper_id: paperId,
    run_id: handoff.downstream_adapter.run_id,
    artifact_id: `cloud_obsidian_export_${paperId}`,
    export_status: "prepared",
    canonical_status: "derived_noncanonical",
    review_status: "review_pending",
    source_pdf_sha256: handoff.downstream_adapter.source_pdf_sha256,
    payload_class: handoff.downstream_adapter.payload_class,
    section_markers: {
      start: sectionMarkdown.split("\n")[0],
      end: "<!-- paperpipe:cloud-derived:end -->",
    },
    section_markdown: sectionMarkdown,
    note_markdown: noteMarkdown,
    warnings: [],
    provenance_summary: handoff.downstream_adapter.provenance_summary,
  };
}

export function registerMockCloudPaperDownstreamArtifacts(
  paperId: string,
  lanes: CloudPaperDownstreamLane[] = ["meeting_pack", "chart_pack", "image_evidence", "method_comparison", "obsidian_export"],
): CloudPaperDownstreamArtifactRegistrationResponse {
  const handoff = getMockCloudPaperDownstreamHandoff(paperId);
  const registered_artifacts = lanes
    .map((lane) => {
      const candidateIds = handoff.downstream_adapter.candidates
        .filter((candidate) => candidate.allowed_lanes.includes(lane))
        .map((candidate) => candidate.candidate_id);
      if (candidateIds.length === 0) {
        return null;
      }
      return {
        artifact_id: `cloud_downstream_${lane}_${paperId}`,
        lane,
        candidate_ids: candidateIds,
        candidate_count: candidateIds.length,
        canonical_status: "derived_noncanonical" as const,
        review_status: "review_pending" as const,
        review_events: [],
        source_pdf_sha256: handoff.downstream_adapter.source_pdf_sha256,
        payload_class: handoff.downstream_adapter.payload_class,
      };
    })
    .filter((artifact): artifact is NonNullable<typeof artifact> => artifact !== null);

  return {
    schema_version: "cloud_paper_downstream_artifact_registration.v1",
    paper_id: paperId,
    run_id: handoff.downstream_adapter.run_id,
    registration_status: "registered",
    canonical_status: "derived_noncanonical",
    review_status: "review_pending",
    source_pdf_sha256: handoff.downstream_adapter.source_pdf_sha256,
    payload_class: handoff.downstream_adapter.payload_class,
    registered_artifacts,
    warnings: [],
    provenance_summary: handoff.downstream_adapter.provenance_summary,
  };
}

export function getMockCloudPaperDownstreamArtifactRegistry(
  paperId: string,
  registration?: CloudPaperDownstreamArtifactRegistrationResponse | null,
): CloudPaperDownstreamArtifactRegistryResponse {
  const handoff = getMockCloudPaperDownstreamHandoff(paperId);
  const registrations =
    registration
      ? [registration]
      : paperId === "paper_mock_promotion_ready"
        ? [reviewAllRegistrationArtifacts(registerMockCloudPaperDownstreamArtifacts(paperId), "review_approved")]
      : paperId === "paper_mock_reviewed"
        ? [reviewRegistrationArtifact(registerMockCloudPaperDownstreamArtifacts(paperId), "review_approved")]
        : [];
  return {
    schema_version: "cloud_paper_downstream_artifact_registry.v1",
    paper_id: paperId,
    run_id: handoff.downstream_adapter.run_id,
    registry_status: registrations.length > 0 ? "available" : "empty",
    canonical_status: "derived_noncanonical",
    review_status: aggregateMockRegistrationReviewStatus(registrations),
    source_pdf_sha256: handoff.downstream_adapter.source_pdf_sha256,
    payload_class: handoff.downstream_adapter.payload_class,
    registrations,
    warnings: [],
    provenance_summary: handoff.downstream_adapter.provenance_summary,
  };
}

export function getMockCloudPaperDownstreamPromotionReadiness(
  paperId: string,
  registry?: CloudPaperDownstreamArtifactRegistryResponse | null,
): CloudPaperDownstreamPromotionReadinessResponse {
  const resolvedRegistry = registry ?? getMockCloudPaperDownstreamArtifactRegistry(paperId);
  const artifacts = resolvedRegistry.registrations.flatMap((registration) => registration.registered_artifacts);
  const blockers: CloudPaperDownstreamPromotionReadinessResponse["blockers"] = [];
  for (const artifact of artifacts) {
    if (artifact.review_status === "review_pending") {
      blockers.push({
        code: "review_pending",
        message: "Registered downstream artifact is still pending review.",
        artifact_id: artifact.artifact_id,
        lane: artifact.lane,
      });
    }
    if (artifact.review_status === "review_rejected") {
      blockers.push({
        code: "review_rejected",
        message: "Registered downstream artifact was rejected during review.",
        artifact_id: artifact.artifact_id,
        lane: artifact.lane,
      });
    }
  }
  if (artifacts.length === 0) {
    blockers.push({
      code: "registry_empty",
      message: "No registered downstream artifacts are available for promotion review.",
      artifact_id: null,
      lane: null,
    });
  }
  const approvedArtifactCount = artifacts.filter((artifact) => artifact.review_status === "review_approved").length;
  const pendingArtifactCount = artifacts.filter((artifact) => artifact.review_status === "review_pending").length;
  const rejectedArtifactCount = artifacts.filter((artifact) => artifact.review_status === "review_rejected").length;
  const eligible = artifacts.length > 0 && blockers.length === 0;
  return {
    schema_version: "cloud_paper_downstream_promotion_readiness.v1",
    paper_id: resolvedRegistry.paper_id,
    run_id: resolvedRegistry.run_id,
    promotion_status: eligible ? "eligible" : "blocked",
    eligible,
    canonical_status: "derived_noncanonical",
    review_status: resolvedRegistry.review_status,
    total_artifact_count: artifacts.length,
    approved_artifact_count: approvedArtifactCount,
    pending_artifact_count: pendingArtifactCount,
    rejected_artifact_count: rejectedArtifactCount,
    blockers,
    source_pdf_sha256: resolvedRegistry.source_pdf_sha256,
    payload_class: resolvedRegistry.payload_class,
    warnings: resolvedRegistry.warnings,
    provenance_summary: resolvedRegistry.provenance_summary,
  };
}

export function getMockCloudPaperDownstreamPromotionPlan(
  paperId: string,
  registry?: CloudPaperDownstreamArtifactRegistryResponse | null,
): CloudPaperDownstreamPromotionPlanResponse {
  const resolvedRegistry = registry ?? getMockCloudPaperDownstreamArtifactRegistry(paperId);
  const readiness = getMockCloudPaperDownstreamPromotionReadiness(paperId, resolvedRegistry);
  const artifacts = resolvedRegistry.registrations.flatMap((registration) => registration.registered_artifacts);
  return {
    schema_version: "cloud_paper_downstream_promotion_plan.v1",
    paper_id: resolvedRegistry.paper_id,
    run_id: resolvedRegistry.run_id,
    plan_status: readiness.eligible ? "ready" : "blocked",
    dry_run: true,
    mutation_applied: false,
    promotion_target: "canonical_structured_state",
    canonical_status: "derived_noncanonical",
    review_status: resolvedRegistry.review_status,
    total_artifact_count: readiness.total_artifact_count,
    approved_artifact_count: readiness.approved_artifact_count,
    pending_artifact_count: readiness.pending_artifact_count,
    rejected_artifact_count: readiness.rejected_artifact_count,
    blockers: readiness.blockers,
    promotion_items: readiness.eligible
      ? artifacts
          .filter((artifact) => artifact.review_status === "review_approved")
          .map((artifact) => ({
            artifact_id: artifact.artifact_id,
            lane: artifact.lane,
            candidate_ids: artifact.candidate_ids,
            candidate_count: artifact.candidate_count,
            review_status: "review_approved" as const,
            canonical_status: "derived_noncanonical" as const,
            promotion_action: "prepare_canonical_state_promotion" as const,
            source_pdf_sha256: artifact.source_pdf_sha256,
            payload_class: artifact.payload_class,
          }))
      : [],
    source_pdf_sha256: resolvedRegistry.source_pdf_sha256,
    payload_class: resolvedRegistry.payload_class,
    warnings: resolvedRegistry.warnings,
    provenance_summary: resolvedRegistry.provenance_summary,
  };
}

export function reviewMockCloudPaperDownstreamArtifact(
  paperId: string,
  artifactId: string,
  reviewStatus: Exclude<CloudPaperDownstreamReviewStatus, "review_pending">,
): CloudPaperDownstreamArtifactRegistryResponse {
  const registry = getMockCloudPaperDownstreamArtifactRegistry(paperId, registerMockCloudPaperDownstreamArtifacts(paperId));
  const registrations = registry.registrations.map((registration) => {
    const registered_artifacts = registration.registered_artifacts.map((artifact) =>
      artifact.artifact_id === artifactId
        ? {
            ...artifact,
            review_status: reviewStatus,
            review_events: [...artifact.review_events, mockReviewEvent(artifact.artifact_id, reviewStatus)],
          }
        : artifact,
    );
    return {
      ...registration,
      registered_artifacts,
      review_status: aggregateMockArtifactReviewStatus(registered_artifacts),
    };
  });
  return {
    ...registry,
    review_status: aggregateMockRegistrationReviewStatus(registrations),
    registrations,
  };
}

function reviewRegistrationArtifact(
  registration: CloudPaperDownstreamArtifactRegistrationResponse,
  reviewStatus: Exclude<CloudPaperDownstreamReviewStatus, "review_pending">,
): CloudPaperDownstreamArtifactRegistrationResponse {
  const firstArtifactId = registration.registered_artifacts[0]?.artifact_id ?? null;
  if (!firstArtifactId) {
    return registration;
  }
  const registered_artifacts = registration.registered_artifacts.map((artifact) =>
    artifact.artifact_id === firstArtifactId
      ? {
          ...artifact,
          review_status: reviewStatus,
          review_events: [...artifact.review_events, mockReviewEvent(artifact.artifact_id, reviewStatus)],
        }
      : artifact,
  );
  return {
    ...registration,
    registered_artifacts,
    review_status: aggregateMockArtifactReviewStatus(registered_artifacts),
  };
}

function reviewAllRegistrationArtifacts(
  registration: CloudPaperDownstreamArtifactRegistrationResponse,
  reviewStatus: Exclude<CloudPaperDownstreamReviewStatus, "review_pending">,
): CloudPaperDownstreamArtifactRegistrationResponse {
  const registered_artifacts = registration.registered_artifacts.map((artifact) => ({
    ...artifact,
    review_status: reviewStatus,
    review_events: [...artifact.review_events, mockReviewEvent(artifact.artifact_id, reviewStatus)],
  }));
  return {
    ...registration,
    registered_artifacts,
    review_status: aggregateMockArtifactReviewStatus(registered_artifacts),
  };
}

function mockReviewEvent(
  artifactId: string,
  reviewStatus: Exclude<CloudPaperDownstreamReviewStatus, "review_pending">,
) {
  return {
    event_id: `cloud_downstream_review_${artifactId}`,
    artifact_id: artifactId,
    review_status: reviewStatus,
    reviewer_role: "maintainer" as const,
    reviewed_at: "2026-06-03T00:00:00.000Z",
    reviewer_note_recorded: true,
  };
}

function aggregateMockRegistrationReviewStatus(
  registrations: CloudPaperDownstreamArtifactRegistrationResponse[],
): CloudPaperDownstreamReviewStatus {
  return aggregateMockArtifactReviewStatus(registrations.flatMap((registration) => registration.registered_artifacts));
}

function aggregateMockArtifactReviewStatus(
  artifacts: Array<{ review_status: CloudPaperDownstreamReviewStatus }>,
): CloudPaperDownstreamReviewStatus {
  const statuses = new Set(artifacts.map((artifact) => artifact.review_status));
  if (statuses.size === 0 || statuses.has("review_pending")) {
    return "review_pending";
  }
  if (statuses.has("review_rejected")) {
    return "review_rejected";
  }
  return "review_approved";
}

function replaceMockCloudDerivedSection(existingMarkdown: string, sectionMarkdown: string): string {
  const section = sectionMarkdown.trim();
  const existing = existingMarkdown.trim();
  if (!existing) {
    return `${section}\n`;
  }
  const startPrefix = "<!-- paperpipe:cloud-derived:start ";
  const endMarker = "<!-- paperpipe:cloud-derived:end -->";
  const startIndex = existing.indexOf(startPrefix);
  const endIndex = startIndex >= 0 ? existing.indexOf(endMarker, startIndex) : -1;
  if (startIndex < 0 || endIndex < 0) {
    return `${existing}\n\n${section}\n`;
  }
  const prefix = existing.slice(0, startIndex).trim();
  const suffix = existing.slice(endIndex + endMarker.length).trim();
  return [prefix, section, suffix].filter(Boolean).join("\n\n") + "\n";
}

function mockCloudSearchTerms(query: string): string[] {
  return query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
}

export function searchMockCloudPapers(query: string): CloudPaperSearchResponse {
  const cleanedQuery = query.trim();
  const terms = mockCloudSearchTerms(cleanedQuery);
  if (terms.length === 0) {
    return {
      schema_version: "cloud_paper_search.v1",
      query: cleanedQuery,
      items: [],
    };
  }

  const items = getMockCloudPapers().items
    .filter((bundle) => bundle.processing_status === "ready" && bundle.allowed_actions.includes("read_page"))
    .map((bundle) => {
      const page = getMockCloudPaperPage(bundle.paper_id);
      const matched_blocks = page.blocks
        .filter((block) => terms.every((term) => (block.text ?? "").toLowerCase().includes(term)))
        .map((block) => ({
          block_id: block.block_id,
          page: block.page,
          kind: block.kind,
          text_snippet: block.text ?? "",
          payload_class: block.payload_class,
          metadata: block.metadata,
        }));
      return { bundle, matched_blocks };
    })
    .filter((item) => item.matched_blocks.length > 0);

  return {
    schema_version: "cloud_paper_search.v1",
    query: cleanedQuery,
    items,
  };
}

export function getMockPaperNotesHomeContext(): PaperNotesHomeContext {
  const noteSlugByPaperId: Record<string, string> = {};
  const triageCounts = {
    revisit: 0,
    needs_verification: 0,
    experiment_relevant: 0,
  };
  let markedPapers = 0;
  let noteBackedPapers = 0;
  let starred = 0;
  for (const note of MOCK_PAPER_NOTES) {
    for (const candidate of [note.id, note.slug]) {
      for (const variant of paperNoteIdVariants(candidate)) {
        if (!(variant in noteSlugByPaperId)) {
          noteSlugByPaperId[variant] = note.slug;
        }
      }
    }
    const noteStarred = note.starred === true;
    const hasOperatorNote = note.has_operator_note === true;
    const triageLabels = note.triage_labels ?? [];
    if (noteStarred) {
      starred += 1;
    }
    if (hasOperatorNote) {
      noteBackedPapers += 1;
    }
    if (noteStarred || hasOperatorNote || triageLabels.length > 0) {
      markedPapers += 1;
    }
    for (const label of triageLabels) {
      triageCounts[label] += 1;
    }
  }

  const latestNoteUpdatedAt = [...MOCK_PAPER_NOTES]
    .map((note) => note.updated_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => Date.parse(right) - Date.parse(left))[0] ?? null;

  return {
    saved_notes: MOCK_PAPER_NOTES.length,
    structured_notes: MOCK_PAPER_NOTES.filter((note) => note.structured_state_present === true).length,
    latest_note_updated_at: latestNoteUpdatedAt,
    note_context_limited: false,
    note_slug_by_paper_id: noteSlugByPaperId,
    marker_summary: {
      marked_papers: markedPapers,
      note_backed_papers: noteBackedPapers,
      starred,
      triage_counts: triageCounts,
    },
  };
}

export function getMockPaperNoteDetail(
  slug: string,
  _options?: { readingAssistLocale?: string | null },
): PaperNoteDetailResponse {
  const note = MOCK_PAPER_NOTES.find((item) => item.slug === slug) ?? null;
  const storedDetail = MOCK_PAPER_NOTE_DETAILS[slug];
  const requiresDynamicReadingAssist =
    note?.slug === "adaptiveInterventionSignalsAmbiguous2026" && ((note.reading_assist_locales?.length ?? 0) > 1 || Boolean(_options?.readingAssistLocale));
  if (note && requiresDynamicReadingAssist) {
    const builtDetail = buildMockPaperNoteDetail(note, _options);
    return deepClone({
      ...builtDetail,
      operator_state: storedDetail?.operator_state ?? builtDetail.operator_state,
    });
  }
  return deepClone(
    note
      ? storedDetail ?? buildMockPaperNoteDetail(note, _options)
      : storedDetail ?? buildMockPaperNoteDetail(buildFallbackPaperNoteSummary(slug), _options),
  );
}

export function getMockPaperNoteOperatorState(slug: string): PaperNoteOperatorState {
  const detail = MOCK_PAPER_NOTE_DETAILS[slug];
  if (detail?.operator_state) {
    return deepClone(detail.operator_state);
  }
  return deepClone(buildMockPaperOperatorState(buildFallbackPaperNoteSummary(slug)));
}

export function updateMockPaperNoteOperatorState(
  slug: string,
  payload: PaperNoteOperatorStateUpdateRequest,
): PaperNoteOperatorState {
  const note = MOCK_PAPER_NOTES.find((item) => item.slug === slug) ?? null;
  const existingState =
    MOCK_PAPER_NOTE_DETAILS[slug]?.operator_state ??
    (note ? buildMockPaperOperatorState(note) : buildMockPaperOperatorState(buildFallbackPaperNoteSummary(slug)));
  const updatedAt = new Date().toISOString();
  const paperNoteText = hasPaperOperatorNoteText(payload.paper_note_text) ? String(payload.paper_note_text).trim() : null;
  const nextState: PaperNoteOperatorState = {
    ...existingState,
    paper_note_text: paperNoteText,
    starred: payload.starred === true,
    triage_labels: [...payload.triage_labels],
    created_at: existingState.created_at ?? updatedAt,
    updated_at: updatedAt,
  };

  if (note) {
    note.starred = nextState.starred;
    note.triage_labels = [...nextState.triage_labels];
    note.has_operator_note = hasPaperOperatorNoteText(nextState.paper_note_text);
    MOCK_PAPER_NOTE_DETAILS[slug] = {
      ...buildMockPaperNoteDetail(note),
      operator_state: nextState,
    };
  }

  return deepClone(nextState);
}

export function getMockPaperNoteStructuredStateByPaperId(paperId: string) {
  const note = MOCK_PAPER_NOTES.find((item) => item.id === paperId) ?? null;
  if (!note || !note.structured_state_present) {
    return null;
  }
  return {
    paper_id: paperId,
    slug: note.slug,
    note_path: note.note_path,
    structured_state: buildMockStructuredState(note),
    operator_state: getMockPaperNoteOperatorState(note.slug),
  };
}

export function getMockPapers(): PaperSummary[] {
  return deepClone(MOCK_PAPERS);
}

export function getMockPaper(paperId: string): PaperDetail {
  return deepClone(MOCK_PAPERS.find((paper) => paper.paper_id === paperId) ?? MOCK_PAPERS[0]);
}

export function getMockJobs(paperId: string): JobStatus[] {
  return deepClone(MOCK_JOBS[paperId] ?? []);
}

export function getMockJob(jobId: string): JobStatus {
  for (const jobs of Object.values(MOCK_JOBS)) {
    const job = jobs.find((item) => item.job_id === jobId);
    if (job) {
      return deepClone(job);
    }
  }
  return {
    job_id: jobId,
    paper_id: MOCK_PAPERS[0].paper_id,
    run_id: "run-mock-live",
    status: "running",
    progress: 10,
    stage: "ingest",
    created_at: new Date().toISOString(),
  };
}

export function getMockPersonas(): PersonaListResponse {
  return {
    personas: [
      {
        id: "default",
        title: "Default (No Persona Override)",
        enabled: true,
        kind: "compatibility",
        source: "builtin",
        notes: "Compatibility alias. Prefer explicit reasoning persona and profile context in new clients.",
      },
      {
        id: "librarian",
        title: "Librarian",
        enabled: true,
        kind: "reasoning_persona",
        source: "builtin",
        notes: "Search-first intake with source coverage and retrieval-gap tracking.",
      },
      {
        id: "researcher",
        title: "Researcher",
        enabled: true,
        kind: "reasoning_persona",
        source: "builtin",
        notes: "Interpretive synthesis with mechanism and uncertainty made explicit.",
      },
      {
        id: "extractor_reviewer",
        title: "Extractor / Reviewer",
        enabled: true,
        kind: "reasoning_persona",
        source: "builtin",
        notes: "Structured extraction and conservative evidence review.",
      },
      {
        id: "coglab",
        title: "Cognitive Lab",
        enabled: true,
        kind: "profile",
        source: "yaml",
        notes: "Memory/confound-focused profile overlay.",
      },
      {
        id: "metabolism_review",
        title: "Metabolism Review",
        enabled: true,
        kind: "profile",
        source: "yaml",
        notes: "Metabolic outcomes and intervention-effect context.",
      },
    ],
  };
}

export function getMockArtifactsLatest(paperId: string): ArtifactBundle {
  const paper = MOCK_PAPERS.find((item) => item.paper_id === paperId) ?? MOCK_PAPERS[0];
  const runId = paper.latest_run_id ?? "run-mock";
  const notebook = NOTEBOOK_BY_PAPER[paper.paper_id] ?? PLACEHOLDER_NOTEBOOK;
  return deepClone(toArtifactBundle(paper.paper_id, runId, notebook));
}

function toMockObsidianMarkdown(notebook: NotebookArtifact): string {
  const lines: string[] = [];
  lines.push("<!-- AI_AGENT_START -->");
  lines.push("## 🤖 PaperPipe AI Analysis");
  lines.push(`### 🧪 Scientific Claims (${notebook.claims.length})`);
  for (const claim of notebook.claims.slice(0, 6)) {
    lines.push(`- ${claim.text}`);
  }
  lines.push("### 📊 Statistical Verification");
  lines.push(`- Verdict: ${notebook.verdict.label} (${notebook.verdict.level})`);
  lines.push("<!-- AI_AGENT_END -->");
  return lines.join("\n");
}

export function getMockObsidianMirror(paperId: string, runId: string): ObsidianMirror {
  const notebook = NOTEBOOK_BY_PAPER[paperId] ?? PLACEHOLDER_NOTEBOOK;
  const generated = toMockObsidianMarkdown(notebook);
  if (paperId === "paper-2026-ambiguous") {
    return {
      paper_id: paperId,
      run_id: runId,
      generated_markdown: generated,
      has_claimset: true,
      has_stats_report: true,
      claims: notebook.claims.map((claim) => ({
        claim_id: claim.claim_id,
        claim_type: "evidence",
        statement: claim.text,
        confidence: claim.confidence === "high" ? 0.9 : claim.confidence === "medium" ? 0.65 : 0.35,
        evidence_quote: undefined,
        evidence_page: claim.claim_id === "claim-1" ? 1 : undefined,
        evidence_grounded: claim.claim_id === "claim-1" ? true : null,
        evidence_resolution: claim.claim_id === "claim-1" ? "OK" : null,
        limitations: [],
      })),
      stats_checks: [
        {
          check_id: "mock-check-1",
          test_type: "consistency",
          verdict: "verified",
          claim_id: "claim-1",
          evidence_page: 1,
          evidence_grounded: true,
          evidence_resolution: "OK",
          hypothesis: "Primary intervention consistency",
          notes: "Early window response aligns with anchored statement.",
          decision_error: false,
        },
        {
          check_id: "mock-check-2",
          test_type: "effect-size-disambiguation",
          verdict: "verified",
          claim_id: null,
          evidence_page: 1,
          evidence_grounded: false,
          evidence_resolution: "AMBIGUOUS_MATCH",
          hypothesis: "Effect size remained moderate after subgroup split adjustment",
          notes: "Use subgroup split signal to map to effect-size claim even when page hint overlaps.",
          decision_error: false,
        },
      ],
    };
  }
  const firstClaimId = notebook.claims[0]?.claim_id ?? "claim-1";
  const secondClaimId = notebook.claims[1]?.claim_id ?? firstClaimId;
  const firstPage = notebook.highlights.find((item) => item.claim_id === firstClaimId)?.page ?? 1;
  const secondPage = notebook.highlights.find((item) => item.claim_id === secondClaimId)?.page ?? firstPage;
  return {
    paper_id: paperId,
    run_id: runId,
    generated_markdown: generated,
    has_claimset: notebook.claims.length > 0,
    has_stats_report: true,
    claims: notebook.claims.map((claim) => ({
      claim_id: claim.claim_id,
      claim_type: "evidence",
      statement: claim.text,
      confidence: claim.confidence === "high" ? 0.9 : claim.confidence === "medium" ? 0.65 : 0.35,
      evidence_quote: undefined,
      evidence_page: undefined,
      limitations: [],
    })),
    stats_checks: [
      {
        check_id: "mock-check-1",
        test_type: "consistency",
        verdict: notebook.verdict.level === "fail" ? "inconsistent" : "verified",
        claim_id: firstClaimId,
        evidence_page: firstPage,
        hypothesis: "Primary summary consistency",
        notes: notebook.verdict.detail,
        decision_error: notebook.verdict.level === "fail",
      },
      {
        check_id: "mock-check-2",
        test_type: "effect-size",
        verdict: "verified",
        claim_id: secondClaimId,
        evidence_page: secondPage,
        hypothesis: "Secondary effect size plausibility",
        notes: "Effect size direction preserved across subgroup split.",
        decision_error: false,
      },
    ],
  };
}

export function getMockTimeline(runId: string): TimelineResponse {
  const fallback = MOCK_TIMELINES["run-001"];
  return deepClone(MOCK_TIMELINES[runId] ?? fallback);
}

export function getMockMeetingPack(packId: string): MeetingPackResponse {
  const generated = MOCK_GENERATED_MEETING_PACKS.get(packId);
  if (generated) {
    return deepClone(generated);
  }
  const response = deepClone(MOCK_MEETING_PACK_RESPONSE);
  response.pack.id = packId || MOCK_MEETING_PACK_ID;
  return response;
}

export function getMockMeetingPackIndex(): MeetingPackListResponse {
  const generatedItems = MOCK_GENERATED_MEETING_PACK_ORDER
    .map((packId) => MOCK_GENERATED_MEETING_PACKS.get(packId))
    .filter((response): response is MeetingPackResponse => Boolean(response))
    .map((response) => buildMeetingPackListItem(response));
  const base = deepClone(MOCK_MEETING_PACK_LIST_RESPONSE);
  return {
    ...base,
    total: generatedItems.length + base.items.length,
    items: [...generatedItems, ...base.items],
  };
}

export function getMockMeetingPackTrace(packId: string): MeetingPackTraceResponse {
  const generated = MOCK_GENERATED_MEETING_PACKS.get(packId);
  if (generated) {
    return buildMeetingPackTraceResponse(generated);
  }
  const response = deepClone(MOCK_MEETING_PACK_TRACE_RESPONSE);
  response.pack_id = packId || MOCK_MEETING_PACK_ID;
  return response;
}

export function getMockMeetingPackValidation(packId: string): MeetingPackValidationResponse {
  const generated = MOCK_GENERATED_MEETING_PACKS.get(packId);
  if (generated) {
    return buildMeetingPackValidationResponse(generated);
  }
  const response = deepClone(MOCK_MEETING_PACK_VALIDATION_RESPONSE);
  response.validation.pack_id = packId || MOCK_MEETING_PACK_ID;
  return response;
}

export function createMockMeetingPack(request: MeetingPackRequestSnapshot): MeetingPackResponse {
  const response = deepClone(MOCK_MEETING_PACK_RESPONSE);
  const now = new Date();
  const sourceRef = request.source_items[0]?.ref?.trim() || "paper-slug";
  const packId = buildMockMeetingPackId(request.mode);
  const normalizedRequestTitle = normalizeRequestedMeetingPackTitle(request.title, sourceRef);
  const title = normalizedRequestTitle || `${formatMeetingPackModeLabel(request.mode)} draft for ${sourceRef}`;

  response.pack.id = packId;
  response.pack.mode = request.mode;
  response.pack.output_mode_family = outputModeFamilyForMeetingPackMode(request.mode);
  response.pack.title = title;
  response.pack.created_at = now.toISOString();
  response.pack.readiness = "evidence_backed";
  response.pack.generation_request = deepClone(request);
  response.pack.generation_request.title = normalizedRequestTitle;
  response.pack.regenerated_from_pack_id = null;
  response.pack.source_items = request.source_items.map((item, index) => ({
    id: `src_${String(index + 1).padStart(2, "0")}`,
    type: item.type,
    ref: item.ref,
    title: item.ref,
    priority: index + 1,
    included: true,
  }));
  response.pack.retrieval_trace = request.source_items.flatMap((item, index) => {
    const sourceItemId = `src_${String(index + 1).padStart(2, "0")}`;
    return [
      {
        order: index * 2 + 1,
        selector_type: item.type,
        selector_ref: item.ref,
        action: "selector_selected",
        outcome: "selected",
        detail: "Selector accepted for draft generation.",
        source_item_id: sourceItemId,
        source_path: null,
        matched_paper_slugs: [],
        metadata: {},
      },
      {
        order: index * 2 + 2,
        selector_type: item.type,
        selector_ref: item.ref,
        action: item.type === "paper_slug" ? "paper_state_loaded" : "selector_resolved",
        outcome: item.type === "paper_slug" ? "loaded" : "resolved",
        detail:
          item.type === "paper_slug"
            ? "Loaded the selected paper slug into the draft."
            : "Resolved selector context for the draft.",
        source_item_id: sourceItemId,
        source_path: item.type === "paper_slug" ? `.pp/${item.ref}/state.json` : item.ref,
        matched_paper_slugs: item.type === "paper_slug" ? [item.ref] : [],
        metadata: {},
      },
    ];
  });
  response.pack.one_page_summary.overview = `This mock meeting draft starts from ${sourceRef} so you can inspect the full pack flow before the live backend is available.`;
  response.pack.one_page_summary.key_points = [
    {
      label: "Starting point",
      text: `The draft was created from the paper slug ${sourceRef}. Replace this with a live paper slug to generate a real pack.`,
      evidence_refs: ["evref_01"],
      uncertainty_note: "Mock generation keeps the workflow shape but not the final scientific content.",
    },
  ];
  response.pack.one_page_summary.uncertainties = [
    "This is mock-generated draft content for workflow review.",
  ];
  response.pack.slides = [
    {
      slide_title: "Why this paper is in the meeting",
      purpose: "Frame the selected paper slug for discussion",
      bullets: [
        `Source slug: ${sourceRef}`,
        `Mode: ${formatMeetingPackModeLabel(request.mode)}`,
      ],
      evidence_refs: ["evref_01"],
      caution_notes: ["Replace mock content with a live draft before reuse."],
    },
    {
      slide_title: "What to review next",
      purpose: "Check evidence, trace, and discussion prompts",
      bullets: [
        "Open the trace panel to confirm which selectors were used.",
        "Use regenerate after changing selector inputs.",
      ],
      evidence_refs: ["evref_01"],
      caution_notes: [],
    },
  ];
  response.pack.discussion_questions = [
    {
      question: `What meeting angle do we want to take for ${sourceRef}?`,
      rationale: "A starting prompt helps the route feel usable before a live backend is connected.",
      evidence_refs: ["evref_01"],
    },
  ];
  response.pack.expected_questions = [
    {
      question: "Is this a live draft or a fallback demo?",
      suggested_response:
        "This draft was created in mock mode to demonstrate the creation flow while the backend is unavailable.",
      evidence_refs: ["evref_01"],
    },
  ];
  response.pack.next_steps = [
    {
      action: "Reconnect the live backend and regenerate this draft.",
      why: "That will replace placeholder content with canonical evidence-backed slides.",
      priority: "medium",
      evidence_refs: ["evref_01"],
    },
  ];
  response.pack.evidence_refs = [
    {
      id: "evref_01",
      paper_slug: sourceRef,
      claim_id: null,
      evidence_id: null,
      run_id: "mock-meeting-pack-generate",
      support_type: "direct",
      note: "Mock source reference created from the draft request.",
    },
  ];
  response.markdown = [
    `# ${title}`,
    "",
    "## One-page Summary",
    "",
    response.pack.one_page_summary.overview,
    "",
    "## Slide Outline",
    "",
    ...response.pack.slides.map((slide, index) => `${index + 1}. ${slide.slide_title}`),
  ].join("\n");
  response.markdown_sync = {
    status: "in_sync",
    stored_markdown_sha1: "b".repeat(40),
    rendered_markdown_sha1: "b".repeat(40),
    note: "Mock-generated markdown mirrors the current draft bundle.",
  };

  MOCK_GENERATED_MEETING_PACKS.set(packId, response);
  MOCK_GENERATED_MEETING_PACK_ORDER.unshift(packId);
  return deepClone(response);
}

export function getMockMethodComparison(comparisonId: string): MethodComparisonResponse {
  const generated = MOCK_GENERATED_METHOD_COMPARISONS.get(comparisonId);
  if (generated) {
    return deepClone(generated);
  }
  const response = deepClone(MOCK_METHOD_COMPARISON_RESPONSE);
  response.comparison.comparison_id = comparisonId || MOCK_METHOD_COMPARISON_ID;
  return response;
}

export function getMockMethodComparisonIndex(): MethodComparisonListResponse {
  const generatedItems = MOCK_GENERATED_METHOD_COMPARISON_ORDER
    .map((comparisonId) => MOCK_GENERATED_METHOD_COMPARISONS.get(comparisonId))
    .filter((response): response is MethodComparisonResponse => Boolean(response))
    .map((response) => buildMethodComparisonListItem(response));
  const base = deepClone(MOCK_METHOD_COMPARISON_LIST_RESPONSE);
  return {
    ...base,
    total: generatedItems.length + base.items.length,
    items: [...generatedItems, ...base.items],
  };
}

export function createMockMethodComparison(
  request: MethodComparisonCreateRequest,
): MethodComparisonResponse {
  const now = new Date().toISOString();
  const paperIds = Array.from(new Set(request.paper_ids.map((paperId) => paperId.trim()).filter(Boolean)));
  const fieldIds = Array.from(new Set(request.field_ids));
  const comparisonId = request.comparison_id?.trim() || buildMockMethodComparisonId();
  const title =
    request.title?.trim() ||
    (paperIds.length <= 1
      ? `${resolveMockComparisonPaperTitle(paperIds[0] ?? "paper")} method comparison`
      : `${resolveMockComparisonPaperTitle(paperIds[0] ?? "paper")} + ${paperIds.length - 1} more method comparison`);
  const rows = paperIds.map((paperId, index) => buildMockMethodComparisonRow(paperId, fieldIds, index));
  const warnings = rows.flatMap((row) =>
    row.cells.flatMap((cell) => {
      if (cell.status === "conflict") {
        return [`${cell.field_id.replaceAll("_", " ")} cell for ${row.paper_id} should be reviewed before export.`];
      }
      return [];
    }),
  );

  const comparison: MethodComparison = {
    comparison_id: comparisonId,
    title,
    created_at: request.created_at ?? now,
    generated_at: now,
    paper_ids: paperIds,
    columns: fieldIds.map((fieldId) => ({
      field_id: fieldId,
      label: MOCK_METHOD_COMPARISON_FIELD_SPECS[fieldId].label,
      value_kind: MOCK_METHOD_COMPARISON_FIELD_SPECS[fieldId].value_kind,
    })),
    rows,
    source_summary: {
      source_priority: ["claimset.resolved.json", "document_artifact", "paper_note_state"],
      note: "Mock-generated comparison reflects the claimset-focused review lane. Conflict and missing cells should stay review-visible.",
      source_paper_count: rows.length,
      note_backed_paper_count: rows.filter((row) => Boolean(row.paper_slug)).length,
      operator_override_count: 0,
    },
    warnings,
  };

  const response: MethodComparisonResponse = {
    comparison,
    csv_text: buildMockMethodComparisonCsv(comparison),
    markdown: buildMockMethodComparisonMarkdown(comparison),
  };

  MOCK_GENERATED_METHOD_COMPARISONS.set(comparisonId, response);
  MOCK_GENERATED_METHOD_COMPARISON_ORDER.unshift(comparisonId);
  return deepClone(response);
}

export function getMockChartPack(chartPackId: string): ChartPackResponse {
  const generated = MOCK_GENERATED_CHART_PACKS.get(chartPackId);
  if (generated) {
    return deepClone(generated);
  }
  if (chartPackId === MOCK_SECONDARY_CHART_PACK_ID) {
    return deepClone(MOCK_SECONDARY_CHART_PACK_RESPONSE);
  }
  return deepClone(MOCK_CHART_PACK_RESPONSE);
}

export function getMockChartPackIndex(): ChartPackListResponse {
  const generatedItems = MOCK_GENERATED_CHART_PACK_ORDER
    .map((chartPackId) => MOCK_GENERATED_CHART_PACKS.get(chartPackId))
    .filter((item): item is ChartPackResponse => Boolean(item))
    .map((item) => buildChartPackListItem(item));

  return deepClone({
    total: MOCK_CHART_PACK_LIST_RESPONSE.total + generatedItems.length,
    items: [...generatedItems, ...MOCK_CHART_PACK_LIST_RESPONSE.items],
  });
}

export function createMockChartPack(request: ChartPackRequestSnapshot): ChartPackResponse {
  const now = new Date();
  const createdAt = request.created_at?.trim() || now.toISOString();
  const chartRequest = request.charts[0];
  const templateId = chartRequest?.template_id ?? "stats_check_status_counts";
  const chartPackId = request.chart_pack_id?.trim() || buildMockChartPackId();
  const chartId = chartRequest?.chart_id?.trim() || `chart_01_${templateId.replaceAll("_", "-")}`;
  const chartTitle = chartRequest?.title?.trim() || defaultMockChartTitle(templateId);
  const chartPackTitle = request.title?.trim() || `${chartTitle} chart pack`;
  const sourceRef = chartRequest?.source_ref ?? {
    source_kind: "stats_report",
    paper_id: "paper-2023-imaging",
    run_id: "run-001",
    source_label: "stats_report.json",
  };
  const fieldMappings =
    chartRequest?.field_mappings && chartRequest.field_mappings.length > 0
      ? chartRequest.field_mappings
      : templateId === "reported_vs_computed_p_scatter"
        ? [
            { target_field: "reported_p", source_field: "reported_p" },
            { target_field: "computed_p", source_field: "computed_p" },
          ]
        : [
            { target_field: "status", source_field: "status" },
            { target_field: "value", source_field: "count" },
          ];
  const sort =
    chartRequest?.sort ??
    (templateId === "reported_vs_computed_p_scatter"
      ? { field: "reported_p", direction: "asc" as const }
      : { field: "status", direction: "asc" as const });
  const warnings = buildMockChartPackWarnings(templateId);
  const csvText = buildMockChartPackCsv(templateId);
  const specPayload = buildMockChartPackSpec(chartId, chartTitle, templateId, warnings);
  const cautionNotes = warnings.length > 0
    ? [
        "Some charts include warning states; inspect source lineage before reuse.",
        "Reported/computed p charts include only exact numeric pairs and skip approximate values.",
      ]
    : [];
  const [csvHeader, ...csvRows] = csvText.split("\n");
  const markdownTableLines = csvHeader
    ? [
        `| ${csvHeader.split(",").join(" | ")} |`,
        `| ${csvHeader
          .split(",")
          .map(() => "---")
          .join(" | ")} |`,
        ...csvRows.map((row) => `| ${row.split(",").join(" | ")} |`),
      ]
    : [];

  const response: ChartPackResponse = {
    chart_pack: {
      chart_pack_id: chartPackId,
      title: chartPackTitle,
      created_at: createdAt,
      generated_at: createdAt,
      charts: [
        {
          chart_id: chartId,
          title: chartTitle,
          template_id: templateId,
          source_ref: {
            ...sourceRef,
            source_label: sourceRef.source_label ?? "stats_report.json",
          },
          field_mappings: fieldMappings,
          filters: chartRequest?.filters ?? [],
          sort,
          transforms: [
            ...fieldMappings.map((mapping) => ({
              kind: "field_mapping" as const,
              description: `Mapped ${mapping.source_field} -> ${mapping.target_field}.`,
              field: mapping.target_field,
            })),
            {
              kind: "sort" as const,
              description: `Sorted rows by ${sort.field} ${sort.direction}.`,
              field: sort.field,
            },
          ],
          warnings,
          data_snapshot_ref: {
            kind: "data_csv",
            path: `data/${chartId}.csv`,
            mime_type: "text/csv",
          },
          spec_ref: {
            kind: "spec_json",
            path: `specs/${chartId}.json`,
            mime_type: "application/json",
          },
          render_refs: [
            {
              kind: "render_svg",
              path: `renders/${chartId}.svg`,
              mime_type: "image/svg+xml",
            },
          ],
        },
      ],
      source_items: [
        {
          ...sourceRef,
          source_label: sourceRef.source_label ?? "stats_report.json",
        },
      ],
      generation_request: {
        chart_pack_id: request.chart_pack_id ?? chartPackId,
        title: request.title ?? chartPackTitle,
        notes: request.notes ?? null,
        created_at: createdAt,
        charts: [
          {
            chart_id: chartRequest?.chart_id ?? chartId,
            title: chartRequest?.title ?? chartTitle,
            template_id: templateId,
            source_ref: {
              ...sourceRef,
              source_label: sourceRef.source_label ?? "stats_report.json",
            },
            field_mappings: fieldMappings,
            filters: chartRequest?.filters ?? [],
            sort,
          },
        ],
      },
      render_env: {
        engine: "chart_pack_template_renderer",
        version: "v0",
        notes: "Deterministic template-driven spec builder over saved artifact snapshots.",
      },
      caution_notes: cautionNotes,
      warnings,
    },
    markdown: [
      `# ${chartPackTitle}`,
      "",
      `- Chart Pack ID: ${chartPackId}`,
      `- Charts: 1`,
      "",
      "## Charts",
      `### ${chartTitle}`,
      `- Template: ${templateId}`,
      `- Data snapshot: data/${chartId}.csv`,
      "",
      ...markdownTableLines,
    ].join("\n"),
    data_snapshots: {
      [chartId]: csvText,
    },
    specs: {
      [chartId]: specPayload,
    },
    quality_gate: {
      schema_version: "2026-04-17.chart-pack-handoff.v1",
      workflow: "chart_pack",
      chart_pack_id: chartPackId,
      overall_status: warnings.length > 0 ? "warn" : "pass",
      bundle_ready: true,
      handoff_ready: warnings.length === 0,
      reason_codes: warnings.length > 0 ? ["CHART_WARNING_PRESENT"] : [],
      checks: [
        { name: "source_items_persisted", status: "pass", detail: "true" },
        { name: "data_snapshot_refs_complete", status: "pass", detail: "true" },
        { name: "spec_refs_complete", status: "pass", detail: "true" },
        { name: "markdown_synced_at_write", status: "pass", detail: "in_sync" },
        {
          name: "artifact_brief_review",
          status: warnings.length > 0 ? "warn" : "pass",
          detail: warnings.length > 0 ? "CHART_WARNING_PRESENT" : "pass",
        },
        {
          name: "warning_state_requires_review",
          status: warnings.length > 0 ? "warn" : "pass",
          detail: warnings.length > 0 ? "true" : "false",
        },
      ],
    },
  };

  MOCK_GENERATED_CHART_PACKS.set(chartPackId, response);
  MOCK_GENERATED_CHART_PACK_ORDER.unshift(chartPackId);
  return deepClone(response);
}

export function getMockImageEvidence(imageEvidenceId: string): ImageEvidenceResponse {
  if (imageEvidenceId === MOCK_SECONDARY_IMAGE_EVIDENCE_ID) {
    return deepClone(MOCK_SECONDARY_IMAGE_EVIDENCE_RESPONSE);
  }
  return deepClone(MOCK_IMAGE_EVIDENCE_RESPONSE);
}

export function getMockImageEvidenceIndex(): ImageEvidenceListResponse {
  return deepClone(MOCK_IMAGE_EVIDENCE_LIST_RESPONSE);
}

export function getMockProtocolCard(protocolId: string): ProtocolCardResponse {
  const generated = MOCK_GENERATED_PROTOCOL_CARDS.get(protocolId);
  if (generated) {
    return deepClone(generated);
  }
  if (protocolId === MOCK_SECONDARY_PROTOCOL_CARD_ID) {
    return deepClone(MOCK_SECONDARY_PROTOCOL_CARD_RESPONSE);
  }
  return deepClone(MOCK_PROTOCOL_CARD_RESPONSE);
}

export function getMockProtocolCardIndex(): ProtocolCardListResponse {
  const generatedItems = MOCK_GENERATED_PROTOCOL_CARD_ORDER
    .map((protocolId) => MOCK_GENERATED_PROTOCOL_CARDS.get(protocolId))
    .filter((response): response is ProtocolCardResponse => Boolean(response))
    .map((response) => buildProtocolCardListItem(response));

  return deepClone({
    total: MOCK_PROTOCOL_CARD_LIST_RESPONSE.total + generatedItems.length,
    items: [...generatedItems, ...MOCK_PROTOCOL_CARD_LIST_RESPONSE.items],
  });
}

function buildMockProtocolMarkdown(response: ProtocolCardResponse): string {
  const currentVersion = response.versions.find(
    (version) => version.version_id === response.protocol_card.current_version_id,
  ) ?? response.versions[0];

  return [
    `# ${response.protocol_card.title}`,
    "",
    `- Protocol ID: \`${response.protocol_card.protocol_id}\``,
    `- Source kind: ${response.protocol_card.source_kind.replaceAll("_", " ")}`,
    `- Validation status: ${response.protocol_card.validation_status.replaceAll("_", " ")}`,
    currentVersion ? `- Current version: \`${currentVersion.version_id}\`` : null,
    "",
    "## Current snapshot",
    "",
    currentVersion?.content_snapshot ?? "No saved snapshot.",
  ]
    .filter((line): line is string => Boolean(line))
    .join("\n");
}

export function createMockProtocolCard(request: ProtocolCardRequestSnapshot): ProtocolCardResponse {
  const now = new Date().toISOString();
  const protocolId = request.protocol_id?.trim() || buildMockProtocolCardId();
  const linkedPaperIds = Array.from(new Set(request.linked_paper_ids.map((item) => item.trim()).filter(Boolean)));
  const linkedNoteSlugs = Array.from(new Set(request.linked_note_slugs.map((item) => item.trim()).filter(Boolean)));
  const versions = request.versions.map((version, index) => {
    const versionNumber = version.version_number || index + 1;
    const protocolSuffix = protocolId.replace(/^protocol_/, "");
    return {
      version_id: version.version_id?.trim() || `protver_${protocolSuffix}_v${versionNumber}`,
      protocol_id: protocolId,
      version_number: versionNumber,
      key_steps_summary: [...version.key_steps_summary],
      materials: [...version.materials],
      equipment: [...version.equipment],
      critical_conditions: [...version.critical_conditions],
      readouts: [...version.readouts],
      cautions: [...version.cautions],
      content_snapshot: version.content_snapshot,
      change_reason: version.change_reason ?? null,
      status: version.status,
      created_by: version.created_by,
      created_at: version.created_at?.trim() || now,
      source_refs: version.source_refs.map((ref) => ({ ...ref })),
      note: version.note ?? null,
    };
  });
  const currentVersion =
    versions.find((version) => version.status === "active") ??
    versions[versions.length - 1];

  const response: ProtocolCardResponse = {
    protocol_card: {
      protocol_id: protocolId,
      title: request.title.trim(),
      purpose: request.purpose?.trim() || null,
      context: request.context?.trim() || null,
      source_kind: request.source_kind,
      linked_paper_ids: linkedPaperIds,
      linked_note_slugs: linkedNoteSlugs,
      current_version_id: currentVersion?.version_id ?? null,
      validation_status: request.validation_status,
      created_at: request.created_at?.trim() || now,
      updated_at: request.updated_at?.trim() || now,
      version_summaries: versions.map((version) => ({
        version_id: version.version_id,
        version_number: version.version_number,
        status: version.status,
        created_at: version.created_at,
        change_reason: version.change_reason,
        source_ref_count: version.source_refs.length,
      })),
    },
    versions,
    markdown: "",
  };

  response.markdown = buildMockProtocolMarkdown(response);
  MOCK_GENERATED_PROTOCOL_CARDS.set(protocolId, response);
  MOCK_GENERATED_PROTOCOL_CARD_ORDER.unshift(protocolId);
  return deepClone(response);
}

export function createMockJob(): JobEnqueueResponse {
  const stamp = Date.now();
  return {
    job_id: `job-mock-${stamp}`,
    run_id: `run-mock-${stamp}`,
    status: "queued",
  };
}

export interface MockStreamFrame {
  stage: string;
  progress: number;
  status: JobStatus["status"];
  log: string;
  level?: "INFO" | "ERROR";
}

export function getMockStreamFrames(paperId: string, jobId: string, runId: string): MockStreamFrame[] {
  const base: MockStreamFrame[] = [
    { stage: "ingest", progress: 14, status: "running", log: "Ingest complete: 12 pages extracted." },
    { stage: "index", progress: 33, status: "running", log: "Indexer produced 164 chunks." },
    { stage: "read", progress: 58, status: "running", log: "Claim synthesizer produced 9 candidate claims." },
    { stage: "verify", progress: 82, status: "running", log: "Stats verifier running p-value and N consistency checks." },
    { stage: "completed", progress: 100, status: "completed", log: "Pipeline completed. Artifacts written.", level: "INFO" },
  ];

  if (paperId === "paper-2025-nutrition") {
    return [
      ...base.slice(0, 3),
      { stage: "verify", progress: 79, status: "failed", log: "Verifier failed: table_03 schema mismatch.", level: "ERROR" },
    ];
  }

  return base.map((frame) => ({ ...frame, log: `[${jobId}/${runId}] ${frame.log}` }));
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function clampPct(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function normalizeBBoxPct(
  left: number,
  top: number,
  width: number,
  height: number,
): Pick<EvidenceHighlight, "left" | "top" | "width" | "height"> {
  const safeLeft = clampPct(left);
  const safeTop = clampPct(top);
  const safeWidth = clampPct(width);
  const safeHeight = clampPct(height);
  return {
    left: safeLeft,
    top: safeTop,
    width: clampPct(Math.min(safeWidth, 100 - safeLeft)),
    height: clampPct(Math.min(safeHeight, 100 - safeTop)),
  };
}

function normalizeBBoxFromUnknownRect(
  leftValue: unknown,
  topValue: unknown,
  widthValue: unknown,
  heightValue: unknown,
  pageWidth?: number,
  pageHeight?: number,
): Pick<EvidenceHighlight, "left" | "top" | "width" | "height"> {
  const left = asFiniteNumber(leftValue) ?? 0;
  const top = asFiniteNumber(topValue) ?? 0;
  const width = asFiniteNumber(widthValue) ?? 0;
  const height = asFiniteNumber(heightValue) ?? 0;

  const values = [left, top, width, height];
  const isUnitScale = values.every((value) => value >= 0 && value <= 1);
  if (isUnitScale) {
    return normalizeBBoxPct(left * 100, top * 100, width * 100, height * 100);
  }

  const hasPixelHint = values.some((value) => Math.abs(value) > 100);
  const widthBase = pageWidth ?? 0;
  const heightBase = pageHeight ?? 0;
  if (hasPixelHint && widthBase > 0 && heightBase > 0) {
    return normalizeBBoxPct((left / widthBase) * 100, (top / heightBase) * 100, (width / widthBase) * 100, (height / heightBase) * 100);
  }

  return normalizeBBoxPct(left, top, width, height);
}

function normalizeMatchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/-\s+/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenizeMatchText(value: string): string[] {
  return normalizeMatchText(value)
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length > 2);
}

function buildMatchPhrases(tokens: string[]): string[] {
  if (tokens.length === 0) {
    return [];
  }

  const phrases: string[] = [];
  const pushWindow = (start: number, width: number) => {
    if (start < 0 || width < 3 || start + width > tokens.length) {
      return;
    }
    const phrase = tokens.slice(start, start + width).join(" ").trim();
    if (phrase.length >= 12) {
      phrases.push(phrase);
    }
  };

  for (const width of [16, 12, 9, 7]) {
    pushWindow(0, Math.min(width, tokens.length));
  }

  if (tokens.length >= 12) {
    const middleStart = Math.max(0, Math.floor((tokens.length - 10) / 2));
    pushWindow(middleStart, Math.min(10, tokens.length - middleStart));
  }

  if (tokens.length >= 10) {
    pushWindow(tokens.length - 8, 8);
  }

  return Array.from(new Set(phrases));
}

interface DocumentBlockMatch {
  pageIndex: number;
  left: number;
  top: number;
  width: number;
  height: number;
  text: string;
}

interface DocumentPageContext {
  pageIndex: number;
  width: number;
  height: number;
  blocks: DocumentBlockMatch[];
}

function toPctFromPdfBbox(
  bboxPdf: unknown,
  pageWidth: number,
  pageHeight: number,
): Pick<EvidenceHighlight, "left" | "top" | "width" | "height"> | null {
  if (!Array.isArray(bboxPdf) || bboxPdf.length !== 4) {
    return null;
  }

  const x0 = asFiniteNumber(bboxPdf[0]);
  const y0 = asFiniteNumber(bboxPdf[1]);
  const x1 = asFiniteNumber(bboxPdf[2]);
  const y1 = asFiniteNumber(bboxPdf[3]);
  if (x0 === null || y0 === null || x1 === null || y1 === null) {
    return null;
  }

  const minX = Math.min(x0, x1);
  const maxX = Math.max(x0, x1);
  const minY = Math.min(y0, y1);
  const maxY = Math.max(y0, y1);
  if (maxX <= minX || maxY <= minY || pageWidth <= 0 || pageHeight <= 0) {
    return null;
  }

  return normalizeBBoxPct(
    (minX / pageWidth) * 100,
    (minY / pageHeight) * 100,
    ((maxX - minX) / pageWidth) * 100,
    ((maxY - minY) / pageHeight) * 100,
  );
}

function parseDocumentPages(documentData: unknown): DocumentPageContext[] {
  const root = asRecord(documentData);
  if (!root || !Array.isArray(root.pages)) {
    return [];
  }

  const pages: DocumentPageContext[] = [];
  root.pages.forEach((pageValue, fallbackIndex) => {
    const page = asRecord(pageValue);
    if (!page) {
      return;
    }

    const pageIndexRaw = asFiniteNumber(page.page_index);
    const pageIndex = Math.max(0, Math.round(pageIndexRaw ?? fallbackIndex));
    const pageWidth = asFiniteNumber(page.width);
    const pageHeight = asFiniteNumber(page.height);
    if (!pageWidth || !pageHeight || !Array.isArray(page.blocks)) {
      pages.push({ pageIndex, width: pageWidth ?? 0, height: pageHeight ?? 0, blocks: [] });
      return;
    }

    const blocks = page.blocks
      .map((blockValue) => {
        const block = asRecord(blockValue);
        if (!block || !Array.isArray(block.lines)) {
          return null;
        }

        const lineTexts = block.lines
          .map((lineValue) => asRecord(lineValue))
          .map((line) => asString(line?.text))
          .filter((text): text is string => text !== null);
        const text = lineTexts.join(" ").trim();
        if (!text) {
          return null;
        }

        const bboxPct = toPctFromPdfBbox(block.bbox_pdf, pageWidth, pageHeight);
        if (!bboxPct || bboxPct.width <= 0 || bboxPct.height <= 0) {
          return null;
        }

        return {
          pageIndex,
          text,
          ...bboxPct,
        } satisfies DocumentBlockMatch;
      })
      .filter((block): block is DocumentBlockMatch => block !== null);

    pages.push({ pageIndex, width: pageWidth, height: pageHeight, blocks });
  });

  return pages;
}

function extractBBoxFromPdf(
  span: Record<string, unknown> | null,
  pageContext: DocumentPageContext | null,
): Pick<EvidenceHighlight, "left" | "top" | "width" | "height"> | null {
  if (!span || !pageContext) {
    return null;
  }
  const raw = span.bbox_pdf ?? span.bboxPdf;
  if (!Array.isArray(raw) || raw.length !== 4) {
    return null;
  }

  const x0 = asFiniteNumber(raw[0]);
  const y0 = asFiniteNumber(raw[1]);
  const x1 = asFiniteNumber(raw[2]);
  const y1 = asFiniteNumber(raw[3]);
  if (x0 === null || y0 === null || x1 === null || y1 === null) {
    return null;
  }
  if (pageContext.width <= 0 || pageContext.height <= 0) {
    return null;
  }

  const minX = Math.min(x0, x1);
  const minY = Math.min(y0, y1);
  const maxX = Math.max(x0, x1);
  const maxY = Math.max(y0, y1);
  if (maxX <= minX || maxY <= minY) {
    return null;
  }

  return normalizeBBoxPct(
    (minX / pageContext.width) * 100,
    (minY / pageContext.height) * 100,
    ((maxX - minX) / pageContext.width) * 100,
    ((maxY - minY) / pageContext.height) * 100,
  );
}

function confidenceToLevel(value: unknown): "low" | "medium" | "high" {
  if (value === "high" || value === "medium" || value === "low") {
    return value;
  }
  if (typeof value === "number") {
    if (value >= 0.75) {
      return "high";
    }
    if (value >= 0.4) {
      return "medium";
    }
    return "low";
  }
  return "medium";
}

function extractClaimsArray(payload: unknown): Array<Record<string, unknown>> {
  const root = asRecord(payload);
  if (!root) {
    return [];
  }
  const direct = root.claims;
  if (Array.isArray(direct)) {
    return direct.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null);
  }
  const nestedClaimSet = asRecord(root.claimset) ?? asRecord(root.ClaimSet);
  if (!nestedClaimSet || !Array.isArray(nestedClaimSet.claims)) {
    return [];
  }
  return nestedClaimSet.claims
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null);
}

function extractClaimText(claim: Record<string, unknown>): string {
  return (
    asString(claim.claim_text) ??
    asString(claim.statement) ??
    asString(claim.text) ??
    asString(claim.claim) ??
    "Claim text missing"
  );
}

function extractEvidenceArray(claim: Record<string, unknown>): Array<Record<string, unknown>> {
  const spans =
    (Array.isArray(claim.evidence_spans) ? claim.evidence_spans : null) ??
    (Array.isArray(claim.evidence) ? claim.evidence : null) ??
    [];
  return spans.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null);
}

function extractPageNumber(span: Record<string, unknown> | null): number | null {
  if (!span) {
    return null;
  }
  const candidate = span.page ?? span.page_index;
  if (typeof candidate !== "number" || !Number.isFinite(candidate)) {
    return null;
  }
  return Math.max(0, Math.round(candidate));
}

function extractBBoxPct(
  span: Record<string, unknown> | null,
  pageContext: DocumentPageContext | null = null,
): Pick<EvidenceHighlight, "left" | "top" | "width" | "height"> | null {
  const pageWidth = pageContext?.width;
  const pageHeight = pageContext?.height;
  const bbox =
    asRecord(span?.bboxPct) ??
    asRecord(span?.bbox_pct) ??
    asRecord(span?.bbox) ??
    asRecord(span?.region);
  if (
    bbox &&
    typeof bbox.left === "number" &&
    typeof bbox.top === "number" &&
    typeof bbox.width === "number" &&
    typeof bbox.height === "number"
  ) {
    return normalizeBBoxFromUnknownRect(bbox.left, bbox.top, bbox.width, bbox.height, pageWidth, pageHeight);
  }

  if (
    bbox &&
    typeof bbox.x === "number" &&
    typeof bbox.y === "number" &&
    typeof bbox.w === "number" &&
    typeof bbox.h === "number"
  ) {
    return normalizeBBoxFromUnknownRect(bbox.x, bbox.y, bbox.w, bbox.h, pageWidth, pageHeight);
  }

  if (
    span &&
    typeof span.left === "number" &&
    typeof span.top === "number" &&
    typeof span.width === "number" &&
    typeof span.height === "number"
  ) {
    return normalizeBBoxFromUnknownRect(span.left, span.top, span.width, span.height, pageWidth, pageHeight);
  }

  return null;
}

function extractEvidenceQuote(span: Record<string, unknown> | null): string | undefined {
  return (
    asString(span?.quote) ??
    asString(span?.raw_text) ??
    asString(span?.text) ??
    asString(span?.excerpt) ??
    undefined
  );
}

function extractHighlightSource(span: Record<string, unknown> | null): EvidenceHighlight["source"] | null {
  const raw = asString(span?.highlight_source) ?? asString(span?.highlightSource);
  if (raw === "bbox" || raw === "text_match" || raw === "approx") {
    return raw;
  }
  return null;
}

function findDocumentBboxForClaim(
  pages: DocumentPageContext[],
  targetDocPageIndex: number | null,
  claimText: string,
  span: Record<string, unknown> | null,
): ({ pageIndex: number } & Pick<EvidenceHighlight, "left" | "top" | "width" | "height">) | null {
  if (pages.length === 0) {
    return null;
  }

  const targetTexts = [
    extractEvidenceQuote(span),
    asString(span?.raw_text),
    claimText,
  ]
    .filter((value): value is string => Boolean(value && value.trim().length > 0))
    .map((value) => value.trim());
  if (targetTexts.length === 0) {
    return null;
  }

  const normalizedTargets = Array.from(
    new Set(targetTexts.map(normalizeMatchText).filter((value) => value.length >= 8)),
  ).map((text) => {
    const tokens = tokenizeMatchText(text);
    return {
      text,
      tokens,
      tokenSet: new Set(tokens),
      phrases: buildMatchPhrases(tokens),
    };
  });

  if (normalizedTargets.length === 0) {
    return null;
  }

  let best:
    | ({
        score: number;
      } & DocumentBlockMatch)
    | null = null;

  for (const page of pages) {
    for (const block of page.blocks) {
      const normalizedBlock = normalizeMatchText(block.text);
      if (!normalizedBlock) {
        continue;
      }
      const blockTokens = new Set(tokenizeMatchText(normalizedBlock));

      let score = 0;
      for (const target of normalizedTargets) {
        let targetScore = 0;
        if (normalizedBlock.includes(target.text)) {
          targetScore += 8 + Math.min(target.text.length / 120, 2);
        } else {
          for (const phrase of target.phrases) {
            if (normalizedBlock.includes(phrase)) {
              targetScore += 2.8;
              break;
            }
          }
        }

        if (target.tokens.length > 0) {
          let overlapCount = 0;
          for (const token of target.tokenSet) {
            if (blockTokens.has(token)) {
              overlapCount += 1;
            }
          }
          targetScore += (overlapCount / target.tokens.length) * 2.4;
        }

        score = Math.max(score, targetScore);
      }

      if (targetDocPageIndex !== null) {
        if (page.pageIndex === targetDocPageIndex) {
          score += 1.1;
        } else if (Math.abs(page.pageIndex - targetDocPageIndex) === 1) {
          score += 0.4;
        }
      }

      if (best === null || score > best.score) {
        best = { ...block, score };
      }
    }
  }

  if (!best || best.score < 0.9) {
    return null;
  }

  return {
    pageIndex: best.pageIndex,
    left: best.left,
    top: best.top,
    width: best.width,
    height: best.height,
  };
}

function resolvePageNumberingMode(rawPages: Array<number | null>, pages: DocumentPageContext[]): "zero_based" | "one_based" {
  const concretePages = rawPages.filter((page): page is number => page !== null);
  if (concretePages.length === 0) {
    return "one_based";
  }
  if (concretePages.some((page) => page === 0)) {
    return "zero_based";
  }

  const pageIndexSet = new Set(pages.map((page) => page.pageIndex));
  if (pageIndexSet.size === 0) {
    return "one_based";
  }

  let zeroBasedScore = 0;
  let oneBasedScore = 0;
  for (const page of concretePages) {
    if (pageIndexSet.has(page)) {
      zeroBasedScore += 1;
    }
    if (page > 0 && pageIndexSet.has(page - 1)) {
      oneBasedScore += 1;
    }
  }

  if (zeroBasedScore > oneBasedScore) {
    return "zero_based";
  }
  return "one_based";
}

function normalizeNotebookSource(value: unknown): EvidenceHighlight["source"] | undefined {
  if (value === "bbox" || value === "text_match" || value === "approx") {
    return value;
  }
  return undefined;
}

function applyClaimLinkGuards(claims: NotebookClaim[], highlights: EvidenceHighlight[]): NotebookClaim[] {
  const highlightMap = buildBestHighlightMap(highlights);
  return claims.map((claim) => {
    const highlight = highlightMap.get(claim.claim_id);
    const state = getClaimLinkState(claim, highlight);
    return {
      ...claim,
      link_health: state.health,
      text_missing: state.textMissing,
    };
  });
}

function normalizeNotebookArtifact(payload: unknown, documentPages: DocumentPageContext[]): NotebookArtifact | null {
  const root = asRecord(payload);
  if (!root) {
    return null;
  }

  const rawClaims = Array.isArray(root.claims)
    ? root.claims.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null)
    : [];
  const parsedClaims: NotebookClaim[] = rawClaims.map((claim, index) => {
    const claimId = asString(claim.claim_id) ?? `claim-${index + 1}`;
    const text = asString(claim.text) ?? "Claim text missing";
    return {
      claim_id: claimId,
      text,
      confidence: confidenceToLevel(claim.confidence),
      text_missing: isClaimTextMissing(text),
      link_health:
        claim.link_health === "mapped" || claim.link_health === "search_fallback" || claim.link_health === "missing"
          ? claim.link_health
          : undefined,
    };
  });

  const rawHighlights = Array.isArray(root.highlights)
    ? root.highlights.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null)
    : [];
  const rawPages = rawHighlights.map((item) => {
    const raw = asFiniteNumber(item.page);
    return raw === null ? null : Math.max(0, Math.round(raw));
  });
  const pageNumberingMode = resolvePageNumberingMode(rawPages, documentPages);

  const parsedHighlights: EvidenceHighlight[] = rawHighlights.map((highlight, index) => {
    const claimId = asString(highlight.claim_id) ?? parsedClaims[index]?.claim_id ?? `claim-${index + 1}`;
    const rawPage = asFiniteNumber(highlight.page);
    const resolvedPage = rawPage === null ? 1 : Math.max(pageNumberingMode === "zero_based" ? Math.round(rawPage) + 1 : Math.round(rawPage), 1);
    const pageContext =
      documentPages.find((page) => page.pageIndex === resolvedPage - 1) ??
      documentPages.find((page) => page.pageIndex === resolvedPage) ??
      null;
    const normalized =
      extractBBoxPct(highlight, pageContext) ??
      (pageContext ? toPctFromPdfBbox(highlight.bbox_pdf ?? highlight.bboxPdf, pageContext.width, pageContext.height) : null) ??
      normalizeBBoxPct(0, 0, 0, 0);
    const source = normalizeNotebookSource(highlight.source) ?? (normalized.width > 0 && normalized.height > 0 ? "bbox" : "approx");

    return {
      claim_id: claimId,
      page: resolvedPage,
      ...normalized,
      quote: asString(highlight.quote) ?? undefined,
      source,
    };
  });

  const claims =
    parsedClaims.length > 0
      ? parsedClaims
      : Array.from(new Set(parsedHighlights.map((item) => item.claim_id))).map((claimId) => ({
          claim_id: claimId,
          text: "Claim text missing",
          confidence: "medium" as const,
          text_missing: true,
        }));

  if (claims.length === 0 && parsedHighlights.length === 0) {
    return null;
  }

  const verdictRecord = asRecord(root.verdict);
  const verdictLevelRaw = asString(verdictRecord?.level);
  const verdictLevel: NotebookArtifact["verdict"]["level"] =
    verdictLevelRaw === "pass" || verdictLevelRaw === "caution" || verdictLevelRaw === "fail"
      ? verdictLevelRaw
      : "caution";

  const agentPlan = Array.isArray(root.agent_plan)
    ? root.agent_plan
        .map((item) => asString(item))
        .filter((item): item is string => item !== null)
    : [];

  return {
    claims: applyClaimLinkGuards(claims, parsedHighlights),
    highlights: parsedHighlights,
    agent_plan: agentPlan.length > 0 ? agentPlan : deepClone(EMPTY_NOTEBOOK.agent_plan),
    sandbox_code: asString(root.sandbox_code) ?? EMPTY_NOTEBOOK.sandbox_code,
    verdict: {
      label: asString(verdictRecord?.label) ?? (verdictLevel === "pass" ? "Pass" : "Pending"),
      detail: asString(verdictRecord?.detail) ?? EMPTY_NOTEBOOK.verdict.detail,
      level: verdictLevel,
    },
  };
}

export function getNotebookFromBundle(bundle: ArtifactBundle): NotebookArtifact {
  const documentPages = parseDocumentPages(bundle.files.document_artifact?.data);
  const notebookData = bundle.files.notebook?.data;
  if (notebookData && typeof notebookData === "object") {
    const normalizedNotebook = normalizeNotebookArtifact(notebookData, documentPages);
    if (normalizedNotebook) {
      return normalizedNotebook;
    }
  }

  const claimsetData = bundle.files.claimset_resolved?.data ?? bundle.files.claimset?.data;
  const statsData = bundle.files.stats_report?.data;
  const rawClaims = extractClaimsArray(claimsetData).slice(0, 20);

  if (rawClaims.length === 0) {
    return deepClone(EMPTY_NOTEBOOK);
  }

  const parsedClaims = rawClaims.map((claim, index) => {
    const claimId = asString(claim.claim_id) ?? `claim-${index + 1}`;
    const text = extractClaimText(claim);
    return {
      claim_id: claimId,
      text,
      confidence: confidenceToLevel(claim.confidence),
      text_missing: isClaimTextMissing(text),
    };
  });

  const rawPages = rawClaims.map((claim) => extractPageNumber(extractEvidenceArray(claim)[0]));
  const pageNumberingMode = resolvePageNumberingMode(rawPages, documentPages);
  const parsedHighlights = rawClaims.map((claim, index) => {
    const primaryEvidence = extractEvidenceArray(claim)[0] ?? null;
    const rawPage = extractPageNumber(primaryEvidence);
    const resolvedPage = rawPage === null ? 1 : Math.max(pageNumberingMode === "zero_based" ? rawPage + 1 : rawPage, 1);
    const hintedDocPageIndex = rawPage === null ? null : Math.max(pageNumberingMode === "zero_based" ? rawPage : rawPage - 1, 0);
    const targetPageIndex = hintedDocPageIndex ?? Math.max(resolvedPage - 1, 0);
    const targetPage = documentPages.find((page) => page.pageIndex === targetPageIndex) ?? null;
    const bbox = extractBBoxPct(primaryEvidence, targetPage);
    const bboxFromPdf = bbox ? null : extractBBoxFromPdf(primaryEvidence, targetPage);
    const fallbackBbox = bbox || bboxFromPdf
      ? null
      : findDocumentBboxForClaim(documentPages, hintedDocPageIndex, parsedClaims[index].text, primaryEvidence);

    const resolvedHighlightPage = fallbackBbox
      ? fallbackBbox.pageIndex + 1
      : bboxFromPdf && targetPage
        ? targetPage.pageIndex + 1
        : resolvedPage;
    const explicitHighlightSource = extractHighlightSource(primaryEvidence);
    const highlightSource: EvidenceHighlight["source"] =
      explicitHighlightSource ?? (bbox || bboxFromPdf ? "bbox" : fallbackBbox ? "text_match" : "approx");

    return {
      claim_id: parsedClaims[index].claim_id,
      page: resolvedHighlightPage,
      left: bbox?.left ?? bboxFromPdf?.left ?? fallbackBbox?.left ?? 0,
      top: bbox?.top ?? bboxFromPdf?.top ?? fallbackBbox?.top ?? 0,
      width: bbox?.width ?? bboxFromPdf?.width ?? fallbackBbox?.width ?? 0,
      height: bbox?.height ?? bboxFromPdf?.height ?? fallbackBbox?.height ?? 0,
      quote: extractEvidenceQuote(primaryEvidence),
      source: highlightSource,
    };
  });

  const checkCount =
    statsData && typeof statsData === "object" && Array.isArray((statsData as { checks?: unknown[] }).checks)
      ? (statsData as { checks: unknown[] }).checks.length
      : 0;

  return {
    claims: applyClaimLinkGuards(parsedClaims, parsedHighlights),
    highlights: parsedHighlights,
    agent_plan: [
      "Loaded claims from artifact bundle.",
      "Evidence mapping can be reviewed in claimset payload.",
      checkCount > 0 ? `Saved note checks include ${checkCount} checks.` : "Saved note checks are missing or empty.",
    ],
    sandbox_code: "# Sandbox Execution (read-only)\n# Parsed from backend artifact bundle.",
    verdict: {
      label: checkCount > 0 ? "Review" : "Pending",
      detail:
        checkCount > 0
          ? "Artifact loaded from backend. Verify stats checks and evidence links."
          : "Saved claims loaded, but saved note checks are not available yet.",
      level: "caution",
    },
  };
}

export function getNotebookFromStructuredState(
  state: StructuredPaperState,
  bundle?: ArtifactBundle | null,
): NotebookArtifact {
  const documentPages = parseDocumentPages(bundle?.files.document_artifact?.data);
  const statsData = bundle?.files.stats_report?.data;
  const rawClaims = Array.isArray(state.claimset) ? state.claimset.slice(0, 20) : [];
  if (rawClaims.length === 0) {
    return bundle ? getNotebookFromBundle(bundle) : deepClone(EMPTY_NOTEBOOK);
  }

  const parsedClaims: NotebookClaim[] = rawClaims.map((claim, index) => {
    const claimId = asString(claim.id) ?? `claim-${index + 1}`;
    const text = asString(claim.claim) ?? "Claim text missing";
    return {
      claim_id: claimId,
      text,
      confidence: confidenceToLevel(claim.confidence),
      text_missing: isClaimTextMissing(text),
    };
  });

  const parsedHighlights: EvidenceHighlight[] = rawClaims.map((claim, index) => {
    const claimId = parsedClaims[index]?.claim_id ?? asString(claim.id) ?? `claim-${index + 1}`;
    const evidenceArray = Array.isArray(claim.evidence)
      ? claim.evidence.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null)
      : [];
    const primaryEvidence = evidenceArray[0] ?? null;
    const locator = asRecord(primaryEvidence?.locator);
    const rawPage = asFiniteNumber(locator?.page) ?? asFiniteNumber(primaryEvidence?.page);
    const hintedDocPageIndex = rawPage === null ? null : Math.max(Math.round(rawPage), 0);
    const resolvedPage = hintedDocPageIndex === null ? 1 : hintedDocPageIndex + 1;
    const targetPage = hintedDocPageIndex === null
      ? null
      : documentPages.find((page) => page.pageIndex === hintedDocPageIndex) ?? null;
    const bbox = extractBBoxPct(locator ?? primaryEvidence, targetPage);
    const bboxFromPdf = bbox ? null : extractBBoxFromPdf(locator ?? primaryEvidence, targetPage);
    const fallbackBbox = bbox || bboxFromPdf
      ? null
      : findDocumentBboxForClaim(
          documentPages,
          hintedDocPageIndex,
          parsedClaims[index]?.text ?? "Claim text missing",
          locator ?? primaryEvidence,
        );
    const explicitHighlightSource = extractHighlightSource(locator) ?? extractHighlightSource(primaryEvidence);
    const highlightSource: EvidenceHighlight["source"] =
      explicitHighlightSource ?? (bbox || bboxFromPdf ? "bbox" : fallbackBbox ? "text_match" : "approx");
    const resolvedHighlightPage = fallbackBbox
      ? fallbackBbox.pageIndex + 1
      : bboxFromPdf && targetPage
        ? targetPage.pageIndex + 1
        : resolvedPage;

    return {
      claim_id: claimId,
      page: resolvedHighlightPage,
      left: bbox?.left ?? bboxFromPdf?.left ?? fallbackBbox?.left ?? 0,
      top: bbox?.top ?? bboxFromPdf?.top ?? fallbackBbox?.top ?? 0,
      width: bbox?.width ?? bboxFromPdf?.width ?? fallbackBbox?.width ?? 0,
      height: bbox?.height ?? bboxFromPdf?.height ?? fallbackBbox?.height ?? 0,
      quote: extractEvidenceQuote(locator) ?? extractEvidenceQuote(primaryEvidence),
      source: highlightSource,
    };
  });

  const checkCount =
    statsData && typeof statsData === "object" && Array.isArray((statsData as { checks?: unknown[] }).checks)
      ? (statsData as { checks: unknown[] }).checks.length
      : 0;
  const lastRun = Array.isArray(state.runs) && state.runs.length > 0 ? state.runs[0] : null;

  return {
    claims: applyClaimLinkGuards(parsedClaims, parsedHighlights),
    highlights: parsedHighlights,
    agent_plan: [
      `Loaded ${parsedClaims.length} saved claims from canonical state.json.`,
      lastRun ? `Latest skill action: ${asString(lastRun.action) ?? "unknown"} (${asString(lastRun.status) ?? "unknown"}).` : "No skill run metadata recorded.",
      checkCount > 0 ? `Saved note checks include ${checkCount} checks.` : "Saved note checks are missing or empty.",
    ],
    sandbox_code: "# Sandbox Execution (read-only)\n# Canonical structured paper state loaded from state.json.",
    verdict: {
      label: checkCount > 0 ? "Review" : "Pending",
      detail:
        checkCount > 0
          ? "Saved note state loaded from the paper note sidecar. Verify checks and evidence links."
          : "Saved note state loaded, but saved note checks are not available yet.",
      level: "caution",
    },
  };
}

export { SAMPLE_PDF };
