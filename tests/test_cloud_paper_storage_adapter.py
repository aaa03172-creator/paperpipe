from __future__ import annotations

from datetime import datetime, timezone
import importlib

import pytest

from src.schemas.cloud_paper import (
    CloudPaperDerivedArtifactFigure,
    CloudPaperDerivedArtifactFigureAnalysis,
    CloudPaperDerivedArtifactInternal,
    CloudPaperDerivedArtifactOcrBlock,
    CloudPaperDerivedArtifactSourceLocator,
    CloudPaperDerivedArtifactTable,
    CloudPaperPageArtifactInternal,
    CloudPaperPageBlockInternal,
    CloudPaperProvenance,
    CloudPaperUploadIntentRequest,
    derive_cloud_page_artifact_public,
    derive_cloud_paper_public_derived_artifacts,
)
from src.services.cloud_paper_storage import (
    CloudPaperDerivedArtifactNotFoundError,
    CloudPaperStorageConfigError,
    CloudPaperStorageUnavailableError,
    GcsCloudPaperStorageAdapter,
    MockCloudPaperStorageAdapter,
    get_cloud_paper_storage_adapter,
    resolve_cloud_paper_storage_config,
)


def _sample_upload_request() -> CloudPaperUploadIntentRequest:
    return CloudPaperUploadIntentRequest(
        filename="paper.pdf",
        content_type="application/pdf",
        source_pdf_sha256="f" * 64,
        lab_id="lab_001",
    )


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


def _sample_page_artifact(**overrides: object) -> CloudPaperPageArtifactInternal:
    payload = {
        "paper_id": "paper_gcs_000001",
        "run_id": "run_paper_gcs_000001",
        "page_schema_version": "cloud_page_artifact.v1",
        "source_pdf_sha256": "a" * 64,
        "gcs_page_artifact_object_ref": "gs://paperpipe-page-dev/lab_001/paper_gcs_000001/run_paper_gcs_000001/page.json",
        "blocks": [
            CloudPaperPageBlockInternal(
                block_id="block_001",
                page=1,
                kind="text",
                text="Stored page artifact text.",
                bbox_pct={"left": 0.1, "top": 0.2, "width": 0.7, "height": 0.1},
                metadata={
                    "section": "abstract",
                    "private_ref": "gs://paperpipe-page-dev/private",
                },
            )
        ],
        "warnings": [],
        "provenance": CloudPaperProvenance(
            uploaded_by="mock_user",
            processor_name="paperpipe-worker",
            processor_version="0.1.0",
            created_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
            source_pdf_sha256="a" * 64,
        ),
        "worker_metadata": {"service_account": "worker@example.iam.gserviceaccount.com"},
    }
    payload.update(overrides)
    return CloudPaperPageArtifactInternal(**payload)


