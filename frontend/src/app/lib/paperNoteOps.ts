import { PaperNoteOpsSummary, PaperNoteSummary } from "./types";
import { StatusTone, getStatusToneClassName, getStatusToneTextClassName } from "./statusSystem";

export function paperNoteToPaperIdCandidates(note: Pick<PaperNoteSummary, "id" | "slug">): string[] {
  const candidates: string[] = [];
  const rawValues = [note.id ?? "", note.slug ?? ""];
  for (const raw of rawValues) {
    const text = String(raw).trim();
    if (!text) {
      continue;
    }
    if (!candidates.includes(text)) {
      candidates.push(text);
    }
    if (text.startsWith("zotero:")) {
      const stripped = text.slice("zotero:".length).trim();
      if (stripped && !candidates.includes(stripped)) {
        candidates.push(stripped);
      }
    } else if (text.startsWith("zotero") && !text.includes(":")) {
      const prefixed = `zotero:${text.slice("zotero".length)}`;
      if (!candidates.includes(prefixed)) {
        candidates.push(prefixed);
      }
    }
  }
  return candidates;
}

export function buildPaperNoteOpsMap(items: PaperNoteSummary[]): Record<string, PaperNoteOpsSummary> {
  const output: Record<string, PaperNoteOpsSummary> = {};
  for (const item of items) {
    if (!item.ops_summary) {
      continue;
    }
    for (const candidate of paperNoteToPaperIdCandidates(item)) {
      output[candidate] = item.ops_summary;
    }
  }
  return output;
}

export function getPaperNoteOpsTone(summary?: PaperNoteOpsSummary | null): StatusTone {
  if (!summary) {
    return "muted";
  }
  if (summary.state === "healthy") {
    return "success";
  }
  if (summary.state === "action_needed") {
    return "warning";
  }
  return "muted";
}

export function getPaperNoteOpsClassName(summary?: PaperNoteOpsSummary | null): string {
  return getStatusToneClassName(getPaperNoteOpsTone(summary));
}

export function getPaperNoteOpsReasonClassName(summary?: PaperNoteOpsSummary | null): string {
  return getStatusToneTextClassName(getPaperNoteOpsTone(summary));
}

export function getPaperNoteOpsReason(summary?: PaperNoteOpsSummary | null): string {
  if (!summary) {
    return "";
  }
  if (summary.state === "action_needed" && summary.recommended_action === "repair_stats") {
    return `${summary.reason} Open in Workbench to repair the Stats Snapshot.`;
  }
  return summary.reason;
}

export function getPaperNoteOpsActionLabel(summary?: PaperNoteOpsSummary | null): string | null {
  if (!summary) {
    return null;
  }
  if (summary.recommended_action === "repair_stats") {
    return "Repair Stats in Workbench";
  }
  if (summary.recommended_action === "open_workbench") {
    return "Open in Workbench";
  }
  return null;
}
