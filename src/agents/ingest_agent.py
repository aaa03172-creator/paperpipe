
import logging
import fitz  # standard pymupdf import
import pdfplumber
from pathlib import Path
from typing import List, Optional, Tuple

from src.schemas.agent_artifacts import (
    DocumentArtifact, 
    SourceInfo, 
    PaperMetadata, 
    Section, 
    TableData
)

logger = logging.getLogger(__name__)

class IngestAgent:
    """
    Agent responsible for ingesting PDFs and converting them into structured DocumentArtifacts.
    Uses a hybrid approach:
    - PyMuPDF (fitz): Fast metadata and text extraction.
    - pdfplumber: Accurate table extraction.
    """
    
    def __init__(self):
        pass

    def process(self, pdf_path: str) -> Optional[DocumentArtifact]:
        """
        Main entry point. Parses PDF and returns a structured artifact.
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        try:
            # 1. Fast Extraction with PyMuPDF
            doc_meta, sections, full_text_len = self._extract_text_and_meta(path)
            
            # 2. Table Extraction with pdfplumber
            tables = self._extract_tables(path)
            
            # 3. Construct Artifact
            artifact = DocumentArtifact(
                doc_id=f"file:{path.name}", # Temporary ID, needs refinement if DOI available
                source=SourceInfo(type="pdf", ref=str(path.absolute())),
                metadata=doc_meta,
                sections=sections,
                tables=tables
            )
            
            # Refine ID if DOI found in metadata
            if artifact.metadata.doi:
                artifact.doc_id = f"doi:{artifact.metadata.doi}"
                
            logger.info(f"Ingested {path.name}: {len(sections)} sections, {len(tables)} tables.")
            return artifact
            
        except Exception as e:
            logger.error(f"Failed to ingest PDF {pdf_path}: {e}")
            return None

    def _extract_text_and_meta(self, path: Path) -> Tuple[PaperMetadata, List[Section], int]:
        """
        Uses PyMuPDF to extract metadata and text split by heuristic sections.
        """
        doc = fitz.open(path)
        
        # Metadata
        meta = doc.metadata
        paper_meta = PaperMetadata(
            title=meta.get('title', path.stem),
            authors=[meta.get('author', '')] if meta.get('author') else [],
            year=int(meta.get('creationDate', '0')[2:6]) if meta.get('creationDate') and len(meta.get('creationDate')) > 6 else 0,
            journal=meta.get('subject', 'Unknown')
        )
        
        # Text Extraction & Segmentation
        sections = []
        global_text = ""
        current_section_name = "preamble"
        start_char = 0
        
        # Simple heuristic keywords for sections
        SECTION_HEADERS = {
            "abstract": ["abstract", "summary"],
            "introduction": ["introduction", "background"],
            "methods": ["methods", "methodology", "experimental procedures", "materials and methods"],
            "results": ["results", "findings"],
            "discussion": ["discussion", "conclusion"],
            "references": ["references", "bibliography"]
        }
        
        # Accumulate text page by page
        for page_num, page in enumerate(doc):
            text = page.get_text()
            
            # Check for section headers in the first few lines of the page or blocks
            # This is a naive heuristic. Improved logic would check font size/boldness.
            lines = text.split('\n')
            for line in lines:
                clean_line = line.strip().lower()
                # If line is short and matches a header keyword
                if len(clean_line) < 50:
                    for sec_name, keywords in SECTION_HEADERS.items():
                        if any(k in clean_line for k in keywords):
                            if current_section_name != sec_name:
                                # Finish previous section logic could go here if we tracked per-section text buffer
                                # For now, we assume strict linear flow (which isn't always true for 2-column)
                                # Better approach: Just tag the change.
                                current_section_name = sec_name
                                break
            
            # For this MVP, we will just create ONE section per page to avoid granular complexity,
            # unless we implement a much smarter parser.
            # Correction: The prompt asks for "sections".
            # Let's try to map pages to sections roughly.
            
            # Actually, a better simple strategy for MVP:
            # 1. Get all text.
            # 2. Regex find headers.
            # 3. Slice.
            
            # Let's stick to Page-based sections for robustness if regex fails, 
            # OR create a single "full_text" section if structure is unclear.
            
            # Let's append to global text and keep track of indices.
            page_start_char = len(global_text)
            global_text += text + "\n"
            page_end_char = len(global_text)
            
            sections.append(Section(
                name=f"page_{page_num+1}", # Fallback name
                text=text,
                char_start=page_start_char,
                char_end=page_end_char,
                page_start=page_num+1,
                page_end=page_num+1
            ))
            
        doc.close()
        return paper_meta, sections, len(global_text)

    def _extract_tables(self, path: Path) -> List[TableData]:
        """
        Uses pdfplumber to extract tables.
        """
        tables = []
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    extracted = page.extract_tables()
                    for j, table in enumerate(extracted):
                        # Clean table data
                        clean_data = [
                            [cell.strip() if cell else "" for cell in row]
                            for row in table
                            if any(row) # Skip empty rows
                        ]
                        
                        if clean_data:
                            tables.append(TableData(
                                table_id=f"T{len(tables)+1}",
                                caption=f"Table found on page {i+1}",
                                data=clean_data,
                                source_page=i+1
                            ))
        except Exception as e:
            logger.warning(f"Table extraction failed for {path}: {e}")
            
        return tables
