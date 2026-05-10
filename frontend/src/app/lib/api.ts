import { apiPath, APP_CONFIG } from "./config";
import {
  ApiResult,
  ArtifactBundle,
  ChartPackListResponse,
  ChartPackRequestSnapshot,
  ChartPackResponse,
  ImageEvidenceListResponse,
  ImageEvidenceResponse,
  JobEnqueueResponse,
  JobCancelResponse,
  JobStatus,
  MethodComparisonCreateRequest,
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
  PaperNotesHomeContext,
  PaperNoteImportResponse,
  PaperNoteListResponse,
  PaperNoteOperatorState,
  PaperNoteOperatorStateUpdateRequest,
  PaperNoteStructuredStateLookupResponse,
  PaperSynthesisManifest,
  PaperSynthesisListItem,
  PaperSynthesisListResponse,
  PaperSummary,
  PersonaListResponse,
  ProtocolCardListResponse,
  ProtocolAttachmentBundle,
  ProtocolAttachmentDraftResponse,
  ProtocolCardRequestSnapshot,
  ProtocolCardResponse,
  ReasoningPersonaId,
  RuntimeReadinessResponse,
  SkillRunResponse,
  TimelineResponse,
  StatsRepairResponse,
} from "./types";
import {
  createMockJob,
  createMockChartPack,
  createMockProtocolCard,
  getMockChartPack,
  getMockChartPackIndex,
  getMockImageEvidence,
  getMockImageEvidenceIndex,
  getMockArtifactsLatest,
  getMockHealth,
  getMockPaperNoteDetail,
  getMockPaperNotesHomeContext,
  getMockPaperNotesIndex,
  getMockPaperNoteOperatorState,
  getMockPaperNoteStructuredStateByPaperId,
  getMockMethodComparison,
  getMockMethodComparisonIndex,
  createMockMeetingPack,
  getMockMeetingPackIndex,
  getMockMeetingPack,
  getMockMeetingPackTrace,
  getMockMeetingPackValidation,
  createMockMethodComparison,
  getMockJob,
  getMockJobs,
  getMockObsidianMirror,
  getMockPaper,
  getMockPapers,
  getMockPersonas,
  getMockProtocolCard,
  getMockProtocolCardIndex,
  getMockTimeline,
  MockPaperNoteQuery,
  updateMockPaperNoteOperatorState,
  SAMPLE_PDF,
} from "./mock";

const FORCE_MOCK_REASON = "mock mode forced by VITE_FORCE_MOCK";
const LIVE_PAPERS_CACHE_TTL_MS = 15_000;
const PAPER_NOTE_STRUCTURED_LOOKUP_CACHE_TTL_MS = 5_000;

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

interface ProtocolAttachmentDraftCreateRequest {
  file: File;
  noteSlug?: string;
  paperId?: string;
  runId?: string;
  title?: string;
  purpose?: string;
  signal?: AbortSignal;
}

const livePapersCache: {
  items: PaperSummary[];
  reusable: boolean;
  updatedAt: number;
} = {
  items: [],
  reusable: false,
  updatedAt: 0,
};

const paperNoteStructuredLookupCache = new Map<
  string,
  {
    value: PaperNoteStructuredStateLookupResponse;
    updatedAt: number;
  }
>();

function snapshotPaperList(items: PaperSummary[]): PaperSummary[] {
  return items.map((item) => ({ ...item }));
}

function snapshotPaperNoteStructuredLookup(
  value: PaperNoteStructuredStateLookupResponse,
): PaperNoteStructuredStateLookupResponse {
  return JSON.parse(JSON.stringify(value)) as PaperNoteStructuredStateLookupResponse;
}

function getCachedPaperNoteStructuredLookup(paperId: string): PaperNoteStructuredStateLookupResponse | null {
  for (const candidate of buildPaperIdCandidates(paperId)) {
    const cached = paperNoteStructuredLookupCache.get(candidate);
    if (!cached) {
      continue;
    }
    if (Date.now() - cached.updatedAt > PAPER_NOTE_STRUCTURED_LOOKUP_CACHE_TTL_MS) {
      paperNoteStructuredLookupCache.delete(candidate);
      continue;
    }
    return snapshotPaperNoteStructuredLookup(cached.value);
  }
  return null;
}

function replaceCachedPaperNoteStructuredLookup(
  value: PaperNoteStructuredStateLookupResponse,
  options?: { paperIds?: string[] },
): void {
  const keys = new Set<string>();
  for (const candidate of buildPaperIdCandidates(value.paper_id)) {
    keys.add(candidate);
  }
  const slug = String(value.slug ?? "").trim();
  if (slug) {
    keys.add(slug);
  }
  for (const paperId of options?.paperIds ?? []) {
    for (const candidate of buildPaperIdCandidates(paperId)) {
      keys.add(candidate);
    }
  }
  if (keys.size === 0) {
    return;
  }
  const snapshot = snapshotPaperNoteStructuredLookup(value);
  const updatedAt = Date.now();
  for (const key of keys) {
    paperNoteStructuredLookupCache.set(key, { value: snapshot, updatedAt });
  }
}

