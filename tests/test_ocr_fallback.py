from pathlib import Path
import shutil
from unittest.mock import patch

import fitz
from PIL import Image, ImageDraw, ImageFont
import pytest

from src.agents.ingest_agent import IngestAgent
from src.ingest.ocr_fallback import run_ocr


def _make_pdf(path: Path, text: str | None = None) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    if text:
        page.insert_text((72, 100), text)
    doc.save(path)
    doc.close()


def _make_image_only_scanned_pdf(path: Path, image_path: Path) -> None:
    image = Image.new("RGB", (1800, 1200), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 72)
    except Exception:
        font = ImageFont.load_default()
    lines = [
        "SCANNED OCR FIXTURE",
        "ALPHA MEMORY TEST",
        "PAPERPIPE PARSER",
    ]
    y = 180
    for line in lines:
        draw.text((160, y), line, fill="black", font=font)
        y += 130
    image.save(image_path)

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(36, 72, 576, 432), filename=str(image_path))
    doc.save(path)
    doc.close()


def _artifact_text_len(artifact) -> int:
    return sum(len(s.text or "") for s in artifact.sections)


def test_ocr_fallback_scanned_fixture_increases_text_len(tmp_path):
    src_pdf = tmp_path / "scanned.pdf"
    ocr_pdf = tmp_path / "ocr_out.pdf"

    _make_pdf(src_pdf, text=None)
    _make_pdf(ocr_pdf, text="Recovered text via OCR fallback")

    ingest = IngestAgent(enable_ocr_fallback=True, ocr_min_text_chars=1)

    with patch("src.agents.ingest_agent.detect_need_ocr", return_value=False):
        base_artifact = ingest.process(str(src_pdf), enable_ocr_fallback=False)
    base_len = _artifact_text_len(base_artifact)

    with patch("src.agents.ingest_agent.detect_need_ocr", return_value=True), patch(
        "src.agents.ingest_agent.run_ocr",
        return_value={
            "ocr_applied": True,
            "ocr_engine": "ocrmypdf",
            "ocr_version": "test-version",
            "ocr_lang": "eng",
            "ocr_output_path": str(ocr_pdf),
            "error": None,
        },
    ):
        ocr_artifact = ingest.process(str(src_pdf), enable_ocr_fallback=True, ocr_min_text_chars=1)

    ocr_len = _artifact_text_len(ocr_artifact)
    assert ocr_len > base_len
    assert ocr_artifact.metadata.ocr_applied is True
    assert ocr_artifact.metadata.ocr_engine == "ocrmypdf"
    assert ocr_artifact.metadata.ocr_output_path == str(ocr_pdf)


def test_ocr_fallback_process_v2_uses_ocr_pdf_for_page_blocks(tmp_path):
    src_pdf = tmp_path / "scanned.pdf"
    ocr_pdf = tmp_path / "ocr_out.pdf"

    _make_pdf(src_pdf, text=None)
    _make_pdf(ocr_pdf, text="Recovered text via OCR fallback")

    ingest = IngestAgent(enable_ocr_fallback=True, ocr_min_text_chars=1)

    with patch("src.agents.ingest_agent.detect_need_ocr", return_value=True), patch(
        "src.agents.ingest_agent.run_ocr",
        return_value={
            "ocr_applied": True,
            "ocr_engine": "ocrmypdf",
            "ocr_version": "test-version",
            "ocr_lang": "eng",
            "ocr_output_path": str(ocr_pdf),
            "error": None,
        },
    ):
        artifact = ingest.process_v2(str(src_pdf))

    assert artifact is not None
    page_text = "\n".join(
        line.text
        for page in artifact.pages
        for block in page.blocks
        for line in block.lines
    )
    assert "Recovered text via OCR fallback" in page_text
    assert artifact.meta.source_ref == str(src_pdf.absolute())


def test_ocr_fallback_fail_safe_keeps_original_on_error(tmp_path):
    src_pdf = tmp_path / "source.pdf"
    _make_pdf(src_pdf, text="Original text exists")

    ingest = IngestAgent()
    with patch("src.agents.ingest_agent.detect_need_ocr", return_value=True), patch(
        "src.agents.ingest_agent.run_ocr",
        return_value={
            "ocr_applied": False,
            "ocr_engine": "ocrmypdf",
            "ocr_version": "test-version",
            "ocr_lang": "eng",
            "ocr_output_path": None,
            "error": "simulated_failure",
        },
    ):
        artifact = ingest.process(str(src_pdf), enable_ocr_fallback=True)

    assert artifact is not None
    assert _artifact_text_len(artifact) > 0
    assert artifact.metadata.ocr_applied is False
    assert artifact.metadata.ocr_error == "simulated_failure"
    assert artifact.source.ref == str(src_pdf.absolute())


def test_run_ocr_uses_skip_text_without_force_ocr(tmp_path):
    src_pdf = tmp_path / "source.pdf"
    out_pdf = tmp_path / "ocr_out.pdf"
    _make_pdf(src_pdf, text=None)

    with patch("src.ingest.ocr_fallback.shutil.which", return_value="/opt/homebrew/bin/ocrmypdf"), patch(
        "src.ingest.ocr_fallback.subprocess.check_output", return_value="17.4.0"
    ), patch("src.ingest.ocr_fallback.subprocess.run") as run_mock:
        result = run_ocr(src_pdf, out_pdf)

    cmd = run_mock.call_args[0][0]
    assert "--skip-text" in cmd
    assert "--force-ocr" not in cmd
    assert result["ocr_applied"] is True


def test_real_image_only_scanned_pdf_ocr_round_trip(tmp_path, monkeypatch):
    if shutil.which("ocrmypdf") is None or shutil.which("tesseract") is None:
        pytest.skip("ocrmypdf and tesseract are required for the real OCR fixture")

    src_pdf = tmp_path / "real_scanned_source.pdf"
    image_path = tmp_path / "real_scanned_source.png"
    cache_dir = tmp_path / "ocr-cache"
    monkeypatch.setenv("PAPERPIPE_OCR_CACHE_DIR", str(cache_dir))
    _make_image_only_scanned_pdf(src_pdf, image_path)

    base_artifact = IngestAgent(enable_ocr_fallback=False).process(str(src_pdf))
    assert base_artifact is not None
    assert _artifact_text_len(base_artifact) == 0
    assert base_artifact.metadata.ocr_applied is False

    ocr_artifact = IngestAgent(enable_ocr_fallback=True, ocr_min_text_chars=20).process_v2(str(src_pdf))

    assert ocr_artifact is not None
    text = "\n".join(
        line.text
        for page in ocr_artifact.pages
        for block in page.blocks
        for line in block.lines
    )
    assert "SCANNED OCR FIXTURE" in text
    assert "ALPHA MEMORY TEST" in text
    assert "PAPERPIPE PARSER" in text
    assert ocr_artifact.meta.source_ref == str(src_pdf.absolute())

    cache_outputs = list(cache_dir.glob("*.pdf"))
    assert len(cache_outputs) == 1
    assert cache_outputs[0].exists()
