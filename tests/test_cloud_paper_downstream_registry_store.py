from __future__ import annotations

import importlib

import pytest

from src.schemas.cloud_paper import CloudPaperDownstreamArtifactRegistrationRequest
from src.services.cloud_paper_downstream import (
    build_cloud_paper_downstream_adapter_response,
    build_cloud_paper_downstream_promotion_plan,
    build_cloud_paper_downstream_promotion_readiness,
    register_cloud_paper_downstream_artifacts,
)
from src.services.cloud_paper_downstream_registry import (
    CloudPaperDownstreamRegistryConfigError,
    CloudPaperDownstreamRegistryArtifactNotFoundError,
    CloudPaperFirestoreDownstreamRegistryStore,
    InMemoryCloudPaperDownstreamRegistryStore,
    resolve_cloud_paper_downstream_registry_config,
)
from src.services.cloud_paper_fake import get_mock_cloud_derived_artifacts


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


def _sample_registration():
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    adapter = build_cloud_paper_downstream_adapter_response(derived)
    registration = register_cloud_paper_downstream_artifacts(
        adapter,
        CloudPaperDownstreamArtifactRegistrationRequest(lanes=["meeting_pack", "obsidian_export"]),
    )
    return adapter, registration


def test_downstream_registry_config_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE", raising=False)

    config = resolve_cloud_paper_downstream_registry_config()

    assert config.store == "memory"
    assert config.firestore_collection == "cloud_paper_downstream_registry"


def test_in_memory_downstream_registry_round_trips_review_pending_registration() -> None:
    adapter, registration = _sample_registration()
    store = InMemoryCloudPaperDownstreamRegistryStore()

    stored = store.store_registration(registration)
    registry = store.get_registry(adapter)

    assert stored == registration
    assert registry.registry_status == "available"
    assert registry.review_status == "review_pending"
    assert registry.canonical_status == "derived_noncanonical"
    assert registry.registrations == [registration]

    stored_again = store.store_registration(registration)
    assert stored_again == registration
    assert store.get_registry(adapter).registrations == [registration]


def test_in_memory_downstream_registry_reviews_registered_artifact() -> None:
    adapter, registration = _sample_registration()
    store = InMemoryCloudPaperDownstreamRegistryStore()
    store.store_registration(registration)
    artifact_id = registration.registered_artifacts[0].artifact_id

    reviewed = store.review_artifact(
        adapter,
        artifact_id=artifact_id,
        review_status="review_approved",
        reviewer_role="maintainer",
        reviewer_note_recorded=True,
    )

    reviewed_artifact = next(
        artifact
        for stored_registration in reviewed.registrations
        for artifact in stored_registration.registered_artifacts
        if artifact.artifact_id == artifact_id
    )
    assert reviewed.registry_status == "available"
    assert reviewed.review_status == "review_pending"
    assert reviewed_artifact.review_status == "review_approved"
    assert reviewed_artifact.review_events[-1].review_status == "review_approved"
    assert reviewed_artifact.review_events[-1].reviewer_role == "maintainer"
    assert reviewed_artifact.review_events[-1].reviewer_note_recorded is True
    assert store.get_registry(adapter).registrations == reviewed.registrations

    with pytest.raises(CloudPaperDownstreamRegistryArtifactNotFoundError):
        store.review_artifact(
            adapter,
            artifact_id="missing_artifact",
            review_status="review_rejected",
            reviewer_role="maintainer",
        )


def test_downstream_promotion_readiness_blocks_until_all_artifacts_are_approved() -> None:
    adapter, registration = _sample_registration()
    store = InMemoryCloudPaperDownstreamRegistryStore()

    empty_readiness = build_cloud_paper_downstream_promotion_readiness(store.get_registry(adapter))
    assert empty_readiness.promotion_status == "blocked"
    assert empty_readiness.eligible is False
    assert empty_readiness.blockers[0].code == "registry_empty"

    store.store_registration(registration)
    pending_readiness = build_cloud_paper_downstream_promotion_readiness(store.get_registry(adapter))
    assert pending_readiness.promotion_status == "blocked"
    assert pending_readiness.pending_artifact_count == len(registration.registered_artifacts)
    assert {blocker.code for blocker in pending_readiness.blockers} == {"review_pending"}

    for artifact in registration.registered_artifacts:
        store.review_artifact(
            adapter,
            artifact_id=artifact.artifact_id,
            review_status="review_approved",
            reviewer_role="maintainer",
        )

    ready = build_cloud_paper_downstream_promotion_readiness(store.get_registry(adapter))
    assert ready.promotion_status == "eligible"
    assert ready.eligible is True
    assert ready.approved_artifact_count == ready.total_artifact_count
    assert ready.blockers == []


