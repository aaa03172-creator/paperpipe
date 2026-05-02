#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_COMPARE_METRICS_PATHS = [
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "docling_pilot_manifest_expanded_20260424_r28"
    / "metrics.json",
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "docling_pilot_manifest_expanded_broad_20260424_r29"
    / "metrics.json",
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "docling_pilot_manifest_refresh_20260423_r24"
    / "metrics.json",
]
DEFAULT_SECTION_SUMMARY_PATHS = [
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "section_quality_audits"
    / "docling_section_quality_audit_20260324_r15"
    / "summary.json",
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "section_quality_audits"
    / "docling_section_quality_audit_broad_20260324_r18"
    / "summary.json",
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "section_quality_audits"
    / "docling_section_quality_audit_refresh_20260423_r25"
    / "summary.json",
]
DEFAULT_TABLE_MERGE_SUMMARY_PATHS = [
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "table_merge_audits"
    / "docling_same_page_merge_audit_expanded_20260424_r33"
    / "summary.json",
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "table_merge_audits"
    / "docling_same_page_merge_audit_broad_20260424_r34"
    / "summary.json",
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "table_merge_audits"
    / "docling_same_page_merge_audit_refresh_20260424_r35"
    / "summary.json",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_json_path(path: Path, *, default_filename: str) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir():
        candidate = candidate / default_filename
    return candidate


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_expected={path}")
    return payload


def _load_json_artifacts(
    paths: list[Path],
    *,
    default_filename: str,
) -> tuple[list[tuple[Path, dict[str, Any]]], list[dict[str, Any]]]:
    loaded: list[tuple[Path, dict[str, Any]]] = []
    load_errors: list[dict[str, Any]] = []
    for raw_path in paths:
        path = _resolve_json_path(raw_path, default_filename=default_filename)
        if not path.exists():
            load_errors.append({"path": str(path), "error": "missing"})
            continue
        try:
            loaded.append((path, _load_json_dict(path)))
        except Exception as exc:
            load_errors.append({"path": str(path), "error": str(exc)})
    return loaded, load_errors


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _add_blocker(blockers: list[str], code: str) -> None:
    if code not in blockers:
        blockers.append(code)


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _backend_metrics(metrics: dict[str, Any], backend: str) -> dict[str, Any]:
    all_metrics = _dict_value(metrics.get("backend_metrics"))
    return _dict_value(all_metrics.get(backend))


def _compare_run_summary(
    *,
    path: Path | None,
    metrics: dict[str, Any],
    baseline_backend: str,
    candidate_backend: str,
) -> dict[str, Any]:
    baseline = _backend_metrics(metrics, baseline_backend)
    candidate = _backend_metrics(metrics, candidate_backend)
    comparison = _dict_value(metrics.get("comparison"))
    decision = _dict_value(comparison.get("decision"))
    document_count = _int_value(metrics.get("document_count") or baseline.get("document_count"))
    baseline_success_count = _int_value(baseline.get("success_count"))
    candidate_success_count = _int_value(candidate.get("success_count"))

    return {
        "path": str(path) if path is not None else None,
        "run_id": metrics.get("run_id"),
        "schema_version": metrics.get("schema_version"),
        "baseline_backend": metrics.get("baseline_backend"),
        "candidate_backend": metrics.get("candidate_backend"),
        "document_count": document_count,
        "decision_passed": bool(decision.get("passed")),
        "failed_checks": _list_value(decision.get("failed_checks")),
        "baseline": {
            "success_count": baseline_success_count,
            "error_count": _int_value(baseline.get("error_count")),
            "backend_unavailable_count": _int_value(baseline.get("backend_unavailable_count")),
            "docs_with_text_count": _int_value(baseline.get("docs_with_text_count")),
            "docs_with_doi_count": _int_value(baseline.get("docs_with_doi_count")),
            "docs_with_tables_count": _int_value(baseline.get("docs_with_tables_count")),
            "docs_with_meaningful_tables_count": _int_value(
                baseline.get("docs_with_meaningful_tables_count")
            ),
            "avg_text_char_count": _float_value(baseline.get("avg_text_char_count")),
            "missing_success_count": max(document_count - baseline_success_count, 0),
            "empty_text_docs_count": max(
                baseline_success_count - _int_value(baseline.get("docs_with_text_count")),
                0,
            ),
        },
        "candidate": {
            "success_count": candidate_success_count,
            "error_count": _int_value(candidate.get("error_count")),
            "backend_unavailable_count": _int_value(candidate.get("backend_unavailable_count")),
            "docs_with_text_count": _int_value(candidate.get("docs_with_text_count")),
            "docs_with_doi_count": _int_value(candidate.get("docs_with_doi_count")),
            "docs_with_tables_count": _int_value(candidate.get("docs_with_tables_count")),
            "docs_with_meaningful_tables_count": _int_value(
                candidate.get("docs_with_meaningful_tables_count")
            ),
            "docs_with_table_fallback_count": _int_value(candidate.get("docs_with_table_fallback_count")),
            "avg_text_char_count": _float_value(candidate.get("avg_text_char_count")),
            "missing_success_count": max(document_count - candidate_success_count, 0),
            "empty_text_docs_count": max(
                candidate_success_count - _int_value(candidate.get("docs_with_text_count")),
                0,
            ),
        },
        "comparison": {
            "compared_document_count": _int_value(comparison.get("compared_document_count")),
            "backend_unavailable_doc_count": len(_list_value(comparison.get("backend_unavailable_docs"))),
            "error_increase_doc_count": len(_list_value(comparison.get("error_increase_docs"))),
            "empty_text_increase_doc_count": len(_list_value(comparison.get("empty_text_increase_docs"))),
            "doi_loss_doc_count": len(_list_value(comparison.get("doi_loss_docs"))),
            "meaningful_table_loss_doc_count": len(_list_value(comparison.get("meaningful_table_loss_docs"))),
            "meaningful_table_gain_doc_count": len(_list_value(comparison.get("meaningful_table_gain_docs"))),
            "same_page_merge_doc_count": len(_list_value(comparison.get("same_page_merge_docs"))),
            "low_text_ratio_doc_count": len(_list_value(comparison.get("low_text_ratio_docs"))),
        },
    }


def _section_run_summary(path: Path | None, summary: dict[str, Any]) -> dict[str, Any]:
    document_count = _int_value(summary.get("document_count"))
    return {
        "path": str(path) if path is not None else None,
        "run_id": summary.get("run_id"),
        "status": summary.get("status"),
        "document_count": document_count,
        "page_coverage_preserved_count": _int_value(summary.get("page_coverage_preserved_count")),
        "missing_page_docs_count": _int_value(summary.get("missing_page_docs_count")),
        "low_page_text_ratio_docs_count": _int_value(summary.get("low_page_text_ratio_docs_count")),
        "low_page_text_ratio_unclassified_docs_count": _int_value(
            summary.get("low_page_text_ratio_unclassified_docs_count")
        ),
        "low_total_text_ratio_docs_count": _int_value(summary.get("low_total_text_ratio_docs_count")),
        "section_collapse_docs_count": _int_value(summary.get("section_collapse_docs_count")),
    }


def _table_merge_run_summary(path: Path | None, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path) if path is not None else None,
        "run_id": summary.get("run_id"),
        "status": summary.get("status"),
        "document_count": _int_value(summary.get("document_count")),
        "semantic_merge_preserved_count": _int_value(summary.get("semantic_merge_preserved_count")),
        "content_gap_count": _int_value(summary.get("content_gap_count")),
    }


