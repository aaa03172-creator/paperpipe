import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft, RefreshCw, Stethoscope } from "lucide-react";
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
              Use this page when the app boots but a feature still feels unavailable, or before sharing the runtime with someone else.
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
          <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">What to do next</h2>
          <ul className="mt-3 space-y-2 text-sm text-[var(--pp-text-secondary)]">
            <li>Resolve error checks before trying real deep-read or artifact generation flows.</li>
            <li>Warnings usually mean the app can open, but some runtime paths or assets still need cleanup.</li>
            <li>If you are intentionally in mock mode, disable it before using this page as a live readiness signal.</li>
            {hasPickupWarnings ? (
              <li>
                If the watch-folder checks are warning on this machine, automatic pickup may not run yet. Use{" "}
                <Link to="/papers" className="text-[var(--pp-accent-text)] underline underline-offset-2">
                  Import PDF in Paper Notes
                </Link>{" "}
                while you finish local setup.
              </li>
            ) : null}
          </ul>
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
