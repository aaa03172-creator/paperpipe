import json

from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2
from src.schemas.agent_artifacts import ClaimSet, DocumentChunk, EvidenceSpan, IndexArtifact, ScientificClaim
from src.services.claimset_coverage_sidecar import (
    build_claimset_coverage_sidecar,
    write_claimset_coverage_sidecar,
)


def _doc(page_texts: list[str]) -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="doc-1",
        meta=ArtifactMetaV2(title="Coverage Test", authors=["A"], source_ref="/tmp/test.pdf"),
        pages=[
            PageV2(
                page_index=idx,
                width=595.0,
                height=842.0,
                blocks=[BlockV2(block_id=f"b{idx}", lines=[LineV2(line_id=f"l{idx}", text=text)])],
            )
            for idx, text in enumerate(page_texts)
        ],
        tables=[],
    )


def _index(page_texts: list[str]) -> IndexArtifact:
    chunks = [
        DocumentChunk(
            chunk_id=f"p{idx + 1:02d}_c01",
            text=text,
            section_name=f"page_{idx + 1}",
            page_hint=idx + 1,
        )
        for idx, text in enumerate(page_texts)
    ]
    return IndexArtifact(doc_id="doc-1", vector_store_id="v1", chunk_count=len(chunks), chunks=chunks)


def _claim(claim_id: str, statement: str, page: int, raw_text: str) -> ScientificClaim:
    return ScientificClaim(
        claim_id=claim_id,
        type="mechanism",
        statement=statement,
        confidence=0.9,
        evidence_spans=[
            EvidenceSpan(
                page=page - 1,
                chunk_id=f"p{page:02d}_c01",
                raw_text=raw_text,
                quote=raw_text,
                rationale="direct support",
                section=f"page_{page}",
                grounded=True,
                resolution="OK",
            )
        ],
    )


def test_clustered_claimset_on_review_paper_receives_warn_or_fail(tmp_path):
    page_texts = [
        "Animal models create a translation gap for human physiology and clinical trial prediction.",
        "Human cellular systems include iPSC stem cell platforms and primary human cell assays.",
        "Organoid and organ-on-chip microphysiological systems model tissue context.",
        "AI and machine learning support active learning and foundation model discovery.",
        "Regulatory agencies including FDA and OECD need qualification and benchmark evidence.",
        "Ethic consent privacy federated data and workforce training affect adoption.",
        "Additional review context.",
        "More broad evidence synthesis.",
        "References.",
    ]
    claims = ClaimSet(
        doc_id="doc-1",
        claims=[
            _claim("CLM-001", "iPSC stem cell systems improve human toxicology modeling.", 2, page_texts[1]),
            _claim("CLM-002", "iPSC stem cell assays improve human toxicology screening.", 2, page_texts[1]),
            _claim("CLM-003", "Human iPSC platforms improve toxicology model relevance.", 2, page_texts[1]),
        ],
    )

    sidecar = build_claimset_coverage_sidecar(
        paper_id="science-aeb0045",
        run_id="run-1",
        document_artifact=_doc(page_texts),
        index_artifact=_index(page_texts),
        resolved_claimset=claims,
    )

    assert sidecar.coverage_status in {"warn", "fail"}
    assert sidecar.page_summary.covered_pages == [2]
    assert "low_page_coverage" in sidecar.reason_codes
    assert "low_section_diversity" in sidecar.reason_codes
    assert sidecar.metrics.missing_topic_signal_count >= 3
    assert sidecar.duplicate_warnings
    assert sidecar.recommended_next_action != "none"

    path = write_claimset_coverage_sidecar(sidecar, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["canonical_status"] == "non_canonical"
    assert payload["source_artifacts"] == ["document_artifact.json", "index_artifact.json", "claimset.resolved.json"]


def test_grounded_claimset_across_pages_and_topics_receives_pass():
    page_texts = [
        "Animal translation and human physiology are central review concerns.",
        "Human cellular systems include iPSC and stem cell assays.",
        "Organoid organ-on-chip and microphysiological systems expand model diversity.",
        "AI and machine learning help prioritize candidates.",
    ]
    claims = ClaimSet(
        doc_id="doc-1",
        claims=[
            _claim("CLM-001", "Animal translation remains a central human physiology limitation.", 1, page_texts[0]),
            _claim("CLM-002", "iPSC stem cell assays represent human cellular systems.", 2, page_texts[1]),
            _claim("CLM-003", "Organoid organ-on-chip microphysiological systems expand model diversity.", 3, page_texts[2]),
            _claim("CLM-004", "AI and machine learning prioritize candidates.", 4, page_texts[3]),
        ],
    )

    sidecar = build_claimset_coverage_sidecar(
        paper_id="science-aeb0045",
        run_id="run-2",
        document_artifact=_doc(page_texts),
        index_artifact=_index(page_texts),
        resolved_claimset=claims,
    )

    assert sidecar.coverage_status == "pass"
    assert sidecar.page_summary.covered_pages == [1, 2, 3, 4]
    assert sidecar.metrics.grounded_evidence_ratio == 1.0
    assert sidecar.metrics.page_coverage_ratio == 1.0
    assert sidecar.metrics.missing_topic_signal_count == 0
    assert sidecar.recommended_next_action == "none"


def test_coverage_derives_page_from_chunk_page_section_when_page_hint_and_span_page_missing():
    page_texts = [
        "Animal translation and human physiology are central review concerns.",
        "Human cellular systems include iPSC and stem cell assays.",
        "Organoid organ-on-chip and microphysiological systems expand model diversity.",
        "AI and machine learning help prioritize candidates.",
    ]
    index_artifact = IndexArtifact(
        doc_id="doc-1",
        vector_store_id="v1",
        chunk_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="chunk-page-2",
                text=page_texts[1],
                section_name="page_2",
                page_hint=None,
            )
        ],
    )
    claims = ClaimSet(
        doc_id="doc-1",
        claims=[
            ScientificClaim(
                claim_id="CLM-001",
                type="mechanism",
                statement="iPSC stem cell assays represent human cellular systems.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="chunk-page-2",
                        raw_text=page_texts[1],
                        quote=page_texts[1],
                        rationale="direct support",
                        section="page_2",
                        grounded=True,
                        resolution="OK",
                    )
                ],
            )
        ],
    )

    sidecar = build_claimset_coverage_sidecar(
        paper_id="science-aeb0045",
        run_id="run-section-page",
        document_artifact=_doc(page_texts),
        index_artifact=index_artifact,
        resolved_claimset=claims,
    )

    assert sidecar.page_summary.covered_pages == [2]
    assert sidecar.evidence_summary.pages_with_grounded_evidence == [2]
    assert sidecar.metrics.covered_page_count == 1
    assert sidecar.metrics.page_coverage_ratio == 0.25


def test_mouse_behavior_training_does_not_trigger_ethics_governance_signal():
    page_texts = [
        "Mice were trained on the rotarod apparatus for two days before motor testing.",
        "The assay measured coordination after lesion induction.",
    ]
    claims = ClaimSet(
        doc_id="doc-1",
        claims=[_claim("CLM-001", "The study measured motor coordination.", 2, page_texts[1])],
    )

    sidecar = build_claimset_coverage_sidecar(
        paper_id="motor-study",
        run_id="run-training",
        document_artifact=_doc(page_texts),
        index_artifact=_index(page_texts),
        resolved_claimset=claims,
    )

    ethics_signal = next(signal for signal in sidecar.topic_signals if signal.key == "ethics_governance")
    assert ethics_signal.present_in_document is False
