#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "goldset" / "manifests" / "science_aeb0045_ingest_index_oracle_20260429.json"
DEFAULT_OUT_DIR = ROOT / "snapshots" / "local_pdf_ingest_index_oracle"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    from src.skills.storage import atomic_write_text

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_expected={path}")
    return payload


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _chunk_text(text: str, *, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    text_len = len(text)
    step = max(chunk_size - overlap, 1)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += step
    return chunks


def build_chunk_summary(doc: Any) -> dict[str, Any]:
    from src.contracts.artifact_views import get_artifact_header, iter_text_sections
    from src.services.identity import make_chunk_id

    header = get_artifact_header(doc)
    chunks: list[dict[str, Any]] = []
    page_chunk_counts: dict[int, int] = {}

    for section in iter_text_sections(doc):
        for fallback_ordinal, text_chunk in enumerate(_chunk_text(section.text), start=1):
            if section.page_hint is not None:
                chunk_ordinal = page_chunk_counts.get(section.page_hint, 0) + 1
                page_chunk_counts[section.page_hint] = chunk_ordinal
            else:
                chunk_ordinal = fallback_ordinal
            chunk_id = make_chunk_id(
                page_hint=section.page_hint,
                section_ordinal=section.ordinal,
                chunk_ordinal=chunk_ordinal,
            )
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "section_name": section.name,
                    "page_hint": section.page_hint,
                    "text_chars": len(text_chunk),
                }
            )

    chunks_with_page_hint = sum(1 for chunk in chunks if chunk.get("page_hint") is not None)
    return {
        "doc_id": header.doc_id,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "chunk_count": len(chunks),
        "chunks_with_page_hint": chunks_with_page_hint,
        "page_hint_coverage": (chunks_with_page_hint / len(chunks)) if chunks else 0.0,
        "first_chunk_ids": [str(chunk["chunk_id"]) for chunk in chunks[:10]],
        "last_chunk_ids": [str(chunk["chunk_id"]) for chunk in chunks[-10:]],
        "page_chunk_counts": {str(page): count for page, count in sorted(page_chunk_counts.items())},
    }


def build_document_summary(doc: Any) -> dict[str, Any]:
    from src.contracts.artifact_views import get_artifact_header

    header = get_artifact_header(doc)
    meta = getattr(doc, "meta", None) or getattr(doc, "metadata", None)
    return {
        "doc_id": header.doc_id,
        "title": header.title,
        "authors": list(header.authors or []),
        "source_ref": header.source_ref,
        "year": getattr(meta, "year", None),
        "journal": getattr(meta, "journal", None),
        "doi": getattr(meta, "doi", None),
        "page_count": len(list(getattr(doc, "pages", []) or [])),
        "table_count": len(list(getattr(doc, "tables", []) or [])),
        "schema_version": getattr(doc, "schema_version", None),
    }


def evaluate_expectations(
    *,
    document_summary: dict[str, Any],
    chunk_summary: dict[str, Any],
    expected: dict[str, Any],
    actual_sha256: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}

    def add_check(name: str, passed: bool, actual: Any, expected_value: Any) -> None:
        checks[name] = {
            "passed": bool(passed),
            "actual": actual,
            "expected": expected_value,
        }

    title_contains = str(expected.get("title_contains") or "").strip()
    if title_contains:
        title = str(document_summary.get("title") or "")
        add_check(
            "title_contains",
            title_contains.lower() in title.lower(),
            title,
            title_contains,
        )

    if "page_count" in expected:
        add_check("page_count", document_summary.get("page_count") == expected["page_count"], document_summary.get("page_count"), expected["page_count"])

    if "table_count" in expected:
        add_check("table_count", document_summary.get("table_count") == expected["table_count"], document_summary.get("table_count"), expected["table_count"])

    if "min_chunk_count" in expected:
        actual_count = int(chunk_summary.get("chunk_count") or 0)
        min_count = int(expected["min_chunk_count"])
        add_check("min_chunk_count", actual_count >= min_count, actual_count, f">={min_count}")

    if bool(expected.get("require_page_hints")):
        chunk_count = int(chunk_summary.get("chunk_count") or 0)
        hinted_count = int(chunk_summary.get("chunks_with_page_hint") or 0)
        add_check("require_page_hints", chunk_count > 0 and hinted_count == chunk_count, hinted_count, chunk_count)

    required_chunk_ids = [str(item) for item in expected.get("required_chunk_ids") or []]
    if required_chunk_ids:
        present = set(chunk_summary.get("first_chunk_ids") or []) | set(chunk_summary.get("last_chunk_ids") or [])
        missing = [chunk_id for chunk_id in required_chunk_ids if chunk_id not in present]
        add_check("required_chunk_ids", not missing, {"missing": missing}, required_chunk_ids)

    if expected_sha256:
        add_check("source_pdf_sha256", actual_sha256 == expected_sha256, actual_sha256, expected_sha256)

    return {
        "passed": all(item["passed"] for item in checks.values()),
        "checks": checks,
    }


