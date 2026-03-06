import { apiPath, APP_CONFIG } from "./config";
import {
  ApiResult,
  ArtifactBundle,
  JobEnqueueResponse,
  JobStatus,
  ObsidianMirror,
  ObsidianSyncResponse,
  PaperDetail,
  PaperSummary,
  PersonaListResponse,
  TimelineResponse,
} from "./types";
import {
  createMockJob,
  getMockArtifactsLatest,
  getMockHealth,
  getMockJob,
  getMockJobs,
  getMockPaper,
  getMockPapers,
  getMockPersonas,
  getMockObsidianMirror,
  getMockTimeline,
  SAMPLE_PDF,
} from "./mock";

const FORCE_MOCK_REASON = "mock mode forced by VITE_FORCE_MOCK";

interface DeepReadRequest {
  paper_id: string;
  run_verify: boolean;
  clean_reindex: boolean;
  persona_id: string;
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

function requestHeaders(init?: RequestInit): HeadersInit {
  const headers = new Headers(init?.headers ?? undefined);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (APP_CONFIG.apiKey && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", APP_CONFIG.apiKey);
  }
  return headers;
}

function binaryRequestHeaders(): HeadersInit {
  const headers = new Headers();
  if (APP_CONFIG.apiKey) {
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

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function firstRecord(value: unknown): Record<string, unknown> | null {
  const row = asArray(value).find((item) => asRecord(item) !== null);
  return row ? (row as Record<string, unknown>) : null;
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

async function fetchBlobObjectUrl(pathOrUrl: string, absoluteUrl = false): Promise<string> {
  const timeout = withTimeout();
  try {
    const target = absoluteUrl ? pathOrUrl : apiPath(pathOrUrl);
    const response = await fetch(target, {
      signal: timeout.signal,
      headers: binaryRequestHeaders(),
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new ApiHttpError(pathOrUrl, response.status, response.statusText, body);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  } finally {
    timeout.cancel();
  }
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
    if (APP_CONFIG.strictApi) {
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

  return {
    paper_id: String(raw.paper_id ?? "unknown-paper"),
    title: String(raw.title ?? raw.paper_id ?? "Untitled"),
    authors: raw.authors ? String(raw.authors) : undefined,
    year: typeof raw.year === "number" ? raw.year : undefined,
    pdf_exists: raw.pdf_exists === true,
    pdf_path: raw.pdf_path ? String(raw.pdf_path) : undefined,
    status,
    issues,
    issues_label: issues > 0 ? `⚠️ ${issues} Issues` : "No critical issues",
    updated_at: raw.updated_at ? String(raw.updated_at) : undefined,
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
      const rows = await firstSuccess<Record<string, unknown>[]>(["/papers"]);
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
    if (APP_CONFIG.strictApi) {
      throw error;
    }
    return {
      data: createMockJob(),
      isMock: true,
      reason: "deepread enqueue unavailable",
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
    if (APP_CONFIG.strictApi) {
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
    if (APP_CONFIG.strictApi) {
      throw error;
    }
    return {
      data: getMockTimeline(runId),
      isMock: true,
      reason: "timeline endpoint unavailable",
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

function normalizeObsidianMirrorFromArtifacts(
  paperId: string,
  runId: string,
  payload: Record<string, unknown>,
): ObsidianMirror {
  const claimsetData = asRecord(asRecord(payload.claimset)?.data);
  const statsData = asRecord(asRecord(payload.stats_report)?.data);

  const claims = asArray(claimsetData?.claims)
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => {
      const evidence = firstRecord(item.evidence_spans) ?? firstRecord(item.evidence);
      return {
        claim_id: asString(item.claim_id) ?? crypto.randomUUID(),
        claim_type: asString(item.type) ?? asString(item.claim_type) ?? "evidence",
        statement: asString(item.statement) ?? asString(item.claim_text) ?? "Claim text missing",
        confidence: asNumber(item.confidence) ?? 0,
        evidence_quote: asString(evidence?.quote) ?? asString(evidence?.raw_text),
        evidence_page: asNumber(evidence?.page),
        limitations: asArray(item.limitations)
          .map((entry) => asString(entry))
          .filter((entry): entry is string => entry !== null),
      };
    });

  const statsChecks = asArray(statsData?.checks)
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => ({
      check_id: asString(item.check_id) ?? crypto.randomUUID(),
      test_type: asString(item.test_type) ?? "unknown",
      verdict: asString(item.verdict) ?? "unknown",
      hypothesis: asString(item.hypothesis),
      notes: asString(item.notes),
      decision_error: Boolean(item.decision_error),
    }));

  const lines: string[] = [];
  lines.push("<!-- AI_AGENT_START -->");
  lines.push("## 🤖 PaperPipe AI Analysis");
  lines.push(`### 🧪 Scientific Claims (${claims.length})`);
  for (const claim of claims.slice(0, 8)) {
    lines.push(`- ${claim.statement}`);
  }
  lines.push(`### 📊 Statistical Verification (${statsChecks.length})`);
  for (const check of statsChecks.slice(0, 8)) {
    lines.push(`- ${check.test_type}: ${check.verdict}`);
  }
  lines.push("<!-- AI_AGENT_END -->");

  return {
    paper_id: asString(payload.paper_id) ?? paperId,
    run_id: asString(payload.run_id) ?? runId,
    generated_markdown: lines.join("\n"),
    has_claimset: claims.length > 0,
    has_stats_report: statsChecks.length > 0,
    claims,
    stats_checks: statsChecks,
  };
}

export async function getObsidianMirror(paperId: string, runId: string): Promise<ApiResult<ObsidianMirror>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockObsidianMirror(paperId, runId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  const query = `paper_id=${encodeURIComponent(paperId)}&run_id=${encodeURIComponent(runId)}`;
  try {
    return {
      data: await firstSuccess<ObsidianMirror>([`/obsidian/mirror?${query}`]),
      isMock: false,
    };
  } catch {
    try {
      const artifactsPayload = await firstSuccess<Record<string, unknown>>([`/obsidian/artifacts?${query}`]);
      return {
        data: normalizeObsidianMirrorFromArtifacts(paperId, runId, artifactsPayload),
        isMock: false,
      };
    } catch (error) {
      if (APP_CONFIG.strictApi) {
        throw error;
      }
      return {
        data: getMockObsidianMirror(paperId, runId),
        isMock: true,
        reason: "obsidian mirror unavailable",
      };
    }
  }
}

export async function syncToObsidian(paperId: string, runId: string): Promise<ApiResult<ObsidianSyncResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: {
        status: "mock_synced",
        message: "Mock mode: sync request was simulated.",
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
    if (APP_CONFIG.strictApi) {
      throw error;
    }
    return {
      data: {
        status: "mock_synced",
        message: "Sync endpoint unavailable. Returned mock response.",
      },
      isMock: true,
      reason: "obsidian sync unavailable",
    };
  }
}

export async function getPaperPdfBlobUrl(paperId: string): Promise<ApiResult<string>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: await fetchBlobObjectUrl(SAMPLE_PDF, true),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    return {
      data: await fetchBlobObjectUrl(`/papers/${encodeURIComponent(paperId)}/pdf`),
      isMock: false,
    };
  } catch (error) {
    if (APP_CONFIG.strictApi) {
      throw error;
    }
    return {
      data: await fetchBlobObjectUrl(SAMPLE_PDF, true),
      isMock: true,
      reason: "pdf endpoint unavailable",
    };
  }
}

export function getPaperPdfUrl(paperId: string, useMock: boolean): string {
  if (useMock) {
    return SAMPLE_PDF;
  }
  return apiPath(`/papers/${encodeURIComponent(paperId)}/pdf`);
}
