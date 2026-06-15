from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import os
from typing import Literal, Protocol

from src.schemas.cloud_paper import (
    CloudPaperDownstreamAdapterResponse,
    CloudPaperDownstreamArtifactReviewEvent,
    CloudPaperDownstreamArtifactRegistryResponse,
    CloudPaperDownstreamArtifactRegistrationResponse,
    CloudPaperDownstreamReviewStatus,
    CloudPaperRole,
)


CloudPaperDownstreamRegistryStoreMode = Literal["memory", "firestore"]


class CloudPaperDownstreamRegistryConfigError(ValueError):
    pass


class CloudPaperDownstreamRegistryArtifactNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class CloudPaperDownstreamRegistryConfig:
    store: CloudPaperDownstreamRegistryStoreMode = "memory"
    gcp_project_id: str | None = None
    firestore_collection: str = "cloud_paper_downstream_registry"


class CloudPaperDownstreamRegistryStore(Protocol):
    def clear(self) -> None:
        ...

    def store_registration(
        self,
        registration: CloudPaperDownstreamArtifactRegistrationResponse,
    ) -> CloudPaperDownstreamArtifactRegistrationResponse:
        ...

    def get_registry(
        self,
        adapter_response: CloudPaperDownstreamAdapterResponse,
    ) -> CloudPaperDownstreamArtifactRegistryResponse:
        ...

    def review_artifact(
        self,
        adapter_response: CloudPaperDownstreamAdapterResponse,
        *,
        artifact_id: str,
        review_status: CloudPaperDownstreamReviewStatus,
        reviewer_role: CloudPaperRole,
        reviewer_note_recorded: bool = False,
    ) -> CloudPaperDownstreamArtifactRegistryResponse:
        ...


def _env_value(*names: str) -> str | None:
    for name in names:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    return None


def resolve_cloud_paper_downstream_registry_config() -> CloudPaperDownstreamRegistryConfig:
    raw_store = (
        _env_value("PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE", "LATTICE_CLOUD_DOWNSTREAM_REGISTRY_STORE")
        or "memory"
    ).strip().lower()
    if raw_store == "mock":
        raw_store = "memory"
    if raw_store not in {"memory", "firestore"}:
        raise CloudPaperDownstreamRegistryConfigError(f"Unsupported downstream registry store: {raw_store}")
    collection = (
        _env_value(
            "PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION",
            "LATTICE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION",
        )
        or "cloud_paper_downstream_registry"
    )
    return CloudPaperDownstreamRegistryConfig(
        store=raw_store,  # type: ignore[arg-type]
        gcp_project_id=_env_value("PAPERPIPE_GCP_PROJECT_ID", "LATTICE_GCP_PROJECT_ID"),
        firestore_collection=collection,
    )


class InMemoryCloudPaperDownstreamRegistryStore:
    def __init__(self) -> None:
        self._registrations: dict[str, list[CloudPaperDownstreamArtifactRegistrationResponse]] = {}

    def clear(self) -> None:
        self._registrations.clear()

    def store_registration(
        self,
        registration: CloudPaperDownstreamArtifactRegistrationResponse,
    ) -> CloudPaperDownstreamArtifactRegistrationResponse:
        key = _registry_key(
            paper_id=registration.paper_id,
            run_id=registration.run_id,
            source_pdf_sha256=registration.source_pdf_sha256,
        )
        registrations = self._registrations.setdefault(key, [])
        artifact_ids = {artifact.artifact_id for artifact in registration.registered_artifacts}
        for index, existing in enumerate(registrations):
            existing_ids = {artifact.artifact_id for artifact in existing.registered_artifacts}
            if existing_ids == artifact_ids:
                registrations[index] = registration
                return registration
        registrations.append(registration)
        return registration

    def get_registry(
        self,
        adapter_response: CloudPaperDownstreamAdapterResponse,
    ) -> CloudPaperDownstreamArtifactRegistryResponse:
        registrations = list(
            self._registrations.get(
                _registry_key(
                    paper_id=adapter_response.paper_id,
                    run_id=adapter_response.run_id,
                    source_pdf_sha256=adapter_response.source_pdf_sha256,
                ),
                [],
            )
        )
        return _registry_response(adapter_response, registrations)

    def review_artifact(
        self,
        adapter_response: CloudPaperDownstreamAdapterResponse,
        *,
        artifact_id: str,
        review_status: CloudPaperDownstreamReviewStatus,
        reviewer_role: CloudPaperRole,
        reviewer_note_recorded: bool = False,
    ) -> CloudPaperDownstreamArtifactRegistryResponse:
        key = _registry_key(
            paper_id=adapter_response.paper_id,
            run_id=adapter_response.run_id,
            source_pdf_sha256=adapter_response.source_pdf_sha256,
        )
        registrations = list(self._registrations.get(key, []))
        updated_registrations, updated = _review_registrations(
            registrations,
            artifact_id=artifact_id,
            review_status=review_status,
            reviewer_role=reviewer_role,
            reviewer_note_recorded=reviewer_note_recorded,
        )
        if not updated:
            raise CloudPaperDownstreamRegistryArtifactNotFoundError("Downstream artifact review target not found.")
        self._registrations[key] = updated_registrations
        return _registry_response(adapter_response, updated_registrations)


