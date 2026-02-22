from dataclasses import dataclass
from typing import Iterable

from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.schemas.agent_artifacts import DocumentArtifact


@dataclass(frozen=True)
class TextSectionView:
    name: str
    text: str
    page: int | None = None


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
        for idx, section in enumerate(doc.sections, start=1):
            page = section.page_start if section.page_start is not None else idx
            yield TextSectionView(name=section.name, text=section.text, page=page)
        return

    for page in doc.pages:
        lines: list[str] = []
        for block in page.blocks:
            for line in block.lines:
                if line.text and line.text.strip():
                    lines.append(line.text)
        text = "\n".join(lines).strip()
        if not text:
            continue
        yield TextSectionView(name=f"page_{page.page_index + 1}", text=text, page=page.page_index + 1)
