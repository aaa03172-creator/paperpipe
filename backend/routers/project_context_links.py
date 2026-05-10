from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from src.project_memory.store import load_project_memory_workspace
from src.schemas.project_context_link import ProjectContextLinkDecision
from src.services.event_log import sanitize_event_payload_for_log, sanitize_event_text_for_log
from src.services.runtime_paths import project_context_link_log_path


logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/project-context-links", tags=["project-context-links"])

PROJECT_CONTEXT_LINK_FILE = None


def _project_context_link_file():
    return PROJECT_CONTEXT_LINK_FILE or project_context_link_log_path()


def _sanitize_project_context_link_decision(
    decision: ProjectContextLinkDecision,
) -> ProjectContextLinkDecision:
    updates = {}
    for field_name in (
        "decision_id",
        "project_id",
        "entity_id",
        "actor_id",
        "note",
        "timestamp",
    ):
        value = getattr(decision, field_name)
        sanitized = sanitize_event_text_for_log(value)
        if sanitized != value:
            updates[field_name] = sanitized

    sanitized_metadata = sanitize_event_payload_for_log(decision.metadata)
    if sanitized_metadata != decision.metadata:
        updates["metadata"] = sanitized_metadata

    if not updates:
        return decision
    return decision.model_copy(update=updates)


@router.post("")
async def submit_project_context_link(payload: ProjectContextLinkDecision):
    try:
        load_project_memory_workspace(payload.project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Project Memory workspace not found: {payload.project_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if not payload.timestamp:
            payload.timestamp = datetime.now(timezone.utc).isoformat()
        payload = _sanitize_project_context_link_decision(payload)

        log_file = _project_context_link_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(payload.model_dump_json() + "\n")

        logger.info(
            "Project context link decision saved for project_id=%s entity_type=%s entity_id=%s",
            payload.project_id,
            payload.entity_type,
            payload.entity_id,
        )
        return {"status": "saved", "message": "Project context link decision recorded successfully."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to save project context link decision: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[ProjectContextLinkDecision])
async def list_project_context_links(
    project_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    relationship_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    log_file = _project_context_link_file()
    if not log_file.exists():
        return []

    try:
        rows = [
            line.strip()
            for line in log_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        logger.error("Failed to read project context link log: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out: list[ProjectContextLinkDecision] = []
    for raw in reversed(rows):
        try:
            case = _sanitize_project_context_link_decision(
                ProjectContextLinkDecision.model_validate(json.loads(raw))
            )
        except Exception:
            continue

        if project_id and case.project_id != project_id:
            continue
        if entity_type and case.entity_type != entity_type:
            continue
        if entity_id and case.entity_id != entity_id:
            continue
        if relationship_type and case.relationship_type != relationship_type:
            continue
        if actor_id and case.actor_id != actor_id:
            continue

        out.append(case)
        if len(out) >= limit:
            break

    return out
