import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, FileSearch, Route, Search, ShieldAlert } from "lucide-react";
import {
  generateChartPack,
  getApiErrorMessage,
  getChartPack,
  getChartPackDataCsvUrl,
  getChartPackIndex,
  getPaperNotesIndex,
  getChartPackRenderSvgUrl,
  getChartPackSpecUrl,
} from "../lib/api";
import {
  ChartPack,
  ChartDefinition,
  ChartPackGateStatus,
  ChartPackListItem,
  ChartPackListResponse,
  ChartPackQualityGate,
  ChartPackRequestSnapshot,
  ChartPackResponse,
  PaperNoteSummary,
  ChartTemplateId,
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

interface CsvPreview {
  header: string[];
  rows: string[][];
}

interface ChartPackPresetOption {
  id: ChartTemplateId;
  label: string;
  help: string;
}

interface RecentChartSourceChoice {
  paperId: string;
  runId: string;
  title: string;
  noteSlug: string;
}

const CHART_PACK_PRESET_OPTIONS: ChartPackPresetOption[] = [
  {
    id: "stats_check_status_counts",
    label: "Verification status counts",
    help: "Count saved verification checks by verdict from one stats report.",
  },
  {
    id: "reported_vs_computed_p_scatter",
    label: "Reported vs computed p scatter",
    help: "Compare exact reported p values against computed p values from one stats report.",
  },
];

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

function gateToneClassName(status: ChartPackGateStatus): string {
  if (status === "pass") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (status === "fail") {
    return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
  }
  return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
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

function defaultCreateChartTitle(templateId: ChartTemplateId): string {
  return templateLabel(templateId);
}

function buildCreateFieldMappings(templateId: ChartTemplateId) {
  if (templateId === "reported_vs_computed_p_scatter") {
    return [
      { target_field: "reported_p", source_field: "reported_p" },
      { target_field: "computed_p", source_field: "computed_p" },
    ];
  }
  return [
    { target_field: "status", source_field: "status" },
    { target_field: "value", source_field: "count" },
  ];
}

function buildCreateSort(templateId: ChartTemplateId) {
  if (templateId === "reported_vs_computed_p_scatter") {
    return { field: "reported_p", direction: "asc" as const };
  }
  return { field: "status", direction: "asc" as const };
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

function escapeSvgText(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
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

function numericCell(value: string | undefined): number | null {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildChartPreviewSvg(
  chart: ChartDefinition,
  preview: CsvPreview,
  specPayload: Record<string, unknown> | undefined,
): string | null {
  const mark = typeof specPayload?.mark === "string" ? specPayload.mark : null;
  if (!mark) {
    return null;
  }

  const width = 520;
  const height = 260;
  const left = 64;
  const right = 28;
  const top = 28;
  const bottom = 42;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const xField = typeof (specPayload?.encoding as Record<string, unknown> | undefined)?.x === "string"
    ? ((specPayload?.encoding as Record<string, unknown>).x as string)
    : preview.header[0] ?? "x";
  const yField = typeof (specPayload?.encoding as Record<string, unknown> | undefined)?.y === "string"
    ? ((specPayload?.encoding as Record<string, unknown>).y as string)
    : preview.header[1] ?? "y";

  const numericSeries = preview.rows
    .map((row) => ({
      label: row[0] ?? "",
      x: numericCell(row[0]),
      y: numericCell(row[1]),
    }))
    .filter((entry) => entry.y !== null) as Array<{ label: string; x: number | null; y: number }>;

  const yValues = numericSeries.map((entry) => entry.y);
  const yMin = yValues.length > 0 ? Math.min(0, ...yValues) : 0;
  const yMax = yValues.length > 0 ? Math.max(0, ...yValues) : 1;
  const ySpan = yMax - yMin || 1;
  const scaleY = (value: number) => top + ((yMax - value) / ySpan) * plotHeight;
  const baselineY = scaleY(0);
  const frame = [
    `<rect x="0" y="0" width="${width}" height="${height}" rx="16" fill="#0f172a"/>`,
    `<rect x="${left}" y="${top}" width="${plotWidth}" height="${plotHeight}" rx="10" fill="#111827" stroke="#334155"/>`,
    `<line x1="${left}" y1="${top + plotHeight}" x2="${left + plotWidth}" y2="${top + plotHeight}" stroke="#475569" stroke-width="1"/>`,
    `<line x1="${left}" y1="${top}" x2="${left}" y2="${top + plotHeight}" stroke="#475569" stroke-width="1"/>`,
  ];

  const labels = [
    `<text x="${left}" y="18" fill="#e2e8f0" font-size="14" font-weight="600">${escapeSvgText(chart.title)}</text>`,
    `<text x="${left + plotWidth}" y="18" fill="#94a3b8" font-size="11" text-anchor="end">${escapeSvgText(String(mark))}</text>`,
    `<text x="${left}" y="${height - 12}" fill="#94a3b8" font-size="11">${escapeSvgText(xField)}</text>`,
    `<text x="16" y="${top - 8}" fill="#94a3b8" font-size="11">${escapeSvgText(yField)}</text>`,
  ];

  if (numericSeries.length === 0) {
    return [
      `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvgText(chart.title)} mock preview">`,
      ...frame,
      ...labels,
      `<text x="${width / 2}" y="${height / 2}" fill="#94a3b8" font-size="13" text-anchor="middle">No numeric rows available for preview</text>`,
      `</svg>`,
    ].join("");
  }

  const yTicks = [yMin, (yMin + yMax) / 2, yMax].map((value) => {
    const y = scaleY(value);
    return [
      `<line x1="${left}" y1="${y}" x2="${left + plotWidth}" y2="${y}" stroke="${Math.abs(value) < 1e-9 ? "#38bdf8" : "#1e293b"}" stroke-width="${Math.abs(value) < 1e-9 ? 1.5 : 1}" stroke-dasharray="${Math.abs(value) < 1e-9 ? "" : "4 4"}"/>`,
      `<text x="${left - 10}" y="${y + 4}" fill="#94a3b8" font-size="11" text-anchor="end">${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(2)}</text>`,
    ].join("");
  });

  let marks: string[] = [];
  if (mark === "point") {
    const xValues = numericSeries.map((entry) => entry.x).filter((value): value is number => value !== null);
    const xMin = xValues.length > 0 ? Math.min(...xValues) : 0;
    const xMax = xValues.length > 0 ? Math.max(...xValues) : 1;
    const xSpan = xMax - xMin || 1;
    const scaleX = (value: number) => left + ((value - xMin) / xSpan) * plotWidth;
    marks = numericSeries.map((entry) => {
      const x = scaleX(entry.x ?? xMin);
      const y = scaleY(entry.y);
      return [
        `<circle cx="${x}" cy="${y}" r="5" fill="#38bdf8" fill-opacity="0.9" stroke="#e0f2fe" stroke-width="1.5"/>`,
        `<text x="${x}" y="${Math.max(top + 12, y - 10)}" fill="#cbd5e1" font-size="10" text-anchor="middle">${escapeSvgText(entry.label || String(entry.x ?? ""))}</text>`,
      ].join("");
    });
  } else if (mark === "line") {
    const step = numericSeries.length === 1 ? 0 : plotWidth / (numericSeries.length - 1);
    const points = numericSeries
      .map((entry, index) => `${left + step * index},${scaleY(entry.y)}`)
      .join(" ");
    marks = [
      `<polyline fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${points}"/>`,
      ...numericSeries.flatMap((entry, index) => {
        const x = left + step * index;
        const y = scaleY(entry.y);
        return [
          `<circle cx="${x}" cy="${y}" r="4" fill="#e0f2fe" stroke="#38bdf8" stroke-width="2"/>`,
          `<text x="${x}" y="${height - 20}" fill="#94a3b8" font-size="10" text-anchor="middle">${escapeSvgText(entry.label)}</text>`,
        ];
      }),
    ];
  } else {
    const gap = 12;
    const barWidth = Math.max(24, (plotWidth - gap * Math.max(0, numericSeries.length - 1)) / numericSeries.length);
    marks = numericSeries.flatMap((entry, index) => {
      const x = left + index * (barWidth + gap);
      const valueY = scaleY(entry.y);
      const barHeight = Math.max(2, Math.abs(baselineY - valueY));
      const y = entry.y >= 0 ? valueY : baselineY;
      return [
        `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="6" fill="#38bdf8" fill-opacity="0.9"/>`,
        `<text x="${x + barWidth / 2}" y="${height - 20}" fill="#94a3b8" font-size="10" text-anchor="middle">${escapeSvgText(entry.label)}</text>`,
      ];
    });
  }

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvgText(chart.title)} mock preview">`,
    ...frame,
    ...yTicks,
    ...labels,
    ...marks,
    `</svg>`,
  ].join("");
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

function noteLatestRunId(note: PaperNoteSummary): string | null {
  if (note.ops_summary?.latest_run_id?.trim()) {
    return note.ops_summary.latest_run_id.trim();
  }
  const rawSignals =
    note.pp_signals && typeof note.pp_signals === "object" && !Array.isArray(note.pp_signals)
      ? (note.pp_signals as Record<string, unknown>)
      : null;
  return typeof rawSignals?.last_run_id === "string" && rawSignals.last_run_id.trim()
    ? rawSignals.last_run_id.trim()
    : null;
}

function noteHasSavedStatsReport(note: PaperNoteSummary): boolean {
  if (note.ops_summary?.has_stats_report === true) {
    return true;
  }
  const rawSignals =
    note.pp_signals && typeof note.pp_signals === "object" && !Array.isArray(note.pp_signals)
      ? (note.pp_signals as Record<string, unknown>)
      : null;
  return rawSignals?.stats_report_written === true;
}

function recentChartSourceChoices(notes: PaperNoteSummary[]): RecentChartSourceChoice[] {
  const seen = new Set<string>();
  const choices: RecentChartSourceChoice[] = [];

  for (const note of notes) {
    const paperId = typeof note.id === "string" && note.id.trim().length > 0 ? note.id.trim() : null;
    const runId = noteLatestRunId(note);
    if (!paperId || !runId || !noteHasSavedStatsReport(note)) {
      continue;
    }
    const dedupeKey = `${paperId}::${runId}`;
    if (seen.has(dedupeKey)) {
      continue;
    }
    seen.add(dedupeKey);
    choices.push({
      paperId,
      runId,
      title: note.title,
      noteSlug: note.slug,
    });
    if (choices.length >= 6) {
      break;
    }
  }

  return choices;
}

function buildChartHeaderWhenToUse(routeChartPackId?: string): string {
  if (routeChartPackId) {
    return "Use this pack when you need one chart-ready artifact you can verify before CSV/spec export, note reuse, or meeting handoff.";
  }
  return "Use this lane when you want to turn one saved workbench run into a reviewable chart bundle before export or discussion.";
}

function buildChartHeaderContinuity(chartPack: ChartPack | null): string {
  const linkedPaperIds = Array.from(
    new Set(
      (chartPack?.source_items ?? [])
        .map((sourceItem) => sourceItem.paper_id?.trim())
        .filter((paperId): paperId is string => Boolean(paperId)),
    ),
  );

  if (linkedPaperIds.length > 0) {
    return `Canonical evidence lives upstream in ${linkedPaperIds.length} linked paper review${linkedPaperIds.length === 1 ? "" : "s"} behind this pack. Open review from the source items before exporting CSV/spec bundles or reusing charts downstream.`;
  }

  return "Canonical evidence lives upstream in the saved review context behind this pack. Open review from the source items before exporting CSV/spec bundles or reusing charts downstream.";
}

function buildChartHeaderDerivedFrom(chartPack: ChartPack | null): string {
  if (!chartPack) {
    return "Derived from one saved workbench run plus its chart-pack source refs once a pack is generated.";
  }
  const primarySource = chartPack.source_items[0];
  const primaryLabel = primarySource ? `${primarySource.paper_id} / ${primarySource.run_id}` : "the saved run context";
  return `Derived from ${chartPack.source_items.length} saved source ref${chartPack.source_items.length === 1 ? "" : "s"} anchored on ${primaryLabel}.`;
}

function buildChartReviewPriorityCopy(
  packWarningsCount: number,
  cautionNotesCount: number,
  warningChartCount: number,
): { tone: "attention" | "clear"; title: string; detail: string } {
  if (packWarningsCount > 0 || warningChartCount > 0) {
    return {
      tone: "attention",
      title: "Review warning-marked charts before export or downstream reuse.",
      detail:
        cautionNotesCount > 0
          ? "Read the caution notes, then inspect warning-marked chart cards and source-item review links before treating this pack as reusable."
          : "Inspect warning-marked chart cards and source-item review links before treating this pack as reusable downstream.",
    };
  }
  if (cautionNotesCount > 0) {
    return {
      tone: "attention",
      title: "Read caution notes before reusing a clean-looking chart pack.",
      detail: "This pack has no explicit warnings, but saved caution notes still narrow what should be exported or reused downstream.",
    };
  }
  return {
    tone: "clear",
    title: "No pack-level warnings or caution notes are saved.",
    detail: "A quick source-item review is still the safest final check before exporting CSV/spec bundles or reusing charts downstream.",
  };
}

function buildQualityGateSummary(
  qualityGate: ChartPackQualityGate | null,
): { title: string; detail: string } {
  if (!qualityGate) {
    return {
      title: "No saved quality gate is available for this chart pack yet.",
      detail: "Treat this as an older bundle and rely on warning cards, caution notes, and source-item review before reuse.",
    };
  }
  if (qualityGate.overall_status === "pass") {
    return {
      title: "Saved bundle checks passed for this chart pack.",
      detail: "The bundle-local contract is complete. A normal source-item review is still the last honest check before downstream reuse.",
    };
  }
  if (qualityGate.overall_status === "fail") {
    return {
      title: "This chart pack is missing required saved bundle members.",
      detail: "Do not treat this pack as handoff-ready until the failing bundle checks are repaired.",
    };
  }
  return {
    title: "This chart pack still needs review before downstream reuse.",
    detail: "The saved quality gate found warning or review-required conditions. Read the flagged checks before exporting or handing the pack off.",
  };
}

function normalizeChartPackCreateError(error: unknown, paperId: string, runId: string): string {
  const message = getApiErrorMessage(error);
  if (message.includes("Artifact run directory not found") || message.includes("stats_report.json not found")) {
    return `We couldn't find a saved stats report for ${paperId} / ${runId}. Open that paper in the workbench, run or refresh checks, then try this latest run again.`;
  }
  if (message.includes("Unsupported stats_report template")) {
    return "This chart preset is not available for that saved stats report yet. Try the verification status counts preset first.";
  }
  return message;
}

export function ChartPackPage() {
  const navigate = useNavigate();
  const { chartPackId: routeChartPackId } = useParams<{ chartPackId?: string }>();
  const [indexResponse, setIndexResponse] = useState<ChartPackListResponse | null>(null);
  const [packResponse, setPackResponse] = useState<ChartPackResponse | null>(null);
  const [recentSources, setRecentSources] = useState<RecentChartSourceChoice[]>([]);
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [createPaperId, setCreatePaperId] = useState("");
  const [createRunId, setCreateRunId] = useState("");
  const [createPackTitle, setCreatePackTitle] = useState("");
  const [createChartTitle, setCreateChartTitle] = useState("");
  const [createTemplateId, setCreateTemplateId] = useState<ChartTemplateId>("stats_check_status_counts");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creatingPack, setCreatingPack] = useState(false);
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
      setRecentSources([]);
      setMockReasons([]);

      try {
        const [chartPackResult, noteResult] = await Promise.all([
          getChartPackIndex(),
          getPaperNotesIndex({ pageSize: 50 }),
        ]);
        if (!mounted) {
          return;
        }
        setIndexResponse(chartPackResult.data);
        setRecentSources(recentChartSourceChoices(noteResult.data.items));
        setMockReasons(collectMockReasons([chartPackResult, noteResult]));
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

  function applyRecentSource(choice: RecentChartSourceChoice) {
    setCreatePaperId(choice.paperId);
    setCreateRunId(choice.runId);
    setCreateError(null);
  }

  async function handleGenerateChartPack(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const paperId = createPaperId.trim();
    const runId = createRunId.trim();
    const packTitle = createPackTitle.trim();
    const chartTitle = createChartTitle.trim();

    if (!paperId) {
      setCreateError("Enter a paper ID to start a chart pack.");
      return;
    }
    if (!runId) {
      setCreateError("Enter a run ID from the saved stats report you want to review.");
      return;
    }

    setCreatingPack(true);
    setCreateError(null);
    try {
      const payload: ChartPackRequestSnapshot = {
        title: packTitle || undefined,
        charts: [
          {
            title: chartTitle || defaultCreateChartTitle(createTemplateId),
            template_id: createTemplateId,
            source_ref: {
              source_kind: "stats_report",
              paper_id: paperId,
              run_id: runId,
              source_label: "stats_report.json",
            },
            field_mappings: buildCreateFieldMappings(createTemplateId),
            filters: [],
            sort: buildCreateSort(createTemplateId),
          },
        ],
      };
      const result = await generateChartPack(payload);
      navigate(`/chart-packs/${encodeURIComponent(result.data.chart_pack.chart_pack_id)}`);
    } catch (actionError) {
      setCreateError(normalizeChartPackCreateError(actionError, paperId, runId));
    } finally {
      setCreatingPack(false);
    }
  }

  const chartPack = packResponse?.chart_pack ?? null;
  const qualityGate = packResponse?.quality_gate ?? null;
  const packWarningsCount = chartPack?.warnings.length ?? 0;
  const cautionNotesCount = chartPack?.caution_notes.length ?? 0;
  const warningChartCount = useMemo(
    () => chartPack?.charts.filter((chart) => chart.warnings.length > 0).length ?? 0,
    [chartPack],
  );
  const reviewPriority = useMemo(
    () => buildChartReviewPriorityCopy(packWarningsCount, cautionNotesCount, warningChartCount),
    [cautionNotesCount, packWarningsCount, warningChartCount],
  );
  const qualityGateSummary = useMemo(() => buildQualityGateSummary(qualityGate), [qualityGate]);
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
        <ArtifactHeaderContext
          testId="chart-pack-header-context"
          emphasizeFirstItem={Boolean(routeChartPackId)}
          items={[
            routeChartPackId ? { label: "Derived artifact", value: buildChartHeaderContinuity(chartPack) } : null,
            { label: "When to use", value: buildChartHeaderWhenToUse(routeChartPackId) },
            { label: "Derived from", value: buildChartHeaderDerivedFrom(chartPack) },
          ].filter((item): item is { label: string; value: string } => item !== null)}
        />
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
                      const mockRenderSvg = mockReasons.length > 0
                        ? buildChartPreviewSvg(chart, preview, specPayload)
                        : null;
                      const renderSvgRef = chart.render_refs.find((ref) => ref.kind === "render_svg") ?? null;
                      const renderHref = mockRenderSvg
                        ? buildMockDownloadHref(mockRenderSvg, "image/svg+xml")
                        : renderSvgRef
                          ? getChartPackRenderSvgUrl(chartPack.chart_pack_id, chart.chart_id)
                          : null;

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
                              title="Review chart warnings, source lineage, and quality gate before exporting."
                              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 text-xs text-[var(--pp-text-secondary)]"
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
                            {renderHref ? (
                              <a
                                href={renderHref}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 text-xs text-[var(--pp-text-secondary)]"
                              >
                                Open SVG
                              </a>
                            ) : null}
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
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                                Render preview
                              </div>
                              <div className="text-[11px] text-[var(--pp-text-dim)]">
                                {mockRenderSvg
                                  ? "Mock preview from saved CSV/spec"
                                  : renderSvgRef
                                    ? "Saved SVG render"
                                    : "No saved SVG render"}
                              </div>
                            </div>
                            <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">
                              {mockRenderSvg
                                ? "Mock mode synthesizes a local preview from saved CSV/spec so this card mirrors the live render surface without hiding its derived status."
                                : renderSvgRef
                                  ? "This preview comes from the saved bundle render. Keep warnings, transforms, and source lineage above it as the stronger review context."
                                  : "This chart does not currently expose a saved SVG render in the bundle."}
                            </p>
                            {renderHref ? (
                              <div className="mt-3 overflow-hidden rounded-md border border-[var(--pp-border)] bg-[#0f172a]">
                                <img
                                  src={renderHref}
                                  alt={`${chart.title} render preview`}
                                  className="block max-h-[260px] w-full object-contain"
                                  loading="lazy"
                                  data-testid={`chart-render-preview-${chart.chart_id}`}
                                />
                              </div>
                            ) : null}
                          </div>

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
            <Card data-testid="chart-pack-review-priority-card">
              <CardHeader>
                <CardTitle>Review priority</CardTitle>
                <CardDescription>Decide whether this pack is ready for export, or whether warnings and caution notes should stop reuse first.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div
                  data-testid="chart-pack-review-priority"
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
                  <Badge variant="outline" className={warningBadgeClassName(packWarningsCount)}>
                    Warnings {packWarningsCount}
                  </Badge>
                  <Badge variant="outline" className={warningBadgeClassName(cautionNotesCount)}>
                    Caution notes {cautionNotesCount}
                  </Badge>
                  <Badge variant="outline" className={warningBadgeClassName(warningChartCount)}>
                    Warning charts {warningChartCount}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card data-testid="chart-pack-quality-gate-card">
              <CardHeader>
                <CardTitle>Quality gate</CardTitle>
                <CardDescription>Saved bundle-local handoff checks keep review-required packs explicit before export or reuse.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className={`rounded-md border p-3 text-sm ${gateToneClassName(qualityGate?.overall_status ?? "warn")}`}>
                  <p className="font-medium">{qualityGateSummary.title}</p>
                  <p className="mt-2">{qualityGateSummary.detail}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className={gateToneClassName(qualityGate?.overall_status ?? "warn")}>
                    Status {qualityGate?.overall_status ?? "missing"}
                  </Badge>
                  <Badge variant="outline" className={warningBadgeClassName(qualityGate?.bundle_ready ? 0 : 1)}>
                    Bundle ready {qualityGate?.bundle_ready ? "yes" : "no"}
                  </Badge>
                  <Badge variant="outline" className={warningBadgeClassName(qualityGate?.handoff_ready ? 0 : 1)}>
                    Handoff ready {qualityGate?.handoff_ready ? "yes" : "no"}
                  </Badge>
                </div>
                {qualityGate?.reason_codes && qualityGate.reason_codes.length > 0 ? (
                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Reason codes
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {qualityGate.reason_codes.map((reasonCode) => (
                        <Badge key={reasonCode} variant="outline" className={gateToneClassName(qualityGate.overall_status)}>
                          {reasonCode}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : null}
                {qualityGate?.checks && qualityGate.checks.length > 0 ? (
                  <div className="space-y-2">
                    {qualityGate.checks.map((check) => (
                      <div
                        key={check.name}
                        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium text-[var(--pp-text-primary)]">{check.name}</div>
                          <Badge variant="outline" className={gateToneClassName(check.status)}>
                            {check.status}
                          </Badge>
                        </div>
                        <p className="mt-2 text-[var(--pp-text-secondary)]">{check.detail}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                    No saved quality-gate checks are available for this chart pack.
                  </div>
                )}
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
                    {sourceItem.paper_id ? (
                      <Link
                        to={`/workbench/${encodeURIComponent(sourceItem.paper_id)}`}
                        className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--pp-accent-text)] underline-offset-2 hover:underline"
                      >
                        Open review
                        <ArrowRight className="h-3 w-3" />
                      </Link>
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
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Search chart packs
                </CardTitle>
                <CardDescription>Search saved derived chart packs by title or artifact id before opening a review snapshot.</CardDescription>
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
                  {(indexResponse?.total ?? 0) > 0
                    ? `${indexResponse?.total ?? 0} saved derived chart pack${(indexResponse?.total ?? 0) === 1 ? "" : "s"}.`
                    : "No saved derived chart packs yet. Start one below from a saved stats report, then review warnings and exports here."}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Create from a saved run</CardTitle>
                <CardDescription>
                  Recent saved runs are the fastest path. Manual paper and run IDs stay available below when you already
                  know the exact saved review snapshot.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs text-[var(--pp-text-secondary)]">
                  Chart packs stay downstream of saved review runs. Re-open note or workbench context before exporting CSV or spec bundles downstream.
                </div>
                <form onSubmit={handleGenerateChartPack} className="space-y-3">
                  <div className="rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    <p className="font-semibold uppercase tracking-wide text-[var(--pp-accent-text)]">
                      Recommended path
                    </p>
                    <p className="mt-1">
                      Start with a recent saved run when you can. Manual paper and run entry is still available below as
                      a fallback.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        Recent saved runs
                      </span>
                      <span className="text-[11px] text-[var(--pp-text-dim)]">
                        Click one to fill both the paper ID and run ID.
                      </span>
                    </div>
                    {recentSources.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {recentSources.map((choice) => {
                          const isSelected = createPaperId.trim() === choice.paperId && createRunId.trim() === choice.runId;
                          return (
                            <Button
                              key={`${choice.paperId}-${choice.runId}`}
                              type="button"
                              variant={isSelected ? "default" : "outline"}
                              size="sm"
                              className="h-auto max-w-full justify-start px-3 py-2 text-left"
                              onClick={() => applyRecentSource(choice)}
                            >
                              <span className="flex min-w-0 flex-col items-start">
                                <span className="max-w-[240px] truncate text-xs font-medium">{choice.title}</span>
                                <span className="font-mono text-[11px] text-[var(--pp-text-dim)]">{choice.runId}</span>
                              </span>
                            </Button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-dim)]">
                        No recent saved runs are ready yet. Open a paper, run or refresh checks, then come back here to
                        build a chart pack from that saved run.
                      </p>
                    )}
                  </div>

                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    Manual saved run fallback. Fill the paper ID and run ID below when you already know the exact saved
                    review snapshot you want.
                  </div>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Chart preset
                    </span>
                    <select
                      value={createTemplateId}
                      onChange={(event) => setCreateTemplateId(event.target.value as ChartTemplateId)}
                      aria-label="Chart pack preset"
                      className="w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)] outline-none focus:border-[var(--pp-accent-border)]"
                    >
                      {CHART_PACK_PRESET_OPTIONS.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    {CHART_PACK_PRESET_OPTIONS.find((option) => option.id === createTemplateId)?.help}
                  </p>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Paper ID
                    </span>
                    <Input
                      value={createPaperId}
                      onChange={(event) => setCreatePaperId(event.target.value)}
                      placeholder="paper-e2e-001"
                      aria-label="Chart pack paper id"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Run ID
                    </span>
                    <Input
                      value={createRunId}
                      onChange={(event) => setCreateRunId(event.target.value)}
                      placeholder="run_e2e_fixture_001"
                      aria-label="Chart pack run id"
                    />
                  </label>

                  <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    Need the run ID? Open the paper in the workbench first, then come back and reuse the latest saved
                    run.
                  </p>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Chart pack title
                    </span>
                    <Input
                      value={createPackTitle}
                      onChange={(event) => setCreatePackTitle(event.target.value)}
                      placeholder="Optional. A chart pack title will be generated if left blank."
                      aria-label="Chart pack title"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Chart title
                    </span>
                    <Input
                      value={createChartTitle}
                      onChange={(event) => setCreateChartTitle(event.target.value)}
                      placeholder={defaultCreateChartTitle(createTemplateId)}
                      aria-label="Chart title"
                    />
                  </label>

                  <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    This first create path is intentionally bounded to one chart per pack so you can review the saved CSV and spec right away.
                  </p>

                  {createError ? (
                    <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                      {createError}
                    </p>
                  ) : null}

                  <Button type="submit" disabled={creatingPack || !createPaperId.trim() || !createRunId.trim()}>
                    {creatingPack ? "Creating chart pack…" : "Create chart pack"}
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
                  Saved chart-pack artifacts
                </CardTitle>
                <CardDescription>Each card summarizes chart count, warning load, and saved-run readiness before downstream reuse.</CardDescription>
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
                  {(indexResponse?.total ?? 0) > 0
                    ? "No chart packs match the current search."
                    : "No saved derived chart packs yet. Generate and save a chart pack to inspect warnings and outputs here."}
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