def run_document_oracle(
    document: dict[str, Any],
    *,
    pdf_override: Path | None = None,
) -> dict[str, Any]:
    from src.agents.ingest_agent import IngestAgent

    pdf_path = (pdf_override or Path(str(document.get("local_path") or ""))).expanduser()
    if not pdf_path.is_absolute():
        pdf_path = (ROOT / pdf_path).resolve()
    else:
        pdf_path = pdf_path.resolve()

    expected = document.get("expected") if isinstance(document.get("expected"), dict) else {}
    result: dict[str, Any] = {
        "document_id": document.get("document_id"),
        "paper_id": document.get("paper_id"),
        "local_path": str(pdf_path),
        "payload_class": document.get("payload_class"),
        "status": "not_run",
        "decision": {"passed": False, "checks": {}},
    }

    if not pdf_path.exists():
        result["status"] = "missing_pdf"
        result["error"] = f"missing_pdf={pdf_path}"
        return result

    actual_sha256 = _sha256_file(pdf_path)
    parser_backend = str(document.get("parser_backend") or "fitz_pdfplumber")
    ingester = IngestAgent(parser_backend=parser_backend)
    doc = ingester.process_v2(str(pdf_path))
    if doc is None:
        result["status"] = "ingest_failed"
        result["error"] = "ingest_returned_none"
        return result

    document_summary = build_document_summary(doc)
    chunk_summary = build_chunk_summary(doc)
    decision = evaluate_expectations(
        document_summary=document_summary,
        chunk_summary=chunk_summary,
        expected=expected,
        actual_sha256=actual_sha256,
        expected_sha256=str(document.get("source_pdf_sha256") or "").strip() or None,
    )

    result.update(
        {
            "status": "completed",
            "parser_backend": parser_backend,
            "source_pdf_sha256": actual_sha256,
            "document_summary": document_summary,
            "chunk_summary": chunk_summary,
            "decision": decision,
        }
    )
    return result


def build_run_summary(
    *,
    manifest: dict[str, Any],
    details: list[dict[str, Any]],
    manifest_path: Path,
    run_id: str,
) -> dict[str, Any]:
    failed = [item for item in details if not bool((item.get("decision") or {}).get("passed"))]
    return {
        "schema_version": "local_pdf_ingest_index_oracle.summary.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "source_manifest": str(manifest_path),
        "manifest_batch_id": manifest.get("manifest_batch_id"),
        "layer": "review_gate_artifact",
        "canonical_status": "non_canonical",
        "document_count": len(details),
        "passed_count": len(details) - len(failed),
        "failed_count": len(failed),
        "decision": {
            "passed": not failed,
            "failed_documents": [item.get("document_id") for item in failed],
        },
        "documents": [
            {
                "document_id": item.get("document_id"),
                "status": item.get("status"),
                "passed": bool((item.get("decision") or {}).get("passed")),
                "page_count": ((item.get("document_summary") or {}).get("page_count")),
                "table_count": ((item.get("document_summary") or {}).get("table_count")),
                "chunk_count": ((item.get("chunk_summary") or {}).get("chunk_count")),
            }
            for item in details
        ],
    }


def run_local_pdf_ingest_index_oracle(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT_DIR,
    run_id: str | None = None,
    pdf_override: Path | None = None,
) -> Path:
    manifest_path = manifest_path.expanduser().resolve()
    manifest = _load_json_dict(manifest_path)
    run_id = run_id or f"local_pdf_ingest_index_oracle_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = out_dir.expanduser().resolve() / run_id
    documents = manifest.get("documents")
    if not isinstance(documents, list):
        raise ValueError("manifest_documents_array_required")

    details = [
        run_document_oracle(document, pdf_override=pdf_override if len(documents) == 1 else None)
        for document in documents
        if isinstance(document, dict)
    ]
    summary = build_run_summary(
        manifest=manifest,
        details=details,
        manifest_path=manifest_path,
        run_id=run_id,
    )
    _write_json(run_root / "details.json", {"documents": details})
    _write_json(run_root / "summary.json", summary)
    return run_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local PDF ingest/index oracle expectations.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--pdf", type=Path, default=None, help="Override PDF path for single-document manifests.")
    args = parser.parse_args(argv)

    run_root = run_local_pdf_ingest_index_oracle(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        run_id=args.run_id,
        pdf_override=args.pdf,
    )
    summary = _load_json_dict(run_root / "summary.json")
    print(f"[check_local_pdf_ingest_index_oracle] out={run_root}")
    print(f"[check_local_pdf_ingest_index_oracle] summary={run_root / 'summary.json'}")
    print(f"[check_local_pdf_ingest_index_oracle] passed={summary['decision']['passed']}")
    return 0 if bool(summary["decision"]["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
