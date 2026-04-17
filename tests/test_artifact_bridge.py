from types import SimpleNamespace

from src.contracts.document_artifact_v2 import (
    DocumentArtifactV2,
    ArtifactMetaV2,
    PageV2,
    BlockV2,
    LineV2,
    SpanV2,
)
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.contracts.artifact_bridge import ensure_legacy_document_artifact
from src.agents.reader_agent import ReaderAgent
from src.agents.indexer_agent import IndexerAgent


def _make_v2() -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="doc-v2-001",
        meta=ArtifactMetaV2(
            title="V2 Title",
            authors=["A", "B"],
            year=2024,
            journal="J",
            source_ref="/tmp/sample.pdf",
        ),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="blk_1",
                        bbox_pdf=[10.0, 10.0, 200.0, 80.0],
                        lines=[
                            LineV2(
                                line_id="ln_1",
                                text="This is line one.",
                                spans=[SpanV2(span_id="sp_1", text="This is line one.")],
                                bbox_unavailable=True,
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[
            {
                "table_id": "T1",
                "caption": "Example Table",
                "data": [["A", "B"], ["1", "2"]],
                "source_page": 1,
            }
        ],
    )


def test_artifact_bridge_converts_v2_to_legacy():
    v2 = _make_v2()
    legacy = ensure_legacy_document_artifact(v2)
    assert legacy.doc_id == "doc-v2-001"
    assert legacy.metadata.title == "V2 Title"
    assert len(legacy.sections) == 1
    assert "line one" in legacy.sections[0].text
    assert len(legacy.tables) == 1
    assert legacy.tables[0].table_id == "T1"


def test_reader_agent_accepts_v2_input(monkeypatch):
    v2 = _make_v2()
    class FakeAdapter:
        def __init__(self, model_name=None):
            self.model_name = model_name

        def generate(self, *args, **kwargs):
            return SimpleNamespace(text='{"doc_id":"doc-v2-001","claims":[]}')

    import src.agents.reader_agent as reader_module

    monkeypatch.setattr(reader_module, "OllamaModelAdapter", FakeAdapter)
    reader = ReaderAgent(model_name="llama3:latest")

    result = reader.analyze(v2)
    assert result is not None
    assert result.doc_id == "doc-v2-001"


def test_artifact_views_extract_header_and_sections_from_v2():
    v2 = _make_v2()
    header = get_artifact_header(v2)
    sections = list(iter_text_sections(v2))

    assert header.doc_id == "doc-v2-001"
    assert header.title == "V2 Title"
    assert header.source_ref == "/tmp/sample.pdf"
    assert len(sections) == 1
    assert sections[0].name == "page_1"
    assert sections[0].page_hint == 1
    assert sections[0].ordinal == 1
    assert "line one" in sections[0].text


def test_artifact_views_preserve_page_hints_for_legacy_artifact():
    legacy = ensure_legacy_document_artifact(_make_v2())
    sections = list(iter_text_sections(legacy))

    assert len(sections) == 1
    assert sections[0].name == "page_1"
    assert sections[0].page_hint == 1
    assert sections[0].ordinal == 1


def test_indexer_agent_accepts_v2_input_without_init():
    v2 = _make_v2()

    class FakeCollection:
        def __init__(self):
            self.last_upsert = None

        def upsert(self, ids, embeddings, metadatas, documents):
            self.last_upsert = {
                "ids": ids,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "documents": documents,
            }

    fake_collection = FakeCollection()
    fake_adapter = SimpleNamespace(embed=lambda text, model=None: [0.1, 0.2, 0.3])

    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    agent.adapter = fake_adapter
    agent.collection = fake_collection

    out = agent.process(v2)
    assert out.doc_id == "doc-v2-001"
    assert out.chunk_count >= 1
    assert fake_collection.last_upsert is not None
    assert fake_collection.last_upsert["metadatas"][0]["source"] == "/tmp/sample.pdf"
