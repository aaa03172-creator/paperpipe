from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ImageSourceKind = Literal["local_file", "external_image_ref"]
ImageWarningSeverity = Literal["info", "warning", "error"]
ImageDerivedOutputKind = Literal[
    "thumbnail",
    "representative_crop",
    "overlay",
    "measurement_export",
    "other",
]
ImageHandoffTargetKind = Literal["napari", "omero", "other_local_viewer"]
ChecksumAlgorithm = Literal["md5", "sha1", "sha256", "sha512"]
ImageArtifactKind = Literal["view_state_json", "handoff_json", "derived_file"]


class ImageChecksum(BaseModel):
    algorithm: ChecksumAlgorithm = "sha256"
    value: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_checksum(self):
        self.value = self.value.strip()
        return self


class ImageSourceRef(BaseModel):
    source_kind: ImageSourceKind
    local_path: str | None = None
    external_ref: str | None = None
    source_label: str | None = None

    @model_validator(mode="after")
    def validate_source_ref(self):
        if self.local_path is not None:
            self.local_path = self.local_path.strip() or None
        if self.external_ref is not None:
            self.external_ref = self.external_ref.strip() or None
        if self.source_label is not None:
            self.source_label = self.source_label.strip() or None

        if self.source_kind == "local_file":
            if not self.local_path:
                raise ValueError("local_file source refs require local_path")
            if self.external_ref is not None:
                raise ValueError("local_file source refs must not include external_ref")
            return self
        if self.source_kind == "external_image_ref":
            if not self.external_ref:
                raise ValueError("external_image_ref source refs require external_ref")
            if self.local_path is not None:
                raise ValueError("external_image_ref source refs must not include local_path")
            return self
        return self


class ImageMetadata(BaseModel):
    filename: str | None = None
    source_size_bytes: int | None = Field(default=None, ge=0)
    width_px: int | None = Field(default=None, ge=1)
    height_px: int | None = Field(default=None, ge=1)
    channel_count: int | None = Field(default=None, ge=1)
    z_slices: int | None = Field(default=None, ge=1)
    t_slices: int | None = Field(default=None, ge=1)
    modality: str | None = None
    acquisition_note: str | None = None
    source_created_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_metadata(self):
        if self.filename is not None:
            self.filename = self.filename.strip() or None
        if self.modality is not None:
            self.modality = self.modality.strip() or None
        if self.acquisition_note is not None:
            self.acquisition_note = self.acquisition_note.strip() or None
        return self


class ImageViewport(BaseModel):
    x: float = 0
    y: float = 0
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)


class ImageChannelRange(BaseModel):
    channel_id: str = Field(..., min_length=1)
    min_value: float | None = None
    max_value: float | None = None

    @model_validator(mode="after")
    def validate_range(self):
        self.channel_id = self.channel_id.strip()
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("ImageChannelRange min_value must be <= max_value")
        return self


class ImageViewState(BaseModel):
    active_channels: list[str] = Field(default_factory=list)
    intensity_ranges: list[ImageChannelRange] = Field(default_factory=list)
    z_index: int | None = Field(default=None, ge=0)
    t_index: int | None = Field(default=None, ge=0)
    zoom_level: float | None = Field(default=None, gt=0)
    viewport: ImageViewport | None = None
    visible_overlays: list[str] = Field(default_factory=list)
    selected_region_labels: list[str] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_view_state(self):
        self.active_channels = [value.strip() for value in self.active_channels if value.strip()]
        self.visible_overlays = [value.strip() for value in self.visible_overlays if value.strip()]
        self.selected_region_labels = [value.strip() for value in self.selected_region_labels if value.strip()]
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ImageArtifactRef(BaseModel):
    kind: ImageArtifactKind
    path: str = Field(..., min_length=1)
    mime_type: str | None = None

    @model_validator(mode="after")
    def validate_relative_path(self):
        normalized = self.path.strip()
        if not normalized:
            raise ValueError("ImageArtifactRef.path must be non-empty")
        if Path(normalized).is_absolute():
            raise ValueError("ImageArtifactRef.path must be image-evidence-relative")
        self.path = normalized
        if self.mime_type is not None:
            self.mime_type = self.mime_type.strip() or None
        return self


class ImageDerivedOutput(BaseModel):
    derived_output_id: str = Field(..., min_length=1)
    kind: ImageDerivedOutputKind
    source_image_evidence_id: str = Field(..., min_length=1)
    created_by: str = Field(..., min_length=1)
    created_at: datetime
    tool_name: str = Field(..., min_length=1)
    tool_version: str | None = None
    bundle_ref: ImageArtifactRef | None = None
    external_ref: str | None = None
    view_state_ref: ImageArtifactRef | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_output(self):
        self.derived_output_id = self.derived_output_id.strip()
        self.source_image_evidence_id = self.source_image_evidence_id.strip()
        self.created_by = self.created_by.strip()
        self.tool_name = self.tool_name.strip()
        if self.tool_version is not None:
            self.tool_version = self.tool_version.strip() or None
        if self.external_ref is not None:
            self.external_ref = self.external_ref.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None

        if (self.bundle_ref is None) == (self.external_ref is None):
            raise ValueError("ImageDerivedOutput requires exactly one of bundle_ref or external_ref")
        if self.bundle_ref is not None and self.bundle_ref.kind != "derived_file":
            raise ValueError("ImageDerivedOutput.bundle_ref must use kind=derived_file")
        if self.view_state_ref is not None and self.view_state_ref.kind != "view_state_json":
            raise ValueError("ImageDerivedOutput.view_state_ref must use kind=view_state_json")
        return self


