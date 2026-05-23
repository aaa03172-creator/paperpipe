import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, FileSearch, Route, Search, ShieldAlert } from "lucide-react";
import {
  getApiErrorMessage,
  getRecentPaperChoices,
  generateMethodComparison,
  getMethodComparison,
  getMethodComparisonCsvUrl,
  getMethodComparisonIndex,
} from "../lib/api";
import {
  EvidenceLocator,
  MethodComparison,
  MethodComparisonCell,
  MethodComparisonCellStatus,
  MethodComparisonCreateRequest,
  MethodComparisonFieldId,
  MethodComparisonListItem,
  MethodComparisonListResponse,
  MethodComparisonResponse,
  PaperSummary,
} from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { ArtifactHeaderContext } from "../components/ArtifactHeaderContext";

interface ApiLikeResult {
  isMock: boolean;
  reason?: string;
}

interface StatusCounts {
  explicit: number;
  inferred: number;
  missing: number;
  conflict: number;
}

interface EvidenceEntry {
  row: MethodComparison["rows"][number];
  columnLabel: string;
  cell: MethodComparisonCell;
}

interface MethodComparisonFieldOption {
  id: MethodComparisonFieldId;
  label: string;
  help: string;
}

const METHOD_COMPARISON_FIELD_OPTIONS: MethodComparisonFieldOption[] = [
  { id: "intervention", label: "Intervention", help: "What was tested or applied." },
  { id: "comparator", label: "Comparator", help: "Control, placebo, or baseline condition." },
  { id: "duration_or_timepoint", label: "Duration / Timepoint", help: "Treatment window or key measurement timing." },
  { id: "primary_readout", label: "Primary Readout", help: "Main endpoint or assay emphasized in the paper." },
  { id: "sample_size", label: "Sample Size", help: "Reported N or count tied to the compared lane." },
];
const DEFAULT_METHOD_COMPARISON_FIELDS = METHOD_COMPARISON_FIELD_OPTIONS.map((option) => option.id);

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function collectMockReasons(results: ApiLikeResult[]): string[] {
  return Array.from(
    new Set(
      results
        .filter((result) => result.isMock && result.reason)
        .map((result) => result.reason as string),
    ),
  );
}

function matchesComparisonQuery(item: MethodComparisonListItem, query: string): boolean {
  if (!query) {
    return true;
  }
  const haystacks = [item.title, item.comparison_id];
  return haystacks.some((value) => value.toLowerCase().includes(query));
}

function cellStatusLabel(status: MethodComparisonCellStatus): string {
  if (status === "explicit") {
    return "Explicit";
  }
  if (status === "inferred") {
    return "Inferred";
  }
  if (status === "conflict") {
    return "Conflict";
  }
  return "Missing";
}

function cellStatusBadgeClassName(status: MethodComparisonCellStatus): string {
  if (status === "explicit") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (status === "inferred") {
    return "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]";
  }
  if (status === "conflict") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]";
}

function cellSurfaceClassName(status: MethodComparisonCellStatus): string {
  if (status === "explicit") {
    return "border-[var(--pp-status-completed-border)]/60 bg-[var(--pp-status-completed-bg)]/50";
  }
  if (status === "inferred") {
    return "border-[var(--pp-accent-border)]/60 bg-[var(--pp-accent-soft)]/50";
  }
  if (status === "conflict") {
    return "border-[var(--pp-warning-border)]/60 bg-[var(--pp-warning-bg)]/60";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)]";
}

function valueText(value?: string | number | null): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function formatLocator(locator?: EvidenceLocator | null): string {
  if (!locator) {
    return "Locator unavailable";
  }
  const tokens: string[] = [];
  if (typeof locator.page === "number") {
    tokens.push(`p.${locator.page}`);
  }
  if (locator.section) {
    tokens.push(locator.section);
  }
  if (locator.chunk_id) {
    tokens.push(locator.chunk_id);
  }
  if (locator.table_id) {
    tokens.push(`table ${locator.table_id}`);
  }
  if (locator.cell_id) {
    tokens.push(`cell ${locator.cell_id}`);
  }
  if (locator.source) {
    tokens.push(locator.source);
  }
  if (tokens.length === 0) {
    return "Locator unavailable";
  }
  return tokens.join(" · ");
}

