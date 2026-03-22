import { KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpDown, Check, Search, X } from "lucide-react";
import { getApiErrorMessage, getPaperNotesIndex } from "../lib/api";
import { PaperNoteSummary } from "../lib/types";
import { formatFreeformStatusLabel, getFreeformStatusTone, getStatusToneClassName } from "../lib/statusSystem";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
import { StatusBadge } from "../components/StatusBadge";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "../components/ui/command";
import { Input } from "../components/ui/input";

type SortBy = "date_processed" | "confidence";
type SortOrder = "asc" | "desc";
const DEFAULT_PAGE_SIZE = 30;
const PAGE_SIZE_OPTIONS = [30, 50, 100] as const;
const QUERY_TERM_PATTERN = /"([^"]+)"|(\S+)/g;
type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];

function isPageSizeOption(value: number): value is PageSize {
  return PAGE_SIZE_OPTIONS.some((option) => option === value);
}

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

function parsePageSize(value: string | null): PageSize {
  if (!value) {
    return DEFAULT_PAGE_SIZE;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || !isPageSizeOption(parsed)) {
    return DEFAULT_PAGE_SIZE;
  }
  return parsed;
}

function parseStructuredOnly(value: string | null): boolean {
  if (!value) {
    return false;
  }
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes";
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

function parseSearchTerms(value: string): string[] {
  const terms: string[] = [];
  for (const match of value.matchAll(QUERY_TERM_PATTERN)) {
    const raw = match[1] ?? match[2] ?? "";
    const normalized = raw.trim().toLowerCase().replace(/\s+/g, " ");
    if (normalized) {
      terms.push(normalized);
    }
  }
  return terms;
}

function hasQuotedSearch(value: string): boolean {
  return value.includes('"');
}

function uniqueSearchTerms(value: string): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const term of parseSearchTerms(value)) {
    if (seen.has(term)) {
      continue;
    }
    seen.add(term);
    output.push(term);
  }
  return output;
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

type ListBadgeTone = "accent" | "outline" | "muted" | "success" | "warning" | "danger";

function listBadgeClassName(tone: ListBadgeTone): string {
  if (tone === "accent") {
    return getStatusToneClassName("accent");
  }
  if (tone === "success") {
    return getStatusToneClassName("success");
  }
  if (tone === "warning") {
    return getStatusToneClassName("warning");
  }
  if (tone === "danger") {
    return getStatusToneClassName("danger");
  }
  if (tone === "outline") {
    return getStatusToneClassName("outline");
  }
  return getStatusToneClassName("muted");
}

function buildStateBadges(item: PaperNoteSummary): Array<{ label: string; tone: ListBadgeTone }> {
  const signals = (item.pp_signals ?? {}) as Record<string, unknown>;
  const badges: Array<{ label: string; tone: ListBadgeTone }> = [];
  if (signals.has_claimset === true || (item.claim_tags?.length ?? 0) > 0) {
    badges.push({ label: "ClaimSet ready", tone: "success" });
  }
  if ((item.entities?.length ?? 0) > 0 || (item.mesh?.length ?? 0) > 0 || (item.outcomes?.length ?? 0) > 0) {
    badges.push({ label: "Structured", tone: "accent" });
  }
  if (item.doi) {
    badges.push({ label: "DOI", tone: "outline" });
  }
  if (item.zotero_link) {
    badges.push({ label: "Zotero", tone: "outline" });
  }
  if (typeof signals.citation_count === "number" && signals.citation_count > 0) {
    badges.push({ label: `${signals.citation_count} cites`, tone: "muted" });
  }
  return badges;
}

function buildInsightText(item: PaperNoteSummary): string[] {
  const signals = (item.pp_signals ?? {}) as Record<string, unknown>;
  const output: string[] = [];
  if (typeof signals.last_appraisal === "string" && signals.last_appraisal.trim()) {
    output.push(`Appraisal: ${signals.last_appraisal.trim()}`);
  }
  if ((item.claim_tags?.length ?? 0) > 0) {
    output.push(`Claim tags ${item.claim_tags!.slice(0, 3).join(", ")}`);
  }
  if ((item.outcomes?.length ?? 0) > 0) {
    output.push(`Outcomes ${item.outcomes!.slice(0, 2).join(", ")}`);
  }
  return output.slice(0, 2);
}

