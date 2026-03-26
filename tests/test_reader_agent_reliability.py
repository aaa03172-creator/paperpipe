from types import SimpleNamespace

from src.agents.reader_agent import ReaderAgent
from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
)


def _make_doc() -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="doc-reader-001",
        meta=ArtifactMetaV2(
            title="Reader Reliability Study",
            authors=["A. Author", "B. Author"],
            year=2024,
            journal="UnitTest Journal",
            source_ref="/tmp/doc-reader-001.pdf",
        ),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b0",
                        lines=[
                            LineV2(
                                line_id="l0",
                                text="Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
                                spans=[
                                    SpanV2(
                                        span_id="s0",
                                        text="Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
                                    )
                                ],
                            ),
                            LineV2(
                                line_id="l1",
                                text="No severe adverse events were observed in either arm.",
                                spans=[
                                    SpanV2(
                                        span_id="s1",
                                        text="No severe adverse events were observed in either arm.",
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )


def test_reader_retries_when_first_response_has_empty_claims():
    doc = _make_doc()
    reader = ReaderAgent(model_name="llama3:latest")

    calls = {"n": 0}

    def _fake_generate(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(text='{"doc_id":"doc-reader-001","claims":[]}')
        return SimpleNamespace(
            text="""
{
  "doc_id": "doc-reader-001",
  "claims": [
    {
      "claim_id": "CLM-777",
      "type": "efficacy",
      "statement": "Treatment improved memory score by 18% (p = 0.01).",
      "evidence_spans": [
        {
          "page": 0,
          "raw_text": "Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
          "quote": "improved memory score by 18% (p = 0.01, N = 64)",
          "rationale": "Directly reported in the result sentence.",
          "section": "page_1"
        }
      ],
      "limitations": ["single-center"],
      "confidence": 0.9
    }
  ]
}
"""
        )

    reader.adapter.generate = _fake_generate
    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    assert result.claims[0].claim_id == "CLM-777"
    span = result.claims[0].evidence_spans[0]
    assert span.chunk_id == "p01_c01"
    assert span.page == 0
    assert span.char_start is not None
    assert span.char_end is not None
    assert calls["n"] >= 2


def test_reader_uses_boundary_aligned_base_prompt_and_runtime_overlay():
    reader = ReaderAgent(
        model_name="llama3:latest",
        persona_hint="reasoning_persona=librarian\nprofile_id=coglab",
    )

    assert "evidence-grounded Deep Read analyst" in reader.system_prompt
    assert "separate from optional reasoning persona, profile context, and feedback overlays" in reader.system_prompt
    assert "Runtime overlay:" in reader.system_prompt
    assert "reasoning_persona=librarian" in reader.system_prompt


def test_reader_drops_unsupported_limitations_when_source_text_lacks_support():
    doc = _make_doc()
    reader = ReaderAgent(model_name="llama3:latest")
    reader.adapter.generate = lambda *_args, **_kwargs: SimpleNamespace(
        text="""
{
  "doc_id": "doc-reader-001",
  "claims": [
    {
      "claim_id": "CLM-777",
      "type": "efficacy",
      "statement": "Treatment improved memory score by 18% (p = 0.01).",
      "evidence_spans": [
        {
          "page": 0,
          "raw_text": "Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
          "quote": "improved memory score by 18% (p = 0.01, N = 64)",
          "rationale": "Directly reported in the result sentence.",
          "section": "page_1"
        }
      ],
      "limitations": ["small sample size"],
      "confidence": 0.9
    }
  ]
}
"""
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    assert result.claims[0].limitations == []


def test_reader_keeps_supported_limitations_when_source_text_contains_support():
    doc = DocumentArtifactV2(
        document_id="doc-reader-002",
        meta=ArtifactMetaV2(
            title="Reader Reliability Study 2",
            authors=["A. Author"],
            year=2024,
            journal="UnitTest Journal",
            source_ref="/tmp/doc-reader-002.pdf",
        ),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b0",
                        lines=[
                            LineV2(
                                line_id="l0",
                                text="Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
                                spans=[
                                    SpanV2(
                                        span_id="s0",
                                        text="Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
                                    )
                                ],
                            ),
                            LineV2(
                                line_id="l1",
                                text="This single-center study may limit generalizability.",
                                spans=[
                                    SpanV2(
                                        span_id="s1",
                                        text="This single-center study may limit generalizability.",
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )
    reader = ReaderAgent(model_name="llama3:latest")
    reader.adapter.generate = lambda *_args, **_kwargs: SimpleNamespace(
        text="""
{
  "doc_id": "doc-reader-002",
  "claims": [
    {
      "claim_id": "CLM-888",
      "type": "efficacy",
      "statement": "Treatment improved memory score by 18% (p = 0.01).",
      "evidence_spans": [
        {
          "page": 0,
          "raw_text": "Compared with placebo, treatment improved memory score by 18% (p = 0.01, N = 64).",
          "quote": "improved memory score by 18% (p = 0.01, N = 64)",
          "rationale": "Directly reported in the result sentence.",
          "section": "page_1"
        }
      ],
      "limitations": ["single-center"],
      "confidence": 0.9
    }
  ]
}
"""
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    assert result.claims[0].limitations == ["single-center"]


def test_reader_expands_evidence_excerpt_when_same_chunk_supports_more_of_statement():
    doc = DocumentArtifactV2(
        document_id="doc-reader-003",
        meta=ArtifactMetaV2(
            title="Reader Reliability Study 3",
            authors=["A. Author"],
            year=2024,
            journal="UnitTest Journal",
            source_ref="/tmp/doc-reader-003.pdf",
        ),
        pages=[
            PageV2(
                page_index=1,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b0",
                        lines=[
                            LineV2(
                                line_id="l0",
                                text=(
                                    "SMPD1 mRNA was not down-regulated and ASM protein levels were also not significantly "
                                    "changed by KARI compounds, indicating that KARI compounds inhibited ASM activity "
                                    "without changing mRNA and protein levels. We further confirmed the direct inhibition "
                                    "effects of the KARI compounds on the secretory form of ASM."
                                ),
                                spans=[
                                    SpanV2(
                                        span_id="s0",
                                        text=(
                                            "SMPD1 mRNA was not down-regulated and ASM protein levels were also not "
                                            "significantly changed by KARI compounds, indicating that KARI compounds "
                                            "inhibited ASM activity without changing mRNA and protein levels. We further "
                                            "confirmed the direct inhibition effects of the KARI compounds on the "
                                            "secretory form of ASM."
                                        ),
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )
    reader = ReaderAgent(model_name="llama3:latest")
    reader.adapter.generate = lambda *_args, **_kwargs: SimpleNamespace(
        text="""
{
  "doc_id": "doc-reader-003",
  "claims": [
    {
      "claim_id": "CLM-999",
      "type": "mechanism",
      "statement": "KARI compounds directly inhibit ASM activity without changing mRNA and protein levels.",
      "evidence_spans": [
        {
          "page": 1,
          "chunk_id": "p02_c01",
          "raw_text": "We further confirmed the direct inhibition effects of the KARI compounds on the secretory form of ASM.",
          "quote": "directly inhibit ASM activity",
          "rationale": "The text explicitly states that KARI compounds inhibit ASM activity without changing mRNA and protein levels.",
          "section": "page_2"
        }
      ],
      "limitations": [],
      "confidence": 0.9
    }
  ]
}
"""
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    span = result.claims[0].evidence_spans[0]
    assert "without changing mRNA and protein levels" in span.raw_text
    assert span.chunk_id == "p02_c01"
    assert span.source_span is not None
    assert span.source_span[0] >= 0
    assert span.quote
    assert span.quote.lower() in span.raw_text.lower()
    assert span.quote != "KARI compounds directly inhibit ASM activity without changing mRNA and protein levels."


def test_reader_uses_heuristic_fallback_when_all_llm_attempts_fail():
    doc = _make_doc()
    reader = ReaderAgent(model_name="llama3:latest")
    reader.adapter.generate = lambda *_args, **_kwargs: SimpleNamespace(text="not-json-response")

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) >= 1
    assert all(claim.unknown for claim in result.claims)
    assert all((claim.unknown_reason or "").strip() == "HEURISTIC_BACKFILL" for claim in result.claims)
    assert result.claims[0].evidence_spans
    assert result.claims[0].evidence_spans[0].chunk_id == "p01_c01"


def test_reader_replaces_placeholder_chunk_id_with_local_chunk_match():
    doc = _make_doc()
    reader = ReaderAgent(model_name="llama3:latest")
    reader.adapter.generate = lambda *_args, **_kwargs: SimpleNamespace(
        text="""
{
  "doc_id": "doc-reader-001",
  "claims": [
    {
      "claim_id": "CLM-123",
      "type": "efficacy",
      "statement": "Treatment improved memory score by 18% (p = 0.01).",
      "evidence_spans": [
        {
          "chunk_id": "ev_1",
          "quote": "treatment improved memory score by 18% (p = 0.01, N = 64)",
          "rationale": "Directly reported in the result sentence."
        }
      ],
      "confidence": 0.88
    }
  ]
}
"""
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    span = result.claims[0].evidence_spans[0]
    assert span.chunk_id == "p01_c01"
    assert span.page == 0
    assert span.source_span is not None
    assert span.source_span[0] >= 0
