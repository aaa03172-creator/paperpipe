import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, FlaskConical, NotebookPen } from "lucide-react";
import { EvidenceHighlight, NotebookArtifact, ObsidianMirror } from "../lib/types";
import { buildBestHighlightMap, getClaimLinkState } from "../lib/claimGuard";
import { circledNumber } from "../lib/ui";

interface ArtifactPanelProps {
  notebook: NotebookArtifact;
  highlights: EvidenceHighlight[];
  rawArtifact: unknown;
  obsidianMirror: ObsidianMirror | null;
  syncEnabled: boolean;
  syncing: boolean;
  onSyncObsidian: () => void;
  activeClaimId: string | null;
  onSelectClaim: (claimId: string) => void;
  density: "detail" | "compact";
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
  notebook,
  highlights,
  rawArtifact,
  obsidianMirror,
  syncEnabled,
  syncing,
  onSyncObsidian,
  activeClaimId,
  onSelectClaim,
  density,
}: ArtifactPanelProps) {
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
                      onClick={() => onSelectClaim(claim.claim_id)}
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
                      return (
                        <li key={claim.claim_id}>
                          <button
                            type="button"
                            disabled={!canJump}
                            onClick={() => {
                              if (targetClaimId) {
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
                    Stats Snapshot
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {obsidianMirror.stats_checks.slice(0, 8).map((check) => {
                      const targetClaimId = resolveStatsCheckTargetId(check, notebook, highlights, activeClaimId);
                      const canJump = Boolean(targetClaimId);
                      const isActive = Boolean(targetClaimId && targetClaimId === activeClaimId);
                      return (
                        <li key={check.check_id}>
                          <button
                            type="button"
                            disabled={!canJump}
                            onClick={() => {
                              if (targetClaimId) {
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
                <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2 text-[11px] leading-5 text-[var(--pp-text-secondary)]">
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
            <pre className="mt-2 overflow-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 text-xs text-[var(--pp-text-secondary)]">
              {JSON.stringify(rawArtifact, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </section>
  );
}
