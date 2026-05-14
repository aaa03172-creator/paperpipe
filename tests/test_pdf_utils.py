from pathlib import Path

import src.pdf as pdf_mod


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, _path):
        self.pages = [
            _FakePage("page1"),
            _FakePage("page2"),
            _FakePage("page3"),
        ]


def test_extract_text_returns_empty_on_missing_file(tmp_path):
    missing = tmp_path / "missing.pdf"
    text = pdf_mod.extract_text_from_pdf(missing, max_pages=3)
    assert text == ""


def test_extract_text_reads_up_to_max_pages(monkeypatch, tmp_path):
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(pdf_mod.pypdf, "PdfReader", _FakeReader)
    text = pdf_mod.extract_text_from_pdf(pdf_file, max_pages=2)
    assert "page1" in text
    assert "page2" in text
    assert "page3" not in text
