import { JobLifecycle, PaperUiStatus, PipelineStage } from "./types";

export const PIPELINE_STEPS: Array<{ key: PipelineStage; label: string }> = [
  { key: "ingest", label: "Ingest" },
  { key: "index", label: "Index" },
  { key: "read", label: "Deep Read" },
  { key: "verify", label: "Stats Verify" },
  { key: "completed", label: "Finalize" },
];

export function mapStage(stage?: string, status?: JobLifecycle): PipelineStage {
  const raw = String(stage ?? status ?? "").toLowerCase();
  if (raw.includes("ingest")) return "ingest";
  if (raw.includes("index")) return "index";
  if (raw.includes("read")) return "read";
  if (raw.includes("verify")) return "verify";
  if (raw.includes("complete") || raw.includes("done")) return "completed";
  if (raw.includes("fail") || raw.includes("cancel")) return "completed";
  return "ingest";
}

export function lifecycleToPaperStatus(status?: JobLifecycle): PaperUiStatus {
  const raw = String(status ?? "").toLowerCase();
  if (raw === "running" || raw === "queued") return "processing";
  if (raw === "completed") return "completed";
  if (raw === "failed" || raw === "cancelled") return "failed";
  return "not_started";
}

export function statusLabel(status: PaperUiStatus): string {
  switch (status) {
    case "processing":
      return "Processing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "not_started":
    default:
      return "Not Started";
  }
}

export function jobLabel(status: JobLifecycle): string {
  if (status === "running") return "Processing";
  if (status === "queued") return "Queued";
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  return "Cancelled";
}

export function circledNumber(index: number): string {
  const marks = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"];
  return marks[index] ?? `${index + 1}.`;
}
