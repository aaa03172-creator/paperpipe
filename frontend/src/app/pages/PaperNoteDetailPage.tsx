import { Children, ReactNode, isValidElement, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, FileText, FlaskConical, LibraryBig, Link2, PanelRightOpen, ScrollText, ShieldCheck } from "lucide-react";
import { getApiErrorMessage, getPaperNoteDetail, logClientUserAction, runSkillAction } from "../lib/api";
import {
  OutputModeFamily,
  PaperNoteContextTrace,
  PaperNoteDetailResponse,
  PaperNoteReference,
  PaperNoteRelated,
  PaperNoteSummary,
  SkillActionInfo,
  SkillClaimCard,
  SkillRunRecord,
  StructuredPaperState,
} from "../lib/types";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
import { StatusBadge } from "../components/StatusBadge";
import { formatFreeformStatusLabel, getFreeformStatusTone } from "../lib/statusSystem";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Separator } from "../components/ui/separator";
import { Sheet } from "../components/ui/sheet";

interface OutlineItem {
  id: string;
  label: string;
  level: number;
}

type FocusKind = "claim" | "evidence" | "run";
type ViewerOutputMode = Extract<OutputModeFamily, "learner" | "builder_debug">;

interface FocusTarget {
  kind: FocusKind;
  id: string;
}

function parseViewerOutputMode(value: string | null): ViewerOutputMode {
  return value === "builder_debug" ? "builder_debug" : "learner";
}

function formatViewerOutputModeLabel(value: ViewerOutputMode): string {
  return value === "builder_debug" ? "Inspect" : "Learner";
}

function buildViewerModeSearchParams(searchParams: URLSearchParams, mode: ViewerOutputMode): URLSearchParams {
  const next = new URLSearchParams(searchParams);
  if (mode === "learner") {
    next.delete("view");
  } else {
    next.set("view", mode);
  }
  return next;
}

function getViewerModeSummary(value: ViewerOutputMode): string {
  if (value === "builder_debug") {
    return "Inspect mode lifts actions, run history, and structured claims ahead of supporting context.";
  }
  return "Learner mode keeps related papers, references, and reading context closer to the markdown flow.";
}

function getViewerContextDescription(value: ViewerOutputMode): string {
  if (value === "builder_debug") {
    return "Inspect structured outputs and operational state first, then hand off to Workbench when deeper evidence debugging is needed.";
  }
  return "Use the note outline, related papers, and references before handing off to Workbench for evidence validation.";
}

function getReadingViewDescription(value: ViewerOutputMode): string {
  if (value === "builder_debug") {
    return "Markdown body stays canonical while the surrounding rail prioritizes inspection-oriented structured outputs.";
  }
  return "Markdown body rendered from the Obsidian note, with internal wiki-links preserved and reading support kept close.";
}

function parseFocusParam(value: string | null): FocusTarget | null {
  if (!value) {
    return null;
  }
  const separator = value.indexOf(":");
  if (separator <= 0) {
    return null;
  }
  const kind = value.slice(0, separator) as FocusKind;
  const id = value.slice(separator + 1).trim();
  if (!["claim", "evidence", "run"].includes(kind) || !id) {
    return null;
  }
  return { kind, id };
}

