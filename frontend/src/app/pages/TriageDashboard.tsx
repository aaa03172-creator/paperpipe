import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, LayoutGrid } from "lucide-react";
import { getApiErrorMessage, getHealth, getPapers } from "../lib/api";
import { PaperSummary } from "../lib/types";
import { Rail } from "../components/Rail";
import { StatusChip } from "../components/StatusChip";
import { useAppStore } from "../store/useAppStore";

export function TriageDashboard() {
  const navigate = useNavigate();
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const searchQuery = useAppStore((state) => state.searchQuery);
  const setSearchQuery = useAppStore((state) => state.setSearchQuery);
  const mockMode = useAppStore((state) => state.mockMode);
  const mockReasons = useAppStore((state) => state.mockReasons);
  const markMockMode = useAppStore((state) => state.markMockMode);
  const clearMockMode = useAppStore((state) => state.clearMockMode);
  const themeMode = useAppStore((state) => state.themeMode);
  const setThemeMode = useAppStore((state) => state.setThemeMode);

  useEffect(() => {
    let mounted = true;

    async function load() {
      clearMockMode();
      setLoading(true);
      setLoadError(null);

      try {
        const [healthResult, paperResult] = await Promise.all([getHealth(), getPapers()]);
        if (!mounted) {
          return;
        }

        if (healthResult.isMock) {
          markMockMode(healthResult.reason);
        }
        if (paperResult.isMock) {
          markMockMode(paperResult.reason);
        }

        setPapers(paperResult.data);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setPapers([]);
        setLoadError(getApiErrorMessage(error));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [clearMockMode, markMockMode]);

  useEffect(() => {
    document.title = "Triage | Lattice";
  }, []);

  const filteredPapers = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();
    if (!keyword) {
      return papers;
    }
    return papers.filter((paper) => {
      const target = `${paper.title} ${paper.paper_id} ${paper.authors ?? ""}`.toLowerCase();
      return target.includes(keyword);
    });
  }, [papers, searchQuery]);

  function moveToWorkbench(paperId: string, options?: { focusIssues?: boolean }) {
    const encoded = encodeURIComponent(paperId);
    if (options?.focusIssues) {
      navigate(`/workbench/${encoded}?focus=issues`);
      return;
    }
    navigate(`/workbench/${encoded}`);
  }

  function issueLabel(paper: PaperSummary): string {
    return paper.issues_label ?? (paper.issues ? `⚠️ ${paper.issues} Issues` : "No critical issues");
  }

  function formatUpdatedAt(updatedAt?: string): string {
    if (!updatedAt) {
      return "-";
    }
    return new Date(updatedAt).toLocaleString();
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <LayoutGrid className="h-3.5 w-3.5" />
              Research queue
            </p>
            <h1 className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">Triage Dashboard</h1>
            <p className="text-sm text-[var(--pp-text-secondary)]">
              Review paper status and open the workbench when deeper evidence inspection is needed.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockMode ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
              Theme
              <select
                value={themeMode}
                onChange={(event) => setThemeMode(event.target.value as "dark" | "light" | "system")}
                className="bg-transparent text-[var(--pp-text-primary)] outline-none"
              >
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System</option>
              </select>
            </label>
          </div>
        </div>
        {mockMode && mockReasons.length > 0 ? (
          <details data-testid="triage-mock-mode-details" className="mt-2 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-2">
            <summary className="cursor-pointer text-xs font-semibold text-[var(--pp-warning-text)]">
              Mock fallback details
            </summary>
            <ul className="mt-1 space-y-1 text-xs text-[var(--pp-warning-text)]">
              {mockReasons.map((reason) => (
                <li key={reason} data-testid="triage-mock-mode-reason-item">{reason}</li>
              ))}
            </ul>
          </details>
        ) : null}
        {loadError ? (
          <p className="mt-2 text-xs text-[var(--pp-status-failed-text)]">API error: {loadError}</p>
        ) : null}
      </header>

      <main className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
        <div className="min-h-0">
          <Rail
            papers={filteredPapers}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onSelectPaper={(paperId) => navigate(`/workbench/${encodeURIComponent(paperId)}`)}
          />
        </div>

        <section className="surface-card min-h-0 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">Papers in queue</h2>
            <p className="text-xs text-[var(--pp-text-dim)]">{filteredPapers.length} results</p>
          </div>

          {loading ? (
            <p className="text-sm text-[var(--pp-text-dim)]">Loading triage queue...</p>
          ) : (
            <div className="space-y-3">
              <div className="space-y-2 md:hidden">
                {filteredPapers.map((paper) => (
                  <article key={paper.paper_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="line-clamp-2 text-sm font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
                        <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
                      </div>
                      <StatusChip status={paper.status ?? "not_started"} />
                    </div>

                    <p className="mt-2 text-xs text-[var(--pp-text-dim)]">Updated: {formatUpdatedAt(paper.updated_at)}</p>

                    <div className="mt-3 grid grid-cols-1 gap-2">
                      <button
                        type="button"
                        onClick={() => moveToWorkbench(paper.paper_id)}
                        className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-2 text-xs font-medium text-[var(--pp-accent-text)]"
                      >
                        Open Workbench
                        <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveToWorkbench(paper.paper_id, { focusIssues: true })}
                        disabled={(paper.issues ?? 0) === 0}
                        className={[
                          "inline-flex items-center justify-center rounded-md border px-2.5 py-2 text-xs",
                          (paper.issues ?? 0) > 0
                            ? "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
                            : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
                        ].join(" ")}
                      >
                        {(paper.issues ?? 0) > 0 ? `Issues first · ${issueLabel(paper)}` : "No critical issues"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>

              <div className="hidden overflow-auto rounded-md border border-[var(--pp-border)] md:block">
                <table className="w-full min-w-[760px] border-collapse text-sm">
                  <thead className="bg-[var(--pp-surface-muted)] text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">
                    <tr>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Paper</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Status</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Issues</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Updated</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-right">Open</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPapers.map((paper) => (
                      <tr
                        key={paper.paper_id}
                        className="cursor-pointer bg-[var(--pp-surface-raised)] hover:bg-[var(--pp-surface-selected)]"
                        onClick={() => moveToWorkbench(paper.paper_id)}
                      >
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <p className="font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
                          <p className="text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <StatusChip status={paper.status ?? "not_started"} />
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveToWorkbench(paper.paper_id, { focusIssues: true });
                            }}
                            disabled={(paper.issues ?? 0) === 0}
                            className={[
                              "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
                              (paper.issues ?? 0) > 0
                                ? "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
                                : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
                            ].join(" ")}
                          >
                            {issueLabel(paper)}
                          </button>
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3 text-xs text-[var(--pp-text-dim)]">
                          {formatUpdatedAt(paper.updated_at)}
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3 text-right">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveToWorkbench(paper.paper_id);
                            }}
                            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs font-medium text-[var(--pp-accent-text)]"
                          >
                            Open Workbench
                            <ArrowRight className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
