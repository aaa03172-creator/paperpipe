import { useMemo, useState } from "react";
import { ChevronDown, FileText, Search, TriangleAlert } from "lucide-react";
import { PaperSummary } from "../lib/types";
import { statusLabel } from "../lib/ui";

interface RailProps {
  papers: PaperSummary[];
  selectedPaperId?: string;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onSelectPaper: (paperId: string) => void;
  mobileCollapsedByDefault?: boolean;
}

function statusClasses(status: PaperSummary["status"]): string {
  if (status === "processing") {
    return "bg-[var(--pp-status-processing-bg)] text-[var(--pp-status-processing-text)] border-[var(--pp-status-processing-border)]";
  }
  if (status === "completed") {
    return "bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)] border-[var(--pp-status-completed-border)]";
  }
  if (status === "failed") {
    return "bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)] border-[var(--pp-status-failed-border)]";
  }
  return "bg-[var(--pp-status-idle-bg)] text-[var(--pp-status-idle-text)] border-[var(--pp-status-idle-border)]";
}

export function Rail({
  papers,
  selectedPaperId,
  searchQuery,
  onSearchChange,
  onSelectPaper,
  mobileCollapsedByDefault = true,
}: RailProps) {
  const [mobileOpen, setMobileOpen] = useState(!mobileCollapsedByDefault);
  const query = searchQuery.trim().toLowerCase();
  const filteredPapers = useMemo(() => {
    if (!query) {
      return papers;
    }
    return papers.filter((paper) =>
      `${paper.title} ${paper.paper_id} ${paper.authors ?? ""}`.toLowerCase().includes(query),
    );
  }, [papers, query]);

  const totalCount = papers.length;
  const filteredCount = filteredPapers.length;

  const paperButtons = filteredPapers.map((paper) => {
    const active = paper.paper_id === selectedPaperId;
    return (
      <button
        key={paper.paper_id}
        type="button"
        onClick={() => onSelectPaper(paper.paper_id)}
        className={[
          "w-full rounded-md border p-3 text-left transition-colors",
          active
            ? "border-[var(--pp-accent)] bg-[var(--pp-surface-selected)]"
            : "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] hover:bg-[var(--pp-surface-muted)]",
        ].join(" ")}
      >
        <div className="flex items-start gap-2">
          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-[var(--pp-text-dim)]" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
            <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between gap-2">
          <span
            className={[
              "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
              statusClasses(paper.status),
            ].join(" ")}
          >
            {statusLabel(paper.status ?? "not_started")}
          </span>

          {(paper.issues ?? 0) > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2 py-0.5 text-[11px] text-[var(--pp-warning-text)]">
              <TriangleAlert className="h-3 w-3" />
              {paper.issues}
            </span>
          ) : null}
        </div>
      </button>
    );
  });

  return (
    <aside className="surface-card flex min-h-0 max-h-[min(72vh,760px)] flex-col overflow-hidden p-3 xl:h-full xl:max-h-none">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Navigation Rail</p>
        <label className="mt-3 flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2 py-2">
          <Search className="h-4 w-4 text-[var(--pp-text-dim)]" />
          <input
            value={searchQuery}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search papers"
            className="w-full bg-transparent text-sm text-[var(--pp-text-primary)] outline-none placeholder:text-[var(--pp-text-dim)]"
            aria-label="Search papers"
          />
        </label>
        {query ? (
          <div className="mt-1 flex items-center justify-between gap-2 text-xs text-[var(--pp-text-dim)]">
            <span>{`${filteredCount} / ${totalCount} matched`}</span>
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="rounded-full border border-[var(--pp-border)] px-2 py-0.5 text-[11px] text-[var(--pp-text-secondary)]"
            >
              Clear
            </button>
          </div>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => setMobileOpen((value) => !value)}
        className="mt-3 inline-flex items-center justify-between rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)] xl:hidden"
      >
        <span>{query ? `Papers · ${filteredCount}/${totalCount}` : `Papers · ${totalCount}`}</span>
        <ChevronDown className={["h-3.5 w-3.5 transition-transform", mobileOpen ? "rotate-180" : "rotate-0"].join(" ")} />
      </button>

      <div
        className={[
          "mt-3 space-y-2 overflow-auto pr-1",
          mobileOpen ? "block max-h-[min(58vh,620px)]" : "hidden",
          "xl:mt-3 xl:flex-1 xl:max-h-none xl:space-y-2 xl:overflow-auto xl:pr-1 xl:block",
        ].join(" ")}
      >
        {paperButtons.length > 0 ? (
          paperButtons
        ) : (
          <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-dim)]">
            {query ? "No papers matched this search." : "No papers available."}
          </div>
        )}
      </div>
    </aside>
  );
}
