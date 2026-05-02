#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS_SUMMARY_PATH = (
    ROOT / "snapshots" / "parser_baseline_readiness" / "parser_baseline_readiness_20260424_r6" / "summary.json"
)
DEFAULT_SECTION_DETAILS_PATH = (
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "section_quality_audits"
    / "docling_section_quality_audit_refresh_20260423_r25"
    / "details.json"
)
DEFAULT_TABLE_MERGE_DETAILS_PATH = (
    ROOT
    / "snapshots"
    / "ingest_backend_eval"
    / "table_merge_audits"
    / "docling_same_page_merge_audit_refresh_20260423_r27"
    / "details.json"
)


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


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _round_float(value: Any, digits: int = 4) -> float:
    return round(_float_value(value), digits)


def _compact_blocker_triage_text(summary: dict[str, Any]) -> str:
    decision = _dict_value(summary.get("decision"))
    aggregate = _dict_value(summary.get("aggregate"))
    parts = [
        f"candidate_action={decision.get('candidate_action')}",
        f"table_runtime_patch_action={decision.get('table_runtime_patch_action')}",
        f"section_docs={_int_value(aggregate.get('section_blocker_doc_count'))}",
        f"missing_page_docs={_int_value(aggregate.get('section_missing_page_doc_count'))}",
        f"unclassified_low_ratio_docs={_int_value(aggregate.get('section_unclassified_low_ratio_doc_count'))}",
        f"table_gap_docs={_int_value(aggregate.get('table_merge_content_gap_doc_count'))}",
        f"table_missing_cells={_int_value(aggregate.get('table_merge_missing_cell_count'))}",
        f"table_truncation_pairs={_int_value(aggregate.get('table_candidate_truncation_pair_count'))}",
        f"table_duplicate_risk_pages={_int_value(aggregate.get('table_same_page_duplicate_risk_page_count'))}",
    ]
    return " ".join(parts)


def _classify_section_page(page: dict[str, Any]) -> str:
    bucket = str(page.get("review_bucket") or "").strip()
    signals = {str(item) for item in _list_value(page.get("review_signals"))}
    ratio = _float_value(page.get("ratio"))
    baseline_digit_ratio = _float_value(page.get("baseline_digit_ratio"))
    baseline_chars = _int_value(page.get("baseline_char_count"))
    candidate_chars = _int_value(page.get("candidate_char_count"))

    if bucket and bucket != "needs_manual_review":
        return f"{bucket}_review"
    if baseline_digit_ratio >= 0.2:
        return "numeric_dense_page_manual_review"
    if candidate_chars <= 32 and baseline_chars <= 200:
        return "short_low_candidate_page_manual_review"
    if candidate_chars == 0 or ratio <= 0.05:
        return "near_empty_candidate_page_manual_review"
    if "baseline_table_page" in signals or "candidate_table_page" in signals:
        return "table_signal_page_manual_review"
    return "unclassified_low_ratio_manual_review"


def _section_document_triage(document: dict[str, Any]) -> dict[str, Any] | None:
    classification = _dict_value(document.get("classification"))
    missing_pages = [_int_value(page) for page in _list_value(classification.get("missing_substantive_pages"))]
    low_pages = [_dict_value(page) for page in _list_value(classification.get("low_page_text_ratio_pages"))]
    unclassified_pages = [
        page for page in low_pages if str(page.get("review_bucket") or "").strip() == "needs_manual_review"
    ]
    if not missing_pages and not unclassified_pages:
        return None

    page_triages: list[dict[str, Any]] = []
    for page in unclassified_pages:
        page_triages.append(
            {
                "page": _int_value(page.get("page")),
                "triage_bucket": _classify_section_page(page),
                "baseline_char_count": _int_value(page.get("baseline_char_count")),
                "candidate_char_count": _int_value(page.get("candidate_char_count")),
                "ratio": _round_float(page.get("ratio")),
                "baseline_digit_ratio": _round_float(page.get("baseline_digit_ratio")),
                "candidate_digit_ratio": _round_float(page.get("candidate_digit_ratio")),
                "review_signals": _list_value(page.get("review_signals")),
            }
        )

    total_ratio = _round_float(classification.get("total_text_ratio"))
    return {
        "pdf_path": str(document.get("pdf_path") or ""),
        "missing_substantive_pages": missing_pages,
        "unclassified_low_ratio_pages": page_triages,
        "baseline_section_count": _int_value(classification.get("baseline_section_count")),
        "candidate_section_count": _int_value(classification.get("candidate_section_count")),
        "baseline_total_text_chars": _int_value(classification.get("baseline_total_text_chars")),
        "candidate_total_text_chars": _int_value(classification.get("candidate_total_text_chars")),
        "total_text_ratio": total_ratio,
        "triage_recommendation": (
            "manual_section_page_review_required"
            if missing_pages
            else "manual_low_ratio_bucket_review_required"
        ),
    }


