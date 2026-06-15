from __future__ import annotations

import importlib

import pytest

from src.schemas.cloud_paper import (
    CloudPaperMetadataRecord,
    CloudPaperUploadIntentRequest,
    CloudPaperWarning,
)
from src.services.cloud_paper_metadata import (
    CloudPaperFirestoreMetadataStore,
    CloudPaperMetadataConfigError,
    InMemoryCloudPaperMetadataStore,
    resolve_cloud_paper_metadata_config,
)


def _sample_request() -> CloudPaperUploadIntentRequest:
    return CloudPaperUploadIntentRequest(
        filename="paper.pdf",
        content_type="application/pdf",
        source_pdf_sha256="f" * 64,
        lab_id="lab_001",
    )


def test_metadata_store_creates_intent_record_with_pending_lifecycle() -> None:
    store = InMemoryCloudPaperMetadataStore()

    record = store.create_upload_intent_record(
        paper_id="paper_mock_000001",
        upload_intent_id="upl_mock_000001",
        request=_sample_request(),
    )

    assert isinstance(record, CloudPaperMetadataRecord)
    assert record.paper_id == "paper_mock_000001"
    assert record.upload_intent_id == "upl_mock_000001"
    assert record.upload_status == "intent_created"
    assert record.processing_status == "pending"
    assert record.warnings == []
    assert store.get("paper_mock_000001") == record


def test_metadata_store_marks_upload_ready_after_checksum_match() -> None:
    store = InMemoryCloudPaperMetadataStore()
    store.create_upload_intent_record(
        paper_id="paper_mock_000001",
        upload_intent_id="upl_mock_000001",
        request=_sample_request(),
    )

    ready = store.mark_upload_ready("paper_mock_000001")

    assert ready.upload_status == "ready"
    assert ready.processing_status == "ready"
    assert ready.warnings == []


def test_metadata_store_marks_processing_running_and_failed() -> None:
    store = InMemoryCloudPaperMetadataStore()
    store.create_upload_intent_record(
        paper_id="paper_mock_000001",
        upload_intent_id="upl_mock_000001",
        request=_sample_request(),
    )
    store.mark_upload_received("paper_mock_000001")

    running = store.mark_processing_running("paper_mock_000001")
    failed = store.mark_processing_failed(
        "paper_mock_000001",
        warning=CloudPaperWarning(
            code="MOCK_PROCESSING_FAILED",
            message="Mock processing failed.",
            severity="high",
        ),
    )

    assert running.upload_status == "processing"
    assert running.processing_status == "running"
    assert failed.upload_status == "failed"
    assert failed.processing_status == "failed"
    assert failed.warnings[0].code == "MOCK_PROCESSING_FAILED"


def test_metadata_store_blocks_upload_with_warning() -> None:
    store = InMemoryCloudPaperMetadataStore()
    store.create_upload_intent_record(
        paper_id="paper_mock_000001",
        upload_intent_id="upl_mock_000001",
        request=_sample_request(),
    )

    blocked = store.mark_upload_blocked(
        "paper_mock_000001",
        warning=CloudPaperWarning(
            code="CHECKSUM_MISMATCH",
            message="Uploaded PDF checksum did not match the expected source checksum.",
            severity="high",
        ),
    )

    assert blocked.upload_status == "blocked"
    assert blocked.processing_status == "blocked"
    assert blocked.warnings[0].code == "CHECKSUM_MISMATCH"


def test_metadata_store_ready_transition_is_idempotent() -> None:
    store = InMemoryCloudPaperMetadataStore()
    store.create_upload_intent_record(
        paper_id="paper_mock_000001",
        upload_intent_id="upl_mock_000001",
        request=_sample_request(),
    )

    first = store.mark_upload_ready("paper_mock_000001")
    second = store.mark_upload_ready("paper_mock_000001")

    assert first == second
    assert second.upload_status == "ready"
    assert second.processing_status == "ready"


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


def _patch_fake_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeFirestoreClient.instances.clear()
    _FakeFirestoreClient.collections_by_name.clear()
    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "google.cloud.firestore":
            return _FakeFirestoreModule
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)


def test_metadata_config_defaults_to_in_memory_store(monkeypatch) -> None:
    monkeypatch.delenv("PAPERPIPE_CLOUD_METADATA_STORE", raising=False)

    config = resolve_cloud_paper_metadata_config()

    assert config.store == "memory"
    assert config.firestore_collection == "cloud_papers"


def test_firestore_metadata_store_round_trips_records(monkeypatch) -> None:
    _patch_fake_firestore(monkeypatch)
    store = CloudPaperFirestoreMetadataStore(
        project_id="knudc-a01068202087",
        collection_name="cloud_papers_demo",
        allow_clear=True,
    )

    record = store.create_upload_intent_record(
        paper_id="paper_demo_000001",
        upload_intent_id="upl_demo_000001",
        request=_sample_request(),
    )

    assert _FakeFirestoreClient.instances[0].project == "knudc-a01068202087"
    assert store.get("paper_demo_000001") == record
    assert store.list_records() == [record]

    ready = store.mark_upload_ready("paper_demo_000001")
    assert ready.upload_status == "ready"
    assert ready.processing_status == "ready"
    assert store.get("paper_demo_000001") == ready


def test_firestore_metadata_store_fails_closed_without_dependency(monkeypatch) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "google.cloud.firestore":
            raise ImportError("missing firestore")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(CloudPaperMetadataConfigError, match="google-cloud-firestore"):
        CloudPaperFirestoreMetadataStore(
            project_id="knudc-a01068202087",
            collection_name="cloud_papers_demo",
        )
