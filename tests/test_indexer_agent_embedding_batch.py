from src.agents.indexer_agent import IndexerAgent
from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
)


class FakeAdapter:
    def __init__(self):
        self.batch_calls = []
        self.single_calls = []

    def embed(self, text, model="nomic-embed-text"):
        self.single_calls.append({"text": text, "model": model})
        return [1.0, 0.0]

    def embed_batch(self, texts, model="nomic-embed-text"):
        self.batch_calls.append({"texts": list(texts), "model": model})
        return [[1.0, float(index)] for index, _text in enumerate(texts)]


class FakeCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, ids, embeddings, metadatas, documents):
        self.upserts.append(
            {
                "ids": ids,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "documents": documents,
            }
        )


def test_indexer_uses_batch_embedding_for_chunks():
    doc = DocumentArtifactV2(
        document_id="doc-batch-001",
        meta=ArtifactMetaV2(title="Batch Paper", authors=["A"], source_ref="paper.pdf"),
        pages=[
            PageV2(
                page_index=0,
                width=100,
                height=100,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[
                            LineV2(
                                line_id="l1",
                                text="a" * 1200,
                                spans=[SpanV2(span_id="s1", text="a" * 1200)],
                            )
                        ],
                    )
                ],
            ),
            PageV2(
                page_index=1,
                width=100,
                height=100,
                blocks=[
                    BlockV2(
                        block_id="b2",
                        lines=[
                            LineV2(
                                line_id="l2",
                                text="b" * 1200,
                                spans=[SpanV2(span_id="s2", text="b" * 1200)],
                            )
                        ],
                    )
                ],
            ),
        ],
        tables=[],
    )
    agent = IndexerAgent.__new__(IndexerAgent)
    agent.embedding_model = "nomic-embed-text"
    agent.adapter = FakeAdapter()
    agent.collection = FakeCollection()

    result = agent.process(doc)

    assert result.chunk_count > 0
    assert len(agent.adapter.batch_calls) == 1
    assert agent.adapter.single_calls == []
    assert len(agent.adapter.batch_calls[0]["texts"]) == result.chunk_count
    assert len(agent.collection.upserts) == 1
    assert len(agent.collection.upserts[0]["embeddings"]) == result.chunk_count
