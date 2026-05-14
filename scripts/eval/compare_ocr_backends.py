#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import fitz

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.ocr_fallback import run_ocr


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


def _extract_pdf_text_metrics(pdf_path: Path) -> tuple[int, list[int]]:
    doc = fitz.open(pdf_path)
    try:
        page_counts: list[int] = []
        for page in doc:
            page_counts.append(len((page.get_text() or "").strip()))
    finally:
        doc.close()
    return sum(page_counts), page_counts


def _extract_text_preview(text: str, limit: int = 160) -> str:
    normalized = " ".join(str(text or "").split())
    return normalized[:limit]


def _backend_available(backend_name: str) -> tuple[bool, str | None]:
    normalized = str(backend_name or "").strip().lower()
    if normalized == "ocrmypdf":
        if shutil.which("ocrmypdf") is None:
            return False, "ocrmypdf_not_installed"
        return True, None
    if normalized == "paddleocr":
        if importlib.util.find_spec("paddleocr") is None:
            return False, "paddleocr_not_installed"
        return True, None
    return False, f"unknown_backend:{normalized}"


def _paddleocr_version() -> str | None:
    try:
        return importlib.metadata.version("paddleocr")
    except Exception:
        return None


def _flatten_paddleocr_page_result(page_result: Any) -> str:
    if not page_result:
        return ""
    if isinstance(page_result, dict):
        texts = page_result.get("rec_texts")
        if isinstance(texts, list):
            return "\n".join(str(text or "").strip() for text in texts if str(text or "").strip())
        return ""
    if isinstance(page_result, list) and page_result and isinstance(page_result[0], dict):
        lines: list[str] = []
        for item in page_result:
            text = _flatten_paddleocr_page_result(item)
            if text:
                lines.append(text)
        return "\n".join(lines)
    lines: list[str] = []
    for item in page_result:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text_info = item[1]
        if isinstance(text_info, (list, tuple)) and text_info:
            text = str(text_info[0] or "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def run_paddleocr_text(pdf_in: Path, out_dir: Path, lang: str = "en") -> dict[str, Any]:
    try:
        paddleocr_mod = importlib.import_module("paddleocr")
    except Exception:
        return {
            "ocr_applied": False,
            "ocr_engine": "paddleocr",
            "ocr_version": _paddleocr_version(),
            "ocr_lang": lang,
            "ocr_output_path": None,
            "text_output_path": None,
            "text_char_count": 0,
            "page_text_char_counts": [],
            "error": "paddleocr_not_installed",
        }

    paddle_ocr_cls = getattr(paddleocr_mod, "PaddleOCR", None)
    if paddle_ocr_cls is None:
        return {
            "ocr_applied": False,
            "ocr_engine": "paddleocr",
            "ocr_version": _paddleocr_version(),
            "ocr_lang": lang,
            "ocr_output_path": None,
            "text_output_path": None,
            "text_char_count": 0,
            "page_text_char_counts": [],
            "error": "paddleocr_class_missing",
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    combined_lines: list[str] = []
    page_text_char_counts: list[int] = []
    page_payloads: list[dict[str, Any]] = []

    try:
        ocr = paddle_ocr_cls(lang=lang)
        doc = fitz.open(pdf_in)
        try:
            with tempfile.TemporaryDirectory(prefix="paperpipe_paddleocr_") as tmp_dir_raw:
                tmp_dir = Path(tmp_dir_raw)
                for page_index in range(doc.page_count):
                    page = doc.load_page(page_index)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    image_path = tmp_dir / f"page_{page_index + 1}.png"
                    pix.save(str(image_path))
                    result = ocr.ocr(str(image_path))
                    page_text = ""
                    if isinstance(result, list) and result:
                        page_text = "\n".join(
                            part for part in (_flatten_paddleocr_page_result(page_result) for page_result in result) if part
                        )
                    page_text = str(page_text or "").strip()
                    combined_lines.append(page_text)
                    page_text_char_counts.append(len(page_text))
                    page_payloads.append(
                        {
                            "page": page_index + 1,
                            "text_char_count": len(page_text),
                            "text_preview": _extract_text_preview(page_text),
                        }
                    )
        finally:
            doc.close()

        text = "\n\n".join(line for line in combined_lines if line)
        text_output_path = out_dir / "ocr.txt"
        details_path = out_dir / "ocr_details.json"
        text_output_path.write_text(text, encoding="utf-8")
        _write_json(
            details_path,
            {
                "schema_version": "paddleocr_eval_output.v1",
                "generated_at": _utc_now_iso(),
                "pdf_path": str(pdf_in),
                "ocr_engine": "paddleocr",
                "ocr_version": _paddleocr_version(),
                "ocr_lang": lang,
                "page_count": len(page_payloads),
                "page_text_char_counts": page_text_char_counts,
                "pages": page_payloads,
            },
        )
        return {
            "ocr_applied": True,
            "ocr_engine": "paddleocr",
            "ocr_version": _paddleocr_version(),
            "ocr_lang": lang,
            "ocr_output_path": None,
            "text_output_path": str(text_output_path),
            "text_char_count": len(text),
            "page_text_char_counts": page_text_char_counts,
            "error": None,
        }
    except Exception as exc:
        return {
            "ocr_applied": False,
            "ocr_engine": "paddleocr",
            "ocr_version": _paddleocr_version(),
            "ocr_lang": lang,
            "ocr_output_path": None,
            "text_output_path": None,
            "text_char_count": 0,
            "page_text_char_counts": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def evaluate_pdf_with_backend(
    pdf_path: Path,
    backend_name: str,
    *,
    output_root: Path,
    lang: str,
) -> dict[str, Any]:
    pdf_path = pdf_path.expanduser().resolve()
    row: dict[str, Any] = {
        "schema_version": "ocr_backend_eval_row.v1",
        "evaluated_at": _utc_now_iso(),
        "pdf_path": str(pdf_path),
        "pdf_name": pdf_path.name,
        "requested_backend": backend_name,
        "backend_available": None,
        "backend_fallback_note": None,
        "pdf_sha256": None,
        "success": False,
        "error": None,
        "page_count": 0,
        "text_char_count": 0,
        "page_text_char_counts": [],
        "ocr_applied": False,
        "ocr_engine": None,
        "ocr_version": None,
        "ocr_lang": lang,
        "ocr_output_path": None,
        "text_output_path": None,
        "elapsed_seconds": 0.0,
    }

    if not pdf_path.exists():
        row["error"] = "PDF_NOT_FOUND"
        return row

    row["pdf_sha256"] = _sha256_file(pdf_path)
    doc = fitz.open(pdf_path)
    try:
        row["page_count"] = doc.page_count
    finally:
        doc.close()
    available, unavailable_reason = _backend_available(backend_name)
    row["backend_available"] = available
    row["backend_fallback_note"] = unavailable_reason
    if not available:
        row["error"] = unavailable_reason
        return row

    started = time.perf_counter()
    normalized = str(backend_name or "").strip().lower()
    if normalized == "ocrmypdf":
        output_path = output_root / "ocrmypdf" / f"{row['pdf_sha256']}.pdf"
        meta = run_ocr(pdf_path, output_path, lang=lang)
        row.update(
            {
                "ocr_applied": bool(meta.get("ocr_applied")),
                "ocr_engine": meta.get("ocr_engine"),
                "ocr_version": meta.get("ocr_version"),
                "ocr_lang": meta.get("ocr_lang"),
                "ocr_output_path": meta.get("ocr_output_path"),
                "error": meta.get("error"),
            }
        )
        if meta.get("ocr_applied") and meta.get("ocr_output_path"):
            output_pdf = Path(str(meta["ocr_output_path"]))
            text_char_count, page_text_char_counts = _extract_pdf_text_metrics(output_pdf)
            row["text_char_count"] = text_char_count
            row["page_text_char_counts"] = page_text_char_counts
            row["success"] = True
    elif normalized == "paddleocr":
        output_dir = output_root / "paddleocr" / str(row["pdf_sha256"])
        meta = run_paddleocr_text(pdf_path, output_dir, lang=lang)
        row.update(
            {
                "ocr_applied": bool(meta.get("ocr_applied")),
                "ocr_engine": meta.get("ocr_engine"),
                "ocr_version": meta.get("ocr_version"),
                "ocr_lang": meta.get("ocr_lang"),
                "ocr_output_path": meta.get("ocr_output_path"),
                "text_output_path": meta.get("text_output_path"),
                "text_char_count": int(meta.get("text_char_count") or 0),
                "page_text_char_counts": list(meta.get("page_text_char_counts") or []),
                "error": meta.get("error"),
            }
        )
        row["success"] = bool(meta.get("ocr_applied"))
    else:
        row["error"] = f"unknown_backend:{backend_name}"

    row["elapsed_seconds"] = round(time.perf_counter() - started, 4)
    return row


def _backend_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    success_rows = [row for row in rows if row.get("success")]
    text_counts = [int(row.get("text_char_count") or 0) for row in success_rows]
    elapsed = [float(row.get("elapsed_seconds") or 0.0) for row in success_rows]
    return {
        "document_count": total,
        "success_count": len(success_rows),
        "error_count": total - len(success_rows),
        "backend_unavailable_count": sum(1 for row in rows if row.get("backend_available") is False),
        "avg_text_char_count": mean(text_counts) if text_counts else 0.0,
        "avg_elapsed_seconds": mean(elapsed) if elapsed else 0.0,
        "zero_text_docs_count": sum(1 for row in success_rows if int(row.get("text_char_count") or 0) == 0),
    }


def compare_ocr_rows(
    *,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    min_candidate_text_ratio: float = 0.5,
    max_baseline_unavailable_docs: int = 0,
    max_backend_unavailable_docs: int = 0,
    max_baseline_error_docs: int = 0,
    max_backend_error_docs: int = 0,
    max_error_increase_docs: int = 0,
    max_zero_text_docs: int = 0,
    max_low_text_ratio_docs: int = 0,
) -> dict[str, Any]:
    baseline_by_pdf = {str(row["pdf_path"]): row for row in baseline_rows}
    candidate_by_pdf = {str(row["pdf_path"]): row for row in candidate_rows}
    compared_paths = sorted(set(baseline_by_pdf) & set(candidate_by_pdf))

    baseline_unavailable_docs: list[dict[str, Any]] = []
    backend_unavailable_docs: list[dict[str, Any]] = []
    baseline_error_docs: list[dict[str, Any]] = []
    backend_error_docs: list[dict[str, Any]] = []
    error_increase_docs: list[dict[str, Any]] = []
    zero_text_docs: list[dict[str, Any]] = []
    low_text_ratio_docs: list[dict[str, Any]] = []
    text_gain_docs: list[dict[str, Any]] = []

    for pdf_path in compared_paths:
        baseline = baseline_by_pdf[pdf_path]
        candidate = candidate_by_pdf[pdf_path]

        if baseline.get("backend_available") is False:
            baseline_unavailable_docs.append(
                {
                    "pdf_path": pdf_path,
                    "requested_backend": baseline.get("requested_backend"),
                    "note": baseline.get("backend_fallback_note"),
                }
            )

        if candidate.get("backend_available") is False:
            backend_unavailable_docs.append(
                {
                    "pdf_path": pdf_path,
                    "requested_backend": candidate.get("requested_backend"),
                    "note": candidate.get("backend_fallback_note"),
                }
            )

        if baseline.get("backend_available") is not False and not baseline.get("success"):
            baseline_error_docs.append(
                {
                    "pdf_path": pdf_path,
                    "requested_backend": baseline.get("requested_backend"),
                    "error": baseline.get("error"),
                }
            )

        if candidate.get("backend_available") is not False and not candidate.get("success"):
            backend_error_docs.append(
                {
                    "pdf_path": pdf_path,
                    "requested_backend": candidate.get("requested_backend"),
                    "error": candidate.get("error"),
                }
            )

        if baseline.get("success") and not candidate.get("success"):
            error_increase_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_error": baseline.get("error"),
                    "candidate_error": candidate.get("error"),
                }
            )

        baseline_text = int(baseline.get("text_char_count") or 0)
        candidate_text = int(candidate.get("text_char_count") or 0)
        if candidate.get("success") and candidate_text == 0:
            zero_text_docs.append({"pdf_path": pdf_path})
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
        if candidate_text > baseline_text:
            text_gain_docs.append(
                {
                    "pdf_path": pdf_path,
                    "baseline_text_char_count": baseline_text,
                    "candidate_text_char_count": candidate_text,
                }
            )

    failed_checks: list[str] = []
    if len(baseline_unavailable_docs) > max_baseline_unavailable_docs:
        failed_checks.append("baseline_unavailable_docs")
    if len(backend_unavailable_docs) > max_backend_unavailable_docs:
        failed_checks.append("backend_unavailable_docs")
    if len(baseline_error_docs) > max_baseline_error_docs:
        failed_checks.append("baseline_error_docs")
    if len(backend_error_docs) > max_backend_error_docs:
        failed_checks.append("backend_error_docs")
    if len(error_increase_docs) > max_error_increase_docs:
        failed_checks.append("error_increase_docs")
    if len(zero_text_docs) > max_zero_text_docs:
        failed_checks.append("zero_text_docs")
    if len(low_text_ratio_docs) > max_low_text_ratio_docs:
        failed_checks.append("low_text_ratio_docs")

    return {
        "compared_document_count": len(compared_paths),
        "baseline_unavailable_docs": baseline_unavailable_docs,
        "backend_unavailable_docs": backend_unavailable_docs,
        "baseline_error_docs": baseline_error_docs,
        "backend_error_docs": backend_error_docs,
        "error_increase_docs": error_increase_docs,
        "zero_text_docs": zero_text_docs,
        "low_text_ratio_docs": low_text_ratio_docs,
        "text_gain_docs": text_gain_docs,
        "decision": {
            "passed": len(failed_checks) == 0,
            "failed_checks": failed_checks,
            "thresholds": {
                "min_candidate_text_ratio": min_candidate_text_ratio,
                "max_baseline_unavailable_docs": max_baseline_unavailable_docs,
                "max_backend_unavailable_docs": max_backend_unavailable_docs,
                "max_baseline_error_docs": max_baseline_error_docs,
                "max_backend_error_docs": max_backend_error_docs,
                "max_error_increase_docs": max_error_increase_docs,
                "max_zero_text_docs": max_zero_text_docs,
                "max_low_text_ratio_docs": max_low_text_ratio_docs,
            },
        },
    }


def run_comparison(
    *,
    pdf_paths: list[Path],
    baseline_backend: str,
    candidate_backend: str,
    baseline_lang: str,
    candidate_lang: str,
    out_dir: Path,
    run_id: str,
    min_candidate_text_ratio: float,
    max_baseline_unavailable_docs: int,
    max_backend_unavailable_docs: int,
    max_baseline_error_docs: int,
    max_backend_error_docs: int,
    max_error_increase_docs: int,
    max_zero_text_docs: int,
    max_low_text_ratio_docs: int,
    manifest: str | None,
) -> Path:
    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    ocr_output_root = run_root / "ocr_outputs"

    baseline_rows = [
        evaluate_pdf_with_backend(path, baseline_backend, output_root=ocr_output_root, lang=baseline_lang)
        for path in pdf_paths
    ]
    candidate_rows = [
        evaluate_pdf_with_backend(path, candidate_backend, output_root=ocr_output_root, lang=candidate_lang)
        for path in pdf_paths
    ]

    detailed_results_path = run_root / "detailed_results.jsonl"
    with detailed_results_path.open("w", encoding="utf-8") as handle:
        for row in baseline_rows + candidate_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    comparison = compare_ocr_rows(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        min_candidate_text_ratio=min_candidate_text_ratio,
        max_baseline_unavailable_docs=max_baseline_unavailable_docs,
        max_backend_unavailable_docs=max_backend_unavailable_docs,
        max_baseline_error_docs=max_baseline_error_docs,
        max_backend_error_docs=max_backend_error_docs,
        max_error_increase_docs=max_error_increase_docs,
        max_zero_text_docs=max_zero_text_docs,
        max_low_text_ratio_docs=max_low_text_ratio_docs,
    )

    metrics = {
        "schema_version": "ocr_backend_eval.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "baseline_backend": baseline_backend,
        "candidate_backend": candidate_backend,
        "document_count": len(pdf_paths),
        "inputs": {
            "manifest": manifest,
            "pdf_paths": [str(path) for path in pdf_paths],
            "baseline_lang": baseline_lang,
            "candidate_lang": candidate_lang,
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
        },
    )
    return run_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded OCR backend comparison for hard-PDF eval slices.")
    parser.add_argument("--pdf", action="append", default=[], help="PDF path to include. May be repeated.")
    parser.add_argument("--manifest", help="Manifest JSON with documents[].local_path entries.")
    parser.add_argument("--baseline-backend", default="ocrmypdf", help="Baseline OCR backend name.")
    parser.add_argument("--candidate-backend", default="paddleocr", help="Candidate OCR backend name.")
    parser.add_argument("--baseline-lang", default="eng", help="Language code for the baseline OCR backend.")
    parser.add_argument("--candidate-lang", default="en", help="Language code for the candidate OCR backend.")
    parser.add_argument("--out-dir", default="snapshots/ocr_backend_eval", help="Output directory.")
    parser.add_argument("--run-id", default=None, help="Optional run id.")
    parser.add_argument("--min-candidate-text-ratio", type=float, default=0.5)
    parser.add_argument("--max-baseline-unavailable-docs", type=int, default=0)
    parser.add_argument("--max-backend-unavailable-docs", type=int, default=0)
    parser.add_argument("--max-baseline-error-docs", type=int, default=0)
    parser.add_argument("--max-backend-error-docs", type=int, default=0)
    parser.add_argument("--max-error-increase-docs", type=int, default=0)
    parser.add_argument("--max-zero-text-docs", type=int, default=0)
    parser.add_argument("--max-low-text-ratio-docs", type=int, default=0)
    args = parser.parse_args()

    pdf_paths = _collect_pdf_paths(pdfs=args.pdf, manifest=args.manifest)
    if not pdf_paths:
        parser.error("Provide at least one --pdf or --manifest with documents[].local_path entries.")

    run_id = args.run_id or f"ocr_backend_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    run_root = run_comparison(
        pdf_paths=pdf_paths,
        baseline_backend=args.baseline_backend,
        candidate_backend=args.candidate_backend,
        baseline_lang=args.baseline_lang,
        candidate_lang=args.candidate_lang,
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        min_candidate_text_ratio=args.min_candidate_text_ratio,
        max_baseline_unavailable_docs=args.max_baseline_unavailable_docs,
        max_backend_unavailable_docs=args.max_backend_unavailable_docs,
        max_baseline_error_docs=args.max_baseline_error_docs,
        max_backend_error_docs=args.max_backend_error_docs,
        max_error_increase_docs=args.max_error_increase_docs,
        max_zero_text_docs=args.max_zero_text_docs,
        max_low_text_ratio_docs=args.max_low_text_ratio_docs,
        manifest=args.manifest,
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