interface StructuredSignalChip {
  label: string;
  matched: boolean;
}

function buildStructuredSignalChips(item: PaperNoteSummary, query?: string): StructuredSignalChip[] {
  const ordered = [...(item.entities ?? []), ...(item.mesh ?? []), ...(item.outcomes ?? []), ...(item.claim_tags ?? [])];
  const tokens = parseSearchTerms(query ?? "");
  const seen = new Set<string>();
  const matched: StructuredSignalChip[] = [];
  const remaining: StructuredSignalChip[] = [];
  for (const value of ordered) {
    const trimmed = value.trim();
    if (!trimmed) {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const entry = { label: trimmed, matched: tokens.length > 0 && tokens.some((token) => trimmed.toLowerCase().includes(token)) };
    if (entry.matched) {
      matched.push(entry);
    } else {
      remaining.push(entry);
    }
  }
  return [...matched, ...remaining].slice(0, 4);
}

function secondaryLabel(item: PaperNoteSummary): string {
  const alias = item.aliases.find((value) => value.trim() && value.trim() !== item.title.trim());
  if (alias) {
    return alias;
  }
  if (item.id?.trim()) {
    return item.id.trim();
  }
  return item.slug;
}

function PaperNoteListRow({ item, query }: { item: PaperNoteSummary; query?: string }) {
  const stateBadges = buildStateBadges(item);
  const insightText = buildInsightText(item);
  const structuredSignalChips = buildStructuredSignalChips(item, query);
  const visibleTags = item.tags.slice(0, 4);
  const extraTagCount = Math.max(item.tags.length - visibleTags.length, 0);

  return (
    <article
      className="rounded-xl border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 transition-colors hover:bg-[var(--pp-surface-selected)] md:p-4"
      data-testid="paper-note-list-row"
    >
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_240px] lg:gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-2 lg:hidden">
            <div className="min-w-0">
              <Link
                to={`/papers/${encodeURIComponent(item.slug)}`}
                className="line-clamp-2 text-sm font-semibold text-[var(--pp-text-primary)] underline-offset-2 hover:underline md:text-base"
              >
                {item.title}
              </Link>
              <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{secondaryLabel(item)}</p>
            </div>
            <div className="flex flex-wrap justify-end gap-1.5">
              <StatusBadge label={formatFreeformStatusLabel(item.status)} tone={getFreeformStatusTone(item.status)} />
              {typeof item.confidence === "number" ? <Badge variant="outline">confidence {confidenceLabel(item.confidence)}</Badge> : null}
            </div>
          </div>

          <div className="hidden lg:block">
            <Link
              to={`/papers/${encodeURIComponent(item.slug)}`}
              className="line-clamp-2 text-base font-semibold text-[var(--pp-text-primary)] underline-offset-2 hover:underline"
            >
              {item.title}
            </Link>
            <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{secondaryLabel(item)}</p>
          </div>

          {item.ops_summary ? (
            <div className="mt-3">
              <OperationalStateSummary
                summary={item.ops_summary}
                badgeTestId="paper-note-ops-badge"
                reasonTestId="paper-note-ops-reason"
                compact
              />
            </div>
          ) : null}

          {stateBadges.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {stateBadges.map((badge) => (
                <span
                  key={`${item.slug}-state-${badge.label}`}
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${listBadgeClassName(badge.tone)}`}
                >
                  {badge.label}
                </span>
              ))}
            </div>
          ) : null}

          {insightText.length > 0 ? (
            <div className="mt-3 space-y-1">
              {insightText.map((line) => (
                <p key={`${item.slug}-insight-${line}`} className="text-xs text-[var(--pp-text-secondary)]">
                  {line}
                </p>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{item.note_path}</p>
          )}

          {structuredSignalChips.length > 0 ? (
            <div className="mt-3" data-testid="paper-note-list-signals">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">
                Structured signals
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {structuredSignalChips.map((signal) => (
                  <Badge
                    key={`${item.slug}-structured-signal-${signal.label}`}
                    data-testid="paper-note-list-signal-chip"
                    data-highlighted={signal.matched ? "true" : "false"}
                    variant={signal.matched ? "default" : "muted"}
                  >
                    {signal.label}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-3 flex flex-wrap gap-1.5">
            {visibleTags.map((tag) => (
              <Badge key={`${item.slug}-${tag}`}>{tag}</Badge>
            ))}
            {extraTagCount > 0 ? <Badge variant="muted">+{extraTagCount} tags</Badge> : null}
          </div>
        </div>

        <div className="grid gap-3 rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
          <div className="hidden flex-wrap gap-1.5 lg:flex">
            <StatusBadge label={formatFreeformStatusLabel(item.status)} tone={getFreeformStatusTone(item.status)} />
            {typeof item.confidence === "number" ? <Badge variant="outline">confidence {confidenceLabel(item.confidence)}</Badge> : null}
          </div>

          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-[var(--pp-text-dim)]">Processed</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{formatDate(item.date_processed)}</dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Ops</dt>
              <dd className="mt-1">
                {item.ops_summary ? (
                  <OperationalStateSummary summary={item.ops_summary} compact showActionHint={false} />
                ) : (
                  <span className="text-[var(--pp-text-dim)]">No signal</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Claim Tags</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{item.claim_tags?.length ?? 0}</dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Source</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">
                {item.doi ? "DOI" : item.zotero_link ? "Zotero" : "Vault"}
              </dd>
            </div>
          </dl>

          <p className="truncate text-xs text-[var(--pp-text-dim)]">{item.note_path}</p>
        </div>
      </div>
    </article>
  );
}

export function PaperNotesListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const loadSequence = useRef(0);
  const tagPickerRef = useRef<HTMLDivElement | null>(null);
  const [items, setItems] = useState<PaperNoteSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allStatuses, setAllStatuses] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState(() => searchParams.get("q") ?? "");
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [tagInput, setTagInput] = useState(() => searchParams.get("tag_input") ?? "");
  const [tagMenuOpen, setTagMenuOpen] = useState(false);
  const [highlightedTagIndex, setHighlightedTagIndex] = useState(0);
  const [selectedTags, setSelectedTags] = useState<string[]>(() => parseSelectedTags(searchParams.get("tags")));
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get("status") ?? "all");
  const [structuredOnly, setStructuredOnly] = useState(() => parseStructuredOnly(searchParams.get("structured")));
  const [sortBy, setSortBy] = useState<SortBy>(() => parseSortBy(searchParams.get("sort")));
  const [sortOrder, setSortOrder] = useState<SortOrder>(() => parseSortOrder(searchParams.get("order")));
  const [page, setPage] = useState(() => parsePage(searchParams.get("page")));
  const [pageSize, setPageSize] = useState<PageSize>(() => parsePageSize(searchParams.get("page_size")));

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setQuery(queryInput);
    }, 250);
    return () => window.clearTimeout(timeoutId);
  }, [queryInput]);

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
          structuredOnly,
          sortBy,
          sortOrder,
          page,
          pageSize,
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
  }, [page, pageSize, query, selectedTags, sortBy, sortOrder, statusFilter, structuredOnly]);

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

  useEffect(() => {
    setHighlightedTagIndex(0);
  }, [tagInput, matchedTagHints.length]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!tagPickerRef.current) {
        return;
      }
      if (event.target instanceof Node && !tagPickerRef.current.contains(event.target)) {
        setTagMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, []);

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
    setTagMenuOpen(false);
    setPage(1);
  }

  function removeTag(tag: string) {
    setSelectedTags((current) => current.filter((value) => value !== tag));
    setPage(1);
  }

  function clearTags() {
    setSelectedTags([]);
    setTagInput("");
    setTagMenuOpen(false);
    setPage(1);
  }

  function handleTagInputKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setTagMenuOpen(true);
      if (matchedTagHints.length > 0) {
        setHighlightedTagIndex((current) => (current + 1) % matchedTagHints.length);
      }
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setTagMenuOpen(true);
      if (matchedTagHints.length > 0) {
        setHighlightedTagIndex((current) => (current - 1 + matchedTagHints.length) % matchedTagHints.length);
      }
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const selected = matchedTagHints[highlightedTagIndex] ?? matchedTagHints[0] ?? tagInput;
      addTag(selected);
      return;
    }
    if (event.key === "Escape") {
      setTagMenuOpen(false);
      return;
    }
    if (event.key === "Backspace" && tagInput.trim() === "" && selectedTags.length > 0) {
      removeTag(selectedTags[selectedTags.length - 1]);
    }
  }

  function handleQueryChange(value: string) {
    setQueryInput(value);
    setPage(1);
  }

  function handleStatusChange(value: string) {
    setStatusFilter(value);
    setPage(1);
  }

  function toggleStructuredOnly() {
    setStructuredOnly((current) => !current);
    setPage(1);
  }

  function clearStructuredOnlyFilter() {
    setStructuredOnly(false);
    setPage(1);
  }

  function handleSortByChange(value: SortBy) {
    setSortBy(value);
    setPage(1);
  }

  function handlePageSizeChange(value: string) {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || !isPageSizeOption(parsed)) {
      return;
    }
    setPageSize(parsed);
    setPage(1);
  }

  function toggleSortOrder() {
    setSortOrder((current) => (current === "desc" ? "asc" : "desc"));
    setPage(1);
  }

  function clearAllFilters() {
    setQueryInput("");
    setQuery("");
    setTagInput("");
    setSelectedTags([]);
    setStatusFilter("all");
    setStructuredOnly(false);
    setPage(1);
  }

  function searchWithoutQuotes() {
    const nextQuery = queryInput.replace(/"/g, " ").replace(/\s+/g, " ").trim();
    setQueryInput(nextQuery);
    setQuery(nextQuery);
    setPage(1);
  }

  function applySuggestedSearch(term: string) {
    setQueryInput(term);
    setQuery(term);
    setPage(1);
  }

  useEffect(() => {
    const next = new URLSearchParams();
    const trimmedQuery = queryInput.trim();
    if (trimmedQuery) {
      next.set("q", trimmedQuery);
    }
    if (selectedTags.length > 0) {
      next.set("tags", selectedTags.join(","));
    }
    if (statusFilter !== "all") {
      next.set("status", statusFilter);
    }
    if (structuredOnly) {
      next.set("structured", "1");
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
    if (pageSize !== DEFAULT_PAGE_SIZE) {
      next.set("page_size", String(pageSize));
    }

    const nextValue = next.toString();
    const currentValue = searchParams.toString();
    if (nextValue !== currentValue) {
      setSearchParams(next, { replace: true });
    }
  }, [page, pageSize, queryInput, searchParams, selectedTags, setSearchParams, sortBy, sortOrder, statusFilter, structuredOnly]);

  const pageWindow = useMemo(() => {
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, start + 4);
    const pages: number[] = [];
    for (let current = start; current <= end; current += 1) {
      pages.push(current);
    }
    return pages;
  }, [page, totalPages]);

  const hasActiveFilters = Boolean(queryInput.trim()) || selectedTags.length > 0 || statusFilter !== "all" || structuredOnly;
  const quotedSearch = hasQuotedSearch(queryInput);
  const suggestedSearchTerms = !quotedSearch ? uniqueSearchTerms(queryInput).slice(0, 3) : [];
  const emptyStateTitle = !hasActiveFilters
    ? "No notes are indexed yet."
    : structuredOnly && queryInput.trim()
      ? "No structured notes matched this search."
      : structuredOnly
        ? "No structured notes are available yet."
        : quotedSearch
          ? "No notes matched this exact phrase."
          : "No notes matched the current filters.";
  const emptyStateDetail = !hasActiveFilters
    ? "Add or sync paper notes into the vault to populate this viewer."
    : structuredOnly && queryInput.trim()
      ? "Try turning off Structured only or broadening the search terms."
      : structuredOnly
        ? "Structured notes appear here after a ClaimSet or structured signals are saved."
        : quotedSearch
          ? "Try removing quotes to search by individual terms instead of an exact phrase."
          : "Try fewer terms, a different tag, or clear the current filters.";

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Lattice · Paper Notes Viewer</p>
        <h1 className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">Paper Notes</h1>
        <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
          Obsidian vault note index with search, filtering, and confidence/date sorting.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-6">
          <label className="md:col-span-2">
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Search</span>
            <span className="flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5">
              <Search className="h-3.5 w-3.5 text-[var(--pp-text-dim)]" />
              <input
                value={queryInput}
                onChange={(event) => handleQueryChange(event.target.value)}
                placeholder="title / alias / slug"
                className="w-full border-0 bg-transparent px-2 py-2 text-sm text-[var(--pp-text-primary)] outline-none"
              />
            </span>
          </label>

          <div>
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Tags (multi)</span>
            <div ref={tagPickerRef} className="relative" data-testid="paper-notes-tag-command">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--pp-text-dim)]" />
                <Input
                  value={tagInput}
                  onChange={(event) => {
                    setTagInput(event.target.value);
                    setTagMenuOpen(true);
                  }}
                  onFocus={() => setTagMenuOpen(true)}
                  onKeyDown={handleTagInputKeyDown}
                  placeholder={selectedTags.length > 0 ? "Add another tag" : "Search tags"}
                  className="pl-8"
                  data-testid="paper-notes-tag-input"
                />
              </div>
              {tagMenuOpen ? (
                <Command className="absolute z-20 mt-2 w-full shadow-[var(--pp-shadow)]">
                  <CommandList>
                    {matchedTagHints.length === 0 ? (
                      <CommandEmpty>No matching tags.</CommandEmpty>
                    ) : (
                      <CommandGroup>
                        {matchedTagHints.map((tag, index) => (
                          <CommandItem
                            key={`hint-${tag}`}
                            onMouseDown={(event) => {
                              event.preventDefault();
                              addTag(tag);
                            }}
                            className={index === highlightedTagIndex ? "bg-[var(--pp-surface-muted)] text-[var(--pp-text-primary)]" : ""}
                            data-testid="paper-notes-tag-option"
                          >
                            <span>{tag}</span>
                            {selectedTags.includes(tag) ? <Check className="h-3.5 w-3.5" /> : null}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    )}
                  </CommandList>
                </Command>
              ) : null}
            </div>
            {selectedTags.length > 0 ? (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {selectedTags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => removeTag(tag)}
                    className="inline-flex items-center gap-1 rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-xs text-[var(--pp-accent-text)]"
                    data-testid="paper-notes-selected-tag"
                  >
                    <span>{tag}</span>
                    <X className="h-3 w-3" />
                  </button>
                ))}
                <Button type="button" variant="ghost" size="sm" onClick={clearTags} className="rounded-full">
                  Clear
                </Button>
              </div>
            ) : null}
            <p className="mt-2 text-xs text-[var(--pp-text-dim)]">
              Type to narrow the tag list. Press Enter to add the highlighted tag.
            </p>
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

          <label>
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Page Size</span>
            <select
              value={pageSize}
              onChange={(event) => handlePageSizeChange(event.target.value)}
              className="w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-sm text-[var(--pp-text-primary)]"
            >
              {PAGE_SIZE_OPTIONS.map((value) => (
                <option key={`page-size-${value}`} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={structuredOnly ? "default" : "outline"}
            onClick={toggleStructuredOnly}
            data-testid="paper-notes-structured-toggle"
          >
            Structured only
          </Button>
          <p className="text-xs text-[var(--pp-text-dim)]">ClaimSet or structured signals only.</p>
        </div>

        {hasActiveFilters ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {queryInput.trim() ? (
              <Badge variant="outline">
                q: {queryInput.trim()}
              </Badge>
            ) : null}
            {queryInput.trim() ? <Badge variant="muted">relevance first</Badge> : null}
            {selectedTags.length > 0 ? (
              <Badge>
                tags: {selectedTags.length}
              </Badge>
            ) : null}
            {statusFilter !== "all" ? (
              <Badge variant="outline">
                status: {statusFilter}
              </Badge>
            ) : null}
            {structuredOnly ? <Badge data-testid="paper-notes-active-structured-filter">structured only</Badge> : null}
            <button
              type="button"
              onClick={clearAllFilters}
              className="rounded-full border border-[var(--pp-border)] px-2 py-0.5 text-xs text-[var(--pp-text-dim)]"
            >
              Clear filters
            </button>
          </div>
        ) : null}
      </header>

      <section className="surface-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-dim)]">
          <span>{loading ? "Loading notes..." : `${total} notes · page ${page}/${totalPages} · size ${pageSize}`}</span>
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
              <div
                className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between"
                data-testid="paper-notes-empty-state"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--pp-text-primary)]">{emptyStateTitle}</p>
                  <p className="mt-1 text-xs text-[var(--pp-text-dim)]">{emptyStateDetail}</p>
                </div>
                {hasActiveFilters ? (
                  <div className="flex flex-wrap gap-2">
                    {suggestedSearchTerms.length > 1 ? (
                      <>
                        {suggestedSearchTerms.map((term) => (
                          <Button
                            key={`empty-search-term-${term}`}
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => applySuggestedSearch(term)}
                            data-testid="paper-notes-empty-search-term"
                          >
                            Search {term}
                          </Button>
                        ))}
                      </>
                    ) : null}
                    {quotedSearch ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={searchWithoutQuotes}
                        data-testid="paper-notes-empty-remove-quotes"
                      >
                        Search without quotes
                      </Button>
                    ) : null}
                    {structuredOnly ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={clearStructuredOnlyFilter}
                        data-testid="paper-notes-empty-clear-structured"
                      >
                        Turn off Structured only
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={clearAllFilters}
                      data-testid="paper-notes-empty-clear-filters"
                    >
                      Clear filters
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="max-h-[72vh] space-y-3 overflow-auto p-3">
              {loading
                ? Array.from({ length: 6 }).map((_, idx) => (
                    <article
                      key={`loading-row-${idx}`}
                      className="rounded-xl border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 md:p-4"
                      aria-hidden="true"
                    >
                      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_240px]">
                        <div>
                          <div className="h-5 w-3/4 animate-pulse rounded bg-[var(--pp-surface-muted)]" />
                          <div className="mt-2 h-3 w-2/5 animate-pulse rounded bg-[var(--pp-surface-muted)]" />
                          <div className="mt-3 flex flex-wrap gap-2">
                            <div className="h-5 w-20 animate-pulse rounded-full bg-[var(--pp-surface-muted)]" />
                            <div className="h-5 w-24 animate-pulse rounded-full bg-[var(--pp-surface-muted)]" />
                          </div>
                          <div className="mt-3 h-3 w-5/6 animate-pulse rounded bg-[var(--pp-surface-muted)]" />
                          <div className="mt-3 flex flex-wrap gap-2">
                            <div className="h-5 w-16 animate-pulse rounded-full bg-[var(--pp-surface-muted)]" />
                            <div className="h-5 w-24 animate-pulse rounded-full bg-[var(--pp-surface-muted)]" />
                            <div className="h-5 w-20 animate-pulse rounded-full bg-[var(--pp-surface-muted)]" />
                          </div>
                        </div>
                        <div className="rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                          <div className="flex flex-wrap gap-2">
                            <div className="h-5 w-20 animate-pulse rounded-full bg-[var(--pp-surface)]" />
                            <div className="h-5 w-24 animate-pulse rounded-full bg-[var(--pp-surface)]" />
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-3">
                            <div className="h-9 animate-pulse rounded bg-[var(--pp-surface)]" />
                            <div className="h-9 animate-pulse rounded bg-[var(--pp-surface)]" />
                            <div className="h-9 animate-pulse rounded bg-[var(--pp-surface)]" />
                            <div className="h-9 animate-pulse rounded bg-[var(--pp-surface)]" />
                          </div>
                        </div>
                      </div>
                    </article>
                  ))
                : items.map((item) => <PaperNoteListRow key={item.slug} item={item} query={query} />)}
            </div>

            {total > 0 && !loading ? (
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
