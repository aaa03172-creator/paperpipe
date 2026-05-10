from pathlib import Path

import fitz

from src.agents.ingest_agent import IngestAgent
from src.ingest.parser_backends import (
    DoclingParserBackend,
    FitzPdfPlumberBackend,
    TABLE_FAIL_FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED,
    TABLE_FAIL_SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION,
    TableExtractionDiagnostics,
    TableExtractionResult,
)
from src.schemas.agent_artifacts import DocumentArtifact, PaperMetadata, Section, SourceInfo, TableData


def _make_pdf(path: Path, text: str | None = None) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    if text:
        page.insert_text((72, 100), text)
    doc.save(path)
    doc.close()


def _make_realistic_born_digital_paper(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((54, 54), "Synthetic Trial of Memory Biomarkers", fontsize=15)
    page.insert_text((54, 76), "A. Reviewer, B. Parser, C. Clinician", fontsize=9)
    page.insert_text((54, 94), "Journal of Synthetic Biomedical Methods, 2026", fontsize=9)
    page.insert_textbox(
        fitz.Rect(54, 126, 285, 735),
        (
            "Abstract\n"
            "Background: Academic papers often use two-column layouts, references, and compact tables.\n"
            "Objective: We test whether PaperPipe keeps section text and evidence-bearing terms.\n"
            "Methods: We generated a license-safe fixture with biomarker, cohort, and outcome language.\n"
            "Results: The intervention arm improved delayed recall by 2.4 points and reduced tau signal.\n"
            "Conclusion: Synthetic fixtures can catch parser regressions without external paper reuse.\n"
            "\n"
            "Introduction\n"
            "Biomedical readers need stable extraction from dense PDF pages. Multi-column papers can scramble "
            "heading order, lose abstracts, or merge unrelated paragraphs when coordinates are ignored.\n"
            "\n"
            "Methods\n"
            "Participants were assigned to biomarker-guided review or usual reading. Outcomes included delayed "
            "recall, amyloid status, tau status, and adverse-event review by an independent adjudicator.\n"
        ),
        fontsize=8,
        lineheight=1.15,
    )
    page.insert_textbox(
        fitz.Rect(310, 126, 541, 735),
        (
            "Results\n"
            "The biomarker-guided group retained more source-grounded claims and fewer unsupported summaries. "
            "Table 1 reports representative values from the synthetic cohort.\n"
            "\n"
            "Discussion\n"
            "The fixture intentionally includes compact paragraphs, academic section headings, and terminology "
            "that downstream extraction should preserve for traceability checks. Limitations include synthetic "
            "language and no real participant data.\n"
        ),
        fontsize=8,
        lineheight=1.15,
    )

    table_page = doc.new_page(width=595, height=842)
    table_page.insert_text((54, 54), "Table 1. Synthetic biomarker outcomes", fontsize=11)
    x0, y0 = 54, 86
    col_widths = [120, 90, 90, 110]
    row_height = 26
    rows = [
        ["Biomarker", "Baseline", "Week 12", "Interpretation"],
        ["Delayed recall", "18.1", "20.5", "Improved"],
        ["Amyloid PET", "Positive", "Positive", "Stable"],
        ["Plasma tau", "8.4", "6.9", "Reduced"],
    ]
    x_positions = [x0]
    for width in col_widths:
        x_positions.append(x_positions[-1] + width)
    for row_idx in range(len(rows) + 1):
        y = y0 + row_idx * row_height
        table_page.draw_line((x0, y), (x_positions[-1], y), width=0.8)
    for x in x_positions:
        table_page.draw_line((x, y0), (x, y0 + len(rows) * row_height), width=0.8)
    for row_idx, row in enumerate(rows):
        y = y0 + row_idx * row_height + 17
        for col_idx, value in enumerate(row):
            table_page.insert_text((x_positions[col_idx] + 4, y), value, fontsize=8)

    table_page.insert_textbox(
        fitz.Rect(54, 230, 541, 520),
        (
            "References\n"
            "1. Smith A, Jones B. Synthetic evidence fixtures for document parsing. J Test Methods. 2024.\n"
            "2. Nguyen C. Table extraction reliability in biomedical PDFs. Parser Eval Reports. 2025.\n"
            "3. Rivera D. Traceability from PDF source to structured state. Lattice Methods. 2026.\n"
        ),
        fontsize=8,
        lineheight=1.15,
    )
    doc.set_metadata(
        {
            "title": "Synthetic Trial of Memory Biomarkers",
            "author": "A. Reviewer; B. Parser; C. Clinician",
            "subject": "Journal of Synthetic Biomedical Methods",
        }
    )
    doc.save(path)
    doc.close()


def _make_large_synthetic_paper(path: Path, *, page_count: int = 24) -> None:
    doc = fitz.open()
    section_cycle = ["Abstract", "Introduction", "Methods", "Results", "Discussion", "References"]
    for page_idx in range(page_count):
        page_no = page_idx + 1
        page = doc.new_page(width=595, height=842)
        heading = section_cycle[page_idx % len(section_cycle)]
        page.insert_text((54, 48), f"Large Synthetic Paper Page {page_no}", fontsize=12)
        page.insert_text((54, 66), heading, fontsize=10)
        left_text = (
            f"{heading}\n"
            f"Page sentinel PSP-{page_no:03d} appears in the left column. "
            "This synthetic academic page repeats enough biomedical-style prose to exercise extraction "
            "without relying on copyrighted paper content. Cohort participants, biomarker measurements, "
            "delayed recall scores, tau signal, and source-grounded claims are intentionally preserved. "
            "The parser should keep this text attached to the correct page and not silently truncate it.\n"
        ) * 3
        right_text = (
            f"Continuation\n"
            f"Right-column sentinel RSP-{page_no:03d} appears after the left column. "
            "Tables, figures, citations, and appendices are not required on every page, but long papers "
            "must keep page order, block identifiers, and source references stable across many pages. "
            "The fixture is intentionally repetitive so missing pages are easy to detect.\n"
        ) * 3
        page.insert_textbox(fitz.Rect(54, 92, 285, 760), left_text, fontsize=8, lineheight=1.15)
        page.insert_textbox(fitz.Rect(310, 92, 541, 760), right_text, fontsize=8, lineheight=1.15)
        page.insert_text((270, 805), str(page_no), fontsize=8)
    doc.set_metadata(
        {
            "title": "Large Synthetic Paper for Parser Regression",
            "author": "PaperPipe Fixture Generator",
            "subject": "Large PDF parser regression",
        }
    )
    doc.save(path)
    doc.close()


def test_ingest_unknown_backend_falls_back_to_default(tmp_path: Path) -> None:
    pdf = tmp_path / "fallback.pdf"
    _make_pdf(pdf, text="fallback parser test")

    ingest = IngestAgent(parser_backend="unknown_backend")
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert ingest.backend.name() == "fitz_pdfplumber"
    assert ingest.last_table_extraction_meta["parser_backend"] == "fitz_pdfplumber"


def test_ingest_docling_placeholder_backend_runs(tmp_path: Path) -> None:
    pdf = tmp_path / "docling.pdf"
    _make_pdf(pdf, text="docling placeholder test")

    ingest = IngestAgent(parser_backend="docling")
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert ingest.backend.name() == "docling"
    assert ingest.last_table_extraction_meta["parser_backend"] == "docling"


def test_ingest_docling_unavailable_reports_effective_fitz_backend(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "docling_unavailable.pdf"
    _make_pdf(pdf, text="docling unavailable fallback test")

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: None)

    ingest = IngestAgent(parser_backend="docling")
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert ingest.last_table_extraction_meta["requested_parser_backend"] == "docling"
    assert ingest.last_table_extraction_meta["parser_backend"] == "fitz_pdfplumber"
    assert ingest.last_table_extraction_meta["parser_backend_fallback_used"] is True


def test_ingest_records_empty_pdf_failure_code(tmp_path: Path) -> None:
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is None
    assert ingest.last_table_extraction_meta["parser_failure_code"] == "PDF_EMPTY"
    assert "empty" in ingest.last_table_extraction_meta["parser_failure_reason"].lower()


def test_ingest_records_invalid_pdf_header_failure_code(tmp_path: Path) -> None:
    pdf = tmp_path / "not_pdf.pdf"
    pdf.write_bytes(b"not a pdf")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is None
    assert ingest.last_table_extraction_meta["parser_failure_code"] == "PDF_INVALID_HEADER"


def test_ingest_records_corrupted_pdf_failure_code(tmp_path: Path) -> None:
    pdf = tmp_path / "corrupted.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a valid xref table\n%%EOF\n")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is None
    assert ingest.last_table_extraction_meta["parser_failure_code"] == "PDF_CORRUPTED"


