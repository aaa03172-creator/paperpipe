import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, FlaskConical, NotebookPen } from "lucide-react";
import { EvidenceHighlight, NotebookArtifact, ObsidianMirror } from "../lib/types";
import { getClaimLinkState } from "../lib/claimGuard";
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
}: ArtifactPanelProps) {
  const verdict = verdictStyle(notebook.verdict.level);
  const highlightMap = new Map(highlights.map((item) => [item.claim_id, item]));

  return (
    <section className="surface-card flex h-full min-h-0 flex-col p-3">
      <header className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Synthesis / Artifact</p>
          <p className="text-sm text-[var(--pp-text-secondary)]">Notebook-style analysis cells</p>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-3 overflow-auto pr-1">
        <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
            <NotebookPen className="h-3.5 w-3.5" />
            Cell 1 Claim
          </div>
          <ul className="space-y-2">
            {notebook.claims.length > 0 ? (
              notebook.claims.map((claim, index) => {
                const active = claim.claim_id === activeClaimId;
                const linkState = getClaimLinkState(claim, highlightMap.get(claim.claim_id));
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
                      <span className="mr-2 text-[var(--pp-accent-text)]">{circledNumber(index)}</span>
                      {stripLeadingClaimMarker(claim.text)}
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

        <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
            <FlaskConical className="h-3.5 w-3.5" />
            Cell 3 Sandbox Execution
          </div>
          <pre className="pp-hatch rounded-md border border-[var(--pp-border)] p-3 text-xs leading-5 text-[var(--pp-text-secondary)]">
            {notebook.sandbox_code}
          </pre>
        </article>

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
                <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2" open>
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Claims Snapshot
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {obsidianMirror.claims.slice(0, 8).map((claim) => (
                      <li key={claim.claim_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5">
                        <p className="text-xs text-[var(--pp-text-primary)]">{claim.statement}</p>
                        <p className="mt-1 text-[10px] text-[var(--pp-text-dim)]">
                          {`${claim.claim_type} · confidence ${claim.confidence.toFixed(2)}${claim.evidence_page !== null && claim.evidence_page !== undefined ? ` · p.${claim.evidence_page}` : ""}`}
                        </p>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}

              {obsidianMirror.stats_checks.length > 0 ? (
                <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2" open>
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Stats Snapshot
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {obsidianMirror.stats_checks.slice(0, 8).map((check) => (
                      <li key={check.check_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5">
                        <p className="text-xs text-[var(--pp-text-primary)]">{check.test_type}</p>
                        <p className="mt-1 text-[10px] text-[var(--pp-text-dim)]">
                          {`${check.verdict}${check.decision_error ? " · decision error" : ""}${check.notes ? ` · ${check.notes}` : ""}`}
                        </p>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}

              <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-2">
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

        <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
            Raw Artifact JSON
          </summary>
          <pre className="mt-2 overflow-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 text-xs text-[var(--pp-text-secondary)]">
            {JSON.stringify(rawArtifact, null, 2)}
          </pre>
        </details>
      </div>
    </section>
  );
}
