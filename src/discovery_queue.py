from __future__ import annotations

import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import load_config
from src.core.ids import make_paper_id
from src.db_paper_read_ops import get_paper_columns
from src.db_utils import get_db_connection
from src.exporter_helpers import expected_obsidian_relpath_for_paper_id
from src.fetch.openalex import OpenAlexFetcher

RELATED_QUEUE_HEADER = "## Related Works (Queue)"
RELATED_QUEUE_RE = re.compile(
    r"^## Related Works \(Queue\)\s*\n.*?(?=^## .+|\Z)",
    re.MULTILINE | re.DOTALL,
)


def run_discovery_queue(
    seed: str,
    limit: int = 10,
    write_obsidian: bool = True,
    fetcher: Optional[OpenAlexFetcher] = None,
) -> Dict[str, Any]:
    if not seed:
        return {
            "seed": seed,
            "items": [],
            "saved": 0,
            "recommended": 0,
            "pending_queue": 0,
            "note_path": None,
        }

    config = load_config()
    fetcher = fetcher or OpenAlexFetcher(email=config.system.unpaywall_email)
    candidates = fetcher.fetch_related_works(seed=seed, limit=limit)

    now_year = datetime.now(timezone.utc).year
    scored_items = []
    for item in candidates:
        scored = dict(item)
        score = _score_candidate(scored, now_year)
        status = "RECOMMENDED" if score >= 0.6 else "PENDING_QUEUE"
        reason = _build_reason(scored, score)
        scored["score"] = score
        scored["status"] = status
        scored["reason"] = reason
        scored["paper_id"] = _make_candidate_paper_id(scored)
        scored_items.append(scored)

    saved = _upsert_discovery_candidates(scored_items)

    note_path = None
    if write_obsidian:
        note_path = _upsert_related_queue_section(seed, scored_items, config.paths.obsidian_vault)

    return {
        "seed": seed,
        "items": scored_items,
        "saved": saved,
        "recommended": sum(1 for x in scored_items if x["status"] == "RECOMMENDED"),
        "pending_queue": sum(1 for x in scored_items if x["status"] == "PENDING_QUEUE"),
        "note_path": str(note_path) if note_path else None,
    }


def upsert_related_queue_section(content: str, new_section: str) -> str:
    section = new_section.strip() + "\n"
    matches = list(RELATED_QUEUE_RE.finditer(content))
    if not matches:
        base = content.rstrip()
        if not base:
            return section
        return f"{base}\n\n{section}"

    first = matches[0]
    out = [content[: first.start()], section]
    cursor = first.end()
    for match in matches[1:]:
        out.append(content[cursor : match.start()])
        cursor = match.end()
    out.append(content[cursor:])
    return "".join(out)


def build_related_queue_markdown(seed: str, items: List[Dict[str, Any]]) -> str:
    lines = [RELATED_QUEUE_HEADER, f"- Seed: `{seed}`"]
    if not items:
        lines.append("- No related works found.")
        return "\n".join(lines)

    for item in items:
        year = item.get("year")
        year_text = f" ({year})" if year else ""
        title = item.get("title") or "Untitled"
        relation = item.get("relation") or "related"
        reason = item.get("reason") or "No reason"
        status = item.get("status") or "PENDING_QUEUE"
        lines.append(
            f"- [{status}] {title}{year_text} | relation={relation} | score={item.get('score', 0):.3f}"
        )
        lines.append(f"  - reason: {reason}")
    return "\n".join(lines)


def _score_candidate(item: Dict[str, Any], now_year: int) -> float:
    year = item.get("year")
    cited_by = int(item.get("cited_by_count") or 0)
    relation = str(item.get("relation") or "")
    is_oa = bool(item.get("is_oa"))

    if isinstance(year, int) and year > 0:
        age = max(0, now_year - year)
        recency = max(0.0, 1.0 - min(age, 20) / 20.0)
    else:
        recency = 0.35

    impact = min(1.0, math.log10(cited_by + 1) / 3.0)
    relation_bonus = 0.05 if relation == "referenced" else 0.0
    oa_bonus = 0.05 if is_oa else 0.0

    score = (0.55 * impact) + (0.35 * recency) + relation_bonus + oa_bonus
    return round(min(1.0, max(0.0, score)), 3)


def _build_reason(item: Dict[str, Any], score: float) -> str:
    relation = item.get("relation") or "related"
    cites = int(item.get("cited_by_count") or 0)
    year = item.get("year")
    parts = [f"relation={relation}", f"citations={cites}", f"score={score:.3f}"]
    if year:
        parts.append(f"year={year}")
    return ", ".join(parts)