def test_ingest_records_encrypted_pdf_failure_code(tmp_path: Path) -> None:
    pdf = tmp_path / "encrypted.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "encrypted content")
    doc.save(
        pdf,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
        permissions=0,
    )
    doc.close()

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is None
    assert ingest.last_table_extraction_meta["parser_failure_code"] == "PDF_ENCRYPTED"


def test_ingest_records_textless_pdf_failure_code_without_failing_artifact(tmp_path: Path) -> None:
    pdf = tmp_path / "textless.pdf"
    _make_pdf(pdf, text=None)

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert ingest.last_table_extraction_meta["parser_failure_code"] == "PDF_TEXTLESS"
    assert "no text" in ingest.last_table_extraction_meta["parser_failure_reason"].lower()


def test_ingest_extracts_doi_from_page_text(tmp_path: Path) -> None:
    pdf = tmp_path / "doi_text.pdf"
    _make_pdf(pdf, text="Methods and results. DOI: 10.1234/AbC.2024-01.")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert artifact.metadata.doi == "10.1234/AbC.2024-01"
    assert artifact.doc_id == "doi:10.1234/AbC.2024-01"


def test_fitz_backend_splits_obvious_academic_section_headings(tmp_path: Path) -> None:
    pdf = tmp_path / "semantic_sections.pdf"
    _make_pdf(
        pdf,
        text=(
            "Semantic Section Paper\n"
            "Abstract\n"
            "This study introduces a parser contract.\n"
            "1 Introduction\n"
            "Prior work needs traceable sections.\n"
            "Materials and Methods\n"
            "We parse explicit headings conservatively.\n"
            "Results\n"
            "Semantic sections are emitted.\n"
            "Discussion\n"
            "The fallback remains page based when headings are absent.\n"
        ),
    )

    backend = FitzPdfPlumberBackend()
    _meta, sections, text_len = backend.extract_text_and_meta(pdf)

    names = [section.name for section in sections]
    assert names == ["page_1_preamble", "abstract", "introduction", "methods", "results", "discussion"]
    assert "This study introduces" in sections[1].text
    assert "We parse explicit headings" in sections[3].text
    assert all(section.page_start == 1 and section.page_end == 1 for section in sections)
    assert sections[1].char_start < sections[2].char_start < sections[3].char_start
    assert text_len > 0


