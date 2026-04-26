#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.parser_backends import create_parser_backend


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_cell(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^a-z0-9*†-]", "", text)
    return text


def _is_meaningful_table(table: Any) -> bool:
    data = list(getattr(table, "data", None) or [])
    rows = len(data)
    cols = max((len(row) for row in data), default=0)
    flattened = [str(cell or "").strip() for row in data for cell in row]
    non_empty_cells = sum(1 for cell in flattened if cell)
    alpha_cells = sum(1 for cell in flattened if any(ch.isalpha() for ch in cell))
    return rows >= 2 and cols >= 2 and non_empty_cells >= 6 and alpha_cells >= 2


def _meaningful_page_counters(tables: list[Any]) -> dict[int, Counter[str]]:
    by_page: dict[int, Counter[str]] = {}
    for table in tables:
        if not _is_meaningful_table(table):
            continue
        page = int(getattr(table, "source_page", 0) or 0)
        if page <= 0:
            continue
        page_counter = by_page.setdefault(page, Counter())
        for row in list(getattr(table, "data", None) or []):
            for cell in row:
                normalized = _normalize_cell(cell)
                if normalized:
                    page_counter[normalized] += 1
    return by_page


def _counter_to_dict(counter: Counter[str], limit: int = 20) -> dict[str, int]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return {key: value for key, value in ordered[:limit]}


def _cell_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _find_single_cell_match(
    baseline_cell: str,
    candidate_counter: Counter[str],
    *,
    min_similarity: float = 0.94,
) -> dict[str, Any] | None:
    generic_suffixes = ("supplement",)
    best: dict[str, Any] | None = None
    for candidate_cell, count in candidate_counter.items():
        if count <= 0 or not candidate_cell:
            continue
        strategy = ""
        similarity = _cell_similarity(baseline_cell, candidate_cell)
        if baseline_cell in candidate_cell and len(baseline_cell) >= 4:
            strategy = "candidate_contains_baseline"
            similarity = 1.0
        elif (
            candidate_cell in baseline_cell
            and len(candidate_cell) >= 8
            and len(candidate_cell) / max(len(baseline_cell), 1) >= 0.9
        ):
            strategy = "candidate_nearly_contains_baseline"
            similarity = max(similarity, len(candidate_cell) / max(len(baseline_cell), 1))
        elif similarity >= min_similarity:
            strategy = "high_similarity"
        else:
            for suffix in generic_suffixes:
                stem = baseline_cell.removesuffix(suffix)
                if (
                    stem != baseline_cell
                    and candidate_cell == stem
                    and len(candidate_cell) / max(len(baseline_cell), 1) >= 0.65
                ):
                    strategy = "generic_suffix_truncation"
                    similarity = max(similarity, len(candidate_cell) / max(len(baseline_cell), 1))
                    break

        if not strategy:
            continue
        candidate = {
            "candidate_cell": candidate_cell,
            "strategy": strategy,
            "similarity": round(similarity, 4),
        }
        if best is None or float(candidate["similarity"]) > float(best["similarity"]):
            best = candidate
    return best


def _find_fragment_cell_match(baseline_cell: str, candidate_counter: Counter[str]) -> dict[str, Any] | None:
    remaining = baseline_cell
    used: list[str] = []
    local_counts: Counter[str] = Counter()

    while remaining:
        candidates = [
            cell
            for cell, count in candidate_counter.items()
            if count > local_counts[cell] and len(cell) >= 3 and cell in remaining
        ]
        if not candidates:
            return None
        best = max(candidates, key=len)
        remaining = remaining.replace(best, "", 1)
        used.append(best)
        local_counts[best] += 1

    if len(used) < 2:
        return None
    return {
        "candidate_cell": "+".join(used),
        "candidate_fragments": used,
        "strategy": "candidate_fragments_cover_baseline",
        "similarity": 1.0,
    }


def _pop_near_cell_match(baseline_cell: str, candidate_counter: Counter[str]) -> dict[str, Any] | None:
    match = _find_single_cell_match(baseline_cell, candidate_counter)
    if match is None:
        match = _find_fragment_cell_match(baseline_cell, candidate_counter)
    if match is None:
        return None

    if match.get("candidate_fragments"):
        for fragment in list(match.get("candidate_fragments") or []):
            candidate_counter[str(fragment)] -= 1
            if candidate_counter[str(fragment)] <= 0:
                del candidate_counter[str(fragment)]
    else:
        candidate_cell = str(match.get("candidate_cell") or "")
        candidate_counter[candidate_cell] -= 1
        if candidate_counter[candidate_cell] <= 0:
            del candidate_counter[candidate_cell]
    return match


