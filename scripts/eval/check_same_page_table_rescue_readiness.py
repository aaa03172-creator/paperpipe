#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPARE_METRICS_PATH = (
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "docling_pilot_manifest_derived_ocr_repo_20260426_r33"
    / "metrics.json"
)
DEFAULT_TABLE_MERGE_SUMMARY_PATH = (
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "table_merge_audits"
    / "docling_same_page_merge_audit_derived_ocr_repo_20260426_r33"
    / "summary.json"
)
DEFAULT_BLOCKER_TRIAGE_SUMMARY_PATH = (
    ROOT
    / "snapshots"
    / "parser_readiness_blocker_triage"
    / "parser_readiness_blocker_triage_derived_ocr_repo_20260426_r16"
    / "summary.json"
)
DEFAULT_RESCUE_CANDIDATE_SUMMARY_PATH = (
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "same_page_table_rescue_candidates"
    / "same_page_table_rescue_candidates_derived_ocr_repo_20260426_r3"
    / "summary.json"
)
DEFAULT_PARSER_READINESS_SUMMARY_PATH = (
    ROOT
    / "snapshots"
    / "parser_baseline_readiness"
    / "parser_baseline_readiness_20260424_r8"
    / "summary.json"
)

PATCH_TAXONOMY = "SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION"
SKIPPED_TAXONOMY = "FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED"


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


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _add_blocker(blockers: list[str], code: str) -> None:
    if code not in blockers:
        blockers.append(code)


def _candidate_taxonomy_counts(compare_metrics: dict[str, Any]) -> dict[str, Any]:
    backend_metrics = _dict_value(compare_metrics.get("backend_metrics"))
    candidate_backend = str(compare_metrics.get("candidate_backend") or "docling")
    candidate = _dict_value(backend_metrics.get(candidate_backend))
    return _dict_value(candidate.get("table_failure_taxonomy_counts"))


def _compact_rescue_readiness_text(summary: dict[str, Any]) -> str:
    inputs = _dict_value(summary.get("inputs"))
    decision = _dict_value(summary.get("decision"))
    parts = [
        f"passed={bool(decision.get('passed'))}",
        f"patches={_int_value(inputs.get('patched_prefix_truncation_count'))}",
        f"remaining_candidates={_int_value(inputs.get('post_patch_candidate_page_count'))}",
        f"derived_table_gaps={_int_value(inputs.get('derived_table_content_gap_count'))}",
        f"source_docs={_int_value(inputs.get('source_readiness_compare_document_count'))}",
        f"default_change_ready={bool(inputs.get('default_parser_change_ready'))}",
    ]
    action = str(inputs.get("table_runtime_patch_action") or "").strip()
    if action:
        parts.append(f"table_runtime_patch_action={action}")
    blockers = decision.get("blockers")
    if isinstance(blockers, list) and blockers:
        parts.append("blockers=" + ",".join(str(item) for item in blockers))
    return " ".join(parts)