class CloudPaperFirestoreDownstreamRegistryStore:
    def __init__(
        self,
        *,
        project_id: str,
        collection_name: str = "cloud_paper_downstream_registry",
        allow_clear: bool = False,
    ) -> None:
        if not project_id.strip():
            raise CloudPaperDownstreamRegistryConfigError(
                "PAPERPIPE_GCP_PROJECT_ID is required for Firestore downstream registry."
            )
        if not collection_name.strip():
            raise CloudPaperDownstreamRegistryConfigError("Firestore downstream registry collection must not be empty.")
        try:
            firestore = importlib.import_module("google.cloud.firestore")
        except ImportError as exc:
            raise CloudPaperDownstreamRegistryConfigError(
                "google-cloud-firestore is not installed; install it only when "
                "PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE=firestore is enabled."
            ) from exc
        self._collection = firestore.Client(project=project_id).collection(collection_name)
        self._allow_clear = allow_clear

    def clear(self) -> None:
        if not self._allow_clear:
            raise CloudPaperDownstreamRegistryConfigError(
                "Firestore downstream registry clear is disabled outside controlled tests."
            )
        for snapshot in self._collection.stream():
            data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
            if not data:
                continue
            document_id = str(data.get("registry_document_id") or "").strip()
            if document_id:
                self._collection.document(document_id).delete()

    def store_registration(
        self,
        registration: CloudPaperDownstreamArtifactRegistrationResponse,
    ) -> CloudPaperDownstreamArtifactRegistrationResponse:
        document_id = _registration_document_id(registration)
        payload = registration.model_dump(mode="json")
        payload["registry_document_id"] = document_id
        payload["registry_key"] = _registry_key(
            paper_id=registration.paper_id,
            run_id=registration.run_id,
            source_pdf_sha256=registration.source_pdf_sha256,
        )
        self._collection.document(document_id).set(payload)
        return registration

    def get_registry(
        self,
        adapter_response: CloudPaperDownstreamAdapterResponse,
    ) -> CloudPaperDownstreamArtifactRegistryResponse:
        prefix = _registry_key(
            paper_id=adapter_response.paper_id,
            run_id=adapter_response.run_id,
            source_pdf_sha256=adapter_response.source_pdf_sha256,
        )
        registrations = []
        for snapshot in self._collection.stream():
            data = snapshot.to_dict()
            if not data:
                continue
            data = dict(data)
            data.pop("registry_document_id", None)
            registry_key = str(data.pop("registry_key", "") or "")
            if registry_key != prefix:
                continue
            registrations.append(CloudPaperDownstreamArtifactRegistrationResponse.model_validate(data))
        registrations.sort(
            key=lambda item: ",".join(artifact.artifact_id for artifact in item.registered_artifacts)
        )
        return _registry_response(adapter_response, registrations)

    def review_artifact(
        self,
        adapter_response: CloudPaperDownstreamAdapterResponse,
        *,
        artifact_id: str,
        review_status: CloudPaperDownstreamReviewStatus,
        reviewer_role: CloudPaperRole,
        reviewer_note_recorded: bool = False,
    ) -> CloudPaperDownstreamArtifactRegistryResponse:
        registry = self.get_registry(adapter_response)
        updated_registrations, updated = _review_registrations(
            registry.registrations,
            artifact_id=artifact_id,
            review_status=review_status,
            reviewer_role=reviewer_role,
            reviewer_note_recorded=reviewer_note_recorded,
        )
        if not updated:
            raise CloudPaperDownstreamRegistryArtifactNotFoundError("Downstream artifact review target not found.")
        for registration in updated_registrations:
            self.store_registration(registration)
        return _registry_response(adapter_response, updated_registrations)


def get_cloud_paper_downstream_registry_store(
    config: CloudPaperDownstreamRegistryConfig | None = None,
) -> CloudPaperDownstreamRegistryStore:
    resolved = config or resolve_cloud_paper_downstream_registry_config()
    if resolved.store == "memory":
        return InMemoryCloudPaperDownstreamRegistryStore()
    if resolved.gcp_project_id is None:
        raise CloudPaperDownstreamRegistryConfigError(
            "PAPERPIPE_GCP_PROJECT_ID is required for Firestore downstream registry."
        )
    return CloudPaperFirestoreDownstreamRegistryStore(
        project_id=resolved.gcp_project_id,
        collection_name=resolved.firestore_collection,
    )


