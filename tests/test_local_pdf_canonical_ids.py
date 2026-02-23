from pathlib import Path

from src.core.ids import make_paper_id
from src.processor_legacy import process_local_pdf_legacy
from src.utils import create_paper_from_pdf


def test_create_paper_from_pdf_uses_canonical_pdf_id(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake\n")

    paper_a = create_paper_from_pdf(pdf_path)
    paper_b = create_paper_from_pdf(pdf_path)

    assert paper_a.id.startswith("pdfsha256:")
    assert paper_a.id == paper_b.id
    assert paper_a.id == make_paper_id(pdf_path=pdf_path)
    assert paper_a.local_pdf_path == pdf_path


def test_process_local_pdf_legacy_uses_canonical_pdf_id(tmp_path):
    pdf_path = tmp_path / "legacy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nlegacy\n")

    paper = process_local_pdf_legacy(pdf_path, config=object())

    assert paper.id.startswith("pdfsha256:")
    assert paper.id == make_paper_id(pdf_path=pdf_path)
    assert paper.source == "local_pdf"
    assert paper.local_pdf_path == Path(pdf_path)