function clearCachedPaperNoteStructuredLookup(keys: Array<string | null | undefined>): void {
  for (const rawKey of keys) {
    const trimmed = String(rawKey ?? "").trim();
    if (!trimmed) {
      continue;
    }
    paperNoteStructuredLookupCache.delete(trimmed);
    for (const candidate of buildPaperIdCandidates(trimmed)) {
      paperNoteStructuredLookupCache.delete(candidate);
    }
  }
}

function buildStructuredLookupFromNoteDetail(
  noteDetail: PaperNoteDetailResponse,
): PaperNoteStructuredStateLookupResponse | null {
  const slug = String(noteDetail.note.slug ?? "").trim();
  const notePath = String(noteDetail.note.note_path ?? "").trim();
  if (!slug || !notePath) {
    return null;
  }
  return {
    paper_id:
      normalizeNoteDetailPaperId(noteDetail.note.id) ??
      normalizeNoteDetailPaperId(noteDetail.operator_state.paper_id) ??
      slug,
    slug,
    note_path: notePath,
    note: noteDetail.note,
    pdf_url: getNoteDetailLocalPdfUrl(noteDetail) ?? getNoteDetailOpenPdfUrl(noteDetail),
    doi_url: getNoteDetailDoiUrl(noteDetail),
    structured_state: noteDetail.structured_state ?? null,
    operator_state: noteDetail.operator_state ?? null,
  };
}

function primeStructuredLookupCacheFromNoteDetail(
  noteDetail: PaperNoteDetailResponse,
  options?: { paperIds?: string[] },
): void {
  const lookup = buildStructuredLookupFromNoteDetail(noteDetail);
  if (!lookup) {
    return;
  }
  replaceCachedPaperNoteStructuredLookup(lookup, options);
}

export function getCachedLivePapers(): PaperSummary[] | null {
  if (!livePapersCache.reusable || livePapersCache.items.length === 0) {
    return null;
  }
  if (Date.now() - livePapersCache.updatedAt > LIVE_PAPERS_CACHE_TTL_MS) {
    livePapersCache.reusable = false;
    return null;
  }
  return snapshotPaperList(livePapersCache.items);
}

export function isCachedLivePapersReusable(): boolean {
  return livePapersCache.reusable;
}

export function replaceCachedLivePapers(items: PaperSummary[], options?: { reusable?: boolean }): void {
  livePapersCache.items = snapshotPaperList(items);
  livePapersCache.updatedAt = Date.now();
  if (typeof options?.reusable === "boolean") {
    livePapersCache.reusable = options.reusable;
  }
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
  responseHeaders?: Record<string, string>;

  constructor(
    path: string,
    status: number,
    statusText: string,
    responseBody?: string,
    responseHeaders?: Record<string, string>,
  ) {
    super(`${path} -> ${status} ${statusText}`);
    this.path = path;
    this.status = status;
    this.responseBody = responseBody;
    this.responseHeaders = responseHeaders;
  }
}

function isApiHttpError(error: unknown): error is ApiHttpError {
  return error instanceof ApiHttpError;
}

function isProxyAvailabilityHttpError(error: unknown): error is ApiHttpError {
  if (!import.meta.env.DEV || !isApiHttpError(error) || error.status !== 500) {
    return false;
  }
  if ((error.responseBody ?? "").trim().length > 0) {
    return false;
  }

  const contentType = (error.responseHeaders?.["content-type"] ?? "").toLowerCase();
  if (!contentType.startsWith("text/plain")) {
    return false;
  }

  const backendOnlyHeaders = [
    "server",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
  ];
  return !backendOnlyHeaders.some((headerName) => {
    const value = error.responseHeaders?.[headerName];
    return typeof value === "string" && value.trim().length > 0;
  });
}

function readResponseHeaders(response: Response): Record<string, string> {
  return Object.fromEntries(Array.from(response.headers.entries(), ([key, value]) => [key.toLowerCase(), value]));
}

function canUseAutoMockFallback(): boolean {
  return APP_CONFIG.autoMockFallback && !APP_CONFIG.strictApi;
}

function canFallbackForReadError(error: unknown): boolean {
  if (!canUseAutoMockFallback()) {
    return false;
  }
  if (isApiHttpError(error)) {
    return isProxyAvailabilityHttpError(error);
  }
  return true;
}