function buildStatusCounts(comparison: MethodComparison | null): StatusCounts {
  const counts: StatusCounts = { explicit: 0, inferred: 0, missing: 0, conflict: 0 };
  if (!comparison) {
    return counts;
  }
  for (const row of comparison.rows) {
    for (const cell of row.cells) {
      counts[cell.status] += 1;
    }
  }
  return counts;
}

function buildEvidenceEntries(comparison: MethodComparison | null): EvidenceEntry[] {
  if (!comparison) {
    return [];
  }

  const columnLabels = new Map(comparison.columns.map((column) => [column.field_id, column.label]));
  const entries: EvidenceEntry[] = [];

  for (const row of comparison.rows) {
    for (const cell of row.cells) {
      if (cell.status === "missing" && cell.evidence_refs.length === 0 && !cell.note) {
        continue;
      }
      entries.push({
        row,
        columnLabel: columnLabels.get(cell.field_id) ?? cell.field_id,
        cell,
      });
    }
  }

  return entries;
}

function parsePaperIdsInput(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[\n,]+/)
        .map((token) => token.trim())
        .filter((token) => token.length > 0),
    ),
  );
}

function recentPaperChoices(papers: PaperSummary[]): PaperSummary[] {
  return papers
    .filter((paper) => paper.paper_id.trim().length > 0 && paper.title.trim().length > 0)
    .slice(0, 6);
}

function buildMethodHeaderWhenToUse(routeComparisonId?: string): string {
  if (routeComparisonId) {
    return "Use this snapshot when you need a reviewable methods grid before CSV export, note handoff, or meeting discussion.";
  }
  return "Use this lane when you want to compare claimset-backed method fields across papers before exporting or carrying the grid into notes.";
}

function buildMethodHeaderDerivedFrom(comparison: MethodComparison | null): string {
  if (!comparison) {
    return "Derived from saved paper claimsets after you choose the papers and fields to compare.";
  }
  return `Derived from ${comparison.paper_ids.length} paper${comparison.paper_ids.length === 1 ? "" : "s"} and ${comparison.columns.length} claimset-backed field${comparison.columns.length === 1 ? "" : "s"} in the saved snapshot.`;
}

function buildMethodHeaderContinuity(comparison: MethodComparison | null): string {
  if (!comparison) {
    return "Canonical evidence lives upstream in the linked paper notes behind each compared row. Open note from the grid before reusing this comparison downstream.";
  }
  const noteBackedRows = comparison.rows.filter((row) => Boolean(row.paper_slug)).length;
  if (noteBackedRows > 0) {
    return `Canonical evidence lives upstream in ${noteBackedRows} linked paper note${noteBackedRows === 1 ? "" : "s"} behind this grid. Open note from the compared rows before exporting or reusing downstream.`;
  }
  return "Canonical evidence lives upstream in linked paper review context. Re-open source notes from compared rows before exporting or reusing this comparison downstream.";
}

function buildMethodReviewPriorityCopy(
  warningsCount: number,
  statusCounts: StatusCounts,
): { tone: "attention" | "clear"; title: string; detail: string } {
  if (warningsCount > 0 || statusCounts.conflict > 0) {
    return {
      tone: "attention",
      title: "Review warnings and conflict-backed cells before export.",
      detail: "Use the comparison grid and evidence trace first. Re-open compared notes from the grid when canonical paper context needs to be checked.",
    };
  }
  if (statusCounts.missing > 0) {
    return {
      tone: "attention",
      title: "Missing cells are explicit gaps, not safe defaults.",
      detail: "If those fields matter for downstream reuse, re-open the compared notes before exporting this snapshot.",
    };
  }
  return {
    tone: "clear",
    title: "No warnings or unresolved cells are saved in this snapshot.",
    detail: "Export is likely fine after a quick row-level note spot-check when you need canonical paper context.",
  };
}