def test_downstream_promotion_plan_is_read_only_and_blocks_partial_reviews() -> None:
    adapter, registration = _sample_registration()
    store = InMemoryCloudPaperDownstreamRegistryStore()
    store.store_registration(registration)

    blocked_plan = build_cloud_paper_downstream_promotion_plan(store.get_registry(adapter))
    assert blocked_plan.schema_version == "cloud_paper_downstream_promotion_plan.v1"
    assert blocked_plan.plan_status == "blocked"
    assert blocked_plan.dry_run is True
    assert blocked_plan.mutation_applied is False
    assert blocked_plan.canonical_status == "derived_noncanonical"
    assert blocked_plan.promotion_items == []
    assert {blocker.code for blocker in blocked_plan.blockers} == {"review_pending"}

    for artifact in registration.registered_artifacts:
        store.review_artifact(
            adapter,
            artifact_id=artifact.artifact_id,
            review_status="review_approved",
            reviewer_role="maintainer",
        )

    ready_plan = build_cloud_paper_downstream_promotion_plan(store.get_registry(adapter))
    assert ready_plan.plan_status == "ready"
    assert ready_plan.dry_run is True
    assert ready_plan.mutation_applied is False
    assert ready_plan.promotion_target == "canonical_structured_state"
    assert ready_plan.blockers == []
    assert len(ready_plan.promotion_items) == len(registration.registered_artifacts)
    assert {item.review_status for item in ready_plan.promotion_items} == {"review_approved"}
    assert {item.canonical_status for item in ready_plan.promotion_items} == {"derived_noncanonical"}
    assert {item.promotion_action for item in ready_plan.promotion_items} == {
        "prepare_canonical_state_promotion"
    }


def test_firestore_downstream_registry_round_trips_registration(monkeypatch) -> None:
    _patch_fake_firestore(monkeypatch)
    adapter, registration = _sample_registration()
    store = CloudPaperFirestoreDownstreamRegistryStore(
        project_id="knudc-a01068202087",
        collection_name="cloud_downstream_registry_demo",
        allow_clear=True,
    )

    stored = store.store_registration(registration)
    registry = store.get_registry(adapter)

    assert _FakeFirestoreClient.instances[0].project == "knudc-a01068202087"
    assert stored == registration
    assert registry.registry_status == "available"
    assert registry.registrations == [registration]
    assert _FakeFirestoreClient.collections_by_name["cloud_downstream_registry_demo"].documents


def test_firestore_downstream_registry_reviews_registered_artifact(monkeypatch) -> None:
    _patch_fake_firestore(monkeypatch)
    adapter, registration = _sample_registration()
    store = CloudPaperFirestoreDownstreamRegistryStore(
        project_id="knudc-a01068202087",
        collection_name="cloud_downstream_registry_demo",
        allow_clear=True,
    )
    store.store_registration(registration)
    artifact_id = registration.registered_artifacts[0].artifact_id

    reviewed = store.review_artifact(
        adapter,
        artifact_id=artifact_id,
        review_status="review_rejected",
        reviewer_role="reviewer",
    )

    reviewed_artifact = next(
        artifact
        for stored_registration in reviewed.registrations
        for artifact in stored_registration.registered_artifacts
        if artifact.artifact_id == artifact_id
    )
    assert reviewed.review_status == "review_pending"
    assert reviewed_artifact.review_status == "review_rejected"
    assert reviewed_artifact.review_events[-1].review_status == "review_rejected"
    assert reviewed_artifact.review_events[-1].reviewer_role == "reviewer"
    assert reviewed_artifact.review_events[-1].reviewer_note_recorded is False
    assert store.get_registry(adapter).registrations == reviewed.registrations


def test_firestore_downstream_registry_fails_closed_without_dependency(monkeypatch) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "google.cloud.firestore":
            raise ImportError("missing firestore")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(CloudPaperDownstreamRegistryConfigError, match="google-cloud-firestore"):
        CloudPaperFirestoreDownstreamRegistryStore(
            project_id="knudc-a01068202087",
            collection_name="cloud_downstream_registry_demo",
        )
