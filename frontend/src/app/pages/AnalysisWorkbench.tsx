import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Copy, Play, RefreshCcw, Square, Wrench } from "lucide-react";
import {
  cancelJobRun,
  enqueueDeepRead,
  getArtifactsLatest,
  getApiErrorMessage,
  getJob,
  getJobsForPaper,
  getLatestPaperSynthesis,
  getObsidianMirror,
  getPaper,
  getPaperNoteStructuredStateByPaperId,
  getPaperPdfBlobUrl,
  getPapers,
  getCachedLivePapers,
  isCachedLivePapersReusable,
  getPersonas,
  replaceCachedLivePapers,
  getRunTimeline,
  logClientUserAction,
  syncToObsidian,
  repairStats,
} from "../lib/api";
import { connectJobStream, StreamSubscription } from "../lib/sse";
import { getPaperAccessSummaryDisplay } from "../lib/accessSummary";
import { formatPaperNoteTriageLabel, hasPaperOperatorNoteText } from "../lib/paperOperatorState";
import { mapStage } from "../lib/ui";
import { deriveContentReviewSummary, type ContentReviewSummary as ContentReviewSummaryModel } from "../lib/contentReview";
import { derivePaperNoteOpsSummary } from "../lib/paperNoteOps";
import { buildBestHighlightMap, getClaimLinkState, summarizeClaimGuard } from "../lib/claimGuard";
import {
  ArtifactBundle,
  JobStatus,
  NotebookArtifact,
  ObsidianMirror,
  PaperDetail,
  PaperNoteOperatorState,
  PaperSynthesisListItem,
  PaperSummary,
  PersonaOption,
  ReasoningPersonaId,
  StructuredPaperState,
  TimelineEvent,
} from "../lib/types";
import { getNotebookFromBundle, getNotebookFromStructuredState } from "../lib/mock";
import { useAppStore } from "../store/useAppStore";
import { Rail } from "../components/Rail";
import { ArtifactPanel } from "../components/ArtifactPanel";
import { ContentReviewSummary } from "../components/ContentReviewSummary";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
import { TimelinePanel } from "../components/TimelinePanel";
import { PanelErrorBoundary } from "../components/PanelErrorBoundary";
import { Badge } from "../components/ui/badge";
import { StatusBadge } from "../components/StatusBadge";
import { WorkspaceContextCard, WorkspaceContextStrip } from "../components/WorkspaceContextStrip";
import { WorkbenchLayout } from "../layouts/WorkbenchLayout";

const PdfPanel = lazy(async () => {
  const module = await import("../components/PdfPanel");
  return { default: module.PdfPanel };
});

function buildIdleJob(paperId: string): JobStatus {
  return {
    job_id: `job-idle-${paperId}`,
    paper_id: paperId,
    status: "queued",
    progress: 0,
    stage: "ingest",
    created_at: new Date().toISOString(),
  };
}

const ISSUE_CLAIM_HINTS = ["issue", "error", "fail", "warning", "mismatch", "inconsistent", "unresolved", "drift", "alert"];

function summarizePaperOperatorNote(value: string | null | undefined, maxLength = 180): string | null {
  const normalized = String(value ?? "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return null;
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
}

function selectIssueClaimId(notebook: NotebookArtifact): string | null {
  const byRiskText = notebook.claims.find((claim) => {
    const text = claim.text.toLowerCase();
    return ISSUE_CLAIM_HINTS.some((keyword) => text.includes(keyword));
  });
  if (byRiskText) {
    return byRiskText.claim_id;
  }
  const byLowConfidence = notebook.claims.find((claim) => claim.confidence === "low");
  return byLowConfidence?.claim_id ?? null;
}

function chooseActiveClaimId(
  notebook: NotebookArtifact,
  focusIssues: boolean,
  currentClaimId: string | null,
): string | null {
  if (currentClaimId && notebook.claims.some((claim) => claim.claim_id === currentClaimId)) {
    return currentClaimId;
  }
  const highlightMap = buildBestHighlightMap(notebook.highlights);

  if (focusIssues) {
    return selectIssueClaimId(notebook) ?? notebook.claims[0]?.claim_id ?? null;
  }

  const mappedClaim = notebook.claims.find(
    (claim) => getClaimLinkState(claim, highlightMap.get(claim.claim_id)).health === "mapped",
  );
  if (mappedClaim) {
    return mappedClaim.claim_id;
  }

  const fallbackClaim = notebook.claims.find(
    (claim) => getClaimLinkState(claim, highlightMap.get(claim.claim_id)).health === "search_fallback",
  );
  if (fallbackClaim) {
    return fallbackClaim.claim_id;
  }

  return notebook.claims[0]?.claim_id ?? null;
}

type StatsActionMode = "repair" | "rebuild";
type WorkbenchActionMode = StatsActionMode | "sync" | "cancel";
type ReasoningSelection = ReasoningPersonaId | "auto";
type ParserBackendOverride = "fitz_pdfplumber" | "docling";

type WorkbenchActionFeedback =
  | {
      tone: "success" | "error";
      mode: WorkbenchActionMode;
      message: string;
    }
  | null;

type SectionNavigationSignalStatus = "pass" | "warn" | "fail";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeSectionNavigationSignalStatus(value: unknown): SectionNavigationSignalStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "pass" || normalized === "warn" || normalized === "fail") {
    return normalized;
  }
  return null;
}

function countStructuredStateSections(state: StructuredPaperState): number {
  const sectionKeys = new Set<string>();
  for (const claim of state.claimset ?? []) {
    for (const evidence of claim.evidence ?? []) {
      const rawSection =
        typeof evidence.locator?.section === "string"
          ? evidence.locator.section
          : typeof evidence.section === "string"
            ? evidence.section
            : "";
      const normalized = rawSection.trim().toLowerCase();
      if (normalized) {
        sectionKeys.add(normalized);
      }
    }
  }
  return sectionKeys.size;
}

function parseSectionNavigationSignalDetail(detail: string | null): { claimsetSectionCount: number | null; summaryPresent: boolean | null } {
  if (!detail) {
    return { claimsetSectionCount: null, summaryPresent: null };
  }
  const claimsetCountMatch = detail.match(/claimset_section_count=(\d+)/i);
  const summaryPresentMatch = detail.match(/summary_present=(true|false)/i);
  return {
    claimsetSectionCount: claimsetCountMatch ? Number.parseInt(claimsetCountMatch[1] ?? "", 10) : null,
    summaryPresent:
      summaryPresentMatch?.[1] === "true" ? true : summaryPresentMatch?.[1] === "false" ? false : null,
  };
}

function buildWorkbenchSectionNavigationSignal(
  state: StructuredPaperState | null,
): { label: string; className: string; detail: string } | null {
  if (!state) {
    return null;
  }
  const latestRunData = isRecord(state.runs?.[0]?.data) ? state.runs[0].data : null;
  const stateSignals = isRecord(state.signals) ? state.signals : null;
  const runtimeSectionSummary = Array.isArray(latestRunData?.section_summary) ? latestRunData.section_summary : [];
  const runtimeSectionCount =
    typeof latestRunData?.section_count === "number"
      ? latestRunData.section_count
      : typeof stateSignals?.section_count === "number"
        ? stateSignals.section_count
        : null;
  const claimsetSectionCount = countStructuredStateSections(state);
  const explicitStatus = normalizeSectionNavigationSignalStatus(
    latestRunData?.section_navigation_signal_status ?? stateSignals?.quality_gate_section_navigation_signal,
  );
  const inferredCount =
    typeof runtimeSectionCount === "number"
      ? runtimeSectionCount
      : runtimeSectionSummary.length > 0
        ? runtimeSectionSummary.length
        : claimsetSectionCount;
  const status = explicitStatus ?? (inferredCount > 0 ? "pass" : null);
  if (!status) {
    return null;
  }

  const rawDetail =
    typeof latestRunData?.section_navigation_signal_detail === "string"
      ? latestRunData.section_navigation_signal_detail
      : status === "pass"
        ? `claimset_section_count=${inferredCount}, summary_present=${runtimeSectionSummary.length > 0 ? "true" : "false"}`
        : null;
  const parsedDetail = parseSectionNavigationSignalDetail(rawDetail);
  const savedSectionCount =
    typeof parsedDetail.claimsetSectionCount === "number" ? parsedDetail.claimsetSectionCount : inferredCount;
  const sectionGroupText = `${savedSectionCount} saved section group${savedSectionCount === 1 ? "" : "s"}`;

  if (status === "pass") {
    return {
      label: "Saved signal ready",
      className:
        "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
      detail: `${sectionGroupText} can reopen saved evidence while you stay in Workbench.`,
    };
  }
  if (status === "warn") {
    return {
      label: "Saved signal thin",
      className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
      detail:
        parsedDetail.summaryPresent === false || savedSectionCount === 0
          ? "Saved section cues are incomplete, so Workbench may rely more on evidence-level anchors than section grouping."
          : "Saved section cues are partial, so section reopen quality may vary across evidence cards.",
    };
  }
  return {
    label: "Saved signal missing",
    className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    detail: "Saved section cues are unavailable in the current note-backed state.",
  };
}

