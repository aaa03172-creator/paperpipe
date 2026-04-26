import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ArrowRight, RefreshCw, Stethoscope } from "lucide-react";
import { getApiErrorMessage, getRuntimeReadiness } from "../lib/api";
import { RuntimeReadinessCheck, RuntimeReadinessResponse } from "../lib/types";
import { StatusBadge } from "../components/StatusBadge";
import { getStatusToneClassName, type StatusTone } from "../lib/statusSystem";

function overallStatusLabel(status: RuntimeReadinessResponse["status"]): string {
  if (status === "ok") {
    return "Ready";
  }
  if (status === "degraded") {
    return "Needs attention";
  }
  return "Blocked";
}

function overallStatusTone(status: RuntimeReadinessResponse["status"]): StatusTone {
  if (status === "ok") {
    return "success";
  }
  if (status === "degraded") {
    return "warning";
  }
  return "danger";
}

function checkStatusTone(status: RuntimeReadinessCheck["status"]): StatusTone {
  if (status === "ok") {
    return "success";
  }
  if (status === "warn") {
    return "warning";
  }
  return "danger";
}

function formatCheckName(name: string): string {
  return name
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const EMPTY_READINESS: RuntimeReadinessResponse = {
  status: "error",
  checks: [],
};

interface RuntimeSuggestedFix {
  key: string;
  title: string;
  body: string;
  href?: string;
  hrefLabel?: string;
  code?: string;
}

export function RuntimeReadinessPage() {
  const [readiness, setReadiness] = useState<RuntimeReadinessResponse>(EMPTY_READINESS);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [fallbackReason, setFallbackReason] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Runtime Readiness | Lattice";
  }, []);

  async function loadReadiness() {
    setLoading(true);
    setLoadError(null);
    setFallbackReason(null);
    try {
      const result = await getRuntimeReadiness();
      setReadiness(result.data);
      if (result.isMock) {
        setFallbackReason(result.reason ?? "Runtime readiness is showing a local diagnostic fallback.");
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error));
      setReadiness(EMPTY_READINESS);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadReadiness();
  }, []);

  const summary = useMemo(() => {
    return readiness.checks.reduce(
      (acc, check) => {
        acc[check.status] += 1;
        return acc;
      },
      { ok: 0, warn: 0, error: 0 },
    );
  }, [readiness.checks]);

  const statusTone = overallStatusTone(readiness.status);
  const hasFailingChecks = summary.warn > 0 || summary.error > 0;
  const hasPickupWarnings = readiness.checks.some(
    (check) =>
      (check.name === "watch_folder" || check.name === "downloads_watch_dir" || check.name === "pdf_storage_dir") &&
      check.status !== "ok",
  );
  const nextStepSummary =
    loadError || fallbackReason
      ? "Restore the live backend signal first, then return to Paper Notes to import or reopen a paper and continue from the saved note."
      : hasPickupWarnings
        ? "Automatic pickup is not fully ready here. Use Import PDF from Paper Notes to open the saved note right away, then keep reading or move into review while you finish local setup."
        : hasFailingChecks
          ? "Clear the warning or error checks first, then return to Paper Notes so the paper-first loop stays on live runtime data."
          : "This machine looks ready for the current paper-first loop. Start from Paper Notes, then continue into Research DNA or Meeting Packs.";
  const showMeetingPackCta = readiness.status === "ok" && !loadError && !fallbackReason;
  const paperNotesTarget = hasPickupWarnings ? "/papers#import-pdf" : "/papers";
  const suggestedFixes = useMemo<RuntimeSuggestedFix[]>(() => {
    const checks = readiness.checks;
    const hasCheckIssue = (names: string[]) =>
      checks.some((check) => names.includes(check.name) && check.status !== "ok");

    const fixes: RuntimeSuggestedFix[] = [];

    if (fallbackReason || hasCheckIssue(["runtime_readiness"])) {
      fixes.push({
        key: "live-backend",
        title: "Restore the live backend signal",
        body: "Disable forced mock mode or start the live backend before treating this page as the current runtime truth.",
      });
    }

    if (hasPickupWarnings) {
      fixes.push({
        key: "pickup",
        title: "Use manual import while pickup is unavailable",
        body: "Automatic pickup is not ready on this machine. Open Paper Notes and use Import PDF to open the saved note right away, then keep reading or move into review while local setup catches up.",
        href: "/papers#import-pdf",
        hrefLabel: "Open Import PDF",
      });
    }

    if (hasCheckIssue(["config_file", "backend_entrypoint", "backend_runtime"])) {
      fixes.push({
        key: "runtime-setup",
        title: "Repair runtime setup before retrying",
        body: "If config loading or backend imports are failing, reinstall runtime dependencies or rebuild the bounded verification environment before sharing or rerunning this workspace.",
        code: "python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap",
      });
    }

    if (hasCheckIssue(["config_root", "runtime_db", "storage_root", "logs_root", "cache_root", "runtime_storage"])) {
      fixes.push({
        key: "runtime-storage",
        title: "Fix writable runtime paths",
        body: "Deep-read runs, note writes, and downstream artifacts need writable storage, logs, and database paths on this machine.",
      });
    }

    if (hasCheckIssue(["ui_bundle"])) {
      fixes.push({
        key: "ui-entry",
        title: "Restore the frontend entry before sharing",
        body: "If the UI bundle is missing or degraded, rebuild the frontend or restore the expected app entry before treating this runtime as share-ready.",
      });
    }

    if (hasCheckIssue(["structured_state_hygiene", "meeting_pack_storage_hygiene", "external_roots"])) {
      fixes.push({
        key: "workspace-hygiene",
        title: "Clean workspace-side residue before trusting saved outputs",
        body: "Hidden fixture sidecars, noisy saved packs, or missing external roots can make note and artifact listings less trustworthy than they look.",
      });
    }

    return fixes;
  }, [fallbackReason, hasPickupWarnings, readiness.checks]);

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <Stethoscope className="h-3.5 w-3.5" />
              Runtime readiness
            </p>
            <h1 className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">
              Check whether this workspace is ready for real runs
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Use this page when the app boots but a feature still feels unavailable, before a real paper-first run, or before sharing the runtime with someone else.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void loadReadiness()}
              disabled={loading}
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Reload checks
            </button>
            <Link
              to="/"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Back to workspace
            </Link>
          </div>
        </div>
      </header>

      {fallbackReason ? (
        <section
          data-testid="runtime-readiness-fallback"
          className="surface-card mb-4 border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-4 text-sm text-[var(--pp-warning-text)]"
        >
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">Showing diagnostic fallback</p>
              <p className="mt-1">{fallbackReason}</p>
            </div>
          </div>
        </section>
      ) : null}

      {loadError ? (
        <section className="surface-card mb-4 border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-4 text-sm text-[var(--pp-status-failed-text)]">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">Runtime checks failed to load</p>
              <p className="mt-1">{loadError}</p>
            </div>
          </div>
        </section>
      ) : null}

      <section className="mb-4 grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <div className="surface-card p-4">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge
              label={overallStatusLabel(readiness.status)}
              tone={statusTone}
              iconTone={statusTone === "danger" ? "danger" : statusTone === "warning" ? "warning" : "success"}
              testId="runtime-readiness-overall"
            />
            <p className="text-sm text-[var(--pp-text-secondary)]">
              {hasFailingChecks
                ? "Fix the items marked warning or error first, then reload the checks from this page."
                : "The core runtime paths and backend entrypoint look ready for real runs."}
            </p>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
              <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">OK</p>
              <p className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{summary.ok}</p>
            </div>
            <div className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3">
              <p className="text-[11px] uppercase tracking-wide text-[var(--pp-warning-text)]">Warnings</p>
              <p className="mt-1 text-xl font-semibold text-[var(--pp-warning-text)]">{summary.warn}</p>
            </div>
            <div className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3">
              <p className="text-[11px] uppercase tracking-wide text-[var(--pp-status-failed-text)]">Errors</p>
              <p className="mt-1 text-xl font-semibold text-[var(--pp-status-failed-text)]">{summary.error}</p>
            </div>
          </div>
        </div>

        <aside className="surface-card p-4">
          <div data-testid="runtime-readiness-product-loop">
            <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">Current product loop</h2>
            <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">
              This page supports the current paper-first baseline instead of replacing it.
            </p>
            <ul className="mt-3 space-y-2 text-sm text-[var(--pp-text-secondary)]">
              <li>
                <span className="font-medium text-[var(--pp-text-primary)]">Paper Notes.</span> Import or reopen a paper, land in the saved note, then inspect saved structured state.
              </li>
              <li>
                <span className="font-medium text-[var(--pp-text-primary)]">Research DNA.</span> Keep reproducible search design in the current API/CLI-first lane.
              </li>
              <li>
                <span className="font-medium text-[var(--pp-text-primary)]">Meeting Packs.</span> Reopen the strongest current downstream artifact after paper state is healthy.
              </li>
            </ul>
          </div>

          <div
            data-testid="runtime-readiness-next-step"
            className="mt-4 border-t border-[var(--pp-border)] pt-4"
          >
            <h3 className="text-sm font-semibold text-[var(--pp-text-primary)]">Best next step on this machine</h3>
            <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">{nextStepSummary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                to={paperNotesTarget}
                data-testid="runtime-readiness-open-papers"
                className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)]"
              >
                Open Paper Notes
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Link>
              {showMeetingPackCta ? (
                <Link
                  to="/meeting-packs"
                  data-testid="runtime-readiness-open-meeting-packs"
                  className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)]"
                >
                  Open Meeting Packs
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </Link>
              ) : null}
            </div>
            <p
              data-testid="runtime-readiness-research-dna-note"
              className="mt-3 text-xs text-[var(--pp-text-dim)]"
            >
              Research DNA stays API/CLI-first for now. Continue with{" "}
              <span className="font-mono text-[var(--pp-text-secondary)]">paperpipe research-dna ...</span>{" "}
              after the runtime is healthy.
            </p>
          </div>

          {suggestedFixes.length > 0 ? (
            <div
              data-testid="runtime-readiness-suggested-fixes"
              className="mt-4 border-t border-[var(--pp-border)] pt-4"
            >
              <h3 className="text-sm font-semibold text-[var(--pp-text-primary)]">Suggested fixes</h3>
              <div className="mt-3 space-y-3">
                {suggestedFixes.map((fix) => (
                  <div
                    key={fix.key}
                    data-testid={`runtime-readiness-fix-${fix.key}`}
                    className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
                  >
                    <p className="text-sm font-medium text-[var(--pp-text-primary)]">{fix.title}</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--pp-text-secondary)]">{fix.body}</p>
                    {fix.code ? (
                      <p className="mt-2 text-xs text-[var(--pp-text-dim)]">
                        <span className="font-medium text-[var(--pp-text-secondary)]">Recovery command:</span>{" "}
                        <span className="font-mono">{fix.code}</span>
                      </p>
                    ) : null}
                    {fix.href && fix.hrefLabel ? (
                      <Link
                        to={fix.href}
                        className="mt-2 inline-flex items-center text-xs text-[var(--pp-accent-text)] underline underline-offset-2"
                      >
                        {fix.hrefLabel}
                      </Link>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </aside>
      </section>

      <section className="surface-card p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">Checks</h2>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Each row maps to a runtime dependency or path that the backend expects to be available.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-6 text-sm text-[var(--pp-text-secondary)]">
            Loading runtime checks...
          </div>
        ) : readiness.checks.length === 0 ? (
          <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-6 text-sm text-[var(--pp-text-secondary)]">
            No readiness checks were returned.
          </div>
        ) : (
          <div className="space-y-3">
            {readiness.checks.map((check) => (
              <article
                key={check.name}
                data-testid={`runtime-readiness-check-${check.name}`}
                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--pp-text-primary)]">{formatCheckName(check.name)}</h3>
                    <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{check.detail}</p>
                    {check.path ? (
                      <p className="mt-2 text-xs text-[var(--pp-text-dim)]">
                        Path: <span className="font-mono">{check.path}</span>
                      </p>
                    ) : null}
                  </div>
                  <span
                    className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${getStatusToneClassName(checkStatusTone(check.status))}`}
                  >
                    {check.status === "ok" ? "OK" : check.status === "warn" ? "Warning" : "Error"}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
