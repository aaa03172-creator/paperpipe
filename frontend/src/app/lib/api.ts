import { apiPath, APP_CONFIG } from "./config";
import {
  ApiResult,
  ArtifactBundle,
  ChartPackListResponse,
  ChartPackResponse,
  ImageEvidenceListResponse,
  ImageEvidenceResponse,
  JobEnqueueResponse,
  JobStatus,
  MethodComparisonListResponse,
  MethodComparisonResponse,
  MeetingPackListResponse,
  MeetingPackRequestSnapshot,
  MeetingPackResponse,
  MeetingPackTraceResponse,
  MeetingPackValidationResponse,
  ObsidianMirror,
  ObsidianSyncResponse,
  PaperDetail,
  PaperNoteDetailResponse,
  PaperNoteListResponse,
  PaperNoteStructuredStateLookupResponse,
  PaperSummary,
  PersonaListResponse,
  ProtocolCardListResponse,
  ProtocolCardResponse,
  ReasoningPersonaId,
  SkillRunResponse,
  TimelineResponse,
  StatsRepairResponse,
} from "./types";
import {
  createMockMeetingPack,
  createMockJob,
  getMockChartPack,
  getMockChartPackIndex,
  getMockImageEvidence,
  getMockImageEvidenceIndex,
  getMockArtifactsLatest,
  getMockHealth,
  getMockMethodComparison,
  getMockMethodComparisonIndex,
  getMockMeetingPackIndex,
  getMockMeetingPack,
  getMockMeetingPackTrace,
  getMockMeetingPackValidation,
  getMockMeetingPackReadOnlyFallbackValidation,
  getMockJob,
  getMockJobs,
  getMockObsidianMirror,
  getMockPaper,
  getMockPapers,
  getMockPersonas,
  getMockProtocolCard,
  getMockProtocolCardIndex,
  getMockTimeline,
  SAMPLE_PDF,
} from "./mock";

const FORCE_MOCK_REASON = "mock mode forced by VITE_FORCE_MOCK";

interface DeepReadRequest {
  paper_id: string;
  run_verify: boolean;
  clean_reindex: boolean;
  persona_id?: string;
  reasoning_persona?: ReasoningPersonaId;
  profile_id?: string;
  parser_backend?: "fitz_pdfplumber" | "docling";
}

interface RepairStatsRequest {
  paper_ids: string[];
  run_id?: string | null;
  artifacts_root?: string;
  max_checks?: number;
  write_bootstrap_meta?: boolean;
  skip_existing?: boolean;
  dry_run?: boolean;
}

interface SkillRunRequest {
  slug: string;
  action: "extract_markdown" | "validate_citations" | "critical_appraisal";
  append_markdown_summary?: boolean;
  force?: boolean;
}

interface ClientUserActionRequest {
  paper_id?: string | null;
  action_type: string;
  source?: string;
  payload?: Record<string, unknown>;
}

class ApiHttpError extends Error {
  status: number;
  path: string;
  responseBody?: string;

  constructor(path: string, status: number, statusText: string, responseBody?: string) {
    super(`${path} -> ${status} ${statusText}`);
    this.path = path;
    this.status = status;
    this.responseBody = responseBody;
  }
}

function isApiHttpError(error: unknown): error is ApiHttpError {
  return error instanceof ApiHttpError;
}

function canUseAutoMockFallback(): boolean {
  return APP_CONFIG.autoMockFallback && !APP_CONFIG.strictApi;
}

function requestHeaders(init?: RequestInit, includeJsonContentType = true): HeadersInit {
  const headers = new Headers(init?.headers ?? undefined);
  if (includeJsonContentType && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (APP_CONFIG.apiKey && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", APP_CONFIG.apiKey);
  }
  return headers;
}

function normalizePaperStatus(raw?: string): PaperSummary["status"] {
  const value = (raw ?? "").toLowerCase();
  if (value.includes("process") || value === "running" || value === "queued") {
    return "processing";
  }
  if (value.includes("complete") || value === "done") {
    return "completed";
  }
  if (value.includes("fail") || value.includes("error") || value.includes("cancel")) {
    return "failed";
  }
  return "not_started";
}

function withTimeout(signal?: AbortSignal | null): { signal: AbortSignal; cancel: () => void } {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), APP_CONFIG.requestTimeoutMs);
  const onAbort = () => controller.abort();
  if (signal) {
    signal.addEventListener("abort", onAbort, { once: true });
  }
  return {
    signal: controller.signal,
    cancel: () => {
      clearTimeout(timeoutId);
      if (signal) {
        signal.removeEventListener("abort", onAbort);
      }
    },
  };
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const timeout = withTimeout(init?.signal);
  try {
    const response = await fetch(apiPath(path), {
      ...init,
      signal: timeout.signal,
      headers: requestHeaders(init),
    });

    if (!response.ok) {
      const responseBody = await response.text().catch(() => "");
      throw new ApiHttpError(path, response.status, response.statusText, responseBody);
    }

    return (await response.json()) as T;
  } finally {
    timeout.cancel();
  }
}