def _sum_nested(runs: list[dict[str, Any]], key: str, nested_key: str | None = None) -> int:
    total = 0
    for run in runs:
        source = _dict_value(run.get(key)) if nested_key is not None else run
        total += _int_value(source.get(nested_key if nested_key is not None else key))
    return total


def _default_change_evidence_advisory(
    *,
    compare_metrics: list[dict[str, Any]],
    reference_generated_at: str,
    compare_document_count: int,
    min_default_change_document_count: int,
    max_default_change_artifact_age_days: int,
) -> dict[str, Any]:
    reference_dt = _parse_iso_datetime(reference_generated_at) or datetime.now(timezone.utc)
    parsed_generated_at = [
        parsed
        for parsed in (_parse_iso_datetime(metrics.get("generated_at")) for metrics in compare_metrics)
        if parsed is not None
    ]
    age_days: list[float] = [
        max((reference_dt - generated_at).total_seconds() / 86400.0, 0.0)
        for generated_at in parsed_generated_at
    ]
    oldest_age_days = max(age_days) if age_days else None
    newest_age_days = min(age_days) if age_days else None
    document_count_floor_met = compare_document_count >= min_default_change_document_count
    freshness_floor_met = (
        oldest_age_days is not None and oldest_age_days <= float(max_default_change_artifact_age_days)
    )
    return {
        "document_count": compare_document_count,
        "min_document_count_for_default_change_review": int(max(min_default_change_document_count, 0)),
        "document_count_floor_met": document_count_floor_met,
        "compare_artifact_generated_at_count": len(parsed_generated_at),
        "oldest_compare_artifact_age_days": round(oldest_age_days, 2) if oldest_age_days is not None else None,
        "newest_compare_artifact_age_days": round(newest_age_days, 2) if newest_age_days is not None else None,
        "max_artifact_age_days_for_default_change_review": int(max(max_default_change_artifact_age_days, 0)),
        "freshness_floor_met": freshness_floor_met,
        "review_hint": (
            "saved evidence is broad and fresh enough to start a default-change review"
            if document_count_floor_met and freshness_floor_met
            else "saved evidence is enough for current baseline visibility, but not enough by itself for a default-change review"
        ),
    }


