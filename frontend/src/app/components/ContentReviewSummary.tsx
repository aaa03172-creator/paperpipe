import { ContentReviewSummary as ContentReviewSummaryModel, getContentReviewHintClassName } from "../lib/contentReview";
import { Badge } from "./ui/badge";
import { StatusBadge } from "./StatusBadge";

interface ContentReviewSummaryProps {
  summary?: ContentReviewSummaryModel | null;
  badgeTestId?: string;
  hintTestId?: string;
  detailTestId?: string;
  className?: string;
  compact?: boolean;
}

export function ContentReviewSummary({
  summary,
  badgeTestId,
  hintTestId,
  detailTestId,
  className,
  compact = false,
}: ContentReviewSummaryProps) {
  if (!summary) {
    return null;
  }

  return (
    <div className={["grid gap-1.5", className ?? ""].join(" ").trim()}>
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge
          label={summary.badgeLabel}
          tone={summary.badgeTone}
          iconTone={summary.badgeIconTone}
          testId={badgeTestId}
        />
        {summary.focusLabel ? <Badge variant="outline">{summary.focusLabel}</Badge> : null}
      </div>
      <p
        data-testid={hintTestId}
        className={`${compact ? "text-[11px]" : "text-xs"} ${getContentReviewHintClassName(summary)}`}
      >
        {summary.hint}
      </p>
      {summary.detail ? (
        <p data-testid={detailTestId} className={`${compact ? "text-[11px]" : "text-xs"} text-[var(--pp-text-dim)]`}>
          {summary.detail}
        </p>
      ) : null}
    </div>
  );
}