async function fetchBlobFromUrl(url: string, init?: RequestInit): Promise<Blob> {
  const timeout = withTimeout(init?.signal);
  try {
    const response = await fetch(url, {
      ...init,
      signal: timeout.signal,
      headers: requestHeaders(init, false),
    });

    if (!response.ok) {
      const responseBody = await response.text().catch(() => "");
      throw new ApiHttpError(url, response.status, response.statusText, responseBody);
    }

    return await response.blob();
  } finally {
    timeout.cancel();
  }
}

async function looksLikePdfBlob(blob: Blob): Promise<boolean> {
  if (blob.size <= 0) {
    return false;
  }

  const mimeType = blob.type.toLowerCase();
  if (mimeType.includes("pdf")) {
    return true;
  }

  const headerBytes = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
  if (headerBytes.length < 5) {
    return false;
  }
  const header = String.fromCharCode(...headerBytes);
  return header.startsWith("%PDF-");
}

async function firstSuccess<T>(paths: string[], init?: RequestInit): Promise<T> {
  let lastError: unknown;
  for (const path of paths) {
    try {
      return await fetchJson<T>(path, init);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("request failed");
}

async function withMockFallback<T>(
  fetcher: () => Promise<T>,
  mocker: () => T,
  reason: string,
): Promise<ApiResult<T>> {
  if (APP_CONFIG.forceMock) {
    return { data: mocker(), isMock: true, reason: FORCE_MOCK_REASON };
  }
  try {
    return { data: await fetcher(), isMock: false };
  } catch (error) {
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return { data: mocker(), isMock: true, reason };
  }
}

export function getApiErrorMessage(error: unknown): string {
  if (isApiHttpError(error)) {
    const body = (error.responseBody ?? "").trim();
    if (body.length > 0) {
      return `${error.message}: ${body}`;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown API error";
}

function normalizePaper(raw: Record<string, unknown>): PaperSummary {
  const status = normalizePaperStatus(typeof raw.status === "string" ? raw.status : undefined);
  const issues = typeof raw.issues === "number" ? raw.issues : status === "failed" ? 1 : 0;
  const issuesLabel = typeof raw.issues_label === "string" && raw.issues_label.trim()
    ? raw.issues_label.trim()
    : issues > 0
      ? `⚠️ ${issues} Issues`
      : "No critical issues";
  const issuesState =
    raw.issues_state === "flagged" || raw.issues_state === "clear" || raw.issues_state === "unavailable"
      ? raw.issues_state
      : undefined;
  const rawOpsSummary =
    raw.ops_summary && typeof raw.ops_summary === "object" && !Array.isArray(raw.ops_summary)
      ? (raw.ops_summary as Record<string, unknown>)
      : null;

  return {
    paper_id: String(raw.paper_id ?? "unknown-paper"),
    title: String(raw.title ?? raw.paper_id ?? "Untitled"),
    authors: raw.authors ? String(raw.authors) : undefined,
    year: typeof raw.year === "number" ? raw.year : undefined,
    pdf_exists: raw.pdf_exists === true,
    pdf_path: raw.pdf_path ? String(raw.pdf_path) : undefined,
    status,
    issues,
    issues_label: issuesLabel,
    issues_state: issuesState,
    updated_at: raw.updated_at ? String(raw.updated_at) : undefined,
    ops_summary: rawOpsSummary
      ? {
          state: rawOpsSummary.state === "healthy" ? "healthy" : "action_needed",
          label: String(rawOpsSummary.label ?? ""),
          reason: String(rawOpsSummary.reason ?? ""),
          recommended_action:
            rawOpsSummary.recommended_action === "repair_stats" || rawOpsSummary.recommended_action === "open_workbench"
              ? rawOpsSummary.recommended_action
              : "none",
          latest_run_id: rawOpsSummary.latest_run_id ? String(rawOpsSummary.latest_run_id) : null,
          has_claimset: rawOpsSummary.has_claimset === true,
          has_stats_report: rawOpsSummary.has_stats_report === true,
          stats_check_count:
            typeof rawOpsSummary.stats_check_count === "number" ? rawOpsSummary.stats_check_count : 0,
        }
      : null,
  };
}

function emptyArtifactBundle(paperId: string): ArtifactBundle {
  return {
    paper_id: paperId,
    run_id: "",
    files: {
      document_artifact: { exists: false },
      index_artifact: { exists: false },
      claimset: { exists: false },
      claimset_resolved: { exists: false },
      stats_report: { exists: false },
      bootstrap_meta: { exists: false },
      run_meta: { exists: false },
      chunks: { exists: false },
    },
  };
}

export async function getHealth(): Promise<ApiResult<{ status: string; version?: string }>> {
  return withMockFallback(
    () => fetchJson<{ status: string; version?: string }>("/health"),
    () => getMockHealth(),
    "health endpoint unavailable",
  );
}

export async function getPapers(): Promise<ApiResult<PaperSummary[]>> {
  return withMockFallback(
    async () => {
      const rows = await firstSuccess<Record<string, unknown>[]>(["/papers?limit=5000"]);
      if (!Array.isArray(rows)) {
        throw new Error("invalid papers response");
      }
      return rows.map(normalizePaper);
    },
    () => getMockPapers(),
    "papers endpoint unavailable",
  );
}

export async function getPaper(paperId: string): Promise<ApiResult<PaperDetail>> {
  return withMockFallback(
    async () => {
      const row = await firstSuccess<Record<string, unknown>>([`/papers/${encodeURIComponent(paperId)}`]);
      return normalizePaper(row) as PaperDetail;
    },
    () => getMockPaper(paperId),
    "paper detail unavailable",
  );
}

interface PaperNoteListQuery {
  q?: string;
  tag?: string;
  tags?: string[];
  status?: string;
  structuredOnly?: boolean;
  sortBy?: "date_processed" | "confidence";
  sortOrder?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}

function buildPaperNotesQuery(params?: PaperNoteListQuery): string {
  const query = new URLSearchParams();
  if (params?.q?.trim()) {
    query.set("q", params.q.trim());
  }
  if (params?.tag?.trim()) {
    query.set("tag", params.tag.trim());
  }
  if (params?.tags && params.tags.length > 0) {
    const normalized = Array.from(
      new Set(
        params.tags
          .map((value) => value.trim())
          .filter((value) => value.length > 0),
      ),
    );
    if (normalized.length > 0) {
      query.set("tags", normalized.join(","));
    }
  }
  if (params?.status?.trim()) {
    query.set("status", params.status.trim());
  }
  if (params?.structuredOnly) {
    query.set("structured_only", "true");
  }
  if (params?.sortBy) {
    query.set("sort_by", params.sortBy);
  }
  if (params?.sortOrder) {
    query.set("sort_order", params.sortOrder);
  }
  if (typeof params?.page === "number" && Number.isFinite(params.page) && params.page > 0) {
    query.set("page", String(Math.floor(params.page)));
  }
  if (typeof params?.pageSize === "number" && Number.isFinite(params.pageSize) && params.pageSize > 0) {
    query.set("page_size", String(Math.floor(params.pageSize)));
  }
  const queryText = query.toString();
  return queryText ? `?${queryText}` : "";
}

export async function getPaperNotesIndex(params?: PaperNoteListQuery): Promise<ApiResult<PaperNoteListResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: {
        generated_at: new Date().toISOString(),
        index_path: "storage/obsidian/paper_notes_index.json",
        total: 0,
        page: 1,
        page_size: 30,
        total_pages: 1,
        available_tags: [],
        available_statuses: [],
        items: [],
      },
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  const query = buildPaperNotesQuery(params);
  return {
    data: await firstSuccess<PaperNoteListResponse>([`/paper-notes${query}`]),
    isMock: false,
  };
}

export async function getPaperNoteDetail(slug: string): Promise<ApiResult<PaperNoteDetailResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: {
        note: {
          slug,
          title: "Mock paper note",
          note_path: `Inbox/PaperPipe/${slug}.md`,
          aliases: [],
          tags: [],
        },
        frontmatter: {},
        body_markdown: "# Mock note\n\nMock mode enabled.",
        related: [],
        references: [],
        structured_state: null,
        available_actions: [],
      },
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<PaperNoteDetailResponse>([`/paper-notes/${encodeURIComponent(slug)}`]),
    isMock: false,
  };
}

export async function getPaperNoteStructuredStateByPaperId(
  paperId: string,
): Promise<ApiResult<PaperNoteStructuredStateLookupResponse | null>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: null,
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<PaperNoteStructuredStateLookupResponse>([
        `/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(paperId)}`,
      ]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      return {
        data: null,
        isMock: false,
        reason: "structured paper note not found",
      };
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: null,
      isMock: true,
      reason: "structured paper note lookup unavailable",
    };
  }
}