def _counter_overlap_ratio(left: Counter[str], right: Counter[str]) -> float:
    left_total = sum(count for count in left.values() if count > 0)
    right_total = sum(count for count in right.values() if count > 0)
    denominator = min(left_total, right_total)
    if denominator <= 0:
        return 0.0
    overlap = sum((left & right).values())
    return round(overlap / denominator, 4)


def _missing_cells_covered_by_fallback(
    missing_counter: Counter[str], fallback_counter: Counter[str]
) -> Counter[str]:
    return Counter({cell: count for cell, count in (missing_counter & fallback_counter).items() if count > 0})


def _candidate_prefix_truncation_repairs(
    missing_counter: Counter[str],
    candidate_counter: Counter[str],
    fallback_counter: Counter[str],
) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    covered_missing = _missing_cells_covered_by_fallback(missing_counter, fallback_counter)
    for missing_cell, missing_count in sorted(covered_missing.items()):
        for candidate_cell, candidate_count in sorted(candidate_counter.items()):
            if candidate_count <= 0:
                continue
            if len(candidate_cell) < 4 or len(candidate_cell) >= len(missing_cell):
                continue
            if not missing_cell.startswith(candidate_cell):
                continue
            repairs.append(
                {
                    "missing_cell": missing_cell,
                    "candidate_cell": candidate_cell,
                    "missing_suffix": missing_cell[len(candidate_cell) :],
                    "missing_count": missing_count,
                    "candidate_count": candidate_count,
                }
            )
    return repairs


def classify_same_page_table_rescue_pair(
    *,
    missing_counter: Counter[str],
    candidate_counter: Counter[str],
    fallback_counter: Counter[str],
    min_overlap_ratio: float = 0.5,
) -> dict[str, Any]:
    overlap_ratio = _counter_overlap_ratio(candidate_counter, fallback_counter)
    covered_missing = _missing_cells_covered_by_fallback(missing_counter, fallback_counter)
    repairs = _candidate_prefix_truncation_repairs(missing_counter, candidate_counter, fallback_counter)
    fallback_extra = fallback_counter - candidate_counter
    unsupported_fallback_extra = fallback_extra - covered_missing

    if not missing_counter:
        action = "skip_no_missing_cells"
        reason = "candidate_table_has_no_missing_cells_to_repair"
    elif not covered_missing:
        action = "skip_low_confidence"
        reason = "fallback_table_does_not_cover_missing_cells"
    elif overlap_ratio < min_overlap_ratio:
        action = "skip_low_confidence"
        reason = "candidate_and_fallback_tables_do_not_share_enough_cells"
    elif repairs:
        action = "patch"
        reason = "fallback_covers_candidate_prefix_truncation"
    elif not unsupported_fallback_extra:
        action = "replace"
        reason = "fallback_adds_missing_cells_without_unsupported_extras"
    else:
        action = "skip_duplicate_risk"
        reason = "fallback_contains_unsupported_extra_cells"

    return {
        "action": action,
        "reason": reason,
        "overlap_ratio": overlap_ratio,
        "covered_missing_cells": _counter_to_dict(covered_missing),
        "unsupported_fallback_extra_cells": _counter_to_dict(unsupported_fallback_extra),
        "candidate_prefix_truncation_repairs": repairs,
    }


