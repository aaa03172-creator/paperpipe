import hashlib
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

import fitz

logger = logging.getLogger(__name__)


def detect_need_ocr(pdf_path: Path, min_text_chars: int = 200) -> bool:
    """
    Heuristic OCR gate:
    - no extracted text, or
    - extracted text below threshold.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning(f"detect_need_ocr: failed to open PDF ({pdf_path}): {e}")
        return False

    try:
        text_len = 0
        for page in doc:
            text_len += len((page.get_text() or "").strip())
        return text_len < min_text_chars
    finally:
        doc.close()


def run_ocr(
    pdf_in: Path,
    pdf_out: Path,
    lang: str = "eng",
    deskew: bool = True,
) -> Dict[str, Any]:
    """
    Run OCRmyPDF in fail-safe mode. Never overwrites input.
    """
    if shutil.which("ocrmypdf") is None:
        return {
            "ocr_applied": False,
            "ocr_engine": "ocrmypdf",
            "ocr_version": None,
            "ocr_lang": lang,
            "ocr_output_path": None,
            "error": "ocrmypdf_not_installed",
        }

    version = None
    try:
        version = subprocess.check_output(["ocrmypdf", "--version"], text=True).strip()
    except Exception:
        version = None

    cmd = [
        "ocrmypdf",
        "--skip-text",
        "--force-ocr",
        "--language",
        lang,
    ]
    if deskew:
        cmd.append("--deskew")
    cmd.extend([str(pdf_in), str(pdf_out)])

    try:
        pdf_out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {
            "ocr_applied": True,
            "ocr_engine": "ocrmypdf",
            "ocr_version": version,
            "ocr_lang": lang,
            "ocr_output_path": str(pdf_out),
            "error": None,
        }
    except Exception as e:
        logger.warning(f"OCR fallback failed for {pdf_in}: {e}")
        return {
            "ocr_applied": False,
            "ocr_engine": "ocrmypdf",
            "ocr_version": version,
            "ocr_lang": lang,
            "ocr_output_path": None,
            "error": str(e),
        }


def build_ocr_cache_path(pdf_path: Path, cache_dir: Path, lang: str) -> Path:
    sig = hashlib.sha256((str(pdf_path.resolve()) + "|" + lang).encode("utf-8")).hexdigest()
    return cache_dir / f"{sig}.pdf"
