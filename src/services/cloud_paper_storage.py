from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib
import json
import os
from typing import Literal, Protocol

from src.schemas.cloud_paper import (
    CloudPaperDerivedArtifactInternal,
    CloudPaperDerivedArtifactStorageResult,
    CloudPaperPageArtifactInternal,
    CloudPaperPageArtifactStorageResult,
    CloudPaperSourceObjectVerification,
    CloudPaperSourceUploadResponse,
    CloudPaperUploadIntentRequest,
    CloudPaperUploadIntentResponse,
)


CloudPaperStorageAdapterMode = Literal["mock", "gcs"]


class CloudPaperStorageConfigError(ValueError):
    pass


class CloudPaperStorageUnavailableError(RuntimeError):
    pass


class CloudPaperPageArtifactNotFoundError(LookupError):
    pass


class CloudPaperDerivedArtifactNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class CloudPaperStorageConfig:
    adapter: CloudPaperStorageAdapterMode = "mock"
    gcp_project_id: str | None = None
    raw_pdf_bucket: str | None = None
    page_artifact_bucket: str | None = None


class CloudPaperStorageAdapter(Protocol):
    adapter: CloudPaperStorageAdapterMode

    def create_upload_intent(
        self,
        request: CloudPaperUploadIntentRequest,
        *,
        paper_id: str,
        upload_intent_id: str,
        expires_at: datetime,
    ) -> CloudPaperUploadIntentResponse:
        ...

    def upload_source_pdf(
        self,
        pdf_bytes: bytes,
        *,
        paper_id: str,
        lab_id: str,
        content_type: str,
    ) -> CloudPaperSourceUploadResponse:
        ...

    def read_source_pdf(
        self,
        *,
        paper_id: str,
        lab_id: str,
    ) -> bytes:
        ...

    def verify_source_pdf(
        self,
        *,
        paper_id: str,
        lab_id: str,
        expected_source_pdf_sha256: str,
    ) -> CloudPaperSourceObjectVerification:
        ...

    def write_page_artifact(
        self,
        artifact: CloudPaperPageArtifactInternal,
        *,
        lab_id: str,
    ) -> CloudPaperPageArtifactStorageResult:
        ...

    def read_page_artifact(
        self,
        *,
        paper_id: str,
        lab_id: str,
        run_id: str,
    ) -> CloudPaperPageArtifactInternal:
        ...

    def write_derived_artifact(
        self,
        artifact: CloudPaperDerivedArtifactInternal,
        *,
        lab_id: str,
    ) -> CloudPaperDerivedArtifactStorageResult:
        ...

    def read_derived_artifact(
        self,
        *,
        paper_id: str,
        lab_id: str,
        run_id: str,
    ) -> CloudPaperDerivedArtifactInternal:
        ...


def _artifact_json_bytes(artifact: CloudPaperPageArtifactInternal | CloudPaperDerivedArtifactInternal) -> bytes:
    payload = artifact.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _env_value(*names: str) -> str | None:
    for name in names:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    return None


def resolve_cloud_paper_storage_config() -> CloudPaperStorageConfig:
    raw_adapter = (_env_value("PAPERPIPE_CLOUD_ADAPTER", "LATTICE_CLOUD_ADAPTER") or "mock").strip().lower()
    if raw_adapter not in {"mock", "gcs"}:
        raise CloudPaperStorageConfigError(f"Unsupported cloud paper storage adapter: {raw_adapter}")
    adapter = raw_adapter
    return CloudPaperStorageConfig(
        adapter=adapter,  # type: ignore[arg-type]
        gcp_project_id=_env_value("PAPERPIPE_GCP_PROJECT_ID", "LATTICE_GCP_PROJECT_ID"),
        raw_pdf_bucket=_env_value("PAPERPIPE_GCS_RAW_PDF_BUCKET", "LATTICE_GCS_RAW_PDF_BUCKET"),
        page_artifact_bucket=_env_value(
            "PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET",
            "LATTICE_GCS_PAGE_ARTIFACT_BUCKET",
        ),
    )


