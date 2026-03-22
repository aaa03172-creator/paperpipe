import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Route, Search, ShieldAlert } from "lucide-react";
import { getApiErrorMessage, getProtocolCard, getProtocolCardIndex } from "../lib/api";
import {
  EvidenceLocator,
  ProtocolCard,
  ProtocolCardListItem,
  ProtocolCardListResponse,
  ProtocolCardResponse,
  ProtocolSourceKind,
  ProtocolValidationStatus,
  ProtocolVersion,
  ProtocolVersionStatus,
} from "../lib/types";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";

interface ApiLikeResult {
  isMock: boolean;
  reason?: string;
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

function matchesProtocolQuery(item: ProtocolCardListItem, query: string): boolean {
  if (!query) {
    return true;
  }
  const haystacks = [item.title, item.protocol_id, item.source_kind, item.validation_status];
  return haystacks.some((value) => value.toLowerCase().includes(query));
}

function sourceKindLabel(value: ProtocolSourceKind): string {
  if (value === "paper_derived") {
    return "Paper derived";
  }
  if (value === "internal_adaptation") {
    return "Internal adaptation";
  }
  return "Mixed";
}

function validationStatusLabel(value: ProtocolValidationStatus): string {
  if (value === "verified_by_user") {
    return "Verified by user";
  }
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function versionStatusLabel(value: ProtocolVersionStatus): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function validationBadgeClassName(value: ProtocolValidationStatus): string {
  if (value === "verified_by_user" || value === "reviewed") {
    return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
  }
  if (value === "draft" || value === "unreviewed") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)]";
}

function versionStatusBadgeClassName(value: ProtocolVersionStatus): string {
  if (value === "active") {
    return "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]";
  }
  if (value === "draft") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]";
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
  return tokens.length > 0 ? tokens.join(" · ") : "Locator unavailable";
}

function pickDefaultVersion(protocolCard: ProtocolCard | null, versions: ProtocolVersion[]): ProtocolVersion | null {
  if (!protocolCard || versions.length === 0) {
    return null;
  }
  const current = versions.find((item) => item.version_id === protocolCard.current_version_id);
  if (current) {
    return current;
  }
  return [...versions].sort((left, right) => right.version_number - left.version_number)[0] ?? null;
}