def test_fitz_backend_preserves_page_section_when_no_heading_is_detected(tmp_path: Path) -> None:
    pdf = tmp_path / "page_fallback.pdf"
    _make_pdf(pdf, text="This paragraph discusses results without making Results a standalone heading.")

    backend = FitzPdfPlumberBackend()
    _meta, sections, _text_len = backend.extract_text_and_meta(pdf)

    assert [section.name for section in sections] == ["page_1"]
    assert "standalone heading" in sections[0].text


def test_realistic_born_digital_paper_preserves_sections_table_and_references(tmp_path: Path) -> None:
    pdf = tmp_path / "realistic_born_digital.pdf"
    _make_realistic_born_digital_paper(pdf)

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert artifact.metadata.title == "Synthetic Trial of Memory Biomarkers"
    text = "\n".join(section.text for section in artifact.sections)
    normalized_text = " ".join(text.replace("-\n", "-").split())
    section_names = {section.name for section in artifact.sections}
    assert {"abstract", "introduction", "methods", "results", "discussion", "references"} <= section_names
    assert "delayed recall by 2.4 points" in normalized_text
    assert "Traceability from PDF source to structured state" in normalized_text
    assert len(text) > 900

    table_cells = {
        str(cell).strip()
        for table in artifact.tables
        for row in table.data
        for cell in row
    }
    assert {"Biomarker", "Delayed recall", "Week 12", "Plasma tau"} <= table_cells
    assert any(table.source_page == 2 for table in artifact.tables)
    assert ingest.last_table_extraction_meta["parser_failure_code"] is None


def test_realistic_scanned_paper_ocr_fixture_preserves_recovered_academic_text(tmp_path: Path, monkeypatch) -> None:
    scanned_pdf = tmp_path / "scanned_source.pdf"
    ocr_pdf = tmp_path / "scanned_source.ocr.pdf"
    _make_pdf(scanned_pdf, text=None)
    _make_realistic_born_digital_paper(ocr_pdf)

    ingest = IngestAgent(enable_ocr_fallback=True, ocr_min_text_chars=20)
    monkeypatch.setattr("src.agents.ingest_agent.detect_need_ocr", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "src.agents.ingest_agent.run_ocr",
        lambda *_args, **_kwargs: {
            "ocr_applied": True,
            "ocr_engine": "ocrmypdf",
            "ocr_version": "test-version",
            "ocr_lang": "eng",
            "ocr_output_path": str(ocr_pdf),
            "error": None,
        },
    )

    artifact = ingest.process(str(scanned_pdf))

    assert artifact is not None
    text = "\n".join(section.text for section in artifact.sections)
    normalized_text = " ".join(text.replace("-\n", "-").split())
    assert "Synthetic Trial of Memory Biomarkers" in normalized_text
    assert "biomarker-guided group retained more source-grounded claims" in normalized_text
    assert artifact.metadata.ocr_applied is True
    assert artifact.metadata.ocr_output_path == str(ocr_pdf)
    assert ingest.last_table_extraction_meta["parser_failure_code"] is None