class MockCloudPaperStorageAdapter:
    adapter: CloudPaperStorageAdapterMode = "mock"
    _page_artifacts: dict[tuple[str, str, str], CloudPaperPageArtifactInternal] = {}
    _derived_artifacts: dict[tuple[str, str, str], CloudPaperDerivedArtifactInternal] = {}
    _source_pdfs: dict[tuple[str, str], bytes] = {}

    def create_upload_intent(
        self,
        request: CloudPaperUploadIntentRequest,
        *,
        paper_id: str,
        upload_intent_id: str,
        expires_at: datetime,
    ) -> CloudPaperUploadIntentResponse:
        return CloudPaperUploadIntentResponse(
            upload_intent_id=upload_intent_id,
            paper_id=paper_id,
            upload_mode="mock",
            expires_at=expires_at,
        )

    def upload_source_pdf(
        self,
        pdf_bytes: bytes,
        *,
        paper_id: str,
        lab_id: str,
        content_type: str,
    ) -> CloudPaperSourceUploadResponse:
        self._source_pdfs[(lab_id, paper_id)] = pdf_bytes
        return CloudPaperSourceUploadResponse(
            paper_id=paper_id,
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            source_pdf_size_bytes=len(pdf_bytes),
            content_type=content_type,
        )

    def read_source_pdf(
        self,
        *,
        paper_id: str,
        lab_id: str,
    ) -> bytes:
        pdf_bytes = self._source_pdfs.get((lab_id, paper_id))
        if pdf_bytes is None:
            raise CloudPaperStorageUnavailableError("Source PDF is not available in mock storage.")
        return pdf_bytes

    def verify_source_pdf(
        self,
        *,
        paper_id: str,
        lab_id: str,
        expected_source_pdf_sha256: str,
    ) -> CloudPaperSourceObjectVerification:
        return CloudPaperSourceObjectVerification(
            paper_id=paper_id,
            exists=True,
            checksum_matches=True,
            source_pdf_sha256=expected_source_pdf_sha256,
        )

    def write_page_artifact(
        self,
        artifact: CloudPaperPageArtifactInternal,
        *,
        lab_id: str,
    ) -> CloudPaperPageArtifactStorageResult:
        object_ref = f"gs://paperpipe-mock-pages/{lab_id}/{artifact.paper_id}/{artifact.run_id}/page.json"
        stored = CloudPaperPageArtifactInternal(
            **{
                **artifact.model_dump(),
                "gcs_page_artifact_object_ref": object_ref,
            }
        )
        payload = _artifact_json_bytes(stored)
        page_artifact_sha256 = hashlib.sha256(payload).hexdigest()
        self._page_artifacts[(lab_id, stored.paper_id, stored.run_id)] = stored
        return CloudPaperPageArtifactStorageResult(
            paper_id=stored.paper_id,
            run_id=stored.run_id,
            page_schema_version=stored.page_schema_version,
            page_artifact_sha256=page_artifact_sha256,
            page_artifact_size_bytes=len(payload),
        )

    def read_page_artifact(
        self,
        *,
        paper_id: str,
        lab_id: str,
        run_id: str,
    ) -> CloudPaperPageArtifactInternal:
        artifact = self._page_artifacts.get((lab_id, paper_id, run_id))
        if artifact is None:
            raise CloudPaperPageArtifactNotFoundError(paper_id)
        return artifact

    def write_derived_artifact(
        self,
        artifact: CloudPaperDerivedArtifactInternal,
        *,
        lab_id: str,
    ) -> CloudPaperDerivedArtifactStorageResult:
        object_ref = f"gs://paperpipe-mock-derived/{lab_id}/{artifact.paper_id}/{artifact.run_id}/derived.json"
        stored = CloudPaperDerivedArtifactInternal(
            **{
                **artifact.model_dump(),
                "gcs_derived_artifact_object_ref": object_ref,
            }
        )
        payload = _artifact_json_bytes(stored)
        derived_artifact_sha256 = hashlib.sha256(payload).hexdigest()
        self._derived_artifacts[(lab_id, stored.paper_id, stored.run_id)] = stored
        return CloudPaperDerivedArtifactStorageResult(
            paper_id=stored.paper_id,
            run_id=stored.run_id,
            derived_artifact_sha256=derived_artifact_sha256,
            derived_artifact_size_bytes=len(payload),
        )

    def read_derived_artifact(
        self,
        *,
        paper_id: str,
        lab_id: str,
        run_id: str,
    ) -> CloudPaperDerivedArtifactInternal:
        artifact = self._derived_artifacts.get((lab_id, paper_id, run_id))
        if artifact is None:
            raise CloudPaperDerivedArtifactNotFoundError(paper_id)
        return artifact


