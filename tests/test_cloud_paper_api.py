from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import fitz

import src.db_utils as db_utils
from backend import main as api_main
from src.services.event_log import list_user_actions
from src.services.cloud_paper_fake import reset_mock_cloud_paper_state


def _browser_headers() -> dict[str, str]:
    return {"origin": "http://testserver"}


def _maintainer_hydrate_headers() -> dict[str, str]:
    return {
        **_browser_headers(),
        "x-paperpipe-actor-id": "user_maintainer",
        "x-paperpipe-lab-id": "lab_001",
        "x-paperpipe-role": "maintainer",
        "x-paperpipe-device-registered": "true",
        "x-paperpipe-download-allowed": "true",
    }


def setup_function() -> None:
    reset_mock_cloud_paper_state()


def _real_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_textbox(
        fitz.Rect(54, 72, 558, 140),
        "Real Cloud Upload Title\nAuthors: PaperPipe E2E",
        fontsize=16,
    )
    page.insert_textbox(
        fitz.Rect(54, 160, 558, 260),
        "Abstract\nThis abstract proves the cloud page processor used actual PDF text extraction.",
        fontsize=11,
    )
    page.insert_textbox(
        fitz.Rect(54, 290, 558, 430),
        "Introduction\nThe body snippet should mention hippocampal signal, methods context, and real extracted content.",
        fontsize=11,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class _FakeBlob:
    def __init__(self, name: str):
        self.name = name
        self.uploads: list[dict[str, object]] = []
        self.metadata: dict[str, str] | None = None
        self.size: int | None = None
        self._data = b""
        self._exists = False

    def upload_from_string(self, data: bytes, *, content_type: str) -> None:
        self.uploads.append({"data": data, "content_type": content_type})
        self.size = len(data)
        self._data = data
        self._exists = True

    def download_as_bytes(self) -> bytes:
        if not self._exists:
            raise FileNotFoundError(self.name)
        return self._data

    def exists(self) -> bool:
        return self._exists

    def reload(self) -> None:
        if not self._exists:
            raise FileNotFoundError(self.name)


class _FakeBucket:
    def __init__(self, name: str):
        self.name = name
        self.blobs: dict[str, _FakeBlob] = {}

    def exists(self) -> bool:
        return True

    def blob(self, name: str) -> _FakeBlob:
        if name not in self.blobs:
            self.blobs[name] = _FakeBlob(name)
        return self.blobs[name]


class _FakeStorageClient:
    instances: list["_FakeStorageClient"] = []
    buckets_by_name: dict[str, _FakeBucket] = {}

    def __init__(self, *, project: str):
        self.project = project
        self.buckets: dict[str, _FakeBucket] = {}
        self.instances.append(self)

    def bucket(self, name: str) -> _FakeBucket:
        if name not in self.buckets_by_name:
            self.buckets_by_name[name] = _FakeBucket(name)
        bucket = self.buckets_by_name[name]
        self.buckets[name] = bucket
        return bucket


class _FakeStorageModule:
    Client = _FakeStorageClient


class _FakeFirestoreSnapshot:
    def __init__(self, data: dict[str, object] | None):
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, object] | None:
        if self._data is None:
            return None
        return dict(self._data)


class _FakeFirestoreDocument:
    def __init__(self, collection: "_FakeFirestoreCollection", document_id: str):
        self._collection = collection
        self._document_id = document_id

    def set(self, data: dict[str, object]) -> None:
        self._collection.documents[self._document_id] = dict(data)

    def get(self) -> _FakeFirestoreSnapshot:
        return _FakeFirestoreSnapshot(self._collection.documents.get(self._document_id))

    def delete(self) -> None:
        self._collection.documents.pop(self._document_id, None)


class _FakeFirestoreCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}

    def document(self, document_id: str) -> _FakeFirestoreDocument:
        return _FakeFirestoreDocument(self, document_id)

    def limit(self, _count: int) -> "_FakeFirestoreCollection":
        return self

    def stream(self) -> list[_FakeFirestoreSnapshot]:
        return [_FakeFirestoreSnapshot(data) for data in self.documents.values()]


class _FakeFirestoreClient:
    instances: list["_FakeFirestoreClient"] = []
    collections_by_name: dict[str, _FakeFirestoreCollection] = {}

    def __init__(self, *, project: str):
        self.project = project
        self.instances.append(self)

    def collection(self, collection_name: str) -> _FakeFirestoreCollection:
        if collection_name not in self.collections_by_name:
            self.collections_by_name[collection_name] = _FakeFirestoreCollection()
        return self.collections_by_name[collection_name]


class _FakeFirestoreModule:
    Client = _FakeFirestoreClient


class _FakeDefaultCredentialsError(Exception):
    pass


class _FakeAuthModule:
    default_exception: Exception | None = None

    @classmethod
    def default(cls, *args, **kwargs):
        if cls.default_exception is not None:
            raise cls.default_exception
        return object(), "paperpipe-dev"


def _patch_fake_firestore(monkeypatch) -> None:
    _FakeFirestoreClient.instances.clear()
    _FakeFirestoreClient.collections_by_name.clear()
    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "google.cloud.firestore":
            return _FakeFirestoreModule
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)


def _patch_fake_gcp(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    _FakeFirestoreClient.instances.clear()
    _FakeFirestoreClient.collections_by_name.clear()
    _FakeAuthModule.default_exception = None
    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "google.cloud.storage":
            return _FakeStorageModule
        if name == "google.cloud.firestore":
            return _FakeFirestoreModule
        if name == "google.auth":
            return _FakeAuthModule
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)


def _assert_cloud_public_payload_is_redacted(payload: dict[str, object]) -> None:
    text = str(payload)
    assert "gcs_pdf_object_ref" not in text
    assert "gcs_page_artifact_object_ref" not in text
    assert "gs://" not in text
    assert "signed_url" not in text
    assert "service_account" not in text
    assert "/Users/" not in text
    assert "storage/artifacts" not in text


