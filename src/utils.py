
import re
from datetime import datetime
from pathlib import Path
from src.schemas import Paper
from src.core.ids import make_paper_id

def clean_filename(text: str) -> str:
    """
    Remove invalid characters from a string to make it safe for filenames.
    Replacing spaces with underscores, removing special chars.
    """
    if not text:
        return "Untitled"
    
    # Remove special characters invalid in filenames
    clean = re.sub(r'[\\/:*?"<>|]', '', text)
    # Replace spaces with underscores
    clean = clean.replace(' ', '_')
    # Remove multiple underscores
    clean = re.sub(r'_+', '_', clean)
    # Trim
    clean = clean.strip('_')
    
    return clean[:100] # Limit length

def generate_filename(paper: Paper) -> str:
    """
    Generate a standardized filename based on Paper metadata.
    Schema: {Year}_{FirstAuthor}_{ShortTitle}.pdf
    e.g. 2024_Kim_DeepLearningForMCI.pdf
    """
    # 1. Year
    today = datetime.now().strftime("%Y-%m-%d")
    year = today[:4]
    if paper.published:
        # Extract YYYY
        match = re.search(r'\d{4}', paper.published)
        if match:
            year = match.group(0)
            
    # 2. First Author
    author = "Unknown"
    if paper.authors:
        # Take first author's last name if possible, or just the string
        first_author = paper.authors[0]
        # Heuristic: split by space, take last part (Last Name)
        parts = first_author.split()
        if parts:
            author = parts[-1] 
        else:
            author = clean_filename(first_author)
    
    # 3. Short Title
    # Take first 4-5 words or up to 30 chars
    title_clean = clean_filename(paper.title)
    short_title = title_clean
    
    return f"{year}_{author}_{short_title}.pdf"

def create_paper_from_pdf(pdf_path: Path) -> Paper:
    """
    Extract metadata from a PDF and create a Paper object.
    Used for local file ingestion and organization.
    """
    from pypdf import PdfReader
    from datetime import datetime

    title = None
    doi = None
    
    try:
        reader = PdfReader(pdf_path)
        meta = reader.metadata
        if meta:
            title = meta.get('/Title')
            doi = meta.get('/DOI') or meta.get('/doi')
            # Try to find date in metadata
            # creation_date = meta.get('/CreationDate') 
    except Exception as e:
        print(f"   ⚠️ PDF Metadata read failed: {e}")

    # Fallback to filename
    if not title or title.strip() == "":
        title = pdf_path.stem.replace("_", " ").replace("-", " ")
    
    paper_id = make_paper_id(
        doi=doi,
        pdf_path=pdf_path,
        fallback=f"localfile:{clean_filename(title).lower()}",
    )
    
    published_date = datetime.now().strftime("%Y-%m-%d")
    
    return Paper(
        id=paper_id,
        title=title,
        source="Local",
        published=published_date,
        authors=["Unknown"], # Hard to extract reliably without DOI
        summary="",
        doi=doi,
        link=f"file://{pdf_path.absolute()}",
        local_pdf_path=pdf_path
    )
