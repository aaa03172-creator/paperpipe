import argparse
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

DEFAULT_EMBEDDING_MODEL = "NeuML/pubmedbert-base-embeddings"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
INDEXER_DEVICE_ENV = "PAPERPIPE_INDEXER_DEVICE"

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def _detect_mps_device() -> str | None:
    try:
        import torch  # type: ignore
    except ImportError:
        return None

    try:
        if bool(torch.backends.mps.is_available()):
            return "mps"
    except Exception:
        return None
    return None


def resolve_embedding_device(requested_device: str | None = None) -> str | None:
    raw_device = requested_device if requested_device is not None else os.getenv(INDEXER_DEVICE_ENV)
    normalized = str(raw_device or "auto").strip().lower()
    if normalized in {"", "auto"}:
        return _detect_mps_device()
    if normalized in {"default", "none"}:
        return None
    return normalized



def default_collection_name(model_name: str, version: int = 1) -> str:
    return f"paper_pipe_bio__{_model_slug(model_name)}__v{version}"


def _load_feedback(feedback_json: str | None) -> dict[str, Any]:
    if not feedback_json:
        return {}
    try:
        parsed = json.loads(feedback_json)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def extract_tags(feedback: dict[str, Any]) -> list[str]:
    """Best-effort only: extract tags if explicitly present in feedback_json."""
    tags: list[str] = []

    raw_tags = feedback.get("tags")
    if isinstance(raw_tags, list):
        tags.extend(str(t) for t in raw_tags if t)

    soft_tags = feedback.get("soft_tags")
    if isinstance(soft_tags, list):
        for item in soft_tags:
            if isinstance(item, str):
                tags.append(item)
            elif isinstance(item, dict):
                tag_value = item.get("tag") or item.get("name")
                if tag_value:
                    tags.append(str(tag_value))

    cleaned: list[str] = []
    seen: set[str] = set()
    for t in tags:
        tag = t.strip()
        if not tag:
            continue
        if tag.startswith("#"):
            tag = tag[1:]
        if tag not in seen:
            seen.add(tag)
            cleaned.append(tag)

    return cleaned


def build_document(row: dict[str, Any], tags: list[str]) -> str:
    summary = (row.get("summary") or "").strip()
    title = (row.get("title") or "").strip()
    evidence = (row.get("evidence_snippet") or "").strip()

    if summary:
        primary = summary
    else:
        primary = title
        if evidence:
            primary = f"{primary}\nEvidence: {evidence}"

    parts = [primary]

    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    snippet_500 = evidence[:500]
    meta_line = (
        f"Meta: slot={row.get('slot') or ''}; venue={row.get('venue') or ''}; "
        f"gate_reason={row.get('gate_reason') or ''}; evidence_snippet={snippet_500}"
    )
    parts.append(meta_line)

    return "\n\n".join(parts).strip()


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


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
        embedding_device: str | None = None,
        now_fn: Callable[[], str] = _utc_now_iso,
    ) -> None:
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.model_name = model_name
        self.collection_version = collection_version
        self.collection_name = collection_name or default_collection_name(model_name, collection_version)
        self.bge_query_prefix = bge_query_prefix
        self._chroma_client = chroma_client
        self._embedder = embedder
        self._requested_embedding_device = embedding_device
        self.embedding_device: str | None = None
        self._now_fn = now_fn

    def _ensure_embedder(self) -> Any:
        if self._embedder is not None:
            return self._embedder

        self.embedding_device = resolve_embedding_device(self._requested_embedding_device)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for indexing/search. "
                "Install it in the active environment."
            ) from exc

        try:
            if self.embedding_device:
                self._embedder = SentenceTransformer(self.model_name, device=self.embedding_device)
            else:
                self._embedder = SentenceTransformer(self.model_name)
        except Exception:
            if self.embedding_device != "mps":
                raise
            logger.warning(
                "SentenceTransformer MPS initialization failed for %s; falling back to CPU.",
                self.model_name,
                exc_info=True,
            )
            self.embedding_device = "cpu"
            self._embedder = SentenceTransformer(self.model_name, device="cpu")
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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if include_all:
            cur.execute("SELECT * FROM papers")
        else:
            cur.execute(
                """
                SELECT *
                FROM papers
                WHERE gate_decision = 'APPROVED'
                   OR status IN ('APPROVED', 'INDEXED')
                """
            )

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def _encode_texts(self, texts: list[str]) -> list[list[float]]:
        embedder = self._ensure_embedder()
        embeddings = embedder.encode(texts, normalize_embeddings=True)
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()
        return embeddings

    def _use_bge_query_prefix(self) -> bool:
        mode = (self.bge_query_prefix or "auto").lower()
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


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperPipe local biomedical embedding indexer")
    parser.add_argument("--db", required=True, help="SQLite DB path")
    parser.add_argument("--chroma", default="./storage/vector_db", help="Chroma persist path")
    parser.add_argument(
        "--collection",
        default=None,
        help="Collection name (default: auto from model naming rule)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="SentenceTransformer model name (default: NeuML/pubmedbert-base-embeddings)",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=1,
        help="Collection version number (default: 1)",
    )
    parser.add_argument(
        "--bge-query-prefix",
        choices=["auto", "on", "off"],
        default="auto",
        help="Apply BGE retrieval prefix for query encoding (default: auto)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help=(
            "SentenceTransformer device: auto, cpu, mps, cuda, cuda:0, or default. "
            f"Defaults to ${INDEXER_DEVICE_ENV} or auto MPS detection."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_index = subparsers.add_parser("index", help="Index papers into ChromaDB")
    p_index.add_argument("--all", action="store_true", help="Index all papers without approval filter")

    p_search = subparsers.add_parser("search", help="Search indexed papers")
    p_search.add_argument("query", help="Search query text")
    p_search.add_argument("--k", type=int, default=5, help="Top-k results")

    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    indexer = PaperIndexer(
        db_path=args.db,
        chroma_path=args.chroma,
        model_name=args.model,
        collection_name=args.collection,
        collection_version=args.version,
        bge_query_prefix=args.bge_query_prefix,
        embedding_device=args.device,
    )

    if args.command == "index":
        result = indexer.index(include_all=args.all)
        print(json.dumps({"collection": result.collection_name, "indexed_count": result.indexed_count}))
        return

    if args.command == "search":
        results = indexer.search(query=args.query, k=args.k)
        print(json.dumps(results, ensure_ascii=False, default=str))
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
