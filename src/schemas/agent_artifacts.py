from typing import List, Optional, Union, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid

# -----------------------------------------------------------------------------
# 1. DocumentArtifact (Output of Ingest Agent)
# -----------------------------------------------------------------------------

class SourceInfo(BaseModel):
    type: Literal["pdf", "url", "text"]
    ref: str = Field(..., description="Path to file or URL")

class AuthorInfo(BaseModel):
    name: str

class PaperMetadata(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: int = Field(default=0)
    journal: str = Field(default="Unknown")
    doi: Optional[str] = None
    pmid: Optional[str] = None
    
    # Extra flexible fields
    raw_date: Optional[str] = None
    # OCR fallback metadata (PR#3)
    ocr_applied: bool = False
    ocr_engine: Optional[str] = None
    ocr_version: Optional[str] = None
    ocr_lang: Optional[str] = None
    ocr_error: Optional[str] = None
    ocr_output_path: Optional[str] = None
    
class Section(BaseModel):
    name: str = Field(..., description="Standardized section name (abstract, methods, results, discussion, etc.)")
    text: str
    char_start: int
    char_end: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None

class TableData(BaseModel):
    table_id: str
    caption: str
    data: List[List[str]] = Field(default_factory=list, description="2D array of strings representing the table")
    source_page: int

class DocumentArtifact(BaseModel):
    doc_id: str = Field(..., description="Unique ID: 'doi:...' or 'pmid:...' or 'file:...'")
    source: SourceInfo
    metadata: PaperMetadata
    sections: List[Section] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "doc_id": "doi:10.1038/s41586-023-00000-x",
                    "source": {"type": "pdf", "ref": "/path/to/paper.pdf"},
                    "metadata": {"title": "Example Paper", "authors": ["John Doe"], "year": 2024},
                    "sections": [{"name": "abstract", "text": "This is an abstract...", "char_start": 0, "char_end": 500}]
                }
            ]
        }
    }


# -----------------------------------------------------------------------------
# 2. IndexArtifact (Output of Indexer Agent)
# -----------------------------------------------------------------------------

class ChunkingStrategy(BaseModel):
    strategy: Literal["semantic", "section", "recursive", "fixed"]
    chunk_size: int
    overlap: int

class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    vector_id: Optional[str] = None 
    section_name: str
    embedding: Optional[List[float]] = None
    page_hint: Optional[int] = Field(None, description="0-indexed page hint when known")
    section_ordinal: Optional[int] = Field(None, description="1-indexed section position in the source document")
    chunk_ordinal: Optional[int] = Field(None, description="1-indexed chunk position within the section")
    chunk_id_version: Optional[str] = Field(None, description="Chunk-id strategy label for downstream compatibility")

class IndexArtifact(BaseModel):
    doc_id: str
    vector_store_id: str
    chunk_count: int
    chunks: List[DocumentChunk] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 3. ClaimSet (Output of Scientific Reader Agent)
# -----------------------------------------------------------------------------