def test_realistic_malformed_paper_fixture_keeps_structured_failure_code(tmp_path: Path) -> None:
    pdf = tmp_path / "malformed_realistic_header.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a valid xref table\n%%EOF\n")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is None
    assert ingest.last_table_extraction_meta["parser_failure_code"] == "PDF_CORRUPTED"


def test_large_synthetic_paper_preserves_all_pages_and_v2_source_refs(tmp_path: Path) -> None:
    pdf = tmp_path / "large_synthetic_paper.pdf"
    _make_large_synthetic_paper(pdf, page_count=24)

    ingest = IngestAgent()
    artifact = ingest.process_v2(str(pdf))

    assert artifact is not None
    assert artifact.meta.title == "Large Synthetic Paper for Parser Regression"
    assert len(artifact.pages) == 24
    assert ingest.last_table_extraction_meta["parser_failure_code"] is None

    page_texts = []
    span_source_refs = []
    for page in artifact.pages:
        text = "\n".join(line.text for block in page.blocks for line in block.lines)
        page_texts.append(text)
        span_source_refs.extend(
            str(span.source_ref)
            for block in page.blocks
            for line in block.lines
            for span in line.spans
            if span.source_ref
        )

    assert "PSP-001" in page_texts[0]
    assert "RSP-001" in page_texts[0]
    assert "PSP-024" in page_texts[-1]
    assert "RSP-024" in page_texts[-1]
    assert all(f"PSP-{page_no:03d}" in page_texts[page_no - 1] for page_no in range(1, 25))
    assert all(any(f"#page={page_idx}" in source_ref for source_ref in span_source_refs) for page_idx in range(24))
    assert sum(len(page.blocks) for page in artifact.pages) >= 48


def test_ingest_derives_arxiv_doi_from_filename(tmp_path: Path) -> None:
    pdf = tmp_path / "1411.2441.pdf"
    _make_pdf(pdf, text="Preprint without explicit DOI")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert artifact.metadata.doi == "10.48550/arXiv.1411.2441"
    assert artifact.doc_id == "doi:10.48550/arXiv.1411.2441"


def test_ingest_derives_lancet_review_doi_from_signature(tmp_path: Path) -> None:
    pdf = tmp_path / "lancet_review.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        "Cognitive impairment in multiple sclerosis",
        "Nancy D Chiaravalloti, John DeLuca",
        "www.thelancet.com/neurology   Vol 7   December 2008",
    ]
    y = 100
    for line in lines:
        page.insert_text((72, y), line)
        y += 18
    doc.set_metadata(
        {
            "title": "Cognitive impairment in multiple sclerosis",
            "author": "Nancy D Chiaravalloti; John DeLuca",
            "subject": "The Lancet Neurology",
        }
    )
    doc.save(pdf)
    doc.close()

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert artifact.metadata.doi == "10.1016/S1474-4422(08)70259-X"
    assert artifact.doc_id == "doi:10.1016/S1474-4422(08)70259-X"


def test_docling_backend_uses_conversion_when_available(monkeypatch) -> None:
    class FakeConversionDocument:
        pages = [
            type("P", (), {"text": "Docling text page 1"})(),
            type("P", (), {"text": "Docling text page 2"})(),
        ]

        def export_to_markdown(self):
            return (
                "| ColA | ColB |\n"
                "| --- | --- |\n"
                "| 1 | 2 |\n"
                "| 3 | 4 |\n"
            )

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        DoclingParserBackend,
        "_read_pdf_metadata",
        lambda self, _path: type("Meta", (), {"title": "x", "authors": [], "year": 0, "journal": "Unknown"})(),
    )
    backend = DoclingParserBackend()
    meta, sections, text_len = backend.extract_text_and_meta(Path("/tmp/unused.pdf"))
    assert meta.title == "x"
    assert len(sections) == 2
    assert text_len > 0
    table_result = backend.extract_tables(Path("/tmp/unused.pdf"))
    assert len(table_result.tables) == 1
    assert table_result.tables[0].data[0] == ["ColA", "ColB"]


