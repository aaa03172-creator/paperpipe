import logging
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from pydantic import ValidationError
from pypdf import PdfReader

from src.config import AppConfig, load_config
from src.schemas import Paper
from src.processor import process_paper
from src.fetchers import fetch_pubmed  
from src.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

def extract_doi_from_pdf(pdf_path: Path) -> Optional[str]:
    """PDF 첫 페이지에서 DOI를 추출합니다."""
    try:
        reader = PdfReader(pdf_path)
        if not reader.pages:
            return None
            
        first_page_text = reader.pages[0].extract_text()
        # DOI Regex (standard)
        # Matches: 10.xxxx/xxxxx
        doi_pattern = r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b'
        match = re.search(doi_pattern, first_page_text, re.IGNORECASE)
        
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Failed to extract DOI from {pdf_path}: {e}")
        
    return None

def process_local_pdf(pdf_path: Path, config: AppConfig):
    """
    로컬 PDF를 처리합니다.
    1. DOI 추출
    2. 메타데이터 검색 (PubMed Fetcher using DOI as term)
    3. Paper 객체 생성 및 처리
    4. 라이브러리로 이동
    """
    logger.info(f"Processing local PDF: {pdf_path.name}")
    
    doi = extract_doi_from_pdf(pdf_path)
    paper = None
    
    if doi:
        logger.info(f"Found DOI: {doi}. Fetching metadata...")
        # Use fetch_pubmed with DOI as keyword
        papers = fetch_pubmed([doi], max_results=1)
        if papers:
            paper = papers[0]
            logger.info(f"Metadata fetched: {paper.title}")
    
    if not paper:
        logger.warning(f"Metadata fetch failed or no DOI. Falling back to basic file info.")
        paper = Paper(
            id=doi if doi else f"local-{int(time.time())}",
            title=pdf_path.stem.replace("_", " "),
            authors=["Unknown"],
            published="2024-01-01", # Placeholder
            source="Unknown",
            summary="Imported from local watch folder.",
            link=f"https://doi.org/{doi}" if doi else "",
            local_pdf_path=pdf_path
        )

    # Ensure local path is set (fetcher doesn't set it)
    paper.local_pdf_path = pdf_path
    
    # Trigger Processor
    llm_provider = get_llm_provider(config.llm)
    
    # We assign a default slot "manual" or "clinical" logic?
    # Let's use 'manual' slot to indicate source.
    paper_data = {'paper': paper, 'slot': 'manual', 'tags': ['#ManualImport']}
    
    try:
        result = process_paper(paper_data, config, llm_provider, is_deep_target=False)
        logger.info(f"Successfully processed {paper.title}")
    except Exception as e:
        logger.error(f"Error processing {paper.title}: {e}", exc_info=True)


def run_watcher(path: Path, config: AppConfig):
    """폴더를 주기적으로 스캔하여 새로운 PDF를 처리합니다."""
    logger.info(f"Starting Watch Folder service on {path}")
    if not path.exists():
        logger.error(f"Watch folder {path} does not exist!")
        return

    while True:
        try:
            # Simple polling
            for item in path.glob("*.pdf"):
                # Check if file is completely copied (not changing size)
                # For simplicity, just process. Real watchers use file system events.
                process_local_pdf(item, config)
                
                # Move to 'processed' folder to avoid loop
                processed_dir = path / "processed"
                processed_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(processed_dir / item.name))
                logger.info(f"Moved {item.name} to processed/")
                
        except Exception as e:
            logger.error(f"Watcher loop error: {e}")
        
        time.sleep(10)  # Sleep 10 seconds
