from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CLOUD_PAPER_BUNDLE_SCHEMA_VERSION = "cloud_paper_bundle.v1"
CLOUD_PAPER_BUNDLE_PUBLIC_SCHEMA_VERSION = "cloud_paper_bundle_public.v1"

CloudPaperPayloadClass = Literal["local_only", "lab_allowed", "external_allowed"]
CloudPaperProcessingStatus = Literal["pending", "running", "ready", "failed", "blocked"]
CloudPaperRole = Literal["lab_admin", "maintainer", "reviewer", "reader"]
CloudPaperAction = Literal[
    "read_page",
    "read_pdf",
    "hydrate_download",
    "run_optional_ai",
    "export",
    "share",
    "upload",
    "delete",
]
CloudPaperWarningSeverity = Literal["info", "low", "medium", "high", "critical"]
CloudPaperHydrationStatus = Literal["not_hydrated", "hydrated", "stale", "failed", "blocked"]
CloudPaperUploadMode = Literal["mock", "backend_mediated", "signed_url"]
CloudPaperUploadLifecycleStatus = Literal["intent_created", "upload_received", "processing", "ready", "failed", "blocked"]
CloudPaperAuthPreflightStatus = Literal[
    "ready",
    "mock_mode",
    "submission_bundle",
    "misconfigured",
    "dependency_missing",
    "auth_missing",
    "permission_denied",
    "unavailable",
]
CloudPaperAuthPreflightCheckStatus = Literal["ok", "warning", "error", "skipped"]
CloudPaperDownstreamLane = Literal[
    "meeting_pack",
    "chart_pack",
    "image_evidence",
    "method_comparison",
    "obsidian_export",
]
CloudPaperDownstreamCandidateKind = Literal["ocr_text", "table", "figure", "figure_analysis"]
CloudPaperCanonicalStatus = Literal["derived_noncanonical"]
CloudPaperDownstreamReviewStatus = Literal["review_pending", "review_approved", "review_rejected"]

_SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_required_text(value: str, *, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _clean_sha256(value: str, *, field_name: str) -> str:
    cleaned = _clean_required_text(value, field_name=field_name)
    if not _SHA256_RE.match(cleaned):
        raise ValueError(f"{field_name} must be a 64-character sha256 hex digest")
    return cleaned.lower()


class CloudPaperWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    severity: CloudPaperWarningSeverity = "info"

    @model_validator(mode="after")
    def normalize_warning(self):
        self.code = _clean_required_text(self.code, field_name="code")
        self.message = _clean_required_text(self.message, field_name="message")
        return self


class CloudPaperPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: CloudPaperRole
    can_read_page: bool = False
    can_read_pdf: bool = False
    can_hydrate: bool = False
    can_upload: bool = False
    can_delete: bool = False
    can_run_optional_ai: bool = False
    can_export: bool = False
    can_share: bool = False

    def allowed_actions_for_status(self, processing_status: CloudPaperProcessingStatus) -> list[CloudPaperAction]:
        if processing_status != "ready":
            return []

        actions: list[CloudPaperAction] = []
        if self.can_read_page:
            actions.append("read_page")
        if self.can_read_pdf:
            actions.append("read_pdf")
        if self.can_hydrate:
            actions.append("hydrate_download")
        if self.can_run_optional_ai:
            actions.append("run_optional_ai")
        if self.can_export:
            actions.append("export")
        if self.can_share:
            actions.append("share")
        if self.can_upload:
            actions.append("upload")
        if self.can_delete:
            actions.append("delete")
        return actions


class CloudPaperProvenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uploaded_by: str
    processor_name: str
    processor_version: str
    created_at: datetime
    source_pdf_sha256: str

    @model_validator(mode="after")
    def normalize_summary(self):
        self.uploaded_by = _clean_required_text(self.uploaded_by, field_name="uploaded_by")
        self.processor_name = _clean_required_text(self.processor_name, field_name="processor_name")
        self.processor_version = _clean_required_text(self.processor_version, field_name="processor_version")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uploaded_by: str
    processor_name: str
    processor_version: str
    model_name: str | None = None
    model_version: str | None = None
    created_at: datetime
    source_pdf_sha256: str

    @model_validator(mode="after")
    def normalize_provenance(self):
        self.uploaded_by = _clean_required_text(self.uploaded_by, field_name="uploaded_by")
        self.processor_name = _clean_required_text(self.processor_name, field_name="processor_name")
        self.processor_version = _clean_required_text(self.processor_version, field_name="processor_version")
        self.model_name = _clean_optional_text(self.model_name)
        self.model_version = _clean_optional_text(self.model_version)
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self

    def to_summary(self) -> CloudPaperProvenanceSummary:
        return CloudPaperProvenanceSummary(
            uploaded_by=self.uploaded_by,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            created_at=self.created_at,
            source_pdf_sha256=self.source_pdf_sha256,
        )


class CloudPaperHydrationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CloudPaperHydrationStatus = "not_hydrated"
    device_id: str | None = None
    local_bundle_ref: str | None = None
    hydrated_at: datetime | None = None
    source_pdf_sha256: str | None = None
    page_artifact_sha256: str | None = None

    @model_validator(mode="after")
    def normalize_hydration(self):
        self.device_id = _clean_optional_text(self.device_id)
        self.local_bundle_ref = _clean_optional_text(self.local_bundle_ref)
        if self.source_pdf_sha256 is not None:
            self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.page_artifact_sha256 is not None:
            self.page_artifact_sha256 = _clean_sha256(
                self.page_artifact_sha256,
                field_name="page_artifact_sha256",
            )
        return self

    def to_public(self) -> CloudPaperHydrationState:
        return CloudPaperHydrationState(
            status=self.status,
            device_id=None,
            local_bundle_ref=None,
            hydrated_at=self.hydrated_at,
            source_pdf_sha256=self.source_pdf_sha256,
            page_artifact_sha256=self.page_artifact_sha256,
        )


class CloudPaperLocalHydrationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_local_hydration_manifest.v1"] = "cloud_paper_local_hydration_manifest.v1"
    paper_id: str
    run_id: str
    device_id: str
    local_bundle_ref: str
    source_pdf_relative_path: str
    page_artifact_relative_path: str
    source_pdf_sha256: str
    page_artifact_sha256: str
    hydrated_at: datetime

    @model_validator(mode="after")
    def normalize_manifest(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.device_id = _clean_required_text(self.device_id, field_name="device_id")
        self.local_bundle_ref = _clean_relative_bundle_path(self.local_bundle_ref, field_name="local_bundle_ref")
        self.source_pdf_relative_path = _clean_relative_bundle_path(
            self.source_pdf_relative_path,
            field_name="source_pdf_relative_path",
        )
        self.page_artifact_relative_path = _clean_relative_bundle_path(
            self.page_artifact_relative_path,
            field_name="page_artifact_relative_path",
        )
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.page_artifact_sha256 = _clean_sha256(
            self.page_artifact_sha256,
            field_name="page_artifact_sha256",
        )
        return self

    def to_public_state(self) -> CloudPaperHydrationState:
        return CloudPaperHydrationState(
            status="hydrated",
            device_id=self.device_id,
            local_bundle_ref=self.local_bundle_ref,
            hydrated_at=self.hydrated_at,
            source_pdf_sha256=self.source_pdf_sha256,
            page_artifact_sha256=self.page_artifact_sha256,
        ).to_public()


class CloudPaperAccessContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    lab_id: str
    paper_lab_id: str
    role: CloudPaperRole
    authenticated: bool = False
    device_registered: bool = False
    session_approved: bool = False
    download_allowed_by_policy: bool = False

    @model_validator(mode="after")
    def normalize_context(self):
        self.actor_id = _clean_required_text(self.actor_id, field_name="actor_id")
        self.lab_id = _clean_required_text(self.lab_id, field_name="lab_id")
        self.paper_lab_id = _clean_required_text(self.paper_lab_id, field_name="paper_lab_id")
        return self


class CloudPaperBundleInternal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_bundle.v1"] = CLOUD_PAPER_BUNDLE_SCHEMA_VERSION
    paper_id: str
    lab_id: str
    cloud_source_id: str
    gcs_pdf_object_ref: str
    source_pdf_sha256: str
    source_pdf_size_bytes: int = Field(..., gt=0)
    source_pdf_content_type: str
    gcs_page_artifact_object_ref: str
    page_artifact_sha256: str
    page_schema_version: str
    run_id: str
    processing_status: CloudPaperProcessingStatus
    payload_class: CloudPaperPayloadClass
    created_at: datetime
    updated_at: datetime
    provenance: CloudPaperProvenance
    local_hydration: CloudPaperHydrationState | None = None
    warnings: list[CloudPaperWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_internal_bundle(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.lab_id = _clean_required_text(self.lab_id, field_name="lab_id")
        self.cloud_source_id = _clean_required_text(self.cloud_source_id, field_name="cloud_source_id")
        self.gcs_pdf_object_ref = _clean_required_text(self.gcs_pdf_object_ref, field_name="gcs_pdf_object_ref")
        self.gcs_page_artifact_object_ref = _clean_required_text(
            self.gcs_page_artifact_object_ref,
            field_name="gcs_page_artifact_object_ref",
        )
        if not self.gcs_pdf_object_ref.startswith("gs://"):
            raise ValueError("gcs_pdf_object_ref must be an opaque GCS object ref")
        if not self.gcs_page_artifact_object_ref.startswith("gs://"):
            raise ValueError("gcs_page_artifact_object_ref must be an opaque GCS object ref")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.page_artifact_sha256 = _clean_sha256(
            self.page_artifact_sha256,
            field_name="page_artifact_sha256",
        )
        self.source_pdf_content_type = _clean_required_text(
            self.source_pdf_content_type,
            field_name="source_pdf_content_type",
        )
        self.page_schema_version = _clean_required_text(self.page_schema_version, field_name="page_schema_version")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        if self.provenance.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance.source_pdf_sha256 must match source_pdf_sha256")
        return self

    def to_public(self, *, current_actor_permissions: CloudPaperPermissions) -> "CloudPaperBundlePublic":
        return derive_cloud_paper_public_bundle(self, current_actor_permissions=current_actor_permissions)


class CloudPaperBundlePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_bundle_public.v1"] = CLOUD_PAPER_BUNDLE_PUBLIC_SCHEMA_VERSION
    paper_id: str
    lab_id: str
    processing_status: CloudPaperProcessingStatus
    payload_class: CloudPaperPayloadClass
    page_schema_version: str | None = None
    run_id: str | None = None
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    permissions: CloudPaperPermissions
    provenance_summary: CloudPaperProvenanceSummary
    local_hydration: CloudPaperHydrationState | None = None
    allowed_actions: list[CloudPaperAction] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_public_bundle(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.lab_id = _clean_required_text(self.lab_id, field_name="lab_id")
        self.page_schema_version = _clean_optional_text(self.page_schema_version)
        self.run_id = _clean_optional_text(self.run_id)
        if self.local_hydration is not None:
            self.local_hydration = self.local_hydration.to_public()
        self.allowed_actions = _dedupe_actions(self.allowed_actions)
        expected_actions = self.permissions.allowed_actions_for_status(self.processing_status)
        if self.allowed_actions != expected_actions:
            raise ValueError("allowed_actions must match permissions and processing_status")
        return self


class CloudPaperListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_list.v1"] = "cloud_paper_list.v1"
    items: list[CloudPaperBundlePublic] = Field(default_factory=list)


class CloudPaperAuthPreflightCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    label: str
    status: CloudPaperAuthPreflightCheckStatus
    message: str
    remediation: str | None = None

    @model_validator(mode="after")
    def normalize_check(self):
        self.check_id = _clean_required_text(self.check_id, field_name="check_id")
        self.label = _clean_required_text(self.label, field_name="label")
        self.message = _clean_required_text(self.message, field_name="message")
        self.remediation = _clean_optional_text(self.remediation)
        return self


class CloudPaperAuthPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_auth_preflight.v1"] = "cloud_paper_auth_preflight.v1"
    status: CloudPaperAuthPreflightStatus
    adapter: Literal["mock", "gcs"]
    project_id: str | None = None
    firestore_collection: str | None = None
    credential_source: str
    checks: list[CloudPaperAuthPreflightCheck] = Field(default_factory=list)
    next_action_label: str
    setup_commands: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_response(self):
        self.project_id = _clean_optional_text(self.project_id)
        self.firestore_collection = _clean_optional_text(self.firestore_collection)
        self.credential_source = _clean_required_text(self.credential_source, field_name="credential_source")
        self.next_action_label = _clean_required_text(self.next_action_label, field_name="next_action_label")
        self.setup_commands = [_clean_required_text(command, field_name="setup_commands") for command in self.setup_commands]
        return self


class CloudPaperSearchBlockHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    page: int = Field(..., ge=1)
    kind: Literal["text", "table", "figure"]
    text_snippet: str
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_hit(self):
        self.block_id = _clean_required_text(self.block_id, field_name="block_id")
        self.text_snippet = _clean_required_text(self.text_snippet, field_name="text_snippet")
        self.metadata = _redact_public_metadata(self.metadata)
        return self


class CloudPaperSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle: CloudPaperBundlePublic
    matched_blocks: list[CloudPaperSearchBlockHit] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_search_hit(self):
        if self.bundle.processing_status != "ready":
            raise ValueError("cloud paper search hits must point to ready page artifacts")
        if "read_page" not in self.bundle.allowed_actions:
            raise ValueError("cloud paper search hits must be readable by the current actor")
        if not self.matched_blocks:
            raise ValueError("matched_blocks must not be empty")
        return self


class CloudPaperSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_search.v1"] = "cloud_paper_search.v1"
    query: str
    items: list[CloudPaperSearchHit] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_search_response(self):
        self.query = str(self.query or "").strip()
        return self


class CloudPaperUploadIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content_type: str = "application/pdf"
    source_pdf_sha256: str
    lab_id: str = "lab_001"

    @model_validator(mode="after")
    def normalize_request(self):
        self.filename = _clean_required_text(self.filename, field_name="filename")
        self.content_type = _clean_required_text(self.content_type, field_name="content_type")
        if self.content_type != "application/pdf":
            raise ValueError("content_type must be application/pdf")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.lab_id = _clean_required_text(self.lab_id, field_name="lab_id")
        return self


class CloudPaperUploadIntentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_intent_id: str
    paper_id: str
    upload_mode: CloudPaperUploadMode = "mock"
    expires_at: datetime

    @model_validator(mode="after")
    def normalize_response(self):
        self.upload_intent_id = _clean_required_text(self.upload_intent_id, field_name="upload_intent_id")
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        return self


class CloudPaperSourceUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    upload_status: Literal["upload_received"] = "upload_received"
    source_pdf_sha256: str
    source_pdf_size_bytes: int = Field(..., gt=0)
    content_type: str = "application/pdf"

    @model_validator(mode="after")
    def normalize_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.content_type = _clean_required_text(self.content_type, field_name="content_type")
        if self.content_type != "application/pdf":
            raise ValueError("content_type must be application/pdf")
        return self


class CloudPaperSourceObjectVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    exists: bool = False
    checksum_matches: bool = False
    source_pdf_sha256: str | None = None
    source_pdf_size_bytes: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def normalize_verification(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        if self.source_pdf_sha256 is not None:
            self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if not self.exists and self.checksum_matches:
            raise ValueError("checksum_matches cannot be true when source object does not exist")
        return self


class CloudPaperUploadCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_pdf_sha256: str

    @model_validator(mode="after")
    def normalize_request(self):
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperMetadataRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    upload_intent_id: str
    request: CloudPaperUploadIntentRequest
    upload_status: CloudPaperUploadLifecycleStatus = "intent_created"
    processing_status: CloudPaperProcessingStatus = "pending"
    warnings: list[CloudPaperWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_record(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.upload_intent_id = _clean_required_text(self.upload_intent_id, field_name="upload_intent_id")
        expected_processing_by_upload_status: dict[CloudPaperUploadLifecycleStatus, CloudPaperProcessingStatus] = {
            "intent_created": "pending",
            "upload_received": "pending",
            "processing": "running",
            "ready": "ready",
            "failed": "failed",
            "blocked": "blocked",
        }
        expected = expected_processing_by_upload_status[self.upload_status]
        if self.processing_status != expected:
            raise ValueError("processing_status must match upload_status")
        return self


class CloudPaperOperationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: Literal[
        "CLOUD_PAPER_BLOCKED",
        "CLOUD_PAPER_NOT_READY",
        "CLOUD_PAPER_NOT_FOUND",
        "CLOUD_PAPER_STORAGE_UNAVAILABLE",
        "CLOUD_PAPER_FORBIDDEN",
    ]
    message: str
    bundle: CloudPaperBundlePublic | None = None

    @model_validator(mode="after")
    def normalize_error(self):
        self.message = _clean_required_text(self.message, field_name="message")
        return self


class CloudPaperPageBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    page: int = Field(..., ge=1)
    kind: Literal["text", "table", "figure"]
    text: str | None = None
    bbox_pct: dict[str, float] | None = None
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_block(self):
        self.block_id = _clean_required_text(self.block_id, field_name="block_id")
        self.text = _clean_optional_text(self.text)
        return self


class CloudPaperPageBlockInternal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    page: int = Field(..., ge=1)
    kind: Literal["text", "table", "figure"]
    text: str | None = None
    bbox_pct: dict[str, float] | None = None
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)
    worker_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_block(self):
        self.block_id = _clean_required_text(self.block_id, field_name="block_id")
        self.text = _clean_optional_text(self.text)
        return self

    def to_public(self) -> CloudPaperPageBlock:
        return CloudPaperPageBlock(
            block_id=self.block_id,
            page=self.page,
            kind=self.kind,
            text=self.text,
            bbox_pct=self.bbox_pct,
            payload_class=self.payload_class,
            metadata=_redact_public_metadata(self.metadata),
        )


class CloudPaperPageArtifactPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_page_artifact_public.v1"] = "cloud_page_artifact_public.v1"
    paper_id: str
    run_id: str
    page_schema_version: str
    source_pdf_sha256: str
    blocks: list[CloudPaperPageBlock] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_artifact(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.page_schema_version = _clean_required_text(self.page_schema_version, field_name="page_schema_version")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperSummarySourceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    page: int = Field(..., ge=1)
    kind: Literal["text", "table", "figure"]
    text_snippet: str
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_source_block(self):
        self.block_id = _clean_required_text(self.block_id, field_name="block_id")
        self.text_snippet = _clean_required_text(self.text_snippet, field_name="text_snippet")
        self.metadata = _redact_public_metadata(self.metadata)
        return self


class CloudPaperSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_summary.v1"] = "cloud_paper_summary.v1"
    paper_id: str
    run_id: str
    input_source: Literal["cloud_page_artifact"] = "cloud_page_artifact"
    summary_kind: Literal["extractive_bridge"] = "extractive_bridge"
    review_status: Literal["draft"] = "draft"
    payload_class: CloudPaperPayloadClass = "local_only"
    summary_text: str
    source_blocks: list[CloudPaperSummarySourceBlock] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_summary_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.summary_text = _clean_required_text(self.summary_text, field_name="summary_text")
        return self


class CloudPaperDerivedArtifactSourceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=1)
    source_pdf_sha256: str
    block_id: str | None = None
    bbox_pct: dict[str, float] | None = None

    @model_validator(mode="after")
    def normalize_source_locator(self):
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.block_id = _clean_optional_text(self.block_id)
        return self


class CloudPaperDerivedArtifactOcrBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr_block_id: str
    text: str
    confidence: float = Field(..., ge=0, le=1)
    source: CloudPaperDerivedArtifactSourceLocator
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_ocr_block(self):
        self.ocr_block_id = _clean_required_text(self.ocr_block_id, field_name="ocr_block_id")
        self.text = _clean_required_text(self.text, field_name="text")
        self.metadata = _redact_public_metadata(self.metadata)
        return self


class CloudPaperDerivedArtifactTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str
    page: int = Field(..., ge=1)
    caption: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)
    source: CloudPaperDerivedArtifactSourceLocator
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_table(self):
        self.table_id = _clean_required_text(self.table_id, field_name="table_id")
        self.caption = _clean_optional_text(self.caption)
        self.columns = [_clean_required_text(column, field_name="columns") for column in self.columns]
        self.rows = [[str(cell).strip() for cell in row] for row in self.rows]
        self.metadata = _redact_public_metadata(self.metadata)
        return self


class CloudPaperDerivedArtifactFigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figure_id: str
    page: int = Field(..., ge=1)
    caption: str | None = None
    bbox_pct: dict[str, float] | None = None
    image_available: bool = False
    image_route: str | None = None
    confidence: float = Field(..., ge=0, le=1)
    source: CloudPaperDerivedArtifactSourceLocator
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_figure(self):
        self.figure_id = _clean_required_text(self.figure_id, field_name="figure_id")
        self.caption = _clean_optional_text(self.caption)
        self.image_route = _clean_optional_text(self.image_route)
        if self.image_route is not None and not self.image_route.startswith("/api/cloud/papers/"):
            raise ValueError("image_route must be a same-origin cloud paper API route")
        self.metadata = _redact_public_metadata(self.metadata)
        return self


class CloudPaperDerivedArtifactFigureAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    figure_id: str
    page: int = Field(..., ge=1)
    summary: str
    confidence: float = Field(..., ge=0, le=1)
    source: CloudPaperDerivedArtifactSourceLocator
    payload_class: CloudPaperPayloadClass = "local_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_figure_analysis(self):
        self.analysis_id = _clean_required_text(self.analysis_id, field_name="analysis_id")
        self.figure_id = _clean_required_text(self.figure_id, field_name="figure_id")
        self.summary = _clean_required_text(self.summary, field_name="summary")
        self.metadata = _redact_public_metadata(self.metadata)
        return self


class CloudPaperDerivedArtifactsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_derived_artifacts.v1"] = "cloud_paper_derived_artifacts.v1"
    paper_id: str
    run_id: str
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    ocr_blocks: list[CloudPaperDerivedArtifactOcrBlock] = Field(default_factory=list)
    tables: list[CloudPaperDerivedArtifactTable] = Field(default_factory=list)
    figures: list[CloudPaperDerivedArtifactFigure] = Field(default_factory=list)
    figure_analyses: list[CloudPaperDerivedArtifactFigureAnalysis] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_derived_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperDownstreamArtifactCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    kind: CloudPaperDownstreamCandidateKind
    paper_id: str
    run_id: str
    payload_class: CloudPaperPayloadClass = "local_only"
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    allowed_lanes: list[CloudPaperDownstreamLane] = Field(default_factory=list, min_length=1)
    source: CloudPaperDerivedArtifactSourceLocator
    title: str
    text: str | None = None
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    image_route: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_candidate(self):
        self.candidate_id = _clean_required_text(self.candidate_id, field_name="candidate_id")
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.title = _clean_required_text(self.title, field_name="title")
        self.text = _clean_optional_text(self.text)
        self.allowed_lanes = _dedupe_downstream_lanes(self.allowed_lanes)
        self.table_columns = [_clean_required_text(column, field_name="table_columns") for column in self.table_columns]
        self.table_rows = [[str(cell).strip() for cell in row] for row in self.table_rows]
        self.image_route = _clean_optional_text(self.image_route)
        if self.image_route is not None and not self.image_route.startswith("/api/cloud/papers/"):
            raise ValueError("image_route must be a same-origin cloud paper API route")
        if self.provenance_summary.source_pdf_sha256 != self.source.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source.source_pdf_sha256")
        return self


class CloudPaperDownstreamAdapterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_downstream_adapter.v1"] = "cloud_paper_downstream_adapter.v1"
    paper_id: str
    run_id: str
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    candidates: list[CloudPaperDownstreamArtifactCandidate] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_adapter_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.provenance_summary.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source_pdf_sha256")
        for candidate in self.candidates:
            if candidate.paper_id != self.paper_id:
                raise ValueError("candidate.paper_id must match response paper_id")
            if candidate.run_id != self.run_id:
                raise ValueError("candidate.run_id must match response run_id")
            if candidate.source.source_pdf_sha256 != self.source_pdf_sha256:
                raise ValueError("candidate source checksum must match response source_pdf_sha256")
        return self


class CloudPaperObsidianExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    existing_markdown: str | None = None


class CloudPaperObsidianSectionMarkers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str

    @model_validator(mode="after")
    def normalize_markers(self):
        self.start = _clean_required_text(self.start, field_name="start")
        self.end = _clean_required_text(self.end, field_name="end")
        return self


class CloudPaperObsidianExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_obsidian_export.v1"] = "cloud_paper_obsidian_export.v1"
    paper_id: str
    run_id: str
    artifact_id: str
    export_status: Literal["prepared"] = "prepared"
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    review_status: CloudPaperDownstreamReviewStatus = "review_pending"
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    section_markers: CloudPaperObsidianSectionMarkers
    section_markdown: str
    note_markdown: str
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_export_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.artifact_id = _clean_required_text(self.artifact_id, field_name="artifact_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.section_markdown = _clean_required_text(self.section_markdown, field_name="section_markdown")
        self.note_markdown = _clean_required_text(self.note_markdown, field_name="note_markdown")
        if self.provenance_summary.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source_pdf_sha256")
        return self


class CloudPaperDownstreamArtifactRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lanes: list[CloudPaperDownstreamLane] = Field(
        default_factory=lambda: [
            "meeting_pack",
            "chart_pack",
            "image_evidence",
            "method_comparison",
            "obsidian_export",
        ],
        min_length=1,
    )

    @model_validator(mode="after")
    def normalize_request(self):
        self.lanes = _dedupe_downstream_lanes(self.lanes)
        return self


class CloudPaperDownstreamArtifactReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: Literal["review_approved", "review_rejected"]
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.reviewer_note = _clean_optional_text(self.reviewer_note)
        return self


class CloudPaperDownstreamArtifactReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    artifact_id: str
    review_status: Literal["review_approved", "review_rejected"]
    reviewer_role: CloudPaperRole
    reviewed_at: datetime
    reviewer_note_recorded: bool = False

    @model_validator(mode="after")
    def normalize_event(self):
        self.event_id = _clean_required_text(self.event_id, field_name="event_id")
        self.artifact_id = _clean_required_text(self.artifact_id, field_name="artifact_id")
        return self


class CloudPaperRegisteredDownstreamArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    lane: CloudPaperDownstreamLane
    candidate_ids: list[str] = Field(default_factory=list, min_length=1)
    candidate_count: int = Field(..., ge=1)
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    review_status: CloudPaperDownstreamReviewStatus = "review_pending"
    review_events: list[CloudPaperDownstreamArtifactReviewEvent] = Field(default_factory=list)
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"

    @model_validator(mode="after")
    def normalize_registered_artifact(self):
        self.artifact_id = _clean_required_text(self.artifact_id, field_name="artifact_id")
        self.candidate_ids = [_clean_required_text(candidate_id, field_name="candidate_ids") for candidate_id in self.candidate_ids]
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.candidate_count != len(self.candidate_ids):
            raise ValueError("candidate_count must match candidate_ids")
        return self


class CloudPaperDownstreamArtifactRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_downstream_artifact_registration.v1"] = (
        "cloud_paper_downstream_artifact_registration.v1"
    )
    paper_id: str
    run_id: str
    registration_status: Literal["registered"] = "registered"
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    review_status: CloudPaperDownstreamReviewStatus = "review_pending"
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    registered_artifacts: list[CloudPaperRegisteredDownstreamArtifact] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_registration_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.provenance_summary.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source_pdf_sha256")
        for artifact in self.registered_artifacts:
            if artifact.source_pdf_sha256 != self.source_pdf_sha256:
                raise ValueError("registered artifact checksum must match response source_pdf_sha256")
        return self


class CloudPaperDownstreamArtifactRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_downstream_artifact_registry.v1"] = (
        "cloud_paper_downstream_artifact_registry.v1"
    )
    paper_id: str
    run_id: str
    registry_status: Literal["empty", "available"] = "empty"
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    review_status: CloudPaperDownstreamReviewStatus = "review_pending"
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    registrations: list[CloudPaperDownstreamArtifactRegistrationResponse] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_registry_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.provenance_summary.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source_pdf_sha256")
        expected_status = "available" if self.registrations else "empty"
        if self.registry_status != expected_status:
            raise ValueError("registry_status must match registrations")
        for registration in self.registrations:
            if registration.paper_id != self.paper_id:
                raise ValueError("registration.paper_id must match registry paper_id")
            if registration.run_id != self.run_id:
                raise ValueError("registration.run_id must match registry run_id")
            if registration.source_pdf_sha256 != self.source_pdf_sha256:
                raise ValueError("registration checksum must match registry source_pdf_sha256")
        return self


class CloudPaperDownstreamPromotionBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["registry_empty", "review_pending", "review_rejected"]
    message: str
    artifact_id: str | None = None
    lane: CloudPaperDownstreamLane | None = None

    @model_validator(mode="after")
    def normalize_blocker(self):
        self.message = _clean_required_text(self.message, field_name="message")
        self.artifact_id = _clean_optional_text(self.artifact_id)
        return self


class CloudPaperDownstreamPromotionReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_downstream_promotion_readiness.v1"] = (
        "cloud_paper_downstream_promotion_readiness.v1"
    )
    paper_id: str
    run_id: str
    promotion_status: Literal["eligible", "blocked"] = "blocked"
    eligible: bool = False
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    review_status: CloudPaperDownstreamReviewStatus = "review_pending"
    total_artifact_count: int = Field(..., ge=0)
    approved_artifact_count: int = Field(..., ge=0)
    pending_artifact_count: int = Field(..., ge=0)
    rejected_artifact_count: int = Field(..., ge=0)
    blockers: list[CloudPaperDownstreamPromotionBlocker] = Field(default_factory=list)
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_readiness(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.provenance_summary.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source_pdf_sha256")
        if self.total_artifact_count != (
            self.approved_artifact_count + self.pending_artifact_count + self.rejected_artifact_count
        ):
            raise ValueError("artifact counts must sum to total_artifact_count")
        expected_eligible = self.total_artifact_count > 0 and not self.blockers
        if self.eligible != expected_eligible:
            raise ValueError("eligible must match blockers and total_artifact_count")
        expected_status = "eligible" if self.eligible else "blocked"
        if self.promotion_status != expected_status:
            raise ValueError("promotion_status must match eligible")
        return self


class CloudPaperDownstreamPromotionPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    lane: CloudPaperDownstreamLane
    candidate_ids: list[str] = Field(default_factory=list, min_length=1)
    candidate_count: int = Field(..., ge=1)
    review_status: Literal["review_approved"] = "review_approved"
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    promotion_action: Literal["prepare_canonical_state_promotion"] = "prepare_canonical_state_promotion"
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"

    @model_validator(mode="after")
    def normalize_plan_item(self):
        self.artifact_id = _clean_required_text(self.artifact_id, field_name="artifact_id")
        self.candidate_ids = [_clean_required_text(candidate_id, field_name="candidate_ids") for candidate_id in self.candidate_ids]
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.candidate_count != len(self.candidate_ids):
            raise ValueError("candidate_count must match candidate_ids")
        return self


class CloudPaperDownstreamPromotionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_downstream_promotion_plan.v1"] = (
        "cloud_paper_downstream_promotion_plan.v1"
    )
    paper_id: str
    run_id: str
    plan_status: Literal["ready", "blocked"] = "blocked"
    dry_run: Literal[True] = True
    mutation_applied: Literal[False] = False
    promotion_target: Literal["canonical_structured_state"] = "canonical_structured_state"
    canonical_status: CloudPaperCanonicalStatus = "derived_noncanonical"
    review_status: CloudPaperDownstreamReviewStatus = "review_pending"
    total_artifact_count: int = Field(..., ge=0)
    approved_artifact_count: int = Field(..., ge=0)
    pending_artifact_count: int = Field(..., ge=0)
    rejected_artifact_count: int = Field(..., ge=0)
    blockers: list[CloudPaperDownstreamPromotionBlocker] = Field(default_factory=list)
    promotion_items: list[CloudPaperDownstreamPromotionPlanItem] = Field(default_factory=list)
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_plan(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        if self.provenance_summary.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance_summary.source_pdf_sha256 must match source_pdf_sha256")
        if self.total_artifact_count != (
            self.approved_artifact_count + self.pending_artifact_count + self.rejected_artifact_count
        ):
            raise ValueError("artifact counts must sum to total_artifact_count")
        expected_status = "blocked" if self.blockers else "ready"
        if self.plan_status != expected_status:
            raise ValueError("plan_status must match blockers")
        if self.plan_status == "blocked" and self.promotion_items:
            raise ValueError("blocked promotion plans must not include promotion_items")
        if self.plan_status == "ready" and len(self.promotion_items) != self.approved_artifact_count:
            raise ValueError("ready promotion plan item count must match approved_artifact_count")
        for item in self.promotion_items:
            if item.source_pdf_sha256 != self.source_pdf_sha256:
                raise ValueError("promotion item checksum must match plan source_pdf_sha256")
        return self


class CloudPaperOcrResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_ocr.v1"] = "cloud_paper_ocr.v1"
    paper_id: str
    run_id: str
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    ocr_blocks: list[CloudPaperDerivedArtifactOcrBlock] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_ocr_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperTablesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_tables.v1"] = "cloud_paper_tables.v1"
    paper_id: str
    run_id: str
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    tables: list[CloudPaperDerivedArtifactTable] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_tables_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperFiguresResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_figures.v1"] = "cloud_paper_figures.v1"
    paper_id: str
    run_id: str
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    figures: list[CloudPaperDerivedArtifactFigure] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_figures_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperFigureAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_figure_analysis.v1"] = "cloud_paper_figure_analysis.v1"
    paper_id: str
    run_id: str
    figure_id: str
    source_pdf_sha256: str
    payload_class: CloudPaperPayloadClass = "local_only"
    analyses: list[CloudPaperDerivedArtifactFigureAnalysis] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance_summary: CloudPaperProvenanceSummary

    @model_validator(mode="after")
    def normalize_figure_analysis_response(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.figure_id = _clean_required_text(self.figure_id, field_name="figure_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        return self


class CloudPaperDerivedArtifactInternal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_derived_artifacts_internal.v1"] = (
        "cloud_paper_derived_artifacts_internal.v1"
    )
    paper_id: str
    run_id: str
    source_pdf_sha256: str
    gcs_derived_artifact_object_ref: str
    payload_class: CloudPaperPayloadClass = "local_only"
    ocr_blocks: list[CloudPaperDerivedArtifactOcrBlock] = Field(default_factory=list)
    tables: list[CloudPaperDerivedArtifactTable] = Field(default_factory=list)
    figures: list[CloudPaperDerivedArtifactFigure] = Field(default_factory=list)
    figure_analyses: list[CloudPaperDerivedArtifactFigureAnalysis] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance: CloudPaperProvenance
    worker_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_derived_internal(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.gcs_derived_artifact_object_ref = _clean_required_text(
            self.gcs_derived_artifact_object_ref,
            field_name="gcs_derived_artifact_object_ref",
        )
        if not self.gcs_derived_artifact_object_ref.startswith("gs://"):
            raise ValueError("gcs_derived_artifact_object_ref must be an opaque GCS object ref")
        if self.provenance.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance.source_pdf_sha256 must match source_pdf_sha256")
        return self

    def to_public(self) -> CloudPaperDerivedArtifactsResponse:
        return derive_cloud_paper_public_derived_artifacts(self)


class CloudPaperPageArtifactStorageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    run_id: str
    page_schema_version: str
    page_artifact_sha256: str
    page_artifact_size_bytes: int = Field(..., gt=0)

    @model_validator(mode="after")
    def normalize_storage_result(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.page_schema_version = _clean_required_text(self.page_schema_version, field_name="page_schema_version")
        self.page_artifact_sha256 = _clean_sha256(
            self.page_artifact_sha256,
            field_name="page_artifact_sha256",
        )
        return self


class CloudPaperDerivedArtifactStorageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    run_id: str
    derived_artifact_sha256: str
    derived_artifact_size_bytes: int = Field(..., gt=0)

    @model_validator(mode="after")
    def normalize_storage_result(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.derived_artifact_sha256 = _clean_sha256(
            self.derived_artifact_sha256,
            field_name="derived_artifact_sha256",
        )
        return self


class CloudPaperPageArtifactInternal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_page_artifact.v1"] = "cloud_page_artifact.v1"
    paper_id: str
    run_id: str
    page_schema_version: str
    source_pdf_sha256: str
    gcs_page_artifact_object_ref: str
    blocks: list[CloudPaperPageBlockInternal] = Field(default_factory=list)
    warnings: list[CloudPaperWarning] = Field(default_factory=list)
    provenance: CloudPaperProvenance
    worker_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_artifact(self):
        self.paper_id = _clean_required_text(self.paper_id, field_name="paper_id")
        self.run_id = _clean_required_text(self.run_id, field_name="run_id")
        self.page_schema_version = _clean_required_text(self.page_schema_version, field_name="page_schema_version")
        self.source_pdf_sha256 = _clean_sha256(self.source_pdf_sha256, field_name="source_pdf_sha256")
        self.gcs_page_artifact_object_ref = _clean_required_text(
            self.gcs_page_artifact_object_ref,
            field_name="gcs_page_artifact_object_ref",
        )
        if not self.gcs_page_artifact_object_ref.startswith("gs://"):
            raise ValueError("gcs_page_artifact_object_ref must be an opaque GCS object ref")
        if self.provenance.source_pdf_sha256 != self.source_pdf_sha256:
            raise ValueError("provenance.source_pdf_sha256 must match source_pdf_sha256")
        return self

    def to_public(self) -> CloudPaperPageArtifactPublic:
        return derive_cloud_page_artifact_public(self)


class CloudPaperToolCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    label: str
    action: CloudPaperAction
    allowed_payload_classes: list[CloudPaperPayloadClass]
    requires_hydrated_bundle: bool = False

    @model_validator(mode="after")
    def normalize_capability(self):
        self.tool_id = _clean_required_text(self.tool_id, field_name="tool_id")
        self.label = _clean_required_text(self.label, field_name="label")
        self.allowed_payload_classes = list(dict.fromkeys(self.allowed_payload_classes))
        if not self.allowed_payload_classes:
            raise ValueError("allowed_payload_classes must not be empty")
        return self


class CloudPaperClientRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cloud_paper_client_runtime_config.v1"] = "cloud_paper_client_runtime_config.v1"
    api_base_path: str = "/api"
    cloud_adapter: Literal["mock", "gcs"] = "mock"
    gcs_configured: bool = False
    enabled_contracts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_config(self):
        self.api_base_path = _clean_required_text(self.api_base_path, field_name="api_base_path")
        if not self.api_base_path.startswith("/"):
            raise ValueError("api_base_path must be a same-origin path")
        self.enabled_contracts = list(dict.fromkeys(self.enabled_contracts))
        return self


def _dedupe_actions(actions: list[CloudPaperAction]) -> list[CloudPaperAction]:
    ordered: list[CloudPaperAction] = []
    seen: set[str] = set()
    for action in actions:
        if action in seen:
            continue
        ordered.append(action)
        seen.add(action)
    return ordered


def _dedupe_downstream_lanes(lanes: list[CloudPaperDownstreamLane]) -> list[CloudPaperDownstreamLane]:
    ordered: list[CloudPaperDownstreamLane] = []
    seen: set[str] = set()
    for lane in lanes:
        if lane in seen:
            continue
        ordered.append(lane)
        seen.add(lane)
    if not ordered:
        raise ValueError("allowed_lanes must not be empty")
    return ordered


def _clean_relative_bundle_path(value: str, *, field_name: str) -> str:
    cleaned = _clean_required_text(value, field_name=field_name)
    if cleaned.startswith("/") or cleaned.startswith("~") or "://" in cleaned or ".." in cleaned.split("/"):
        raise ValueError(f"{field_name} must be a relative local bundle path")
    return cleaned


def _redact_public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    private_fragments = ("gcs", "signed_url", "service_account", "local_path", "worker")
    public_metadata: dict[str, Any] = {}
    for key, value in metadata.items():
        normalized_key = str(key).lower()
        if normalized_key.startswith("_") or any(fragment in normalized_key for fragment in private_fragments):
            continue
        if _metadata_value_contains_private_ref(value):
            continue
        public_metadata[key] = value
    return public_metadata


def _metadata_value_contains_private_ref(value: Any) -> bool:
    private_value_fragments = ("gs://", "signed", "service_account", "/Users/")
    if isinstance(value, str):
        return any(fragment in value for fragment in private_value_fragments)
    if isinstance(value, dict):
        return any(
            _metadata_value_contains_private_ref(key) or _metadata_value_contains_private_ref(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_metadata_value_contains_private_ref(item) for item in value)
    return False


def derive_cloud_page_artifact_public(artifact: CloudPaperPageArtifactInternal) -> CloudPaperPageArtifactPublic:
    return CloudPaperPageArtifactPublic(
        paper_id=artifact.paper_id,
        run_id=artifact.run_id,
        page_schema_version=artifact.page_schema_version,
        source_pdf_sha256=artifact.source_pdf_sha256,
        blocks=[block.to_public() for block in artifact.blocks],
        warnings=artifact.warnings,
        provenance_summary=artifact.provenance.to_summary(),
    )


def derive_cloud_paper_public_derived_artifacts(
    artifact: CloudPaperDerivedArtifactInternal,
) -> CloudPaperDerivedArtifactsResponse:
    return CloudPaperDerivedArtifactsResponse(
        paper_id=artifact.paper_id,
        run_id=artifact.run_id,
        source_pdf_sha256=artifact.source_pdf_sha256,
        payload_class=artifact.payload_class,
        ocr_blocks=artifact.ocr_blocks,
        tables=artifact.tables,
        figures=artifact.figures,
        figure_analyses=artifact.figure_analyses,
        warnings=artifact.warnings,
        provenance_summary=artifact.provenance.to_summary(),
    )


def derive_cloud_paper_public_bundle(
    bundle: CloudPaperBundleInternal,
    *,
    current_actor_permissions: CloudPaperPermissions,
) -> CloudPaperBundlePublic:
    return CloudPaperBundlePublic(
        paper_id=bundle.paper_id,
        lab_id=bundle.lab_id,
        processing_status=bundle.processing_status,
        payload_class=bundle.payload_class,
        page_schema_version=bundle.page_schema_version if bundle.processing_status == "ready" else None,
        run_id=bundle.run_id,
        warnings=bundle.warnings,
        permissions=current_actor_permissions,
        provenance_summary=bundle.provenance.to_summary(),
        local_hydration=bundle.local_hydration.to_public() if bundle.local_hydration is not None else None,
        allowed_actions=current_actor_permissions.allowed_actions_for_status(bundle.processing_status),
    )
