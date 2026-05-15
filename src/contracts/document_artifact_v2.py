import hashlib
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator


BBoxPDF = List[float]  # [x0, y0, x1, y1] in PDF coordinates (points), origin top-left.


class ArtifactMetaV2(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: int = 0
    journal: str = "Unknown"
    doi: Optional[str] = None
    source_ref: str


class SpanV2(BaseModel):
    span_id: str
    text: str
    bbox_pdf: Optional[BBoxPDF] = None
    source_ref: Optional[str] = None
    bbox_unavailable: bool = False


class LineV2(BaseModel):
    line_id: str
    text: str
    bbox_pdf: Optional[BBoxPDF] = None
    spans: List[SpanV2] = Field(default_factory=list)
    bbox_unavailable: bool = False


class BlockV2(BaseModel):
    block_id: str
    bbox_pdf: Optional[BBoxPDF] = None
    lines: List[LineV2] = Field(default_factory=list)
    bbox_unavailable: bool = False


class PageV2(BaseModel):
    page_index: int  # 0-indexed
    width: float
    height: float
    blocks: List[BlockV2] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bbox_bounds(self):
        for block in self.blocks:
            _assert_bbox_within_page(block.bbox_pdf, self.width, self.height, f"block:{block.block_id}")
            for line in block.lines:
                _assert_bbox_within_page(line.bbox_pdf, self.width, self.height, f"line:{line.line_id}")
                for span in line.spans:
                    _assert_bbox_within_page(span.bbox_pdf, self.width, self.height, f"span:{span.span_id}")
        return self


class TableV2(BaseModel):
    table_id: str
    caption: str
    data: List[List[str]] = Field(default_factory=list)
    source_page: int
    source_ref: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    provenance_note: Optional[str] = None


class DocumentArtifactV2(BaseModel):
    document_id: str
    meta: ArtifactMetaV2
    pages: List[PageV2] = Field(default_factory=list)
    tables: List[TableV2] = Field(default_factory=list)
    schema_version: str = "2.0"


def _assert_bbox_within_page(bbox: Optional[BBoxPDF], page_w: float, page_h: float, label: str) -> None:
    if bbox is None:
        return
    if len(bbox) != 4:
        raise ValueError(f"{label}: bbox must have 4 values")
    x0, y0, x1, y1 = bbox
    if min(x0, y0, x1, y1) < 0:
        raise ValueError(f"{label}: bbox has negative coordinates")
    if x0 > x1 or y0 > y1:
        raise ValueError(f"{label}: bbox order must be x0<=x1 and y0<=y1")
    if x1 > page_w or y1 > page_h:
        raise ValueError(f"{label}: bbox outside page bounds")


def stable_id(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]
