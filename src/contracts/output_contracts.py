from __future__ import annotations

import hashlib
import re
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.core.evidence_resolver import parse_page_from_chunk_id
from src.schemas.agent_artifacts import ClaimSet, IndexArtifact


_WS_RE = re.compile(r"\s+")


def _normalize_claim_text(text: str) -> str:
    normalized = _WS_RE.sub(" ", str(text or "").strip().lower())
    return normalized


def _claim_fingerprint(text: str) -> str:
    normalized = _normalize_claim_text(text)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


class ChunkContract(BaseModel):
    chunk_id: str
    page: Optional[int] = None
    text: str
    section_hint: Optional[str] = None


class ChunkSetContract(BaseModel):
    paper_id: str
    run_id: str
    schema_version: str = "1.0"
    chunk_count: int
    chunks: List[ChunkContract] = Field(default_factory=list)


class EvidenceRefContract(BaseModel):
    chunk_id: Optional[str] = None
    quote: Optional[str] = None
    page: Optional[int] = None
    grounded: Optional[bool] = None
    resolution: Optional[str] = None


class ClaimContract(BaseModel):
    claim_id: str
    claim_fingerprint: str
    text: str
    type: Optional[str] = None
    evidence: List[EvidenceRefContract] = Field(default_factory=list)


class ClaimSetContract(BaseModel):
    paper_id: str
    run_id: str
    stage: Literal["raw", "resolved"]
    schema_version: str = "1.0"
    model: Optional[str] = None
    claims: List[ClaimContract] = Field(default_factory=list)


def build_chunkset_contract(
    *,
    paper_id: str,
    run_id: str,
    index_artifact: IndexArtifact,
) -> ChunkSetContract:
    chunks: List[ChunkContract] = []
    for chunk in index_artifact.chunks:
        chunks.append(
            ChunkContract(
                chunk_id=chunk.chunk_id,
                page=parse_page_from_chunk_id(chunk.chunk_id),
                text=chunk.text,
                section_hint=chunk.section_name,
            )
        )
    return ChunkSetContract(
        paper_id=paper_id,
        run_id=run_id,
        chunk_count=len(chunks),
        chunks=chunks,
    )


def build_claimset_contract(
    *,
    paper_id: str,
    run_id: str,
    claim_set: ClaimSet,
    stage: Literal["raw", "resolved"],
    model: Optional[str] = None,
) -> ClaimSetContract:
    claims: List[ClaimContract] = []
    for claim in claim_set.claims:
        evidence: List[EvidenceRefContract] = []
        for span in claim.evidence_spans:
            evidence.append(
                EvidenceRefContract(
                    chunk_id=span.chunk_id,
                    quote=span.quote or span.raw_text,
                    page=span.page,
                    grounded=span.grounded,
                    resolution=span.resolution,
                )
            )

        text = claim.statement or ""
        claims.append(
            ClaimContract(
                claim_id=claim.claim_id,
                claim_fingerprint=_claim_fingerprint(text),
                text=text,
                type=claim.type,
                evidence=evidence,
            )
        )

    return ClaimSetContract(
        paper_id=paper_id,
        run_id=run_id,
        stage=stage,
        model=model,
        claims=claims,
    )


def claimset_contract_to_legacy_claimset(payload: ClaimSetContract) -> dict[str, Any]:
    """
    Bridge adapter for legacy consumers expecting {"doc_id", "claims"} shape.
    """
    claims: list[dict[str, Any]] = []
    for claim in payload.claims:
        evidence_spans: list[dict[str, Any]] = []
        for ev in claim.evidence:
            evidence_spans.append(
                {
                    "chunk_id": ev.chunk_id,
                    "quote": ev.quote,
                    "page": ev.page,
                    "grounded": ev.grounded,
                    "resolution": ev.resolution,
                }
            )
        claims.append(
            {
                "claim_id": claim.claim_id,
                "type": claim.type or "unknown",
                "statement": claim.text,
                "evidence_spans": evidence_spans,
            }
        )
    return {"doc_id": payload.paper_id, "claims": claims}
