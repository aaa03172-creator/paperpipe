import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowDownToLine, ArrowLeft, ArrowRight, ExternalLink, Route, Search, ShieldAlert, Upload } from "lucide-react";
import {
  createProtocolCard,
  getProtocolAttachmentBundle,
  createProtocolDraftFromAttachment,
  getApiErrorMessage,
  getPaperNotesIndex,
  getProtocolAttachmentBundleUrl,
  getProtocolAttachmentMarkdownUrl,
  getProtocolAttachmentSourceUrl,
  getProtocolCard,
  getProtocolCardIndex,
} from "../lib/api";
import {
  EvidenceLocator,
  ProtocolAttachmentBundle,
  PaperNoteSummary,
  ProtocolAttachmentDraftResponse,
  ProtocolCard,
  ProtocolCardListItem,
  ProtocolCardListResponse,
  ProtocolCardRequestSnapshot,
  ProtocolCardResponse,
  ProtocolSourceKind,
  ProtocolValidationStatus,
  ProtocolVersion,
  ProtocolVersionStatus,
} from "../lib/types";
import { Button } from "../components/ui/button";
import { buttonClassName } from "../components/ui/buttonClassName";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { ArtifactHeaderContext } from "../components/ArtifactHeaderContext";

interface ApiLikeResult {
  isMock: boolean;
  reason?: string;
}

interface RecentProtocolNoteChoice {
  slug: string;
  paperId: string;
  title: string;
}

interface ProtocolCardNavigationState {
  attachmentDraft?: ProtocolAttachmentDraftResponse | null;
}

interface ProtocolAttachmentReference {
  attachmentBundleId: string;
  sourceFilename: string | null;
}

interface LoadedProtocolAttachmentBundle {
  reference: ProtocolAttachmentReference;
  bundle: ProtocolAttachmentBundle | null;
  error: string | null;
}

interface ProtocolAttachmentPreviewHints {
  mediaType?: string | null;
  sourceFilename?: string | null;
}

interface ProtocolAttachmentSourceAction {
  href: string;
  kind: "open" | "download";
  label: string;
  testId: string;
  primary: boolean;
}

const PROTOCOL_ATTACHMENT_ACCEPT =
  ".txt,.md,.csv,.tsv,.json,.yaml,.yml,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.tif,.tiff,image/*";

