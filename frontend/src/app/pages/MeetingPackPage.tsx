import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  FileSearch,
  Route,
  Search,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import {
  getApiErrorMessage,
  getMeetingPackIndex,
  getMeetingPack,
  getMeetingPackTrace,
  getMeetingPackValidation,
  regenerateMeetingPack,
  rerenderMeetingPack,
} from "../lib/api";
import {
  MeetingPack,
  MeetingPackListItem,
  MeetingPackListResponse,
  OutputModeFamily,
  MeetingPackResponse,
  MeetingPackTraceResponse,
  MeetingPackValidationResponse,
} from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Separator } from "../components/ui/separator";

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

function formatModeLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatOutputModeFamilyLabel(value: OutputModeFamily): string {
  if (value === "lab_meeting") {
    return "Lab Meeting";
  }
  if (value === "project_update") {
    return "Project Update";
  }
  if (value === "builder_debug") {
    return "Builder / Debug";
  }
  return "Learner";
}

function badgeToneClass(tone: "success" | "warning" | "danger" | "muted"): string {
  if (tone === "success") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (tone === "warning") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  if (tone === "danger") {
    return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function readinessTone(readiness: MeetingPack["readiness"]): "success" | "warning" {
  return readiness === "evidence_backed" ? "success" : "warning";
}

function syncTone(status?: string | null): "success" | "warning" {
  return status === "in_sync" ? "success" : "warning";
}

function outcomeTone(outcome: string): "success" | "warning" | "muted" {
  if (outcome === "loaded" || outcome === "resolved") {
    return "success";
  }
  if (outcome === "deduped") {
    return "warning";
  }
  return "muted";
}

function actionSummaryRows(counts: Record<string, number>): Array<[string, number]> {
  return Object.entries(counts);
}

type TracePresenceFilter = "all" | "with_trace" | "legacy";
type DraftAction = "regenerate" | "rerender";
type ActionNoticeTone = "success" | "danger";

interface ApiLikeResult {
  isMock: boolean;
  reason?: string;
}

interface MeetingPackActionNotice {
  tone: ActionNoticeTone;
  message: string;
}

interface MeetingPackNavigationState {
  meetingPackNotice?: MeetingPackActionNotice;
}

function isObjectWithKeys(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  return Object.keys(value as Record<string, unknown>).length > 0;
}

function matchesPackIndexQuery(item: MeetingPackListItem, query: string): boolean {
  if (!query) {
    return true;
  }

  const haystacks = [
    item.title,
    item.pack_id,
    item.primary_source_title ?? "",
    item.mode,
    formatModeLabel(item.mode),
    item.output_mode_family,
    formatOutputModeFamilyLabel(item.output_mode_family),
  ];

  return haystacks.some((value) => value.toLowerCase().includes(query));
}

function matchesTracePresence(item: MeetingPackListItem, filter: TracePresenceFilter): boolean {
  if (filter === "with_trace") {
    return item.trace_entry_count > 0;
  }
  if (filter === "legacy") {
    return item.trace_entry_count === 0;
  }
  return true;
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

export function MeetingPackPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { packId: routePackId } = useParams<{ packId?: string }>();
  const [packIdInput, setPackIdInput] = useState(routePackId ?? "");
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [tracePresenceFilter, setTracePresenceFilter] = useState<TracePresenceFilter>("all");
  const [indexResponse, setIndexResponse] = useState<MeetingPackListResponse | null>(null);
  const [packResponse, setPackResponse] = useState<MeetingPackResponse | null>(null);
  const [traceResponse, setTraceResponse] = useState<MeetingPackTraceResponse | null>(null);
  const [validationResponse, setValidationResponse] = useState<MeetingPackValidationResponse | null>(null);
  const [runningAction, setRunningAction] = useState<DraftAction | null>(null);
  const [actionNotice, setActionNotice] = useState<MeetingPackActionNotice | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockReasons, setMockReasons] = useState<string[]>([]);

  useEffect(() => {
    setPackIdInput(routePackId ?? "");
    setActionNotice(null);
  }, [routePackId]);

  useEffect(() => {
    const navigationState = (location.state as MeetingPackNavigationState | null) ?? null;
    if (!navigationState?.meetingPackNotice) {
      return;
    }
    setActionNotice(navigationState.meetingPackNotice);
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    const titleSuffix = routePackId ? ` ${routePackId}` : "";
    document.title = `Meeting Packs${titleSuffix}`;
  }, [routePackId]);

  useEffect(() => {
    let mounted = true;

    async function load(packId: string) {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setPackResponse(null);
      setTraceResponse(null);
      setValidationResponse(null);
      setMockReasons([]);

      try {
        const [packResult, traceResult, validationResult] = await Promise.all([
          getMeetingPack(packId),
          getMeetingPackTrace(packId),
          getMeetingPackValidation(packId),
        ]);
        if (!mounted) {
          return;
        }
        setPackResponse(packResult.data);
        setTraceResponse(traceResult.data);
        setValidationResponse(validationResult.data);
        setMockReasons(collectMockReasons([packResult, traceResult, validationResult]));
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

    async function loadIndex() {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setPackResponse(null);
      setTraceResponse(null);
      setValidationResponse(null);
      setMockReasons([]);

      try {
        const result = await getMeetingPackIndex();
        if (!mounted) {
          return;
        }
        setIndexResponse(result.data);
        setMockReasons(result.isMock && result.reason ? [result.reason] : []);
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

    if (routePackId) {
      void load(routePackId);
      return () => {
        mounted = false;
      };
    }

    void loadIndex();
    return () => {
      mounted = false;
    };
  }, [routePackId]);

  const packIndex = useMemo(() => indexResponse?.items ?? [], [indexResponse]);
  const normalizedIndexSearchQuery = indexSearchQuery.trim().toLowerCase();
  const filteredPackIndex = useMemo(
    () =>
      packIndex.filter(
        (item) =>
          matchesPackIndexQuery(item, normalizedIndexSearchQuery) &&
          matchesTracePresence(item, tracePresenceFilter),
      ),
    [normalizedIndexSearchQuery, packIndex, tracePresenceFilter],
  );
  const hasActiveIndexFilters = normalizedIndexSearchQuery.length > 0 || tracePresenceFilter !== "all";
  const pack = packResponse?.pack ?? null;
  const packMarkdownSync = packResponse?.markdown_sync ?? null;
  const validation = validationResponse?.validation ?? null;
  const trace = traceResponse ?? null;
  const traceActions = useMemo(
    () => actionSummaryRows(trace?.summary.action_counts ?? {}),
    [trace],
  );
  const traceOutcomes = useMemo(
    () => actionSummaryRows(trace?.summary.outcome_counts ?? {}),
    [trace],
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextPackId = packIdInput.trim();
    if (!nextPackId) {
      return;
    }
    navigate(`/meeting-packs/${encodeURIComponent(nextPackId)}`);
  }

  function resetIndexFilters() {
    setIndexSearchQuery("");
    setTracePresenceFilter("all");
  }

  async function handleRerenderDraft() {
    if (!routePackId) {
      return;
    }

    setRunningAction("rerender");
    setActionNotice(null);
    try {
      const [rerenderResult, traceResult, validationResult] = await Promise.all([
        rerenderMeetingPack(routePackId),
        getMeetingPackTrace(routePackId),
        getMeetingPackValidation(routePackId),
      ]);
      setPackResponse(rerenderResult.data);
      setTraceResponse(traceResult.data);
      setValidationResponse(validationResult.data);
      setMockReasons(collectMockReasons([rerenderResult, traceResult, validationResult]));
      setActionNotice({
        tone: "success",
        message: "Saved markdown rerendered from the current meeting pack JSON.",
      });
    } catch (actionError) {
      setActionNotice({
        tone: "danger",
        message: getApiErrorMessage(actionError),
      });
    } finally {
      setRunningAction(null);
    }
  }

  async function handleRegenerateDraft() {
    if (!routePackId) {
      return;
    }

    setRunningAction("regenerate");
    setActionNotice(null);
    try {
      const regenerateResult = await regenerateMeetingPack(routePackId);
      const nextPackId = regenerateResult.data.pack.id;
      const successNotice: MeetingPackActionNotice = {
        tone: "success",
        message: "Draft regenerated from the saved selector set.",
      };
      if (nextPackId && nextPackId !== routePackId) {
        navigate(`/meeting-packs/${encodeURIComponent(nextPackId)}`, {
          state: { meetingPackNotice: successNotice },
        });
        return;
      }

      const [traceResult, validationResult] = await Promise.all([
        getMeetingPackTrace(routePackId),
        getMeetingPackValidation(routePackId),
      ]);
      setPackResponse(regenerateResult.data);
      setTraceResponse(traceResult.data);
      setValidationResponse(validationResult.data);
      setMockReasons(collectMockReasons([regenerateResult, traceResult, validationResult]));
      navigate(`/meeting-packs/${encodeURIComponent(routePackId)}`, {
        replace: true,
        state: { meetingPackNotice: successNotice },
      });
    } catch (actionError) {
      setActionNotice({
        tone: "danger",
        message: getApiErrorMessage(actionError),
      });
    } finally {
      setRunningAction(null);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <FileSearch className="h-3.5 w-3.5" />
              Meeting pack review
              <Badge variant="muted" className="uppercase">Operational</Badge>
            </div>
            <h1 className="mt-2 text-lg font-semibold text-[var(--pp-text-primary)]">
              {pack?.title ?? "Saved meeting packs"}
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Review saved meeting-pack drafts, validation state, and trace coverage before rerender or downstream reuse.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/"
              className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Dashboard
            </Link>
            <Link
              to="/papers"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]"
            >
              Paper Notes
            </Link>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-2 sm:flex-row">
          <Input
            value={packIdInput}
            onChange={(event) => setPackIdInput(event.target.value)}
            placeholder="meetingpack_20260317T090000Z_journal_club_..."
            aria-label="Meeting pack ID"
            className="font-mono text-xs"
          />
          <Button type="submit" className="sm:w-auto">
            Open pack
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>

        {mockReasons.length > 0 ? (
          <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
      </header>

      {!routePackId ? (
        <main className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card>
            <CardHeader>
              <CardTitle>Saved meeting packs</CardTitle>
              <CardDescription>
                Recent saved drafts from `storage/meeting_packs`. Open one to inspect draft state, validation, and retrieval trace.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                  <label>
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Search
                    </span>
                    <span className="relative flex items-center">
                      <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[var(--pp-text-dim)]" />
                      <Input
                        value={indexSearchQuery}
                        onChange={(event) => setIndexSearchQuery(event.target.value)}
                        placeholder="title / pack_id / source / mode"
                        className="pl-8"
                        aria-label="Search saved meeting packs"
                      />
                    </span>
                  </label>

                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={resetIndexFilters}
                      disabled={!hasActiveIndexFilters}
                    >
                      Clear filters
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Trace
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant={tracePresenceFilter === "all" ? "secondary" : "ghost"}
                    onClick={() => setTracePresenceFilter("all")}
                  >
                    All
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={tracePresenceFilter === "with_trace" ? "secondary" : "ghost"}
                    onClick={() => setTracePresenceFilter("with_trace")}
                  >
                    With trace
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={tracePresenceFilter === "legacy" ? "secondary" : "ghost"}
                    onClick={() => setTracePresenceFilter("legacy")}
                  >
                    Legacy trace-free
                  </Button>
                </div>

                <p className="mt-3 text-xs text-[var(--pp-text-dim)]">
                  Showing {filteredPackIndex.length} of {packIndex.length} saved packs.
                </p>
              </div>

              {loading ? (
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-dim)]">
                  Loading saved packs…
                </div>
              ) : error ? (
                <div className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                  {error}
                </div>
              ) : filteredPackIndex.length > 0 ? (
                filteredPackIndex.map((item) => (
                  <article key={item.pack_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium text-[var(--pp-text-primary)]">{item.title}</div>
                      <Badge variant="outline">{formatModeLabel(item.mode)}</Badge>
                      <Badge variant="muted">{formatOutputModeFamilyLabel(item.output_mode_family)}</Badge>
                      <Badge className={badgeToneClass(readinessTone(item.readiness))}>
                        {item.readiness.replace("_", " ")}
                      </Badge>
                      {item.trace_entry_count > 0 ? (
                        <Badge variant="muted">{item.trace_entry_count} trace events</Badge>
                      ) : (
                        <Badge variant="muted">legacy trace-free</Badge>
                      )}
                    </div>
                    <div className="mt-2 grid gap-2 text-xs text-[var(--pp-text-dim)] sm:grid-cols-2">
                      <div>Created: {formatDateTime(item.created_at)}</div>
                      <div>Slides: {item.slide_count} · Sources: {item.source_count}</div>
                    </div>
                    {item.primary_source_title ? (
                      <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">
                        Primary source: {item.primary_source_title}
                      </p>
                    ) : null}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => navigate(`/meeting-packs/${encodeURIComponent(item.pack_id)}`)}
                      >
                        Open pack
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                      <span className="font-mono text-[11px] text-[var(--pp-text-dim)]">{item.pack_id}</span>
                    </div>
                  </article>
                ))
              ) : packIndex.length > 0 ? (
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  No saved meeting packs match the current search or trace filter.
                </div>
              ) : (
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  No saved meeting packs found yet.
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Open by pack ID</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                This screen is intentionally operational. It is for debugging selector resolution, load paths, markdown drift, and regenerate availability.
              </div>
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                You can still paste a `pack_id` directly if the pack is not in the recent list or if you want to jump to a copied artifact ID.
              </div>
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                Detail view shows selector/load trajectory, matched slugs, source paths, and regenerate/drift status in one place.
              </div>
            </CardContent>
          </Card>
        </main>
      ) : loading ? (
        <main className="surface-card p-6 text-sm text-[var(--pp-text-dim)]">Loading meeting pack…</main>
      ) : error ? (
        <main className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-[var(--pp-status-failed-text)]">
                <AlertTriangle className="h-4 w-4" />
                Unable to load pack
              </CardTitle>
              <CardDescription>{routePackId}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                {error}
              </p>
              <p className="text-sm text-[var(--pp-text-secondary)]">
                Check that the pack exists under `storage/meeting_packs`, then reopen it from the form above.
              </p>
            </CardContent>
          </Card>
        </main>
      ) : pack && validation && trace ? (
        <main className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                  <span>{pack.title}</span>
                  <Badge className={badgeToneClass(readinessTone(pack.readiness))}>{pack.readiness.replace("_", " ")}</Badge>
                  <Badge className={badgeToneClass(syncTone(packMarkdownSync?.status))}>
                    {packMarkdownSync?.status === "drifted" ? "Markdown drift" : "Markdown in sync"}
                  </Badge>
                </CardTitle>
                <CardDescription className="font-mono text-xs">{pack.id}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="muted">{formatOutputModeFamilyLabel(pack.output_mode_family)}</Badge>
                  <Badge variant="outline">{formatModeLabel(pack.mode)}</Badge>
                  <Badge variant="muted">{pack.source_items.length} sources</Badge>
                  <Badge variant="muted">{pack.slides.length} slides</Badge>
                  <Badge variant="muted">{pack.evidence_refs.length} evidence refs</Badge>
                  <Badge variant="muted">{pack.discussion_questions.length} discussion prompts</Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Created</div>
                    <div>{formatDateTime(pack.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Output mode family</div>
                    <div>{formatOutputModeFamilyLabel(pack.output_mode_family)}</div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Regenerate strategy</div>
                    <div>{validation.regenerate_strategy.replace(/_/g, " ")}</div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Concrete mode</div>
                    <div>{formatModeLabel(pack.mode)}</div>
                  </div>
                </div>
                <p>{pack.one_page_summary.overview || "No overview saved."}</p>
                <p className="text-xs text-[var(--pp-text-dim)]">
                  Concrete mode shapes this draft directly. The family tag shows the broader presentation lane without implying a different evidence policy.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Draft summary
                </CardTitle>
                <CardDescription>
                  Canonical evidence still lives in structured paper state. This section is only the saved draft context.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Key points</div>
                  {pack.one_page_summary.key_points.length > 0 ? (
                    <div className="space-y-2">
                      {pack.one_page_summary.key_points.map((point) => (
                        <article key={point.label} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                          <div className="text-sm font-medium text-[var(--pp-text-primary)]">{point.label}</div>
                          <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{point.text}</p>
                          {point.uncertainty_note ? (
                            <p className="mt-2 text-xs text-[var(--pp-warning-text)]">{point.uncertainty_note}</p>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--pp-text-dim)]">No key points saved.</p>
                  )}
                </div>

                {pack.one_page_summary.uncertainties.length > 0 ? (
                  <div>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Uncertainties</div>
                    <div className="space-y-2">
                      {pack.one_page_summary.uncertainties.map((item) => (
                        <p
                          key={item}
                          className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3 text-sm text-[var(--pp-warning-text)]"
                        >
                          {item}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Source items and slide outline</CardTitle>
                <CardDescription>
                  This is the pack-level draft structure, separate from retrieval observability.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  {pack.source_items.map((item) => (
                    <article key={item.id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-medium text-[var(--pp-text-primary)]">{item.title}</div>
                        <Badge variant="outline">{item.type.replace(/_/g, " ")}</Badge>
                        {!item.included ? <Badge className={badgeToneClass("warning")}>excluded</Badge> : null}
                      </div>
                      <p className="mt-1 break-all font-mono text-[11px] text-[var(--pp-text-dim)]">{item.ref}</p>
                    </article>
                  ))}
                </div>

                <div className="space-y-2">
                  {pack.slides.map((slide, index) => (
                    <article key={`${slide.slide_title}-${index}`} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                      <div className="text-sm font-medium text-[var(--pp-text-primary)]">
                        {index + 1}. {slide.slide_title}
                      </div>
                      <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{slide.purpose}</p>
                      {slide.bullets[0] ? (
                        <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{slide.bullets[0]}</p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Discussion and next steps</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  {pack.discussion_questions.length > 0 ? (
                    pack.discussion_questions.map((question) => (
                      <article key={question.question} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-sm font-medium text-[var(--pp-text-primary)]">{question.question}</div>
                        <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{question.rationale}</p>
                      </article>
                    ))
                  ) : (
                    <p className="text-sm text-[var(--pp-text-dim)]">No discussion prompts saved.</p>
                  )}
                </div>

                <div className="space-y-2">
                  {pack.next_steps.length > 0 ? (
                    pack.next_steps.map((step) => (
                      <article key={step.action} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-medium text-[var(--pp-text-primary)]">{step.action}</div>
                          <Badge variant="muted">{step.priority}</Badge>
                        </div>
                        <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{step.why}</p>
                      </article>
                    ))
                  ) : (
                    <p className="text-sm text-[var(--pp-text-dim)]">No next steps saved.</p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Saved markdown</CardTitle>
                <CardDescription>Useful when checking drift versus the deterministic render.</CardDescription>
              </CardHeader>
              <CardContent>
                <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)]">
                  <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-[var(--pp-text-primary)]">
                    Expand saved markdown
                  </summary>
                  <Separator />
                  <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap p-3 text-xs text-[var(--pp-text-secondary)]">
                    {packResponse?.markdown || "No markdown saved."}
                  </pre>
                </details>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4" />
                  Validation
                </CardTitle>
                <CardDescription>Regenerate safety and markdown sync are shown together to reduce diagnosis hops.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Badge className={badgeToneClass(validation.can_regenerate ? "success" : "danger")}>
                    {validation.can_regenerate ? "Can regenerate" : "Regenerate unavailable"}
                  </Badge>
                  <Badge className={badgeToneClass(syncTone(validation.markdown_sync.status))}>
                    {validation.markdown_sync.status === "drifted" ? "Markdown drifted" : "Markdown in sync"}
                  </Badge>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                  Strategy: {validation.regenerate_strategy.replace(/_/g, " ")}
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                    Draft actions
                  </div>
                  <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">
                    These controls only rewrite or regenerate the saved draft artifact. They do not replace canonical evidence review.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={handleRegenerateDraft}
                      disabled={!validation.can_regenerate || runningAction !== null}
                    >
                      {runningAction === "regenerate" ? "Regenerating…" : "Regenerate draft"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={handleRerenderDraft}
                      disabled={runningAction !== null}
                    >
                      {runningAction === "rerender" ? "Rerendering…" : "Rerender markdown"}
                    </Button>
                  </div>
                  {!validation.can_regenerate ? (
                    <p className="mt-3 text-xs text-[var(--pp-text-dim)]">
                      Regenerate stays gated until the saved selector set can be resolved safely in the current vault.
                    </p>
                  ) : null}
                </div>
                {actionNotice ? (
                  <p
                    className={`rounded-md border p-3 text-sm ${
                      actionNotice.tone === "danger"
                        ? "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]"
                        : "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                    }`}
                  >
                    {actionNotice.message}
                  </p>
                ) : null}
                {validation.warnings.length > 0 ? (
                  <div className="space-y-2">
                    {validation.warnings.map((warning) => (
                      <p
                        key={warning}
                        className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3 text-sm text-[var(--pp-warning-text)]"
                      >
                        {warning}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--pp-text-dim)]">No validation warnings.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Route className="h-4 w-4" />
                  Retrieval trace
                </CardTitle>
                <CardDescription>
                  Operational trace only. It shows selector and load trajectory, not scientific judgment.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {trace.available ? (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Entries</div>
                        <div className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">{trace.summary.entry_count}</div>
                      </div>
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Selectors</div>
                        <div className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">{trace.summary.selector_count}</div>
                      </div>
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Matched slugs</div>
                        <div className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">{trace.summary.matched_paper_count}</div>
                      </div>
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Source paths</div>
                        <div className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">{trace.summary.source_path_count}</div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Action counts</div>
                      <div className="flex flex-wrap gap-2">
                        {traceActions.map(([action, count]) => (
                          <Badge key={action} variant="outline">
                            {action} · {count}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Outcome counts</div>
                      <div className="flex flex-wrap gap-2">
                        {traceOutcomes.map(([outcome, count]) => (
                          <Badge key={outcome} className={badgeToneClass(outcomeTone(outcome))}>
                            {outcome} · {count}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Matched paper slugs</div>
                      <div className="space-y-1">
                        {trace.summary.matched_paper_slugs.map((slug) => (
                          <div key={slug} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 font-mono text-[11px] text-[var(--pp-text-secondary)]">
                            {slug}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Source paths</div>
                      <div className="space-y-1">
                        {trace.summary.source_paths.map((path) => (
                          <div key={path} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 font-mono text-[11px] text-[var(--pp-text-secondary)]">
                            {path}
                          </div>
                        ))}
                      </div>
                    </div>

                    <Separator />

                    <ol className="space-y-2">
                      {trace.trace.map((entry) => (
                        <li key={`${entry.order}-${entry.action}`}>
                          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="muted">#{entry.order}</Badge>
                              <Badge variant="outline">{entry.selector_type}</Badge>
                              <Badge className={badgeToneClass(outcomeTone(entry.outcome))}>{entry.outcome}</Badge>
                              <div className="text-sm font-medium text-[var(--pp-text-primary)]">{entry.action}</div>
                            </div>
                            <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">{entry.detail}</p>
                            <p className="mt-2 break-all font-mono text-[11px] text-[var(--pp-text-dim)]">
                              selector_ref: {entry.selector_ref}
                            </p>
                            {entry.source_path ? (
                              <p className="mt-1 break-all font-mono text-[11px] text-[var(--pp-text-dim)]">
                                source_path: {entry.source_path}
                              </p>
                            ) : null}
                            {entry.matched_paper_slugs.length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {entry.matched_paper_slugs.map((slug) => (
                                  <Badge key={`${entry.order}-${slug}`} variant="outline" className="font-mono">
                                    {slug}
                                  </Badge>
                                ))}
                              </div>
                            ) : null}
                            {isObjectWithKeys(entry.metadata) ? (
                              <details className="mt-2">
                                <summary className="cursor-pointer text-xs font-medium text-[var(--pp-text-dim)]">
                                  Metadata
                                </summary>
                                <pre className="mt-2 overflow-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-canvas)] p-2 text-[11px] text-[var(--pp-text-secondary)]">
                                  {JSON.stringify(entry.metadata, null, 2)}
                                </pre>
                              </details>
                            ) : null}
                          </article>
                        </li>
                      ))}
                    </ol>
                  </>
                ) : (
                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]">
                    No retrieval trace is saved for this pack yet. This usually means it predates trace persistence.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </main>
      ) : null}
    </div>
  );
}
