import sqlite3
from pathlib import Path

from src.indexer import DEFAULT_EMBEDDING_MODEL, PaperIndexer, default_collection_name


DDL_SQL = """
CREATE TABLE papers (
    paper_id TEXT PRIMARY KEY,
    doi TEXT,
    title TEXT NOT NULL,
    year INTEGER,
    venue TEXT,
    source TEXT,
    slot TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',
    confidence REAL,
    gate_decision TEXT,
    gate_reason TEXT,
    evidence_snippet TEXT,
    pdf_status TEXT,
    pdf_path TEXT,
    obsidian_path TEXT,
    ris_path TEXT,
    feedback_json TEXT,
    agent_version TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, summary TEXT);
CREATE INDEX idx_papers_status ON papers(status);
CREATE INDEX idx_papers_slot ON papers(slot);
CREATE INDEX idx_papers_doi ON papers(doi);
CREATE TABLE review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT,
    owner TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution TEXT,
    FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
);
"""


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def encode(self, texts, normalize_embeddings=True):
        self.calls.append({"texts": texts, "normalize_embeddings": normalize_embeddings})
        vectors = []
        for text in texts:
            length = float(len(text))
            checksum = float(sum(ord(c) for c in text) % 1000)
            vectors.append([length, checksum])
        return vectors


class FakeCollection:
    def __init__(self):
        self.records = {}

    def upsert(self, ids, embeddings, metadatas, documents):
        for i, pid in enumerate(ids):
            self.records[pid] = {
                "id": pid,
                "embedding": embeddings[i],
                "metadata": metadatas[i],
                "document": documents[i],
            }

    def query(self, query_embeddings, n_results=5):
        keys = list(self.records.keys())[:n_results]
        return {
            "ids": [keys],
            "metadatas": [[self.records[k]["metadata"] for k in keys]],
            "documents": [[self.records[k]["document"] for k in keys]],
        }


class FakeChromaClient:
    def __init__(self):
        self.collections = {}

    def get_or_create_collection(self, name, metadata=None):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


def _build_test_db(path: Path):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(DDL_SQL)

    cur.execute(
        """
        INSERT INTO papers (
            paper_id, doi, title, year, venue, source, slot, status, confidence,
            gate_decision, gate_reason, evidence_snippet, feedback_json, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "approved_001",
            "10.1000/approved",
            "Approved Paper",
            2024,
            "Lancet",
            "pubmed",
            "clinical",
            "APPROVED",
            0.93,
            "APPROVED",
            "confidence_high",
            "Strong evidence snippet",
            '{"tags":["Neurology"],"soft_tags":["#MCI","#Biomarker"]}',
            "This is an approved summary",
        ),
    )

    cur.execute(
        """
        INSERT INTO papers (
            paper_id, doi, title, year, venue, source, slot, status, confidence,
            gate_decision, gate_reason, evidence_snippet, feedback_json, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "pending_001",
            "10.1000/pending",
            "Pending Paper",
            2023,
            "NEJM",
            "pubmed",
            "mechanism",
            "CLASSIFIED",
            0.72,
            "PENDING_REVIEW",
            "needs_review",
            "Pending evidence snippet",
            '{"soft_tags":["#ReviewNeeded"]}',
            "Pending summary",
        ),
    )

    conn.commit()
    conn.close()


def test_index_filters_approved_by_default_and_all_mode(tmp_path):
    db_path = tmp_path / "state.db"
    _build_test_db(db_path)

    client = FakeChromaClient()
    embedder = FakeEmbedder()

    indexer = PaperIndexer(
        db_path=str(db_path),
        chroma_client=client,
        embedder=embedder,
    )

    result_default = indexer.index(include_all=False)
    assert result_default.indexed_count == 1

    collection = client.get_or_create_collection(indexer.collection_name)
    assert set(collection.records.keys()) == {"approved_001"}
    assert embedder.calls[0]["normalize_embeddings"] is True

    result_all = indexer.index(include_all=True)
    assert result_all.indexed_count == 2
    assert set(collection.records.keys()) == {"approved_001", "pending_001"}


def test_index_upsert_is_idempotent_and_updates_metadata_timestamp(tmp_path):
    db_path = tmp_path / "state.db"
    _build_test_db(db_path)

    client = FakeChromaClient()
    embedder = FakeEmbedder()
    times = iter(["2026-02-17T00:00:00+00:00", "2026-02-17T00:01:00+00:00"])

    indexer = PaperIndexer(
        db_path=str(db_path),
        chroma_client=client,
        embedder=embedder,
        now_fn=lambda: next(times),
    )

    indexer.index(include_all=False)
    collection = client.get_or_create_collection(indexer.collection_name)
    first_meta = collection.records["approved_001"]["metadata"]

    indexer.index(include_all=False)
    second_meta = collection.records["approved_001"]["metadata"]

    assert len(collection.records) == 1
    assert first_meta["indexed_at"] != second_meta["indexed_at"]


def test_search_returns_non_empty_structure_when_index_exists(tmp_path):
    db_path = tmp_path / "state.db"
    _build_test_db(db_path)

    client = FakeChromaClient()
    embedder = FakeEmbedder()

    indexer = PaperIndexer(
        db_path=str(db_path),
        chroma_client=client,
        embedder=embedder,
    )

    indexer.index(include_all=False)
    results = indexer.search("approved query", k=5)

    assert "ids" in results
    assert "metadatas" in results
    assert "documents" in results
    assert len(results["ids"]) == 1
    assert len(results["ids"][0]) >= 1


def test_default_model_policy_is_neuml_and_collection_v1():
    indexer = PaperIndexer(db_path=":memory:")
    assert indexer.model_name == DEFAULT_EMBEDDING_MODEL
    assert indexer.model_name == "NeuML/pubmedbert-base-embeddings"
    assert indexer.collection_name == default_collection_name("NeuML/pubmedbert-base-embeddings", 1)


def test_bge_query_prefix_auto_applies_for_bge_model(tmp_path):
    db_path = tmp_path / "state.db"
    _build_test_db(db_path)
    client = FakeChromaClient()
    embedder = FakeEmbedder()

    indexer = PaperIndexer(
        db_path=str(db_path),
        chroma_client=client,
        embedder=embedder,
        model_name="BAAI/bge-small-en-v1.5",
        bge_query_prefix="auto",
    )
    indexer.index(include_all=False)
    results = indexer.search("biomarker", k=3)

    encoded_query = embedder.calls[-1]["texts"][0]
    assert encoded_query.startswith("Represent this sentence for searching relevant passages:")
    assert results["query_prefix_used"] is True


def test_bge_query_prefix_off_disables_prefix(tmp_path):
    db_path = tmp_path / "state.db"
    _build_test_db(db_path)
    client = FakeChromaClient()
    embedder = FakeEmbedder()

    indexer = PaperIndexer(
        db_path=str(db_path),
        chroma_client=client,
        embedder=embedder,
        model_name="BAAI/bge-small-en-v1.5",
        bge_query_prefix="off",
    )
    indexer.index(include_all=False)
    results = indexer.search("biomarker", k=3)

    encoded_query = embedder.calls[-1]["texts"][0]
    assert encoded_query == "biomarker"
    assert results["query_prefix_used"] is False
