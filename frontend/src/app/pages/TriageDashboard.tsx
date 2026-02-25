import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, LayoutGrid } from "lucide-react";
import { getHealth, getPapers } from "../lib/api";
import { PaperSummary } from "../lib/types";
import { Rail } from "../components/Rail";
import { StatusChip } from "../components/StatusChip";
import { useAppStore } from "../store/useAppStore";

export function TriageDashboard() {
  const navigate = useNavigate();
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [loading, setLoading] = useState(true);

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
      setLoading(false);
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [clearMockMode, markMockMode]);

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

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <LayoutGrid className="h-3.5 w-3.5" />
              Phase 3 Control UI
            </p>
            <h1 className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">Triage Dashboard</h1>
            <p className="text-sm text-[var(--pp-text-secondary)]">Paper selection and issue-first routing into Analysis Workbench.</p>
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
          <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
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
            <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">Paper Queue</h2>
            <p className="text-xs text-[var(--pp-text-dim)]">{filteredPapers.length} items</p>
          </div>

          {loading ? (
            <p className="text-sm text-[var(--pp-text-dim)]">Loading papers...</p>
          ) : (
            <div className="overflow-auto rounded-md border border-[var(--pp-border)]">
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
                      onClick={() => navigate(`/workbench/${encodeURIComponent(paper.paper_id)}`)}
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
                            navigate(`/workbench/${encodeURIComponent(paper.paper_id)}?focus=issues`);
                          }}
                          className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]"
                        >
                          {paper.issues_label ?? (paper.issues ? `⚠️ ${paper.issues} Issues` : "No critical issues")}
                        </button>
                      </td>
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 text-xs text-[var(--pp-text-dim)]">
                        {paper.updated_at ? new Date(paper.updated_at).toLocaleString() : "-"}
                      </td>
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 text-right">
                        <Link
                          to={`/workbench/${encodeURIComponent(paper.paper_id)}`}
                          onClick={(event) => event.stopPropagation()}
                          className="inline-flex items-center gap-1 text-xs text-[var(--pp-accent-text)]"
                        >
                          Open
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
