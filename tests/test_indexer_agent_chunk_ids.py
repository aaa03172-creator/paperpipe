from types import SimpleNamespace

from src.agents.indexer_agent import CHUNK_ID_VERSION, VECTOR_ID_VERSION, IndexerAgent, make_vector_id
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.schemas.agent_artifacts import DocumentArtifact, PaperMetadata, Section, SourceInfo
from src.services.identity import make_chunk_id


class _FakeCollection:
    def __init__(self):
        self.calls: list[dict] = []
        self.existing_ids: list[str] = []
        self.existing_metadatas: list[dict] = []
        self.deleted_ids: list[str] = []

    def upsert(self, ids, embeddings, metadatas, documents):
        self.calls.append(
            {
                "ids": list(ids),
                "embeddings": list(embeddings),
                "metadatas": list(metadatas),
                "documents": list(documents),
            }
        )

    def get(self, where=None, include=None):
        if self.existing_metadatas:
            metadatas = list(self.existing_metadatas)
        else:
            metadatas = [{"doc_id": (where or {}).get("doc_id")} for _ in self.existing_ids]
        return {"ids": list(self.existing_ids), "metadatas": metadatas}

    def delete(self, ids):
        self.deleted_ids.extend(list(ids))


def _build_agent() -> tuple[IndexerAgent, _FakeCollection]:
    collection = _FakeCollection()
    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    agent.adapter = SimpleNamespace(embed=lambda text, model=None: [0.1, 0.2, 0.3])
    agent.collection = collection
    return agent, collection


def _make_v2_doc(text: str, *, document_id: str = "doc-det-001") -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id=document_id,
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
    expected_vector_ids = [make_vector_id(doc_id="doc-det-001", chunk_id=chunk_id) for chunk_id in first_ids]
    assert first_ids == ["p01_c01", "p01_c02", "p01_c03"]
    assert second_ids == first_ids
    assert collection.calls[0]["ids"] == expected_vector_ids
    assert collection.calls[1]["ids"] == expected_vector_ids
    assert collection.calls[0]["metadatas"][0]["chunk_id"] == "p01_c01"
    assert collection.calls[0]["metadatas"][0]["vector_id"] == expected_vector_ids[0]
    assert collection.calls[0]["metadatas"][0]["vector_id_version"] == VECTOR_ID_VERSION
    assert first.chunks[0].vector_id == expected_vector_ids[0]
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


def test_indexer_agent_vector_ids_are_scoped_by_document_id():
    text = "A" * 1200
    first_doc = _make_v2_doc(text, document_id="doc-det-001")
    second_doc = _make_v2_doc(text, document_id="doc-det-002")
    agent, collection = _build_agent()

    first = agent.process(first_doc)
    second = agent.process(second_doc)

    assert [chunk.chunk_id for chunk in first.chunks] == [chunk.chunk_id for chunk in second.chunks]
    assert collection.calls[0]["ids"] != collection.calls[1]["ids"]
    assert set(collection.calls[0]["ids"]).isdisjoint(collection.calls[1]["ids"])
    assert first.chunks[0].vector_id != second.chunks[0].vector_id


def test_indexer_agent_prunes_only_stale_doc_vectors_after_successful_upsert():
    agent, collection = _build_agent()
    keep_id = make_vector_id(doc_id="doc-det-001", chunk_id="p01_c01")
    stale_id = make_vector_id(doc_id="doc-det-001", chunk_id="p01_c99")
    legacy_unscoped_id = "p01_c01"
    collection.existing_ids = [keep_id, stale_id, legacy_unscoped_id]

    removed = agent.prune_doc_index("doc-det-001", keep_ids=[keep_id])

    assert removed == 2
    assert collection.deleted_ids == [stale_id, legacy_unscoped_id]


def test_indexer_agent_prune_is_noop_without_replacement_vector_ids():
    agent, collection = _build_agent()
    collection.existing_ids = ["p01_c01"]

    removed = agent.prune_doc_index("doc-det-001", keep_ids=[])

    assert removed == 0
    assert collection.deleted_ids == []


def test_indexer_agent_audit_vector_index_reports_legacy_unscoped_ids():
    agent, collection = _build_agent()
    scoped_id = make_vector_id(doc_id="doc-det-001", chunk_id="p01_c01")
    collection.existing_ids = ["p01_c01", scoped_id, "other-vector"]
    collection.existing_metadatas = [
        {"doc_id": "doc-det-001", "chunk_id": "p01_c01"},
        {
            "doc_id": "doc-det-001",
            "chunk_id": "p01_c01",
            "vector_id": scoped_id,
            "vector_id_version": VECTOR_ID_VERSION,
        },
        {
            "doc_id": "",
            "chunk_id": "p02_c01",
            "vector_id": "different-vector",
            "vector_id_version": VECTOR_ID_VERSION,
        },
    ]

    audit = agent.audit_vector_index("doc-det-001")

    assert audit["doc_id"] == "doc-det-001"
    assert audit["total_vectors"] == 3
    assert audit["legacy_unscoped_count"] == 1
    assert audit["legacy_unscoped_ids"] == ["p01_c01"]
    assert audit["unversioned_count"] == 1
    assert audit["unversioned_ids"] == ["p01_c01"]
    assert audit["missing_doc_id_count"] == 1
    assert audit["metadata_vector_id_mismatch_count"] == 1
    assert audit["metadata_vector_id_mismatch_ids"] == ["other-vector"]
    assert audit["vector_id_version_counts"] == {"missing": 1, VECTOR_ID_VERSION: 2}


def test_indexer_agent_audit_vector_index_keeps_unversioned_uuid_separate_from_chunk_locator_ids():
    agent, collection = _build_agent()
    collection.existing_ids = ["a63deb9b-7267-4f17-aa90-f7356f0c5070"]
    collection.existing_metadatas = [
        {"doc_id": "doc-det-001", "chunk_id": "p01_c01"},
    ]

    audit = agent.audit_vector_index()

    assert audit["total_vectors"] == 1
    assert audit["legacy_unscoped_count"] == 0
    assert audit["legacy_unscoped_ids"] == []
    assert audit["unversioned_count"] == 1
    assert audit["unversioned_ids"] == ["a63deb9b-7267-4f17-aa90-f7356f0c5070"]


def test_indexer_agent_marks_partial_embedding_replacement_incomplete():
    collection = _FakeCollection()
    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    calls = {"count": 0}

    def embed(text, model=None):
        calls["count"] += 1
        return [] if calls["count"] == 2 else [0.1, 0.2, 0.3]

    agent.adapter = SimpleNamespace(embed=embed)
    agent.collection = collection
    doc = _make_v2_doc("A" * 2200)

    out = agent.process(doc)

    assert agent.last_index_attempted_chunks == 3
    assert agent.last_index_skipped_chunks == 1
    assert agent.last_index_complete is False
    assert out.chunk_count == 2
    assert len(collection.calls[0]["ids"]) == 2