def _make_candidate_paper_id(item: Dict[str, Any]) -> str:
    doi = str(item.get("doi") or "").strip().lower()
    if doi:
        return make_paper_id(doi=doi)

    openalex_id = str(item.get("openalex_id") or "").strip()
    if openalex_id:
        return f"openalex:{openalex_id.rstrip('/').split('/')[-1]}"

    title = str(item.get("title") or "untitled").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", title).strip("_") or "untitled"
    return f"related:{slug}"


def _upsert_discovery_candidates(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        columns = get_paper_columns(cursor)
        if not columns:
            return 0

        saved = 0
        for item in items:
            if _upsert_one_candidate(cursor, columns, item):
                saved += 1
        conn.commit()
        return saved
    finally:
        conn.close()


def _upsert_one_candidate(cursor: sqlite3.Cursor, columns: set[str], item: Dict[str, Any]) -> bool:
    paper_id = item["paper_id"]
    doi = item.get("doi")
    existing_id = _find_existing_paper_id(cursor, columns, paper_id, doi)

    updates = {
        "status": item["status"],
        "title": item.get("title") or "Untitled",
        "year": item.get("year"),
        "venue": item.get("venue"),
        "source": "openalex_related",
        "gate_reason": item.get("reason"),
        "evidence_snippet": item.get("reason"),
        "confidence": item.get("score"),
        "slot": "DISCOVER_QUEUE",
    }
    if doi:
        updates["doi"] = doi

    if existing_id:
        fields = []
        params: List[Any] = []
        for key, value in updates.items():
            if key in columns:
                fields.append(f"{key} = ?")
                params.append(value)
        if "updated_at" in columns:
            fields.append("updated_at = CURRENT_TIMESTAMP")
        if not fields:
            return False
        params.append(existing_id)
        cursor.execute(f"UPDATE papers SET {', '.join(fields)} WHERE paper_id = ?", params)
        return True

    insert_map = {
        "paper_id": paper_id,
        "status": item["status"],
        "title": item.get("title") or "Untitled",
        "doi": doi,
        "year": item.get("year"),
        "venue": item.get("venue"),
        "source": "openalex_related",
        "gate_reason": item.get("reason"),
        "evidence_snippet": item.get("reason"),
        "confidence": item.get("score"),
        "slot": "DISCOVER_QUEUE",
    }
    cols = [k for k in insert_map if k in columns]
    if "created_at" in columns:
        cols.append("created_at")
    if "updated_at" in columns:
        cols.append("updated_at")

    vals: List[Any] = [insert_map[k] for k in cols if k not in {"created_at", "updated_at"}]
    if "created_at" in cols:
        vals.append(datetime.now(timezone.utc).isoformat())
    if "updated_at" in cols:
        vals.append(datetime.now(timezone.utc).isoformat())

    placeholders = ", ".join("?" for _ in cols)
    cursor.execute(
        f"INSERT INTO papers ({', '.join(cols)}) VALUES ({placeholders})",
        vals,
    )
    return True


def _find_existing_paper_id(
    cursor: sqlite3.Cursor,
    columns: set[str],
    paper_id: str,
    doi: Optional[str],
) -> Optional[str]:
    if "paper_id" in columns:
        row = cursor.execute(
            "SELECT paper_id FROM papers WHERE paper_id = ? LIMIT 1",
            (paper_id,),
        ).fetchone()
        if row:
            return row[0]

    if doi and "doi" in columns:
        row = cursor.execute(
            "SELECT paper_id FROM papers WHERE doi = ? LIMIT 1",
            (doi,),
        ).fetchone()
        if row:
            return row[0]
    return None


def _upsert_related_queue_section(seed: str, items: List[Dict[str, Any]], vault_path: Path) -> Optional[Path]:
    vault = Path(vault_path).expanduser()
    vault.mkdir(parents=True, exist_ok=True)

    target = _resolve_seed_note_path(seed, vault)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(f"# {seed}\n", encoding="utf-8")

    section = build_related_queue_markdown(seed, items)
    content = target.read_text(encoding="utf-8")
    updated = upsert_related_queue_section(content, section)
    target.write_text(updated, encoding="utf-8")
    return target


def _resolve_seed_note_path(seed: str, vault_path: Path) -> Path:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        columns = get_paper_columns(cursor)
        if columns:
            conditions = []
            params: List[str] = []
            if "paper_id" in columns:
                conditions.append("paper_id = ?")
                params.append(seed)
            if "doi" in columns:
                conditions.append("doi = ?")
                params.append(seed)
            if conditions:
                row = cursor.execute(
                    f"SELECT paper_id, obsidian_path FROM papers WHERE {' OR '.join(conditions)} LIMIT 1",
                    params,
                ).fetchone()
                if row:
                    rel = row["obsidian_path"] if "obsidian_path" in columns else None
                    if rel:
                        return vault_path / str(rel)
                    return vault_path / expected_obsidian_relpath_for_paper_id(str(row["paper_id"] or seed))
    finally:
        conn.close()

    return vault_path / expected_obsidian_relpath_for_paper_id(seed)
