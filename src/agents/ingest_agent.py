import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.ingest.cloud_table_fallback import CloudTableFallbackExtractor
from src.ingest.ocr_fallback import build_ocr_cache_path, detect_need_ocr, run_ocr
from src.ingest.parser_backends import (
    TABLE_FAIL_BUDGET_EXCEEDED,
    TABLE_FAIL_OCR_LOW_CONF,
    ParserBackend,
    TableExtractionResult,
    create_parser_backend,
)
from src.schemas.agent_artifacts import DocumentArtifact, PaperMetadata, Section, SourceInfo, TableData

logger = logging.getLogger(__name__)


DEFAULT_TABLE_EXTRACTION_META = {
    "parser_backend": "fitz_pdfplumber",
    "table_extraction_pass": "pass1",
    "table_failure_taxonomy": [],
    "fallback_used": False,
    "fallback_pages": [],
}


class IngestAgent:
    """
    Agent responsible for ingesting PDFs and converting them into structured artifacts.
    """

    def __init__(
        self,
        parser_backend: str = "fitz_pdfplumber",
        enable_ocr_fallback: bool = False,
        ocr_lang: str = "eng",
        ocr_min_text_chars: int = 200,
        enable_table_pass2_ocr: bool = False,
        enable_cloud_table_fallback: bool = False,
        cloud_table_page_budget: int = 2,
        cloud_table_model: str = "gpt-4o-mini",
        cloud_table_base_url: Optional[str] = None,
        cloud_table_api_key: Optional[str] = None,
        cloud_table_timeout_seconds: int = 30,
    ):
        self.backend: ParserBackend = create_parser_backend(parser_backend)
        self.enable_ocr_fallback = bool(enable_ocr_fallback)
        self.ocr_lang = str(ocr_lang or "eng")
        self.ocr_min_text_chars = int(ocr_min_text_chars)
        self.enable_table_pass2_ocr = bool(enable_table_pass2_ocr)
        self.enable_cloud_table_fallback = bool(enable_cloud_table_fallback)
        self.cloud_table_page_budget = int(cloud_table_page_budget)
        self.cloud_table_model = str(cloud_table_model or "gpt-4o-mini")
        self.cloud_table_base_url = str(cloud_table_base_url).strip() if cloud_table_base_url else None
        self.cloud_table_api_key = str(cloud_table_api_key).strip() if cloud_table_api_key else None
        self.cloud_table_timeout_seconds = int(cloud_table_timeout_seconds)
        self.last_table_extraction_meta = dict(DEFAULT_TABLE_EXTRACTION_META)
        self.last_table_extraction_meta["parser_backend"] = self.backend.name()

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
        enable_ocr_fallback: Optional[bool] = None,
        ocr_lang: Optional[str] = None,
        ocr_min_text_chars: Optional[int] = None,
        enable_table_pass2_ocr: Optional[bool] = None,
        enable_cloud_table_fallback: Optional[bool] = None,
        cloud_table_page_budget: Optional[int] = None,
        cloud_table_model: Optional[str] = None,
        cloud_table_base_url: Optional[str] = None,
        cloud_table_api_key: Optional[str] = None,
        cloud_table_timeout_seconds: Optional[int] = None,
    ) -> Optional[DocumentArtifact]:
        """
        Main entry point. Parses PDF and returns a structured artifact.
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.error("PDF file not found: %s", pdf_path)
            return None

        enable_ocr_fallback_resolved = self.enable_ocr_fallback if enable_ocr_fallback is None else bool(enable_ocr_fallback)
        ocr_lang_resolved = self.ocr_lang if ocr_lang is None else str(ocr_lang or "eng")
        ocr_min_text_chars_resolved = (
            self.ocr_min_text_chars if ocr_min_text_chars is None else int(ocr_min_text_chars)
        )
        enable_table_pass2_ocr_resolved = (
            self.enable_table_pass2_ocr if enable_table_pass2_ocr is None else bool(enable_table_pass2_ocr)
        )
        enable_cloud_table_fallback_resolved = (
            self.enable_cloud_table_fallback
            if enable_cloud_table_fallback is None
            else bool(enable_cloud_table_fallback)
        )
        cloud_table_page_budget_resolved = (
            self.cloud_table_page_budget
            if cloud_table_page_budget is None
            else int(cloud_table_page_budget)
        )
        cloud_table_model_resolved = (
            self.cloud_table_model if cloud_table_model is None else str(cloud_table_model or "gpt-4o-mini")
        )
        cloud_table_base_url_resolved = (
            self.cloud_table_base_url
            if cloud_table_base_url is None
            else (str(cloud_table_base_url).strip() or None)
        )
        cloud_table_api_key_resolved = (
            self.cloud_table_api_key if cloud_table_api_key is None else (str(cloud_table_api_key).strip() or None)
        )
        cloud_table_timeout_seconds_resolved = (
            self.cloud_table_timeout_seconds
            if cloud_table_timeout_seconds is None
            else int(cloud_table_timeout_seconds)
        )

        ingest_path = path
        ocr_meta = {
            "ocr_applied": False,
            "ocr_engine": None,
            "ocr_version": None,
            "ocr_lang": None,
            "ocr_output_path": None,
            "error": None,
        }
        self.last_table_extraction_meta = dict(DEFAULT_TABLE_EXTRACTION_META)
        self.last_table_extraction_meta["parser_backend"] = self.backend.name()

        try:
            if enable_ocr_fallback_resolved and detect_need_ocr(path, min_text_chars=ocr_min_text_chars_resolved):
                ocr_cache_path = build_ocr_cache_path(path, cache_dir=Path("storage/ocr_cache"), lang=ocr_lang_resolved)
                ocr_meta = run_ocr(path, ocr_cache_path, lang=ocr_lang_resolved)
                if ocr_meta.get("ocr_applied") and ocr_meta.get("ocr_output_path"):
                    candidate = Path(str(ocr_meta["ocr_output_path"]))
                    if candidate.exists():
                        ingest_path = candidate

            doc_meta, sections, _ = self._extract_text_and_meta(ingest_path)
            pass1 = self.backend.extract_tables(ingest_path)
            tables = pass1.tables
            table_extraction_pass = pass1.diagnostics.table_extraction_pass or "pass1"
            table_failure_taxonomy = set(pass1.diagnostics.table_failure_taxonomy or [])
            fallback_used = bool(pass1.diagnostics.fallback_used)
            fallback_pages = list(pass1.diagnostics.fallback_pages or [])

            # Pass2: OCR-based table recovery if pass1 produced no tables.
            if not tables and enable_table_pass2_ocr_resolved:
                table_ocr_path: Optional[Path] = None
                if ocr_meta.get("ocr_applied") and ocr_meta.get("ocr_output_path"):
                    candidate = Path(str(ocr_meta["ocr_output_path"]))
                    if candidate.exists():
                        table_ocr_path = candidate
                else:
                    need_ocr_for_tables = detect_need_ocr(path, min_text_chars=ocr_min_text_chars_resolved)
                    if need_ocr_for_tables:
                        ocr_cache_path = build_ocr_cache_path(
                            path, cache_dir=Path("storage/ocr_cache"), lang=ocr_lang_resolved
                        )
                        pass2_ocr_meta = run_ocr(path, ocr_cache_path, lang=ocr_lang_resolved)
                        if pass2_ocr_meta.get("ocr_applied") and pass2_ocr_meta.get("ocr_output_path"):
                            candidate = Path(str(pass2_ocr_meta["ocr_output_path"]))
                            if candidate.exists():
                                table_ocr_path = candidate
                                if not ocr_meta.get("ocr_applied"):
                                    ocr_meta = pass2_ocr_meta

                if table_ocr_path is not None:
                    pass2 = self.backend.extract_tables(table_ocr_path)
                    table_failure_taxonomy.update(pass2.diagnostics.table_failure_taxonomy or [])
                    if pass2.tables:
                        tables = pass2.tables
                        table_extraction_pass = "pass2"
                        fallback_used = True
                        fallback_pages = sorted(
                            {
                                int(t.source_page)
                                for t in tables
                                if isinstance(getattr(t, "source_page", None), int) and int(t.source_page) > 0
                            }
                        )
                    else:
                        table_failure_taxonomy.add(TABLE_FAIL_OCR_LOW_CONF)
                else:
                    table_failure_taxonomy.add(TABLE_FAIL_OCR_LOW_CONF)

            # Pass3: Cloud fallback on selected pages within explicit budget.
            if not tables and enable_cloud_table_fallback_resolved:
                if cloud_table_page_budget_resolved <= 0:
                    table_failure_taxonomy.add(TABLE_FAIL_BUDGET_EXCEEDED)
                else:
                    pass3 = self._extract_tables_pass3_cloud(
                        path=path,
                        page_budget=cloud_table_page_budget_resolved,
                        model=cloud_table_model_resolved,
                        api_key=cloud_table_api_key_resolved,
                        base_url=cloud_table_base_url_resolved,
                        timeout_seconds=cloud_table_timeout_seconds_resolved,
                    )
                    table_extraction_pass = pass3.diagnostics.table_extraction_pass or "pass3"
                    table_failure_taxonomy.update(pass3.diagnostics.table_failure_taxonomy or [])
                    fallback_pages = sorted(
                        {
                            int(p)
                            for p in (fallback_pages + list(pass3.diagnostics.fallback_pages or []))
                            if isinstance(p, int) and int(p) > 0
                        }
                    )
                    if pass3.tables:
                        tables = pass3.tables
                        fallback_used = True

            doc_meta.ocr_applied = bool(ocr_meta.get("ocr_applied"))
            doc_meta.ocr_engine = ocr_meta.get("ocr_engine")
            doc_meta.ocr_version = ocr_meta.get("ocr_version")
            doc_meta.ocr_lang = ocr_meta.get("ocr_lang")
            doc_meta.ocr_error = ocr_meta.get("error")
            doc_meta.ocr_output_path = ocr_meta.get("ocr_output_path")

            self.last_table_extraction_meta = {
                "parser_backend": self.backend.name(),
                "table_extraction_pass": table_extraction_pass,
                "table_failure_taxonomy": sorted(table_failure_taxonomy),
                "fallback_used": bool(fallback_used),
                "fallback_pages": sorted({int(p) for p in fallback_pages if isinstance(p, int)}),
            }

            artifact = DocumentArtifact(
                doc_id=f"file:{path.name}",
                source=SourceInfo(type="pdf", ref=str(path.absolute())),
                metadata=doc_meta,
                sections=sections,
                tables=tables,
            )
            if artifact.metadata.doi:
                artifact.doc_id = f"doi:{artifact.metadata.doi}"

            logger.info(
                "Ingested %s via parser=%s: %d sections, %d tables.",
                path.name,
                self.backend.name(),
                len(sections),
                len(tables),
            )
            return artifact

        except Exception as exc:
            logger.error("Failed to ingest PDF %s: %s", pdf_path, exc)
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
        return self.backend.extract_text_and_meta(path)

    def _extract_tables(self, path: Path) -> List[TableData]:
        table_result = self.backend.extract_tables(path)
        self.last_table_extraction_meta = {
            "parser_backend": self.backend.name(),
            "table_extraction_pass": table_result.diagnostics.table_extraction_pass,
            "table_failure_taxonomy": list(table_result.diagnostics.table_failure_taxonomy or []),
            "fallback_used": bool(table_result.diagnostics.fallback_used),
            "fallback_pages": [int(p) for p in (table_result.diagnostics.fallback_pages or [])],
        }
        return table_result.tables

    def _build_v2_from_pdf(self, path: Path, legacy: DocumentArtifact) -> DocumentArtifactV2:
        return self.backend.build_v2_from_pdf(path, legacy)

    def _extract_tables_pass3_cloud(
        self,
        path: Path,
        page_budget: int,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout_seconds: int,
    ) -> TableExtractionResult:
        extractor = CloudTableFallbackExtractor(
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        return extractor.extract_tables(pdf_path=path, page_budget=page_budget)
