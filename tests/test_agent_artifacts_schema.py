from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import src.agents.indexer_agent as indexer_agent_mod
from src.agents.indexer_agent import IndexerAgent
from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
)
from src.schemas.agent_artifacts import DocumentChunk, EvidenceSpan, ScientificClaim


def test_document_chunk_accepts_optional_metadata_fields():
    chunk = DocumentChunk(
        chunk_id="chunk-1",
        text="sample text",
        section_name="results",
        page_hint=2,
        section_ordinal=3,
        chunk_ordinal=1,
        chunk_id_version="legacy-uuid-v1",
    )

    assert chunk.page_hint == 2
    assert chunk.section_ordinal == 3
    assert chunk.chunk_ordinal == 1
    assert chunk.chunk_id_version == "legacy-uuid-v1"


def test_evidence_span_accepts_table_evidence_without_raw_text():
    span = EvidenceSpan(raw_text="   ", table_id="tbl-1", cell_id="r1c1")

    assert span.raw_text is None
    assert span.table_id == "tbl-1"
    assert span.cell_id == "r1c1"


def test_evidence_span_requires_complete_table_reference_when_raw_text_missing():
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text=" ", table_id="tbl-1")


def test_evidence_span_rejects_invalid_bbox_pdf_shape():
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text="evidence", bbox_pdf=[1.0, 2.0, 3.0])


def test_evidence_span_rejects_invalid_bbox_pct_keys():
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text="evidence", bbox_pct={"left": 0.1, "top": 0.2, "width": 0.3})


def test_scientific_claim_unknown_defaults_reason():
    claim = ScientificClaim(
        claim_id="c1",
        type="efficacy",
        statement="Unknown outcome.",
        confidence=0.4,
        unknown=True,
    )

    assert claim.unknown is True
    assert claim.unknown_reason == "UNSPECIFIED"


class _FakeCollection:
    def __init__(self):
        self.last_upsert = None

    def upsert(self, ids, embeddings, metadatas, documents):
        self.last_upsert = {
            "ids": ids,
            "embeddings": embeddings,
            "metadatas": metadatas,
            "documents": documents,
        }


class _FakeChromaClient:
    def __init__(self, collection):
        self.collection = collection

    def get_or_create_collection(self, name):
        return self.collection


class _FakeAdapter:
    def embed(self, text, model):
        return [float(len(text))]


def test_indexer_agent_emits_chunk_metadata(monkeypatch):
    monkeypatch.setattr(
        indexer_agent_mod,
        "load_config",
        lambda: SimpleNamespace(agents=SimpleNamespace(rag_index_path=None)),
    )
    monkeypatch.setattr(indexer_agent_mod, "OllamaModelAdapter", lambda: _FakeAdapter())

    collection = _FakeCollection()
    client = _FakeChromaClient(collection)
    monkeypatch.setattr(indexer_agent_mod.chromadb, "PersistentClient", lambda path: client)

    indexer = IndexerAgent()
    doc = DocumentArtifactV2(
        document_id="doc-1",
        meta=ArtifactMetaV2(title="Doc", authors=["A"], source_ref="/tmp/doc.pdf"),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[LineV2(line_id="l1", text="First page text", spans=[SpanV2(span_id="s1", text="First page text")])],
                    )
                ],
            ),
            PageV2(
                page_index=1,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b2",
                        lines=[LineV2(line_id="l2", text="Second page text", spans=[SpanV2(span_id="s2", text="Second page text")])],
                    )
                ],
            ),
        ],
        tables=[],
    )

    result = indexer.process(doc)

    assert result.chunk_count == 2
    assert [chunk.page_hint for chunk in result.chunks] == [0, 1]
    assert [chunk.section_ordinal for chunk in result.chunks] == [1, 2]
    assert [chunk.chunk_ordinal for chunk in result.chunks] == [1, 1]
    assert all(chunk.chunk_id_version == indexer_agent_mod.CHUNK_ID_VERSION for chunk in result.chunks)
    assert collection.last_upsert is not None
    assert collection.last_upsert["metadatas"][0]["page_hint"] == 0
    assert collection.last_upsert["metadatas"][1]["section_ordinal"] == 2