def test_docling_markdown_table_fallback_marks_page_unknown(monkeypatch) -> None:
    class FakeConversionDocument:
        tables = []

        def export_to_markdown(self):
            return (
                "| ColA | ColB |\n"
                "| --- | --- |\n"
                "| 1 | 2 |\n"
            )

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        FitzPdfPlumberBackend,
        "extract_tables",
        lambda self, _path: TableExtractionResult(
            tables=[],
            diagnostics=TableExtractionDiagnostics(table_failure_taxonomy=["NO_TABLE_FOUND"]),
        ),
    )

    backend = DoclingParserBackend()
    table_result = backend.extract_tables(Path("/tmp/unused.pdf"))

    assert len(table_result.tables) == 1
    assert table_result.tables[0].source_page == -1


def test_docling_backend_prefers_structured_tables_when_available(monkeypatch) -> None:
    class FakeRow:
        def __init__(self, values):
            self._values = list(values)

        def tolist(self):
            return list(self._values)

    class FakeDataFrame:
        columns = ["", "ColA", "ColB"]

        def iterrows(self):
            yield 0, FakeRow(["Row1", "1", "2"])
            yield 1, FakeRow(["Row2", "3", "4"])

    class FakeTable:
        prov = [type("Prov", (), {"page_no": 7})()]

        def export_to_dataframe(self, _doc):
            return FakeDataFrame()

        def caption_text(self, _doc):
            return "Structured caption"

    class FakeConversionDocument:
        pages = [type("P", (), {"text": "Docling text page 1"})()]
        tables = [FakeTable()]

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        DoclingParserBackend,
        "_read_pdf_metadata",
        lambda self, _path: type("Meta", (), {"title": "x", "authors": [], "year": 0, "journal": "Unknown"})(),
    )

    backend = DoclingParserBackend()
    table_result = backend.extract_tables(Path("/tmp/unused.pdf"))

    assert len(table_result.tables) == 1
    assert table_result.tables[0].caption == "Structured caption"
    assert table_result.tables[0].source_page == 7
    assert table_result.tables[0].source_ref == "/tmp/unused.pdf#page=6"
    assert table_result.tables[0].extraction_method == "docling.structured_table"
    assert table_result.tables[0].confidence == 0.75
    assert "Docling provenance" in str(table_result.tables[0].provenance_note)
    assert table_result.tables[0].data[0] == ["", "ColA", "ColB"]
    assert table_result.tables[0].data[1] == ["Row1", "1", "2"]


def test_build_v2_preserves_table_provenance_fields(tmp_path: Path) -> None:
    pdf = tmp_path / "table_provenance.pdf"
    _make_pdf(pdf, text="paper text")
    legacy = DocumentArtifact(
        doc_id="file:table_provenance",
        source=SourceInfo(type="pdf", ref=str(pdf)),
        metadata=PaperMetadata(title="Table Provenance", authors=[], year=2026),
        sections=[
            Section(name="page_1", text="paper text", char_start=0, char_end=10, page_start=1, page_end=1),
        ],
        tables=[
            TableData(
                table_id="T1",
                caption="Table found on page 1",
                data=[["A", "B"], ["1", "2"]],
                source_page=1,
                source_ref=f"{pdf}#page=0",
                extraction_method="pdfplumber.extract_tables",
                confidence=0.6,
                provenance_note="Table reconstructed from pdfplumber cell text; cell/page bbox provenance is unavailable.",
            )
        ],
    )

    artifact_v2 = FitzPdfPlumberBackend().build_v2_from_pdf(pdf, legacy)

    assert len(artifact_v2.tables) == 1
    table = artifact_v2.tables[0]
    assert table.source_ref == f"{pdf}#page=0"
    assert table.extraction_method == "pdfplumber.extract_tables"
    assert table.confidence == 0.6
    assert "bbox provenance is unavailable" in str(table.provenance_note)


def test_docling_backend_builds_page_sections_from_dict_pages(monkeypatch) -> None:
    class FakeItem:
        def __init__(self, text: str, page_no: int):
            self.text = text
            self.prov = [type("Prov", (), {"page_no": page_no})()]

    class FakeConversionDocument:
        pages = {1: object(), 2: object()}

        def iterate_items(self):
            yield FakeItem("Page one title", 1), 0
            yield FakeItem("Page one body", 1), 0
            yield FakeItem("Page two title", 2), 0

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        DoclingParserBackend,
        "_read_pdf_metadata",
        lambda self, _path: type("Meta", (), {"title": "x", "authors": [], "year": 0, "journal": "Unknown"})(),
    )

    backend = DoclingParserBackend()
    meta, sections, text_len = backend.extract_text_and_meta(Path("/tmp/unused.pdf"))

    assert meta.title == "x"
    assert len(sections) == 2
    assert sections[0].name == "page_1"
    assert sections[0].page_start == 1
    assert "Page one title" in sections[0].text
    assert sections[1].name == "page_2"
    assert sections[1].page_start == 2
    assert "Page two title" in sections[1].text
    assert text_len == sum(len(section.text) for section in sections)


