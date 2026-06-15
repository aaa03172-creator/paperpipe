import logging
import hashlib
from pathlib import Path
import re
import tempfile
from typing import Dict, Any

logger = logging.getLogger(__name__)

_RIS_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _ris_export_path(paper_data: Dict[str, Any], export_dir: Path) -> Path:
    identity = str(
        paper_data.get("paper_id")
        or paper_data.get("id")
        or paper_data.get("doi")
        or paper_data.get("title")
        or "paper"
    ).strip()
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    stem = _RIS_FILENAME_SAFE_RE.sub("_", identity).strip("._-") or "paper"
    stem = stem[:80].strip("._-") or "paper"
    return export_dir / "ris" / f"{stem}-{digest}.ris"


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def export_to_ris(paper_data: Dict[str, Any], export_dir: Path) -> Path | None:
    """
    Export paper data to a RIS file for Zotero import.
    Writes one atomic RIS file per paper under export/ris/.
    """
    if not export_dir:
        logger.warning("Export directory not configured. Skipping Zotero export.")
        return None

    ris_file = _ris_export_path(paper_data, Path(export_dir))
    
    # process_paper returns result_dict which IS the paper dict + extras.
    # So `paper_data` argument here should be the result_dict from processor.
    
    # Mapping
    # TY  - JOUR
    # TI  - Title
    # AU  - Author 1 ...
    # AB  - Abstract
    # DO  - DOI
    # UR  - URL
    # KW  - Keywords (Tags)
    # ER  - 
    
    try:
        # Pydantic model dump or dict access
        # result_dict has flattened fields: title, authors, etc.
        # But let's check input of this function. I will call it with result_dict.
        
        data = paper_data
        
        ris_lines = ["TY  - JOUR"]
        ris_lines.append(f"TI  - {data.get('title', 'No Title')}")
        
        for author in data.get('authors', []):
            ris_lines.append(f"AU  - {author}")
            
        # Year
        pub_date = data.get('published', '')
        if pub_date:
            year = pub_date.split("-")[0]
            ris_lines.append(f"PY  - {year}")

        doi = str(data.get("doi") or "").strip()
        if doi:
            ris_lines.append(f"DO  - {doi}")
        ris_lines.append(f"UR  - {data.get('link', '')}")
        ris_lines.append(f"AB  - {data.get('summary', '')}")
        
        # Tags (Slot + Hybrid Tags)
        slot = data.get('slot', 'Uncategorized')
        ris_lines.append(f"KW  - Slot:{slot}")
        
        hybrid_tags = data.get('hybrid_tags')
        if hybrid_tags:
            # Soft Tags (Keywords)
            for tag in hybrid_tags.get('soft_tags', []):
                 ris_lines.append(f"KW  - {tag.replace('#', '')}")
            
            # Hard Tags (Extracted Data)
            for key, value in hybrid_tags.get('hard_tags', {}).items():
                if value and str(value).lower() != 'unknown':
                    ris_lines.append(f"KW  - {key}:{value}")

        # Local File Link (L1)
        # Zotero can import this if it points to a valid file
        local_pdf = data.get('local_pdf_path')
        if local_pdf:
            # RIS format for file link is often L1 - file:///path
            # But standard Zotero import might just want the path.
            # Let's try file URI format.
            abs_path = Path(local_pdf).absolute()
            ris_lines.append(f"L1  - file://{abs_path}")

        ris_lines.append("ER  - \n")
        
        _atomic_write_text(ris_file, "\n".join(ris_lines))
            
        logger.info(f"   📤 Exported to Zotero RIS: {ris_file}")
        return ris_file

    except Exception as e:
        logger.error(f"Failed to export RIS: {e}")
        return None
