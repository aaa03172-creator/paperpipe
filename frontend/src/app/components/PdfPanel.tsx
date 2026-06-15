import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { FileWarning, Link2 } from "lucide-react";
import { circledNumber } from "../lib/ui";
import { EvidenceHighlight, NotebookClaim } from "../lib/types";
import { pickBestHighlightForClaim } from "../lib/claimGuard";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

const pdfDocumentOptions = {
  isEvalSupported: false,
};

function getInitialPdfPageWidth(): number {
  if (typeof window === "undefined") {
    return 760;
  }
  return Math.max(280, Math.min(760, window.innerWidth - 60));
}

interface PdfPanelProps {
  title: string;
  paperId: string;
  pdfUrl: string;
  pdfAvailable: boolean;
  placeholderNotice?: string | null;
  claims: NotebookClaim[];
  highlights: EvidenceHighlight[];
  activeClaimId: string | null;
  highlightMode: "soft" | "focus";
}

interface TextMatchSnippet {
  key: string;
  globalIndex: number;
  pageIndex: number;
  preview: string;
}

interface HighlightArea {
  pageIndex: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

interface TextMatch {
  pageIndex: number;
  startIndex: number;
  endIndex: number;
  pageText: string;
}

interface LoadedPdfPage {
  getTextContent(): Promise<{ items: Array<{ str?: string }> }>;
}

interface LoadedPdfDocument {
  numPages: number;
  getPage(pageNumber: number): Promise<LoadedPdfPage>;
}

function clampPct(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function normalizeBBoxPct(
  left: number,
  top: number,
  width: number,
  height: number,
): Pick<HighlightArea, "left" | "top" | "width" | "height"> {
  const safeLeft = clampPct(left);
  const safeTop = clampPct(top);
  const safeWidth = clampPct(width);
  const safeHeight = clampPct(height);
  return {
    left: safeLeft,
    top: safeTop,
    width: clampPct(Math.min(safeWidth, 100 - safeLeft)),
    height: clampPct(Math.min(safeHeight, 100 - safeTop)),
  };
}

function normalizeSearchText(text: string | null | undefined): string | null {
  if (!text) {
    return null;
  }
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length < 4) {
    return null;
  }
  return compact.length > 180 ? compact.slice(0, 180) : compact;
}

function buildSearchKeywords(primary: string | null | undefined, fallback: string | null | undefined): string[] {
  const normalizedPrimary = normalizeSearchText(primary);
  const normalizedFallback = normalizeSearchText(fallback);
  const source = normalizedPrimary ?? normalizedFallback;
  if (!source) {
    return [];
  }

  const phraseKeywords = [
    normalizedPrimary,
    normalizedFallback,
  ].filter((item): item is string => Boolean(item));

  const cleaned = source.replace(/[^A-Za-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
  const words = cleaned.split(" ").filter((word) => word.length > 2);
  if (words.length === 0) {
    return Array.from(new Set(phraseKeywords));
  }

  const candidates = [
    words.slice(0, 12).join(" "),
    words.slice(0, 8).join(" "),
    words.slice(0, 6).join(" "),
    words.slice(0, 4).join(" "),
  ];
  return Array.from(new Set([...phraseKeywords, ...candidates.filter((item) => item.length >= 8)])).slice(0, 10);
}

function toHighlightArea(activeHighlight: EvidenceHighlight | null): HighlightArea | null {
  if (!activeHighlight) {
    return null;
  }
  if (activeHighlight.source === "text_match") {
    return null;
  }
  if (activeHighlight.width <= 0 || activeHighlight.height <= 0) {
    return null;
  }
  const normalized = normalizeBBoxPct(
    activeHighlight.left,
    activeHighlight.top,
    activeHighlight.width,
    activeHighlight.height,
  );
  return {
    pageIndex: Math.max(0, activeHighlight.page - 1),
    left: normalized.left,
    top: normalized.top,
    width: normalized.width,
    height: normalized.height,
  };
}

function buildTextMatchPreview(match: TextMatch): string {
  const pageText = match.pageText;
  if (!pageText) {
    return "";
  }
  const start = Math.max(match.startIndex - 72, 0);
  const end = Math.min(match.endIndex + 84, pageText.length);
  const raw = pageText.slice(start, end).replace(/\s+/g, " ").trim();
  if (!raw) {
    return "";
  }
  const prefix = start > 0 ? "..." : "";
  const suffix = end < pageText.length ? "..." : "";
  return `${prefix}${raw}${suffix}`;
}

function findTextMatches(pageText: string, pageIndex: number, keywords: string[]): TextMatch[] {
  const lowerPageText = pageText.toLowerCase();
  const matches: TextMatch[] = [];
  const seen = new Set<string>();

  keywords.forEach((keyword) => {
    const normalizedKeyword = keyword.replace(/\s+/g, " ").trim().toLowerCase();
    if (!normalizedKeyword) {
      return;
    }
    let startIndex = lowerPageText.indexOf(normalizedKeyword);
    while (startIndex >= 0) {
      const endIndex = startIndex + normalizedKeyword.length;
      const key = `${startIndex}:${endIndex}`;
      if (!seen.has(key)) {
        seen.add(key);
        matches.push({ pageIndex, startIndex, endIndex, pageText });
      }
      startIndex = lowerPageText.indexOf(normalizedKeyword, startIndex + normalizedKeyword.length);
    }
  });

  return matches;
}

function normalizeRankingText(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function tokenizeRankingText(text: string): string[] {
  return normalizeRankingText(text)
    .split(" ")
    .map((item) => item.trim())
    .filter((item) => item.length > 2);
}

function scoreSnippet({
  preview,
  pageIndex,
  preferredPageIndex,
  rankingText,
}: {
  preview: string;
  pageIndex: number;
  preferredPageIndex: number;
  rankingText: string;
}): number {
  let score = 0;
  if (pageIndex === preferredPageIndex) {
    score += 2.2;
  } else if (Math.abs(pageIndex - preferredPageIndex) === 1) {
    score += 0.7;
  }

  const normalizedPreview = normalizeRankingText(preview);
  const normalizedRankingText = normalizeRankingText(rankingText);
  if (normalizedPreview && normalizedRankingText && normalizedPreview.includes(normalizedRankingText)) {
    score += 4.0;
  }

  const rankingTokens = new Set(tokenizeRankingText(rankingText));
  if (rankingTokens.size > 0 && normalizedPreview) {
    const previewTokens = new Set(tokenizeRankingText(preview));
    let overlapCount = 0;
    rankingTokens.forEach((token) => {
      if (previewTokens.has(token)) {
        overlapCount += 1;
      }
    });
    score += (overlapCount / rankingTokens.size) * 2.6;
  }

  return score;
}

function buildTextMatchSnippets(
  matches: TextMatch[],
  rankingText: string,
  preferredPageIndex: number,
): TextMatchSnippet[] {
  const seen = new Set<string>();
  const scoredSnippets: Array<TextMatchSnippet & { score: number }> = [];
  matches.forEach((match, globalIndex) => {
    const key = `${match.pageIndex}:${match.startIndex}:${match.endIndex}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    const preview = buildTextMatchPreview(match);
    scoredSnippets.push({
      key,
      globalIndex,
      pageIndex: match.pageIndex,
      preview: preview || `Match on page ${match.pageIndex + 1}`,
      score: scoreSnippet({
        preview,
        pageIndex: match.pageIndex,
        preferredPageIndex,
        rankingText,
      }),
    });
  });
  const top = [...scoredSnippets]
    .sort((a, b) => b.score - a.score || a.globalIndex - b.globalIndex)
    .slice(0, 10)
    .map((item) => item.key);
  const topKeySet = new Set(top);
  return scoredSnippets
    .filter((item) => topKeySet.has(item.key))
    .sort((a, b) => a.globalIndex - b.globalIndex)
    .map((item) => ({
      key: item.key,
      globalIndex: item.globalIndex,
      pageIndex: item.pageIndex,
      preview: item.preview,
    }));
}

function pickPreferredSnippet(
  snippets: TextMatchSnippet[],
  rankingText: string,
  preferredPageIndex: number,
): TextMatchSnippet | null {
  if (snippets.length === 0) {
    return null;
  }
  const scored = snippets
    .map((snippet) => ({
      snippet,
      score: scoreSnippet({
        preview: snippet.preview,
        pageIndex: snippet.pageIndex,
        preferredPageIndex,
        rankingText,
      }),
    }))
    .sort((a, b) => b.score - a.score || a.snippet.globalIndex - b.snippet.globalIndex);
  return scored[0]?.snippet ?? snippets[0] ?? null;
}

export function PdfPanel({
  title,
  paperId,
  pdfUrl,
  pdfAvailable,
  placeholderNotice,
  claims,
  highlights,
  activeClaimId,
  highlightMode,
}: PdfPanelProps) {
  const [loadedPdfMeta, setLoadedPdfMeta] = useState<{ url: string; pageCount: number } | null>(null);
  const [loadedPdfDoc, setLoadedPdfDoc] = useState<LoadedPdfDocument | null>(null);
  const [searchMeta, setSearchMeta] = useState<{ claimKey: string; count: number } | null>(null);
  const [textMatchSnippets, setTextMatchSnippets] = useState<TextMatchSnippet[]>([]);
  const [activeTextMatchIndex, setActiveTextMatchIndex] = useState<number | null>(null);
  const [visiblePageIndex, setVisiblePageIndex] = useState(0);
  const [pageRenderWidth, setPageRenderWidth] = useState(getInitialPdfPageWidth);
  const viewerContainerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef(new Map<number, HTMLDivElement>());
  const activeClaim = useMemo(
    () => claims.find((claim) => claim.claim_id === activeClaimId) ?? null,
    [claims, activeClaimId],
  );
  const activeHighlight = useMemo(
    () => pickBestHighlightForClaim(highlights, activeClaimId),
    [highlights, activeClaimId],
  );
  const activeClaimIndex = useMemo(
    () => claims.findIndex((claim) => claim.claim_id === activeClaimId),
    [claims, activeClaimId],
  );
  const activeClaimLabel = activeClaimIndex >= 0 ? circledNumber(activeClaimIndex) : null;
  const searchKeywords = useMemo(
    () => buildSearchKeywords(activeHighlight?.quote ?? null, activeClaim?.text ?? null),
    [activeHighlight, activeClaim],
  );
  const rankingText = useMemo(
    () => `${activeHighlight?.quote ?? ""} ${activeClaim?.text ?? ""}`.trim(),
    [activeHighlight?.quote, activeClaim?.text],
  );
  const claimKey = activeClaimId ?? "__none";
  const searchMatchCount = searchMeta?.claimKey === claimKey ? searchMeta.count : 0;
  const activePageIndex = useMemo(() => Math.max((activeHighlight?.page ?? 1) - 1, 0), [activeHighlight]);
  const activeArea = useMemo(() => toHighlightArea(activeHighlight), [activeHighlight]);
  const textMatchMode = activeHighlight?.source === "text_match";
  const pageCount = loadedPdfMeta?.url === pdfUrl ? loadedPdfMeta.pageCount : null;
  const resolvedActivePageIndex = useMemo(() => {
    if (!pageCount || pageCount < 1) {
      return activePageIndex;
    }
    return Math.min(activePageIndex, pageCount - 1);
  }, [activePageIndex, pageCount]);

  const resolvedActiveArea = useMemo(() => {
    if (!activeArea) {
      return null;
    }
    if (activeArea.pageIndex === resolvedActivePageIndex) {
      return activeArea;
    }
    return {
      ...activeArea,
      pageIndex: resolvedActivePageIndex,
    };
  }, [activeArea, resolvedActivePageIndex]);

  const softMode = highlightMode === "soft";
  const selectedBorderWidth = softMode ? 2 : 3;
  const selectedBg = softMode ? "rgba(34, 211, 238, 0.18)" : "rgba(34, 211, 238, 0.30)";
  const selectedShadow = softMode
    ? "0 0 0 1px rgba(34, 211, 238, 0.42), 0 4px 10px rgba(0, 0, 0, 0.26)"
    : "0 0 0 2px rgba(34, 211, 238, 0.55), 0 6px 16px rgba(0, 0, 0, 0.35)";
  const fallbackBorderWidth = softMode ? 2 : 3;
  const fallbackBg = softMode ? "rgba(245, 158, 11, 0.2)" : "rgba(245, 158, 11, 0.34)";
  const fallbackShadow = softMode
    ? "0 0 0 1px rgba(245, 158, 11, 0.42), 0 4px 10px rgba(0, 0, 0, 0.24)"
    : "0 0 0 2px rgba(245, 158, 11, 0.55), 0 6px 16px rgba(0, 0, 0, 0.35)";
  const searchBorder = softMode ? "2px solid rgba(245, 158, 11, 0.84)" : "3px solid rgba(245, 158, 11, 0.95)";
  const searchBg = softMode ? "rgba(245, 158, 11, 0.2)" : "rgba(245, 158, 11, 0.34)";
  const searchShadow = softMode
    ? "0 0 0 1px rgba(245, 158, 11, 0.42), 0 4px 10px rgba(0, 0, 0, 0.24)"
    : "0 0 0 2px rgba(245, 158, 11, 0.55), 0 6px 16px rgba(0, 0, 0, 0.35)";

  const syncSequenceRef = useRef(0);

  const pages = useMemo(
    () => Array.from({ length: pageCount ?? 0 }, (_, pageIndex) => pageIndex),
    [pageCount],
  );

  const setPageRef = useCallback((pageIndex: number, node: HTMLDivElement | null) => {
    if (node) {
      pageRefs.current.set(pageIndex, node);
    } else {
      pageRefs.current.delete(pageIndex);
    }
  }, []);

  const scrollToPage = useCallback((pageIndex: number) => {
    window.requestAnimationFrame(() => {
      pageRefs.current.get(pageIndex)?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }, []);

  const activateSnippet = useCallback(
    (snippet: TextMatchSnippet) => {
      setActiveTextMatchIndex(snippet.globalIndex);
      setVisiblePageIndex(snippet.pageIndex);
      scrollToPage(snippet.pageIndex);
    },
    [scrollToPage],
  );

  useLayoutEffect(() => {
    const container = viewerContainerRef.current;
    if (!container) {
      return;
    }
    const updateWidth = () => {
      const containerMaxWidth = container.clientWidth - 28;
      const viewportMaxWidth = window.innerWidth - 60;
      const nextWidth = Math.max(280, Math.min(920, containerMaxWidth, viewportMaxWidth));
      setPageRenderWidth(nextWidth);
    };
    updateWidth();
    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(container);
    window.addEventListener("resize", updateWidth);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateWidth);
    };
  }, [pdfAvailable, pdfUrl]);

  const activeTextMatchPos = useMemo(() => {
    if (textMatchSnippets.length === 0) {
      return -1;
    }
    if (activeTextMatchIndex === null) {
      return 0;
    }
    const found = textMatchSnippets.findIndex((item) => item.globalIndex === activeTextMatchIndex);
    return found >= 0 ? found : 0;
  }, [textMatchSnippets, activeTextMatchIndex]);
  const activeTextMatchSnippet = activeTextMatchPos >= 0 ? textMatchSnippets[activeTextMatchPos] : null;

  useEffect(() => {
    if (!pdfUrl || loadedPdfMeta?.url !== pdfUrl || !loadedPdfDoc) {
      return;
    }

    const localClaimKey = claimKey;
    const localSequence = syncSequenceRef.current + 1;
    syncSequenceRef.current = localSequence;

    const syncSelection = async () => {
      setVisiblePageIndex(resolvedActivePageIndex);
      scrollToPage(resolvedActivePageIndex);

      if (resolvedActiveArea) {
        setSearchMeta({ claimKey: localClaimKey, count: 0 });
        setTextMatchSnippets([]);
        setActiveTextMatchIndex(null);
        return;
      }

      if (searchKeywords.length === 0) {
        setSearchMeta({ claimKey: localClaimKey, count: 0 });
        setTextMatchSnippets([]);
        setActiveTextMatchIndex(null);
        return;
      }

      setSearchMeta({ claimKey: localClaimKey, count: 0 });
      setTextMatchSnippets([]);
      setActiveTextMatchIndex(null);

      const readPageText = async (pageIndex: number) => {
        const page = await loadedPdfDoc.getPage(pageIndex + 1);
        const textContent = await page.getTextContent();
        return textContent.items
          .map((item) => item.str ?? "")
          .filter(Boolean)
          .join(" ")
          .replace(/\s+/g, " ")
          .trim();
      };

      const preferredPageText = await readPageText(resolvedActivePageIndex);
      let matches = findTextMatches(preferredPageText, resolvedActivePageIndex, searchKeywords);
      if (syncSequenceRef.current !== localSequence) {
        return;
      }
      if (matches.length === 0) {
        const allMatches: TextMatch[] = [];
        for (let pageIndex = 0; pageIndex < loadedPdfDoc.numPages; pageIndex += 1) {
          if (pageIndex === resolvedActivePageIndex) {
            continue;
          }
          const pageText = await readPageText(pageIndex);
          allMatches.push(...findTextMatches(pageText, pageIndex, searchKeywords));
          if (syncSequenceRef.current !== localSequence) {
            return;
          }
        }
        matches = allMatches;
        if (syncSequenceRef.current !== localSequence) {
          return;
        }
      }
      setSearchMeta({ claimKey: localClaimKey, count: matches.length });
      const snippets = buildTextMatchSnippets(matches, rankingText, resolvedActivePageIndex);
      setTextMatchSnippets(snippets);
      const preferredSnippet = pickPreferredSnippet(snippets, rankingText, resolvedActivePageIndex);
      if (preferredSnippet) {
        activateSnippet(preferredSnippet);
      } else {
        setActiveTextMatchIndex(null);
      }
    };

    void syncSelection();
    return () => {
      syncSequenceRef.current += 1;
    };
  }, [
    claimKey,
    loadedPdfDoc,
    loadedPdfMeta?.url,
    pdfUrl,
    rankingText,
    activateSnippet,
    resolvedActiveArea,
    resolvedActivePageIndex,
    searchKeywords,
    scrollToPage,
  ]);

  const viewerKey = pdfUrl;

  const renderHighlightLayer = (pageIndex: number) => {
    const selectedArea = resolvedActiveArea;
    const showSelected = Boolean(selectedArea && pageIndex === selectedArea.pageIndex);
    const showApprox = !selectedArea && searchMatchCount === 0 && pageIndex === resolvedActivePageIndex;
    const showSearch = textMatchMode && activeTextMatchSnippet?.pageIndex === pageIndex;
    if (!showSelected && !showApprox && !showSearch) {
      return null;
    }
    const area: HighlightArea = (showSelected && selectedArea) ? selectedArea : {
      pageIndex,
      left: 6,
      top: 8,
      width: 88,
      height: 10,
    };
    return (
      <div
        data-testid={showSelected ? "claim-highlight" : showSearch ? "claim-search-highlight" : "claim-approx-highlight"}
        className="pointer-events-none absolute rounded-md"
        style={{
          left: `${area.left}%`,
          top: `${area.top}%`,
          width: `${area.width}%`,
          height: `${area.height}%`,
          borderStyle: showApprox ? "dashed" : "solid",
          borderWidth: showSearch ? undefined : showApprox ? fallbackBorderWidth : selectedBorderWidth,
          border: showSearch ? searchBorder : undefined,
          borderColor: showSearch ? undefined : showApprox ? "#f59e0b" : "#22d3ee",
          background: showSearch ? searchBg : showApprox ? fallbackBg : selectedBg,
          boxShadow: showSearch ? searchShadow : showApprox ? fallbackShadow : selectedShadow,
          zIndex: showSearch ? 28 : 30,
        }}
      >
        {showSelected && activeClaimLabel ? (
          <span className="absolute -top-6 left-0 rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--pp-accent-text)] shadow-sm">
            {activeClaimLabel}
          </span>
        ) : null}
      </div>
    );
  };

  return (
    <section className="surface-card flex min-h-0 flex-col p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">PDF Renderer</p>
          <h2 className="mt-1 line-clamp-2 text-sm font-semibold text-[var(--pp-text-primary)]">{title}</h2>
          <p className="mt-0.5 text-xs text-[var(--pp-text-dim)]">{paperId}</p>
        </div>

        {activeHighlight ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-1 text-xs text-[var(--pp-accent-text)]">
            <Link2 className="h-3.5 w-3.5" />
            {textMatchMode ? `Text Match · p.${activeHighlight.page}` : `Claim Link · p.${activeHighlight.page}`}
          </span>
        ) : null}
      </div>

      {textMatchMode ? (
        <div className="mb-2 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="inline-flex rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-surface-raised)] px-2 py-0.5 font-semibold text-[var(--pp-warning-text)]">
              정밀 anchor 아님
            </span>
            <span className="text-[var(--pp-warning-text)]">텍스트 매칭 근거 ({searchMatchCount}건)</span>
            {activeTextMatchSnippet ? (
              <span className="inline-flex rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-surface-raised)] px-2 py-0.5 text-[10px] text-[var(--pp-warning-text)]">
                선택 {activeTextMatchPos + 1}/{textMatchSnippets.length}
              </span>
            ) : null}
          </div>
          {textMatchSnippets.length > 1 ? (
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (textMatchSnippets.length === 0) {
                    return;
                  }
                  const currentPos = activeTextMatchPos >= 0 ? activeTextMatchPos : 0;
                  const nextPos = Math.max(currentPos - 1, 0);
                  activateSnippet(textMatchSnippets[nextPos]);
                }}
                disabled={activeTextMatchPos <= 0}
                className={[
                  "rounded-md border px-2 py-1 text-[10px]",
                  activeTextMatchPos <= 0
                    ? "cursor-not-allowed border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]"
                    : "border-[var(--pp-warning-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-warning-text)]",
                ].join(" ")}
              >
                이전
              </button>
              <button
                type="button"
                onClick={() => {
                  if (textMatchSnippets.length === 0) {
                    return;
                  }
                  const currentPos = activeTextMatchPos >= 0 ? activeTextMatchPos : 0;
                  const nextPos = Math.min(currentPos + 1, textMatchSnippets.length - 1);
                  activateSnippet(textMatchSnippets[nextPos]);
                }}
                disabled={activeTextMatchPos >= textMatchSnippets.length - 1}
                className={[
                  "rounded-md border px-2 py-1 text-[10px]",
                  activeTextMatchPos >= textMatchSnippets.length - 1
                    ? "cursor-not-allowed border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]"
                    : "border-[var(--pp-warning-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-warning-text)]",
                ].join(" ")}
              >
                다음
              </button>
            </div>
          ) : null}
          {textMatchSnippets.length > 0 ? (
            <ul className="mt-2 space-y-1">
              {textMatchSnippets.map((snippet) => (
                <li key={snippet.key}>
                  <button
                    type="button"
                    onClick={() => {
                      activateSnippet(snippet);
                    }}
                    className={[
                      "w-full rounded-md border px-2 py-1.5 text-left text-[11px]",
                      activeTextMatchSnippet?.key === snippet.key
                        ? "border-[var(--pp-accent-border)] bg-[var(--pp-surface-selected)] text-[var(--pp-text-primary)]"
                        : "border-[var(--pp-warning-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-primary)]",
                    ].join(" ")}
                  >
                    <span className="mr-2 inline-flex rounded-full border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--pp-warning-text)]">
                      p.{snippet.pageIndex + 1}
                    </span>
                    {snippet.preview}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[11px] text-[var(--pp-warning-text)]">
              매칭 가능한 문장 구간을 찾는 중입니다.
            </p>
          )}
        </div>
      ) : null}

      {placeholderNotice ? (
        <div className="mb-2 rounded-md border border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] px-3 py-2 text-xs text-[var(--pp-warning-text)]">
          <p className="font-semibold">Placeholder PDF active</p>
          <p className="mt-1">{placeholderNotice}</p>
        </div>
      ) : null}

      <div className="relative min-h-0 flex-1 overflow-hidden rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)]">
        {pdfAvailable && pdfUrl ? (
          <div
            ref={viewerContainerRef}
            data-testid="pdf-viewer"
            className="h-[70vh] min-h-[420px] w-full overflow-auto px-3 py-4 xl:h-[calc(100vh-10rem)]"
          >
            <Document
              key={viewerKey}
              file={pdfUrl}
              options={pdfDocumentOptions}
              loading={
                <div className="flex min-h-[360px] items-center justify-center text-xs text-[var(--pp-text-dim)]">
                  PDF를 불러오는 중입니다.
                </div>
              }
              error={
                <div className="flex min-h-[360px] items-center justify-center text-xs text-[var(--pp-warning-text)]">
                  PDF 렌더링에 실패했습니다.
                </div>
              }
              onLoadSuccess={(pdf) => {
                const loadedDoc = pdf as LoadedPdfDocument;
                setLoadedPdfMeta({ url: pdfUrl, pageCount: loadedDoc.numPages });
                setLoadedPdfDoc(loadedDoc);
                setVisiblePageIndex(resolvedActivePageIndex);
              }}
            >
              {pages.map((pageIndex) => (
                <div
                  key={pageIndex}
                  ref={(node) => setPageRef(pageIndex, node)}
                  role="region"
                  aria-label={`Page ${pageIndex + 1}`}
                  data-page-index={pageIndex}
                  data-active-page={visiblePageIndex === pageIndex ? "true" : "false"}
                  className="relative mx-auto mb-4 w-fit overflow-hidden rounded-sm bg-white shadow-sm"
                >
                  <Page
                    pageNumber={pageIndex + 1}
                    width={pageRenderWidth}
                    renderAnnotationLayer
                    renderTextLayer
                    onLoadSuccess={() => {
                      if (pageIndex === resolvedActivePageIndex) {
                        scrollToPage(pageIndex);
                      }
                    }}
                    onRenderSuccess={() => {
                      if (pageIndex === resolvedActivePageIndex) {
                        scrollToPage(pageIndex);
                      }
                    }}
                  />
                  <div className="pointer-events-none absolute inset-0">
                    {renderHighlightLayer(pageIndex)}
                  </div>
                </div>
              ))}
            </Document>
          </div>
        ) : (
          <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-2 px-4 text-center">
            <FileWarning className="h-8 w-8 text-[var(--pp-text-dim)]" />
            <p className="text-sm text-[var(--pp-text-primary)]">PDF를 불러올 수 없습니다.</p>
            <p className="text-xs text-[var(--pp-text-dim)]">백엔드 PDF 엔드포인트 실패 시 source evidence가 아닌 placeholder PDF를 사용합니다.</p>
          </div>
        )}
      </div>
    </section>
  );
}