export async function getMeetingPack(packId: string): Promise<ApiResult<MeetingPackResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMeetingPack(packId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<MeetingPackResponse>([`/meeting-packs/${encodeURIComponent(packId)}`]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      throw error;
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: getMockMeetingPack(packId),
      isMock: true,
      reason: "meeting pack unavailable, mock draft loaded",
    };
  }
}

export async function getMeetingPackIndex(): Promise<ApiResult<MeetingPackListResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMeetingPackIndex(),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return withMockFallback(
    () => firstSuccess<MeetingPackListResponse>(["/meeting-packs"]),
    () => getMockMeetingPackIndex(),
    "meeting pack index unavailable, mock drafts loaded",
  );
}

export async function generateMeetingPack(
  payload: MeetingPackRequestSnapshot,
): Promise<ApiResult<MeetingPackResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: createMockMeetingPack(payload),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await fetchJson<MeetingPackResponse>("/meeting-packs/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
      isMock: false,
    };
  } catch (error) {
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: createMockMeetingPack(payload),
      isMock: true,
      reason: "meeting pack generation unavailable, mock draft created",
    };
  }
}

export async function getMethodComparison(comparisonId: string): Promise<ApiResult<MethodComparisonResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMethodComparison(comparisonId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<MethodComparisonResponse>([
      `/method-comparisons/${encodeURIComponent(comparisonId)}`,
    ]),
    isMock: false,
  };
}