function toFocusDomId(kind: FocusKind, id: string): string {
  return `pp-focus-${kind}-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function buildFocusHref(kind: FocusKind, id: string): string {
  return `?focus=${encodeURIComponent(`${kind}:${id}`)}`;
}

function getFocusClassName(active: boolean): string {
  if (!active) {
    return "";
  }
  return "ring-2 ring-[var(--pp-accent-text)] ring-offset-2 ring-offset-[var(--pp-surface-raised)]";
}

function getGroundingBadge(grounded?: boolean | null, resolution?: string | null): { label: string; className: string } | null {
  if (grounded === true) {
    if (resolution === "NORMALIZED_MATCH") {
      return {
        label: "Grounded (normalized)",
        className:
          "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
      };
    }
    return {
      label: "Grounded",
      className:
        "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
    };
  }
  if (grounded === false) {
    if (resolution === "AMBIGUOUS_MATCH") {
      return {
        label: "Needs review",
        className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
      };
    }
    return {
      label: "Unresolved",
      className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    };
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function getRunWriteScopeBadges(run: SkillRunRecord): Array<{ label: string; variant: "outline" | "muted" }> {
  if (!isRecord(run.artifacts)) {
    return [];
  }
  const writeScope = isRecord(run.artifacts.write_scope) ? run.artifacts.write_scope : null;
  if (!writeScope) {
    return [];
  }
  const badges: Array<{ label: string; variant: "outline" | "muted" }> = [];
  if (writeScope.structured_state === true) {
    badges.push({ label: "state updated", variant: "outline" });
  }
  if (writeScope.frontmatter_pp === true) {
    badges.push({ label: "frontmatter updated", variant: "outline" });
  }
  if (writeScope.markdown_summary === true) {
    badges.push({ label: "body summary", variant: "muted" });
  } else if (writeScope.markdown_summary === false) {
    badges.push({ label: "body skipped", variant: "muted" });
  }
  return badges;
}

type SignalDiff = {
  key: string;
  label: string;
  kind: "new" | "changed";
  before: string | null;
  after: string;
};

const SIGNAL_DIFF_LABELS: Record<string, string> = {
  citation_count: "citations",
  run_count: "runs",
  claim_count: "claims",
  evidence_count: "evidence",
  has_claimset: "structured claims",
  last_appraisal: "appraisal",
  last_action: "last action",
  last_status: "last status",
};

const SIGNAL_DIFF_ORDER = [
  "citation_count",
  "run_count",
  "claim_count",
  "evidence_count",
  "has_claimset",
  "last_appraisal",
  "last_action",
  "last_status",
] as const;

function formatSignalValue(key: string, value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "boolean") {
    return key === "has_claimset" ? (value ? "ready" : "not ready") : value ? "yes" : "no";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  return null;
}

function getSignalRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function computeSignalDiffs(before: unknown, after: unknown): SignalDiff[] {
  const previousSignals = getSignalRecord(before);
  const nextSignals = getSignalRecord(after);
  const diffs: SignalDiff[] = [];

  for (const key of SIGNAL_DIFF_ORDER) {
    const label = SIGNAL_DIFF_LABELS[key];
    const beforeValue = formatSignalValue(key, previousSignals[key]);
    const afterValue = formatSignalValue(key, nextSignals[key]);
    if (afterValue === null || beforeValue === afterValue) {
      continue;
    }
    if (key === "has_claimset" && afterValue === "not ready" && (beforeValue === null || beforeValue === "not ready")) {
      continue;
    }
    if ((key === "claim_count" || key === "evidence_count") && afterValue === "0" && beforeValue === null) {
      continue;
    }
    diffs.push({
      key,
      label,
      kind: beforeValue === null ? "new" : "changed",
      before: beforeValue,
      after: afterValue,
    });
  }

  return diffs;
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

function confidenceLabel(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function resolveWorkbenchPaperId(note: PaperNoteDetailResponse["note"] | null): string | null {
  if (!note) {
    return null;
  }
  const id = (note.id ?? "").trim();
  if (id.length > 0) {
    return id;
  }
  if (note.slug.startsWith("zotero") && !note.slug.includes(":")) {
    return `zotero:${note.slug.slice("zotero".length)}`;
  }
  return note.slug;
}

function slugifyHeading(value: string): string {
  return value
    .toLowerCase()
    .replace(/[`*_~[\]().,:;!?/\\]+/g, " ")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function extractNodeText(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number") {
        return String(child);
      }
      if (isValidElement<{ children?: ReactNode }>(child)) {
        return extractNodeText(child.props.children);
      }
      return "";
    })
    .join(" ")
    .trim();
}

