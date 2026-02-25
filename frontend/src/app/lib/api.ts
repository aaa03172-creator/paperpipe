import { apiPath, APP_CONFIG } from "./config";
import {
  ApiResult,
  ArtifactBundle,
  JobEnqueueResponse,
  JobStatus,
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
  getMockTimeline,
  SAMPLE_PDF,
} from "./mock";

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
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
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
  try {
    return { data: await fetcher(), isMock: false };
  } catch {
    return { data: mocker(), isMock: true, reason };
  }
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
  return withMockFallback(
    () =>
      firstSuccess<JobEnqueueResponse>(["/jobs/deepread"], {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    () => createMockJob(),
    "deepread enqueue unavailable",
  );
}

export async function getArtifactsLatest(paperId: string): Promise<ApiResult<ArtifactBundle>> {
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
    return {
      data: getMockArtifactsLatest(paperId),
      isMock: true,
      reason: "artifact latest unavailable",
    };
  }
}

export async function getRunTimeline(runId: string): Promise<ApiResult<TimelineResponse>> {
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

export function getPaperPdfUrl(paperId: string, useMock: boolean): string {
  if (useMock) {
    return SAMPLE_PDF;
  }
  return apiPath(`/papers/${encodeURIComponent(paperId)}/pdf`);
}
