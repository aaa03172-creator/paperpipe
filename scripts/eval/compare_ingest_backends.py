#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.ingest_agent import IngestAgent


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest_pdfs(path: Path) -> list[Path]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("documents") or []
    pdfs: list[Path] = []
    for doc in documents:
        local_path = str((doc or {}).get("local_path") or "").strip()
        if local_path:
            pdfs.append(Path(local_path).expanduser().resolve())
    return pdfs


def _collect_pdf_paths(*, pdfs: list[str], manifest: str | None) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()
    for raw in pdfs:
        path = Path(raw).expanduser().resolve()
        if str(path) not in seen:
            resolved.append(path)
            seen.add(str(path))
    if manifest:
        for path in _load_manifest_pdfs(Path(manifest).expanduser().resolve()):
            if str(path) not in seen:
                resolved.append(path)
                seen.add(str(path))
    return resolved


def _backend_available(ingest: IngestAgent, requested_backend: str) -> tuple[bool, str | None]:
    normalized = requested_backend.strip().lower()
    if normalized != "docling":
        return True, None
    converter = getattr(ingest.backend, "_converter", "__missing__")
    if converter is None:
        return False, "Docling unavailable; runtime fell back to fitz/pdfplumber behavior."
    return True, None


def _table_summary(table: Any) -> dict[str, Any]:
    data = list(getattr(table, "data", None) or [])
    rows = len(data)
    cols = max((len(row) for row in data), default=0)
    flattened = [str(cell or "").strip() for row in data for cell in row]
    non_empty_cells = sum(1 for cell in flattened if cell)
    alpha_cells = sum(1 for cell in flattened if any(ch.isalpha() for ch in cell))
    return {
        "table_id": str(getattr(table, "table_id", "") or ""),
        "source_page": int(getattr(table, "source_page", 0) or 0),
        "rows": rows,
        "cols": cols,
        "non_empty_cells": non_empty_cells,
        "alpha_cells": alpha_cells,
    }


def _is_meaningful_table(summary: dict[str, Any]) -> bool:
    return (
        int(summary.get("rows") or 0) >= 2
        and int(summary.get("cols") or 0) >= 2
        and int(summary.get("non_empty_cells") or 0) >= 6
        and int(summary.get("alpha_cells") or 0) >= 2
    )


def _meaningful_table_count(row: dict[str, Any]) -> int:
    return sum(1 for summary in row.get("table_summaries") or [] if _is_meaningful_table(summary))


def evaluate_pdf_with_backend(pdf_path: Path, backend_name: str) -> dict[str, Any]:
    pdf_path = pdf_path.expanduser().resolve()
    row: dict[str, Any] = {
        "schema_version": "ingest_backend_eval_row.v1",
        "evaluated_at": _utc_now_iso(),
        "pdf_path": str(pdf_path),
        "pdf_name": pdf_path.name,
        "requested_backend": backend_name,
        "effective_backend": None,
        "backend_available": None,
        "backend_fallback_note": None,
        "pdf_sha256": None,
        "success": False,
        "error": None,
        "doc_id": None,
        "title": None,
        "doi": None,
        "has_doi": False,
        "section_count": 0,
        "text_char_count": 0,
        "table_count": 0,
        "meaningful_table_count": 0,
        "table_pages": [],
        "table_summaries": [],
        "ocr_applied": False,
        "table_extraction_pass": None,
        "table_failure_taxonomy": [],
    }

    if not pdf_path.exists():
        row["error"] = "PDF_NOT_FOUND"
        return row

    row["pdf_sha256"] = _sha256_file(pdf_path)

    ingest = IngestAgent(parser_backend=backend_name)
    row["effective_backend"] = ingest.backend.name()
    available, fallback_note = _backend_available(ingest, backend_name)
    row["backend_available"] = available
    row["backend_fallback_note"] = fallback_note

    try:
        artifact = ingest.process(str(pdf_path))
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row

    if artifact is None:
        row["error"] = "INGEST_RETURNED_NONE"
        return row

    row["success"] = True
    row["doc_id"] = artifact.doc_id
    row["title"] = artifact.metadata.title
    row["doi"] = artifact.metadata.doi
    row["has_doi"] = bool(artifact.metadata.doi)
    row["section_count"] = len(artifact.sections)
    row["text_char_count"] = sum(len(section.text or "") for section in artifact.sections)
    row["table_count"] = len(artifact.tables)
    row["table_summaries"] = [_table_summary(table) for table in artifact.tables]
    row["meaningful_table_count"] = _meaningful_table_count(row)
    row["table_pages"] = sorted(
        {
            int(table.source_page)
            for table in artifact.tables
            if isinstance(getattr(table, "source_page", None), int) and int(table.source_page) > 0
        }
    )
    row["ocr_applied"] = bool(artifact.metadata.ocr_applied)
    row["table_extraction_pass"] = str(ingest.last_table_extraction_meta.get("table_extraction_pass") or "")
    row["table_failure_taxonomy"] = list(ingest.last_table_extraction_meta.get("table_failure_taxonomy") or [])
    return row