def test_cloud_root_routes_require_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    responses = [
        client.get("/cloud/papers/paper_mock_ready"),
        client.get("/cloud/papers/paper_mock_ready/page"),
        client.get("/cloud/papers/paper_mock_ready/summary"),
        client.get("/cloud/papers/paper_mock_ready/derived-artifacts"),
        client.get("/cloud/papers/paper_mock_ready/downstream-adapter"),
        client.get("/cloud/papers/paper_mock_ready/meeting-pack-context"),
        client.get("/cloud/papers/paper_mock_ready/chart-pack/tables/table_001/snapshot"),
        client.get("/cloud/papers/paper_mock_ready/image-evidence/figures/figure_001/request"),
        client.get("/cloud/papers/paper_mock_ready/method-comparison-context"),
        client.get("/cloud/papers/paper_mock_ready/obsidian-section"),
        client.get("/cloud/papers/paper_mock_ready/downstream-artifacts/registry"),
        client.post("/cloud/papers/paper_mock_ready/obsidian-section/export", json={}),
        client.post("/cloud/papers/paper_mock_ready/downstream-artifacts/register", json={}),
        client.get("/cloud/papers/paper_mock_ready/ocr"),
        client.get("/cloud/papers/paper_mock_ready/tables"),
        client.get("/cloud/papers/paper_mock_ready/figures"),
        client.get("/cloud/papers/paper_mock_ready/figures/figure_001/analysis"),
        client.get("/cloud/papers/paper_mock_ready/figures/figure_001/image"),
        client.get("/cloud/papers/search", params={"q": "processed"}),
        client.post(
            "/cloud/papers/upload-intents",
            json={
                "filename": "paper.pdf",
                "content_type": "application/pdf",
                "source_pdf_sha256": "a" * 64,
                "lab_id": "lab_001",
            },
        ),
        client.post(
            "/cloud/papers/paper_mock_ready/source-pdf",
            files={"source_pdf": ("paper.pdf", b"%PDF-1.4\nmock", "application/pdf")},
        ),
        client.post("/cloud/papers/paper_mock_ready/complete-upload", json={"source_pdf_sha256": "a" * 64}),
        client.post("/cloud/papers/paper_mock_ready/hydrate-local"),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.json()["error_code"] == "UNAUTHORIZED"


def test_cloud_api_prefixed_routes_bridge_same_origin_browser_calls(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    blocked = client.get("/api/cloud/papers/paper_mock_ready")
    assert blocked.status_code == 401
    assert blocked.json()["error_code"] == "UNAUTHORIZED"

    status = client.get("/api/cloud/papers/paper_mock_ready", headers=_browser_headers())
    assert status.status_code == 200
    payload = status.json()
    assert payload["paper_id"] == "paper_mock_ready"
    assert payload["processing_status"] == "ready"
    assert payload["allowed_actions"] == ["read_page"]
    _assert_cloud_public_payload_is_redacted(payload)

    page = client.get("/api/cloud/papers/paper_mock_ready/page", headers=_browser_headers())
    assert page.status_code == 200
    page_payload = page.json()
    assert page_payload["paper_id"] == "paper_mock_ready"
    assert page_payload["schema_version"] == "cloud_page_artifact_public.v1"
    assert page_payload["blocks"][0]["block_id"] == "block_001"
    assert page_payload["blocks"][0]["page"] == 1
    assert page_payload["blocks"][0]["metadata"] == {"section": "abstract"}
    _assert_cloud_public_payload_is_redacted(page_payload)
    assert "worker_metadata" not in str(page_payload)

    summary = client.get("/api/cloud/papers/paper_mock_ready/summary", headers=_browser_headers())
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["paper_id"] == "paper_mock_ready"
    assert summary_payload["schema_version"] == "cloud_paper_summary.v1"
    assert summary_payload["input_source"] == "cloud_page_artifact"
    assert summary_payload["summary_kind"] == "extractive_bridge"
    assert summary_payload["review_status"] == "draft"
    assert summary_payload["payload_class"] == "local_only"
    assert "Mock processed page text" in summary_payload["summary_text"]
    assert summary_payload["source_blocks"][0]["block_id"] == "block_001"
    assert summary_payload["source_blocks"][0]["page"] == 1
    assert summary_payload["source_blocks"][0]["payload_class"] == "local_only"
    assert summary_payload["source_blocks"][0]["metadata"] == {"section": "abstract"}
    _assert_cloud_public_payload_is_redacted(summary_payload)

    derived = client.get("/api/cloud/papers/paper_mock_ready/derived-artifacts", headers=_browser_headers())
    assert derived.status_code == 200
    derived_payload = derived.json()
    assert derived_payload["paper_id"] == "paper_mock_ready"
    assert derived_payload["schema_version"] == "cloud_paper_derived_artifacts.v1"
    assert derived_payload["payload_class"] == "local_only"
    assert derived_payload["ocr_blocks"][0]["ocr_block_id"] == "ocr_001"
    assert derived_payload["ocr_blocks"][0]["source"]["page"] == 1
    assert derived_payload["tables"][0]["table_id"] == "table_001"
    assert derived_payload["figures"][0]["figure_id"] == "figure_001"
    assert derived_payload["figures"][0]["image_route"].startswith("/api/cloud/papers/")
    assert derived_payload["figure_analyses"][0]["figure_id"] == "figure_001"
    _assert_cloud_public_payload_is_redacted(derived_payload)

    downstream = client.get("/api/cloud/papers/paper_mock_ready/downstream-adapter", headers=_browser_headers())
    assert downstream.status_code == 200
    downstream_payload = downstream.json()
    assert downstream_payload["schema_version"] == "cloud_paper_downstream_adapter.v1"
    assert downstream_payload["candidates"][0]["canonical_status"] == "derived_noncanonical"
    assert {candidate["kind"] for candidate in downstream_payload["candidates"]} == {
        "ocr_text",
        "table",
        "figure",
        "figure_analysis",
    }
    _assert_cloud_public_payload_is_redacted(downstream_payload)

    meeting_context = client.get("/api/cloud/papers/paper_mock_ready/meeting-pack-context", headers=_browser_headers())
    assert meeting_context.status_code == 200
    meeting_payload = meeting_context.json()
    assert meeting_payload["schema_version"] == "meeting_pack_cloud_derived_context.v1"
    assert meeting_payload["readiness"] == "background_only"
    assert meeting_payload["items"][0]["support_type"] == "background"
    assert meeting_payload["items"][0]["evidence_refs"] == []
    _assert_cloud_public_payload_is_redacted(meeting_payload)

    chart_snapshot = client.get(
        "/api/cloud/papers/paper_mock_ready/chart-pack/tables/table_001/snapshot",
        headers=_browser_headers(),
    )
    assert chart_snapshot.status_code == 200
    chart_payload = chart_snapshot.json()
    assert chart_payload["source_ref"]["source_kind"] == "cloud_derived_table"
    assert chart_payload["rows"] == [{"Group": "Control", "N": 10}, {"Group": "Treatment", "N": 12}]
    assert any(warning["code"] == "cloud_derived_noncanonical" for warning in chart_payload["warnings"])
    _assert_cloud_public_payload_is_redacted(chart_payload)

    image_request = client.get(
        "/api/cloud/papers/paper_mock_ready/image-evidence/figures/figure_001/request",
        headers=_browser_headers(),
    )
    assert image_request.status_code == 200
    image_payload = image_request.json()
    assert image_payload["source_ref"]["source_kind"] == "external_image_ref"
    assert image_payload["source_ref"]["external_ref"].startswith("/api/cloud/papers/")
    assert image_payload["linked_claim_refs"] == []
    assert any(warning["code"] == "cloud_derived_noncanonical" for warning in image_payload["warnings"])
    _assert_cloud_public_payload_is_redacted(image_payload)

    method_context = client.get(
        "/api/cloud/papers/paper_mock_ready/method-comparison-context",
        headers=_browser_headers(),
    )
    assert method_context.status_code == 200
    method_payload = method_context.json()
    assert method_payload["schema_version"] == "method_comparison_cloud_derived_context.v1"
    assert method_payload["readiness"] == "background_only"
    assert method_payload["items"][0]["comparison_cell_status"] == "missing"
    assert method_payload["items"][0]["evidence_refs"] == []
    _assert_cloud_public_payload_is_redacted(method_payload)

    obsidian_section = client.get("/api/cloud/papers/paper_mock_ready/obsidian-section", headers=_browser_headers())
    assert obsidian_section.status_code == 200
    assert obsidian_section.headers["content-type"].startswith("text/plain")
    assert "## Cloud-Derived Context" in obsidian_section.text
    assert "Canonical status: derived_noncanonical" in obsidian_section.text
    _assert_cloud_public_payload_is_redacted({"markdown": obsidian_section.text})

    reader_obsidian_export = client.post(
        "/api/cloud/papers/paper_mock_ready/obsidian-section/export",
        json={},
        headers=_browser_headers(),
    )
    assert reader_obsidian_export.status_code == 403
    assert reader_obsidian_export.json()["error_code"] == "CLOUD_PAPER_FORBIDDEN"

    existing_note = "# Existing Paper Note\n\nOld content.\n\n" + obsidian_section.text + "\nTrailing note."
    obsidian_export = client.post(
        "/api/cloud/papers/paper_mock_ready/obsidian-section/export",
        json={"existing_markdown": existing_note},
        headers=_maintainer_hydrate_headers(),
    )
    assert obsidian_export.status_code == 200
    obsidian_export_payload = obsidian_export.json()
    assert obsidian_export_payload["schema_version"] == "cloud_paper_obsidian_export.v1"
    assert obsidian_export_payload["export_status"] == "prepared"
    assert obsidian_export_payload["canonical_status"] == "derived_noncanonical"
    assert obsidian_export_payload["review_status"] == "review_pending"
    assert obsidian_export_payload["section_markers"]["start"].startswith("<!-- paperpipe:cloud-derived:start")
    assert obsidian_export_payload["note_markdown"].count("<!-- paperpipe:cloud-derived:start") == 1
    assert "Trailing note." in obsidian_export_payload["note_markdown"]
    _assert_cloud_public_payload_is_redacted(obsidian_export_payload)

    obsidian_export_again = client.post(
        "/api/cloud/papers/paper_mock_ready/obsidian-section/export",
        json={"existing_markdown": obsidian_export_payload["note_markdown"]},
        headers=_maintainer_hydrate_headers(),
    )
    assert obsidian_export_again.status_code == 200
    assert obsidian_export_again.json()["artifact_id"] == obsidian_export_payload["artifact_id"]
    assert obsidian_export_again.json()["note_markdown"] == obsidian_export_payload["note_markdown"]

    reader_register = client.post(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/register",
        json={},
        headers=_browser_headers(),
    )
    assert reader_register.status_code == 403
    assert reader_register.json()["error_code"] == "CLOUD_PAPER_FORBIDDEN"

    registration = client.post(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/register",
        json={"lanes": ["meeting_pack", "chart_pack", "image_evidence", "method_comparison", "obsidian_export"]},
        headers=_maintainer_hydrate_headers(),
    )
    assert registration.status_code == 200
    registration_payload = registration.json()
    assert registration_payload["schema_version"] == "cloud_paper_downstream_artifact_registration.v1"
    assert registration_payload["registration_status"] == "registered"
    assert registration_payload["canonical_status"] == "derived_noncanonical"
    assert registration_payload["review_status"] == "review_pending"
    assert {artifact["lane"] for artifact in registration_payload["registered_artifacts"]} == {
        "meeting_pack",
        "chart_pack",
        "image_evidence",
        "method_comparison",
        "obsidian_export",
    }
    assert all(artifact["candidate_count"] > 0 for artifact in registration_payload["registered_artifacts"])
    _assert_cloud_public_payload_is_redacted(registration_payload)

    registry = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/registry",
        headers=_browser_headers(),
    )
    assert registry.status_code == 200
    registry_payload = registry.json()
    assert registry_payload["schema_version"] == "cloud_paper_downstream_artifact_registry.v1"
    assert registry_payload["paper_id"] == "paper_mock_ready"
    assert registry_payload["run_id"] == registration_payload["run_id"]
    assert registry_payload["registry_status"] == "available"
    assert registry_payload["canonical_status"] == "derived_noncanonical"
    assert registry_payload["review_status"] == "review_pending"
    assert registry_payload["registrations"] == [registration_payload]
    _assert_cloud_public_payload_is_redacted(registry_payload)

    artifact_id = registration_payload["registered_artifacts"][0]["artifact_id"]
    reader_review = client.post(
        f"/api/cloud/papers/paper_mock_ready/downstream-artifacts/{artifact_id}/review",
        json={"review_status": "review_approved", "reviewer_note": "Looks ready for demo handoff."},
        headers=_browser_headers(),
    )
    assert reader_review.status_code == 403
    assert reader_review.json()["error_code"] == "CLOUD_PAPER_FORBIDDEN"

    review = client.post(
        f"/api/cloud/papers/paper_mock_ready/downstream-artifacts/{artifact_id}/review",
        json={"review_status": "review_approved", "reviewer_note": "Looks ready for demo handoff."},
        headers=_maintainer_hydrate_headers(),
    )
    assert review.status_code == 200
    review_payload = review.json()
    assert review_payload["schema_version"] == "cloud_paper_downstream_artifact_registry.v1"
    assert review_payload["canonical_status"] == "derived_noncanonical"
    assert review_payload["review_status"] == "review_pending"
    reviewed_artifact = next(
        artifact
        for registered in review_payload["registrations"]
        for artifact in registered["registered_artifacts"]
        if artifact["artifact_id"] == artifact_id
    )
    assert reviewed_artifact["review_status"] == "review_approved"
    assert "reviewer_note" not in reviewed_artifact
    assert reviewed_artifact["review_events"][-1]["review_status"] == "review_approved"
    assert reviewed_artifact["review_events"][-1]["reviewer_role"] == "maintainer"
    assert reviewed_artifact["review_events"][-1]["reviewer_note_recorded"] is True
    assert "reviewer_note" not in reviewed_artifact["review_events"][-1]
    _assert_cloud_public_payload_is_redacted(review_payload)
    assert "Looks ready for demo handoff." not in json.dumps(review_payload)

    reviewed_registry = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/registry",
        headers=_browser_headers(),
    )
    assert reviewed_registry.status_code == 200
    reviewed_registry_artifact = next(
        artifact
        for registered in reviewed_registry.json()["registrations"]
        for artifact in registered["registered_artifacts"]
        if artifact["artifact_id"] == artifact_id
    )
    assert reviewed_registry.json()["review_status"] == "review_pending"
    assert reviewed_registry_artifact["review_status"] == "review_approved"
    assert reviewed_registry_artifact["review_events"][-1]["reviewer_role"] == "maintainer"

    promotion_readiness = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/promotion-readiness",
        headers=_browser_headers(),
    )
    assert promotion_readiness.status_code == 200
    promotion_payload = promotion_readiness.json()
    assert promotion_payload["schema_version"] == "cloud_paper_downstream_promotion_readiness.v1"
    assert promotion_payload["canonical_status"] == "derived_noncanonical"
    assert promotion_payload["promotion_status"] == "blocked"
    assert promotion_payload["eligible"] is False
    assert promotion_payload["approved_artifact_count"] == 1
    assert promotion_payload["pending_artifact_count"] > 0
    assert any(blocker["code"] == "review_pending" for blocker in promotion_payload["blockers"])
    _assert_cloud_public_payload_is_redacted(promotion_payload)

    blocked_plan = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/promotion-plan",
        headers=_browser_headers(),
    )
    assert blocked_plan.status_code == 200
    blocked_plan_payload = blocked_plan.json()
    assert blocked_plan_payload["schema_version"] == "cloud_paper_downstream_promotion_plan.v1"
    assert blocked_plan_payload["plan_status"] == "blocked"
    assert blocked_plan_payload["dry_run"] is True
    assert blocked_plan_payload["mutation_applied"] is False
    assert blocked_plan_payload["canonical_status"] == "derived_noncanonical"
    assert blocked_plan_payload["promotion_items"] == []
    assert any(blocker["code"] == "review_pending" for blocker in blocked_plan_payload["blockers"])
    _assert_cloud_public_payload_is_redacted(blocked_plan_payload)

    for registered_artifact in registration_payload["registered_artifacts"][1:]:
        remaining_review = client.post(
            f"/api/cloud/papers/paper_mock_ready/downstream-artifacts/{registered_artifact['artifact_id']}/review",
            json={"review_status": "review_approved"},
            headers=_maintainer_hydrate_headers(),
        )
        assert remaining_review.status_code == 200

    ready_promotion = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/promotion-readiness",
        headers=_browser_headers(),
    )
    assert ready_promotion.status_code == 200
    ready_payload = ready_promotion.json()
    assert ready_payload["promotion_status"] == "eligible"
    assert ready_payload["eligible"] is True
    assert ready_payload["approved_artifact_count"] == ready_payload["total_artifact_count"]
    assert ready_payload["blockers"] == []
    _assert_cloud_public_payload_is_redacted(ready_payload)

    ready_plan = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/promotion-plan",
        headers=_browser_headers(),
    )
    assert ready_plan.status_code == 200
    ready_plan_payload = ready_plan.json()
    assert ready_plan_payload["schema_version"] == "cloud_paper_downstream_promotion_plan.v1"
    assert ready_plan_payload["plan_status"] == "ready"
    assert ready_plan_payload["dry_run"] is True
    assert ready_plan_payload["mutation_applied"] is False
    assert ready_plan_payload["promotion_target"] == "canonical_structured_state"
    assert ready_plan_payload["canonical_status"] == "derived_noncanonical"
    assert ready_plan_payload["blockers"] == []
    assert len(ready_plan_payload["promotion_items"]) == len(registration_payload["registered_artifacts"])
    assert {item["review_status"] for item in ready_plan_payload["promotion_items"]} == {"review_approved"}
    assert {item["promotion_action"] for item in ready_plan_payload["promotion_items"]} == {
        "prepare_canonical_state_promotion"
    }
    _assert_cloud_public_payload_is_redacted(ready_plan_payload)

    ocr = client.get("/api/cloud/papers/paper_mock_ready/ocr", headers=_browser_headers())
    assert ocr.status_code == 200
    ocr_payload = ocr.json()
    assert ocr_payload["schema_version"] == "cloud_paper_ocr.v1"
    assert ocr_payload["ocr_blocks"][0]["ocr_block_id"] == "ocr_001"
    _assert_cloud_public_payload_is_redacted(ocr_payload)

    tables = client.get("/api/cloud/papers/paper_mock_ready/tables", headers=_browser_headers())
    assert tables.status_code == 200
    tables_payload = tables.json()
    assert tables_payload["schema_version"] == "cloud_paper_tables.v1"
    assert tables_payload["tables"][0]["table_id"] == "table_001"
    _assert_cloud_public_payload_is_redacted(tables_payload)

    figures = client.get("/api/cloud/papers/paper_mock_ready/figures", headers=_browser_headers())
    assert figures.status_code == 200
    figures_payload = figures.json()
    assert figures_payload["schema_version"] == "cloud_paper_figures.v1"
    assert figures_payload["figures"][0]["figure_id"] == "figure_001"
    assert figures_payload["figures"][0]["image_route"].startswith("/api/cloud/papers/")
    _assert_cloud_public_payload_is_redacted(figures_payload)

    analysis = client.get(
        "/api/cloud/papers/paper_mock_ready/figures/figure_001/analysis",
        headers=_browser_headers(),
    )
    assert analysis.status_code == 200
    analysis_payload = analysis.json()
    assert analysis_payload["schema_version"] == "cloud_paper_figure_analysis.v1"
    assert analysis_payload["figure_id"] == "figure_001"
    assert analysis_payload["analyses"][0]["analysis_id"] == "figure_analysis_001"
    _assert_cloud_public_payload_is_redacted(analysis_payload)

    image = client.get(
        "/api/cloud/papers/paper_mock_ready/figures/figure_001/image",
        headers=_browser_headers(),
    )
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content.startswith(b"\x89PNG")