def test_docling_backend_fills_internal_missing_pages_from_fitz_sections(monkeypatch) -> None:
    class FakeItem:
        def __init__(self, text: str, page_no: int):
            self.text = text
            self.prov = [type("Prov", (), {"page_no": page_no})()]

    class FakeConversionDocument:
        pages = {1: object(), 2: object(), 3: object()}

        def iterate_items(self):
            yield FakeItem("Docling page one", 1), 0
            yield FakeItem("Docling page three", 3), 0

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    fallback_calls = {"count": 0}

    def fake_fitz_text(self, _path):
        fallback_calls["count"] += 1
        return (
            type(
                "Meta",
                (),
                {"title": "x", "authors": [], "year": 0, "journal": "Unknown", "doi": "10.1000/example"},
            )(),
            [
                Section(name="page_1", text="Fitz page one", char_start=0, char_end=13, page_start=1, page_end=1),
                Section(
                    name="page_2",
                    text="Fitz page two fallback text " * 4,
                    char_start=14,
                    char_end=130,
                    page_start=2,
                    page_end=2,
                ),
                Section(name="page_3", text="Fitz page three", char_start=131, char_end=146, page_start=3, page_end=3),
            ],
            146,
        )

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        DoclingParserBackend,
        "_read_pdf_metadata",
        lambda self, _path: type(
            "Meta",
            (),
            {"title": "x", "authors": [], "year": 0, "journal": "Unknown", "doi": "10.1000/example"},
        )(),
    )
    monkeypatch.setattr(FitzPdfPlumberBackend, "extract_text_and_meta", fake_fitz_text)

    backend = DoclingParserBackend()
    meta, sections, text_len = backend.extract_text_and_meta(Path("/tmp/unused.pdf"))

    assert meta.doi == "10.1000/example"
    assert fallback_calls["count"] == 1
    assert [section.page_start for section in sections] == [1, 2, 3]
    assert sections[1].name == "page_2_fitz_fallback"
    assert "Fitz page two fallback text" in sections[1].text
    assert [section.char_start for section in sections] == [0, sections[0].char_end + 1, sections[1].char_end + 1]
    assert text_len == sum(len(section.text) for section in sections)


def test_docling_backend_merges_meaningful_fallback_pages(monkeypatch) -> None:
    class FakeRow:
        def __init__(self, values):
            self._values = list(values)

        def tolist(self):
            return list(self._values)

    class FakeDataFrame:
        columns = ["", "ColA", "ColB"]

        def iterrows(self):
            yield 0, FakeRow(["Row1", "1", "2"])
            yield 1, FakeRow(["Row2", "3", "4"])

    class FakeTable:
        prov = [type("Prov", (), {"page_no": 2})()]

        def export_to_dataframe(self, _doc):
            return FakeDataFrame()

        def caption_text(self, _doc):
            return "Structured caption"

    class FakeConversionDocument:
        pages = [type("P", (), {"text": "Docling text page 1"})()]
        tables = [FakeTable()]

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        DoclingParserBackend,
        "_read_pdf_metadata",
        lambda self, _path: type("Meta", (), {"title": "x", "authors": [], "year": 0, "journal": "Unknown"})(),
    )
    monkeypatch.setattr(
        FitzPdfPlumberBackend,
        "extract_tables",
        lambda self, _path: TableExtractionResult(
            tables=[
                TableData(
                    table_id="F0",
                    caption="Same page fallback table should not duplicate page 2",
                    data=[["A", "B", "C"], ["fallback", "same", "page"]],
                    source_page=2,
                ),
                TableData(
                    table_id="F1",
                    caption="Table found on page 4",
                    data=[["A", "B", "C"], ["1", "2", "3"], ["4", "5", "6"]],
                    source_page=4,
                ),
                TableData(
                    table_id="F2",
                    caption="Degenerate fragment on page 5",
                    data=[["fragment"]],
                    source_page=5,
                ),
            ],
            diagnostics=TableExtractionDiagnostics(
                table_extraction_pass="pass1",
                table_failure_taxonomy=[],
                fallback_used=False,
                fallback_pages=[],
            ),
        ),
    )

    backend = DoclingParserBackend()
    table_result = backend.extract_tables(Path("/tmp/unused.pdf"))

    assert [table.source_page for table in table_result.tables] == [2, 4]
    assert "Same page fallback" not in " ".join(table.caption for table in table_result.tables)
    assert table_result.tables[1].caption == "Table found on page 4"
    assert table_result.diagnostics.fallback_used is True
    assert table_result.diagnostics.fallback_pages == [4]
    assert TABLE_FAIL_FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED in (
        table_result.diagnostics.table_failure_taxonomy
    )


