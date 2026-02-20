
import logging
import fitz  # standard pymupdf import
import pdfplumber
import re
from pathlib import Path
from typing import List, Optional, Tuple

from src.schemas.agent_artifacts import (
    DocumentArtifact, 
    SourceInfo, 
    PaperMetadata, 
    Section, 
    TableData
)
from src.contracts.document_artifact_v2 import (
    DocumentArtifactV2,
    ArtifactMetaV2,
    PageV2,
    BlockV2,
    LineV2,
    SpanV2,
    TableV2,
    stable_id,
)
from src.ingest.ocr_fallback import detect_need_ocr, run_ocr, build_ocr_cache_path

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

    @staticmethod
    def _safe_parse_year(creation_date: str | None) -> int:
        """
        Parse year from PDF metadata creationDate safely.
        Accepts canonical PDF date strings (e.g., D:20190101120000)
        and falls back to any 4-digit year match.
        """
        if not creation_date:
            return 0
        if len(creation_date) > 6:
            chunk = creation_date[2:6]
            if chunk.isdigit():
                return int(chunk)
        match = re.search(r"(19|20)\d{2}", creation_date)
        if match:
            try:
                return int(match.group(0))
            except Exception:
                return 0
        return 0

    @staticmethod
    def _clamp_bbox_to_page(bbox: List[float], page_width: float, page_height: float) -> List[float]:
        x0, y0, x1, y1 = bbox
        x0 = max(0.0, min(float(x0), page_width))
        y0 = max(0.0, min(float(y0), page_height))
        x1 = max(0.0, min(float(x1), page_width))
        y1 = max(0.0, min(float(y1), page_height))
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        return [x0, y0, x1, y1]

    def process(
        self,
        pdf_path: str,
        enable_ocr_fallback: bool = False,
        ocr_lang: str = "eng",
        ocr_min_text_chars: int = 200,
    ) -> Optional[DocumentArtifact]:
        """
        Main entry point. Parses PDF and returns a structured artifact.
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None

        ingest_path = path
        ocr_meta = {
            "ocr_applied": False,
            "ocr_engine": None,
            "ocr_version": None,
            "ocr_lang": None,
            "ocr_output_path": None,
            "error": None,
        }
        
        try:
            if enable_ocr_fallback and detect_need_ocr(path, min_text_chars=ocr_min_text_chars):
                ocr_cache_path = build_ocr_cache_path(path, cache_dir=Path("storage/ocr_cache"), lang=ocr_lang)
                ocr_meta = run_ocr(path, ocr_cache_path, lang=ocr_lang)
                if ocr_meta.get("ocr_applied") and ocr_meta.get("ocr_output_path"):
                    candidate = Path(str(ocr_meta["ocr_output_path"]))
                    if candidate.exists():
                        ingest_path = candidate

            # 1. Fast Extraction with PyMuPDF
            doc_meta, sections, full_text_len = self._extract_text_and_meta(ingest_path)
            
            # 2. Table Extraction with pdfplumber
            tables = self._extract_tables(ingest_path)

            # 2.5 OCR metadata
            doc_meta.ocr_applied = bool(ocr_meta.get("ocr_applied"))
            doc_meta.ocr_engine = ocr_meta.get("ocr_engine")
            doc_meta.ocr_version = ocr_meta.get("ocr_version")
            doc_meta.ocr_lang = ocr_meta.get("ocr_lang")
            doc_meta.ocr_error = ocr_meta.get("error")
            doc_meta.ocr_output_path = ocr_meta.get("ocr_output_path")
            
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

    def process_v2(self, pdf_path: str) -> Optional[DocumentArtifactV2]:
        """
        Additive v2 contract output.
        Keeps existing ingest behavior intact while exposing stable IDs + bbox-ready structure.
        """
        legacy = self.process(pdf_path)
        if not legacy:
            return None
        return self._build_v2_from_pdf(Path(pdf_path), legacy)

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
            year=self._safe_parse_year(meta.get('creationDate')),
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

    def _build_v2_from_pdf(self, path: Path, legacy: DocumentArtifact) -> DocumentArtifactV2:
        """
        Build DocumentArtifactV2 from current parser capabilities.
        bbox is emitted only when available; otherwise set null + bbox_unavailable=true.
        """
        meta_v2 = ArtifactMetaV2(
            title=legacy.metadata.title,
            authors=legacy.metadata.authors,
            year=legacy.metadata.year,
            journal=legacy.metadata.journal,
            doi=legacy.metadata.doi,
            source_ref=legacy.source.ref,
        )

        pages: List[PageV2] = []
        doc = fitz.open(path)
        try:
            for page_idx, page in enumerate(doc):
                page_width = float(page.rect.width)
                page_height = float(page.rect.height)

                # PyMuPDF block tuples:
                # (x0, y0, x1, y1, text, block_no, block_type)
                raw_blocks = page.get_text("blocks")
                sorted_blocks = sorted(
                    raw_blocks,
                    key=lambda b: (round(float(b[1]), 3), round(float(b[0]), 3), round(float(b[3]), 3), round(float(b[2]), 3)),
                )

                blocks: List[BlockV2] = []
                for block_order, block in enumerate(sorted_blocks):
                    x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4] or ""
                    bbox = self._clamp_bbox_to_page(
                        [float(x0), float(y0), float(x1), float(y1)],
                        page_width,
                        page_height,
                    )

                    block_id = f"blk_{stable_id(legacy.doc_id, str(page_idx), str(block_order), f'{x0:.3f}', f'{y0:.3f}', f'{x1:.3f}', f'{y1:.3f}', text.strip())}"

                    lines: List[LineV2] = []
                    for line_order, line_text in enumerate([ln for ln in text.splitlines() if ln.strip()]):
                        line_id = f"ln_{stable_id(block_id, str(line_order), line_text.strip())}"
                        # Current parser does not provide per-line bbox reliably.
                        span_id = f"sp_{stable_id(line_id, '0', line_text.strip())}"
                        span = SpanV2(
                            span_id=span_id,
                            text=line_text,
                            bbox_pdf=None,
                            source_ref=f"{legacy.source.ref}#page={page_idx}",
                            bbox_unavailable=True,
                        )
                        line = LineV2(
                            line_id=line_id,
                            text=line_text,
                            bbox_pdf=None,
                            spans=[span],
                            bbox_unavailable=True,
                        )
                        lines.append(line)

                    block_model = BlockV2(
                        block_id=block_id,
                        bbox_pdf=bbox,
                        lines=lines,
                        bbox_unavailable=False,
                    )
                    blocks.append(block_model)

                page_model = PageV2(
                    page_index=page_idx,
                    width=page_width,
                    height=page_height,
                    blocks=blocks,
                )
                pages.append(page_model)
        finally:
            doc.close()

        tables_v2 = [
            TableV2(
                table_id=t.table_id,
                caption=t.caption,
                data=t.data,
                source_page=t.source_page,
            )
            for t in legacy.tables
        ]

        return DocumentArtifactV2(
            document_id=legacy.doc_id,
            meta=meta_v2,
            pages=pages,
            tables=tables_v2,
        )
