from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Protocol

import fitz

from src.schemas.cloud_paper import (
    CloudPaperDerivedArtifactFigure,
    CloudPaperDerivedArtifactFigureAnalysis,
    CloudPaperDerivedArtifactInternal,
    CloudPaperDerivedArtifactOcrBlock,
    CloudPaperDerivedArtifactSourceLocator,
    CloudPaperDerivedArtifactTable,
    CloudPaperMetadataRecord,
    CloudPaperPageArtifactInternal,
    CloudPaperPageBlockInternal,
    CloudPaperProvenance,
    CloudPaperWarning,
)
from src.services.cloud_paper_metadata import CloudPaperMetadataStore
from src.services.cloud_paper_storage import CloudPaperStorageAdapter


class CloudPaperProcessingFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CloudPaperPageProcessor(Protocol):
    def build_page_artifact(
        self,
        *,
        paper_id: str,
        run_id: str,
        lab_id: str,
        source_pdf_sha256: str,
    ) -> CloudPaperPageArtifactInternal:
        ...


class CloudPaperDerivedArtifactProcessor(Protocol):
    def build_derived_artifacts(
        self,
        *,
        paper_id: str,
        run_id: str,
        lab_id: str,
        source_pdf_sha256: str,
        source_pdf_bytes: bytes,
    ) -> CloudPaperDerivedArtifactInternal:
        ...


