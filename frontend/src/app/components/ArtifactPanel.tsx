import { ReactNode, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, FileText, FlaskConical, NotebookPen } from "lucide-react";
import { getPaperSynthesisManifest, getPaperSynthesisMarkdownUrl, logClientUserAction } from "../lib/api";
import {
  EvidenceHighlight,
  NotebookArtifact,
  ObsidianMirror,
  PaperNoteOpsSummary,
  PaperSynthesisManifest,
  PaperSynthesisListItem,
  RunInferenceSummary,
} from "../lib/types";
import { buildBestHighlightMap, getClaimLinkState } from "../lib/claimGuard";
import { ContentReviewSummary as ContentReviewSummaryModel } from "../lib/contentReview";
import { circledNumber } from "../lib/ui";
import { ContentReviewSummary } from "./ContentReviewSummary";
import { OperationalStateSummary } from "./OperationalStateSummary";
import { Badge } from "./ui/badge";

interface ArtifactPanelProps {
  paperId?: string | null;
  runId?: string | null;
  notebook: NotebookArtifact;
  highlights: EvidenceHighlight[];
  inferenceSummary?: RunInferenceSummary | null;
  rawArtifact: unknown;
  obsidianMirror: ObsidianMirror | null;
  opsSummary?: PaperNoteOpsSummary | null;
  contentReviewSummary?: ContentReviewSummaryModel | null;
  paperSynthesis?: PaperSynthesisListItem | null;
  syncEnabled: boolean;
  syncing: boolean;
  onSyncObsidian: () => void;
  activeClaimId: string | null;
  onSelectClaim: (claimId: string) => void;
  density: "detail" | "compact";
}

interface PaperSynthesisManifestState {
  synthesisId: string | null;
  data: PaperSynthesisManifest | null;
  loading: boolean;
  error: string | null;
}

function verdictStyle(level: NotebookArtifact["verdict"]["level"]): { icon: ReactNode; className: string } {
  if (level === "pass") {
    return {
      icon: <CheckCircle2 className="h-4 w-4" />,
      className: "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
    };
  }
  if (level === "fail") {
    return {
      icon: <AlertTriangle className="h-4 w-4" />,
      className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    };
  }
  return {
    icon: <CircleHelp className="h-4 w-4" />,
    className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
  };
}

function stripLeadingClaimMarker(text: string): string {
  return text.replace(/^[①②③④⑤⑥⑦⑧⑨⑩]\s*/, "");
}

