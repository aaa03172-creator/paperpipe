from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, List, Tuple

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


def safe_parse_year(creation_date: str | None) -> int:
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


def clamp_bbox_to_page(bbox: List[float], page_width: float, page_height: float) -> List[float]:
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


def extract_text_and_meta(
    path: Path, parse_year_fn: Callable[[str | None], int]
) -> Tuple[PaperMetadata, List[Section], int]:
    """
    Uses PyMuPDF to extract metadata and text split by page-based sections.
    """
    doc = fitz.open(path)

    meta = doc.metadata
    paper_meta = PaperMetadata(
        title=meta.get("title", path.stem),
        authors=[meta.get("author", "")] if meta.get("author") else [],
        year=parse_year_fn(meta.get("creationDate")),
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
                name=f"page_{page_num+1}",
                text=text,
                char_start=page_start_char,
                char_end=page_end_char,
                page_start=page_num + 1,
                page_end=page_num + 1,
            )
        )

    doc.close()
    return paper_meta, sections, len(global_text)


def extract_tables(path: Path) -> List[TableData]:
    """
    Uses pdfplumber to extract tables.
    """
    tables: List[TableData] = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                extracted = page.extract_tables()
                for table in extracted:
                    clean_data = [
                        [cell.strip() if cell else "" for cell in row]
                        for row in table
                        if any(row)
                    ]

                    if clean_data:
                        tables.append(
                            TableData(
                                table_id=f"T{len(tables)+1}",
                                caption=f"Table found on page {i+1}",
                                data=clean_data,
                                source_page=i + 1,
                            )
                        )
    except Exception as exc:
        logger.warning(f"Table extraction failed for {path}: {exc}")

    return tables


def build_v2_from_pdf(
    path: Path,
    legacy: DocumentArtifact,
    clamp_bbox_fn: Callable[[List[float], float, float], List[float]],
) -> DocumentArtifactV2:
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

            raw_blocks = page.get_text("blocks")
            sorted_blocks = sorted(
                raw_blocks,
                key=lambda b: (
                    round(float(b[1]), 3),
                    round(float(b[0]), 3),
                    round(float(b[3]), 3),
                    round(float(b[2]), 3),
                ),
            )

            blocks: List[BlockV2] = []
            for block_order, block in enumerate(sorted_blocks):
                x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4] or ""
                bbox = clamp_bbox_fn(
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