function getInlineNoticeClassName(tone: "warning" | "success" | "error"): string {
  if (tone === "success") {
    return "rounded-md border border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] px-3 py-2 text-xs text-[var(--pp-status-completed-text)]";
  }
  if (tone === "error") {
    return "rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] px-3 py-2 text-xs text-[var(--pp-status-failed-text)]";
  }
  return "rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2 text-xs text-[var(--pp-warning-text)]";
}

function getActionFeedbackTestId(mode: WorkbenchActionMode, tone: "success" | "error"): string {
  if (mode === "cancel") {
    return `cancel-run-${tone}`;
  }
  if (mode === "sync") {
    return `sync-obsidian-${tone}`;
  }
  return `${mode}-stats-${tone}`;
}

function getActionFeedbackTitle(mode: WorkbenchActionMode, tone: "success" | "error"): string {
  if (tone === "success") {
    if (mode === "repair") {
      return "Saved checks refreshed.";
    }
    if (mode === "rebuild") {
      return "Saved checks rebuilt.";
    }
    if (mode === "cancel") {
      return "Deep read cancelled.";
    }
    return "Obsidian sync completed.";
  }

  if (mode === "repair") {
    return "Refresh checks failed.";
  }
  if (mode === "rebuild") {
    return "Rebuild checks failed.";
  }
  if (mode === "cancel") {
    return "Cancel run failed.";
  }
  return "Obsidian sync failed.";
}

interface ContentReviewNoticeModel {
  title: string;
  detail: string | null;
  footnote: string;
}

function buildContentReviewNoticeModel(
  summary: ContentReviewSummaryModel,
  focusIssues: boolean,
): ContentReviewNoticeModel {
  if (summary.state === "flagged") {
    return {
      title: focusIssues
        ? `${summary.issueCount} flagged review issue${summary.issueCount === 1 ? "" : "s"} remain in focus.`
        : `${summary.issueCount} flagged review issue${summary.issueCount === 1 ? "" : "s"} should be checked before downstream reuse.`,
      detail: summary.detail,
      footnote: focusIssues
        ? "Risk focus is on. Saved checks stay separate while flagged claims are prioritized first."
        : "Saved checks stay separate. Claim review only changes which claims are surfaced first.",
    };
  }

  if (summary.state === "unavailable") {
    return {
      title: focusIssues ? "Risk focus is on, but claim review is not available yet." : "Claim review is not available yet.",
      detail: summary.detail,
      footnote: "Continue with saved checks, or generate claim review when you need claim-level ranking.",
    };
  }

  return {
    title: "Risk focus is on, but no claim review flags are recorded.",
    detail: null,
    footnote: "Saved checks stay separate. Risk focus only changes which claims are surfaced first.",
  };
}

function inferPersonaKind(option: PersonaOption): PersonaOption["kind"] {
  if (option.kind) {
    return option.kind;
  }
  if (option.id === "default") {
    return "compatibility";
  }
  return option.source === "builtin" ? "reasoning_persona" : "profile";
}

function buildRunSelection(reasoning: ReasoningSelection, profileId: string): {
  personaId: string;
  reasoningPersona?: ReasoningPersonaId;
  profileId?: string;
} {
  const trimmedProfileId = profileId.trim();
  const resolvedReasoning = reasoning === "auto" ? undefined : reasoning;
  return {
    personaId: trimmedProfileId || resolvedReasoning || "default",
    reasoningPersona: resolvedReasoning,
    profileId: trimmedProfileId || undefined,
  };
}

function resolveParserBackendOverride(rawValue: string | null): ParserBackendOverride | undefined {
  const normalized = String(rawValue || "").trim().toLowerCase();
  if (normalized === "fitz_pdfplumber" || normalized === "docling") {
    return normalized;
  }
  return undefined;
}

function buildWorkbenchPaperPath(paperId: string, parserBackendOverride?: ParserBackendOverride): string {
  const encodedPaperId = encodeURIComponent(paperId);
  if (!parserBackendOverride) {
    return `/workbench/${encodedPaperId}`;
  }
  const query = new URLSearchParams({ parser_backend: parserBackendOverride });
  return `/workbench/${encodedPaperId}?${query.toString()}`;
}

function paperIdVariants(paperId: string | null | undefined): string[] {
  const text = (paperId ?? "").trim();
  if (!text) {
    return [];
  }
  const variants: string[] = [];
  const append = (value: string) => {
    const candidate = value.trim();
    if (candidate && !variants.includes(candidate)) {
      variants.push(candidate);
    }
  };
  append(text);
  if (text.includes(":")) {
    append(text.split(":", 2)[1] ?? "");
  }
  return variants;
}

function paperIdsMatch(left: string | null | undefined, right: string | null | undefined): boolean {
  const rightVariants = new Set(paperIdVariants(right));
  return paperIdVariants(left).some((candidate) => rightVariants.has(candidate));
}

function shouldCanonicalizeWorkbenchPaperRoute(
  requestedPaperId: string | null | undefined,
  resolvedPaperId: string | null | undefined,
  resolvedNoteSlug?: string | null,
): boolean {
  const requested = (requestedPaperId ?? "").trim();
  const resolved = (resolvedPaperId ?? "").trim();
  if (!requested || !resolved || requested === resolved) {
    return false;
  }
  if (paperIdsMatch(requested, resolved)) {
    return true;
  }
  const noteSlug = (resolvedNoteSlug ?? "").trim();
  if (!noteSlug || requested !== noteSlug) {
    return false;
  }
  return true;
}

function findPaperInList(papers: PaperSummary[], paperId: string): PaperDetail | null {
  const requestedPaperId = paperId.trim();
  const matched = papers.find((entry) => {
    if (paperIdsMatch(entry.paper_id, requestedPaperId)) {
      return true;
    }
    return (entry.note_slug ?? "").trim() === requestedPaperId;
  });
  return matched ? ({ ...matched } as PaperDetail) : null;
}

function upsertPaperInList(papers: PaperSummary[], nextPaper: PaperDetail): PaperSummary[] {
  const index = papers.findIndex((entry) => paperIdsMatch(entry.paper_id, nextPaper.paper_id));
  const nextSummary: PaperSummary = { ...nextPaper };
  if (index < 0) {
    return [nextSummary, ...papers];
  }
  const updated = [...papers];
  updated[index] = {
    ...updated[index],
    ...nextSummary,
  };
  return updated;
}

function formatParserBackendLabel(value?: string | null): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "fitz_pdfplumber") {
    return "PDF text";
  }
  if (normalized === "docling") {
    return "Docling";
  }
  return String(value ?? "").trim();
}

function describeParserSelection(
  job: JobStatus | null,
  fallbackRequested?: ParserBackendOverride,
  allowFallbackRequested = false,
): string | null {
  const requested = job?.requested_parser_backend ?? (allowFallbackRequested ? fallbackRequested : undefined);
  const effective = job?.parser_backend;
  if (effective && requested && effective !== requested) {
    return `Document reader ${formatParserBackendLabel(effective)} (requested ${formatParserBackendLabel(requested)})`;
  }
  if (effective) {
    return `Document reader ${formatParserBackendLabel(effective)}`;
  }
  if (requested) {
    return `Requested document reader ${formatParserBackendLabel(requested)}`;
  }
  return null;
}

function buildParserResolutionMessage(job: JobStatus | null): string | null {
  const effective = job?.parser_backend;
  if (!effective) {
    return null;
  }
  const requested = job?.requested_parser_backend;
  if (requested && requested !== effective) {
    return `document reader selected: ${formatParserBackendLabel(effective)} (requested ${formatParserBackendLabel(requested)})`;
  }
  return `document reader selected: ${formatParserBackendLabel(effective)}`;
}

function buildParserResolutionLogKey(job: JobStatus | null): string | null {
  if (!job?.job_id || job.status !== "completed" || !job.parser_backend) {
    return null;
  }
  return `${job.job_id}:${job.requested_parser_backend ?? ""}:${job.parser_backend}`;
}

function hasParserSelectionMetadata(job: JobStatus | null | undefined): boolean {
  return Boolean(job?.requested_parser_backend || job?.parser_backend);
}

