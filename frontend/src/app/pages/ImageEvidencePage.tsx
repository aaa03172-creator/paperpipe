import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Link2, Route, Search, ShieldAlert } from "lucide-react";
import { getApiErrorMessage, getImageEvidence, getImageEvidenceIndex } from "../lib/api";
import {
  ImageDerivedOutput,
  ImageEvidence,
  ImageEvidenceListItem,
  ImageEvidenceListResponse,
  ImageEvidenceResponse,
  ImageWarningSeverity,
} from "../lib/types";
import { Badge } from "../components/ui/badge";
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

function formatByteSize(value?: number | null): string {
  if (typeof value !== "number" || value < 0) {
    return "-";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
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

function matchesImageEvidenceQuery(item: ImageEvidenceListItem, query: string): boolean {
  if (!query) {
    return true;
  }
  const haystacks = [item.title, item.image_evidence_id, item.paper_id ?? "", item.paper_slug ?? "", item.content_format];
  return haystacks.some((value) => value.toLowerCase().includes(query));
}

function warningBadgeClassName(count: number): string {
  if (count > 0) {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
}

function warningToneClassName(severity: ImageWarningSeverity): string {
  if (severity === "warning" || severity === "error") {
    return "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)]";
}

function sourceKindLabel(kind: ImageEvidence["source_ref"]["source_kind"]): string {
  if (kind === "local_file") {
    return "Local file";
  }
  return "External image ref";
}

function derivedOutputKindLabel(kind: ImageDerivedOutput["kind"]): string {
  if (kind === "thumbnail") {
    return "Thumbnail";
  }
  if (kind === "representative_crop") {
    return "Representative crop";
  }
  if (kind === "measurement_export") {
    return "Measurement export";
  }
  if (kind === "overlay") {
    return "Overlay";
  }
  return "Derived output";
}

function describeSourceRef(imageEvidence: ImageEvidence): string {
  if (imageEvidence.source_ref.source_kind === "local_file") {
    return imageEvidence.source_ref.local_path ?? "Unavailable";
  }
  return imageEvidence.source_ref.external_ref ?? "Unavailable";
}

function dimensionText(imageEvidence: ImageEvidence): string {
  const width = imageEvidence.metadata.width_px;
  const height = imageEvidence.metadata.height_px;
  if (!width || !height) {
    return "-";
  }
  return `${width} × ${height}`;
}

export function ImageEvidencePage() {
  const navigate = useNavigate();
  const { imageEvidenceId: routeImageEvidenceId } = useParams<{ imageEvidenceId?: string }>();
  const [indexResponse, setIndexResponse] = useState<ImageEvidenceListResponse | null>(null);
  const [detailResponse, setDetailResponse] = useState<ImageEvidenceResponse | null>(null);
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockReasons, setMockReasons] = useState<string[]>([]);

  useEffect(() => {
    const titleSuffix = routeImageEvidenceId ? ` ${routeImageEvidenceId}` : "";
    document.title = `Image Evidence${titleSuffix} | Lattice`;
  }, [routeImageEvidenceId]);

  useEffect(() => {
    let mounted = true;

    async function loadIndex() {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setDetailResponse(null);
      setMockReasons([]);

      try {
        const result = await getImageEvidenceIndex();
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

    async function loadDetail(imageEvidenceId: string) {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setDetailResponse(null);
      setMockReasons([]);

      try {
        const result = await getImageEvidence(imageEvidenceId);
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

    if (routeImageEvidenceId) {
      void loadDetail(routeImageEvidenceId);
    } else {
      void loadIndex();
    }

    return () => {
      mounted = false;
    };
  }, [routeImageEvidenceId]);

  const normalizedSearchQuery = indexSearchQuery.trim().toLowerCase();
  const filteredItems = useMemo(
    () => (indexResponse?.items ?? []).filter((item) => matchesImageEvidenceQuery(item, normalizedSearchQuery)),
    [indexResponse, normalizedSearchQuery],
  );
  const imageEvidence = detailResponse?.image_evidence ?? null;
  const viewState = detailResponse?.view_state ?? null;
  const handoffTargets = detailResponse?.handoff_targets ?? [];
  const paperNoteHref = imageEvidence?.paper_slug ? `/papers/${encodeURIComponent(imageEvidence.paper_slug)}` : null;

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <Route className="h-3.5 w-3.5" />
              Image evidence review
            </div>
            <h1 className="mt-2 text-lg font-semibold text-[var(--pp-text-primary)]">
              {imageEvidence?.title ?? "Image Evidence"}
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Review saved image-evidence metadata before reuse in notes, packs, or external viewers.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockReasons.length > 0 ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            {routeImageEvidenceId ? (
              <Button variant="outline" size="sm" onClick={() => navigate("/image-evidence")}>
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to index
              </Button>
            ) : null}
            {paperNoteHref ? (
              <Link
                to={paperNoteHref}
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

      {routeImageEvidenceId ? (
        <main className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            {loading && !imageEvidence ? (
              <Card>
                <CardContent className="p-4 text-sm text-[var(--pp-text-dim)]">Loading image evidence…</CardContent>
              </Card>
            ) : null}

            {error && !imageEvidence ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-[var(--pp-status-failed-text)]">
                    <ShieldAlert className="h-4 w-4" />
                    Image evidence unavailable
                  </CardTitle>
                  <CardDescription>The viewer could not load this saved image-evidence bundle.</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                    {error}
                  </p>
                </CardContent>
              </Card>
            ) : null}

            {imageEvidence ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Bundle Review</CardTitle>
                    <CardDescription>
                      Raw source identity comes first; derived outputs and handoff metadata stay secondary.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{sourceKindLabel(imageEvidence.source_ref.source_kind)}</Badge>
                      <Badge variant="outline">{imageEvidence.content_format}</Badge>
                      <Badge variant="outline" className={warningBadgeClassName(imageEvidence.warnings.length)}>
                        {imageEvidence.warnings.length > 0 ? `${imageEvidence.warnings.length} warning` : "Clean bundle"}
                      </Badge>
                    </div>

                    <div className="grid gap-3 text-sm text-[var(--pp-text-secondary)] md:grid-cols-2">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Image Evidence ID</div>
                        <div className="mt-1 font-mono text-[var(--pp-text-primary)]">{imageEvidence.image_evidence_id}</div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Created</div>
                        <div className="mt-1">{formatDateTime(imageEvidence.created_at)}</div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Paper ID</div>
                        <div className="mt-1">{imageEvidence.paper_id ?? "Unlinked"}</div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Paper Note</div>
                        <div className="mt-1">
                          {paperNoteHref ? (
                            <Link to={paperNoteHref} className="text-[var(--pp-accent-text)] underline-offset-4 hover:underline">
                              {imageEvidence.paper_slug}
                            </Link>
                          ) : (
                            imageEvidence.paper_slug ?? "Unavailable"
                          )}
                        </div>
                      </div>
                      <div className="md:col-span-2">
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Raw Source Ref</div>
                        <pre className="mt-1 overflow-x-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs text-[var(--pp-text-secondary)]">
{describeSourceRef(imageEvidence)}
                        </pre>
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Source Label</div>
                        <div className="mt-1">{imageEvidence.source_ref.source_label ?? "Unavailable"}</div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Checksum</div>
                        <div className="mt-1 font-mono text-xs">
                          {imageEvidence.checksum ? `${imageEvidence.checksum.algorithm}:${imageEvidence.checksum.value}` : "Not recorded"}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Warnings</CardTitle>
                    <CardDescription>Bundle warnings remain visible instead of being hidden behind the saved JSON.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {imageEvidence.warnings.length > 0 ? (
                      imageEvidence.warnings.map((warning) => (
                        <div
                          key={`${warning.code}-${warning.message}`}
                          className={`rounded-md border p-3 text-sm ${warningToneClassName(warning.severity)}`}
                        >
                          <div className="text-[11px] font-semibold uppercase tracking-wide">{warning.code}</div>
                          <p className="mt-1">{warning.message}</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-[var(--pp-text-dim)]">No bundle warnings saved.</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Derived Outputs</CardTitle>
                    <CardDescription>
                      Derived outputs remain separate from the raw source and carry explicit provenance fields.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {imageEvidence.derived_outputs.length > 0 ? (
                      imageEvidence.derived_outputs.map((output) => (
                        <article
                          key={output.derived_output_id}
                          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div className="text-sm font-medium text-[var(--pp-text-primary)]">{derivedOutputKindLabel(output.kind)}</div>
                              <div className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">{output.derived_output_id}</div>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <Badge variant="outline">{output.tool_name}</Badge>
                              {output.tool_version ? <Badge variant="outline">{output.tool_version}</Badge> : null}
                            </div>
                          </div>

                          <div className="mt-3 grid gap-2 text-xs text-[var(--pp-text-dim)] sm:grid-cols-2">
                            <div>Created by: {output.created_by}</div>
                            <div>Created at: {formatDateTime(output.created_at)}</div>
                            <div>Source bundle: {output.source_image_evidence_id}</div>
                            <div>View-state ref: {output.view_state_ref?.path ?? "Unavailable"}</div>
                          </div>

                          <div className="mt-3 space-y-2 text-sm text-[var(--pp-text-secondary)]">
                            <div>
                              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Stored Ref</div>
                              <div className="mt-1 font-mono text-xs">
                                {output.bundle_ref?.path ?? output.external_ref ?? "Unavailable"}
                              </div>
                            </div>
                            {output.note ? <p>{output.note}</p> : null}
                          </div>
                        </article>
                      ))
                    ) : (
                      <p className="text-sm text-[var(--pp-text-dim)]">No derived outputs registered.</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Linked References</CardTitle>
                    <CardDescription>Claim and artifact links stay explicit instead of pretending to be validated image grounding.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Linked Claims</div>
                      {imageEvidence.linked_claim_refs.length > 0 ? (
                        imageEvidence.linked_claim_refs.map((link) => (
                          <div key={link.claim_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm">
                            <div className="font-mono text-xs text-[var(--pp-text-dim)]">{link.claim_id}</div>
                            <div className="mt-1 text-[var(--pp-text-secondary)]">{link.note ?? "No note saved."}</div>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-[var(--pp-text-dim)]">No linked claims saved.</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Linked Artifacts</div>
                      {imageEvidence.linked_artifact_refs.length > 0 ? (
                        imageEvidence.linked_artifact_refs.map((link) => (
                          <div
                            key={`${link.artifact_kind}-${link.artifact_id}`}
                            className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm"
                          >
                            <div className="font-mono text-xs text-[var(--pp-text-dim)]">
                              {link.artifact_kind} / {link.artifact_id}
                            </div>
                            <div className="mt-1 text-[var(--pp-text-secondary)]">{link.note ?? "No note saved."}</div>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-[var(--pp-text-dim)]">No linked artifacts saved.</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </div>

          <aside className="space-y-4">
            {imageEvidence ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Bundle Summary</CardTitle>
                    <CardDescription>Quick trust-calibration before reusing the bundle downstream.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                    <div className="flex items-center justify-between">
                      <span>Derived outputs</span>
                      <Badge variant="outline">{imageEvidence.derived_outputs.length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Warnings</span>
                      <Badge variant="outline" className={warningBadgeClassName(imageEvidence.warnings.length)}>
                        {imageEvidence.warnings.length}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>View state</span>
                      <Badge variant="outline">{viewState ? "Saved" : "None"}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Handoff targets</span>
                      <Badge variant="outline">{handoffTargets.length}</Badge>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Metadata</CardTitle>
                    <CardDescription>Saved operator-visible metadata only. No pixel analysis is performed here.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                    <div className="flex items-center justify-between gap-3">
                      <span>Filename</span>
                      <span className="text-right">{imageEvidence.metadata.filename ?? "Unavailable"}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Size</span>
                      <span className="text-right">{formatByteSize(imageEvidence.metadata.source_size_bytes)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Dimensions</span>
                      <span className="text-right">{dimensionText(imageEvidence)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Channels</span>
                      <span className="text-right">{imageEvidence.metadata.channel_count ?? "-"}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Modality</span>
                      <span className="text-right">{imageEvidence.metadata.modality ?? "-"}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Acquired</span>
                      <span className="text-right">{formatDateTime(imageEvidence.metadata.source_created_at)}</span>
                    </div>
                    {imageEvidence.metadata.acquisition_note ? (
                      <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs">
                        {imageEvidence.metadata.acquisition_note}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>View State</CardTitle>
                    <CardDescription>Saved viewport and channel context, not a new canonical evidence model.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                    {viewState ? (
                      <>
                        <div className="flex flex-wrap gap-1.5">
                          {viewState.active_channels.length > 0 ? viewState.active_channels.map((channel) => (
                            <Badge key={channel} variant="outline">{channel}</Badge>
                          )) : (
                            <span className="text-[var(--pp-text-dim)]">No active channels saved.</span>
                          )}
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>Zoom</span>
                          <span>{viewState.zoom_level ?? "-"}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>z-index</span>
                          <span>{viewState.z_index ?? "-"}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>t-index</span>
                          <span>{viewState.t_index ?? "-"}</span>
                        </div>
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Viewport</div>
                          <div className="mt-1 text-xs">
                            {viewState.viewport
                              ? `${viewState.viewport.x}, ${viewState.viewport.y}, ${viewState.viewport.width}, ${viewState.viewport.height}`
                              : "Unavailable"}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Overlays</div>
                          <div className="mt-1 text-xs">{viewState.visible_overlays.join(", ") || "None"}</div>
                        </div>
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Selected Regions</div>
                          <div className="mt-1 text-xs">{viewState.selected_region_labels.join(", ") || "None"}</div>
                        </div>
                        {viewState.note ? (
                          <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs">
                            {viewState.note}
                          </p>
                        ) : null}
                      </>
                    ) : (
                      <p className="text-sm text-[var(--pp-text-dim)]">No view state saved for this bundle.</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Handoff Targets</CardTitle>
                    <CardDescription>Structured viewer handoff metadata only. This surface does not launch external tools.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {handoffTargets.length > 0 ? handoffTargets.map((target) => (
                      <div
                        key={`${target.target}-${target.openable_ref}`}
                        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-secondary)]"
                      >
                        <div className="flex items-center gap-2">
                          <Link2 className="h-4 w-4 text-[var(--pp-text-dim)]" />
                          <span className="font-medium text-[var(--pp-text-primary)]">{target.target}</span>
                        </div>
                        <pre className="mt-2 overflow-x-auto rounded-md bg-[var(--pp-surface)] p-2 text-xs text-[var(--pp-text-secondary)]">
{target.openable_ref}
                        </pre>
                        {target.view_state_ref?.path ? (
                          <div className="mt-2 text-xs text-[var(--pp-text-dim)]">View-state ref: {target.view_state_ref.path}</div>
                        ) : null}
                        {target.notes ? <p className="mt-2 text-xs">{target.notes}</p> : null}
                      </div>
                    )) : (
                      <p className="text-sm text-[var(--pp-text-dim)]">No handoff targets saved for this bundle.</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Trust Boundary</CardTitle>
                    <CardDescription>What this viewer helps you verify, and what it does not.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-[var(--pp-text-secondary)]">
                    <p>This viewer confirms saved metadata, warning state, and raw-vs-derived lineage.</p>
                    <p>It does not validate pixel-level interpretation, ROI correctness, or claim truth.</p>
                    <p>Representative outputs should be treated as operator-scoped derivatives unless separately validated elsewhere.</p>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </aside>
        </main>
      ) : (
        <main className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="h-4 w-4" />
                Search image bundles
              </CardTitle>
              <CardDescription>Find saved image-evidence bundles by title, bundle id, paper id, or slug.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                value={indexSearchQuery}
                onChange={(event) => setIndexSearchQuery(event.target.value)}
                placeholder="Search title or image evidence id"
              />
              <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-dim)]">
                Image evidence stays metadata-first in v0. This index is for trust calibration, not image interpretation.
              </div>
            </CardContent>
          </Card>

          <section className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Saved image bundles</CardTitle>
                <CardDescription>Open a saved bundle to inspect warnings, derived-output lineage, and handoff metadata.</CardDescription>
              </CardHeader>
              <CardContent>
                {loading && !indexResponse ? (
                  <p className="text-sm text-[var(--pp-text-dim)]">Loading image evidence…</p>
                ) : null}

                {error && !indexResponse ? (
                  <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] p-3 text-sm text-[var(--pp-status-failed-text)]">
                    {error}
                  </p>
                ) : null}

                {indexResponse ? (
                  filteredItems.length > 0 ? (
                    <div className="space-y-3">
                      {filteredItems.map((item) => (
                        <article
                          key={item.image_evidence_id}
                          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div className="text-sm font-medium text-[var(--pp-text-primary)]">{item.title}</div>
                              <div className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">{item.image_evidence_id}</div>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <Badge variant="outline">{item.content_format}</Badge>
                              <Badge variant="outline" className={warningBadgeClassName(item.warning_count)}>
                                {item.warning_count > 0 ? `${item.warning_count} warning` : "Clean bundle"}
                              </Badge>
                            </div>
                          </div>

                          <div className="mt-3 grid gap-2 text-xs text-[var(--pp-text-dim)] sm:grid-cols-2">
                            <div>Paper: {item.paper_id ?? "Unlinked"}</div>
                            <div>Created: {formatDateTime(item.created_at)}</div>
                            <div>Derived outputs: {item.derived_output_count}</div>
                            <div>View state / handoff: {item.has_view_state ? "saved" : "none"} / {item.has_handoff ? "saved" : "none"}</div>
                          </div>

                          <div className="mt-3 flex items-center justify-end">
                            <Button size="sm" onClick={() => navigate(`/image-evidence/${item.image_evidence_id}`)}>
                              Open bundle
                              <ArrowRight className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--pp-text-dim)]">No saved bundles matched this query.</p>
                  )
                ) : null}
              </CardContent>
            </Card>
          </section>
        </main>
      )}
    </div>
  );
}
