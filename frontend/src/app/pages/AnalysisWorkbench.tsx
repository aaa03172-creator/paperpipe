import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Play, RefreshCcw } from "lucide-react";
import {
  enqueueDeepRead,
  getArtifactsLatest,
  getJob,
  getJobsForPaper,
  getPaper,
  getPaperPdfUrl,
  getPapers,
  getPersonas,
  getRunTimeline,
} from "../lib/api";
import { connectJobStream, StreamSubscription } from "../lib/sse";
import { mapStage } from "../lib/ui";
import {
  ArtifactBundle,
  JobStatus,
  NotebookArtifact,
  PaperDetail,
  PaperSummary,
  PersonaOption,
  TimelineEvent,
} from "../lib/types";
import { getNotebookFromBundle } from "../lib/mock";
import { useAppStore } from "../store/useAppStore";
import { Rail } from "../components/Rail";
import { PdfPanel } from "../components/PdfPanel";
import { ArtifactPanel } from "../components/ArtifactPanel";
import { TimelinePanel } from "../components/TimelinePanel";
import { WorkbenchLayout } from "../layouts/WorkbenchLayout";

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

export function AnalysisWorkbench() {
  const params = useParams<{ paperId: string }>();
  const navigate = useNavigate();
  const paperId = decodeURIComponent(params.paperId ?? "");

  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [artifactBundle, setArtifactBundle] = useState<ArtifactBundle | null>(null);
  const [notebook, setNotebook] = useState<NotebookArtifact>(() => getNotebookFromBundle(getNotebookFallback(paperId)));
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [runVerify, setRunVerify] = useState(true);
  const [cleanReindex, setCleanReindex] = useState(false);

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

  const jobRef = useRef<JobStatus | null>(null);

  useEffect(() => {
    jobRef.current = job;
  }, [job]);

  useEffect(() => {
    let mounted = true;

    async function loadWorkbench() {
      if (!paperId) {
        return;
      }

      clearMockMode();

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
      setActiveClaimId(notebookData.claims[0]?.claim_id ?? null);

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

    }

    void loadWorkbench();

    return () => {
      mounted = false;
    };
  }, [paperId, clearMockMode, markMockMode, setActiveClaimId]);

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
          const nextArtifacts = await getArtifactsLatest(paperId);
          if (nextArtifacts.isMock) {
            markMockMode(nextArtifacts.reason);
          }
          setArtifactBundle(nextArtifacts.data);
          const nextNotebook = getNotebookFromBundle(nextArtifacts.data);
          setNotebook(nextNotebook);
          setActiveClaimId(nextNotebook.claims[0]?.claim_id ?? null);
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
  }, [streamJobId, streamRunId, streamStatus, mockMode, paperId, markMockMode, setActiveClaimId]);

  async function refreshData() {
    if (!paperId) {
      return;
    }
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
    setActiveClaimId(nextNotebook.claims[0]?.claim_id ?? null);
  }

  async function runDeepRead() {
    if (!paperId) {
      return;
    }

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
  const pdfAvailable = mockMode || Boolean(paper?.pdf_exists);
  const pdfUrl = getPaperPdfUrl(paperId, mockMode);

  return (
    <WorkbenchLayout
      title="Analysis Workbench"
      subtitle={paper?.title ?? paperId}
      stage={stage}
      jobStatus={currentJob.status}
      mockMode={mockMode}
      mockReason={mockReason}
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
        <PdfPanel
          title={paper?.title ?? "Selected Paper"}
          paperId={paperId}
          pdfUrl={pdfUrl}
          pdfAvailable={pdfAvailable}
          highlights={notebook.highlights}
          activeClaimId={activeClaimId}
        />
      }
      artifactPanel={
        <ArtifactPanel
          notebook={notebook}
          rawArtifact={artifactBundle?.files ?? {}}
          activeClaimId={activeClaimId}
          onSelectClaim={setActiveClaimId}
        />
      }
      timelinePanel={<TimelinePanel events={timelineEvents} />}
      controls={
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

          <button
            type="button"
            onClick={() => void refreshData()}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Refresh
          </button>

          <button
            type="button"
            onClick={() => void runDeepRead()}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs text-[var(--pp-accent-text)]"
          >
            <Play className="h-3.5 w-3.5" />
            Deep Read Run
          </button>
        </>
      }
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
