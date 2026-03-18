import {
  ArtifactBundle,
  EvidenceHighlight,
  JobEnqueueResponse,
  JobStatus,
  MethodComparisonListResponse,
  MethodComparisonResponse,
  MeetingPackListResponse,
  MeetingPackResponse,
  MeetingPackTraceResponse,
  MeetingPackValidationResponse,
  NotebookClaim,
  NotebookArtifact,
  ObsidianMirror,
  PaperDetail,
  PaperSummary,
  PersonaListResponse,
  StructuredPaperState,
  TimelineResponse,
} from "./types";
import { buildBestHighlightMap, getClaimLinkState, isClaimTextMissing } from "./claimGuard";

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const SAMPLE_PDF = "/sample.pdf";

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

const BASE_NOTEBOOK: NotebookArtifact = {
  claims: [
    {
      claim_id: "claim-1",
      text: "① RAG mitigates hallucination by grounding responses in relevant documents.",
      confidence: "high",
    },
    {
      claim_id: "claim-2",
      text: "② The methods and indexer pipeline combine PyMuPDF parsing with ChromaDB retrieval.",
      confidence: "medium",
    },
    {
      claim_id: "claim-3",
      text: "③ Section-aware chunking achieved hit rate 0.85, while fixed-window achieved 0.60.",
      confidence: "low",
    },
    {
      claim_id: "claim-4",
      text: "④ Discussion notes structure-preserving parsing as essential and flags PDF-header dependence as a limitation.",
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
    "Parse section-level claims with mandatory evidence anchors.",
    "Reconcile table schema before statistical verification.",
    "Run sandbox checks for p-value bounds and N consistency.",
    "Emit verdict with confidence tags and unresolved gaps.",
  ],
  sandbox_code: [
    "# Sandbox Execution (read-only)",
    "import pandas as pd",
    "from scipy import stats",
    "",
    "df = pd.DataFrame({'group': ['A', 'B'], 'mean': [4.1, 5.0], 'n': [42, 40]})",
    "t, p = stats.ttest_ind_from_stats(4.1, 1.2, 42, 5.0, 1.1, 40, equal_var=False)",
    "print({'t_stat': round(float(t), 4), 'p_value': round(float(p), 4)})",
  ].join("\n"),
  verdict: {
    label: "Caution",
    detail: "Core claim is supported, but table-level N mismatch needs manual reconciliation.",
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
  "paper-2023-imaging": BASE_NOTEBOOK,
  "paper-2024-glucose": {
    ...BASE_NOTEBOOK,
    verdict: {
      label: "Pass",
      detail: "All mandatory checks passed with consistent evidence spans.",
      level: "pass",
    },
  },
  "paper-2025-nutrition": {
    ...BASE_NOTEBOOK,
    claims: [
      ...BASE_NOTEBOOK.claims.slice(0, 2),
      {
        claim_id: "claim-3",
        text: "Claim text missing",
        confidence: "low",
      },
      ...BASE_NOTEBOOK.claims.slice(3),
    ],
    highlights: [
      BASE_NOTEBOOK.highlights[0],
      { claim_id: "claim-2", page: 4, top: 0, left: 0, width: 0, height: 0 },
      { claim_id: "claim-3", page: 5, top: 0, left: 0, width: 0, height: 0 },
      ...BASE_NOTEBOOK.highlights.slice(3),
    ],
    verdict: {
      label: "Fail",
      detail: "Verifier failed due to unresolved schema mismatch in telemetry summary table.",
      level: "fail",
    },
  },
  "paper-2022-omics": BASE_NOTEBOOK,
  "paper-2026-ambiguous": {
    ...BASE_NOTEBOOK,
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
  total: 2,
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

export function getMockHealth(): { status: string; version: string } {
  return { status: "ok", version: "mock-3.0" };
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
  const notebook = NOTEBOOK_BY_PAPER[paper.paper_id] ?? BASE_NOTEBOOK;
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
  const notebook = NOTEBOOK_BY_PAPER[paperId] ?? BASE_NOTEBOOK;
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
  const response = deepClone(MOCK_MEETING_PACK_RESPONSE);
  response.pack.id = packId || MOCK_MEETING_PACK_ID;
  return response;
}

export function getMockMeetingPackIndex(): MeetingPackListResponse {
  return deepClone(MOCK_MEETING_PACK_LIST_RESPONSE);
}

export function getMockMeetingPackTrace(packId: string): MeetingPackTraceResponse {
  const response = deepClone(MOCK_MEETING_PACK_TRACE_RESPONSE);
  response.pack_id = packId || MOCK_MEETING_PACK_ID;
  return response;
}

export function getMockMeetingPackValidation(packId: string): MeetingPackValidationResponse {
  const response = deepClone(MOCK_MEETING_PACK_VALIDATION_RESPONSE);
  response.validation.pack_id = packId || MOCK_MEETING_PACK_ID;
  return response;
}

export function getMockMethodComparison(comparisonId: string): MethodComparisonResponse {
  const response = deepClone(MOCK_METHOD_COMPARISON_RESPONSE);
  response.comparison.comparison_id = comparisonId || MOCK_METHOD_COMPARISON_ID;
  return response;
}

export function getMockMethodComparisonIndex(): MethodComparisonListResponse {
  return deepClone(MOCK_METHOD_COMPARISON_LIST_RESPONSE);
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
      checkCount > 0 ? `Stats report contains ${checkCount} checks.` : "Stats report is missing or empty.",
    ],
    sandbox_code: "# Sandbox Execution (read-only)\n# Parsed from backend artifact bundle.",
    verdict: {
      label: checkCount > 0 ? "Review" : "Pending",
      detail:
        checkCount > 0
          ? "Artifact loaded from backend. Verify stats checks and evidence links."
          : "Claimset loaded, but stats report is not available yet.",
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
      `Loaded ${parsedClaims.length} structured claims from canonical state.json.`,
      lastRun ? `Latest skill action: ${asString(lastRun.action) ?? "unknown"} (${asString(lastRun.status) ?? "unknown"}).` : "No skill run metadata recorded.",
      checkCount > 0 ? `Stats report contains ${checkCount} checks.` : "Stats report is missing or empty.",
    ],
    sandbox_code: "# Sandbox Execution (read-only)\n# Canonical structured paper state loaded from state.json.",
    verdict: {
      label: checkCount > 0 ? "Review" : "Pending",
      detail:
        checkCount > 0
          ? "Canonical structured state loaded from the paper note sidecar. Verify stats checks and evidence links."
          : "Canonical structured state loaded, but stats report is not available yet.",
      level: "caution",
    },
  };
}

export { SAMPLE_PDF };
