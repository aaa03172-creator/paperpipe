import { ChangeEvent, Children, ReactNode, isValidElement, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Copy, ExternalLink, FileText, FlaskConical, Languages, LibraryBig, Link2, PanelRightOpen, Save, ScrollText, ShieldCheck, Star, Upload } from "lucide-react";
import {
  createProtocolDraftFromAttachment,
  enqueueDeepRead,
  getApiErrorMessage,
  getJob,
  getPaperNoteDetail,
  logClientUserAction,
  runSkillAction,
  updatePaperNoteOperatorState,
} from "../lib/api";
import {
  formatPaperNoteTriageLabel,
  hasPaperOperatorNoteText,
  isSamePaperOperatorState,
  MAX_PAPER_OPERATOR_NOTE_LENGTH,
  normalizePaperOperatorNoteText,
  PAPER_NOTE_OPERATOR_TRIAGE_LABELS,
} from "../lib/paperOperatorState";
import {
  AppraisalCheckStatus,
  AppraisalConcernSeverity,
  CriticalAppraisalCheck,
  CriticalAppraisalConcern,
  CriticalAppraisalQuestion,
  CriticalAppraisalReport,
  JobLifecycle,
  OutputModeFamily,
  PaperNoteContextTrace,
  PaperNoteDetailResponse,
  PaperNoteOperatorState,
  PaperNoteOperatorTriageLabel,
  PaperNoteReference,
  PaperNoteRelated,
  PaperNoteSectionNavigatorItem as PaperNoteSectionNavigatorApiItem,
  PaperNoteSummary,
  ProtocolAttachmentDraftResponse,
  SkillActionInfo,
  SkillRunRecord,
  StructuredPaperState,
} from "../lib/types";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
import { StatusBadge } from "../components/StatusBadge";
import { WorkspaceContextCard, WorkspaceContextStrip } from "../components/WorkspaceContextStrip";
import { jobLabel } from "../lib/ui";
import { sanitizeRenderableHref } from "../lib/safeLinks";
import { formatFreeformStatusLabel, getFreeformStatusTone, getPaperLifecycleTone, getStatusToneClassName } from "../lib/statusSystem";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { buttonClassName } from "../components/ui/buttonClassName";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Separator } from "../components/ui/separator";
import { Sheet } from "../components/ui/sheet";

interface OutlineItem {
  id: string;
  label: string;
  level: number;
}

interface SectionNavigatorItem {
  key: string;
  label: string;
  outlineId?: string | null;
  outlineOrder?: number | null;
  claimCount: number;
  evidenceCount: number;
  representativeClaimId?: string | null;
  representativeEvidenceId?: string | null;
  pageStart?: number | null;
  pageEnd?: number | null;
  matchedToOutline: boolean;
}

type FocusKind = "claim" | "evidence" | "run";
type ViewerOutputMode = Extract<OutputModeFamily, "learner" | "builder_debug">;
type ImportDeepReadJobStatus = {
  jobId: string;
  runId?: string | null;
  status: JobLifecycle;
  progress?: number | null;
  stage?: string | null;
  errorMessage?: string | null;
};

interface FocusTarget {
  kind: FocusKind;
  id: string;
}

interface ProtocolCardAttachmentNavigationState {
  attachmentDraft: ProtocolAttachmentDraftResponse;
}

const PROTOCOL_ATTACHMENT_ACCEPT =
  ".txt,.md,.csv,.tsv,.json,.yaml,.yml,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.tif,.tiff,image/*";

function parseViewerOutputMode(value: string | null): ViewerOutputMode {
  return value === "builder_debug" ? "builder_debug" : "learner";
}

function formatViewerOutputModeLabel(value: ViewerOutputMode): string {
  return value === "builder_debug" ? "Review" : "Read";
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
    return "Review mode lifts actions, run history, and saved claims ahead of supporting context.";
  }
  return "Read mode keeps related papers, references, and reading context closer to the markdown flow.";
}

function getViewerContextDescription(value: ViewerOutputMode): string {
  if (value === "builder_debug") {
    return "Review structured outputs and operational state first, then hand off to the deeper review surface when needed.";
  }
  return "Use the note outline, related papers, and references before handing off to review for evidence validation.";
}

function getReadingViewDescription(value: ViewerOutputMode): string {
  if (value === "builder_debug") {
    return "Markdown body stays canonical while the surrounding rail prioritizes review-oriented structured outputs.";
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

function getImportDeepReadStatusGuidance(job: ImportDeepReadJobStatus): string {
  if (job.status === "queued") {
    return "Queued on the local worker. Open review for full progress; if it stays queued, check /ready.";
  }
  if (job.status === "running") {
    return "Deep read is running. This can take several minutes; open review for logs and live progress.";
  }
  if (job.status === "completed") {
    return "Deep read completed. Open review to inspect saved evidence and generated state.";
  }
  if (job.status === "failed") {
    return "Deep read stopped before completion. Open review for logs, then check /ready if inference setup looks unhealthy.";
  }
  return "Deep read was cancelled. Queue it again when you are ready to continue.";
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

type SectionNavigationSignalStatus = "pass" | "warn" | "fail";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => (typeof item === "string" ? item.trim() : "")).filter(Boolean);
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeSectionNavigationSignalStatus(value: unknown): SectionNavigationSignalStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "pass" || normalized === "warn" || normalized === "fail") {
    return normalized;
  }
  return null;
}

function parseSectionNavigationSignalDetail(detail: string | null): { claimsetSectionCount: number | null; summaryPresent: boolean | null } {
  if (!detail) {
    return { claimsetSectionCount: null, summaryPresent: null };
  }
  const claimsetCountMatch = detail.match(/claimset_section_count=(\d+)/i);
  const summaryPresentMatch = detail.match(/summary_present=(true|false)/i);
  return {
    claimsetSectionCount: claimsetCountMatch ? Number.parseInt(claimsetCountMatch[1] ?? "", 10) : null,
    summaryPresent:
      summaryPresentMatch?.[1] === "true" ? true : summaryPresentMatch?.[1] === "false" ? false : null,
  };
}

function buildSectionNavigationSignalSummary(state: StructuredPaperState | null): { label: string; className: string; detail: string } | null {
  if (!state) {
    return null;
  }
  const latestRunData = isRecord(state.runs?.[0]?.data) ? state.runs[0].data : null;
  const stateSignals = isRecord(state.signals) ? state.signals : null;
  const runtimeSectionSummary = Array.isArray(latestRunData?.section_summary) ? latestRunData.section_summary : [];
  const runtimeSectionCount =
    typeof latestRunData?.section_count === "number"
      ? latestRunData.section_count
      : typeof stateSignals?.section_count === "number"
        ? stateSignals.section_count
        : null;
  const explicitStatus = normalizeSectionNavigationSignalStatus(
    latestRunData?.section_navigation_signal_status ?? stateSignals?.quality_gate_section_navigation_signal,
  );
  const inferredStatus =
    runtimeSectionSummary.length > 0 || (typeof runtimeSectionCount === "number" && runtimeSectionCount > 0) ? "pass" : null;
  const status = explicitStatus ?? inferredStatus;
  if (!status) {
    return null;
  }

  const rawDetail =
    typeof latestRunData?.section_navigation_signal_detail === "string"
      ? latestRunData.section_navigation_signal_detail
      : status === "pass"
        ? `claimset_section_count=${runtimeSectionCount ?? runtimeSectionSummary.length}, summary_present=${
            runtimeSectionSummary.length > 0 ? "true" : "false"
          }`
        : null;
  const parsedDetail = parseSectionNavigationSignalDetail(rawDetail);
  const sectionGroupText =
    typeof parsedDetail.claimsetSectionCount === "number"
      ? `${parsedDetail.claimsetSectionCount} saved section group${parsedDetail.claimsetSectionCount === 1 ? "" : "s"}`
      : "Saved section groups";

  if (status === "pass") {
    return {
      label: "Saved signal ready",
      className:
        "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
      detail: `${sectionGroupText} are available for reopening note headings or saved evidence.`,
    };
  }
  if (status === "warn") {
    return {
      label: "Saved signal thin",
      className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
      detail:
        parsedDetail.summaryPresent === false || parsedDetail.claimsetSectionCount === 0
          ? "Latest saved run did not keep full section cues, so the viewer may fall back to note headings or evidence labels."
          : "Saved section cues are incomplete, so navigation may rely on viewer-side fallback grouping.",
    };
  }
  return {
    label: "Saved signal missing",
    className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    detail: "Saved section cues are missing; rerun Deep Read if you need stronger section reopen support.",
  };
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
  has_claimset: "saved claims",
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

function normalizeAppraisalCheckStatus(value: unknown): AppraisalCheckStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "pass" || normalized === "warn" || normalized === "fail" || normalized === "not_run") {
    return normalized;
  }
  return null;
}

function normalizeAppraisalConcernSeverity(value: unknown): AppraisalConcernSeverity | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "info" || normalized === "warn" || normalized === "fail") {
    return normalized;
  }
  return null;
}

function parseAppraisalCheck(value: unknown): CriticalAppraisalCheck | null {
  if (!isRecord(value)) {
    return null;
  }
  const code = typeof value.code === "string" ? value.code.trim() : "";
  const label = typeof value.label === "string" ? value.label.trim() : "";
  const detail = typeof value.detail === "string" ? value.detail.trim() : "";
  const status = normalizeAppraisalCheckStatus(value.status);
  if (!code || !label || !detail || !status) {
    return null;
  }
  return { code, label, status, detail };
}

function parseAppraisalConcern(value: unknown): CriticalAppraisalConcern | null {
  if (!isRecord(value)) {
    return null;
  }
  const code = typeof value.code === "string" ? value.code.trim() : "";
  const title = typeof value.title === "string" ? value.title.trim() : "";
  const detail = typeof value.detail === "string" ? value.detail.trim() : "";
  const severity = normalizeAppraisalConcernSeverity(value.severity);
  if (!code || !title || !detail || !severity) {
    return null;
  }
  return {
    code,
    title,
    detail,
    severity,
    claim_ids: asStringArray(value.claim_ids),
    evidence_ids: asStringArray(value.evidence_ids),
    source_artifacts: asStringArray(value.source_artifacts),
  };
}

function parseAppraisalQuestion(value: unknown): CriticalAppraisalQuestion | null {
  if (!isRecord(value)) {
    return null;
  }
  const code = typeof value.code === "string" ? value.code.trim() : "";
  const question = typeof value.question === "string" ? value.question.trim() : "";
  const rationale = typeof value.rationale === "string" ? value.rationale.trim() : "";
  if (!code || !question || !rationale) {
    return null;
  }
  return {
    code,
    question,
    rationale,
    claim_ids: asStringArray(value.claim_ids),
    evidence_ids: asStringArray(value.evidence_ids),
  };
}

function buildLegacyAppraisalReport(run: SkillRunRecord, appraisal: Record<string, unknown>): CriticalAppraisalReport | null {
  const label = typeof appraisal.label === "string" ? appraisal.label.trim() : "";
  const claimCount = asFiniteNumber(appraisal.claim_count) ?? 0;
  const evidenceCount = asFiniteNumber(appraisal.evidence_count) ?? 0;
  const avgConfidence = asFiniteNumber(appraisal.avg_confidence) ?? 0;
  const verifiedChecks = asFiniteNumber(appraisal.verified_checks) ?? 0;
  const inconsistentChecks = asFiniteNumber(appraisal.inconsistent_checks) ?? 0;
  if (!label) {
    return null;
  }
  return {
    schema_version: "critical_appraisal.v1-legacy",
    layer: "review_gate",
    canonical_status: "non_canonical",
    label,
    summary:
      typeof run.summary === "string" && run.summary.trim()
        ? run.summary.trim()
        : `${label}: ${claimCount} claims, avg confidence ${avgConfidence.toFixed(2)}, ${inconsistentChecks} inconsistent checks.`,
    claim_count: claimCount,
    evidence_count: evidenceCount,
    avg_confidence: avgConfidence,
    verified_checks: verifiedChecks,
    inconsistent_checks: inconsistentChecks,
    checks: [],
    concerns: [],
    questions: [],
    warnings: [],
    source_artifacts: [],
  };
}

