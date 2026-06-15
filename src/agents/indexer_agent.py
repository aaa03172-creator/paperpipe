import hashlib
import logging
import re
from typing import List, Optional
import chromadb
from src.agents.adapter import OllamaModelAdapter
from src.schemas.agent_artifacts import DocumentArtifact, IndexArtifact, DocumentChunk
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.config import load_config
from src.services.identity import make_chunk_id
from src.services.runtime_paths import rag_root

logger = logging.getLogger(__name__)

CHUNK_ID_VERSION = "det-v1"
VECTOR_ID_VERSION = "doc-scope-v1"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
LEGACY_CHUNK_VECTOR_ID_RE = re.compile(r"^[ps]\d{2,}_c\d{2,}$")


def make_vector_id(*, doc_id: str, chunk_id: str) -> str:
    doc_key = hashlib.sha256(str(doc_id or "document").encode("utf-8")).hexdigest()[:16]
    return f"doc_{doc_key}__{chunk_id}"


class IndexerAgent:
    """
    Agent responsible for chunking, embedding, and indexing documents into the RAG store.
    Uses 'nomic-embed-text' via Ollama adapter and ChromaDB for storage.
    """
    
    def __init__(
        self,
        embedding_model: str = "nomic-embed-text",
        collection_name: str = "paperpipe_rag",
        persist_path: str | None = None,
    ):
        self.config = load_config()
        self.embedding_model = embedding_model
        self.adapter = OllamaModelAdapter() # Helper for embeddings
        
        # Initialize ChromaDB
        self.persist_path = str(persist_path) if persist_path is not None else str(rag_root())
        if persist_path is None and self.config.agents and self.config.agents.rag_index_path:
             self.persist_path = self.config.agents.rag_index_path
             
        self.chroma_client = chromadb.PersistentClient(path=self.persist_path)
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def reset_doc_index(self, doc_id: str) -> int:
        """
        Remove existing vectors for a document before re-indexing.
        Returns number of deleted chunk ids.
        """
        if not doc_id:
            return 0
        try:
            existing = self.collection.get(where={"doc_id": doc_id}, include=["metadatas"])
            ids = existing.get("ids") or []
            if not ids:
                return 0
            self.collection.delete(ids=ids)
            logger.info("Clean reindex removed %s chunks for %s", len(ids), doc_id)
            return len(ids)
        except Exception as exc:
            logger.error("Failed to reset index for %s: %s", doc_id, exc)
            raise

    def prune_doc_index(self, doc_id: str, *, keep_ids: List[str]) -> int:
        """
        Remove stale vectors for a document after replacement vectors have been upserted.
        Returns number of deleted chunk ids.
        """
        if not doc_id:
            return 0
        keep = {str(item) for item in keep_ids if str(item or "").strip()}
        if not keep:
            logger.warning("Skipping prune for %s because no replacement vector ids were provided", doc_id)
            return 0
        try:
            existing = self.collection.get(where={"doc_id": doc_id}, include=["metadatas"])
            ids = [str(item) for item in (existing.get("ids") or []) if str(item or "").strip()]
            stale_ids = [item for item in ids if item not in keep]
            if not stale_ids:
                return 0
            self.collection.delete(ids=stale_ids)
            logger.info("Clean reindex pruned %s stale chunks for %s", len(stale_ids), doc_id)
            return len(stale_ids)
        except Exception as exc:
            logger.error("Failed to prune index for %s: %s", doc_id, exc)
            raise

    def audit_vector_index(self, doc_id: Optional[str] = None, *, sample_limit: int = 25) -> dict:
        """Read-only audit for legacy or inconsistent vector IDs in Chroma."""
        get_kwargs = {"include": ["metadatas"]}
        if doc_id:
            get_kwargs["where"] = {"doc_id": doc_id}
        existing = self.collection.get(**get_kwargs)
        ids = [str(item) for item in (existing.get("ids") or []) if str(item or "").strip()]
        metadatas = list(existing.get("metadatas") or [])
        version_counts: dict[str, int] = {}
        legacy_unscoped_ids: list[str] = []
        unversioned_ids: list[str] = []
        missing_doc_id_count = 0
        metadata_vector_id_mismatch_ids: list[str] = []

        for idx, vector_id in enumerate(ids):
            metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
            chunk_id = str(metadata.get("chunk_id") or "")
            metadata_vector_id = str(metadata.get("vector_id") or "")
            vector_id_version = str(metadata.get("vector_id_version") or "").strip()
            version_key = vector_id_version or "missing"
            version_counts[version_key] = version_counts.get(version_key, 0) + 1
            if not vector_id_version:
                unversioned_ids.append(vector_id)

            if not str(metadata.get("doc_id") or "").strip():
                missing_doc_id_count += 1
            if metadata_vector_id and metadata_vector_id != vector_id:
                metadata_vector_id_mismatch_ids.append(vector_id)
            if vector_id == chunk_id or LEGACY_CHUNK_VECTOR_ID_RE.match(vector_id):
                legacy_unscoped_ids.append(vector_id)

        return {
            "doc_id": doc_id,
            "total_vectors": len(ids),
            "legacy_unscoped_count": len(legacy_unscoped_ids),
            "legacy_unscoped_ids": legacy_unscoped_ids[:sample_limit],
            "unversioned_count": len(unversioned_ids),
            "unversioned_ids": unversioned_ids[:sample_limit],
            "missing_doc_id_count": missing_doc_id_count,
            "metadata_vector_id_mismatch_count": len(metadata_vector_id_mismatch_ids),
            "metadata_vector_id_mismatch_ids": metadata_vector_id_mismatch_ids[:sample_limit],
            "vector_id_version_counts": version_counts,
            "vector_id_version": VECTOR_ID_VERSION,
        }

    def process(self, doc: DocumentArtifact | DocumentArtifactV2) -> IndexArtifact:
        """
        Chunks and indexes the document.
        Returns an IndexArtifact summarizing the operation.
        """
        header = get_artifact_header(doc)
        logger.info(f"Indexer Agent processing: {header.doc_id}")
        
        chunks: List[DocumentChunk] = []
        candidate_ids = []
        candidate_metadatas = []
        candidate_documents = []
        candidate_chunks: List[DocumentChunk] = []
        page_chunk_counts: dict[int, int] = {}
        attempted_chunks = 0
        skipped_chunks = 0
        self.last_index_attempted_chunks = 0
        self.last_index_skipped_chunks = 0
        self.last_index_complete = False
        
        # Section-aware chunking
        for section in iter_text_sections(doc):
            section_chunks = self._chunk_text(section.text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            
            for i, text_chunk in enumerate(section_chunks, start=1):
                attempted_chunks += 1
                if section.page_hint is not None:
                    chunk_ordinal = page_chunk_counts.get(section.page_hint, 0) + 1
                    page_chunk_counts[section.page_hint] = chunk_ordinal
                else:
                    chunk_ordinal = i
                chunk_id = make_chunk_id(
                    page_hint=section.page_hint,
                    section_ordinal=section.ordinal,
                    chunk_ordinal=chunk_ordinal,
                )
                vector_id = make_vector_id(doc_id=header.doc_id, chunk_id=chunk_id)

                candidate_ids.append(vector_id)
                candidate_metadatas.append({
                    "doc_id": header.doc_id,
                    "title": header.title,
                    "section": section.name,
                    "chunk_id": chunk_id,
                    "chunk_index": i - 1,
                    "chunk_ordinal": chunk_ordinal,
                    "section_ordinal": section.ordinal,
                    "page_hint": section.page_hint,
                    "chunk_id_version": CHUNK_ID_VERSION,
                    "vector_id": vector_id,
                    "vector_id_version": VECTOR_ID_VERSION,
                    "source": header.source_ref,
                })
                candidate_documents.append(text_chunk)
                
                # Create Schema Object
                candidate_chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    text=text_chunk,
                    vector_id=vector_id,
                    section_name=section.name,
                    page_hint=section.page_hint,
                    section_ordinal=section.ordinal,
                    chunk_ordinal=chunk_ordinal,
                    chunk_id_version=CHUNK_ID_VERSION,
                ))

        embed_batch = getattr(self.adapter, "embed_batch", None)
        if callable(embed_batch):
            candidate_embeddings = embed_batch(candidate_documents, model=self.embedding_model)
        else:
            candidate_embeddings = [
                self.adapter.embed(text_chunk, model=self.embedding_model)
                for text_chunk in candidate_documents
            ]

        ids = []
        embeddings = []
        metadatas = []
        documents = []
        for idx, text_chunk in enumerate(candidate_documents):
            embedding = candidate_embeddings[idx] if idx < len(candidate_embeddings) else []
            if not embedding:
                skipped_chunks += 1
                metadata = candidate_metadatas[idx]
                logger.warning(
                    "Failed to embed chunk %s in section %s",
                    metadata.get("chunk_ordinal"),
                    metadata.get("section"),
                )
                continue

            ids.append(candidate_ids[idx])
            embeddings.append(embedding)
            metadatas.append(candidate_metadatas[idx])
            documents.append(text_chunk)
            chunks.append(candidate_chunks[idx])
        
        # Batch upsert to Chroma
        if ids:
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            logger.info(f"Indexed {len(ids)} chunks for {header.doc_id}")
        else:
            logger.warning(f"No chunks indexed for {header.doc_id}")
        self.last_index_attempted_chunks = attempted_chunks
        self.last_index_skipped_chunks = skipped_chunks
        self.last_index_complete = attempted_chunks > 0 and skipped_chunks == 0 and len(chunks) == attempted_chunks
            
        return IndexArtifact(
            doc_id=header.doc_id,
            vector_store_id="chromadb",
            chunk_count=len(chunks),
            chunks=chunks # Note: DocumentChunk in schema might be light, avoiding full text if not needed, but here we include it.
        )


    def query(self, query_text: str, n_results: int = 5) -> List[str]:
        """
        Queries the vector store for relevant chunks.
        """
        # Embed query
        query_embedding = self.adapter.embed(query_text, model=self.embedding_model)
        if not query_embedding:
            logger.error("Failed to embed query.")
            return []
            
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Chroma returns lists of lists (one per query)
        if results and results['documents']:
            return results['documents'][0]
        return []

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Simple overlapping character-based chunking.
        """
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            
            if end == text_len:
                break
                
            start += chunk_size - overlap
            
        return chunks
