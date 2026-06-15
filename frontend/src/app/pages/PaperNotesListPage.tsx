import { ChangeEvent, KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowUpDown, Check, Cloud, Download, FileText, RefreshCw, Search, ShieldCheck, Upload, X } from "lucide-react";
import { getApiErrorMessage, getCloudPaperAuthPreflight, getCloudPaperPage, getCloudPapers, getPaperNotesIndex, hydrateCloudPaper, importPaperPdf, searchCloudPapers, uploadCloudPaperPdf } from "../lib/api";
import { getPaperNoteOpsActionLabel, getPaperNoteOpsReason, paperNoteToPaperIdCandidates } from "../lib/paperNoteOps";
import { formatPaperNoteTriageLabel, PAPER_NOTE_OPERATOR_TRIAGE_LABELS } from "../lib/paperOperatorState";
import { formatFreeformStatusLabel, getFreeformStatusTone, getStatusToneClassName } from "../lib/statusSystem";
import { CloudPaperAuthPreflightResponse, CloudPaperBundlePublic, CloudPaperHydrationState, CloudPaperPageArtifactPublic, CloudPaperSearchHit, PaperNoteOperatorTriageLabel, PaperNoteSummary } from "../lib/types";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
import { StatusBadge } from "../components/StatusBadge";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { buttonClassName } from "../components/ui/buttonClassName";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "../components/ui/command";
import { Input } from "../components/ui/input";

type SortBy = "date_processed" | "confidence";
type SortOrder = "asc" | "desc";
type ReadingAssistFilter = "available" | `locale:${string}`;
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

function parseBooleanFlag(value: string | null): boolean {
  if (!value) {
    return false;
  }
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes";
}

function parseTriageLabel(value: string | null): PaperNoteOperatorTriageLabel | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return PAPER_NOTE_OPERATOR_TRIAGE_LABELS.find((label) => label === normalized) ?? null;
}

function parseReadingAssistLocale(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return normalized || null;
}

function parseReadingAssistFilter(hasReadingAssistValue: string | null, localeValue: string | null): ReadingAssistFilter | null {
  const locale = parseReadingAssistLocale(localeValue);
  if (locale) {
    return `locale:${locale}`;
  }
  return parseBooleanFlag(hasReadingAssistValue) ? "available" : null;
}

function readingAssistLocaleFromFilter(filter: ReadingAssistFilter | null): string | null {
  if (!filter || !filter.startsWith("locale:")) {
    return null;
  }
  const locale = filter.slice("locale:".length).trim().toLowerCase();
  return locale || null;
}

function formatReadingAssistLocaleLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "ko") {
    return "Korean";
  }
  if (normalized === "ja") {
    return "Japanese";
  }
  return normalized.toUpperCase();
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

function readingAssistBadgeLabel(item: PaperNoteSummary): string | null {
  const signals = (item.pp_signals ?? {}) as Record<string, unknown>;
  const locales = Array.from(
    new Set(
      (item.reading_assist_locales ?? [])
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean),
    ),
  );
  const hasReadingAssist = item.reading_assist_available === true || signals.has_reading_assists === true || locales.length > 0;
  if (!hasReadingAssist) {
    return null;
  }
  if (locales.length === 1) {
    return locales[0] === "ko" ? "Korean assist" : `${locales[0].toUpperCase()} assist`;
  }
  if (locales.length > 1) {
    return `${locales.length} reading assists`;
  }
  return "Reading assist";
}

