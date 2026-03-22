import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, FileSearch, Route, Search, ShieldAlert } from "lucide-react";
import {
  getApiErrorMessage,
  getChartPack,
  getChartPackDataCsvUrl,
  getChartPackIndex,
  getChartPackSpecUrl,
} from "../lib/api";
import { ChartDefinition, ChartPackListItem, ChartPackListResponse, ChartPackResponse } from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";

interface ApiLikeResult {
  isMock: boolean;
  reason?: string;
}

interface CsvPreview {
  header: string[];
  rows: string[][];
}

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

function matchesChartPackQuery(item: ChartPackListItem, query: string): boolean {
  if (!query) {
    return true;
  }
  const haystacks = [item.title, item.chart_pack_id];
  return haystacks.some((value) => value.toLowerCase().includes(query));
}

function warningBadgeClassName(count: number): string {
  if (count > 0) {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
}

function warningToneClassName(severity: "info" | "warning" | "error"): string {
  if (severity === "warning" || severity === "error") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)]";
}

function templateLabel(templateId: ChartDefinition["template_id"]): string {
  if (templateId === "stats_check_status_counts") {
    return "Stats check status counts";
  }
  if (templateId === "reported_vs_computed_p_scatter") {
    return "Reported vs computed p scatter";
  }
  if (templateId === "table_numeric_bar") {
    return "Numeric table bar chart";
  }
  return "Numeric table line chart";
}

function describeSourceRef(chart: ChartDefinition): string {
  const { source_ref: sourceRef } = chart;
  const parts = [sourceRef.source_kind, sourceRef.paper_id, sourceRef.run_id];
  if (sourceRef.table_id) {
    parts.push(sourceRef.table_id);
  }
  return parts.join(" / ");
}

function buildMockDownloadHref(content: string, mimeType: string): string {
  return `data:${mimeType};charset=utf-8,${encodeURIComponent(content)}`;
}

function parseCsvText(csvText: string): CsvPreview {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let inQuotes = false;

  for (let index = 0; index < csvText.length; index += 1) {
    const char = csvText[index];
    const nextChar = csvText[index + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        currentCell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && char === ",") {
      currentRow.push(currentCell);
      currentCell = "";
      continue;
    }

    if (!inQuotes && (char === "\n" || char === "\r")) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      currentRow.push(currentCell);
      rows.push(currentRow);
      currentRow = [];
      currentCell = "";
      continue;
    }

    currentCell += char;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    currentRow.push(currentCell);
    rows.push(currentRow);
  }

  const [header = [], ...body] = rows;
  return { header, rows: body };
}

function specSummary(specPayload: Record<string, unknown> | undefined): string {
  if (!specPayload) {
    return "Spec unavailable";
  }
  const mark = typeof specPayload.mark === "string" ? specPayload.mark : "unknown";
  const encoding = specPayload.encoding && typeof specPayload.encoding === "object"
    ? (specPayload.encoding as Record<string, unknown>)
    : null;
  const x = typeof encoding?.x === "string" ? encoding.x : "?";
  const y = typeof encoding?.y === "string" ? encoding.y : "?";
  const rowCount = typeof specPayload.row_count === "number" ? specPayload.row_count : null;
  const rowCountText = rowCount === null ? "row count unknown" : `${rowCount} row${rowCount === 1 ? "" : "s"}`;
  return `${mark} · x=${x} · y=${y} · ${rowCountText}`;
}

