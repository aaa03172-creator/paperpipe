from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from src.schemas.agent_artifacts import ClaimSet

SCHEMA_INVALID = "SCHEMA_INVALID"
NO_EVIDENCE_SPAN = "NO_EVIDENCE_SPAN"
EVIDENCE_LOCATION_MISSING = "EVIDENCE_LOCATION_MISSING"
NUMERIC_SANITY_FAIL = "NUMERIC_SANITY_FAIL"
FORBIDDEN_PHRASE = "FORBIDDEN_PHRASE"
HALLUCINATION_PATTERN = "HALLUCINATION_PATTERN"
LEAKAGE_RISK = "LEAKAGE_RISK"
TEACHER_REVIEW_FRAGMENTARY_CLAIM = "TEACHER_REVIEW_FRAGMENTARY_CLAIM"
TEACHER_REVIEW_MISALIGNED_QUOTE = "TEACHER_REVIEW_MISALIGNED_QUOTE"

DEFAULT_FORBIDDEN_PHRASES = (
    "as an ai language model",
    "i cannot access",
    "no summary available",
    "i apologize, but",
    "this paper is not provided",
)

ASSERTIVE_PATTERNS = (
    "proves",
    "definitive",
    "always",
    "never",
    "guarantees",
    "certainly",
)