export function AnalysisWorkbench() {
  const params = useParams<{ paperId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const paperId = params.paperId ?? "";
  const focusIssues = searchParams.get("focus") === "issues";
  const parserBackendOverride = useMemo(
    () => resolveParserBackendOverride(searchParams.get("parser_backend")),
    [searchParams],
  );

  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [artifactBundle, setArtifactBundle] = useState<ArtifactBundle | null>(null);
  const [notebook, setNotebook] = useState<NotebookArtifact>(() => getNotebookFromBundle(getNotebookFallback(paperId)));
  const [paperStructuredState, setPaperStructuredState] = useState<StructuredPaperState | null>(null);
  const [noteSlug, setNoteSlug] = useState<string | null>(null);
  const [paperOperatorState, setPaperOperatorState] = useState<PaperNoteOperatorState | null>(null);
  const [paperSynthesis, setPaperSynthesis] = useState<PaperSynthesisListItem | null>(null);
  const [copiedWorkbenchPaperId, setCopiedWorkbenchPaperId] = useState(false);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [obsidianMirror, setObsidianMirror] = useState<ObsidianMirror | null>(null);
  const [loadingObsidianMirror, setLoadingObsidianMirror] = useState(false);
  const [syncingObsidian, setSyncingObsidian] = useState(false);
  const [cancellingRun, setCancellingRun] = useState(false);
  const [runningStatsAction, setRunningStatsAction] = useState<StatsActionMode | null>(null);
  const [actionFeedback, setActionFeedback] = useState<WorkbenchActionFeedback>(null);
  const [runVerify, setRunVerify] = useState(true);
  const [cleanReindex, setCleanReindex] = useState(false);
  const [panelDensity, setPanelDensity] = useState<"detail" | "compact">("detail");
  const [highlightMode, setHighlightMode] = useState<"soft" | "focus">("soft");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfPlaceholderNotice, setPdfPlaceholderNotice] = useState<string | null>(null);
  const [preserveRequestedParserSelection, setPreserveRequestedParserSelection] = useState(false);

  const searchQuery = useAppStore((state) => state.searchQuery);
  const setSearchQuery = useAppStore((state) => state.setSearchQuery);
  const activeClaimId = useAppStore((state) => state.activeClaimId);
  const setActiveClaimId = useAppStore((state) => state.setActiveClaimId);
  const selectedReasoningPersona = useAppStore((state) => state.selectedReasoningPersona);
  const setSelectedReasoningPersona = useAppStore((state) => state.setSelectedReasoningPersona);
  const selectedProfileId = useAppStore((state) => state.selectedProfileId);
  const setSelectedProfileId = useAppStore((state) => state.setSelectedProfileId);
  const terminalOpen = useAppStore((state) => state.terminalOpen);
  const setTerminalOpen = useAppStore((state) => state.setTerminalOpen);
  const toggleTerminal = useAppStore((state) => state.toggleTerminal);
  const mockMode = useAppStore((state) => state.mockMode);
  const mockReasons = useAppStore((state) => state.mockReasons);
  const markMockMode = useAppStore((state) => state.markMockMode);
  const clearMockMode = useAppStore((state) => state.clearMockMode);
  const themeMode = useAppStore((state) => state.themeMode);
  const setThemeMode = useAppStore((state) => state.setThemeMode);
  const paperNoteOpsByPaperId = useMemo(
    () =>
      Object.fromEntries(
        papers
          .filter((entry) => entry.ops_summary)
          .map((entry) => [entry.paper_id, entry.ops_summary!]),
      ),
    [papers],
  );
  const currentOpsSummary = useMemo(
    () =>
      paperNoteOpsByPaperId[paperId] ??
      derivePaperNoteOpsSummary({
        hasClaimset:
          Boolean(artifactBundle?.files.claimset_resolved?.exists) ||
          Boolean(artifactBundle?.files.claimset?.exists) ||
          Boolean(obsidianMirror?.has_claimset) ||
          Boolean(obsidianMirror?.claims.length),
        hasStatsReport:
          Boolean(artifactBundle?.files.stats_report?.exists) ||
          Boolean(obsidianMirror?.has_stats_report) ||
          Boolean(obsidianMirror?.stats_checks.length),
        statsCheckCount: obsidianMirror?.stats_checks.length ?? 0,
        latestRunId: job?.run_id ?? artifactBundle?.run_id ?? obsidianMirror?.run_id ?? null,
      }),
    [artifactBundle, job?.run_id, obsidianMirror, paperId, paperNoteOpsByPaperId],
  );
  const contentReviewSummary = useMemo(
    () =>
      paper
        ? deriveContentReviewSummary(paper.issues, {
            focusIssues,
            issuesLabel: paper.issues_label,
            issuesState: paper.issues_state,
          })
        : null,
    [focusIssues, paper],
  );
  const showContentReviewSummary =
    contentReviewSummary !== null &&
    (focusIssues || contentReviewSummary.issueCount > 0 || contentReviewSummary.state === "unavailable");
  const contentReviewFallbackText =
    contentReviewSummary?.state === "clear"
      ? "No claim review flags are recorded in the current paper summary."
      : "Claim review summary is not available for this paper yet.";
  const reasoningOptions = useMemo(
    () => personas.filter((option) => inferPersonaKind(option) === "reasoning_persona"),
    [personas],
  );
  const profileOptions = useMemo(
    () => personas.filter((option) => inferPersonaKind(option) === "profile"),
    [personas],
  );

  const filteredPapers = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return papers;
    }
    return papers.filter((item) => `${item.title} ${item.paper_id} ${item.authors ?? ""}`.toLowerCase().includes(q));
  }, [papers, searchQuery]);
  const claimGuard = useMemo(
    () => summarizeClaimGuard(notebook.claims, notebook.highlights),
    [notebook.claims, notebook.highlights],
  );

  const jobRef = useRef<JobStatus | null>(null);
  const paperIdRef = useRef<string>(paperId);
  const activeClaimIdRef = useRef<string | null>(activeClaimId);
  const focusIssuesRef = useRef<boolean>(focusIssues);
  const pdfBlobUrlRef = useRef<string | null>(null);
  const parserResolutionLogRef = useRef<string | null>(null);

  jobRef.current = job;
  paperIdRef.current = paperId;
  activeClaimIdRef.current = activeClaimId;
  focusIssuesRef.current = focusIssues;

  useEffect(() => {
    setCopiedWorkbenchPaperId(false);
  }, [paperId]);

  useEffect(() => {
    if (selectedReasoningPersona !== "auto" && !reasoningOptions.some((option) => option.id === selectedReasoningPersona)) {
      setSelectedReasoningPersona("auto");
    }
    if (selectedProfileId && !profileOptions.some((option) => option.id === selectedProfileId)) {
      setSelectedProfileId("");
    }
  }, [
    profileOptions,
    reasoningOptions,
    selectedProfileId,
    selectedReasoningPersona,
    setSelectedProfileId,
    setSelectedReasoningPersona,
  ]);

  const replacePdfBlobUrl = useCallback((nextUrl: string | null) => {
    if (pdfBlobUrlRef.current && pdfBlobUrlRef.current !== nextUrl) {
      URL.revokeObjectURL(pdfBlobUrlRef.current);
    }
    pdfBlobUrlRef.current = nextUrl;
    setPdfBlobUrl(nextUrl);
  }, []);

  const replacePaperList = useCallback((nextPapers: PaperSummary[], options?: { reusable?: boolean }) => {
    const reusable = options?.reusable ?? isCachedLivePapersReusable();
    replaceCachedLivePapers(nextPapers, { reusable });
    setPapers(nextPapers);
  }, []);

  const mergePaperIntoList = useCallback((nextPaper: PaperDetail) => {
    setPapers((prev) => {
      const updated = upsertPaperInList(prev, nextPaper);
      replaceCachedLivePapers(updated, { reusable: isCachedLivePapersReusable() });
      return updated;
    });
  }, []);

  const loadObsidianMirror = useCallback(
    async (runId: string | null | undefined) => {
      if (!paperId || !runId) {
        setObsidianMirror(null);
        setLoadingObsidianMirror(false);
        return;
      }

      setLoadingObsidianMirror(true);
      try {
        const mirrorResult = await getObsidianMirror(paperId, runId);
        if (mirrorResult.isMock) {
          markMockMode(mirrorResult.reason);
        }
        setObsidianMirror(mirrorResult.data);
      } finally {
        setLoadingObsidianMirror(false);
      }
    },
    [paperId, markMockMode],
  );

  const resolveNotebook = useCallback(
    async (
      bundle: ArtifactBundle,
    ): Promise<{
      notebook: NotebookArtifact;
      noteSlug: string | null;
      operatorState: PaperNoteOperatorState | null;
      structuredState: StructuredPaperState | null;
    }> => {
      const structuredResult = await getPaperNoteStructuredStateByPaperId(paperId);
      if (structuredResult.isMock) {
        markMockMode(structuredResult.reason);
      }
      const resolvedNoteSlug = structuredResult.data?.slug ?? null;
      const structuredState = structuredResult.data?.structured_state ?? null;
      const operatorState = structuredResult.data?.operator_state ?? null;
      if (structuredState && structuredState.claimset.length > 0) {
        return {
          notebook: getNotebookFromStructuredState(structuredState, bundle),
          noteSlug: resolvedNoteSlug,
          operatorState,
          structuredState,
        };
      }
      return {
        notebook: getNotebookFromBundle(bundle),
        noteSlug: resolvedNoteSlug,
        operatorState,
        structuredState,
      };
    },
    [markMockMode, paperId],
  );

  useEffect(() => {
    let mounted = true;

    async function loadLatestPaperSynthesis() {
      if (!noteSlug) {
        setPaperSynthesis(null);
        return;
      }

      const synthesisResult = await getLatestPaperSynthesis(noteSlug);
      if (!mounted) {
        return;
      }
      if (synthesisResult.isMock && synthesisResult.data) {
        markMockMode(synthesisResult.reason);
      }
      setPaperSynthesis(synthesisResult.data);
    }

    void loadLatestPaperSynthesis();

    return () => {
      mounted = false;
    };
  }, [markMockMode, noteSlug]);

  useEffect(() => {
    const key = buildParserResolutionLogKey(job);
    const message = buildParserResolutionMessage(job);
    if (!key || !message) {
      return;
    }
    if (parserResolutionLogRef.current === key) {
      return;
    }
    parserResolutionLogRef.current = key;
    setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][INFO] ${message}`]);
  }, [job]);

  useEffect(() => {
    return () => {
      if (pdfBlobUrlRef.current) {
        URL.revokeObjectURL(pdfBlobUrlRef.current);
        pdfBlobUrlRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const paperTitle = paper?.title?.trim();
    if (paperTitle) {
      document.title = `${paperTitle} | Lattice Workbench`;
      return;
    }
    if (paperId) {
      document.title = `${paperId} | Lattice Workbench`;
      return;
    }
    document.title = "Lattice Workbench";
  }, [paper?.title, paperId]);

  useEffect(() => {
    if (!parserBackendOverride) {
      setPreserveRequestedParserSelection(false);
    }
  }, [parserBackendOverride]);

  useEffect(() => {
    let mounted = true;

    async function loadWorkbench() {
      if (!paperId) {
        return;
      }

      setLoadError(null);
      setActionFeedback(null);
      setJob(null);
      setTimelineEvents([]);
      setTerminalLogs([]);
      parserResolutionLogRef.current = null;
      clearMockMode();
      replacePdfBlobUrl(null);
      setPdfPlaceholderNotice(null);
      setNoteSlug(null);
      setPaperStructuredState(null);
      setPaperOperatorState(null);
      setPaperSynthesis(null);
      setObsidianMirror(null);
      setLoadingObsidianMirror(true);

      try {
        const cachedPaperList = getCachedLivePapers();
        const [papersResult, personaResult, jobsResult, artifactResult] = await Promise.all([
          cachedPaperList ? Promise.resolve(null) : getPapers({ preferCache: true }),
          getPersonas(),
          getJobsForPaper(paperId),
          getArtifactsLatest(paperId),
        ]);

        if (!mounted) {
          return;
        }

        if (papersResult?.isMock) markMockMode(papersResult.reason);
        if (personaResult.isMock) markMockMode(personaResult.reason);
        if (jobsResult.isMock) markMockMode(jobsResult.reason);
        if (artifactResult.isMock) markMockMode(artifactResult.reason);

        const visiblePapers = cachedPaperList ?? papersResult?.data ?? [];
        if (papersResult) {
          replacePaperList(papersResult.data, { reusable: !papersResult.isMock });
        }
        setPersonas(personaResult.data.personas ?? []);

        let currentPaper = findPaperInList(visiblePapers, paperId);
        if (!currentPaper) {
          const structuredLookupResult = await getPaperNoteStructuredStateByPaperId(paperId);
          if (!mounted) {
            return;
          }
          if (structuredLookupResult.isMock && structuredLookupResult.data) {
            markMockMode(structuredLookupResult.reason);
          }
          if (
            structuredLookupResult.data &&
            shouldCanonicalizeWorkbenchPaperRoute(
              paperId,
              structuredLookupResult.data.paper_id,
              structuredLookupResult.data.slug,
            )
          ) {
            navigate(buildWorkbenchPaperPath(structuredLookupResult.data.paper_id, parserBackendOverride), {
              replace: true,
            });
            return;
          }
          const paperResult = await getPaper(paperId, { preferNoteDetail: true });
          if (!mounted) {
            return;
          }
          if (paperResult.isMock) {
            markMockMode(paperResult.reason);
          }
          currentPaper = paperResult.data;
          mergePaperIntoList(paperResult.data);
        }

        if (shouldCanonicalizeWorkbenchPaperRoute(paperId, currentPaper.paper_id, currentPaper.note_slug)) {
          navigate(buildWorkbenchPaperPath(currentPaper.paper_id, parserBackendOverride), { replace: true });
          return;
        }

        setPaper(currentPaper);

        const initialJob = jobsResult.data[0] ?? null;
        setJob(initialJob);

        const bundle = artifactResult.data;
        setArtifactBundle(bundle);
        const notebookResult = await resolveNotebook(bundle);
        if (!mounted) {
          return;
        }
        setNoteSlug(notebookResult.noteSlug);
        setPaperStructuredState(notebookResult.structuredState);
        setPaperOperatorState(notebookResult.operatorState);
        setNotebook(notebookResult.notebook);
        setActiveClaimId(chooseActiveClaimId(notebookResult.notebook, focusIssues, null));
        try {
          const pdfResult = await getPaperPdfBlobUrl(paperId, {
            preferPlaceholder: currentPaper.pdf_exists === false,
          });
          if (!mounted) {
            URL.revokeObjectURL(pdfResult.data);
            return;
          }
          if (pdfResult.isMock) {
            const usesPlaceholderPdf = (pdfResult.reason ?? "").includes("placeholder sample loaded");
            if (!usesPlaceholderPdf) {
              markMockMode(pdfResult.reason);
            }
            setPdfPlaceholderNotice(
              "The current PDF is a generic placeholder used to keep the viewer layout explorable. It is not source evidence for this paper.",
            );
          } else {
            setPdfPlaceholderNotice(null);
          }
          replacePdfBlobUrl(pdfResult.data);
        } catch (error) {
          if (!mounted) {
            return;
          }
          const pdfMessage = getApiErrorMessage(error);
          replacePdfBlobUrl(null);
          setPdfPlaceholderNotice(null);
          setLoadError((prev) => prev ? `${prev} / PDF: ${pdfMessage}` : `PDF unavailable: ${pdfMessage}`);
        }

        const runIdForMirror = initialJob?.run_id ?? bundle.run_id;
        await loadObsidianMirror(runIdForMirror);
        if (!mounted) {
          return;
        }

        if (initialJob?.run_id) {
          const timelineResult = await getRunTimeline(initialJob.run_id);
          if (!mounted) {
            return;
          }
          if (paperIdRef.current !== paperId || jobRef.current?.job_id !== initialJob.job_id) {
            return;
          }
          if (timelineResult.isMock) {
            markMockMode(timelineResult.reason);
          }
          setTimelineEvents(timelineResult.data.events);
          const parserResolutionKey = buildParserResolutionLogKey(initialJob);
          const parserResolutionMessage = buildParserResolutionMessage(initialJob);
          if (parserResolutionKey) {
            parserResolutionLogRef.current = parserResolutionKey;
          }
          const nextTerminalLogs = timelineResult.data.events.map((event) => {
              const level = event.level ?? (event.event === "error" ? "ERROR" : "INFO");
              return `[${event.ts ?? new Date().toISOString()}][${level}] ${event.message ?? event.raw ?? event.event}`;
            });
          if (parserResolutionMessage) {
            nextTerminalLogs.push(`[${new Date().toISOString()}][INFO] ${parserResolutionMessage}`);
          }
          setTerminalLogs(nextTerminalLogs);
        } else {
          setTimelineEvents([]);
          setTerminalLogs([]);
        }
      } catch (error) {
        if (!mounted) {
          return;
        }
        const message = getApiErrorMessage(error);
        setLoadError(message);
        replacePdfBlobUrl(null);
        setTimelineEvents([]);
        setObsidianMirror(null);
        setLoadingObsidianMirror(false);
        setTerminalLogs([`[${new Date().toISOString()}][ERROR] ${message}`]);
      }
    }

    void loadWorkbench();

    return () => {
      mounted = false;
    };
  }, [
    paperId,
    focusIssues,
    parserBackendOverride,
    navigate,
    clearMockMode,
    loadObsidianMirror,
    markMockMode,
    mergePaperIntoList,
    replacePaperList,
    replacePdfBlobUrl,
    resolveNotebook,
    setActiveClaimId,
  ]);

  const streamJobId = job?.job_id;
  const streamRunId = job?.run_id;
  const streamStatus = job?.status;

  useEffect(() => {
    const currentJob = jobRef.current;
    if (!currentJob || !streamJobId || !paperId) {
      return;
    }
    if (streamStatus === "completed" || streamStatus === "failed" || streamStatus === "cancelled") {
      return;
    }

    let subscription: StreamSubscription | null = null;
    let latestStage = currentJob.stage;
    const ownsCurrentScreen = (jobId = streamJobId) =>
      paperIdRef.current === paperId && jobRef.current?.job_id === jobId;

    subscription = connectJobStream(
      {
        paperId,
        jobId: streamJobId,
        runId: streamRunId ?? `run-${Date.now()}`,
        forceMock: mockMode,
        initialStatus: currentJob,
      },
      {
        onStatus: (next) => {
          if (!ownsCurrentScreen(next.job_id)) {
            return;
          }
          latestStage = next.stage;
          setJob(next);
          setTimelineEvents((prev) => {
            const entry: TimelineEvent = {
              event: "status",
              source: "sse",
              ts: new Date().toISOString(),
              stage: next.stage,
              progress: next.progress,
              level: "INFO",
              message: next.status,
            };
            return [...prev.slice(-199), entry];
          });
        },
        onLog: (line, level = "INFO") => {
          if (!ownsCurrentScreen()) {
            return;
          }
          const timestamp = new Date().toISOString();
          setTerminalLogs((prev) => [...prev.slice(-499), `[${timestamp}][${level}] ${line}`]);
          setTimelineEvents((prev) => {
            const entry: TimelineEvent = {
              event: level === "ERROR" ? "error" : "log",
              source: "sse",
              ts: timestamp,
              stage: latestStage,
              level,
              message: line,
            };
            return [...prev.slice(-199), entry];
          });
        },
        onDone: (status) => {
          if (!ownsCurrentScreen()) {
            return;
          }
          setJob((prev) =>
            prev
              ? {
                  ...prev,
                  status,
                  progress: status === "completed" ? 100 : prev.progress,
                  stage:
                    status === "completed" ? "completed" : status === "cancelled" ? "cancelled" : prev.stage,
                  finished_at: new Date().toISOString(),
                }
              : prev,
          );
          if (mockMode) {
            return;
          }
          void getJob(streamJobId)
            .then(async (jobResult) => {
              let resolvedJobResult = jobResult;
              if (!hasParserSelectionMetadata(jobResult.data)) {
                const jobsResult = await getJobsForPaper(paperId);
                if (!jobsResult.isMock) {
                  const matchedJob = jobsResult.data.find((candidate) => candidate.job_id === streamJobId) ?? null;
                  if (hasParserSelectionMetadata(matchedJob)) {
                    resolvedJobResult = {
                      data: matchedJob!,
                      isMock: false,
                    };
                  }
                }
              }
              if (!ownsCurrentScreen(resolvedJobResult.data.job_id)) {
                return;
              }
              if (resolvedJobResult.isMock) {
                markMockMode(resolvedJobResult.reason);
              }
              setJob((prev) =>
                prev && prev.job_id === resolvedJobResult.data.job_id
                  ? {
                      ...prev,
                      ...resolvedJobResult.data,
                      requested_parser_backend:
                        resolvedJobResult.data.requested_parser_backend ?? prev.requested_parser_backend,
                      parser_backend: resolvedJobResult.data.parser_backend ?? prev.parser_backend,
                    }
                  : resolvedJobResult.data,
              );
            })
            .catch((error) => {
              const message = getApiErrorMessage(error);
              setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
            });
        },
        onArtifactReady: async () => {
          if (!ownsCurrentScreen()) {
            return;
          }
          try {
            const [nextArtifacts, nextPaper] = await Promise.all([
              getArtifactsLatest(paperId),
              getPaper(paperId, { preferNoteDetail: true }),
            ]);
            if (!ownsCurrentScreen()) {
              return;
            }
            if (nextArtifacts.isMock) {
              markMockMode(nextArtifacts.reason);
            }
            if (nextPaper.isMock) {
              markMockMode(nextPaper.reason);
            }
            setPaper(nextPaper.data);
            mergePaperIntoList(nextPaper.data);
            setArtifactBundle(nextArtifacts.data);
            const nextNotebook = await resolveNotebook(nextArtifacts.data);
            if (!ownsCurrentScreen()) {
              return;
            }
            setNoteSlug(nextNotebook.noteSlug);
            setPaperStructuredState(nextNotebook.structuredState);
            setPaperOperatorState(nextNotebook.operatorState);
            setNotebook(nextNotebook.notebook);
            setActiveClaimId(
              chooseActiveClaimId(nextNotebook.notebook, focusIssuesRef.current, activeClaimIdRef.current),
            );
            await loadObsidianMirror(nextArtifacts.data.run_id);
          } catch (error) {
            const message = getApiErrorMessage(error);
            setLoadError(message);
            setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
          }
        },
        onModeChange: (isMock, reason) => {
          if (isMock) {
            markMockMode(reason);
          }
        },
      },
    );

    return () => {
      subscription?.close();
    };
  }, [
    streamJobId,
    streamRunId,
    streamStatus,
    mockMode,
    paperId,
    loadObsidianMirror,
    markMockMode,
    mergePaperIntoList,
    resolveNotebook,
    setActiveClaimId,
  ]);

  async function refreshData() {
    if (!paperId) {
      return;
    }
    try {
      setLoadError(null);
      const [jobResult, artifactResult, paperResult] = await Promise.all([
        job ? getJob(job.job_id) : Promise.resolve(null),
        getArtifactsLatest(paperId),
        getPaper(paperId, { preferNoteDetail: true }),
      ]);

      if (jobResult && jobResult.isMock) {
        markMockMode(jobResult.reason);
      }
      if (artifactResult.isMock) {
        markMockMode(artifactResult.reason);
      }
      if (paperResult.isMock) {
        markMockMode(paperResult.reason);
      }

      if (jobResult) {
        setJob(jobResult.data);
      }

      setPaper(paperResult.data);
      mergePaperIntoList(paperResult.data);
      setArtifactBundle(artifactResult.data);
      const nextNotebook = await resolveNotebook(artifactResult.data);
      setNoteSlug(nextNotebook.noteSlug);
      setPaperStructuredState(nextNotebook.structuredState);
      setPaperOperatorState(nextNotebook.operatorState);
      setNotebook(nextNotebook.notebook);
      setActiveClaimId(chooseActiveClaimId(nextNotebook.notebook, focusIssues, activeClaimId));
      const runIdForMirror = jobResult?.data.run_id ?? artifactResult.data.run_id ?? job?.run_id ?? null;
      await loadObsidianMirror(runIdForMirror);
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
    }
  }

  async function handleStatsAction(mode: StatsActionMode) {
    if (!paperId) {
      return;
    }
    const targetRunId = job?.run_id ?? artifactBundle?.run_id ?? obsidianMirror?.run_id ?? null;
    const skipExisting = mode === "repair";
    try {
      setRunningStatsAction(mode);
      setLoadError(null);
      setActionFeedback(null);
      const repairResult = await repairStats({
        paper_ids: [paperId],
        run_id: targetRunId,
        skip_existing: skipExisting,
        write_bootstrap_meta: true,
        dry_run: false,
      });
      if (repairResult.isMock) {
        markMockMode(repairResult.reason);
      }
      const summary = `repair-stats summary: mode=${mode}, seeded=${repairResult.data.seeded}, skipped=${repairResult.data.skipped}, total=${repairResult.data.total}`;
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][INFO] ${summary}`]);
      setActionFeedback({
        tone: "success",
        mode,
        message:
          mode === "repair"
            ? repairResult.data.seeded > 0
              ? "Saved checks rebuilt from the current saved claims. The current paper now uses the refreshed checks."
              : "Saved checks refresh completed without changes."
            : repairResult.data.seeded > 0
              ? "Existing saved checks were replaced from the current saved claims. The current paper now uses the refreshed checks."
              : "Saved checks rebuild completed without changes.",
      });
      setTerminalOpen(true);
      await refreshData();
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setActionFeedback({
        tone: "error",
        mode,
        message: `${mode === "repair" ? "Refresh checks" : "Rebuild checks"} failed: ${message}`,
      });
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
      setTerminalOpen(true);
    } finally {
      setRunningStatsAction(null);
    }
  }

  async function handleSyncObsidian() {
    if (!paperId) {
      return;
    }
    const runId = job?.run_id ?? artifactBundle?.run_id ?? obsidianMirror?.run_id ?? null;
    if (!runId) {
      setLoadError("No run id available for Obsidian sync.");
      setActionFeedback({
        tone: "error",
        mode: "sync",
        message: "No run id available for Obsidian sync.",
      });
      return;
    }

    try {
      setSyncingObsidian(true);
      setLoadError(null);
      setActionFeedback(null);
      const syncResult = await syncToObsidian(paperId, runId);
      if (syncResult.isMock) {
        markMockMode(syncResult.reason);
      }
      await loadObsidianMirror(runId);
      const syncMessage = syncResult.data.message ?? "Obsidian note updated.";
      setActionFeedback({
        tone: "success",
        mode: "sync",
        message: syncMessage,
      });
      setTerminalLogs((prev) => [
        ...prev.slice(-499),
        `[${new Date().toISOString()}][INFO] obsidian-sync summary: ${syncMessage}`,
      ]);
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setActionFeedback({
        tone: "error",
        mode: "sync",
        message: `Sync to Obsidian failed: ${message}`,
      });
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
      setTerminalOpen(true);
    } finally {
      setSyncingObsidian(false);
    }
  }

  async function runDeepRead() {
    if (!paperId) {
      return;
    }
    try {
      setLoadError(null);
      setActionFeedback(null);
      const runSelection = buildRunSelection(selectedReasoningPersona, selectedProfileId);
      const enqueueResult = await enqueueDeepRead({
        paper_id: paperId,
        run_verify: runVerify,
        clean_reindex: cleanReindex,
        persona_id: runSelection.personaId,
        reasoning_persona: runSelection.reasoningPersona,
        profile_id: runSelection.profileId,
        parser_backend: parserBackendOverride,
      });

      if (enqueueResult.isMock) {
        markMockMode(enqueueResult.reason);
      }

      const newJob: JobStatus = {
        job_id: enqueueResult.data.job_id,
        paper_id: paperId,
        run_id: enqueueResult.data.run_id ?? `run-${Date.now()}`,
        persona_id: runSelection.personaId,
        reasoning_persona: runSelection.reasoningPersona,
        profile_id: runSelection.profileId,
        requested_parser_backend: parserBackendOverride,
        status: "queued",
        progress: 0,
        stage: "ingest",
        created_at: new Date().toISOString(),
      };

      setJob(newJob);
      setTimelineEvents([]);
      const enqueueSummary = parserBackendOverride
        ? `deepread enqueued (${newJob.job_id}, requested_parser=${parserBackendOverride})`
        : `deepread enqueued (${newJob.job_id})`;
      setTerminalLogs([`[${new Date().toISOString()}][INFO] ${enqueueSummary}`]);
      setTerminalOpen(true);
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
      setTerminalOpen(true);
    }
  }

  async function copyWorkbenchPaperId() {
    if (!paperId || typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      return;
    }
    try {
      await navigator.clipboard.writeText(paperId);
      setCopiedWorkbenchPaperId(true);
      window.setTimeout(() => setCopiedWorkbenchPaperId(false), 1800);
    } catch {
      setCopiedWorkbenchPaperId(false);
    }
  }

  async function handleCancelRun() {
    if (!paperId || !job?.job_id) {
      return;
    }

    const targetJobId = job.job_id;
    const targetRunId = job.run_id ?? null;
    try {
      setCancellingRun(true);
      setLoadError(null);
      setActionFeedback(null);
      const cancelResult = await cancelJobRun(targetJobId);
      if (cancelResult.isMock) {
        markMockMode(cancelResult.reason);
      }

      const timestamp = new Date().toISOString();
      setJob((prev) =>
        prev && prev.job_id === targetJobId
          ? {
              ...prev,
              status: "cancelled",
              stage: "cancelled",
              finished_at: timestamp,
            }
          : prev,
      );
      setTimelineEvents((prev) => [
        ...prev.slice(-199),
        {
          event: "status",
          source: "user_action",
          ts: timestamp,
          stage: "cancelled",
          level: "INFO",
          message: "cancelled",
        },
      ]);
      setTerminalLogs((prev) => [
        ...prev.slice(-499),
        `[${timestamp}][INFO] deepread cancelled (${targetJobId})`,
      ]);
      setActionFeedback({
        tone: "success",
        mode: "cancel",
        message: cancelResult.isMock
          ? "The current run was cancelled in fallback mode. Existing saved artifacts stay as-is."
          : "The current deep read was cancelled. Existing saved artifacts stay as-is.",
      });
      logClientUserAction({
        paper_id: paperId,
        action_type: "deepread_cancel_requested",
        source: "workbench",
        payload: {
          job_id: targetJobId,
          run_id: targetRunId,
        },
      });
      setTerminalOpen(true);
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setActionFeedback({
        tone: "error",
        mode: "cancel",
        message: `Cancel run failed: ${message}`,
      });
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
      setTerminalOpen(true);
    } finally {
      setCancellingRun(false);
    }
  }

  const focusWorkbenchRegion = useCallback((regionId: string) => {
    const element = document.getElementById(regionId);
    if (element instanceof HTMLElement) {
      element.focus();
    }
  }, []);

  if (!paperId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--pp-canvas)] text-sm text-[var(--pp-text-secondary)]">
        Invalid paper id.
      </div>
    );
  }

  const currentJob = job ?? buildIdleJob(paperId);
  const stage = mapStage(currentJob.stage, currentJob.status);
  const mockReason = mockReasons.join(" / ");
  const pdfAvailable = Boolean(pdfBlobUrl);
  const pdfUrl = pdfBlobUrl ?? "";
  const runIdForObsidianSync = job?.run_id ?? artifactBundle?.run_id ?? obsidianMirror?.run_id ?? null;
  const hasClaimsetArtifact =
    Boolean(artifactBundle?.files.claimset_resolved?.exists) ||
    Boolean(artifactBundle?.files.claimset?.exists) ||
    Boolean(obsidianMirror?.has_claimset) ||
    Boolean(obsidianMirror?.claims.length);
  const hasStatsArtifact =
    Boolean(artifactBundle?.files.stats_report?.exists) ||
    Boolean(obsidianMirror?.has_stats_report) ||
    Boolean(obsidianMirror?.stats_checks.length);
  const canRepairStats = !loadingObsidianMirror && hasClaimsetArtifact && !hasStatsArtifact;
  const canRebuildStats = !loadingObsidianMirror && hasClaimsetArtifact && hasStatsArtifact;
  const hasActiveRun = job?.status === "queued" || job?.status === "running";
  const repairingStats = runningStatsAction !== null;
  const actionBusy = repairingStats || syncingObsidian || cancellingRun;
  const hasClaimGuardNotice = claimGuard.fallbackCount > 0 || claimGuard.missingCount > 0 || claimGuard.missingTextCount > 0;
  const showNotice =
    showContentReviewSummary ||
    loadError ||
    hasClaimGuardNotice ||
    canRepairStats ||
    repairingStats ||
    cancellingRun ||
    syncingObsidian ||
    Boolean(actionFeedback);
  const showRebuildNotice = runningStatsAction === "rebuild";
  const parserSelectionLabel = describeParserSelection(
    job,
    parserBackendOverride,
    preserveRequestedParserSelection || (mockMode && Boolean(parserBackendOverride)),
  );
  const workbenchAccessSummary = getPaperAccessSummaryDisplay(paper?.access_summary);
  const workbenchSubtitle = "Review evidence, saved checks, and claim flags before regenerating or exporting downstream artifacts.";
  const paperOperatorNotePreview = summarizePaperOperatorNote(paperOperatorState?.paper_note_text);
  const sectionNavigationSignal = buildWorkbenchSectionNavigationSignal(paperStructuredState);
  const hasPaperOperatorMarkers = Boolean(
    paperOperatorState &&
      (paperOperatorState.starred ||
        paperOperatorState.triage_labels.length > 0 ||
        hasPaperOperatorNoteText(paperOperatorState.paper_note_text)),
  );
  const contentReviewNotice =
    showContentReviewSummary && contentReviewSummary ? buildContentReviewNoticeModel(contentReviewSummary, focusIssues) : null;
  const railShortcutNav = (
    <>
      <button
        type="button"
        onClick={() => focusWorkbenchRegion("workbench-document-panel")}
        className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2 py-0.5 text-[11px] text-[var(--pp-text-dim)]"
      >
        Jump to document panel
      </button>
      <button
        type="button"
        onClick={() => focusWorkbenchRegion("workbench-artifact-panel")}
        className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2 py-0.5 text-[11px] text-[var(--pp-text-dim)]"
      >
        Jump to artifact panel
      </button>
      <button
        type="button"
        onClick={() => focusWorkbenchRegion("workbench-timeline-panel")}
        className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2 py-0.5 text-[11px] text-[var(--pp-text-dim)]"
      >
        Jump to timeline
      </button>
    </>
  );
  const controlsDesktop = (
    <>
      <div
        data-testid="workbench-review-actions"
        className="flex flex-wrap items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2"
      >
        <div className="mr-1 min-w-[11rem]">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Review actions</p>
          <p className="text-[11px] leading-5 text-[var(--pp-text-dim)]">
            Keep the evidence-review loop moving before you tune session settings.
          </p>
        </div>

        {hasActiveRun || cancellingRun ? (
          <button
            type="button"
            onClick={() => void handleCancelRun()}
            disabled={cancellingRun}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] px-2.5 py-1.5 text-xs text-[var(--pp-status-failed-text)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Square className="h-3.5 w-3.5" />
            {cancellingRun ? "Cancelling..." : "Cancel run"}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void runDeepRead()}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs text-[var(--pp-accent-text)]"
          >
            <Play className="h-3.5 w-3.5" />
            Run deep read
          </button>
        )}

        <button
          type="button"
          onClick={() => void refreshData()}
          className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          Refresh
        </button>

        {canRepairStats ? (
          <button
            type="button"
            onClick={() => void handleStatsAction("repair")}
            disabled={actionBusy}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1.5 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Wrench className="h-3.5 w-3.5" />
            {runningStatsAction === "repair" ? "Refreshing..." : "Refresh checks"}
          </button>
        ) : null}
      </div>

      <details
        data-testid="workbench-session-controls"
        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
      >
        <summary className="cursor-pointer font-semibold text-[var(--pp-text-dim)]">Session controls</summary>
        <div className="mt-2 grid gap-2">
          <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Review setup</p>
            <p className="mt-1 max-w-[24rem] text-[11px] leading-5 text-[var(--pp-text-dim)]">
              Use these controls when you need to tune reading style, context, or document-reader behavior for this
              session.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
                Reading style
                <select
                  aria-label="Reading style"
                  value={selectedReasoningPersona}
                  onChange={(event) => setSelectedReasoningPersona(event.target.value as ReasoningSelection)}
                  className="bg-transparent text-[var(--pp-text-primary)] outline-none"
                >
                  <option value="auto">Auto</option>
                  {reasoningOptions.map((persona) => (
                    <option key={persona.id} value={persona.id}>
                      {persona.title}
                    </option>
                  ))}
                </select>
              </label>

              <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
                Context profile
                <select
                  aria-label="Context profile"
                  value={selectedProfileId}
                  onChange={(event) => setSelectedProfileId(event.target.value)}
                  className="bg-transparent text-[var(--pp-text-primary)] outline-none"
                >
                  <option value="">No context profile</option>
                  {profileOptions.map((persona) => (
                    <option key={persona.id} value={persona.id}>
                      {persona.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {parserSelectionLabel ? (
              <p data-testid="workbench-parser-selection" className="mt-2 text-[11px] text-[var(--pp-text-dim)]">
                {parserSelectionLabel}
              </p>
            ) : null}
          </div>

          {canRebuildStats || runningStatsAction === "rebuild" ? (
            <div
              data-testid="stats-advanced-controls"
              className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2"
            >
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Review maintenance</p>
              <p className="mt-1 text-[11px] leading-5 text-[var(--pp-text-dim)]">
                Rebuild saved checks from the latest saved claims when the current review snapshot looks stale or
                inconsistent.
              </p>
              <button
                type="button"
                onClick={() => void handleStatsAction("rebuild")}
                disabled={actionBusy}
                className="mt-2 inline-flex items-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1.5 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Wrench className="h-3.5 w-3.5" />
                {runningStatsAction === "rebuild" ? "Rebuilding saved checks..." : "Rebuild saved checks"}
              </button>
            </div>
          ) : null}

          <label className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
            <input
              aria-label="Verify checks"
              type="checkbox"
              checked={runVerify}
              onChange={(event) => setRunVerify(event.target.checked)}
            />
            Verify checks
          </label>

          <label className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
            <input
              aria-label="Fresh retrieval"
              type="checkbox"
              checked={cleanReindex}
              onChange={(event) => setCleanReindex(event.target.checked)}
            />
            Fresh retrieval
          </label>

          <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
            Theme
            <select
              aria-label="Theme"
              value={themeMode}
              onChange={(event) => setThemeMode(event.target.value as "dark" | "light" | "system")}
              className="bg-transparent text-[var(--pp-text-primary)] outline-none"
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="system">System</option>
            </select>
          </label>

          <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
            Panel density
            <select
              aria-label="Panel density"
              value={panelDensity}
              onChange={(event) => setPanelDensity(event.target.value as "detail" | "compact")}
              className="bg-transparent text-[var(--pp-text-primary)] outline-none"
            >
              <option value="detail">Detail</option>
              <option value="compact">Compact</option>
            </select>
          </label>

          <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
            Evidence highlight
            <select
              aria-label="Evidence highlight"
              value={highlightMode}
              onChange={(event) => setHighlightMode(event.target.value as "soft" | "focus")}
              className="bg-transparent text-[var(--pp-text-primary)] outline-none"
            >
              <option value="soft">Soft</option>
              <option value="focus">Focus</option>
            </select>
          </label>
        </div>
      </details>
    </>
  );
  const controlsMobile = (
    <>
      <div
        data-testid="workbench-review-actions-mobile"
        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2"
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Review actions</p>
        <p className="mt-1 text-[11px] leading-5 text-[var(--pp-text-dim)]">
          Move the current evidence-review thread forward before opening extra session controls.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => void refreshData()}
            className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Refresh
          </button>

          {hasActiveRun || cancellingRun ? (
            <button
              type="button"
              onClick={() => void handleCancelRun()}
              disabled={cancellingRun}
              className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] px-3 py-2 text-xs font-medium text-[var(--pp-status-failed-text)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Square className="h-3.5 w-3.5" />
              {cancellingRun ? "Cancelling..." : "Cancel run"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void runDeepRead()}
              className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 py-2 text-xs font-medium text-[var(--pp-accent-text)]"
            >
              <Play className="h-3.5 w-3.5" />
              Run deep read
            </button>
          )}
        </div>

        {canRepairStats ? (
          <button
            type="button"
            onClick={() => void handleStatsAction("repair")}
            disabled={actionBusy}
            className="mt-2 inline-flex w-full items-center justify-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Wrench className="h-3.5 w-3.5" />
            {runningStatsAction === "repair" ? "Refreshing..." : "Refresh checks"}
          </button>
        ) : null}
      </div>

      <div
        data-testid="workbench-session-setup-mobile"
        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2"
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Session setup</p>
        <p className="mt-1 text-[11px] leading-5 text-[var(--pp-text-dim)]">
          Tune reading style, context, and document-reader behavior for this session.
        </p>

        <label className="mt-2 flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
          Reading style
          <select
            aria-label="Reading style"
            value={selectedReasoningPersona}
            onChange={(event) => setSelectedReasoningPersona(event.target.value as ReasoningSelection)}
            className="max-w-[62%] bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
          >
            <option value="auto">Auto</option>
            {reasoningOptions.map((persona) => (
              <option key={persona.id} value={persona.id}>
                {persona.title}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-2 flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
          Context profile
          <select
            aria-label="Context profile"
            value={selectedProfileId}
            onChange={(event) => setSelectedProfileId(event.target.value)}
            className="max-w-[62%] bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
          >
            <option value="">No context profile</option>
            {profileOptions.map((persona) => (
              <option key={persona.id} value={persona.id}>
                {persona.title}
              </option>
            ))}
          </select>
        </label>

        {parserSelectionLabel ? (
          <p data-testid="workbench-parser-selection-mobile" className="mt-2 text-[11px] text-[var(--pp-text-dim)]">
            {parserSelectionLabel}
          </p>
        ) : null}
      </div>

      <details data-testid="stats-advanced-controls" className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
          Review maintenance
        </summary>
        <div className="mt-2 grid gap-2">
          {canRebuildStats || runningStatsAction === "rebuild" ? (
            <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2">
              <p className="text-[11px] leading-5 text-[var(--pp-text-dim)]">
                Rebuild saved checks from the latest saved claims when the current review snapshot looks stale or
                inconsistent.
              </p>
              <button
                type="button"
                onClick={() => void handleStatsAction("rebuild")}
                disabled={actionBusy}
                className="mt-2 inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Wrench className="h-3.5 w-3.5" />
                {runningStatsAction === "rebuild" ? "Rebuilding saved checks..." : "Rebuild saved checks"}
              </button>
            </div>
          ) : null}

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            <span>Verify checks</span>
            <input
              aria-label="Verify checks"
              type="checkbox"
              checked={runVerify}
              onChange={(event) => setRunVerify(event.target.checked)}
            />
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            <span>Fresh retrieval</span>
            <input
              aria-label="Fresh retrieval"
              type="checkbox"
              checked={cleanReindex}
              onChange={(event) => setCleanReindex(event.target.checked)}
            />
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            Theme
            <select
              aria-label="Theme"
              value={themeMode}
              onChange={(event) => setThemeMode(event.target.value as "dark" | "light" | "system")}
              className="bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="system">System</option>
            </select>
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            Panel density
            <select
              aria-label="Panel density"
              value={panelDensity}
              onChange={(event) => setPanelDensity(event.target.value as "detail" | "compact")}
              className="bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
            >
              <option value="detail">Detail</option>
              <option value="compact">Compact</option>
            </select>
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            Evidence highlight
            <select
              aria-label="Evidence highlight"
              value={highlightMode}
              onChange={(event) => setHighlightMode(event.target.value as "soft" | "focus")}
              className="bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
            >
              <option value="soft">Soft</option>
              <option value="focus">Focus</option>
            </select>
          </label>
        </div>
      </details>
    </>
  );

  return (
    <WorkbenchLayout
      title={paper?.title ?? paperId ?? "Review"}
      subtitle={workbenchSubtitle}
      headerMeta={
        <WorkspaceContextStrip
          testId="workbench-workspace-context"
          description="Keep access, saved checks, and claim review status aligned while you validate evidence."
          className="mt-0"
        >
          <WorkspaceContextCard eyebrow="Access" testId="workbench-workspace-context-access">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={workbenchAccessSummary.label}
                tone={workbenchAccessSummary.tone}
                className="px-2"
                testId="workbench-access-badge"
              />
              {workbenchAccessSummary.href ? (
                <a
                  href={workbenchAccessSummary.href}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="workbench-access-link"
                  className="text-xs text-[var(--pp-accent-text)] underline underline-offset-2"
                >
                  {workbenchAccessSummary.linkLabel}
                </a>
              ) : null}
            </div>
          </WorkspaceContextCard>
          <WorkspaceContextCard eyebrow="Saved review state" testId="workbench-workspace-context-state">
            <div
              className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-[var(--pp-text-dim)]"
              data-testid="workbench-paper-id-copy-row"
            >
              <span>
                Paper ID <span className="font-mono text-[var(--pp-text-secondary)]">{paperId}</span>
              </span>
              <button
                type="button"
                onClick={copyWorkbenchPaperId}
                className="inline-flex h-7 items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 text-xs text-[var(--pp-text-secondary)] hover:border-[var(--pp-accent-border)] hover:text-[var(--pp-accent-text)]"
                data-testid="workbench-copy-paper-id"
              >
                <Copy className="h-3.5 w-3.5" />
                {copiedWorkbenchPaperId ? "Copied" : "Copy ID"}
              </button>
            </div>
            <OperationalStateSummary
              summary={currentOpsSummary}
              badgeTestId="workbench-header-ops-badge"
              reasonTestId="workbench-header-ops-reason"
              compact
            />
            {sectionNavigationSignal ? (
              <div
                className="mt-1.5 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2.5 py-2"
                data-testid="workbench-section-navigation-signal"
              >
                <div className="flex flex-wrap gap-2">
                  <Badge className={sectionNavigationSignal.className}>{sectionNavigationSignal.label}</Badge>
                </div>
                <p className="mt-1.5 text-xs text-[var(--pp-text-dim)]" data-testid="workbench-section-navigation-signal-detail">
                  {sectionNavigationSignal.detail}
                </p>
              </div>
            ) : null}
            <div
              className="mt-1.5 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2.5 py-2"
              data-testid="workbench-paper-operator-summary"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Paper note</p>
              {!noteSlug ? (
                <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                  Linked paper note is not resolved yet, so paper-level judgment is unavailable here.
                </p>
              ) : hasPaperOperatorMarkers && paperOperatorState ? (
                <>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {paperOperatorState.starred ? <Badge variant="default">Starred</Badge> : null}
                    {hasPaperOperatorNoteText(paperOperatorState.paper_note_text) ? <Badge variant="outline">My note</Badge> : null}
                    {paperOperatorState.triage_labels.map((label) => (
                      <Badge key={`workbench-operator-${label}`} variant="muted">
                        {formatPaperNoteTriageLabel(label)}
                      </Badge>
                    ))}
                  </div>
                  {paperOperatorNotePreview ? (
                    <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{paperOperatorNotePreview}</p>
                  ) : null}
                  <Link
                    to={`/papers/${encodeURIComponent(noteSlug)}`}
                    className="mt-2 inline-flex text-xs text-[var(--pp-accent-text)] underline underline-offset-2"
                  >
                    Continue in note
                  </Link>
                </>
              ) : (
                <>
                  <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                    No paper-level note or triage markers are saved for this paper yet.
                  </p>
                  <Link
                    to={`/papers/${encodeURIComponent(noteSlug)}`}
                    className="mt-2 inline-flex text-xs text-[var(--pp-accent-text)] underline underline-offset-2"
                  >
                    Continue in note
                  </Link>
                </>
              )}
            </div>
          </WorkspaceContextCard>
          <WorkspaceContextCard eyebrow="Claim review" testId="workbench-workspace-context-review">
            {showContentReviewSummary ? (
              <ContentReviewSummary
                summary={contentReviewSummary}
                badgeTestId="workbench-header-review-badge"
                hintTestId="workbench-header-review-hint"
                detailTestId="workbench-header-review-detail"
                compact
              />
            ) : (
              <p className="text-xs text-[var(--pp-text-dim)]">{contentReviewFallbackText}</p>
            )}
          </WorkspaceContextCard>
        </WorkspaceContextStrip>
      }
      stage={stage}
      jobStatus={currentJob.status}
      mockMode={mockMode}
      mockReason={mockReason}
      notice={showNotice ? (
        <div className="grid gap-2">
          {canRepairStats || runningStatsAction === "repair" ? (
            <div data-testid="repair-stats-warning" className={getInlineNoticeClassName("warning")}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p className="font-semibold">
                    {runningStatsAction === "repair" ? "Refreshing saved checks..." : "Saved note checks are missing or empty."}
                  </p>
                  <p className="mt-1 text-[11px]">
                    {runningStatsAction === "repair"
                      ? "Rebuilding saved checks from the current saved claims. The artifact panel refreshes when the refresh finishes."
                      : "This paper already has saved claims but no saved checks artifact. Use Refresh checks to rebuild the saved checks from the current claims."}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
          {contentReviewNotice ? (
            <div data-testid="content-review-notice" className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Review focus</p>
              <p className="mt-1 text-sm text-[var(--pp-text-primary)]">
                {contentReviewNotice.title}
              </p>
              {contentReviewNotice.detail ? (
                <p data-testid="content-review-notice-detail" className="mt-1 text-[11px] text-[var(--pp-text-dim)]">
                  {contentReviewNotice.detail}
                </p>
              ) : null}
              <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">
                {contentReviewNotice.footnote}
              </p>
            </div>
          ) : null}
          {showRebuildNotice ? (
            <div data-testid="rebuild-stats-warning" className={getInlineNoticeClassName("warning")}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p className="font-semibold">Rebuilding saved checks...</p>
                  <p className="mt-1 text-[11px]">
                    Refreshing the saved review snapshot from the latest saved claims. The artifact panel refreshes when
                    the rebuild finishes.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
          {syncingObsidian ? (
            <div data-testid="sync-obsidian-warning" className={getInlineNoticeClassName("warning")}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p className="font-semibold">Syncing Obsidian mirror...</p>
                  <p className="mt-1 text-[11px]">
                    The current generated markdown is being written back to the vault note. The preview refreshes when
                    sync finishes.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
          {cancellingRun ? (
            <div data-testid="cancel-run-warning" className={getInlineNoticeClassName("warning")}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p className="font-semibold">Cancelling deep read...</p>
                  <p className="mt-1 text-[11px]">
                    The current run is being stopped. Existing saved artifacts stay in place unless you start a new run.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
          {actionFeedback ? (
            <div
              data-testid={getActionFeedbackTestId(actionFeedback.mode, actionFeedback.tone)}
              className={getInlineNoticeClassName(actionFeedback.tone)}
            >
              <div className="flex items-start gap-2">
                {actionFeedback.tone === "success" ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                )}
                <div>
                  <p className="font-semibold">{getActionFeedbackTitle(actionFeedback.mode, actionFeedback.tone)}</p>
                  <p className="mt-1 text-[11px]">{actionFeedback.message}</p>
                </div>
              </div>
            </div>
          ) : null}
          {claimGuard.fallbackCount > 0 ? (
            <p data-testid="claim-guard-fallback" className="text-xs text-[var(--pp-warning-text)]">
              {`${claimGuard.fallbackCount} claim(s) missing bbox; text-search fallback is active.`}
            </p>
          ) : null}
          {claimGuard.missingCount > 0 ? (
            <p data-testid="claim-guard-missing" className="text-xs text-[var(--pp-status-failed-text)]">
              {`${claimGuard.missingCount} claim(s) missing both bbox and usable text; jump defaults to page 1.`}
            </p>
          ) : null}
          {claimGuard.missingTextCount > 0 ? (
            <p data-testid="claim-guard-text-missing" className="text-xs text-[var(--pp-status-failed-text)]">
              {`${claimGuard.missingTextCount} claim text field(s) are missing.`}
            </p>
          ) : null}
          {loadError ? (
            <div data-testid="workbench-load-error" className="text-xs text-[var(--pp-status-failed-text)]">
              <p>API error: {loadError}</p>
              <p className="mt-1 text-[var(--pp-text-dim)]">
                If this should be a live workbench run,{" "}
                <Link to="/ready" className="text-[var(--pp-accent-text)] underline underline-offset-2">
                  open Runtime checks
                </Link>{" "}
                before retrying.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
      rail={
        <Rail
          papers={filteredPapers}
          paperNoteOpsByPaperId={paperNoteOpsByPaperId}
          selectedPaperId={paperId}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          shortcutNav={railShortcutNav}
          onSelectPaper={(nextPaperId) => {
            setPreserveRequestedParserSelection(Boolean(parserBackendOverride));
            logClientUserAction({
              paper_id: nextPaperId,
              action_type: "workbench_select_paper",
              payload: {
                origin: "workbench_rail",
                from_paper_id: paperId,
              },
            });
            navigate(buildWorkbenchPaperPath(nextPaperId, parserBackendOverride));
          }}
        />
      }
      pdfPanel={
        <PanelErrorBoundary
          resetKey={pdfUrl}
          onError={(error) => {
            setLoadError((prev) => prev ?? `PDF viewer runtime error: ${error.message}`);
          }}
          fallback={
            <section className="surface-card flex min-h-0 flex-col p-3">
              <div className="flex min-h-[420px] flex-col items-center justify-center gap-2 text-center">
                <p className="text-sm text-[var(--pp-text-primary)]">PDF viewer failed to render.</p>
                <p className="text-xs text-[var(--pp-text-dim)]">
                  Try refreshing this paper. If the issue persists, re-open workbench from the paper list.
                </p>
              </div>
            </section>
          }
        >
          <Suspense
            fallback={
              <section className="surface-card flex min-h-0 flex-col p-3">
                <div className="flex min-h-[420px] items-center justify-center text-sm text-[var(--pp-text-dim)]">
                  Loading PDF viewer...
                </div>
              </section>
            }
          >
            <PdfPanel
              title={paper?.title ?? "Selected Paper"}
              paperId={paperId}
              pdfUrl={pdfUrl}
              pdfAvailable={pdfAvailable}
              placeholderNotice={pdfPlaceholderNotice}
              claims={notebook.claims}
              highlights={notebook.highlights}
              activeClaimId={activeClaimId}
              highlightMode={highlightMode}
            />
          </Suspense>
        </PanelErrorBoundary>
      }
      artifactPanel={
        <ArtifactPanel
          paperId={paperId}
          runId={job?.run_id ?? artifactBundle?.run_id ?? obsidianMirror?.run_id ?? null}
          notebook={notebook}
          highlights={notebook.highlights}
          inferenceSummary={artifactBundle?.inference_summary ?? null}
          rawArtifact={artifactBundle?.files ?? {}}
          obsidianMirror={obsidianMirror}
          opsSummary={currentOpsSummary}
          contentReviewSummary={showContentReviewSummary ? contentReviewSummary : null}
          paperSynthesis={paperSynthesis}
          syncEnabled={Boolean(runIdForObsidianSync) && !repairingStats}
          syncing={syncingObsidian}
          onSyncObsidian={() => void handleSyncObsidian()}
          activeClaimId={activeClaimId}
          onSelectClaim={setActiveClaimId}
          density={panelDensity}
        />
      }
      timelinePanel={<TimelinePanel events={timelineEvents} density={panelDensity} />}
      controls={controlsDesktop}
      controlsMobile={controlsMobile}
      terminalOpen={terminalOpen}
      terminalLogs={terminalLogs}
      onToggleTerminal={toggleTerminal}
      onCloseTerminal={() => setTerminalOpen(false)}
    />
  );
}

function getNotebookFallback(paperId: string): ArtifactBundle {
  return {
    paper_id: paperId,
    run_id: `run-fallback-${paperId}`,
    files: {},
  };
}
