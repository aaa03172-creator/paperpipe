from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


ProvenanceKind = Literal["metadata", "figure", "reference"]
ProvenanceStatus = Literal["captured", "partial", "not_run", "not_available", "failed"]

PROVENANCE_SOURCE_RUN_META = "run_meta.json"
PROVENANCE_SOURCE_DOCUMENT_ARTIFACT = "document_artifact.json"
PROVENANCE_SOURCE_FIGURE_CAPTIONS = "figure_captions.json"
PROVENANCE_SOURCE_NOTE_FRONTMATTER = "note_frontmatter"
PROVENANCE_SOURCE_NOTE_REFERENCES_SECTION = "note_references_section"


class ProvenanceAspect(BaseModel):
    kind: ProvenanceKind
    status: ProvenanceStatus = "not_run"
    source_artifacts: list[str] = Field(default_factory=list)
    source_fields: list[str] = Field(default_factory=list)
    artifact_path: str | None = None
    count: int | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_aspect(self):
        self.source_artifacts = _dedupe_clean(self.source_artifacts)
        self.source_fields = _dedupe_clean(self.source_fields)
        self.notes = _dedupe_clean(self.notes)
        if self.artifact_path is not None:
            self.artifact_path = self.artifact_path.strip() or None
        return self


class PaperRunProvenanceSummary(BaseModel):
    schema_version: Literal["paper_run_provenance.v1"] = "paper_run_provenance.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    metadata: ProvenanceAspect = Field(default_factory=lambda: ProvenanceAspect(kind="metadata"))
    figures: ProvenanceAspect = Field(default_factory=lambda: ProvenanceAspect(kind="figure"))
    references: ProvenanceAspect = Field(default_factory=lambda: ProvenanceAspect(kind="reference"))

    @model_validator(mode="after")
    def normalize_summary(self):
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        if self.metadata.kind != "metadata":
            raise ValueError("metadata provenance aspect must use kind='metadata'")
        if self.figures.kind != "figure":
            raise ValueError("figures provenance aspect must use kind='figure'")
        if self.references.kind != "reference":
            raise ValueError("references provenance aspect must use kind='reference'")
        return self


def _dedupe_clean(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned
