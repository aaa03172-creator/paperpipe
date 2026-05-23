from __future__ import annotations

import json
import os
from typing import Any, Optional

PROXY_PREFIX = os.getenv("PAPERPIPE_INSTITUTIONAL_PROXY", "")


def _clean_doi(value: str) -> str:
    doi = (value or "").strip()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "DOI:"]:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix) :]
            break
    return doi.strip()


def _parse_feedback(feedback_json: Any) -> dict[str, Any]:
    if isinstance(feedback_json, dict):
        return feedback_json
    if isinstance(feedback_json, str) and feedback_json.strip():
        try:
            parsed = json.loads(feedback_json)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def generate_institutional_proxy_url(
    doi: Optional[str] = None,
    publisher_url: Optional[str] = None,
    paper: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Build KNU libproxy URL from DOI first, then publisher URL."""
    if paper:
        feedback = _parse_feedback(paper.get("feedback_json"))
        links = feedback.get("links") if isinstance(feedback.get("links"), dict) else {}
        doi = doi or paper.get("doi")
        publisher_url = (
            publisher_url
            or links.get("publisher_url")
            or feedback.get("publisher_url")
            or paper.get("publisher_url")
            or paper.get("link")
        )

    clean_doi = _clean_doi(doi or "")
    if clean_doi:
        return f"{PROXY_PREFIX}https://doi.org/{clean_doi}"

    target = (publisher_url or "").strip()
    if target.startswith("http://") or target.startswith("https://"):
        return f"{PROXY_PREFIX}{target}"

    return None


def upsert_institutional_proxy_link(feedback_json: Any, proxy_url: str) -> str:
    """Store proxy URL in feedback_json.links.institutional_proxy_url."""
    payload = _parse_feedback(feedback_json)
    links = payload.get("links")
    if not isinstance(links, dict):
        links = {}
        payload["links"] = links
    links["institutional_proxy_url"] = proxy_url
    return json.dumps(payload, ensure_ascii=False)


def extract_institutional_proxy_link(feedback_json: Any) -> Optional[str]:
    payload = _parse_feedback(feedback_json)
    links = payload.get("links")
    if isinstance(links, dict):
        url = links.get("institutional_proxy_url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None
