from typing import List, Optional, Union, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, field_validator

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
    page: Optional[int] = Field(0, description="0-indexed PDF page number")
    chunk_id: Optional[str] = Field("unknown", description="Standard chunk_id from DocumentArtifact")
    char_start: Optional[int] = Field(None, description="Start offset in chunk")
    char_end: Optional[int] = Field(None, description="End offset in chunk")
    
    # Text Content
    raw_text: str = Field(..., description="Extracted raw text or table caption")
    quote: Optional[str] = Field(None, description="Short excerpt (recommended < 25 words)")
    rationale: Optional[str] = Field(None, description="MANDATORY: Why this evidence supports the claim (1-2 sentences)")

    # Backwards compatibility fields (Optional)
    section: Optional[str] = None
    source_span: Optional[List[int]] = None

class ScientificClaim(BaseModel):
    claim_id: str = Field(..., description="Unique ID (e.g. CLM-001)")
    type: str = Field(..., description="e.g. efficacy, safety, mechanism")
    statement: str = Field(..., description="The claim text")
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1.0)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v == "methodology":
            return "methods"
        if v == "modeling":
            return "methods"
        return v
    
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
    paper_id: str
    run_id: str
    original_claim_id: Optional[str] = None
    user_correction: str
    accepted: bool
    timestamp: Optional[str] = None
