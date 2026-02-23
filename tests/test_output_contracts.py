from src.contracts.output_contracts import (
    build_chunkset_contract,
    build_claimset_contract,
    claimset_contract_to_legacy_claimset,
)
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentChunk,
    EvidenceSpan,
    IndexArtifact,
    ScientificClaim,
)


def test_build_chunkset_contract_parses_page_from_chunk_id():
    index_artifact = IndexArtifact(
        doc_id="paper_1",
        vector_store_id="vs",
        chunk_count=2,
        chunks=[
            DocumentChunk(chunk_id="p01_c01", text="A", section_name="intro"),
            DocumentChunk(chunk_id="p12_c03", text="B", section_name="results"),
        ],
    )

    payload = build_chunkset_contract(
        paper_id="paper_1",
        run_id="run_1",
        index_artifact=index_artifact,
    )

    assert payload.paper_id == "paper_1"
    assert payload.run_id == "run_1"
    assert payload.chunk_count == 2
    assert payload.chunks[0].page == 1
    assert payload.chunks[1].page == 12


def test_build_claimset_contract_and_bridge_adapter():
    claim_set = ClaimSet(
        doc_id="paper_2",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improves memory ",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        page=3,
                        chunk_id="p03_c01",
                        raw_text="Drug A improved memory",
                        quote="improved memory",
                        grounded=True,
                        resolution="OK",
                    )
                ],
            )
        ],
    )

    payload_1 = build_claimset_contract(
        paper_id="paper_2",
        run_id="run_2",
        claim_set=claim_set,
        stage="resolved",
        model="reader-model",
    )
    payload_2 = build_claimset_contract(
        paper_id="paper_2",
        run_id="run_2",
        claim_set=ClaimSet(
            doc_id="paper_2",
            claims=[
                ScientificClaim(
                    claim_id="c1",
                    type="efficacy",
                    statement="drug  a   improves   memory",
                    confidence=0.9,
                    evidence_spans=[],
                )
            ],
        ),
        stage="resolved",
    )

    assert payload_1.claims[0].claim_fingerprint == payload_2.claims[0].claim_fingerprint

    legacy = claimset_contract_to_legacy_claimset(payload_1)
    assert legacy["doc_id"] == "paper_2"
    assert legacy["claims"][0]["claim_id"] == "c1"
    assert legacy["claims"][0]["evidence_spans"][0]["chunk_id"] == "p03_c01"
