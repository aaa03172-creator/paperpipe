from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]*[A-Z0-9]", re.IGNORECASE)
_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "urn:doi:")


def _normalize_doi(raw: str | None) -> str:
    value = str(raw or "").strip()
    lower_value = value.lower()
    for prefix in _DOI_PREFIXES:
        if lower_value.startswith(prefix):
            value = value[len(prefix) :]
            lower_value = value.lower()
            break
    match = _DOI_RE.search(value)
    if match:
        return match.group(0).strip()
    return value.strip()


def _extract_doi_from_text(text: str | None) -> Optional[str]:
    text = str(text or "").strip()
    if not text:
        return None
    normalized = _normalize_doi(text)
    match = _DOI_RE.search(normalized)
    if match:
        return _normalize_doi(match.group(0)) or None
    return None


def _extract_doi(*candidates: str | None) -> Optional[str]:
    for candidate in candidates:
        doi = _extract_doi_from_text(candidate)
        if doi:
            return doi
    return None


def _crossref_lookup(doi: str, timeout_seconds: int) -> tuple[bool, str]:
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    headers = {"User-Agent": "paperpipe/0.1 (anchor-verify)"}
    try:
        response = requests.get(url, timeout=timeout_seconds, headers=headers)
        if response.status_code == 200:
            return True, "CROSSREF_OK"
        if response.status_code == 404:
            return False, "CROSSREF_NOT_FOUND"
        return False, f"CROSSREF_HTTP_{response.status_code}"
    except requests.Timeout:
        return False, "CROSSREF_TIMEOUT"
    except Exception as exc:
        logger.debug("Crossref anchor verify failed for %s: %s", doi, exc)
        return False, "CROSSREF_ERROR"


def _semantic_scholar_lookup(doi: str, timeout_seconds: int) -> tuple[bool, str]:
    encoded = quote(f"DOI:{doi}", safe="")
    url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded}?fields=paperId,title,year"
    headers = {"User-Agent": "paperpipe/0.1 (anchor-verify)"}
    try:
        response = requests.get(url, timeout=timeout_seconds, headers=headers)
        if response.status_code == 200:
            return True, "S2_OK"
        if response.status_code == 404:
            return False, "S2_NOT_FOUND"
        return False, f"S2_HTTP_{response.status_code}"
    except requests.Timeout:
        return False, "S2_TIMEOUT"
    except Exception as exc:
        logger.debug("Semantic Scholar anchor verify failed for %s: %s", doi, exc)
        return False, "S2_ERROR"


def resolve_anchor_api_context(
    doc_id: str | None,
    timeout_seconds: int = 2,
    *,
    doi_hint: str | None = None,
    source_ref: str | None = None,
    id_hint: str | None = None,
) -> Dict[str, Any]:
    """
    Resolve verification API context for anchor audit logs.
    Returns provider + reason codes used to annotate each anchor check.
    """
    doi = _extract_doi(doi_hint, doc_id, id_hint, source_ref)
    if not doi:
        return {
            "doi": None,
            "provider": "none",
            "status": "no_doi",
            "reason_codes": ["NO_DOI", "NO_API"],
        }

    crossref_ok, crossref_reason = _crossref_lookup(doi, timeout_seconds=timeout_seconds)
    if crossref_ok:
        return {
            "doi": doi,
            "provider": "crossref",
            "status": "ok",
            "reason_codes": [crossref_reason],
        }

    s2_ok, s2_reason = _semantic_scholar_lookup(doi, timeout_seconds=timeout_seconds)
    if s2_ok:
        return {
            "doi": doi,
            "provider": "semantic_scholar",
            "status": "ok",
            "reason_codes": [crossref_reason, s2_reason],
        }

    return {
        "doi": doi,
        "provider": "none",
        "status": "unavailable",
        "reason_codes": [crossref_reason, s2_reason, "NO_API"],
    }
