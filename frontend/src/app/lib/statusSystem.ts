import { JobLifecycle, PaperUiStatus } from "./types";

export type StatusTone = "idle" | "processing" | "success" | "warning" | "danger" | "outline" | "muted" | "accent";

export function getStatusToneClassName(tone: StatusTone): string {
  switch (tone) {
    case "processing":
      return "border-[var(--pp-status-processing-border)] bg-[var(--pp-status-processing-bg)] text-[var(--pp-status-processing-text)]";
    case "success":
      return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
    case "warning":
      return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
    case "danger":
      return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
    case "outline":
      return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)]";
    case "muted":
      return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
    case "accent":
      return "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]";
    case "idle":
    default:
      return "border-[var(--pp-status-idle-border)] bg-[var(--pp-status-idle-bg)] text-[var(--pp-status-idle-text)]";
  }
}

export function getStatusToneTextClassName(tone: StatusTone): string {
  switch (tone) {
    case "processing":
      return "text-[var(--pp-status-processing-text)]";
    case "success":
      return "text-[var(--pp-status-completed-text)]";
    case "warning":
      return "text-[var(--pp-warning-text)]";
    case "danger":
      return "text-[var(--pp-status-failed-text)]";
    case "accent":
      return "text-[var(--pp-accent-text)]";
    case "outline":
    case "muted":
    case "idle":
    default:
      return "text-[var(--pp-text-secondary)]";
  }
}

export function getPaperLifecycleTone(status?: PaperUiStatus | JobLifecycle | null): StatusTone {
  const normalized = String(status ?? "").toLowerCase();
  if (normalized === "processing" || normalized === "running" || normalized === "queued") {
    return "processing";
  }
  if (normalized === "completed") {
    return "success";
  }
  if (normalized === "failed" || normalized === "cancelled") {
    return "danger";
  }
  return "idle";
}

export function getFreeformStatusTone(status?: string | null): StatusTone {
  const normalized = String(status ?? "").trim().toLowerCase();
  if (!normalized) {
    return "muted";
  }
  if (normalized.includes("not started") || normalized.includes("not_started") || normalized === "new" || normalized === "draft") {
    return "idle";
  }
  if (normalized.includes("process") || normalized.includes("queue") || normalized.includes("run")) {
    return "processing";
  }
  if (normalized.includes("index") || normalized.includes("complete") || normalized.includes("ready")) {
    return "success";
  }
  if (normalized.includes("review") || normalized.includes("pending") || normalized.includes("hold")) {
    return "warning";
  }
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("missing")) {
    return "danger";
  }
  return "outline";
}

export function formatFreeformStatusLabel(status?: string | null): string {
  if (!status) {
    return "Unknown";
  }
  return status.replace(/_/g, " ");
}