export async function getMethodComparisonIndex(): Promise<ApiResult<MethodComparisonListResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMethodComparisonIndex(),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<MethodComparisonListResponse>(["/method-comparisons"]),
    isMock: false,
  };
}

export function getMethodComparisonCsvUrl(comparisonId: string): string {
  return apiPath(`/method-comparisons/${encodeURIComponent(comparisonId)}/export.csv`);
}

export async function getChartPack(chartPackId: string): Promise<ApiResult<ChartPackResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockChartPack(chartPackId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<ChartPackResponse>([
      `/chart-packs/${encodeURIComponent(chartPackId)}`,
    ]),
    isMock: false,
  };
}

export async function getChartPackIndex(): Promise<ApiResult<ChartPackListResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockChartPackIndex(),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<ChartPackListResponse>(["/chart-packs"]),
    isMock: false,
  };
}

export async function getImageEvidence(imageEvidenceId: string): Promise<ApiResult<ImageEvidenceResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockImageEvidence(imageEvidenceId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<ImageEvidenceResponse>([
      `/image-evidence/${encodeURIComponent(imageEvidenceId)}`,
    ]),
    isMock: false,
  };
}

export async function getImageEvidenceIndex(): Promise<ApiResult<ImageEvidenceListResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockImageEvidenceIndex(),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<ImageEvidenceListResponse>(["/image-evidence"]),
    isMock: false,
  };
}

export async function getProtocolCard(protocolId: string): Promise<ApiResult<ProtocolCardResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockProtocolCard(protocolId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<ProtocolCardResponse>([
      `/protocol-cards/${encodeURIComponent(protocolId)}`,
    ]),
    isMock: false,
  };
}

export async function getProtocolCardIndex(): Promise<ApiResult<ProtocolCardListResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockProtocolCardIndex(),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await firstSuccess<ProtocolCardListResponse>(["/protocol-cards"]),
    isMock: false,
  };
}

export function getChartPackDataCsvUrl(chartPackId: string, chartId: string): string {
  return apiPath(
    `/chart-packs/${encodeURIComponent(chartPackId)}/charts/${encodeURIComponent(chartId)}/data.csv`,
  );
}

export function getChartPackSpecUrl(chartPackId: string, chartId: string): string {
  return apiPath(
    `/chart-packs/${encodeURIComponent(chartPackId)}/charts/${encodeURIComponent(chartId)}/spec.json`,
  );
}