function parseCriticalAppraisalReport(run: SkillRunRecord | null): CriticalAppraisalReport | null {
  if (!run || !isRecord(run.data)) {
    return null;
  }
  const record = run.data;
  if (isRecord(record.appraisal_report)) {
    const report = record.appraisal_report;
    const label = typeof report.label === "string" ? report.label.trim() : "";
    const summary = typeof report.summary === "string" ? report.summary.trim() : "";
    if (!label || !summary) {
      return null;
    }
    return {
      schema_version: typeof report.schema_version === "string" ? report.schema_version : "critical_appraisal.v2",
      layer: "review_gate",
      canonical_status: "non_canonical",
      label,
      summary,
      claim_count: asFiniteNumber(report.claim_count) ?? 0,
      evidence_count: asFiniteNumber(report.evidence_count) ?? 0,
      avg_confidence: asFiniteNumber(report.avg_confidence) ?? 0,
      verified_checks: asFiniteNumber(report.verified_checks) ?? 0,
      inconsistent_checks: asFiniteNumber(report.inconsistent_checks) ?? 0,
      checks: Array.isArray(report.checks)
        ? report.checks.map(parseAppraisalCheck).filter((item): item is CriticalAppraisalCheck => item !== null)
        : [],
      concerns: Array.isArray(report.concerns)
        ? report.concerns.map(parseAppraisalConcern).filter((item): item is CriticalAppraisalConcern => item !== null)
        : [],
      questions: Array.isArray(report.questions)
        ? report.questions.map(parseAppraisalQuestion).filter((item): item is CriticalAppraisalQuestion => item !== null)
        : [],
      warnings: asStringArray(report.warnings),
      source_artifacts: asStringArray(report.source_artifacts),
    };
  }
  if (isRecord(record.appraisal)) {
    return buildLegacyAppraisalReport(run, record.appraisal);
  }
  return null;
}

function getLatestCriticalAppraisalRun(state: StructuredPaperState | null): SkillRunRecord | null {
  if (!state) {
    return null;
  }
  return state.runs.find((run) => run.action === "critical_appraisal") ?? null;
}

function toggleOperatorTriageLabel(
  labels: PaperNoteOperatorTriageLabel[],
  target: PaperNoteOperatorTriageLabel,
): PaperNoteOperatorTriageLabel[] {
  const next = new Set(labels);
  if (next.has(target)) {
    next.delete(target);
  } else {
    next.add(target);
  }
  return PAPER_NOTE_OPERATOR_TRIAGE_LABELS.filter((label) => next.has(label));
}

function buildOperatorStateUpdatePayload(operatorState: PaperNoteOperatorState) {
  const normalizedText = normalizePaperOperatorNoteText(operatorState.paper_note_text);
  return {
    paper_note_text: normalizedText.length > 0 ? normalizedText : null,
    starred: operatorState.starred,
    triage_labels: [...operatorState.triage_labels],
  };
}

function applyOperatorStateToDetail(
  detail: PaperNoteDetailResponse,
  operatorState: PaperNoteOperatorState,
): PaperNoteDetailResponse {
  return {
    ...detail,
    operator_state: operatorState,
    note: {
      ...detail.note,
      starred: operatorState.starred,
      has_operator_note: hasPaperOperatorNoteText(operatorState.paper_note_text),
      triage_labels: [...operatorState.triage_labels],
    },
  };
}

function OperatorStateBadges({ operatorState }: { operatorState: PaperNoteOperatorState | null }) {
  if (!operatorState) {
    return null;
  }

  const hasNote = hasPaperOperatorNoteText(operatorState.paper_note_text);
  const hasMarkers = operatorState.starred || hasNote || operatorState.triage_labels.length > 0;
  if (!hasMarkers) {
    return null;
  }

  return (
    <>
      {operatorState.starred ? (
        <Badge variant="default" data-testid="paper-note-operator-badge-starred">
          Starred
        </Badge>
      ) : null}
      {hasNote ? (
        <Badge variant="outline" data-testid="paper-note-operator-badge-note">
          My note
        </Badge>
      ) : null}
      {operatorState.triage_labels.map((label) => (
        <Badge
          key={`operator-badge-${label}`}
          variant="muted"
          data-testid={`paper-note-operator-badge-${label}`}
        >
          {formatPaperNoteTriageLabel(label)}
        </Badge>
      ))}
    </>
  );
}

interface ReviewSnapshotCounts {
  claimCount: number;
  evidenceCount: number;
  groundedCount: number;
  needsReviewCount: number;
  unresolvedCount: number;
}

type StructuredClaim = StructuredPaperState["claimset"][number];
type StructuredEvidence = StructuredClaim["evidence"][number];

interface ReviewBridgeFocus {
  kind: "claim" | "evidence";
  focusId: string;
  claimId: string;
  claimText: string;
  evidenceText: string | null;
  location: string | null;
  emphasisLabel: string;
  reviewHint: string;
  groundingBadge: { label: string; className: string } | null;
}

interface ReviewBridgeStatusCopy {
  title: string;
  detail: string;
  className: string;
}

function toSafeCount(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.trunc(value));
  }
  return fallback;
}

function deriveReviewSnapshotCounts(state: StructuredPaperState | null): ReviewSnapshotCounts {
  if (!state) {
    return {
      claimCount: 0,
      evidenceCount: 0,
      groundedCount: 0,
      needsReviewCount: 0,
      unresolvedCount: 0,
    };
  }

  let groundedCount = 0;
  let needsReviewCount = 0;
  let unresolvedCount = 0;
  let fallbackEvidenceCount = 0;

  state.claimset.forEach((claim) => {
    fallbackEvidenceCount += claim.evidence.length;
    claim.evidence.forEach((evidence) => {
      if (evidence.grounded === true) {
        groundedCount += 1;
        return;
      }
      if (evidence.grounded === false && evidence.resolution === "AMBIGUOUS_MATCH") {
        needsReviewCount += 1;
        return;
      }
      if (evidence.grounded === false) {
        unresolvedCount += 1;
      }
    });
  });

  return {
    claimCount: toSafeCount(state.signals.claim_count, state.claimset.length),
    evidenceCount: toSafeCount(state.signals.evidence_count, fallbackEvidenceCount),
    groundedCount,
    needsReviewCount,
    unresolvedCount,
  };
}

function buildReviewSnapshotSummary(stateLoaded: boolean, counts: ReviewSnapshotCounts): string {
  if (!stateLoaded) {
    return "No saved review state is loaded yet. This note still works for reading, but structured evidence review will stay thinner until saved state exists.";
  }
  if (counts.claimCount === 0 && counts.evidenceCount === 0) {
    return "Saved review state is loaded, but no saved claims or evidence excerpts are recorded yet.";
  }
  if (counts.needsReviewCount > 0 || counts.unresolvedCount > 0) {
    return `${counts.claimCount} saved claims and ${counts.evidenceCount} evidence excerpts are available. ${counts.groundedCount} grounded, ${counts.needsReviewCount} need review, and ${counts.unresolvedCount} remain unresolved.`;
  }
  if (counts.evidenceCount > 0) {
    return `${counts.claimCount} saved claims and ${counts.evidenceCount} evidence excerpts are available. All recorded evidence is currently grounded.`;
  }
  return `${counts.claimCount} saved claims are available for this note.`;
}

function buildReviewSnapshotNextStep(
  note: PaperNoteSummary | null,
  stateLoaded: boolean,
  counts: ReviewSnapshotCounts,
  hasWorkbenchTarget: boolean,
): string | null {
  const opsSummary = note?.ops_summary ?? null;
  if (opsSummary?.recommended_action === "repair_stats") {
    return "Next step: open Workbench and refresh saved checks before trusting downstream artifacts.";
  }
  if (!hasWorkbenchTarget) {
    return null;
  }
  if (!stateLoaded) {
    return "Next step: open Workbench to generate structured review state for this note.";
  }
  if (counts.needsReviewCount > 0 || counts.unresolvedCount > 0) {
    return "Next step: open Workbench to inspect the flagged evidence before exporting or reusing this note.";
  }
  return "Next step: open Workbench when you want to validate evidence in context or continue into downstream artifacts.";
}

function buildReviewBridgeStatusCopy(stateLoaded: boolean, counts: ReviewSnapshotCounts): ReviewBridgeStatusCopy {
  if (!stateLoaded) {
    return {
      title: "Structured review state is missing.",
      detail: "Open review to generate saved claims and evidence anchors before relying on this note downstream.",
      className: "border-[var(--pp-border)] bg-[var(--pp-surface)] text-[var(--pp-text-secondary)]",
    };
  }
  if (counts.unresolvedCount > 0) {
    return {
      title: "Unresolved evidence is still blocking downstream trust.",
      detail: "Re-open the saved evidence anchor before you reuse this note in a meeting, protocol, or export.",
      className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    };
  }
  if (counts.needsReviewCount > 0) {
    return {
      title: "Ambiguous evidence still needs review.",
      detail: "Check the saved evidence anchor in review mode before treating this note as settled.",
      className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
    };
  }
  if (counts.groundedCount > 0) {
    return {
      title: "Saved evidence is currently grounded.",
      detail: "You can keep reading here, then open review only when you want full claim context or downstream artifact work.",
      className: "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
    };
  }
  return {
    title: "Saved claims are available, but evidence depth is still thin.",
    detail: "Open review when you want to validate or expand the saved anchors behind this note.",
    className: "border-[var(--pp-border)] bg-[var(--pp-surface)] text-[var(--pp-text-secondary)]",
  };
}

