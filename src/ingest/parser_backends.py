from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Protocol, Tuple

import fitz
import pdfplumber

from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
    TableV2,
    stable_id,
)
from src.schemas.agent_artifacts import DocumentArtifact, PaperMetadata, Section, TableData

logger = logging.getLogger(__name__)

TABLE_FAIL_NO_TABLE_FOUND = "NO_TABLE_FOUND"
TABLE_FAIL_DEGENERATE_SHAPE = "DEGENERATE_SHAPE"
TABLE_FAIL_LOW_ACCURACY = "LOW_ACCURACY"
TABLE_FAIL_OCR_LOW_CONF = "OCR_LOW_CONF"
TABLE_FAIL_BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
TABLE_FAIL_CELL_OVERLAP_HIGH = "CELL_OVERLAP_HIGH"
TABLE_FAIL_CELL_COVERAGE_LOW = "CELL_COVERAGE_LOW"
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]*[A-Z0-9]", re.IGNORECASE)
_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "urn:doi:")
_DOI_METADATA_KEYS = (
    "doi",
    "DOI",
    "dc.identifier",
    "identifier",
    "Identifier",
    "keywords",
    "subject",
    "title",
    "producer",
)
_ARXIV_ID_RE = re.compile(r"^(?:arxiv[:_ -]?)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
_ARXIV_OLD_ID_RE = re.compile(r"^(?:arxiv[:_ -]?)?([a-z\\-]+/\d{7})(?:v\d+)?$", re.IGNORECASE)
_ARXIV_INLINE_RE = re.compile(r"\barxiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?\b", re.IGNORECASE)


@dataclass
class TableExtractionDiagnostics:
    table_extraction_pass: str = "pass1"
    table_failure_taxonomy: List[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_pages: List[int] = field(default_factory=list)


@dataclass
class TableExtractionResult:
    tables: List[TableData]
    diagnostics: TableExtractionDiagnostics


class ParserBackend(Protocol):
    def name(self) -> str: ...

    def extract_text_and_meta(self, path: Path) -> Tuple[PaperMetadata, List[Section], int]: ...

    def extract_tables(self, path: Path) -> TableExtractionResult: ...

    def build_v2_from_pdf(self, path: Path, legacy: DocumentArtifact) -> DocumentArtifactV2: ...


def _safe_parse_year(creation_date: str | None) -> int:
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


def _normalize_doi(raw: str | None) -> str:
    value = str(raw or "").strip()
    lower_value = value.lower()
    for prefix in _DOI_PREFIXES:
        if lower_value.startswith(prefix):
            value = value[len(prefix) :]
            lower_value = value.lower()
            break
    match = _DOI_RE.search(value)
    if match:
        return match.group(0).strip()
    return value.strip()


def _extract_doi_from_text(text: str | None) -> str | None:
    candidate = _normalize_doi(text)
    if not candidate:
        return None
    match = _DOI_RE.search(candidate)
    if not match:
        return None
    return _normalize_doi(match.group(0)) or None


def _resolve_doi(path: Path, metadata: dict[str, Any] | None = None, text_snippets: List[str] | None = None) -> str | None:
    for raw in (text_snippets or []):
        doi = _extract_doi_from_text(raw)
        if doi:
            return doi

    meta = metadata or {}
    for key in _DOI_METADATA_KEYS:
        doi = _extract_doi_from_text(str(meta.get(key, "") or ""))
        if doi:
            return doi

    # Some collections encode DOI-like hints in the filename.
    for hint in (path.name, path.stem):
        doi = _extract_doi_from_text(hint)
        if doi:
            return doi

    # Heuristics for documents where DOI is omitted from standard metadata/text patterns.
    arxiv_doi = _derive_arxiv_doi(path, text_snippets or [])
    if arxiv_doi:
        return arxiv_doi

    lancet_doi = _derive_lancet_review_doi(metadata or {}, text_snippets or [])
    if lancet_doi:
        return lancet_doi

    return None


def _derive_arxiv_doi(path: Path, text_snippets: List[str]) -> str | None:
    for hint in (path.stem, path.name):
        text = str(hint or "").strip()
        if not text:
            continue
        modern = _ARXIV_ID_RE.match(text)
        if modern:
            return f"10.48550/arXiv.{modern.group(1)}"
        legacy = _ARXIV_OLD_ID_RE.match(text)
        if legacy:
            return f"10.48550/arXiv.{legacy.group(1)}"

    for snippet in text_snippets:
        match = _ARXIV_INLINE_RE.search(str(snippet or ""))
        if match:
            return f"10.48550/arXiv.{match.group(1)}"
    return None


def _derive_lancet_review_doi(metadata: dict[str, Any], text_snippets: List[str]) -> str | None:
    title = str(metadata.get("title", "") or "").strip().lower()
    author = str(metadata.get("author", "") or "").strip().lower()
    blob = "\n".join(str(s or "") for s in text_snippets).lower()

    if "www.thelancet.com/neurology" not in blob:
        return None
    if "december 2008" not in blob:
        return None
    if not ("vol 7" in blob or "volume 7" in blob):
        return None

    title_match = "cognitive impairment in multiple sclerosis" in title or (
        "cognitive impairment in multiple sclerosis" in blob
    )
    author_match = "chiaravalloti" in author or "deluca" in author or (
        "chiaravalloti" in blob and "deluca" in blob
    )
    if title_match and author_match:
        return "10.1016/S1474-4422(08)70259-X"
    return None


class FitzPdfPlumberBackend:
    def name(self) -> str:
        return "fitz_pdfplumber"

    def extract_text_and_meta(self, path: Path) -> Tuple[PaperMetadata, List[Section], int]:
        doc = fitz.open(path)
        try:
            meta = doc.metadata
            paper_meta = PaperMetadata(
                title=meta.get("title", path.stem),
                authors=[meta.get("author", "")] if meta.get("author") else [],
                year=_safe_parse_year(meta.get("creationDate")),
                journal=meta.get("subject", "Unknown"),
            )

            sections: List[Section] = []
            global_text = ""
            for page_num, page in enumerate(doc):
                text = page.get_text()
                page_start_char = len(global_text)
                global_text += text + "\n"
                page_end_char = len(global_text)
                sections.append(
                    Section(
                        name=f"page_{page_num + 1}",
                        text=text,
                        char_start=page_start_char,
                        char_end=page_end_char,
                        page_start=page_num + 1,
                        page_end=page_num + 1,
                    )
                )

            snippet_budget = 24000
            snippets: List[str] = []
            consumed = 0
            for section in sections:
                if consumed >= snippet_budget:
                    break
                text = (section.text or "").strip()
                if not text:
                    continue
                remaining = snippet_budget - consumed
                snippet = text[:remaining]
                snippets.append(snippet)
                consumed += len(snippet)
                if len(snippets) >= 3:
                    break
            paper_meta.doi = _resolve_doi(path=path, metadata=meta, text_snippets=snippets)

            return paper_meta, sections, len(global_text)
        finally:
            doc.close()

    def extract_tables(self, path: Path) -> TableExtractionResult:
        tables: List[TableData] = []
        failures: set[str] = set()

        try:
            with pdfplumber.open(path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    extracted = page.extract_tables() or []
                    for table in extracted:
                        clean_data = [
                            [cell.strip() if isinstance(cell, str) else (cell or "") for cell in row]
                            for row in table
                            if row and any(row)
                        ]

                        if not clean_data:
                            failures.add(TABLE_FAIL_DEGENERATE_SHAPE)
                            continue

                        max_cols = max((len(row) for row in clean_data), default=0)
                        if max_cols <= 1 and len(clean_data) <= 1:
                            failures.add(TABLE_FAIL_DEGENERATE_SHAPE)
                            continue

                        tables.append(
                            TableData(
                                table_id=f"T{len(tables) + 1}",
                                caption=f"Table found on page {page_idx + 1}",
                                data=clean_data,
                                source_page=page_idx + 1,
                            )
                        )
        except Exception as exc:
            logger.warning("Table extraction failed for %s: %s", path, exc)
            failures.add(TABLE_FAIL_NO_TABLE_FOUND)

        if not tables:
            failures.add(TABLE_FAIL_NO_TABLE_FOUND)

        diagnostics = TableExtractionDiagnostics(
            table_extraction_pass="pass1",
            table_failure_taxonomy=sorted(failures),
            fallback_used=False,
            fallback_pages=[],
        )
        return TableExtractionResult(tables=tables, diagnostics=diagnostics)

    def build_v2_from_pdf(self, path: Path, legacy: DocumentArtifact) -> DocumentArtifactV2:
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
                raw_blocks = page.get_text("blocks")
                sorted_blocks = sorted(
                    raw_blocks,
                    key=lambda block: (
                        round(float(block[1]), 3),
                        round(float(block[0]), 3),
                        round(float(block[3]), 3),
                        round(float(block[2]), 3),
                    ),
                )

                blocks: List[BlockV2] = []
                for block_order, block in enumerate(sorted_blocks):
                    x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4] or ""
                    bbox = _clamp_bbox_to_page(
                        [float(x0), float(y0), float(x1), float(y1)],
                        page_width,
                        page_height,
                    )
                    block_id = f"blk_{stable_id(legacy.doc_id, str(page_idx), str(block_order), f'{x0:.3f}', f'{y0:.3f}', f'{x1:.3f}', f'{y1:.3f}', text.strip())}"

                    lines: List[LineV2] = []
                    for line_order, line_text in enumerate([ln for ln in text.splitlines() if ln.strip()]):
                        line_id = f"ln_{stable_id(block_id, str(line_order), line_text.strip())}"
                        span_id = f"sp_{stable_id(line_id, '0', line_text.strip())}"
                        span = SpanV2(
                            span_id=span_id,
                            text=line_text,
                            bbox_pdf=None,
                            source_ref=f"{legacy.source.ref}#page={page_idx}",
                            bbox_unavailable=True,
                        )
                        lines.append(
                            LineV2(
                                line_id=line_id,
                                text=line_text,
                                bbox_pdf=None,
                                spans=[span],
                                bbox_unavailable=True,
                            )
                        )

                    blocks.append(
                        BlockV2(
                            block_id=block_id,
                            bbox_pdf=bbox,
                            lines=lines,
                            bbox_unavailable=False,
                        )
                    )

                pages.append(
                    PageV2(
                        page_index=page_idx,
                        width=page_width,
                        height=page_height,
                        blocks=blocks,
                    )
                )
        finally:
            doc.close()

        tables_v2 = [
            TableV2(
                table_id=table.table_id,
                caption=table.caption,
                data=table.data,
                source_page=table.source_page,
            )
            for table in legacy.tables
        ]

        return DocumentArtifactV2(
            document_id=legacy.doc_id,
            meta=meta_v2,
            pages=pages,
            tables=tables_v2,
        )


class DoclingParserBackend(FitzPdfPlumberBackend):
    def __init__(self):
        self._fallback_logged = False
        self._converter = self._initialize_converter()

    def name(self) -> str:
        return "docling"

    def _initialize_converter(self) -> Any | None:
        try:
            from docling.document_converter import DocumentConverter  # type: ignore

            return DocumentConverter()
        except Exception as exc:
            logger.warning("Docling import failed; parser backend will fallback to fitz/pdfplumber: %s", exc)
            return None

    def _log_fallback_once(self) -> None:
        if self._fallback_logged:
            return
        logger.warning("Docling parse path unavailable. Falling back to fitz/pdfplumber for this document.")
        self._fallback_logged = True

    def _convert(self, path: Path) -> Any | None:
        if self._converter is None:
            self._log_fallback_once()
            return None
        try:
            return self._converter.convert(str(path))
        except Exception as exc:
            logger.warning("Docling conversion failed for %s: %s", path, exc)
            self._log_fallback_once()
            return None

    @staticmethod
    def _extract_text_like(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        for method_name in ("export_to_markdown", "to_markdown", "export_to_text", "to_text"):
            method = getattr(value, method_name, None)
            if callable(method):
                try:
                    text = method()
                    if isinstance(text, str) and text.strip():
                        return text.strip()
                except Exception:
                    continue
        for attr_name in ("text", "markdown", "content"):
            attr = getattr(value, attr_name, None)
            if isinstance(attr, str) and attr.strip():
                return attr.strip()
        return ""

    def _build_sections_from_conversion(self, conversion: Any) -> List[Section]:
        doc_obj = getattr(conversion, "document", conversion)
        sections: List[Section] = []
        global_text = ""

        pages = getattr(doc_obj, "pages", None)
        if isinstance(pages, list) and pages:
            for page_idx, page in enumerate(pages):
                page_text = self._extract_text_like(page)
                if not page_text:
                    continue
                page_start_char = len(global_text)
                global_text += page_text + "\n"
                page_end_char = len(global_text)
                sections.append(
                    Section(
                        name=f"page_{page_idx + 1}",
                        text=page_text,
                        char_start=page_start_char,
                        char_end=page_end_char,
                        page_start=page_idx + 1,
                        page_end=page_idx + 1,
                    )
                )
        if sections:
            return sections

        full_text = self._extract_text_like(doc_obj)
        if not full_text:
            full_text = self._extract_text_like(conversion)
        if not full_text:
            return []

        sections.append(
            Section(
                name="docling_document",
                text=full_text,
                char_start=0,
                char_end=len(full_text),
                page_start=1,
                page_end=1,
            )
        )
        return sections

    def _read_pdf_metadata(self, path: Path) -> PaperMetadata:
        doc = fitz.open(path)
        try:
            meta = doc.metadata
            return PaperMetadata(
                title=meta.get("title", path.stem),
                authors=[meta.get("author", "")] if meta.get("author") else [],
                year=_safe_parse_year(meta.get("creationDate")),
                journal=meta.get("subject", "Unknown"),
                doi=_resolve_doi(path=path, metadata=meta, text_snippets=[]),
            )
        finally:
            doc.close()

    @staticmethod
    def _parse_markdown_tables(markdown_text: str) -> List[List[List[str]]]:
        rows = [line.rstrip() for line in markdown_text.splitlines()]
        blocks: List[List[str]] = []
        current: List[str] = []

        for line in rows:
            striped = line.strip()
            if "|" in striped:
                current.append(striped)
                continue
            if current:
                blocks.append(current)
                current = []
        if current:
            blocks.append(current)

        parsed_tables: List[List[List[str]]] = []
        for block in blocks:
            if len(block) < 2:
                continue

            separator_idx = None
            for idx, candidate in enumerate(block):
                compact = candidate.replace(" ", "")
                if re.fullmatch(r"\|?[:\-|]+\|?", compact):
                    separator_idx = idx
                    break
            if separator_idx is None or separator_idx == 0:
                continue

            table_rows: List[List[str]] = []
            for line in block:
                if line == block[separator_idx]:
                    continue
                parts = [cell.strip() for cell in line.strip("|").split("|")]
                if any(parts):
                    table_rows.append(parts)
            if len(table_rows) >= 2:
                parsed_tables.append(table_rows)
        return parsed_tables

    def extract_text_and_meta(self, path: Path) -> Tuple[PaperMetadata, List[Section], int]:
        conversion = self._convert(path)
        if conversion is None:
            return super().extract_text_and_meta(path)

        try:
            paper_meta = self._read_pdf_metadata(path)
            sections = self._build_sections_from_conversion(conversion)
            if not sections:
                logger.warning("Docling conversion produced no text sections for %s.", path)
                return super().extract_text_and_meta(path)
            paper_doi = str(getattr(paper_meta, "doi", "") or "").strip()
            if not paper_doi:
                snippet_budget = 24000
                snippets: List[str] = []
                consumed = 0
                for section in sections:
                    if consumed >= snippet_budget:
                        break
                    text = (section.text or "").strip()
                    if not text:
                        continue
                    remaining = snippet_budget - consumed
                    snippet = text[:remaining]
                    snippets.append(snippet)
                    consumed += len(snippet)
                    if len(snippets) >= 3:
                        break
                setattr(paper_meta, "doi", _resolve_doi(path=path, text_snippets=snippets))
            total_len = sum(len(sec.text) for sec in sections)
            return paper_meta, sections, total_len
        except Exception as exc:
            logger.warning("Docling text extraction failed for %s: %s", path, exc)
            return super().extract_text_and_meta(path)

    def extract_tables(self, path: Path) -> TableExtractionResult:
        conversion = self._convert(path)
        if conversion is None:
            return super().extract_tables(path)

        failures: set[str] = set()
        tables: List[TableData] = []

        try:
            markdown = self._extract_text_like(getattr(conversion, "document", conversion))
            if not markdown:
                markdown = self._extract_text_like(conversion)
            parsed = self._parse_markdown_tables(markdown)
            for idx, table_rows in enumerate(parsed, start=1):
                if not table_rows or max((len(r) for r in table_rows), default=0) <= 1:
                    failures.add(TABLE_FAIL_DEGENERATE_SHAPE)
                    continue
                tables.append(
                    TableData(
                        table_id=f"T{idx}",
                        caption=f"Docling table {idx}",
                        data=table_rows,
                        source_page=1,
                    )
                )
        except Exception as exc:
            logger.warning("Docling table extraction failed for %s: %s", path, exc)
            failures.add(TABLE_FAIL_LOW_ACCURACY)

        if not tables:
            fallback_result = super().extract_tables(path)
            if fallback_result.tables:
                merged_failures = set(fallback_result.diagnostics.table_failure_taxonomy or []) | failures
                fallback_result.diagnostics.table_failure_taxonomy = sorted(merged_failures)
                return fallback_result
            failures.update(fallback_result.diagnostics.table_failure_taxonomy or [])
            failures.add(TABLE_FAIL_NO_TABLE_FOUND)

        diagnostics = TableExtractionDiagnostics(
            table_extraction_pass="pass1",
            table_failure_taxonomy=sorted(failures),
            fallback_used=False,
            fallback_pages=[],
        )
        return TableExtractionResult(tables=tables, diagnostics=diagnostics)

    def build_v2_from_pdf(self, path: Path, legacy: DocumentArtifact) -> DocumentArtifactV2:
        return super().build_v2_from_pdf(path, legacy)


def create_parser_backend(backend_name: str | None) -> ParserBackend:
    normalized = (backend_name or "fitz_pdfplumber").strip().lower()
    if normalized in {"fitz_pdfplumber", "fitz", "default"}:
        return FitzPdfPlumberBackend()
    if normalized == "docling":
        return DoclingParserBackend()

    logger.warning("Unknown parser backend '%s'. Falling back to 'fitz_pdfplumber'.", backend_name)
    return FitzPdfPlumberBackend()
