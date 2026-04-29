from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.protocol_card import ProtocolCardRequest, ProtocolDraftSourceSummary


ProtocolAttachmentArtifactFamily = Literal["protocol_attachment"]
ProtocolAttachmentLayer = Literal["raw_source"]
ProtocolAttachmentSourceKind = Literal["uploaded_file"]
ProtocolAttachmentExtractionStatus = Literal["succeeded", "failed"]
ProtocolAttachmentArtifactKind = Literal["source_file", "extracted_markdown"]


class ProtocolAttachmentArtifactRef(BaseModel):
    kind: ProtocolAttachmentArtifactKind
    path: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_ref(self):
        self.path = self.path.strip()
        return self


class ProtocolAttachmentWarning(BaseModel):
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_warning(self):
        self.code = self.code.strip()
        self.message = self.message.strip()
        return self


class ProtocolAttachmentDraftRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    media_type: str | None = None
    note_slug: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    title: str | None = None
    purpose: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.filename = self.filename.strip()
        if self.media_type is not None:
            self.media_type = self.media_type.strip() or None
        if self.note_slug is not None:
            self.note_slug = self.note_slug.strip() or None
        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        if self.title is not None:
            self.title = self.title.strip() or None
        if self.purpose is not None:
            self.purpose = self.purpose.strip() or None
        return self


class ProtocolAttachmentBundle(BaseModel):
    attachment_bundle_id: str = Field(..., pattern=r"^protatt_[A-Za-z0-9._-]+$")
    artifact_family: ProtocolAttachmentArtifactFamily = "protocol_attachment"
    layer: ProtocolAttachmentLayer = "raw_source"
    source_kind: ProtocolAttachmentSourceKind = "uploaded_file"
    title: str = Field(..., min_length=1)
    source_filename: str = Field(..., min_length=1)
    media_type: str | None = None
    byte_size: int = Field(..., ge=0)
    sha1: str = Field(..., pattern=r"^[a-f0-9]{40}$")
    note_slug: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    created_at: datetime
    source_ref: ProtocolAttachmentArtifactRef
    extracted_markdown_ref: ProtocolAttachmentArtifactRef | None = None
    extraction_engine: str | None = None
    extraction_status: ProtocolAttachmentExtractionStatus = "failed"
    extracted_markdown_excerpt: str | None = None
    warnings: list[ProtocolAttachmentWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_bundle(self):
        self.attachment_bundle_id = self.attachment_bundle_id.strip()
        self.title = self.title.strip()
        self.source_filename = self.source_filename.strip()
        if self.media_type is not None:
            self.media_type = self.media_type.strip() or None
        if self.note_slug is not None:
            self.note_slug = self.note_slug.strip() or None
        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        if self.extraction_engine is not None:
            self.extraction_engine = self.extraction_engine.strip() or None
        if self.extracted_markdown_excerpt is not None:
            self.extracted_markdown_excerpt = self.extracted_markdown_excerpt.strip() or None
        return self


class ProtocolAttachmentDraftResponse(BaseModel):
    attachment_bundle: ProtocolAttachmentBundle
    draft: ProtocolCardRequest
    paper_source_summary: ProtocolDraftSourceSummary | None = None
    warnings: list[ProtocolAttachmentWarning] = Field(default_factory=list)