function requestHeaders(init?: RequestInit, includeJsonContentType = true): HeadersInit {
  const headers = new Headers(init?.headers ?? undefined);
  if (includeJsonContentType && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
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

function withTimeout(
  signal?: AbortSignal | null,
  timeoutMs: number = APP_CONFIG.requestTimeoutMs,
): { signal: AbortSignal; cancel: () => void } {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
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

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const timeout = withTimeout(init?.signal, timeoutMs);
  try {
    const response = await fetch(apiPath(path), {
      ...init,
      signal: timeout.signal,
      headers: requestHeaders(init),
    });

    if (!response.ok) {
      const responseBody = await response.text().catch(() => "");
      throw new ApiHttpError(path, response.status, response.statusText, responseBody, readResponseHeaders(response));
    }

    return (await response.json()) as T;
  } finally {
    timeout.cancel();
  }
}

async function postForm<T>(path: string, formData: FormData, init?: RequestInit): Promise<T> {
  const timeout = withTimeout(init?.signal);
  try {
    const response = await fetch(apiPath(path), {
      ...init,
      method: init?.method ?? "POST",
      body: formData,
      signal: timeout.signal,
      headers: requestHeaders(init, false),
    });

    if (!response.ok) {
      const responseBody = await response.text().catch(() => "");
      throw new ApiHttpError(path, response.status, response.statusText, responseBody, readResponseHeaders(response));
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
      throw new ApiHttpError(url, response.status, response.statusText, responseBody, readResponseHeaders(response));
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

function buildPaperIdCandidates(paperId: string): string[] {
  const raw = String(paperId ?? "").trim();
  if (!raw) {
    return [];
  }
  const stripped = raw.startsWith("zotero:") ? raw.slice("zotero:".length).trim() : "";
  const candidates = stripped ? [raw, stripped] : [raw];
  if (stripped && !candidates.includes(stripped)) {
    candidates.push(stripped);
  }
  return candidates;
}

async function tryResolvePaperNoteLookupByPaperIdCandidates(
  paperIds: string[],
): Promise<PaperNoteStructuredStateLookupResponse | null> {
  for (const candidate of paperIds) {
    try {
      const lookup = await fetchJson<PaperNoteStructuredStateLookupResponse>(
        `/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(candidate)}`,
      );
      replaceCachedPaperNoteStructuredLookup(lookup, { paperIds: [candidate, ...paperIds] });
      return lookup;
    } catch (error) {
      if (isApiHttpError(error) && error.status === 404) {
        continue;
      }
      throw error;
    }
  }
  return null;
}

async function tryLoadCanonicalPaperDetailFromLookup(
  lookup: PaperNoteStructuredStateLookupResponse,
  originalCandidates: string[],
): Promise<PaperDetail | null> {
  const seenCandidates = new Set(originalCandidates);
  for (const candidate of buildPaperIdCandidates(lookup.paper_id)) {
    if (seenCandidates.has(candidate)) {
      continue;
    }
    try {
      const row = await fetchJson<Record<string, unknown>>(`/papers/${encodeURIComponent(candidate)}`);
      return normalizePaper(row) as PaperDetail;
    } catch (error) {
      if (isApiHttpError(error) && error.status === 404) {
        continue;
      }
      throw error;
    }
  }
  return null;
}

function synthesizePaperDetailFromStructuredLookup(
  requestedPaperId: string,
  lookup: PaperNoteStructuredStateLookupResponse,
): PaperDetail | null {
  const note = lookup.note;
  if (!note) {
    return null;
  }

  const canonicalPaperId =
    normalizeNoteDetailPaperId(note.id) ??
    normalizeNoteDetailPaperId(lookup.operator_state?.paper_id) ??
    requestedPaperId;
  const pdfUrl = String(lookup.pdf_url ?? "").trim();
  const doiUrl = String(lookup.doi_url ?? "").trim();
  const localPdfUrl = pdfUrl.startsWith("/papers/") ? pdfUrl : null;
  const openPdfUrl = /^https?:\/\//i.test(pdfUrl) ? pdfUrl : null;

  return {
    paper_id: canonicalPaperId,
    note_slug: normalizeNoteDetailPaperId(note.slug),
    title: note.title || note.slug || canonicalPaperId,
    status:
      note.structured_state_present || String(note.status ?? "").trim().toUpperCase() === "INDEXED"
        ? "completed"
        : normalizePaperStatus(note.status ?? undefined),
    issues: 0,
    issues_label: "No critical issues",
    issues_state: "unavailable",
    pdf_exists: Boolean(localPdfUrl),
    updated_at: note.updated_at ?? undefined,
    latest_run_id: note.ops_summary?.latest_run_id ?? undefined,
    ops_summary: note.ops_summary ?? null,
    access_summary: localPdfUrl
      ? {
          status_label: "user_imported_pdf",
          local_pdf_url: localPdfUrl,
          open_access_url: openPdfUrl,
          institution_access_url: doiUrl || null,
        }
      : openPdfUrl
        ? {
            status_label: "open",
            open_access_url: openPdfUrl,
            institution_access_url: doiUrl || null,
            local_pdf_url: null,
          }
        : doiUrl
          ? {
              status_label: "institution_required",
              open_access_url: null,
              institution_access_url: doiUrl,
              local_pdf_url: null,
            }
          : null,
  };
}

function normalizeNoteDetailPaperId(value: string | null | undefined): string | null {
  const trimmed = String(value ?? "").trim();
  return trimmed.length > 0 ? trimmed : null;
}

function getFrontmatterString(frontmatter: Record<string, unknown>, key: string): string | null {
  const raw = frontmatter[key];
  if (typeof raw !== "string") {
    return null;
  }
  const value = raw.trim();
  return value.length > 0 ? value : null;
}

function getNoteDetailLocalPdfUrl(noteDetail: PaperNoteDetailResponse): string | null {
  const frontmatterPdfUrl = getFrontmatterString(noteDetail.frontmatter, "pdf_url");
  if (frontmatterPdfUrl?.startsWith("/papers/")) {
    return frontmatterPdfUrl;
  }
  const pdfReference = noteDetail.references.find((reference) => reference.source === "pdf");
  if (pdfReference?.url?.startsWith("/papers/")) {
    return pdfReference.url;
  }
  return null;
}

function getNoteDetailOpenPdfUrl(noteDetail: PaperNoteDetailResponse): string | null {
  const frontmatterPdfUrl = getFrontmatterString(noteDetail.frontmatter, "pdf_url");
  if (frontmatterPdfUrl && /^https?:\/\//i.test(frontmatterPdfUrl)) {
    return frontmatterPdfUrl;
  }
  const pdfReference = noteDetail.references.find((reference) => reference.source === "pdf");
  if (pdfReference?.url && /^https?:\/\//i.test(pdfReference.url)) {
    return pdfReference.url;
  }
  return null;
}

function getNoteDetailDoiUrl(noteDetail: PaperNoteDetailResponse): string | null {
  const doiReference = noteDetail.references.find((reference) => reference.source === "doi");
  if (doiReference?.url) {
    return doiReference.url;
  }
  const doi = getFrontmatterString(noteDetail.frontmatter, "doi");
  if (!doi) {
    return null;
  }
  const normalized = doi.replace(/^doi:/i, "").trim();
  return normalized ? `https://doi.org/${normalized}` : null;
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
    if (!canFallbackForReadError(error)) {
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
  const rawAccessSummary =
    raw.access_summary && typeof raw.access_summary === "object" && !Array.isArray(raw.access_summary)
      ? (raw.access_summary as Record<string, unknown>)
      : null;
  const localPdfUrl =
    rawAccessSummary && rawAccessSummary.local_pdf_url
      ? String(rawAccessSummary.local_pdf_url)
      : null;

  return {
    paper_id: String(raw.paper_id ?? "unknown-paper"),
    note_slug: raw.note_slug ? String(raw.note_slug) : undefined,
    title: String(raw.title ?? raw.paper_id ?? "Untitled"),
    authors: raw.authors ? String(raw.authors) : undefined,
    year: typeof raw.year === "number" ? raw.year : undefined,
    pdf_exists: raw.pdf_exists === true || Boolean(localPdfUrl),
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
    access_summary: rawAccessSummary
      ? {
          status_label:
            rawAccessSummary.status_label === "open" ||
            rawAccessSummary.status_label === "institution_required" ||
            rawAccessSummary.status_label === "user_imported_pdf"
              ? rawAccessSummary.status_label
              : "unavailable",
          open_access_url: rawAccessSummary.open_access_url ? String(rawAccessSummary.open_access_url) : null,
          institution_access_url: rawAccessSummary.institution_access_url
            ? String(rawAccessSummary.institution_access_url)
            : null,
          local_pdf_url: localPdfUrl,
        }
      : null,
  };
}

function emptyArtifactBundle(paperId: string): ArtifactBundle {
  return {
    paper_id: paperId,
    run_id: "",
    inference_summary: null,
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

function syntheticRuntimeReadiness(detail: string): RuntimeReadinessResponse {
  return {
    status: "error",
    checks: [
      {
        name: "runtime_readiness",
        status: "error",
        detail,
        path: null,
      },
    ],
  };
}

export async function getRuntimeReadiness(): Promise<ApiResult<RuntimeReadinessResponse>> {
  if (APP_CONFIG.forceMock) {
    const detail =
      "Runtime checks are unavailable while mock mode is forced. Disable mock mode to inspect the live backend runtime.";
    return {
      data: syntheticRuntimeReadiness(detail),
      isMock: true,
      reason: detail,
    };
  }

  try {
    return {
      data: await fetchJson<RuntimeReadinessResponse>("/health/ready", undefined, 15_000),
      isMock: false,
    };
  } catch (error) {
    return {
      data: syntheticRuntimeReadiness(
        `Runtime checks could not be loaded. ${getApiErrorMessage(error)}. Start the backend, then reload this page.`,
      ),
      isMock: true,
      reason: "runtime readiness endpoint unavailable",
    };
  }
}

export async function getPapers(options?: { preferCache?: boolean }): Promise<ApiResult<PaperSummary[]>> {
  const cachedPapers = options?.preferCache ? getCachedLivePapers() : null;
  if (cachedPapers !== null) {
    return {
      data: cachedPapers,
      isMock: false,
    };
  }
  return withMockFallback(
    async () => {
      const rows = await firstSuccess<Record<string, unknown>[]>(["/papers/rail?limit=5000"]);
      if (!Array.isArray(rows)) {
        throw new Error("invalid papers response");
      }
      const normalized = rows.map(normalizePaper);
      replaceCachedLivePapers(normalized, { reusable: true });
      return normalized;
    },
    () => getMockPapers(),
    "papers endpoint unavailable",
  );
}

export async function getRecentPaperChoices(limit = 6): Promise<ApiResult<PaperSummary[]>> {
  const normalizedLimit = Math.max(1, Math.min(20, Math.floor(limit)));
  return withMockFallback(
    async () => {
      const rows = await firstSuccess<Record<string, unknown>[]>([
        `/papers/recent?limit=${encodeURIComponent(String(normalizedLimit))}`,
      ]);
      if (!Array.isArray(rows)) {
        throw new Error("invalid recent papers response");
      }
      return rows.map(normalizePaper);
    },
    () => getMockPapers().slice(0, normalizedLimit),
    "recent papers endpoint unavailable",
  );
}

export async function getPaper(
  paperId: string,
  options?: {
    preferNoteDetail?: boolean;
  },
): Promise<ApiResult<PaperDetail>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockPaper(paperId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  const candidates = buildPaperIdCandidates(paperId);
  let lastError: unknown;
  let resolvedLookup: PaperNoteStructuredStateLookupResponse | null = null;

  try {
    for (const candidate of candidates) {
      try {
        const row = await fetchJson<Record<string, unknown>>(`/papers/${encodeURIComponent(candidate)}`);
        return {
          data: normalizePaper(row) as PaperDetail,
          isMock: false,
        };
      } catch (error) {
        lastError = error;
        if (isApiHttpError(error) && error.status === 404) {
          continue;
        }
        throw error;
      }
    }

    if (options?.preferNoteDetail) {
      resolvedLookup ??= await tryResolvePaperNoteLookupByPaperIdCandidates(candidates);
      if (resolvedLookup) {
        const canonicalPaperDetail = await tryLoadCanonicalPaperDetailFromLookup(resolvedLookup, candidates);
        if (canonicalPaperDetail) {
          return {
            data: canonicalPaperDetail,
            isMock: false,
          };
        }
      }
      if (resolvedLookup) {
        const synthesizedFromLookup = synthesizePaperDetailFromStructuredLookup(paperId, resolvedLookup);
        if (synthesizedFromLookup) {
          return {
            data: synthesizedFromLookup,
            isMock: false,
          };
        }
      }
    }
  } catch (error) {
    lastError = error;
  }

  if (!canFallbackForReadError(lastError)) {
    throw lastError instanceof Error ? lastError : new Error("paper detail unavailable");
  }

  return {
    data: getMockPaper(paperId),
    isMock: true,
    reason: "paper detail unavailable",
  };
}

type PaperNoteListQuery = MockPaperNoteQuery;

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
  if (params?.starred) {
    query.set("starred", "true");
  }
  if (params?.triageLabel?.trim()) {
    query.set("triage_label", params.triageLabel.trim());
  }
  if (params?.structuredOnly) {
    query.set("structured_only", "true");
  }
  if (params?.hasReadingAssist) {
    query.set("has_reading_assist", "true");
  }
  if (params?.readingAssistLocale?.trim()) {
    query.set("reading_assist_locale", params.readingAssistLocale.trim().toLowerCase());
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
  const query = buildPaperNotesQuery(params);
  return withMockFallback(
    () => firstSuccess<PaperNoteListResponse>([`/paper-notes${query}`]),
    () => getMockPaperNotesIndex(params),
    "paper notes unavailable, mock index loaded",
  );
}

export async function getPaperNotesHomeContext(): Promise<ApiResult<PaperNotesHomeContext>> {
  return withMockFallback(
    () => firstSuccess<PaperNotesHomeContext>(["/paper-notes/home-context"]),
    () => getMockPaperNotesHomeContext(),
    "paper notes home context unavailable, mock context loaded",
  );
}

export async function importPaperPdf(file: File): Promise<ApiResult<PaperNoteImportResponse>> {
  if (APP_CONFIG.forceMock) {
    throw new Error("PDF import needs a live backend. Turn off forced mock mode and try again.");
  }

  const formData = new FormData();
  formData.append("file", file);

  return {
    data: await postForm<PaperNoteImportResponse>("/paper-notes/import-pdf", formData),
    isMock: false,
  };
}

export async function getPaperNoteDetail(
  slug: string,
  options?: { readingAssistLocale?: string | null },
): Promise<ApiResult<PaperNoteDetailResponse>> {
  const query = new URLSearchParams();
  if (options?.readingAssistLocale?.trim()) {
    query.set("reading_assist_locale", options.readingAssistLocale.trim().toLowerCase());
  }
  const detailQuery = query.toString();
  const detailPath = `/paper-notes/${encodeURIComponent(slug)}${detailQuery ? `?${detailQuery}` : ""}`;
  return withMockFallback(
    async () => {
      const detail = await firstSuccess<PaperNoteDetailResponse>([detailPath]);
      primeStructuredLookupCacheFromNoteDetail(detail, { paperIds: [slug] });
      return detail;
    },
    () => getMockPaperNoteDetail(slug, options),
    "paper note detail unavailable, mock note loaded",
  );
}

export async function getPaperNoteOperatorState(
  slug: string,
): Promise<ApiResult<PaperNoteOperatorState>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockPaperNoteOperatorState(slug),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  return {
    data: await fetchJson<PaperNoteOperatorState>(`/paper-notes/${encodeURIComponent(slug)}/operator-state`),
    isMock: false,
  };
}

export async function updatePaperNoteOperatorState(
  slug: string,
  payload: PaperNoteOperatorStateUpdateRequest,
): Promise<ApiResult<PaperNoteOperatorState>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: updateMockPaperNoteOperatorState(slug, payload),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  const nextState = await fetchJson<PaperNoteOperatorState>(`/paper-notes/${encodeURIComponent(slug)}/operator-state`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  clearCachedPaperNoteStructuredLookup([slug, nextState.note_slug, nextState.paper_id]);
  return {
    data: nextState,
    isMock: false,
  };
}

export async function getPaperNoteStructuredStateByPaperId(
  paperId: string,
): Promise<ApiResult<PaperNoteStructuredStateLookupResponse | null>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: getMockPaperNoteStructuredStateByPaperId(paperId),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  const cachedLookup = getCachedPaperNoteStructuredLookup(paperId);
  if (cachedLookup) {
    return {
      data: cachedLookup,
      isMock: false,
    };
  }

  try {
    const lookup = await firstSuccess<PaperNoteStructuredStateLookupResponse>([
      `/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(paperId)}`,
    ]);
    replaceCachedPaperNoteStructuredLookup(lookup, { paperIds: [paperId] });
    return {
      data: lookup,
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
    if (!canFallbackForReadError(error)) {
      throw error;
    }
    return {
      data: getMockPaperNoteStructuredStateByPaperId(paperId),
      isMock: true,
      reason: "structured paper note lookup unavailable",
    };
  }
}

export async function getLatestPaperSynthesis(
  paperSlug: string,
): Promise<ApiResult<PaperSynthesisListItem | null>> {
  const normalizedSlug = paperSlug.trim();
  if (!normalizedSlug) {
    return {
      data: null,
      isMock: false,
      reason: "paper slug unavailable",
    };
  }

  if (APP_CONFIG.forceMock) {
    return {
      data: null,
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    const query = new URLSearchParams({ paper_slug: normalizedSlug }).toString();
    const response = await firstSuccess<PaperSynthesisListResponse>([`/paper-syntheses?${query}`]);
    return {
      data: response.items[0] ?? null,
      isMock: false,
    };
  } catch (error) {
    return {
      data: null,
      isMock: false,
      reason: getApiErrorMessage(error),
    };
  }
}

export async function getPaperSynthesisManifest(
  synthesisId: string,
): Promise<ApiResult<PaperSynthesisManifest | null>> {
  const normalizedId = synthesisId.trim();
  if (!normalizedId) {
    return {
      data: null,
      isMock: false,
      reason: "paper synthesis id unavailable",
    };
  }

  if (APP_CONFIG.forceMock) {
    return {
      data: null,
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }

  try {
    const response = await firstSuccess<PaperSynthesisManifest>([
      `/paper-syntheses/${encodeURIComponent(normalizedId)}/manifest`,
    ]);
    return {
      data: response,
      isMock: false,
    };
  } catch (error) {
    if (isApiHttpError(error) && error.status === 404) {
      return {
        data: null,
        isMock: false,
        reason: "paper synthesis manifest not found",
      };
    }
    return {
      data: null,
      isMock: false,
      reason: getApiErrorMessage(error),
    };
  }
}

export function getPaperSynthesisMarkdownUrl(synthesisId: string): string {
  return apiPath(`/paper-syntheses/${encodeURIComponent(synthesisId)}/markdown`);
}

export async function getMeetingPack(packId: string): Promise<ApiResult<MeetingPackResponse>> {
  return withMockFallback(
    () => firstSuccess<MeetingPackResponse>([`/meeting-packs/${encodeURIComponent(packId)}`]),
    () => getMockMeetingPack(packId),
    "meeting pack detail unavailable, mock draft loaded",
  );
}

export async function getMeetingPackIndex(): Promise<ApiResult<MeetingPackListResponse>> {
  return withMockFallback(
    () => firstSuccess<MeetingPackListResponse>(["/meeting-packs"]),
    () => getMockMeetingPackIndex(),
    "meeting packs unavailable, mock drafts loaded",
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
    if (isApiHttpError(error) && !isProxyAvailabilityHttpError(error)) {
      throw error;
    }
    if (!canFallbackForReadError(error)) {
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
  return withMockFallback(
    () =>
      firstSuccess<MethodComparisonResponse>([
        `/method-comparisons/${encodeURIComponent(comparisonId)}`,
      ]),
    () => getMockMethodComparison(comparisonId),
    "method comparison unavailable, mock comparison loaded",
  );
}

export async function getMethodComparisonIndex(): Promise<ApiResult<MethodComparisonListResponse>> {
  return withMockFallback(
    () => firstSuccess<MethodComparisonListResponse>(["/method-comparisons"]),
    () => getMockMethodComparisonIndex(),
    "method comparisons unavailable, mock index loaded",
  );
}

export async function generateMethodComparison(
  payload: MethodComparisonCreateRequest,
): Promise<ApiResult<MethodComparisonResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: createMockMethodComparison(payload),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  return {
    data: await fetchJson<MethodComparisonResponse>("/method-comparisons/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    isMock: false,
  };
}

export function getMethodComparisonCsvUrl(comparisonId: string): string {
  return apiPath(`/method-comparisons/${encodeURIComponent(comparisonId)}/export.csv`);
}

export async function getChartPack(chartPackId: string): Promise<ApiResult<ChartPackResponse>> {
  return withMockFallback(
    () =>
      firstSuccess<ChartPackResponse>([
        `/chart-packs/${encodeURIComponent(chartPackId)}`,
      ]),
    () => getMockChartPack(chartPackId),
    "chart pack unavailable, mock pack loaded",
  );
}

export async function getChartPackIndex(): Promise<ApiResult<ChartPackListResponse>> {
  return withMockFallback(
    () => firstSuccess<ChartPackListResponse>(["/chart-packs"]),
    () => getMockChartPackIndex(),
    "chart packs unavailable, mock index loaded",
  );
}

export async function generateChartPack(
  payload: ChartPackRequestSnapshot,
): Promise<ApiResult<ChartPackResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: createMockChartPack(payload),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  return {
    data: await fetchJson<ChartPackResponse>("/chart-packs/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    isMock: false,
  };
}

export async function getImageEvidence(imageEvidenceId: string): Promise<ApiResult<ImageEvidenceResponse>> {
  return withMockFallback(
    () =>
      firstSuccess<ImageEvidenceResponse>([
        `/image-evidence/${encodeURIComponent(imageEvidenceId)}`,
      ]),
    () => getMockImageEvidence(imageEvidenceId),
    "image evidence unavailable, mock entry loaded",
  );
}

export async function getImageEvidenceIndex(): Promise<ApiResult<ImageEvidenceListResponse>> {
  return withMockFallback(
    () => firstSuccess<ImageEvidenceListResponse>(["/image-evidence"]),
    () => getMockImageEvidenceIndex(),
    "image evidence index unavailable, mock entries loaded",
  );
}

export async function getProtocolCard(protocolId: string): Promise<ApiResult<ProtocolCardResponse>> {
  return withMockFallback(
    () =>
      firstSuccess<ProtocolCardResponse>([
        `/protocol-cards/${encodeURIComponent(protocolId)}`,
      ]),
    () => getMockProtocolCard(protocolId),
    "protocol card unavailable, mock entry loaded",
  );
}

export async function getProtocolCardIndex(): Promise<ApiResult<ProtocolCardListResponse>> {
  return withMockFallback(
    () => firstSuccess<ProtocolCardListResponse>(["/protocol-cards"]),
    () => getMockProtocolCardIndex(),
    "protocol cards unavailable, mock index loaded",
  );
}

export async function createProtocolCard(
  payload: ProtocolCardRequestSnapshot,
): Promise<ApiResult<ProtocolCardResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: createMockProtocolCard(payload),
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  return {
    data: await fetchJson<ProtocolCardResponse>("/protocol-cards", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    isMock: false,
  };
}

export async function createProtocolDraftFromAttachment(
  payload: ProtocolAttachmentDraftCreateRequest,
): Promise<ApiResult<ProtocolAttachmentDraftResponse>> {
  if (APP_CONFIG.forceMock) {
    throw new Error("Protocol attachment draft creation needs the live backend.");
  }

  const formData = new FormData();
  formData.set("file", payload.file);

  const noteSlug = payload.noteSlug?.trim();
  const paperId = payload.paperId?.trim();
  const runId = payload.runId?.trim();
  const title = payload.title?.trim();
  const purpose = payload.purpose?.trim();

  if (noteSlug) {
    formData.set("note_slug", noteSlug);
  }
  if (paperId) {
    formData.set("paper_id", paperId);
  }
  if (runId) {
    formData.set("run_id", runId);
  }
  if (title) {
    formData.set("title", title);
  }
  if (purpose) {
    formData.set("purpose", purpose);
  }

  return {
    data: await postForm<ProtocolAttachmentDraftResponse>("/protocol-cards/draft-from-attachment", formData, {
      signal: payload.signal,
    }),
    isMock: false,
  };
}

export async function getProtocolAttachmentBundle(
  attachmentBundleId: string,
): Promise<ApiResult<ProtocolAttachmentBundle>> {
  if (APP_CONFIG.forceMock) {
    throw new Error("Protocol attachment bundle lookup needs the live backend.");
  }
  return {
    data: await fetchJson<ProtocolAttachmentBundle>(
      `/protocol-cards/attachments/${encodeURIComponent(attachmentBundleId)}`,
    ),
    isMock: false,
  };
}

export function getProtocolAttachmentBundleUrl(attachmentBundleId: string): string {
  return apiPath(`/protocol-cards/attachments/${encodeURIComponent(attachmentBundleId)}`);
}

export function getProtocolAttachmentSourceUrl(
  attachmentBundleId: string,
  options?: { download?: boolean },
): string {
  const path = `/protocol-cards/attachments/${encodeURIComponent(attachmentBundleId)}/source`;
  if (options?.download) {
    return apiPath(`${path}?download=1`);
  }
  return apiPath(path);
}

export function getProtocolAttachmentMarkdownUrl(attachmentBundleId: string): string {
  return apiPath(
    `/protocol-cards/attachments/${encodeURIComponent(attachmentBundleId)}/extracted-markdown`,
  );
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

export function getChartPackRenderSvgUrl(chartPackId: string, chartId: string): string {
  return apiPath(
    `/chart-packs/${encodeURIComponent(chartPackId)}/charts/${encodeURIComponent(chartId)}/render.svg`,
  );
}

export async function getMeetingPackTrace(packId: string): Promise<ApiResult<MeetingPackTraceResponse>> {
  return withMockFallback(
    () => firstSuccess<MeetingPackTraceResponse>([`/meeting-packs/${encodeURIComponent(packId)}/trace`]),
    () => getMockMeetingPackTrace(packId),
    "meeting pack trace unavailable, mock trace loaded",
  );
}

export async function getMeetingPackValidation(packId: string): Promise<ApiResult<MeetingPackValidationResponse>> {
  return withMockFallback(
    () =>
      firstSuccess<MeetingPackValidationResponse>([
        `/meeting-packs/${encodeURIComponent(packId)}/validate`,
      ]),
    () => getMockMeetingPackValidation(packId),
    "meeting pack validation unavailable, mock validation loaded",
  );
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
  return {
    data: await firstSuccess<JobEnqueueResponse>(["/jobs/deepread"], {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    isMock: false,
  };
}

export async function cancelJobRun(jobId: string): Promise<ApiResult<JobCancelResponse>> {
  if (APP_CONFIG.forceMock) {
    return {
      data: { status: "cancelled" },
      isMock: true,
      reason: FORCE_MOCK_REASON,
    };
  }
  return {
    data: await fetchJson<JobCancelResponse>(`/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    }),
    isMock: false,
  };
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
  return {
    data: await firstSuccess<StatsRepairResponse>(["/ops/repair-stats"], {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    isMock: false,
  };
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
    const candidates = buildPaperIdCandidates(paperId);
    return {
      data: await firstSuccess<ArtifactBundle>(
        candidates.map((candidate) => `/artifacts/${encodeURIComponent(candidate)}/latest`),
      ),
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
    if (!canFallbackForReadError(error)) {
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
    if (!canFallbackForReadError(error)) {
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
    const candidates = buildPaperIdCandidates(paperId);
    return {
      data: await firstSuccess<ObsidianMirror>(
        candidates.map(
          (candidate) =>
            `/obsidian/mirror?paper_id=${encodeURIComponent(candidate)}&run_id=${encodeURIComponent(runId)}`,
        ),
      ),
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
    if (!canFallbackForReadError(error)) {
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
    if (!canFallbackForReadError(error)) {
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

async function buildPlaceholderPdfResult(reason: string): Promise<ApiResult<string>> {
  const mockBlob = await fetchBlobFromUrl(SAMPLE_PDF);
  if (!(await looksLikePdfBlob(mockBlob))) {
    throw new Error("mock sample PDF is invalid");
  }
  return {
    data: URL.createObjectURL(mockBlob),
    isMock: true,
    reason,
  };
}

export async function getPaperPdfBlobUrl(
  paperId: string,
  options?: {
    preferPlaceholder?: boolean;
  },
): Promise<ApiResult<string>> {
  const apiPdfUrls = buildPaperIdCandidates(paperId).map((candidate) =>
    apiPath(`/papers/${encodeURIComponent(candidate)}/pdf`)
  );
  if (APP_CONFIG.forceMock) {
    return buildPlaceholderPdfResult(FORCE_MOCK_REASON);
  }

  if (options?.preferPlaceholder) {
    return buildPlaceholderPdfResult("paper pdf unavailable, placeholder sample loaded (not source evidence)");
  }

  try {
    let pdfBlob: Blob | null = null;
    let lastPdfUrl = apiPdfUrls[0] ?? apiPath(`/papers/${encodeURIComponent(paperId)}/pdf`);
    let lastError: unknown;
    for (const apiPdfUrl of apiPdfUrls) {
      try {
        const candidateBlob = await fetchBlobFromUrl(apiPdfUrl);
        if (!(await looksLikePdfBlob(candidateBlob))) {
          throw new Error(`invalid PDF payload from ${apiPdfUrl}`);
        }
        pdfBlob = candidateBlob;
        lastPdfUrl = apiPdfUrl;
        break;
      } catch (error) {
        lastError = error;
        lastPdfUrl = apiPdfUrl;
      }
    }
    if (!pdfBlob) {
      throw lastError instanceof Error ? lastError : new Error(`invalid PDF payload from ${lastPdfUrl}`);
    }
    return {
      data: URL.createObjectURL(pdfBlob),
      isMock: false,
    };
  } catch (error) {
    if (!canFallbackForReadError(error)) {
      throw error;
    }
    return buildPlaceholderPdfResult("paper pdf unavailable, placeholder sample loaded (not source evidence)");
  }
}
