import { getPaperNoteOpsActionLabel, getPaperNoteOpsReason, getPaperNoteOpsReasonClassName } from "../lib/paperNoteOps";
import { PaperNoteOpsSummary } from "../lib/types";
import { Badge } from "./ui/badge";
import { OperationalStateBadge } from "./OperationalStateBadge";

interface OperationalStateSummaryProps {
  summary?: PaperNoteOpsSummary | null;
  badgeTestId?: string;
  reasonTestId?: string;
  className?: string;
  compact?: boolean;
  showActionHint?: boolean;
}

export function OperationalStateSummary({
  summary,
  badgeTestId,
  reasonTestId,
  className,
  compact = false,
  showActionHint = true,
}: OperationalStateSummaryProps) {
  if (!summary) {
    return null;
  }

  const actionLabel = showActionHint ? getPaperNoteOpsActionLabel(summary) : null;
  const reason = getPaperNoteOpsReason(summary);
  const reasonClassName = getPaperNoteOpsReasonClassName(summary);

  return (
    <div className={["grid gap-1.5", className ?? ""].join(" ").trim()}>
      <div className="flex flex-wrap items-center gap-1.5">
        <OperationalStateBadge summary={summary} testId={badgeTestId} />
        {actionLabel ? <Badge variant="outline">{actionLabel}</Badge> : null}
      </div>
      {reason ? (
        <p data-testid={reasonTestId} className={`${compact ? "text-[11px]" : "text-xs"} ${reasonClassName}`}>
          {reason}
        </p>
      ) : null}
    </div>
  );
}
