import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, FlaskConical, NotebookPen } from "lucide-react";
import { NotebookArtifact } from "../lib/types";
import { circledNumber } from "../lib/ui";

interface ArtifactPanelProps {
  notebook: NotebookArtifact;
  rawArtifact: unknown;
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

export function ArtifactPanel({ notebook, rawArtifact, activeClaimId, onSelectClaim }: ArtifactPanelProps) {
  const verdict = verdictStyle(notebook.verdict.level);

  return (
    <section className="surface-card flex min-h-0 flex-col p-3">
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
                      {claim.text}
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
