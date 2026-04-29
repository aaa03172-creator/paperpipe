import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, LayoutGrid } from "lucide-react";
import { getApiErrorMessage, getHealth, getPaperNotesHomeContext, getPapers, logClientUserAction } from "../lib/api";
import { PaperAccessSummaryDisplay, getPaperAccessSummaryDisplay } from "../lib/accessSummary";
import { deriveContentReviewSummary } from "../lib/contentReview";
import { formatPaperNoteTriageLabel, PAPER_NOTE_OPERATOR_TRIAGE_LABELS } from "../lib/paperOperatorState";
import { getPaperNoteOpsReason } from "../lib/paperNoteOps";
import { HomeWorkspaceSummary, PaperNotesHomeContext, PaperNoteOperatorTriageLabel, PaperSummary } from "../lib/types";
import { ContentReviewSummary } from "../components/ContentReviewSummary";
import { OperationalStateSummary } from "../components/OperationalStateSummary";
import { Rail } from "../components/Rail";
import { StatusBadge } from "../components/StatusBadge";
import { StatusChip } from "../components/StatusChip";
import { useAppStore } from "../store/useAppStore";

interface HomeResumeCardModel {
  paperId: string;
  paperTitle: string;
  primaryState: "blocked" | "review" | "reading";
  nextActionLabel: string;
  nextActionHint?: string | null;
  ctaLabel: "Fix blocker" | "Resume review" | "Resume reading";
  accessSummary?: PaperAccessSummaryDisplay | null;
  updatedAt?: string | null;
  focusIssues?: boolean;
  noteSlug?: string | null;
}

interface HomeWorkspaceContextModel {
  savedNotes: number;
  structuredNotes: number;
  needsReview: number;
  blocked: number;
  latestUpdatedAt?: string | null;
  noteContextLimited: boolean;
}

interface HomeWorkspaceMarkerLinkModel {
  key: "starred" | PaperNoteOperatorTriageLabel;
  label: string;
  count: number;
  to: string;
  testId: string;
}

interface HomeWorkspaceMarkerSummaryModel {
  markedPapers: number;
  noteBackedPapers: number;
  links: HomeWorkspaceMarkerLinkModel[];
}

const EMPTY_PAPER_NOTES_HOME_CONTEXT: PaperNotesHomeContext = {
  saved_notes: 0,
  structured_notes: 0,
  latest_note_updated_at: null,
  note_context_limited: false,
  note_slug_by_paper_id: {},
  marker_summary: {
    marked_papers: 0,
    note_backed_papers: 0,
    starred: 0,
    triage_counts: {
      revisit: 0,
      needs_verification: 0,
      experiment_relevant: 0,
    },
  },
};

const LIMITED_PAPER_NOTES_HOME_CONTEXT: PaperNotesHomeContext = {
  saved_notes: 0,
  structured_notes: 0,
  latest_note_updated_at: null,
  note_context_limited: true,
  note_slug_by_paper_id: {},
  marker_summary: {
    marked_papers: 0,
    note_backed_papers: 0,
    starred: 0,
    triage_counts: {
      revisit: 0,
      needs_verification: 0,
      experiment_relevant: 0,
    },
  },
};

const EMPTY_HOME_WORKSPACE_SUMMARY: HomeWorkspaceSummary = {
  saved_notes: 0,
  structured_notes: 0,
  needs_review: 0,
  blocked: 0,
  latest_note_updated_at: null,
  note_context_limited: false,
};

function getContentReviewSummary(paper: PaperSummary) {
  return deriveContentReviewSummary(paper.issues, { issuesLabel: paper.issues_label, issuesState: paper.issues_state });
}

