import {
  ArtifactBundle,
  ChartPackListResponse,
  ChartPackResponse,
  EvidenceHighlight,
  ImageEvidenceListResponse,
  ImageEvidenceResponse,
  JobEnqueueResponse,
  JobStatus,
  NotebookArtifact,
  ObsidianMirror,
  PaperDetail,
  PaperSummary,
  PersonaListResponse,
  TimelineResponse,
} from "./types";
import { buildBestHighlightMap, getClaimLinkState, isClaimTextMissing, normalizeHighlightsForUi } from "./claimGuard";

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
    updated_at: "2026-02-22T12:09:00Z",
    abstract: "Narrative review across metabolomics and transcriptomics cohorts.",
  },
  {
    paper_id: "paper-2026-normalized-bbox",
    title: "Assessment of RAG Systems in Agentic Workflows",
    authors: "Jane Smith et al.",
    year: 2026,
    pdf_exists: true,
    pdf_path: SAMPLE_PDF,
    status: "processing",
    issues: 0,
    issues_label: "No critical issues",
    latest_job_id: "job-004",
    latest_run_id: "run-004",
    updated_at: "2026-03-09T06:00:00Z",
    abstract: "Synthetic fixture for normalized bbox and zero-based page compatibility.",
  },
];

const MOCK_JOBS: Record<string, JobStatus[]> = {
  "paper-2023-imaging": [
    {
      job_id: "job-001",
      paper_id: "paper-2023-imaging",
      run_id: "run-001",
      persona_id: "clinical-triage",
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
  "paper-2026-normalized-bbox": [
    {
      job_id: "job-004",
      paper_id: "paper-2026-normalized-bbox",
      run_id: "run-004",
      persona_id: "default",
      status: "running",
      progress: 44,
      stage: "read",
      created_at: "2026-03-09T05:58:00Z",
      started_at: "2026-03-09T05:58:20Z",
    },
  ],
};

const BASE_NOTEBOOK: NotebookArtifact = {
  claims: [
    {
      claim_id: "claim-1",
      text: "① Intervention arm showed lower glucose variability at week 12 compared with control.",
      confidence: "high",
    },
    {
      claim_id: "claim-2",
      text: "② Reported effect size was moderate, but heterogeneity increased in subgroup B.",
      confidence: "medium",
    },
    {
      claim_id: "claim-3",
      text: "③ Two tables report slightly inconsistent participant counts (N mismatch).",
      confidence: "low",
    },
    {
      claim_id: "claim-4",
      text: "④ Primary endpoint remains directionally robust after sensitivity analysis.",
      confidence: "medium",
    },
  ],
  highlights: [
    { claim_id: "claim-1", page: 3, top: 14, left: 11, width: 38, height: 8 },
    { claim_id: "claim-2", page: 4, top: 36, left: 9, width: 44, height: 9 },
    { claim_id: "claim-3", page: 5, top: 57, left: 12, width: 40, height: 8 },
    { claim_id: "claim-4", page: 7, top: 24, left: 10, width: 46, height: 8 },
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
  "paper-2026-normalized-bbox": {
    claims: [
      {
        claim_id: "claim-1",
        text: "① Section-aware method achieved a hit rate above baseline.",
        confidence: "high",
      },
      {
        claim_id: "claim-2",
        text: "② Limitations include sparse tables in older PDFs.",
        confidence: "medium",
      },
      {
        claim_id: "claim-3",
        text: "③ Older papers may lack clear PDF headers, so text fallback should still locate the limitation sentence.",
        confidence: "medium",
      },
    ],
    highlights: [
      { claim_id: "claim-1", page: 0, top: 0.30, left: 0.13, width: 0.52, height: 0.22, source: "bbox" },
      { claim_id: "claim-2", page: 1, top: 0.52, left: 0.10, width: 0.70, height: 0.13, source: "bbox" },
      {
        claim_id: "claim-3",
        page: 0,
        top: 0,
        left: 0,
        width: 0,
        height: 0,
        quote: "Limitations include the reliance on clear PDF headers, which older papers may lack.",
        source: "text_match",
      },
    ],
    agent_plan: [
      "Validate page-index conversion from zero-based artifacts.",
      "Validate normalized bbox conversion from 0~1 unit values.",
      "Validate text-match fallback on the same normalized fixture.",
    ],
    sandbox_code: "# Sandbox Execution (read-only)\n# fixture: normalized bbox",
    verdict: {
      label: "Review",
      detail: "Normalization fixture loaded for anchor-mapping validation.",
      level: "caution",
    },
  },
};

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
    paper_id: "paper-2026-normalized-bbox",
    events: [
      {
        event: "log",
        source: "job_log",
        ts: "2026-03-09T05:58:32Z",
        stage: "ingest",
        level: "INFO",
        message: "Loaded normalized bbox fixture claimset.",
      },
      {
        event: "status",
        source: "synthetic",
        ts: "2026-03-09T05:58:55Z",
        stage: "read",
        progress: 44,
        level: "INFO",
        message: "reader running",
      },
    ],
  },
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
      { id: "default", title: "Default (No Persona Override)", enabled: true, source: "builtin" },
      { id: "clinical-triage", title: "Clinical Triage", enabled: true, source: "yaml", notes: "Risk-first claim synthesis" },
      { id: "stats-auditor", title: "Stats Auditor", enabled: true, source: "yaml", notes: "Strict numeric validation" },
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
        hypothesis: "Primary summary consistency",
        notes: notebook.verdict.detail,
        decision_error: notebook.verdict.level === "fail",
      },
      {
        check_id: "mock-check-2",
        test_type: "effect-size",
        verdict: "verified",
        claim_id: "claim-2",
        evidence_page: 4,
        hypothesis: "Subgroup-B effect-size direction",
        notes: "Effect-size direction preserved across subgroup split.",
        decision_error: false,
      },
    ],
  };
}

