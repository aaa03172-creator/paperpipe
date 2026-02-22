from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_feedback(feedback_json: str | None) -> dict[str, Any]:
    if not feedback_json:
        return {}
    try:
        parsed = json.loads(feedback_json)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def extract_tags(feedback: dict[str, Any]) -> list[str]:
    """Best-effort only: extract tags if explicitly present in feedback_json."""
    tags: list[str] = []

    raw_tags = feedback.get("tags")
    if isinstance(raw_tags, list):
        tags.extend(str(t) for t in raw_tags if t)

    soft_tags = feedback.get("soft_tags")
    if isinstance(soft_tags, list):
        for item in soft_tags:
            if isinstance(item, str):
                tags.append(item)
            elif isinstance(item, dict):
                tag_value = item.get("tag") or item.get("name")
                if tag_value:
                    tags.append(str(tag_value))

    cleaned: list[str] = []
    seen: set[str] = set()
    for t in tags:
        tag = t.strip()
        if not tag:
            continue
        if tag.startswith("#"):
            tag = tag[1:]
        if tag not in seen:
            seen.add(tag)
            cleaned.append(tag)

    return cleaned


def build_document(row: dict[str, Any], tags: list[str]) -> str:
    summary = (row.get("summary") or "").strip()
    title = (row.get("title") or "").strip()
    evidence = (row.get("evidence_snippet") or "").strip()

    if summary:
        primary = summary
    else:
        primary = title
        if evidence:
            primary = f"{primary}\nEvidence: {evidence}"

    parts = [primary]

    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    snippet_500 = evidence[:500]
    meta_line = (
        f"Meta: slot={row.get('slot') or ''}; venue={row.get('venue') or ''}; "
        f"gate_reason={row.get('gate_reason') or ''}; evidence_snippet={snippet_500}"
    )
    parts.append(meta_line)

    return "\n\n".join(parts).strip()


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