def build_same_page_table_rescue_readiness_summary(
    *,
    compare_metrics: dict[str, Any],
    table_merge_summary: dict[str, Any],
    blocker_triage_summary: dict[str, Any],
    rescue_candidate_summary: dict[str, Any],
    parser_readiness_summary: dict[str, Any],
    compare_metrics_path: Path | None,
    table_merge_summary_path: Path | None,
    blocker_triage_summary_path: Path | None,
    rescue_candidate_summary_path: Path | None,
    parser_readiness_summary_path: Path | None,
    run_id: str,
    min_patch_count: int = 1,
    max_remaining_candidate_pages: int = 0,
    min_source_readiness_document_count: int = 53,
) -> dict[str, Any]:
    taxonomy = _candidate_taxonomy_counts(compare_metrics)
    comparison = _dict_value(compare_metrics.get("comparison"))
    compare_decision = _dict_value(comparison.get("decision"))
    triage_aggregate = _dict_value(blocker_triage_summary.get("aggregate"))
    triage_decision = _dict_value(blocker_triage_summary.get("decision"))
    parser_aggregate = _dict_value(parser_readiness_summary.get("aggregate"))
    parser_decision = _dict_value(parser_readiness_summary.get("decision"))

    patched_count = _int_value(taxonomy.get(PATCH_TAXONOMY))
    skipped_count = _int_value(taxonomy.get(SKIPPED_TAXONOMY))
    derived_content_gaps = _int_value(table_merge_summary.get("content_gap_count"))
    triage_table_gaps = _int_value(triage_aggregate.get("table_merge_content_gap_doc_count"))
    triage_truncation_pairs = _int_value(triage_aggregate.get("table_candidate_truncation_pair_count"))
    triage_duplicate_risk_pages = _int_value(triage_aggregate.get("table_same_page_duplicate_risk_page_count"))
    remaining_candidate_pages = _int_value(rescue_candidate_summary.get("candidate_page_count"))
    source_readiness_docs = _int_value(parser_aggregate.get("compare_document_count"))
    source_table_gaps = _int_value(parser_aggregate.get("table_merge_content_gap_count"))

    blockers: list[str] = []
    if not bool(compare_decision.get("passed")):
        _add_blocker(blockers, "derived_compare_decision_failed")
    if patched_count < int(max(min_patch_count, 0)):
        _add_blocker(blockers, "same_page_rescue_patch_taxonomy_missing")
    if derived_content_gaps:
        _add_blocker(blockers, "derived_table_content_gaps_present")
    if triage_table_gaps:
        _add_blocker(blockers, "blocker_triage_table_gaps_present")
    if triage_truncation_pairs:
        _add_blocker(blockers, "blocker_triage_truncation_pairs_present")
    if triage_duplicate_risk_pages:
        _add_blocker(blockers, "blocker_triage_duplicate_risk_pages_present")
    if triage_decision.get("candidate_action") != "no_candidate_blockers_detected":
        _add_blocker(blockers, "blocker_triage_candidate_action_not_clear")
    if triage_decision.get("table_runtime_patch_action") != "no_table_runtime_patch_needed":
        _add_blocker(blockers, "blocker_triage_runtime_patch_action_not_clear")
    if remaining_candidate_pages > int(max(max_remaining_candidate_pages, 0)):
        _add_blocker(blockers, "post_patch_rescue_candidates_remaining")
    if bool(rescue_candidate_summary.get("runtime_change_approved")):
        _add_blocker(blockers, "rescue_candidate_sidecar_must_not_approve_runtime_change")
    if not bool(parser_decision.get("passed")):
        _add_blocker(blockers, "source_parser_readiness_not_green")
    if not bool(parser_decision.get("docling_optional_pilot_supported")):
        _add_blocker(blockers, "source_docling_pilot_not_supported")
    if bool(parser_decision.get("default_parser_change_ready")):
        _add_blocker(blockers, "default_parser_change_unexpectedly_ready")
    if source_readiness_docs < int(max(min_source_readiness_document_count, 0)):
        _add_blocker(blockers, "source_readiness_document_count_below_floor")
    if source_table_gaps:
        _add_blocker(blockers, "source_table_merge_gaps_present")

    generated_at = _utc_now_iso()
    return {
        "schema_version": "same_page_table_rescue_readiness.v1",
        "generated_at": generated_at,
        "run_id": run_id,
        "thresholds": {
            "min_patch_count": int(max(min_patch_count, 0)),
            "max_remaining_candidate_pages": int(max(max_remaining_candidate_pages, 0)),
            "min_source_readiness_document_count": int(max(min_source_readiness_document_count, 0)),
        },
        "inputs": {
            "compare_metrics_path": str(compare_metrics_path) if compare_metrics_path is not None else None,
            "table_merge_summary_path": str(table_merge_summary_path) if table_merge_summary_path is not None else None,
            "blocker_triage_summary_path": (
                str(blocker_triage_summary_path) if blocker_triage_summary_path is not None else None
            ),
            "rescue_candidate_summary_path": (
                str(rescue_candidate_summary_path) if rescue_candidate_summary_path is not None else None
            ),
            "parser_readiness_summary_path": (
                str(parser_readiness_summary_path) if parser_readiness_summary_path is not None else None
            ),
            "compare_run_id": compare_metrics.get("run_id"),
            "table_merge_run_id": table_merge_summary.get("run_id"),
            "blocker_triage_run_id": blocker_triage_summary.get("run_id"),
            "rescue_candidate_run_id": rescue_candidate_summary.get("run_id"),
            "parser_readiness_run_id": parser_readiness_summary.get("run_id"),
            "patched_prefix_truncation_count": patched_count,
            "skipped_primary_page_fallback_count": skipped_count,
            "derived_table_content_gap_count": derived_content_gaps,
            "table_candidate_truncation_pair_count": triage_truncation_pairs,
            "table_same_page_duplicate_risk_page_count": triage_duplicate_risk_pages,
            "table_runtime_patch_action": triage_decision.get("table_runtime_patch_action"),
            "post_patch_candidate_page_count": remaining_candidate_pages,
            "source_readiness_compare_document_count": source_readiness_docs,
            "source_table_merge_content_gap_count": source_table_gaps,
            "default_parser_change_ready": bool(parser_decision.get("default_parser_change_ready")),
        },
        "decision": {
            "passed": not blockers,
            "same_page_rescue_ready": not blockers,
            "runtime_default_unchanged": not bool(parser_decision.get("default_parser_change_ready")),
            "blockers": blockers,
            "decision_reason": (
                "bounded same-page prefix-truncation rescue remains verified and default parser promotion remains blocked"
                if not blockers
                else "same-page table rescue evidence is missing, regressed, or no longer aligned with parser readiness"
            ),
        },
    }


