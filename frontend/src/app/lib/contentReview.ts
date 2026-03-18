import { StatusTone, getStatusToneTextClassName } from "./statusSystem";

export interface ContentReviewSummary {
  issueCount: number;
  state: "flagged" | "clear" | "unavailable";
  badgeLabel: string;
  badgeTone: StatusTone;
  badgeIconTone: "danger" | null;
  reviewLabel: string;
  hint: string;
  detail: string | null;
  focusLabel: string | null;
}

export function deriveContentReviewSummary(
  issueCountValue?: number | null,
  options?: { focusIssues?: boolean; issuesLabel?: string | null; issuesState?: "flagged" | "clear" | "unavailable" | null },
): ContentReviewSummary {
  const issueCount = Math.max(0, issueCountValue ?? 0);
  const focusIssues = options?.focusIssues === true;
  const issuesLabel = typeof options?.issuesLabel === "string" ? options.issuesLabel.trim() : "";
  const explicitState = options?.issuesState;
  const flagged = explicitState === "flagged" || (explicitState == null && issueCount > 0);
  const unavailable =
    explicitState === "unavailable" ||
    (explicitState == null &&
      !flagged &&
      issuesLabel.length > 0 &&
      /not analy[sz]ed|unavailable|not available|pending|not reviewed|not run/i.test(issuesLabel));
  const state = flagged ? "flagged" : unavailable ? "unavailable" : "clear";

  return {
    issueCount,
    state,
    badgeLabel: flagged ? `${issueCount} flagged` : unavailable ? "Unavailable" : "Clear",
    badgeTone: flagged ? "danger" : unavailable ? "muted" : "outline",
    badgeIconTone: flagged ? "danger" : null,
    reviewLabel: flagged ? `Review ${issueCount} issue${issueCount === 1 ? "" : "s"}` : unavailable ? "Review unavailable" : "Review clear",
    hint: flagged
      ? "Content QA flags are separate from artifact health."
      : unavailable
        ? "Content review has not been generated for the current paper summary."
        : "No content flags in the current paper summary.",
    detail: flagged
      ? issuesLabel || `${issueCount} content review flag${issueCount === 1 ? "" : "s"} recorded in the current paper summary.`
      : unavailable
        ? issuesLabel
      : focusIssues
        ? "Issue focus is enabled, so the notebook is using risk-related claim heuristics."
        : null,
    focusLabel: focusIssues ? "Issue focus enabled" : null,
  };
}

export function getContentReviewHintClassName(summary: Pick<ContentReviewSummary, "state">): string {
  return getStatusToneTextClassName(
    summary.state === "flagged" ? "danger" : summary.state === "unavailable" ? "muted" : "outline",
  );
}