def _candidate_truncation_pairs(
    missing_cell_counts: dict[str, Any],
    extra_cell_counts: dict[str, Any],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for missing_cell in sorted(str(cell) for cell in missing_cell_counts):
        missing_count = _int_value(missing_cell_counts.get(missing_cell))
        if missing_count <= 0:
            continue
        for candidate_cell in sorted(str(cell) for cell in extra_cell_counts):
            candidate_count = _int_value(extra_cell_counts.get(candidate_cell))
            if candidate_count <= 0:
                continue
            if len(candidate_cell) < 4 or len(candidate_cell) >= len(missing_cell):
                continue
            if not missing_cell.startswith(candidate_cell):
                continue
            ratio = float(len(candidate_cell)) / float(len(missing_cell))
            if ratio < 0.5:
                continue
            missing_suffix = missing_cell[len(candidate_cell) :]
            pairs.append(
                {
                    "missing_cell": missing_cell,
                    "candidate_cell": candidate_cell,
                    "missing_suffix": missing_suffix,
                    "missing_count": missing_count,
                    "candidate_count": candidate_count,
                    "candidate_length_ratio": round(ratio, 4),
                    "review_reason": "candidate_prefix_truncates_baseline_cell",
                }
            )
    return sorted(
        pairs,
        key=lambda item: (
            -float(item["candidate_length_ratio"]),
            str(item["missing_cell"]),
            str(item["candidate_cell"]),
        ),
    )[:limit]


def _table_document_triage(document: dict[str, Any]) -> dict[str, Any] | None:
    classification = _dict_value(document.get("classification"))
    missing_pages = [_int_value(page) for page in _list_value(classification.get("missing_pages"))]
    missing_cells_total = _int_value(classification.get("missing_cells_total"))
    if not missing_pages and missing_cells_total <= 0:
        return None

    missing_cells_by_page = _dict_value(classification.get("missing_cells_by_page"))
    extra_cells_by_page = _dict_value(classification.get("extra_cells_by_page"))
    pages = []
    for page, cells in sorted(missing_cells_by_page.items(), key=lambda item: _int_value(item[0])):
        cell_counts = _dict_value(cells)
        extra_cell_counts = _dict_value(extra_cells_by_page.get(str(page)))
        extra_cell_count = sum(_int_value(count) for count in extra_cell_counts.values())
        duplicate_risk = bool(extra_cell_count and _int_value(page) not in missing_pages)
        pages.append(
            {
                "page": _int_value(page),
                "missing_cell_count": sum(_int_value(count) for count in cell_counts.values()),
                "extra_cell_count": extra_cell_count,
                "sample_missing_cells": sorted(str(cell) for cell in cell_counts)[:5],
                "sample_extra_cells": sorted(str(cell) for cell in extra_cell_counts)[:5],
                "candidate_truncation_pairs": _candidate_truncation_pairs(cell_counts, extra_cell_counts),
                "same_page_fallback_duplicate_risk": duplicate_risk,
                "fallback_patch_risk": (
                    "same_page_fallback_may_duplicate_candidate_table_cells"
                    if duplicate_risk
                    else "missing_page_or_empty_candidate_page_lower_duplicate_risk"
                ),
            }
        )

    return {
        "pdf_path": str(document.get("pdf_path") or ""),
        "missing_pages": missing_pages,
        "missing_cells_total": missing_cells_total,
        "extra_cells_total": _int_value(classification.get("extra_cells_total")),
        "pages": pages,
        "triage_recommendation": "manual_table_merge_content_review_required",
    }


def _table_runtime_patch_action(table_documents: list[dict[str, Any]], *, duplicate_risk_page_count: int) -> str:
    if duplicate_risk_page_count > 0:
        return "hold_same_page_table_fallback_pending_duplicate_safe_rescue"
    if table_documents:
        return "manual_table_gap_review_before_runtime_patch"
    return "no_table_runtime_patch_needed"


def build_parser_readiness_blocker_triage_summary(
    *,
    readiness_summary: dict[str, Any],
    readiness_summary_path: Path | None,
    section_details: dict[str, Any],
    section_details_path: Path | None,
    table_merge_details: dict[str, Any],
    table_merge_details_path: Path | None,
    run_id: str,
) -> dict[str, Any]:
    section_documents = [
        item
        for item in (_section_document_triage(_dict_value(document)) for document in _list_value(section_details.get("documents")))
        if item is not None
    ]
    table_documents = [
        item
        for item in (
            _table_document_triage(_dict_value(document)) for document in _list_value(table_merge_details.get("documents"))
        )
        if item is not None
    ]

    section_page_bucket_counts: Counter[str] = Counter()
    missing_page_count = 0
    unclassified_low_ratio_page_count = 0
    for document in section_documents:
        missing_page_count += len(_list_value(document.get("missing_substantive_pages")))
        pages = _list_value(document.get("unclassified_low_ratio_pages"))
        unclassified_low_ratio_page_count += len(pages)
        section_page_bucket_counts.update(str(page.get("triage_bucket") or "") for page in pages)

    table_missing_cell_count = sum(_int_value(document.get("missing_cells_total")) for document in table_documents)
    table_candidate_truncation_pair_count = sum(
        len(_list_value(page.get("candidate_truncation_pairs")))
        for document in table_documents
        for page in _list_value(document.get("pages"))
    )
    table_same_page_duplicate_risk_page_count = sum(
        1
        for document in table_documents
        for page in _list_value(document.get("pages"))
        if bool(page.get("same_page_fallback_duplicate_risk"))
    )
    readiness_decision = _dict_value(readiness_summary.get("decision"))
    readiness_blockers = [str(item) for item in _list_value(readiness_decision.get("blockers"))]
    candidate_hold = bool(section_documents or table_documents or readiness_blockers)

    return {
        "schema_version": "parser_readiness_blocker_triage.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "readiness_summary_path": str(readiness_summary_path) if readiness_summary_path is not None else None,
            "readiness_run_id": readiness_summary.get("run_id"),
            "section_details_path": str(section_details_path) if section_details_path is not None else None,
            "section_details_run_id": section_details.get("run_id"),
            "table_merge_details_path": str(table_merge_details_path)
            if table_merge_details_path is not None
            else None,
            "table_merge_details_run_id": table_merge_details.get("run_id"),
        },
        "aggregate": {
            "readiness_blockers": readiness_blockers,
            "section_blocker_doc_count": len(section_documents),
            "section_missing_page_doc_count": sum(
                1 for document in section_documents if _list_value(document.get("missing_substantive_pages"))
            ),
            "section_missing_page_count": missing_page_count,
            "section_unclassified_low_ratio_doc_count": sum(
                1 for document in section_documents if _list_value(document.get("unclassified_low_ratio_pages"))
            ),
            "section_unclassified_low_ratio_page_count": unclassified_low_ratio_page_count,
            "section_page_triage_bucket_counts": dict(sorted(section_page_bucket_counts.items())),
            "table_merge_content_gap_doc_count": len(table_documents),
            "table_merge_missing_cell_count": table_missing_cell_count,
            "table_candidate_truncation_pair_count": table_candidate_truncation_pair_count,
            "table_same_page_duplicate_risk_page_count": table_same_page_duplicate_risk_page_count,
        },
        "section_blockers": section_documents,
        "table_merge_blockers": table_documents,
        "decision": {
            "baseline_action": "keep_fitz_pdfplumber_default",
            "candidate_action": (
                "hold_docling_pilot_pending_manual_review" if candidate_hold else "no_candidate_blockers_detected"
            ),
            "table_runtime_patch_action": _table_runtime_patch_action(
                table_documents,
                duplicate_risk_page_count=table_same_page_duplicate_risk_page_count,
            ),
            "default_parser_change_ready": False,
            "next_patch_lane": (
                "manual_review_then_targeted_parser_or_audit_patch"
                if candidate_hold
                else "readiness_refresh_or_default_change_review"
            ),
            "decision_reason": (
                "Docling should stay behind-flag while section-page and table-merge blockers are reviewed."
                if candidate_hold
                else "No section-page or table-merge blockers were found in the supplied details."
            ),
        },
    }