class GcsCloudPaperStorageAdapter:
    adapter: CloudPaperStorageAdapterMode = "gcs"

    def __init__(self, config: CloudPaperStorageConfig):
        missing = []
        if not config.gcp_project_id:
            missing.append("PAPERPIPE_GCP_PROJECT_ID")
        if not config.raw_pdf_bucket:
            missing.append("PAPERPIPE_GCS_RAW_PDF_BUCKET")
        if not config.page_artifact_bucket:
            missing.append("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET")
        if missing:
            raise CloudPaperStorageConfigError(f"Missing GCS cloud paper config: {', '.join(missing)}")
        self.config = config

    def _load_storage_module(self):
        try:
            return importlib.import_module("google.cloud.storage")
        except ModuleNotFoundError as exc:
            raise CloudPaperStorageUnavailableError(
                "google-cloud-storage is not installed; install it only when PAPERPIPE_CLOUD_ADAPTER=gcs is enabled."
            ) from exc

    def _raw_pdf_object_name(self, *, lab_id: str, paper_id: str) -> str:
        return f"{lab_id}/{paper_id}/source.pdf"

    def _page_artifact_object_name(self, *, lab_id: str, paper_id: str, run_id: str) -> str:
        return f"{lab_id}/{paper_id}/{run_id}/page.json"

    def _derived_artifact_object_name(self, *, lab_id: str, paper_id: str, run_id: str) -> str:
        return f"{lab_id}/{paper_id}/{run_id}/derived.json"

    def create_upload_intent(
        self,
        request: CloudPaperUploadIntentRequest,
        *,
        paper_id: str,
        upload_intent_id: str,
        expires_at: datetime,
    ) -> CloudPaperUploadIntentResponse:
        self._load_storage_module()
        return CloudPaperUploadIntentResponse(
            upload_intent_id=upload_intent_id,
            paper_id=paper_id,
            upload_mode="backend_mediated",
            expires_at=expires_at,
        )

    def upload_source_pdf(
        self,
        pdf_bytes: bytes,
        *,
        paper_id: str,
        lab_id: str,
        content_type: str,
    ) -> CloudPaperSourceUploadResponse:
        if content_type != "application/pdf":
            raise CloudPaperStorageConfigError("source PDF content_type must be application/pdf")
        source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        storage_module = self._load_storage_module()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.raw_pdf_bucket)
        blob = bucket.blob(self._raw_pdf_object_name(lab_id=lab_id, paper_id=paper_id))
        blob.metadata = {
            "paper_id": paper_id,
            "lab_id": lab_id,
            "source_pdf_sha256": source_pdf_sha256,
        }
        blob.upload_from_string(pdf_bytes, content_type=content_type)
        return CloudPaperSourceUploadResponse(
            paper_id=paper_id,
            source_pdf_sha256=source_pdf_sha256,
            source_pdf_size_bytes=len(pdf_bytes),
            content_type=content_type,
        )

    def verify_source_pdf(
        self,
        *,
        paper_id: str,
        lab_id: str,
        expected_source_pdf_sha256: str,
    ) -> CloudPaperSourceObjectVerification:
        storage_module = self._load_storage_module()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.raw_pdf_bucket)
        blob = bucket.blob(self._raw_pdf_object_name(lab_id=lab_id, paper_id=paper_id))
        if not blob.exists():
            return CloudPaperSourceObjectVerification(paper_id=paper_id, exists=False)
        blob.reload()
        metadata = blob.metadata or {}
        source_pdf_sha256 = metadata.get("source_pdf_sha256")
        return CloudPaperSourceObjectVerification(
            paper_id=paper_id,
            exists=True,
            checksum_matches=source_pdf_sha256 == expected_source_pdf_sha256,
            source_pdf_sha256=source_pdf_sha256,
            source_pdf_size_bytes=blob.size,
        )

    def read_source_pdf(
        self,
        *,
        paper_id: str,
        lab_id: str,
    ) -> bytes:
        storage_module = self._load_storage_module()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.raw_pdf_bucket)
        blob = bucket.blob(self._raw_pdf_object_name(lab_id=lab_id, paper_id=paper_id))
        if not blob.exists():
            raise CloudPaperStorageUnavailableError("Source PDF object was not found in cloud storage.")
        return blob.download_as_bytes()

    def write_page_artifact(
        self,
        artifact: CloudPaperPageArtifactInternal,
        *,
        lab_id: str,
    ) -> CloudPaperPageArtifactStorageResult:
        storage_module = self._load_storage_module()
        object_name = self._page_artifact_object_name(
            lab_id=lab_id,
            paper_id=artifact.paper_id,
            run_id=artifact.run_id,
        )
        object_ref = f"gs://{self.config.page_artifact_bucket}/{object_name}"
        stored = CloudPaperPageArtifactInternal(
            **{
                **artifact.model_dump(),
                "gcs_page_artifact_object_ref": object_ref,
            }
        )
        payload = _artifact_json_bytes(stored)
        page_artifact_sha256 = hashlib.sha256(payload).hexdigest()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.page_artifact_bucket)
        blob = bucket.blob(object_name)
        blob.metadata = {
            "paper_id": stored.paper_id,
            "lab_id": lab_id,
            "run_id": stored.run_id,
            "page_artifact_sha256": page_artifact_sha256,
        }
        blob.upload_from_string(payload, content_type="application/json")
        return CloudPaperPageArtifactStorageResult(
            paper_id=stored.paper_id,
            run_id=stored.run_id,
            page_schema_version=stored.page_schema_version,
            page_artifact_sha256=page_artifact_sha256,
            page_artifact_size_bytes=len(payload),
        )

    def read_page_artifact(
        self,
        *,
        paper_id: str,
        lab_id: str,
        run_id: str,
    ) -> CloudPaperPageArtifactInternal:
        storage_module = self._load_storage_module()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.page_artifact_bucket)
        blob = bucket.blob(self._page_artifact_object_name(lab_id=lab_id, paper_id=paper_id, run_id=run_id))
        if not blob.exists():
            raise CloudPaperPageArtifactNotFoundError(paper_id)
        payload = blob.download_as_bytes()
        return CloudPaperPageArtifactInternal.model_validate_json(payload)

    def write_derived_artifact(
        self,
        artifact: CloudPaperDerivedArtifactInternal,
        *,
        lab_id: str,
    ) -> CloudPaperDerivedArtifactStorageResult:
        storage_module = self._load_storage_module()
        object_name = self._derived_artifact_object_name(
            lab_id=lab_id,
            paper_id=artifact.paper_id,
            run_id=artifact.run_id,
        )
        object_ref = f"gs://{self.config.page_artifact_bucket}/{object_name}"
        stored = CloudPaperDerivedArtifactInternal(
            **{
                **artifact.model_dump(),
                "gcs_derived_artifact_object_ref": object_ref,
            }
        )
        payload = _artifact_json_bytes(stored)
        derived_artifact_sha256 = hashlib.sha256(payload).hexdigest()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.page_artifact_bucket)
        blob = bucket.blob(object_name)
        blob.metadata = {
            "paper_id": stored.paper_id,
            "lab_id": lab_id,
            "run_id": stored.run_id,
            "derived_artifact_sha256": derived_artifact_sha256,
        }
        blob.upload_from_string(payload, content_type="application/json")
        return CloudPaperDerivedArtifactStorageResult(
            paper_id=stored.paper_id,
            run_id=stored.run_id,
            derived_artifact_sha256=derived_artifact_sha256,
            derived_artifact_size_bytes=len(payload),
        )

    def read_derived_artifact(
        self,
        *,
        paper_id: str,
        lab_id: str,
        run_id: str,
    ) -> CloudPaperDerivedArtifactInternal:
        storage_module = self._load_storage_module()
        client = storage_module.Client(project=self.config.gcp_project_id)
        bucket = client.bucket(self.config.page_artifact_bucket)
        blob = bucket.blob(self._derived_artifact_object_name(lab_id=lab_id, paper_id=paper_id, run_id=run_id))
        if not blob.exists():
            raise CloudPaperDerivedArtifactNotFoundError(paper_id)
        payload = blob.download_as_bytes()
        return CloudPaperDerivedArtifactInternal.model_validate_json(payload)


def get_cloud_paper_storage_adapter() -> CloudPaperStorageAdapter:
    config = resolve_cloud_paper_storage_config()
    if config.adapter == "mock":
        return MockCloudPaperStorageAdapter()
    return GcsCloudPaperStorageAdapter(config)
