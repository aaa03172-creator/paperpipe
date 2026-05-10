from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from src.schemas.paper_notes import PaperNoteOperatorState, PaperNoteOperatorStateUpdateRequest
from src.services.event_log import sanitize_event_text_for_log
from src.skills.storage import atomic_write_text

_SAFE_KEY_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _operator_state_store_key(*, note_slug: str, paper_id: str | None) -> str:
    raw_key = str(paper_id or note_slug).strip() or str(note_slug).strip()
    safe_key = _SAFE_KEY_PATTERN.sub("-", raw_key).strip("-") or "paper-note"
    digest = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()[:10]
    return f"{safe_key[:80]}-{digest}"


def operator_state_relpath(note_slug: str, paper_id: str | None) -> str:
    return f".pp/operator_state/{_operator_state_store_key(note_slug=note_slug, paper_id=paper_id)}.json"


def operator_state_path(vault_path: Path, note_slug: str, paper_id: str | None) -> Path:
    return vault_path / operator_state_relpath(note_slug, paper_id)


def build_default_operator_state(*, note_slug: str, paper_id: str | None) -> PaperNoteOperatorState:
    normalized_slug = str(note_slug or "").strip()
    normalized_paper_id = str(paper_id or "").strip() or normalized_slug
    return PaperNoteOperatorState(
        note_slug=normalized_slug,
        paper_id=normalized_paper_id,
        paper_note_text=None,
        starred=False,
        triage_labels=[],
        created_at=None,
        updated_at=None,
    )


def _sanitize_operator_state_for_storage(state: PaperNoteOperatorState) -> PaperNoteOperatorState:
    sanitized_note = sanitize_event_text_for_log(state.paper_note_text)
    if sanitized_note == state.paper_note_text:
        return state
    return state.model_copy(update={"paper_note_text": sanitized_note})


def _load_operator_state_from_path(path: Path) -> PaperNoteOperatorState | None:
    if not path.exists():
        return None
    try:
        return _sanitize_operator_state_for_storage(
            PaperNoteOperatorState.model_validate(json.loads(path.read_text(encoding="utf-8")))
        )
    except Exception:
        return None


def load_operator_state(vault_path: Path, note_slug: str, paper_id: str | None) -> PaperNoteOperatorState | None:
    normalized_slug = str(note_slug or "").strip()
    normalized_paper_id = str(paper_id or "").strip() or None

    state = _load_operator_state_from_path(operator_state_path(vault_path, normalized_slug, normalized_paper_id))
    if state is None and normalized_paper_id:
        legacy_path = operator_state_path(vault_path, normalized_slug, None)
        state = _load_operator_state_from_path(legacy_path)
    if state is None:
        return None

    current_paper_id = normalized_paper_id or normalized_slug
    if state.note_slug == normalized_slug and state.paper_id == current_paper_id:
        return state
    return state.model_copy(
        update={
            "note_slug": normalized_slug,
            "paper_id": current_paper_id,
        }
    )


def save_operator_state(
    vault_path: Path,
    *,
    note_slug: str,
    paper_id: str | None,
    update: PaperNoteOperatorStateUpdateRequest,
) -> PaperNoteOperatorState:
    existing = load_operator_state(vault_path, note_slug, paper_id)
    now = datetime.now(tz=timezone.utc)
    state = PaperNoteOperatorState(
        note_slug=str(note_slug or "").strip(),
        paper_id=str(paper_id or "").strip() or str(note_slug or "").strip(),
        paper_note_text=sanitize_event_text_for_log(update.paper_note_text),
        starred=bool(update.starred),
        triage_labels=list(update.triage_labels),
        created_at=existing.created_at if existing and existing.created_at else now,
        updated_at=now,
    )
    state = _sanitize_operator_state_for_storage(state)
    path = operator_state_path(vault_path, state.note_slug, state.paper_id)
    atomic_write_text(path, state.model_dump_json(indent=2, exclude_none=True))
    return state
