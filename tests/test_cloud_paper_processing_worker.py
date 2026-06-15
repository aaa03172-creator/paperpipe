from __future__ import annotations

import hashlib

import fitz

from src.schemas.cloud_paper import CloudPaperUploadIntentRequest
from src.services.cloud_paper_metadata import InMemoryCloudPaperMetadataStore
from src.services.cloud_paper_processing import (
    MockCloudPaperDerivedArtifactProcessor,
    CloudPaperProcessingFailure,
    MockCloudPaperPageProcessor,
    process_cloud_paper_derived_artifacts,
    process_cloud_paper_page_artifact,
)
from src.services.cloud_paper_storage import MockCloudPaperStorageAdapter


def _request() -> CloudPaperUploadIntentRequest:
    return CloudPaperUploadIntentRequest(
        filename="paper.pdf",
        content_type="application/pdf",
        source_pdf_sha256="a" * 64,
        lab_id="lab_001",
    )


def _real_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_textbox(
        fitz.Rect(54, 72, 558, 140),
        "Real Cloud Upload Title\nAuthors: PaperPipe E2E",
        fontsize=16,
    )
    page.insert_textbox(
        fitz.Rect(54, 160, 558, 260),
        "Abstract\nThis abstract proves the cloud page processor used actual PDF text extraction.",
        fontsize=11,
    )
    page.insert_textbox(
        fitz.Rect(54, 290, 558, 430),
        "Introduction\nThe body snippet should mention hippocampal signal, methods context, and real extracted content.",
        fontsize=11,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class _SuccessfulProcessor:
    def build_page_artifact(self, *, paper_id: str, run_id: str, lab_id: str, source_pdf_sha256: str):
        return MockCloudPaperPageProcessor().build_page_artifact(
            paper_id=paper_id,
            run_id=run_id,
            lab_id=lab_id,
            source_pdf_sha256=source_pdf_sha256,
        )


class _FailingProcessor:
    def build_page_artifact(self, *, paper_id: str, run_id: str, lab_id: str, source_pdf_sha256: str):
        raise CloudPaperProcessingFailure("MOCK_PROCESSING_FAILED", "Mock worker failed.")


class _RecordingDerivedProcessor:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_derived_artifacts(
        self,
        *,
        paper_id: str,
        run_id: str,
        lab_id: str,
        source_pdf_sha256: str,
        source_pdf_bytes: bytes,
    ):
        self.calls.append(
            {
                "paper_id": paper_id,
                "run_id": run_id,
                "lab_id": lab_id,
                "source_pdf_sha256": source_pdf_sha256,
                "source_pdf_bytes": source_pdf_bytes,
            }
        )
        return MockCloudPaperDerivedArtifactProcessor().build_derived_artifacts(
            paper_id=paper_id,
            run_id=run_id,
            lab_id=lab_id,
            source_pdf_sha256=source_pdf_sha256,
            source_pdf_bytes=source_pdf_bytes,
        )


def test_processing_worker_writes_artifact_and_marks_ready() -> None:
    store = InMemoryCloudPaperMetadataStore()
    storage = MockCloudPaperStorageAdapter()
    store.create_upload_intent_record(paper_id="paper_mock_000001", upload_intent_id="upl_001", request=_request())
    store.mark_upload_received("paper_mock_000001")

    state = process_cloud_paper_page_artifact(
        paper_id="paper_mock_000001",
        state=store.get("paper_mock_000001"),
        metadata_store=store,
        storage_adapter=storage,
        processor=_SuccessfulProcessor(),
    )

    assert state.upload_status == "ready"
    assert state.processing_status == "ready"
    artifact = storage.read_page_artifact(
        paper_id="paper_mock_000001",
        lab_id="lab_001",
        run_id="run_paper_mock_000001",
    )
    assert artifact.blocks[0].text == "Mock processed page text for cloud paper API contract verification."


def test_real_page_processor_extracts_title_abstract_and_body_text() -> None:
    from src.services.cloud_paper_processing import RealCloudPaperPageProcessor

    pdf_bytes = _real_pdf_bytes()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    storage = MockCloudPaperStorageAdapter()
    storage.upload_source_pdf(
        pdf_bytes,
        paper_id="paper_real_pdf",
        lab_id="lab_001",
        content_type="application/pdf",
    )

    artifact = RealCloudPaperPageProcessor(storage).build_page_artifact(
        paper_id="paper_real_pdf",
        run_id="run_paper_real_pdf",
        lab_id="lab_001",
        source_pdf_sha256=source_pdf_sha256,
    )

    extracted_text = "\n".join(block.text for block in artifact.blocks)
    sections = {block.metadata.get("section") for block in artifact.blocks}
    assert "Real Cloud Upload Title" in extracted_text
    assert "This abstract proves the cloud page processor used actual PDF text extraction." in extracted_text
    assert "hippocampal signal" in extracted_text
    assert {"title", "abstract", "body"}.issubset(sections)
    assert artifact.provenance.processor_name == "paperpipe-real-cloud-page-worker"
    assert artifact.provenance.model_name == "fitz-text-extractor"


def test_extracted_page_blocks_skip_journal_header_for_lancet_style_title() -> None:
    from src.services.cloud_paper_processing import _build_extracted_page_blocks

    blocks = _build_extracted_page_blocks(
        [
            (
                1,
                "\n".join(
                    [
                        "422",
                        "www.thelancet.com/neurology Vol 19 May 2020",
                        "Articles",
                        "*Co-first authors",
                        "†Contributed equally",
                        "Department of Psychiatry and Neurochemistry",
                        "University of Gothenburg, Gothenburg, Sweden",
                        "Molecular Medicine",
                        "Blood phosphorylated tau 181 as a biomarker for Alzheimer's",
                        "disease: a diagnostic performance and prediction modelling",
                        "study using data from four prospective cohorts",
                        "Thomas K Karikari, Tharick A Pascoal, Nicholas J Ashton, Shorena Janelidze",
                        "Summary",
                        "Background CSF and PET biomarkers of amyloid beta and tau accurately detect Alzheimer's disease pathology.",
                        "Methods We developed and validated an ultrasensitive blood immunoassay for p-tau181.",
                        "Introduction",
                        "More than 50 million people worldwide have dementia.",
                    ]
                ),
            )
        ]
    )

    by_section = {block.metadata.get("section"): block.text for block in blocks}
    assert by_section["title"] == (
        "Blood phosphorylated tau 181 as a biomarker for Alzheimer's disease: "
        "a diagnostic performance and prediction modelling study using data from four prospective cohorts"
    )
    assert "Background CSF and PET biomarkers" in by_section["abstract"]
    assert "More than 50 million people worldwide" in by_section["body"]


def test_processing_worker_failure_marks_failed_without_ready_artifact() -> None:
    store = InMemoryCloudPaperMetadataStore()
    storage = MockCloudPaperStorageAdapter()
    store.create_upload_intent_record(paper_id="paper_mock_000002", upload_intent_id="upl_002", request=_request())
    store.mark_upload_received("paper_mock_000002")

    state = process_cloud_paper_page_artifact(
        paper_id="paper_mock_000002",
        state=store.get("paper_mock_000002"),
        metadata_store=store,
        storage_adapter=storage,
        processor=_FailingProcessor(),
    )

    assert state.upload_status == "failed"
    assert state.processing_status == "failed"
    assert state.warnings[0].code == "MOCK_PROCESSING_FAILED"


def test_derived_artifact_worker_reads_raw_pdf_inside_storage_boundary_and_is_idempotent() -> None:
    pdf_bytes = b"%PDF-1.4\nmock derived worker source"
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    request = CloudPaperUploadIntentRequest(
        filename="paper.pdf",
        content_type="application/pdf",
        source_pdf_sha256=source_pdf_sha256,
        lab_id="lab_001",
    )
    storage = MockCloudPaperStorageAdapter()
    storage.upload_source_pdf(
        pdf_bytes,
        paper_id="paper_mock_derived",
        lab_id="lab_001",
        content_type="application/pdf",
    )
    store = InMemoryCloudPaperMetadataStore()
    store.create_upload_intent_record(paper_id="paper_mock_derived", upload_intent_id="upl_derived", request=request)
    state = store.mark_upload_received("paper_mock_derived")
    processor = _RecordingDerivedProcessor()

    first = process_cloud_paper_derived_artifacts(
        paper_id="paper_mock_derived",
        state=state,
        storage_adapter=storage,
        processor=processor,
    )
    second = process_cloud_paper_derived_artifacts(
        paper_id="paper_mock_derived",
        state=state,
        storage_adapter=storage,
        processor=processor,
    )

    assert len(processor.calls) == 2
    assert processor.calls[0]["source_pdf_bytes"] == pdf_bytes
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.paper_id == "paper_mock_derived"
    assert first.run_id == "run_paper_mock_derived"
    assert first.source_pdf_sha256 == source_pdf_sha256
    assert first.gcs_derived_artifact_object_ref.endswith("/paper_mock_derived/run_paper_mock_derived/derived.json")
    assert first.ocr_blocks[0].source.source_pdf_sha256 == source_pdf_sha256
    assert first.tables[0].table_id == "table_001"
    assert first.figures[0].image_route == "/api/cloud/papers/paper_mock_derived/figures/figure_001/image"
    assert first.figure_analyses[0].figure_id == "figure_001"


def test_derived_artifact_worker_rejects_source_pdf_bytes_checksum_mismatch() -> None:
    request = CloudPaperUploadIntentRequest(
        filename="paper.pdf",
        content_type="application/pdf",
        source_pdf_sha256="a" * 64,
        lab_id="lab_001",
    )
    storage = MockCloudPaperStorageAdapter()
    storage.upload_source_pdf(
        b"%PDF-1.4\nunexpected bytes",
        paper_id="paper_mock_mismatch",
        lab_id="lab_001",
        content_type="application/pdf",
    )
    store = InMemoryCloudPaperMetadataStore()
    store.create_upload_intent_record(paper_id="paper_mock_mismatch", upload_intent_id="upl_mismatch", request=request)
    state = store.mark_upload_received("paper_mock_mismatch")
    processor = _RecordingDerivedProcessor()

    try:
        process_cloud_paper_derived_artifacts(
            paper_id="paper_mock_mismatch",
            state=state,
            storage_adapter=storage,
            processor=processor,
        )
    except CloudPaperProcessingFailure as exc:
        assert exc.code == "DERIVED_ARTIFACT_SOURCE_BYTES_MISMATCH"
    else:
        raise AssertionError("Expected source bytes checksum mismatch to fail before derived processing.")
    assert processor.calls == []
