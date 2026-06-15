#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


DEFAULT_PROJECT_ID = "knudc-a01068202087"
DEFAULT_RAW_BUCKET = "paperpipe-raw-pdf-dev-knudc-a01068202087"
DEFAULT_PAGE_BUCKET = "paperpipe-page-artifacts-dev-knudc-a01068202087"
DEFAULT_FIRESTORE_COLLECTION = "cloud_papers_demo"
DEFAULT_QUERY = "processed page text"
DEFAULT_LAB_ID = "lab_001"
FORBIDDEN_PUBLIC_TERMS = (
    "gcs_pdf_object_ref",
    "gcs_page_artifact_object_ref",
    "gs://",
    "signed_url",
    "service_account",
    "/Users/",
    "storage/artifacts",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the controlled PaperPipe GCS+Firestore cloud paper demo smoke "
            "through the FastAPI app without deploying Cloud Run or Cloud Tasks."
        )
    )
    parser.add_argument(
        "--pdf-path",
        default=os.getenv("PAPERPIPE_DEMO_PDF_PATH"),
        help="Path to the demo PDF. Defaults to PAPERPIPE_DEMO_PDF_PATH.",
    )
    parser.add_argument("--project-id", default=os.getenv("PAPERPIPE_GCP_PROJECT_ID", DEFAULT_PROJECT_ID))
    parser.add_argument("--raw-bucket", default=os.getenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", DEFAULT_RAW_BUCKET))
    parser.add_argument(
        "--page-bucket",
        default=os.getenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", DEFAULT_PAGE_BUCKET),
    )
    parser.add_argument(
        "--metadata-collection",
        default=os.getenv("PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION", DEFAULT_FIRESTORE_COLLECTION),
    )
    parser.add_argument("--lab-id", default=os.getenv("PAPERPIPE_DEMO_LAB_ID", DEFAULT_LAB_ID))
    parser.add_argument("--query", default=os.getenv("PAPERPIPE_DEMO_SEARCH_QUERY", DEFAULT_QUERY))
    parser.add_argument("--api-key", default=os.getenv("LATTICE_API_KEY", "demo-secret"))
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only the final machine-readable summary JSON.",
    )
    return parser.parse_args()


def _configure_env(args: argparse.Namespace) -> None:
    os.environ["LATTICE_API_KEY"] = args.api_key
    os.environ.setdefault("LATTICE_CORS_ALLOW_ORIGINS", "http://testserver")
    os.environ["PAPERPIPE_CLOUD_ADAPTER"] = "gcs"
    os.environ["PAPERPIPE_CLOUD_METADATA_STORE"] = "firestore"
    os.environ["PAPERPIPE_GCP_PROJECT_ID"] = args.project_id
    os.environ["PAPERPIPE_GCS_RAW_PDF_BUCKET"] = args.raw_bucket
    os.environ["PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET"] = args.page_bucket
    os.environ["PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION"] = args.metadata_collection


def _fail(message: str) -> None:
    raise RuntimeError(message)


def _assert_status(response: Any, expected_status: int, label: str) -> dict[str, Any]:
    if response.status_code != expected_status:
        body = response.text[:1000]
        _fail(f"{label} returned HTTP {response.status_code}, expected {expected_status}. Body: {body}")
    try:
        return response.json()
    except Exception as exc:  # pragma: no cover - defensive script output
        raise RuntimeError(f"{label} did not return JSON.") from exc


def _assert_public_payload_is_redacted(payload: Any, *, label: str, extra_terms: tuple[str, ...]) -> None:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    for term in (*FORBIDDEN_PUBLIC_TERMS, *extra_terms):
        if term and term in text:
            _fail(f"{label} leaked browser-hidden cloud/internal detail: {term}")


def _firestore_document_summary(
    *,
    project_id: str,
    collection: str,
    paper_id: str,
    lab_id: str,
) -> dict[str, Any]:
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError("google-cloud-firestore is required; run with `uv run --extra cloud`.") from exc

    snapshot = firestore.Client(project=project_id).collection(collection).document(paper_id).get()
    if not snapshot.exists:
        _fail(f"Firestore document was not found for {collection}/{paper_id}.")
    data = snapshot.to_dict() or {}
    expected = {
        "paper_id": paper_id,
        "upload_status": "ready",
        "processing_status": "ready",
        "lab_id": lab_id,
    }
    request = data.get("request") or {}
    if request.get("lab_id") != expected["lab_id"]:
        _fail(f"Firestore lab_id mismatch: expected {expected['lab_id']}, got {request.get('lab_id')}")
    for field in ("paper_id", "upload_status", "processing_status"):
        if data.get(field) != expected[field]:
            _fail(f"Firestore {field} mismatch: expected {expected[field]}, got {data.get(field)}")
    return {
        "document_exists": True,
        "upload_status": data.get("upload_status"),
        "processing_status": data.get("processing_status"),
        "lab_id": request.get("lab_id"),
    }