def _compact_parser_baseline_text(summary: dict[str, Any]) -> str:
    aggregate = _dict_value(summary.get("aggregate"))
    decision = _dict_value(summary.get("decision"))
    parts = [
        f"passed={bool(decision.get('passed'))}",
        f"baseline_usable={bool(decision.get('baseline_parser_usable'))}",
        f"docling_pilot={bool(decision.get('docling_optional_pilot_supported'))}",
        f"default_change_ready={bool(decision.get('default_parser_change_ready'))}",
    ]
    action = str(decision.get("recommended_action") or "").strip()
    if action:
        parts.append(f"action={action}")
    docs = _int_value(aggregate.get("compare_document_count"))
    if docs:
        parts.append(f"docs={docs}")
    section_docs = _int_value(aggregate.get("section_document_count"))
    if section_docs:
        parts.append(f"section_docs={section_docs}")
    table_gaps = _int_value(aggregate.get("table_merge_content_gap_count"))
    parts.append(f"table_merge_gaps={table_gaps}")
    blockers = _list_value(decision.get("blockers"))
    if blockers:
        parts.append("blockers=" + ",".join(str(item) for item in blockers))
    return " ".join(parts)


def build_parser_baseline_readiness_summary(
    *,
    compare_metrics: list[dict[str, Any]],
    compare_metrics_paths: list[Path | None],
    section_summaries: list[dict[str, Any]],
    section_summary_paths: list[Path | None],
    table_merge_summaries: list[dict[str, Any]],
    table_merge_summary_paths: list[Path | None],
    run_id: str,
    load_errors: list[dict[str, Any]] | None = None,
    baseline_backend: str = "fitz_pdfplumber",
    candidate_backend: str = "docling",
    max_baseline_error_docs: int = 0,
    max_baseline_empty_text_docs: int = 0,
    max_candidate_error_docs: int = 0,
    max_candidate_empty_text_docs: int = 0,
    max_candidate_doi_loss_docs: int = 0,
    max_candidate_low_text_ratio_docs: int = 0,
    max_section_missing_page_docs: int = 0,
    max_section_low_total_text_ratio_docs: int = 0,
    max_section_collapse_docs: int = 0,
    max_section_unclassified_low_ratio_docs: int = 0,
    max_table_merge_content_gap_docs: int = 0,
    min_default_change_document_count: int = 50,
    max_default_change_artifact_age_days: int = 30,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    blockers: list[str] = []
    artifact_load_errors = list(load_errors or [])
    for error in artifact_load_errors:
        _add_blocker(blockers, "artifact_load_error")

    compare_runs = [
        _compare_run_summary(
            path=compare_metrics_paths[idx] if idx < len(compare_metrics_paths) else None,
            metrics=metrics,
            baseline_backend=baseline_backend,
            candidate_backend=candidate_backend,
        )
        for idx, metrics in enumerate(compare_metrics)
    ]
    section_runs = [
        _section_run_summary(
            section_summary_paths[idx] if idx < len(section_summary_paths) else None,
            summary,
        )
        for idx, summary in enumerate(section_summaries)
    ]
    table_merge_runs = [
        _table_merge_run_summary(
            table_merge_summary_paths[idx] if idx < len(table_merge_summary_paths) else None,
            summary,
        )
        for idx, summary in enumerate(table_merge_summaries)
    ]

    if not compare_runs:
        _add_blocker(blockers, "compare_metrics_missing")
    if compare_runs and not section_runs:
        _add_blocker(blockers, "section_quality_audit_missing")

    for run in compare_runs:
        schema_version = str(run.get("schema_version") or "")
        if not schema_version.startswith("ingest_backend_eval.v"):
            _add_blocker(blockers, "unsupported_compare_metrics_schema")
        if run.get("baseline_backend") != baseline_backend:
            _add_blocker(blockers, "unexpected_baseline_backend")
        if run.get("candidate_backend") != candidate_backend:
            _add_blocker(blockers, "unexpected_candidate_backend")
        if _int_value(run.get("document_count")) <= 0:
            _add_blocker(blockers, "compare_metrics_empty_document_set")
        if not bool(run.get("decision_passed")):
            _add_blocker(blockers, "compare_decision_failed")

    baseline_error_docs = _sum_nested(compare_runs, "baseline", "error_count") + _sum_nested(
        compare_runs, "baseline", "missing_success_count"
    )
    baseline_empty_text_docs = _sum_nested(compare_runs, "baseline", "empty_text_docs_count")
    baseline_backend_unavailable_docs = _sum_nested(compare_runs, "baseline", "backend_unavailable_count")
    candidate_error_docs = _sum_nested(compare_runs, "candidate", "error_count") + _sum_nested(
        compare_runs, "candidate", "missing_success_count"
    )
    candidate_empty_text_docs = _sum_nested(compare_runs, "candidate", "empty_text_docs_count")
    candidate_backend_unavailable_docs = _sum_nested(compare_runs, "candidate", "backend_unavailable_count")
    candidate_doi_loss_docs = _sum_nested(compare_runs, "comparison", "doi_loss_doc_count")
    candidate_low_text_ratio_docs = _sum_nested(compare_runs, "comparison", "low_text_ratio_doc_count")
    same_page_merge_docs = _sum_nested(compare_runs, "comparison", "same_page_merge_doc_count")

    if baseline_error_docs > max_baseline_error_docs:
        _add_blocker(blockers, "baseline_errors_present")
    if baseline_backend_unavailable_docs:
        _add_blocker(blockers, "baseline_backend_unavailable")
    if baseline_empty_text_docs > max_baseline_empty_text_docs:
        _add_blocker(blockers, "baseline_empty_text_docs_present")
    if candidate_error_docs > max_candidate_error_docs:
        _add_blocker(blockers, "candidate_errors_present")
    if candidate_backend_unavailable_docs:
        _add_blocker(blockers, "candidate_backend_unavailable")
    if candidate_empty_text_docs > max_candidate_empty_text_docs:
        _add_blocker(blockers, "candidate_empty_text_docs_present")
    if candidate_doi_loss_docs > max_candidate_doi_loss_docs:
        _add_blocker(blockers, "candidate_doi_loss_docs_present")
    if candidate_low_text_ratio_docs > max_candidate_low_text_ratio_docs:
        _add_blocker(blockers, "candidate_low_text_ratio_docs_present")

    section_missing_page_docs = _sum_nested(section_runs, "missing_page_docs_count")
    section_low_total_text_ratio_docs = _sum_nested(section_runs, "low_total_text_ratio_docs_count")
    section_collapse_docs = _sum_nested(section_runs, "section_collapse_docs_count")
    section_unclassified_low_ratio_docs = _sum_nested(section_runs, "low_page_text_ratio_unclassified_docs_count")
    if section_missing_page_docs > max_section_missing_page_docs:
        _add_blocker(blockers, "section_missing_page_docs_present")
    if section_low_total_text_ratio_docs > max_section_low_total_text_ratio_docs:
        _add_blocker(blockers, "section_low_total_text_ratio_docs_present")
    if section_collapse_docs > max_section_collapse_docs:
        _add_blocker(blockers, "section_collapse_docs_present")
    if section_unclassified_low_ratio_docs > max_section_unclassified_low_ratio_docs:
        _add_blocker(blockers, "section_unclassified_low_ratio_docs_present")

    table_merge_content_gap_docs = _sum_nested(table_merge_runs, "content_gap_count")
    table_merge_document_count = _sum_nested(table_merge_runs, "document_count")
    if same_page_merge_docs > 0 and not table_merge_runs:
        _add_blocker(blockers, "table_merge_audit_missing_for_same_page_merges")
    if same_page_merge_docs > table_merge_document_count:
        _add_blocker(blockers, "table_merge_audit_incomplete")
    if table_merge_content_gap_docs > max_table_merge_content_gap_docs:
        _add_blocker(blockers, "table_merge_content_gap_docs_present")

    baseline_blockers = {
        "compare_metrics_missing",
        "unsupported_compare_metrics_schema",
        "unexpected_baseline_backend",
        "compare_metrics_empty_document_set",
        "baseline_errors_present",
        "baseline_backend_unavailable",
        "baseline_empty_text_docs_present",
        "artifact_load_error",
    }
    candidate_blockers = set(blockers) - {
        "unexpected_baseline_backend",
        "baseline_errors_present",
        "baseline_backend_unavailable",
        "baseline_empty_text_docs_present",
    }
    baseline_parser_usable = not any(blocker in baseline_blockers for blocker in blockers)
    docling_optional_pilot_supported = baseline_parser_usable and not candidate_blockers

    aggregate = {
        "compare_run_count": len(compare_runs),
        "compare_document_count": _sum_nested(compare_runs, "document_count"),
        "compare_passed_count": sum(1 for run in compare_runs if bool(run.get("decision_passed"))),
        "baseline_success_count": _sum_nested(compare_runs, "baseline", "success_count"),
        "baseline_error_docs_count": baseline_error_docs,
        "baseline_empty_text_docs_count": baseline_empty_text_docs,
        "baseline_docs_with_doi_count": _sum_nested(compare_runs, "baseline", "docs_with_doi_count"),
        "candidate_success_count": _sum_nested(compare_runs, "candidate", "success_count"),
        "candidate_error_docs_count": candidate_error_docs,
        "candidate_empty_text_docs_count": candidate_empty_text_docs,
        "candidate_docs_with_doi_count": _sum_nested(compare_runs, "candidate", "docs_with_doi_count"),
        "candidate_docs_with_table_fallback_count": _sum_nested(
            compare_runs, "candidate", "docs_with_table_fallback_count"
        ),
        "candidate_meaningful_table_gain_docs_count": _sum_nested(
            compare_runs, "comparison", "meaningful_table_gain_doc_count"
        ),
        "candidate_meaningful_table_loss_docs_count": _sum_nested(
            compare_runs, "comparison", "meaningful_table_loss_doc_count"
        ),
        "candidate_doi_loss_docs_count": candidate_doi_loss_docs,
        "candidate_low_text_ratio_docs_count": candidate_low_text_ratio_docs,
        "same_page_merge_docs_count": same_page_merge_docs,
        "section_run_count": len(section_runs),
        "section_document_count": _sum_nested(section_runs, "document_count"),
        "section_page_coverage_preserved_count": _sum_nested(section_runs, "page_coverage_preserved_count"),
        "section_low_page_text_ratio_docs_count": _sum_nested(section_runs, "low_page_text_ratio_docs_count"),
        "section_missing_page_docs_count": section_missing_page_docs,
        "section_low_total_text_ratio_docs_count": section_low_total_text_ratio_docs,
        "section_collapse_docs_count": section_collapse_docs,
        "section_unclassified_low_ratio_docs_count": section_unclassified_low_ratio_docs,
        "table_merge_run_count": len(table_merge_runs),
        "table_merge_document_count": table_merge_document_count,
        "table_merge_content_gap_count": table_merge_content_gap_docs,
    }

    default_change_evidence = _default_change_evidence_advisory(
        compare_metrics=compare_metrics,
        reference_generated_at=generated_at,
        compare_document_count=_int_value(aggregate.get("compare_document_count")),
        min_default_change_document_count=min_default_change_document_count,
        max_default_change_artifact_age_days=max_default_change_artifact_age_days,
    )
    default_parser_change_blockers = [
        "current_reports_classify_docling_as_behind_flag_optional_pilot",
        "default_parser_change_requires_explicit_architecture_decision",
        "docling_path_remains_hybrid_optional_backend_not_pure_default_replacement",
    ]
    if not bool(default_change_evidence.get("document_count_floor_met")):
        default_parser_change_blockers.append("bounded_sample_below_default_change_review_floor")
    if not bool(default_change_evidence.get("freshness_floor_met")):
        default_parser_change_blockers.append("parser_eval_artifacts_need_refresh_for_default_change_review")
    return {
        "schema_version": "parser_baseline_readiness.v1",
        "generated_at": generated_at,
        "run_id": run_id,
        "thresholds": {
            "baseline_backend": baseline_backend,
            "candidate_backend": candidate_backend,
            "max_baseline_error_docs": int(max(max_baseline_error_docs, 0)),
            "max_baseline_empty_text_docs": int(max(max_baseline_empty_text_docs, 0)),
            "max_candidate_error_docs": int(max(max_candidate_error_docs, 0)),
            "max_candidate_empty_text_docs": int(max(max_candidate_empty_text_docs, 0)),
            "max_candidate_doi_loss_docs": int(max(max_candidate_doi_loss_docs, 0)),
            "max_candidate_low_text_ratio_docs": int(max(max_candidate_low_text_ratio_docs, 0)),
            "max_section_missing_page_docs": int(max(max_section_missing_page_docs, 0)),
            "max_section_low_total_text_ratio_docs": int(max(max_section_low_total_text_ratio_docs, 0)),
            "max_section_collapse_docs": int(max(max_section_collapse_docs, 0)),
            "max_section_unclassified_low_ratio_docs": int(max(max_section_unclassified_low_ratio_docs, 0)),
            "max_table_merge_content_gap_docs": int(max(max_table_merge_content_gap_docs, 0)),
            "min_default_change_document_count": int(max(min_default_change_document_count, 0)),
            "max_default_change_artifact_age_days": int(max(max_default_change_artifact_age_days, 0)),
        },
        "inputs": {
            "compare_metrics_paths": [str(path) if path is not None else None for path in compare_metrics_paths],
            "section_summary_paths": [str(path) if path is not None else None for path in section_summary_paths],
            "table_merge_summary_paths": [
                str(path) if path is not None else None for path in table_merge_summary_paths
            ],
            "load_errors": artifact_load_errors,
        },
        "runs": {
            "compare_metrics": compare_runs,
            "section_quality": section_runs,
            "table_merge": table_merge_runs,
        },
        "aggregate": aggregate,
        "advisory": {
            "default_change_review_evidence": default_change_evidence,
        },
        "decision": {
            "passed": not blockers,
            "parser_baseline_ready": not blockers,
            "baseline_parser_usable": baseline_parser_usable,
            "docling_optional_pilot_supported": docling_optional_pilot_supported,
            "default_parser_change_ready": False,
            "recommended_runtime_default": baseline_backend,
            "recommended_candidate_mode": "behind_flag_optional_hybrid_pilot",
            "recommended_action": "keep_fitz_pdfplumber_default_and_docling_behind_flag",
            "blockers": blockers,
            "default_parser_change_blockers": default_parser_change_blockers,
            "decision_reason": (
                "saved parser-eval artifacts support the current default parser and a bounded behind-flag docling pilot, "
                "but not a default parser replacement"
                if not blockers
                else "parser baseline readiness is blocked by missing or regressed eval evidence"
            ),
        },
    }


def run_parser_baseline_readiness(
    *,
    compare_metrics_paths: list[Path],
    section_summary_paths: list[Path],
    table_merge_summary_paths: list[Path],
    out_dir: Path,
    run_id: str,
) -> Path:
    compare_artifacts, compare_errors = _load_json_artifacts(
        compare_metrics_paths,
        default_filename="metrics.json",
    )
    section_artifacts, section_errors = _load_json_artifacts(
        section_summary_paths,
        default_filename="summary.json",
    )
    table_artifacts, table_errors = _load_json_artifacts(
        table_merge_summary_paths,
        default_filename="summary.json",
    )
    summary = build_parser_baseline_readiness_summary(
        compare_metrics=[payload for _path, payload in compare_artifacts],
        compare_metrics_paths=[path for path, _payload in compare_artifacts],
        section_summaries=[payload for _path, payload in section_artifacts],
        section_summary_paths=[path for path, _payload in section_artifacts],
        table_merge_summaries=[payload for _path, payload in table_artifacts],
        table_merge_summary_paths=[path for path, _payload in table_artifacts],
        run_id=run_id,
        load_errors=compare_errors + section_errors + table_errors,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check saved parser-eval artifacts and report whether the current parser baseline is usable, "
            "whether docling remains safe as a behind-flag pilot, and whether default parser promotion is supported."
        )
    )
    parser.add_argument(
        "--compare-metrics",
        action="append",
        dest="compare_metrics_paths",
        default=None,
        help="Path to compare_ingest_backends metrics.json. May be passed multiple times.",
    )
    parser.add_argument(
        "--section-summary",
        action="append",
        dest="section_summary_paths",
        default=None,
        help="Path to audit_section_quality summary.json. May be passed multiple times.",
    )
    parser.add_argument(
        "--table-merge-summary",
        action="append",
        dest="table_merge_summary_paths",
        default=None,
        help="Path to audit_table_merge_semantics summary.json. May be passed multiple times.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "parser_baseline_readiness"),
        help="Directory to write the parser baseline readiness summary into.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    parser.add_argument(
        "--allow-advisory-hold",
        action="store_true",
        help=(
            "Return success when the default parser baseline is usable even if the optional candidate pilot is on hold. "
            "Use this for smoke visibility checks, not for promotion decisions."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_parser_baseline_readiness(
        compare_metrics_paths=[
            Path(path) for path in (args.compare_metrics_paths or [str(path) for path in DEFAULT_COMPARE_METRICS_PATHS])
        ],
        section_summary_paths=[
            Path(path) for path in (args.section_summary_paths or [str(path) for path in DEFAULT_SECTION_SUMMARY_PATHS])
        ],
        table_merge_summary_paths=[
            Path(path)
            for path in (args.table_merge_summary_paths or [str(path) for path in DEFAULT_TABLE_MERGE_SUMMARY_PATHS])
        ],
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    payload = _load_json_dict(run_root / "summary.json")
    print(f"[check_parser_baseline_readiness] out={run_root}")
    print(f"[check_parser_baseline_readiness] summary={run_root / 'summary.json'}")
    print("[check_parser_baseline_readiness] " + _compact_parser_baseline_text(payload))
    decision = _dict_value(payload.get("decision"))
    passed = bool(decision.get("passed"))
    advisory_hold_allowed = bool(args.allow_advisory_hold) and bool(decision.get("baseline_parser_usable"))
    return 0 if passed or advisory_hold_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