export function ChartPackPage() {
  const navigate = useNavigate();
  const { chartPackId: routeChartPackId } = useParams<{ chartPackId?: string }>();
  const [indexResponse, setIndexResponse] = useState<ChartPackListResponse | null>(null);
  const [packResponse, setPackResponse] = useState<ChartPackResponse | null>(null);
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockReasons, setMockReasons] = useState<string[]>([]);

  useEffect(() => {
    const titleSuffix = routeChartPackId ? ` ${routeChartPackId}` : "";
    document.title = `Chart Packs${titleSuffix} | Lattice`;
  }, [routeChartPackId]);

  useEffect(() => {
    let mounted = true;

    async function loadIndex() {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setPackResponse(null);
      setMockReasons([]);

      try {
        const result = await getChartPackIndex();
        if (!mounted) {
          return;
        }
        setIndexResponse(result.data);
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

    async function loadPack(chartPackId: string) {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setPackResponse(null);
      setMockReasons([]);

      try {
        const result = await getChartPack(chartPackId);
        if (!mounted) {
          return;
        }
        setPackResponse(result.data);
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

    if (routeChartPackId) {
      void loadPack(routeChartPackId);
    } else {
      void loadIndex();
    }

    return () => {
      mounted = false;
    };
  }, [routeChartPackId]);

  const normalizedSearchQuery = indexSearchQuery.trim().toLowerCase();
  const filteredItems = useMemo(
    () => (indexResponse?.items ?? []).filter((item) => matchesChartPackQuery(item, normalizedSearchQuery)),
    [indexResponse, normalizedSearchQuery],
  );
  const chartPack = packResponse?.chart_pack ?? null;
  const previewByChartId = useMemo(() => {
    const previews = new Map<string, CsvPreview>();
    for (const [chartId, csvText] of Object.entries(packResponse?.data_snapshots ?? {})) {
      previews.set(chartId, parseCsvText(csvText));
    }
    return previews;
  }, [packResponse]);

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <Route className="h-3.5 w-3.5" />
              Chart pack review
            </div>
            <h1 className="mt-2 text-lg font-semibold text-[var(--pp-text-primary)]">
              {chartPack?.title ?? "Chart Packs"}
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Review saved chart-pack artifacts before export or downstream reuse.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockReasons.length > 0 ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            {routeChartPackId ? (
              <Button variant="outline" size="sm" onClick={() => navigate("/chart-packs")}>
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to index
              </Button>
            ) : null}
            <Link
              to="/method-comparisons"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Method Comparisons
            </Link>
            <Link
              to="/image-evidence"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Image Evidence
            </Link>
            <Link
              to="/meeting-packs"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Meeting Packs
            </Link>
          </div>
        </div>
        {mockReasons.length > 0 ? (
          <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
      </header>

      {routeChartPackId ? (
        <main className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            {loading && !chartPack ? (
              <Card>
                <CardContent className="p-4 text-sm text-[var(--pp-text-dim)]">Loading chart pack…</CardContent>
              </Card>
            ) : null}

            {error && !chartPack ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-[var(--pp-status-failed-text)]">
                    <ShieldAlert className="h-4 w-4" />
                    Chart pack unavailable
                  </CardTitle>
                  <CardDescription>The viewer could not load this saved chart pack.</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                    {error}
                  </p>
                </CardContent>
              </Card>
            ) : null}

            {chartPack ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Charts</CardTitle>
                    <CardDescription>
                      Each chart keeps source lineage, transforms, warning state, and pack-relative CSV/spec artifacts together.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {chartPack.charts.map((chart) => {
                      const preview = previewByChartId.get(chart.chart_id) ?? { header: [], rows: [] };
                      const specPayload = packResponse?.specs[chart.chart_id];
                      const csvText = packResponse?.data_snapshots[chart.chart_id] ?? "";
                      const dataHref = mockReasons.length > 0
                        ? buildMockDownloadHref(csvText, "text/csv")
                        : getChartPackDataCsvUrl(chartPack.chart_pack_id, chart.chart_id);
                      const specHref = mockReasons.length > 0
                        ? buildMockDownloadHref(JSON.stringify(specPayload ?? {}, null, 2), "application/json")
                        : getChartPackSpecUrl(chartPack.chart_pack_id, chart.chart_id);

                      return (
                        <article
                          key={chart.chart_id}
                          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-[var(--pp-text-primary)]">{chart.title}</div>
                              <div className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">{chart.chart_id}</div>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <Badge variant="outline">{templateLabel(chart.template_id)}</Badge>
                              <Badge variant="outline" className={warningBadgeClassName(chart.warnings.length)}>
                                {chart.warnings.length > 0 ? `${chart.warnings.length} warning` : "Clean chart"}
                              </Badge>
                            </div>
                          </div>

                          <div className="mt-3 grid gap-2 text-xs text-[var(--pp-text-dim)] sm:grid-cols-2">
                            <div>Source: {describeSourceRef(chart)}</div>
                            <div>Spec: {specSummary(specPayload)}</div>
                            <div>CSV: {chart.data_snapshot_ref?.path ?? "Unavailable"}</div>
                            <div>Spec JSON: {chart.spec_ref?.path ?? "Unavailable"}</div>
                          </div>

                          <div className="mt-3 flex flex-wrap gap-2">
                            <a
                              href={dataHref}
                              download={`${chart.chart_id}.csv`}
                              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 text-xs font-medium text-[var(--pp-accent-text)]"
                            >
                              Export CSV
                            </a>
                            <a
                              href={specHref}
                              download={`${chart.chart_id}.json`}
                              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 text-xs text-[var(--pp-text-secondary)]"
                            >
                              Open spec JSON
                            </a>
                          </div>

                          {chart.warnings.length > 0 ? (
                            <div className="mt-3 space-y-2">
                              {chart.warnings.map((warning) => (
                                <div
                                  key={`${chart.chart_id}-${warning.code}-${warning.message}`}
                                  className={`rounded-md border p-3 text-sm ${warningToneClassName(warning.severity)}`}
                                >
                                  <div className="text-[11px] font-semibold uppercase tracking-wide">{warning.code}</div>
                                  <p className="mt-1">{warning.message}</p>
                                </div>
                              ))}
                            </div>
                          ) : null}

                          {chart.transforms.length > 0 ? (
                            <div className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3">
                              <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                                Transforms
                              </div>
                              <div className="mt-2 space-y-2">
                                {chart.transforms.map((transform, index) => (
                                  <div key={`${chart.chart_id}-${transform.kind}-${index}`} className="text-sm text-[var(--pp-text-secondary)]">
                                    <Badge variant="outline">{transform.kind}</Badge>
                                    <span className="ml-2">{transform.description}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}

                          <div className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3">
                            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                              Snapshot preview
                            </div>
                            {preview.header.length > 0 ? (
                              <div className="mt-2 overflow-x-auto rounded-md border border-[var(--pp-border)]">
                                <table className="w-full min-w-[420px] border-collapse text-sm">
                                  <thead className="bg-[var(--pp-surface-muted)] text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">
                                    <tr>
                                      {preview.header.map((cell) => (
                                        <th key={cell} className="border-b border-[var(--pp-border)] px-3 py-2 text-left">
                                          {cell}
                                        </th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {preview.rows.slice(0, 5).map((row, rowIndex) => (
                                      <tr key={`${chart.chart_id}-${rowIndex}`} className="bg-[var(--pp-surface-raised)]">
                                        {preview.header.map((_, cellIndex) => (
                                          <td
                                            key={`${chart.chart_id}-${rowIndex}-${cellIndex}`}
                                            className="border-b border-[var(--pp-border)] px-3 py-2 text-[var(--pp-text-secondary)]"
                                          >
                                            {row[cellIndex] || "-"}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-[var(--pp-text-dim)]">No preview rows saved for this snapshot.</p>
                            )}
                          </div>
                        </article>
                      );
                    })}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Rendered Markdown</CardTitle>
                    <CardDescription>Saved markdown preview for the current chart pack bundle.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <pre className="overflow-x-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                      {packResponse?.markdown ?? ""}
                    </pre>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </div>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Snapshot</CardTitle>
                <CardDescription>Current saved artifact metadata and bounded storage context.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm text-[var(--pp-text-secondary)]">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Created</div>
                  <div className="mt-1">{formatDateTime(chartPack?.created_at)}</div>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Generated</div>
                  <div className="mt-1">{formatDateTime(chartPack?.generated_at)}</div>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Coverage</div>
                  <div className="mt-1">
                    {(chartPack?.charts.length ?? 0)} charts · {(chartPack?.source_items.length ?? 0)} source refs
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Caution Notes</CardTitle>
                <CardDescription>Read these notes before reusing CSV or spec payloads downstream.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {(chartPack?.caution_notes.length ?? 0) > 0 ? (
                  chartPack?.caution_notes.map((note) => (
                    <div
                      key={note}
                      className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]"
                    >
                      {note}
                    </div>
                  ))
                ) : (
                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                    No caution notes saved for this chart pack.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Pack Warnings</CardTitle>
                <CardDescription>Warnings stay explicit at the pack level so chart polish does not hide source limits.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {(chartPack?.warnings.length ?? 0) > 0 ? (
                  chartPack?.warnings.map((warning) => (
                    <div
                      key={`${warning.code}-${warning.message}`}
                      className={`rounded-md border p-3 text-sm ${warningToneClassName(warning.severity)}`}
                    >
                      <div className="text-[11px] font-semibold uppercase tracking-wide">{warning.code}</div>
                      <p className="mt-1">{warning.message}</p>
                    </div>
                  ))
                ) : (
                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                    No pack-level warnings saved.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Source Items</CardTitle>
                <CardDescription>The viewer preserves backend source order for each saved chart pack.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {(chartPack?.source_items ?? []).map((sourceItem, index) => (
                  <div
                    key={`${sourceItem.source_kind}-${sourceItem.paper_id}-${sourceItem.run_id}-${index}`}
                    className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-[var(--pp-text-primary)]">{sourceItem.source_kind}</div>
                      {sourceItem.table_id ? <Badge variant="outline">{sourceItem.table_id}</Badge> : null}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">
                      {sourceItem.paper_id} / {sourceItem.run_id}
                    </div>
                    {sourceItem.source_label ? (
                      <div className="mt-2 text-xs text-[var(--pp-text-secondary)]">{sourceItem.source_label}</div>
                    ) : null}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Render Env</CardTitle>
                <CardDescription>Spec generation stays template-driven and file-backed in this v0 lane.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  <div className="font-medium text-[var(--pp-text-primary)]">
                    {chartPack?.render_env?.engine ?? "Unavailable"}
                  </div>
                  <div className="mt-1 text-xs text-[var(--pp-text-dim)]">{chartPack?.render_env?.version ?? "-"}</div>
                  {chartPack?.render_env?.notes ? (
                    <p className="mt-2">{chartPack.render_env.notes}</p>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      ) : (
        <main className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="h-4 w-4" />
                Search chart packs
              </CardTitle>
              <CardDescription>Search by title or artifact id before opening a saved chart pack.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="block">
                <span className="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                  Search
                </span>
                <Input
                  value={indexSearchQuery}
                  onChange={(event) => setIndexSearchQuery(event.target.value)}
                  placeholder="Search title or chart pack id"
                />
              </label>
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                {indexResponse?.total ?? 0} saved chart pack{(indexResponse?.total ?? 0) === 1 ? "" : "s"}.
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileSearch className="h-4 w-4" />
                Saved chart-pack artifacts
              </CardTitle>
              <CardDescription>Each card summarizes chart count, warning load, and last generation timestamp.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading ? (
                <p className="text-sm text-[var(--pp-text-dim)]">Loading chart pack index…</p>
              ) : null}
              {error ? (
                <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                  {error}
                </p>
              ) : null}
              {!loading && !error && filteredItems.length === 0 ? (
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  No chart packs match the current search.
                </div>
              ) : null}
              {!loading && !error
                ? filteredItems.map((item) => (
                    <article
                      key={item.chart_pack_id}
                      className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-[var(--pp-text-primary)]">{item.title}</div>
                          <div className="mt-1 break-all font-mono text-[11px] text-[var(--pp-text-dim)]">
                            {item.chart_pack_id}
                          </div>
                        </div>
                        <Badge variant="outline" className={warningBadgeClassName(item.warning_count)}>
                          {item.warning_count > 0 ? `${item.warning_count} warning` : "Clean snapshot"}
                        </Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-[var(--pp-text-dim)] sm:grid-cols-2">
                        <div>Created: {formatDateTime(item.created_at)}</div>
                        <div>Generated: {formatDateTime(item.generated_at)}</div>
                        <div>{item.chart_count} charts</div>
                        <div>{item.warning_count} warning{item.warning_count === 1 ? "" : "s"}</div>
                      </div>
                      <div className="mt-3">
                        <Button size="sm" onClick={() => navigate(`/chart-packs/${encodeURIComponent(item.chart_pack_id)}`)}>
                          Open chart pack
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
