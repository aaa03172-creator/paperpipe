import { ReactNode } from "react";
import { TerminalSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { Stepper } from "../components/Stepper";
import { StatusChip } from "../components/StatusChip";
import { TerminalDrawer } from "../components/TerminalDrawer";
import { JobLifecycle, PipelineStage } from "../lib/types";

interface WorkbenchLayoutProps {
  title: string;
  subtitle?: string;
  stage: PipelineStage;
  jobStatus: JobLifecycle;
  mockMode: boolean;
  mockReason?: string;
  mockReasons?: string[];
  rail: ReactNode;
  pdfPanel: ReactNode;
  artifactPanel: ReactNode;
  timelinePanel: ReactNode;
  controls?: ReactNode;
  controlsMobile?: ReactNode;
  notice?: ReactNode;
  terminalOpen: boolean;
  terminalLogs: string[];
  onToggleTerminal: () => void;
  onCloseTerminal: () => void;
}

export function WorkbenchLayout({
  title,
  subtitle,
  stage,
  jobStatus,
  mockMode,
  mockReason,
  mockReasons = [],
  rail,
  pdfPanel,
  artifactPanel,
  timelinePanel,
  controls,
  controlsMobile,
  notice,
  terminalOpen,
  terminalLogs,
  onToggleTerminal,
  onCloseTerminal,
}: WorkbenchLayoutProps) {
  const mobileControls = controlsMobile ?? controls;

  return (
    <div className="min-h-screen overflow-x-hidden bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-[var(--pp-text-primary)]">{title}</h1>
            {subtitle ? <p className="text-sm text-[var(--pp-text-secondary)]">{subtitle}</p> : null}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <StatusChip status={jobStatus} asJob />
            {mockMode ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                {mockReasons.length > 0 ? `Mock mode · ${mockReasons.length}` : "Mock mode"}
              </span>
            ) : null}
            <Link
              to="/papers"
              className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Paper Notes
            </Link>
            <button
              type="button"
              onClick={onToggleTerminal}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              <TerminalSquare className="h-3.5 w-3.5" />
              Terminal logs
            </button>
          </div>
        </div>

        <div className="mt-3 border-t border-[var(--pp-border)] pt-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Stepper stage={stage} jobStatus={jobStatus} />
            <div className="hidden flex-wrap items-center gap-2 md:flex">{controls}</div>
          </div>

          {mobileControls ? (
            <details className="mt-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] md:hidden">
              <summary className="cursor-pointer px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                Workbench controls
              </summary>
              <div className="grid gap-2 border-t border-[var(--pp-border)] p-3">{mobileControls}</div>
            </details>
          ) : null}
        </div>

        {mockMode && mockReason ? (
          <details data-testid="mock-mode-details" className="mt-2 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold text-[var(--pp-warning-text)]">
              Mock fallback details
            </summary>
            <ul className="mt-2 space-y-1 text-xs text-[var(--pp-warning-text)]">
              {mockReasons.length > 0
                ? mockReasons.map((reason) => (
                    <li key={reason} data-testid="mock-mode-reason-item">{reason}</li>
                  ))
                : <li data-testid="mock-mode-reason-item">{mockReason}</li>}
            </ul>
          </details>
        ) : null}
        {notice ? <div className="mt-2">{notice}</div> : null}
      </header>

      <main className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1.05fr)_minmax(0,1fr)] xl:items-start">
        <div className="order-2 min-h-0 xl:order-1 xl:sticky xl:top-4 xl:h-[calc(100vh-6.5rem)] xl:self-start">{rail}</div>
        <div className="order-1 min-h-0 xl:order-2">{pdfPanel}</div>
        <div className="order-3 grid min-h-0 gap-4 xl:order-3">
          <div className="min-h-0 xl:sticky xl:top-4 xl:h-[calc(100vh-6.5rem)] xl:self-start">{artifactPanel}</div>
          <div className="min-h-0">{timelinePanel}</div>
        </div>
      </main>

      <TerminalDrawer open={terminalOpen} logs={terminalLogs} onClose={onCloseTerminal} />
    </div>
  );
}