def _run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    pdf_path = Path(args.pdf_path or "").expanduser()
    if not args.pdf_path:
        _fail("Provide --pdf-path or set PAPERPIPE_DEMO_PDF_PATH.")
    if not pdf_path.is_file():
        _fail("Demo PDF was not found. Check --pdf-path or PAPERPIPE_DEMO_PDF_PATH.")

    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    _configure_env(args)

    from fastapi.testclient import TestClient

    from backend import main as api_main
    from src.services.cloud_paper_fake import reset_mock_cloud_paper_state

    reset_mock_cloud_paper_state()
    client = TestClient(api_main.app)
    headers = {"origin": "http://testserver"}
    redaction_extra_terms = (args.raw_bucket, args.page_bucket)

    upload = _assert_status(
        client.post(
            "/api/cloud/papers/upload-intents",
            json={
                "filename": pdf_path.name,
                "content_type": "application/pdf",
                "source_pdf_sha256": pdf_sha256,
                "lab_id": args.lab_id,
            },
            headers=headers,
        ),
        200,
        "upload intent",
    )
    _assert_public_payload_is_redacted(upload, label="upload intent", extra_terms=redaction_extra_terms)
    if upload.get("upload_mode") != "backend_mediated":
        _fail(f"Expected backend_mediated upload mode, got {upload.get('upload_mode')}.")
    paper_id = str(upload.get("paper_id") or "")
    if not paper_id:
        _fail("Upload intent did not return paper_id.")

    pending = _assert_status(client.get(f"/api/cloud/papers/{paper_id}", headers=headers), 200, "pending bundle")
    if pending.get("processing_status") != "pending":
        _fail(f"Expected pending processing_status, got {pending.get('processing_status')}.")
    _assert_public_payload_is_redacted(pending, label="pending bundle", extra_terms=redaction_extra_terms)

    source_upload = _assert_status(
        client.post(
            f"/api/cloud/papers/{paper_id}/source-pdf",
            files={"source_pdf": (pdf_path.name, pdf_bytes, "application/pdf")},
            headers=headers,
        ),
        200,
        "source PDF upload",
    )
    if source_upload.get("source_pdf_sha256") != pdf_sha256:
        _fail("Source upload SHA256 did not match the local PDF.")
    if source_upload.get("source_pdf_size_bytes") != len(pdf_bytes):
        _fail("Source upload size did not match the local PDF.")
    _assert_public_payload_is_redacted(source_upload, label="source PDF upload", extra_terms=redaction_extra_terms)

    completed = _assert_status(
        client.post(
            f"/api/cloud/papers/{paper_id}/complete-upload",
            json={"source_pdf_sha256": pdf_sha256},
            headers=headers,
        ),
        200,
        "complete upload",
    )
    if completed.get("processing_status") != "ready":
        _fail(f"Expected ready processing_status, got {completed.get('processing_status')}.")
    _assert_public_payload_is_redacted(completed, label="completed bundle", extra_terms=redaction_extra_terms)

    page = _assert_status(client.get(f"/api/cloud/papers/{paper_id}/page", headers=headers), 200, "page read")
    if page.get("schema_version") != "cloud_page_artifact_public.v1":
        _fail(f"Unexpected public page schema: {page.get('schema_version')}")
    if page.get("paper_id") != paper_id:
        _fail("Public page paper_id did not match the uploaded paper.")
    if not page.get("blocks"):
        _fail("Public page returned no blocks.")
    _assert_public_payload_is_redacted(page, label="public page", extra_terms=redaction_extra_terms)

    search = _assert_status(
        client.get("/api/cloud/papers/search", params={"q": args.query}, headers=headers),
        200,
        "cloud search",
    )
    hit_ids = [item.get("bundle", {}).get("paper_id") for item in search.get("items", [])]
    if paper_id not in hit_ids:
        _fail(f"Search query did not include the uploaded paper_id. Hits: {hit_ids}")
    _assert_public_payload_is_redacted(search, label="cloud search", extra_terms=redaction_extra_terms)

    firestore_summary = _firestore_document_summary(
        project_id=args.project_id,
        collection=args.metadata_collection,
        paper_id=paper_id,
        lab_id=args.lab_id,
    )

    return {
        "status": "passed",
        "project_id": args.project_id,
        "metadata_collection": args.metadata_collection,
        "pdf_name": pdf_path.name,
        "pdf_size_bytes": len(pdf_bytes),
        "pdf_sha256": pdf_sha256,
        "paper_id": paper_id,
        "upload_mode": upload.get("upload_mode"),
        "processing_status": completed.get("processing_status"),
        "page_schema_version": page.get("schema_version"),
        "page_block_count": len(page.get("blocks", [])),
        "search_query": args.query,
        "search_hit_ids": hit_ids,
        "firestore": firestore_summary,
        "public_redaction": "passed",
    }


def main() -> int:
    args = _parse_args()
    try:
        summary = _run_smoke(args)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        else:
            print(f"Cloud paper demo rehearsal smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("Cloud paper demo rehearsal smoke passed.")
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
