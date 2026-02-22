from __future__ import annotations

import hashlib
import re


def make_paper_key(paper_id: str) -> str:
    """
    Deterministic filesystem-safe key derived from paper_id.

    Format:
      {normalized_slug}_{hash8}
    """
    raw = str(paper_id or "").strip().lower()
    if not raw:
        raw = "paper"

    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if not slug:
        slug = "paper"
    slug = slug[:48]

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{digest}"
