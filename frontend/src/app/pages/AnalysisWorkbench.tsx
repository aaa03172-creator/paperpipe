import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Play, RefreshCcw, Wrench } from "lucide-react";
import {
  enqueueDeepRead,
  getArtifactsLatest,
  getApiErrorMessage,
  getJob,
  getJobsForPaper,
  getObsidianMirror,
  getPaper,
  getPaperNoteStructuredStateByPaperId,
  getPaperPdfBlobUrl,
  getPapers,
  getPersonas,
  getRunTimeline,
  logClientUserAction,
  syncToObsidian,
  repairStats,
} from "../lib/api";
import { connectJobStream, StreamSubscription } from "../lib/sse";
import { mapStage } from "../lib/ui";
import { deriveContentReviewSummary } from "../lib/contentReview";
import { derivePaperNoteOpsSummary } from "../lib/paperNoteOps";
import { buildBestHighlightMap, getClaimLinkState, summarizeClaimGuard } from "../lib/claimGuard";
import {
  ArtifactBundle,
  JobStatus,
  NotebookArtifact,
  ObsidianMirror,
  PaperDetail,
  PaperSummary,
  PersonaOption,
  ReasoningPersonaId,
  TimelineEvent,
} from "../lib/types";
import { getNotebookFromBundle, getNotebookFromStructuredState } from "../lib/mock";
import { useAppStore } from "../store/useAppStore";
import { Rail } from "../components/Rail";
import { ArtifactPanel } from "../components/ArtifactPanel";
import { TimelinePanel } from "../components/TimelinePanel";
import { PanelErrorBoundary } from "../components/PanelErrorBoundary";
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
type WorkbenchActionMode = StatsActionMode | "sync";
type ReasoningSelection = ReasoningPersonaId | "auto";

type WorkbenchActionFeedback =
  | {
      tone: "success" | "error";
      mode: WorkbenchActionMode;
      message: string;
    }
  | null;

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
  if (mode === "sync") {
    return `sync-obsidian-${tone}`;
  }
  return `${mode}-stats-${tone}`;
}