function extractOutline(markdown: string, noteTitle?: string | null): OutlineItem[] {
  const seen = new Map<string, number>();
  const items: OutlineItem[] = [];
  const lines = markdown.split("\n");
  for (const line of lines) {
    const match = /^(#{1,3})\s+(.+?)\s*$/.exec(line.trim());
    if (!match) {
      continue;
    }
    const level = match[1].length;
    const label = match[2].trim();
    if (!label) {
      continue;
    }
    if (level === 1 && noteTitle && label === noteTitle.trim()) {
      continue;
    }
    const baseId = slugifyHeading(label);
    if (!baseId) {
      continue;
    }
    const count = (seen.get(baseId) ?? 0) + 1;
    seen.set(baseId, count);
    items.push({
      id: count === 1 ? baseId : `${baseId}-${count}`,
      label,
      level,
    });
  }
  return items;
}

function getReferencePolicyMessage(references: PaperNoteReference[]): string {
  const hasPdf = references.some((reference) => reference.source === "pdf");
  if (hasPdf) {
    return "Local-safe PDF links may appear here. If they are unavailable or masked, DOI and Zotero remain the default access paths.";
  }
  return "This note currently prefers DOI or Zotero links over direct PDF exposure.";
}

function getReferenceSourceLabel(source: PaperNoteReference["source"]): string {
  switch (source) {
    case "pdf":
      return "Private-safe PDF";
    case "doi":
      return "Canonical DOI";
    case "zotero":
      return "Zotero Library";
    default:
      return "External Link";
  }
}

function getReferenceSourceDescription(source: PaperNoteReference["source"]): string {
  switch (source) {
    case "pdf":
      return "Direct document access shown only when the link appears local-safe.";
    case "doi":
      return "Stable citation target preferred when direct PDF exposure is not appropriate.";
    case "zotero":
      return "Open the note from your personal library workflow.";
    default:
      return "Supplementary publisher or external resource.";
  }
}

function getReferencePolicySummary(references: PaperNoteReference[]): {
  primaryLabel: string;
  summary: string;
  detail: string;
} {
  const first = references[0] ?? null;
  const hasPdf = references.some((reference) => reference.source === "pdf");
  const hasDoi = references.some((reference) => reference.source === "doi");
  const hasZotero = references.some((reference) => reference.source === "zotero");

  if (hasPdf) {
    return {
      primaryLabel: first ? getReferenceSourceLabel(first.source) : "Private-safe PDF",
      summary: "Direct PDF access is available for this note.",
      detail: "This usually means the source looks local/private-safe. DOI or Zotero remain safer fallback paths when you need a citation or library context.",
    };
  }

  if (hasDoi || hasZotero) {
    return {
      primaryLabel: first ? getReferenceSourceLabel(first.source) : "DOI or Zotero",
      summary: "This viewer is avoiding direct PDF exposure.",
      detail: "Use DOI for canonical citation routing and Zotero for library-based access. Local PDF links may be absent or intentionally masked.",
    };
  }

  return {
    primaryLabel: first ? getReferenceSourceLabel(first.source) : "External Link",
    summary: "Only external reference links are available for this note.",
    detail: "The viewer can still route you to publisher or supporting resources even when no DOI, Zotero, or private-safe PDF link is present.",
  };
}

function HeadingWithAnchor({
  level,
  children,
}: {
  level: 1 | 2 | 3;
  children: ReactNode;
}) {
  const text = extractNodeText(children);
  const id = slugifyHeading(text);
  const Tag = `h${level}` as "h1" | "h2" | "h3";
  return (
    <Tag id={id}>
      <a href={`#${id}`} className="paper-note-heading-anchor">
        {children}
      </a>
    </Tag>
  );
}

function PropertiesPanel({
  note,
  aliases,
  tags,
}: {
  note: PaperNoteSummary | null;
  aliases: string[];
  tags: string[];
}) {
  const signals = (note?.pp_signals ?? {}) as Record<string, unknown>;
  const citationCount = typeof signals.citation_count === "number" ? signals.citation_count : null;
  const hasClaimset = signals.has_claimset === true;
  const lastAppraisal = typeof signals.last_appraisal === "string" ? signals.last_appraisal : null;
  const opsSummary = note?.ops_summary ?? null;

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Properties</CardTitle>
        <CardDescription>Frontmatter mirrored from the Obsidian note.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <dl className="space-y-4 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">id</dt>
            <dd className="mt-1 break-all text-[var(--pp-text-primary)]">{note?.id ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">aliases</dt>
            <dd className="mt-1 text-[var(--pp-text-primary)]">{aliases.length > 0 ? aliases.join(" | ") : "-"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">tags</dt>
            <dd className="mt-1 flex flex-wrap gap-1.5">
              {tags.length > 0 ? tags.map((tag) => <Badge key={`tag-${tag}`}>{tag}</Badge>) : <span>-</span>}
            </dd>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">date</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{formatDate(note?.date_processed)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">confidence</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{confidenceLabel(note?.confidence)}</dd>
            </div>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">status</dt>
            <dd className="mt-1">
              <StatusBadge label={formatFreeformStatusLabel(note?.status)} tone={getFreeformStatusTone(note?.status)} />
            </dd>
          </div>
          {opsSummary ? (
            <div data-testid="paper-note-ops-summary">
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">operational state</dt>
              <dd className="mt-1">
                <OperationalStateSummary
                  summary={opsSummary}
                  badgeTestId="paper-note-ops-badge"
                  reasonTestId="paper-note-ops-reason"
                />
              </dd>
            </div>
          ) : null}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">citations</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{citationCount ?? "-"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">structured claims</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{hasClaimset ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">appraisal</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{lastAppraisal ?? "-"}</dd>
            </div>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

function OutlinePanel({
  outline,
  onNavigate,
}: {
  outline: OutlineItem[];
  onNavigate?: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Outline</CardTitle>
        <CardDescription>Jump across the note like an Obsidian reading sidebar.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {outline.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No headings were detected in this note.</p>
        ) : (
          <nav aria-label="Note outline">
            <ul className="space-y-1">
              {outline.map((item) => (
                <li key={item.id}>
                  <a
                    href={`#${item.id}`}
                    onClick={onNavigate}
                    className="block rounded-md px-2 py-1.5 text-sm text-[var(--pp-text-secondary)] transition-colors hover:bg-[var(--pp-surface-muted)] hover:text-[var(--pp-text-primary)]"
                    style={{ paddingLeft: `${0.5 + Math.max(item.level - 1, 0) * 0.75}rem` }}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </CardContent>
    </Card>
  );
}

function RelatedPapersPanel({
  related,
  onNavigate,
}: {
  related: PaperNoteRelated[];
  onNavigate?: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Related Papers</CardTitle>
        <CardDescription>Recommended by shared tags plus structured signals from the same vault.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {related.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No related papers found by shared tags or structured signals.</p>
        ) : (
          <ul className="space-y-3">
            {related.map((item) => (
              <li key={`related-${item.slug}`} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                <Link
                  to={`/papers/${encodeURIComponent(item.slug)}`}
                  onClick={onNavigate}
                  className="paper-note-link text-sm font-medium"
                >
                  {item.title}
                </Link>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.shared_tags.map((tag) => (
                    <Badge key={`${item.slug}-${tag}`} variant="outline">
                      {tag}
                    </Badge>
                  ))}
                  {item.shared_signals.map((signal) => (
                    <Badge key={`${item.slug}-signal-${signal}`} variant="muted">
                      {signal}
                    </Badge>
                  ))}
                </div>
                <p className="mt-2 text-xs text-[var(--pp-text-dim)]">
                  shared tags: {item.shared_tags.join(", ") || "-"}
                  {item.shared_signals.length > 0 ? ` · structured signals: ${item.shared_signals.join(", ")}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ReferencesPanel({ references }: { references: PaperNoteReference[] }) {
  const policy = getReferencePolicySummary(references);
  const hasDoi = references.some((reference) => reference.source === "doi");
  const hasZotero = references.some((reference) => reference.source === "zotero");

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>References</CardTitle>
        <CardDescription>{getReferencePolicyMessage(references)}</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {references.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No references available.</p>
        ) : (
          <div className="space-y-3">
            <section
              className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
              data-testid="paper-note-reference-policy"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Access Policy</p>
                  <p className="mt-1 text-sm font-medium text-[var(--pp-text-primary)]">{policy.summary}</p>
                </div>
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--pp-accent-text)]" />
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge variant="outline">Preferred: {policy.primaryLabel}</Badge>
                {hasDoi ? <Badge variant="muted">DOI ready</Badge> : null}
                {hasZotero ? <Badge variant="muted">Zotero ready</Badge> : null}
              </div>
              <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{policy.detail}</p>
            </section>

            <ul className="space-y-3">
              {references.map((reference, idx) => (
                <li key={`reference-${idx}`} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <a
                      href={reference.url}
                      target="_blank"
                      rel="noreferrer"
                      className="paper-note-link inline-flex min-w-0 items-center gap-1 text-sm font-medium"
                    >
                      <span className="truncate">{reference.label}</span>
                      <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                    </a>
                    <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                      {idx === 0 ? <Badge variant="outline">Preferred</Badge> : null}
                      <Badge variant="muted" className="uppercase">
                        {reference.source}
                      </Badge>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-xs text-[var(--pp-text-dim)]">
                    {reference.source === "pdf" ? <FileText className="h-3.5 w-3.5" /> : null}
                    {reference.source === "doi" ? <Link2 className="h-3.5 w-3.5" /> : null}
                    {reference.source === "zotero" ? <LibraryBig className="h-3.5 w-3.5" /> : null}
                    {reference.source === "external" ? <ExternalLink className="h-3.5 w-3.5" /> : null}
                    <span>{getReferenceSourceDescription(reference.source)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ActionsPanel({
  actions,
  runningAction,
  actionMessage,
  signalDiffs,
  appendMarkdownSummary,
  onAppendMarkdownSummaryChange,
  onRun,
}: {
  actions: SkillActionInfo[];
  runningAction: SkillActionInfo["action"] | null;
  actionMessage: string | null;
  signalDiffs: SignalDiff[];
  appendMarkdownSummary: boolean;
  onAppendMarkdownSummaryChange: (value: boolean) => void;
  onRun: (action: SkillActionInfo["action"]) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Actions</CardTitle>
        <CardDescription>Safe skill actions gated by license, network, and secret policy.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="grid gap-3 pt-4">
        <label
          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
          data-testid="paper-note-append-markdown-toggle"
        >
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={appendMarkdownSummary}
              onChange={(event) => onAppendMarkdownSummaryChange(event.target.checked)}
              disabled={runningAction !== null}
              className="mt-0.5 h-4 w-4 rounded border border-[var(--pp-border)] bg-[var(--pp-surface)] accent-[var(--pp-accent-text)]"
            />
            <div>
              <p className="text-sm font-medium text-[var(--pp-text-primary)]">Add short note summary</p>
              <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                Structured state stays canonical. This only controls whether a short run summary is appended to the
                markdown body.
              </p>
            </div>
          </div>
        </label>
        {actions.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No approved actions are available for this note.</p>
        ) : (
          actions.map((action) => (
            <article key={action.action} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-[var(--pp-text-primary)]">{action.title}</p>
                  <p className="mt-1 text-xs text-[var(--pp-text-dim)]">{action.description}</p>
                </div>
                <Button
                  size="sm"
                  onClick={() => onRun(action.action)}
                  disabled={!action.enabled || runningAction !== null}
                >
                  {runningAction === action.action ? "Running..." : action.button_label}
                </Button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge variant="outline">{action.network}</Badge>
                {action.sandbox ? <Badge variant="muted">{action.sandbox}</Badge> : null}
                {action.license ? <Badge variant="outline">{action.license}</Badge> : null}
                {action.secrets_required.map((secret) => (
                  <Badge key={`${action.action}-${secret}`} variant="outline">
                    secret {secret}
                  </Badge>
                ))}
                {action.source_skills.map((skill) => (
                  <Badge key={`${action.action}-${skill}`}>{skill}</Badge>
                ))}
              </div>
              {!action.enabled && action.disabled_reason ? (
                <p
                  className="mt-2 text-xs text-[var(--pp-text-secondary)]"
                  data-testid={`paper-note-action-disabled-reason-${action.action}`}
                >
                  {action.disabled_reason}
                </p>
              ) : null}
            </article>
          ))
        )}
        {actionMessage ? <p className="text-xs text-[var(--pp-text-secondary)]">{actionMessage}</p> : null}
        {signalDiffs.length > 0 ? (
          <div
            className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
            data-testid="paper-note-signal-diff"
          >
            <p className="text-sm font-medium text-[var(--pp-text-primary)]">Signal updates</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {signalDiffs.map((diff) => (
                <Badge key={diff.key} variant="outline">
                  {diff.kind === "new" ? `new ${diff.label}: ${diff.after}` : `${diff.label}: ${diff.before} -> ${diff.after}`}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function AutomationResultsPanel({
  state,
  focusTarget,
}: {
  state: StructuredPaperState | null;
  focusTarget: FocusTarget | null;
}) {
  const runs = state?.runs ?? [];
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Run history</CardTitle>
        <CardDescription>Structured runs recorded in the note sidecar state.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {state ? (
          <div className="mb-3 flex flex-wrap gap-1.5">
            <Badge variant="outline">runs {runs.length}</Badge>
            <Badge variant="outline">claims {Number(state.signals.claim_count ?? state.claimset.length)}</Badge>
            <Badge variant="outline">
              evidence {Number(state.signals.evidence_count ?? state.claimset.reduce((sum, claim) => sum + claim.evidence.length, 0))}
            </Badge>
          </div>
        ) : null}
        {runs.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No structured runs recorded yet.</p>
        ) : (
          <div className="grid gap-3">
            {runs.map((run: SkillRunRecord) => {
              const writeScopeBadges = getRunWriteScopeBadges(run);
              return (
                <article
                  key={run.id}
                  id={toFocusDomId("run", run.id)}
                  className={`rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 ${getFocusClassName(
                    focusTarget?.kind === "run" && focusTarget.id === run.id,
                  )}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-[var(--pp-text-primary)]">{run.action}</p>
                      <p className="mt-1 text-xs text-[var(--pp-text-dim)]">{formatDateTime(run.ts)}</p>
                      <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">{run.id}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1.5">
                      <Badge variant={run.status === "succeeded" ? "muted" : "outline"}>{run.status}</Badge>
                      <Link to={buildFocusHref("run", run.id)} className="paper-note-link text-[11px]">
                        Deep link
                      </Link>
                    </div>
                  </div>
                  <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">{run.summary}</p>
                  {writeScopeBadges.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5" data-testid="paper-note-run-write-scope">
                      {writeScopeBadges.map((badge) => (
                        <Badge key={`${run.id}-${badge.label}`} variant={badge.variant}>
                          {badge.label}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ClaimSetPanel({
  claims,
  focusTarget,
}: {
  claims: SkillClaimCard[];
  focusTarget: FocusTarget | null;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Structured claims</CardTitle>
        <CardDescription>Claim cards rendered from structured state for review and retrieval.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {claims.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No structured claims are available for this note.</p>
        ) : (
          <div className="grid gap-3">
            {claims.map((claim) => (
              <article
                key={claim.id}
                id={toFocusDomId("claim", claim.id)}
                className={`rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 ${getFocusClassName(
                  focusTarget?.kind === "claim" && focusTarget.id === claim.id,
                )}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-[var(--pp-text-primary)]">{claim.claim}</p>
                    <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">{claim.id}</p>
                    {claim.source_claim_id ? (
                      <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">source {claim.source_claim_id}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    {typeof claim.confidence === "number" ? (
                      <Badge variant="outline">{claim.confidence.toFixed(2)}</Badge>
                    ) : null}
                    <Link to={buildFocusHref("claim", claim.id)} className="paper-note-link text-[11px]">
                      Deep link
                    </Link>
                  </div>
                </div>
                {claim.evidence.length > 0 ? (
                  <ul className="mt-3 space-y-2 text-xs text-[var(--pp-text-secondary)]">
                    {claim.evidence.map((evidence, index) => {
                      const evidenceId = evidence.id ?? `${claim.id}-evidence-${index + 1}`;
                      const groundingBadge = getGroundingBadge(evidence.grounded, evidence.resolution);
                      return (
                        <li
                          key={`${claim.id}-evidence-${index}`}
                          id={toFocusDomId("evidence", evidenceId)}
                          className={`rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2 ${getFocusClassName(
                            focusTarget?.kind === "evidence" && focusTarget.id === evidenceId,
                          )}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <p>{evidence.text}</p>
                            <Link to={buildFocusHref("evidence", evidenceId)} className="paper-note-link shrink-0 text-[11px]">
                              Deep link
                            </Link>
                          </div>
                          <p className="mt-1 break-all text-[11px] text-[var(--pp-text-dim)]">{evidenceId}</p>
                          <p className="mt-1 text-[var(--pp-text-dim)]">
                            {evidence.locator?.section ?? evidence.section ?? "Section n/a"}
                            {typeof (evidence.locator?.page ?? evidence.page) === "number"
                              ? ` · page ${(evidence.locator?.page ?? evidence.page ?? 0) + 1}`
                              : ""}
                            {evidence.locator?.chunk_id ? ` · ${evidence.locator.chunk_id}` : ""}
                            {evidence.locator?.source ?? evidence.source ? ` · ${evidence.locator?.source ?? evidence.source}` : ""}
                          </p>
                          {groundingBadge ? (
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              <Badge className={groundingBadge.className}>{groundingBadge.label}</Badge>
                            </div>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {claim.tags.map((tag) => (
                    <Badge key={`${claim.id}-tag-${tag}`}>{tag}</Badge>
                  ))}
                  {claim.outcomes.map((outcome) => (
                    <Badge key={`${claim.id}-outcome-${outcome}`} variant="muted">
                      {outcome}
                    </Badge>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function getStructuredStateTraceEntry(contextTrace: PaperNoteContextTrace | null | undefined) {
  if (!contextTrace?.trace?.length) {
    return null;
  }
  return [...contextTrace.trace].reverse().find((entry) => entry.action === "structured_state_loaded") ?? null;
}

function StructuredStateNotice({
  state,
  contextTrace,
  noteSlug,
}: {
  state: StructuredPaperState | null;
  contextTrace: PaperNoteContextTrace | null | undefined;
  noteSlug: string | null | undefined;
}) {
  if (state) {
    return null;
  }

  const traceEntry = getStructuredStateTraceEntry(contextTrace);
  const expectedPath = traceEntry?.source_path ?? (noteSlug ? `.pp/${noteSlug}/state.json` : null);
  const traceSummary = contextTrace?.summary;
  const hasCompactTrace =
    Boolean(contextTrace?.available) &&
    ((traceSummary?.entry_count ?? 0) > 0 || (traceSummary?.related_count ?? 0) > 0 || (traceSummary?.reference_count ?? 0) > 0);

  return (
    <Card
      className="overflow-hidden border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)]/40"
      data-testid="paper-note-structured-state-notice"
    >
      <CardHeader>
        <CardTitle>Structured state is not loaded</CardTitle>
        <CardDescription>
          Reading content is available, but no saved structured sidecar was loaded for run history or structured claims.
        </CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <p className="text-sm text-[var(--pp-text-secondary)]">
          This note can still be reviewed, but the structured panels below reflect a missing canonical sidecar rather than an empty saved run.
        </p>
        {expectedPath ? (
          <p
            className="mt-2 break-all text-xs text-[var(--pp-text-dim)]"
            data-testid="paper-note-structured-state-path"
          >
            Expected sidecar: {expectedPath}
          </p>
        ) : null}
        {hasCompactTrace ? (
          <div className="mt-3 flex flex-wrap gap-1.5" data-testid="paper-note-context-trace-summary">
            <Badge variant="outline">trace {traceSummary?.entry_count ?? 0}</Badge>
            {typeof traceSummary?.related_count === "number" && traceSummary.related_count > 0 ? (
              <Badge variant="outline">related {traceSummary.related_count}</Badge>
            ) : null}
            {typeof traceSummary?.reference_count === "number" && traceSummary.reference_count > 0 ? (
              <Badge variant="outline">references {traceSummary.reference_count}</Badge>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function PaperNoteDetailPage() {
  const params = useParams<{ slug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const slug = params.slug ?? "";

  const [data, setData] = useState<PaperNoteDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const [runningAction, setRunningAction] = useState<SkillActionInfo["action"] | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [signalDiffs, setSignalDiffs] = useState<SignalDiff[]>([]);
  const [appendMarkdownSummary, setAppendMarkdownSummary] = useState(true);
  const actionRunLockRef = useRef(false);

  async function loadDetail(targetSlug: string) {
    if (!targetSlug) {
      setLoadError("Missing note slug.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const result = await getPaperNoteDetail(targetSlug);
      setData(result.data);
    } catch (error) {
      setData(null);
      setLoadError(getApiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!slug) {
        setLoadError("Missing note slug.");
        setLoading(false);
        return;
      }
      setLoading(true);
      setLoadError(null);
      try {
        const result = await getPaperNoteDetail(slug);
        if (!mounted) {
          return;
        }
        setData(result.data);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setData(null);
        setLoadError(getApiErrorMessage(error));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [slug]);

  useEffect(() => {
    actionRunLockRef.current = false;
    setRunningAction(null);
    setActionMessage(null);
    setSignalDiffs([]);
    setAppendMarkdownSummary(true);
  }, [slug]);

  const note = data?.note ?? null;
  const structuredState = data?.structured_state ?? null;
  const contextTrace = data?.context_trace ?? null;
  const availableActions = data?.available_actions ?? [];
  const focusTarget = useMemo(() => parseFocusParam(searchParams.get("focus")), [searchParams]);
  const viewerMode = useMemo(() => parseViewerOutputMode(searchParams.get("view")), [searchParams]);
  const aliases = useMemo(() => note?.aliases ?? [], [note]);
  const tags = useMemo(() => note?.tags ?? [], [note]);
  const workbenchPaperId = useMemo(() => resolveWorkbenchPaperId(note), [note]);
  const outline = useMemo(() => extractOutline(data?.body_markdown ?? "", note?.title), [data?.body_markdown, note?.title]);

  function logOpenWorkbench(origin: string) {
    if (!workbenchPaperId) {
      return;
    }
    logClientUserAction({
      paper_id: workbenchPaperId,
      action_type: "open_workbench",
      payload: {
        origin,
        note_slug: slug,
      },
    });
  }

  async function handleRunAction(action: SkillActionInfo["action"]) {
    if (!slug || runningAction !== null || actionRunLockRef.current) {
      return;
    }
    actionRunLockRef.current = true;
    setRunningAction(action);
    setActionMessage(null);
    try {
      const previousSignals = data?.note?.pp_signals ?? {};
      const result = await runSkillAction({
        slug,
        action,
        append_markdown_summary: appendMarkdownSummary,
      });
      setActionMessage(
        appendMarkdownSummary ? result.run.summary : `${result.run.summary} Structured state updated without markdown summary.`,
      );
      setSignalDiffs(computeSignalDiffs(previousSignals, getSignalRecord(result.frontmatter_pp?.signals)));
      await loadDetail(slug);
    } catch (error) {
      setSignalDiffs([]);
      setActionMessage(`Action failed: ${getApiErrorMessage(error)}`);
    } finally {
      actionRunLockRef.current = false;
      setRunningAction(null);
    }
  }

  useEffect(() => {
    if (note?.title) {
      document.title = `${note.title} | Lattice`;
      return;
    }
    if (slug) {
      document.title = `${slug} | Lattice`;
      return;
    }
    document.title = "Paper Note | Lattice";
  }, [note?.title, slug]);

  useEffect(() => {
    if (!focusTarget) {
      return;
    }
    if (typeof window !== "undefined" && window.innerWidth < 1280) {
      setSidePanelOpen(true);
    }
  }, [focusTarget]);

  useEffect(() => {
    if (!focusTarget) {
      return;
    }
    const timer = window.setTimeout(() => {
      const target = document.getElementById(toFocusDomId(focusTarget.kind, focusTarget.id));
      if (!target) {
        return;
      }
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [focusTarget, structuredState?.updated_at, sidePanelOpen]);

  function handleViewerModeChange(mode: ViewerOutputMode) {
    setSearchParams(buildViewerModeSearchParams(searchParams, mode), { replace: true });
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4 pb-24 md:pb-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Paper note detail</p>
            <h1 className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{note?.title ?? slug}</h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Review note content, related papers, and references before opening the workbench.
            </p>
            {note?.id ? <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{note.id}</p> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link to="/papers">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to list
              </Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              className="md:hidden"
              onClick={() => setSidePanelOpen(true)}
              data-testid="paper-note-open-side-panel"
            >
              <PanelRightOpen className="h-3.5 w-3.5" />
              Review details
            </Button>
            {workbenchPaperId ? (
              <Link
                to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                className="hidden md:inline-flex"
                onClick={() => logOpenWorkbench("paper_note_header")}
              >
                <Button size="sm">
                  <FlaskConical className="h-3.5 w-3.5" />
                  Open in Workbench
                </Button>
              </Link>
            ) : (
              <Link to="/" className="hidden md:inline-flex">
                <Button variant="outline" size="sm">
                  Workbench
                </Button>
              </Link>
            )}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {note?.status ? <StatusBadge label={formatFreeformStatusLabel(note.status)} tone={getFreeformStatusTone(note.status)} /> : null}
          {typeof note?.confidence === "number" ? <Badge variant="outline">confidence {confidenceLabel(note.confidence)}</Badge> : null}
          {tags.slice(0, 4).map((tag) => (
            <Badge key={`header-tag-${tag}`}>{tag}</Badge>
          ))}
        </div>
        <div className="mt-4 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3" data-testid="paper-note-view-mode-controls">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">View mode</span>
            <Button
              size="sm"
              variant={viewerMode === "learner" ? "secondary" : "ghost"}
              onClick={() => handleViewerModeChange("learner")}
            >
              Learner
            </Button>
            <Button
              size="sm"
              variant={viewerMode === "builder_debug" ? "secondary" : "ghost"}
              onClick={() => handleViewerModeChange("builder_debug")}
            >
              Inspect
            </Button>
            <Badge variant="outline">Current focus: {formatViewerOutputModeLabel(viewerMode)}</Badge>
          </div>
          <p className="mt-2 text-sm text-[var(--pp-text-secondary)]" data-testid="paper-note-view-mode-summary">
            {getViewerModeSummary(viewerMode)}
          </p>
        </div>
      </header>

      {loading ? <p className="text-sm text-[var(--pp-text-dim)]">Loading note...</p> : null}
      {loadError ? <p className="text-sm text-[var(--pp-status-failed-text)]">API error: {loadError}</p> : null}

      {!loading && !loadError && data ? (
        <main className="grid grid-cols-1 gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="hidden xl:block">
            <div className="sticky top-4 grid gap-4">
              <Card className="overflow-hidden">
                <CardHeader>
                  <CardTitle>Reading Context</CardTitle>
                  <CardDescription>{getViewerContextDescription(viewerMode)}</CardDescription>
                </CardHeader>
                <Separator />
                <CardContent className="pt-4">
                  <p className="text-sm text-[var(--pp-text-secondary)]">{note?.note_path ?? slug}</p>
                  <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{getViewerModeSummary(viewerMode)}</p>
                  {workbenchPaperId ? (
                    <Link
                      to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                      className="mt-4 inline-flex"
                      onClick={() => logOpenWorkbench("paper_note_context_card")}
                    >
                      <Button className="w-full">
                        <FlaskConical className="h-4 w-4" />
                        Open in Workbench
                      </Button>
                    </Link>
                  ) : null}
                </CardContent>
              </Card>

              <OutlinePanel outline={outline} />
            </div>
          </aside>

          <section className="grid min-h-0 gap-4">
            <Card className="overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <ScrollText className="h-4 w-4 text-[var(--pp-accent-text)]" />
                  <CardTitle>Reading View</CardTitle>
                </div>
                <CardDescription>{getReadingViewDescription(viewerMode)}</CardDescription>
              </CardHeader>
              <Separator />
              <CardContent className="pt-4">
                <article className="paper-note-markdown">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1({ children }) {
                        return <HeadingWithAnchor level={1}>{children}</HeadingWithAnchor>;
                      },
                      h2({ children }) {
                        return <HeadingWithAnchor level={2}>{children}</HeadingWithAnchor>;
                      },
                      h3({ children }) {
                        return <HeadingWithAnchor level={3}>{children}</HeadingWithAnchor>;
                      },
                      a({ href, children }) {
                        if (!href) {
                          return <span>{children}</span>;
                        }
                        if (href.startsWith("/papers/")) {
                          return (
                            <Link to={href} className="paper-note-link">
                              {children}
                            </Link>
                          );
                        }
                        return (
                          <a href={href} target="_blank" rel="noreferrer" className="paper-note-link">
                            {children}
                          </a>
                        );
                      },
                    }}
                  >
                    {data.body_markdown}
                  </ReactMarkdown>
                </article>
              </CardContent>
            </Card>
          </section>

          <aside className="hidden xl:block">
            <div className="sticky top-4 grid gap-4">
              {viewerMode === "builder_debug" ? (
                <>
                  <ActionsPanel
                    actions={availableActions}
                    runningAction={runningAction}
                    actionMessage={actionMessage}
                    signalDiffs={signalDiffs}
                    appendMarkdownSummary={appendMarkdownSummary}
                    onAppendMarkdownSummaryChange={setAppendMarkdownSummary}
                    onRun={handleRunAction}
                  />
                  <StructuredStateNotice state={structuredState} contextTrace={contextTrace} noteSlug={note?.slug} />
                  <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} />
                  <ClaimSetPanel claims={structuredState?.claimset ?? []} focusTarget={focusTarget} />
                  <PropertiesPanel note={note} aliases={aliases} tags={tags} />
                  <RelatedPapersPanel related={data.related} />
                  <ReferencesPanel references={data.references} />
                </>
              ) : (
                <>
                  <PropertiesPanel note={note} aliases={aliases} tags={tags} />
                  <RelatedPapersPanel related={data.related} />
                  <ReferencesPanel references={data.references} />
                  <ActionsPanel
                    actions={availableActions}
                    runningAction={runningAction}
                    actionMessage={actionMessage}
                    signalDiffs={signalDiffs}
                    appendMarkdownSummary={appendMarkdownSummary}
                    onAppendMarkdownSummaryChange={setAppendMarkdownSummary}
                    onRun={handleRunAction}
                  />
                  <StructuredStateNotice state={structuredState} contextTrace={contextTrace} noteSlug={note?.slug} />
                  <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} />
                  <ClaimSetPanel claims={structuredState?.claimset ?? []} focusTarget={focusTarget} />
                </>
              )}
            </div>
          </aside>
        </main>
      ) : null}

      <Sheet
        open={sidePanelOpen}
        onOpenChange={setSidePanelOpen}
        title="Review details"
        description="Metadata, outline, related papers, references, actions, and claim cards."
      >
        {!data ? null : (
          <div className="grid gap-4">
            {viewerMode === "builder_debug" ? (
              <>
                <ActionsPanel
                  actions={availableActions}
                  runningAction={runningAction}
                  actionMessage={actionMessage}
                  signalDiffs={signalDiffs}
                  appendMarkdownSummary={appendMarkdownSummary}
                  onAppendMarkdownSummaryChange={setAppendMarkdownSummary}
                  onRun={handleRunAction}
                />
                <StructuredStateNotice state={structuredState} contextTrace={contextTrace} noteSlug={note?.slug} />
                <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} />
                <ClaimSetPanel claims={structuredState?.claimset ?? []} focusTarget={focusTarget} />
                <PropertiesPanel note={note} aliases={aliases} tags={tags} />
                <OutlinePanel outline={outline} onNavigate={() => setSidePanelOpen(false)} />
                <RelatedPapersPanel related={data.related} onNavigate={() => setSidePanelOpen(false)} />
                <ReferencesPanel references={data.references} />
              </>
            ) : (
              <>
                <PropertiesPanel note={note} aliases={aliases} tags={tags} />
                <OutlinePanel outline={outline} onNavigate={() => setSidePanelOpen(false)} />
                <RelatedPapersPanel related={data.related} onNavigate={() => setSidePanelOpen(false)} />
                <ReferencesPanel references={data.references} />
                <ActionsPanel
                  actions={availableActions}
                  runningAction={runningAction}
                  actionMessage={actionMessage}
                  signalDiffs={signalDiffs}
                  appendMarkdownSummary={appendMarkdownSummary}
                  onAppendMarkdownSummaryChange={setAppendMarkdownSummary}
                  onRun={handleRunAction}
                />
                <StructuredStateNotice state={structuredState} contextTrace={contextTrace} noteSlug={note?.slug} />
                <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} />
                <ClaimSetPanel claims={structuredState?.claimset ?? []} focusTarget={focusTarget} />
              </>
            )}
          </div>
        )}
      </Sheet>

      {workbenchPaperId ? (
        <div className="fixed bottom-3 left-3 right-3 z-30 md:hidden">
          <Link
            to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
            className="inline-flex w-full"
            onClick={() => logOpenWorkbench("paper_note_mobile_cta")}
          >
            <Button className="w-full shadow-[var(--pp-shadow)]">
              <FlaskConical className="h-4 w-4" />
              Open in Workbench
            </Button>
          </Link>
        </div>
      ) : null}
    </div>
  );
}
