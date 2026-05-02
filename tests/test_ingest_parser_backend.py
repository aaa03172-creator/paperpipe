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
from src.schemas.agent_artifacts import Section, TableData


def _make_pdf(path: Path, text: str | None = None) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    if text:
        page.insert_text((72, 100), text)
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


def test_ingest_extracts_doi_from_page_text(tmp_path: Path) -> None:
    pdf = tmp_path / "doi_text.pdf"
    _make_pdf(pdf, text="Methods and results. DOI: 10.1234/AbC.2024-01.")

    ingest = IngestAgent()
    artifact = ingest.process(str(pdf))

    assert artifact is not None
    assert artifact.metadata.doi == "10.1234/AbC.2024-01"
    assert artifact.doc_id == "doi:10.1234/AbC.2024-01"


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
    assert table_result.tables[0].data[0] == ["", "ColA", "ColB"]
    assert table_result.tables[0].data[1] == ["Row1", "1", "2"]


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