def _registry_response(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    registrations: list[CloudPaperDownstreamArtifactRegistrationResponse],
) -> CloudPaperDownstreamArtifactRegistryResponse:
    return CloudPaperDownstreamArtifactRegistryResponse(
        paper_id=adapter_response.paper_id,
        run_id=adapter_response.run_id,
        registry_status="available" if registrations else "empty",
        review_status=_aggregate_registry_review_status(registrations),
        source_pdf_sha256=adapter_response.source_pdf_sha256,
        payload_class=adapter_response.payload_class,
        registrations=registrations,
        warnings=adapter_response.warnings,
        provenance_summary=adapter_response.provenance_summary,
    )


def _review_registrations(
    registrations: list[CloudPaperDownstreamArtifactRegistrationResponse],
    *,
    artifact_id: str,
    review_status: CloudPaperDownstreamReviewStatus,
    reviewer_role: CloudPaperRole,
    reviewer_note_recorded: bool = False,
) -> tuple[list[CloudPaperDownstreamArtifactRegistrationResponse], bool]:
    updated = False
    updated_registrations: list[CloudPaperDownstreamArtifactRegistrationResponse] = []
    reviewed_at = datetime.now(timezone.utc)
    for registration in registrations:
        artifacts = []
        for artifact in registration.registered_artifacts:
            if artifact.artifact_id == artifact_id:
                event = _review_event(
                    artifact_id=artifact_id,
                    review_status=review_status,
                    reviewer_role=reviewer_role,
                    reviewer_note_recorded=reviewer_note_recorded,
                    reviewed_at=reviewed_at,
                    event_index=len(artifact.review_events),
                )
                artifacts.append(
                    artifact.model_copy(
                        update={
                            "review_status": review_status,
                            "review_events": [*artifact.review_events, event],
                        }
                    )
                )
                updated = True
            else:
                artifacts.append(artifact)
        updated_registrations.append(
            registration.model_copy(
                update={
                    "registered_artifacts": artifacts,
                    "review_status": _aggregate_artifact_review_status(artifacts),
                }
            )
        )
    return updated_registrations, updated


def _review_event(
    *,
    artifact_id: str,
    review_status: CloudPaperDownstreamReviewStatus,
    reviewer_role: CloudPaperRole,
    reviewer_note_recorded: bool,
    reviewed_at: datetime,
    event_index: int,
) -> CloudPaperDownstreamArtifactReviewEvent:
    if review_status == "review_pending":
        raise ValueError("review event status must be review_approved or review_rejected")
    digest = hashlib.sha256(
        "\n".join(
            [
                artifact_id,
                review_status,
                reviewer_role,
                reviewed_at.isoformat(),
                str(event_index),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return CloudPaperDownstreamArtifactReviewEvent(
        event_id=f"cloud_downstream_review_{digest}",
        artifact_id=artifact_id,
        review_status=review_status,
        reviewer_role=reviewer_role,
        reviewed_at=reviewed_at,
        reviewer_note_recorded=reviewer_note_recorded,
    )


def _aggregate_registry_review_status(
    registrations: list[CloudPaperDownstreamArtifactRegistrationResponse],
) -> CloudPaperDownstreamReviewStatus:
    return _aggregate_artifact_review_status(
        [artifact for registration in registrations for artifact in registration.registered_artifacts]
    )


def _aggregate_artifact_review_status(
    artifacts: list,
) -> CloudPaperDownstreamReviewStatus:
    statuses = {artifact.review_status for artifact in artifacts}
    if not statuses or "review_pending" in statuses:
        return "review_pending"
    if "review_rejected" in statuses:
        return "review_rejected"
    return "review_approved"


def _registration_document_id(registration: CloudPaperDownstreamArtifactRegistrationResponse) -> str:
    artifact_ids = ",".join(artifact.artifact_id for artifact in registration.registered_artifacts)
    digest = hashlib.sha256(
        "\n".join(
            [
                _registry_key(
                    paper_id=registration.paper_id,
                    run_id=registration.run_id,
                    source_pdf_sha256=registration.source_pdf_sha256,
                ),
                artifact_ids,
            ]
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"{registration.paper_id}_{registration.run_id}_{digest}"


def _registry_key(*, paper_id: str, run_id: str, source_pdf_sha256: str) -> str:
    return "\n".join([paper_id, run_id, source_pdf_sha256])
