from dataclasses import dataclass
import re
from typing import Iterable

from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.schemas.agent_artifacts import DocumentArtifact

_PAGE_RE = re.compile(r"^page_(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class TextSectionView:
    name: str
    text: str
    page_hint: int | None = None  # 1-indexed if available
    ordinal: int = 0


@dataclass(frozen=True)
class ArtifactHeaderView:
    doc_id: str
    title: str
    authors: list[str]
    source_ref: str


def get_artifact_header(doc: DocumentArtifact | DocumentArtifactV2) -> ArtifactHeaderView:
    if isinstance(doc, DocumentArtifact):
        return ArtifactHeaderView(
            doc_id=doc.doc_id,
            title=doc.metadata.title,
            authors=doc.metadata.authors,
            source_ref=doc.source.ref,
        )
    return ArtifactHeaderView(
        doc_id=doc.document_id,
        title=doc.meta.title,
        authors=doc.meta.authors,
        source_ref=doc.meta.source_ref,
    )


def iter_text_sections(doc: DocumentArtifact | DocumentArtifactV2) -> Iterable[TextSectionView]:
    if isinstance(doc, DocumentArtifact):
        for ordinal, section in enumerate(doc.sections, start=1):
            page_hint = section.page_start if isinstance(section.page_start, int) and section.page_start > 0 else None
            if page_hint is None:
                match = _PAGE_RE.match((section.name or "").strip())
                if match:
                    page_hint = int(match.group(1))
            yield TextSectionView(name=section.name, text=section.text, page_hint=page_hint, ordinal=ordinal)
        return

    for ordinal, page in enumerate(doc.pages, start=1):
        lines: list[str] = []
        for block in page.blocks:
            for line in block.lines:
                if line.text and line.text.strip():
                    lines.append(line.text)
        text = "\n".join(lines).strip()
        if not text:
            continue
        yield TextSectionView(
            name=f"page_{page.page_index + 1}",
            text=text,
            page_hint=page.page_index + 1,
            ordinal=ordinal,
        )
