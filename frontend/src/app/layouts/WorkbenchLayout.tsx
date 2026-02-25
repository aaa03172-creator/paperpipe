import { ReactNode } from "react";
import { TerminalSquare } from "lucide-react";
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
  rail: ReactNode;
  pdfPanel: ReactNode;
  artifactPanel: ReactNode;
  timelinePanel: ReactNode;
  controls?: ReactNode;
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
  rail,
  pdfPanel,
  artifactPanel,
  timelinePanel,
  controls,
  terminalOpen,
  terminalLogs,
  onToggleTerminal,
  onCloseTerminal,
}: WorkbenchLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
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
                Mock mode
              </span>
            ) : null}
            <button
              type="button"
              onClick={onToggleTerminal}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              <TerminalSquare className="h-3.5 w-3.5" />
              Show Terminal Logs
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--pp-border)] pt-3">
          <Stepper stage={stage} jobStatus={jobStatus} />
          <div className="flex flex-wrap items-center gap-2">{controls}</div>
        </div>

        {mockMode && mockReason ? (
          <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{mockReason}</p>
        ) : null}
      </header>

      <main className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1.05fr)_minmax(0,1fr)]">
        <div className="min-h-0">{rail}</div>
        <div className="min-h-0">{pdfPanel}</div>
        <div className="grid min-h-0 gap-4">
          <div className="min-h-0">{artifactPanel}</div>
          <div className="min-h-0">{timelinePanel}</div>
        </div>
      </main>

      <TerminalDrawer open={terminalOpen} logs={terminalLogs} onClose={onCloseTerminal} />
    </div>
  );
}
