from fastapi import APIRouter, HTTPException
import json
import os
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/papers", tags=["papers"])

ZOTERO_EXPORT_PATH = "storage/zotero_export.json"

class PaperSummary(BaseModel):
    paper_id: str
    citekey: str
    title: str
    year: int
    pdf_exists: bool

class PaperDetail(PaperSummary):
    pdf_path: Optional[str] = None
    authors: List[str] = []

def _load_zotero_data():
    if not os.path.exists(ZOTERO_EXPORT_PATH):
        return []
    try:
        with open(ZOTERO_EXPORT_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def _parse_paper(item):
    # Extract ID (Zotero Key)
    paper_id = item.get("id", "unknown")
    citekey = item.get("citation-key", paper_id)
    title = item.get("title", "Untitled")
    
    # Extract Year
    issued = item.get("issued", {}).get("date-parts", [[0]])
    year = issued[0][0] if issued and issued[0] else 0
    
    # Extract PDF Path (naive check based on 'custom' extra field or heuristic)
    # Better BibTeX might export file paths differently depending on settings.
    # For now, let's assume a standard path pattern or check 'file' field if CSL-JSON has it.
    # CSL-JSON usually doesn't have a standardized file path field easily accessible 
    # unless exported with specific options.
    # Let's assume a convention: storage/{citekey}.pdf
    
    # Check if PDF exists in library
    # The requirement says "extract... pdf_path". 
    # Often BetterBibTeX puts it in `file` or we infer it.
    # Let's infer it for now as `Library/{citekey}.pdf` or check the item.
    
    pdf_path = f"Library/{citekey}.pdf" # Hypothetical path
    # If the item has a 'file' field from specific exports, use it.
    
    # Check actual file existence
    pdf_exists = os.path.exists(pdf_path)
    
    authors = []
    if "author" in item:
        for a in item["author"]:
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name: authors.append(name)

    return PaperDetail(
        paper_id=paper_id,
        citekey=citekey,
        title=title,
        year=year,
        pdf_exists=pdf_exists,
        pdf_path=pdf_path if pdf_exists else None,
        authors=authors
    )

@router.get("", response_model=List[PaperSummary])
async def list_papers():
    raw_data = _load_zotero_data()
    papers = []
    for item in raw_data:
        # Filter for entries that look like papers
        if item.get("type") in ["article-journal", "paper-conference", "report", "article", "book"]:
             papers.append(_parse_paper(item))
    return papers

@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper(paper_id: str):
    raw_data = _load_zotero_data()
    for item in raw_data:
        if item.get("id") == paper_id or item.get("citation-key") == paper_id:
             return _parse_paper(item)
    raise HTTPException(status_code=404, detail="Paper not found")
