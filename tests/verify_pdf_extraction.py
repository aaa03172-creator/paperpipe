from pathlib import Path
from src.pdf import extract_text_from_pdf
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_extraction():
    # Test valid PDF
    pdf_path = Path("Library/1411.2441.pdf")
    if pdf_path.exists():
        logger.info(f"Testing valid PDF: {pdf_path}")
        text = extract_text_from_pdf(pdf_path, max_pages=3)
        if len(text) > 100:
            logger.info("✅ Success: Extracted substantial text.")
            print(f"Sample text:\n{text[:500]}...")
        else:
            logger.error("❌ Failure: Extracted text too short.")
    else:
        logger.warning(f"⚠️ Skipped valid PDF test: {pdf_path} not found.")

    # Test missing PDF
    missing_path = Path("Library/non_existent.pdf")
    logger.info(f"Testing missing PDF: {missing_path}")
    text = extract_text_from_pdf(missing_path)
    if text == "":
        logger.info("✅ Success: Handled missing PDF correctly.")
    else:
        logger.error(f"❌ Failure: Should return empty string for missing PDF, got '{text}'")

if __name__ == "__main__":
    test_extraction()
