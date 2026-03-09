import { EvidenceHighlight, NotebookClaim } from "./types";

const CLAIM_TEXT_PLACEHOLDER = "claim text missing";

export type ClaimLinkHealth = "mapped" | "search_fallback" | "missing";

export interface ClaimLinkState {
  health: ClaimLinkHealth;
  textMissing: boolean;
  hasHighlight: boolean;
  hasBBox: boolean;
  page: number;
}

export interface ClaimGuardSummary {
  total: number;
  mappedCount: number;
  fallbackCount: number;
  missingCount: number;
  missingTextCount: number;
}

function highlightSourceScore(source: EvidenceHighlight["source"] | undefined): number {
  if (source === "bbox") {
    return 3.0;
  }
  if (source === "text_match") {
    return 2.0;
  }
  if (source === "approx") {
    return 1.0;
  }
  return 0.5;
}

function highlightQualityScore(item: EvidenceHighlight, index: number): number {
  const hasBBox = item.width > 0 && item.height > 0;
  const area = hasBBox ? item.width * item.height : 0;
  return (
    (hasBBox ? 4.0 : 0) +
    highlightSourceScore(item.source) +
    Math.min(area / 500, 2.0) +
    Math.max(item.page, 1) * 0.001 +
    index * 0.0001
  );
}

export function pickBestHighlightForClaim(
  allHighlights: EvidenceHighlight[],
  claimId: string | null,
): EvidenceHighlight | null {
  if (!claimId) {
    return null;
  }
  const candidates = allHighlights.filter((item) => item.claim_id === claimId);
  if (candidates.length === 0) {
    return null;
  }
  if (candidates.length === 1) {
    return candidates[0];
  }

  let best: EvidenceHighlight | null = null;
  let bestScore = Number.NEGATIVE_INFINITY;
  candidates.forEach((item, index) => {
    const score = highlightQualityScore(item, index);
    if (score > bestScore) {
      bestScore = score;
      best = item;
    }
  });
  return best;
}

export function buildBestHighlightMap(highlights: EvidenceHighlight[]): Map<string, EvidenceHighlight> {
  const bestByClaim = new Map<string, { highlight: EvidenceHighlight; score: number }>();

  highlights.forEach((item, index) => {
    const score = highlightQualityScore(item, index);
    const current = bestByClaim.get(item.claim_id);
    if (!current || score > current.score) {
      bestByClaim.set(item.claim_id, { highlight: item, score });
    }
  });

  return new Map(Array.from(bestByClaim.entries()).map(([claimId, value]) => [claimId, value.highlight]));
}

export function isClaimTextMissing(text: string | null | undefined): boolean {
  if (!text) {
    return true;
  }
  const normalized = text.trim().toLowerCase();
  return normalized.length < 4 || normalized === CLAIM_TEXT_PLACEHOLDER;
}

export function getClaimLinkState(claim: NotebookClaim, highlight: EvidenceHighlight | undefined): ClaimLinkState {
  const textMissing = isClaimTextMissing(claim.text);
  const hasHighlight = Boolean(highlight);
  const hasBBox = Boolean(highlight && highlight.width > 0 && highlight.height > 0);
  const isTextMatch = highlight?.source === "text_match";
  const page = Math.max(highlight?.page ?? 1, 1);

  if (hasBBox && !isTextMatch) {
    return {
      health: "mapped",
      textMissing,
      hasHighlight,
      hasBBox,
      page,
    };
  }
  if (!textMissing) {
    return {
      health: "search_fallback",
      textMissing,
      hasHighlight,
      hasBBox,
      page,
    };
  }
  return {
    health: "missing",
    textMissing,
    hasHighlight,
    hasBBox,
    page,
  };
}

export function summarizeClaimGuard(claims: NotebookClaim[], highlights: EvidenceHighlight[]): ClaimGuardSummary {
  const highlightMap = buildBestHighlightMap(highlights);

  let mappedCount = 0;
  let fallbackCount = 0;
  let missingCount = 0;
  let missingTextCount = 0;

  for (const claim of claims) {
    const state = getClaimLinkState(claim, highlightMap.get(claim.claim_id));
    if (state.health === "mapped") {
      mappedCount += 1;
    } else if (state.health === "search_fallback") {
      fallbackCount += 1;
    } else {
      missingCount += 1;
    }
    if (state.textMissing) {
      missingTextCount += 1;
    }
  }

  return {
    total: claims.length,
    mappedCount,
    fallbackCount,
    missingCount,
    missingTextCount,
  };
}
