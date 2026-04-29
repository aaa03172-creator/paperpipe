import { ReactNode, useMemo, useState } from "react";
import { ChevronDown, FileText, Search } from "lucide-react";
import { getPaperAccessSummaryDisplay } from "../lib/accessSummary";
import { deriveContentReviewSummary } from "../lib/contentReview";
import { PaperNoteOpsSummary, PaperSummary } from "../lib/types";
import { OperationalStateSummary } from "./OperationalStateSummary";
import { StatusChip } from "./StatusChip";
import { StatusBadge } from "./StatusBadge";

interface RailProps {
  papers: PaperSummary[];
  paperNoteOpsByPaperId?: Record<string, PaperNoteOpsSummary>;
  selectedPaperId?: string;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onSelectPaper: (paperId: string) => void;
  mobileCollapsedByDefault?: boolean;
  shortcutNav?: ReactNode;
}

function paperIdVariants(paperId?: string): string[] {
  const text = paperId?.trim() ?? "";
  if (!text) {
    return [];
  }

  const variants: string[] = [];
  const append = (value: string) => {
    const candidate = value.trim();
    if (candidate && !variants.includes(candidate)) {
      variants.push(candidate);
    }
  };

  append(text);
  append(text.replaceAll(":", ""));
  if (text.includes(":")) {
    const suffix = text.split(":", 2)[1]?.trim() ?? "";
    append(suffix);
    append(suffix.replaceAll(":", ""));
  }
  return variants;
}

function paperIdsMatch(left?: string, right?: string): boolean {
  const leftVariants = paperIdVariants(left);
  const rightVariants = new Set(paperIdVariants(right));
  return leftVariants.some((candidate) => rightVariants.has(candidate));
}

export function Rail({
  papers,
  paperNoteOpsByPaperId = {},
  selectedPaperId,
  searchQuery,
  onSearchChange,
  onSelectPaper,
  mobileCollapsedByDefault = true,
  shortcutNav,
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
    const active = paperIdsMatch(paper.paper_id, selectedPaperId);
    const opsSummary = paperNoteOpsByPaperId[paper.paper_id] ?? null;
    const accessSummary = getPaperAccessSummaryDisplay(paper.access_summary);
    const contentReviewSummary = deriveContentReviewSummary(paper.issues, {
      issuesLabel: paper.issues_label,
      issuesState: paper.issues_state,
    });
    const issueCount = contentReviewSummary.issueCount;
    const reviewDetail = active && contentReviewSummary.detail ? contentReviewSummary.detail : null;
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
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <StatusChip status={paper.status ?? "not_started"} />
          </div>

          {issueCount > 0 ? (
            <StatusBadge
              label={`Review ${issueCount}`}
              tone="danger"
              iconTone="danger"
              className="px-2"
              testId="rail-review-issues-badge"
            />
          ) : contentReviewSummary.state === "unavailable" ? (
            <StatusBadge
              label="Review unavailable"
              tone="muted"
              className="px-2"
              testId="rail-review-unavailable-badge"
            />
          ) : null}
        </div>
        {reviewDetail ? (
          <p data-testid="rail-review-detail" className="mt-2 line-clamp-2 text-[11px] text-[var(--pp-text-dim)]">
            {reviewDetail}
          </p>
        ) : null}
        <div className="mt-2">
          <StatusBadge
            label={accessSummary.label}
            tone={accessSummary.tone}
            className="px-2"
            testId="rail-access-badge"
          />
        </div>
        {opsSummary ? (
          <div className="mt-2">
            <OperationalStateSummary
              summary={opsSummary}
              badgeTestId="rail-ops-badge"
              reasonTestId="rail-ops-reason"
              compact
              showActionHint={false}
            />
          </div>
        ) : null}
      </button>
    );
  });

  return (
    <aside className="surface-card flex min-h-0 max-h-[min(72vh,760px)] flex-col overflow-hidden p-3 xl:h-full xl:max-h-none">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Papers</p>
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
        {shortcutNav ? <div className="mt-2 flex flex-wrap items-center gap-1.5">{shortcutNav}</div> : null}
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
