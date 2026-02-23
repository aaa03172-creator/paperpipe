from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.feedback_retriever import FeedbackRetriever
from src.core.artifact_paths import build_artifact_dir
from src.core.paper_identity import make_paper_key
from src.db_utils import get_db_connection
from src.profiles.profile_store import load_profiles


logger = logging.getLogger("paperpipe.backend")
FEEDBACK_FILE = Path("storage/feedback.jsonl")
REVIEW_NEEDS_READER = "NEEDS_READER"


def resolve_note_path_for_paper(config, paper_id: str) -> Optional[Path]:
    vault_path = config.paths.obsidian_vault
    idx_files = [config.paths.index_all, Path("00_Index/on_demand.csv")]
    for rel_idx in idx_files:
        index_path = vault_path / rel_idx
        if not index_path.exists():
            continue
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row.get("Paper_ID") == paper_id or row.get("DOI") == paper_id:
                        note_rel = row.get("Note_Path")
                        if note_rel:
                            note_path = vault_path / note_rel
                            if note_path.exists():
                                return note_path
        except Exception:
            continue
    return None


def resolve_persona_hint(persona_id: str, *, load_profiles_fn=load_profiles) -> Optional[str]:
    pid = (persona_id or "default").strip()
    if not pid or pid == "default":
        return None
    try:
        conf = load_profiles_fn()
    except Exception as exc:
        logger.warning("Persona profile load failed for '%s': %s", pid, exc)
        return None
    for profile in conf.profiles:
        if profile.id == pid and profile.enabled:
            hint_parts = [f"profile_id={profile.id}", f"title={profile.title}"]
            if profile.notes:
                hint_parts.append(f"notes={profile.notes}")
            query = profile.query.to_boolean_string()
            if query:
                hint_parts.append(f"query_focus={query}")
            return "\n".join(hint_parts)
    return None


def load_similar_feedback_top3(
    query_text: str,
    limit: int = 3,
    *,
    feedback_file: Path = FEEDBACK_FILE,
) -> List[Dict[str, str]]:
    """
    Uses FeedbackRetriever to find top-K approved feedback cases relevant to the query.
    """
    try:
        retriever = FeedbackRetriever()
        cases = retriever.query_relevant_feedback(query_text, limit=limit)
        if cases:
            return cases
    except Exception as exc:
        logger.warning("Failed to load similar feedback: %s", exc)
    if not feedback_file.exists():
        return []

    lines = feedback_file.read_text(encoding="utf-8").splitlines()
    items: List[Dict[str, str]] = []
    seen_papers: set[str] = set()
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if rec.get("accepted") is not True:
            continue
        rec_paper = str(rec.get("paper_id") or "")
        if not rec_paper or rec_paper == query_text or rec_paper in seen_papers:
            continue
        correction = str(rec.get("user_correction") or "").strip()
        if not correction:
            continue
        preview = correction.replace("\n", " ")[:180]
        items.append({"paper_id": rec_paper, "preview": preview})
        seen_papers.add(rec_paper)
        if len(items) >= limit:
            break
    return items


def resolve_main_model(config) -> str:
    agents = getattr(config, "agents", None)
    model_name = getattr(agents, "main_model", None) if agents is not None else None
    return model_name or "llama3:latest"


def write_bootstrap_meta(artifact_dir: Path, payload: Dict[str, Any]) -> None:
    try:
        with open(artifact_dir / "bootstrap_meta.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to write bootstrap_meta.json: %s", exc)


def enqueue_needs_reader_followup(paper_id: str, reason: str) -> str:
    """
    Best-effort operational follow-up for not-ready claimsets.
    Returns one of: queued | already_open | queue_unavailable | queue_error.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM review_queue
            WHERE paper_id = ? AND decision = ? AND resolved_at IS NULL
            LIMIT 1
            """,
            (paper_id, REVIEW_NEEDS_READER),
        )
        if cur.fetchone():
            return "already_open"
        cur.execute(
            """
            INSERT INTO review_queue (paper_id, decision, reason)
            VALUES (?, ?, ?)
            """,
            (paper_id, REVIEW_NEEDS_READER, reason),
        )
        conn.commit()
        return "queued"
    except sqlite3.OperationalError as exc:
        logger.warning("review_queue unavailable for paper_id=%s: %s", paper_id, exc)
        return "queue_unavailable"
    except Exception as exc:
        logger.warning("review_queue enqueue failed for paper_id=%s: %s", paper_id, exc)
        return "queue_error"
    finally:
        if conn is not None:
            conn.close()


