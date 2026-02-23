from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

CANONICAL_PAPER_ID_PREFIXES = ("zotero:", "doi:", "pdfsha256:", "paper:")


def normalize_doi(value: str | None) -> str:
    doi = str(value or "").strip()
    if not doi:
        return ""

    lowered = doi.lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "doi.org/",
        "doi:",
    )
    for prefix in prefixes:
        if lowered.startswith(prefix):
            doi = doi[len(prefix) :]
            lowered = doi.lower()
            break

    return doi.strip().lower().rstrip(").,;]>\"'")


def is_canonical_paper_id(value: str | None) -> bool:
    paper_id = str(value or "").strip()
    if not paper_id:
        return False
    return paper_id.startswith(CANONICAL_PAPER_ID_PREFIXES)


def classify_paper_id(value: str | None) -> str:
    paper_id = str(value or "").strip()
    if not paper_id:
        return "empty"
    if is_canonical_paper_id(paper_id):
        prefix = paper_id.split(":", 1)[0]
        return f"canonical:{prefix}"

    lowered = paper_id.lower()
    if lowered.startswith(("http://", "https://", "file://")):
        return "legacy:url_like"
    if lowered.startswith("10.") or "doi.org/" in lowered:
        return "legacy:doi_like"
    if lowered.startswith("local--") or lowered.startswith("local-") or lowered.startswith("localfile:"):
        return "legacy:local_like"
    return "legacy:other"


def propose_canonical_paper_id(
    current_paper_id: str | None,
    *,
    doi: str | None = None,
    pdf_path: str | Path | None = None,
) -> str:
    current = str(current_paper_id or "").strip()
    if is_canonical_paper_id(current):
        return current

    proposed = make_paper_id(doi=doi, pdf_path=pdf_path)
    if proposed == "paper:unknown":
        return current
    return proposed


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_paper_id(
    *,
    zotero_key: str | None = None,
    doi: str | None = None,
    pdf_path: str | Path | None = None,
    fallback: str | None = None,
) -> str:
    key = str(zotero_key or "").strip()
    if key:
        return f"zotero:{key}"

    norm_doi = normalize_doi(doi)
    if norm_doi:
        return f"doi:{norm_doi}"

    if pdf_path:
        try:
            pdf_hash = sha256_file(pdf_path)
            if pdf_hash:
                return f"pdfsha256:{pdf_hash}"
        except Exception:
            pass

    fb = str(fallback or "").strip()
    if fb:
        return fb

    return "paper:unknown"
