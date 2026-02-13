
import fitz
import os

def create_dummy_pdf(filename="test_rag_paper.pdf"):
    doc = fitz.open()
    page = doc.new_page()
    
    text = """
    Assessment of RAG Systems in Agentic Workflows: A Comparative Analysis
    John Doe, Jane Smith
    Department of AI Research, Future University
    
    Abstract
    Retrieval-Augmented Generation (RAG) is becoming a cornerstone for autonomous AI agents. However, standard chunking strategies often fragmentation of semantic context. In this study, we propose a "Section-Aware" chunking mechanism that respects document structure. We evaluated this approach on a dataset of 100 scientific papers. Our results demonstrate a 30% improvement in retrieval accuracy compared to fixed-window chunking.
    
    1. Introduction
    Large Language Models (LLMs) hallucinate when knowledge is missing. RAG mitigates this by providing relevant context. Most systems use fixed character counts (e.g., 500 chars) to split text, which breaks sentences and logical flows. We hypothesize that section-based splitting yields better embeddings.
    
    2. Methods
    We developed an Indexer Agent using PyMuPDF for parsing and ChromaDB for vector storage. The system detects headers (Introduction, Methods, Results) and groups text accordingly. We used 'nomic-embed-text' for embeddings.
    The evaluation metric was Hit Rate@5 on a synthetic QA dataset generated from the papers.
    
    3. Results
    The Section-Aware method achieved a Hit Rate@5 of 0.85, whereas the Fixed-Window method achieved 0.65 (p < 0.05).
    Qualitatively, the retrieval chunks contained complete arguments rather than fragmented sentences.
    
    4. Discussion
    Our findings suggest that structure-preserving parsing is essential for scientific RAG.
    Limitations include the reliance on clear PDF headers, which older papers may lack.
    Future work will explore vision-based layout analysis.
    
    5. Conclusion
    Section-aware chunking significantly boosts RAG performance for scientific literature.
    """
    
    page.insert_text((50, 50), text)
    doc.save(filename)
    print(f"Created {filename}")
    return os.path.abspath(filename)

if __name__ == "__main__":
    create_dummy_pdf()
