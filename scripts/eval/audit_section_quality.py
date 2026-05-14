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
from src.schemas.agent_artifacts import Section


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_metrics(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_pdf_paths_from_metrics(metrics: dict[str, Any]) -> list[Path]:
    paths = metrics.get("inputs", {}).get("pdf_paths") or []
    seen: set[str] = set()
    resolved: list[Path] = []
    for raw in paths:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        resolved.append(Path(value))
    return resolved


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _page_range(section: Section) -> range:
    start_page = int(section.page_start or 0)
    end_page = int(section.page_end or 0)
    if start_page <= 0 and end_page <= 0:
        start_page = 1
        end_page = 1
    elif start_page <= 0:
        start_page = end_page
    elif end_page <= 0:
        end_page = start_page
    if end_page < start_page:
        start_page, end_page = end_page, start_page
    return range(start_page, end_page + 1)


def collapse_sections_by_page(sections: list[Section]) -> dict[int, int]:
    page_char_counts: dict[int, int] = {}
    for section in sections:
        text = str(section.text or "")
        if not text.strip():
            continue
        page_range = _page_range(section)
        page_span = max(1, len(page_range))
        per_page = len(text) // page_span
        remainder = len(text) % page_span
        for offset, page in enumerate(page_range):
            page_char_counts[page] = page_char_counts.get(page, 0) + per_page + (1 if offset < remainder else 0)
    return dict(sorted(page_char_counts.items()))


def collect_section_text_by_page(sections: list[Section]) -> dict[int, str]:
    page_texts: dict[int, list[str]] = {}
    for section in sections:
        text = _normalize_text(section.text)
        if not text:
            continue
        for page in _page_range(section):
            page_texts.setdefault(page, []).append(text)
    return {page: "\n".join(parts) for page, parts in sorted(page_texts.items())}


def collect_table_pages(tables: list[Any]) -> list[int]:
    pages = {
        int(getattr(table, "source_page", 0) or 0)
        for table in tables
        if int(getattr(table, "source_page", 0) or 0) > 0
    }
    return sorted(pages)


def _digit_ratio(text: str) -> float:
    normalized = str(text or "")
    alnum_chars = [char for char in normalized if char.isalnum()]
    if not alnum_chars:
        return 0.0
    digit_chars = sum(1 for char in alnum_chars if char.isdigit())
    return float(digit_chars) / float(len(alnum_chars))


def _has_figure_cue(text: str) -> bool:
    normalized = str(text or "").lower()
    return bool(
        re.search(r"\b(fig(?:ure)?\.?)\b", normalized)
        or "representative image" in normalized
        or "representative images" in normalized
        or "scale bar" in normalized
    )


def classify_low_ratio_page(
    *,
    page: int,
    baseline_text: str,
    candidate_text: str,
    baseline_table_pages: list[int],
    candidate_table_pages: list[int],
) -> dict[str, Any]:
    signals: list[str] = []
    bucket = "needs_manual_review"

    if page in baseline_table_pages:
        signals.append("baseline_table_page")
    if page in candidate_table_pages:
        signals.append("candidate_table_page")

    baseline_figure_cue = _has_figure_cue(baseline_text)
    candidate_figure_cue = _has_figure_cue(candidate_text)
    if baseline_figure_cue:
        signals.append("baseline_figure_cue")
    if candidate_figure_cue:
        signals.append("candidate_figure_cue")

    baseline_digit_ratio = _digit_ratio(baseline_text)
    candidate_digit_ratio = _digit_ratio(candidate_text)

    has_table_signal = "baseline_table_page" in signals or "candidate_table_page" in signals
    has_figure_signal = baseline_figure_cue or candidate_figure_cue

    if has_table_signal and has_figure_signal:
        bucket = "table_and_figure_heavy_page"
    elif has_table_signal:
        bucket = "table_heavy_page"
    elif has_figure_signal:
        bucket = "figure_heavy_page"
    elif baseline_digit_ratio >= 0.2:
        bucket = "numeric_dense_page"
        signals.append("baseline_numeric_dense")

    return {
        "review_bucket": bucket,
        "review_signals": signals,
        "baseline_digit_ratio": baseline_digit_ratio,
        "candidate_digit_ratio": candidate_digit_ratio,
    }


def classify_page_text_coverage(
    baseline_pages: dict[int, int],
    candidate_pages: dict[int, int],
    *,
    baseline_page_texts: dict[int, str] | None = None,
    candidate_page_texts: dict[int, str] | None = None,
    baseline_table_pages: list[int] | None = None,
    candidate_table_pages: list[int] | None = None,
    baseline_section_count: int,
    candidate_section_count: int,
    min_page_text_ratio: float = 0.4,
    min_total_text_ratio: float = 0.5,
    min_substantive_page_chars: int = 80,
) -> dict[str, Any]:
    substantive_baseline_pages = sorted(
        page for page, char_count in baseline_pages.items() if int(char_count) >= min_substantive_page_chars
    )
    missing_substantive_pages = [
        page for page in substantive_baseline_pages if int(candidate_pages.get(page, 0) or 0) <= 0
    ]

    low_page_text_ratio_pages: list[dict[str, Any]] = []
    for page in substantive_baseline_pages:
        baseline_char_count = int(baseline_pages.get(page, 0) or 0)
        candidate_char_count = int(candidate_pages.get(page, 0) or 0)
        if baseline_char_count <= 0 or candidate_char_count <= 0:
            continue
        ratio = float(candidate_char_count) / float(baseline_char_count)
        if ratio < min_page_text_ratio:
            review = classify_low_ratio_page(
                page=page,
                baseline_text=str((baseline_page_texts or {}).get(page, "") or ""),
                candidate_text=str((candidate_page_texts or {}).get(page, "") or ""),
                baseline_table_pages=list(baseline_table_pages or []),
                candidate_table_pages=list(candidate_table_pages or []),
            )
            low_page_text_ratio_pages.append(
                {
                    "page": page,
                    "baseline_char_count": baseline_char_count,
                    "candidate_char_count": candidate_char_count,
                    "ratio": ratio,
                    **review,
                }
            )

    baseline_total_chars = sum(int(value or 0) for value in baseline_pages.values())
    candidate_total_chars = sum(int(value or 0) for value in candidate_pages.values())
    total_text_ratio = (
        float(candidate_total_chars) / float(baseline_total_chars) if baseline_total_chars > 0 else 1.0
    )
    low_total_text_ratio = baseline_total_chars > 0 and total_text_ratio < min_total_text_ratio
    section_collapse = len(substantive_baseline_pages) > 1 and candidate_section_count <= 1

    return {
        "baseline_pages": sorted(baseline_pages),
        "candidate_pages": sorted(candidate_pages),
        "substantive_baseline_pages": substantive_baseline_pages,
        "missing_substantive_pages": missing_substantive_pages,
        "low_page_text_ratio_pages": low_page_text_ratio_pages,
        "baseline_page_char_counts": {str(page): count for page, count in baseline_pages.items()},
        "candidate_page_char_counts": {str(page): count for page, count in candidate_pages.items()},
        "baseline_section_count": baseline_section_count,
        "candidate_section_count": candidate_section_count,
        "baseline_total_text_chars": baseline_total_chars,
        "candidate_total_text_chars": candidate_total_chars,
        "total_text_ratio": total_text_ratio,
        "low_total_text_ratio": low_total_text_ratio,
        "section_collapse": section_collapse,
        "page_coverage_preserved": not missing_substantive_pages and not low_page_text_ratio_pages and not section_collapse,
    }


def run_audit(
    *,
    metrics_path: Path,
    out_dir: Path,
    run_id: str,
    min_page_text_ratio: float,
    min_total_text_ratio: float,
    min_substantive_page_chars: int,
) -> Path:
    metrics = _load_metrics(metrics_path)
    baseline_backend = str(metrics.get("baseline_backend") or "fitz_pdfplumber")
    candidate_backend = str(metrics.get("candidate_backend") or "docling")
    pdf_paths = _extract_pdf_paths_from_metrics(metrics)

    baseline_parser = create_parser_backend(baseline_backend)
    candidate_parser = create_parser_backend(candidate_backend)
    documents: list[dict[str, Any]] = []
    page_coverage_preserved_count = 0
    missing_page_docs_count = 0
    low_page_text_ratio_docs_count = 0
    low_total_text_ratio_docs_count = 0
    section_collapse_docs_count = 0
    low_page_text_ratio_doc_bucket_counts: Counter[str] = Counter()
    low_page_text_ratio_page_bucket_counts: Counter[str] = Counter()
    low_page_text_ratio_unclassified_docs_count = 0

    for pdf_path in pdf_paths:
        _, baseline_sections, _baseline_len = baseline_parser.extract_text_and_meta(pdf_path)
        _, candidate_sections, _candidate_len = candidate_parser.extract_text_and_meta(pdf_path)
        baseline_tables = baseline_parser.extract_tables(pdf_path).tables
        candidate_tables = candidate_parser.extract_tables(pdf_path).tables

        baseline_pages = collapse_sections_by_page(baseline_sections)
        candidate_pages = collapse_sections_by_page(candidate_sections)
        baseline_page_texts = collect_section_text_by_page(baseline_sections)
        candidate_page_texts = collect_section_text_by_page(candidate_sections)
        classification = classify_page_text_coverage(
            baseline_pages,
            candidate_pages,
            baseline_page_texts=baseline_page_texts,
            candidate_page_texts=candidate_page_texts,
            baseline_table_pages=collect_table_pages(baseline_tables),
            candidate_table_pages=collect_table_pages(candidate_tables),
            baseline_section_count=len(baseline_sections),
            candidate_section_count=len(candidate_sections),
            min_page_text_ratio=min_page_text_ratio,
            min_total_text_ratio=min_total_text_ratio,
            min_substantive_page_chars=min_substantive_page_chars,
        )
        if classification["page_coverage_preserved"]:
            page_coverage_preserved_count += 1
        if classification["missing_substantive_pages"]:
            missing_page_docs_count += 1
        if classification["low_page_text_ratio_pages"]:
            low_page_text_ratio_docs_count += 1
            page_buckets = [
                str(page.get("review_bucket") or "needs_manual_review")
                for page in classification["low_page_text_ratio_pages"]
            ]
            doc_buckets = set(page_buckets)
            low_page_text_ratio_doc_bucket_counts.update(doc_buckets)
            low_page_text_ratio_page_bucket_counts.update(page_buckets)
            if "needs_manual_review" in doc_buckets:
                low_page_text_ratio_unclassified_docs_count += 1
        if classification["low_total_text_ratio"]:
            low_total_text_ratio_docs_count += 1
        if classification["section_collapse"]:
            section_collapse_docs_count += 1

        documents.append(
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
        "schema_version": "section_quality_audit.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "metrics_path": str(metrics_path),
        "baseline_backend": baseline_backend,
        "candidate_backend": candidate_backend,
        "documents": documents,
    }
    summary_payload = {
        "run_id": run_id,
        "status": "ok",
        "document_count": len(documents),
        "page_coverage_preserved_count": page_coverage_preserved_count,
        "missing_page_docs_count": missing_page_docs_count,
        "low_page_text_ratio_docs_count": low_page_text_ratio_docs_count,
        "low_page_text_ratio_doc_bucket_counts": dict(sorted(low_page_text_ratio_doc_bucket_counts.items())),
        "low_page_text_ratio_page_bucket_counts": dict(sorted(low_page_text_ratio_page_bucket_counts.items())),
        "low_page_text_ratio_unclassified_docs_count": low_page_text_ratio_unclassified_docs_count,
        "low_total_text_ratio_docs_count": low_total_text_ratio_docs_count,
        "section_collapse_docs_count": section_collapse_docs_count,
        "details_path": str(run_root / "details.json"),
    }
    _write_json(run_root / "details.json", details_payload)
    _write_json(run_root / "summary.json", summary_payload)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit page-aware section/text quality for parser backend comparisons.")
    parser.add_argument("--metrics", required=True, help="Path to compare_ingest_backends metrics.json")
    parser.add_argument(
        "--out-dir",
        default="snapshots/ingest_backend_eval/section_quality_audits",
        help="Output directory for audit artifacts.",
    )
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument(
        "--min-page-text-ratio",
        type=float,
        default=0.4,
        help="Minimum candidate/baseline ratio for substantive baseline pages.",
    )
    parser.add_argument(
        "--min-total-text-ratio",
        type=float,
        default=0.5,
        help="Minimum candidate/baseline ratio for total text chars.",
    )
    parser.add_argument(
        "--min-substantive-page-chars",
        type=int,
        default=80,
        help="Ignore baseline pages with fewer chars than this when flagging missing or low-ratio pages.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("section_quality_audit_%Y%m%d_%H%M%S")
    run_root = run_audit(
        metrics_path=Path(str(args.metrics)).expanduser().resolve(),
        out_dir=Path(str(args.out_dir)).expanduser().resolve(),
        run_id=run_id,
        min_page_text_ratio=float(args.min_page_text_ratio),
        min_total_text_ratio=float(args.min_total_text_ratio),
        min_substantive_page_chars=int(args.min_substantive_page_chars),
    )
    print(f"[audit_section_quality] out={run_root}")
    print(f"[audit_section_quality] summary={run_root / 'summary.json'}")


if __name__ == "__main__":
    main()