def _backend_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    success_rows = [row for row in rows if row.get("success")]
    text_counts = [int(row.get("text_char_count") or 0) for row in success_rows]
    return {
        "document_count": total,
        "success_count": len(success_rows),
        "error_count": total - len(success_rows),
        "backend_unavailable_count": sum(1 for row in rows if row.get("backend_available") is False),
        "docs_with_doi_count": sum(1 for row in success_rows if row.get("has_doi")),
        "docs_with_tables_count": sum(1 for row in success_rows if int(row.get("table_count") or 0) > 0),
        "docs_with_meaningful_tables_count": sum(
            1 for row in success_rows if int(row.get("meaningful_table_count") or 0) > 0
        ),
        "docs_with_text_count": sum(1 for row in success_rows if int(row.get("text_char_count") or 0) > 0),
        "avg_text_char_count": mean(text_counts) if text_counts else 0.0,
        "table_failure_taxonomy_counts": _taxonomy_counts(rows),
    }


def _taxonomy_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for code in row.get("table_failure_taxonomy") or []:
            code_str = str(code)
            counts[code_str] = counts.get(code_str, 0) + 1
    return dict(sorted(counts.items()))


def compare_backend_rows(
    *,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    min_candidate_text_ratio: float = 0.5,
    max_backend_unavailable_docs: int = 0,
    max_error_increase_docs: int = 0,
    max_empty_text_increase_docs: int = 0,
    max_doi_loss_docs: int = 0,
    max_meaningful_table_loss_docs: int = 0,
    max_low_text_ratio_docs: int = 0,
) -> dict[str, Any]:
    baseline_by_pdf = {str(row["pdf_path"]): row for row in baseline_rows}
    candidate_by_pdf = {str(row["pdf_path"]): row for row in candidate_rows}
    compared_paths = sorted(set(baseline_by_pdf) & set(candidate_by_pdf))

    error_increase_docs: list[dict[str, Any]] = []
    empty_text_increase_docs: list[dict[str, Any]] = []
    backend_unavailable_docs: list[dict[str, Any]] = []
    doi_loss_docs: list[dict[str, Any]] = []
    meaningful_table_loss_docs: list[dict[str, Any]] = []
    meaningful_table_gain_docs: list[dict[str, Any]] = []
    raw_table_loss_docs: list[dict[str, Any]] = []
    raw_table_gain_docs: list[dict[str, Any]] = []
    doi_gain_docs: list[dict[str, Any]] = []
    low_text_ratio_docs: list[dict[str, Any]] = []

    for pdf_path in compared_paths:
        baseline = baseline_by_pdf[pdf_path]
        candidate = candidate_by_pdf[pdf_path]

        if candidate.get("backend_available") is False:
            backend_unavailable_docs.append(
                {
                    "pdf_path": pdf_path,
                    "requested_backend": candidate.get("requested_backend"),
                    "effective_backend": candidate.get("effective_backend"),
                    "note": candidate.get("backend_fallback_note"),
                }
            )

        baseline_success = bool(baseline.get("success"))
        candidate_success = bool(candidate.get("success"))
        if baseline_success and not candidate_success:
            error_increase_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_error": baseline.get("error"),
                    "candidate_error": candidate.get("error"),
                }
            )

        baseline_text = int(baseline.get("text_char_count") or 0)
        candidate_text = int(candidate.get("text_char_count") or 0)
        if baseline_text > 0 and candidate_text == 0:
            empty_text_increase_docs.append({"pdf_path": pdf_path})
        if baseline_text > 0:
            ratio = float(candidate_text) / float(baseline_text)
            if ratio < min_candidate_text_ratio:
                low_text_ratio_docs.append(
                    {
                        "pdf_path": pdf_path,
                        "baseline_text_char_count": baseline_text,
                        "candidate_text_char_count": candidate_text,
                        "ratio": ratio,
                    }
                )

        baseline_has_doi = bool(baseline.get("has_doi"))
        candidate_has_doi = bool(candidate.get("has_doi"))
        if baseline_has_doi and not candidate_has_doi:
            doi_loss_docs.append({"pdf_path": pdf_path, "baseline_doi": baseline.get("doi")})
        if candidate_has_doi and not baseline_has_doi:
            doi_gain_docs.append({"pdf_path": pdf_path, "candidate_doi": candidate.get("doi")})

        baseline_table_count = int(baseline.get("table_count") or 0)
        candidate_table_count = int(candidate.get("table_count") or 0)
        if candidate_table_count < baseline_table_count:
            raw_table_loss_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_table_count": baseline_table_count,
                    "candidate_table_count": candidate_table_count,
                }
            )
        if candidate_table_count > baseline_table_count:
            raw_table_gain_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_table_count": baseline_table_count,
                    "candidate_table_count": candidate_table_count,
                }
            )

        baseline_meaningful_table_count = _meaningful_table_count(baseline)
        candidate_meaningful_table_count = _meaningful_table_count(candidate)
        if candidate_meaningful_table_count < baseline_meaningful_table_count:
            meaningful_table_loss_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_meaningful_table_count": baseline_meaningful_table_count,
                    "candidate_meaningful_table_count": candidate_meaningful_table_count,
                    "baseline_table_count": baseline_table_count,
                    "candidate_table_count": candidate_table_count,
                }
            )
        if candidate_meaningful_table_count > baseline_meaningful_table_count:
            meaningful_table_gain_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_meaningful_table_count": baseline_meaningful_table_count,
                    "candidate_meaningful_table_count": candidate_meaningful_table_count,
                    "baseline_table_count": baseline_table_count,
                    "candidate_table_count": candidate_table_count,
                }
            )

    failed_checks: list[str] = []
    if len(backend_unavailable_docs) > max_backend_unavailable_docs:
        failed_checks.append("backend_unavailable_docs")
    if len(error_increase_docs) > max_error_increase_docs:
        failed_checks.append("error_increase_docs")
    if len(empty_text_increase_docs) > max_empty_text_increase_docs:
        failed_checks.append("empty_text_increase_docs")
    if len(doi_loss_docs) > max_doi_loss_docs:
        failed_checks.append("doi_loss_docs")
    if len(meaningful_table_loss_docs) > max_meaningful_table_loss_docs:
        failed_checks.append("meaningful_table_loss_docs")
    if len(low_text_ratio_docs) > max_low_text_ratio_docs:
        failed_checks.append("low_text_ratio_docs")

    return {
        "compared_document_count": len(compared_paths),
        "backend_unavailable_docs": backend_unavailable_docs,
        "error_increase_docs": error_increase_docs,
        "empty_text_increase_docs": empty_text_increase_docs,
        "doi_loss_docs": doi_loss_docs,
        "doi_gain_docs": doi_gain_docs,
        "meaningful_table_loss_docs": meaningful_table_loss_docs,
        "meaningful_table_gain_docs": meaningful_table_gain_docs,
        "raw_table_loss_docs": raw_table_loss_docs,
        "raw_table_gain_docs": raw_table_gain_docs,
        "low_text_ratio_docs": low_text_ratio_docs,
        "decision": {
            "passed": len(failed_checks) == 0,
            "failed_checks": failed_checks,
            "thresholds": {
                "min_candidate_text_ratio": min_candidate_text_ratio,
                "max_backend_unavailable_docs": max_backend_unavailable_docs,
                "max_error_increase_docs": max_error_increase_docs,
                "max_empty_text_increase_docs": max_empty_text_increase_docs,
                "max_doi_loss_docs": max_doi_loss_docs,
                "max_meaningful_table_loss_docs": max_meaningful_table_loss_docs,
                "max_low_text_ratio_docs": max_low_text_ratio_docs,
            },
        },
    }


