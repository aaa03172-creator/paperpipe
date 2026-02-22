from types import SimpleNamespace

from src.agents.indexer_agent import IndexerAgent
from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
)
from src.schemas.agent_artifacts import (
    DocumentArtifact,
    PaperMetadata,
    Section,
    SourceInfo,
)


class _FakeCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, ids, embeddings, metadatas, documents):
        self.upserts.append(
            {
                "ids": list(ids),
                "embeddings": list(embeddings),
                "metadatas": list(metadatas),
                "documents": list(documents),
            }
        )


def _build_v2_doc() -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="doc-v2",
        meta=ArtifactMetaV2(title="T", authors=["A"], source_ref="/tmp/doc.pdf"),
        pages=[
            PageV2(
                page_index=0,
                width=100.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[LineV2(line_id="l1", text="page one text", spans=[SpanV2(span_id="s1", text="page one text")])],
                    )
                ],
            ),
            PageV2(
                page_index=1,
                width=100.0,
                height=100.0,
                blocks=[
                    BlockV2(
                        block_id="b2",
                        lines=[LineV2(line_id="l2", text="page two text", spans=[SpanV2(span_id="s2", text="page two text")])],
                    )
                ],
            ),
        ],
        tables=[],
    )


def test_indexer_chunk_ids_are_deterministic_for_same_v2_doc():
    fake_collection = _FakeCollection()
    fake_adapter = SimpleNamespace(embed=lambda text, model=None: [0.1, 0.2])

    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    agent.adapter = fake_adapter
    agent.collection = fake_collection

    doc = _build_v2_doc()
    out1 = agent.process(doc)
    out2 = agent.process(doc)

    ids1 = [c.chunk_id for c in out1.chunks]
    ids2 = [c.chunk_id for c in out2.chunks]
    assert ids1 == ids2 == ["p01_c01", "p02_c01"]
    assert fake_collection.upserts[0]["ids"] == ["p01_c01", "p02_c01"]
    assert fake_collection.upserts[1]["ids"] == ["p01_c01", "p02_c01"]
    assert fake_collection.upserts[0]["metadatas"][0]["page"] == 1
    assert fake_collection.upserts[0]["metadatas"][1]["page"] == 2


def test_indexer_uses_section_page_start_for_legacy_artifact():
    fake_collection = _FakeCollection()
    fake_adapter = SimpleNamespace(embed=lambda text, model=None: [0.1, 0.2])

    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    agent.adapter = fake_adapter
    agent.collection = fake_collection

    doc = DocumentArtifact(
        doc_id="doc-legacy",
        source=SourceInfo(type="pdf", ref="/tmp/legacy.pdf"),
        metadata=PaperMetadata(title="Legacy"),
        sections=[
            Section(name="abstract", text="a", char_start=0, char_end=1, page_start=3),
            Section(name="methods", text="b", char_start=2, char_end=3, page_start=4),
        ],
    )
    out = agent.process(doc)
    ids = [c.chunk_id for c in out.chunks]
    assert ids == ["p03_c01", "p04_c01"]
