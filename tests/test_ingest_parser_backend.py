from pathlib import Path

import fitz

from src.agents.ingest_agent import IngestAgent
from src.ingest.parser_backends import DoclingParserBackend, TableExtractionDiagnostics, TableExtractionResult
from src.schemas.agent_artifacts import TableData


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
