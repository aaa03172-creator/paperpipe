import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpDown, Search } from "lucide-react";
import { getApiErrorMessage, getPaperNotesIndex } from "../lib/api";
import { PaperNoteSummary } from "../lib/types";

type SortBy = "date_processed" | "confidence";
type SortOrder = "asc" | "desc";
const PAGE_SIZE = 30;

function parseSortBy(value: string | null): SortBy {
  if (value === "confidence" || value === "date_processed") {
    return value;
  }
  return "date_processed";
}

function parseSortOrder(value: string | null): SortOrder {
  if (value === "asc" || value === "desc") {
    return value;
  }
  return "desc";
}

function parsePage(value: string | null): number {
  if (!value) {
    return 1;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    return 1;
  }
  return parsed;
}

function parseSelectedTags(value: string | null): string[] {
  if (!value) {
    return [];
  }
  const unique = new Set(
    value
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean),
  );
  return Array.from(unique.values());
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

function confidenceLabel(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

export function PaperNotesListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const loadSequence = useRef(0);
  const [items, setItems] = useState<PaperNoteSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allStatuses, setAllStatuses] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [tagInput, setTagInput] = useState(() => searchParams.get("tag_input") ?? "");
  const [selectedTags, setSelectedTags] = useState<string[]>(() => parseSelectedTags(searchParams.get("tags")));
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get("status") ?? "all");
  const [sortBy, setSortBy] = useState<SortBy>(() => parseSortBy(searchParams.get("sort")));
  const [sortOrder, setSortOrder] = useState<SortOrder>(() => parseSortOrder(searchParams.get("order")));
  const [page, setPage] = useState(() => parsePage(searchParams.get("page")));

  useEffect(() => {
    const seq = loadSequence.current + 1;
    loadSequence.current = seq;
    let active = true;

    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const result = await getPaperNotesIndex({
          q: query.trim() || undefined,
          tags: selectedTags,
          status: statusFilter !== "all" ? statusFilter : undefined,
          sortBy,
          sortOrder,
          page,
          pageSize: PAGE_SIZE,
        });
        if (!active || loadSequence.current !== seq) {
          return;
        }
        const response = result.data;
        setItems(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
        setAllTags(response.available_tags);
        setAllStatuses(response.available_statuses);
        if (response.page !== page) {
          setPage(response.page);
        }
      } catch (error) {
        if (!active || loadSequence.current !== seq) {
          return;
        }
        setItems([]);
        setTotal(0);
        setTotalPages(1);
        setLoadError(getApiErrorMessage(error));
      } finally {
        if (active && loadSequence.current === seq) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [page, query, selectedTags, sortBy, sortOrder, statusFilter]);

  useEffect(() => {
    document.title = "Paper Notes | Lattice";
  }, []);

  const matchedTagHints = useMemo(() => {
    const needle = tagInput.trim().toLowerCase();
    if (!needle) {
      return allTags.filter((tag) => !selectedTags.includes(tag)).slice(0, 8);
    }
    return allTags
      .filter((tag) => tag.toLowerCase().includes(needle) && !selectedTags.includes(tag))
      .slice(0, 8);
  }, [allTags, selectedTags, tagInput]);

  function addTag(raw: string) {
    const input = raw.trim();
    if (!input) {
      return;
    }
    const exact = allTags.find((tag) => tag.toLowerCase() === input.toLowerCase());
    const candidate = exact ?? allTags.find((tag) => tag.toLowerCase().includes(input.toLowerCase()));
    if (!candidate) {
      return;
    }
    setSelectedTags((current) => (current.includes(candidate) ? current : [...current, candidate]));
    setTagInput("");
    setPage(1);
  }

  function removeTag(tag: string) {
    setSelectedTags((current) => current.filter((value) => value !== tag));
    setPage(1);
  }

  function clearTags() {
    setSelectedTags([]);
    setPage(1);
  }

  function handleQueryChange(value: string) {
    setQuery(value);
    setPage(1);
  }

  function handleStatusChange(value: string) {
    setStatusFilter(value);
    setPage(1);
  }

  function handleSortByChange(value: SortBy) {
    setSortBy(value);
    setPage(1);
  }

  function toggleSortOrder() {
    setSortOrder((current) => (current === "desc" ? "asc" : "desc"));
    setPage(1);
  }

  useEffect(() => {
    const next = new URLSearchParams();
    const trimmedQuery = query.trim();
    const trimmedTagInput = tagInput.trim();
    if (trimmedQuery) {
      next.set("q", trimmedQuery);
    }
    if (selectedTags.length > 0) {
      next.set("tags", selectedTags.join(","));
    }
    if (statusFilter !== "all") {
      next.set("status", statusFilter);
    }
    if (sortBy !== "date_processed") {
      next.set("sort", sortBy);
    }
    if (sortOrder !== "desc") {
      next.set("order", sortOrder);
    }
    if (page > 1) {
      next.set("page", String(page));
    }
    if (trimmedTagInput) {
      next.set("tag_input", trimmedTagInput);
    }

    const nextValue = next.toString();
    const currentValue = searchParams.toString();
    if (nextValue !== currentValue) {
      setSearchParams(next, { replace: true });
    }
  }, [page, query, searchParams, selectedTags, setSearchParams, sortBy, sortOrder, statusFilter, tagInput]);

  const pageWindow = useMemo(() => {
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, start + 4);
    const pages: number[] = [];
    for (let current = start; current <= end; current += 1) {
      pages.push(current);
    }
    return pages;
  }, [page, totalPages]);

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Lattice · Paper Notes Viewer</p>
        <h1 className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">Paper Notes</h1>
        <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
          Obsidian vault note index with search, filtering, and confidence/date sorting.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-4">
          <label className="md:col-span-2">
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Search</span>
            <span className="flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5">
              <Search className="h-3.5 w-3.5 text-[var(--pp-text-dim)]" />
              <input
                value={query}
                onChange={(event) => handleQueryChange(event.target.value)}
                placeholder="title / alias / slug"
                className="w-full border-0 bg-transparent px-2 py-2 text-sm text-[var(--pp-text-primary)] outline-none"
              />
            </span>
          </label>

          <div>
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Tags (multi)</span>
            <div className="flex items-center gap-2">
              <input
                value={tagInput}
                onChange={(event) => setTagInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addTag(tagInput);
                  }
                }}
                list="paper-note-tags"
                placeholder="Type tag and Enter"
                className="w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-sm text-[var(--pp-text-primary)]"
              />
              <button
                type="button"
                onClick={() => addTag(tagInput)}
                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-xs text-[var(--pp-text-secondary)]"
              >
                Add
              </button>
            </div>
            <datalist id="paper-note-tags">
              {allTags.map((tag) => (
                <option key={tag} value={tag} />
              ))}
            </datalist>
            {selectedTags.length > 0 ? (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {selectedTags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => removeTag(tag)}
                    className="inline-flex items-center rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-xs text-[var(--pp-accent-text)]"
                  >
                    {tag} ×
                  </button>
                ))}
                <button
                  type="button"
                  onClick={clearTags}
                  className="rounded-full border border-[var(--pp-border)] px-2 py-0.5 text-xs text-[var(--pp-text-dim)]"
                >
                  Clear
                </button>
              </div>
            ) : null}
            {matchedTagHints.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {matchedTagHints.map((tag) => (
                  <button
                    key={`hint-${tag}`}
                    type="button"
                    onClick={() => addTag(tag)}
                    className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-0.5 text-xs text-[var(--pp-text-secondary)]"
                  >
                    + {tag}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <label>
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Status</span>
            <select
              value={statusFilter}
              onChange={(event) => handleStatusChange(event.target.value)}
              className="w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-sm text-[var(--pp-text-primary)]"
            >
              <option value="all">All status</option>
              {allStatuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Sort</span>
            <div className="flex items-center gap-2">
              <select
                value={sortBy}
                onChange={(event) => handleSortByChange(event.target.value as SortBy)}
                className="w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-sm text-[var(--pp-text-primary)]"
              >
                <option value="date_processed">date_processed</option>
                <option value="confidence">confidence</option>
              </select>
              <button
                type="button"
                onClick={toggleSortOrder}
                className="inline-flex h-[35px] w-[35px] items-center justify-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)]"
                aria-label="Toggle sort order"
                title={`Sort ${sortOrder === "desc" ? "descending" : "ascending"}`}
              >
                <ArrowUpDown className="h-3.5 w-3.5" />
              </button>
            </div>
          </label>
        </div>
      </header>

      <section className="surface-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-dim)]">
          <span>{loading ? "Loading notes..." : `${total} notes · page ${page}/${totalPages}`}</span>
          <Link to="/" className="text-[var(--pp-accent-text)] underline-offset-2 hover:underline">
            Open Workbench
          </Link>
        </div>
        {loadError ? (
          <p className="p-4 text-sm text-[var(--pp-status-failed-text)]">API error: {loadError}</p>
        ) : null}
        {!loadError ? (
          <>
            {!loading && total === 0 ? (
              <p className="p-4 text-sm text-[var(--pp-text-dim)]">No notes matched the current filters.</p>
            ) : null}

            <div className="space-y-2 p-3 md:hidden">
              {items.map((item) => (
                <article key={item.slug} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3">
                  <Link
                    to={`/papers/${encodeURIComponent(item.slug)}`}
                    className="text-sm font-medium text-[var(--pp-text-primary)] underline-offset-2 hover:underline"
                  >
                    {item.title}
                  </Link>
                  <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{item.slug}</p>

                  <div className="mt-2 flex flex-wrap gap-1">
                    {item.tags.slice(0, 4).map((tag) => (
                      <span
                        key={`${item.slug}-${tag}`}
                        className="inline-flex rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-xs text-[var(--pp-accent-text)]"
                      >
                        {tag}
                      </span>
                    ))}
                    {item.tags.length > 4 ? (
                      <span className="inline-flex rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2 py-0.5 text-xs text-[var(--pp-text-dim)]">
                        +{item.tags.length - 4}
                      </span>
                    ) : null}
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-[var(--pp-text-secondary)]">
                    <div>
                      <p className="text-[var(--pp-text-dim)]">Status</p>
                      <p>{item.status ?? "-"}</p>
                    </div>
                    <div>
                      <p className="text-[var(--pp-text-dim)]">Date</p>
                      <p>{formatDate(item.date_processed)}</p>
                    </div>
                    <div>
                      <p className="text-[var(--pp-text-dim)]">Conf.</p>
                      <p>{confidenceLabel(item.confidence)}</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>

            <div className="hidden max-h-[70vh] overflow-auto md:block">
              <table className="w-full min-w-[860px] border-collapse text-sm">
                <thead className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">
                  <tr>
                    <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Title</th>
                    <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Tags</th>
                    <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Status</th>
                    <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Date</th>
                    <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.slug} className="bg-[var(--pp-surface)] hover:bg-[var(--pp-surface-selected)]">
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 align-top">
                        <Link
                          to={`/papers/${encodeURIComponent(item.slug)}`}
                          className="font-medium text-[var(--pp-text-primary)] underline-offset-2 hover:underline"
                        >
                          {item.title}
                        </Link>
                        <p className="mt-1 text-xs text-[var(--pp-text-dim)]">{item.slug}</p>
                      </td>
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 align-top">
                        <div className="flex max-w-[340px] flex-wrap gap-1">
                          {item.tags.length === 0 ? <span className="text-xs text-[var(--pp-text-dim)]">-</span> : null}
                          {item.tags.map((tag) => (
                            <span
                              key={`${item.slug}-${tag}`}
                              className="inline-flex rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-xs text-[var(--pp-accent-text)]"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 align-top text-xs text-[var(--pp-text-secondary)]">
                        {item.status ?? "-"}
                      </td>
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 align-top text-xs text-[var(--pp-text-secondary)]">
                        {formatDate(item.date_processed)}
                      </td>
                      <td className="border-b border-[var(--pp-border)] px-3 py-3 align-top text-xs text-[var(--pp-text-secondary)]">
                        {confidenceLabel(item.confidence)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {total > 0 ? (
              <div className="flex items-center justify-between border-t border-[var(--pp-border)] px-3 py-2">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page <= 1}
                  className="rounded-md border border-[var(--pp-border)] px-2.5 py-1 text-xs text-[var(--pp-text-secondary)] disabled:opacity-50"
                >
                  Prev
                </button>
                <div className="flex items-center gap-1">
                  {pageWindow.map((value) => (
                    <button
                      key={`page-${value}`}
                      type="button"
                      onClick={() => setPage(value)}
                      className={[
                        "rounded-md border px-2.5 py-1 text-xs",
                        value === page
                          ? "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]"
                          : "border-[var(--pp-border)] text-[var(--pp-text-secondary)]",
                      ].join(" ")}
                    >
                      {value}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                  disabled={page >= totalPages}
                  className="rounded-md border border-[var(--pp-border)] px-2.5 py-1 text-xs text-[var(--pp-text-secondary)] disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}