def _sample_derived_artifact(**overrides: object) -> CloudPaperDerivedArtifactInternal:
    source_pdf_sha256 = "a" * 64
    source_page_1 = CloudPaperDerivedArtifactSourceLocator(
        page=1,
        source_pdf_sha256=source_pdf_sha256,
        block_id="block_001",
    )
    source_page_2 = CloudPaperDerivedArtifactSourceLocator(page=2, source_pdf_sha256=source_pdf_sha256)
    source_page_3 = CloudPaperDerivedArtifactSourceLocator(page=3, source_pdf_sha256=source_pdf_sha256)
    payload = {
        "paper_id": "paper_gcs_000001",
        "run_id": "run_paper_gcs_000001",
        "source_pdf_sha256": source_pdf_sha256,
        "gcs_derived_artifact_object_ref": (
            "gs://paperpipe-derived-dev/lab_001/paper_gcs_000001/run_paper_gcs_000001/derived.json"
        ),
        "payload_class": "local_only",
        "ocr_blocks": [
            CloudPaperDerivedArtifactOcrBlock(
                ocr_block_id="ocr_001",
                text="Stored OCR text.",
                confidence=0.91,
                source=source_page_1,
                metadata={"engine": "mock-ocr", "gcs_image_ref": "gs://private/page.png"},
            )
        ],
        "tables": [
            CloudPaperDerivedArtifactTable(
                table_id="table_001",
                page=2,
                caption="Stored table.",
                columns=["Group", "N"],
                rows=[["Control", "10"]],
                confidence=0.82,
                source=source_page_2,
            )
        ],
        "figures": [
            CloudPaperDerivedArtifactFigure(
                figure_id="figure_001",
                page=3,
                caption="Stored figure.",
                image_available=True,
                image_route="/api/cloud/papers/paper_gcs_000001/figures/figure_001/image",
                confidence=0.77,
                source=source_page_3,
                metadata={"signed_url": "https://signed.example.test/private"},
            )
        ],
        "figure_analyses": [
            CloudPaperDerivedArtifactFigureAnalysis(
                analysis_id="figure_analysis_001",
                figure_id="figure_001",
                page=3,
                summary="Stored figure analysis.",
                confidence=0.7,
                source=source_page_3,
            )
        ],
        "warnings": [],
        "provenance": CloudPaperProvenance(
            uploaded_by="mock_user",
            processor_name="paperpipe-derived-worker",
            processor_version="0.1.0",
            created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=timezone.utc),
            source_pdf_sha256=source_pdf_sha256,
        ),
        "worker_metadata": {"service_account": "worker@example.iam.gserviceaccount.com"},
    }
    payload.update(overrides)
    return CloudPaperDerivedArtifactInternal(**payload)


def test_default_cloud_storage_adapter_is_mock(monkeypatch) -> None:
    monkeypatch.delenv("PAPERPIPE_CLOUD_ADAPTER", raising=False)
    monkeypatch.delenv("LATTICE_CLOUD_ADAPTER", raising=False)

    config = resolve_cloud_paper_storage_config()
    adapter = get_cloud_paper_storage_adapter()

    assert config.adapter == "mock"
    assert isinstance(adapter, MockCloudPaperStorageAdapter)


def test_mock_storage_adapter_returns_redacted_upload_contract() -> None:
    adapter = MockCloudPaperStorageAdapter()

    response = adapter.create_upload_intent(
        _sample_upload_request(),
        paper_id="paper_mock_000001",
        upload_intent_id="upl_mock_000001",
        expires_at=datetime(2026, 5, 30, 1, 17, 3, tzinfo=timezone.utc),
    )

    assert response.upload_mode == "mock"
    assert response.paper_id == "paper_mock_000001"
    assert "gs://" not in str(response.model_dump(mode="json"))


def test_unknown_cloud_storage_adapter_mode_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "surprise")

    with pytest.raises(CloudPaperStorageConfigError, match="Unsupported cloud paper storage adapter"):
        resolve_cloud_paper_storage_config()