function getActionFeedbackTitle(mode: WorkbenchActionMode, tone: "success" | "error"): string {
  if (tone === "success") {
    if (mode === "repair") {
      return "Stats repair completed.";
    }
    if (mode === "rebuild") {
      return "Stats rebuild completed.";
    }
    return "Obsidian sync completed.";
  }

  if (mode === "repair") {
    return "Stats repair failed.";
  }
  if (mode === "rebuild") {
    return "Stats rebuild failed.";
  }
  return "Obsidian sync failed.";
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

export function AnalysisWorkbench() {
  const params = useParams<{ paperId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const paperId = params.paperId ?? "";
  const focusIssues = searchParams.get("focus") === "issues";

  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [artifactBundle, setArtifactBundle] = useState<ArtifactBundle | null>(null);
  const [notebook, setNotebook] = useState<NotebookArtifact>(() => getNotebookFromBundle(getNotebookFallback(paperId)));
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [obsidianMirror, setObsidianMirror] = useState<ObsidianMirror | null>(null);
  const [loadingObsidianMirror, setLoadingObsidianMirror] = useState(false);
  const [syncingObsidian, setSyncingObsidian] = useState(false);
  const [runningStatsAction, setRunningStatsAction] = useState<StatsActionMode | null>(null);
  const [actionFeedback, setActionFeedback] = useState<WorkbenchActionFeedback>(null);
  const [runVerify, setRunVerify] = useState(true);
  const [cleanReindex, setCleanReindex] = useState(false);
  const [panelDensity, setPanelDensity] = useState<"detail" | "compact">("detail");
  const [highlightMode, setHighlightMode] = useState<"soft" | "focus">("soft");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);

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
  const activeClaimIdRef = useRef<string | null>(activeClaimId);
  const focusIssuesRef = useRef<boolean>(focusIssues);
  const pdfBlobUrlRef = useRef<string | null>(null);

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
    async (bundle: ArtifactBundle): Promise<NotebookArtifact> => {
      const structuredResult = await getPaperNoteStructuredStateByPaperId(paperId);
      if (structuredResult.isMock) {
        markMockMode(structuredResult.reason);
      }
      const structuredState = structuredResult.data?.structured_state;
      if (structuredState && structuredState.claimset.length > 0) {
        return getNotebookFromStructuredState(structuredState, bundle);
      }
      return getNotebookFromBundle(bundle);
    },
    [markMockMode, paperId],
  );

  useEffect(() => {
    jobRef.current = job;
  }, [job]);

  useEffect(() => {
    activeClaimIdRef.current = activeClaimId;
  }, [activeClaimId]);

  useEffect(() => {
    focusIssuesRef.current = focusIssues;
  }, [focusIssues]);

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
    let mounted = true;

    async function loadWorkbench() {
      if (!paperId) {
        return;
      }

      setLoadError(null);
      setActionFeedback(null);
      clearMockMode();
      replacePdfBlobUrl(null);
      setObsidianMirror(null);
      setLoadingObsidianMirror(true);

      try {
        const [papersResult, paperResult, personaResult, jobsResult, artifactResult] = await Promise.all([
          getPapers(),
          getPaper(paperId),
          getPersonas(),
          getJobsForPaper(paperId),
          getArtifactsLatest(paperId),
        ]);

        if (!mounted) {
          return;
        }

        if (papersResult.isMock) markMockMode(papersResult.reason);
        if (paperResult.isMock) markMockMode(paperResult.reason);
        if (personaResult.isMock) markMockMode(personaResult.reason);
        if (jobsResult.isMock) markMockMode(jobsResult.reason);
        if (artifactResult.isMock) markMockMode(artifactResult.reason);

        setPapers(papersResult.data);
        setPaper(paperResult.data);
        setPersonas(personaResult.data.personas ?? []);

        const initialJob = jobsResult.data[0] ?? null;
        setJob(initialJob);

        const bundle = artifactResult.data;
        setArtifactBundle(bundle);
        const notebookData = await resolveNotebook(bundle);
        setNotebook(notebookData);
        setActiveClaimId(chooseActiveClaimId(notebookData, focusIssues, null));
        try {
          const pdfResult = await getPaperPdfBlobUrl(paperId);
          if (!mounted) {
            URL.revokeObjectURL(pdfResult.data);
            return;
          }
          if (pdfResult.isMock) {
            markMockMode(pdfResult.reason);
          }
          replacePdfBlobUrl(pdfResult.data);
        } catch (error) {
          if (!mounted) {
            return;
          }
          const pdfMessage = getApiErrorMessage(error);
          replacePdfBlobUrl(null);
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
          if (timelineResult.isMock) {
            markMockMode(timelineResult.reason);
          }
          setTimelineEvents(timelineResult.data.events);
          setTerminalLogs(
            timelineResult.data.events.map((event) => {
              const level = event.level ?? (event.event === "error" ? "ERROR" : "INFO");
              return `[${event.ts ?? new Date().toISOString()}][${level}] ${event.message ?? event.raw ?? event.event}`;
            }),
          );
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
  }, [paperId, focusIssues, clearMockMode, loadObsidianMirror, markMockMode, replacePdfBlobUrl, resolveNotebook, setActiveClaimId]);

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
          setJob((prev) =>
            prev
              ? {
                  ...prev,
                  status,
                  progress: status === "completed" ? 100 : prev.progress,
                  stage: status === "completed" ? "completed" : prev.stage,
                  finished_at: new Date().toISOString(),
                }
              : prev,
          );
        },
        onArtifactReady: async () => {
          try {
            const [nextArtifacts, nextPapers] = await Promise.all([getArtifactsLatest(paperId), getPapers()]);
            if (nextArtifacts.isMock) {
              markMockMode(nextArtifacts.reason);
            }
            if (nextPapers.isMock) {
              markMockMode(nextPapers.reason);
            }
            setPapers(nextPapers.data);
            setArtifactBundle(nextArtifacts.data);
            const nextNotebook = await resolveNotebook(nextArtifacts.data);
            setNotebook(nextNotebook);
            setActiveClaimId(
              chooseActiveClaimId(nextNotebook, focusIssuesRef.current, activeClaimIdRef.current),
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
  }, [streamJobId, streamRunId, streamStatus, mockMode, paperId, loadObsidianMirror, markMockMode, resolveNotebook, setActiveClaimId]);

  async function refreshData() {
    if (!paperId) {
      return;
    }
    try {
      setLoadError(null);
      const [jobResult, artifactResult, papersResult] = await Promise.all([
        job ? getJob(job.job_id) : Promise.resolve(null),
        getArtifactsLatest(paperId),
        getPapers(),
      ]);

      if (jobResult && jobResult.isMock) {
        markMockMode(jobResult.reason);
      }
      if (artifactResult.isMock) {
        markMockMode(artifactResult.reason);
      }
      if (papersResult.isMock) {
        markMockMode(papersResult.reason);
      }

      if (jobResult) {
        setJob(jobResult.data);
      }

      setPapers(papersResult.data);
      setArtifactBundle(artifactResult.data);
      const nextNotebook = await resolveNotebook(artifactResult.data);
      setNotebook(nextNotebook);
      setActiveClaimId(chooseActiveClaimId(nextNotebook, focusIssues, activeClaimId));
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
              ? `Stats snapshot rebuilt from claimset. ${repairResult.data.seeded} artifact bundle updated.`
              : "Stats repair completed without changes."
            : repairResult.data.seeded > 0
              ? `Existing Stats Snapshot was replaced from the current claimset fallback. ${repairResult.data.seeded} artifact bundle updated.`
              : "Stats rebuild completed without changes.",
      });
      setTerminalOpen(true);
      await refreshData();
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setActionFeedback({
        tone: "error",
        mode,
        message: `${mode === "repair" ? "Repair Stats" : "Rebuild Stats"} failed: ${message}`,
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
        status: "queued",
        progress: 0,
        stage: "ingest",
        created_at: new Date().toISOString(),
      };

      setJob(newJob);
      setTimelineEvents([]);
      setTerminalLogs([`[${new Date().toISOString()}][INFO] deepread enqueued (${newJob.job_id})`]);
      setTerminalOpen(true);
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
      setTerminalOpen(true);
    }
  }

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
  const repairingStats = runningStatsAction !== null;
  const actionBusy = repairingStats || syncingObsidian;
  const hasClaimGuardNotice = claimGuard.fallbackCount > 0 || claimGuard.missingCount > 0 || claimGuard.missingTextCount > 0;
  const showNotice =
    showContentReviewSummary ||
    loadError ||
    hasClaimGuardNotice ||
    canRepairStats ||
    repairingStats ||
    syncingObsidian ||
    Boolean(actionFeedback);
  const showRebuildNotice = runningStatsAction === "rebuild";
  const controlsDesktop = (
    <>
      <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        Reasoning
        <select
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

      <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        Profile
        <select
          value={selectedProfileId}
          onChange={(event) => setSelectedProfileId(event.target.value)}
          className="bg-transparent text-[var(--pp-text-primary)] outline-none"
        >
          <option value="">No profile</option>
          {profileOptions.map((persona) => (
            <option key={persona.id} value={persona.id}>
              {persona.title}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        onClick={() => void runDeepRead()}
        className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs text-[var(--pp-accent-text)]"
      >
        <Play className="h-3.5 w-3.5" />
        Deep Read Run
      </button>

      <button
        type="button"
        onClick={() => void refreshData()}
        className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
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
          {runningStatsAction === "repair" ? "Repairing..." : "Repair Stats"}
        </button>
      ) : null}

      {canRebuildStats || runningStatsAction === "rebuild" ? (
        <details
          data-testid="stats-advanced-controls"
          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
        >
          <summary className="cursor-pointer font-semibold text-[var(--pp-text-dim)]">Advanced actions</summary>
          <div className="mt-2 grid gap-2">
            <p className="max-w-[18rem] text-[11px] leading-5 text-[var(--pp-text-dim)]">
              Rebuild overwrites the current Stats Snapshot with a fresh claimset fallback. Use this only when the
              existing snapshot is stale or inconsistent.
            </p>
            <button
              type="button"
              onClick={() => void handleStatsAction("rebuild")}
              disabled={actionBusy}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1.5 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Wrench className="h-3.5 w-3.5" />
              {runningStatsAction === "rebuild" ? "Rebuilding..." : "Rebuild Stats"}
            </button>
          </div>
        </details>
      ) : null}

      <label className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        <input type="checkbox" checked={runVerify} onChange={(event) => setRunVerify(event.target.checked)} />
        Stats Verify
      </label>

      <label className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        <input type="checkbox" checked={cleanReindex} onChange={(event) => setCleanReindex(event.target.checked)} />
        Clean Reindex
      </label>

      <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        Theme
        <select
          value={themeMode}
          onChange={(event) => setThemeMode(event.target.value as "dark" | "light" | "system")}
          className="bg-transparent text-[var(--pp-text-primary)] outline-none"
        >
          <option value="dark">Dark</option>
          <option value="light">Light</option>
          <option value="system">System</option>
        </select>
      </label>

      <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        View
        <select
          value={panelDensity}
          onChange={(event) => setPanelDensity(event.target.value as "detail" | "compact")}
          className="bg-transparent text-[var(--pp-text-primary)] outline-none"
        >
          <option value="detail">Detail</option>
          <option value="compact">Compact</option>
        </select>
      </label>

      <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        Highlight
        <select
          value={highlightMode}
          onChange={(event) => setHighlightMode(event.target.value as "soft" | "focus")}
          className="bg-transparent text-[var(--pp-text-primary)] outline-none"
        >
          <option value="soft">Soft</option>
          <option value="focus">Focus</option>
        </select>
      </label>

    </>
  );
  const controlsMobile = (
    <>
      <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
        Reasoning
        <select
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

      <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
        Profile
        <select
          value={selectedProfileId}
          onChange={(event) => setSelectedProfileId(event.target.value)}
          className="max-w-[62%] bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
        >
          <option value="">No profile</option>
          {profileOptions.map((persona) => (
            <option key={persona.id} value={persona.id}>
              {persona.title}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => void refreshData()}
          className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          Refresh
        </button>

        <button
          type="button"
          onClick={() => void runDeepRead()}
          className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 py-2 text-xs font-medium text-[var(--pp-accent-text)]"
        >
          <Play className="h-3.5 w-3.5" />
          Deep Read Run
        </button>
      </div>

      {canRepairStats ? (
        <button
          type="button"
          onClick={() => void handleStatsAction("repair")}
          disabled={actionBusy}
          className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Wrench className="h-3.5 w-3.5" />
          {runningStatsAction === "repair" ? "Repairing..." : "Repair Stats"}
        </button>
      ) : null}

      <details data-testid="stats-advanced-controls" className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
          Advanced controls
        </summary>
        <div className="mt-2 grid gap-2">
          {canRebuildStats || runningStatsAction === "rebuild" ? (
            <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2">
              <p className="text-[11px] leading-5 text-[var(--pp-text-dim)]">
                Rebuild overwrites the current Stats Snapshot with a fresh claimset fallback.
              </p>
              <button
                type="button"
                onClick={() => void handleStatsAction("rebuild")}
                disabled={actionBusy}
                className="mt-2 inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2 text-xs text-[var(--pp-warning-text)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Wrench className="h-3.5 w-3.5" />
                {runningStatsAction === "rebuild" ? "Rebuilding..." : "Rebuild Stats"}
              </button>
            </div>
          ) : null}

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            <span>Stats Verify</span>
            <input type="checkbox" checked={runVerify} onChange={(event) => setRunVerify(event.target.checked)} />
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            <span>Clean Reindex</span>
            <input type="checkbox" checked={cleanReindex} onChange={(event) => setCleanReindex(event.target.checked)} />
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            Theme
            <select
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
            View
            <select
              value={panelDensity}
              onChange={(event) => setPanelDensity(event.target.value as "detail" | "compact")}
              className="bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
            >
              <option value="detail">Detail</option>
              <option value="compact">Compact</option>
            </select>
          </label>

          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
            Highlight
            <select
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
      title="Analysis Workbench"
      subtitle={paper?.title ?? paperId}
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
                    {runningStatsAction === "repair" ? "Repairing stats snapshot..." : "Stats report is missing or empty."}
                  </p>
                  <p className="mt-1 text-[11px]">
                    {runningStatsAction === "repair"
                      ? "Rebuilding Stats Snapshot from the current claimset. The artifact panel refreshes when the repair finishes."
                      : "This paper already has claimset data but no stats_report artifact. Use Repair Stats to rebuild the Stats Snapshot from the current claimset."}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
          {showContentReviewSummary ? (
            <div data-testid="content-review-notice" className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Content Review</p>
              <p className="mt-1 text-sm text-[var(--pp-text-primary)]">
                {contentReviewSummary!.state === "flagged"
                  ? `${contentReviewSummary!.issueCount} content review flag${contentReviewSummary!.issueCount === 1 ? "" : "s"} available.`
                  : contentReviewSummary!.state === "unavailable"
                    ? "Content review is not available yet."
                  : "No content flags recorded."}
              </p>
              {contentReviewSummary!.state !== "clear" && contentReviewSummary!.detail ? (
                <p data-testid="content-review-notice-detail" className="mt-1 text-[11px] text-[var(--pp-text-dim)]">
                  {contentReviewSummary!.detail}
                </p>
              ) : null}
              <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">
                {focusIssues
                  ? "Issue focus is enabled. Risk-related claims are prioritized separately from artifact health."
                  : "Content review is separate from artifact health and only affects claim-priority guidance."}
              </p>
            </div>
          ) : null}
          {showRebuildNotice ? (
            <div data-testid="rebuild-stats-warning" className={getInlineNoticeClassName("warning")}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p className="font-semibold">Rebuilding stats snapshot...</p>
                  <p className="mt-1 text-[11px]">
                    Rebuild Stats overwrites the current Stats Snapshot from the latest claimset fallback. The artifact
                    panel refreshes when the rebuild finishes.
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
            <p className="text-xs text-[var(--pp-status-failed-text)]">API error: {loadError}</p>
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
          onSelectPaper={(nextPaperId) => {
            logClientUserAction({
              paper_id: nextPaperId,
              action_type: "workbench_select_paper",
              payload: {
                origin: "workbench_rail",
                from_paper_id: paperId,
              },
            });
            navigate(`/workbench/${encodeURIComponent(nextPaperId)}`);
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
          rawArtifact={artifactBundle?.files ?? {}}
          obsidianMirror={obsidianMirror}
          opsSummary={currentOpsSummary}
          contentReviewSummary={showContentReviewSummary ? contentReviewSummary : null}
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
