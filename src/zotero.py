import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

def export_to_ris(paper_data: Dict[str, Any], export_dir: Path) -> Path:
    """
    Export paper data to a RIS file for Zotero import.
    Appends to a daily RIS file (e.g., export/2024-01-27_import.ris).
    """
    if not export_dir:
        logger.warning("Export directory not configured. Skipping Zotero export.")
        return None

    export_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    ris_file = export_dir / f"{today}_import.ris"
    
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
            
        ris_lines.append(f"DO  - {data.get('id', '').replace('PMID:', '')}") # Simple ID/DOI handling
        ris_lines.append(f"UR  - {data.get('link', '')}")
        ris_lines.append(f"AB  - {data.get('summary', '')}")
        
        # Tags (Slot + Hybrid Tags)
        slot = data.get('slot', 'Uncategorized')
        ris_lines.append(f"KW  - Slot:{slot}")
        
        hybrid_tags = data.get('hybrid_tags', {})
        if hybrid_tags:
            for tag in hybrid_tags.get('soft_tags', []):
                 ris_lines.append(f"KW  - {tag.replace('#', '')}")
        
        ris_lines.append("ER  - \n")
        
        # Append to file
        with open(ris_file, "a", encoding="utf-8") as f:
            f.write("\n".join(ris_lines))
            
        logger.info(f"   📥 Exported to Zotero RIS: {ris_file}")
        return ris_file

    except Exception as e:
        logger.error(f"Failed to export RIS: {e}")
        return None
