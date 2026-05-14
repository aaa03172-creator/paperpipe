import { TerminalSquare, X } from "lucide-react";

interface TerminalDrawerProps {
  open: boolean;
  logs: string[];
  onClose: () => void;
}

export function TerminalDrawer({ open, logs, onClose }: TerminalDrawerProps) {
  if (!open) {
    return null;
  }

  return (
    <aside
      className="fixed right-0 top-0 z-40 h-full w-full max-w-xl border-l border-[var(--pp-border)] bg-[var(--pp-surface)] shadow-xl"
      aria-hidden={false}
    >
      <header className="flex items-center justify-between border-b border-[var(--pp-border)] px-4 py-3">
        <div className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--pp-text-primary)]">
          <TerminalSquare className="h-4 w-4" />
          Terminal Logs
        </div>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center justify-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-1.5 text-[var(--pp-text-secondary)]"
          aria-label="Close terminal logs"
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      <pre className="h-[calc(100%-53px)] overflow-auto bg-[var(--pp-log-bg)] p-4 font-mono text-xs leading-5 text-[var(--pp-log-text)]">
        {logs.length > 0
          ? logs.join("\n")
          : "[INFO] Waiting for stream...\n[INFO] Open a paper and start or observe a job to view logs."}
      </pre>
    </aside>
  );
}