def test_docling_backend_patches_same_page_prefix_truncation_without_fallback_page(monkeypatch) -> None:
    class FakeRow:
        def __init__(self, values):
            self._values = list(values)

        def tolist(self):
            return list(self._values)

    class FakeDataFrame:
        columns = ["Status", "Likelihood"]

        def iterrows(self):
            yield 0, FakeRow(["Amyloid unknown, tau", "Further investigation"])
            yield 1, FakeRow(["Shared row", "Shared value"])
            yield 2, FakeRow(["Shared row 2", "Shared value 2"])

    class FakeTable:
        prov = [type("Prov", (), {"page_no": 8})()]

        def export_to_dataframe(self):
            return FakeDataFrame()

    class FakeConversionDocument:
        pages = {1: object()}
        tables = [FakeTable()]

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        FitzPdfPlumberBackend,
        "extract_tables",
        lambda self, _path: TableExtractionResult(
            tables=[
                TableData(
                    table_id="F1",
                    caption="Same logical table with full suffix",
                    data=[
                        ["Status", "Likelihood"],
                        ["Amyloid unknown, tau unknown", "Further investigation"],
                        ["Shared row", "Shared value"],
                        ["Shared row 2", "Shared value 2"],
                    ],
                    source_page=8,
                )
            ],
            diagnostics=TableExtractionDiagnostics(
                table_extraction_pass="pass1",
                table_failure_taxonomy=[],
                fallback_used=False,
                fallback_pages=[],
            ),
        ),
    )

    backend = DoclingParserBackend()
    table_result = backend.extract_tables(Path("/tmp/unused.pdf"))

    flattened = [cell for row in table_result.tables[0].data for cell in row]
    assert "Amyloid unknown, tau unknown" in flattened
    assert "Amyloid unknown, tau" not in flattened
    assert table_result.diagnostics.fallback_used is False
    assert table_result.diagnostics.fallback_pages == []
    assert table_result.diagnostics.same_page_table_rescue_actions == ["patch"]
    assert table_result.diagnostics.same_page_table_rescue_pages == [8]
    assert table_result.diagnostics.same_page_table_rescue_patched_cells == [
        {
            "page": 8,
            "action": "patch",
            "reason": "fallback_covers_candidate_prefix_truncation",
            "candidate_cell": "amyloidunknowntau",
            "replacement_cell": "amyloidunknowntauunknown",
            "missing_suffix": "unknown",
            "candidate_length_ratio": 0.7083,
        }
    ]
    assert TABLE_FAIL_SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION in (
        table_result.diagnostics.table_failure_taxonomy
    )
    assert TABLE_FAIL_FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED not in (
        table_result.diagnostics.table_failure_taxonomy
    )


def test_docling_backend_falls_back_to_fitz_for_doi_when_conversion_text_misses_it(monkeypatch) -> None:
    class FakeConversionDocument:
        text = "Converted content without front-matter DOI."

    class FakeConversion:
        document = FakeConversionDocument()

    class FakeConverter:
        def convert(self, _path: str):
            return FakeConversion()

    monkeypatch.setattr(DoclingParserBackend, "_initialize_converter", lambda self: FakeConverter())
    monkeypatch.setattr(
        DoclingParserBackend,
        "_read_pdf_metadata",
        lambda self, _path: type(
            "Meta",
            (),
            {"title": "x", "authors": [], "year": 0, "journal": "Unknown", "doi": None},
        )(),
    )
    monkeypatch.setattr(
        FitzPdfPlumberBackend,
        "extract_text_and_meta",
        lambda self, _path: (
            type(
                "Meta",
                (),
                {"title": "x", "authors": [], "year": 0, "journal": "Unknown", "doi": "10.1002/alz.12787"},
            )(),
            [Section(name="page_1", text="DOI: 10.1002/alz.12787", char_start=0, char_end=22, page_start=1, page_end=1)],
            22,
        ),
    )

    backend = DoclingParserBackend()
    meta, sections, text_len = backend.extract_text_and_meta(Path("/tmp/unused.pdf"))

    assert meta.doi == "10.1002/alz.12787"
    assert len(sections) == 1
    assert text_len > 0


