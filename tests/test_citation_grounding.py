from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
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


def test_resolve_claimset_grounding_supports_soft_hyphen_normalization() -> None:
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="definition",
                statement="Amyloid positivity has limited predictive value.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p02_c06",
                        quote="Amyloid β positivity is insufficient to definitively predict the occurrence of symptoms (mild cognitive impairment or dementia) in individuals without clinical impairment.",
                        raw_text="Amyloid β positivity is insufficient to definitively predict the occurrence of symptoms (mild cognitive impairment or dementia) in individuals without clinical impairment.",
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
                chunk_id="p02_c06",
                text="amyloid β positivity is insufficient to definitively predict the occur\u00adrence of symptoms (mild cognitive impairment or dem\u00aden\u00adtia) in individuals without clinical impairment.",
                section_name="page_2",
                page_hint=2,
            )
        ],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "NORMALIZED_MATCH"
    assert span.chunk_id == "p02_c06"
    assert span.page == 1


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


def test_resolve_claimset_grounding_enriches_unique_block_bbox_from_document_v2():
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
                chunk_id="p01_c01",
                text="The intervention improved the primary outcome in the treatment arm.",
                section_name="Results",
                page_hint=1,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(
                page_index=0,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-1",
                        bbox_pdf=[10.0, 20.0, 190.0, 60.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="The intervention improved the primary outcome in the treatment arm.",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="The intervention improved the primary outcome in the treatment arm.",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "OK"
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [10.0, 20.0, 190.0, 60.0]
    assert span.bbox_pct == {"left": 5.0, "top": 20.0, "width": 90.0, "height": 40.0}


def test_resolve_claimset_grounding_salvages_unique_document_block_when_chunk_match_fails():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="mechanism",
                statement="Persistent firing requires NR2B kinetics.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p03_c01",
                        page=3,
                        quote="Persistent neuronal firing requires the slower kinetics of the NR2B receptor.",
                        raw_text="Persistent neuronal firing requires the slower kinetics of the NR2B receptor.",
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
                text="A neighboring paragraph that does not include the claim text.",
                section_name="page_4",
                page_hint=4,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(page_index=0, width=200.0, height=100.0, blocks=[]),
            PageV2(page_index=1, width=200.0, height=100.0, blocks=[]),
            PageV2(
                page_index=2,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-target",
                        bbox_pdf=[20.0, 30.0, 180.0, 70.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="Persistent neuronal firing requires the slower kinetics of the NR2B receptor.",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="Persistent neuronal firing requires the slower kinetics of the NR2B receptor.",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
            PageV2(page_index=3, width=200.0, height=100.0, blocks=[]),
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "OK"
    assert span.page == 2
    assert span.section == "page_3"
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [20.0, 30.0, 180.0, 70.0]


def test_resolve_claimset_grounding_matches_quote_with_trailing_punctuation_removed():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="mechanism",
                statement="Persistent firing requires NR2B kinetics.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p03_c01",
                        quote="Persistent neuronal firing requires the slower kinetics of the NR2B receptor.",
                        raw_text="Persistent neuronal firing requires the slower kinetics of the NR2B receptor.",
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
                text="These physiological data are consistent with computational models predicting that persistent neuronal firing requires the slower kinetics of the NR2B receptor (Wang, 1999).",
                section_name="page_3",
                page_hint=3,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(
                page_index=2,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-target",
                        bbox_pdf=[20.0, 30.0, 180.0, 70.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="These physiological data are consistent with computational models predicting that persistent neuronal firing requires the slower kinetics of the NR2B receptor (Wang, 1999).",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="These physiological data are consistent with computational models predicting that persistent neuronal firing requires the slower kinetics of the NR2B receptor (Wang, 1999).",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.page == 2
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [20.0, 30.0, 180.0, 70.0]


def test_resolve_claimset_grounding_matches_quote_with_internal_hyphen_variants():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="safety",
                statement="Avagacestat safety signal.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p02_c04",
                        quote="Avagacestat was relatively well-tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d, and increases in non-melanoma skin cancer and non-progressive, reversible renal tubule effects were observed.",
                        raw_text="Avagacestat was relatively well-tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d, and increases in non-melanoma skin cancer and non-progressive, reversible renal tubule effects were observed.",
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
                chunk_id="p02_c04",
                text="Avagacestat was relatively well tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d, and increases in nonmelanoma skin cancer and nonprogressive, reversible renal tubule effects were observed.",
                section_name="page_2",
                page_hint=2,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(
                page_index=1,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-target",
                        bbox_pdf=[20.0, 30.0, 180.0, 70.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="Avagacestat was relatively well tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d, and increases in nonmelanoma skin cancer and nonprogressive, reversible renal tubule effects were observed.",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="Avagacestat was relatively well tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d, and increases in nonmelanoma skin cancer and nonprogressive, reversible renal tubule effects were observed.",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution in {"OK", "NORMALIZED_MATCH"}
    assert span.page == 1
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [20.0, 30.0, 180.0, 70.0]


def test_resolve_claimset_grounding_matches_quote_with_numeric_unit_spacing_variants():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="safety",
                statement="Dose tolerability.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p04_c01",
                        quote="Avagacestat was relatively well-tolerated with low discontinuation rates (19.6%) at a dose of 50mg/d.",
                        raw_text="Avagacestat was relatively well-tolerated with low discontinuation rates (19.6%) at a dose of 50mg/d.",
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
                chunk_id="p04_c01",
                text="Avagacestat was relatively well tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d.",
                section_name="page_4",
                page_hint=4,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(
                page_index=3,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-target",
                        bbox_pdf=[20.0, 30.0, 180.0, 70.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="Avagacestat was relatively well tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d.",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="Avagacestat was relatively well tolerated with low discontinuation rates (19.6%) at a dose of 50 mg/d.",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution in {"OK", "NORMALIZED_MATCH"}
    assert span.page == 3
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [20.0, 30.0, 180.0, 70.0]


def test_resolve_claimset_grounding_matches_quote_with_inline_reference_markers_removed():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="definition",
                statement="General cognitive impairments in older adults can extend beyond memory alone.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p02_c07",
                        quote="Cognitive impairments of elderly people are not limited to memory, and a host of definitions—including ageing-associated cognitive decline, mild cognitive decline, and cognitive impairment–no dementia (CIND)—are based on more general impairments of cognition, including impairments in language, visuospatial awareness, and attention.",
                        raw_text="Cognitive impairments of elderly people are not limited to memory, and a host of definitions—including ageing-associated cognitive decline, mild cognitive decline, and cognitive impairment–no dementia (CIND)—are based on more general impairments of cognition, including impairments in language, visuospatial awareness, and attention.",
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
                chunk_id="p02_c07",
                text="More general definitions\nCognitive impairments of elderly people are not limited to\nmemory, and a host of definitions—including ageing-\nassociated cognitive decline,21 mild cognitive decline,30 and\ncognitive impairment–no dementia (CIND)5—are based on\nmore general impairments of cognition, including\nimpairments in language, visuospatial awareness, and\nattention.",
                section_name="page_2",
                page_hint=2,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(
                page_index=1,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-target",
                        bbox_pdf=[20.0, 30.0, 180.0, 70.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="Cognitive impairments of elderly people are not limited to memory, and a host of definitions—including ageing-associated cognitive decline,21 mild cognitive decline,30 and cognitive impairment–no dementia (CIND)5—are based on more general impairments of cognition, including impairments in language, visuospatial awareness, and attention.",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="Cognitive impairments of elderly people are not limited to memory, and a host of definitions—including ageing-associated cognitive decline,21 mild cognitive decline,30 and cognitive impairment–no dementia (CIND)5—are based on more general impairments of cognition, including impairments in language, visuospatial awareness, and attention.",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution in {"OK", "NORMALIZED_MATCH"}
    assert span.page == 1
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [20.0, 30.0, 180.0, 70.0]


def test_resolve_claimset_grounding_uses_claim_statement_for_bbox_only_fallback():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="definition",
                statement="Age-associated memory impairment is a condition characterized by decline in ability in older individuals with memory function one standard deviation or more below that in young people.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p02_c05",
                        quote="Different diagnostic schemes may be sensitive to different diseases... Crook and co-workers19 were the first to derive specific criteria and measurements for the definition of abnormal memory function among elderly people.",
                        raw_text="Different diagnostic schemes may be sensitive to different diseases... Crook and co-workers19 were the first to derive specific criteria and measurements for the definition of abnormal memory function among elderly people.",
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
                chunk_id="p02_c05",
                text="Different diagnostic schemes may be sensitive to different diseases... Crook and co-workers19 were the first to derive specific criteria and measurements for the definition of abnormal memory function among elderly people.",
                section_name="page_2",
                page_hint=2,
            )
        ],
    )
    document_artifact = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="Paper 1", authors=["A"], source_ref="/tmp/paper.pdf"),
        pages=[
            PageV2(
                page_index=1,
                width=200.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="blk-target",
                        bbox_pdf=[20.0, 30.0, 180.0, 70.0],
                        lines=[
                            LineV2(
                                line_id="ln-1",
                                text="used the term age-associated memory impairment for the decline in ability in older individuals with memory function one standard deviation or more below that in young people.",
                                spans=[
                                    SpanV2(
                                        span_id="sp-1",
                                        text="used the term age-associated memory impairment for the decline in ability in older individuals with memory function one standard deviation or more below that in young people.",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )

    resolved = resolve_claimset_grounding(claimset, index_artifact, document_artifact=document_artifact)
    span = resolved.claims[0].evidence_spans[0]
    assert span.grounded is True
    assert span.resolution == "OK"
    assert span.page == 1
    assert span.highlight_source == "bbox"
    assert span.bbox_pdf == [20.0, 30.0, 180.0, 70.0]
