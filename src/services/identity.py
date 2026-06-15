from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import uuid


_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)
_SAFE_PAPER_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _file_content_paper_id(file_path: str | Path) -> str | None:
    path = Path(file_path).expanduser()
    try:
        if not path.exists() or not path.is_file():
            return None
        digest = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"userpdf-{digest.hexdigest()[:16]}"
    except OSError:
        return None


def normalize_doi(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _DOI_PREFIX_RE.sub("", text)
    return text.strip().lower()


def bridge_doc_id_to_paper_id(doc_id: str) -> str:
    text = str(doc_id or "").strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered.startswith("doi:"):
        doi = normalize_doi(text)
        return f"doi:{doi}" if doi else ""
    if lowered.startswith(("pmid:", "zotero:")):
        prefix, value = text.split(":", 1)
        return f"{prefix.lower()}:{value.strip()}"
    if lowered.startswith("file:"):
        value = text.split(":", 1)[1].strip()
        stable = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
        return f"file:{stable}"
    return text


def make_runtime_paper_id(
    *,
    paper_id: str | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    zotero_key: str | None = None,
    file_path: str | Path | None = None,
) -> str:
    if paper_id and str(paper_id).strip():
        return bridge_doc_id_to_paper_id(str(paper_id))

    if zotero_key and str(zotero_key).strip():
        return f"zotero:{str(zotero_key).strip()}"

    normalized_doi = normalize_doi(str(doi or ""))
    if normalized_doi:
        return f"doi:{normalized_doi}"

    if pmid and str(pmid).strip():
        return f"pmid:{str(pmid).strip()}"

    if file_path:
        content_id = _file_content_paper_id(file_path)
        if content_id:
            return content_id
        return bridge_doc_id_to_paper_id(f"file:{Path(file_path)}")

    raise ValueError("Unable to determine runtime paper_id")


def paper_id_candidate_ids(paper_id: str) -> list[str]:
    text = str(paper_id or "").strip()
    if not text:
        return []

    candidates: list[str] = []

    def _append(value: str) -> None:
        candidate = value.strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    _append(text)
    if text.startswith("zotero:"):
        _append(text.split(":", 1)[1].strip())
    elif ":" not in text:
        _append(f"zotero:{text}")
    return candidates


def paper_id_self_and_suffix_candidate_ids(paper_id: str) -> list[str]:
    text = str(paper_id or "").strip()
    if not text:
        return []

    candidates: list[str] = []
    for candidate in (text, text.split(":", 1)[1].strip() if ":" in text else ""):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def paper_id_search_variants(paper_id: str) -> list[str]:
    text = str(paper_id or "").strip()
    if not text:
        return []

    variants: list[str] = []

    def _append(value: str) -> None:
        candidate = value.strip()
        if candidate and candidate not in variants:
            variants.append(candidate)

    _append(text)
    _append(text.replace(":", ""))
    if ":" in text:
        suffix = text.split(":", 1)[1].strip()
        _append(suffix)
        _append(suffix.replace(":", ""))
    return variants


def paper_note_lookup_candidate_ids(paper_id: str) -> list[str]:
    text = str(paper_id or "").strip()
    if not text:
        return []

    candidates = paper_id_search_variants(text)
    if ":" not in text:
        for candidate in paper_id_search_variants(f"zotero:{text}"):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def new_job_id() -> str:
    return str(uuid.uuid4())


def new_run_id(now: datetime | None = None) -> str:
    dt = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    return f"run_{dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def make_chunk_id(*, page_hint: int | None, section_ordinal: int, chunk_ordinal: int) -> str:
    if page_hint is not None and page_hint > 0:
        return f"p{page_hint:02d}_c{chunk_ordinal:02d}"
    return f"s{section_ordinal:02d}_c{chunk_ordinal:02d}"


def make_paper_key(paper_id: str) -> str:
    text = str(paper_id or "").strip()
    if not text:
        text = "paper"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"paper_{digest}"


def legacy_artifact_paper_segment(paper_id: str) -> str:
    return str(paper_id)


def artifact_paper_segment(paper_id: str) -> str:
    raw = legacy_artifact_paper_segment(paper_id).strip()
    if raw and raw not in {".", ".."} and _SAFE_PAPER_SEGMENT_RE.fullmatch(raw):
        return raw
    return make_paper_key(raw)
