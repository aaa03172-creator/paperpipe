from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.schemas.agent_artifacts import (
    DocumentArtifact,
    SourceInfo,
    PaperMetadata,
    Section,
    TableData,
)


def v2_to_legacy_document_artifact(doc_v2: DocumentArtifactV2) -> DocumentArtifact:
    sections = []
    cursor = 0
    for page in doc_v2.pages:
        lines = []
        for block in page.blocks:
            for line in block.lines:
                if line.text and line.text.strip():
                    lines.append(line.text)
        text = "\n".join(lines).strip()
        if not text:
            continue
        start = cursor
        end = start + len(text)
        cursor = end + 1
        sections.append(
            Section(
                name=f"page_{page.page_index + 1}",
                text=text,
                char_start=start,
                char_end=end,
                page_start=page.page_index + 1,
                page_end=page.page_index + 1,
            )
        )

    return DocumentArtifact(
        doc_id=doc_v2.document_id,
        source=SourceInfo(type="pdf", ref=doc_v2.meta.source_ref),
        metadata=PaperMetadata(
            title=doc_v2.meta.title,
            authors=doc_v2.meta.authors,
            year=doc_v2.meta.year,
            journal=doc_v2.meta.journal,
            doi=doc_v2.meta.doi,
        ),
        sections=sections,
        tables=[
            TableData(
                table_id=t.table_id,
                caption=t.caption,
                data=t.data,
                source_page=t.source_page,
            )
            for t in doc_v2.tables
        ],
    )


def ensure_legacy_document_artifact(doc: DocumentArtifact | DocumentArtifactV2) -> DocumentArtifact:
    if isinstance(doc, DocumentArtifact):
        return doc
    return v2_to_legacy_document_artifact(doc)