def classify_page_cell_coverage(
    baseline_pages: dict[int, Counter[str]], candidate_pages: dict[int, Counter[str]]
) -> dict[str, Any]:
    baseline_page_ids = sorted(baseline_pages)
    candidate_page_ids = sorted(candidate_pages)
    missing_pages = [page for page in baseline_page_ids if page not in candidate_page_ids]

    missing_cells_by_page: dict[int, Counter[str]] = {}
    extra_cells_by_page: dict[int, Counter[str]] = {}
    near_matched_cells_by_page: dict[int, Counter[str]] = {}
    near_match_examples_by_page: dict[int, list[dict[str, Any]]] = {}
    for page in baseline_page_ids:
        baseline_counter = baseline_pages.get(page, Counter())
        candidate_counter = candidate_pages.get(page, Counter())
        candidate_remainder = candidate_counter - baseline_counter
        missing = Counter()
        for baseline_cell, count in (baseline_counter - candidate_counter).items():
            for _idx in range(count):
                match = _pop_near_cell_match(baseline_cell, candidate_remainder)
                if match is None:
                    missing[baseline_cell] += 1
                    continue
                near_matched_cells_by_page.setdefault(page, Counter())[baseline_cell] += 1
                near_match_examples_by_page.setdefault(page, []).append(
                    {
                        "baseline_cell": baseline_cell,
                        **match,
                    }
                )
        if missing:
            missing_cells_by_page[page] = missing
        extra = candidate_remainder
        if extra:
            extra_cells_by_page[page] = extra

    missing_total = sum(sum(counter.values()) for counter in missing_cells_by_page.values())
    extra_total = sum(sum(counter.values()) for counter in extra_cells_by_page.values())
    near_matched_total = sum(sum(counter.values()) for counter in near_matched_cells_by_page.values())
    return {
        "baseline_pages": baseline_page_ids,
        "candidate_pages": candidate_page_ids,
        "missing_pages": missing_pages,
        "missing_cells_total": missing_total,
        "extra_cells_total": extra_total,
        "near_matched_cells_total": near_matched_total,
        "semantic_merge_preserved": not missing_pages and missing_total == 0,
        "missing_cells_by_page": {str(page): _counter_to_dict(counter) for page, counter in missing_cells_by_page.items()},
        "extra_cells_by_page": {str(page): _counter_to_dict(counter) for page, counter in extra_cells_by_page.items()},
        "near_matched_cells_by_page": {
            str(page): _counter_to_dict(counter) for page, counter in near_matched_cells_by_page.items()
        },
        "near_match_examples_by_page": {str(page): examples for page, examples in near_match_examples_by_page.items()},
    }


def _load_metrics(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_pdf_paths_from_metrics(metrics: dict[str, Any]) -> list[Path]:
    docs = metrics.get("comparison", {}).get("same_page_merge_docs") or []
    seen: set[str] = set()
    paths: list[Path] = []
    for doc in docs:
        pdf_path = str((doc or {}).get("pdf_path") or "").strip()
        if not pdf_path or pdf_path in seen:
            continue
        seen.add(pdf_path)
        paths.append(Path(pdf_path))
    return paths


def run_audit(*, metrics_path: Path, out_dir: Path, run_id: str) -> Path:
    metrics = _load_metrics(metrics_path)
    baseline_backend = str(metrics.get("baseline_backend") or "fitz_pdfplumber")
    candidate_backend = str(metrics.get("candidate_backend") or "docling")
    pdf_paths = _extract_pdf_paths_from_metrics(metrics)

    baseline_parser = create_parser_backend(baseline_backend)
    candidate_parser = create_parser_backend(candidate_backend)
    details: list[dict[str, Any]] = []
    semantic_merge_preserved_count = 0

    for pdf_path in pdf_paths:
        baseline_result = baseline_parser.extract_tables(pdf_path)
        candidate_result = candidate_parser.extract_tables(pdf_path)
        baseline_pages = _meaningful_page_counters(baseline_result.tables)
        candidate_pages = _meaningful_page_counters(candidate_result.tables)
        classification = classify_page_cell_coverage(baseline_pages, candidate_pages)
        if classification["semantic_merge_preserved"]:
            semantic_merge_preserved_count += 1
        details.append(
            {
                "pdf_path": str(pdf_path),
                "baseline_backend": baseline_backend,
                "candidate_backend": candidate_backend,
                "classification": classification,
            }
        )

    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    details_payload = {
        "schema_version": "table_merge_semantics_audit.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "metrics_path": str(metrics_path),
        "baseline_backend": baseline_backend,
        "candidate_backend": candidate_backend,
        "documents": details,
    }
    summary_payload = {
        "run_id": run_id,
        "status": "ok",
        "document_count": len(details),
        "semantic_merge_preserved_count": semantic_merge_preserved_count,
        "content_gap_count": len(details) - semantic_merge_preserved_count,
        "details_path": str(run_root / "details.json"),
    }
    _write_json(run_root / "details.json", details_payload)
    _write_json(run_root / "summary.json", summary_payload)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit semantic preservation for same-page merged table docs.")
    parser.add_argument("--metrics", required=True, help="Path to compare_ingest_backends metrics.json")
    parser.add_argument(
        "--out-dir",
        default="snapshots/ingest_backend_eval/table_merge_audits",
        help="Output directory for audit artifacts.",
    )
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("table_merge_audit_%Y%m%d_%H%M%S")
    run_root = run_audit(
        metrics_path=Path(str(args.metrics)).expanduser().resolve(),
        out_dir=Path(str(args.out_dir)).expanduser().resolve(),
        run_id=run_id,
    )
    print(f"[audit_table_merge_semantics] out={run_root}")
    print(f"[audit_table_merge_semantics] summary={run_root / 'summary.json'}")


if __name__ == "__main__":
    main()
