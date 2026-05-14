import { PaperNoteOperatorState, PaperNoteOperatorTriageLabel } from "./types";

export const PAPER_NOTE_OPERATOR_TRIAGE_LABELS: PaperNoteOperatorTriageLabel[] = [
  "revisit",
  "needs_verification",
  "experiment_relevant",
];

export const MAX_PAPER_OPERATOR_NOTE_LENGTH = 4000;

const TRIAGE_LABEL_TEXT: Record<PaperNoteOperatorTriageLabel, string> = {
  revisit: "Revisit",
  needs_verification: "Needs verification",
  experiment_relevant: "Experiment relevant",
};

export function formatPaperNoteTriageLabel(label: PaperNoteOperatorTriageLabel): string {
  return TRIAGE_LABEL_TEXT[label] ?? label;
}

export function normalizePaperOperatorNoteText(value: string | null | undefined): string {
  return String(value ?? "").trim();
}

export function hasPaperOperatorNoteText(value: string | null | undefined): boolean {
  return normalizePaperOperatorNoteText(value).length > 0;
}

export function isSamePaperOperatorState(
  left: Pick<PaperNoteOperatorState, "paper_note_text" | "starred" | "triage_labels">,
  right: Pick<PaperNoteOperatorState, "paper_note_text" | "starred" | "triage_labels">,
): boolean {
  if (normalizePaperOperatorNoteText(left.paper_note_text) !== normalizePaperOperatorNoteText(right.paper_note_text)) {
    return false;
  }
  if (Boolean(left.starred) !== Boolean(right.starred)) {
    return false;
  }
  const leftLabels = left.triage_labels.join("|");
  const rightLabels = right.triage_labels.join("|");
  return leftLabels === rightLabels;
}
