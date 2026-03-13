from typing import List

from pydantic import BaseModel, Field


class ArtifactMetaV2(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: int = 0
    journal: str = "Unknown"
    doi: str | None = None
    source_ref: str


class TableV2(BaseModel):
    table_id: str
    caption: str
    data: List[List[str]] = Field(default_factory=list)
    source_page: int


class DocumentArtifactV2(BaseModel):
    document_id: str
    meta: ArtifactMetaV2
    pages: List[dict] = Field(default_factory=list)
    tables: List[TableV2] = Field(default_factory=list)
    schema_version: str = "2.0"
