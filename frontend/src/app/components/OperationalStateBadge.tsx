import { getPaperNoteOpsTone } from "../lib/paperNoteOps";
import { PaperNoteOpsSummary } from "../lib/types";
import { StatusBadge } from "./StatusBadge";

interface OperationalStateBadgeProps {
  summary?: PaperNoteOpsSummary | null;
  testId?: string;
  className?: string;
}

export function OperationalStateBadge({ summary, testId, className }: OperationalStateBadgeProps) {
  if (!summary) {
    return null;
  }

  const tone = getPaperNoteOpsTone(summary);
  const iconTone = tone === "success" || tone === "warning" || tone === "danger" || tone === "processing" ? tone : null;

  return <StatusBadge label={summary.label} tone={tone} iconTone={iconTone} testId={testId} className={className} />;
}
