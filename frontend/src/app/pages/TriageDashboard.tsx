import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, LayoutGrid } from "lucide-react";
import { getApiErrorMessage, getHealth, getPapers, logClientUserAction } from "../lib/api";
import { deriveContentReviewSummary } from "../lib/contentReview";
import { PaperSummary } from "../lib/types";
import { ContentReviewSummary } from "../components/ContentReviewSummary";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
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
  const paperNoteOpsByPaperId = useMemo(
    () =>
      Object.fromEntries(
        papers
          .filter((paper) => paper.ops_summary)
          .map((paper) => [paper.paper_id, paper.ops_summary!]),
      ),
    [papers],
  );

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

  function moveToWorkbench(paperId: string, options?: { focusIssues?: boolean; origin?: string }) {
    logClientUserAction({
      paper_id: paperId,
      action_type: options?.focusIssues ? "open_workbench_focus_issues" : "open_workbench",
      payload: {
        origin: options?.origin ?? "triage_dashboard",
        focus_issues: options?.focusIssues === true,
      },
    });
    const encoded = encodeURIComponent(paperId);
    if (options?.focusIssues) {
      navigate(`/workbench/${encoded}?focus=issues`);
      return;
    }
    navigate(`/workbench/${encoded}`);
  }

  function getContentReviewSummary(paper: PaperSummary) {
    return deriveContentReviewSummary(paper.issues, { issuesLabel: paper.issues_label, issuesState: paper.issues_state });
  }

  function reviewIssueButtonClassName(paper: PaperSummary): string {
    const summary = getContentReviewSummary(paper);
    if (summary.state === "flagged") {
      return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
    }
    if (summary.state === "unavailable") {
      return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-dim)]";
    }
    return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
  }

  function formatUpdatedAt(updatedAt?: string): string {
    if (!updatedAt) {
      return "-";
    }
    return new Date(updatedAt).toLocaleString();
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="max-w-2xl">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <LayoutGrid className="h-3.5 w-3.5" />
              Research queue
            </p>
            <h1 className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">Triage Dashboard</h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Review paper status, check content review signals, and open the workbench.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockMode ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            <Link
              to="/papers"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Paper Notes
            </Link>
            <Link
              to="/meeting-packs"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Meeting Packs
            </Link>
            <Link
              to="/method-comparisons"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Method Comparisons
            </Link>
            <Link
              to="/chart-packs"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Chart Packs
            </Link>
            <Link
              to="/image-evidence"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Image Evidence
            </Link>
            <Link
              to="/protocol-cards"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              Protocol Cards
            </Link>
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
          <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
        {loadError ? (
          <p className="mt-2 text-xs text-[var(--pp-status-failed-text)]">API error: {loadError}</p>
        ) : null}
      </header>

      <main className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
        <div className="min-h-0">
          <Rail
            papers={filteredPapers}
            paperNoteOpsByPaperId={paperNoteOpsByPaperId}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onSelectPaper={(paperId) => moveToWorkbench(paperId, { origin: "triage_rail" })}
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
                {filteredPapers.map((paper) => {
                  const contentReview = getContentReviewSummary(paper);
                  return (
                    <article key={paper.paper_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="line-clamp-2 text-sm font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
                        <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
                      </div>
                      <StatusChip status={paper.status ?? "not_started"} />
                    </div>

                    <div className="mt-2">
                      <OperationalStateSummary
                        summary={paperNoteOpsByPaperId[paper.paper_id]}
                        badgeTestId="triage-ops-badge"
                        reasonTestId="triage-ops-reason"
                        compact
                      />
                    </div>

                    <p className="mt-2 text-xs text-[var(--pp-text-dim)]">Updated: {formatUpdatedAt(paper.updated_at)}</p>

                    <div className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Content review</p>
                      </div>
                      <ContentReviewSummary
                        summary={contentReview}
                        badgeTestId="triage-review-badge"
                        hintTestId="triage-review-hint"
                        detailTestId="triage-review-detail"
                        className="mt-1"
                        compact
                      />
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        <button
                          type="button"
                          onClick={() => moveToWorkbench(paper.paper_id, { origin: "triage_mobile_open" })}
                          className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-2 text-xs font-medium text-[var(--pp-accent-text)]"
                        >
                          Open Workbench
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveToWorkbench(paper.paper_id, { focusIssues: true, origin: "triage_mobile_content_review" })}
                          disabled={contentReview.issueCount === 0}
                          data-testid="triage-content-review-button"
                          className={[
                            "inline-flex items-center justify-center rounded-md border px-2.5 py-2 text-xs",
                            reviewIssueButtonClassName(paper),
                          ].join(" ")}
                        >
                          {contentReview.reviewLabel}
                        </button>
                      </div>
                    </div>
                    </article>
                  );
                })}
              </div>

              <div className="hidden overflow-auto rounded-md border border-[var(--pp-border)] md:block">
                <table className="w-full min-w-[760px] border-collapse text-sm">
                  <thead className="bg-[var(--pp-surface-muted)] text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">
                    <tr>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Paper</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Status</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Content Review</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Updated</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-right">Open</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPapers.map((paper) => {
                      const contentReview = getContentReviewSummary(paper);
                      return (
                      <tr
                        key={paper.paper_id}
                        className="cursor-pointer bg-[var(--pp-surface-raised)] hover:bg-[var(--pp-surface-selected)]"
                        onClick={() => moveToWorkbench(paper.paper_id, { origin: "triage_table_row" })}
                      >
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <p className="font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
                          <p className="text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
                          <div className="mt-2">
                            <OperationalStateSummary
                              summary={paperNoteOpsByPaperId[paper.paper_id]}
                              badgeTestId="triage-ops-badge"
                              reasonTestId="triage-ops-reason"
                              compact
                            />
                          </div>
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <StatusChip status={paper.status ?? "not_started"} />
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveToWorkbench(paper.paper_id, { focusIssues: true, origin: "triage_table_content_review" });
                            }}
                            disabled={contentReview.issueCount === 0}
                            data-testid="triage-content-review-button"
                            className={[
                              "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
                              reviewIssueButtonClassName(paper),
                            ].join(" ")}
                          >
                            {contentReview.reviewLabel}
                          </button>
                          <ContentReviewSummary
                            summary={contentReview}
                            badgeTestId="triage-review-badge"
                            hintTestId="triage-review-hint"
                            detailTestId="triage-review-detail"
                            className="mt-1"
                            compact
                          />
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3 text-xs text-[var(--pp-text-dim)]">
                          {formatUpdatedAt(paper.updated_at)}
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3 text-right">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveToWorkbench(paper.paper_id, { origin: "triage_table_open" });
                            }}
                            className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs font-medium text-[var(--pp-accent-text)]"
                          >
                            Open Workbench
                            <ArrowRight className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                      );
                    })}
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
