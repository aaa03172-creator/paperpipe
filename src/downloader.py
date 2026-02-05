import requests
import logging
from pathlib import Path
import re
from typing import Optional

from src.schemas import Paper
from src.config import AppConfig

# 로거 설정
logger = logging.getLogger(__name__)

def _sanitize_filename(name: str) -> str:
    """파일 이름으로 사용하기에 부적합한 문자를 제거하거나 대체합니다."""
    # 슬래시, 백슬래시, 콜론 등 일반적인 금지 문자를 밑줄로 대체
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    # 추가적으로 파일명 길이 제한 (예: 200자)
    return name[:200]

def download_paper(paper: Paper, config: AppConfig) -> Paper:
    """
    논문 PDF를 다운로드하여 지정된 디렉토리에 저장합니다.
    다운로드 성공 시 Paper 객체에 로컬 경로를 업데이트하여 반환합니다.
    """
    if not paper.pdf_link:
        logger.debug(f"[{paper.id}] PDF link not available, skipping download.")
        return paper

    if not config.paths.upload_dir:
        logger.warning(f"[{paper.id}] Upload directory not configured, skipping download.")
        return paper

    # 업로드 디렉토리가 없으면 생성
    upload_path = Path(config.paths.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # 파일명 생성 및 정제
    filename = _sanitize_filename(paper.id) + ".pdf"
    filepath = upload_path / filename

    # 이미 파일이 존재하면 다운로드 건너뛰기
    if filepath.exists():
        logger.info(f"[{paper.id}] PDF already exists at {filepath}, skipping download.")
        paper.local_pdf_path = filepath
        return paper

    try:
        if paper.pdf_link:
            logger.info(f"[{paper.id}] Attempting direct download from {paper.pdf_link}...")
            try:
                _download_file(paper.pdf_link, filepath)
                paper.local_pdf_path = filepath
                logger.info(f"[{paper.id}] Successfully downloaded PDF to {filepath}")
                return paper
            except requests.exceptions.RequestException as e:
                logger.warning(f"[{paper.id}] Direct download failed: {e}. Trying Unpaywall...")

        # Unpaywall Attempt
        oa_url = _fetch_oa_link(paper.id, config.system.unpaywall_email)
        if oa_url:
            logger.info(f"[{paper.id}] Found OA link via Unpaywall: {oa_url}")
            _download_file(oa_url, filepath)
            paper.local_pdf_path = filepath
            paper.pdf_link = oa_url  # Update link for reference
            logger.info(f"[{paper.id}] Successfully downloaded OA PDF to {filepath}")
        else:
            logger.warning(f"[{paper.id}] No accessible PDF found (Direct or Unpaywall).")

    except requests.exceptions.RequestException as e:
        logger.error(f"[{paper.id}] Failed to download PDF. Error: {e}")
    
    return paper

def _fetch_oa_link(doi: str, email: Optional[str]) -> Optional[str]:
    """Unpaywall API를 통해 OA PDF 링크를 조회합니다."""
    if not email:
        logger.debug("Unpaywall email not configured. Skipping OA check.")
        return None
        
    # DOI Cleaning (simple)
    clean_doi = doi.replace("doi.org/", "").replace("http://", "").replace("https://", "")
    
    url = f"https://api.unpaywall.org/v2/{clean_doi}?email={email}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            best_loc = data.get('best_oa_location', {})
            if best_loc and best_loc.get('url_for_pdf'):
                return best_loc['url_for_pdf']
    except Exception as e:
        logger.warning(f"Unpaywall query failed for {doi}: {e}")
    
    return None

def _download_file(url: str, filepath: Path):
    """URL에서 파일을 stream 모드로 다운로드합니다."""
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