def run_parser_readiness_blocker_triage(
    *,
    readiness_summary_path: Path,
    section_details_path: Path,
    table_merge_details_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    readiness_path = _resolve_json_path(readiness_summary_path, default_filename="summary.json")
    section_path = _resolve_json_path(section_details_path, default_filename="details.json")
    table_path = _resolve_json_path(table_merge_details_path, default_filename="details.json")
    summary = build_parser_readiness_blocker_triage_summary(
        readiness_summary=_load_json_dict(readiness_path),
        readiness_summary_path=readiness_path,
        section_details=_load_json_dict(section_path),
        section_details_path=section_path,
        table_merge_details=_load_json_dict(table_path),
        table_merge_details_path=table_path,
        run_id=run_id,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize parser-readiness blockers into manual-review buckets without changing parser runtime behavior."
    )
    parser.add_argument(
        "--readiness-summary",
        default=str(DEFAULT_READINESS_SUMMARY_PATH),
        help="Path to parser baseline readiness summary.json or its run directory.",
    )
    parser.add_argument(
        "--section-details",
        default=str(DEFAULT_SECTION_DETAILS_PATH),
        help="Path to audit_section_quality details.json or its run directory.",
    )
    parser.add_argument(
        "--table-merge-details",
        default=str(DEFAULT_TABLE_MERGE_DETAILS_PATH),
        help="Path to audit_table_merge_semantics details.json or its run directory.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "parser_readiness_blocker_triage"),
        help="Directory to write the blocker triage summary into.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_parser_readiness_blocker_triage(
        readiness_summary_path=Path(args.readiness_summary),
        section_details_path=Path(args.section_details),
        table_merge_details_path=Path(args.table_merge_details),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    payload = _load_json_dict(run_root / "summary.json")
    print(f"[summarize_parser_readiness_blockers] out={run_root}")
    print(f"[summarize_parser_readiness_blockers] summary={run_root / 'summary.json'}")
    print("[summarize_parser_readiness_blockers] " + _compact_blocker_triage_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
