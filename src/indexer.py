import re
from dataclasses import dataclass
from typing import Any, Callable

from src.indexer_content import (
    build_document as _build_document_content,
    extract_tags as _extract_tags_from_feedback,
    load_feedback as _load_feedback_json,
    safe_int as _safe_int_value,
    utc_now_iso as _utc_now_iso_value,
)
from src.indexer_store import select_index_rows

DEFAULT_EMBEDDING_MODEL = "NeuML/pubmedbert-base-embeddings"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
VALID_BGE_QUERY_PREFIX_MODES = {"auto", "on", "off"}


def _utc_now_iso() -> str:
    return _utc_now_iso_value()


def _model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")



def default_collection_name(model_name: str, version: int = 1) -> str:
    return f"paper_pipe_bio__{_model_slug(model_name)}__v{version}"


def _load_feedback(feedback_json: str | None) -> dict[str, Any]:
    return _load_feedback_json(feedback_json)


def extract_tags(feedback: dict[str, Any]) -> list[str]:
    return _extract_tags_from_feedback(feedback)


def build_document(row: dict[str, Any], tags: list[str]) -> str:
    return _build_document_content(row, tags)


def _safe_int(value: Any) -> int | None:
    return _safe_int_value(value)


@dataclass
class IndexRunResult:
    collection_name: str
    indexed_count: int


class PaperIndexer:
    def __init__(
        self,
        db_path: str,
        chroma_path: str = "./storage/vector_db",
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        collection_name: str | None = None,
        collection_version: int = 1,
        bge_query_prefix: str = "auto",
        chroma_client: Any | None = None,
        embedder: Any | None = None,
        now_fn: Callable[[], str] = _utc_now_iso,
    ) -> None:
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.model_name = model_name
        self.collection_version = collection_version
        self.collection_name = collection_name or default_collection_name(model_name, collection_version)
        mode = (bge_query_prefix or "auto").lower()
        if mode not in VALID_BGE_QUERY_PREFIX_MODES:
            raise ValueError(
                "bge_query_prefix must be one of: auto, on, off."
            )
        self.bge_query_prefix = mode
        self._chroma_client = chroma_client
        self._embedder = embedder
        self._now_fn = now_fn

    def _ensure_embedder(self) -> Any:
        if self._embedder is not None:
            return self._embedder

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for indexing/search. "
                "Install it in the active environment."
            ) from exc

        self._embedder = SentenceTransformer(self.model_name)
        return self._embedder

    def _ensure_chroma_client(self) -> Any:
        if self._chroma_client is not None:
            return self._chroma_client

        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is required for indexing/search. Install it in the active environment."
            ) from exc

        self._chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        return self._chroma_client

    def _get_collection(self) -> Any:
        client = self._ensure_chroma_client()
        return client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _select_rows(self, include_all: bool) -> list[dict[str, Any]]:
        return select_index_rows(self.db_path, include_all=include_all)

    def _encode_texts(self, texts: list[str]) -> list[list[float]]:
        embedder = self._ensure_embedder()
        embeddings = embedder.encode(texts, normalize_embeddings=True)
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()
        return embeddings

    def _use_bge_query_prefix(self) -> bool:
        mode = self.bge_query_prefix
        if mode == "on":
            return True
        if mode == "off":
            return False
        return "bge" in self.model_name.lower()

    def _prepare_query_text(self, query: str) -> tuple[str, bool]:
        use_prefix = self._use_bge_query_prefix()
        if not use_prefix:
            return query, False
        return f"{BGE_QUERY_PREFIX}{query}", True

    def index(self, include_all: bool = False) -> IndexRunResult:
        rows = self._select_rows(include_all=include_all)
        if not rows:
            return IndexRunResult(collection_name=self.collection_name, indexed_count=0)

        ids: list[str] = []
        docs: list[str] = []
        metadatas: list[dict[str, Any]] = []

        timestamp = self._now_fn()

        for row in rows:
            # [Fix] Use 'doi' as ID if 'paper_id' missing
            pid = str(row.get("paper_id") or row.get("doi") or "")
            if not pid:
                continue

            feedback = _load_feedback(row.get("feedback_json"))
            tags = extract_tags(feedback)
            ids.append(pid)
            docs.append(build_document(row, tags))
            metadatas.append(
                {
                    "paper_id": pid,
                    "title": str(row.get("title") or ""),
                    "year": _safe_int(row.get("year")),
                    "venue": str(row.get("venue") or ""),
                    "slot": str(row.get("slot") or ""),
                    "status": str(row.get("status") or ""),
                    "gate_decision": str(row.get("gate_decision") or ""),
                    "doi": str(row.get("doi") or ""),
                    "embedding_model": self.model_name,
                    "collection_name": self.collection_name,
                    "collection_version": self.collection_version,
                    "indexed_at": timestamp,
                    "tags_count": len(tags),
                }
            )

        if not ids:
            return IndexRunResult(collection_name=self.collection_name, indexed_count=0)

        embeddings = self._encode_texts(docs)
        collection = self._get_collection()

        try:
            collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs)
        except AttributeError:
            collection.delete(ids=ids)
            collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs)

        return IndexRunResult(collection_name=self.collection_name, indexed_count=len(ids))

    def search(self, query: str, k: int = 5) -> dict[str, Any]:
        query_text, query_prefix_used = self._prepare_query_text(query)
        embedding = self._encode_texts([query_text])[0]
        collection = self._get_collection()
        results = collection.query(query_embeddings=[embedding], n_results=k)
        results["query_prefix_used"] = query_prefix_used
        return results


def main() -> None:
    from src.indexer_cli import run_cli

    run_cli(indexer_factory=PaperIndexer, default_model=DEFAULT_EMBEDDING_MODEL)


if __name__ == "__main__":
    main()
