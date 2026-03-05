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
  const page = Math.max(highlight?.page ?? 1, 1);

  if (hasBBox) {
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
  const highlightMap = new Map(highlights.map((item) => [item.claim_id, item]));

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
