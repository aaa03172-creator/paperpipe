from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeAlias

from src.schemas.ml_extraction_normalization import (
    ExtractionNormalizationCase,
    ExtractionNormalizationFieldResult,
    ExtractionNormalizationPilotReport,
)
from src.schemas.ml_training_examples import TrainingExample


JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def build_extraction_normalization_case(
    example: TrainingExample,
    *,
    evaluated_at: datetime | None = None,
) -> ExtractionNormalizationCase:
    if example.task_type != "extraction":
        raise ValueError("extraction normalization requires an extraction training example")
    if not example.reviewed_output:
        raise ValueError("extraction normalization requires reviewed_output")

    candidate_fields = _flatten_json_object(example.candidate_output, allow_empty=True)
    reviewed_fields = _flatten_json_object(example.reviewed_output, allow_empty=False)
    field_results = _build_field_results(candidate_fields=candidate_fields, reviewed_fields=reviewed_fields)
    reviewed_field_count = len(field_results)
    matched_count = sum(1 for field in field_results if field.matched)
    missing_count = sum(1 for field in field_results if field.missing_candidate)
    extra_paths = sorted(path for path in candidate_fields if path not in reviewed_fields)
    traced_field_count = reviewed_field_count if example.source_spans else 0

    return ExtractionNormalizationCase(
        example_id=example.example_id,
        paper_id=example.paper_id,
        run_id=example.run_id,
        artifact_id=example.artifact_id,
        payload_class=example.payload_class,
        reviewed_field_count=reviewed_field_count,
        matched_reviewed_field_count=matched_count,
        missing_reviewed_field_count=missing_count,
        extra_candidate_field_count=len(extra_paths),
        field_exact_match_rate=_rate(matched_count, reviewed_field_count),
        field_coverage_rate=_rate(reviewed_field_count - missing_count, reviewed_field_count),
        source_trace_coverage_rate=_rate(traced_field_count, reviewed_field_count),
        field_results=field_results,
        extra_candidate_field_paths=extra_paths,
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
    )


def build_extraction_normalization_pilot_report(
    cases: list[ExtractionNormalizationCase],
    *,
    evaluated_at: datetime | None = None,
) -> ExtractionNormalizationPilotReport:
    if not cases:
        raise ValueError("at least one extraction normalization case is required")

    reviewed_field_count = sum(case.reviewed_field_count for case in cases)
    matched_count = sum(case.matched_reviewed_field_count for case in cases)
    missing_count = sum(case.missing_reviewed_field_count for case in cases)
    traced_count = sum(round(case.source_trace_coverage_rate * case.reviewed_field_count) for case in cases)
    extra_count = sum(case.extra_candidate_field_count for case in cases)
    payload_classes = {case.payload_class for case in cases}
    warnings = []
    if len(payload_classes) > 1:
        warnings.append("mixed_payload_classes")

    return ExtractionNormalizationPilotReport(
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
        payload_class=cases[0].payload_class,
        case_count=len(cases),
        reviewed_field_count=reviewed_field_count,
        field_exact_match_rate=_rate(matched_count, reviewed_field_count),
        field_coverage_rate=_rate(reviewed_field_count - missing_count, reviewed_field_count),
        source_trace_coverage_rate=_rate(traced_count, reviewed_field_count),
        extra_candidate_field_count=extra_count,
        warnings=warnings,
    )


def write_extraction_normalization_case(case: ExtractionNormalizationCase, out: Path) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(case.model_dump_json(indent=2), encoding="utf-8")
    return out


def write_extraction_normalization_pilot_report(
    report: ExtractionNormalizationPilotReport,
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out


def _build_field_results(
    *,
    candidate_fields: dict[str, str],
    reviewed_fields: dict[str, str],
) -> list[ExtractionNormalizationFieldResult]:
    results: list[ExtractionNormalizationFieldResult] = []
    for field_path in sorted(reviewed_fields):
        candidate_value_json = candidate_fields.get(field_path)
        missing_candidate = candidate_value_json is None
        reviewed_value_json = reviewed_fields[field_path]
        results.append(
            ExtractionNormalizationFieldResult(
                field_path=field_path,
                candidate_value_json=candidate_value_json,
                reviewed_value_json=reviewed_value_json,
                matched=candidate_value_json == reviewed_value_json,
                missing_candidate=missing_candidate,
            )
        )
    return results


def _flatten_json_object(payload: dict[str, JsonValue], *, allow_empty: bool) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key in sorted(payload):
        _flatten_json_value(prefix=key, value=payload[key], flattened=flattened)
    if not allow_empty and not flattened:
        raise ValueError("extraction payload must contain at least one reviewed field")
    return flattened


def _flatten_json_value(
    *,
    prefix: str,
    value: JsonValue,
    flattened: dict[str, str],
) -> None:
    match value:
        case dict() if value:
            for key in sorted(value):
                _flatten_json_value(
                    prefix=f"{prefix}.{key}",
                    value=value[key],
                    flattened=flattened,
                )
        case dict():
            flattened[prefix] = _json_leaf(value)
        case list():
            flattened[prefix] = _json_leaf(value)
        case str() | int() | float() | bool() | None:
            flattened[prefix] = _json_leaf(value)


def _json_leaf(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)