P_VALUE_RE = re.compile(r"\bp\s*([<=>])\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)
PERCENT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
N_RE = re.compile(r"\b[Nn]\s*=\s*([0-9]+)")


@dataclass(frozen=True)
class GateFinding:
    gate: str
    reason_code: str
    detail: str


@dataclass
class GateDecision:
    passed: bool
    reason_codes: list[str] = field(default_factory=list)
    findings: list[GateFinding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _extract_claimset_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, ClaimSet):
        return payload.model_dump()
    if isinstance(payload, dict):
        if isinstance(payload.get("claims"), list):
            return payload
        nested = payload.get("ClaimSet")
        if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
            return nested
        nested = payload.get("claimset")
        if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
            return nested
    return {}


def _span_has_location(span: dict[str, Any], *, page_requires_presence: bool = False) -> bool:
    page = span.get("page")
    if isinstance(page, int) and page >= 0:
        if not page_requires_presence or "page" in span:
            return True
    section = span.get("section")
    if isinstance(section, str) and section.strip():
        return True
    source_span = span.get("source_span")
    if isinstance(source_span, list) and len(source_span) >= 2:
        return True
    if span.get("char_start") is not None and span.get("char_end") is not None:
        return True
    return False


def _contains_forbidden(text: str, phrases: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    for phrase in phrases:
        if phrase in lowered:
            return phrase
    return None


class GateEngine:
    def __init__(self, forbidden_phrases: tuple[str, ...] = DEFAULT_FORBIDDEN_PHRASES):
        self.forbidden_phrases = forbidden_phrases

    def evaluate(self, payload: Any, *, summary_text: str | None = None) -> GateDecision:
        findings: list[GateFinding] = []
        reason_codes: set[str] = set()

        claimset_payload = _extract_claimset_payload(payload)
        claimset_obj: ClaimSet | None = None
        try:
            claimset_obj = ClaimSet.model_validate(claimset_payload)
        except ValidationError as exc:
            reason_codes.add(SCHEMA_INVALID)
            findings.append(GateFinding(gate="SchemaGate", reason_code=SCHEMA_INVALID, detail=str(exc).splitlines()[0]))

        if claimset_obj is not None:
            claims = claimset_obj.claims
            raw_claims = claimset_payload.get("claims")
            if not isinstance(raw_claims, list):
                raw_claims = []
            if not claims:
                reason_codes.add(NO_EVIDENCE_SPAN)
                findings.append(
                    GateFinding(
                        gate="EvidenceGate",
                        reason_code=NO_EVIDENCE_SPAN,
                        detail="claims array is empty",
                    )
                )
            for idx, claim in enumerate(claims):
                if not claim.evidence_spans:
                    reason_codes.add(NO_EVIDENCE_SPAN)
                    findings.append(
                        GateFinding(
                            gate="EvidenceGate",
                            reason_code=NO_EVIDENCE_SPAN,
                            detail=f"claim_id={claim.claim_id} has no evidence_spans",
                        )
                    )
                    continue

                raw_claim = raw_claims[idx] if idx < len(raw_claims) and isinstance(raw_claims[idx], dict) else None
                raw_spans = raw_claim.get("evidence_spans") if isinstance(raw_claim, dict) else None
                if isinstance(raw_spans, list):
                    span_payloads = [span for span in raw_spans if isinstance(span, dict)]
                    page_requires_presence = True
                else:
                    span_payloads = [span.model_dump() for span in claim.evidence_spans]
                    page_requires_presence = False

                if not any(
                    _span_has_location(span_payload, page_requires_presence=page_requires_presence)
                    for span_payload in span_payloads
                ):
                    reason_codes.add(EVIDENCE_LOCATION_MISSING)
                    findings.append(
                        GateFinding(
                            gate="EvidenceGate",
                            reason_code=EVIDENCE_LOCATION_MISSING,
                            detail=f"claim_id={claim.claim_id} evidence spans missing location fields",
                        )
                    )

                statement = claim.statement or ""
                evidence_text = " ".join(
                    (
                        (span.quote or "").strip() + " " + (span.raw_text or "").strip()
                        for span in claim.evidence_spans
                    )
                ).strip()
                if self._numeric_sanity_fails(statement, evidence_text):
                    reason_codes.add(NUMERIC_SANITY_FAIL)
                    findings.append(
                        GateFinding(
                            gate="NumericSanityGate",
                            reason_code=NUMERIC_SANITY_FAIL,
                            detail=f"claim_id={claim.claim_id} numeric cues unsupported by evidence text",
                        )
                    )

                if self._hallucination_risk(claim.statement, claim.confidence, evidence_text):
                    reason_codes.add(HALLUCINATION_PATTERN)
                    findings.append(
                        GateFinding(
                            gate="HallucinationHeuristicGate",
                            reason_code=HALLUCINATION_PATTERN,
                            detail=f"claim_id={claim.claim_id} high-confidence assertion with weak evidence",
                        )
                    )

            text_targets = [summary_text or ""] + [claim.statement for claim in claims]
            for txt in text_targets:
                if not txt:
                    continue
                phrase = _contains_forbidden(txt, self.forbidden_phrases)
                if phrase:
                    reason_codes.add(FORBIDDEN_PHRASE)
                    findings.append(
                        GateFinding(
                            gate="ForbiddenPhraseGate",
                            reason_code=FORBIDDEN_PHRASE,
                            detail=f"forbidden phrase detected: {phrase}",
                        )
                    )

        decision = GateDecision(
            passed=len(reason_codes) == 0,
            reason_codes=sorted(reason_codes),
            findings=findings,
            metrics={
                "finding_count": len(findings),
                "reason_count": len(reason_codes),
            },
        )
        return decision

    @staticmethod
    def _numeric_sanity_fails(statement: str, evidence_text: str) -> bool:
        statement = statement or ""
        evidence_text = evidence_text or ""
        requires_numeric = bool(P_VALUE_RE.search(statement) or PERCENT_RE.search(statement) or N_RE.search(statement))
        if not requires_numeric:
            return False
        if not re.search(r"\d", evidence_text):
            return True

        for match in P_VALUE_RE.finditer(statement):
            value = float(match.group(2))
            if value < 0 or value > 1:
                return True
        return False

    @staticmethod
    def _hallucination_risk(statement: str, confidence: float, evidence_text: str) -> bool:
        if confidence < 0.9:
            return False
        lowered = (statement or "").lower()
        assertive = any(token in lowered for token in ASSERTIVE_PATTERNS)
        if not assertive:
            return False
        return len((evidence_text or "").strip()) < 20
