
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from src.schemas.agent_artifacts import (
    DocumentArtifact, 
    PaperMetadata,
    Section,
    SourceInfo, 
    TableData,
)
from src.contracts.document_artifact_v2 import (
    DocumentArtifactV2,
)
from src.agents.ingest_core import (
    build_v2_from_pdf,
    clamp_bbox_to_page,
    extract_tables,
    extract_text_and_meta,
    safe_parse_year,
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
        return safe_parse_year(creation_date)

    @staticmethod
    def _clamp_bbox_to_page(bbox: List[float], page_width: float, page_height: float) -> List[float]:
        return clamp_bbox_to_page(bbox, page_width, page_height)

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
        return extract_text_and_meta(path, self._safe_parse_year)

    def _extract_tables(self, path: Path) -> List[TableData]:
        return extract_tables(path)

    def _build_v2_from_pdf(self, path: Path, legacy: DocumentArtifact) -> DocumentArtifactV2:
        return build_v2_from_pdf(path, legacy, self._clamp_bbox_to_page)