export async function getMeetingPackTrace(packId: string): Promise<ApiResult<MeetingPackTraceResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMeetingPackTrace(packId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<MeetingPackTraceResponse>([`/meeting-packs/${encodeURIComponent(packId)}/trace`]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      throw error;
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: getMockMeetingPackTrace(packId),
      isMock: true,
      reason: "meeting pack trace unavailable, mock trace loaded",
    };
  }
}

export async function getMeetingPackValidation(packId: string): Promise<ApiResult<MeetingPackValidationResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMeetingPackValidation(packId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<MeetingPackValidationResponse>([
        `/meeting-packs/${encodeURIComponent(packId)}/validate`,
      ]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      throw error;
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: getMockMeetingPackReadOnlyFallbackValidation(packId),
      isMock: true,
      reason: "meeting pack validation unavailable, mock validation loaded",
    };
  }
}

export async function regenerateMeetingPack(packId: string): Promise<ApiResult<MeetingPackResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMeetingPack(packId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await fetchJson<MeetingPackResponse>(`/meeting-packs/${encodeURIComponent(packId)}/regenerate`, {
      method: "POST",
    }),
    isMock: false,
  };
}

export async function rerenderMeetingPack(packId: string): Promise<ApiResult<MeetingPackResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockMeetingPack(packId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  return {
    data: await fetchJson<MeetingPackResponse>(`/meeting-packs/${encodeURIComponent(packId)}/rerender`, {
      method: "POST",
    }),
    isMock: false,
  };
}

export async function runSkillAction(payload: SkillRunRequest): Promise<SkillRunResponse> {
  return firstSuccess<SkillRunResponse>(["/skills/run"], {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getJobsForPaper(paperId: string): Promise<ApiResult<JobStatus[]>> {
  return withMockFallback(
    async () => {
      const data = await firstSuccess<unknown>([
        `/jobs?paper_id=${encodeURIComponent(paperId)}`,
      ]);
      if (Array.isArray(data)) {
        return data as JobStatus[];
      }
      if (data && typeof data === "object" && Array.isArray((data as { jobs?: JobStatus[] }).jobs)) {
        return (data as { jobs: JobStatus[] }).jobs;
      }
      throw new Error("jobs response shape mismatch");
    },
    () => getMockJobs(paperId),
    "jobs query endpoint unavailable",
  );
}

export async function getJob(jobId: string): Promise<ApiResult<JobStatus>> {
  return withMockFallback(
    () => firstSuccess<JobStatus>([`/jobs/${encodeURIComponent(jobId)}`]),
    () => getMockJob(jobId),
    "job endpoint unavailable",
  );
}

export async function enqueueDeepRead(payload: DeepReadRequest): Promise<ApiResult<JobEnqueueResponse>> {
  if (APP_CONFIG.forceMock) {
    return { data: createMockJob(), isMock: true, reason: FORCE_MOCK_REASON };
  }
  try {
    return {
      data: await firstSuccess<JobEnqueueResponse>(["/jobs/deepread"], {
        method: "POST",
        body: JSON.stringify(payload),
      }),
      isMock: false,
    };
  } catch (error) {
    // Backend returned a valid 4xx response (e.g. duplicate open job, auth, validation):
    // surface it to UI instead of masking with mock enqueue.
    if (isApiHttpError(error) && error.status >= 400 && error.status < 500) {
      throw error;
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: createMockJob(),
      isMock: true,
      reason: "deepread enqueue unavailable",
    };
  }
}

export function logClientUserAction(payload: ClientUserActionRequest): void {
  if (APP_CONFIG.forceMock) {
    return;
  }

  const body = JSON.stringify({
    paper_id: payload.paper_id ?? null,
    action_type: payload.action_type,
    source: payload.source ?? "ui",
    payload: payload.payload ?? null,
  });

  void fetch(apiPath("/user-actions"), {
    method: "POST",
    body,
    headers: requestHeaders(undefined),
    keepalive: true,
  }).catch(() => undefined);
}

export async function repairStats(payload: RepairStatsRequest): Promise<ApiResult<StatsRepairResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: {
        seeded: 1,
        planned: 0,
        skipped: 0,
        total: 1,
        results: [
          {
            paper_id: payload.paper_ids[0] ?? "mock-paper",
            run_id: payload.run_id ?? "run-mock-001",
            status: "seeded",
            checks: 3,
            reason: "claimset.json",
          },
        ],
      },
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<StatsRepairResponse>(["/ops/repair-stats"], {
        method: "POST",
        body: JSON.stringify(payload),
      }),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status >= 400 && error.status < 500) {
      throw error;
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: {
        seeded: 0,
        planned: 0,
        skipped: Math.max(1, payload.paper_ids.length),
        total: Math.max(1, payload.paper_ids.length),
        results: (payload.paper_ids.length > 0 ? payload.paper_ids : ["mock-paper"]).map((paperId) => ({
          paper_id: paperId,
          run_id: payload.run_id ?? null,
          status: "skipped" as const,
          checks: 0,
          reason: "repair-stats endpoint unavailable",
        })),
      },
      isMock: true,
      reason: "repair-stats endpoint unavailable",
    };
  }
}