function truncateText(value: string | null | undefined, maxLength = 220): string {
  const trimmed = value?.trim() ?? "";
  if (!trimmed || trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function buildEvidenceLocationSummary(evidence: StructuredEvidence, fallbackEvidenceId: string): string | null {
  const parts: string[] = [];
  const section = evidence.locator?.section ?? evidence.section;
  if (section) {
    parts.push(section);
  }
  const page = evidence.locator?.page ?? evidence.page;
  if (typeof page === "number") {
    parts.push(`page ${page + 1}`);
  }
  if (evidence.locator?.chunk_id) {
    parts.push(evidence.locator.chunk_id);
  }
  if (parts.length === 0 && fallbackEvidenceId) {
    parts.push(fallbackEvidenceId);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function getEvidencePriority(evidence: StructuredEvidence): number {
  if (evidence.grounded === false && evidence.resolution === "AMBIGUOUS_MATCH") {
    return 3;
  }
  if (evidence.grounded === false) {
    return 2;
  }
  if (evidence.grounded === true) {
    return 1;
  }
  return 0;
}

function deriveReviewBridgeFocus(state: StructuredPaperState | null): ReviewBridgeFocus | null {
  const claims: StructuredClaim[] = state?.claimset ?? [];
  let bestMatch:
    | {
        claim: StructuredClaim;
        evidence: StructuredEvidence;
        evidenceId: string;
        priority: number;
      }
    | null = null;

  for (const claim of claims) {
    for (const [index, evidence] of claim.evidence.entries()) {
      const priority = getEvidencePriority(evidence);
      if (priority <= 0) {
        continue;
      }
      const evidenceId = evidence.id ?? `${claim.id}-evidence-${index + 1}`;
      if (!bestMatch || priority > bestMatch.priority) {
        bestMatch = {
          claim,
          evidence,
          evidenceId,
          priority,
        };
      }
    }
  }

  if (bestMatch) {
    const reviewHint =
      bestMatch.priority >= 3
        ? "Check this saved anchor before treating the note as settled."
        : bestMatch.priority === 2
          ? "Resolve this saved anchor before you reuse the note downstream."
          : "Use this saved anchor when you want to jump back into source context.";
    return {
      kind: "evidence",
      focusId: bestMatch.evidenceId,
      claimId: bestMatch.claim.id,
      claimText: bestMatch.claim.claim,
      evidenceText: bestMatch.evidence.text ?? null,
      location: buildEvidenceLocationSummary(bestMatch.evidence, bestMatch.evidenceId),
      emphasisLabel:
        bestMatch.priority >= 3
          ? "Flagged evidence to inspect"
          : bestMatch.priority === 2
            ? "Unresolved evidence to reopen first"
            : "Saved evidence ready to reuse",
      reviewHint,
      groundingBadge: getGroundingBadge(bestMatch.evidence.grounded, bestMatch.evidence.resolution),
    };
  }

  const firstClaim = claims[0] ?? null;
  if (!firstClaim) {
    return null;
  }

  return {
    kind: "claim",
    focusId: firstClaim.id,
    claimId: firstClaim.id,
    claimText: firstClaim.claim,
    evidenceText: null,
    location: null,
    emphasisLabel: "Saved claim ready to review",
    reviewHint: "Open review when you want to add or validate saved evidence anchors behind this claim.",
    groundingBadge: null,
  };
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

function isCanonicalNoteSlugCandidate(value?: string | null): boolean {
  const trimmed = value?.trim() ?? "";
  if (!trimmed) {
    return false;
  }
  return /\s/.test(trimmed) === false;
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

function normalizeSectionKey(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  return slugifyHeading(trimmed) || trimmed.toLowerCase();
}

function buildSectionNavigatorItemsFromRuntimeSummary(
  state: StructuredPaperState,
  outline: OutlineItem[],
): SectionNavigatorItem[] {
  const outlineByKey = new Map<string, { id: string; label: string; order: number }>();
  outline.forEach((item, index) => {
    const key = normalizeSectionKey(item.label);
    if (!key || outlineByKey.has(key)) {
      return;
    }
    outlineByKey.set(key, {
      id: item.id,
      label: item.label,
      order: index,
    });
  });

  const rawSummary = state.runs?.[0]?.data?.["section_summary"];
  if (!Array.isArray(rawSummary) || rawSummary.length === 0) {
    return [];
  }

  const items: SectionNavigatorItem[] = [];
  for (const rawItem of rawSummary) {
    if (!rawItem || typeof rawItem !== "object") {
      continue;
    }
    const record = rawItem as Record<string, unknown>;
    const fallbackLabel = typeof record.label === "string" ? record.label.trim() : "";
    const key = normalizeSectionKey(
      typeof record.key === "string" ? record.key : fallbackLabel,
    );
    if (!key || !fallbackLabel) {
      continue;
    }
    const outlineMatch = outlineByKey.get(key);
    items.push({
      key,
      label: outlineMatch?.label ?? fallbackLabel,
      outlineId: outlineMatch?.id ?? null,
      outlineOrder: outlineMatch?.order ?? null,
      claimCount: typeof record.claim_count === "number" ? record.claim_count : 0,
      evidenceCount: typeof record.evidence_count === "number" ? record.evidence_count : 0,
      representativeClaimId:
        typeof record.representative_claim_id === "string" ? record.representative_claim_id : null,
      representativeEvidenceId:
        typeof record.representative_evidence_id === "string" ? record.representative_evidence_id : null,
      pageStart: typeof record.page_start === "number" ? record.page_start : null,
      pageEnd: typeof record.page_end === "number" ? record.page_end : null,
      matchedToOutline: Boolean(outlineMatch),
    });
  }

  return items.sort((left, right) => {
    if (left.matchedToOutline && right.matchedToOutline) {
      return (left.outlineOrder ?? Number.MAX_SAFE_INTEGER) - (right.outlineOrder ?? Number.MAX_SAFE_INTEGER);
    }
    if (left.matchedToOutline !== right.matchedToOutline) {
      return left.matchedToOutline ? -1 : 1;
    }
    if (left.evidenceCount !== right.evidenceCount) {
      return right.evidenceCount - left.evidenceCount;
    }
    if (left.claimCount !== right.claimCount) {
      return right.claimCount - left.claimCount;
    }
    return left.label.localeCompare(right.label);
  });
}

function buildSectionNavigatorItems(state: StructuredPaperState | null, outline: OutlineItem[]): SectionNavigatorItem[] {
  if (!state) {
    return [];
  }

  const runtimeItems = buildSectionNavigatorItemsFromRuntimeSummary(state, outline);
  if (runtimeItems.length > 0) {
    return runtimeItems;
  }

  const outlineByKey = new Map<string, { id: string; label: string; order: number }>();
  outline.forEach((item, index) => {
    const key = normalizeSectionKey(item.label);
    if (!key || outlineByKey.has(key)) {
      return;
    }
    outlineByKey.set(key, {
      id: item.id,
      label: item.label,
      order: index,
    });
  });

  const sections = new Map<
    string,
    {
      key: string;
      label: string;
      outlineId?: string | null;
      outlineOrder?: number | null;
      claimCount: number;
      evidenceCount: number;
      representativeClaimId?: string | null;
      representativeEvidenceId?: string | null;
      pages: number[];
      matchedToOutline: boolean;
    }
  >();

  for (const claim of state.claimset ?? []) {
    const claimSectionKeys = new Set<string>();
    for (const [index, evidence] of (claim.evidence ?? []).entries()) {
      const sectionLabel = `${evidence.locator?.section ?? evidence.section ?? ""}`.trim();
      if (!sectionLabel) {
        continue;
      }

      const key = normalizeSectionKey(sectionLabel);
      if (!key) {
        continue;
      }

      const outlineMatch = outlineByKey.get(key);
      const existing = sections.get(key);
      const next =
        existing ??
        {
          key,
          label: outlineMatch?.label ?? sectionLabel,
          outlineId: outlineMatch?.id ?? null,
          outlineOrder: outlineMatch?.order ?? null,
          claimCount: 0,
          evidenceCount: 0,
          representativeClaimId: null,
          representativeEvidenceId: null,
          pages: [],
          matchedToOutline: Boolean(outlineMatch),
        };

      if (!claimSectionKeys.has(key)) {
        next.claimCount += 1;
        claimSectionKeys.add(key);
      }
      next.evidenceCount += 1;
      if (!next.representativeClaimId) {
        next.representativeClaimId = claim.id;
      }
      if (!next.representativeEvidenceId) {
        next.representativeEvidenceId = evidence.id ?? `${claim.id}-evidence-${index + 1}`;
      }

      const page = evidence.locator?.page ?? evidence.page;
      if (typeof page === "number" && Number.isFinite(page)) {
        next.pages.push(page);
      }

      sections.set(key, next);
    }
  }

  return Array.from(sections.values())
    .map((item) => {
      const sortedPages = Array.from(new Set(item.pages)).sort((left, right) => left - right);
      return {
        key: item.key,
        label: item.label,
        outlineId: item.outlineId,
        outlineOrder: item.outlineOrder,
        claimCount: item.claimCount,
        evidenceCount: item.evidenceCount,
        representativeClaimId: item.representativeClaimId,
        representativeEvidenceId: item.representativeEvidenceId,
        pageStart: sortedPages.length > 0 ? sortedPages[0] : null,
        pageEnd: sortedPages.length > 0 ? sortedPages[sortedPages.length - 1] : null,
        matchedToOutline: item.matchedToOutline,
      };
    })
    .sort((left, right) => {
      if (left.matchedToOutline && right.matchedToOutline) {
        return (left.outlineOrder ?? Number.MAX_SAFE_INTEGER) - (right.outlineOrder ?? Number.MAX_SAFE_INTEGER);
      }
      if (left.matchedToOutline !== right.matchedToOutline) {
        return left.matchedToOutline ? -1 : 1;
      }
      if (left.evidenceCount !== right.evidenceCount) {
        return right.evidenceCount - left.evidenceCount;
      }
      if (left.claimCount !== right.claimCount) {
        return right.claimCount - left.claimCount;
      }
      return left.label.localeCompare(right.label);
    });
}

function mapSectionNavigatorItemsFromApi(items: PaperNoteSectionNavigatorApiItem[]): SectionNavigatorItem[] {
  return items.map((item) => ({
    key: item.key,
    label: item.label,
    outlineId: item.outline_id ?? null,
    outlineOrder: item.outline_order ?? null,
    claimCount: item.claim_count,
    evidenceCount: item.evidence_count,
    representativeClaimId: item.representative_claim_id ?? null,
    representativeEvidenceId: item.representative_evidence_id ?? null,
    pageStart: item.page_start ?? null,
    pageEnd: item.page_end ?? null,
    matchedToOutline: item.matched_to_outline,
  }));
}

function formatSectionPageRange(pageStart?: number | null, pageEnd?: number | null): string | null {
  if (typeof pageStart !== "number") {
    return null;
  }
  if (typeof pageEnd === "number" && pageEnd > pageStart) {
    return `pages ${pageStart + 1}-${pageEnd + 1}`;
  }
  return `page ${pageStart + 1}`;
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

function formatReadingAssistBadgeLabel(label: string, value: string): string {
  return `${label} ${value.trim()}`;
}

function buildReadingAssistBlockMetaBadges(
  readingAssist: NonNullable<PaperNoteDetailResponse["reading_assist"]>,
  block: NonNullable<PaperNoteDetailResponse["reading_assist"]>["blocks"][number],
): string[] {
  const badges: string[] = [];
  const sourceLocale = block.source_locale?.trim() || readingAssist.canonical_locale?.trim();
  if (sourceLocale) {
    badges.push(formatReadingAssistBadgeLabel("Source", formatReadingAssistLocaleLabel(sourceLocale)));
  }
  if (block.translator?.trim()) {
    badges.push(formatReadingAssistBadgeLabel("Translator", block.translator));
  }
  if (block.model?.trim()) {
    badges.push(formatReadingAssistBadgeLabel("Model", block.model));
  }
  if (block.version?.trim()) {
    badges.push(formatReadingAssistBadgeLabel("Version", block.version));
  }
  return badges;
}

function resolveReadingAssistLocales(
  note: PaperNoteSummary | null,
  signals: Record<string, unknown>,
  readingAssist?: PaperNoteDetailResponse["reading_assist"] | null,
): string[] {
  const explicitLocales = (note?.reading_assist_locales ?? [])
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  if (explicitLocales.length > 0) {
    return Array.from(new Set(explicitLocales));
  }
  const rawLocales = signals.reading_assist_locales;
  const locales = Array.isArray(rawLocales)
    ? rawLocales
        .map((value) => (typeof value === "string" ? value.trim().toLowerCase() : ""))
        .filter(Boolean)
    : [];
  if (locales.length > 0) {
    return Array.from(new Set(locales));
  }
  const fallbackLocale = typeof readingAssist?.locale === "string" ? readingAssist.locale.trim().toLowerCase() : "";
  return fallbackLocale ? [fallbackLocale] : [];
}

function ReadingAssistPanel({
  readingAssist,
  availableLocales,
  requestedLocale,
  onSelectLocale,
}: {
  readingAssist: PaperNoteDetailResponse["reading_assist"] | null | undefined;
  availableLocales: string[];
  requestedLocale?: string | null;
  onSelectLocale?: (locale: string | null) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  if (!readingAssist || readingAssist.blocks.length === 0) {
    return null;
  }

  const localeLabel = formatReadingAssistLocaleLabel(readingAssist.locale);
  const canonicalLocaleLabel = formatReadingAssistLocaleLabel(readingAssist.canonical_locale);
  const localeOptions = Array.from(new Set(availableLocales.map((locale) => locale.trim().toLowerCase()).filter(Boolean)));

  return (
    <div
      className="mt-4 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
      data-testid="paper-note-reading-assist"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Languages className="h-4 w-4 text-[var(--pp-accent-text)]" />
            <p className="text-sm font-semibold text-[var(--pp-text-primary)]">
              {localeLabel} reading assist
            </p>
          </div>
          <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
            Display-only support for key summary blocks. Canonical note content stays in English/original.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{localeLabel}</Badge>
          <Badge variant="outline">Canonical {canonicalLocaleLabel}</Badge>
          {readingAssist.machine_translated ? <Badge variant="muted">Machine translated</Badge> : null}
          {readingAssist.partial ? <Badge variant="outline">Partial</Badge> : null}
          {localeOptions.length > 1 ? (
            <div className="grid gap-1" data-testid="paper-note-reading-assist-locale-switcher">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                Assist view
              </p>
              <div className="flex flex-wrap items-center gap-1.5">
                <Button
                  type="button"
                  variant={requestedLocale ? "outline" : "default"}
                  size="sm"
                  onClick={() => onSelectLocale?.(null)}
                  data-testid="paper-note-reading-assist-locale-auto"
                >
                  Auto
                </Button>
                {localeOptions.map((locale) => (
                  <Button
                    key={`reading-assist-locale-${locale}`}
                    type="button"
                    variant={requestedLocale === locale ? "default" : "outline"}
                    size="sm"
                    onClick={() => onSelectLocale?.(locale)}
                    data-testid={`paper-note-reading-assist-locale-${locale}`}
                  >
                    {formatReadingAssistLocaleLabel(locale)}
                  </Button>
                ))}
              </div>
              <p className="text-xs text-[var(--pp-text-dim)]">
                {requestedLocale
                  ? "Auto returns to the saved default locale for this note."
                  : "Auto keeps the saved default locale for this note."}
              </p>
            </div>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setExpanded((current) => !current)}
            data-testid="paper-note-reading-assist-toggle"
          >
            {expanded ? `Hide ${localeLabel} reading assist` : `Show ${localeLabel} reading assist`}
          </Button>
        </div>
      </div>
      {expanded ? (
        <div className="mt-3 grid gap-3" data-testid="paper-note-reading-assist-body">
          <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3">
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="outline">Machine translated from English</Badge>
              <Badge variant="outline">English/original text remains canonical</Badge>
              <Badge variant="outline">Translation may be partial</Badge>
            </div>
          </div>
          {readingAssist.blocks.map((block) => (
            <div
              key={`${readingAssist.locale}-${block.kind}`}
              className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-[var(--pp-text-primary)]">{block.label}</p>
                  <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                    Source field {block.source_field}
                    {block.source_heading ? ` · ${block.source_heading}` : ""}
                  </p>
                  {buildReadingAssistBlockMetaBadges(readingAssist, block).length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {buildReadingAssistBlockMetaBadges(readingAssist, block).map((badge) => (
                        <Badge key={`${readingAssist.locale}-${block.kind}-${badge}`} variant="outline">
                          {badge}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Canonical</p>
                  <div className="mt-2 whitespace-pre-line text-sm text-[var(--pp-text-primary)]">
                    {block.canonical_text?.trim() || "Canonical excerpt unavailable in this note body."}
                  </div>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">{localeLabel} assist</p>
                  <div className="mt-2 whitespace-pre-line text-sm text-[var(--pp-text-primary)]">{block.translated_text}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PropertiesPanel({
  note,
  aliases,
  tags,
  structuredState,
  readingAssist,
  requestedReadingAssistLocale,
}: {
  note: PaperNoteSummary | null;
  aliases: string[];
  tags: string[];
  structuredState?: StructuredPaperState | null;
  readingAssist?: PaperNoteDetailResponse["reading_assist"] | null;
  requestedReadingAssistLocale?: string | null;
}) {
  const signals = (note?.pp_signals ?? {}) as Record<string, unknown>;
  const citationCount = typeof signals.citation_count === "number" ? signals.citation_count : null;
  const hasClaimset = signals.has_claimset === true;
  const lastAppraisal = typeof signals.last_appraisal === "string" ? signals.last_appraisal : null;
  const readingAssistLocales = resolveReadingAssistLocales(note, signals, readingAssist);
  const opsSummary = note?.ops_summary ?? null;
  const sectionNavigationSignal = buildSectionNavigationSignalSummary(structuredState ?? null);

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
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">saved checks</dt>
              <dd className="mt-1">
                <OperationalStateSummary
                  summary={opsSummary}
                  badgeTestId="paper-note-ops-badge"
                  reasonTestId="paper-note-ops-reason"
                />
              </dd>
            </div>
          ) : null}
          {sectionNavigationSignal ? (
            <div data-testid="paper-note-section-navigation-signal">
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">section navigator</dt>
              <dd className="mt-1 space-y-2">
                <Badge className={sectionNavigationSignal.className}>{sectionNavigationSignal.label}</Badge>
                <p className="text-xs text-[var(--pp-text-dim)]" data-testid="paper-note-section-navigation-signal-detail">
                  {sectionNavigationSignal.detail}
                </p>
              </dd>
            </div>
          ) : null}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">citations</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{citationCount ?? "-"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">saved claims</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{hasClaimset ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">appraisal</dt>
              <dd className="mt-1 text-[var(--pp-text-primary)]">{lastAppraisal ?? "-"}</dd>
            </div>
          </div>
          {readingAssistLocales.length > 0 ? (
            <div data-testid="paper-note-reading-assist-availability">
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">reading assist</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {readingAssistLocales.map((locale) => (
                  <Badge key={`reading-assist-${locale}`} variant="outline">
                    {formatReadingAssistLocaleLabel(locale)} available
                  </Badge>
                ))}
              </dd>
            </div>
          ) : null}
          {readingAssist ? (
            <div data-testid="paper-note-reading-assist-current-view">
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">assist view</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                <Badge variant="outline">{formatReadingAssistLocaleLabel(readingAssist.locale)} viewing</Badge>
                <Badge variant="outline">{requestedReadingAssistLocale ? "Manual selection" : "Auto default"}</Badge>
              </dd>
            </div>
          ) : null}
        </dl>
      </CardContent>
    </Card>
  );
}

function getAppraisalStatusBadge(status: AppraisalCheckStatus): { label: string; className: string } {
  if (status === "pass") {
    return {
      label: "Pass",
      className:
        "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
    };
  }
  if (status === "fail") {
    return {
      label: "Fail",
      className:
        "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    };
  }
  if (status === "warn") {
    return {
      label: "Warn",
      className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
    };
  }
  return {
    label: "Not run",
    className: "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]",
  };
}

function getAppraisalConcernBadge(severity: AppraisalConcernSeverity): { label: string; className: string } {
  if (severity === "fail") {
    return {
      label: "Concern",
      className:
        "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
    };
  }
  if (severity === "warn") {
    return {
      label: "Follow-up",
      className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
    };
  }
  return {
    label: "Info",
    className: "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]",
  };
}

function AppraisalPanel({
  report,
  run,
}: {
  report: CriticalAppraisalReport;
  run: SkillRunRecord;
}) {
  return (
    <Card className="overflow-hidden" data-testid="paper-note-appraisal-panel">
      <CardHeader>
        <CardTitle>Appraisal</CardTitle>
        <CardDescription>Optional reviewer lane grounded in saved claims, evidence, and additive review sidecars.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="grid gap-4 pt-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{report.label}</Badge>
          <Badge variant="outline">non-canonical</Badge>
          <Badge variant="muted">claims {report.claim_count}</Badge>
          <Badge variant="muted">evidence {report.evidence_count}</Badge>
          <Badge variant="muted">verified {report.verified_checks}</Badge>
          {report.inconsistent_checks > 0 ? (
            <Badge className="border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]">
              inconsistent {report.inconsistent_checks}
            </Badge>
          ) : null}
          <Badge variant="outline">updated {formatDateTime(run.ts)}</Badge>
        </div>

        <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
          <p className="text-sm text-[var(--pp-text-primary)]" data-testid="paper-note-appraisal-summary">
            {report.summary}
          </p>
          <p className="mt-2 text-xs text-[var(--pp-text-dim)]">
            This panel never replaces canonical claim state. It only summarizes downstream review concerns that stay tied to saved evidence.
          </p>
        </div>

        {report.source_artifacts.length > 0 ? (
          <div data-testid="paper-note-appraisal-sources">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Source artifacts</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {report.source_artifacts.map((artifact) => (
                <Badge key={`appraisal-source-${artifact}`} variant="outline">
                  {artifact}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        <section data-testid="paper-note-appraisal-checks">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Checks</p>
          <div className="mt-2 grid gap-2">
            {report.checks.map((check) => {
              const badge = getAppraisalStatusBadge(check.status);
              return (
                <div
                  key={`appraisal-check-${check.code}`}
                  className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-sm font-medium text-[var(--pp-text-primary)]">{check.label}</p>
                    <Badge className={badge.className}>{badge.label}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{check.detail}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section data-testid="paper-note-appraisal-concerns">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Evidence-bounded concerns</p>
          {report.concerns.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--pp-text-dim)]">No evidence-bounded concerns were recorded for this appraisal.</p>
          ) : (
            <div className="mt-2 grid gap-2">
              {report.concerns.map((concern) => {
                const badge = getAppraisalConcernBadge(concern.severity);
                return (
                  <div
                    key={`appraisal-concern-${concern.code}`}
                    className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="text-sm font-medium text-[var(--pp-text-primary)]">{concern.title}</p>
                      <Badge className={badge.className}>{badge.label}</Badge>
                    </div>
                    <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{concern.detail}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-[var(--pp-text-dim)]">
                      {concern.claim_ids.length > 0 ? <Badge variant="outline">claims {concern.claim_ids.length}</Badge> : null}
                      {concern.evidence_ids.length > 0 ? <Badge variant="outline">evidence {concern.evidence_ids.length}</Badge> : null}
                      {concern.source_artifacts.map((artifact) => (
                        <Badge key={`appraisal-concern-${concern.code}-${artifact}`} variant="muted">
                          {artifact}
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section data-testid="paper-note-appraisal-questions">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Author-facing questions</p>
          {report.questions.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--pp-text-dim)]">No follow-up questions were generated from this appraisal.</p>
          ) : (
            <div className="mt-2 grid gap-2">
              {report.questions.map((question) => (
                <div
                  key={`appraisal-question-${question.code}`}
                  className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3"
                >
                  <p className="text-sm font-medium text-[var(--pp-text-primary)]">{question.question}</p>
                  <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{question.rationale}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-[var(--pp-text-dim)]">
                    {question.claim_ids.length > 0 ? <Badge variant="outline">claims {question.claim_ids.length}</Badge> : null}
                    {question.evidence_ids.length > 0 ? <Badge variant="outline">evidence {question.evidence_ids.length}</Badge> : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {report.warnings.length > 0 ? (
          <div data-testid="paper-note-appraisal-warnings">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Warnings</p>
            <ul className="mt-2 space-y-2 text-xs text-[var(--pp-text-dim)]">
              {report.warnings.map((warning) => (
                <li key={`appraisal-warning-${warning}`}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ReviewSnapshotPanel({
  note,
  state,
  workbenchPaperId,
}: {
  note: PaperNoteSummary | null;
  state: StructuredPaperState | null;
  workbenchPaperId: string | null;
}) {
  const stateLoaded = Boolean(state);
  const counts = deriveReviewSnapshotCounts(state);
  const summary = buildReviewSnapshotSummary(stateLoaded, counts);
  const nextStep = buildReviewSnapshotNextStep(note, stateLoaded, counts, Boolean(workbenchPaperId));

  return (
    <div
      className="mt-4 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
      data-testid="paper-note-review-snapshot"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[var(--pp-accent-text)]" />
            <p className="text-sm font-semibold text-[var(--pp-text-primary)]">Review snapshot</p>
          </div>
          <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
            Surface saved state, evidence grounding, and the next best research action before deeper inspection.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant={stateLoaded ? "muted" : "outline"}>{stateLoaded ? "Saved state loaded" : "Saved state missing"}</Badge>
          {state?.updated_at ? <Badge variant="outline">updated {formatDateTime(state.updated_at)}</Badge> : null}
          {counts.claimCount > 0 ? <Badge variant="outline">claims {counts.claimCount}</Badge> : null}
          {counts.evidenceCount > 0 ? <Badge variant="outline">evidence {counts.evidenceCount}</Badge> : null}
          {counts.groundedCount > 0 ? (
            <Badge className="border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]">
              grounded {counts.groundedCount}
            </Badge>
          ) : null}
          {counts.needsReviewCount > 0 ? (
            <Badge className="border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]">
              needs review {counts.needsReviewCount}
            </Badge>
          ) : null}
          {counts.unresolvedCount > 0 ? (
            <Badge className="border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]">
              unresolved {counts.unresolvedCount}
            </Badge>
          ) : null}
        </div>
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className="grid gap-2">
          <p className="text-sm text-[var(--pp-text-primary)]" data-testid="paper-note-review-summary">
            {summary}
          </p>
          {nextStep ? (
            <p className="text-xs text-[var(--pp-text-dim)]" data-testid="paper-note-review-next-step">
              {nextStep}
            </p>
          ) : null}
        </div>
        <OperationalStateSummary
          summary={note?.ops_summary}
          badgeTestId="paper-note-review-ops-badge"
          reasonTestId="paper-note-review-ops-reason"
          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
        />
      </div>
    </div>
  );
}

function ReviewBridgePanel({
  note,
  state,
  workbenchPaperId,
  protocolCardStartHref,
}: {
  note: PaperNoteSummary | null;
  state: StructuredPaperState | null;
  workbenchPaperId: string | null;
  protocolCardStartHref: string | null;
}) {
  const stateLoaded = Boolean(state);
  const counts = deriveReviewSnapshotCounts(state);
  const summary = buildReviewSnapshotSummary(stateLoaded, counts);
  const nextStep = buildReviewSnapshotNextStep(note, stateLoaded, counts, Boolean(workbenchPaperId));
  const focus = deriveReviewBridgeFocus(state);
  const bridgeStatus = buildReviewBridgeStatusCopy(stateLoaded, counts);

  return (
    <div
      className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
      data-testid="paper-note-review-bridge"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[var(--pp-accent-text)]" />
            <p className="text-sm font-semibold text-[var(--pp-text-primary)]">Review focus</p>
          </div>
          <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
            Keep saved evidence state, flagged review, and the next handoff close while you read.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant={stateLoaded ? "muted" : "outline"}>{stateLoaded ? "Saved state loaded" : "Saved state missing"}</Badge>
          {counts.claimCount > 0 ? <Badge variant="outline">claims {counts.claimCount}</Badge> : null}
          {counts.needsReviewCount > 0 ? (
            <Badge className="border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]">
              needs review {counts.needsReviewCount}
            </Badge>
          ) : null}
          {counts.unresolvedCount > 0 ? (
            <Badge className="border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]">
              unresolved {counts.unresolvedCount}
            </Badge>
          ) : null}
          {counts.needsReviewCount === 0 && counts.unresolvedCount === 0 && counts.groundedCount > 0 ? (
            <Badge className="border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]">
              grounded {counts.groundedCount}
            </Badge>
          ) : null}
        </div>
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className="grid gap-3">
          <div className={`rounded-md border px-3 py-2 ${bridgeStatus.className}`} data-testid="paper-note-review-bridge-status">
            <p className="text-xs font-semibold uppercase tracking-wide">Trust state</p>
            <p className="mt-1 text-sm font-medium">{bridgeStatus.title}</p>
            <p className="mt-1 text-xs opacity-90">{bridgeStatus.detail}</p>
          </div>
          <p className="text-sm text-[var(--pp-text-primary)]">{summary}</p>
          {focus ? (
            <div
              className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
              data-testid="paper-note-review-focus"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">{focus.emphasisLabel}</p>
                {focus.groundingBadge ? <Badge className={focus.groundingBadge.className}>{focus.groundingBadge.label}</Badge> : null}
              </div>
              <div className="mt-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2 text-[11px] text-[var(--pp-text-secondary)]">
                <p className="font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Primary source anchor</p>
                <p className="mt-1" data-testid="paper-note-review-focus-location">
                  {focus.location ? `Source anchor: ${focus.location}` : "Source anchor lives in saved structured state."}
                </p>
                <p className="mt-1 text-[var(--pp-text-dim)]" data-testid="paper-note-review-focus-hint">
                  {focus.reviewHint}
                </p>
              </div>
              <p className="mt-2 text-sm font-medium text-[var(--pp-text-primary)]" data-testid="paper-note-review-focus-claim">
                {truncateText(focus.claimText, 180)}
              </p>
              {focus.evidenceText ? (
                <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{truncateText(focus.evidenceText, 240)}</p>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[var(--pp-text-dim)]">
                <Badge variant="outline">{focus.kind === "evidence" ? "Saved evidence anchor" : "Saved claim anchor"}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[var(--pp-text-dim)]">
                <Link to={buildFocusHref(focus.kind, focus.focusId)} className="paper-note-link text-xs font-medium">
                  {focus.kind === "evidence" ? "Open saved evidence" : "Open saved claim"}
                </Link>
              </div>
            </div>
          ) : null}
        </div>
        <div className="grid gap-3">
          <OperationalStateSummary
            summary={note?.ops_summary}
            badgeTestId="paper-note-review-bridge-ops-badge"
            reasonTestId="paper-note-review-bridge-ops-reason"
            compact
            className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
            showActionHint={false}
          />
          {nextStep ? <p className="text-xs text-[var(--pp-text-dim)]">{nextStep}</p> : null}
          <div className="flex flex-wrap gap-2">
            {workbenchPaperId ? (
              <Link
                to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                className={buttonClassName({ size: "sm" })}
                onClick={() =>
                  logClientUserAction({
                    paper_id: workbenchPaperId,
                    action_type: "open_workbench",
                    source: "paper_note_review_bridge",
                    payload: {
                      note_slug: note?.slug ?? null,
                    },
                  })
                }
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Open review
              </Link>
            ) : null}
            {protocolCardStartHref ? (
              <Link to={protocolCardStartHref} className={buttonClassName({ variant: "outline", size: "sm" })}>
                Save protocol card
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function SavedStatePanel({
  note,
  state,
  contextTrace,
}: {
  note: PaperNoteSummary | null;
  state: StructuredPaperState | null;
  contextTrace?: PaperNoteContextTrace | null;
}) {
  const structuredStateEntry = contextTrace?.trace.find((entry) => entry.action === "structured_state_loaded") ?? null;
  const structuredStatePath = structuredStateEntry?.source_path ?? (note ? `.pp/${note.slug}/state.json` : null);
  const structuredStateLoaded = structuredStateEntry ? structuredStateEntry.outcome === "loaded" : Boolean(state);
  const summary = contextTrace?.summary ?? null;

  return (
    <Card className="overflow-hidden" data-testid="paper-note-saved-state-panel">
      <CardHeader>
        <CardTitle>Saved note state</CardTitle>
        <CardDescription>Shows whether saved note state backed this detail view.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="grid gap-3 pt-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge
            className={
              structuredStateLoaded
                ? "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                : "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]"
            }
            data-testid="paper-note-saved-state-status"
          >
            {structuredStateLoaded ? "Loaded" : "Missing"}
          </Badge>
          {summary ? <Badge variant="outline">trace {summary.entry_count}</Badge> : null}
          {state?.updated_at ? <Badge variant="outline">updated {formatDateTime(state.updated_at)}</Badge> : null}
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">Expected state path</p>
          <p className="mt-1 break-all text-sm text-[var(--pp-text-primary)]">{structuredStatePath ?? "-"}</p>
        </div>
        {structuredStateLoaded ? (
          <p className="text-sm text-[var(--pp-text-secondary)]">
            Saved note state is available for this note detail view.
          </p>
        ) : (
          <p className="text-sm text-[var(--pp-status-failed-text)]">
            No saved note state was loaded for this note. Related papers and references may still render from note and
            index metadata.
          </p>
        )}
        {summary ? (
          <>
            <div className="flex flex-wrap gap-1.5" data-testid="paper-note-context-trace-summary">
              <Badge variant="outline">source paths {summary.source_path_count}</Badge>
              <Badge variant="outline">related {summary.related_count}</Badge>
              <Badge variant="outline">references {summary.reference_count}</Badge>
            </div>
            <details className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
              <summary className="cursor-pointer text-sm font-medium text-[var(--pp-text-primary)]">Trace summary</summary>
              {structuredStateEntry ? (
                <p className="mt-2 text-xs text-[var(--pp-text-secondary)]">{structuredStateEntry.detail}</p>
              ) : null}
              {summary.source_paths.length > 0 ? (
                <ul className="mt-2 space-y-1 text-xs text-[var(--pp-text-dim)]">
                  {summary.source_paths.slice(0, 4).map((path) => (
                    <li key={path} className="break-all">
                      {path}
                    </li>
                  ))}
                </ul>
              ) : null}
            </details>
          </>
        ) : null}
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

function SectionNavigatorPanel({
  sections,
  stateLoaded,
  onNavigate,
}: {
  sections: SectionNavigatorItem[];
  stateLoaded: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Card className="overflow-hidden" data-testid="paper-note-section-navigator">
      <CardHeader>
        <CardTitle>Section navigator</CardTitle>
        <CardDescription>Pilot section map from saved evidence sections plus note headings.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {!stateLoaded ? (
          <p className="text-sm text-[var(--pp-text-dim)]">Saved note state is required before section-linked navigation can appear.</p>
        ) : sections.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">No saved section-linked evidence was found for this note yet.</p>
        ) : (
          <ul className="space-y-3">
            {sections.map((item) => {
              const pageRange = formatSectionPageRange(item.pageStart, item.pageEnd);
              return (
                <li key={item.key} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-[var(--pp-text-primary)]">{item.label}</p>
                      <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                        {item.matchedToOutline ? "Matched to a note heading." : "Saved evidence section only."}
                      </p>
                    </div>
                    <div className="flex flex-wrap justify-end gap-1.5">
                      <Badge variant="outline">claims {item.claimCount}</Badge>
                      <Badge variant="outline">evidence {item.evidenceCount}</Badge>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge variant={item.matchedToOutline ? "muted" : "outline"}>
                      {item.matchedToOutline ? "note heading matched" : "state-only section"}
                    </Badge>
                    {pageRange ? <Badge variant="muted">{pageRange}</Badge> : null}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.outlineId ? (
                      <a href={`#${item.outlineId}`} onClick={onNavigate} className={buttonClassName({ variant: "outline", size: "sm" })}>
                        Open note section
                      </a>
                    ) : null}
                    {item.representativeEvidenceId ? (
                      <Link
                        to={buildFocusHref("evidence", item.representativeEvidenceId)}
                        onClick={onNavigate}
                        className={buttonClassName({ variant: "outline", size: "sm" })}
                      >
                        Open saved evidence
                      </Link>
                    ) : item.representativeClaimId ? (
                      <Link
                        to={buildFocusHref("claim", item.representativeClaimId)}
                        onClick={onNavigate}
                        className={buttonClassName({ variant: "outline", size: "sm" })}
                      >
                        Open saved claim
                      </Link>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
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
              {references.map((reference, idx) => {
                const safeHref = sanitizeRenderableHref(reference.url);
                return (
                  <li key={`reference-${idx}`} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3">
                    <div className="flex items-start justify-between gap-3">
                      {safeHref ? (
                        <a
                          href={safeHref}
                          target="_blank"
                          rel="noreferrer"
                          className="paper-note-link inline-flex min-w-0 items-center gap-1 text-sm font-medium"
                        >
                          <span className="truncate">{reference.label}</span>
                          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                        </a>
                      ) : (
                        <span className="inline-flex min-w-0 items-center gap-1 text-sm font-medium text-[var(--pp-text)]">
                          <span className="truncate">{reference.label}</span>
                        </span>
                      )}
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
                );
              })}
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
  structuredStatePath,
}: {
  state: StructuredPaperState | null;
  focusTarget: FocusTarget | null;
  structuredStatePath?: string | null;
}) {
  const runs = state?.runs ?? [];
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Run history</CardTitle>
        <CardDescription>Saved runs recorded in the note state.</CardDescription>
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
        {!state ? (
          <div className="space-y-2">
            <p className="text-sm text-[var(--pp-status-failed-text)]">No saved note state was loaded for this note.</p>
            {structuredStatePath ? <p className="break-all text-xs text-[var(--pp-text-dim)]">{structuredStatePath}</p> : null}
            <p className="text-xs text-[var(--pp-text-dim)]">Run history only appears after saved note state is available.</p>
          </div>
        ) : runs.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">Saved note state loaded, but no saved runs are recorded yet.</p>
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
  state,
  focusTarget,
  structuredStatePath,
}: {
  state: StructuredPaperState | null;
  focusTarget: FocusTarget | null;
  structuredStatePath?: string | null;
}) {
  const claims = state?.claimset ?? [];
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Saved claims</CardTitle>
        <CardDescription>Claim cards loaded from saved note state for review and retrieval.</CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {!state ? (
          <div className="space-y-2">
            <p className="text-sm text-[var(--pp-status-failed-text)]">No saved note state was loaded for this note.</p>
            {structuredStatePath ? <p className="break-all text-xs text-[var(--pp-text-dim)]">{structuredStatePath}</p> : null}
            <p className="text-xs text-[var(--pp-text-dim)]">Saved claims only appear after saved note state is available.</p>
          </div>
        ) : claims.length === 0 ? (
          <p className="text-sm text-[var(--pp-text-dim)]">Saved note state loaded, but no saved claims are recorded yet.</p>
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

function OperatorStatePanel({
  operatorState,
  dirty,
  saving,
  saveMessage,
  saveError,
  onToggleStar,
  onToggleTriage,
  onNoteChange,
  onReset,
  onSave,
}: {
  operatorState: PaperNoteOperatorState | null;
  dirty: boolean;
  saving: boolean;
  saveMessage: string | null;
  saveError: string | null;
  onToggleStar: () => void;
  onToggleTriage: (label: PaperNoteOperatorTriageLabel) => void;
  onNoteChange: (value: string) => void;
  onReset: () => void;
  onSave: () => void;
}) {
  if (!operatorState) {
    return null;
  }

  const noteText = String(operatorState.paper_note_text ?? "");
  const noteLength = noteText.length;
  const remainingCharacters = Math.max(0, MAX_PAPER_OPERATOR_NOTE_LENGTH - noteLength);

  return (
    <Card className="overflow-hidden" data-testid="paper-note-operator-panel">
      <CardHeader>
        <CardTitle>My note</CardTitle>
        <CardDescription>
          Keep paper-level judgment separate from canonical saved claims and evidence-linked review state.
        </CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={operatorState.starred ? "default" : "outline"}
              onClick={onToggleStar}
              data-testid="paper-note-operator-star-toggle"
            >
              <Star className="h-3.5 w-3.5" />
              {operatorState.starred ? "Starred" : "Star this paper"}
            </Button>
            {PAPER_NOTE_OPERATOR_TRIAGE_LABELS.map((label) => (
              <Button
                key={`operator-triage-${label}`}
                size="sm"
                variant={operatorState.triage_labels.includes(label) ? "default" : "outline"}
                onClick={() => onToggleTriage(label)}
                data-testid={`paper-note-operator-triage-${label}`}
              >
                {formatPaperNoteTriageLabel(label)}
              </Button>
            ))}
          </div>

          <div className="flex flex-wrap gap-1.5">
            <OperatorStateBadges operatorState={operatorState} />
            {operatorState.updated_at ? <Badge variant="outline">updated {formatDateTime(operatorState.updated_at)}</Badge> : null}
          </div>

          <label className="grid gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Paper-level note</span>
            <textarea
              value={noteText}
              onChange={(event) => onNoteChange(event.target.value)}
              placeholder="Capture why this paper matters, what to revisit, or why it should not be trusted yet."
              maxLength={MAX_PAPER_OPERATOR_NOTE_LENGTH}
              rows={6}
              className="min-h-[8.5rem] rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)] outline-none placeholder:text-[var(--pp-text-dim)]"
              data-testid="paper-note-operator-textarea"
            />
          </label>

          <div className="flex items-center justify-between gap-3 text-xs text-[var(--pp-text-dim)]">
            <p>Paper-level only. Keep claim or passage-grounded review in Workbench.</p>
            <p>{remainingCharacters} chars left</p>
          </div>

          {saveError ? (
            <p className="text-xs text-[var(--pp-status-failed-text)]" data-testid="paper-note-operator-save-error">
              {saveError}
            </p>
          ) : null}
          {saveMessage ? (
            <p className="text-xs text-[var(--pp-text-secondary)]" data-testid="paper-note-operator-save-message">
              {saveMessage}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={onSave}
              disabled={saving || !dirty}
              data-testid="paper-note-operator-save"
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? "Saving..." : "Save note"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onReset}
              disabled={saving || !dirty}
              data-testid="paper-note-operator-reset"
            >
              Reset
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function PaperNoteDetailPage() {
  const params = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const slug = params.slug ?? "";
  const requestedReadingAssistLocale = (searchParams.get("reading_assist_locale") ?? "").trim().toLowerCase() || null;

  const [data, setData] = useState<PaperNoteDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mockReason, setMockReason] = useState<string | null>(null);
  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const [operatorDraft, setOperatorDraft] = useState<PaperNoteOperatorState | null>(null);
  const [savingOperatorState, setSavingOperatorState] = useState(false);
  const [operatorSaveMessage, setOperatorSaveMessage] = useState<string | null>(null);
  const [operatorSaveError, setOperatorSaveError] = useState<string | null>(null);
  const [runningAction, setRunningAction] = useState<SkillActionInfo["action"] | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [signalDiffs, setSignalDiffs] = useState<SignalDiff[]>([]);
  const [appendMarkdownSummary, setAppendMarkdownSummary] = useState(true);
  const [loadedDetailSlug, setLoadedDetailSlug] = useState("");
  const [creatingProtocolAttachmentDraft, setCreatingProtocolAttachmentDraft] = useState(false);
  const [protocolAttachmentError, setProtocolAttachmentError] = useState<string | null>(null);
  const [copiedImportPaperId, setCopiedImportPaperId] = useState(false);
  const [queueingImportDeepRead, setQueueingImportDeepRead] = useState(false);
  const [importDeepReadMessage, setImportDeepReadMessage] = useState<string | null>(null);
  const [importDeepReadError, setImportDeepReadError] = useState<string | null>(null);
  const [importDeepReadJob, setImportDeepReadJob] = useState<ImportDeepReadJobStatus | null>(null);
  const actionRunLockRef = useRef(false);
  const protocolAttachmentInputRef = useRef<HTMLInputElement | null>(null);
  const detailRequestIdRef = useRef(0);
  const mountedRef = useRef(true);

  const loadDetail = useCallback(async (targetSlug: string, readingAssistLocale?: string | null) => {
    const requestId = detailRequestIdRef.current + 1;
    detailRequestIdRef.current = requestId;
    if (!targetSlug) {
      setLoadError("Missing note slug.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const result = await getPaperNoteDetail(targetSlug, { readingAssistLocale });
      if (!mountedRef.current || detailRequestIdRef.current !== requestId) {
        return;
      }
      setLoadedDetailSlug(targetSlug);
      setCopiedImportPaperId(false);
      setImportDeepReadMessage(null);
      setImportDeepReadError(null);
      setImportDeepReadJob(null);
      setMockReason(result.isMock && result.reason ? result.reason : null);
      setData(result.data);
      setOperatorDraft(result.data.operator_state);
      setOperatorSaveMessage(null);
      setOperatorSaveError(null);
    } catch (error) {
      if (!mountedRef.current || detailRequestIdRef.current !== requestId) {
        return;
      }
      setLoadedDetailSlug(targetSlug);
      setMockReason(null);
      setData(null);
      setOperatorDraft(null);
      setOperatorSaveMessage(null);
      setOperatorSaveError(null);
      setLoadError(getApiErrorMessage(error));
    } finally {
      if (mountedRef.current && detailRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void loadDetail(slug, requestedReadingAssistLocale);
  }, [loadDetail, requestedReadingAssistLocale, slug]);

  useEffect(() => {
    const jobId = importDeepReadJob?.jobId;
    const status = importDeepReadJob?.status;
    if (!jobId || status === "completed" || status === "failed" || status === "cancelled") {
      return;
    }
    const timer = window.setInterval(() => {
      void getJob(jobId)
        .then((result) => {
          if (result.isMock && result.reason) {
            setMockReason(result.reason);
          }
          setImportDeepReadJob((prev) =>
            prev?.jobId === jobId
              ? {
                  ...prev,
                  runId: result.data.run_id ?? prev.runId,
                  status: result.data.status,
                  progress: result.data.progress,
                  stage: result.data.stage,
                  errorMessage: result.data.error_message,
                }
              : prev,
          );
        })
        .catch((error) => {
          setImportDeepReadError(`Status refresh failed: ${getApiErrorMessage(error)}`);
        });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [importDeepReadJob?.jobId, importDeepReadJob?.status]);

  useEffect(() => {
    actionRunLockRef.current = false;
    setRunningAction(null);
    setActionMessage(null);
    setSignalDiffs([]);
    setAppendMarkdownSummary(true);
    setOperatorDraft(null);
    setSavingOperatorState(false);
    setOperatorSaveMessage(null);
    setOperatorSaveError(null);
    setCreatingProtocolAttachmentDraft(false);
    setProtocolAttachmentError(null);
  }, [slug]);

  const note = data?.note ?? null;
  const structuredState = data?.structured_state ?? null;
  const readingAssist = data?.reading_assist ?? null;
  const operatorState = operatorDraft ?? data?.operator_state ?? null;
  const contextTrace = data?.context_trace ?? null;
  const availableActions = data?.available_actions ?? [];
  const focusTarget = useMemo(() => parseFocusParam(searchParams.get("focus")), [searchParams]);
  const viewerMode = useMemo(() => parseViewerOutputMode(searchParams.get("view")), [searchParams]);
  const aliases = useMemo(() => note?.aliases ?? [], [note]);
  const tags = useMemo(() => note?.tags ?? [], [note]);
  const noteSignals = useMemo(() => ((note?.pp_signals ?? {}) as Record<string, unknown>), [note?.pp_signals]);
  const readingAssistLocales = useMemo(
    () => resolveReadingAssistLocales(note, noteSignals, readingAssist),
    [note, noteSignals, readingAssist],
  );
  const references = useMemo(() => data?.references ?? [], [data?.references]);
  const workbenchPaperId = useMemo(() => resolveWorkbenchPaperId(note), [note]);
  const importMode = typeof noteSignals.import_mode === "string" ? noteSignals.import_mode.trim() : "";
  const isManualPdfImport = importMode === "manual_pdf";
  const importedPdfReference = useMemo(() => references.find((reference) => reference.source === "pdf") ?? null, [references]);
  const protocolCardStartHref = useMemo(() => {
    const noteRouteSlug = slug.trim() || note?.slug?.trim() || "";
    if (!noteRouteSlug) {
      return null;
    }
    const next = new URLSearchParams();
    next.set("noteSlug", noteRouteSlug);
    if (workbenchPaperId) {
      next.set("paperId", workbenchPaperId);
    }
    return `/protocol-cards?${next.toString()}`;
  }, [slug, note?.slug, workbenchPaperId]);
  const protocolAttachmentHint = mockReason
    ? "Attachment-derived protocol drafts need the live backend. They stay disabled while this page is in fallback mode."
    : "Attach protocol text, images, or documents when this paper note needs external protocol context before save.";
  const outline = useMemo(() => extractOutline(data?.body_markdown ?? "", note?.title), [data?.body_markdown, note?.title]);
  const sectionNavigator = useMemo(() => {
    const apiItems = data?.section_navigator ?? [];
    if (apiItems.length > 0) {
      return mapSectionNavigatorItemsFromApi(apiItems);
    }
    return buildSectionNavigatorItems(structuredState, outline);
  }, [data?.section_navigator, outline, structuredState]);
  const operatorStateDirty = useMemo(() => {
    if (!operatorState || !data?.operator_state) {
      return false;
    }
    return !isSamePaperOperatorState(operatorState, data.operator_state);
  }, [data?.operator_state, operatorState]);
  const structuredStatePath = useMemo(() => {
    const structuredStateEntry = contextTrace?.trace.find((entry) => entry.action === "structured_state_loaded") ?? null;
    return structuredStateEntry?.source_path ?? (note ? `.pp/${note.slug}/state.json` : null);
  }, [contextTrace, note]);
  const latestCriticalAppraisalRun = useMemo(() => getLatestCriticalAppraisalRun(structuredState), [structuredState]);
  const criticalAppraisalReport = useMemo(
    () => parseCriticalAppraisalReport(latestCriticalAppraisalRun),
    [latestCriticalAppraisalRun],
  );

  useEffect(() => {
    const canonicalNoteSlug = note?.slug?.trim() ?? "";
    if (
      !slug ||
      loadedDetailSlug !== slug ||
      !canonicalNoteSlug ||
      canonicalNoteSlug === slug ||
      !isCanonicalNoteSlugCandidate(canonicalNoteSlug)
    ) {
      return;
    }
    navigate(
      {
        pathname: `/papers/${encodeURIComponent(canonicalNoteSlug)}`,
        search: searchParams.toString() ? `?${searchParams.toString()}` : "",
      },
      { replace: true },
    );
  }, [loadedDetailSlug, navigate, note?.slug, searchParams, slug]);

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

  function updateOperatorDraftState(
    updater: (current: PaperNoteOperatorState) => PaperNoteOperatorState,
  ) {
    setOperatorDraft((current) => {
      const base = current ?? data?.operator_state ?? null;
      if (!base) {
        return current;
      }
      return updater(base);
    });
    setOperatorSaveError(null);
    setOperatorSaveMessage(null);
  }

  function handleOperatorNoteChange(value: string) {
    updateOperatorDraftState((current) => ({
      ...current,
      paper_note_text: value,
    }));
  }

  function handleToggleOperatorStar() {
    updateOperatorDraftState((current) => ({
      ...current,
      starred: !current.starred,
    }));
  }

  function handleToggleOperatorTriage(label: PaperNoteOperatorTriageLabel) {
    updateOperatorDraftState((current) => ({
      ...current,
      triage_labels: toggleOperatorTriageLabel(current.triage_labels, label),
    }));
  }

  function handleResetOperatorState() {
    if (!data?.operator_state) {
      return;
    }
    setOperatorDraft(data.operator_state);
    setOperatorSaveError(null);
    setOperatorSaveMessage(null);
  }

  async function handleSaveOperatorState() {
    if (!slug || !operatorState || !operatorStateDirty) {
      return;
    }
    setSavingOperatorState(true);
    setOperatorSaveError(null);
    setOperatorSaveMessage(null);
    try {
      const result = await updatePaperNoteOperatorState(slug, buildOperatorStateUpdatePayload(operatorState));
      const nextState = result.data;
      setData((current) => (current ? applyOperatorStateToDetail(current, nextState) : current));
      setOperatorDraft(nextState);
      setOperatorSaveMessage(
        nextState.starred || hasPaperOperatorNoteText(nextState.paper_note_text) || nextState.triage_labels.length > 0
          ? "Saved to this paper."
          : "Paper-level markers cleared.",
      );
    } catch (error) {
      setOperatorSaveError(`Save failed: ${getApiErrorMessage(error)}`);
    } finally {
      setSavingOperatorState(false);
    }
  }

  function openProtocolAttachmentPicker() {
    if (!protocolCardStartHref || mockReason || creatingProtocolAttachmentDraft) {
      return;
    }
    protocolAttachmentInputRef.current?.click();
  }

  async function handleProtocolAttachmentSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file || !protocolCardStartHref) {
      return;
    }

    const noteSlug = slug.trim() || note?.slug?.trim() || "";
    if (!noteSlug) {
      setProtocolAttachmentError("Missing note slug for protocol attachment handoff.");
      return;
    }

    setCreatingProtocolAttachmentDraft(true);
    setProtocolAttachmentError(null);
    try {
      const result = await createProtocolDraftFromAttachment({
        file,
        noteSlug,
        paperId: workbenchPaperId ?? undefined,
      });
      navigate(protocolCardStartHref, {
        state: {
          attachmentDraft: result.data,
        } satisfies ProtocolCardAttachmentNavigationState,
      });
    } catch (error) {
      setProtocolAttachmentError(getApiErrorMessage(error));
    } finally {
      setCreatingProtocolAttachmentDraft(false);
    }
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

  function handleReadingAssistLocaleChange(locale: string | null) {
    const next = new URLSearchParams(searchParams);
    const normalizedLocale = locale?.trim().toLowerCase() ?? "";
    if (!normalizedLocale) {
      next.delete("reading_assist_locale");
      setSearchParams(next, { replace: true });
      return;
    }
    if (requestedReadingAssistLocale === normalizedLocale) {
      next.delete("reading_assist_locale");
    } else {
      next.set("reading_assist_locale", normalizedLocale);
    }
    setSearchParams(next, { replace: true });
  }

  async function copyImportPaperId() {
    if (!workbenchPaperId || typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      return;
    }
    try {
      await navigator.clipboard.writeText(workbenchPaperId);
      setCopiedImportPaperId(true);
      window.setTimeout(() => setCopiedImportPaperId(false), 1800);
    } catch {
      setCopiedImportPaperId(false);
    }
  }

  async function queueImportDeepRead() {
    if (!workbenchPaperId || queueingImportDeepRead) {
      return;
    }
    setQueueingImportDeepRead(true);
    setImportDeepReadMessage(null);
    setImportDeepReadError(null);
    setImportDeepReadJob(null);
    try {
      const result = await enqueueDeepRead({
        paper_id: workbenchPaperId,
        run_verify: false,
        clean_reindex: false,
      });
      const runText = result.data.run_id ? ` (${result.data.run_id})` : "";
      setImportDeepReadJob({
        jobId: result.data.job_id,
        runId: result.data.run_id,
        status: result.data.status,
        progress: 0,
        stage: "queued",
      });
      setImportDeepReadMessage(`Deep read queued${runText}. Open review to watch progress.`);
    } catch (error) {
      setImportDeepReadError(getApiErrorMessage(error));
    } finally {
      setQueueingImportDeepRead(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4 pb-24 md:pb-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Read</p>
            <h1 className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{note?.title ?? slug}</h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Read note context, related papers, and references before opening review.
            </p>
            {mockReason ? (
              <div data-testid="paper-note-runtime-guidance" className="mt-2 text-xs text-[var(--pp-text-dim)]">
                <p>Fallback mode: {mockReason}</p>
                <p className="mt-1">
                  If you expected live note data here,{" "}
                  <Link to="/ready" className="text-[var(--pp-accent-text)] underline underline-offset-2">
                    open Runtime checks
                  </Link>{" "}
                  before retrying this note.
                </p>
              </div>
            ) : null}
            {note?.id ? <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{note.id}</p> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={protocolAttachmentInputRef}
              type="file"
              accept={PROTOCOL_ATTACHMENT_ACCEPT}
              onChange={handleProtocolAttachmentSelection}
              className="hidden"
              data-testid="paper-note-protocol-attachment-input"
            />
            <Link to="/papers" className={buttonClassName({ variant: "ghost", size: "sm" })}>
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to list
            </Link>
            <Link to="/ready" className={buttonClassName({ variant: "outline", size: "sm" })}>
              Runtime checks
            </Link>
            {protocolCardStartHref ? (
              <Link to={protocolCardStartHref} className={buttonClassName({ variant: "outline", size: "sm" })}>
                Save protocol card
              </Link>
            ) : null}
            {protocolCardStartHref ? (
              <Button
                variant="outline"
                size="sm"
                onClick={openProtocolAttachmentPicker}
                disabled={Boolean(mockReason) || creatingProtocolAttachmentDraft}
                data-testid="paper-note-protocol-attachment-button"
              >
                <Upload className="h-3.5 w-3.5" />
                {creatingProtocolAttachmentDraft ? "Preparing protocol draft..." : "Attach protocol file"}
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              className="md:hidden"
              onClick={() => setSidePanelOpen(true)}
              data-testid="paper-note-open-side-panel"
            >
              <PanelRightOpen className="h-3.5 w-3.5" />
              Note panels
            </Button>
            {workbenchPaperId ? (
              <Link
                to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                className={buttonClassName({ size: "sm", className: "hidden md:inline-flex" })}
                onClick={() => logOpenWorkbench("paper_note_header")}
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Open review
              </Link>
            ) : null}
            {workbenchPaperId ? null : (
              <Link to="/" className={buttonClassName({ variant: "outline", size: "sm", className: "hidden md:inline-flex" })}>
                Review
              </Link>
            )}
          </div>
        </div>
        {protocolCardStartHref ? (
          <div className="mt-3 text-xs text-[var(--pp-text-dim)]" data-testid="paper-note-protocol-attachment-hint">
            {protocolAttachmentHint}
          </div>
        ) : null}
        {protocolAttachmentError ? (
          <p className="mt-2 text-xs text-[var(--pp-status-failed-text)]" data-testid="paper-note-protocol-attachment-error">
            Attachment draft failed: {protocolAttachmentError}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {note?.status ? <StatusBadge label={formatFreeformStatusLabel(note.status)} tone={getFreeformStatusTone(note.status)} /> : null}
          {typeof note?.confidence === "number" ? <Badge variant="outline">confidence {confidenceLabel(note.confidence)}</Badge> : null}
          <OperatorStateBadges operatorState={operatorState} />
          {tags.slice(0, 4).map((tag) => (
            <Badge key={`header-tag-${tag}`}>{tag}</Badge>
          ))}
        </div>
        {isManualPdfImport ? (
          <div
            className="mt-4 flex flex-col gap-3 rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] p-3 md:flex-row md:items-center md:justify-between"
            data-testid="paper-note-import-guidance"
          >
            <div className="max-w-2xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Imported note ready</p>
              <p className="text-sm font-medium text-[var(--pp-text-primary)]">This note is already saved in Lattice.</p>
              <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">
                This note came from a local PDF on this machine. Keep reading here, reopen the original PDF when you need
                the source file, or open review when you want extracted claims and saved checks.
              </p>
              {workbenchPaperId ? (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--pp-text-dim)]" data-testid="paper-note-import-guidance-paper-id">
                  <span>
                    Paper ID <span className="font-mono text-[var(--pp-text-secondary)]">{workbenchPaperId}</span>
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={copyImportPaperId}
                    data-testid="paper-note-import-guidance-copy-paper-id"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copiedImportPaperId ? "Copied" : "Copy ID"}
                  </Button>
                </div>
              ) : null}
            </div>
            <div className="flex flex-col gap-2 md:items-end">
              <div className="flex flex-wrap gap-2 md:justify-end">
                {workbenchPaperId ? (
                  <Link
                    to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                    className={buttonClassName({ size: "sm" })}
                    data-testid="paper-note-import-guidance-open-review"
                    onClick={() => logOpenWorkbench("paper_note_import_guidance")}
                  >
                    Open review
                  </Link>
                ) : null}
                {workbenchPaperId ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={queueImportDeepRead}
                    disabled={Boolean(mockReason) || queueingImportDeepRead}
                    data-testid="paper-note-import-guidance-queue-deepread"
                  >
                    {queueingImportDeepRead ? "Queueing..." : "Queue deep read"}
                  </Button>
                ) : null}
                {importedPdfReference ? (
                  <a
                    href={importedPdfReference.url}
                    target="_blank"
                    rel="noreferrer"
                    className={buttonClassName({ variant: "outline", size: "sm" })}
                    data-testid="paper-note-import-guidance-open-pdf"
                  >
                    Open saved PDF
                  </a>
                ) : null}
              </div>
              {importDeepReadMessage ? (
                <p className="text-xs text-[var(--pp-status-completed-text)]" data-testid="paper-note-import-guidance-deepread-message">
                  {importDeepReadMessage}
                </p>
              ) : null}
              {importDeepReadJob ? (
                <div
                  className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-left text-xs text-[var(--pp-text-secondary)]"
                  data-testid="paper-note-import-guidance-deepread-status"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={getStatusToneClassName(getPaperLifecycleTone(importDeepReadJob.status))}>
                      Status {jobLabel(importDeepReadJob.status)}
                    </Badge>
                    {importDeepReadJob.stage ? (
                      <span>
                        Stage <span className="font-mono text-[var(--pp-text-primary)]">{importDeepReadJob.stage}</span>
                      </span>
                    ) : null}
                    {typeof importDeepReadJob.progress === "number" ? <span>Progress {importDeepReadJob.progress}%</span> : null}
                    {importDeepReadJob.runId ? (
                      <span>
                        Run <span className="font-mono text-[var(--pp-text-primary)]">{importDeepReadJob.runId}</span>
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1">
                    Job <span className="font-mono text-[var(--pp-text-primary)]">{importDeepReadJob.jobId}</span>
                  </p>
                  <p className="mt-1" data-testid="paper-note-import-guidance-deepread-status-guidance">
                    {getImportDeepReadStatusGuidance(importDeepReadJob)}
                  </p>
                  {importDeepReadJob.errorMessage ? (
                    <p className="mt-1 text-[var(--pp-status-failed-text)]">{importDeepReadJob.errorMessage}</p>
                  ) : null}
                </div>
              ) : null}
              {importDeepReadError ? (
                <p className="text-xs text-[var(--pp-status-failed-text)]" data-testid="paper-note-import-guidance-deepread-error">
                  Deep read queue failed: {importDeepReadError}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
        <WorkspaceContextStrip
          testId="paper-note-workspace-context"
          description="Keep the saved note, structured state, and current mode aligned before handing off to deeper review."
        >
          <WorkspaceContextCard eyebrow="Saved note" testId="paper-note-workspace-context-note">
            <p className="break-all text-sm font-medium text-[var(--pp-text-primary)]">{note?.note_path ?? slug}</p>
            <div className="flex flex-wrap gap-1.5">
              {note?.status ? <StatusBadge label={formatFreeformStatusLabel(note.status)} tone={getFreeformStatusTone(note.status)} /> : null}
              {note?.updated_at ? <Badge variant="outline">updated {formatDateTime(note.updated_at)}</Badge> : null}
            </div>
          </WorkspaceContextCard>
          <WorkspaceContextCard eyebrow="Structured state" testId="paper-note-workspace-context-state">
            <p className="text-sm text-[var(--pp-text-primary)]">
              {structuredState ? "Saved state is ready for review and evidence follow-up." : "No saved state is loaded for this note yet."}
            </p>
            <div className="flex flex-wrap gap-1.5">
              <Badge variant={structuredState ? "muted" : "outline"}>
                {structuredState ? "Saved state loaded" : "Saved state missing"}
              </Badge>
              {structuredState?.updated_at ? <Badge variant="outline">updated {formatDateTime(structuredState.updated_at)}</Badge> : null}
              {structuredState && structuredState.claimset.length > 0 ? <Badge variant="outline">claims {structuredState.claimset.length}</Badge> : null}
            </div>
          </WorkspaceContextCard>
          <WorkspaceContextCard eyebrow="Workspace mode" testId="paper-note-view-mode-controls">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant={viewerMode === "learner" ? "secondary" : "ghost"}
                onClick={() => handleViewerModeChange("learner")}
              >
                Read
              </Button>
              <Button
                size="sm"
                variant={viewerMode === "builder_debug" ? "secondary" : "ghost"}
                onClick={() => handleViewerModeChange("builder_debug")}
              >
                Review
              </Button>
              <Badge variant="outline">Current mode: {formatViewerOutputModeLabel(viewerMode)}</Badge>
            </div>
            <p className="text-sm text-[var(--pp-text-secondary)]" data-testid="paper-note-view-mode-summary">
              {getViewerModeSummary(viewerMode)}
            </p>
          </WorkspaceContextCard>
        </WorkspaceContextStrip>
        <ReviewSnapshotPanel note={note} state={structuredState} workbenchPaperId={workbenchPaperId} />
      </header>

      {loading ? <p className="text-sm text-[var(--pp-text-dim)]">Loading note...</p> : null}
      {loadError ? (
        <div data-testid="paper-note-load-error" className="text-sm text-[var(--pp-status-failed-text)]">
          <p>API error: {loadError}</p>
          <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
            If this note should be loading from the live runtime,{" "}
            <Link to="/ready" className="text-[var(--pp-accent-text)] underline underline-offset-2">
              open Runtime checks
            </Link>{" "}
            before retrying.
          </p>
        </div>
      ) : null}

      {!loading && !loadError && data ? (
        <main className="grid grid-cols-1 gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="hidden xl:block">
            <div className="sticky top-4 grid gap-4">
              <Card className="overflow-hidden">
                <CardHeader>
                  <CardTitle>Read context</CardTitle>
                  <CardDescription>{getViewerContextDescription(viewerMode)}</CardDescription>
                </CardHeader>
                <Separator />
                <CardContent className="pt-4">
                  <p className="text-sm text-[var(--pp-text-secondary)]">{note?.note_path ?? slug}</p>
                  <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{getViewerModeSummary(viewerMode)}</p>
                  {structuredState?.updated_at ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <Badge variant="outline">saved state {formatDateTime(structuredState.updated_at)}</Badge>
                      {structuredState.claimset.length > 0 ? <Badge variant="outline">claims {structuredState.claimset.length}</Badge> : null}
                    </div>
                  ) : null}
                  {workbenchPaperId ? (
                    <Link
                      to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                      className={buttonClassName({ className: "mt-4 w-full" })}
                      onClick={() => logOpenWorkbench("paper_note_context_card")}
                    >
                      <FlaskConical className="h-4 w-4" />
                      Open review
                    </Link>
                  ) : null}
                </CardContent>
              </Card>

              <OutlinePanel outline={outline} />
              <SectionNavigatorPanel sections={sectionNavigator} stateLoaded={Boolean(structuredState)} />
            </div>
          </aside>

          <section className="grid min-h-0 gap-4">
            <Card className="overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <ScrollText className="h-4 w-4 text-[var(--pp-accent-text)]" />
              <CardTitle>Read</CardTitle>
                </div>
                <CardDescription>{getReadingViewDescription(viewerMode)}</CardDescription>
              </CardHeader>
              <Separator />
              <CardContent className="pt-4">
                <ReviewBridgePanel
                  note={note}
                  state={structuredState}
                  workbenchPaperId={workbenchPaperId}
                  protocolCardStartHref={protocolCardStartHref}
                />
                <ReadingAssistPanel
                  readingAssist={readingAssist}
                  availableLocales={readingAssistLocales}
                  requestedLocale={requestedReadingAssistLocale}
                  onSelectLocale={handleReadingAssistLocaleChange}
                />
                <article className="paper-note-markdown mt-4">
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
                  <SavedStatePanel note={note} state={structuredState} contextTrace={contextTrace} />
                  <ClaimSetPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                  <OperatorStatePanel
                    operatorState={operatorState}
                    dirty={operatorStateDirty}
                    saving={savingOperatorState}
                    saveMessage={operatorSaveMessage}
                    saveError={operatorSaveError}
                    onToggleStar={handleToggleOperatorStar}
                    onToggleTriage={handleToggleOperatorTriage}
                    onNoteChange={handleOperatorNoteChange}
                    onReset={handleResetOperatorState}
                    onSave={handleSaveOperatorState}
                  />
                  <ActionsPanel
                    actions={availableActions}
                    runningAction={runningAction}
                    actionMessage={actionMessage}
                    signalDiffs={signalDiffs}
                    appendMarkdownSummary={appendMarkdownSummary}
                    onAppendMarkdownSummaryChange={setAppendMarkdownSummary}
                    onRun={handleRunAction}
                  />
                  {criticalAppraisalReport && latestCriticalAppraisalRun ? (
                    <AppraisalPanel report={criticalAppraisalReport} run={latestCriticalAppraisalRun} />
                  ) : null}
                  <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                  <PropertiesPanel
                    note={note}
                    aliases={aliases}
                    tags={tags}
                    structuredState={structuredState}
                    readingAssist={readingAssist}
                    requestedReadingAssistLocale={requestedReadingAssistLocale}
                  />
                  <RelatedPapersPanel related={data.related} />
                  <ReferencesPanel references={data.references} />
                </>
              ) : (
                <>
                  <SavedStatePanel note={note} state={structuredState} contextTrace={contextTrace} />
                  <ClaimSetPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                  <OperatorStatePanel
                    operatorState={operatorState}
                    dirty={operatorStateDirty}
                    saving={savingOperatorState}
                    saveMessage={operatorSaveMessage}
                    saveError={operatorSaveError}
                    onToggleStar={handleToggleOperatorStar}
                    onToggleTriage={handleToggleOperatorTriage}
                    onNoteChange={handleOperatorNoteChange}
                    onReset={handleResetOperatorState}
                    onSave={handleSaveOperatorState}
                  />
                  <PropertiesPanel
                    note={note}
                    aliases={aliases}
                    tags={tags}
                    structuredState={structuredState}
                    readingAssist={readingAssist}
                    requestedReadingAssistLocale={requestedReadingAssistLocale}
                  />
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
                  <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                </>
              )}
            </div>
          </aside>
        </main>
      ) : null}

      <Sheet
        open={sidePanelOpen}
        onOpenChange={setSidePanelOpen}
        title="Note panels"
        description="Metadata, your paper-level note, outline, related papers, references, actions, and saved claims."
      >
        {!data ? null : (
          <div className="grid gap-4">
            {viewerMode === "builder_debug" ? (
              <>
                <SavedStatePanel note={note} state={structuredState} contextTrace={contextTrace} />
                <ClaimSetPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                <OperatorStatePanel
                  operatorState={operatorState}
                  dirty={operatorStateDirty}
                  saving={savingOperatorState}
                  saveMessage={operatorSaveMessage}
                  saveError={operatorSaveError}
                  onToggleStar={handleToggleOperatorStar}
                  onToggleTriage={handleToggleOperatorTriage}
                  onNoteChange={handleOperatorNoteChange}
                  onReset={handleResetOperatorState}
                  onSave={handleSaveOperatorState}
                />
                <ActionsPanel
                  actions={availableActions}
                  runningAction={runningAction}
                  actionMessage={actionMessage}
                  signalDiffs={signalDiffs}
                  appendMarkdownSummary={appendMarkdownSummary}
                  onAppendMarkdownSummaryChange={setAppendMarkdownSummary}
                  onRun={handleRunAction}
                />
                {criticalAppraisalReport && latestCriticalAppraisalRun ? (
                  <AppraisalPanel report={criticalAppraisalReport} run={latestCriticalAppraisalRun} />
                ) : null}
                <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                <PropertiesPanel note={note} aliases={aliases} tags={tags} structuredState={structuredState} />
                <OutlinePanel outline={outline} onNavigate={() => setSidePanelOpen(false)} />
                <SectionNavigatorPanel
                  sections={sectionNavigator}
                  stateLoaded={Boolean(structuredState)}
                  onNavigate={() => setSidePanelOpen(false)}
                />
                <RelatedPapersPanel related={data.related} onNavigate={() => setSidePanelOpen(false)} />
                <ReferencesPanel references={data.references} />
              </>
            ) : (
              <>
                <SavedStatePanel note={note} state={structuredState} contextTrace={contextTrace} />
                <ClaimSetPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
                <OperatorStatePanel
                  operatorState={operatorState}
                  dirty={operatorStateDirty}
                  saving={savingOperatorState}
                  saveMessage={operatorSaveMessage}
                  saveError={operatorSaveError}
                  onToggleStar={handleToggleOperatorStar}
                  onToggleTriage={handleToggleOperatorTriage}
                  onNoteChange={handleOperatorNoteChange}
                  onReset={handleResetOperatorState}
                  onSave={handleSaveOperatorState}
                />
                <PropertiesPanel note={note} aliases={aliases} tags={tags} structuredState={structuredState} />
                <OutlinePanel outline={outline} onNavigate={() => setSidePanelOpen(false)} />
                <SectionNavigatorPanel
                  sections={sectionNavigator}
                  stateLoaded={Boolean(structuredState)}
                  onNavigate={() => setSidePanelOpen(false)}
                />
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
                <AutomationResultsPanel state={structuredState} focusTarget={focusTarget} structuredStatePath={structuredStatePath} />
              </>
            )}
          </div>
        )}
      </Sheet>

      {workbenchPaperId ? (
        <div className="fixed bottom-3 left-3 right-3 z-30 md:hidden" data-testid="paper-note-mobile-sticky-actions">
          <div className="grid gap-2">
            {isManualPdfImport && importedPdfReference ? (
              <a
                href={importedPdfReference.url}
                target="_blank"
                rel="noreferrer"
                className={buttonClassName({ variant: "outline", className: "w-full shadow-[var(--pp-shadow)]" })}
                data-testid="paper-note-mobile-sticky-open-pdf"
              >
                Open saved PDF
              </a>
            ) : protocolCardStartHref ? (
              <Link
                to={protocolCardStartHref}
                className={buttonClassName({ variant: "outline", className: "w-full shadow-[var(--pp-shadow)]" })}
                data-testid="paper-note-mobile-sticky-save-protocol"
              >
                Save protocol card
              </Link>
            ) : null}
            <Link
              to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
              className={buttonClassName({ className: "w-full shadow-[var(--pp-shadow)]" })}
              data-testid="paper-note-mobile-sticky-open-review"
              onClick={() => logOpenWorkbench("paper_note_mobile_cta")}
            >
              <FlaskConical className="h-4 w-4" />
              Open review
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
