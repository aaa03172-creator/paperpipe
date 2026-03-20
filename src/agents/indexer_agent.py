
import logging
import uuid
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from src.agents.adapter import OllamaModelAdapter
from src.schemas.agent_artifacts import DocumentArtifact, IndexArtifact, DocumentChunk
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.config import load_config

logger = logging.getLogger(__name__)
CHUNK_ID_VERSION = "legacy-uuid-v1"

class IndexerAgent:
    """
    Agent responsible for chunking, embedding, and indexing documents into the RAG store.
    Uses 'nomic-embed-text' via Ollama adapter and ChromaDB for storage.
    """
    
    def __init__(self, embedding_model: str = "nomic-embed-text", collection_name: str = "paperpipe_rag"):
        self.config = load_config()
        self.embedding_model = embedding_model
        self.adapter = OllamaModelAdapter() # Helper for embeddings
        
        # Initialize ChromaDB
        # We need a persistent path. For now, let's hardcode 'storage/rag' or get from config if available.
        # Assuming config has agents.rag_index_path or similar.
        self.persist_path = "storage/rag"
        if self.config.agents and self.config.agents.rag_index_path:
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

    def process(self, doc: DocumentArtifact | DocumentArtifactV2) -> IndexArtifact:
        """
        Chunks and indexes the document.
        Returns an IndexArtifact summarizing the operation.
        """
        header = get_artifact_header(doc)
        logger.info(f"Indexer Agent processing: {header.doc_id}")
        
        chunks: List[DocumentChunk] = []
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        # Section-aware chunking
        for section_ordinal, section in enumerate(iter_text_sections(doc), start=1):
            section_chunks = self._chunk_text(section.text, chunk_size=1000, overlap=200)
            page_hint: Optional[int] = None
            if section.name.startswith("page_"):
                suffix = section.name.removeprefix("page_").strip()
                if suffix.isdigit():
                    page_hint = max(int(suffix) - 1, 0)
            
            for i, text_chunk in enumerate(section_chunks):
                chunk_ordinal = i + 1
                chunk_id = str(uuid.uuid4())
                
                # Create embedding
                embedding = self.adapter.embed(text_chunk, model=self.embedding_model)
                if not embedding:
                    logger.warning(f"Failed to embed chunk {i} in section {section.name}")
                    continue
                
                # Append to lists for batch add
                ids.append(chunk_id)
                embeddings.append(embedding)
                metadatas.append({
                    "doc_id": header.doc_id,
                    "title": header.title,
                    "section": section.name,
                    "chunk_index": i,
                    "section_ordinal": section_ordinal,
                    "chunk_ordinal": chunk_ordinal,
                    "page_hint": page_hint,
                    "chunk_id_version": CHUNK_ID_VERSION,
                    "source": header.source_ref
                })
                documents.append(text_chunk)
                
                # Create Schema Object
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    text=text_chunk,
                    vector_id=chunk_id,
                    section_name=section.name,
                    page_hint=page_hint,
                    section_ordinal=section_ordinal,
                    chunk_ordinal=chunk_ordinal,
                    chunk_id_version=CHUNK_ID_VERSION,
                ))
        
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