function parseUpdatedAt(updatedAt?: string): number {
  const timestamp = Date.parse(updatedAt ?? "");
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function paperIdVariants(value?: string | null): string[] {
  const text = value?.trim() ?? "";
  if (!text) {
    return [];
  }

  const variants: string[] = [];
  const append = (candidate: string) => {
    const normalized = candidate.trim();
    if (normalized && !variants.includes(normalized)) {
      variants.push(normalized);
    }
  };

  append(text);
  append(text.replaceAll(":", ""));
  if (text.includes(":")) {
    const suffix = text.split(":", 2)[1]?.trim() ?? "";
    append(suffix);
    append(suffix.replaceAll(":", ""));
  }
  return variants;
}

function resolveNoteSlugForPaperId(noteSlugByPaperId: Record<string, string>, paperId?: string | null): string | null {
  for (const candidate of paperIdVariants(paperId)) {
    const slug = noteSlugByPaperId[candidate];
    if (slug) {
      return slug;
    }
  }
  return null;
}

function deriveResumePriority(paper: PaperSummary, noteSlug?: string | null): 3 | 2 | 1 | 0 {
  const contentReview = getContentReviewSummary(paper);
  if (paper.ops_summary?.recommended_action === "repair_stats") {
    return 3;
  }
  if (paper.ops_summary?.recommended_action === "open_workbench" || contentReview.state === "flagged") {
    return 2;
  }
  if (noteSlug) {
    return 1;
  }
  return 0;
}

function buildHomeResumeCardModel(items: PaperSummary[], noteSlugByPaperId: Record<string, string>): HomeResumeCardModel | null {
  const sorted = [...items].sort((left, right) => {
    const priorityDelta =
      deriveResumePriority(right, resolveNoteSlugForPaperId(noteSlugByPaperId, right.paper_id)) -
      deriveResumePriority(left, resolveNoteSlugForPaperId(noteSlugByPaperId, left.paper_id));
    if (priorityDelta !== 0) {
      return priorityDelta;
    }

    const updatedAtDelta = parseUpdatedAt(right.updated_at) - parseUpdatedAt(left.updated_at);
    if (updatedAtDelta !== 0) {
      return updatedAtDelta;
    }

    return left.title.localeCompare(right.title);
  });

  const candidate = sorted[0];
  if (!candidate) {
    return null;
  }

  const noteSlug = resolveNoteSlugForPaperId(noteSlugByPaperId, candidate.paper_id);
  const priority = deriveResumePriority(candidate, noteSlug);
  if (priority <= 0) {
    return null;
  }

  const accessSummary = getPaperAccessSummaryDisplay(candidate.access_summary);
  const resolvedAccessSummary = accessSummary.label === "No route" ? null : accessSummary;

  if (candidate.ops_summary?.recommended_action === "repair_stats") {
    return {
      paperId: candidate.paper_id,
      paperTitle: candidate.title,
      primaryState: "blocked",
      nextActionLabel: noteSlug ? "Next: Repair saved note checks before review." : "Next: Fix the blocker before continuing review.",
      nextActionHint: getPaperNoteOpsReason(candidate.ops_summary) || "Saved checks are missing for the current claims.",
      ctaLabel: "Fix blocker",
      accessSummary: resolvedAccessSummary,
      updatedAt: candidate.updated_at ?? null,
      focusIssues: false,
    };
  }

  const contentReview = getContentReviewSummary(candidate);
  const flagged = contentReview.state === "flagged";
  if (priority === 1 && noteSlug) {
    return {
      paperId: candidate.paper_id,
      paperTitle: candidate.title,
      primaryState: "reading",
      nextActionLabel: "Next: Reopen the saved note and keep reading.",
      nextActionHint: "Land in the saved note first, then move into review when you need deeper evidence validation.",
      ctaLabel: "Resume reading",
      accessSummary: resolvedAccessSummary,
      updatedAt: candidate.updated_at ?? null,
      focusIssues: false,
      noteSlug,
    };
  }

  return {
    paperId: candidate.paper_id,
    paperTitle: candidate.title,
    primaryState: "review",
    nextActionLabel:
      flagged && noteSlug
        ? "Next: Continue review from the saved note thread."
        : flagged
          ? "Next: Review flagged claims and evidence."
          : noteSlug
            ? "Next: Open review from the saved note thread."
            : "Next: Continue evidence review for this paper.",
    nextActionHint: flagged
      ? contentReview.detail ?? `${contentReview.issueCount} claim review flag${contentReview.issueCount === 1 ? "" : "s"} recorded in the current paper summary.`
      : noteSlug
        ? "The saved note is ready for grounded evidence review."
        : "Evidence review is the best next step for this paper.",
    ctaLabel: "Resume review",
    accessSummary: resolvedAccessSummary,
    updatedAt: candidate.updated_at ?? null,
    focusIssues: flagged && contentReview.issueCount > 0,
    noteSlug,
  };
}

function buildWorkspaceSummaryFallback(
  papers: PaperSummary[],
  paperNotesHomeContext: PaperNotesHomeContext,
): HomeWorkspaceSummary {
  let blocked = 0;
  let needsReview = 0;

  for (const paper of papers) {
    if (paper.ops_summary?.state === "action_needed") {
      blocked += 1;
      continue;
    }

    if (getContentReviewSummary(paper).state !== "clear") {
      needsReview += 1;
    }
  }

  return {
    saved_notes: paperNotesHomeContext.saved_notes,
    structured_notes: paperNotesHomeContext.structured_notes,
    needs_review: needsReview,
    blocked,
    latest_note_updated_at: paperNotesHomeContext.latest_note_updated_at ?? null,
    note_context_limited: paperNotesHomeContext.note_context_limited,
  };
}

function buildHomeWorkspaceContextModel(
  workspaceSummary: HomeWorkspaceSummary,
  noteContextLimited: boolean,
): HomeWorkspaceContextModel {
  return {
    savedNotes: workspaceSummary.saved_notes,
    structuredNotes: workspaceSummary.structured_notes,
    needsReview: workspaceSummary.needs_review,
    blocked: workspaceSummary.blocked,
    latestUpdatedAt: workspaceSummary.latest_note_updated_at ?? null,
    noteContextLimited,
  };
}

function buildHomeWorkspaceMarkerSummaryModel(
  paperNotesHomeContext: PaperNotesHomeContext,
): HomeWorkspaceMarkerSummaryModel {
  const markerSummary = paperNotesHomeContext.marker_summary;
  return {
    markedPapers: markerSummary?.marked_papers ?? 0,
    noteBackedPapers: markerSummary?.note_backed_papers ?? 0,
    links: [
      {
        key: "starred",
        label: "Starred",
        count: markerSummary?.starred ?? 0,
        to: "/papers?starred=1",
        testId: "home-workspace-marker-starred",
      },
      ...PAPER_NOTE_OPERATOR_TRIAGE_LABELS.map((label) => ({
        key: label,
        label: formatPaperNoteTriageLabel(label),
        count: markerSummary?.triage_counts?.[label] ?? 0,
        to: `/papers?triage_label=${encodeURIComponent(label)}`,
        testId: `home-workspace-marker-${label.replace(/_/g, "-")}`,
      })),
    ],
  };
}

function formatHomeWorkspaceMarkerDetail(markerSummary: HomeWorkspaceMarkerSummaryModel): string {
  if (markerSummary.markedPapers <= 0) {
    return "No paper-level markers yet. Save a star, triage label, or private note from a paper note when you need a revisit lane.";
  }

  const markedPhrase = markerSummary.markedPapers === 1 ? "paper already carries" : "papers already carry";
  const notePhrase =
    markerSummary.noteBackedPapers <= 0
      ? "No private paper note saved yet."
      : markerSummary.noteBackedPapers === 1
        ? "1 includes a private note."
        : `${markerSummary.noteBackedPapers} include a private note.`;
  return `${markerSummary.markedPapers} ${markedPhrase} paper-level judgment. ${notePhrase}`;
}

export function TriageDashboard() {
  const navigate = useNavigate();
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [paperNotesHomeContext, setPaperNotesHomeContext] = useState<PaperNotesHomeContext>(EMPTY_PAPER_NOTES_HOME_CONTEXT);
  const [workspaceSummary, setWorkspaceSummary] = useState<HomeWorkspaceSummary>(EMPTY_HOME_WORKSPACE_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const searchQuery = useAppStore((state) => state.searchQuery);
  const setSearchQuery = useAppStore((state) => state.setSearchQuery);
  const mockMode = useAppStore((state) => state.mockMode);
  const mockReasons = useAppStore((state) => state.mockReasons);
  const markMockMode = useAppStore((state) => state.markMockMode);
  const clearMockMode = useAppStore((state) => state.clearMockMode);
  const themeMode = useAppStore((state) => state.themeMode);
  const setThemeMode = useAppStore((state) => state.setThemeMode);
  const paperNoteOpsByPaperId = useMemo(
    () =>
      Object.fromEntries(
        papers
          .filter((paper) => paper.ops_summary)
          .map((paper) => [paper.paper_id, paper.ops_summary!]),
      ),
    [papers],
  );

  useEffect(() => {
    let mounted = true;

    async function load() {
      clearMockMode();
      setLoading(true);
      setLoadError(null);

      try {
        const [healthResult, paperResult, paperNotesResult] = await Promise.all([
          getHealth(),
          getPapers({ preferCache: true }),
          getPaperNotesHomeContext(),
        ]);
        if (!mounted) {
          return;
        }

        if (healthResult.isMock) {
          markMockMode(healthResult.reason);
        }
        if (paperResult.isMock) {
          markMockMode(paperResult.reason);
        }
        const primarySurfaceIsMock = healthResult.isMock || paperResult.isMock;
        const noteContextLimited = !primarySurfaceIsMock && paperNotesResult.isMock;
        if (primarySurfaceIsMock && paperNotesResult.isMock) {
          markMockMode(paperNotesResult.reason);
        }

        const resolvedPaperNotesHomeContext =
          primarySurfaceIsMock || !paperNotesResult.isMock
            ? paperNotesResult.data
            : {
                ...LIMITED_PAPER_NOTES_HOME_CONTEXT,
                note_context_limited: noteContextLimited,
              };
        const resolvedWorkspaceSummary = buildWorkspaceSummaryFallback(
          paperResult.data,
          resolvedPaperNotesHomeContext,
        );

        setPapers(paperResult.data);
        setPaperNotesHomeContext(resolvedPaperNotesHomeContext);
        setWorkspaceSummary(resolvedWorkspaceSummary);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setPapers([]);
        setPaperNotesHomeContext(LIMITED_PAPER_NOTES_HOME_CONTEXT);
        setWorkspaceSummary(EMPTY_HOME_WORKSPACE_SUMMARY);
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
  }, [clearMockMode, markMockMode]);

  useEffect(() => {
    document.title = "Triage | Lattice";
  }, []);

  const filteredPapers = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();
    if (!keyword) {
      return papers;
    }
    return papers.filter((paper) => {
      const target = `${paper.title} ${paper.paper_id} ${paper.authors ?? ""}`.toLowerCase();
      return target.includes(keyword);
    });
  }, [papers, searchQuery]);

  const triageSummary = useMemo(() => {
    const counts = {
      repair: 0,
      review: 0,
      ready: 0,
    };

    for (const paper of filteredPapers) {
      if (paper.ops_summary?.state === "action_needed") {
        counts.repair += 1;
        continue;
      }

      const contentReview = getContentReviewSummary(paper);
      if (contentReview.state !== "clear") {
        counts.review += 1;
        continue;
      }

      counts.ready += 1;
    }

    return counts;
  }, [filteredPapers]);

  const paperNoteSlugByPaperId = useMemo(() => paperNotesHomeContext.note_slug_by_paper_id ?? {}, [paperNotesHomeContext]);

  const homeResumeCard = useMemo(() => buildHomeResumeCardModel(papers, paperNoteSlugByPaperId), [paperNoteSlugByPaperId, papers]);
  const homeWorkspaceContext = useMemo(
    () =>
      buildHomeWorkspaceContextModel(
        workspaceSummary,
        paperNotesHomeContext.note_context_limited || workspaceSummary.note_context_limited,
      ),
    [paperNotesHomeContext.note_context_limited, workspaceSummary],
  );
  const homeWorkspaceMarkers = useMemo(
    () => buildHomeWorkspaceMarkerSummaryModel(paperNotesHomeContext),
    [paperNotesHomeContext],
  );

  const startLinks = [
    {
      to: "/papers#import-pdf",
      title: "Add your PDF",
      detail: "Import one paper, open the saved note right away, then continue into review when you need evidence work.",
    },
    {
      to: "/papers",
      title: "Browse Paper Notes",
      detail: "Open saved notes, keep reading, or move into review when a paper needs evidence work.",
    },
    {
      to: "/ready",
      title: "Runtime checks",
      detail: "Check live runs, pickup setup, and storage paths before you rely on this local runtime.",
    },
  ] as const;

  const toolLinks = [
    { to: "/meeting-packs", label: "Meeting Packs" },
    { to: "/method-comparisons", label: "Method Comparisons" },
    { to: "/chart-packs", label: "Chart Packs" },
    { to: "/image-evidence", label: "Image Evidence" },
    { to: "/protocol-cards", label: "Protocol Cards" },
  ] as const;

  function moveToWorkbench(paperId: string, options?: { focusIssues?: boolean; origin?: string }) {
    logClientUserAction({
      paper_id: paperId,
      action_type: options?.focusIssues ? "open_workbench_focus_issues" : "open_workbench",
      payload: {
        origin: options?.origin ?? "triage_dashboard",
        focus_issues: options?.focusIssues === true,
      },
    });
    const encoded = encodeURIComponent(paperId);
    if (options?.focusIssues) {
      navigate(`/workbench/${encoded}?focus=issues`);
      return;
    }
    navigate(`/workbench/${encoded}`);
  }

  function reviewIssueButtonClassName(paper: PaperSummary): string {
    const summary = getContentReviewSummary(paper);
    if (summary.state === "flagged") {
      return "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]";
    }
    if (summary.state === "unavailable") {
      return "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-dim)]";
    }
    return "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]";
  }

  function getPrimaryNextAction(paper: PaperSummary): { label: string; className: string } {
    const contentReview = getContentReviewSummary(paper);
    if (paper.ops_summary?.recommended_action === "repair_stats") {
      return {
        label: "Repair stats",
        className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
      };
    }

    if (paper.ops_summary?.recommended_action === "open_workbench") {
      return {
        label: "Open workbench",
        className: "border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]",
      };
    }

    if (contentReview.state === "flagged") {
      return {
        label: contentReview.reviewLabel,
        className: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
      };
    }

    return {
      label: "Open workbench",
      className: "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]",
    };
  }

  function handleHomeResumeCardClick(card: HomeResumeCardModel) {
    if (card.primaryState === "reading" && card.noteSlug) {
      navigate(`/papers/${encodeURIComponent(card.noteSlug)}`);
      return;
    }
    moveToWorkbench(card.paperId, {
      focusIssues: card.focusIssues === true,
      origin: card.primaryState === "blocked" ? "home_resume_card_blocked" : "home_resume_card_review",
    });
  }

  function formatUpdatedAt(updatedAt?: string): string {
    if (!updatedAt) {
      return "-";
    }
    return new Date(updatedAt).toLocaleString();
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="max-w-2xl">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <LayoutGrid className="h-3.5 w-3.5" />
              Paper-first workspace
            </p>
            <h1 className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">
              Start with one paper and keep the evidence thread intact
            </h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Bring a PDF into Paper Notes, land in the saved note, then open the workbench when you need grounded claims, source-backed evidence, or saved outputs.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mockMode ? (
              <span className="inline-flex items-center rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-2.5 py-1 text-xs text-[var(--pp-warning-text)]">
                Mock mode
              </span>
            ) : null}
            <label className="inline-flex items-center gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2 py-1.5 text-xs text-[var(--pp-text-secondary)]">
              Theme
              <select
                value={themeMode}
                onChange={(event) => setThemeMode(event.target.value as "dark" | "light" | "system")}
                className="bg-transparent text-[var(--pp-text-primary)] outline-none"
              >
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System</option>
              </select>
            </label>
          </div>
        </div>
        {mockMode && mockReasons.length > 0 ? (
          <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{mockReasons.join(" / ")}</p>
        ) : null}
        {loadError ? (
          <p className="mt-2 text-xs text-[var(--pp-status-failed-text)]">API error: {loadError}</p>
        ) : null}

        <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
          <section className="rounded-xl border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
            {homeResumeCard ? (
              <div data-testid="home-resume-card">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Continue current work</p>
                <p
                  data-testid="home-resume-title"
                  className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]"
                >
                  {homeResumeCard.paperTitle}
                </p>
                <p
                  data-testid="home-resume-next-action"
                  className="mt-3 text-sm font-medium text-[var(--pp-text-primary)]"
                >
                  {homeResumeCard.nextActionLabel}
                </p>
                {homeResumeCard.nextActionHint ? (
                  <p
                    data-testid="home-resume-hint"
                    className="mt-1 text-sm text-[var(--pp-text-secondary)]"
                  >
                    {homeResumeCard.nextActionHint}
                  </p>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <StatusBadge
                    label={
                      homeResumeCard.primaryState === "blocked"
                        ? "Blocked"
                        : homeResumeCard.primaryState === "review"
                          ? "Needs review"
                          : "Ready"
                    }
                    tone={
                      homeResumeCard.primaryState === "blocked"
                        ? "warning"
                        : homeResumeCard.primaryState === "review"
                          ? "processing"
                          : "success"
                    }
                    className="px-2"
                  />
                  {homeResumeCard.accessSummary ? (
                    <StatusBadge
                      label={homeResumeCard.accessSummary.label}
                      tone={homeResumeCard.accessSummary.tone}
                      className="px-2"
                    />
                  ) : null}
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0 text-xs text-[var(--pp-text-dim)]">
                    {homeResumeCard.updatedAt ? `Updated ${formatUpdatedAt(homeResumeCard.updatedAt)}` : "Continue from the latest saved note or review thread."}
                    {homeResumeCard.accessSummary?.href && homeResumeCard.accessSummary.linkLabel ? (
                      <>
                        {" · "}
                        <a
                          href={homeResumeCard.accessSummary.href}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--pp-accent-text)] underline underline-offset-2"
                        >
                          {homeResumeCard.accessSummary.linkLabel}
                        </a>
                      </>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleHomeResumeCardClick(homeResumeCard)}
                    data-testid="home-resume-cta"
                    className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 py-2 text-sm font-medium text-[var(--pp-accent-text)]"
                  >
                    {homeResumeCard.ctaLabel}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Start here</p>
                    <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
                      If you are new here, import one paper, land in its saved note, then continue in review when you need evidence work.
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-3">
                  {startLinks.map((link) => (
                    <Link
                      key={link.title}
                      to={link.to}
                      className="rounded-lg border border-[var(--pp-border)] bg-[var(--pp-surface)] p-3 transition-colors hover:border-[var(--pp-accent-border)] hover:bg-[var(--pp-accent-soft)]"
                    >
                      <p className="text-sm font-medium text-[var(--pp-text-primary)]">{link.title}</p>
                      <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">{link.detail}</p>
                    </Link>
                  ))}
                </div>
              </>
            )}
          </section>

          <div className="space-y-3">
            <section
              data-testid="home-workspace-context"
              className="rounded-xl border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Workspace context</p>
              <p
                data-testid="home-workspace-context-summary"
                className="mt-1 text-sm text-[var(--pp-text-secondary)]"
              >
                {homeWorkspaceContext.noteContextLimited
                  ? "Saved note context is limited right now, so reopen reading from Paper Notes directly while current review load still reflects the live workspace."
                  : homeWorkspaceContext.savedNotes > 0
                    ? "This home stays paper-first. Saved notes show where to reopen reading, paper markers show what is already active, and review load shows what may need evidence work next."
                    : "This home still starts from papers. Import one paper, land in the saved note, then use review load to decide what to continue next."}
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Saved notes</p>
                  <p
                    data-testid="home-workspace-context-saved-notes"
                    className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]"
                  >
                    {homeWorkspaceContext.noteContextLimited ? "Unavailable" : homeWorkspaceContext.savedNotes}
                  </p>
                </div>
                <div className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Structured notes</p>
                  <p
                    data-testid="home-workspace-context-structured-notes"
                    className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]"
                  >
                    {homeWorkspaceContext.noteContextLimited ? "Unavailable" : homeWorkspaceContext.structuredNotes}
                  </p>
                </div>
                <div className="rounded-md border border-[var(--pp-status-processing-border)] bg-[var(--pp-status-processing-bg)] px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-status-processing-text)]">Needs review</p>
                  <p
                    data-testid="home-workspace-context-needs-review"
                    className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]"
                  >
                    {homeWorkspaceContext.needsReview}
                  </p>
                </div>
                <div className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-warning-text)]">Blocked</p>
                  <p
                    data-testid="home-workspace-context-blocked"
                    className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]"
                  >
                    {homeWorkspaceContext.blocked}
                  </p>
                </div>
              </div>
              {homeWorkspaceContext.noteContextLimited ? (
                <div
                  data-testid="home-workspace-marker-limited"
                  className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-2"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Paper markers</p>
                  <p className="mt-1 text-xs text-[var(--pp-text-secondary)]">
                    Paper-level markers are unavailable while saved note context is limited. Open Paper Notes directly to reopen a saved note or check starred and triaged papers right now.
                  </p>
                </div>
              ) : (
                <div
                  data-testid="home-workspace-marker-summary"
                  className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Paper markers</p>
                      <p
                        data-testid="home-workspace-marker-detail"
                        className="mt-1 text-xs text-[var(--pp-text-secondary)]"
                      >
                        {formatHomeWorkspaceMarkerDetail(homeWorkspaceMarkers)}
                      </p>
                    </div>
                    <Link
                      to="/papers"
                      className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)] transition-colors hover:bg-[var(--pp-surface-muted)]"
                    >
                      Open paper notes
                    </Link>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {homeWorkspaceMarkers.links.map((link) => (
                      <Link
                        key={link.key}
                        to={link.to}
                        data-testid={link.testId}
                        className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 transition-colors hover:bg-[var(--pp-surface-muted)]"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">{link.label}</p>
                        <p className="mt-1 text-base font-semibold text-[var(--pp-text-primary)]">{link.count}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <p data-testid="home-workspace-context-detail" className="text-xs text-[var(--pp-text-dim)]">
                  {homeWorkspaceContext.noteContextLimited
                    ? "Saved note detail is limited on this machine. Browse Paper Notes directly to reopen a saved note or verify note-level detail before moving into review."
                    : homeWorkspaceContext.latestUpdatedAt
                      ? `Latest saved note updated ${formatUpdatedAt(homeWorkspaceContext.latestUpdatedAt)}. Reopen a saved note to keep reading, or move into review when a paper needs evidence work.`
                      : "No saved note context yet. Import one paper, land in the saved note, then continue into review."}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to="/papers"
                    className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)] transition-colors hover:bg-[var(--pp-surface-muted)]"
                  >
                    Browse Paper Notes
                  </Link>
                  <a
                    href="#home-queue-lens"
                    data-testid="home-workspace-context-action-list-link"
                    className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)] transition-colors hover:bg-[var(--pp-surface-muted)]"
                  >
                    Jump to queue lens
                  </a>
                </div>
              </div>
            </section>

            <section
              data-testid="home-saved-outputs"
              className="rounded-xl border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Saved outputs</p>
              <p data-testid="home-saved-outputs-summary" className="mt-1 text-sm text-[var(--pp-text-secondary)]">
                Open saved outputs after you finish the current paper thread, whether that means reading, review, or blocker repair.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {toolLinks.map((link) => (
                  <Link
                    key={link.label}
                    to={link.to}
                    className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)] transition-colors hover:bg-[var(--pp-surface-muted)]"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </div>
      </header>

      <main id="home-queue-lens" className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
        <div className="min-h-0">
          <Rail
            papers={filteredPapers}
            paperNoteOpsByPaperId={paperNoteOpsByPaperId}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onSelectPaper={(paperId) => moveToWorkbench(paperId, { origin: "triage_rail" })}
          />
        </div>

        <section className="surface-card min-h-0 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">Queue lens</h2>
              <p className="mt-1 text-xs text-[var(--pp-text-dim)]">
                Operational view over current papers. Search narrows this queue without changing workspace context.
              </p>
            </div>
            <p className="text-xs text-[var(--pp-text-dim)]">{filteredPapers.length} results</p>
          </div>

          {loading ? (
            <p className="text-sm text-[var(--pp-text-dim)]">Loading papers, notes, and saved outputs...</p>
          ) : (
            <div className="space-y-3">
              <div
                data-testid="triage-summary-strip"
                className="grid gap-2 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-2 sm:grid-cols-3"
              >
                <div
                  data-testid="triage-summary-repair"
                  className="rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2.5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-warning-text)]">
                    Needs repair
                  </p>
                  <p className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{triageSummary.repair}</p>
                  <p className="mt-1 text-xs text-[var(--pp-warning-text)]">Stats or note fixes block review.</p>
                </div>

                <div
                  data-testid="triage-summary-review"
                  className="rounded-md border border-[var(--pp-status-processing-border)] bg-[var(--pp-status-processing-bg)] px-3 py-2.5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-status-processing-text)]">
                    Needs review
                  </p>
                  <p className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{triageSummary.review}</p>
                  <p className="mt-1 text-xs text-[var(--pp-status-processing-text)]">
                    Claims, mappings, or review checks still need a human pass.
                  </p>
                </div>

                <div
                  data-testid="triage-summary-ready"
                  className="rounded-md border border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] px-3 py-2.5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-status-completed-text)]">
                    Ready
                  </p>
                  <p className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{triageSummary.ready}</p>
                  <p className="mt-1 text-xs text-[var(--pp-status-completed-text)]">
                    No repair or review blockers are visible before you open notes or workbench.
                  </p>
                </div>
              </div>

              <div className="space-y-2 md:hidden">
                {filteredPapers.map((paper) => {
                  const contentReview = getContentReviewSummary(paper);
                  const primaryAction = getPrimaryNextAction(paper);
                  const accessSummary = getPaperAccessSummaryDisplay(paper.access_summary);
                  return (
                    <article key={paper.paper_id} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="line-clamp-2 text-sm font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
                        <p className="mt-1 truncate text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
                      </div>
                      <StatusChip status={paper.status ?? "not_started"} />
                    </div>

                    <div className="mt-2">
                      <OperationalStateSummary
                        summary={paperNoteOpsByPaperId[paper.paper_id]}
                        badgeTestId="triage-ops-badge"
                        reasonTestId="triage-ops-reason"
                        compact
                      />
                    </div>

                    <p data-testid="triage-updated-at" className="mt-2 text-xs text-[var(--pp-text-dim)]">
                      Updated: {formatUpdatedAt(paper.updated_at)}
                    </p>

                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <StatusBadge label={accessSummary.label} tone={accessSummary.tone} className="px-2" testId="triage-access-badge" />
                      {accessSummary.href ? (
                        <a
                          href={accessSummary.href}
                          target="_blank"
                          rel="noreferrer"
                          data-testid="triage-access-link"
                          className="text-xs text-[var(--pp-accent-text)] underline underline-offset-2"
                        >
                          {accessSummary.linkLabel}
                        </a>
                      ) : null}
                    </div>

                    <div className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] p-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">Content review</p>
                      </div>
                      <ContentReviewSummary
                        summary={contentReview}
                        badgeTestId="triage-review-badge"
                        hintTestId="triage-review-hint"
                        detailTestId="triage-review-detail"
                        className="mt-1"
                        compact
                      />
                      <div className="mt-3 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)] px-2.5 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">
                          Primary next action
                        </p>
                        <p
                          data-testid="triage-primary-action"
                          className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-xs ${primaryAction.className}`}
                        >
                          {primaryAction.label}
                        </p>
                      </div>
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        <button
                          type="button"
                          onClick={() => moveToWorkbench(paper.paper_id, { origin: "triage_mobile_open" })}
                          className="inline-flex items-center justify-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-2 text-xs font-medium text-[var(--pp-accent-text)]"
                        >
                          Open Workbench
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveToWorkbench(paper.paper_id, { focusIssues: true, origin: "triage_mobile_content_review" })}
                          disabled={contentReview.issueCount === 0}
                          data-testid="triage-content-review-button"
                          className={[
                            "inline-flex items-center justify-center rounded-md border px-2.5 py-2 text-xs",
                            reviewIssueButtonClassName(paper),
                          ].join(" ")}
                        >
                          {contentReview.reviewLabel}
                        </button>
                      </div>
                    </div>
                    </article>
                  );
                })}
              </div>

              <div className="hidden overflow-auto rounded-md border border-[var(--pp-border)] md:block">
                <table className="w-full min-w-[760px] border-collapse text-sm">
                  <thead className="bg-[var(--pp-surface-muted)] text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">
                    <tr>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Paper</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Status</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Claim review</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-left">Updated</th>
                      <th className="border-b border-[var(--pp-border)] px-3 py-2 text-right">Open</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPapers.map((paper) => {
                      const contentReview = getContentReviewSummary(paper);
                      const primaryAction = getPrimaryNextAction(paper);
                      const accessSummary = getPaperAccessSummaryDisplay(paper.access_summary);
                      return (
                      <tr
                        key={paper.paper_id}
                        className="cursor-pointer bg-[var(--pp-surface-raised)] hover:bg-[var(--pp-surface-selected)]"
                        onClick={() => moveToWorkbench(paper.paper_id, { origin: "triage_table_row" })}
                      >
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <p className="font-medium text-[var(--pp-text-primary)]">{paper.title}</p>
                          <p className="text-xs text-[var(--pp-text-dim)]">{paper.paper_id}</p>
                          <div className="mt-2">
                            <OperationalStateSummary
                              summary={paperNoteOpsByPaperId[paper.paper_id]}
                              badgeTestId="triage-ops-badge"
                              reasonTestId="triage-ops-reason"
                              compact
                            />
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <StatusBadge
                              label={accessSummary.label}
                              tone={accessSummary.tone}
                              className="px-2"
                              testId="triage-access-badge"
                            />
                            {accessSummary.href ? (
                              <a
                                href={accessSummary.href}
                                target="_blank"
                                rel="noreferrer"
                                data-testid="triage-access-link"
                                onClick={(event) => event.stopPropagation()}
                                className="text-xs text-[var(--pp-accent-text)] underline underline-offset-2"
                              >
                                {accessSummary.linkLabel}
                              </a>
                            ) : null}
                          </div>
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <StatusChip status={paper.status ?? "not_started"} />
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveToWorkbench(paper.paper_id, { focusIssues: true, origin: "triage_table_content_review" });
                            }}
                            disabled={contentReview.issueCount === 0}
                            data-testid="triage-content-review-button"
                            className={[
                              "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
                              reviewIssueButtonClassName(paper),
                            ].join(" ")}
                          >
                            {contentReview.reviewLabel}
                          </button>
                          <ContentReviewSummary
                            summary={contentReview}
                            badgeTestId="triage-review-badge"
                            hintTestId="triage-review-hint"
                            detailTestId="triage-review-detail"
                            className="mt-1"
                            compact
                          />
                        </td>
                        <td
                          data-testid="triage-updated-at"
                          className="border-b border-[var(--pp-border)] px-3 py-3 text-xs text-[var(--pp-text-dim)]"
                        >
                          {formatUpdatedAt(paper.updated_at)}
                        </td>
                        <td className="border-b border-[var(--pp-border)] px-3 py-3 text-right">
                          <div className="grid justify-items-end gap-2">
                            <div className="text-right">
                              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">
                                Primary next action
                              </p>
                              <p
                                data-testid="triage-primary-action"
                                className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-xs ${primaryAction.className}`}
                              >
                                {primaryAction.label}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                moveToWorkbench(paper.paper_id, { origin: "triage_table_open" });
                              }}
                              className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs font-medium text-[var(--pp-accent-text)]"
                            >
                              Open Workbench
                              <ArrowRight className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