export async function getArtifactsLatest(paperId: string): Promise<ApiResult<ArtifactBundle>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockArtifactsLatest(paperId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  try {
    return {
      data: await firstSuccess<ArtifactBundle>([`/artifacts/${encodeURIComponent(paperId)}/latest`]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      return {
        data: emptyArtifactBundle(paperId),
        isMock: false,
        reason: "artifact not generated yet",
      };
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: getMockArtifactsLatest(paperId),
      isMock: true,
      reason: "artifact latest unavailable",
    };
  }
}

export async function getRunTimeline(runId: string): Promise<ApiResult<TimelineResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockTimeline(runId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  try {
    return {
      data: await firstSuccess<TimelineResponse>([`/runs/${encodeURIComponent(runId)}/timeline`]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      return {
        data: { run_id: runId, events: [] },
        isMock: false,
        reason: "timeline not generated yet",
      };
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: getMockTimeline(runId),
      isMock: true,
      reason: "timeline endpoint unavailable",
    };
  }
}

export async function getObsidianMirror(paperId: string, runId: string): Promise<ApiResult<ObsidianMirror | null>> {
  if (!runId || runId.trim().length === 0) {
    return {
      data: null,
      isMock: false,
      reason: "run id unavailable",
    };
  }

  if (APP_CONFIG.forceMock) {
    return {
      data: getMockObsidianMirror(paperId, runId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<ObsidianMirror>([
        `/obsidian/mirror?paper_id=${encodeURIComponent(paperId)}&run_id=${encodeURIComponent(runId)}`,
      ]),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      return {
        data: null,
        isMock: false,
        reason: "obsidian mirror not generated yet",
      };
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: getMockObsidianMirror(paperId, runId),
      isMock: true,
      reason: "obsidian mirror unavailable",
    };
  }
}

export async function syncToObsidian(paperId: string, runId: string): Promise<ApiResult<ObsidianSyncResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: {
        status: "synced",
        file: `obsidian/Inbox/${paperId}.md`,
        message: "Mock sync completed",
      },
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await firstSuccess<ObsidianSyncResponse>(["/obsidian/sync"], {
        method: "POST",
        body: JSON.stringify({ paper_id: paperId, run_id: runId }),
      }),
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status >= 400 && error.status < 500) {
      throw error;
    }
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    return {
      data: {
        status: "sync_failed",
        message: "sync endpoint unavailable",
      },
      isMock: true,
      reason: "obsidian sync unavailable",
    };
  }
}

export async function getPersonas(): Promise<ApiResult<PersonaListResponse>> {
  return withMockFallback(
    () => firstSuccess<PersonaListResponse>(["/personas"]),
    () => getMockPersonas(),
    "persona registry unavailable",
  );
}

export async function getPaperPdfBlobUrl(paperId: string): Promise<ApiResult<string>> {
  const apiPdfUrl = apiPath(`/papers/${encodeURIComponent(paperId)}/pdf`);
  if (APP_CONFIG.forceMock) {
    const mockBlob = await fetchBlobFromUrl(SAMPLE_PDF);
    if (!(await looksLikePdfBlob(mockBlob))) {
      throw new Error("mock sample PDF is invalid");
    }
    return {
      data: URL.createObjectURL(mockBlob),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    const pdfBlob = await fetchBlobFromUrl(apiPdfUrl);
    if (!(await looksLikePdfBlob(pdfBlob))) {
      throw new Error(`invalid PDF payload from ${apiPdfUrl}`);
    }
    return {
      data: URL.createObjectURL(pdfBlob),
      isMock: false,
    };
  } catch (error) {
    if (!canUseAutoMockFallback()) {
      throw error;
    }
    const mockBlob = await fetchBlobFromUrl(SAMPLE_PDF);
    if (!(await looksLikePdfBlob(mockBlob))) {
      throw error;
    }
    return {
      data: URL.createObjectURL(mockBlob),
      isMock: true,
      reason: "paper pdf unavailable, sample loaded",
    };
  }
}
