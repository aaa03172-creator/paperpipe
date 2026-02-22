from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.institutional_access import (
    extract_institutional_proxy_link,
    generate_institutional_proxy_url,
)


def build_zotero_links(paper: Dict[str, Any]) -> List[str]:
    links: List[str] = []
    zotero_key = (paper.get("zotero_key") or "").strip()
    if not zotero_key:
        return links

    links.append(f"[Zotero Item](zotero://select/library/items/{zotero_key})")

    page = paper.get("page")
    if page is not None:
        links.append(f"[Zotero PDF](zotero://open-pdf/library/items/{zotero_key}?page={page})")

    return links


def build_pdf_links(paper: Dict[str, Any], vault_path: Path) -> List[str]:
    links: List[str] = []
    pdf_path_str = paper.get("pdf_path")
    if not pdf_path_str:
        return links

    pdf_path = Path(pdf_path_str).expanduser()
    if pdf_path.exists():
        try:
            rel = pdf_path.relative_to(vault_path)
            links.append(f"[[{rel.as_posix()}]]")
        except ValueError:
            links.append(f"[Open PDF](file://{pdf_path.absolute()})")
    else:
        links.append(f"[Open PDF](file://{pdf_path.absolute()})")

    return links


def build_institutional_download_block(paper: Dict[str, Any], feedback: Dict[str, Any]) -> str:
    status = str(paper.get("pdf_status") or "").strip().lower()
    if status != "manual_required":
        return ""

    url = extract_institutional_proxy_link(feedback)
    if not url:
        url = generate_institutional_proxy_url(paper=paper)
    if not url:
        return ""

    return (
        "## Download (Institutional)\n"
        f"- [Institutional Link]({url})\n"
        "- Login once, download PDF, it will be auto-collected.\n"
    )


def sanitize_frontmatter_tag(tag: Any) -> Optional[str]:
    if tag is None:
        return None
    value = str(tag).strip()
    if not value:
        return None
    if value.startswith("#"):
        value = value[1:]
    value = value.replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_/-]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or None


def expected_obsidian_relpath_for_paper_id(paper_id: str) -> str:
    safe_filename = "".join([c for c in paper_id if c.isalnum() or c in (" ", "-", "_")]).strip()
    if not safe_filename:
        safe_filename = "paper"
    return f"Inbox/PaperPipe/{safe_filename}.md"
