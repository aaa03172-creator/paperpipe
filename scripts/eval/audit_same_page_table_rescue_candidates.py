#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.eval.audit_table_merge_semantics import (  # noqa: E402
    _counter_to_dict,
    _meaningful_page_counters,
    classify_same_page_table_rescue_pair,
)
from src.ingest.parser_backends import create_parser_backend  # noqa: E402

DEFAULT_TABLE_MERGE_DETAILS_PATH = (
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "table_merge_audits"
    / "docling_same_page_merge_audit_derived_ocr_repo_20260424_r31"
    / "details.json"
)
DEFAULT_OUT_DIR = ROOT / "snapshots" / "ingest_backend_eval" / "same_page_table_rescue_candidates"

PageCounterLoader = Callable[[Path, str, str], tuple[dict[int, Counter[str]], dict[int, Counter[str]]]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _counter_from_mapping(value: Any) -> Counter[str]:
    counter: Counter[str] = Counter()
    for cell, count in _dict_value(value).items():
        normalized_cell = str(cell)
        normalized_count = _int_value(count)
        if normalized_cell and normalized_count > 0:
            counter[normalized_cell] += normalized_count
    return counter


def _load_meaningful_page_counters(
    pdf_path: Path,
    baseline_backend: str,
    candidate_backend: str,
) -> tuple[dict[int, Counter[str]], dict[int, Counter[str]]]:
    baseline_parser = create_parser_backend(baseline_backend)
    candidate_parser = create_parser_backend(candidate_backend)
    baseline_result = baseline_parser.extract_tables(pdf_path)
    candidate_result = candidate_parser.extract_tables(pdf_path)
    return (
        _meaningful_page_counters(baseline_result.tables),
        _meaningful_page_counters(candidate_result.tables),
    )


def _classify_rescue_page(
    *,
    page: int,
    missing_counter: Counter[str],
    baseline_pages: dict[int, Counter[str]],
    candidate_pages: dict[int, Counter[str]],
    min_overlap_ratio: float,
) -> dict[str, Any]:
    candidate_counter = candidate_pages.get(page, Counter())
    fallback_counter = baseline_pages.get(page, Counter())
    if not candidate_counter:
        return {
            "action": "skip_not_same_page_candidate",
            "reason": "candidate_has_no_table_counter_on_missing_cell_page",
            "overlap_ratio": 0.0,
            "covered_missing_cells": {},
            "unsupported_fallback_extra_cells": {},
            "candidate_prefix_truncation_repairs": [],
        }
    if not fallback_counter:
        return {
            "action": "skip_low_confidence",
            "reason": "fallback_has_no_table_counter_on_missing_cell_page",
            "overlap_ratio": 0.0,
            "covered_missing_cells": {},
            "unsupported_fallback_extra_cells": {},
            "candidate_prefix_truncation_repairs": [],
        }
    return classify_same_page_table_rescue_pair(
        missing_counter=missing_counter,
        candidate_counter=candidate_counter,
        fallback_counter=fallback_counter,
        min_overlap_ratio=min_overlap_ratio,
    )


def build_same_page_table_rescue_candidate_payloads(
    *,
    table_merge_details: dict[str, Any],
    table_merge_details_path: Path | None,
    run_id: str,
    min_overlap_ratio: float = 0.5,
    page_counter_loader: PageCounterLoader = _load_meaningful_page_counters,
) -> tuple[dict[str, Any], dict[str, Any]]:
    page_counter_cache: dict[tuple[str, str, str], tuple[dict[int, Counter[str]], dict[int, Counter[str]]]] = {}
    candidates: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    documents_with_candidates: set[str] = set()

    for document in _list_value(table_merge_details.get("documents")):
        doc = _dict_value(document)
        classification = _dict_value(doc.get("classification"))
        missing_cells_by_page = _dict_value(classification.get("missing_cells_by_page"))
        if not missing_cells_by_page:
            continue

        pdf_path = Path(str(doc.get("pdf_path") or ""))
        baseline_backend = str(doc.get("baseline_backend") or table_merge_details.get("baseline_backend") or "")
        candidate_backend = str(doc.get("candidate_backend") or table_merge_details.get("candidate_backend") or "")
        cache_key = (str(pdf_path), baseline_backend, candidate_backend)
        if cache_key not in page_counter_cache:
            page_counter_cache[cache_key] = page_counter_loader(pdf_path, baseline_backend, candidate_backend)
        baseline_pages, candidate_pages = page_counter_cache[cache_key]
        documents_with_candidates.add(str(pdf_path))

        for page_text, missing_cells in sorted(missing_cells_by_page.items(), key=lambda item: _int_value(item[0])):
            page = _int_value(page_text)
            missing_counter = _counter_from_mapping(missing_cells)
            result = _classify_rescue_page(
                page=page,
                missing_counter=missing_counter,
                baseline_pages=baseline_pages,
                candidate_pages=candidate_pages,
                min_overlap_ratio=min_overlap_ratio,
            )
            action = str(result.get("action") or "unknown")
            reason = str(result.get("reason") or "unknown")
            candidate_counter = candidate_pages.get(page, Counter())
            action_counts[action] += 1
            reason_counts[reason] += 1
            candidates.append(
                {
                    "pdf_path": str(pdf_path),
                    "page": page,
                    "baseline_backend": baseline_backend,
                    "candidate_backend": candidate_backend,
                    "current_runtime_behavior": (
                        "same_page_fallback_skipped"
                        if candidate_counter
                        else "not_same_page_rescue_candidate"
                    ),
                    "runtime_change_approved": False,
                    "missing_cells": _counter_to_dict(missing_counter),
                    "candidate_cell_count": sum(candidate_counter.values()),
                    "fallback_cell_count": sum(baseline_pages.get(page, Counter()).values()),
                    **result,
                }
            )

    details_payload = {
        "schema_version": "same_page_table_rescue_candidates.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "table_merge_details_path": str(table_merge_details_path or ""),
            "table_merge_run_id": str(table_merge_details.get("run_id") or ""),
            "min_overlap_ratio": min_overlap_ratio,
        },
        "candidates": candidates,
    }
    summary_payload = {
        "schema_version": "same_page_table_rescue_candidates.summary.v1",
        "generated_at": details_payload["generated_at"],
        "run_id": run_id,
        "status": "ok",
        "runtime_change_approved": False,
        "implementation_layer": "review_gate_artifact",
        "candidate_page_count": len(candidates),
        "document_count": len(documents_with_candidates),
        "action_counts": dict(sorted(action_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "recommended_runtime_posture": "keep_same_page_fallback_skip_until_runtime_rescue_is_approved",
        "details_path": "",
        "report_path": "",
    }
    return summary_payload, details_payload


def render_report(summary: dict[str, Any], details: dict[str, Any]) -> str:
    lines = [
        "# Same-Page Table Rescue Candidates",
        "",
        f"Run ID: `{summary.get('run_id')}`",
        "",
        "## Summary",
        "",
        f"- candidate pages: `{summary.get('candidate_page_count')}`",
        f"- runtime change approved: `{summary.get('runtime_change_approved')}`",
        f"- recommended runtime posture: `{summary.get('recommended_runtime_posture')}`",
        f"- action counts: `{json.dumps(summary.get('action_counts') or {}, sort_keys=True)}`",
        "",
        "## Candidates",
        "",
    ]
    candidates = _list_value(details.get("candidates"))
    if not candidates:
        lines.append("- none")
    for candidate in candidates:
        item = _dict_value(candidate)
        lines.append(
            "- "
            f"page `{item.get('page')}` "
            f"action `{item.get('action')}` "
            f"reason `{item.get('reason')}` "
            f"overlap `{item.get('overlap_ratio')}` "
            f"pdf `{item.get('pdf_path')}`"
        )
    lines.append("")
    lines.append("This report is review evidence only; it does not change parser output.")
    lines.append("")
    return "\n".join(lines)


def run_audit(
    *,
    table_merge_details_path: Path,
    out_dir: Path,
    run_id: str,
    min_overlap_ratio: float = 0.5,
) -> Path:
    table_merge_details = _load_json_dict(table_merge_details_path)
    summary_payload, details_payload = build_same_page_table_rescue_candidate_payloads(
        table_merge_details=table_merge_details,
        table_merge_details_path=table_merge_details_path,
        run_id=run_id,
        min_overlap_ratio=min_overlap_ratio,
    )

    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    details_path = run_root / "details.json"
    report_path = run_root / "report.md"
    summary_payload["details_path"] = str(details_path)
    summary_payload["report_path"] = str(report_path)
    _write_json(run_root / "summary.json", summary_payload)
    _write_json(details_path, details_payload)
    _write_text(report_path, render_report(summary_payload, details_payload))
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify review-only same-page table rescue candidates from table-merge audit details."
    )
    parser.add_argument(
        "--table-merge-details",
        default=str(DEFAULT_TABLE_MERGE_DETAILS_PATH),
        help="Path to table merge audit details.json.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for same-page rescue candidate artifacts.",
    )
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument("--min-overlap-ratio", type=float, default=0.5, help="Minimum same-table overlap ratio.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("same_page_table_rescue_candidates_%Y%m%d_%H%M%S")
    run_root = run_audit(
        table_merge_details_path=Path(str(args.table_merge_details)).expanduser().resolve(),
        out_dir=Path(str(args.out_dir)).expanduser().resolve(),
        run_id=run_id,
        min_overlap_ratio=float(args.min_overlap_ratio),
    )
    summary = _load_json_dict(run_root / "summary.json")
    print(
        "[audit_same_page_table_rescue_candidates] "
        f"out={run_root} "
        f"candidate_pages={summary.get('candidate_page_count')} "
        f"actions={summary.get('action_counts')}"
    )


if __name__ == "__main__":
    main()