export function MethodComparisonPage() {
  const navigate = useNavigate();
  const { comparisonId: routeComparisonId } = useParams<{ comparisonId?: string }>();
  const [indexResponse, setIndexResponse] = useState<MethodComparisonListResponse | null>(null);
  const [comparisonResponse, setComparisonResponse] = useState<MethodComparisonResponse | null>(null);
  const [recentPapers, setRecentPapers] = useState<PaperSummary[]>([]);
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [createPaperIdsInput, setCreatePaperIdsInput] = useState("");
  const [createTitle, setCreateTitle] = useState("");
  const [selectedFieldIds, setSelectedFieldIds] = useState<MethodComparisonFieldId[]>(DEFAULT_METHOD_COMPARISON_FIELDS);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creatingComparison, setCreatingComparison] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockReasons, setMockReasons] = useState<string[]>([]);

  useEffect(() => {
    const titleSuffix = routeComparisonId ? ` ${routeComparisonId}` : "";
    document.title = `Method Comparisons${titleSuffix} | Lattice`;
  }, [routeComparisonId]);

  useEffect(() => {
    let mounted = true;

    async function loadIndex() {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setComparisonResponse(null);
      setRecentPapers([]);
      setMockReasons([]);

      try {
        const [comparisonIndexResult, papersResult] = await Promise.all([
          getMethodComparisonIndex(),
          getRecentPaperChoices(),
        ]);
        if (!mounted) {
          return;
        }
        setIndexResponse(comparisonIndexResult.data);
        setRecentPapers(recentPaperChoices(papersResult.data));
        setMockReasons(collectMockReasons([comparisonIndexResult, papersResult]));
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(getApiErrorMessage(loadError));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    async function loadComparison(comparisonId: string) {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setComparisonResponse(null);
      setMockReasons([]);

      try {
        const result = await getMethodComparison(comparisonId);
        if (!mounted) {
          return;
        }
        setComparisonResponse(result.data);
        setMockReasons(collectMockReasons([result]));
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(getApiErrorMessage(loadError));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    if (routeComparisonId) {
      void loadComparison(routeComparisonId);
      return () => {
        mounted = false;
      };
    }

    void loadIndex();
    return () => {
      mounted = false;
    };
  }, [routeComparisonId]);

  const normalizedSearchQuery = indexSearchQuery.trim().toLowerCase();
  const filteredItems = useMemo(
    () => (indexResponse?.items ?? []).filter((item) => matchesComparisonQuery(item, normalizedSearchQuery)),
    [indexResponse, normalizedSearchQuery],
  );
  const comparison = comparisonResponse?.comparison ?? null;
  const statusCounts = useMemo(() => buildStatusCounts(comparison), [comparison]);
  const evidenceEntries = useMemo(() => buildEvidenceEntries(comparison), [comparison]);
  const warningsCount = comparison?.warnings.length ?? 0;
  const reviewPriority = useMemo(
    () => buildMethodReviewPriorityCopy(warningsCount, statusCounts),
    [statusCounts, warningsCount],
  );
  const selectedPaperIds = useMemo(() => parsePaperIdsInput(createPaperIdsInput), [createPaperIdsInput]);
  const csvHref = useMemo(() => {
    if (!routeComparisonId) {
      return null;
    }
    if (mockReasons.length > 0) {
      if (!comparisonResponse?.csv_text) {
        return null;
      }
      return `data:text/csv;charset=utf-8,${encodeURIComponent(comparisonResponse.csv_text)}`;
    }
    return getMethodComparisonCsvUrl(routeComparisonId);
  }, [comparisonResponse, mockReasons, routeComparisonId]);
  const csvDownloadName = routeComparisonId ? `${routeComparisonId}.csv` : "method-comparison.csv";

  function toggleField(fieldId: MethodComparisonFieldId) {
    setSelectedFieldIds((prev) =>
      prev.includes(fieldId) ? prev.filter((item) => item !== fieldId) : [...prev, fieldId],
    );
  }

  function toggleCreatePaperId(paperId: string) {
    setCreateError(null);
    setCreatePaperIdsInput((prev) => {
      const nextIds = parsePaperIdsInput(prev);
      if (nextIds.includes(paperId)) {
        return nextIds.filter((item) => item !== paperId).join("\n");
      }
      return [...nextIds, paperId].join("\n");
    });
  }

  async function handleGenerateComparison(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const paperIds = parsePaperIdsInput(createPaperIdsInput);
    const title = createTitle.trim();

    if (paperIds.length === 0) {
      setCreateError("Enter at least one paper ID to start a comparison.");
      return;
    }
    if (selectedFieldIds.length === 0) {
      setCreateError("Choose at least one field to compare.");
      return;
    }

    setCreatingComparison(true);
    setCreateError(null);
    try {
      const payload: MethodComparisonCreateRequest = {
        title: title || undefined,
        paper_ids: paperIds,
        field_ids: selectedFieldIds,
      };
      const result = await generateMethodComparison(payload);
      navigate(`/method-comparisons/${encodeURIComponent(result.data.comparison.comparison_id)}`);
    } catch (actionError) {
      setCreateError(getApiErrorMessage(actionError));
    } finally {
      setCreatingComparison(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <Route className="h-3.5 w-3.5" />
              Method comparison review
            </div>
            <h1 className="mt-2 text-lg font-semibold text-[var(--pp-text-primary)]">
              {comparison?.title ?? "Method Comparisons"}
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              {routeComparisonId
                ? "Review saved comparison snapshots before export, note handoff, or downstream discussion."
                : "Open saved comparison snapshots or start a new comparison from paper IDs before export or note handoff."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockReasons.length > 0 ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            {routeComparisonId ? (
              <Button variant="outline" size="sm" onClick={() => navigate("/method-comparisons")}>
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to index
              </Button>
            ) : null}
            {csvHref ? (
              <a
                href={csvHref}
                download={csvDownloadName}
                title="Review priority and evidence trace before exporting."
                className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
              >
                Export CSV
              </a>
            ) : null}
            <Link
              to="/papers"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Paper Notes
            </Link>
            <Link
              to="/meeting-packs"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Meeting Packs
            </Link>
            <Link
              to="/image-evidence"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Image Evidence
            </Link>
          </div>
        </div>
        <ArtifactHeaderContext
          testId="method-comparison-header-context"
          emphasizeFirstItem={Boolean(routeComparisonId)}
          items={[
            routeComparisonId ? { label: "Derived artifact", value: buildMethodHeaderContinuity(comparison) } : null,
            { label: "When to use", value: buildMethodHeaderWhenToUse(routeComparisonId) },
            { label: "Derived from", value: buildMethodHeaderDerivedFrom(comparison) },
          ].filter((item): item is { label: string; value: string } => item !== null)}
        />
        {mockReasons.length > 0 ? (
          <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
      </header>

      {routeComparisonId ? (
        <main className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            {loading && !comparison ? (
              <Card>
                <CardContent className="p-4 text-sm text-[var(--pp-text-dim)]">Loading method comparison…</CardContent>
              </Card>
            ) : null}

            {error && !comparison ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-[var(--pp-status-failed-text)]">
                    <ShieldAlert className="h-4 w-4" />
                    Comparison unavailable
                  </CardTitle>
                  <CardDescription>The viewer could not load this saved comparison snapshot.</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                    {error}
                  </p>
                </CardContent>
              </Card>
            ) : null}

            {comparison ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Comparison Grid</CardTitle>
                    <CardDescription>
                      Non-missing cells are evidence-linked. Conflict cells should be treated as review-required, not reusable truth.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline" className={cellStatusBadgeClassName("explicit")}>
                        Explicit {statusCounts.explicit}
                      </Badge>
                      <Badge variant="outline" className={cellStatusBadgeClassName("inferred")}>
                        Inferred {statusCounts.inferred}
                      </Badge>
                      <Badge variant="outline" className={cellStatusBadgeClassName("conflict")}>
                        Conflict {statusCounts.conflict}
                      </Badge>
                      <Badge variant="outline" className={cellStatusBadgeClassName("missing")}>
                        Missing {statusCounts.missing}
                      </Badge>
                    </div>

                    <div className="overflow-x-auto rounded-md border border-[var(--pp-border)]">
                      <table className="w-full min-w-[980px] border-collapse text-sm">
                        <thead className="bg-[var(--pp-surface-muted)] text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">
                          <tr>
                            <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Paper</th>
                            {comparison.columns.map((column) => (
                              <th key={column.field_id} className="border-b border-[var(--pp-border)] px-3 py-2 text-left">
                                {column.label}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {comparison.rows.map((row) => {
                            const cellsByField = new Map(row.cells.map((cell) => [cell.field_id, cell]));
                            return (
                              <tr key={row.paper_id} className="align-top bg-[var(--pp-surface-raised)]">
                                <td className="border-b border-[var(--pp-border)] px-3 py-3">
                                  <div className="min-w-[220px]">
                                    <div className="font-medium text-[var(--pp-text-primary)]">{row.title}</div>
                                    <div className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">{row.paper_id}</div>
                                    {row.paper_slug ? (
                                      <Link
                                        to={`/papers/${encodeURIComponent(row.paper_slug)}`}
                                        className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--pp-accent-text)] underline-offset-2 hover:underline"
                                      >
                                        Open note
                                        <ArrowRight className="h-3 w-3" />
                                      </Link>
                                    ) : null}
                                  </div>
                                </td>
                                {comparison.columns.map((column) => {
                                  const cell = cellsByField.get(column.field_id) ?? {
                                    field_id: column.field_id,
                                    value: null,
                                    normalized_value: null,
                                    status: "missing" as const,
                                    note: null,
                                    evidence_refs: [],
                                  };
                                  return (
                                    <td key={column.field_id} className="border-b border-[var(--pp-border)] px-3 py-3">
                                      <div
                                        className={[
                                          "rounded-md border p-2.5",
                                          cellSurfaceClassName(cell.status),
                                        ].join(" ")}
                                      >
                                        <div className="flex flex-wrap items-center gap-2">
                                          <Badge variant="outline" className={cellStatusBadgeClassName(cell.status)}>
                                            {cellStatusLabel(cell.status)}
                                          </Badge>
                                          <span className="text-xs text-[var(--pp-text-dim)]">
                                            {cell.evidence_refs.length} ref{cell.evidence_refs.length === 1 ? "" : "s"}
                                          </span>
                                        </div>
                                        <p className="mt-2 text-sm font-medium text-[var(--pp-text-primary)]">
                                          {valueText(cell.value)}
                                        </p>
                                        {cell.note ? (
                                          <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{cell.note}</p>
                                        ) : null}
                                      </div>
                                    </td>
                                  );
                                })}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Evidence Trace</CardTitle>
                    <CardDescription>Cell-level lineage is grouped by paper and field so review stays tied to the comparison grid.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {evidenceEntries.length === 0 ? (
                      <p className="text-sm text-[var(--pp-text-dim)]">No evidence-linked or review-flagged cells are available.</p>
                    ) : (
                      evidenceEntries.map((entry, index) => (
                        <article
                          key={`${entry.row.paper_id}-${entry.cell.field_id}-${index}`}
                          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <div className="text-sm font-medium text-[var(--pp-text-primary)]">{entry.columnLabel}</div>
                              <div className="mt-1 text-xs text-[var(--pp-text-dim)]">
                                {entry.row.title} · {entry.row.paper_id}
                              </div>
                            </div>
                            <Badge variant="outline" className={cellStatusBadgeClassName(entry.cell.status)}>
                              {cellStatusLabel(entry.cell.status)}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm text-[var(--pp-text-primary)]">{valueText(entry.cell.value)}</p>
                          {entry.cell.note ? (
                            <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{entry.cell.note}</p>
                          ) : null}
                          {entry.cell.evidence_refs.length > 0 ? (
                            <div className="mt-3 space-y-2">
                              {entry.cell.evidence_refs.map((ref, refIndex) => (
                                <div
                                  key={`${ref.paper_slug}-${ref.evidence_id ?? ref.claim_id ?? refIndex}`}
                                  className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-2.5"
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Badge variant="muted">{ref.paper_slug}</Badge>
                                    {ref.claim_id ? <Badge variant="outline">claim {ref.claim_id}</Badge> : null}
                                    {ref.evidence_id ? <Badge variant="outline">evidence {ref.evidence_id}</Badge> : null}
                                  </div>
                                  <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{formatLocator(ref.locator)}</p>
                                  {ref.run_id ? (
                                    <p className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">{ref.run_id}</p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </article>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Rendered Markdown</CardTitle>
                    <CardDescription>Saved markdown preview for the current comparison artifact bundle.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <pre className="overflow-x-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                      {comparisonResponse?.markdown ?? ""}
                    </pre>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </div>

          <div className="space-y-4">
            <Card data-testid="method-comparison-review-priority-card">
              <CardHeader>
                <CardTitle>Review priority</CardTitle>
                <CardDescription>Decide whether this snapshot is ready for export, or whether warnings and cell gaps need review first.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div
                  data-testid="method-comparison-review-priority"
                  className={`rounded-md border p-3 text-sm ${
                    reviewPriority.tone === "attention"
                      ? "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
                      : "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                  }`}
                >
                  <p className="font-medium">{reviewPriority.title}</p>
                  <p className="mt-2">{reviewPriority.detail}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className={warningsCount > 0 ? cellStatusBadgeClassName("conflict") : cellStatusBadgeClassName("explicit")}>
                    Warnings {warningsCount}
                  </Badge>
                  <Badge variant="outline" className={cellStatusBadgeClassName("conflict")}>
                    Conflict {statusCounts.conflict}
                  </Badge>
                  <Badge variant="outline" className={cellStatusBadgeClassName("missing")}>
                    Missing {statusCounts.missing}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Warnings</CardTitle>
                <CardDescription>Warnings should be read before reusing CSV or markdown downstream.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {warningsCount > 0 ? (
                  comparison?.warnings.map((warning) => (
                    <div
                      key={warning}
                      className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3 text-sm text-[var(--pp-warning-text)]"
                    >
                      {warning}
                    </div>
                  ))
                ) : (
                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                    No warnings saved for this comparison.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Snapshot</CardTitle>
                <CardDescription>Current saved artifact metadata and review counts.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm text-[var(--pp-text-secondary)]">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Created</div>
                  <div className="mt-1">{formatDateTime(comparison?.created_at)}</div>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Generated</div>
                  <div className="mt-1">{formatDateTime(comparison?.generated_at)}</div>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Coverage</div>
                  <div className="mt-1">
                    {(comparison?.paper_ids.length ?? 0)} papers · {(comparison?.columns.length ?? 0)} fields
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Source Discipline</CardTitle>
                <CardDescription>Comparison generation stays bounded to the current source-priority contract.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Source priority</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(comparison?.source_summary.source_priority ?? []).map((source) => (
                      <Badge key={source} variant="outline">
                        {source}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Lane note</div>
                  <p className="mt-2">{comparison?.source_summary.note ?? "No source note saved."}</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Field Registry</CardTitle>
                <CardDescription>The viewer preserves backend column order from the saved comparison artifact.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {(comparison?.columns ?? []).map((column) => (
                  <div
                    key={column.field_id}
                    className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-[var(--pp-text-primary)]">{column.label}</div>
                      <Badge variant="outline">{column.value_kind}</Badge>
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">{column.field_id}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </main>
      ) : (
        <main className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Search comparisons
                </CardTitle>
                <CardDescription>Search saved derived comparisons by title or artifact id before opening a review snapshot.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <label className="block">
                  <span className="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Search
                  </span>
                  <Input
                    value={indexSearchQuery}
                    onChange={(event) => setIndexSearchQuery(event.target.value)}
                    placeholder="Search title or comparison id"
                  />
                </label>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  {(indexResponse?.total ?? 0) > 0
                    ? `${indexResponse?.total ?? 0} saved derived comparison${(indexResponse?.total ?? 0) === 1 ? "" : "s"}.`
                    : "No saved derived comparisons yet. Start one from paper IDs below, then review fields and evidence here."}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Start a new comparison</CardTitle>
                <CardDescription>
                  Create one derived comparison from saved claimset-backed fields, then land directly in the review surface.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs text-[var(--pp-text-secondary)]">
                  Comparisons stay downstream of saved note review. Re-open source notes before exporting or reusing downstream.
                </div>
                <form onSubmit={handleGenerateComparison} className="space-y-3">
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Papers to compare
                    </span>
                    <textarea
                      value={createPaperIdsInput}
                      onChange={(event) => setCreatePaperIdsInput(event.target.value)}
                      placeholder={"paper-e2e-methodcmp-alpha-001\npaper-e2e-methodcmp-beta-001"}
                      aria-label="Method comparison paper ids"
                      className="min-h-[112px] w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)] outline-none placeholder:text-[var(--pp-text-dim)] focus:border-[var(--pp-accent-border)]"
                    />
                    <span className="mt-2 block text-xs text-[var(--pp-text-dim)]">
                      Paste paper IDs one per line, or pick from recent papers below.
                    </span>
                  </label>

                  {recentPapers.length > 0 ? (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        Recent papers
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {recentPapers.map((paper) => {
                          const selected = selectedPaperIds.includes(paper.paper_id);
                          return (
                            <Button
                              key={paper.paper_id}
                              type="button"
                              size="sm"
                              variant={selected ? "default" : "outline"}
                              className="h-auto max-w-full items-start justify-start px-3 py-2 text-left"
                              onClick={() => toggleCreatePaperId(paper.paper_id)}
                            >
                              <span className="flex min-w-0 flex-col">
                                <span className="truncate text-xs font-medium">{paper.title}</span>
                                <span className="truncate font-mono text-[11px] opacity-80">{paper.paper_id}</span>
                              </span>
                            </Button>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Comparison title
                    </span>
                    <Input
                      value={createTitle}
                      onChange={(event) => setCreateTitle(event.target.value)}
                      placeholder="Optional. A comparison title will be generated if left blank."
                      aria-label="Method comparison title"
                    />
                  </label>

                  <div>
                    <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Fields
                    </span>
                    <div className="space-y-2">
                      {METHOD_COMPARISON_FIELD_OPTIONS.map((option) => {
                        const checked = selectedFieldIds.includes(option.id);
                        return (
                          <label
                            key={option.id}
                            className="flex cursor-pointer items-start gap-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleField(option.id)}
                              className="mt-0.5 h-4 w-4 rounded border-[var(--pp-border)] bg-[var(--pp-surface)]"
                            />
                            <span>
                              <span className="block text-sm font-medium text-[var(--pp-text-primary)]">{option.label}</span>
                              <span className="mt-1 block text-xs text-[var(--pp-text-secondary)]">{option.help}</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    Use paper IDs from Paper Notes or workbench URLs. The comparison generator reads saved claimset-backed fields for each paper and opens the saved snapshot right away.
                  </p>

                  {createError ? (
                    <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                      {createError}
                    </p>
                  ) : null}

                  <Button
                    type="submit"
                    disabled={creatingComparison || parsePaperIdsInput(createPaperIdsInput).length === 0 || selectedFieldIds.length === 0}
                  >
                    {creatingComparison ? "Creating comparison…" : "Create comparison"}
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileSearch className="h-4 w-4" />
                  Saved comparison snapshots
                </CardTitle>
                <CardDescription>Each card summarizes derived scope, warning load, and last generation timestamp before downstream reuse.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
              {loading ? (
                <p className="text-sm text-[var(--pp-text-dim)]">Loading comparison index…</p>
              ) : null}
              {error ? (
                <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                  {error}
                </p>
              ) : null}
              {!loading && !error && filteredItems.length === 0 ? (
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  {(indexResponse?.total ?? 0) > 0
                    ? "No comparisons match the current search."
                    : "No saved derived comparisons yet. Save one to compare papers and evidence here."}
                </div>
              ) : null}
              {!loading && !error
                ? filteredItems.map((item) => (
                    <article
                      key={item.comparison_id}
                      className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-[var(--pp-text-primary)]">{item.title}</div>
                          <div className="mt-1 break-all font-mono text-[11px] text-[var(--pp-text-dim)]">
                            {item.comparison_id}
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className={
                            item.warning_count > 0
                              ? "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
                              : "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                          }
                        >
                          {item.warning_count > 0 ? `${item.warning_count} warning` : "Clean snapshot"}
                        </Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-[var(--pp-text-dim)] sm:grid-cols-2">
                        <div>Created: {formatDateTime(item.created_at)}</div>
                        <div>Generated: {formatDateTime(item.generated_at)}</div>
                        <div>{item.paper_count} papers</div>
                        <div>{item.field_count} fields</div>
                      </div>
                      <div className="mt-3">
                        <Button size="sm" onClick={() => navigate(`/method-comparisons/${encodeURIComponent(item.comparison_id)}`)}>
                          Open comparison
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </article>
                  ))
                : null}
            </CardContent>
          </Card>
        </main>
      )}
    </div>
  );
}