class MockCloudPaperPageProcessor:
    def build_page_artifact(
        self,
        *,
        paper_id: str,
        run_id: str,
        lab_id: str,
        source_pdf_sha256: str,
    ) -> CloudPaperPageArtifactInternal:
        return CloudPaperPageArtifactInternal(
            paper_id=paper_id,
            run_id=run_id,
            page_schema_version="cloud_page_artifact.v1",
            source_pdf_sha256=source_pdf_sha256,
            gcs_page_artifact_object_ref=f"gs://paperpipe-mock-pages/{lab_id}/{paper_id}/{run_id}/page.json",
            blocks=[
                CloudPaperPageBlockInternal(
                    block_id="block_001",
                    page=1,
                    kind="text",
                    text="Mock processed page text for cloud paper API contract verification.",
                    bbox_pct={"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.2},
                    payload_class="local_only",
                    metadata={"section": "abstract"},
                    worker_metadata={
                        "gcs_page_artifact_object_ref": f"gs://paperpipe-mock-pages/{lab_id}/{paper_id}/{run_id}/page.json",
                        "service_account": "mock-worker@example.iam.gserviceaccount.com",
                        "local_path": f"/Users/mock/{paper_id}/page.json",
                    },
                )
            ],
            warnings=[],
            provenance=CloudPaperProvenance(
                uploaded_by="mock_user",
                processor_name="paperpipe-mock-cloud-page-worker",
                processor_version="0.1.0",
                model_name="mock-page-processor",
                model_version="2026-05-30",
                created_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
                source_pdf_sha256=source_pdf_sha256,
            ),
            worker_metadata={
                "gcs_page_artifact_object_ref": f"gs://paperpipe-mock-pages/{lab_id}/{paper_id}/{run_id}/page.json",
                "service_account": "mock-worker@example.iam.gserviceaccount.com",
                "local_path": f"/Users/mock/{paper_id}/page.json",
            },
        )


class RealCloudPaperPageProcessor:
    def __init__(self, storage_adapter: CloudPaperStorageAdapter, *, max_pages: int = 3):
        self.storage_adapter = storage_adapter
        self.max_pages = max(1, max_pages)

    def build_page_artifact(
        self,
        *,
        paper_id: str,
        run_id: str,
        lab_id: str,
        source_pdf_sha256: str,
    ) -> CloudPaperPageArtifactInternal:
        source_pdf_bytes = self.storage_adapter.read_source_pdf(paper_id=paper_id, lab_id=lab_id)
        actual_sha256 = hashlib.sha256(source_pdf_bytes).hexdigest()
        if actual_sha256 != source_pdf_sha256:
            raise CloudPaperProcessingFailure(
                "PAGE_SOURCE_BYTES_MISMATCH",
                "Page artifact source PDF bytes do not match the upload metadata checksum.",
            )

        pages = _extract_pdf_pages(source_pdf_bytes, max_pages=self.max_pages)
        blocks = _build_extracted_page_blocks(pages)
        if not blocks:
            raise CloudPaperProcessingFailure(
                "PDF_TEXT_EXTRACTION_EMPTY",
                "Uploaded PDF opened but produced no extractable page text.",
            )

        created_at = datetime.now(timezone.utc)
        object_ref = f"gs://paperpipe-page-artifacts/{lab_id}/{paper_id}/{run_id}/page.json"
        return CloudPaperPageArtifactInternal(
            paper_id=paper_id,
            run_id=run_id,
            page_schema_version="cloud_page_artifact.v1",
            source_pdf_sha256=source_pdf_sha256,
            gcs_page_artifact_object_ref=object_ref,
            blocks=blocks,
            warnings=[],
            provenance=CloudPaperProvenance(
                uploaded_by="backend_upload",
                processor_name="paperpipe-real-cloud-page-worker",
                processor_version="0.1.0",
                model_name="fitz-text-extractor",
                model_version=f"pymupdf-{fitz.VersionBind}",
                created_at=created_at,
                source_pdf_sha256=source_pdf_sha256,
            ),
            worker_metadata={
                "source_boundary": "server_worker_only",
                "pages_read": len(pages),
                "raw_pdf_bytes_read": len(source_pdf_bytes),
            },
        )


def _extract_pdf_pages(source_pdf_bytes: bytes, *, max_pages: int) -> list[tuple[int, str]]:
    try:
        with fitz.open(stream=source_pdf_bytes, filetype="pdf") as doc:
            pages: list[tuple[int, str]] = []
            for page_index in range(min(len(doc), max_pages)):
                text = _normalize_extracted_text(doc[page_index].get_text("text"))
                if text:
                    pages.append((page_index + 1, text))
            return pages
    except Exception as exc:
        raise CloudPaperProcessingFailure(
            "PDF_TEXT_EXTRACTION_FAILED",
            f"Uploaded PDF text extraction failed: {type(exc).__name__}",
        ) from exc


def _normalize_extracted_text(value: str | None) -> str:
    if not value:
        return ""
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _clip_text(value: str, *, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    return clipped or cleaned[:max_chars].strip()


def _first_nonempty_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def _title_candidate_lines(text: str, *, max_lines: int = 100) -> list[str]:
    return [line.strip() for line in text.splitlines()[:max_lines] if line.strip()]


def _is_likely_title_line(line: str) -> bool:
    cleaned = line.strip()
    lowered = cleaned.lower()
    if len(cleaned) < 18:
        return False
    if re.fullmatch(r"[\d\s–—-]+", cleaned):
        return False
    blocked_terms = (
        "www.",
        "lancet",
        "articles",
        "comment page",
        "authors:",
        "co-first author",
        "contributed equally",
        "department",
        "institute",
        "university",
        "hospital",
        "laboratory",
        "centre",
        "center",
        "foundation",
        "correspondence",
        "published",
        "academy",
    )
    if any(term in lowered for term in blocked_terms):
        return False
    if cleaned.count(",") >= 3:
        return False
    return True


def _is_title_continuation_line(line: str) -> bool:
    cleaned = line.strip()
    if not _is_likely_title_line(cleaned):
        return False
    if re.match(r"^(authors?|summary|abstract|background|methods|results|interpretation)\b", cleaned, re.I):
        return False
    return True


def _title_candidate_score(title: str) -> int:
    lowered = title.lower()
    score = 0
    if ":" in title:
        score += 2
    title_terms = (
        "alzheimer",
        "amyloid",
        "biomarker",
        "diagnostic",
        "disease",
        "prediction",
        "prospective",
        "study",
        "tau",
    )
    score += sum(3 for term in title_terms if term in lowered)
    if title.rstrip().endswith(","):
        score -= 4
    return score


def _extract_title_candidate(text: str, *, max_chars: int = 240) -> str:
    lines = _title_candidate_lines(text)
    best_title = ""
    best_score = -1
    for index, line in enumerate(lines):
        if not _is_likely_title_line(line):
            continue
        title_parts = [line]
        for continuation in lines[index + 1 : index + 4]:
            combined = " ".join(title_parts + [continuation])
            if len(combined) > max_chars or not _is_title_continuation_line(continuation):
                break
            title_parts.append(continuation)
        title = _clip_text(" ".join(title_parts), max_chars=max_chars)
        score = _title_candidate_score(title)
        if score > best_score or (score == best_score and best_title and len(title) < len(best_title)):
            best_title = title
            best_score = score
    if best_title:
        return best_title
    return _clip_text(_first_nonempty_line(text), max_chars=max_chars)


def _extract_section_after_heading(text: str, heading: str, *, stop_headings: tuple[str, ...], max_chars: int) -> str:
    heading_pattern = re.compile(rf"(?im)^\s*{re.escape(heading)}\s*$")
    match = heading_pattern.search(text)
    if not match:
        return ""
    remainder = text[match.end() :].strip()
    stop_pattern = re.compile(r"(?im)^\s*(?:" + "|".join(re.escape(item) for item in stop_headings) + r")\s*$")
    stop_match = stop_pattern.search(remainder)
    if stop_match:
        remainder = remainder[: stop_match.start()]
    return _clip_text(remainder, max_chars=max_chars)


def _build_extracted_page_blocks(pages: list[tuple[int, str]]) -> list[CloudPaperPageBlockInternal]:
    first_page_number = pages[0][0] if pages else 1
    full_text = "\n".join(text for _page, text in pages)
    title = _extract_title_candidate(full_text, max_chars=240)
    abstract = _extract_section_after_heading(
        full_text,
        "Abstract",
        stop_headings=("Introduction", "Background", "Methods", "Materials and Methods", "Results"),
        max_chars=900,
    )
    if not abstract:
        abstract = _extract_section_after_heading(
            full_text,
            "Summary",
            stop_headings=("Introduction", "Discussion", "References"),
            max_chars=900,
        )
    body = _extract_section_after_heading(
        full_text,
        "Introduction",
        stop_headings=("Methods", "Materials and Methods", "Results", "Discussion", "References"),
        max_chars=1200,
    )

    if not body:
        body_source = full_text
        if abstract:
            body_source = body_source.replace(abstract, "", 1)
        if title:
            body_source = body_source.replace(title, "", 1)
        body = _clip_text(body_source, max_chars=1200)

    candidates = [
        ("block_title", "title", title),
        ("block_abstract", "abstract", abstract),
        ("block_body", "body", body),
    ]
    blocks: list[CloudPaperPageBlockInternal] = []
    for block_id, section, text in candidates:
        if not text:
            continue
        blocks.append(
            CloudPaperPageBlockInternal(
                block_id=block_id,
                page=first_page_number,
                kind="text",
                text=text,
                bbox_pct=None,
                payload_class="local_only",
                metadata={"section": section, "extraction_method": "fitz.get_text"},
                worker_metadata={"section": section},
            )
        )
    return blocks


class MockCloudPaperDerivedArtifactProcessor:
    def build_derived_artifacts(
        self,
        *,
        paper_id: str,
        run_id: str,
        lab_id: str,
        source_pdf_sha256: str,
        source_pdf_bytes: bytes,
    ) -> CloudPaperDerivedArtifactInternal:
        source_page_1 = CloudPaperDerivedArtifactSourceLocator(
            page=1,
            source_pdf_sha256=source_pdf_sha256,
            block_id="block_001",
            bbox_pct={"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.2},
        )
        source_page_2 = CloudPaperDerivedArtifactSourceLocator(page=2, source_pdf_sha256=source_pdf_sha256)
        source_page_3 = CloudPaperDerivedArtifactSourceLocator(page=3, source_pdf_sha256=source_pdf_sha256)
        return CloudPaperDerivedArtifactInternal(
            paper_id=paper_id,
            run_id=run_id,
            source_pdf_sha256=source_pdf_sha256,
            gcs_derived_artifact_object_ref=f"gs://paperpipe-mock-derived/{lab_id}/{paper_id}/{run_id}/derived.json",
            payload_class="local_only",
            ocr_blocks=[
                CloudPaperDerivedArtifactOcrBlock(
                    ocr_block_id="ocr_001",
                    text="Mock OCR text recovered from a rendered cloud PDF page.",
                    confidence=0.91,
                    source=source_page_1,
                    payload_class="local_only",
                    metadata={"engine": "mock-ocr", "source_pdf_size_bytes": len(source_pdf_bytes)},
                )
            ],
            tables=[
                CloudPaperDerivedArtifactTable(
                    table_id="table_001",
                    page=2,
                    caption="Mock reconstructed table from cloud PDF layout.",
                    columns=["Group", "N"],
                    rows=[["Control", "10"], ["Treatment", "12"]],
                    confidence=0.82,
                    source=source_page_2,
                    payload_class="local_only",
                )
            ],
            figures=[
                CloudPaperDerivedArtifactFigure(
                    figure_id="figure_001",
                    page=3,
                    caption="Mock figure crop from rendered cloud PDF page.",
                    bbox_pct={"left": 0.1, "top": 0.1, "width": 0.7, "height": 0.5},
                    image_available=True,
                    image_route=f"/api/cloud/papers/{paper_id}/figures/figure_001/image",
                    confidence=0.77,
                    source=source_page_3,
                    payload_class="local_only",
                )
            ],
            figure_analyses=[
                CloudPaperDerivedArtifactFigureAnalysis(
                    analysis_id="figure_analysis_001",
                    figure_id="figure_001",
                    page=3,
                    summary="Mock figure analysis placeholder derived from a server-side figure crop.",
                    confidence=0.7,
                    source=source_page_3,
                    payload_class="local_only",
                )
            ],
            warnings=[],
            provenance=CloudPaperProvenance(
                uploaded_by="mock_user",
                processor_name="paperpipe-mock-derived-artifact-worker",
                processor_version="0.1.0",
                model_name="mock-derived-artifact-processor",
                model_version="2026-06-02",
                created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=timezone.utc),
                source_pdf_sha256=source_pdf_sha256,
            ),
            worker_metadata={
                "raw_pdf_bytes_read": len(source_pdf_bytes),
                "source_boundary": "server_worker_only",
            },
        )


def process_cloud_paper_page_artifact(
    *,
    paper_id: str,
    state: CloudPaperMetadataRecord | None,
    metadata_store: CloudPaperMetadataStore,
    storage_adapter: CloudPaperStorageAdapter,
    processor: CloudPaperPageProcessor | None = None,
) -> CloudPaperMetadataRecord:
    if state is None:
        raise LookupError(paper_id)
    metadata_store.mark_processing_running(paper_id)
    worker = processor or RealCloudPaperPageProcessor(storage_adapter)
    try:
        artifact = worker.build_page_artifact(
            paper_id=paper_id,
            run_id=f"run_{paper_id}",
            lab_id=state.request.lab_id,
            source_pdf_sha256=state.request.source_pdf_sha256,
        )
        storage_adapter.write_page_artifact(artifact, lab_id=state.request.lab_id)
    except CloudPaperProcessingFailure as exc:
        return metadata_store.mark_processing_failed(
            paper_id,
            warning=CloudPaperWarning(code=exc.code, message=exc.message, severity="high"),
        )
    except Exception as exc:
        return metadata_store.mark_processing_failed(
            paper_id,
            warning=CloudPaperWarning(
                code="PROCESSING_FAILED",
                message=f"Cloud page processing failed: {type(exc).__name__}",
                severity="high",
            ),
        )
    return metadata_store.mark_upload_ready(paper_id)


def process_cloud_paper_derived_artifacts(
    *,
    paper_id: str,
    state: CloudPaperMetadataRecord | None,
    storage_adapter: CloudPaperStorageAdapter,
    processor: CloudPaperDerivedArtifactProcessor | None = None,
) -> CloudPaperDerivedArtifactInternal:
    if state is None:
        raise LookupError(paper_id)
    run_id = f"run_{paper_id}"
    source_pdf_bytes = storage_adapter.read_source_pdf(
        paper_id=paper_id,
        lab_id=state.request.lab_id,
    )
    actual_source_pdf_sha256 = hashlib.sha256(source_pdf_bytes).hexdigest()
    if actual_source_pdf_sha256 != state.request.source_pdf_sha256:
        raise CloudPaperProcessingFailure(
            "DERIVED_ARTIFACT_SOURCE_BYTES_MISMATCH",
            "Derived artifact source PDF bytes do not match the upload metadata checksum.",
        )
    worker = processor or MockCloudPaperDerivedArtifactProcessor()
    artifact = worker.build_derived_artifacts(
        paper_id=paper_id,
        run_id=run_id,
        lab_id=state.request.lab_id,
        source_pdf_sha256=state.request.source_pdf_sha256,
        source_pdf_bytes=source_pdf_bytes,
    )
    if artifact.paper_id != paper_id:
        raise CloudPaperProcessingFailure("DERIVED_ARTIFACT_PAPER_MISMATCH", "Derived artifact paper id mismatch.")
    if artifact.run_id != run_id:
        raise CloudPaperProcessingFailure("DERIVED_ARTIFACT_RUN_MISMATCH", "Derived artifact run id mismatch.")
    if artifact.source_pdf_sha256 != state.request.source_pdf_sha256:
        raise CloudPaperProcessingFailure(
            "DERIVED_ARTIFACT_SOURCE_MISMATCH",
            "Derived artifact source checksum mismatch.",
        )
    return artifact
