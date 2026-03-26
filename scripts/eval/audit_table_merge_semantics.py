#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
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


def classify_page_cell_coverage(
    baseline_pages: dict[int, Counter[str]], candidate_pages: dict[int, Counter[str]]
) -> dict[str, Any]:
    baseline_page_ids = sorted(baseline_pages)
    candidate_page_ids = sorted(candidate_pages)
    missing_pages = [page for page in baseline_page_ids if page not in candidate_page_ids]

    missing_cells_by_page: dict[int, Counter[str]] = {}
    extra_cells_by_page: dict[int, Counter[str]] = {}
    for page in baseline_page_ids:
        baseline_counter = baseline_pages.get(page, Counter())
        candidate_counter = candidate_pages.get(page, Counter())
        missing = baseline_counter - candidate_counter
        if missing:
            missing_cells_by_page[page] = missing
        extra = candidate_counter - baseline_counter
        if extra:
            extra_cells_by_page[page] = extra

    missing_total = sum(sum(counter.values()) for counter in missing_cells_by_page.values())
    extra_total = sum(sum(counter.values()) for counter in extra_cells_by_page.values())
    return {
        "baseline_pages": baseline_page_ids,
        "candidate_pages": candidate_page_ids,
        "missing_pages": missing_pages,
        "missing_cells_total": missing_total,
        "extra_cells_total": extra_total,
        "semantic_merge_preserved": not missing_pages and missing_total == 0,
        "missing_cells_by_page": {str(page): _counter_to_dict(counter) for page, counter in missing_cells_by_page.items()},
        "extra_cells_by_page": {str(page): _counter_to_dict(counter) for page, counter in extra_cells_by_page.items()},
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