class ImageClaimLink(BaseModel):
    claim_id: str = Field(..., min_length=1)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_link(self):
        self.claim_id = self.claim_id.strip()
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ImageArtifactLink(BaseModel):
    artifact_kind: str = Field(..., min_length=1)
    artifact_id: str = Field(..., min_length=1)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_link(self):
        self.artifact_kind = self.artifact_kind.strip()
        self.artifact_id = self.artifact_id.strip()
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ImageHandoffTarget(BaseModel):
    target: ImageHandoffTargetKind
    openable_ref: str = Field(..., min_length=1)
    view_state_ref: ImageArtifactRef | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_target(self):
        self.openable_ref = self.openable_ref.strip()
        if self.view_state_ref is not None and self.view_state_ref.kind != "view_state_json":
            raise ValueError("ImageHandoffTarget.view_state_ref must use kind=view_state_json")
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class ImageWarning(BaseModel):
    code: str = Field(..., min_length=1)
    severity: ImageWarningSeverity = "warning"
    message: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_warning(self):
        self.code = self.code.strip()
        self.message = self.message.strip()
        return self


class ImageEvidenceRequest(BaseModel):
    image_evidence_id: str | None = None
    title: str | None = None
    paper_id: str | None = None
    paper_slug: str | None = None
    source_ref: ImageSourceRef
    content_format: str = Field(..., min_length=1)
    checksum: ImageChecksum | None = None
    metadata: ImageMetadata = Field(default_factory=ImageMetadata)
    view_state: ImageViewState | None = None
    linked_claim_refs: list[ImageClaimLink] = Field(default_factory=list)
    linked_artifact_refs: list[ImageArtifactLink] = Field(default_factory=list)
    derived_outputs: list[ImageDerivedOutput] = Field(default_factory=list)
    handoff_targets: list[ImageHandoffTarget] = Field(default_factory=list)
    warnings: list[ImageWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_request(self):
        if self.image_evidence_id is not None:
            self.image_evidence_id = self.image_evidence_id.strip() or None
        if self.title is not None:
            self.title = self.title.strip() or None
        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.paper_slug is not None:
            self.paper_slug = self.paper_slug.strip() or None
        self.content_format = self.content_format.strip()
        return self


class ImageEvidence(BaseModel):
    image_evidence_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    created_at: datetime
    paper_id: str | None = None
    paper_slug: str | None = None
    source_ref: ImageSourceRef
    content_format: str = Field(..., min_length=1)
    checksum: ImageChecksum | None = None
    metadata: ImageMetadata = Field(default_factory=ImageMetadata)
    view_state_ref: ImageArtifactRef | None = None
    handoff_ref: ImageArtifactRef | None = None
    derived_outputs: list[ImageDerivedOutput] = Field(default_factory=list)
    linked_claim_refs: list[ImageClaimLink] = Field(default_factory=list)
    linked_artifact_refs: list[ImageArtifactLink] = Field(default_factory=list)
    warnings: list[ImageWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bundle(self):
        self.image_evidence_id = self.image_evidence_id.strip()
        self.title = self.title.strip()
        self.content_format = self.content_format.strip()
        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.paper_slug is not None:
            self.paper_slug = self.paper_slug.strip() or None
        if self.view_state_ref is not None and self.view_state_ref.kind != "view_state_json":
            raise ValueError("ImageEvidence.view_state_ref must use kind=view_state_json")
        if self.handoff_ref is not None and self.handoff_ref.kind != "handoff_json":
            raise ValueError("ImageEvidence.handoff_ref must use kind=handoff_json")
        derived_output_ids = [output.derived_output_id for output in self.derived_outputs]
        if len(set(derived_output_ids)) != len(derived_output_ids):
            raise ValueError("ImageEvidence.derived_outputs must not contain duplicate derived_output_id values")
        return self


class ImageEvidenceSummary(BaseModel):
    image_evidence_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    paper_id: str | None = None
    paper_slug: str | None = None
    content_format: str = Field(..., min_length=1)
    created_at: datetime
    derived_output_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    has_view_state: bool = False
    has_handoff: bool = False


def summarize_image_evidence(image_evidence: ImageEvidence) -> ImageEvidenceSummary:
    return ImageEvidenceSummary(
        image_evidence_id=image_evidence.image_evidence_id,
        title=image_evidence.title,
        paper_id=image_evidence.paper_id,
        paper_slug=image_evidence.paper_slug,
        content_format=image_evidence.content_format,
        created_at=image_evidence.created_at,
        derived_output_count=len(image_evidence.derived_outputs),
        warning_count=len(image_evidence.warnings),
        has_view_state=image_evidence.view_state_ref is not None,
        has_handoff=image_evidence.handoff_ref is not None,
    )


class ImageEvidenceResponse(BaseModel):
    image_evidence: ImageEvidence
    view_state: ImageViewState | None = None
    handoff_targets: list[ImageHandoffTarget] = Field(default_factory=list)


class ImageEvidenceListResponse(BaseModel):
    items: list[ImageEvidenceSummary] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
