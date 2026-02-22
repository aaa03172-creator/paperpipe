from __future__ import annotations

import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "DOI:"):
        if doi.startswith(prefix.lower()):
            doi = doi[len(prefix) :]
            break
    return doi.strip().rstrip(").,;]>\"'")


def sanitize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def extract_doi_from_filename(path: Path) -> str:
    stem = path.stem
    candidate = stem.replace("_", "/")
    match = DOI_RE.search(candidate)
    if match:
        return normalize_doi(match.group(0))
    return ""


def extract_doi_candidates_from_pdf_content(path: Path) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def record(value: str, source: str) -> None:
        doi = normalize_doi(value)
        if not doi or doi in seen:
            return
        candidates.append((doi, source))
        seen.add(doi)

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        meta = reader.metadata or {}
        for value in meta.values():
            if not value:
                continue
            for match in DOI_RE.finditer(str(value)):
                record(match.group(0), "metadata")
        for page in reader.pages[:3]:
            text = page.extract_text() or ""
            for match in DOI_RE.finditer(text):
                record(match.group(0), "text")
    except Exception:
        pass

    try:
        raw = path.read_bytes()
        text = raw.decode("latin-1", errors="ignore")
        for match in DOI_RE.finditer(text):
            record(match.group(0), "raw")
    except Exception:
        pass
    return candidates


def tokenize_text_for_score(value: str) -> set[str]:
    return {token for token in sanitize_text(value).split() if len(token) >= 3}


def is_confident_content_doi_match(file_stem: str, row: dict[str, Any], source: str) -> bool:
    if source == "metadata":
        return True
    stem_tokens = tokenize_text_for_score(file_stem)
    if not stem_tokens:
        return False

    title = str(row.get("title") or "")
    title_tokens = tokenize_text_for_score(title)
    if stem_tokens.intersection(title_tokens):
        return True

    paper_id = str(row.get("paper_id") or "").lower()
    if paper_id and paper_id in file_stem.lower():
        return True

    return SequenceMatcher(None, sanitize_text(file_stem), sanitize_text(title)).ratio() >= 0.35


def best_title_candidates(
    filename_stem: str,
    rows: list[dict[str, Any]],
    threshold: float,
) -> list[tuple[float, dict[str, Any]]]:
    key = sanitize_text(filename_stem)
    scored: list[tuple[float, dict[str, Any]]] = []
    if not key:
        return scored
    for row in rows:
        title = sanitize_text(str(row.get("title") or ""))
        if not title:
            continue
        score = SequenceMatcher(None, key, title).ratio()
        if score >= threshold:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def resolve_destination(storage_dir: Path, paper_id: str, suffix: str = ".pdf") -> Path:
    storage_dir.mkdir(parents=True, exist_ok=True)
    target = storage_dir / f"{paper_id}{suffix}"
    if not target.exists():
        return target
    ts = int(time.time())
    return storage_dir / f"{paper_id}_{ts}{suffix}"
