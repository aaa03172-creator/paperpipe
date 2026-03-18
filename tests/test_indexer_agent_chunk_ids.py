from types import SimpleNamespace

from src.agents.indexer_agent import CHUNK_ID_VERSION, IndexerAgent
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.schemas.agent_artifacts import DocumentArtifact, PaperMetadata, Section, SourceInfo
from src.services.identity import make_chunk_id


class _FakeCollection:
    def __init__(self):
        self.calls: list[dict] = []

    def upsert(self, ids, embeddings, metadatas, documents):
        self.calls.append(
            {
                "ids": list(ids),
                "embeddings": list(embeddings),
                "metadatas": list(metadatas),
                "documents": list(documents),
            }
        )


def _build_agent() -> tuple[IndexerAgent, _FakeCollection]:
    collection = _FakeCollection()
    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    agent.adapter = SimpleNamespace(embed=lambda text, model=None: [0.1, 0.2, 0.3])
    agent.collection = collection
    return agent, collection


def _make_v2_doc(text: str) -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="doc-det-001",
        meta=ArtifactMetaV2(title="Deterministic", authors=["A"], source_ref="/tmp/sample.pdf"),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[LineV2(line_id="l1", text=text, spans=[SpanV2(span_id="s1", text=text)])],
                    )
                ],
            )
        ],
        tables=[],
    )


def test_make_chunk_id_prefers_page_hint_and_falls_back_to_section_ordinal():
    assert make_chunk_id(page_hint=3, section_ordinal=9, chunk_ordinal=7) == "p03_c07"
    assert make_chunk_id(page_hint=None, section_ordinal=2, chunk_ordinal=4) == "s02_c04"


def test_indexer_agent_chunk_ids_are_stable_for_repeated_v2_runs():
    text = "A" * 2200
    doc = _make_v2_doc(text)
    agent, collection = _build_agent()

    first = agent.process(doc)
    second = agent.process(doc)

    first_ids = [chunk.chunk_id for chunk in first.chunks]
    second_ids = [chunk.chunk_id for chunk in second.chunks]
    assert first_ids == ["p01_c01", "p01_c02", "p01_c03"]
    assert second_ids == first_ids
    assert collection.calls[0]["ids"] == first_ids
    assert collection.calls[1]["ids"] == second_ids
    assert first.chunks[0].page_hint == 1
    assert first.chunks[0].section_ordinal == 1
    assert first.chunks[0].chunk_ordinal == 1
    assert first.chunks[0].chunk_id_version == CHUNK_ID_VERSION


def test_indexer_agent_uses_section_fallback_ids_when_page_unknown():
    doc = DocumentArtifact(
        doc_id="doc-fallback-001",
        source=SourceInfo(type="pdf", ref="/tmp/sample.pdf"),
        metadata=PaperMetadata(title="Fallback"),
        sections=[
            Section(
                name="abstract",
                text="B" * 1300,
                char_start=0,
                char_end=1300,
                page_start=None,
                page_end=None,
            )
        ],
        tables=[],
    )
    agent, _collection = _build_agent()

    out = agent.process(doc)
    assert [chunk.chunk_id for chunk in out.chunks] == ["s01_c01", "s01_c02"]
    assert out.chunks[0].page_hint is None
    assert out.chunks[0].section_name == "abstract"