def run_same_page_table_rescue_readiness(
    *,
    compare_metrics_path: Path,
    table_merge_summary_path: Path,
    blocker_triage_summary_path: Path,
    rescue_candidate_summary_path: Path,
    parser_readiness_summary_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    compare_path = _resolve_json_path(compare_metrics_path, default_filename="metrics.json")
    table_path = _resolve_json_path(table_merge_summary_path)
    triage_path = _resolve_json_path(blocker_triage_summary_path)
    rescue_path = _resolve_json_path(rescue_candidate_summary_path)
    readiness_path = _resolve_json_path(parser_readiness_summary_path)
    summary = build_same_page_table_rescue_readiness_summary(
        compare_metrics=_load_json_dict(compare_path),
        table_merge_summary=_load_json_dict(table_path),
        blocker_triage_summary=_load_json_dict(triage_path),
        rescue_candidate_summary=_load_json_dict(rescue_path),
        parser_readiness_summary=_load_json_dict(readiness_path),
        compare_metrics_path=compare_path,
        table_merge_summary_path=table_path,
        blocker_triage_summary_path=triage_path,
        rescue_candidate_summary_path=rescue_path,
        parser_readiness_summary_path=readiness_path,
        run_id=run_id,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check saved same-page table rescue evidence and source parser readiness stay aligned."
    )
    parser.add_argument("--compare-metrics", default=str(DEFAULT_COMPARE_METRICS_PATH))
    parser.add_argument("--table-merge-summary", default=str(DEFAULT_TABLE_MERGE_SUMMARY_PATH))
    parser.add_argument("--blocker-triage-summary", default=str(DEFAULT_BLOCKER_TRIAGE_SUMMARY_PATH))
    parser.add_argument("--rescue-candidate-summary", default=str(DEFAULT_RESCUE_CANDIDATE_SUMMARY_PATH))
    parser.add_argument("--parser-readiness-summary", default=str(DEFAULT_PARSER_READINESS_SUMMARY_PATH))
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "same_page_table_rescue_readiness"),
        help="Directory to write readiness summary artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_same_page_table_rescue_readiness(
        compare_metrics_path=Path(args.compare_metrics),
        table_merge_summary_path=Path(args.table_merge_summary),
        blocker_triage_summary_path=Path(args.blocker_triage_summary),
        rescue_candidate_summary_path=Path(args.rescue_candidate_summary),
        parser_readiness_summary_path=Path(args.parser_readiness_summary),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    payload = _load_json_dict(run_root / "summary.json")
    print(f"[check_same_page_table_rescue_readiness] out={run_root}")
    print(f"[check_same_page_table_rescue_readiness] summary={run_root / 'summary.json'}")
    print("[check_same_page_table_rescue_readiness] " + _compact_rescue_readiness_text(payload))
    return 0 if bool(_dict_value(payload.get("decision")).get("passed")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
