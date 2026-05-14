import logging
from pathlib import Path
import pypdf

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: Path, max_pages: int = 5) -> str:
    """
    Extracts text from a PDF file up to max_pages.
    Returns empty string on failure.
    """
    if not pdf_path.exists():
        logger.warning(f"PDF not found at {pdf_path}")
        return ""
        
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        text = ""
        count = 0
        for page in reader.pages:
            if count >= max_pages:
                break
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
            count += 1
        
        logger.info(f"Extracted {len(text)} chars from {pdf_path.name} ({count} pages)")
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        return ""