class EvidenceSpan(BaseModel):
    """
    Evidence location within the document.
    Updated for Milestone 5 Strict Compliance.
    """
    page: Optional[int] = Field(None, description="0-indexed PDF page number")
    chunk_id: Optional[str] = Field("unknown", description="Standard chunk_id from DocumentArtifact")
    char_start: Optional[int] = Field(None, description="Start offset in chunk")
    char_end: Optional[int] = Field(None, description="End offset in chunk")
    
    # Text Content
    raw_text: Optional[str] = Field(None, description="Extracted raw text or table caption")
    quote: Optional[str] = Field(None, description="Short excerpt (recommended < 25 words)")
    rationale: Optional[str] = Field(None, description="MANDATORY: Why this evidence supports the claim (1-2 sentences)")

    # Precise location hints (additive)
    bbox_pdf: Optional[List[float]] = Field(
        None,
        description="[x0, y0, x1, y1] in PDF points (top-left origin canonical)",
    )
    bbox_pct: Optional[Dict[str, float]] = Field(
        None,
        description="UI-friendly percentage bbox with keys: left, top, width, height",
    )
    highlight_source: Optional[Literal["bbox", "text_match", "approx"]] = Field(
        None,
        description="Explicit evidence-to-PDF mapping quality for frontend rendering",
    )
    table_id: Optional[str] = None
    cell_id: Optional[str] = None
    unknown_reason: Optional[str] = None
    grounded: Optional[bool] = Field(None, description="Set by runtime resolver after quote-to-chunk verification")
    resolution: Optional[str] = Field(None, description="Runtime grounding result (e.g. OK, NORMALIZED_MATCH, FAILED_MATCH)")

    # Backwards compatibility fields (Optional)
    section: Optional[str] = None
    source_span: Optional[List[int]] = None

    @model_validator(mode="after")
    def validate_evidence_payload(self):
        self.raw_text = (self.raw_text or "").strip() or None
        self.table_id = (self.table_id or "").strip() or None
        self.cell_id = (self.cell_id or "").strip() or None

        has_raw_text = self.raw_text is not None
        has_table_ref = self.table_id is not None or self.cell_id is not None
        if has_table_ref and (self.table_id is None or self.cell_id is None):
            raise ValueError("EvidenceSpan table evidence requires both table_id and cell_id")
        if not has_raw_text and not (self.table_id and self.cell_id):
            raise ValueError("EvidenceSpan requires raw_text or a table_id/cell_id pair")

        if self.bbox_pdf is not None:
            if len(self.bbox_pdf) != 4:
                raise ValueError("EvidenceSpan bbox_pdf must contain exactly four coordinates")
            x0, y0, x1, y1 = self.bbox_pdf
            if min(x0, y0, x1, y1) < 0:
                raise ValueError("EvidenceSpan bbox_pdf coordinates must be non-negative")
            if x0 > x1 or y0 > y1:
                raise ValueError("EvidenceSpan bbox_pdf must satisfy x0<=x1 and y0<=y1")

        if self.bbox_pct is not None:
            required_keys = {"left", "top", "width", "height"}
            if not required_keys.issubset(self.bbox_pct):
                raise ValueError("EvidenceSpan bbox_pct must include left, top, width, and height")

        return self

class ScientificClaim(BaseModel):
    claim_id: str = Field(..., description="Unique ID (e.g. CLM-001)")
    type: str = Field(..., description="e.g. efficacy, safety, mechanism")
    statement: str = Field(..., description="The claim text")
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1.0)
    unknown: bool = False
    unknown_reason: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v == "methodology":
            return "methods"
        if v == "modeling":
            return "methods"
        return v

    @model_validator(mode="after")
    def normalize_unknown(self):
        self.unknown_reason = (self.unknown_reason or "").strip() or None
        if self.unknown and self.unknown_reason is None:
            self.unknown_reason = "UNSPECIFIED"
        return self
    
class ClaimSet(BaseModel):
    doc_id: str
    claims: List[ScientificClaim] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 4. Stats Verification (Milestone 5)
# -----------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    INCONSISTENT = "inconsistent"
    UNVERIFIABLE = "unverifiable"

class StatCheckEntry(BaseModel):
    """
    Self-contained record of a single statistical verification.
    """
    check_id: str = Field(..., description="Unique ID, maps to claim_id if applicable")
    hypothesis: Optional[str] = Field(None, description="The hypothesis being tested")
    test_type: str = Field(..., description="e.g., 't-test', 'ANOVA', 'Chi-square'")
    method: Optional[str] = None
    
    # Reported (Extracted)
    reported_stat: Optional[float] = None
    reported_df_tuple: Optional[List[float]] = Field(None, description="Parsed Degrees of Freedom")
    df_parse_status: str = Field("unknown", description="'success', 'failed'")
    reported_p: Optional[str] = None
    alpha_used: float = Field(0.05, description="Significance level used by authors")
    
    # Recalculated (Verified)
    computed_p: Optional[float] = None
    decision_error: bool = Field(False, description="True if significance conclusion differs")
    confidence_interval_consistency: Optional[bool] = None
    
    # Execution Details
    code: str = Field(..., description="Python code executed")
    outputs: str = Field(..., description="Stdout/Stderr from Sandbox")
    
    # Verdict
    verdict: VerificationStatus
    notes: Optional[str] = None
    evidence: List[EvidenceSpan] = Field(default_factory=list)

class SandboxMetadata(BaseModel):
    image: str
    mem_limit: str
    read_only: bool

class StatsReport(BaseModel):
    doc_id: str
    run_id: str
    input_tables_used: List[str] = Field(default_factory=list)
    checks: List[StatCheckEntry] = Field(default_factory=list)
    sandbox: Optional[SandboxMetadata] = None
    schema_version: str = "1.0"

# -----------------------------------------------------------------------------
# 5. Feedback (HITL)
# -----------------------------------------------------------------------------

class FeedbackCase(BaseModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paper_id: str
    run_id: str
    original_claim_id: Optional[str] = None
    user_correction: str
    accepted: bool
    timestamp: Optional[str] = None