export function ProtocolCardPage() {
  const navigate = useNavigate();
  const { protocolId: routeProtocolId } = useParams<{ protocolId?: string }>();
  const [indexResponse, setIndexResponse] = useState<ProtocolCardListResponse | null>(null);
  const [detailResponse, setDetailResponse] = useState<ProtocolCardResponse | null>(null);
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockReasons, setMockReasons] = useState<string[]>([]);

  useEffect(() => {
    const titleSuffix = routeProtocolId ? ` ${routeProtocolId}` : "";
    document.title = `Protocol Cards${titleSuffix} | Lattice`;
  }, [routeProtocolId]);

  useEffect(() => {
    let mounted = true;

    async function loadIndex() {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setDetailResponse(null);
      setSelectedVersionId(null);
      setMockReasons([]);

      try {
        const result = await getProtocolCardIndex();
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

    async function loadDetail(protocolId: string) {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setDetailResponse(null);
      setSelectedVersionId(null);
      setMockReasons([]);

      try {
        const result = await getProtocolCard(protocolId);
        if (!mounted) {
          return;
        }
        setDetailResponse(result.data);
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

    if (routeProtocolId) {
      void loadDetail(routeProtocolId);
    } else {
      void loadIndex();
    }

    return () => {
      mounted = false;
    };
  }, [routeProtocolId]);

  const normalizedSearchQuery = indexSearchQuery.trim().toLowerCase();
  const filteredItems = useMemo(
    () => (indexResponse?.items ?? []).filter((item) => matchesProtocolQuery(item, normalizedSearchQuery)),
    [indexResponse, normalizedSearchQuery],
  );
  const protocolCard = detailResponse?.protocol_card ?? null;
  const versions = useMemo(
    () => [...(detailResponse?.versions ?? [])].sort((left, right) => right.version_number - left.version_number),
    [detailResponse],
  );
  const selectedVersion = useMemo(() => {
    if (!protocolCard) {
      return null;
    }
    if (selectedVersionId) {
      return versions.find((item) => item.version_id === selectedVersionId) ?? pickDefaultVersion(protocolCard, versions);
    }
    return pickDefaultVersion(protocolCard, versions);
  }, [protocolCard, versions, selectedVersionId]);

  useEffect(() => {
    if (!protocolCard) {
      setSelectedVersionId(null);
      return;
    }
    const defaultVersion = pickDefaultVersion(protocolCard, versions);
    setSelectedVersionId(defaultVersion?.version_id ?? null);
  }, [protocolCard, versions]);

  const primaryNoteHref = protocolCard?.linked_note_slugs[0]
    ? `/papers/${encodeURIComponent(protocolCard.linked_note_slugs[0])}`
    : null;

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <Route className="h-3.5 w-3.5" />
              Protocol knowledge review
            </div>
            <h1 className="mt-2 text-lg font-semibold text-[var(--pp-text-primary)]">
              {protocolCard?.title ?? "Protocol Cards"}
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Review saved protocol-card bundles before reusing a current version in notes or downstream artifacts.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockReasons.length > 0 ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            {routeProtocolId ? (
              <Button variant="outline" size="sm" onClick={() => navigate("/protocol-cards")}>
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
              to="/chart-packs"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Chart Packs
            </Link>
            <Link
              to="/image-evidence"
              className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-xs text-[var(--pp-text-secondary)]"
            >
              Image Evidence
            </Link>
            {primaryNoteHref ? (
              <Link
                to={primaryNoteHref}
                className="inline-flex h-8 items-center rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 text-xs font-medium text-[var(--pp-accent-text)]"
              >
                Open note
              </Link>
            ) : null}
          </div>
        </div>
        {mockReasons.length > 0 ? (
          <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
      </header>

      {error ? (
        <Card className="mb-4 border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <ShieldAlert className="h-4 w-4" />
              Protocol card unavailable
            </CardTitle>
            <CardDescription className="text-[var(--pp-warning-text)]/80">{error}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {!routeProtocolId ? (
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
            <CardHeader>
              <CardTitle className="text-sm">Search protocol cards</CardTitle>
              <CardDescription>Find saved protocol bundles by title, protocol ID, source kind, or validation state.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--pp-text-dim)]" />
                <Input
                  value={indexSearchQuery}
                  onChange={(event) => setIndexSearchQuery(event.target.value)}
                  placeholder="Search title or protocol id"
                  className="pl-9"
                />
              </div>
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-secondary)]">
                {indexResponse ? `${filteredItems.length} of ${indexResponse.total} saved protocol cards` : "Waiting for protocol cards"}
              </div>
            </CardContent>
          </Card>

          <div className="space-y-3">
            {loading ? (
              <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                <CardContent className="py-8 text-sm text-[var(--pp-text-secondary)]">Loading protocol cards…</CardContent>
              </Card>
            ) : null}

            {!loading && filteredItems.length === 0 ? (
              <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                <CardContent className="py-8 text-sm text-[var(--pp-text-secondary)]">
                  No protocol cards matched the current search.
                </CardContent>
              </Card>
            ) : null}

            {filteredItems.map((item) => (
              <article
                key={item.protocol_id}
                className="rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface)] p-4 shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className={`rounded-full border px-2 py-0.5 ${validationBadgeClassName(item.validation_status)}`}>
                        {validationStatusLabel(item.validation_status)}
                      </span>
                      <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-0.5 text-[var(--pp-text-secondary)]">
                        {sourceKindLabel(item.source_kind)}
                      </span>
                    </div>
                    <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">{item.title}</h2>
                    <p className="text-xs text-[var(--pp-text-dim)]">{item.protocol_id}</p>
                  </div>

                  <Button size="sm" onClick={() => navigate(`/protocol-cards/${encodeURIComponent(item.protocol_id)}`)}>
                    Open protocol card
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>

                <dl className="mt-4 grid gap-3 text-xs text-[var(--pp-text-secondary)] md:grid-cols-4">
                  <div>
                    <dt className="text-[var(--pp-text-dim)]">Current version</dt>
                    <dd className="mt-1 font-medium text-[var(--pp-text-primary)]">{item.current_version_id ?? "-"}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--pp-text-dim)]">Version count</dt>
                    <dd className="mt-1 font-medium text-[var(--pp-text-primary)]">{item.version_count}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--pp-text-dim)]">Linked papers</dt>
                    <dd className="mt-1 font-medium text-[var(--pp-text-primary)]">{item.linked_paper_count}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--pp-text-dim)]">Updated</dt>
                    <dd className="mt-1 font-medium text-[var(--pp-text-primary)]">{formatDateTime(item.updated_at)}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-4">
            {loading && !protocolCard ? (
              <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                <CardContent className="py-8 text-sm text-[var(--pp-text-secondary)]">Loading protocol card…</CardContent>
              </Card>
            ) : null}

            {protocolCard && selectedVersion ? (
              <>
                <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                  <CardHeader>
                    <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                      Version review
                      <span className={`rounded-full border px-2 py-0.5 text-xs ${validationBadgeClassName(protocolCard.validation_status)}`}>
                        {validationStatusLabel(protocolCard.validation_status)}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-xs ${versionStatusBadgeClassName(selectedVersion.status)}`}>
                        {versionStatusLabel(selectedVersion.status)}
                      </span>
                    </CardTitle>
                    <CardDescription>
                      The inspector is read-only. Current version state should be interpreted alongside its saved source refs.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Version</div>
                        <div className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">v{selectedVersion.version_number}</div>
                        <div className="mt-1 text-xs text-[var(--pp-text-secondary)]">{selectedVersion.version_id}</div>
                      </div>
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Created by</div>
                        <div className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{selectedVersion.created_by}</div>
                        <div className="mt-1 text-xs text-[var(--pp-text-secondary)]">{formatDateTime(selectedVersion.created_at)}</div>
                      </div>
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Source refs</div>
                        <div className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{selectedVersion.source_refs.length}</div>
                        <div className="mt-1 text-xs text-[var(--pp-text-secondary)]">Evidence-linked version snapshot</div>
                      </div>
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Source kind</div>
                        <div className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{sourceKindLabel(protocolCard.source_kind)}</div>
                        <div className="mt-1 text-xs text-[var(--pp-text-secondary)]">
                          {protocolCard.current_version_id === selectedVersion.version_id ? "Selected as current version" : "Historical version selected"}
                        </div>
                      </div>
                    </div>

                    {selectedVersion.change_reason ? (
                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                        <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Change reason</div>
                        <p className="mt-2 text-sm text-[var(--pp-text-primary)]">{selectedVersion.change_reason}</p>
                      </div>
                    ) : null}

                    <div className="grid gap-4 xl:grid-cols-2">
                      <Card className="border-[var(--pp-border)] bg-[var(--pp-surface-raised)]">
                        <CardHeader>
                          <CardTitle className="text-sm">Key steps</CardTitle>
                        </CardHeader>
                        <CardContent>
                          {selectedVersion.key_steps_summary.length > 0 ? (
                            <ul className="space-y-2 text-sm text-[var(--pp-text-primary)]">
                              {selectedVersion.key_steps_summary.map((step) => (
                                <li key={step} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-2">
                                  {step}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-sm text-[var(--pp-text-secondary)]">No key-step summary saved for this version.</p>
                          )}
                        </CardContent>
                      </Card>

                      <Card className="border-[var(--pp-border)] bg-[var(--pp-surface-raised)]">
                        <CardHeader>
                          <CardTitle className="text-sm">Critical conditions and readouts</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3 text-sm">
                          <div>
                            <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Critical conditions</div>
                            {selectedVersion.critical_conditions.length > 0 ? (
                              <ul className="mt-2 space-y-1 text-[var(--pp-text-primary)]">
                                {selectedVersion.critical_conditions.map((item) => (
                                  <li key={item}>• {item}</li>
                                ))}
                              </ul>
                            ) : (
                              <p className="mt-2 text-[var(--pp-text-secondary)]">No critical conditions saved.</p>
                            )}
                          </div>
                          <div>
                            <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Readouts</div>
                            {selectedVersion.readouts.length > 0 ? (
                              <ul className="mt-2 space-y-1 text-[var(--pp-text-primary)]">
                                {selectedVersion.readouts.map((item) => (
                                  <li key={item}>• {item}</li>
                                ))}
                              </ul>
                            ) : (
                              <p className="mt-2 text-[var(--pp-text-secondary)]">No readouts saved.</p>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    </div>

                    <Card className="border-[var(--pp-border)] bg-[var(--pp-surface-raised)]">
                      <CardHeader>
                        <CardTitle className="text-sm">Materials, equipment, and cautions</CardTitle>
                      </CardHeader>
                      <CardContent className="grid gap-4 text-sm md:grid-cols-3">
                        <div>
                          <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Materials</div>
                          {selectedVersion.materials.length > 0 ? (
                            <ul className="mt-2 space-y-1 text-[var(--pp-text-primary)]">
                              {selectedVersion.materials.map((item) => (
                                <li key={item}>• {item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-[var(--pp-text-secondary)]">No materials saved.</p>
                          )}
                        </div>
                        <div>
                          <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Equipment</div>
                          {selectedVersion.equipment.length > 0 ? (
                            <ul className="mt-2 space-y-1 text-[var(--pp-text-primary)]">
                              {selectedVersion.equipment.map((item) => (
                                <li key={item}>• {item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-[var(--pp-text-secondary)]">No equipment saved.</p>
                          )}
                        </div>
                        <div>
                          <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Cautions</div>
                          {selectedVersion.cautions.length > 0 ? (
                            <ul className="mt-2 space-y-1 text-[var(--pp-text-primary)]">
                              {selectedVersion.cautions.map((item) => (
                                <li key={item}>• {item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-[var(--pp-text-secondary)]">No cautions saved.</p>
                          )}
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-[var(--pp-border)] bg-[var(--pp-surface-raised)]">
                      <CardHeader>
                        <CardTitle className="text-sm">Content snapshot</CardTitle>
                        <CardDescription>Saved version text only. This viewer does not edit or execute protocol content.</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs leading-6 text-[var(--pp-text-primary)]">
                          {selectedVersion.content_snapshot}
                        </pre>
                        {selectedVersion.note ? (
                          <p className="mt-3 text-sm text-[var(--pp-text-secondary)]">{selectedVersion.note}</p>
                        ) : null}
                      </CardContent>
                    </Card>

                    <Card className="border-[var(--pp-border)] bg-[var(--pp-surface-raised)]">
                      <CardHeader>
                        <CardTitle className="text-sm">Source refs</CardTitle>
                        <CardDescription>Evidence-linked references saved with this version snapshot.</CardDescription>
                      </CardHeader>
                      <CardContent>
                        {selectedVersion.source_refs.length > 0 ? (
                          <div className="space-y-3">
                            {selectedVersion.source_refs.map((ref, index) => (
                              <article
                                key={`${ref.paper_slug}-${ref.claim_id ?? index}`}
                                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
                              >
                                <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--pp-text-secondary)]">
                                  <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-0.5">
                                    {ref.paper_slug}
                                  </span>
                                  {ref.claim_id ? <span>Claim {ref.claim_id}</span> : null}
                                  {ref.run_id ? <span>Run {ref.run_id}</span> : null}
                                </div>
                                <p className="mt-2 text-sm text-[var(--pp-text-primary)]">{formatLocator(ref.locator)}</p>
                              </article>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-[var(--pp-text-secondary)]">No source refs saved for this version.</p>
                        )}
                      </CardContent>
                    </Card>
                  </CardContent>
                </Card>

                <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                  <CardHeader>
                    <CardTitle className="text-sm">Saved markdown</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs leading-6 text-[var(--pp-text-primary)]">
                      {detailResponse?.markdown}
                    </pre>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </div>

          <div className="space-y-4">
            {protocolCard ? (
              <>
                <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                  <CardHeader>
                    <CardTitle className="text-sm">Version history</CardTitle>
                    <CardDescription>Current version stays highlighted, but historical snapshots remain inspectable.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {versions.map((version) => {
                      const isSelected = version.version_id === selectedVersion?.version_id;
                      const isCurrent = version.version_id === protocolCard.current_version_id;
                      return (
                        <button
                          key={version.version_id}
                          type="button"
                          onClick={() => setSelectedVersionId(version.version_id)}
                          className={`w-full rounded-md border p-3 text-left transition ${
                            isSelected
                              ? "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)]"
                              : "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] hover:bg-[var(--pp-surface)]"
                          }`}
                        >
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className={`rounded-full border px-2 py-0.5 ${versionStatusBadgeClassName(version.status)}`}>
                              {versionStatusLabel(version.status)}
                            </span>
                            {isCurrent ? (
                              <span className="rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-[var(--pp-accent-text)]">
                                Current version
                              </span>
                            ) : null}
                          </div>
                          <div className="mt-2 text-sm font-semibold text-[var(--pp-text-primary)]">v{version.version_number}</div>
                          <div className="mt-1 text-xs text-[var(--pp-text-secondary)]">{version.version_id}</div>
                          <div className="mt-2 text-xs text-[var(--pp-text-secondary)]">
                            {version.source_refs.length} source refs · {formatDateTime(version.created_at)}
                          </div>
                        </button>
                      );
                    })}
                  </CardContent>
                </Card>

                <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                  <CardHeader>
                    <CardTitle className="text-sm">Linked context</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm">
                    <div>
                      <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Linked papers</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {protocolCard.linked_paper_ids.length > 0 ? protocolCard.linked_paper_ids.map((paperId) => (
                          <span
                            key={paperId}
                            className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1 text-xs text-[var(--pp-text-secondary)]"
                          >
                            {paperId}
                          </span>
                        )) : <span className="text-[var(--pp-text-secondary)]">No linked papers.</span>}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Linked notes</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {protocolCard.linked_note_slugs.length > 0 ? protocolCard.linked_note_slugs.map((slug) => (
                          <Link
                            key={slug}
                            to={`/papers/${encodeURIComponent(slug)}`}
                            className="rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-1 text-xs text-[var(--pp-accent-text)]"
                          >
                            {slug}
                          </Link>
                        )) : <span className="text-[var(--pp-text-secondary)]">No linked notes.</span>}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                  <CardHeader>
                    <CardTitle className="text-sm">Trust boundary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                    <p>
                      This inspector reviews saved protocol knowledge. It does not validate experimental success or act as a protocol execution console.
                    </p>
                    <p>
                      Draft, reviewed, and verified-by-user states should be read literally. A saved current version is still bounded by its source refs and change reasons.
                    </p>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
