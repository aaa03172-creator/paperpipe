#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_READINESS_SUMMARY_PATH = (
    ROOT
    / "snapshots"
    / "parser_baseline_readiness"
    / "parser_baseline_readiness_20260424_r8"
    / "summary.json"
)
DEFAULT_DERIVED_RESCUE_READINESS_SUMMARY_PATH = (
    ROOT
    / "snapshots"
    / "same_page_table_rescue_readiness"
    / "same_page_table_rescue_readiness_20260426_r2"
    / "summary.json"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_json_path(path: Path, *, default_filename: str = "summary.json") -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir():
        candidate = candidate / default_filename
    return candidate


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_expected={path}")
    return payload


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _add_blocker(blockers: list[str], code: str) -> None:
    if code not in blockers:
        blockers.append(code)


def _load_optional_compare_from_derived(
    derived_rescue_readiness: dict[str, Any],
    explicit_path: Path | None,
) -> tuple[dict[str, Any] | None, Path | None, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    raw_path = explicit_path
    if raw_path is None:
        derived_inputs = _dict_value(derived_rescue_readiness.get("inputs"))
        raw_value = str(derived_inputs.get("compare_metrics_path") or "").strip()
        if raw_value:
            raw_path = Path(raw_value)
    if raw_path is None:
        return None, None, errors
    path = _resolve_json_path(raw_path, default_filename="metrics.json")
    if not path.exists():
        errors.append({"path": str(path), "error": "missing"})
        return None, path, errors
    try:
        return _load_json_dict(path), path, errors
    except Exception as exc:
        errors.append({"path": str(path), "error": str(exc)})
        return None, path, errors


def _source_readiness_lane(
    *,
    source_readiness: dict[str, Any],
    source_path: Path | None,
) -> dict[str, Any]:
    aggregate = _dict_value(source_readiness.get("aggregate"))
    decision = _dict_value(source_readiness.get("decision"))
    advisory = _dict_value(source_readiness.get("advisory"))
    default_change_review = _dict_value(advisory.get("default_change_review_evidence"))
    return {
        "lane_id": "source_pdf_readiness",
        "artifact_layer": "review_gate_artifact",
        "source_material_layer": "raw_source",
        "promotion_role": "canonical_source_readiness",
        "summary_path": str(source_path) if source_path is not None else None,
        "run_id": source_readiness.get("run_id"),
        "schema_version": source_readiness.get("schema_version"),
        "readiness_passed": bool(decision.get("passed")),
        "baseline_parser_usable": bool(decision.get("baseline_parser_usable")),
        "docling_optional_pilot_supported": bool(decision.get("docling_optional_pilot_supported")),
        "default_change_review_eligible": bool(
            default_change_review.get("document_count_floor_met")
            and default_change_review.get("freshness_floor_met")
        ),
        "default_change_promotion_eligible": False,
        "document_count": _int_value(aggregate.get("compare_document_count")),
        "compare_run_count": _int_value(aggregate.get("compare_run_count")),
        "compare_passed_count": _int_value(aggregate.get("compare_passed_count")),
        "table_merge_content_gap_count": _int_value(aggregate.get("table_merge_content_gap_count")),
        "same_page_merge_docs_count": _int_value(aggregate.get("same_page_merge_docs_count")),
        "source_compare_metrics_paths": _list_value(_dict_value(source_readiness.get("inputs")).get("compare_metrics_paths")),
        "default_parser_change_ready": bool(decision.get("default_parser_change_ready")),
        "default_parser_change_blockers": _list_value(decision.get("default_parser_change_blockers")),
    }


def _derived_stress_lane(
    *,
    derived_rescue_readiness: dict[str, Any],
    derived_rescue_path: Path | None,
    derived_compare_metrics: dict[str, Any] | None,
    derived_compare_path: Path | None,
) -> dict[str, Any]:
    inputs = _dict_value(derived_rescue_readiness.get("inputs"))
    decision = _dict_value(derived_rescue_readiness.get("decision"))
    compare_metrics = _dict_value(derived_compare_metrics)
    candidate_backend = str(compare_metrics.get("candidate_backend") or "docling")
    candidate_metrics = _dict_value(_dict_value(compare_metrics.get("backend_metrics")).get(candidate_backend))
    comparison = _dict_value(compare_metrics.get("comparison"))
    return {
        "lane_id": "derived_ocr_repo_stress",
        "artifact_layer": "review_gate_artifact",
        "source_material_layer": "derived_review_artifact",
        "promotion_role": "derived_stress_review_only",
        "summary_path": str(derived_rescue_path) if derived_rescue_path is not None else None,
        "compare_metrics_path": str(derived_compare_path) if derived_compare_path is not None else None,
        "run_id": derived_rescue_readiness.get("run_id"),
        "compare_run_id": inputs.get("compare_run_id") or compare_metrics.get("run_id"),
        "readiness_passed": bool(decision.get("passed")),
        "same_page_rescue_ready": bool(decision.get("same_page_rescue_ready")),
        "runtime_default_unchanged": bool(decision.get("runtime_default_unchanged")),
        "default_change_review_eligible": False,
        "default_change_promotion_eligible": False,
        "document_count": _int_value(compare_metrics.get("document_count")),
        "compare_decision_passed": bool(_dict_value(comparison.get("decision")).get("passed")),
        "patched_prefix_truncation_count": _int_value(inputs.get("patched_prefix_truncation_count")),
        "post_patch_candidate_page_count": _int_value(inputs.get("post_patch_candidate_page_count")),
        "derived_table_content_gap_count": _int_value(inputs.get("derived_table_content_gap_count")),
        "same_page_table_rescue_doc_count": _int_value(candidate_metrics.get("docs_with_same_page_table_rescue_count")),
        "same_page_table_rescue_page_event_count": _int_value(
            candidate_metrics.get("same_page_table_rescue_page_event_count")
        ),
        "same_page_table_rescue_patched_cell_count": _int_value(
            candidate_metrics.get("same_page_table_rescue_patched_cell_count")
        ),
        "review_only_reason": (
            "derived OCR/repo-owned stress artifacts are useful for parser robustness review, "
            "but are not canonical source-PDF readiness evidence"
        ),
    }


def build_parser_eval_artifact_inventory_summary(
    *,
    source_readiness: dict[str, Any],
    source_readiness_path: Path | None,
    derived_rescue_readiness: dict[str, Any],
    derived_rescue_readiness_path: Path | None,
    derived_compare_metrics: dict[str, Any] | None,
    derived_compare_metrics_path: Path | None,
    run_id: str,
    load_errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    artifact_load_errors = list(load_errors or [])
    for _error in artifact_load_errors:
        _add_blocker(blockers, "artifact_load_error")

    source_lane = _source_readiness_lane(
        source_readiness=source_readiness,
        source_path=source_readiness_path,
    )
    derived_lane = _derived_stress_lane(
        derived_rescue_readiness=derived_rescue_readiness,
        derived_rescue_path=derived_rescue_readiness_path,
        derived_compare_metrics=derived_compare_metrics,
        derived_compare_path=derived_compare_metrics_path,
    )

    if not source_lane["readiness_passed"]:
        _add_blocker(blockers, "source_readiness_not_green")
    if not source_lane["baseline_parser_usable"]:
        _add_blocker(blockers, "source_baseline_parser_not_usable")
    if not source_lane["docling_optional_pilot_supported"]:
        _add_blocker(blockers, "source_docling_pilot_not_supported")
    if source_lane["default_parser_change_ready"]:
        _add_blocker(blockers, "source_readiness_unexpectedly_marks_default_change_ready")
    if not derived_lane["readiness_passed"]:
        _add_blocker(blockers, "derived_stress_readiness_not_green")
    if not derived_lane["same_page_rescue_ready"]:
        _add_blocker(blockers, "derived_same_page_rescue_not_ready")
    if not derived_lane["runtime_default_unchanged"]:
        _add_blocker(blockers, "derived_stress_changed_runtime_default")
    if derived_lane["document_count"] <= 0:
        _add_blocker(blockers, "derived_compare_metrics_missing_or_empty")
    if derived_lane["default_change_review_eligible"] or derived_lane["default_change_promotion_eligible"]:
        _add_blocker(blockers, "derived_stress_must_remain_review_only")

    default_change_review_document_count = (
        source_lane["document_count"] if source_lane["default_change_review_eligible"] else 0
    )
    return {
        "schema_version": "parser_eval_artifact_inventory.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "layer_classification": {
            "inventory_artifact_layer": "review_gate_artifact",
            "source_pdf_readiness_layer": "review_gate_artifact",
            "derived_stress_layer": "review_gate_artifact",
            "canonical_runtime_state_changed": False,
        },
        "lanes": {
            "source_pdf_readiness": source_lane,
            "derived_ocr_repo_stress": derived_lane,
        },
        "aggregate": {
            "source_readiness_document_count": source_lane["document_count"],
            "derived_stress_document_count": derived_lane["document_count"],
            "total_review_document_count": source_lane["document_count"] + derived_lane["document_count"],
            "default_change_review_document_count": default_change_review_document_count,
            "derived_review_only_document_count": derived_lane["document_count"],
            "default_change_review_eligible": source_lane["default_change_review_eligible"],
            "default_change_promotion_eligible": False,
        },
        "decision": {
            "passed": not blockers,
            "inventory_valid": not blockers,
            "baseline_parser_usable": source_lane["baseline_parser_usable"],
            "docling_optional_pilot_supported": bool(
                source_lane["docling_optional_pilot_supported"] and derived_lane["same_page_rescue_ready"]
            ),
            "default_parser_change_supported": False,
            "recommended_action": "keep_fitz_pdfplumber_default_and_docling_behind_flag",
            "blockers": blockers,
            "promotion_boundary": (
                "Only source-PDF readiness evidence counts toward default-change review. "
                "Derived OCR/repo stress evidence is review-only and must not be used as default-change promotion evidence."
            ),
            "decision_reason": (
                "parser eval artifacts are classified and the derived stress lane remains review-only"
                if not blockers
                else "parser eval artifact inventory found missing, regressed, or misclassified evidence"
            ),
        },
        "inputs": {
            "source_readiness_summary_path": (
                str(source_readiness_path) if source_readiness_path is not None else None
            ),
            "derived_rescue_readiness_summary_path": (
                str(derived_rescue_readiness_path) if derived_rescue_readiness_path is not None else None
            ),
            "derived_compare_metrics_path": (
                str(derived_compare_metrics_path) if derived_compare_metrics_path is not None else None
            ),
            "load_errors": artifact_load_errors,
        },
    }


def run_parser_eval_artifact_inventory(
    *,
    source_readiness_summary_path: Path,
    derived_rescue_readiness_summary_path: Path,
    derived_compare_metrics_path: Path | None,
    out_dir: Path,
    run_id: str,
) -> Path:
    source_path = _resolve_json_path(source_readiness_summary_path)
    derived_path = _resolve_json_path(derived_rescue_readiness_summary_path)
    source_readiness = _load_json_dict(source_path)
    derived_rescue_readiness = _load_json_dict(derived_path)
    derived_compare_metrics, resolved_compare_path, load_errors = _load_optional_compare_from_derived(
        derived_rescue_readiness,
        derived_compare_metrics_path,
    )
    summary = build_parser_eval_artifact_inventory_summary(
        source_readiness=source_readiness,
        source_readiness_path=source_path,
        derived_rescue_readiness=derived_rescue_readiness,
        derived_rescue_readiness_path=derived_path,
        derived_compare_metrics=derived_compare_metrics,
        derived_compare_metrics_path=resolved_compare_path,
        run_id=run_id,
        load_errors=load_errors,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def _compact_inventory_text(summary: dict[str, Any]) -> str:
    aggregate = _dict_value(summary.get("aggregate"))
    decision = _dict_value(summary.get("decision"))
    parts = [
        f"passed={bool(decision.get('passed'))}",
        f"source_docs={_int_value(aggregate.get('source_readiness_document_count'))}",
        f"derived_docs={_int_value(aggregate.get('derived_stress_document_count'))}",
        f"default_review_docs={_int_value(aggregate.get('default_change_review_document_count'))}",
        f"default_change_supported={bool(decision.get('default_parser_change_supported'))}",
        f"derived_review_only={_int_value(aggregate.get('derived_review_only_document_count')) > 0}",
    ]
    blockers = _list_value(decision.get("blockers"))
    if blockers:
        parts.append("blockers=" + ",".join(str(item) for item in blockers))
    return " ".join(parts)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory parser eval artifacts by evidence layer and default-change eligibility."
    )
    parser.add_argument("--source-readiness-summary", default=str(DEFAULT_SOURCE_READINESS_SUMMARY_PATH))
    parser.add_argument("--derived-rescue-readiness-summary", default=str(DEFAULT_DERIVED_RESCUE_READINESS_SUMMARY_PATH))
    parser.add_argument(
        "--derived-compare-metrics",
        default="",
        help="Optional compare_ingest_backends metrics path. Defaults to the path recorded in derived rescue readiness.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "parser_eval_artifact_inventory"),
        help="Directory to write parser eval inventory artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_parser_eval_artifact_inventory(
        source_readiness_summary_path=Path(args.source_readiness_summary),
        derived_rescue_readiness_summary_path=Path(args.derived_rescue_readiness_summary),
        derived_compare_metrics_path=Path(args.derived_compare_metrics) if str(args.derived_compare_metrics).strip() else None,
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    payload = _load_json_dict(run_root / "summary.json")
    print(f"[inventory_parser_eval_artifacts] out={run_root}")
    print(f"[inventory_parser_eval_artifacts] summary={run_root / 'summary.json'}")
    print("[inventory_parser_eval_artifacts] " + _compact_inventory_text(payload))
    return 0 if bool(_dict_value(payload.get("decision")).get("passed")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
