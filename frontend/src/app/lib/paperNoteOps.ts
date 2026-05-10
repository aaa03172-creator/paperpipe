import { PaperNoteOpsSummary, PaperNoteSummary } from "./types";
import { StatusTone, getStatusToneTextClassName } from "./statusSystem";

export function paperNoteToPaperIdCandidates(note: Pick<PaperNoteSummary, "id" | "slug">): string[] {
  return expandPaperIdCandidates(note.id, note.slug);
}

export function paperNoteToWorkbenchPaperId(note: Pick<PaperNoteSummary, "id" | "slug"> | null): string | null {
  if (!note) {
    return null;
  }
  const id = String(note.id ?? "").trim();
  if (id.length > 0) {
    return id;
  }
  const slug = String(note.slug ?? "").trim();
  if (!slug) {
    return null;
  }
  if (slug.startsWith("zotero") && !slug.includes(":")) {
    return `zotero:${slug.slice("zotero".length)}`;
  }
  return slug;
}

export function expandPaperIdCandidates(...rawValues: Array<string | null | undefined>): string[] {
  const candidates: string[] = [];
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

export function getPaperNoteOpsReasonClassName(summary?: PaperNoteOpsSummary | null): string {
  return getStatusToneTextClassName(getPaperNoteOpsTone(summary));
}

export function getPaperNoteOpsReason(summary?: PaperNoteOpsSummary | null): string {
  if (!summary) {
    return "";
  }
  if (summary.state === "action_needed" && summary.recommended_action === "repair_stats") {
    return "Saved note checks are missing or empty. Open the workbench to refresh the saved note checks.";
  }
  if (summary.state === "action_needed" && summary.recommended_action === "open_workbench") {
    if (/stats snapshot/i.test(summary.reason)) {
      return "Saved note checks need review in the workbench.";
    }
  }
  return summary.reason;
}

export function getPaperNoteOpsActionLabel(summary?: PaperNoteOpsSummary | null): string | null {
  if (!summary) {
    return null;
  }
  if (summary.recommended_action === "repair_stats") {
    return "Refresh checks in Workbench";
  }
  if (summary.recommended_action === "open_workbench") {
    return "Review in Workbench";
  }
  return null;
}

export function derivePaperNoteOpsSummary(params: {
  hasClaimset: boolean;
  hasStatsReport: boolean;
  statsCheckCount?: number;
  latestRunId?: string | null;
}): PaperNoteOpsSummary | null {
  const statsCheckCount = Math.max(0, params.statsCheckCount ?? 0);
  if (params.hasClaimset && params.hasStatsReport && statsCheckCount > 0) {
    return {
      state: "healthy",
      label: "Healthy",
      reason: `Saved claims and note checks are available. ${statsCheckCount} checks are ready.`,
      recommended_action: "none",
      latest_run_id: params.latestRunId ?? null,
      has_claimset: true,
      has_stats_report: true,
      stats_check_count: statsCheckCount,
    };
  }

  if (params.hasClaimset && (!params.hasStatsReport || statsCheckCount === 0)) {
    return {
      state: "action_needed",
      label: "Action needed",
      reason: "Saved note checks are missing or empty.",
      recommended_action: "repair_stats",
      latest_run_id: params.latestRunId ?? null,
      has_claimset: true,
      has_stats_report: params.hasStatsReport,
      stats_check_count: statsCheckCount,
    };
  }

  if (params.hasStatsReport && !params.hasClaimset) {
    return {
      state: "action_needed",
      label: "Action needed",
      reason: "Saved note checks exist, but saved claims are missing.",
      recommended_action: "open_workbench",
      latest_run_id: params.latestRunId ?? null,
      has_claimset: false,
      has_stats_report: true,
      stats_check_count: statsCheckCount,
    };
  }

  return null;
}