def test_cloud_papers_list_returns_redacted_ui_index(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    response = client.get("/api/cloud/papers", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "cloud_paper_list.v1"
    paper_ids = [item["paper_id"] for item in payload["items"]]
    assert "paper_mock_ready" in paper_ids
    assert "paper_mock_running" in paper_ids
    assert "paper_mock_failed" in paper_ids
    ready_item = next(item for item in payload["items"] if item["paper_id"] == "paper_mock_ready")
    running_item = next(item for item in payload["items"] if item["paper_id"] == "paper_mock_running")
    assert ready_item["processing_status"] == "ready"
    assert ready_item["allowed_actions"] == ["read_page"]
    assert ready_item["local_hydration"]["status"] == "not_hydrated"
    assert running_item["processing_status"] == "running"
    assert running_item["allowed_actions"] == []
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_papers_list_honors_lab_access_policy(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    response = client.get(
        "/api/cloud/papers",
        headers={
            **_browser_headers(),
            "x-paperpipe-lab-id": "other_lab",
            "x-paperpipe-device-registered": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []


def test_cloud_paper_search_finds_ready_page_text_with_redacted_payload(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    response = client.get(
        "/api/cloud/papers/search",
        params={"q": "processed page text"},
        headers=_browser_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "cloud_paper_search.v1"
    assert payload["query"] == "processed page text"
    assert [item["bundle"]["paper_id"] for item in payload["items"]] == ["paper_mock_ready"]
    hit = payload["items"][0]
    assert hit["bundle"]["processing_status"] == "ready"
    assert hit["bundle"]["allowed_actions"] == ["read_page"]
    assert hit["matched_blocks"][0]["block_id"] == "block_001"
    assert hit["matched_blocks"][0]["page"] == 1
    assert hit["matched_blocks"][0]["payload_class"] == "local_only"
    assert "Mock processed page text" in hit["matched_blocks"][0]["text_snippet"]
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_paper_search_honors_lab_access_policy(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    response = client.get(
        "/api/cloud/papers/search",
        params={"q": "processed page text"},
        headers={
            **_browser_headers(),
            "x-paperpipe-lab-id": "other_lab",
            "x-paperpipe-device-registered": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "cloud_paper_search.v1"
    assert payload["items"] == []
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_upload_intent_and_completion_return_redacted_mock_contract(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)
    pdf_bytes = _real_pdf_bytes()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    upload = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": source_pdf_sha256,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )
    assert upload.status_code == 200
    upload_payload = upload.json()
    assert upload_payload["upload_mode"] == "mock"
    assert upload_payload["paper_id"].startswith("paper_mock_")
    _assert_cloud_public_payload_is_redacted(upload_payload)

    pending = client.get(
        f"/api/cloud/papers/{upload_payload['paper_id']}",
        headers=_browser_headers(),
    )
    assert pending.status_code == 200
    pending_payload = pending.json()
    assert pending_payload["processing_status"] == "pending"
    assert pending_payload["allowed_actions"] == []
    _assert_cloud_public_payload_is_redacted(pending_payload)

    pending_page = client.get(
        f"/api/cloud/papers/{upload_payload['paper_id']}/page",
        headers=_browser_headers(),
    )
    assert pending_page.status_code == 409
    assert pending_page.json()["error_code"] == "CLOUD_PAPER_NOT_READY"
    assert pending_page.json()["bundle"]["processing_status"] == "pending"
    _assert_cloud_public_payload_is_redacted(pending_page.json())

    pending_summary = client.get(
        f"/api/cloud/papers/{upload_payload['paper_id']}/summary",
        headers=_browser_headers(),
    )
    assert pending_summary.status_code == 409
    assert pending_summary.json()["error_code"] == "CLOUD_PAPER_NOT_READY"
    assert pending_summary.json()["bundle"]["processing_status"] == "pending"
    _assert_cloud_public_payload_is_redacted(pending_summary.json())

    pending_derived = client.get(
        f"/api/cloud/papers/{upload_payload['paper_id']}/derived-artifacts",
        headers=_browser_headers(),
    )
    assert pending_derived.status_code == 409
    assert pending_derived.json()["error_code"] == "CLOUD_PAPER_NOT_READY"
    assert pending_derived.json()["bundle"]["processing_status"] == "pending"
    _assert_cloud_public_payload_is_redacted(pending_derived.json())

    pending_downstream = client.get(
        f"/api/cloud/papers/{upload_payload['paper_id']}/downstream-adapter",
        headers=_browser_headers(),
    )
    assert pending_downstream.status_code == 409
    assert pending_downstream.json()["error_code"] == "CLOUD_PAPER_NOT_READY"
    _assert_cloud_public_payload_is_redacted(pending_downstream.json())

    pending_ocr = client.get(
        f"/api/cloud/papers/{upload_payload['paper_id']}/ocr",
        headers=_browser_headers(),
    )
    assert pending_ocr.status_code == 409
    assert pending_ocr.json()["error_code"] == "CLOUD_PAPER_NOT_READY"
    _assert_cloud_public_payload_is_redacted(pending_ocr.json())

    source_upload = client.post(
        f"/api/cloud/papers/{upload_payload['paper_id']}/source-pdf",
        files={"source_pdf": ("example.pdf", pdf_bytes, "application/pdf")},
        headers=_browser_headers(),
    )
    assert source_upload.status_code == 200

    completed = client.post(
        f"/api/cloud/papers/{upload_payload['paper_id']}/complete-upload",
        json={"source_pdf_sha256": source_pdf_sha256},
        headers=_browser_headers(),
    )
    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["paper_id"] == upload_payload["paper_id"]
    assert completed_payload["processing_status"] == "ready"
    assert completed_payload["allowed_actions"] == ["read_page"]
    _assert_cloud_public_payload_is_redacted(completed_payload)


def test_cloud_upload_lifecycle_uses_firestore_metadata_store_when_configured(monkeypatch) -> None:
    _patch_fake_firestore(monkeypatch)
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_METADATA_STORE", "firestore")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION", "cloud_papers_demo")
    client = TestClient(api_main.app)
    pdf_bytes = _real_pdf_bytes()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    upload = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": source_pdf_sha256,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )

    assert upload.status_code == 200
    paper_id = upload.json()["paper_id"]
    collection = _FakeFirestoreClient.collections_by_name["cloud_papers_demo"]
    assert collection.documents[paper_id]["upload_status"] == "intent_created"
    assert _FakeFirestoreClient.instances[0].project == "paperpipe-dev"

    reset_mock_cloud_paper_state()
    pending = client.get(f"/api/cloud/papers/{paper_id}", headers=_browser_headers())
    assert pending.status_code == 200
    assert pending.json()["processing_status"] == "pending"

    source_upload = client.post(
        f"/api/cloud/papers/{paper_id}/source-pdf",
        files={"source_pdf": ("example.pdf", pdf_bytes, "application/pdf")},
        headers=_browser_headers(),
    )
    assert source_upload.status_code == 200

    completed = client.post(
        f"/api/cloud/papers/{paper_id}/complete-upload",
        json={"source_pdf_sha256": source_pdf_sha256},
        headers=_browser_headers(),
    )

    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["processing_status"] == "ready"
    assert collection.documents[paper_id]["upload_status"] == "ready"
    assert collection.documents[paper_id]["processing_status"] == "ready"

    page = client.get(f"/api/cloud/papers/{paper_id}/page", headers=_browser_headers())
    assert page.status_code == 200
    assert page.json()["paper_id"] == paper_id
    _assert_cloud_public_payload_is_redacted(completed_payload)
    _assert_cloud_public_payload_is_redacted(page.json())


def test_cloud_downstream_registry_uses_firestore_store_when_configured(monkeypatch) -> None:
    _patch_fake_firestore(monkeypatch)
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE", "firestore")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION", "cloud_downstream_registry_demo")
    client = TestClient(api_main.app)

    registration = client.post(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/register",
        json={"lanes": ["meeting_pack", "obsidian_export"]},
        headers=_maintainer_hydrate_headers(),
    )

    assert registration.status_code == 200
    registration_payload = registration.json()
    assert registration_payload["review_status"] == "review_pending"
    collection = _FakeFirestoreClient.collections_by_name["cloud_downstream_registry_demo"]
    assert collection.documents
    stored_payload = next(iter(collection.documents.values()))
    assert stored_payload["paper_id"] == "paper_mock_ready"
    assert stored_payload["review_status"] == "review_pending"
    assert stored_payload["canonical_status"] == "derived_noncanonical"
    assert _FakeFirestoreClient.instances[0].project == "paperpipe-dev"

    reset_mock_cloud_paper_state()
    registry = client.get(
        "/api/cloud/papers/paper_mock_ready/downstream-artifacts/registry",
        headers=_browser_headers(),
    )

    assert registry.status_code == 200
    registry_payload = registry.json()
    assert registry_payload["registry_status"] == "available"
    assert registry_payload["registrations"] == [registration_payload]
    _assert_cloud_public_payload_is_redacted(registry_payload)


def test_cloud_gcs_backend_mediated_source_pdf_upload_writes_raw_object(monkeypatch, tmp_path) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)
    client = TestClient(api_main.app)
    pdf_bytes = _real_pdf_bytes()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    expected_paper_id = f"cloudpdf_lab_001_{source_pdf_sha256[:12]}"

    upload_intent = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": source_pdf_sha256,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )
    assert upload_intent.status_code == 200
    upload_intent_payload = upload_intent.json()
    assert upload_intent_payload["upload_mode"] == "backend_mediated"
    assert upload_intent_payload["paper_id"] == expected_paper_id
    assert not upload_intent_payload["paper_id"].startswith("paper_mock_")
    _assert_cloud_public_payload_is_redacted(upload_intent_payload)

    source_upload = client.post(
        f"/api/cloud/papers/{upload_intent_payload['paper_id']}/source-pdf",
        files={"source_pdf": ("example.pdf", pdf_bytes, "application/pdf")},
        headers=_browser_headers(),
    )

    assert source_upload.status_code == 200
    source_payload = source_upload.json()
    assert source_payload["paper_id"] == upload_intent_payload["paper_id"]
    assert source_payload["upload_status"] == "upload_received"
    assert source_payload["source_pdf_sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert source_payload["source_pdf_size_bytes"] == len(pdf_bytes)
    _assert_cloud_public_payload_is_redacted(source_payload)

    client_instance = _FakeStorageClient.instances[0]
    blob = client_instance.buckets["paperpipe-raw-dev"].blobs[
        f"lab_001/{upload_intent_payload['paper_id']}/source.pdf"
    ]
    assert blob.uploads == [{"data": pdf_bytes, "content_type": "application/pdf"}]
    assert blob.metadata == {
        "paper_id": upload_intent_payload["paper_id"],
        "lab_id": "lab_001",
        "source_pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
    }

    completed = client.post(
        f"/api/cloud/papers/{upload_intent_payload['paper_id']}/complete-upload",
        json={"source_pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest()},
        headers=_browser_headers(),
    )

    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["processing_status"] == "ready"
    assert completed_payload["provenance_summary"]["uploaded_by"] == "backend_upload"
    assert completed_payload["provenance_summary"]["processor_name"] == "paperpipe-real-cloud-page-worker"
    _assert_cloud_public_payload_is_redacted(completed_payload)

    page = client.get(
        f"/api/cloud/papers/{upload_intent_payload['paper_id']}/page",
        headers=_browser_headers(),
    )

    assert page.status_code == 200
    page_payload = page.json()
    assert page_payload["paper_id"] == upload_intent_payload["paper_id"]
    extracted_text = "\n".join(block["text"] for block in page_payload["blocks"])
    assert "Real Cloud Upload Title" in extracted_text
    assert "This abstract proves the cloud page processor used actual PDF text extraction." in extracted_text
    assert "hippocampal signal" in extracted_text
    _assert_cloud_public_payload_is_redacted(page_payload)

    page_blob = _FakeStorageClient.buckets_by_name["paperpipe-page-dev"].blobs[
        f"lab_001/{upload_intent_payload['paper_id']}/run_{upload_intent_payload['paper_id']}/page.json"
    ]
    assert page_blob.uploads[0]["content_type"] == "application/json"
    assert page_blob.metadata["paper_id"] == upload_intent_payload["paper_id"]

    derived = client.get(
        f"/api/cloud/papers/{upload_intent_payload['paper_id']}/derived-artifacts",
        headers=_browser_headers(),
    )

    assert derived.status_code == 200
    derived_payload = derived.json()
    assert derived_payload["paper_id"] == upload_intent_payload["paper_id"]
    assert derived_payload["ocr_blocks"][0]["source"]["source_pdf_sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert derived_payload["tables"][0]["table_id"] == "table_001"
    _assert_cloud_public_payload_is_redacted(derived_payload)

    derived_blob = _FakeStorageClient.buckets_by_name["paperpipe-page-dev"].blobs[
        f"lab_001/{upload_intent_payload['paper_id']}/run_{upload_intent_payload['paper_id']}/derived.json"
    ]
    assert derived_blob.uploads[0]["content_type"] == "application/json"
    assert derived_blob.metadata["paper_id"] == upload_intent_payload["paper_id"]
    assert derived_blob.metadata["derived_artifact_sha256"]

    hydrated = client.post(
        f"/api/cloud/papers/{upload_intent_payload['paper_id']}/hydrate-local",
        headers=_maintainer_hydrate_headers(),
    )

    assert hydrated.status_code == 200
    hydration_payload = hydrated.json()
    assert hydration_payload["status"] == "hydrated"
    assert hydration_payload["device_id"] is None
    assert hydration_payload["local_bundle_ref"] is None
    assert hydration_payload["source_pdf_sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    _assert_cloud_public_payload_is_redacted(hydration_payload)

    manifest_paths = list((tmp_path / "artifacts").glob("*/run_*/cloud_hydration_manifest.json"))
    assert len(manifest_paths) == 1
    run_dir = manifest_paths[0].parent
    assert (run_dir / "source" / "source.pdf").read_bytes() == pdf_bytes
    page_payload = json.loads((run_dir / "page" / "page.json").read_text(encoding="utf-8"))
    assert page_payload["paper_id"] == upload_intent_payload["paper_id"]
    manifest_payload = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
    assert manifest_payload["source_pdf_relative_path"] == "source/source.pdf"
    assert manifest_payload["page_artifact_relative_path"] == "page/page.json"


def test_cloud_mock_upload_completion_extracts_real_pdf_page_text() -> None:
    client = TestClient(api_main.app)
    pdf_bytes = _real_pdf_bytes()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    upload_intent = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "real-cloud-upload.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": source_pdf_sha256,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )

    assert upload_intent.status_code == 200
    paper_id = upload_intent.json()["paper_id"]

    source_upload = client.post(
        f"/api/cloud/papers/{paper_id}/source-pdf",
        files={"source_pdf": ("real-cloud-upload.pdf", pdf_bytes, "application/pdf")},
        headers=_browser_headers(),
    )
    assert source_upload.status_code == 200

    completed = client.post(
        f"/api/cloud/papers/{paper_id}/complete-upload",
        json={"source_pdf_sha256": source_pdf_sha256},
        headers=_browser_headers(),
    )
    assert completed.status_code == 200
    assert completed.json()["processing_status"] == "ready"

    page = client.get(f"/api/cloud/papers/{paper_id}/page", headers=_browser_headers())
    assert page.status_code == 200
    page_payload = page.json()
    extracted_text = "\n".join(block["text"] for block in page_payload["blocks"])
    sections = {block["metadata"].get("section") for block in page_payload["blocks"]}
    assert "Real Cloud Upload Title" in extracted_text
    assert "This abstract proves the cloud page processor used actual PDF text extraction." in extracted_text
    assert "hippocampal signal" in extracted_text
    assert {"title", "abstract", "body"}.issubset(sections)
    assert "Mock processed page text" not in extracted_text
    _assert_cloud_public_payload_is_redacted(page_payload)


def test_cloud_beta_access_blocks_cross_lab_read(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    response = client.get(
        "/api/cloud/papers/paper_mock_ready",
        headers={
            **_browser_headers(),
            "x-paperpipe-actor-id": "user_cross_lab",
            "x-paperpipe-lab-id": "lab_other",
            "x-paperpipe-role": "lab_admin",
            "x-paperpipe-device-registered": "true",
            "x-paperpipe-download-allowed": "true",
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "CLOUD_PAPER_FORBIDDEN"
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_beta_access_blocks_hydrate_without_download_permission(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)
    pdf_bytes = _real_pdf_bytes()
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    upload = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": sha,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )
    paper_id = upload.json()["paper_id"]
    client.post(
        f"/api/cloud/papers/{paper_id}/source-pdf",
        files={"source_pdf": ("example.pdf", pdf_bytes, "application/pdf")},
        headers=_browser_headers(),
    )
    client.post(
        f"/api/cloud/papers/{paper_id}/complete-upload",
        json={"source_pdf_sha256": sha},
        headers=_browser_headers(),
    )

    hydrated = client.post(
        f"/api/cloud/papers/{paper_id}/hydrate-local",
        headers={
            **_browser_headers(),
            "x-paperpipe-actor-id": "user_reader",
            "x-paperpipe-lab-id": "lab_001",
            "x-paperpipe-role": "reader",
            "x-paperpipe-device-registered": "true",
            "x-paperpipe-download-allowed": "false",
        },
    )

    assert hydrated.status_code == 403
    payload = hydrated.json()
    assert payload["error_code"] == "CLOUD_PAPER_FORBIDDEN"
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_beta_read_page_and_hydrate_actions_are_audited(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        pdf_bytes = _real_pdf_bytes()
        sha = hashlib.sha256(pdf_bytes).hexdigest()

        upload = client.post(
            "/api/cloud/papers/upload-intents",
            json={
                "filename": "example.pdf",
                "content_type": "application/pdf",
                "source_pdf_sha256": sha,
                "lab_id": "lab_001",
            },
            headers=_browser_headers(),
        )
        paper_id = upload.json()["paper_id"]
        client.post(
            f"/api/cloud/papers/{paper_id}/source-pdf",
            files={"source_pdf": ("example.pdf", pdf_bytes, "application/pdf")},
            headers=_browser_headers(),
        )
        client.post(
            f"/api/cloud/papers/{paper_id}/complete-upload",
            json={"source_pdf_sha256": sha},
            headers=_browser_headers(),
        )

        status = client.get(f"/api/cloud/papers/{paper_id}", headers=_maintainer_hydrate_headers())
        page = client.get(f"/api/cloud/papers/{paper_id}/page", headers=_maintainer_hydrate_headers())
        hydrated = client.post(f"/api/cloud/papers/{paper_id}/hydrate-local", headers=_maintainer_hydrate_headers())
        status_after_hydrate = client.get(f"/api/cloud/papers/{paper_id}", headers=_maintainer_hydrate_headers())

        assert status.status_code == 200
        assert page.status_code == 200
        assert hydrated.status_code == 200
        assert status_after_hydrate.status_code == 200
        assert status_after_hydrate.json()["local_hydration"]["status"] == "hydrated"
        _assert_cloud_public_payload_is_redacted(status_after_hydrate.json())
        actions = list_user_actions(paper_id=paper_id, source="cloud_papers", limit=10)
        action_types = {action["action_type"] for action in actions}
        assert {
            "cloud_paper_status_read",
            "cloud_paper_page_read",
            "cloud_paper_hydrate_download",
        }.issubset(action_types)
        assert "gs://" not in str(actions)
        assert "/Users/" not in str(actions)
    finally:
        db_utils.DB_PATH = original_db_path


def test_cloud_gcs_upload_completion_blocks_missing_source_object(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)
    client = TestClient(api_main.app)

    upload_intent = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": "b" * 64,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )

    completed = client.post(
        f"/api/cloud/papers/{upload_intent.json()['paper_id']}/complete-upload",
        json={"source_pdf_sha256": "b" * 64},
        headers=_browser_headers(),
    )

    assert completed.status_code == 409
    payload = completed.json()
    assert payload["error_code"] == "CLOUD_PAPER_BLOCKED"
    assert payload["bundle"]["processing_status"] == "blocked"
    assert payload["bundle"]["warnings"][0]["code"] == "SOURCE_PDF_MISSING"
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_gcs_source_pdf_upload_blocks_checksum_mismatch_before_storage_write(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)
    client = TestClient(api_main.app)

    upload_intent = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": "b" * 64,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )

    source_upload = client.post(
        f"/api/cloud/papers/{upload_intent.json()['paper_id']}/source-pdf",
        files={"source_pdf": ("example.pdf", b"%PDF-1.4\nwrong", "application/pdf")},
        headers=_browser_headers(),
    )

    assert source_upload.status_code == 409
    payload = source_upload.json()
    assert payload["error_code"] == "CLOUD_PAPER_BLOCKED"
    assert payload["bundle"]["processing_status"] == "blocked"
    assert _FakeStorageClient.instances == []
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_upload_intent_storage_unavailable_is_public_contract(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.delenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", raising=False)
    monkeypatch.delenv("LATTICE_GCS_RAW_PDF_BUCKET", raising=False)
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    client = TestClient(api_main.app)

    response = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": "b" * 64,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload == {
        "error_code": "CLOUD_PAPER_STORAGE_UNAVAILABLE",
        "message": "Missing GCS cloud paper config: PAPERPIPE_GCS_RAW_PDF_BUCKET",
        "bundle": None,
    }
    _assert_cloud_public_payload_is_redacted(payload)

    orphan = client.get("/api/cloud/papers/paper_mock_000001", headers=_browser_headers())
    assert orphan.status_code == 404


def test_cloud_upload_intent_openapi_declares_storage_unavailable_response() -> None:
    client = TestClient(api_main.app)

    paths = client.get("/openapi.json").json()["paths"]
    responses = paths["/cloud/papers/upload-intents"]["post"]["responses"]

    assert "503" in responses
    assert (
        responses["503"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/CloudPaperOperationErrorResponse"
    )

    complete_responses = paths["/cloud/papers/{paper_id}/complete-upload"]["post"]["responses"]
    assert "503" in complete_responses
    assert (
        complete_responses["503"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/CloudPaperOperationErrorResponse"
    )


def test_cloud_upload_completion_blocks_checksum_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    response = client.post(
        "/api/cloud/papers/paper_mock_ready/complete-upload",
        json={"source_pdf_sha256": "c" * 64},
        headers=_browser_headers(),
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error_code"] == "CLOUD_PAPER_BLOCKED"
    assert payload["bundle"]["processing_status"] == "blocked"
    assert payload["bundle"]["warnings"][0]["code"] == "CHECKSUM_MISMATCH"
    _assert_cloud_public_payload_is_redacted(payload)

    status = client.get("/api/cloud/papers/paper_mock_ready", headers=_browser_headers())
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["processing_status"] == "blocked"
    assert status_payload["warnings"][0]["code"] == "CHECKSUM_MISMATCH"
    _assert_cloud_public_payload_is_redacted(status_payload)


def test_cloud_upload_completion_is_idempotent_after_ready(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)
    pdf_bytes = _real_pdf_bytes()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    upload = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "example.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": source_pdf_sha256,
            "lab_id": "lab_001",
        },
        headers=_browser_headers(),
    )
    paper_id = upload.json()["paper_id"]
    source_upload = client.post(
        f"/api/cloud/papers/{paper_id}/source-pdf",
        files={"source_pdf": ("example.pdf", pdf_bytes, "application/pdf")},
        headers=_browser_headers(),
    )
    assert source_upload.status_code == 200

    first = client.post(
        f"/api/cloud/papers/{paper_id}/complete-upload",
        json={"source_pdf_sha256": source_pdf_sha256},
        headers=_browser_headers(),
    )
    second = client.post(
        f"/api/cloud/papers/{paper_id}/complete-upload",
        json={"source_pdf_sha256": source_pdf_sha256},
        headers=_browser_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["processing_status"] == "ready"
    assert second.json()["processing_status"] == "ready"
    assert second.json()["warnings"] == []
    _assert_cloud_public_payload_is_redacted(second.json())


def test_cloud_unknown_paper_returns_not_found(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    status = client.get("/api/cloud/papers/paper_mock_missing", headers=_browser_headers())
    assert status.status_code == 404
    assert status.json()["detail"] == "Cloud paper not found"

    page = client.get("/api/cloud/papers/paper_mock_missing/page", headers=_browser_headers())
    assert page.status_code == 404
    assert page.json()["detail"] == "Cloud paper not found"


def test_cloud_upload_intents_do_not_alias_same_checksum_across_labs(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)
    payload = {
        "filename": "same.pdf",
        "content_type": "application/pdf",
        "source_pdf_sha256": "d" * 64,
    }

    first = client.post(
        "/api/cloud/papers/upload-intents",
        json={**payload, "lab_id": "lab_alpha"},
        headers=_browser_headers(),
    )
    second = client.post(
        "/api/cloud/papers/upload-intents",
        json={**payload, "lab_id": "lab_beta"},
        headers=_browser_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["paper_id"] != second_payload["paper_id"]

    first_status = client.get(f"/api/cloud/papers/{first_payload['paper_id']}", headers=_browser_headers())
    second_status = client.get(f"/api/cloud/papers/{second_payload['paper_id']}", headers=_browser_headers())
    assert first_status.json()["lab_id"] == "lab_alpha"
    assert second_status.json()["lab_id"] == "lab_beta"


def test_cloud_gcs_upload_intents_use_real_cloud_ids_and_lab_namespace(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)
    client = TestClient(api_main.app)
    payload = {
        "filename": "same.pdf",
        "content_type": "application/pdf",
        "source_pdf_sha256": "d" * 64,
    }

    first = client.post(
        "/api/cloud/papers/upload-intents",
        json={**payload, "lab_id": "lab_alpha"},
        headers=_browser_headers(),
    )
    second = client.post(
        "/api/cloud/papers/upload-intents",
        json={**payload, "lab_id": "lab_beta"},
        headers=_browser_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["paper_id"] == "cloudpdf_lab_alpha_dddddddddddd"
    assert second_payload["paper_id"] == "cloudpdf_lab_beta_dddddddddddd"
    assert first_payload["upload_intent_id"] == "upl_gcs_lab_alpha_dddddddddddd"
    assert second_payload["upload_intent_id"] == "upl_gcs_lab_beta_dddddddddddd"


def test_cloud_gcs_mode_hides_mock_fixture_papers(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)
    client = TestClient(api_main.app)

    listed = client.get("/api/cloud/papers", headers=_browser_headers())
    status = client.get("/api/cloud/papers/paper_mock_ready", headers=_browser_headers())

    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert status.status_code == 404


def test_submission_demo_bundle_serves_real_snapshot_without_gcp_auth(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    paper_id = "cloudpdf_lab_001_fe476330a3bd"
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_SUBMISSION_DEMO_BUNDLE", "1")
    monkeypatch.setenv("PAPERPIPE_SUBMISSION_DEMO_BUNDLE_DIR", str(repo_root / "packaging" / "submission_demo"))
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "mock")
    monkeypatch.setenv("PAPERPIPE_CLOUD_METADATA_STORE", "memory")
    client = TestClient(api_main.app)

    preflight = client.get("/api/cloud/papers/auth-preflight", headers=_browser_headers())
    listed = client.get("/api/cloud/papers", headers=_browser_headers())
    search = client.get("/api/cloud/papers/search?q=amyloid", headers=_browser_headers())
    page = client.get(f"/api/cloud/papers/{paper_id}/page", headers=_browser_headers())
    derived = client.get(f"/api/cloud/papers/{paper_id}/derived-artifacts", headers=_browser_headers())
    fixture = client.get("/api/cloud/papers/paper_mock_ready", headers=_browser_headers())

    assert preflight.status_code == 200
    assert preflight.json()["status"] == "submission_bundle"
    assert preflight.json()["credential_source"] == "not_required"
    assert preflight.json()["setup_commands"] == []
    assert listed.status_code == 200
    assert [item["paper_id"] for item in listed.json()["items"]] == [paper_id]
    assert search.status_code == 200
    assert search.json()["items"][0]["bundle"]["paper_id"] == paper_id
    assert page.status_code == 200
    assert "Blood phosphorylated tau 181" in page.json()["blocks"][0]["text"]
    assert "More than 50 million people worldwide" in page.json()["blocks"][2]["text"]
    assert derived.status_code == 200
    assert derived.json()["paper_id"] == paper_id
    assert fixture.status_code == 404
    _assert_cloud_public_payload_is_redacted(preflight.json())
    _assert_cloud_public_payload_is_redacted(listed.json())
    _assert_cloud_public_payload_is_redacted(search.json())
    _assert_cloud_public_payload_is_redacted(page.json())
    _assert_cloud_public_payload_is_redacted(derived.json())


def test_cloud_auth_preflight_ready_when_adc_and_gcp_access_are_available(monkeypatch) -> None:
    _patch_fake_gcp(monkeypatch)
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_CLOUD_METADATA_STORE", "firestore")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setenv("PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION", "cloud_papers_demo")
    client = TestClient(api_main.app)

    response = client.get("/api/cloud/papers/auth-preflight", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "cloud_paper_auth_preflight.v1"
    assert payload["status"] == "ready"
    assert payload["adapter"] == "gcs"
    assert payload["project_id"] == "paperpipe-dev"
    assert payload["firestore_collection"] == "cloud_papers_demo"
    assert payload["credential_source"] == "application_default_credentials"
    assert {check["check_id"]: check["status"] for check in payload["checks"]} == {
        "application_default_credentials": "ok",
        "raw_pdf_bucket": "ok",
        "page_artifact_bucket": "ok",
        "firestore_collection": "ok",
    }
    assert payload["setup_commands"] == [
        "gcloud auth application-default login",
        "gcloud config set project paperpipe-dev",
    ]
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_auth_preflight_guides_application_default_login_when_adc_missing(monkeypatch) -> None:
    _patch_fake_gcp(monkeypatch)
    _FakeAuthModule.default_exception = _FakeDefaultCredentialsError(
        "Could not automatically determine credentials."
    )
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_CLOUD_METADATA_STORE", "firestore")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setenv("PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION", "cloud_papers_demo")
    client = TestClient(api_main.app)

    response = client.get("/api/cloud/papers/auth-preflight", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "auth_missing"
    assert payload["next_action_label"] == "Sign in with Application Default Credentials on this computer."
    assert payload["checks"][0]["check_id"] == "application_default_credentials"
    assert payload["checks"][0]["status"] == "error"
    assert "Application Default Credentials" in payload["checks"][0]["message"]
    assert payload["setup_commands"] == [
        "gcloud auth application-default login",
        "gcloud config set project paperpipe-dev",
    ]
    _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_mock_status_fixtures_cover_non_ready_states(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    for paper_id, expected_status in (
        ("paper_mock_pending", "pending"),
        ("paper_mock_running", "running"),
        ("paper_mock_failed", "failed"),
        ("paper_mock_blocked", "blocked"),
    ):
        response = client.get(f"/api/cloud/papers/{paper_id}", headers=_browser_headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["processing_status"] == expected_status
        assert payload["allowed_actions"] == []
        _assert_cloud_public_payload_is_redacted(payload)


def test_cloud_root_route_accepts_valid_api_key_and_cross_origin_write_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    client = TestClient(api_main.app)

    direct = client.get("/cloud/papers/paper_mock_ready", headers={"X-API-Key": "secret-key"})
    assert direct.status_code == 200
    assert direct.json()["paper_id"] == "paper_mock_ready"

    blocked = client.post(
        "/api/cloud/papers/upload-intents",
        json={
            "filename": "evil.pdf",
            "content_type": "application/pdf",
            "source_pdf_sha256": "e" * 64,
            "lab_id": "lab_001",
        },
        headers={"origin": "https://evil.example"},
    )
    assert blocked.status_code == 403
