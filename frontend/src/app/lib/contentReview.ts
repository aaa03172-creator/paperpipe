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
  const reviewIssueLabel = `Review ${issueCount} issue${issueCount === 1 ? "" : "s"}`;

  return {
    issueCount,
    state,
    badgeLabel: flagged ? `${issueCount} flagged` : unavailable ? "Unavailable" : "Clear",
    badgeTone: flagged ? "danger" : unavailable ? "muted" : "outline",
    badgeIconTone: flagged ? "danger" : null,
    reviewLabel: flagged ? reviewIssueLabel : unavailable ? "Review unavailable" : "Review clear",
    hint: flagged
      ? "Claim review flags are separate from saved checks."
      : unavailable
        ? "Claim review has not been generated for the current paper summary."
        : "No claim review flags in the current paper summary.",
    detail: flagged
      ? issuesLabel || `${issueCount} claim review flag${issueCount === 1 ? "" : "s"} recorded in the current paper summary.`
      : unavailable
        ? issuesLabel
      : focusIssues
        ? "Risk focus is on, so the notebook is using risk-related claim heuristics."
        : null,
    focusLabel: focusIssues ? "Risk focus on" : null,
  };
}

export function getContentReviewHintClassName(summary: Pick<ContentReviewSummary, "state">): string {
  return getStatusToneTextClassName(
    summary.state === "flagged" ? "danger" : summary.state === "unavailable" ? "muted" : "outline",
  );
}
