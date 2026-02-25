import { AlertTriangle, CheckCircle2, CircleDashed, LoaderCircle } from "lucide-react";
import { JobLifecycle, PaperUiStatus } from "../lib/types";
import { jobLabel, statusLabel } from "../lib/ui";

interface StatusChipProps {
  status: PaperUiStatus | JobLifecycle;
  asJob?: boolean;
}

function statusClasses(status: string): string {
  if (status === "processing" || status === "running" || status === "queued") {
    return "border-[var(--pp-status-processing-border)] bg-[var(--pp-status-processing-bg)] text-[var(--pp-status-processing-text)]";
  }
  if (status === "completed") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (status === "failed" || status === "cancelled") {
    return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
  }
  return "border-[var(--pp-status-idle-border)] bg-[var(--pp-status-idle-bg)] text-[var(--pp-status-idle-text)]";
}

function iconForStatus(status: string) {
  if (status === "processing" || status === "running" || status === "queued") {
    return <LoaderCircle className="motion-safe:animate-spin h-3.5 w-3.5" />;
  }
  if (status === "completed") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }
  if (status === "failed" || status === "cancelled") {
    return <AlertTriangle className="h-3.5 w-3.5" />;
  }
  return <CircleDashed className="h-3.5 w-3.5" />;
}

export function StatusChip({ status, asJob = false }: StatusChipProps) {
  const normalized = String(status).toLowerCase();
  return (
    <span className={["inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium", statusClasses(normalized)].join(" ")}>
      {iconForStatus(normalized)}
      {asJob ? jobLabel(status as JobLifecycle) : statusLabel(status as PaperUiStatus)}
    </span>
  );
}
