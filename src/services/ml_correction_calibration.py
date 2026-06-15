from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.ml_correction_calibration import (
    CorrectionCalibrationCase,
    CorrectionCalibrationPilotReport,
)
from src.schemas.ml_training_examples import CorrectionIssueLabel, CorrectionReviewExample


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def build_correction_calibration_case(
    example: CorrectionReviewExample,
    *,
    predicted_label: CorrectionIssueLabel,
    proposed_correction: str,
    confidence: float,
    evaluated_at: datetime | None = None,
) -> CorrectionCalibrationCase:
    proposed_correction = proposed_correction.strip()
    if not proposed_correction:
        raise ValueError("proposed_correction is required")
    expected_correction = example.minimal_correction or example.claim_text
    label_matched = predicted_label == example.expected_label
    correctness_target = 1.0 if label_matched else 0.0

    return CorrectionCalibrationCase(
        example_id=example.example_id,
        paper_id=example.paper_id,
        run_id=example.run_id,
        claim_id=example.claim_id,
        payload_class=example.payload_class,
        expected_label=example.expected_label,
        predicted_label=predicted_label,
        confidence=confidence,
        label_matched=label_matched,
        minimal_correction_similarity=_jaccard_similarity(proposed_correction, expected_correction),
        must_preserve_term_recall=_term_recall(proposed_correction, example.must_preserve_terms),
        forbidden_inference_hit=_contains_any_term(proposed_correction, example.must_not_infer),
        confidence_abs_error=round(abs(confidence - correctness_target), 6),
        source_trace_coverage_rate=1.0 if example.source_spans else 0.0,
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
    )


def build_correction_calibration_pilot_report(
    cases: list[CorrectionCalibrationCase],
    *,
    evaluated_at: datetime | None = None,
) -> CorrectionCalibrationPilotReport:
    if not cases:
        raise ValueError("at least one correction calibration case is required")

    payload_classes = {case.payload_class for case in cases}
    warnings = []
    if len(payload_classes) > 1:
        warnings.append("mixed_payload_classes")

    return CorrectionCalibrationPilotReport(
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
        payload_class=cases[0].payload_class,
        case_count=len(cases),
        label_accuracy=_mean(1.0 if case.label_matched else 0.0 for case in cases),
        mean_minimal_correction_similarity=_mean(case.minimal_correction_similarity for case in cases),
        mean_must_preserve_term_recall=_mean(case.must_preserve_term_recall for case in cases),
        forbidden_inference_rate=_mean(1.0 if case.forbidden_inference_hit else 0.0 for case in cases),
        mean_confidence_abs_error=_mean(case.confidence_abs_error for case in cases),
        source_trace_coverage_rate=_mean(case.source_trace_coverage_rate for case in cases),
        warnings=warnings,
    )


def write_correction_calibration_case(case: CorrectionCalibrationCase, out: Path) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(case.model_dump_json(indent=2), encoding="utf-8")
    return out


def write_correction_calibration_pilot_report(
    report: CorrectionCalibrationPilotReport,
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 6)


def _term_recall(text: str, terms: list[str]) -> float:
    normalized_text = _normalize_text(text)
    normalized_terms = [_normalize_text(term) for term in terms if term.strip()]
    if not normalized_terms:
        return 1.0
    matched_count = sum(1 for term in normalized_terms if term in normalized_text)
    return round(matched_count / len(normalized_terms), 6)


def _contains_any_term(text: str, terms: list[str]) -> bool:
    normalized_text = _normalize_text(text)
    return any(_normalize_text(term) in normalized_text for term in terms if term.strip())


def _token_set(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(text)}


def _normalize_text(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 6)
