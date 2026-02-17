from typing import Any, Dict, List

from src.schemas.gates import (
    ConfidenceComponents,
    EvidenceSnippet,
    GateDecision,
    GateResult,
    ReasonCode,
)


class GateEngine:
    def __init__(self, high_threshold: float, low_threshold: float, require_evidence: bool = True):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.require_evidence = require_evidence

    def evaluate(self, analysis: Dict[str, Any], *, parse_ok: bool = True, schema_ok: bool = True) -> GateResult:
        if not parse_ok:
            return GateResult(
                decision=GateDecision.FAILED,
                reason_codes=[ReasonCode.SCHEMA_PARSE_FAIL],
                confidence_total=0.0,
            )

        if not schema_ok:
            return GateResult(
                decision=GateDecision.FAILED,
                reason_codes=[ReasonCode.SCHEMA_VALIDATION_FAIL],
                confidence_total=0.0,
            )

        missing_fields = self._missing_required_fields(analysis)
        confidence = self._safe_confidence(analysis.get("confidence", 0.0))
        evidence_snippets = self._extract_evidence(analysis)
        reasons: List[ReasonCode] = []

        if missing_fields:
            reasons.append(ReasonCode.MISSING_REQUIRED_FIELDS)
            return GateResult(
                decision=GateDecision.FAILED,
                reason_codes=reasons,
                confidence_total=confidence,
                confidence_components=self._confidence_components(confidence, evidence_snippets, analysis),
                missing_fields=missing_fields,
                evidence_snippets=evidence_snippets,
            )

        decision = self._confidence_decision(confidence, reasons)

        if self.require_evidence and not evidence_snippets:
            reasons.append(ReasonCode.EVIDENCE_MISSING)
            if decision == GateDecision.APPROVED:
                decision = GateDecision.PENDING_REVIEW

        return GateResult(
            decision=decision,
            reason_codes=reasons,
            confidence_total=confidence,
            confidence_components=self._confidence_components(confidence, evidence_snippets, analysis),
            evidence_snippets=evidence_snippets,
        )

    def _confidence_decision(self, confidence: float, reasons: List[ReasonCode]) -> GateDecision:
        if confidence >= self.high_threshold:
            return GateDecision.APPROVED
        if confidence < self.low_threshold:
            reasons.append(ReasonCode.CONFIDENCE_LOW)
            return GateDecision.QUARANTINED
        reasons.append(ReasonCode.CONFIDENCE_MID)
        return GateDecision.PENDING_REVIEW

    @staticmethod
    def _safe_confidence(raw_value: Any) -> float:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _missing_required_fields(analysis: Dict[str, Any]) -> List[str]:
        required = ["confidence", "soft_tags", "hard_tags"]
        missing = [field for field in required if field not in analysis]
        return missing

    @staticmethod
    def _extract_evidence(analysis: Dict[str, Any]) -> List[EvidenceSnippet]:
        snippets: List[EvidenceSnippet] = []
        raw_snippets = analysis.get("evidence_snippets")
        if isinstance(raw_snippets, list):
            for item in raw_snippets:
                if not isinstance(item, dict):
                    continue
                snippet = item.get("snippet")
                if not snippet:
                    continue
                snippets.append(
                    EvidenceSnippet(
                        snippet=snippet,
                        location=item.get("location", "unknown"),
                        supports=item.get("supports", "slot_decision"),
                    )
                )

        if snippets:
            return snippets

        raw_span = analysis.get("evidence_span")
        if isinstance(raw_span, str) and raw_span.strip():
            snippets.append(
                EvidenceSnippet(
                    snippet=raw_span.strip(),
                    location="unknown",
                    supports="slot_decision",
                )
            )
        return snippets

    @staticmethod
    def _confidence_components(
        confidence: float, evidence_snippets: List[EvidenceSnippet], analysis: Dict[str, Any]
    ) -> ConfidenceComponents:
        hard_tags = analysis.get("hard_tags")
        hard_fields_score = 1.0 if isinstance(hard_tags, dict) and hard_tags else 0.0
        evidence_score = 1.0 if evidence_snippets else 0.0
        return ConfidenceComponents(
            self=confidence,
            judge=None,
            metadata=None,
            evidence=evidence_score,
            hard_fields=hard_fields_score,
        )