def run_comparison(
    *,
    pdf_paths: list[Path],
    baseline_backend: str,
    candidate_backend: str,
    out_dir: Path,
    run_id: str,
    min_candidate_text_ratio: float,
    max_backend_unavailable_docs: int,
    max_error_increase_docs: int,
    max_empty_text_increase_docs: int,
    max_doi_loss_docs: int,
    max_meaningful_table_loss_docs: int,
    max_low_text_ratio_docs: int,
    manifest: str | None,
) -> Path:
    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    baseline_rows = [evaluate_pdf_with_backend(path, baseline_backend) for path in pdf_paths]
    candidate_rows = [evaluate_pdf_with_backend(path, candidate_backend) for path in pdf_paths]

    detailed_results_path = run_root / "detailed_results.jsonl"
    with detailed_results_path.open("w", encoding="utf-8") as handle:
        for row in baseline_rows + candidate_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    comparison = compare_backend_rows(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        min_candidate_text_ratio=min_candidate_text_ratio,
        max_backend_unavailable_docs=max_backend_unavailable_docs,
        max_error_increase_docs=max_error_increase_docs,
        max_empty_text_increase_docs=max_empty_text_increase_docs,
        max_doi_loss_docs=max_doi_loss_docs,
        max_meaningful_table_loss_docs=max_meaningful_table_loss_docs,
        max_low_text_ratio_docs=max_low_text_ratio_docs,
    )

    metrics = {
        "schema_version": "ingest_backend_eval.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "baseline_backend": baseline_backend,
        "candidate_backend": candidate_backend,
        "document_count": len(pdf_paths),
        "inputs": {
            "manifest": manifest,
            "pdf_paths": [str(path) for path in pdf_paths],
        },
        "backend_metrics": {
            baseline_backend: _backend_metrics(baseline_rows),
            candidate_backend: _backend_metrics(candidate_rows),
        },
        "comparison": comparison,
    }
    _write_json(run_root / "metrics.json", metrics)
    _write_json(
        run_root / "summary.json",
        {
            "run_id": run_id,
            "status": "ok",
            "metrics_path": str(run_root / "metrics.json"),
            "details_path": str(detailed_results_path),
            "passed": comparison["decision"]["passed"],
            "failed_checks": comparison["decision"]["failed_checks"],
        },
    )
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare PaperPipe ingest backends on a bounded PDF set.")
    parser.add_argument("--pdf", action="append", default=[], help="PDF path to evaluate. Repeat as needed.")
    parser.add_argument(
        "--manifest",
        default="",
        help="Optional manifest.json with documents[].local_path entries, such as goldset/manifest.json.",
    )
    parser.add_argument("--baseline-backend", default="fitz_pdfplumber", help="Baseline parser backend name.")
    parser.add_argument("--candidate-backend", default="docling", help="Candidate parser backend name.")
    parser.add_argument("--out-dir", default="snapshots/ingest_backend_eval", help="Output root directory.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument(
        "--min-candidate-text-ratio",
        type=float,
        default=0.5,
        help="Flag docs where candidate text chars / baseline text chars falls below this ratio.",
    )
    parser.add_argument("--max-backend-unavailable-docs", type=int, default=0)
    parser.add_argument("--max-error-increase-docs", type=int, default=0)
    parser.add_argument("--max-empty-text-increase-docs", type=int, default=0)
    parser.add_argument("--max-doi-loss-docs", type=int, default=0)
    parser.add_argument("--max-meaningful-table-loss-docs", type=int, default=0)
    parser.add_argument("--max-low-text-ratio-docs", type=int, default=0)
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    pdf_paths = _collect_pdf_paths(pdfs=list(args.pdf), manifest=(args.manifest or None))
    if not pdf_paths:
        raise SystemExit("Provide at least one --pdf or a --manifest with documents[].local_path entries.")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("ingest_backend_eval_%Y%m%d_%H%M%S")
    run_root = run_comparison(
        pdf_paths=pdf_paths,
        baseline_backend=str(args.baseline_backend),
        candidate_backend=str(args.candidate_backend),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        min_candidate_text_ratio=float(args.min_candidate_text_ratio),
        max_backend_unavailable_docs=int(args.max_backend_unavailable_docs),
        max_error_increase_docs=int(args.max_error_increase_docs),
        max_empty_text_increase_docs=int(args.max_empty_text_increase_docs),
        max_doi_loss_docs=int(args.max_doi_loss_docs),
        max_meaningful_table_loss_docs=int(args.max_meaningful_table_loss_docs),
        max_low_text_ratio_docs=int(args.max_low_text_ratio_docs),
        manifest=(str(args.manifest).strip() or None),
    )
    print(f"[compare_ingest_backends] out={run_root}")
    print(f"[compare_ingest_backends] metrics={run_root / 'metrics.json'}")


if __name__ == "__main__":
    main()