def test_gcs_adapter_can_be_selected_without_importing_google(monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")

    calls: list[str] = []
    original_import_module = importlib.import_module

    def tracking_import(name: str, package: str | None = None):
        calls.append(name)
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", tracking_import)

    adapter = get_cloud_paper_storage_adapter()

    assert isinstance(adapter, GcsCloudPaperStorageAdapter)
    assert "google.cloud.storage" not in calls


def test_gcs_adapter_upload_intent_requires_real_gcp_dependency_lazily(monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")

    def fail_google_import(name: str, package: str | None = None):
        if name == "google.cloud.storage":
            raise ModuleNotFoundError(name)
        return importlib.import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_google_import)
    adapter = get_cloud_paper_storage_adapter()

    with pytest.raises(CloudPaperStorageUnavailableError, match="google-cloud-storage is not installed"):
        adapter.create_upload_intent(
            _sample_upload_request(),
            paper_id="paper_gcs_000001",
            upload_intent_id="upl_gcs_000001",
            expires_at=datetime(2026, 5, 30, 1, 17, 3, tzinfo=timezone.utc),
        )


def test_gcs_adapter_returns_backend_mediated_upload_intent_without_public_gcs_refs(monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)

    adapter = get_cloud_paper_storage_adapter()
    response = adapter.create_upload_intent(
        _sample_upload_request(),
        paper_id="paper_gcs_000001",
        upload_intent_id="upl_gcs_000001",
        expires_at=datetime(2026, 5, 30, 1, 17, 3, tzinfo=timezone.utc),
    )

    assert response.upload_mode == "backend_mediated"
    assert response.paper_id == "paper_gcs_000001"
    assert "gs://" not in str(response.model_dump(mode="json"))
    assert "paperpipe-raw-dev" not in str(response.model_dump(mode="json"))


def test_gcs_adapter_uploads_pdf_bytes_to_reserved_raw_object(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)

    adapter = get_cloud_paper_storage_adapter()
    result = adapter.upload_source_pdf(
        b"%PDF-1.4\nmock",
        paper_id="paper_gcs_000001",
        lab_id="lab_001",
        content_type="application/pdf",
    )

    assert result.source_pdf_size_bytes == len(b"%PDF-1.4\nmock")
    assert result.source_pdf_sha256
    assert "gs://" not in str(result.model_dump(mode="json"))
    client = _FakeStorageClient.instances[0]
    assert client.project == "paperpipe-dev"
    blob = client.buckets["paperpipe-raw-dev"].blobs["lab_001/paper_gcs_000001/source.pdf"]
    assert blob.uploads == [{"data": b"%PDF-1.4\nmock", "content_type": "application/pdf"}]
    assert blob.metadata == {
        "paper_id": "paper_gcs_000001",
        "lab_id": "lab_001",
        "source_pdf_sha256": result.source_pdf_sha256,
    }


def test_gcs_adapter_verifies_uploaded_source_pdf_metadata(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)

    adapter = get_cloud_paper_storage_adapter()
    uploaded = adapter.upload_source_pdf(
        b"%PDF-1.4\nmock",
        paper_id="paper_gcs_000001",
        lab_id="lab_001",
        content_type="application/pdf",
    )

    verification = adapter.verify_source_pdf(
        paper_id="paper_gcs_000001",
        lab_id="lab_001",
        expected_source_pdf_sha256=uploaded.source_pdf_sha256,
    )

    assert verification.exists is True
    assert verification.checksum_matches is True
    assert verification.source_pdf_sha256 == uploaded.source_pdf_sha256
    assert verification.source_pdf_size_bytes == len(b"%PDF-1.4\nmock")
    assert "gs://" not in str(verification.model_dump(mode="json"))


def test_gcs_adapter_verification_reports_checksum_mismatch_without_leaking_ref(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)

    adapter = get_cloud_paper_storage_adapter()
    adapter.upload_source_pdf(
        b"%PDF-1.4\nmock",
        paper_id="paper_gcs_000001",
        lab_id="lab_001",
        content_type="application/pdf",
    )

    verification = adapter.verify_source_pdf(
        paper_id="paper_gcs_000001",
        lab_id="lab_001",
        expected_source_pdf_sha256="0" * 64,
    )

    assert verification.exists is True
    assert verification.checksum_matches is False
    assert "paperpipe-raw-dev" not in str(verification.model_dump(mode="json"))


def test_gcs_adapter_writes_and_reads_page_artifact_without_public_refs(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)

    adapter = get_cloud_paper_storage_adapter()
    artifact = _sample_page_artifact()

    written = adapter.write_page_artifact(artifact, lab_id="lab_001")
    loaded = adapter.read_page_artifact(
        paper_id=artifact.paper_id,
        lab_id="lab_001",
        run_id=artifact.run_id,
    )
    public = derive_cloud_page_artifact_public(loaded)

    assert written.paper_id == artifact.paper_id
    assert written.run_id == artifact.run_id
    assert written.page_schema_version == artifact.page_schema_version
    assert written.page_artifact_sha256
    assert "gs://" not in str(written.model_dump(mode="json"))
    assert "paperpipe-page-dev" not in str(written.model_dump(mode="json"))
    assert loaded.paper_id == artifact.paper_id
    assert public.blocks[0].metadata == {"section": "abstract"}
    assert "gs://" not in str(public.model_dump(mode="json"))

    blob = _FakeStorageClient.buckets_by_name["paperpipe-page-dev"].blobs[
        "lab_001/paper_gcs_000001/run_paper_gcs_000001/page.json"
    ]
    assert blob.uploads[0]["content_type"] == "application/json"
    assert blob.metadata == {
        "paper_id": artifact.paper_id,
        "lab_id": "lab_001",
        "run_id": artifact.run_id,
        "page_artifact_sha256": written.page_artifact_sha256,
    }


def test_mock_storage_adapter_writes_and_reads_derived_artifact_without_public_refs() -> None:
    adapter = MockCloudPaperStorageAdapter()
    artifact = _sample_derived_artifact(paper_id="paper_mock_derived", run_id="run_paper_mock_derived")

    written = adapter.write_derived_artifact(artifact, lab_id="lab_001")
    loaded = adapter.read_derived_artifact(
        paper_id=artifact.paper_id,
        lab_id="lab_001",
        run_id=artifact.run_id,
    )
    public = derive_cloud_paper_public_derived_artifacts(loaded)

    assert written.paper_id == artifact.paper_id
    assert written.run_id == artifact.run_id
    assert written.derived_artifact_sha256
    assert "gs://" not in str(written.model_dump(mode="json"))
    assert loaded.gcs_derived_artifact_object_ref == (
        "gs://paperpipe-mock-derived/lab_001/paper_mock_derived/run_paper_mock_derived/derived.json"
    )
    assert public.ocr_blocks[0].metadata == {"engine": "mock-ocr"}
    assert "gs://" not in str(public.model_dump(mode="json"))
    assert "signed_url" not in str(public.model_dump(mode="json"))
    with pytest.raises(CloudPaperDerivedArtifactNotFoundError):
        adapter.read_derived_artifact(paper_id="missing", lab_id="lab_001", run_id="run_missing")


def test_gcs_adapter_writes_and_reads_derived_artifact_without_public_refs(monkeypatch) -> None:
    _FakeStorageClient.instances.clear()
    _FakeStorageClient.buckets_by_name.clear()
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-dev")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.setattr(importlib, "import_module", lambda name: _FakeStorageModule)

    adapter = get_cloud_paper_storage_adapter()
    artifact = _sample_derived_artifact()

    written = adapter.write_derived_artifact(artifact, lab_id="lab_001")
    loaded = adapter.read_derived_artifact(
        paper_id=artifact.paper_id,
        lab_id="lab_001",
        run_id=artifact.run_id,
    )
    public = derive_cloud_paper_public_derived_artifacts(loaded)

    assert written.paper_id == artifact.paper_id
    assert written.run_id == artifact.run_id
    assert written.derived_artifact_sha256
    assert "gs://" not in str(written.model_dump(mode="json"))
    assert "paperpipe-page-dev" not in str(written.model_dump(mode="json"))
    assert loaded.paper_id == artifact.paper_id
    assert public.tables[0].table_id == "table_001"
    assert "gs://" not in str(public.model_dump(mode="json"))

    blob = _FakeStorageClient.buckets_by_name["paperpipe-page-dev"].blobs[
        "lab_001/paper_gcs_000001/run_paper_gcs_000001/derived.json"
    ]
    assert blob.uploads[0]["content_type"] == "application/json"
    assert blob.metadata == {
        "paper_id": artifact.paper_id,
        "lab_id": "lab_001",
        "run_id": artifact.run_id,
        "derived_artifact_sha256": written.derived_artifact_sha256,
    }


def test_gcs_adapter_selection_requires_bucket_config(monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-dev")
    monkeypatch.delenv("LATTICE_GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", raising=False)
    monkeypatch.delenv("LATTICE_GCS_RAW_PDF_BUCKET", raising=False)
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-dev")
    monkeypatch.delenv("LATTICE_GCS_PAGE_ARTIFACT_BUCKET", raising=False)

    with pytest.raises(CloudPaperStorageConfigError, match="PAPERPIPE_GCS_RAW_PDF_BUCKET"):
        get_cloud_paper_storage_adapter()