function normalizeClaimTextForMatch(text: string): string {
  return stripLeadingClaimMarker(text)
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function tokenizeMatchText(text: string): string[] {
  return normalizeClaimTextForMatch(text)
    .replace(/[^a-z0-9\s]/g, " ")
    .split(" ")
    .map((item) => item.trim())
    .filter((item) => item.length >= 3);
}

function scoreClaimTextAgainstSignals(claimText: string, signals: string[]): number {
  if (signals.length === 0) {
    return 0;
  }
  const claimTokens = new Set(tokenizeMatchText(claimText));
  if (claimTokens.size === 0) {
    return 0;
  }
  let score = 0;
  for (const signal of signals) {
    const signalTokens = tokenizeMatchText(signal);
    if (signalTokens.length === 0) {
      continue;
    }
    let overlap = 0;
    signalTokens.forEach((token) => {
      if (claimTokens.has(token)) {
        overlap += 1;
      }
    });
    score += overlap / signalTokens.length;
  }
  return score;
}

function getGroundingBadge(grounded?: boolean | null, resolution?: string | null): { label: string; className: string } | null {
  if (grounded === true) {
    if (resolution === "NORMALIZED_MATCH") {
      return {
        label: "Grounded (normalized)",
        className:
          "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
      };
    }
    return {
      label: "Grounded",
      className:
        "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
    };
  }
  if (grounded === false) {
    if (resolution === "AMBIGUOUS_MATCH") {
      return {
        label: "Needs review",
        className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
      };
    }
    return {
      label: "Unresolved",
      className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    };
  }
  return null;
}

function getPaperSynthesisReadinessBadgeClassName(readiness: PaperSynthesisListItem["readiness"]): string {
  if (readiness === "evidence_backed") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (readiness === "mixed") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function getPaperSynthesisFreshnessBadgeClassName(freshness: PaperSynthesisListItem["freshness"]): string {
  if (freshness === "current") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (freshness === "stale") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function formatPaperSynthesisLineageKind(
  kind: PaperSynthesisListItem["lineage_summary"]["present_required_source_kinds"][number],
): string {
  if (kind === "structured_state") {
    return "structured state";
  }
  if (kind === "claimset_resolved") {
    return "resolved claimset";
  }
  return "run metadata";
}

function formatPaperSynthesisSourceKind(kind: PaperSynthesisManifest["source_refs"][number]["kind"]): string {
  if (kind === "structured_state" || kind === "claimset_resolved" || kind === "run_meta") {
    return formatPaperSynthesisLineageKind(kind);
  }
  if (kind === "quality_gate" || kind === "acceptance_contract") {
    return formatPaperSynthesisReviewArtifactKind(kind);
  }
  if (kind === "document_artifact") {
    return "document artifact";
  }
  return "paper note state";
}

function formatPaperSynthesisReviewArtifactKind(
  kind: PaperSynthesisListItem["lineage_summary"]["review_artifact_kinds"][number],
): string {
  if (kind === "quality_gate") {
    return "quality gate";
  }
  return "acceptance contract";
}

function formatPaperSynthesisAnswerRoute(answerRoute: PaperSynthesisListItem["lineage_summary"]["answer_route"]): string {
  if (answerRoute === "canonical_state_then_upstream_evidence") {
    return "Canonical state -> upstream evidence";
  }
  return answerRoute;
}

function formatPaperSynthesisTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatInferenceToken(value: string): string {
  const normalized = value.trim();
  if (!normalized) {
    return "none";
  }
  return normalized.replace(/[_-]+/g, " ");
}

function getInferenceBackendBadgeClassName(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "local") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (normalized === "commercial" || normalized === "mixed" || normalized === "lab_server") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function getInferencePayloadBadgeClassName(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "local only" || normalized === "local_only") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (normalized === "external allowed" || normalized === "external_allowed" || normalized === "mixed") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  if (normalized === "lab allowed" || normalized === "lab_allowed") {
    return "border-[var(--pp-border)] bg-[var(--pp-surface)] text-[var(--pp-text-secondary)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function getInferenceRedactionBadgeClassName(redactionApplied: boolean): string {
  return redactionApplied
    ? "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
    : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function buildInferenceLaneTestId(laneName: string): string {
  return `workbench-inference-lane-${laneName.replace(/[^a-zA-Z0-9_-]+/g, "-")}`;
}

function resolveMirrorClaimTargetId(
  mirrorClaimId: string,
  mirrorStatement: string,
  notebook: NotebookArtifact,
): string | null {
  if (notebook.claims.some((claim) => claim.claim_id === mirrorClaimId)) {
    return mirrorClaimId;
  }
  const normalizedMirror = normalizeClaimTextForMatch(mirrorStatement);
  if (!normalizedMirror) {
    return null;
  }
  const exact = notebook.claims.find((claim) => normalizeClaimTextForMatch(claim.text) === normalizedMirror);
  if (exact) {
    return exact.claim_id;
  }
  const partial = notebook.claims.find((claim) => {
    const normalizedNotebook = normalizeClaimTextForMatch(claim.text);
    if (!normalizedNotebook) {
      return false;
    }
    return (
      normalizedMirror.includes(normalizedNotebook) ||
      normalizedNotebook.includes(normalizedMirror)
    );
  });
  return partial?.claim_id ?? null;
}

function resolveStatsCheckTargetId(
  check: ObsidianMirror["stats_checks"][number],
  notebook: NotebookArtifact,
  highlights: EvidenceHighlight[],
  activeClaimId: string | null,
): string | null {
  if (check.claim_id && notebook.claims.some((claim) => claim.claim_id === check.claim_id)) {
    return check.claim_id;
  }
  if (notebook.claims.some((claim) => claim.claim_id === check.check_id)) {
    return check.check_id;
  }

  const signals = [check.hypothesis, check.notes, check.test_type]
    .map((item) => (item ?? "").trim())
    .filter((item) => item.length >= 6);

  if (signals.length > 0) {
    const ranked = notebook.claims
      .map((claim) => ({
        claimId: claim.claim_id,
        score: scoreClaimTextAgainstSignals(claim.text, signals),
      }))
      .sort((a, b) => b.score - a.score);
    if (ranked[0]?.score > 0) {
      return ranked[0].claimId;
    }
  }

  if (check.evidence_page !== null && check.evidence_page !== undefined) {
    const byPage = highlights.filter((item) => item.page === check.evidence_page);
    if (byPage.length === 1) {
      return byPage[0].claim_id;
    }
    if (byPage.length > 1) {
      if (activeClaimId && byPage.some((item) => item.claim_id === activeClaimId)) {
        return activeClaimId;
      }
      const scored = byPage
        .map((item) => {
          const claim = notebook.claims.find((entry) => entry.claim_id === item.claim_id);
          return {
            claimId: item.claim_id,
            score: scoreClaimTextAgainstSignals(claim?.text ?? "", signals),
          };
        })
        .sort((a, b) => b.score - a.score);
      return scored[0]?.claimId ?? byPage[0].claim_id;
    }
  }

  if (signals.length > 0) {
    const partial = notebook.claims.find((claim) => {
      const normalizedClaim = normalizeClaimTextForMatch(claim.text);
      return signals.some((signal) => {
        const normalizedSignal = normalizeClaimTextForMatch(signal);
        return normalizedClaim.includes(normalizedSignal) || normalizedSignal.includes(normalizedClaim);
      });
    });
    if (partial) {
      return partial.claim_id;
    }
  }
  return null;
}

export function ArtifactPanel({
  paperId,
  runId,
  notebook,
  highlights,
  inferenceSummary,
  rawArtifact,
  obsidianMirror,
  opsSummary,
  contentReviewSummary,
  paperSynthesis,
  syncEnabled,
  syncing,
  onSyncObsidian,
  activeClaimId,
  onSelectClaim,
  density,
}: ArtifactPanelProps) {
  const [paperSynthesisManifestState, setPaperSynthesisManifestState] = useState<PaperSynthesisManifestState>({
    synthesisId: null,
    data: null,
    loading: false,
    error: null,
  });
  const logEvidenceReviewAction = (actionType: string, payload: Record<string, unknown>) => {
    logClientUserAction({
      paper_id: paperId ?? null,
      action_type: actionType,
      source: "ui",
      payload: {
        run_id: runId ?? null,
        ...payload,
      },
    });
  };
  const currentPaperSynthesisId = paperSynthesis?.synthesis_id ?? null;
  const paperSynthesisManifest =
    paperSynthesisManifestState.synthesisId === currentPaperSynthesisId ? paperSynthesisManifestState.data : null;
  const paperSynthesisManifestLoading =
    paperSynthesisManifestState.synthesisId === currentPaperSynthesisId ? paperSynthesisManifestState.loading : false;
  const paperSynthesisManifestError =
    paperSynthesisManifestState.synthesisId === currentPaperSynthesisId ? paperSynthesisManifestState.error : null;

  async function loadPaperSynthesisManifestOnce() {
    if (!paperSynthesis) {
      return;
    }
    const synthesisId = paperSynthesis.synthesis_id;
    const hasCachedManifest =
      paperSynthesisManifestState.synthesisId === synthesisId &&
      (paperSynthesisManifestState.loading || Boolean(paperSynthesisManifestState.data));
    if (hasCachedManifest) {
      return;
    }

    setPaperSynthesisManifestState({
      synthesisId,
      data: null,
      loading: true,
      error: null,
    });
    const manifestResult = await getPaperSynthesisManifest(synthesisId);
    setPaperSynthesisManifestState({
      synthesisId,
      data: manifestResult.data,
      loading: false,
      error: manifestResult.data ? null : manifestResult.reason ?? "paper synthesis manifest unavailable",
    });
  }

  const verdict = verdictStyle(notebook.verdict.level);
  const highlightMap = buildBestHighlightMap(highlights);
  const compact = density === "compact";
  const claimLinkStates = notebook.claims.map((claim) => ({
    claimId: claim.claim_id,
    state: getClaimLinkState(claim, highlightMap.get(claim.claim_id)),
  }));
  const claimLinkStateMap = new Map(claimLinkStates.map((item) => [item.claimId, item.state]));
  const mappedCount = claimLinkStates.filter((item) => item.state.health === "mapped").length;
  const fallbackCount = claimLinkStates.filter((item) => item.state.health === "search_fallback").length;
  const missingCount = claimLinkStates.filter((item) => item.state.health === "missing").length;
  const activeClaimIndex = notebook.claims.findIndex((claim) => claim.claim_id === activeClaimId);
  const activeClaimState = activeClaimId ? claimLinkStateMap.get(activeClaimId) ?? null : null;
  const activeClaimSummary =
    activeClaimIndex >= 0 && activeClaimState
      ? `Active ${circledNumber(activeClaimIndex)} · ${activeClaimState.health === "mapped" ? `p.${activeClaimState.page}` : activeClaimState.health === "search_fallback" ? `Text fallback p.${activeClaimState.page}` : "Missing evidence"}`
      : "Select claim to inspect evidence link";

  return (
    <section className="surface-card flex h-full min-h-0 flex-col p-3">
      <header className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Synthesis / Artifact</p>
          <p className="text-sm text-[var(--pp-text-secondary)]">Notebook-style analysis cells</p>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-3 overflow-auto pr-1">
        {compact ? (
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Compact Summary</div>
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-md border border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] px-2 py-1.5">
                <p className="text-[10px] uppercase tracking-wide text-[var(--pp-status-completed-text)]">Mapped</p>
                <p className="mt-1 text-sm font-semibold text-[var(--pp-status-completed-text)]">{mappedCount}</p>
              </div>
              <div className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2 py-1.5">
                <p className="text-[10px] uppercase tracking-wide text-[var(--pp-warning-text)]">Fallback</p>
                <p className="mt-1 text-sm font-semibold text-[var(--pp-warning-text)]">{fallbackCount}</p>
              </div>
              <div className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] px-2 py-1.5">
                <p className="text-[10px] uppercase tracking-wide text-[var(--pp-status-failed-text)]">Missing</p>
                <p className="mt-1 text-sm font-semibold text-[var(--pp-status-failed-text)]">{missingCount}</p>
              </div>
            </div>
            <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{activeClaimSummary}</p>
          </article>
        ) : null}

        <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
            <NotebookPen className="h-3.5 w-3.5" />
            Cell 1 Claim
          </div>
          <ul className="space-y-2">
            {notebook.claims.length > 0 ? (
              notebook.claims.map((claim, index) => {
                const active = claim.claim_id === activeClaimId;
                const linkState = claimLinkStateMap.get(claim.claim_id) ?? getClaimLinkState(claim, highlightMap.get(claim.claim_id));
                const linkLabel =
                  linkState.health === "mapped"
                    ? `Mapped · p.${linkState.page}`
                    : linkState.health === "search_fallback"
                      ? `Text fallback · p.${linkState.page}`
                      : "Missing evidence";
                const linkClassName =
                  linkState.health === "mapped"
                    ? "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                    : linkState.health === "search_fallback"
                      ? "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
                      : "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
                return (
                  <li key={claim.claim_id}>
                    <button
                      type="button"
                      onClick={() => {
                        logEvidenceReviewAction("workbench_select_claim", {
                          origin: "claim_list",
                          claim_id: claim.claim_id,
                          link_health: linkState.health,
                          page: linkState.page ?? null,
                          text_missing: linkState.textMissing === true,
                        });
                        onSelectClaim(claim.claim_id);
                      }}
                      className={[
                        "w-full rounded-md border px-3 py-2 text-left text-sm",
                        active
                          ? "border-[var(--pp-accent)] bg-[var(--pp-surface-selected)]"
                          : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)]",
                      ].join(" ")}
                    >
                      <p className={compact ? "line-clamp-2" : ""}>
                        <span className="mr-2 text-[var(--pp-accent-text)]">{circledNumber(index)}</span>
                        {stripLeadingClaimMarker(claim.text)}
                      </p>
                      <span className="mt-2 block">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] ${linkClassName}`}>
                          {linkLabel}
                        </span>
                        {linkState.textMissing ? (
                          <span className="ml-1 inline-flex rounded-full border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] px-2 py-0.5 text-[10px] text-[var(--pp-status-failed-text)]">
                            Text missing
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                );
              })
            ) : (
              <li className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2 text-sm text-[var(--pp-text-dim)]">
                No claims available yet.
              </li>
            )}
          </ul>
        </article>

        {compact ? null : (
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <FlaskConical className="h-3.5 w-3.5" />
              Cell 2 Agent Plan
            </div>
            <ol className="space-y-1 text-sm text-[var(--pp-text-secondary)]">
              {notebook.agent_plan.map((step, index) => (
                <li key={`${step}-${index}`}>{`${index + 1}. ${step}`}</li>
              ))}
            </ol>
          </article>
        )}

        {compact ? null : (
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <FlaskConical className="h-3.5 w-3.5" />
              Cell 3 Sandbox Execution
            </div>
            <pre className="pp-hatch rounded-md border border-[var(--pp-border)] p-3 text-xs leading-5 text-[var(--pp-text-secondary)]">
              {notebook.sandbox_code}
            </pre>
          </article>
        )}

        <article className={[
          "rounded-md border p-3",
          verdict.className,
        ].join(" ")}>
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
            {verdict.icon}
            Cell 4 Verdict
          </div>
          <p className="text-sm font-semibold">{notebook.verdict.label}</p>
          <p className="mt-1 text-sm">{notebook.verdict.detail}</p>
        </article>

        {contentReviewSummary ? (
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3" data-testid="workbench-content-review-summary">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Claim review</div>
            <ContentReviewSummary
              summary={contentReviewSummary}
              badgeTestId="workbench-content-review-badge"
              hintTestId="workbench-content-review-hint"
              detailTestId="workbench-content-review-detail"
            />
          </article>
        ) : null}

        {opsSummary ? (
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3" data-testid="workbench-ops-summary">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Saved checks</div>
            <OperationalStateSummary
              summary={opsSummary}
              badgeTestId="workbench-ops-badge"
              reasonTestId="workbench-ops-reason"
            />
          </article>
        ) : null}

        {inferenceSummary ? (
          <article
            className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
            data-testid="workbench-inference-summary"
          >
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <FlaskConical className="h-3.5 w-3.5" />
              Inference boundary
            </div>
            <p className="text-sm text-[var(--pp-text-secondary)]">
              Saved runtime summary for backend placement, payload class, and whether redacted excerpts were used.
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge
                className={getInferenceBackendBadgeClassName(inferenceSummary.selected_backend)}
                data-testid="workbench-inference-backend"
              >
                {`backend: ${formatInferenceToken(inferenceSummary.selected_backend)}`}
              </Badge>
              <Badge
                className={getInferencePayloadBadgeClassName(inferenceSummary.payload_class)}
                data-testid="workbench-inference-payload"
              >
                {`payload: ${formatInferenceToken(inferenceSummary.payload_class)}`}
              </Badge>
              <Badge
                className={getInferenceRedactionBadgeClassName(inferenceSummary.redaction_applied)}
                data-testid="workbench-inference-redaction"
              >
                {inferenceSummary.redaction_applied ? "redaction applied" : "no redaction"}
              </Badge>
            </div>
            <div className="mt-3 space-y-2">
              {Object.entries(inferenceSummary.lanes).map(([laneName, lane]) => (
                <article
                  key={laneName}
                  className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2"
                  data-testid={buildInferenceLaneTestId(laneName)}
                >
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge className="border-[var(--pp-border)] bg-[var(--pp-surface)] text-[var(--pp-text-primary)]">
                      {laneName.replace(/_/g, " ")}
                    </Badge>
                    <Badge className={getInferenceBackendBadgeClassName(lane.selected_backend)}>
                      {formatInferenceToken(lane.selected_backend)}
                    </Badge>
                    <Badge className={getInferencePayloadBadgeClassName(lane.payload_class)}>
                      {formatInferenceToken(lane.payload_class)}
                    </Badge>
                    <Badge className={getInferenceRedactionBadgeClassName(lane.redaction_applied)}>
                      {lane.redaction_applied ? "redacted" : "full local"}
                    </Badge>
                  </div>
                  {lane.provider_name || lane.provider_model ? (
                    <p className="mt-2 text-[11px] text-[var(--pp-text-dim)]">
                      {`provider ${lane.provider_name ?? "unknown"}${lane.provider_model ? ` · ${lane.provider_model}` : ""}`}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          </article>
        ) : null}

        <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3" data-testid="workbench-paper-synthesis">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
            <FileText className="h-3.5 w-3.5" />
            Compiled knowledge
          </div>
          {paperSynthesis ? (
            <div className="space-y-3">
              <p className="text-sm text-[var(--pp-text-secondary)]">
                Latest paper-scoped compiled markdown stays downstream of canonical state and reusable evidence links.
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Badge className="border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]">
                  Non-canonical
                </Badge>
                <Badge className={getPaperSynthesisReadinessBadgeClassName(paperSynthesis.readiness)}>
                  {paperSynthesis.readiness.replace(/_/g, " ")}
                </Badge>
                <Badge className={getPaperSynthesisFreshnessBadgeClassName(paperSynthesis.freshness)}>
                  {paperSynthesis.freshness}
                </Badge>
                <Badge className="border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]">
                  {`${paperSynthesis.template_kind} template`}
                </Badge>
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
                  <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Source refs</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{paperSynthesis.source_ref_count}</p>
                </article>
                <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
                  <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Evidence refs</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{paperSynthesis.evidence_ref_count}</p>
                </article>
                <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
                  <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Warnings</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{paperSynthesis.warning_count}</p>
                </article>
              </div>
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
                <p className="text-sm font-semibold text-[var(--pp-text-primary)]">{paperSynthesis.title}</p>
                <p
                  data-testid="workbench-paper-synthesis-updated-at"
                  className="mt-1 text-[11px] text-[var(--pp-text-dim)]"
                >
                  {`Updated ${formatPaperSynthesisTimestamp(paperSynthesis.updated_at)}. Open the raw markdown when you need the derived note itself.`}
                </p>
              </div>
              <div
                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2"
                data-testid="workbench-paper-synthesis-lineage"
              >
                <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Trust reopen path</p>
                <p
                  className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]"
                  data-testid="workbench-paper-synthesis-answer-route"
                >
                  {formatPaperSynthesisAnswerRoute(paperSynthesis.lineage_summary.answer_route)}
                </p>
                <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">
                  Reopen trust through the minimum upstream lineage before relying on compiled prose.
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {paperSynthesis.lineage_summary.present_required_source_kinds.map((kind) => (
                    <Badge
                      key={kind}
                      className="border-[var(--pp-border)] bg-[var(--pp-surface)] text-[var(--pp-text-secondary)]"
                    >
                      {formatPaperSynthesisLineageKind(kind)}
                    </Badge>
                  ))}
                </div>
                {paperSynthesis.lineage_summary.review_artifact_kinds.length ? (
                  <p className="mt-2 text-[11px] text-[var(--pp-text-dim)]">
                    {`Additive review sidecars: ${paperSynthesis.lineage_summary.review_artifact_kinds
                      .map((kind) => formatPaperSynthesisReviewArtifactKind(kind))
                      .join(", ")}.`}
                  </p>
                ) : null}
              </div>
              <details
                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2"
                data-testid="workbench-paper-synthesis-source-refs"
                onToggle={(event) => {
                  if (!event.currentTarget.open) {
                    return;
                  }
                  logEvidenceReviewAction("workbench_open_paper_synthesis_source_refs", {
                    origin: "compiled_knowledge_card",
                    synthesis_id: paperSynthesis.synthesis_id,
                    paper_slug: paperSynthesis.paper_slug,
                    answer_route: paperSynthesis.lineage_summary.answer_route,
                  });
                  void loadPaperSynthesisManifestOnce();
                }}
              >
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                  Inspect source refs
                </summary>
                {paperSynthesisManifestLoading ? (
                  <p className="mt-2 text-xs text-[var(--pp-text-dim)]">Loading saved source refs...</p>
                ) : null}
                {paperSynthesisManifestError ? (
                  <p className="mt-2 text-xs text-[var(--pp-warning-text)]">{paperSynthesisManifestError}</p>
                ) : null}
                {paperSynthesisManifest ? (
                  <ul className="mt-2 space-y-2">
                    {paperSynthesisManifest.source_refs.map((ref, index) => (
                      <li
                        key={`${ref.kind}-${ref.path ?? index}`}
                        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2"
                        data-testid="workbench-paper-synthesis-source-ref"
                      >
                        <div className="flex flex-wrap gap-1.5">
                          <Badge className="border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]">
                            {formatPaperSynthesisSourceKind(ref.kind)}
                          </Badge>
                          {ref.run_id ? (
                            <Badge className="border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]">
                              {ref.run_id}
                            </Badge>
                          ) : null}
                        </div>
                        {ref.path ? (
                          <p className="mt-2 break-all font-mono text-[11px] text-[var(--pp-text-secondary)]">{ref.path}</p>
                        ) : null}
                        {ref.note ? (
                          <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">{ref.note}</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </details>
              <a
                href={getPaperSynthesisMarkdownUrl(paperSynthesis.synthesis_id)}
                target="_blank"
                rel="noreferrer"
                onClick={() =>
                  logEvidenceReviewAction("workbench_open_paper_synthesis_markdown", {
                    origin: "compiled_knowledge_card",
                    synthesis_id: paperSynthesis.synthesis_id,
                    paper_slug: paperSynthesis.paper_slug,
                    readiness: paperSynthesis.readiness,
                    freshness: paperSynthesis.freshness,
                  })}
                className="inline-flex rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1 text-xs text-[var(--pp-accent-text)]"
              >
                Open markdown
              </a>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-[var(--pp-text-secondary)]">
                This optional lane holds compiled markdown only. It never replaces canonical state or raw-source review.
              </p>
              <p className="text-xs text-[var(--pp-text-dim)]">
                No saved paper synthesis is available for this paper yet. This workbench surface stays read-only.
              </p>
            </div>
          )}
        </article>

        <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Obsidian Mirror</div>
            <button
              type="button"
              onClick={onSyncObsidian}
              disabled={!syncEnabled || syncing}
              className={[
                "rounded-md border px-2.5 py-1 text-xs",
                syncEnabled && !syncing
                  ? "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]"
                  : "cursor-not-allowed border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
              ].join(" ")}
            >
              {syncing ? "Syncing..." : "Sync to Obsidian"}
            </button>
          </div>

          {obsidianMirror ? (
            <div className="space-y-2">
              <p className="text-xs text-[var(--pp-text-dim)]">Obsidian sync payload preview (same payload sent by sync API).</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
                  <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Claims</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{obsidianMirror.claims.length}</p>
                </article>
                <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
                  <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Stats Checks</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{obsidianMirror.stats_checks.length}</p>
                </article>
              </div>

              {obsidianMirror.claims.length > 0 ? (
                <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2" open={!compact}>
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Claims Snapshot
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {obsidianMirror.claims.slice(0, 8).map((claim) => {
                      const targetClaimId = resolveMirrorClaimTargetId(claim.claim_id, claim.statement, notebook);
                      const canJump = Boolean(targetClaimId);
                      const groundingBadge = getGroundingBadge(claim.evidence_grounded, claim.evidence_resolution);
                      return (
                        <li key={claim.claim_id}>
                          <button
                            type="button"
                            disabled={!canJump}
                            onClick={() => {
                              if (targetClaimId) {
                                logEvidenceReviewAction("workbench_jump_mirror_claim", {
                                  origin: "mirror_claim",
                                  mirror_claim_id: claim.claim_id,
                                  target_claim_id: targetClaimId,
                                  evidence_page: claim.evidence_page ?? null,
                                  evidence_chunk_id: claim.evidence_chunk_id ?? null,
                                  evidence_grounded: claim.evidence_grounded ?? null,
                                  evidence_resolution: claim.evidence_resolution ?? null,
                                });
                                onSelectClaim(targetClaimId);
                              }
                            }}
                            className={[
                              "w-full rounded-md border px-2 py-1.5 text-left",
                              canJump
                                ? "border-[var(--pp-border)] bg-[var(--pp-surface-raised)]"
                                : "cursor-not-allowed border-[var(--pp-border)] bg-[var(--pp-surface-muted)] opacity-70",
                            ].join(" ")}
                          >
                            <p className="text-xs text-[var(--pp-text-primary)]">{claim.statement}</p>
                            <p className="mt-1 text-[10px] text-[var(--pp-text-dim)]">
                              {`${claim.claim_type} · confidence ${claim.confidence.toFixed(2)}${claim.evidence_page !== null && claim.evidence_page !== undefined ? ` · p.${claim.evidence_page}` : ""}${canJump ? " · Jump to PDF" : " · Jump unavailable"}`}
                            </p>
                            {groundingBadge ? (
                              <div className="mt-1 flex flex-wrap gap-1.5">
                                <Badge
                                  className={groundingBadge.className}
                                  data-testid={`workbench-mirror-claim-grounding-${claim.claim_id}`}
                                >
                                  {groundingBadge.label}
                                </Badge>
                              </div>
                            ) : null}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </details>
              ) : null}

              {obsidianMirror.stats_checks.length > 0 ? (
                <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2" open={!compact}>
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Saved checks
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {obsidianMirror.stats_checks.slice(0, 8).map((check) => {
                      const targetClaimId = resolveStatsCheckTargetId(check, notebook, highlights, activeClaimId);
                      const canJump = Boolean(targetClaimId);
                      const isActive = Boolean(targetClaimId && targetClaimId === activeClaimId);
                      const groundingBadge = getGroundingBadge(check.evidence_grounded, check.evidence_resolution);
                      return (
                        <li key={check.check_id}>
                          <button
                            type="button"
                            disabled={!canJump}
                            onClick={() => {
                              if (targetClaimId) {
                                logEvidenceReviewAction("workbench_jump_stats_check", {
                                  origin: "stats_snapshot",
                                  check_id: check.check_id,
                                  target_claim_id: targetClaimId,
                                  evidence_page: check.evidence_page ?? null,
                                  evidence_chunk_id: check.evidence_chunk_id ?? null,
                                  evidence_grounded: check.evidence_grounded ?? null,
                                  evidence_resolution: check.evidence_resolution ?? null,
                                });
                                onSelectClaim(targetClaimId);
                              }
                            }}
                            className={[
                              "w-full rounded-md border px-2 py-1.5 text-left",
                              canJump
                                ? isActive
                                  ? "border-[var(--pp-accent-border)] bg-[var(--pp-surface-selected)]"
                                  : "border-[var(--pp-border)] bg-[var(--pp-surface-raised)]"
                                : "cursor-not-allowed border-[var(--pp-border)] bg-[var(--pp-surface-muted)] opacity-70",
                            ].join(" ")}
                          >
                            <p className="text-xs text-[var(--pp-text-primary)]">{check.test_type}</p>
                            <p className="mt-1 text-[10px] text-[var(--pp-text-dim)]">
                              {`${check.verdict}${check.decision_error ? " · decision error" : ""}${check.evidence_page !== null && check.evidence_page !== undefined ? ` · p.${check.evidence_page}` : ""}${canJump ? " · Jump to PDF" : " · Jump unavailable"}${check.notes ? ` · ${check.notes}` : ""}`}
                            </p>
                            {groundingBadge ? (
                              <div className="mt-1 flex flex-wrap gap-1.5">
                                <Badge
                                  className={groundingBadge.className}
                                  data-testid={`workbench-mirror-stat-grounding-${check.check_id}`}
                                >
                                  {groundingBadge.label}
                                </Badge>
                              </div>
                            ) : null}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </details>
              ) : null}

              <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2" open={!compact}>
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                  Generated Markdown (sync preview)
                </summary>
                <pre
                  tabIndex={-1}
                  className="mt-2 max-h-48 overflow-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2 text-[11px] leading-5 text-[var(--pp-text-secondary)]"
                >
                  {obsidianMirror.generated_markdown}
                </pre>
              </details>
            </div>
          ) : (
            <p className="text-sm text-[var(--pp-text-dim)]">
              Run artifact is not ready yet. Start a Deep Read run or refresh data.
            </p>
          )}
        </article>

        {compact ? null : (
          <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              Raw Artifact JSON
            </summary>
            <pre
              tabIndex={-1}
              className="mt-2 overflow-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 text-xs text-[var(--pp-text-secondary)]"
            >
              {JSON.stringify(rawArtifact, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </section>
  );
}