def locate_pdf_for_paper(config, paper_id: str) -> Optional[Path]:
    results = list(config.paths.library_dir.rglob(f"*{paper_id}*.pdf"))
    if not results and "/" in paper_id:
        clean_id = paper_id.replace("/", "_")
        results = list(config.paths.library_dir.rglob(f"*{clean_id}*.pdf"))
    if not results:
        return None
    return results[0]


def build_bootstrap_meta(
    job_id: str,
    run_id: str,
    paper_id: str,
    persona_id: str,
    run_verify: bool,
) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "run_id": run_id,
        "paper_id": paper_id,
        "paper_key": make_paper_key(paper_id),
        "persona_id": persona_id,
        "persona_applied": False,
        "similar_feedback_count": 0,
        "similar_feedback_paper_ids": [],
        "run_verify": bool(run_verify),
        "stats_trigger_reason": "none",
        "stats_cache_hit": False,
        "stats_cache_key": None,
        "stats_cache_path": None,
        "reader_model": None,
        "verifier_used": bool(run_verify),
        "verifier_status": "not_run",
        "stats_report_written": False,
        "artifact_document_written": False,
        "artifact_index_written": False,
        "artifact_claimset_written": False,
        "artifact_stats_written": False,
        "claimset_readiness": "unknown",
        "claimset_ready": None,
        "claimset_claim_count": 0,
        "claimset_readiness_reason": "not_evaluated",
        "claimset_readiness_badge": "UNKNOWN",
        "claimset_ops_action": "none",
        "claimset_ops_alert": False,
        "claimset_ops_note": "not_evaluated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def create_artifact_context(
    job_id: str,
    run_id: str,
    paper_id: str,
    persona_id: str,
    run_verify: bool,
) -> tuple[Path, Dict[str, Any]]:
    paper_key = make_paper_key(paper_id)
    artifact_dir = build_artifact_dir(run_id=run_id, paper_id=paper_id, paper_key=paper_key)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_meta = build_bootstrap_meta(job_id, run_id, paper_id, persona_id, run_verify)
    bootstrap_meta["artifact_paper_dir"] = str(artifact_dir.parent)
    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    return artifact_dir, bootstrap_meta


def write_artifact_model(artifact_dir: Path, filename: str, model_obj: Any) -> None:
    with open(artifact_dir / filename, "w", encoding="utf-8") as handle:
        handle.write(model_obj.model_dump_json(indent=2))


def update_claimset_readiness(bootstrap_meta: Dict[str, Any], paper_id: str, claim_count: int) -> None:
    bootstrap_meta["claimset_claim_count"] = claim_count
    if claim_count > 0:
        bootstrap_meta["claimset_readiness"] = "ready"
        bootstrap_meta["claimset_ready"] = True
        bootstrap_meta["claimset_readiness_reason"] = "claims_present"
        bootstrap_meta["claimset_readiness_badge"] = "READY"
        bootstrap_meta["claimset_ops_action"] = "none"
        bootstrap_meta["claimset_ops_alert"] = False
        bootstrap_meta["claimset_ops_note"] = "ready"
        return

    bootstrap_meta["claimset_readiness"] = "not_ready"
    bootstrap_meta["claimset_ready"] = False
    bootstrap_meta["claimset_readiness_reason"] = "empty_claims"
    bootstrap_meta["claimset_readiness_badge"] = "NOT_READY"
    followup = enqueue_needs_reader_followup(
        paper_id=paper_id,
        reason="Runtime claimset empty (claims=0) after reader step",
    )
    if followup in {"queued", "already_open"}:
        bootstrap_meta["claimset_ops_action"] = "manual_review_queued"
        bootstrap_meta["claimset_ops_alert"] = False
    else:
        bootstrap_meta["claimset_ops_action"] = "manual_review_required"
        bootstrap_meta["claimset_ops_alert"] = True
    bootstrap_meta["claimset_ops_note"] = followup


def mark_runtime_failure(bootstrap_meta: Dict[str, Any], exc: Exception) -> None:
    bootstrap_meta["claimset_readiness"] = "unknown"
    bootstrap_meta["claimset_ready"] = None
    bootstrap_meta["claimset_readiness_reason"] = "runtime_error"
    bootstrap_meta["claimset_readiness_badge"] = "UNKNOWN"
    bootstrap_meta["claimset_ops_action"] = "retry_suggested"
    bootstrap_meta["claimset_ops_alert"] = True
    bootstrap_meta["claimset_ops_note"] = f"runtime_error:{type(exc).__name__}"
