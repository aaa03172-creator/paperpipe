from __future__ import annotations

from typing import Any

from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim

UNKNOWN_REASON_EVIDENCE_MISSING = "EVIDENCE_MISSING"
UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING = "EVIDENCE_LOCATION_MISSING"
UNKNOWN_REASON_UNSPECIFIED = "UNSPECIFIED"


def _span_has_location(span: EvidenceSpan) -> bool:
    if isinstance(span.page, int) and span.page >= 0:
        return True
    if isinstance(span.source_span, list) and len(span.source_span) >= 2:
        return True
    if span.char_start is not None and span.char_end is not None:
        return True
    if isinstance(span.bbox_pdf, list) and len(span.bbox_pdf) == 4:
        return True

    bbox_pct: Any = span.bbox_pct
    if isinstance(bbox_pct, dict):
        if {"left", "top", "width", "height"}.issubset(set(bbox_pct.keys())):
            return True

    table_id = (span.table_id or "").strip()
    cell_id = (span.cell_id or "").strip()
    if table_id and cell_id:
        return True
    return False


def _mark_claim_unknown(claim: ScientificClaim, reason: str, confidence_cap: float) -> None:
    claim.unknown = True
    if not (claim.unknown_reason or "").strip():
        claim.unknown_reason = reason
    claim.confidence = min(claim.confidence, confidence_cap)


def _infer_highlight_source(span: EvidenceSpan) -> str:
    if isinstance(span.bbox_pdf, list) and len(span.bbox_pdf) == 4:
        return "bbox"
    bbox_pct: Any = span.bbox_pct
    if isinstance(bbox_pct, dict):
        if {"left", "top", "width", "height"}.issubset(set(bbox_pct.keys())):
            return "bbox"
    raw_text = (span.raw_text or "").strip()
    quote = (span.quote or "").strip()
    if raw_text or quote:
        return "text_match"
    return "approx"


def enforce_claimset_evidence_policy(
    claim_set: ClaimSet,
    *,
    missing_evidence_conf_cap: float = 0.35,
    missing_location_conf_cap: float = 0.5,
) -> ClaimSet:
    """
    Enforce evidence-first policy.

    - No evidence span -> claim becomes unknown(EVIDENCE_MISSING).
    - Evidence exists but no location metadata -> claim becomes unknown(EVIDENCE_LOCATION_MISSING).
    """
    for claim in claim_set.claims:
        spans = claim.evidence_spans or []
        if not spans:
            _mark_claim_unknown(claim, UNKNOWN_REASON_EVIDENCE_MISSING, missing_evidence_conf_cap)
            continue

        for span in spans:
            if span.highlight_source is None:
                span.highlight_source = _infer_highlight_source(span)

        if not any(_span_has_location(span) for span in spans):
            _mark_claim_unknown(claim, UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING, missing_location_conf_cap)
            continue

        if claim.unknown and not (claim.unknown_reason or "").strip():
            claim.unknown_reason = UNKNOWN_REASON_UNSPECIFIED

    return claim_set
