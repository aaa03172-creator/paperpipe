import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Play, RefreshCcw } from "lucide-react";
import {
  enqueueDeepRead,
  getArtifactsLatest,
  getApiErrorMessage,
  getJob,
  getJobsForPaper,
  getObsidianMirror,
  getPaper,
  getPaperPdfBlobUrl,
  getPapers,
  getPersonas,
  getRunTimeline,
  syncToObsidian,
} from "../lib/api";
import { connectJobStream, StreamSubscription } from "../lib/sse";
import { mapStage } from "../lib/ui";
import { getClaimLinkState, summarizeClaimGuard } from "../lib/claimGuard";
import {
  ArtifactBundle,
  JobStatus,
  NotebookArtifact,
  ObsidianMirror,
  PaperDetail,
  PaperSummary,
  PersonaOption,
  TimelineEvent,
} from "../lib/types";
import { getNotebookFromBundle } from "../lib/mock";
import { useAppStore } from "../store/useAppStore";
import { Rail } from "../components/Rail";
import { ArtifactPanel } from "../components/ArtifactPanel";
import { TimelinePanel } from "../components/TimelinePanel";
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
  const highlightMap = new Map(notebook.highlights.map((item) => [item.claim_id, item]));

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
  const [syncingObsidian, setSyncingObsidian] = useState(false);
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
  const selectedPersonaId = useAppStore((state) => state.selectedPersonaId);
  const setSelectedPersonaId = useAppStore((state) => state.setSelectedPersonaId);
  const terminalOpen = useAppStore((state) => state.terminalOpen);
  const setTerminalOpen = useAppStore((state) => state.setTerminalOpen);
  const toggleTerminal = useAppStore((state) => state.toggleTerminal);
  const mockMode = useAppStore((state) => state.mockMode);
  const mockReasons = useAppStore((state) => state.mockReasons);
  const markMockMode = useAppStore((state) => state.markMockMode);
  const clearMockMode = useAppStore((state) => state.clearMockMode);
  const themeMode = useAppStore((state) => state.themeMode);
  const setThemeMode = useAppStore((state) => state.setThemeMode);

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
        return;
      }

      const mirrorResult = await getObsidianMirror(paperId, runId);
      if (mirrorResult.isMock) {
        markMockMode(mirrorResult.reason);
      }
      setObsidianMirror(mirrorResult.data);
    },
    [paperId, markMockMode],
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
      clearMockMode();
      replacePdfBlobUrl(null);
      setObsidianMirror(null);

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
        const notebookData = getNotebookFromBundle(bundle);
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
        setTerminalLogs([`[${new Date().toISOString()}][ERROR] ${message}`]);
      }
    }

    void loadWorkbench();

    return () => {
      mounted = false;
    };
  }, [paperId, focusIssues, clearMockMode, loadObsidianMirror, markMockMode, replacePdfBlobUrl, setActiveClaimId]);

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
            const nextArtifacts = await getArtifactsLatest(paperId);
            if (nextArtifacts.isMock) {
              markMockMode(nextArtifacts.reason);
            }
            setArtifactBundle(nextArtifacts.data);
            const nextNotebook = getNotebookFromBundle(nextArtifacts.data);
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
  }, [streamJobId, streamRunId, streamStatus, mockMode, paperId, loadObsidianMirror, markMockMode, setActiveClaimId]);

  async function refreshData() {
    if (!paperId) {
      return;
    }
    try {
      setLoadError(null);
      const [jobResult, artifactResult] = await Promise.all([
        job ? getJob(job.job_id) : Promise.resolve(null),
        getArtifactsLatest(paperId),
      ]);

      if (jobResult && jobResult.isMock) {
        markMockMode(jobResult.reason);
      }
      if (artifactResult.isMock) {
        markMockMode(artifactResult.reason);
      }

      if (jobResult) {
        setJob(jobResult.data);
      }

      setArtifactBundle(artifactResult.data);
      const nextNotebook = getNotebookFromBundle(artifactResult.data);
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

  async function handleSyncObsidian() {
    if (!paperId) {
      return;
    }
    const runId = job?.run_id ?? artifactBundle?.run_id ?? obsidianMirror?.run_id ?? null;
    if (!runId) {
      setLoadError("No run id available for Obsidian sync.");
      return;
    }

    try {
      setSyncingObsidian(true);
      setLoadError(null);
      const syncResult = await syncToObsidian(paperId, runId);
      if (syncResult.isMock) {
        markMockMode(syncResult.reason);
      }
      await loadObsidianMirror(runId);
      setTerminalLogs((prev) => [
        ...prev.slice(-499),
        `[${new Date().toISOString()}][INFO] ${syncResult.data.message ?? "Obsidian sync completed"}`,
      ]);
    } catch (error) {
      const message = getApiErrorMessage(error);
      setLoadError(message);
      setTerminalLogs((prev) => [...prev.slice(-499), `[${new Date().toISOString()}][ERROR] ${message}`]);
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
      const enqueueResult = await enqueueDeepRead({
        paper_id: paperId,
        run_verify: runVerify,
        clean_reindex: cleanReindex,
        persona_id: selectedPersonaId,
      });

      if (enqueueResult.isMock) {
        markMockMode(enqueueResult.reason);
      }

      const newJob: JobStatus = {
        job_id: enqueueResult.data.job_id,
        paper_id: paperId,
        run_id: enqueueResult.data.run_id ?? `run-${Date.now()}`,
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
  const hasClaimGuardNotice = claimGuard.fallbackCount > 0 || claimGuard.missingCount > 0 || claimGuard.missingTextCount > 0;
  const controlsDesktop = (
    <>
      <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
        Persona
        <select
          value={selectedPersonaId}
          onChange={(event) => setSelectedPersonaId(event.target.value)}
          className="bg-transparent text-[var(--pp-text-primary)] outline-none"
        >
          {personas.map((persona) => (
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
        Persona
        <select
          value={selectedPersonaId}
          onChange={(event) => setSelectedPersonaId(event.target.value)}
          className="max-w-[62%] bg-transparent text-right text-[var(--pp-text-primary)] outline-none"
        >
          {personas.map((persona) => (
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

      <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
          Advanced controls
        </summary>
        <div className="mt-2 grid gap-2">
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
      notice={focusIssues || loadError || hasClaimGuardNotice ? (
        <>
          {focusIssues ? (
            <p className="text-xs text-[var(--pp-warning-text)]">Issue focus enabled: prioritizing risk-related claims.</p>
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
        </>
      ) : null}
      rail={
        <Rail
          papers={filteredPapers}
          selectedPaperId={paperId}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSelectPaper={(nextPaperId) => navigate(`/workbench/${encodeURIComponent(nextPaperId)}`)}
        />
      }
      pdfPanel={
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
      }
      artifactPanel={
        <ArtifactPanel
          notebook={notebook}
          highlights={notebook.highlights}
          rawArtifact={artifactBundle?.files ?? {}}
          obsidianMirror={obsidianMirror}
          syncEnabled={Boolean(runIdForObsidianSync)}
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