export function getMockTimeline(runId: string): TimelineResponse {
  const fallback = MOCK_TIMELINES["run-001"];
  return deepClone(MOCK_TIMELINES[runId] ?? fallback);
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

  return {
    left: clampPct((minX / pageWidth) * 100),
    top: clampPct((minY / pageHeight) * 100),
    width: clampPct(((maxX - minX) / pageWidth) * 100),
    height: clampPct(((maxY - minY) / pageHeight) * 100),
  };
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

  return {
    left: clampPct((minX / pageContext.width) * 100),
    top: clampPct((minY / pageContext.height) * 100),
    width: clampPct(((maxX - minX) / pageContext.width) * 100),
    height: clampPct(((maxY - minY) / pageContext.height) * 100),
  };
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
): Pick<EvidenceHighlight, "left" | "top" | "width" | "height"> | null {
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
    const isNormalized = bbox.left <= 1 && bbox.top <= 1 && bbox.width <= 1 && bbox.height <= 1;
    const scale = isNormalized ? 100 : 1;
    return {
      left: clampPct(bbox.left * scale),
      top: clampPct(bbox.top * scale),
      width: clampPct(bbox.width * scale),
      height: clampPct(bbox.height * scale),
    };
  }

  if (
    bbox &&
    typeof bbox.x === "number" &&
    typeof bbox.y === "number" &&
    typeof bbox.w === "number" &&
    typeof bbox.h === "number"
  ) {
    const isNormalized = bbox.x <= 1 && bbox.y <= 1 && bbox.w <= 1 && bbox.h <= 1;
    const scale = isNormalized ? 100 : 1;
    return {
      left: clampPct(bbox.x * scale),
      top: clampPct(bbox.y * scale),
      width: clampPct(bbox.w * scale),
      height: clampPct(bbox.h * scale),
    };
  }

  if (
    span &&
    typeof span.left === "number" &&
    typeof span.top === "number" &&
    typeof span.width === "number" &&
    typeof span.height === "number"
  ) {
    const isNormalized = span.left <= 1 && span.top <= 1 && span.width <= 1 && span.height <= 1;
    const scale = isNormalized ? 100 : 1;
    return {
      left: clampPct(span.left * scale),
      top: clampPct(span.top * scale),
      width: clampPct(span.width * scale),
      height: clampPct(span.height * scale),
    };
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

function normalizeNotebookForUi(notebook: NotebookArtifact): NotebookArtifact {
  const normalizedHighlights = normalizeHighlightsForUi(
    Array.isArray(notebook.highlights) ? notebook.highlights : [],
  );
  const normalizedClaims = (Array.isArray(notebook.claims) ? notebook.claims : []).map((claim) => ({
    ...claim,
    text_missing: claim.text_missing ?? isClaimTextMissing(claim.text),
  }));
  const highlightMap = buildBestHighlightMap(normalizedHighlights);
  const claimsWithGuard = normalizedClaims.map((claim) => ({
    ...claim,
    link_health: claim.link_health ?? getClaimLinkState(claim, highlightMap.get(claim.claim_id)).health,
  }));

  return {
    ...notebook,
    claims: claimsWithGuard,
    highlights: normalizedHighlights,
  };
}

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
        render_refs: [],
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
        render_refs: [],
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
        render_refs: [],
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

export function getNotebookFromBundle(bundle: ArtifactBundle): NotebookArtifact {
  const notebookData = bundle.files.notebook?.data;
  if (notebookData && typeof notebookData === "object") {
    return normalizeNotebookForUi(notebookData as NotebookArtifact);
  }

  const claimsetData = bundle.files.claimset_resolved?.data ?? bundle.files.claimset?.data;
  const statsData = bundle.files.stats_report?.data;
  const rawClaims = extractClaimsArray(claimsetData).slice(0, 20);

  if (rawClaims.length === 0) {
    return deepClone(EMPTY_NOTEBOOK);
  }

  const documentPages = parseDocumentPages(bundle.files.document_artifact?.data);
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
  const hasEvidenceSpans = rawClaims.some((claim) => Array.isArray(claim.evidence_spans));
  const hasLegacyEvidence = rawClaims.some((claim) => !Array.isArray(claim.evidence_spans) && Array.isArray(claim.evidence));
  const assumeZeroBased = hasEvidenceSpans && !hasLegacyEvidence;
  const hasZeroBasedPage = assumeZeroBased || rawPages.some((page) => page === 0);
  const parsedHighlights = rawClaims.map((claim, index) => {
    const primaryEvidence = extractEvidenceArray(claim)[0] ?? null;
    const rawPage = extractPageNumber(primaryEvidence);
    const resolvedPage = rawPage === null ? 1 : Math.max(hasZeroBasedPage ? rawPage + 1 : rawPage, 1);
    const hintedDocPageIndex = rawPage === null ? null : Math.max(hasZeroBasedPage ? rawPage : rawPage - 1, 0);
    const targetPageIndex = hintedDocPageIndex ?? Math.max(resolvedPage - 1, 0);
    const targetPage = documentPages.find((page) => page.pageIndex === targetPageIndex) ?? null;
    const bbox = extractBBoxPct(primaryEvidence);
    const bboxFromPdf = bbox ? null : extractBBoxFromPdf(primaryEvidence, targetPage);
    const fallbackBbox = bbox || bboxFromPdf
      ? null
      : findDocumentBboxForClaim(documentPages, hintedDocPageIndex, parsedClaims[index].text, primaryEvidence);

    const resolvedHighlightPage = fallbackBbox
      ? fallbackBbox.pageIndex + 1
      : bboxFromPdf && targetPage
        ? targetPage.pageIndex + 1
        : resolvedPage;

    return {
      claim_id: parsedClaims[index].claim_id,
      page: resolvedHighlightPage,
      left: bbox?.left ?? bboxFromPdf?.left ?? fallbackBbox?.left ?? 0,
      top: bbox?.top ?? bboxFromPdf?.top ?? fallbackBbox?.top ?? 0,
      width: bbox?.width ?? bboxFromPdf?.width ?? fallbackBbox?.width ?? 0,
      height: bbox?.height ?? bboxFromPdf?.height ?? fallbackBbox?.height ?? 0,
      quote: extractEvidenceQuote(primaryEvidence),
    };
  });

  const checkCount =
    statsData && typeof statsData === "object" && Array.isArray((statsData as { checks?: unknown[] }).checks)
      ? (statsData as { checks: unknown[] }).checks.length
      : 0;

  const normalizedHighlights = normalizeHighlightsForUi(parsedHighlights);
  const highlightMap = buildBestHighlightMap(normalizedHighlights);

  const parsedClaimsWithGuard = parsedClaims.map((claim) => {
    const highlight = highlightMap.get(claim.claim_id);
    const state = getClaimLinkState(claim, highlight);
    return {
      ...claim,
      link_health: state.health,
    };
  });

  return {
    claims: parsedClaimsWithGuard,
    highlights: normalizedHighlights,
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

export function getMockChartPack(chartPackId: string): ChartPackResponse {
  if (chartPackId === MOCK_SECONDARY_CHART_PACK_ID) {
    return deepClone(MOCK_SECONDARY_CHART_PACK_RESPONSE);
  }
  return deepClone(MOCK_CHART_PACK_RESPONSE);
}

export function getMockChartPackIndex(): ChartPackListResponse {
  return deepClone(MOCK_CHART_PACK_LIST_RESPONSE);
}

export { SAMPLE_PDF };
