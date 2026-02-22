from src.core.evidence_resolver import (
    normalize_text,
    parse_page_from_chunk_id,
    resolve_claimset_evidence,
)
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentChunk,
    EvidenceSpan,
    IndexArtifact,
    ScientificClaim,
)


def test_parse_page_from_chunk_id():
    assert parse_page_from_chunk_id("p03_c07") == 3
    assert parse_page_from_chunk_id("p1_c2") == 1
    assert parse_page_from_chunk_id("bad") is None


def test_normalize_text_collapses_whitespace_and_quotes():
    raw = '“memory  score”\n improved'
    assert normalize_text(raw) == '"memory score" improved'


def test_resolve_claimset_evidence_marks_exact_match_certain():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="S",
                confidence=0.8,
                evidence_spans=[EvidenceSpan(chunk_id="p02_c01", quote="memory score improved", raw_text="x")],
            )
        ],
    )
    index = IndexArtifact(
        doc_id="doc1",
        vector_store_id="v",
        chunk_count=1,
        chunks=[DocumentChunk(chunk_id="p02_c01", text="The memory score improved significantly.", section_name="page_2")],
    )

    out = resolve_claimset_evidence(claimset, index)
    span = out.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "OK"
    assert span.confidence_band == "certain"
    assert span.page == 2


def test_resolve_claimset_evidence_marks_normalized_match_estimated():
    claimset = ClaimSet(
        doc_id="doc2",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="S",
                confidence=0.8,
                evidence_spans=[EvidenceSpan(chunk_id="p01_c01", quote="memory score improved", raw_text="x")],
            )
        ],
    )
    index = IndexArtifact(
        doc_id="doc2",
        vector_store_id="v",
        chunk_count=1,
        chunks=[DocumentChunk(chunk_id="p01_c01", text="memory\nscore    improved", section_name="page_1")],
    )

    out = resolve_claimset_evidence(claimset, index)
    span = out.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "AMBIGUOUS_MATCH"
    assert span.confidence_band == "estimated"


def test_resolve_claimset_evidence_marks_missing_chunk_hold():
    claimset = ClaimSet(
        doc_id="doc3",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="S",
                confidence=0.8,
                evidence_spans=[EvidenceSpan(chunk_id="p99_c99", quote="not here", raw_text="x")],
            )
        ],
    )
    index = IndexArtifact(doc_id="doc3", vector_store_id="v", chunk_count=0, chunks=[])

    out = resolve_claimset_evidence(claimset, index)
    span = out.claims[0].evidence_spans[0]
    assert span.grounded is False
    assert span.resolution == "MISSING_CHUNK"
    assert span.confidence_band == "hold"
