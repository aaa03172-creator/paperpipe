from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from typing import Literal, Protocol

from src.schemas.cloud_paper import (
    CloudPaperMetadataRecord,
    CloudPaperUploadIntentRequest,
    CloudPaperWarning,
)


CloudPaperMetadataStoreMode = Literal["memory", "firestore"]


class CloudPaperMetadataConfigError(ValueError):
    pass


@dataclass(frozen=True)
class CloudPaperMetadataConfig:
    store: CloudPaperMetadataStoreMode = "memory"
    gcp_project_id: str | None = None
    firestore_collection: str = "cloud_papers"


class CloudPaperMetadataStore(Protocol):
    def clear(self) -> None:
        ...

    def create_upload_intent_record(
        self,
        *,
        paper_id: str,
        upload_intent_id: str,
        request: CloudPaperUploadIntentRequest,
    ) -> CloudPaperMetadataRecord:
        ...

    def get(self, paper_id: str) -> CloudPaperMetadataRecord | None:
        ...

    def list_records(self) -> list[CloudPaperMetadataRecord]:
        ...

    def mark_upload_ready(self, paper_id: str) -> CloudPaperMetadataRecord:
        ...

    def mark_upload_received(self, paper_id: str) -> CloudPaperMetadataRecord:
        ...

    def mark_upload_blocked(self, paper_id: str, *, warning: CloudPaperWarning) -> CloudPaperMetadataRecord:
        ...

    def mark_processing_running(self, paper_id: str) -> CloudPaperMetadataRecord:
        ...

    def mark_processing_failed(self, paper_id: str, *, warning: CloudPaperWarning) -> CloudPaperMetadataRecord:
        ...


class CloudPaperMetadataNotFoundError(LookupError):
    pass


def _env_value(*names: str) -> str | None:
    for name in names:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    return None


def resolve_cloud_paper_metadata_config() -> CloudPaperMetadataConfig:
    raw_store = (
        _env_value("PAPERPIPE_CLOUD_METADATA_STORE", "LATTICE_CLOUD_METADATA_STORE") or "memory"
    ).strip().lower()
    if raw_store == "mock":
        raw_store = "memory"
    if raw_store not in {"memory", "firestore"}:
        raise CloudPaperMetadataConfigError(f"Unsupported cloud paper metadata store: {raw_store}")
    collection = (
        _env_value("PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION", "LATTICE_FIRESTORE_CLOUD_PAPER_COLLECTION")
        or "cloud_papers"
    )
    return CloudPaperMetadataConfig(
        store=raw_store,  # type: ignore[arg-type]
        gcp_project_id=_env_value("PAPERPIPE_GCP_PROJECT_ID", "LATTICE_GCP_PROJECT_ID"),
        firestore_collection=collection,
    )


class InMemoryCloudPaperMetadataStore:
    def __init__(self) -> None:
        self._records: dict[str, CloudPaperMetadataRecord] = {}

    def clear(self) -> None:
        self._records.clear()

    def create_upload_intent_record(
        self,
        *,
        paper_id: str,
        upload_intent_id: str,
        request: CloudPaperUploadIntentRequest,
    ) -> CloudPaperMetadataRecord:
        record = CloudPaperMetadataRecord(
            paper_id=paper_id,
            upload_intent_id=upload_intent_id,
            request=request,
            upload_status="intent_created",
            processing_status="pending",
            warnings=[],
        )
        self._records[paper_id] = record
        return record

    def get(self, paper_id: str) -> CloudPaperMetadataRecord | None:
        return self._records.get(paper_id)

    def list_records(self) -> list[CloudPaperMetadataRecord]:
        return list(self._records.values())

    def mark_upload_ready(self, paper_id: str) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        if current.upload_status == "ready":
            return current
        record = current.model_copy(
            update={
                "upload_status": "ready",
                "processing_status": "ready",
                "warnings": [],
            }
        )
        self._records[paper_id] = record
        return record

    def mark_upload_received(self, paper_id: str) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        if current.upload_status in {"upload_received", "ready"}:
            return current
        record = current.model_copy(
            update={
                "upload_status": "upload_received",
                "processing_status": "pending",
                "warnings": [],
            }
        )
        self._records[paper_id] = record
        return record

    def mark_upload_blocked(self, paper_id: str, *, warning: CloudPaperWarning) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        record = current.model_copy(
            update={
                "upload_status": "blocked",
                "processing_status": "blocked",
                "warnings": [warning],
            }
        )
        self._records[paper_id] = record
        return record

    def mark_processing_running(self, paper_id: str) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        if current.upload_status == "processing":
            return current
        record = current.model_copy(
            update={
                "upload_status": "processing",
                "processing_status": "running",
                "warnings": [],
            }
        )
        self._records[paper_id] = record
        return record

    def mark_processing_failed(self, paper_id: str, *, warning: CloudPaperWarning) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        record = current.model_copy(
            update={
                "upload_status": "failed",
                "processing_status": "failed",
                "warnings": [warning],
            }
        )
        self._records[paper_id] = record
        return record

    def _record_for(self, paper_id: str) -> CloudPaperMetadataRecord:
        record = self.get(paper_id)
        if record is None:
            raise CloudPaperMetadataNotFoundError(paper_id)
        return record


