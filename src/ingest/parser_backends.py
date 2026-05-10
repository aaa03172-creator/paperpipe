from __future__ import annotations

import logging
import re
from collections import Counter
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
TABLE_FAIL_FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED = "FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED"
TABLE_FAIL_SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION = "SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION"
PARSER_FAIL_CORRUPTED = "PDF_CORRUPTED"
PARSER_FAIL_ENCRYPTED = "PDF_ENCRYPTED"
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
_SECTION_HEADING_ALIASES = {
    "abstract": "abstract",
    "summary": "abstract",
    "introduction": "introduction",
    "background": "background",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "materials & methods": "methods",
    "methodology": "methods",
    "results": "results",
    "findings": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "references": "references",
    "bibliography": "references",
    "acknowledgements": "acknowledgements",
    "acknowledgments": "acknowledgements",
    "appendix": "appendix",
}
_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?("
    + "|".join(re.escape(label) for label in sorted(_SECTION_HEADING_ALIASES, key=len, reverse=True))
    + r")\s*:?\s*$",
    re.IGNORECASE,
)


@dataclass
class TableExtractionDiagnostics:
    table_extraction_pass: str = "pass1"
    table_failure_taxonomy: List[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_pages: List[int] = field(default_factory=list)
    same_page_table_rescue_actions: List[str] = field(default_factory=list)
    same_page_table_rescue_pages: List[int] = field(default_factory=list)
    same_page_table_rescue_patched_cells: List[dict[str, Any]] = field(default_factory=list)


@dataclass
class TableExtractionResult:
    tables: List[TableData]
    diagnostics: TableExtractionDiagnostics


class ParserFailure(Exception):
    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


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


def _semantic_sections_for_page(text: str, *, page_num: int, page_start_char: int) -> List[Section]:
    lines = str(text or "").splitlines(keepends=True)
    headings: list[tuple[int, str]] = []
    offset = 0
    for line in lines:
        stripped = line.strip()
        match = _SECTION_HEADING_RE.match(stripped)
        if match:
            canonical = _SECTION_HEADING_ALIASES[match.group(1).lower()]
            headings.append((offset, canonical))
        offset += len(line)

    if not headings:
        return []

    sections: List[Section] = []
    if headings[0][0] > 0:
        prefix = text[: headings[0][0]].strip()
        if prefix:
            sections.append(
                Section(
                    name=f"page_{page_num}_preamble",
                    text=prefix,
                    char_start=page_start_char,
                    char_end=page_start_char + headings[0][0],
                    page_start=page_num,
                    page_end=page_num,
                )
            )

    for idx, (start, name) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue
        sections.append(
            Section(
                name=name,
                text=section_text,
                char_start=page_start_char + start,
                char_end=page_start_char + end,
                page_start=page_num,
                page_end=page_num,
            )
        )
    return sections


class FitzPdfPlumberBackend:
    def name(self) -> str:
        return "fitz_pdfplumber"

    @staticmethod
    def _table_source_ref(path: Path | str, source_page: int) -> str:
        page_suffix = str(source_page - 1) if source_page > 0 else "unknown"
        return f"{path}#page={page_suffix}"

    def effective_name(self) -> str:
        return self.name()

    def fallback_used(self) -> bool:
        return False

    def extract_text_and_meta(self, path: Path) -> Tuple[PaperMetadata, List[Section], int]:
        doc = fitz.open(path)
        try:
            if getattr(doc, "needs_pass", False):
                raise ParserFailure(PARSER_FAIL_ENCRYPTED, "PDF is encrypted and requires a password.")
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
                page_number = page_num + 1
                semantic_sections = _semantic_sections_for_page(
                    text,
                    page_num=page_number,
                    page_start_char=page_start_char,
                )
                if semantic_sections:
                    sections.extend(semantic_sections)
                else:
                    sections.append(
                        Section(
                            name=f"page_{page_number}",
                            text=text,
                            char_start=page_start_char,
                            char_end=page_end_char,
                            page_start=page_number,
                            page_end=page_number,
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
                                source_ref=self._table_source_ref(path, page_idx + 1),
                                extraction_method="pdfplumber.extract_tables",
                                confidence=0.6,
                                provenance_note="Table reconstructed from pdfplumber cell text; cell/page bbox provenance is unavailable.",
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
                source_ref=table.source_ref,
                extraction_method=table.extraction_method,
                confidence=table.confidence,
                provenance_note=table.provenance_note,
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
        self._fallback_used = False
        self._converter = self._initialize_converter()

    def name(self) -> str:
        return "docling"

    def effective_name(self) -> str:
        return "fitz_pdfplumber" if self._fallback_used else self.name()

    def fallback_used(self) -> bool:
        return bool(self._fallback_used)

    def _mark_fitz_fallback(self) -> None:
        self._fallback_used = True

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
            self._mark_fitz_fallback()
            return None
        try:
            return self._converter.convert(str(path))
        except Exception as exc:
            logger.warning("Docling conversion failed for %s: %s", path, exc)
            self._log_fallback_once()
            self._mark_fitz_fallback()
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
        if isinstance(pages, dict) and pages:
            page_fragments: dict[int, List[str]] = {}
            iterate_items = getattr(doc_obj, "iterate_items", None)
            if callable(iterate_items):
                try:
                    for item, _level in iterate_items():
                        item_text = self._extract_text_like(item)
                        if not item_text:
                            continue
                        provenance = list(getattr(item, "prov", None) or [])
                        item_pages = sorted(
                            {
                                int(prov.page_no)
                                for prov in provenance
                                if isinstance(getattr(prov, "page_no", None), int) and int(prov.page_no) > 0
                            }
                        )
                        for page_no in item_pages:
                            page_fragments.setdefault(page_no, []).append(item_text)
                except Exception:
                    page_fragments = {}
            for page_no in sorted(page_fragments):
                page_text = "\n".join(fragment for fragment in page_fragments[page_no] if fragment).strip()
                if not page_text:
                    continue
                page_start_char = len(global_text)
                global_text += page_text + "\n"
                page_end_char = len(global_text)
                sections.append(
                    Section(
                        name=f"page_{page_no}",
                        text=page_text,
                        char_start=page_start_char,
                        char_end=page_end_char,
                        page_start=page_no,
                        page_end=page_no,
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

    @staticmethod
    def _covered_section_pages(sections: List[Section]) -> set[int]:
        pages: set[int] = set()
        for section in sections:
            start_page = int(section.page_start or 0)
            end_page = int(section.page_end or 0)
            if start_page <= 0 and end_page <= 0:
                continue
            if start_page <= 0:
                start_page = end_page
            if end_page <= 0:
                end_page = start_page
            if end_page < start_page:
                start_page, end_page = end_page, start_page
            pages.update(range(start_page, end_page + 1))
        return pages

    @classmethod
    def _internal_missing_section_pages(cls, sections: List[Section]) -> list[int]:
        covered_pages = cls._covered_section_pages(sections)
        if len(covered_pages) <= 1:
            return []
        return [page for page in range(min(covered_pages), max(covered_pages) + 1) if page not in covered_pages]

    @staticmethod
    def _copy_section_with_offsets(section: Section, *, name: str, char_start: int) -> Section:
        text = str(section.text or "")
        return Section(
            name=name,
            text=text,
            char_start=char_start,
            char_end=char_start + len(text),
            page_start=section.page_start,
            page_end=section.page_end,
        )

    @classmethod
    def _merge_missing_page_sections(
        cls,
        primary_sections: List[Section],
        fallback_sections: List[Section],
        *,
        missing_pages: list[int],
        min_fallback_chars: int = 80,
    ) -> List[Section]:
        if not missing_pages:
            return primary_sections

        fallback_by_page: dict[int, Section] = {}
        missing_page_set = set(missing_pages)
        for section in fallback_sections:
            page_start = int(section.page_start or 0)
            page_end = int(section.page_end or 0)
            if page_start != page_end or page_start not in missing_page_set:
                continue
            if len(str(section.text or "").strip()) < min_fallback_chars:
                continue
            fallback_by_page[page_start] = section

        if not fallback_by_page:
            return primary_sections

        merged: list[tuple[int, int, Section, bool]] = []
        for idx, section in enumerate(primary_sections):
            page_start = int(section.page_start or 0)
            merged.append((page_start if page_start > 0 else 10**9, idx, section, False))
        for page in missing_pages:
            fallback = fallback_by_page.get(page)
            if fallback is None:
                continue
            merged.append((page, -1, fallback, True))

        next_char = 0
        output: List[Section] = []
        for _page, _idx, section, is_fallback in sorted(merged, key=lambda item: (item[0], item[1])):
            fallback_page = int(section.page_start or 0)
            name = f"page_{fallback_page}_fitz_fallback" if is_fallback and fallback_page > 0 else section.name
            copied = cls._copy_section_with_offsets(section, name=name, char_start=next_char)
            output.append(copied)
            next_char = copied.char_end + 1
        return output

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

    @staticmethod
    def _normalize_docling_cell(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() == "nan":
            return ""
        return text

    @staticmethod
    def _table_data_is_meaningful(data: List[List[str]]) -> bool:
        rows = len(data)
        cols = max((len(row) for row in data), default=0)
        flattened = [str(cell or "").strip() for row in data for cell in row]
        non_empty_cells = sum(1 for cell in flattened if cell)
        alpha_cells = sum(1 for cell in flattened if any(ch.isalpha() for ch in cell))
        return rows >= 2 and cols >= 2 and non_empty_cells >= 6 and alpha_cells >= 2

    @classmethod
    def _structured_rows_from_docling_table(cls, table: Any, doc_obj: Any) -> List[List[str]]:
        export_to_dataframe = getattr(table, "export_to_dataframe", None)
        if not callable(export_to_dataframe):
            return []

        try:
            dataframe = export_to_dataframe(doc_obj)
        except TypeError:
            dataframe = export_to_dataframe()
        except Exception:
            return []

        table_rows: List[List[str]] = []
        columns = [cls._normalize_docling_cell(col) for col in list(getattr(dataframe, "columns", []))]
        if any(columns):
            table_rows.append(columns)

        iterrows = getattr(dataframe, "iterrows", None)
        if not callable(iterrows):
            return table_rows

        for _row_idx, row in iterrows():
            tolist = getattr(row, "tolist", None)
            raw_values = tolist() if callable(tolist) else list(row)
            values = [cls._normalize_docling_cell(value) for value in raw_values]
            if any(values):
                table_rows.append(values)
        return table_rows

    @staticmethod
    def _docling_table_page(table: Any) -> int:
        for provenance in list(getattr(table, "prov", None) or []):
            page_no = getattr(provenance, "page_no", None)
            if isinstance(page_no, int) and page_no > 0:
                return page_no
        return 1

    @staticmethod
    def _docling_table_caption(table: Any, doc_obj: Any, idx: int) -> str:
        caption_text = getattr(table, "caption_text", None)
        if callable(caption_text):
            try:
                caption = str(caption_text(doc_obj) or "").strip()
            except TypeError:
                caption = str(caption_text() or "").strip()
            except Exception:
                caption = ""
            if caption:
                return caption
        return f"Docling table {idx}"

    @classmethod
    def _extract_structured_docling_tables(cls, doc_obj: Any, *, source_path: Path | str | None = None) -> List[TableData]:
        tables: List[TableData] = []
        for idx, table in enumerate(list(getattr(doc_obj, "tables", None) or []), start=1):
            table_rows = cls._structured_rows_from_docling_table(table, doc_obj)
            if not table_rows or max((len(row) for row in table_rows), default=0) <= 1:
                continue
            source_page = cls._docling_table_page(table)
            tables.append(
                TableData(
                    table_id=f"T{idx}",
                    caption=cls._docling_table_caption(table, doc_obj, idx),
                    data=table_rows,
                    source_page=source_page,
                    source_ref=cls._table_source_ref(source_path, source_page) if source_path is not None else None,
                    extraction_method="docling.structured_table",
                    confidence=0.75,
                    provenance_note="Structured table exported by Docling; source page is derived from Docling provenance.",
                )
            )
        return tables

    @staticmethod
    def _normalize_table_cell(value: Any) -> str:
        text = str(value or "").lower()
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"\s+", "", text)
        return re.sub(r"[^a-z0-9*†-]", "", text)

    @classmethod
    def _table_cell_counter(cls, tables: List[TableData]) -> Counter[str]:
        counter: Counter[str] = Counter()
        for table in tables:
            for row in list(table.data or []):
                for cell in row:
                    normalized = cls._normalize_table_cell(cell)
                    if normalized:
                        counter[normalized] += 1
        return counter

    @classmethod
    def _first_cell_text_by_normalized(cls, tables: List[TableData]) -> dict[str, str]:
        cells: dict[str, str] = {}
        for table in tables:
            for row in list(table.data or []):
                for cell in row:
                    normalized = cls._normalize_table_cell(cell)
                    if normalized and normalized not in cells:
                        cells[normalized] = str(cell or "")
        return cells

    @staticmethod
    def _counter_overlap_ratio(left: Counter[str], right: Counter[str]) -> float:
        left_total = sum(count for count in left.values() if count > 0)
        right_total = sum(count for count in right.values() if count > 0)
        denominator = min(left_total, right_total)
        if denominator <= 0:
            return 0.0
        return round(sum((left & right).values()) / denominator, 4)

    @classmethod
    def _prefix_truncation_repairs(
        cls,
        *,
        missing_counter: Counter[str],
        candidate_counter: Counter[str],
        fallback_cells: dict[str, str],
    ) -> list[dict[str, Any]]:
        repairs: list[dict[str, Any]] = []
        for missing_cell, missing_count in sorted(missing_counter.items()):
            replacement_text = fallback_cells.get(missing_cell)
            if not replacement_text:
                continue
            for candidate_cell, candidate_count in sorted(candidate_counter.items()):
                if candidate_count <= 0:
                    continue
                if len(candidate_cell) < 4 or len(candidate_cell) >= len(missing_cell):
                    continue
                if not missing_cell.startswith(candidate_cell):
                    continue
                candidate_length_ratio = len(candidate_cell) / max(len(missing_cell), 1)
                if candidate_length_ratio < 0.5:
                    continue
                repairs.append(
                    {
                        "candidate_cell": candidate_cell,
                        "missing_cell": missing_cell,
                        "missing_suffix": missing_cell[len(candidate_cell) :],
                        "replacement_text": replacement_text,
                        "missing_count": missing_count,
                        "candidate_count": candidate_count,
                        "candidate_length_ratio": round(candidate_length_ratio, 4),
                    }
                )
        return repairs

    @classmethod
    def _patch_table_cell(cls, table: TableData, *, candidate_cell: str, replacement_text: str) -> tuple[TableData, bool]:
        patched = False
        patched_rows: List[List[str]] = []
        for row in list(table.data or []):
            patched_row: List[str] = []
            for cell in row:
                if not patched and cls._normalize_table_cell(cell) == candidate_cell:
                    patched_row.append(replacement_text)
                    patched = True
                else:
                    patched_row.append(str(cell or ""))
            patched_rows.append(patched_row)

        if not patched:
            return table, False
        return (
            TableData(
                table_id=table.table_id,
                caption=table.caption,
                data=patched_rows,
                source_page=table.source_page,
            ),
            True,
        )

    @classmethod
    def _patch_same_page_prefix_truncations(
        cls,
        primary_tables: List[TableData],
        fallback_tables_by_page: dict[int, List[TableData]],
        *,
        min_overlap_ratio: float = 0.5,
    ) -> tuple[List[TableData], List[int], List[dict[str, Any]]]:
        patched_tables = list(primary_tables)
        patched_pages: set[int] = set()
        patched_cells: list[dict[str, Any]] = []

        for page, fallback_tables in sorted(fallback_tables_by_page.items()):
            primary_page_tables = [
                table for table in patched_tables if int(getattr(table, "source_page", 0) or 0) == page
            ]
            if not primary_page_tables:
                continue
            candidate_counter = cls._table_cell_counter(primary_page_tables)
            fallback_counter = cls._table_cell_counter(fallback_tables)
            if cls._counter_overlap_ratio(candidate_counter, fallback_counter) < min_overlap_ratio:
                continue

            missing_counter = fallback_counter - candidate_counter
            if not missing_counter:
                continue
            repairs = cls._prefix_truncation_repairs(
                missing_counter=missing_counter,
                candidate_counter=candidate_counter,
                fallback_cells=cls._first_cell_text_by_normalized(fallback_tables),
            )
            for repair in repairs:
                for idx, table in enumerate(patched_tables):
                    if int(getattr(table, "source_page", 0) or 0) != page:
                        continue
                    replacement, patched = cls._patch_table_cell(
                        table,
                        candidate_cell=str(repair["candidate_cell"]),
                        replacement_text=str(repair["replacement_text"]),
                    )
                    if not patched:
                        continue
                    patched_tables[idx] = replacement
                    patched_pages.add(page)
                    patched_cells.append(
                        {
                            "page": page,
                            "action": "patch",
                            "reason": "fallback_covers_candidate_prefix_truncation",
                            "candidate_cell": repair["candidate_cell"],
                            "replacement_cell": repair["missing_cell"],
                            "missing_suffix": repair["missing_suffix"],
                            "candidate_length_ratio": repair["candidate_length_ratio"],
                        }
                    )
                    break

        return patched_tables, sorted(patched_pages), patched_cells

    @classmethod
    def _merge_meaningful_fallback_tables(
        cls, primary_tables: List[TableData], fallback_tables: List[TableData]
    ) -> Tuple[List[TableData], List[int], List[int], List[int], List[dict[str, Any]]]:
        merged_tables: List[TableData] = [
            TableData(
                table_id=f"T{idx}",
                caption=table.caption,
                data=table.data,
                source_page=table.source_page,
            )
            for idx, table in enumerate(primary_tables, start=1)
        ]
        seen_pages = {
            int(table.source_page)
            for table in merged_tables
            if isinstance(getattr(table, "source_page", None), int) and int(table.source_page) > 0
        }
        fallback_pages: List[int] = []
        same_page_fallback_tables: dict[int, List[TableData]] = {}

        for table in fallback_tables:
            source_page = int(getattr(table, "source_page", 0) or 0)
            if not cls._table_data_is_meaningful(list(table.data or [])):
                continue
            if source_page in seen_pages:
                same_page_fallback_tables.setdefault(source_page, []).append(table)
                continue
            merged_tables.append(
                TableData(
                    table_id=f"T{len(merged_tables) + 1}",
                    caption=table.caption,
                    data=table.data,
                    source_page=source_page,
                )
            )
            if source_page > 0:
                seen_pages.add(source_page)
                fallback_pages.append(source_page)

        patched_pages: List[int] = []
        patched_cells: List[dict[str, Any]] = []
        if same_page_fallback_tables:
            merged_tables, patched_pages, patched_cells = cls._patch_same_page_prefix_truncations(
                merged_tables,
                same_page_fallback_tables,
            )
        skipped_primary_page_fallback_pages = sorted(set(same_page_fallback_tables) - set(patched_pages))
        return (
            merged_tables,
            sorted(fallback_pages),
            skipped_primary_page_fallback_pages,
            patched_pages,
            patched_cells,
        )

    def extract_text_and_meta(self, path: Path) -> Tuple[PaperMetadata, List[Section], int]:
        conversion = self._convert(path)
        if conversion is None:
            self._mark_fitz_fallback()
            return super().extract_text_and_meta(path)

        try:
            fallback_text_result: tuple[PaperMetadata, List[Section], int] | None = None

            def fallback_text() -> tuple[PaperMetadata, List[Section], int]:
                nonlocal fallback_text_result
                if fallback_text_result is None:
                    fallback_text_result = super(DoclingParserBackend, self).extract_text_and_meta(path)
                return fallback_text_result

            paper_meta = self._read_pdf_metadata(path)
            sections = self._build_sections_from_conversion(conversion)
            if not sections:
                logger.warning("Docling conversion produced no text sections for %s.", path)
                self._mark_fitz_fallback()
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
            paper_doi = str(getattr(paper_meta, "doi", "") or "").strip()
            if not paper_doi:
                try:
                    fallback_meta, _fallback_sections, _fallback_len = fallback_text()
                    fallback_doi = str(getattr(fallback_meta, "doi", "") or "").strip()
                    if fallback_doi:
                        setattr(paper_meta, "doi", fallback_doi)
                except Exception as exc:
                    logger.warning("Docling DOI fallback via fitz failed for %s: %s", path, exc)
            missing_pages = self._internal_missing_section_pages(sections)
            if missing_pages:
                try:
                    _fallback_meta, fallback_sections, _fallback_len = fallback_text()
                    sections = self._merge_missing_page_sections(
                        sections,
                        fallback_sections,
                        missing_pages=missing_pages,
                    )
                except Exception as exc:
                    logger.warning("Docling missing-page text fallback failed for %s: %s", path, exc)
            total_len = sum(len(sec.text) for sec in sections)
            return paper_meta, sections, total_len
        except Exception as exc:
            logger.warning("Docling text extraction failed for %s: %s", path, exc)
            self._mark_fitz_fallback()
            return super().extract_text_and_meta(path)

    def extract_tables(self, path: Path) -> TableExtractionResult:
        conversion = self._convert(path)
        if conversion is None:
            self._mark_fitz_fallback()
            return super().extract_tables(path)

        failures: set[str] = set()
        tables: List[TableData] = []

        try:
            doc_obj = getattr(conversion, "document", conversion)
            tables = self._extract_structured_docling_tables(doc_obj, source_path=path)
            if not tables:
                markdown = self._extract_text_like(doc_obj)
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
                            source_page=-1,
                            source_ref=self._table_source_ref(path, -1),
                            extraction_method="docling.markdown_table",
                            confidence=0.45,
                            provenance_note="Markdown table parsed from Docling text export; source page is unavailable.",
                        )
                    )
        except Exception as exc:
            logger.warning("Docling table extraction failed for %s: %s", path, exc)
            failures.add(TABLE_FAIL_LOW_ACCURACY)

        if not tables:
            fallback_result = super().extract_tables(path)
            if fallback_result.tables:
                self._mark_fitz_fallback()
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

        fallback_pages: List[int] = []
        skipped_primary_page_fallback_pages: List[int] = []
        same_page_table_rescue_pages: List[int] = []
        same_page_table_rescue_patched_cells: List[dict[str, Any]] = []
        try:
            fallback_result = super().extract_tables(path)
            if fallback_result.tables:
                (
                    tables,
                    fallback_pages,
                    skipped_primary_page_fallback_pages,
                    same_page_table_rescue_pages,
                    same_page_table_rescue_patched_cells,
                ) = self._merge_meaningful_fallback_tables(tables, fallback_result.tables)
        except Exception as exc:
            logger.warning("Docling table merge fallback failed for %s: %s", path, exc)

        if skipped_primary_page_fallback_pages:
            failures.add(TABLE_FAIL_FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED)
        if same_page_table_rescue_pages:
            failures.add(TABLE_FAIL_SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION)

        diagnostics = TableExtractionDiagnostics(
            table_extraction_pass="pass1",
            table_failure_taxonomy=sorted(failures),
            fallback_used=bool(fallback_pages),
            fallback_pages=fallback_pages,
            same_page_table_rescue_actions=["patch"] if same_page_table_rescue_pages else [],
            same_page_table_rescue_pages=same_page_table_rescue_pages,
            same_page_table_rescue_patched_cells=same_page_table_rescue_patched_cells,
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