function normalizeRecentNoteIdentity(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function recentNoteSlugLooksRedundant(choice: RecentProtocolNoteChoice): boolean {
  const normalizedTitle = normalizeRecentNoteIdentity(choice.title);
  const normalizedSlug = normalizeRecentNoteIdentity(choice.slug);
  if (!normalizedSlug) {
    return false;
  }
  if (normalizedTitle === normalizedSlug) {
    return true;
  }
  if (normalizedTitle.includes(normalizedSlug) || normalizedSlug.includes(normalizedTitle)) {
    return true;
  }
  return !/[-_/:\s]/.test(choice.slug);
}

function recentProtocolNoteSecondaryLabel(choice: RecentProtocolNoteChoice): {
  text: string;
  monospace: boolean;
} {
  if (choice.paperId && recentNoteSlugLooksRedundant(choice)) {
    return { text: choice.paperId, monospace: true };
  }
  if (choice.slug) {
    return { text: choice.slug, monospace: true };
  }
  return { text: choice.paperId, monospace: true };
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

function formatByteSize(value: number): string {
  if (!Number.isFinite(value) || value < 1024) {
    return `${Math.max(0, Math.round(value))} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(value >= 10 * 1024 ? 0 : 1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function parseProtocolAttachmentReferences(note?: string | null): ProtocolAttachmentReference[] {
  const raw = String(note ?? "");
  if (!raw.trim()) {
    return [];
  }
  const matches = raw.matchAll(/Attachment bundle:\s*(protatt_[A-Za-z0-9._-]+)(?:\s*\(([^)]+)\))?/g);
  const refs: ProtocolAttachmentReference[] = [];
  const seen = new Set<string>();
  for (const match of matches) {
    const attachmentBundleId = String(match[1] ?? "").trim();
    if (!attachmentBundleId || seen.has(attachmentBundleId)) {
      continue;
    }
    seen.add(attachmentBundleId);
    const sourceFilename = String(match[2] ?? "").trim() || null;
    refs.push({ attachmentBundleId, sourceFilename });
  }
  return refs;
}

function dedupeProtocolAttachmentWarnings(warnings: ProtocolAttachmentBundle["warnings"]): ProtocolAttachmentBundle["warnings"] {
  const seen = new Set<string>();
  return warnings.filter((warning) => {
    const key = `${warning.code}:${warning.message}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function protocolAttachmentLooksPreviewable(hints?: ProtocolAttachmentPreviewHints | null): boolean {
  const mediaType = String(hints?.mediaType ?? "").trim().toLowerCase();
  if (mediaType.startsWith("text/")) {
    return true;
  }
  if (mediaType === "application/pdf") {
    return true;
  }
  if (["image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"].includes(mediaType)) {
    return true;
  }

  const suffix = hints?.sourceFilename?.trim().toLowerCase().match(/\.[a-z0-9]+$/)?.[0] ?? "";
  return [
    ".txt",
    ".text",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
  ].includes(suffix);
}

function buildProtocolAttachmentSourceActions({
  attachmentBundleId,
  mediaType,
  sourceFilename,
}: ProtocolAttachmentPreviewHints & {
  attachmentBundleId: string;
}): ProtocolAttachmentSourceAction[] {
  const previewable = protocolAttachmentLooksPreviewable({ mediaType, sourceFilename });
  const actionKinds: ProtocolAttachmentSourceAction["kind"][] = previewable
    ? ["open", "download"]
    : ["download", "open"];

  return actionKinds.map((kind, index) => ({
    href: getProtocolAttachmentSourceUrl(attachmentBundleId, { download: kind === "download" }),
    kind,
    label: kind === "download" ? "Download raw source" : "Open raw source",
    testId:
      kind === "download"
        ? "protocol-card-attachment-download-source"
        : "protocol-card-attachment-open-source",
    primary: index === 0,
  }));
}

function attachmentActionLinkClassName(primary: boolean, options: { raisedSurface: boolean }): string {
  return buttonClassName({
    variant: primary ? "default" : "outline",
    size: "sm",
    className: options.raisedSurface
      ? primary
        ? undefined
        : "bg-[var(--pp-surface-raised)]"
      : primary
        ? undefined
        : "bg-[var(--pp-surface)]",
  });
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

function parseLineSeparatedValues(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/\n+/)
        .map((entry) => entry.trim())
        .filter(Boolean),
    ),
  );
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

function recentProtocolNoteChoices(notes: PaperNoteSummary[]): RecentProtocolNoteChoice[] {
  const seen = new Set<string>();
  const choices: RecentProtocolNoteChoice[] = [];

  for (const note of notes) {
    const slug = note.slug.trim();
    const paperId = typeof note.id === "string" ? note.id.trim() : "";
    const title = note.title.trim();
    if (!slug || !paperId || !title) {
      continue;
    }
    if (seen.has(slug)) {
      continue;
    }
    seen.add(slug);
    choices.push({ slug, paperId, title });
    if (choices.length >= 6) {
      break;
    }
  }

  return choices;
}

function buildProtocolHeaderWhenToUse(routeProtocolId?: string): string {
  if (routeProtocolId) {
    return "Use this card when you need a note-linked protocol snapshot for review, citation, or downstream artifact reuse rather than wet-lab execution.";
  }
  return "Use this lane when you want to save a protocol snapshot from notes, then review whether the current version is safe to reuse downstream.";
}

function buildProtocolHeaderDerivedFrom(protocolCard: ProtocolCard | null, sourceRefCount: number): string {
  if (!protocolCard) {
    return "Derived from paper-linked notes and evidence-backed version snapshots once a protocol card is saved.";
  }
  return `Derived from ${protocolCard.linked_note_slugs.length} linked note${protocolCard.linked_note_slugs.length === 1 ? "" : "s"}, ${protocolCard.linked_paper_ids.length} linked paper${protocolCard.linked_paper_ids.length === 1 ? "" : "s"}, and ${sourceRefCount} source ref${sourceRefCount === 1 ? "" : "s"} in the selected version.`;
}

function buildProtocolHeaderContinuity(hasLinkedNote: boolean): string {
  if (hasLinkedNote) {
    return "Canonical evidence lives upstream in the linked paper note. Continue in note before changing claims, steps, or version status.";
  }
  return "Canonical evidence lives upstream in linked paper review context. Re-open upstream note review before changing claims, steps, or version status.";
}

export function ProtocolCardPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { protocolId: routeProtocolId } = useParams<{ protocolId?: string }>();
  const [searchParams] = useSearchParams();
  const attachmentInputRef = useRef<HTMLInputElement | null>(null);
  const [indexResponse, setIndexResponse] = useState<ProtocolCardListResponse | null>(null);
  const [detailResponse, setDetailResponse] = useState<ProtocolCardResponse | null>(null);
  const [recentNotes, setRecentNotes] = useState<RecentProtocolNoteChoice[]>([]);
  const [indexSearchQuery, setIndexSearchQuery] = useState("");
  const [createTitle, setCreateTitle] = useState("");
  const [createPurpose, setCreatePurpose] = useState("");
  const [createPaperId, setCreatePaperId] = useState("");
  const [createNoteSlug, setCreateNoteSlug] = useState("");
  const [createSourceKind, setCreateSourceKind] = useState<ProtocolSourceKind>("paper_derived");
  const [createVersionStatus, setCreateVersionStatus] = useState<ProtocolVersionStatus>("draft");
  const [createSnapshot, setCreateSnapshot] = useState("");
  const [createKeySteps, setCreateKeySteps] = useState("");
  const [creatingProtocolCard, setCreatingProtocolCard] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createValidationPrimed, setCreateValidationPrimed] = useState(false);
  const [creatingAttachmentDraft, setCreatingAttachmentDraft] = useState(false);
  const [attachmentDraftResponse, setAttachmentDraftResponse] = useState<ProtocolAttachmentDraftResponse | null>(null);
  const [attachmentDraftError, setAttachmentDraftError] = useState<string | null>(null);
  const [selectedVersionAttachmentBundles, setSelectedVersionAttachmentBundles] = useState<LoadedProtocolAttachmentBundle[]>([]);
  const [loadingSelectedVersionAttachments, setLoadingSelectedVersionAttachments] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockReasons, setMockReasons] = useState<string[]>([]);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    const titleSuffix = routeProtocolId ? ` ${routeProtocolId}` : "";
    document.title = `Protocol Cards${titleSuffix} | Lattice`;
  }, [routeProtocolId, reloadTick]);

  useEffect(() => {
    let mounted = true;

    async function loadIndex() {
      setLoading(true);
      setError(null);
      setIndexResponse(null);
      setDetailResponse(null);
      setSelectedVersionId(null);
      setRecentNotes([]);
      setMockReasons([]);

      try {
        const [protocolResult, noteResult] = await Promise.all([
          getProtocolCardIndex(),
          getPaperNotesIndex({ pageSize: 24 }),
        ]);
        if (!mounted) {
          return;
        }
        setIndexResponse(protocolResult.data);
        setRecentNotes(recentProtocolNoteChoices(noteResult.data.items));
        setMockReasons(collectMockReasons([protocolResult, noteResult]));
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
  }, [routeProtocolId, reloadTick]);

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

  const selectedVersionAttachmentRefs = useMemo(
    () => parseProtocolAttachmentReferences(selectedVersion?.note),
    [selectedVersion?.note],
  );

  useEffect(() => {
    if (!routeProtocolId || !selectedVersion || selectedVersionAttachmentRefs.length === 0) {
      setSelectedVersionAttachmentBundles([]);
      setLoadingSelectedVersionAttachments(false);
      return;
    }

    let mounted = true;
    setLoadingSelectedVersionAttachments(true);

    void Promise.all(
      selectedVersionAttachmentRefs.map(async (reference) => {
        try {
          const result = await getProtocolAttachmentBundle(reference.attachmentBundleId);
          return {
            reference,
            bundle: result.data,
            error: null,
          } satisfies LoadedProtocolAttachmentBundle;
        } catch (error) {
          return {
            reference,
            bundle: null,
            error: getApiErrorMessage(error),
          } satisfies LoadedProtocolAttachmentBundle;
        }
      }),
    ).then((results) => {
      if (!mounted) {
        return;
      }
      setSelectedVersionAttachmentBundles(results);
      setLoadingSelectedVersionAttachments(false);
    });

    return () => {
      mounted = false;
    };
  }, [routeProtocolId, selectedVersion, selectedVersionAttachmentRefs]);

  const primaryNoteHref = protocolCard?.linked_note_slugs[0]
    ? `/papers/${encodeURIComponent(protocolCard.linked_note_slugs[0])}`
    : null;
  const trimmedCreateNoteSlug = createNoteSlug.trim();
  const trimmedCreatePaperId = createPaperId.trim();
  const activeCreateNoteChoice = useMemo(
    () =>
      recentNotes.find(
        (choice) => choice.slug === trimmedCreateNoteSlug && choice.paperId === trimmedCreatePaperId,
      ) ??
      recentNotes.find((choice) => choice.slug === trimmedCreateNoteSlug || choice.paperId === trimmedCreatePaperId) ??
      null,
    [recentNotes, trimmedCreateNoteSlug, trimmedCreatePaperId],
  );
  const hasActiveCreateNoteContext = Boolean(trimmedCreateNoteSlug || trimmedCreatePaperId);
  const activeCreateNoteContextLabel =
    activeCreateNoteChoice?.title ?? trimmedCreateNoteSlug ?? trimmedCreatePaperId;
  const createTitleValue = createTitle.trim();
  const createSnapshotValue = createSnapshot.trim();
  const createReadinessMissingItems = [
    !createTitleValue ? "Protocol title" : null,
    !createSnapshotValue ? "Current version snapshot" : null,
  ].filter((item): item is string => item !== null);
  const createFormReady = createReadinessMissingItems.length === 0;
  const createTitleNeedsAttention = createValidationPrimed && !createTitleValue;
  const createSnapshotNeedsAttention = createValidationPrimed && !createSnapshotValue;
  const createTitleGuidance = createTitleValue
    ? "Saved card heading looks ready."
    : "Required before save. Give this saved snapshot a short review title.";
  const createSnapshotGuidance = createSnapshotValue
    ? "Current version snapshot looks ready."
    : "Required before save. Add the current protocol wording or step summary.";
  const attachmentDraftWarnings = useMemo(() => {
    if (!attachmentDraftResponse) {
      return [];
    }
    return dedupeProtocolAttachmentWarnings([
      ...attachmentDraftResponse.attachment_bundle.warnings,
      ...attachmentDraftResponse.warnings,
    ]);
  }, [attachmentDraftResponse]);
  const attachmentBundleUrl = attachmentDraftResponse
    ? getProtocolAttachmentBundleUrl(attachmentDraftResponse.attachment_bundle.attachment_bundle_id)
    : null;
  const attachmentMarkdownUrl =
    attachmentDraftResponse?.attachment_bundle.extracted_markdown_ref
      ? getProtocolAttachmentMarkdownUrl(attachmentDraftResponse.attachment_bundle.attachment_bundle_id)
      : null;
  const attachmentSourceActions = attachmentDraftResponse
    ? buildProtocolAttachmentSourceActions({
        attachmentBundleId: attachmentDraftResponse.attachment_bundle.attachment_bundle_id,
        mediaType: attachmentDraftResponse.attachment_bundle.media_type,
        sourceFilename: attachmentDraftResponse.attachment_bundle.source_filename,
      })
    : [];

  const attachmentDraftDisabledReason = mockReasons.length > 0
    ? "Attachment-to-draft creation needs the live backend. It is disabled while this page is in fallback mode."
    : hasActiveCreateNoteContext
      ? "Upload a file to merge note-backed protocol evidence with external material before saving."
      : "Upload a file, image, or document to seed this protocol draft from external material.";

  const applyAttachmentDraft = useCallback((response: ProtocolAttachmentDraftResponse) => {
    const nextDraft = response.draft;
    const nextVersion = nextDraft.versions[0];
    setCreateTitle(nextDraft.title);
    setCreatePurpose(nextDraft.purpose ?? "");
    setCreateNoteSlug(nextDraft.linked_note_slugs[0] ?? "");
    setCreatePaperId(nextDraft.linked_paper_ids[0] ?? "");
    setCreateSourceKind(nextDraft.source_kind);
    setCreateVersionStatus(nextVersion?.status === "active" ? "active" : "draft");
    setCreateSnapshot(nextVersion?.content_snapshot ?? "");
    setCreateKeySteps((nextVersion?.key_steps_summary ?? []).join("\n"));
    setCreateError(null);
    setCreateValidationPrimed(false);
    setAttachmentDraftError(null);
    setAttachmentDraftResponse(response);
  }, []);

  useEffect(() => {
    if (routeProtocolId) {
      return;
    }
    const prefillNoteSlug = searchParams.get("noteSlug")?.trim() ?? "";
    const prefillPaperId = searchParams.get("paperId")?.trim() ?? "";
    if (!prefillNoteSlug && !prefillPaperId) {
      return;
    }
    if (prefillNoteSlug) {
      setCreateNoteSlug(prefillNoteSlug);
    }
    if (prefillPaperId) {
      setCreatePaperId(prefillPaperId);
    }
    setCreateError(null);
  }, [routeProtocolId, searchParams]);

  useEffect(() => {
    if (routeProtocolId) {
      return;
    }
    const navigationState = (location.state as ProtocolCardNavigationState | null) ?? null;
    if (!navigationState?.attachmentDraft) {
      return;
    }
    applyAttachmentDraft(navigationState.attachmentDraft);
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [applyAttachmentDraft, location.pathname, location.search, location.state, navigate, routeProtocolId]);

  function applyRecentNote(choice: RecentProtocolNoteChoice) {
    setCreateNoteSlug(choice.slug);
    setCreatePaperId(choice.paperId);
    setCreateError(null);
  }

  function clearCreateNoteContext() {
    setCreateNoteSlug("");
    setCreatePaperId("");
    setCreateError(null);
  }

  function retryLoad() {
    setReloadTick((value) => value + 1);
  }

  function openAttachmentPicker() {
    if (mockReasons.length > 0 || creatingAttachmentDraft) {
      return;
    }
    attachmentInputRef.current?.click();
  }

  async function handleAttachmentSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file) {
      return;
    }

    setCreatingAttachmentDraft(true);
    setAttachmentDraftError(null);
    try {
      const result = await createProtocolDraftFromAttachment({
        file,
        noteSlug: createNoteSlug.trim() || undefined,
        paperId: createPaperId.trim() || undefined,
      });
      applyAttachmentDraft(result.data);
    } catch (actionError) {
      setAttachmentDraftError(getApiErrorMessage(actionError));
    } finally {
      setCreatingAttachmentDraft(false);
    }
  }

  async function handleCreateProtocolCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = createTitle.trim();
    const contentSnapshot = createSnapshot.trim();
    const linkedPaperId = createPaperId.trim();
    const linkedNoteSlug = createNoteSlug.trim();

    if (!title) {
      setCreateValidationPrimed(true);
      setCreateError(null);
      return;
    }
    if (!contentSnapshot) {
      setCreateValidationPrimed(true);
      setCreateError(null);
      return;
    }

    setCreatingProtocolCard(true);
    setCreateValidationPrimed(true);
    setCreateError(null);
    try {
      const draftSeedVersion = attachmentDraftResponse?.draft.versions[0] ?? null;
      const linkedPaperIds = linkedPaperId ? [linkedPaperId] : [];
      const linkedNoteSlugs = linkedNoteSlug ? [linkedNoteSlug] : [];
      const payload: ProtocolCardRequestSnapshot = {
        title,
        purpose: createPurpose.trim() || attachmentDraftResponse?.draft.purpose || undefined,
        context:
          attachmentDraftResponse?.draft.context ??
          (linkedNoteSlug ? `Created from the protocol review surface for note ${linkedNoteSlug}.` : undefined),
        source_kind: createSourceKind,
        linked_paper_ids: linkedPaperIds,
        linked_note_slugs: linkedNoteSlugs,
        validation_status: createVersionStatus === "active" ? "draft" : "unreviewed",
        versions: [
          {
            version_number: 1,
            key_steps_summary: parseLineSeparatedValues(createKeySteps),
            materials: draftSeedVersion?.materials ?? [],
            equipment: draftSeedVersion?.equipment ?? [],
            critical_conditions: draftSeedVersion?.critical_conditions ?? [],
            readouts: draftSeedVersion?.readouts ?? [],
            cautions: draftSeedVersion?.cautions ?? [],
            content_snapshot: contentSnapshot,
            change_reason:
              draftSeedVersion?.change_reason ?? "Initial protocol snapshot created from the browser review surface.",
            status: createVersionStatus,
            created_by: draftSeedVersion?.created_by ?? "operator",
            source_refs:
              draftSeedVersion?.source_refs ??
              (linkedNoteSlug ? [{ paper_slug: linkedNoteSlug }] : []),
            note:
              draftSeedVersion?.note ??
              (linkedNoteSlug ? `Linked note slug: ${linkedNoteSlug}` : undefined),
          },
        ],
      };

      const result = await createProtocolCard(payload);
      navigate(`/protocol-cards/${encodeURIComponent(result.data.protocol_card.protocol_id)}`);
    } catch (actionError) {
      setCreateError(getApiErrorMessage(actionError));
    } finally {
      setCreatingProtocolCard(false);
    }
  }

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
        <ArtifactHeaderContext
          testId="protocol-card-header-context"
          emphasizeFirstItem={Boolean(routeProtocolId)}
          items={[
            routeProtocolId ? { label: "Derived artifact", value: buildProtocolHeaderContinuity(Boolean(primaryNoteHref)) } : null,
            { label: "When to use", value: buildProtocolHeaderWhenToUse(routeProtocolId) },
            { label: "Derived from", value: buildProtocolHeaderDerivedFrom(protocolCard, selectedVersion?.source_refs.length ?? 0) },
          ].filter((item): item is { label: string; value: string } => item !== null)}
        />
        {mockReasons.length > 0 ? (
          <p className="mt-3 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
      </header>

      {error ? (
        <Card
          data-testid="protocol-card-load-error"
          className="mb-4 border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <ShieldAlert className="h-4 w-4" />
              Protocol card unavailable
            </CardTitle>
            <CardDescription className="text-[var(--pp-warning-text)]/80">
              {routeProtocolId
                ? "This saved protocol card could not be loaded right now. Try again, or go back to the saved-card index."
                : "Protocol cards could not be loaded right now. Try again to reload the saved-card index."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="rounded-md border border-[var(--pp-warning-border)]/70 bg-[var(--pp-warning-bg)] p-3 text-sm text-[var(--pp-warning-text)]">
              {error}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" data-testid="protocol-card-retry-load" onClick={retryLoad}>
                Try again
              </Button>
              {routeProtocolId ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid="protocol-card-back-to-index"
                  onClick={() => navigate("/protocol-cards")}
                >
                  Back to protocol cards
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!routeProtocolId ? (
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-4">
            <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
              <CardHeader>
                <CardTitle className="text-sm">Search protocol cards</CardTitle>
                <CardDescription>Find saved derived protocol cards by title, protocol ID, source kind, or validation state.</CardDescription>
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
                  {error
                    ? "Saved protocol cards are temporarily unavailable. Try again above, or start a new card if you already know the note context."
                    : indexResponse
                    ? indexResponse.total > 0
                      ? `${filteredItems.length} of ${indexResponse.total} saved derived protocol cards`
                      : "No saved derived protocol cards yet. Start one below, then review versions and note links here."
                    : "Waiting for protocol cards"}
                </div>
              </CardContent>
            </Card>

            <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
              <CardHeader>
                <CardTitle className="text-sm">Save a protocol snapshot</CardTitle>
                <CardDescription>
                  Start with the title and current version snapshot. Add note context when you want the saved card tied
                  back to a specific paper review thread.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-[var(--pp-text-secondary)]">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 text-xs text-[var(--pp-text-secondary)]">
                  Protocol cards stay downstream of note review. Treat them as reusable review artifacts, not execution-ready SOPs.
                </div>
                <form onSubmit={handleCreateProtocolCard} className="space-y-3">
                  <div className="rounded-md border border-dashed border-[var(--pp-accent-border)] bg-[var(--pp-surface-raised)] p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="max-w-2xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-accent-text)]">
                          Seed From Attachment
                        </p>
                        <p className="mt-1 text-sm font-medium text-[var(--pp-text-primary)]">
                          Upload protocol text, images, or documents and let this lane prefill the draft.
                        </p>
                        <p
                          className="mt-1 text-xs text-[var(--pp-text-secondary)]"
                          data-testid="protocol-card-attachment-help"
                        >
                          {attachmentDraftDisabledReason}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-start gap-2">
                        <input
                          ref={attachmentInputRef}
                          type="file"
                          accept={PROTOCOL_ATTACHMENT_ACCEPT}
                          onChange={handleAttachmentSelection}
                          className="hidden"
                          data-testid="protocol-card-attachment-input"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={openAttachmentPicker}
                          disabled={mockReasons.length > 0 || creatingAttachmentDraft}
                          data-testid="protocol-card-attachment-button"
                        >
                          <Upload className="h-3.5 w-3.5" />
                          {creatingAttachmentDraft ? "Preparing draft..." : "Upload attachment"}
                        </Button>
                        <p className="text-[11px] text-[var(--pp-text-dim)]">
                          Raw source is saved first. Review remains required before card save.
                        </p>
                      </div>
                    </div>
                  </div>

                  {attachmentDraftResponse ? (
                    <div
                      data-testid="protocol-card-attachment-notice"
                      className="rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] p-3 text-xs text-[var(--pp-text-secondary)]"
                    >
                      <p className="font-semibold uppercase tracking-wide text-[var(--pp-accent-text)]">
                        {attachmentDraftResponse.draft.source_kind === "mixed"
                          ? "Attachment merged with note context"
                          : "Attachment draft loaded"}
                      </p>
                      <p className="mt-1 text-sm text-[var(--pp-text-primary)]">
                        {attachmentDraftResponse.attachment_bundle.source_filename}
                      </p>
                      <p className="mt-1">
                        Bundle {attachmentDraftResponse.attachment_bundle.attachment_bundle_id} was saved as raw source
                        and the current version snapshot was refreshed from the attachment draft.
                      </p>
                      <div
                        data-testid="protocol-card-attachment-metadata"
                        className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
                      >
                        <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Layer</p>
                          <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                            {attachmentDraftResponse.attachment_bundle.layer}
                          </p>
                        </div>
                        <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Byte size</p>
                          <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                            {formatByteSize(attachmentDraftResponse.attachment_bundle.byte_size)}
                          </p>
                        </div>
                        <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Extraction</p>
                          <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                            {attachmentDraftResponse.attachment_bundle.extraction_status}
                          </p>
                        </div>
                        <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Engine</p>
                          <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                            {attachmentDraftResponse.attachment_bundle.extraction_engine ?? "Unavailable"}
                          </p>
                        </div>
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">
                        {attachmentDraftResponse.attachment_bundle.extraction_status === "succeeded"
                          ? "Automatic text extraction succeeded. Review the prefilled snapshot before saving."
                          : "Automatic text extraction was unavailable. The raw source is preserved and the snapshot may contain a fallback note."}
                      </p>
                      {attachmentDraftResponse.paper_source_summary ? (
                        <p className="mt-1 text-[11px] text-[var(--pp-text-dim)]">
                          Upstream note evidence stayed attached to {attachmentDraftResponse.paper_source_summary.note_slug}.
                        </p>
                      ) : null}
                      {attachmentDraftResponse.attachment_bundle.extracted_markdown_excerpt ? (
                        <div
                          data-testid="protocol-card-attachment-preview"
                          className="mt-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                              Extracted preview
                            </p>
                            <p className="text-[10px] text-[var(--pp-text-dim)]">
                              Review before save
                            </p>
                          </div>
                          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-[var(--pp-text-primary)]">
                            {attachmentDraftResponse.attachment_bundle.extracted_markdown_excerpt}
                          </pre>
                        </div>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-2">
                        {attachmentSourceActions.map((action) => (
                          <a
                            key={action.kind}
                            href={action.href}
                            target="_blank"
                            rel="noreferrer"
                            data-testid={action.testId}
                            data-priority={action.primary ? "primary" : "secondary"}
                            className={attachmentActionLinkClassName(action.primary, { raisedSurface: false })}
                          >
                            {action.label}
                            {action.kind === "download" ? (
                              <ArrowDownToLine className="ml-1.5 h-3.5 w-3.5" />
                            ) : (
                              <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                            )}
                          </a>
                        ))}
                        {attachmentBundleUrl ? (
                          <a
                            href={attachmentBundleUrl}
                            target="_blank"
                            rel="noreferrer"
                            data-testid="protocol-card-attachment-open-bundle"
                            className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 text-[11px] font-medium text-[var(--pp-text-primary)]"
                          >
                            Open bundle JSON
                            <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                          </a>
                        ) : null}
                        {attachmentMarkdownUrl ? (
                          <a
                            href={attachmentMarkdownUrl}
                            target="_blank"
                            rel="noreferrer"
                            data-testid="protocol-card-attachment-open-markdown"
                            className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 text-[11px] font-medium text-[var(--pp-text-primary)]"
                          >
                            Open extracted markdown
                            <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                          </a>
                        ) : null}
                      </div>
                      {attachmentDraftWarnings.length > 0 ? (
                        <div className="mt-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-2 text-[11px] text-[var(--pp-text-secondary)]">
                          {attachmentDraftWarnings.map((warning) => (
                            <p key={`${warning.code}-${warning.message}`}>
                              {warning.code}: {warning.message}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {attachmentDraftError ? (
                    <div
                      data-testid="protocol-card-attachment-error"
                      className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3 text-sm text-[var(--pp-warning-text)]"
                    >
                      {attachmentDraftError}
                    </div>
                  ) : null}

                  <div
                    data-testid="protocol-card-create-readiness"
                    className={`rounded-md border p-3 text-xs ${
                      createFormReady
                        ? "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                        : "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]"
                    }`}
                  >
                    <p className="font-semibold uppercase tracking-wide">
                      {createFormReady ? "Ready to save" : "Still needed before save"}
                    </p>
                    <p className="mt-1">
                      {createFormReady
                        ? "Required fields are in place. Save this derived protocol card when the current snapshot is ready."
                        : `${createReadinessMissingItems.join(" and ")} ${createReadinessMissingItems.length === 1 ? "is" : "are"} still required before this card can be saved.`}
                    </p>
                    <p className="mt-2 text-[11px] opacity-80">
                      The rest of this form is optional or already defaulted, so you can save as soon as those two fields are ready.
                    </p>
                  </div>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Protocol title
                    </span>
                    <Input
                      value={createTitle}
                      onChange={(event) => setCreateTitle(event.target.value)}
                      placeholder="Ketone ester cortical assay snapshot"
                      aria-label="Protocol card title"
                      aria-describedby="protocol-card-title-guidance"
                      aria-invalid={createTitleNeedsAttention ? "true" : undefined}
                      className={
                        createTitleNeedsAttention
                          ? "border-[var(--pp-warning-border)] focus:border-[var(--pp-warning-border)]"
                          : undefined
                      }
                    />
                    <span
                      id="protocol-card-title-guidance"
                      data-testid="protocol-card-title-guidance"
                      className={`mt-1 block text-[11px] ${
                        createTitleNeedsAttention
                          ? "text-[var(--pp-warning-text)]"
                          : createTitleValue
                          ? "text-[var(--pp-status-completed-text)]"
                          : "text-[var(--pp-text-dim)]"
                      }`}
                    >
                      {createTitleGuidance}
                    </span>
                  </label>

                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      Current version snapshot
                    </span>
                    <textarea
                      value={createSnapshot}
                      onChange={(event) => setCreateSnapshot(event.target.value)}
                      placeholder={"Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.\nStep 3: collect BHB readout."}
                      aria-label="Protocol card version snapshot"
                      aria-describedby="protocol-card-snapshot-guidance"
                      aria-invalid={createSnapshotNeedsAttention ? "true" : undefined}
                      className={`min-h-[136px] w-full rounded-md border bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)] outline-none placeholder:text-[var(--pp-text-dim)] ${
                        createSnapshotNeedsAttention
                          ? "border-[var(--pp-warning-border)] focus:border-[var(--pp-warning-border)]"
                          : "border-[var(--pp-border)] focus:border-[var(--pp-accent-border)]"
                      }`}
                    />
                    <span
                      id="protocol-card-snapshot-guidance"
                      data-testid="protocol-card-snapshot-guidance"
                      className={`mt-1 block text-[11px] ${
                        createSnapshotNeedsAttention
                          ? "text-[var(--pp-warning-text)]"
                          : createSnapshotValue
                          ? "text-[var(--pp-status-completed-text)]"
                          : "text-[var(--pp-text-dim)]"
                      }`}
                    >
                      {createSnapshotGuidance}
                    </span>
                  </label>

                  <div
                    data-testid="protocol-card-create-optional-context"
                    className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]"
                  >
                    Optional context and review details are not required to save. Add them when you want this card to be easier to revisit, trace, or hand off later.
                  </div>

                  <div className="rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    <p className="font-semibold uppercase tracking-wide text-[var(--pp-accent-text)]">
                      Recommended context fill
                    </p>
                    <p className="mt-1">
                      If this snapshot should stay tied to a paper review thread, use a recent note first. Manual note
                      slug and paper ID entry stays available below as a fallback.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        Recent notes
                      </span>
                      <span className="text-[11px] text-[var(--pp-text-dim)]">
                        Click one to fill both the note slug and linked paper id.
                      </span>
                    </div>
                    {recentNotes.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {recentNotes.map((choice) => {
                          const isSelected = createNoteSlug.trim() === choice.slug && createPaperId.trim() === choice.paperId;
                          const secondaryLabel = recentProtocolNoteSecondaryLabel(choice);
                          return (
                            <Button
                              key={choice.slug}
                              type="button"
                              variant={isSelected ? "default" : "outline"}
                              size="sm"
                              aria-label={`Use recent note ${choice.title}`}
                              data-testid="protocol-card-recent-note-choice"
                              className="h-auto max-w-full justify-start px-3 py-2 text-left"
                              onClick={() => applyRecentNote(choice)}
                            >
                              <span className="flex min-w-0 flex-col items-start">
                                <span className="max-w-[240px] truncate text-xs font-medium">{choice.title}</span>
                                <span
                                  className={`${secondaryLabel.monospace ? "font-mono" : ""} text-[11px] text-[var(--pp-text-dim)]`}
                                >
                                  {secondaryLabel.text}
                                </span>
                              </span>
                            </Button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-dim)]">
                        No recent notes are ready yet. Open Paper Notes first, then come back here to save a protocol
                        card with note context.
                      </p>
                    )}
                  </div>

                  {hasActiveCreateNoteContext ? (
                    <div
                      data-testid="protocol-card-create-context"
                      className="rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] p-3 text-xs text-[var(--pp-text-secondary)]"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="font-semibold uppercase tracking-wide text-[var(--pp-accent-text)]">
                            Current note context
                          </p>
                          <p className="text-sm text-[var(--pp-text-primary)]">
                            {activeCreateNoteContextLabel}
                          </p>
                          {trimmedCreateNoteSlug ? (
                            <p className="font-mono text-[11px] text-[var(--pp-text-dim)]">
                              Note slug: {trimmedCreateNoteSlug}
                            </p>
                          ) : null}
                          {trimmedCreatePaperId ? (
                            <p className="font-mono text-[11px] text-[var(--pp-text-dim)]">
                              Paper id: {trimmedCreatePaperId}
                            </p>
                          ) : null}
                        </div>
                        <Button type="button" variant="outline" size="sm" onClick={clearCreateNoteContext}>
                          Clear note context
                        </Button>
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-xs text-[var(--pp-text-secondary)]">
                    Manual note-context fallback. Fill the linked note slug or paper ID below only when recent notes do
                    not match the review thread you want.
                  </div>

                  <label className="block">
                    <span className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      <span>Purpose</span>
                      <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-0.5 text-[10px] text-[var(--pp-text-secondary)]">
                        Optional
                      </span>
                    </span>
                    <Input
                      value={createPurpose}
                      onChange={(event) => setCreatePurpose(event.target.value)}
                      placeholder="Optional. What this saved protocol card is meant to support."
                      aria-label="Protocol card purpose"
                    />
                    <span className="mt-1 block text-[11px] text-[var(--pp-text-dim)]">
                      Optional. Add this when the title alone is not enough to explain what this saved snapshot should support later.
                    </span>
                  </label>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        <span>Linked note slug</span>
                        <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-0.5 text-[10px] text-[var(--pp-text-secondary)]">
                          Optional
                        </span>
                      </span>
                      <Input
                        value={createNoteSlug}
                        onChange={(event) => setCreateNoteSlug(event.target.value)}
                        placeholder="leeKetogenicIntervention2024"
                        aria-label="Protocol card linked note slug"
                      />
                    </label>

                    <label className="block">
                      <span className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        <span>Linked paper id</span>
                        <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-0.5 text-[10px] text-[var(--pp-text-secondary)]">
                          Optional
                        </span>
                      </span>
                      <Input
                        value={createPaperId}
                        onChange={(event) => setCreatePaperId(event.target.value)}
                        placeholder="paper-e2e-protocol-browser"
                        aria-label="Protocol card linked paper id"
                      />
                    </label>
                  </div>

                  <p className="text-[11px] text-[var(--pp-text-dim)]">
                    Optional upstream context. Fill one or both when this saved card should stay tied to a specific paper note, or use Recent notes to fill both together.
                  </p>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        <span>Source kind</span>
                        <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-0.5 text-[10px] text-[var(--pp-text-secondary)]">
                          Defaults set
                        </span>
                      </span>
                      <select
                        value={createSourceKind}
                        onChange={(event) => setCreateSourceKind(event.target.value as ProtocolSourceKind)}
                        aria-label="Protocol card source kind"
                        className="h-10 w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-sm text-[var(--pp-text-primary)] outline-none focus:border-[var(--pp-accent-border)]"
                      >
                        <option value="paper_derived">Paper derived</option>
                        <option value="internal_adaptation">Internal adaptation</option>
                        <option value="mixed">Mixed</option>
                      </select>
                    </label>

                    <label className="block">
                      <span className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                        <span>Current version status</span>
                        <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-0.5 text-[10px] text-[var(--pp-text-secondary)]">
                          Defaults set
                        </span>
                      </span>
                      <select
                        value={createVersionStatus}
                        onChange={(event) => setCreateVersionStatus(event.target.value as ProtocolVersionStatus)}
                        aria-label="Protocol card current version status"
                        className="h-10 w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-sm text-[var(--pp-text-primary)] outline-none focus:border-[var(--pp-accent-border)]"
                      >
                        <option value="draft">Draft</option>
                        <option value="active">Active</option>
                      </select>
                    </label>
                  </div>

                  <p className="text-[11px] text-[var(--pp-text-dim)]">
                    Defaults are already safe for most note-backed saves. Only change them when this card is an internal adaptation or already the active working version.
                  </p>

                  <label className="block">
                    <span className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                      <span>Key steps</span>
                      <span className="rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2 py-0.5 text-[10px] text-[var(--pp-text-secondary)]">
                        Optional
                      </span>
                    </span>
                    <textarea
                      value={createKeySteps}
                      onChange={(event) => setCreateKeySteps(event.target.value)}
                      placeholder={"Prepare cortical neurons\nApply ketone ester pulse\nCollect BHB readout"}
                      aria-label="Protocol card key steps"
                      className="min-h-[112px] w-full rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-sm text-[var(--pp-text-primary)] outline-none placeholder:text-[var(--pp-text-dim)] focus:border-[var(--pp-accent-border)]"
                    />
                    <span className="mt-1 block text-[11px] text-[var(--pp-text-dim)]">
                      Optional. Save a skim-friendly step skeleton here when you want faster revisit than rereading the full version snapshot.
                    </span>
                  </label>

                  {createError ? (
                    <div className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3 text-sm text-[var(--pp-warning-text)]">
                      {createError}
                    </div>
                  ) : null}

                  <Button type="submit" size="sm" disabled={creatingProtocolCard}>
                    {creatingProtocolCard ? "Creating protocol card…" : "Create protocol card"}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-3">
            {loading ? (
              <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                <CardContent className="py-8 text-sm text-[var(--pp-text-secondary)]">Loading protocol cards…</CardContent>
              </Card>
            ) : null}

            {!loading && !error && filteredItems.length === 0 ? (
              <Card className="border-[var(--pp-border)] bg-[var(--pp-surface)]">
                <CardContent className="py-8 text-sm text-[var(--pp-text-secondary)]">
                  {indexResponse && indexResponse.total > 0 ? (
                    <div className="space-y-3">
                      <p>No saved protocol cards matched this search yet. Clear the search or start a new protocol card from the left.</p>
                      {indexSearchQuery.trim() ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          data-testid="protocol-card-clear-search"
                          onClick={() => setIndexSearchQuery("")}
                        >
                          Clear search
                        </Button>
                      ) : null}
                    </div>
                  ) : (
                    "No saved derived protocol cards yet. Start one from the left, then review versions, linked papers, and validation here."
                  )}
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
                    <dd
                      data-testid="protocol-card-index-updated-at"
                      className="mt-1 font-medium text-[var(--pp-text-primary)]"
                    >
                      {formatDateTime(item.updated_at)}
                    </dd>
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
                        <div
                          data-testid="protocol-card-detail-created-at"
                          className="mt-1 text-xs text-[var(--pp-text-secondary)]"
                        >
                          {formatDateTime(selectedVersion.created_at)}
                        </div>
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

                    {selectedVersionAttachmentRefs.length > 0 ? (
                      <Card
                        data-testid="protocol-card-detail-attachments"
                        className="border-[var(--pp-border)] bg-[var(--pp-surface-raised)]"
                      >
                        <CardHeader>
                          <CardTitle className="text-sm">Attachment provenance</CardTitle>
                          <CardDescription>
                            Raw-source attachment bundles preserved for this saved version snapshot.
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          {loadingSelectedVersionAttachments ? (
                            <p className="text-sm text-[var(--pp-text-secondary)]">Loading attachment provenance…</p>
                          ) : null}
                          {selectedVersionAttachmentBundles.map((item) => {
                            const bundle = item.bundle;
                            const displayFilename = bundle?.source_filename ?? item.reference.sourceFilename ?? item.reference.attachmentBundleId;
                            const sourceActions = buildProtocolAttachmentSourceActions({
                              attachmentBundleId: item.reference.attachmentBundleId,
                              mediaType: bundle?.media_type,
                              sourceFilename: bundle?.source_filename ?? item.reference.sourceFilename,
                            });
                            const bundleUrl = getProtocolAttachmentBundleUrl(item.reference.attachmentBundleId);
                            const markdownUrl = bundle?.extracted_markdown_ref
                              ? getProtocolAttachmentMarkdownUrl(item.reference.attachmentBundleId)
                              : null;
                            const bundleWarnings = bundle ? dedupeProtocolAttachmentWarnings(bundle.warnings) : [];

                            return (
                              <article
                                key={item.reference.attachmentBundleId}
                                data-testid="protocol-card-detail-attachment-item"
                                className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3"
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <p className="text-sm font-medium text-[var(--pp-text-primary)]">{displayFilename}</p>
                                    <p className="mt-1 font-mono text-[11px] text-[var(--pp-text-dim)]">
                                      {item.reference.attachmentBundleId}
                                    </p>
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {sourceActions.map((action) => (
                                      <a
                                        key={action.kind}
                                        href={action.href}
                                        target="_blank"
                                        rel="noreferrer"
                                        data-testid={action.testId.replace(
                                          "protocol-card-attachment",
                                          "protocol-card-detail-attachment",
                                        )}
                                        data-priority={action.primary ? "primary" : "secondary"}
                                        className={attachmentActionLinkClassName(action.primary, { raisedSurface: true })}
                                      >
                                        {action.label}
                                        {action.kind === "download" ? (
                                          <ArrowDownToLine className="ml-1.5 h-3.5 w-3.5" />
                                        ) : (
                                          <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                                        )}
                                      </a>
                                    ))}
                                    <a
                                      href={bundleUrl}
                                      target="_blank"
                                      rel="noreferrer"
                                      data-testid="protocol-card-detail-attachment-open-bundle"
                                      className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-[11px] font-medium text-[var(--pp-text-primary)]"
                                    >
                                      Open bundle JSON
                                      <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                                    </a>
                                    {markdownUrl ? (
                                      <a
                                        href={markdownUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                        data-testid="protocol-card-detail-attachment-open-markdown"
                                        className="inline-flex h-8 items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-[11px] font-medium text-[var(--pp-text-primary)]"
                                      >
                                        Open extracted markdown
                                        <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                                      </a>
                                    ) : null}
                                  </div>
                                </div>
                                {bundle ? (
                                  <>
                                    <div
                                      data-testid="protocol-card-detail-attachment-metadata"
                                      className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
                                    >
                                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2">
                                        <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Layer</p>
                                        <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                                          {bundle.layer}
                                        </p>
                                      </div>
                                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2">
                                        <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Byte size</p>
                                        <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                                          {formatByteSize(bundle.byte_size)}
                                        </p>
                                      </div>
                                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2">
                                        <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Extraction</p>
                                        <p className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]">
                                          {bundle.extraction_status}
                                        </p>
                                      </div>
                                      <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-2">
                                        <p className="text-[10px] uppercase tracking-wide text-[var(--pp-text-dim)]">Saved</p>
                                        <p
                                          data-testid="protocol-card-detail-attachment-saved-at"
                                          className="mt-1 text-[11px] font-medium text-[var(--pp-text-primary)]"
                                        >
                                          {formatDateTime(bundle.created_at)}
                                        </p>
                                      </div>
                                    </div>
                                    <p className="mt-2 text-[11px] text-[var(--pp-text-dim)]">
                                      {bundle.extraction_engine
                                        ? `Extraction engine: ${bundle.extraction_engine}`
                                        : "Extraction engine unavailable for this bundle."}
                                    </p>
                                    {bundle.extraction_status === "failed" || bundleWarnings.length > 0 ? (
                                      <div
                                        data-testid="protocol-card-detail-attachment-warnings"
                                        className="mt-2 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] p-3 text-[11px] text-[var(--pp-warning-text)]"
                                      >
                                        {bundle.extraction_status === "failed" ? (
                                          <p className="font-medium">
                                            Automatic text extraction was unavailable. Review the uploaded raw source directly before reuse.
                                          </p>
                                        ) : null}
                                        {bundleWarnings.map((warning) => (
                                          <p key={`${warning.code}-${warning.message}`} className={bundle.extraction_status === "failed" ? "mt-1" : undefined}>
                                            {warning.code}: {warning.message}
                                          </p>
                                        ))}
                                      </div>
                                    ) : null}
                                    {bundle.extracted_markdown_excerpt ? (
                                      <div
                                        data-testid="protocol-card-detail-attachment-preview"
                                        className="mt-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
                                      >
                                        <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
                                          Extracted preview
                                        </p>
                                        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-[var(--pp-text-primary)]">
                                          {bundle.extracted_markdown_excerpt}
                                        </pre>
                                      </div>
                                    ) : null}
                                  </>
                                ) : (
                                  <p
                                    data-testid="protocol-card-detail-attachment-error"
                                    className="mt-3 text-sm text-[var(--pp-warning-text)]"
                                  >
                                    Bundle metadata could not be loaded right now: {item.error ?? "Unknown attachment error"}
                                  </p>
                                )}
                              </article>
                            );
                          })}
                        </CardContent>
                      </Card>
                    ) : null}

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
                          <div
                            data-testid="protocol-card-detail-version-created-at"
                            className="mt-2 text-xs text-[var(--pp-text-secondary)]"
                          >
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