function buildStateBadges(item: PaperNoteSummary): Array<{ label: string; tone: ListBadgeTone }> {
  const signals = (item.pp_signals ?? {}) as Record<string, unknown>;
  const badges: Array<{ label: string; tone: ListBadgeTone }> = [];
  if (item.structured_state_present === true) {
    badges.push({ label: "Saved note", tone: "success" });
  } else if (item.structured_state_present === false) {
    badges.push({ label: "Needs saved note", tone: "warning" });
  }
  if (signals.has_claimset === true || (item.claim_tags?.length ?? 0) > 0) {
    badges.push({ label: "Claims saved", tone: "success" });
  }
  const readingAssistLabel = readingAssistBadgeLabel(item);
  if (readingAssistLabel) {
    badges.push({ label: readingAssistLabel, tone: "accent" });
  }
  if ((item.entities?.length ?? 0) > 0 || (item.mesh?.length ?? 0) > 0 || (item.outcomes?.length ?? 0) > 0) {
    badges.push({ label: "Structured tags", tone: "accent" });
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

function buildOperatorBadges(item: PaperNoteSummary): Array<{ label: string; tone: ListBadgeTone }> {
  const badges: Array<{ label: string; tone: ListBadgeTone }> = [];
  if (item.starred === true) {
    badges.push({ label: "Starred", tone: "accent" });
  }
  if (item.has_operator_note === true) {
    badges.push({ label: "My note", tone: "outline" });
  }
  for (const label of item.triage_labels ?? []) {
    badges.push({ label: formatPaperNoteTriageLabel(label), tone: "muted" });
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
    output.push(`Claim topics ${item.claim_tags!.slice(0, 3).join(", ")}`);
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

interface PaperNotesVisibleSummary {
  visibleCount: number;
  structuredCount: number;
  needsReviewCount: number;
  blockedCount: number;
}

interface PaperNoteNextActionModel {
  title: string;
  detail: string;
  primaryLabel: string;
  primaryHref: string;
  primaryTestId: string;
  secondaryLabel?: string;
  secondaryHref?: string;
  secondaryTestId?: string;
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

function buildVisibleSummary(items: PaperNoteSummary[]): PaperNotesVisibleSummary {
  return {
    visibleCount: items.length,
    structuredCount: items.filter((item) => item.structured_state_present === true).length,
    needsReviewCount: items.filter((item) => item.ops_summary?.recommended_action === "open_workbench").length,
    blockedCount: items.filter((item) => item.ops_summary?.recommended_action === "repair_stats").length,
  };
}

function resolvePaperNoteWorkbenchHref(item: Pick<PaperNoteSummary, "id" | "slug">): string | null {
  const candidate = paperNoteToPaperIdCandidates(item)[0] ?? null;
  return candidate ? `/workbench/${encodeURIComponent(candidate)}` : null;
}

function buildPaperNoteHref(slug: string, readingAssistLocale?: string | null): string {
  const query = new URLSearchParams();
  if (readingAssistLocale?.trim()) {
    query.set("reading_assist_locale", readingAssistLocale.trim().toLowerCase());
  }
  const queryText = query.toString();
  return `/papers/${encodeURIComponent(slug)}${queryText ? `?${queryText}` : ""}`;
}

function buildPaperNoteNextAction(item: PaperNoteSummary, readingAssistLocale?: string | null): PaperNoteNextActionModel {
  const noteHref = buildPaperNoteHref(item.slug, readingAssistLocale);
  const workbenchHref = resolvePaperNoteWorkbenchHref(item);
  const workbenchActionLabel = getPaperNoteOpsActionLabel(item.ops_summary) ?? "Open review";
  if (item.ops_summary?.recommended_action === "repair_stats" && workbenchHref) {
    return {
      title: "Next action",
      detail: getPaperNoteOpsReason(item.ops_summary),
      primaryLabel: workbenchActionLabel,
      primaryHref: workbenchHref,
      primaryTestId: "paper-note-next-action-review",
      secondaryLabel: "Open note",
      secondaryHref: noteHref,
      secondaryTestId: "paper-note-next-action-note",
    };
  }
  if (item.ops_summary?.recommended_action === "open_workbench" && workbenchHref) {
    return {
      title: "Next action",
      detail: getPaperNoteOpsReason(item.ops_summary),
      primaryLabel: workbenchActionLabel,
      primaryHref: workbenchHref,
      primaryTestId: "paper-note-next-action-review",
      secondaryLabel: "Open note",
      secondaryHref: noteHref,
      secondaryTestId: "paper-note-next-action-note",
    };
  }
  if (item.structured_state_present === true && workbenchHref) {
    return {
      title: "Next action",
      detail: "Saved note context is ready for grounded evidence review.",
      primaryLabel: "Resume review",
      primaryHref: workbenchHref,
      primaryTestId: "paper-note-next-action-review",
      secondaryLabel: "Open note",
      secondaryHref: noteHref,
      secondaryTestId: "paper-note-next-action-note",
    };
  }
  return {
    title: "Next action",
    detail:
      item.structured_state_present === true
        ? "Reopen the note to inspect saved structure, references, and related context."
        : "Open the note first, then save structure before deeper evidence review.",
    primaryLabel: "Open note",
    primaryHref: noteHref,
    primaryTestId: "paper-note-next-action-note",
  };
}

function PaperNoteListRow({
  item,
  query,
  readingAssistLocale,
}: {
  item: PaperNoteSummary;
  query?: string;
  readingAssistLocale?: string | null;
}) {
  const stateBadges = buildStateBadges(item);
  const operatorBadges = buildOperatorBadges(item);
  const insightText = buildInsightText(item);
  const structuredSignalChips = buildStructuredSignalChips(item, query);
  const visibleTags = item.tags.slice(0, 4);
  const extraTagCount = Math.max(item.tags.length - visibleTags.length, 0);
  const noteHref = buildPaperNoteHref(item.slug, readingAssistLocale);
  const nextAction = buildPaperNoteNextAction(item, readingAssistLocale);

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
                to={noteHref}
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
              to={noteHref}
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

          {operatorBadges.length > 0 ? (
            <div className="mt-3" data-testid="paper-note-list-operator-badges">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">My markers</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {operatorBadges.map((badge) => (
                  <span
                    key={`${item.slug}-operator-${badge.label}`}
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${listBadgeClassName(badge.tone)}`}
                  >
                    {badge.label}
                  </span>
                ))}
              </div>
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
                Structured tags
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
              <dd data-testid="paper-note-list-processed-date" className="mt-1 text-[var(--pp-text-primary)]">
                {formatDate(item.date_processed)}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Checks</dt>
              <dd className="mt-1">
                {item.ops_summary ? (
                  <OperationalStateSummary summary={item.ops_summary} compact showActionHint={false} />
                ) : (
                  <span className="text-[var(--pp-text-dim)]">No checks yet</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Claim topics</dt>
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

          <div
            className="grid gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
            data-testid="paper-note-next-action"
          >
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">{nextAction.title}</p>
              <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">{nextAction.detail}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                to={nextAction.primaryHref}
                className={buttonClassName({ size: "sm" })}
                data-testid={nextAction.primaryTestId}
              >
                {nextAction.primaryLabel}
              </Link>
              {nextAction.secondaryHref && nextAction.secondaryLabel && nextAction.secondaryTestId ? (
                <Link
                  to={nextAction.secondaryHref}
                  className={buttonClassName({ variant: "outline", size: "sm" })}
                  data-testid={nextAction.secondaryTestId}
                >
                  {nextAction.secondaryLabel}
                </Link>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

function formatCloudPaperStatusLabel(status: CloudPaperBundlePublic["processing_status"]): string {
  if (status === "ready") {
    return "Cloud ready";
  }
  if (status === "running") {
    return "Processing";
  }
  if (status === "pending") {
    return "Queued";
  }
  if (status === "failed") {
    return "Failed";
  }
  return "Blocked";
}

function cloudPaperStatusTone(status: CloudPaperBundlePublic["processing_status"]): "success" | "warning" | "danger" | "muted" {
  if (status === "ready") {
    return "success";
  }
  if (status === "running" || status === "pending") {
    return "warning";
  }
  if (status === "failed" || status === "blocked") {
    return "danger";
  }
  return "muted";
}

function CloudPaperListRow({
  item,
  pagePreview,
  hydrationState,
  loadingPage,
  hydrating,
  onLoadPage,
  onHydrate,
}: {
  item: CloudPaperBundlePublic;
  pagePreview?: CloudPaperPageArtifactPublic | null;
  hydrationState?: CloudPaperHydrationState | null;
  loadingPage: boolean;
  hydrating: boolean;
  onLoadPage: (paperId: string) => void;
  onHydrate: (paperId: string) => void;
}) {
  const canReadPage = item.allowed_actions.includes("read_page");
  const canHydrate = item.allowed_actions.includes("hydrate_download");
  const effectiveHydration = hydrationState ?? item.local_hydration ?? null;
  const hydrationStatus = effectiveHydration?.status ?? "not_hydrated";
  const primaryWarning = item.warnings[0]?.message;
  const previewText = pagePreview?.blocks.find((block) => block.text?.trim())?.text?.trim();

  return (
    <article className="rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3" data-testid="cloud-paper-list-row">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-start gap-2">
            <Cloud className="mt-0.5 h-4 w-4 text-[var(--pp-accent-text)]" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[var(--pp-text-primary)]">{item.paper_id}</p>
              <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                Lab {item.lab_id} · {item.provenance_summary.processor_name} · {formatDate(item.provenance_summary.created_at)}
              </p>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${listBadgeClassName(cloudPaperStatusTone(item.processing_status))}`}>
              {formatCloudPaperStatusLabel(item.processing_status)}
            </span>
            <Badge variant={hydrationStatus === "hydrated" ? "default" : "muted"}>
              {hydrationStatus === "hydrated" ? "Available offline" : "Cloud source"}
            </Badge>
            <Badge variant="outline">{item.payload_class}</Badge>
            {canHydrate ? <Badge variant="outline">download allowed</Badge> : <Badge variant="muted">read-only device</Badge>}
          </div>
          {primaryWarning ? (
            <p className="mt-2 text-xs text-[var(--pp-status-failed-text)]">{primaryWarning}</p>
          ) : (
            <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">
              Server page data is used directly in this installed UI; local files are only written when policy allows hydration.
            </p>
          )}
          {previewText ? (
            <div className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3" data-testid="cloud-paper-page-preview">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Page preview</p>
              <p className="mt-1 line-clamp-3 text-xs text-[var(--pp-text-secondary)]">{previewText}</p>
            </div>
          ) : null}
        </div>
        <div className="grid gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
          <dl className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-[var(--pp-text-dim)]">Run</dt>
              <dd className="mt-1 truncate text-[var(--pp-text-primary)]">{item.run_id ?? "pending"}</dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Role</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{item.permissions.role}</dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Page schema</dt>
              <dd className="mt-1 truncate text-[var(--pp-text-primary)]">{item.page_schema_version ?? "not ready"}</dd>
            </div>
            <div>
              <dt className="text-[var(--pp-text-dim)]">Actions</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{item.allowed_actions.length}</dd>
            </div>
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => onLoadPage(item.paper_id)} disabled={!canReadPage || loadingPage}>
              {loadingPage ? <RefreshCw className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {loadingPage ? "Loading" : pagePreview ? "Refresh page" : "Preview page"}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => onHydrate(item.paper_id)} disabled={!canHydrate || hydrating}>
              {hydrating ? <RefreshCw className="h-4 w-4 animate-spin" /> : canHydrate ? <Download className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
              {hydrating ? "Downloading" : canHydrate ? "Hydrate" : "Locked"}
            </Button>
            <Link
              to={`/papers/${encodeURIComponent(item.paper_id)}?source=cloud`}
              className={buttonClassName({ size: "sm" })}
              data-testid="cloud-paper-open-viewer"
            >
              Open viewer
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}

function CloudPaperSearchResults({
  query,
  items,
  loading,
  error,
  mockReason,
}: {
  query: string;
  items: CloudPaperSearchHit[];
  loading: boolean;
  error: string | null;
  mockReason: string | null;
}) {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return null;
  }

  return (
    <div
      className="border-b border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-3"
      data-testid="cloud-paper-search-results"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Cloud page matches</p>
          <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">
            {loading ? "Searching processed page text..." : `${items.length} cloud match${items.length === 1 ? "" : "es"} for "${trimmedQuery}"`}
          </p>
        </div>
        {mockReason ? <Badge variant="muted">mock search</Badge> : null}
      </div>
      {error ? (
        <p className="mt-3 text-xs text-[var(--pp-status-failed-text)]">Cloud search failed: {error}</p>
      ) : null}
      {!loading && !error && items.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {items.map((item) => {
            const firstMatch = item.matched_blocks[0];
            return (
              <Link
                key={item.bundle.paper_id}
                to={`/papers/${encodeURIComponent(item.bundle.paper_id)}?source=cloud`}
                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 text-left transition hover:border-[var(--pp-accent-border)]"
                data-testid="cloud-paper-search-result-row"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Cloud className="h-4 w-4 text-[var(--pp-accent-text)]" aria-hidden="true" />
                  <span className="text-sm font-semibold text-[var(--pp-text-primary)]">{item.bundle.paper_id}</span>
                  <Badge variant="outline">page {firstMatch.page}</Badge>
                  <Badge variant="muted">{firstMatch.payload_class}</Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-[var(--pp-text-secondary)]">{firstMatch.text_snippet}</p>
              </Link>
            );
          })}
        </div>
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <p className="mt-3 text-xs text-[var(--pp-text-dim)]">No readable cloud pages matched this search.</p>
      ) : null}
    </div>
  );
}

function getCloudAuthStatusLabel(preflight: CloudPaperAuthPreflightResponse | null): string {
  if (!preflight) {
    return "Checking";
  }
  if (preflight.status === "ready") {
    return "GCP auth ready";
  }
  if (preflight.status === "submission_bundle") {
    return "Submitted demo ready";
  }
  if (preflight.status === "auth_missing") {
    return "ADC sign-in needed";
  }
  if (preflight.status === "permission_denied") {
    return "Access needed";
  }
  if (preflight.status === "misconfigured") {
    return "Cloud config needed";
  }
  if (preflight.status === "dependency_missing") {
    return "Cloud runtime missing";
  }
  if (preflight.status === "mock_mode") {
    return "Mock mode";
  }
  return "Cloud check failed";
}

function getCloudAuthToneClassName(status: CloudPaperAuthPreflightResponse["status"] | "loading" | "error"): string {
  if (status === "ready" || status === "submission_bundle") {
    return "border-[var(--pp-status-ready-border)] bg-[var(--pp-status-ready-bg)] text-[var(--pp-status-ready-text)]";
  }
  if (status === "auth_missing" || status === "permission_denied" || status === "misconfigured" || status === "dependency_missing" || status === "error") {
    return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
  }
  return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
}

function CloudAuthPreflightPanel({
  preflight,
  loading,
  error,
  mockReason,
  onRefresh,
}: {
  preflight: CloudPaperAuthPreflightResponse | null;
  loading: boolean;
  error: string | null;
  mockReason: string | null;
  onRefresh: () => void;
}) {
  const status = error ? "error" : loading ? "loading" : preflight?.status ?? "unavailable";
  const statusLabel = error ? "Cloud check failed" : loading ? "Checking GCP auth" : getCloudAuthStatusLabel(preflight);
  const commands = preflight?.setup_commands ?? [];
  const shouldShowCommands = commands.length > 0 && preflight?.status !== "ready";
  const canCopyCommands = shouldShowCommands && typeof navigator !== "undefined" && Boolean(navigator.clipboard);
  const checkItems = preflight?.checks ?? [];

  async function copyCommands() {
    if (!canCopyCommands) {
      return;
    }
    await navigator.clipboard.writeText(commands.join("\n"));
  }

  return (
    <div className="border-b border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-3" data-testid="cloud-auth-preflight">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={getCloudAuthToneClassName(status)}>
              <ShieldCheck className="h-3.5 w-3.5" />
              {statusLabel}
            </Badge>
            {preflight?.project_id ? <Badge variant="muted">project {preflight.project_id}</Badge> : null}
            {preflight?.firestore_collection ? <Badge variant="muted">metadata {preflight.firestore_collection}</Badge> : null}
          </div>
          <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">
            {error
              ? `Cloud auth check could not run: ${error}`
              : preflight?.next_action_label ?? "Checking whether this computer can read the shared GCP demo data."}
          </p>
          {mockReason ? <p className="mt-1 text-xs text-[var(--pp-text-dim)]">Fallback mode: {mockReason}</p> : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {shouldShowCommands ? (
            <Button type="button" variant="outline" size="sm" onClick={copyCommands} disabled={!canCopyCommands}>
              <Check className="h-4 w-4" />
              Copy commands
            </Button>
          ) : null}
          <Button type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Check again
          </Button>
        </div>
      </div>
      {shouldShowCommands ? (
        <pre className="mt-3 overflow-x-auto rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 text-xs text-[var(--pp-text-primary)]">
          {commands.join("\n")}
        </pre>
      ) : null}
      {checkItems.length > 0 ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {checkItems.map((check) => (
            <div key={check.check_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
              <div className="flex items-center gap-2">
                {check.status === "ok" ? (
                  <Check className="h-4 w-4 text-[var(--pp-status-ready-text)]" />
                ) : check.status === "error" ? (
                  <X className="h-4 w-4 text-[var(--pp-status-failed-text)]" />
                ) : (
                  <Cloud className="h-4 w-4 text-[var(--pp-text-dim)]" />
                )}
                <p className="text-xs font-semibold text-[var(--pp-text-primary)]">{check.label}</p>
              </div>
              <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">{check.message}</p>
              {check.remediation ? <p className="mt-1 text-xs text-[var(--pp-text-dim)]">{check.remediation}</p> : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function PaperNotesListPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const loadSequence = useRef(0);
  const cloudAuthSequence = useRef(0);
  const cloudLoadSequence = useRef(0);
  const cloudSearchSequence = useRef(0);
  const tagPickerRef = useRef<HTMLDivElement | null>(null);
  const importCalloutRef = useRef<HTMLDivElement | null>(null);
  const importButtonRef = useRef<HTMLButtonElement | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const cloudUploadInputRef = useRef<HTMLInputElement | null>(null);
  const [items, setItems] = useState<PaperNoteSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allStatuses, setAllStatuses] = useState<string[]>([]);
  const [availableReadingAssistNoteCount, setAvailableReadingAssistNoteCount] = useState(0);
  const [availableReadingAssistLocales, setAvailableReadingAssistLocales] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mockReason, setMockReason] = useState<string | null>(null);
  const [cloudPapers, setCloudPapers] = useState<CloudPaperBundlePublic[]>([]);
  const [cloudLoading, setCloudLoading] = useState(true);
  const [cloudError, setCloudError] = useState<string | null>(null);
  const [cloudMockReason, setCloudMockReason] = useState<string | null>(null);
  const [cloudAuthPreflight, setCloudAuthPreflight] = useState<CloudPaperAuthPreflightResponse | null>(null);
  const [cloudAuthLoading, setCloudAuthLoading] = useState(true);
  const [cloudAuthError, setCloudAuthError] = useState<string | null>(null);
  const [cloudAuthMockReason, setCloudAuthMockReason] = useState<string | null>(null);
  const [cloudPagePreviewById, setCloudPagePreviewById] = useState<Record<string, CloudPaperPageArtifactPublic>>({});
  const [cloudHydrationById, setCloudHydrationById] = useState<Record<string, CloudPaperHydrationState>>({});
  const [cloudSearchHits, setCloudSearchHits] = useState<CloudPaperSearchHit[]>([]);
  const [cloudSearchLoading, setCloudSearchLoading] = useState(false);
  const [cloudSearchError, setCloudSearchError] = useState<string | null>(null);
  const [cloudSearchMockReason, setCloudSearchMockReason] = useState<string | null>(null);
  const [loadingCloudPageId, setLoadingCloudPageId] = useState<string | null>(null);
  const [hydratingCloudPaperId, setHydratingCloudPaperId] = useState<string | null>(null);
  const [cloudActionError, setCloudActionError] = useState<string | null>(null);
  const [isCloudUploading, setIsCloudUploading] = useState(false);
  const [queryInput, setQueryInput] = useState(() => searchParams.get("q") ?? "");
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [tagInput, setTagInput] = useState(() => searchParams.get("tag_input") ?? "");
  const [tagMenuOpen, setTagMenuOpen] = useState(false);
  const [highlightedTagIndex, setHighlightedTagIndex] = useState(0);
  const [selectedTags, setSelectedTags] = useState<string[]>(() => parseSelectedTags(searchParams.get("tags")));
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get("status") ?? "all");
  const [starredOnly, setStarredOnly] = useState(() => parseBooleanFlag(searchParams.get("starred")));
  const [triageFilter, setTriageFilter] = useState<PaperNoteOperatorTriageLabel | null>(() =>
    parseTriageLabel(searchParams.get("triage_label")),
  );
  const [structuredOnly, setStructuredOnly] = useState(() => parseStructuredOnly(searchParams.get("structured")));
  const [readingAssistFilter, setReadingAssistFilter] = useState<ReadingAssistFilter | null>(() =>
    parseReadingAssistFilter(searchParams.get("has_reading_assist"), searchParams.get("reading_assist_locale")),
  );
  const [sortBy, setSortBy] = useState<SortBy>(() => parseSortBy(searchParams.get("sort")));
  const [sortOrder, setSortOrder] = useState<SortOrder>(() => parseSortOrder(searchParams.get("order")));
  const [page, setPage] = useState(() => parsePage(searchParams.get("page")));
  const [pageSize, setPageSize] = useState<PageSize>(() => parsePageSize(searchParams.get("page_size")));
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const activeReadingAssistLocale = readingAssistLocaleFromFilter(readingAssistFilter);

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
          starred: starredOnly,
          triageLabel: triageFilter ?? undefined,
          structuredOnly,
          hasReadingAssist: readingAssistFilter !== null,
          readingAssistLocale: activeReadingAssistLocale ?? undefined,
          sortBy,
          sortOrder,
          page,
          pageSize,
        });
        if (!active || loadSequence.current !== seq) {
          return;
        }
        const response = result.data;
        setMockReason(result.isMock && result.reason ? result.reason : null);
        setItems(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
        setAllTags(response.available_tags);
        setAllStatuses(response.available_statuses);
        setAvailableReadingAssistNoteCount(response.available_reading_assist_note_count);
        setAvailableReadingAssistLocales(response.available_reading_assist_locales);
        if (response.page !== page) {
          setPage(response.page);
        }
      } catch (error) {
        if (!active || loadSequence.current !== seq) {
          return;
        }
        setMockReason(null);
        setItems([]);
        setTotal(0);
        setTotalPages(1);
        setAvailableReadingAssistNoteCount(0);
        setAvailableReadingAssistLocales([]);
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
  }, [activeReadingAssistLocale, page, pageSize, query, readingAssistFilter, selectedTags, sortBy, sortOrder, starredOnly, statusFilter, structuredOnly, triageFilter]);

  async function loadCloudAuthPreflight() {
    const seq = cloudAuthSequence.current + 1;
    cloudAuthSequence.current = seq;
    setCloudAuthLoading(true);
    setCloudAuthError(null);
    try {
      const result = await getCloudPaperAuthPreflight();
      if (cloudAuthSequence.current !== seq) {
        return;
      }
      setCloudAuthPreflight(result.data);
      setCloudAuthMockReason(result.isMock && result.reason ? result.reason : null);
    } catch (error) {
      if (cloudAuthSequence.current !== seq) {
        return;
      }
      setCloudAuthPreflight(null);
      setCloudAuthMockReason(null);
      setCloudAuthError(getApiErrorMessage(error));
    } finally {
      if (cloudAuthSequence.current === seq) {
        setCloudAuthLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadCloudAuthPreflight();
  }, []);

  useEffect(() => {
    const seq = cloudLoadSequence.current + 1;
    cloudLoadSequence.current = seq;
    let active = true;

    async function loadCloudPapers() {
      setCloudLoading(true);
      setCloudError(null);
      try {
        const result = await getCloudPapers();
        if (!active || cloudLoadSequence.current !== seq) {
          return;
        }
        setCloudPapers(result.data.items);
        setCloudMockReason(result.isMock && result.reason ? result.reason : null);
      } catch (error) {
        if (!active || cloudLoadSequence.current !== seq) {
          return;
        }
        setCloudPapers([]);
        setCloudMockReason(null);
        setCloudError(getApiErrorMessage(error));
      } finally {
        if (active && cloudLoadSequence.current === seq) {
          setCloudLoading(false);
        }
      }
    }

    void loadCloudPapers();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const trimmedQuery = query.trim();
    const seq = cloudSearchSequence.current + 1;
    cloudSearchSequence.current = seq;
    if (!trimmedQuery) {
      setCloudSearchHits([]);
      setCloudSearchLoading(false);
      setCloudSearchError(null);
      setCloudSearchMockReason(null);
      return;
    }

    let active = true;

    async function loadCloudSearch() {
      setCloudSearchLoading(true);
      setCloudSearchError(null);
      try {
        const result = await searchCloudPapers(trimmedQuery);
        if (!active || cloudSearchSequence.current !== seq) {
          return;
        }
        setCloudSearchHits(result.data.items);
        setCloudSearchMockReason(result.isMock && result.reason ? result.reason : null);
      } catch (error) {
        if (!active || cloudSearchSequence.current !== seq) {
          return;
        }
        setCloudSearchHits([]);
        setCloudSearchMockReason(null);
        setCloudSearchError(getApiErrorMessage(error));
      } finally {
        if (active && cloudSearchSequence.current === seq) {
          setCloudSearchLoading(false);
        }
      }
    }

    void loadCloudSearch();
    return () => {
      active = false;
    };
  }, [query]);

  useEffect(() => {
    document.title = "Paper Notes | Lattice";
  }, []);

  useEffect(() => {
    if (location.hash !== "#import-pdf") {
      return;
    }
    const frameId = window.requestAnimationFrame(() => {
      importCalloutRef.current?.scrollIntoView({ block: "center" });
      if (!mockReason) {
        importButtonRef.current?.focus();
      }
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [location.hash, mockReason]);

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

  function openImportPicker() {
    importInputRef.current?.click();
  }

  function openCloudUploadPicker() {
    cloudUploadInputRef.current?.click();
  }

  async function handleImportSelection(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile) {
      return;
    }

    setImportError(null);
    setIsImporting(true);
    try {
      const result = await importPaperPdf(selectedFile);
      navigate(`/papers/${encodeURIComponent(result.data.slug)}`);
    } catch (error) {
      setImportError(getApiErrorMessage(error));
    } finally {
      setIsImporting(false);
    }
  }

  async function handleCloudUploadSelection(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile) {
      return;
    }

    setCloudActionError(null);
    setIsCloudUploading(true);
    try {
      const result = await uploadCloudPaperPdf(selectedFile);
      setCloudPapers((current) => [result.data, ...current.filter((item) => item.paper_id !== result.data.paper_id)]);
      navigate(`/papers/${encodeURIComponent(result.data.paper_id)}?source=cloud`);
    } catch (error) {
      setCloudActionError(getApiErrorMessage(error));
    } finally {
      setIsCloudUploading(false);
    }
  }

  async function handleLoadCloudPage(paperId: string) {
    setCloudActionError(null);
    setLoadingCloudPageId(paperId);
    try {
      const result = await getCloudPaperPage(paperId);
      setCloudPagePreviewById((current) => ({ ...current, [paperId]: result.data }));
    } catch (error) {
      setCloudActionError(getApiErrorMessage(error));
    } finally {
      setLoadingCloudPageId((current) => (current === paperId ? null : current));
    }
  }

  async function handleHydrateCloudPaper(paperId: string) {
    setCloudActionError(null);
    setHydratingCloudPaperId(paperId);
    try {
      const result = await hydrateCloudPaper(paperId);
      setCloudHydrationById((current) => ({ ...current, [paperId]: result.data }));
      setCloudPapers((current) =>
        current.map((item) =>
          item.paper_id === paperId
            ? {
                ...item,
                local_hydration: result.data,
              }
            : item,
        ),
      );
    } catch (error) {
      setCloudActionError(getApiErrorMessage(error));
    } finally {
      setHydratingCloudPaperId((current) => (current === paperId ? null : current));
    }
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

  function toggleStarredOnly() {
    setStarredOnly((current) => !current);
    setPage(1);
  }

  function toggleTriageFilter(value: PaperNoteOperatorTriageLabel) {
    setTriageFilter((current) => (current === value ? null : value));
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

  function toggleReadingAssistAvailable() {
    setReadingAssistFilter((current) => (current === "available" ? null : "available"));
    setPage(1);
  }

  function toggleReadingAssistLocale(locale: string) {
    const normalizedLocale = locale.trim().toLowerCase();
    if (!normalizedLocale) {
      return;
    }
    setReadingAssistFilter((current) => {
      const activeLocale = readingAssistLocaleFromFilter(current);
      return activeLocale === normalizedLocale ? null : `locale:${normalizedLocale}`;
    });
    setPage(1);
  }

  function clearReadingAssistFilter() {
    setReadingAssistFilter(null);
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
    setStarredOnly(false);
    setTriageFilter(null);
    setStructuredOnly(false);
    setReadingAssistFilter(null);
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
    if (starredOnly) {
      next.set("starred", "1");
    }
    if (triageFilter) {
      next.set("triage_label", triageFilter);
    }
    if (structuredOnly) {
      next.set("structured", "1");
    }
    if (readingAssistFilter !== null) {
      next.set("has_reading_assist", "1");
    }
    if (activeReadingAssistLocale) {
      next.set("reading_assist_locale", activeReadingAssistLocale);
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
  }, [activeReadingAssistLocale, page, pageSize, queryInput, readingAssistFilter, searchParams, selectedTags, setSearchParams, sortBy, sortOrder, starredOnly, statusFilter, structuredOnly, triageFilter]);

  const pageWindow = useMemo(() => {
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, start + 4);
    const pages: number[] = [];
    for (let current = start; current <= end; current += 1) {
      pages.push(current);
    }
    return pages;
  }, [page, totalPages]);

  const hasReadingAssistOnly = readingAssistFilter !== null;
  const readingAssistLocaleOptions = useMemo(() => {
    const normalized = Array.from(
      new Set(
        availableReadingAssistLocales
          .map((value) => value.trim().toLowerCase())
          .filter(Boolean),
      ),
    );
    if (activeReadingAssistLocale && !normalized.includes(activeReadingAssistLocale)) {
      normalized.push(activeReadingAssistLocale);
    }
    return normalized.sort((left, right) => left.localeCompare(right));
  }, [activeReadingAssistLocale, availableReadingAssistLocales]);
  const readingAssistFilterLabel = activeReadingAssistLocale
    ? `${formatReadingAssistLocaleLabel(activeReadingAssistLocale)} assist`
    : "reading assist";
  const readingAssistAvailabilitySummary =
    availableReadingAssistNoteCount > 0
      ? readingAssistLocaleOptions.length > 0
        ? `${availableReadingAssistNoteCount} notes · ${readingAssistLocaleOptions.map((locale) => formatReadingAssistLocaleLabel(locale)).join(", ")}`
        : `${availableReadingAssistNoteCount} notes with saved reading assist`
      : "No saved reading-assist notes match the current search context yet.";
  const hasActiveFilters =
    Boolean(queryInput.trim()) ||
    selectedTags.length > 0 ||
    statusFilter !== "all" ||
    starredOnly ||
    triageFilter !== null ||
    structuredOnly ||
    hasReadingAssistOnly;
  const quotedSearch = hasQuotedSearch(queryInput);
  const suggestedSearchTerms = !quotedSearch ? uniqueSearchTerms(queryInput).slice(0, 3) : [];
  const emptyStateTitle = !hasActiveFilters
    ? "No notes are indexed yet."
    : structuredOnly && hasReadingAssistOnly && queryInput.trim()
      ? `No structured notes with ${readingAssistFilterLabel} matched this search.`
      : structuredOnly && hasReadingAssistOnly
        ? `No structured notes with ${readingAssistFilterLabel} are available yet.`
    : structuredOnly && queryInput.trim()
      ? "No structured notes matched this search."
      : structuredOnly
        ? "No structured notes are available yet."
        : hasReadingAssistOnly && queryInput.trim()
          ? `No notes with ${readingAssistFilterLabel} matched this search.`
          : hasReadingAssistOnly
            ? `No notes with ${readingAssistFilterLabel} are available yet.`
        : quotedSearch
          ? "No notes matched this exact phrase."
          : "No notes matched the current filters.";
  const emptyStateDetail = !hasActiveFilters
    ? "Automatic pickup depends on local setup. If it is not ready yet, use Import PDF here."
    : structuredOnly && hasReadingAssistOnly && queryInput.trim()
      ? "Try turning off one of the note-presence filters or broadening the search terms."
      : structuredOnly && hasReadingAssistOnly
        ? activeReadingAssistLocale
          ? `Structured ${formatReadingAssistLocaleLabel(activeReadingAssistLocale)} reading assist appears here only after saved summary-level assist is available.`
          : "Reading assist appears here only on notes that already have saved derived summary-level support."
    : structuredOnly && queryInput.trim()
      ? "Try turning off the structured-notes filter or broadening the search terms."
      : structuredOnly
        ? "Structured notes appear here after saved claims or structured tags are added."
        : hasReadingAssistOnly && queryInput.trim()
          ? activeReadingAssistLocale
            ? `Try turning off the ${formatReadingAssistLocaleLabel(activeReadingAssistLocale)}-assist filter or broadening the search terms.`
            : "Try turning off the reading-assist filter or broadening the search terms."
          : hasReadingAssistOnly
            ? activeReadingAssistLocale
              ? `${formatReadingAssistLocaleLabel(activeReadingAssistLocale)} reading assist is still partial and only appears on notes that already have derived summary-level support.`
              : "Reading assist is still partial and only appears on notes that already have saved derived summary-level support."
        : quotedSearch
          ? "Try removing quotes to search by individual terms instead of an exact phrase."
          : "Try fewer terms, a different tag, or clear the current filters.";
  const importDisabledReason = mockReason
    ? "Manual PDF import needs the live backend. It is disabled while this page is in fallback mode."
    : "Import a PDF from this computer when automatic pickup is not ready yet.";
  const firstNoteEntryState = !loading && !loadError && !hasActiveFilters && total === 0;
  const importCalloutEyebrow = firstNoteEntryState ? "Start here" : "Optional fallback";
  const importCalloutTitle = firstNoteEntryState ? "Import your first PDF" : "Add your own PDF";
  const importCalloutDetail = firstNoteEntryState
    ? "If automatic pickup is not ready on this machine, import one PDF here. Lattice opens the saved note immediately so you can keep going from the paper detail."
    : "Automatic pickup is preferred. Use manual import only when pickup is not ready yet, then continue from the saved note.";
  const firstNoteEmptyStateDetail = mockReason
    ? "This page is currently in fallback mode, so finish runtime setup first. Once the live backend is ready, you can import one PDF and open the saved note right away."
    : "Start with one PDF on this machine. If automatic pickup is not ready yet, import it here and Lattice will open the saved note right away.";
  const visibleSummary = useMemo(() => buildVisibleSummary(items), [items]);
  const cloudReadyCount = cloudPapers.filter((item) => item.processing_status === "ready").length;
  const cloudProcessingCount = cloudPapers.filter((item) => item.processing_status === "pending" || item.processing_status === "running").length;
  const cloudBlockedCount = cloudPapers.filter((item) => item.processing_status === "failed" || item.processing_status === "blocked").length;
  const cloudUploadDisabled = Boolean(cloudMockReason) || cloudAuthPreflight?.status === "submission_bundle" || isCloudUploading;

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Paper note index</p>
        <h1 className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">Paper Notes</h1>
        <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
          Find the next paper to review, reopen saved structure, or continue grounded evidence work.
        </p>

        <div
          id="import-pdf"
          ref={importCalloutRef}
          data-testid="paper-notes-import-callout"
          className="mt-4 flex flex-col gap-3 rounded-lg border border-dashed border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 md:flex-row md:items-center md:justify-between"
        >
          <div className="max-w-2xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">{importCalloutEyebrow}</p>
            <p className="text-sm font-medium text-[var(--pp-text-primary)]">{importCalloutTitle}</p>
            <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">
              {importCalloutDetail}
            </p>
          </div>
          <div className="flex flex-col items-start gap-2 md:items-end">
            <input
              ref={importInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleImportSelection}
              className="hidden"
              data-testid="paper-notes-import-input"
            />
            <Button
              ref={importButtonRef}
              type="button"
              onClick={openImportPicker}
              disabled={Boolean(mockReason) || isImporting}
              variant="outline"
              size="sm"
              data-testid="paper-notes-import-button"
            >
              <Upload className="h-4 w-4" />
              {isImporting ? "Importing PDF..." : "Import PDF"}
            </Button>
            <p className="text-xs text-[var(--pp-text-dim)]">{importDisabledReason}</p>
            <Link
              to="/ready"
              className="text-xs text-[var(--pp-accent-text)] underline decoration-[var(--pp-accent-border)] underline-offset-2"
            >
              Check automatic pickup setup
            </Link>
          </div>
        </div>
        {importError ? (
          <p className="mt-3 text-xs text-[var(--pp-status-failed-text)]" data-testid="paper-notes-import-error">
            Import failed: {importError}
          </p>
        ) : null}

        <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-6">
          <label className="md:col-span-2">
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Search</span>
            <span className="flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5">
              <Search className="h-3.5 w-3.5 text-[var(--pp-text-dim)]" />
              <input
                aria-label="Search papers"
                value={queryInput}
                onChange={(event) => handleQueryChange(event.target.value)}
                placeholder="Title, alias, or slug"
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
                  aria-label="Search tags"
                  value={tagInput}
                  onChange={(event) => {
                    setTagInput(event.target.value);
                    setTagMenuOpen(true);
                  }}
                  onFocus={() => setTagMenuOpen(tagInput.trim().length > 0)}
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
                    aria-label={`Remove tag ${tag}`}
                    className="inline-flex items-center gap-1 rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-xs text-[var(--pp-accent-text)]"
                    data-testid="paper-notes-selected-tag"
                  >
                    <span>{tag}</span>
                    <X className="h-3 w-3" />
                  </button>
                ))}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={clearTags}
                  aria-label="Clear selected tags"
                  className="rounded-full"
                >
                  Clear
                </Button>
              </div>
            ) : null}
            <p className="mt-2 text-xs text-[var(--pp-text-dim)]">
              Type to narrow the tag list, then press Enter to add the highlighted tag.
            </p>
          </div>

          <label>
            <span className="mb-1 block text-xs text-[var(--pp-text-dim)]">Status</span>
            <select
              aria-label="Status"
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
                aria-label="Sort"
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
              aria-label="Page size"
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
            variant={starredOnly ? "default" : "outline"}
            onClick={toggleStarredOnly}
            data-testid="paper-notes-starred-toggle"
          >
            Starred
          </Button>
          {PAPER_NOTE_OPERATOR_TRIAGE_LABELS.map((label) => (
            <Button
              key={`triage-filter-${label}`}
              type="button"
              size="sm"
              variant={triageFilter === label ? "default" : "outline"}
              onClick={() => toggleTriageFilter(label)}
              data-testid={`paper-notes-triage-toggle-${label}`}
            >
              {formatPaperNoteTriageLabel(label)}
            </Button>
          ))}
          <Button
            type="button"
            size="sm"
            variant={structuredOnly ? "default" : "outline"}
            onClick={toggleStructuredOnly}
            data-testid="paper-notes-structured-toggle"
          >
            Only structured notes
          </Button>
          <Button
            type="button"
            size="sm"
            variant={hasReadingAssistOnly ? "default" : "outline"}
            onClick={toggleReadingAssistAvailable}
            data-testid="paper-notes-reading-assist-available-toggle"
          >
            Reading assist available
          </Button>
          {readingAssistLocaleOptions.map((locale) => {
            const localeLabel = formatReadingAssistLocaleLabel(locale);
            return (
              <Button
                key={`reading-assist-locale-${locale}`}
                type="button"
                size="sm"
                variant={activeReadingAssistLocale === locale ? "default" : "outline"}
                onClick={() => toggleReadingAssistLocale(locale)}
                data-testid={locale === "ko" ? "paper-notes-reading-assist-toggle" : `paper-notes-reading-assist-toggle-${locale}`}
              >
                Only {localeLabel} assist
              </Button>
            );
          })}
          <p className="text-xs text-[var(--pp-text-dim)]">
            Filters narrow the current list only.
          </p>
          <p className="text-xs text-[var(--pp-text-dim)]">{readingAssistAvailabilitySummary}</p>
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
            {starredOnly ? (
              <Badge variant="outline" data-testid="paper-notes-active-starred-filter">
                starred only
              </Badge>
            ) : null}
            {triageFilter ? (
              <Badge variant="outline" data-testid="paper-notes-active-triage-filter">
                triage: {formatPaperNoteTriageLabel(triageFilter)}
              </Badge>
            ) : null}
            {structuredOnly ? <Badge data-testid="paper-notes-active-structured-filter">structured notes only</Badge> : null}
            {hasReadingAssistOnly ? (
              <Badge data-testid="paper-notes-active-reading-assist-filter">
                {activeReadingAssistLocale ? `${formatReadingAssistLocaleLabel(activeReadingAssistLocale)} assist only` : "Reading assist available"}
              </Badge>
            ) : null}
            <button
              type="button"
              onClick={clearAllFilters}
              aria-label="Clear all filters"
              className="rounded-full border border-[var(--pp-border)] px-2 py-0.5 text-xs text-[var(--pp-text-dim)]"
            >
              Clear filters
            </button>
          </div>
        ) : null}
      </header>

      <section className="surface-card mb-4 overflow-hidden" data-testid="cloud-paper-index">
        <div className="flex flex-col gap-3 border-b border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Cloud paper/page</p>
            <h2 className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]">Server-backed papers</h2>
            <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">
              Cloud PDF storage and server-generated page artifacts are shown here without splitting away from the paper index.
            </p>
          </div>
          <div className="flex flex-col gap-2 md:items-end">
            <input
              ref={cloudUploadInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleCloudUploadSelection}
              className="hidden"
              data-testid="cloud-paper-upload-input"
            />
            <Button
              type="button"
              onClick={openCloudUploadPicker}
              disabled={cloudUploadDisabled}
              variant="outline"
              size="sm"
              data-testid="cloud-paper-upload-button"
            >
              {isCloudUploading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {isCloudUploading ? "Uploading" : "Upload cloud PDF"}
            </Button>
            <div className="grid min-w-full grid-cols-3 gap-2 text-xs md:min-w-[300px]">
            <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Ready</p>
              <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{cloudReadyCount}</p>
            </div>
            <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Processing</p>
              <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{cloudProcessingCount}</p>
            </div>
            <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Needs check</p>
              <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{cloudBlockedCount}</p>
            </div>
            </div>
          </div>
        </div>
        <CloudAuthPreflightPanel
          preflight={cloudAuthPreflight}
          loading={cloudAuthLoading}
          error={cloudAuthError}
          mockReason={cloudAuthMockReason}
          onRefresh={() => {
            void loadCloudAuthPreflight();
          }}
        />
        {cloudMockReason ? (
          <div className="border-b border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2 text-xs text-[var(--pp-text-dim)]">
            Fallback mode: {cloudMockReason}
          </div>
        ) : null}
        {cloudActionError ? (
          <div className="border-b border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2 text-xs text-[var(--pp-status-failed-text)]">
            Cloud action failed: {cloudActionError}
          </div>
        ) : null}
        <CloudPaperSearchResults
          query={query}
          items={cloudSearchHits}
          loading={cloudSearchLoading}
          error={cloudSearchError}
          mockReason={cloudSearchMockReason}
        />
        {cloudError ? (
          <div className="p-4 text-sm text-[var(--pp-status-failed-text)]" data-testid="cloud-paper-load-error">
            API error: {cloudError}
          </div>
        ) : cloudLoading ? (
          <div className="space-y-3 p-3" aria-label="Loading cloud papers">
            {Array.from({ length: 3 }).map((_, idx) => (
              <div key={`cloud-loading-${idx}`} className="rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3">
                <div className="h-4 w-2/5 animate-pulse rounded bg-[var(--pp-surface-muted)]" />
                <div className="mt-3 h-3 w-3/5 animate-pulse rounded bg-[var(--pp-surface-muted)]" />
              </div>
            ))}
          </div>
        ) : cloudPapers.length > 0 ? (
          <div className="space-y-3 p-3">
            {cloudPapers.map((item) => (
              <CloudPaperListRow
                key={item.paper_id}
                item={item}
                pagePreview={cloudPagePreviewById[item.paper_id] ?? null}
                hydrationState={cloudHydrationById[item.paper_id] ?? null}
                loadingPage={loadingCloudPageId === item.paper_id}
                hydrating={hydratingCloudPaperId === item.paper_id}
                onLoadPage={handleLoadCloudPage}
                onHydrate={handleHydrateCloudPaper}
              />
            ))}
          </div>
        ) : (
          <div className="p-4 text-sm text-[var(--pp-text-secondary)]">No cloud papers are visible for this lab and device.</div>
        )}
      </section>

      <section className="surface-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs text-[var(--pp-text-dim)]">
          <span>{loading ? "Loading notes..." : `${total} notes · page ${page}/${totalPages} · size ${pageSize}`}</span>
        </div>
        {mockReason ? (
          <div
            data-testid="paper-notes-runtime-guidance"
            className="border-b border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2 text-xs text-[var(--pp-text-dim)]"
          >
            <p>Fallback mode: {mockReason}</p>
            <p className="mt-1">
              If you expected the live notes index here,{" "}
              <Link to="/ready" className="text-[var(--pp-accent-text)] underline underline-offset-2">
                open Runtime checks
              </Link>{" "}
              before retrying this page.
            </p>
          </div>
        ) : null}
        {loadError ? (
          <div data-testid="paper-notes-load-error" className="p-4 text-sm text-[var(--pp-status-failed-text)]">
            <p>API error: {loadError}</p>
            <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
              If this page should be loading from the live runtime,{" "}
              <Link to="/ready" className="text-[var(--pp-accent-text)] underline underline-offset-2">
                open Runtime checks
              </Link>{" "}
              before retrying.
            </p>
          </div>
        ) : null}
        {!loadError ? (
          <>
            {!loading && total > 0 ? (
              <div
                className="border-b border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-3"
                data-testid="paper-notes-visible-summary"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Visible now</p>
                    <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
                      These counts reflect the notes currently visible after search, filters, and pagination.
                    </p>
                  </div>
                  <div className="grid min-w-full gap-2 sm:min-w-[420px] sm:grid-cols-4">
                    <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
                      <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Visible</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{visibleSummary.visibleCount}</p>
                    </div>
                    <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
                      <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Structured</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{visibleSummary.structuredCount}</p>
                    </div>
                    <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
                      <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Needs review</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{visibleSummary.needsReviewCount}</p>
                    </div>
                    <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-3 py-2">
                      <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Repair first</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{visibleSummary.blockedCount}</p>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
            {!loading && total === 0 ? (
              <div
                className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between"
                data-testid="paper-notes-empty-state"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--pp-text-primary)]">{emptyStateTitle}</p>
                  <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                    {!hasActiveFilters ? firstNoteEmptyStateDetail : emptyStateDetail}
                  </p>
                </div>
                {!hasActiveFilters ? (
                  <div className="flex flex-col items-start gap-2 md:items-end">
                    <div className="flex flex-wrap gap-2">
                      {!mockReason ? (
                        <Button
                          type="button"
                          size="sm"
                          onClick={openImportPicker}
                          disabled={isImporting}
                          data-testid="paper-notes-empty-import"
                        >
                          <Upload className="h-4 w-4" />
                          {isImporting ? "Importing PDF..." : "Import PDF"}
                        </Button>
                      ) : null}
                      <Link
                        to="/ready"
                        className={buttonClassName({ variant: "outline", size: "sm" })}
                        data-testid="paper-notes-empty-runtime"
                      >
                        Check automatic pickup setup
                      </Link>
                    </div>
                    <p className="text-xs text-[var(--pp-text-dim)]">
                      {mockReason
                        ? "Manual import is unavailable until the live backend is ready."
                        : "Import one paper, then continue from the saved note detail."}
                    </p>
                  </div>
                ) : (
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
                        Turn off structured filter
                      </Button>
                    ) : null}
                    {hasReadingAssistOnly ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={clearReadingAssistFilter}
                        data-testid="paper-notes-empty-clear-reading-assist"
                      >
                        {activeReadingAssistLocale
                          ? `Turn off ${formatReadingAssistLocaleLabel(activeReadingAssistLocale)}-assist filter`
                          : "Turn off reading-assist filter"}
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
                )}
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
                : items.map((item) => (
                    <PaperNoteListRow
                      key={item.slug}
                      item={item}
                      query={query}
                      readingAssistLocale={activeReadingAssistLocale}
                    />
                  ))}
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
