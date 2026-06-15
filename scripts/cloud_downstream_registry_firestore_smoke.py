#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Sequence


DEFAULT_PROJECT_ID = "knudc-a01068202087"
DEFAULT_REGISTRY_COLLECTION = "cloud_downstream_registry_demo"
DEFAULT_PAPER_ID = "paper_mock_ready"
DEFAULT_LAB_ID = "lab_001"
FORBIDDEN_PUBLIC_TERMS = (
    "gcs_pdf_object_ref",
    "gcs_page_artifact_object_ref",
    "gs://",
    "signed_url",
    "service_account",
    "/Users/",
    "storage/artifacts",
    "claimset.resolved.json",
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a controlled Firestore smoke for the PaperPipe cloud-derived "
            "downstream review-pending registry."
        )
    )
    parser.add_argument("--project-id", default=os.getenv("PAPERPIPE_GCP_PROJECT_ID", DEFAULT_PROJECT_ID))
    parser.add_argument(
        "--registry-collection",
        default=os.getenv("PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION", DEFAULT_REGISTRY_COLLECTION),
    )
    parser.add_argument("--paper-id", default=os.getenv("PAPERPIPE_DEMO_REGISTRY_PAPER_ID", DEFAULT_PAPER_ID))
    parser.add_argument("--lab-id", default=os.getenv("PAPERPIPE_DEMO_LAB_ID", DEFAULT_LAB_ID))
    parser.add_argument("--api-key", default=os.getenv("LATTICE_API_KEY", "demo-secret"))
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only the final machine-readable summary JSON.",
    )
    return parser.parse_args(argv)


def _configure_env(args: argparse.Namespace) -> None:
    os.environ["LATTICE_API_KEY"] = args.api_key
    os.environ.setdefault("LATTICE_CORS_ALLOW_ORIGINS", "http://testserver")
    os.environ["PAPERPIPE_CLOUD_ADAPTER"] = "mock"
    os.environ["PAPERPIPE_CLOUD_METADATA_STORE"] = "memory"
    os.environ["PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE"] = "firestore"
    os.environ["PAPERPIPE_GCP_PROJECT_ID"] = args.project_id
    os.environ["PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION"] = args.registry_collection


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


def _assert_public_payload_is_redacted(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    for term in FORBIDDEN_PUBLIC_TERMS:
        if term in text:
            _fail(f"{label} leaked browser-hidden cloud/internal detail: {term}")


def _firestore_registry_summary(
    *,
    project_id: str,
    collection: str,
    paper_id: str,
) -> dict[str, Any]:
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError("google-cloud-firestore is required; run with `uv run --extra cloud`.") from exc

    client = firestore.Client(project=project_id)
    documents = []
    for snapshot in client.collection(collection).stream():
        data = snapshot.to_dict() or {}
        if data.get("paper_id") != paper_id:
            continue
        documents.append(data)
    if not documents:
        _fail(f"Firestore registry document was not found for paper_id={paper_id} in {collection}.")

    latest = documents[-1]
    if latest.get("canonical_status") != "derived_noncanonical":
        _fail(f"Unexpected Firestore canonical_status: {latest.get('canonical_status')}")
    if latest.get("review_status") != "review_pending":
        _fail(f"Unexpected Firestore review_status: {latest.get('review_status')}")
    return {
        "document_count_for_paper": len(documents),
        "canonical_status": latest.get("canonical_status"),
        "review_status": latest.get("review_status"),
        "registered_artifact_count": len(latest.get("registered_artifacts") or []),
    }


def _run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    _configure_env(args)

    from fastapi.testclient import TestClient

    from backend import main as api_main
    from src.services.cloud_paper_fake import reset_mock_cloud_paper_state

    reset_mock_cloud_paper_state()
    client = TestClient(api_main.app)
    browser_headers = {"origin": "http://testserver"}
    maintainer_headers = {
        **browser_headers,
        "x-paperpipe-actor-id": "registry_smoke_maintainer",
        "x-paperpipe-lab-id": args.lab_id,
        "x-paperpipe-role": "maintainer",
        "x-paperpipe-device-registered": "true",
        "x-paperpipe-download-allowed": "true",
    }

    registration = _assert_status(
        client.post(
            f"/api/cloud/papers/{args.paper_id}/downstream-artifacts/register",
            json={"lanes": ["meeting_pack", "obsidian_export"]},
            headers=maintainer_headers,
        ),
        200,
        "downstream registry registration",
    )
    if registration.get("review_status") != "review_pending":
        _fail(f"Expected review_pending registration, got {registration.get('review_status')}.")
    if registration.get("canonical_status") != "derived_noncanonical":
        _fail(f"Expected derived_noncanonical registration, got {registration.get('canonical_status')}.")
    _assert_public_payload_is_redacted(registration, label="registration")

    reset_mock_cloud_paper_state()
    registry = _assert_status(
        client.get(
            f"/api/cloud/papers/{args.paper_id}/downstream-artifacts/registry",
            headers=browser_headers,
        ),
        200,
        "downstream registry readback",
    )
    if registry.get("registry_status") != "available":
        _fail(f"Expected available registry, got {registry.get('registry_status')}.")
    if registry.get("registrations") != [registration]:
        _fail("Registry readback did not match the registration payload.")
    _assert_public_payload_is_redacted(registry, label="registry readback")

    firestore_summary = _firestore_registry_summary(
        project_id=args.project_id,
        collection=args.registry_collection,
        paper_id=args.paper_id,
    )

    return {
        "status": "passed",
        "project_id": args.project_id,
        "registry_collection": args.registry_collection,
        "paper_id": args.paper_id,
        "registration_status": registration.get("registration_status"),
        "registry_status": registry.get("registry_status"),
        "review_status": registry.get("review_status"),
        "canonical_status": registry.get("canonical_status"),
        "registered_artifact_count": len(registration.get("registered_artifacts", [])),
        "firestore": firestore_summary,
        "public_redaction": "passed",
    }


def main() -> int:
    args = _parse_args()
    try:
        summary = _run_smoke(args)
    except Exception as exc:
        payload = {"status": "failed", "error": str(exc)}
        if args.json:
            print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        else:
            print(f"Cloud downstream registry Firestore smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("Cloud downstream registry Firestore smoke passed.")
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