def test_ingest_records_table_failure_taxonomy_for_no_table_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "no_tables.pdf"
    _make_pdf(pdf, text="This page does not contain any table grid.")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    meta = ingest.last_table_extraction_meta
    assert meta["table_extraction_pass"] == "pass1"
    assert "NO_TABLE_FOUND" in meta["table_failure_taxonomy"]
    assert meta["fallback_used"] is False
    assert meta["fallback_pages"] == []


def test_ingest_table_pass2_ocr_recovers_tables(tmp_path: Path, monkeypatch) -> None:
    src_pdf = tmp_path / "source.pdf"
    ocr_pdf = tmp_path / "ocr.pdf"
    _make_pdf(src_pdf, text="source")
    _make_pdf(ocr_pdf, text="ocr-recovered")

    ingest = IngestAgent(enable_table_pass2_ocr=True)

    def fake_extract_tables(path: Path) -> TableExtractionResult:
        if Path(path) == src_pdf:
            return TableExtractionResult(
                tables=[],
                diagnostics=TableExtractionDiagnostics(
                    table_extraction_pass="pass1",
                    table_failure_taxonomy=["NO_TABLE_FOUND"],
                    fallback_used=False,
                    fallback_pages=[],
                ),
            )
        return TableExtractionResult(
            tables=[
                TableData(
                    table_id="T1",
                    caption="Recovered table",
                    data=[["A", "B"], ["1", "2"]],
                    source_page=1,
                )
            ],
            diagnostics=TableExtractionDiagnostics(
                table_extraction_pass="pass2",
                table_failure_taxonomy=[],
                fallback_used=True,
                fallback_pages=[1],
            ),
        )

    monkeypatch.setattr(ingest.backend, "extract_tables", fake_extract_tables)
    monkeypatch.setattr("src.agents.ingest_agent.detect_need_ocr", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "src.agents.ingest_agent.run_ocr",
        lambda *_args, **_kwargs: {
            "ocr_applied": True,
            "ocr_engine": "ocrmypdf",
            "ocr_version": "test-version",
            "ocr_lang": "eng",
            "ocr_output_path": str(ocr_pdf),
            "error": None,
        },
    )

    artifact = ingest.process(str(src_pdf))
    assert artifact is not None
    assert len(artifact.tables) == 1
    assert ingest.last_table_extraction_meta["table_extraction_pass"] == "pass2"
    assert ingest.last_table_extraction_meta["fallback_used"] is True
    assert ingest.last_table_extraction_meta["fallback_pages"] == [1]


def test_ingest_table_pass3_budget_exceeded_recorded(tmp_path: Path) -> None:
    pdf = tmp_path / "pass3_budget.pdf"
    _make_pdf(pdf, text="no tables")

    ingest = IngestAgent(enable_cloud_table_fallback=True, cloud_table_page_budget=0)
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert "BUDGET_EXCEEDED" in ingest.last_table_extraction_meta["table_failure_taxonomy"]


def test_ingest_table_pass3_cloud_recovers_tables(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "pass3.pdf"
    _make_pdf(pdf, text="Table 1: sample | values")

    ingest = IngestAgent(enable_cloud_table_fallback=True, cloud_table_page_budget=2)

    monkeypatch.setattr(
        ingest.backend,
        "extract_tables",
        lambda _path: TableExtractionResult(
            tables=[],
            diagnostics=TableExtractionDiagnostics(
                table_extraction_pass="pass1",
                table_failure_taxonomy=["NO_TABLE_FOUND"],
                fallback_used=False,
                fallback_pages=[],
            ),
        ),
    )
    monkeypatch.setattr(
        ingest,
        "_extract_tables_pass3_cloud",
        lambda **_kwargs: TableExtractionResult(
            tables=[
                TableData(
                    table_id="CF1",
                    caption="Cloud fallback table (page 1)",
                    data=[["A", "B"], ["1", "2"]],
                    source_page=1,
                )
            ],
            diagnostics=TableExtractionDiagnostics(
                table_extraction_pass="pass3",
                table_failure_taxonomy=[],
                fallback_used=True,
                fallback_pages=[1],
            ),
        ),
    )

    artifact = ingest.process(str(pdf))
    assert artifact is not None
    assert len(artifact.tables) == 1
    assert ingest.last_table_extraction_meta["table_extraction_pass"] == "pass3"
    assert ingest.last_table_extraction_meta["fallback_used"] is True
    assert ingest.last_table_extraction_meta["fallback_pages"] == [1]
