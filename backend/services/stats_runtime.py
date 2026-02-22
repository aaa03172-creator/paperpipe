from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.db_utils import get_db_connection
from src.db_event_log import log_user_action
from src.schemas.agent_artifacts import StatsReport

STATS_TRIGGER_TAGS = {"#important", "#action/stats_check"}


def resolve_stats_trigger_for_paper(
    paper_id: str,
    *,
    run_verify: bool,
    run_profile: str,
) -> tuple[bool, str]:
    """
    Decide whether stats verification should run.

    Priority:
    1) fast_ingest explicitly disables stats.
    2) deep_verify profile always enables stats.
    3) run_verify=True enables stats.
    4) trigger tags in feedback_json enable stats.
    """
    reasons: list[str] = []

    profile = (run_profile or "").strip().lower()
    if profile == "fast_ingest":
        return False, "profile:fast_ingest_skip"

    if profile == "deep_verify":
        reasons.append("profile:deep_verify")

    if run_verify:
        reasons.append("flag:run_verify")

    matched_tags = _load_stats_trigger_tags(paper_id)
    if matched_tags:
        reasons.append("tags:" + ",".join(sorted(matched_tags)))
        _record_trigger_actions(paper_id, matched_tags)

    if not reasons:
        return False, "none"
    return True, ";".join(reasons)


def build_stats_cache_key(
    *,
    doc_artifact: Any,
    claim_set: Any,
    stats_profile: str,
    schema_version: str,
) -> tuple[str, str]:
    """
    Build deterministic cache key using:
      key = sha256(paper_hash + stats_profile + schema_version)
    """
    doc_payload = _safe_model_dump(doc_artifact)
    claim_payload = _safe_model_dump(claim_set)

    basis = {
        "doc": doc_payload,
        "claims": claim_payload,
    }
    paper_hash = hashlib.sha256(
        json.dumps(basis, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    key_material = f"{paper_hash}|{stats_profile}|{schema_version}".encode("utf-8")
    cache_key = hashlib.sha256(key_material).hexdigest()
    return cache_key, paper_hash


def load_cached_stats_report(cache_dir: Path, cache_key: str) -> tuple[StatsReport | None, Path]:
    cache_path = cache_dir / f"{cache_key}.json"
    if not cache_path.exists():
        return None, cache_path

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        try:
            return StatsReport.model_validate(data), cache_path
        except Exception:
            return StatsReport(**data), cache_path
    except Exception:
        return None, cache_path


def save_cached_stats_report(cache_dir: Path, cache_key: str, report: StatsReport) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{cache_key}.json"
    cache_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return cache_path


def _safe_model_dump(payload: Any) -> Any:
    if payload is None:
        return None
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "dict"):
        return payload.dict()
    return payload


def _load_stats_trigger_tags(paper_id: str) -> set[str]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT feedback_json
            FROM papers
            WHERE paper_id = ? OR doi = ?
            LIMIT 1
            """,
            (paper_id, paper_id),
        ).fetchone()
        if not row:
            return set()
        raw_feedback = row[0]
    except Exception:
        return set()
    finally:
        conn.close()

    try:
        payload = json.loads(raw_feedback) if raw_feedback else {}
    except Exception:
        return set()
    if not isinstance(payload, dict):
        return set()

    tags: set[str] = set()
    for raw in payload.get("soft_tags") or []:
        normalized = _normalize_tag(raw)
        if normalized:
            tags.add(normalized)
    for raw in payload.get("tags") or []:
        normalized = _normalize_tag(raw)
        if normalized:
            tags.add(normalized)

    return tags.intersection(STATS_TRIGGER_TAGS)


def _normalize_tag(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    if not value:
        return None

    value = value.replace(" ", "")
    if value == "important":
        return "#important"
    if value in {"action/stats_check", "#action/stats_check", "stats_check", "#stats_check"}:
        return "#action/stats_check"
    if not value.startswith("#"):
        value = f"#{value}"
    return value


def _record_trigger_actions(paper_id: str, matched_tags: set[str]) -> None:
    action_map = {
        "#important": "important",
        "#action/stats_check": "stats_check",
    }
    for tag in matched_tags:
        action_type = action_map.get(tag)
        if not action_type:
            continue
        try:
            log_user_action(
                paper_id=paper_id,
                action_type=action_type,
                source="runtime",
                payload={"tag": tag},
            )
        except Exception:
            continue
