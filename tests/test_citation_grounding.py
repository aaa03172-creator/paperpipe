from src.schemas.agent_artifacts import ClaimSet, DocumentChunk, EvidenceSpan, IndexArtifact, ScientificClaim
from src.services.citation_grounding import resolve_claimset_grounding


def test_resolve_claimset_grounding_prefers_matching_chunk_id_and_sets_offsets():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved outcome.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p03_c01",
                        quote="improved the primary outcome",
                        raw_text="improved the primary outcome",
                        rationale="quoted directly",
                    )
                ],
            )
        ],
    )
    index_artifact = IndexArtifact(
        doc_id="paper-1",
        vector_store_id="test",
        chunk_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="p03_c01",
                text="The intervention improved the primary outcome in the treatment arm.",
                section_name="Results",
                page_hint=3,
            )
        ],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "OK"
    assert span.page == 2
    assert span.section == "Results"
    assert span.char_start is not None
    assert span.char_end is not None
    assert span.source_span == [span.char_start, span.char_end]


def test_resolve_claimset_grounding_supports_normalized_match_without_chunk_id():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved outcome.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        quote="ketone supple- mentation improved memory scores",
                        raw_text="ketone supple- mentation improved memory scores",
                        rationale="quoted directly",
                    )
                ],
            )
        ],
    )
    index_artifact = IndexArtifact(
        doc_id="paper-1",
        vector_store_id="test",
        chunk_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="p01_c01",
                text="ketone supplementation improved memory scores versus placebo.",
                section_name="Results",
                page_hint=1,
            )
        ],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "NORMALIZED_MATCH"
    assert span.chunk_id == "p01_c01"
    assert span.page == 0


def test_resolve_claimset_grounding_supports_ligature_normalization() -> None:
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved outcome.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p01_c01",
                        quote="protein levels were also not significantly changed",
                        raw_text="protein levels were also not significantly changed",
                        rationale="quoted directly",
                    )
                ],
            )
        ],
    )
    index_artifact = IndexArtifact(
        doc_id="paper-1",
        vector_store_id="test",
        chunk_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="p01_c01",
                text="ASM protein levels were also not signiﬁcantly changed by KARI compounds.",
                section_name="Results",
                page_hint=1,
            )
        ],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "NORMALIZED_MATCH"
    assert span.chunk_id == "p01_c01"


def test_resolve_claimset_grounding_marks_ambiguous_matches():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved outcome.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        quote="shared evidence text",
                        raw_text="shared evidence text",
                        rationale="quoted directly",
                    )
                ],
            )
        ],
    )
    index_artifact = IndexArtifact(
        doc_id="paper-1",
        vector_store_id="test",
        chunk_count=2,
        chunks=[
            DocumentChunk(
                chunk_id="p01_c01",
                text="shared evidence text in section one.",
                section_name="Results",
                page_hint=1,
            ),
            DocumentChunk(
                chunk_id="p02_c01",
                text="shared evidence text in section two.",
                section_name="Discussion",
                page_hint=2,
            ),
        ],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is False
    assert span.resolution == "AMBIGUOUS_MATCH"