class CloudPaperFirestoreMetadataStore:
    def __init__(
        self,
        *,
        project_id: str,
        collection_name: str = "cloud_papers",
        allow_clear: bool = False,
    ) -> None:
        if not project_id.strip():
            raise CloudPaperMetadataConfigError("PAPERPIPE_GCP_PROJECT_ID is required for Firestore metadata.")
        if not collection_name.strip():
            raise CloudPaperMetadataConfigError("Firestore cloud paper collection must not be empty.")
        try:
            firestore = importlib.import_module("google.cloud.firestore")
        except ImportError as exc:
            raise CloudPaperMetadataConfigError(
                "google-cloud-firestore is not installed; install it only when "
                "PAPERPIPE_CLOUD_METADATA_STORE=firestore is enabled."
            ) from exc
        self._collection = firestore.Client(project=project_id).collection(collection_name)
        self._allow_clear = allow_clear

    def clear(self) -> None:
        if not self._allow_clear:
            raise CloudPaperMetadataConfigError("Firestore metadata clear is disabled outside controlled tests.")
        for snapshot in self._collection.stream():
            document_id = getattr(snapshot, "id", None)
            data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
            paper_id = document_id or (data or {}).get("paper_id")
            if paper_id:
                self._collection.document(str(paper_id)).delete()

    def create_upload_intent_record(
        self,
        *,
        paper_id: str,
        upload_intent_id: str,
        request: CloudPaperUploadIntentRequest,
    ) -> CloudPaperMetadataRecord:
        record = CloudPaperMetadataRecord(
            paper_id=paper_id,
            upload_intent_id=upload_intent_id,
            request=request,
            upload_status="intent_created",
            processing_status="pending",
            warnings=[],
        )
        self._write(record)
        return record

    def get(self, paper_id: str) -> CloudPaperMetadataRecord | None:
        snapshot = self._collection.document(paper_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        data = snapshot.to_dict()
        if not data:
            return None
        return CloudPaperMetadataRecord.model_validate(data)

    def list_records(self) -> list[CloudPaperMetadataRecord]:
        records = []
        for snapshot in self._collection.stream():
            data = snapshot.to_dict()
            if data:
                records.append(CloudPaperMetadataRecord.model_validate(data))
        return sorted(records, key=lambda record: record.paper_id)

    def mark_upload_ready(self, paper_id: str) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        if current.upload_status == "ready":
            return current
        return self._replace(
            current,
            upload_status="ready",
            processing_status="ready",
            warnings=[],
        )

    def mark_upload_received(self, paper_id: str) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        if current.upload_status in {"upload_received", "ready"}:
            return current
        return self._replace(
            current,
            upload_status="upload_received",
            processing_status="pending",
            warnings=[],
        )

    def mark_upload_blocked(self, paper_id: str, *, warning: CloudPaperWarning) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        return self._replace(
            current,
            upload_status="blocked",
            processing_status="blocked",
            warnings=[warning],
        )

    def mark_processing_running(self, paper_id: str) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        if current.upload_status == "processing":
            return current
        return self._replace(
            current,
            upload_status="processing",
            processing_status="running",
            warnings=[],
        )

    def mark_processing_failed(self, paper_id: str, *, warning: CloudPaperWarning) -> CloudPaperMetadataRecord:
        current = self._record_for(paper_id)
        return self._replace(
            current,
            upload_status="failed",
            processing_status="failed",
            warnings=[warning],
        )

    def _record_for(self, paper_id: str) -> CloudPaperMetadataRecord:
        record = self.get(paper_id)
        if record is None:
            raise CloudPaperMetadataNotFoundError(paper_id)
        return record

    def _replace(self, current: CloudPaperMetadataRecord, **updates: object) -> CloudPaperMetadataRecord:
        record = current.model_copy(update=updates)
        self._write(record)
        return record

    def _write(self, record: CloudPaperMetadataRecord) -> None:
        self._collection.document(record.paper_id).set(record.model_dump(mode="json"))


def get_cloud_paper_metadata_store(config: CloudPaperMetadataConfig | None = None) -> CloudPaperMetadataStore:
    resolved = config or resolve_cloud_paper_metadata_config()
    if resolved.store == "memory":
        return InMemoryCloudPaperMetadataStore()
    if resolved.gcp_project_id is None:
        raise CloudPaperMetadataConfigError("PAPERPIPE_GCP_PROJECT_ID is required for Firestore metadata.")
    return CloudPaperFirestoreMetadataStore(
        project_id=resolved.gcp_project_id,
        collection_name=resolved.firestore_collection,
    )
