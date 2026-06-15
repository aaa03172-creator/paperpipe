from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import logging
from math import ceil
import os
from pathlib import Path
import json
import re
from tempfile import NamedTemporaryFile
from typing import Any, Literal
from urllib.parse import quote, unquote, urlparse

import anyio
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
import sqlite3
import yaml

from src.config import load_config
from src.db_utils import get_db_connection, save_paper_state
from src.schemas.paper_notes import (
    PaperNoteContextTrace,
    PaperNoteContextTraceEntry,
    PaperNoteContextTraceSummary,
    PaperNoteDetailResponse,
    PaperNotesHomeMarkerSummary,
    PaperNotesHomeContextResponse,
    PaperNoteImportResponse,
    PaperNoteIndexItem,
    PaperNoteListResponse,
    PaperNoteOperatorState,
    PaperNoteOperatorTriageLabel,
    PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER,
    PaperNoteOperatorStateUpdateRequest,
    PaperNoteOpsSummary,
    PaperNoteReadingAssist,
    PaperNoteReadingAssistBlock,
    PaperNoteReferenceLink,
    PaperNoteRelatedItem,
    PaperNoteSectionNavigatorItem,
    PaperNoteStructuredStateLookupResponse,
)
from src.skills.registry import list_available_actions
from src.schemas.skills import build_section_signal_summary
from src.skills.storage import atomic_write_text, load_structured_state
from src.services.fixture_visibility import (
    fixture_structured_state_allowed,
    is_test_fixture_paper_record,
    is_test_fixture_structured_state,
)
from src.services.identity import normalize_doi, paper_id_search_variants, paper_note_lookup_candidate_ids
from src.services.path_masking import is_path_masking_enabled
from src.services.paper_operator_state_store import (
    build_default_operator_state,
    load_operator_state,
    save_operator_state,
)
from src.services.paper_ops_summary import ArtifactSnapshotCache, build_ops_summary_for_candidate_ids
from src.services.runtime_paths import artifacts_root, storage_root
from src.services.event_log import sanitize_event_text_for_log

router = APIRouter(prefix="/paper-notes", tags=["paper-notes"])
logger = logging.getLogger(__name__)

_ALLOWED_REFERENCE_URL_SCHEMES = {"http", "https", "file", "zotero"}
_ALLOWED_REFERENCE_INTERNAL_PREFIXES = ("/papers/",)
_PAPER_PROCESSING_STATUSES = {
    "NEW",
    "FETCHED",
    "PDF_MISSING",
    "PENDING_REVIEW",
    "GATED",
    "APPROVED",
    "QUARANTINED",
    "INDEXED",
    "FAILED",
}

EXCLUDED_DIR_NAMES = {".obsidian", "_backup"}
DEFAULT_PAGE_SIZE = 30
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
QUERY_TERM_PATTERN = re.compile(r'"([^"]+)"|(\S+)')
SLUG_SANITIZE_PATTERN = re.compile(r"[^a-z0-9]+")
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
ONE_LINE_SUMMARY_PATTERN = re.compile(
    r"(?im)^>\s*\*\*(?:one-line summary|one-liner|tl;dr)\*\*\s*$\n(?P<body>(?:^>\s?.*(?:\n|$))+)"
)

READING_ASSIST_LABELS = {
    "one_line_summary": "One-Line Summary",
    "abstract": "Abstract",
    "critical_analysis": "Critical Analysis",
}

READING_ASSIST_HEADING_ALIASES = {
    "abstract": {"abstract"},
    "critical_analysis": {
        "critical analysis",
        "critical review",
        "critical review claimset",
    },
    "one_line_summary": {"one line summary", "one liner", "tldr"},
}

INDEX_CACHE_META_KEY = "_cache_meta"
INDEX_CACHE_RUNTIME_NOTE_METADATA_KEY = "_runtime_note_metadata"
INDEX_CACHE_FORMAT_VERSION = 3


def _index_cache_path() -> Path:
    return storage_root() / "obsidian" / "paper_notes_index.json"


def _path_signature_token(path: Path, *, relative_to: Path) -> str | None:
    try:
        stat = path.stat()
    except OSError:
        return None

    try:
        relative = path.relative_to(relative_to).as_posix()
    except ValueError:
        relative = str(path)
    kind = "d" if path.is_dir() else "f"
    size = 0 if kind == "d" else stat.st_size
    return f"{kind}:{relative}:{stat.st_mtime_ns}:{size}"


def _hash_path_signatures(paths: list[Path], *, relative_to: Path) -> str:
    tokens: list[str] = []
    for path in paths:
        token = _path_signature_token(path, relative_to=relative_to)
        if token:
            tokens.append(token)

    digest = hashlib.sha1()
    for token in sorted(tokens):
        digest.update(token.encode("utf-8"))
        digest.update(b"\n")
    return f"{len(tokens)}:{digest.hexdigest()}"


def _candidate_markdown_paths_for_index_signature(vault_path: Path) -> list[Path]:
    return [
        path
        for path in vault_path.rglob("*.md")
        if path.is_file() and _is_candidate_markdown(path, vault_path)
    ]


def _pp_json_paths_for_index_signature(vault_path: Path) -> list[Path]:
    pp_root = vault_path / ".pp"
    if not pp_root.exists() or not pp_root.is_dir():
        return []
    return [path for path in pp_root.rglob("*.json") if path.is_file()]


def _artifact_paths_for_index_signature(artifacts_path: Path) -> list[Path]:
    if not artifacts_path.exists() or not artifacts_path.is_dir():
        return []

    paths: list[Path] = []
    for paper_dir in artifacts_path.iterdir():
        if not paper_dir.is_dir():
            continue
        for run_dir in paper_dir.iterdir():
            if not run_dir.is_dir():
                continue
            paths.append(run_dir)
            for filename in ("claimset.resolved.json", "claimset.json", "stats_report.json"):
                candidate = run_dir / filename
                if candidate.exists() and candidate.is_file():
                    paths.append(candidate)
    return paths


def _build_index_cache_meta(vault_path: Path, *, artifacts_path: Path) -> dict[str, Any]:
    return {
        "format_version": INDEX_CACHE_FORMAT_VERSION,
        "vault_root": str(vault_path.resolve()),
        "artifacts_root": str(artifacts_path.resolve()),
        "markdown_signature": _hash_path_signatures(
            _candidate_markdown_paths_for_index_signature(vault_path),
            relative_to=vault_path,
        ),
        "pp_json_signature": _hash_path_signatures(
            _pp_json_paths_for_index_signature(vault_path),
            relative_to=vault_path,
        ),
        "artifact_signature": _hash_path_signatures(
            _artifact_paths_for_index_signature(artifacts_path),
            relative_to=artifacts_path,
        ),
    }


def _load_index_from_cache(cache_meta: dict[str, Any]) -> PaperNoteListResponse | None:
    cache_path = _index_cache_path()
    if not cache_path.exists():
        return None

    try:
        raw_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw_payload, dict):
        return None

    stored_meta = raw_payload.get(INDEX_CACHE_META_KEY)
    if not isinstance(stored_meta, dict) or stored_meta != cache_meta:
        return None

    runtime_note_metadata = raw_payload.get(INDEX_CACHE_RUNTIME_NOTE_METADATA_KEY)
    payload = dict(raw_payload)
    payload.pop(INDEX_CACHE_META_KEY, None)
    payload.pop(INDEX_CACHE_RUNTIME_NOTE_METADATA_KEY, None)
    try:
        index = PaperNoteListResponse.model_validate(payload)
    except Exception:
        return None
    if isinstance(runtime_note_metadata, dict):
        items_by_slug = {item.slug: item for item in index.items}
        for slug, metadata in runtime_note_metadata.items():
            item = items_by_slug.get(str(slug or "").strip())
            if item is None:
                continue
            item.load_runtime_source_metadata(metadata if isinstance(metadata, dict) else None)
    return index


def _resolve_import_pdf_max_bytes() -> int:
    raw = (
        os.getenv("LATTICE_MAX_IMPORT_PDF_BYTES")
        or os.getenv("PAPERPIPE_MAX_IMPORT_PDF_BYTES")
        or ""
    ).strip()
    if not raw:
        return 25 * 1024 * 1024
    try:
        return max(int(raw), 1)
    except ValueError:
        return 25 * 1024 * 1024


async def _read_upload_with_size_limit(file: UploadFile, *, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"PDF import exceeds the configured limit of {max_bytes} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", dir=str(path.parent), delete=False) as handle:
        handle.write(content)
        handle.flush()
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _paper_state_persisted(paper_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM papers WHERE paper_id = ? LIMIT 1", (paper_id,))
        return cursor.fetchone() is not None
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def _delete_imported_paper_state(paper_id: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
        conn.commit()
    except sqlite3.OperationalError:
        conn.rollback()
    finally:
        conn.close()


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        return {}, content

    yaml_block = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    try:
        parsed = yaml.safe_load(yaml_block) or {}
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}
    return parsed, body


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    text = str(value).strip()
    return [text] if text else []


def _load_visible_structured_state(
    vault_path: Path,
    slug: str,
    frontmatter: dict[str, Any] | None,
):
    state = load_structured_state(vault_path, slug, frontmatter)
    if state is None:
        return None
    if is_test_fixture_structured_state(state) and not fixture_structured_state_allowed(vault_path):
        return None
    return state


def _resolve_lookup_frontmatter(vault_path: Path, target: PaperNoteIndexItem) -> tuple[Path, dict[str, Any]]:
    note_path = vault_path / target.note_path
    if not note_path.exists():
        raise HTTPException(status_code=404, detail=f"Note file not found: {target.note_path}")

    if target.has_runtime_source_metadata():
        frontmatter = target.build_runtime_source_frontmatter()
        pp = frontmatter.get("pp")
        if (
            not target.structured_state_present
            or (isinstance(pp, dict) and str(pp.get("structured_path") or "").strip())
        ):
            return note_path, frontmatter

    content = _safe_read_text(note_path)
    frontmatter, _ = _parse_frontmatter(content)
    return note_path, frontmatter


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _to_date_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text if text else None


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            if title:
                return title
    return fallback


def _slugify_heading(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return ""
    text = re.sub(r"[`*_~\[\]().,:;!?/\\]+", " ", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    return text


def _extract_outline_items(markdown: str, *, note_title: str | None) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    normalized_note_title = (note_title or "").strip()
    for raw_line in markdown.splitlines():
        match = re.match(r"^(#{1,3})\s+(.+?)\s*$", raw_line.strip())
        if not match:
            continue
        level = len(match.group(1))
        label = match.group(2).strip()
        if not label:
            continue
        if level == 1 and normalized_note_title and label == normalized_note_title:
            continue
        base_id = _slugify_heading(label)
        if not base_id:
            continue
        count = seen.get(base_id, 0) + 1
        seen[base_id] = count
        items.append(
            {
                "id": base_id if count == 1 else f"{base_id}-{count}",
                "label": label,
                "level": level,
                "order": len(items),
            }
        )
    return items


def _normalize_section_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _slugify_heading(text) or text.lower()


def _coerce_section_signal_summary(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    def _safe_int(candidate: Any) -> int:
        try:
            return max(int(candidate), 0)
        except Exception:
            return 0

    items: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()
        key = _normalize_section_key(raw.get("key") or label)
        if not key or not label:
            continue
        items.append(
            {
                "key": key,
                "label": label,
                "claim_count": _safe_int(raw.get("claim_count")),
                "evidence_count": _safe_int(raw.get("evidence_count")),
                "representative_claim_id": str(raw.get("representative_claim_id") or "").strip() or None,
                "representative_evidence_id": str(raw.get("representative_evidence_id") or "").strip() or None,
                "page_start": raw.get("page_start") if isinstance(raw.get("page_start"), int) else None,
                "page_end": raw.get("page_end") if isinstance(raw.get("page_end"), int) else None,
            }
        )
    return items


def _section_summary_from_structured_state(structured_state: Any) -> list[dict[str, Any]]:
    runs = list(getattr(structured_state, "runs", []) or [])
    if runs:
        latest_data = getattr(runs[0], "data", None)
        if isinstance(latest_data, dict):
            summary = _coerce_section_signal_summary(latest_data.get("section_summary"))
            if summary:
                return summary
    return build_section_signal_summary(list(getattr(structured_state, "claimset", []) or []))


def _build_section_navigator(
    *,
    markdown: str,
    note_title: str | None,
    structured_state: Any,
) -> list[PaperNoteSectionNavigatorItem]:
    if structured_state is None:
        return []

    outline_items = _extract_outline_items(markdown, note_title=note_title)
    outline_by_key: dict[str, dict[str, Any]] = {}
    for item in outline_items:
        key = _normalize_section_key(item["label"])
        if key and key not in outline_by_key:
            outline_by_key[key] = item

    items: list[PaperNoteSectionNavigatorItem] = []
    for entry in _section_summary_from_structured_state(structured_state):
        outline_match = outline_by_key.get(entry["key"])
        items.append(
            PaperNoteSectionNavigatorItem(
                key=entry["key"],
                label=outline_match["label"] if outline_match else entry["label"],
                outline_id=outline_match["id"] if outline_match else None,
                outline_order=outline_match["order"] if outline_match else None,
                claim_count=entry["claim_count"],
                evidence_count=entry["evidence_count"],
                representative_claim_id=entry["representative_claim_id"],
                representative_evidence_id=entry["representative_evidence_id"],
                page_start=entry["page_start"],
                page_end=entry["page_end"],
                matched_to_outline=bool(outline_match),
            )
        )

    return sorted(
        items,
        key=lambda item: (
            0 if item.matched_to_outline else 1,
            item.outline_order if item.outline_order is not None else 10_000,
            -item.evidence_count,
            -item.claim_count,
            item.label.lower(),
        ),
    )


def _normalize_status(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_candidate_markdown(path: Path, vault_path: Path) -> bool:
    try:
        relative = path.relative_to(vault_path)
    except ValueError:
        return False

    for part in relative.parts:
        if part in EXCLUDED_DIR_NAMES:
            return False
        if part.startswith("."):
            return False
    return True


def _is_paper_note(frontmatter: dict[str, Any], relative_path: Path) -> bool:
    if any(
        key in frontmatter
        for key in (
            "id",
            "aliases",
            "tags",
            "date_processed",
            "confidence",
            "status",
        )
    ):
        return True

    rel = str(relative_path).lower()
    if "paperpipe" in rel:
        return True
    return False


def _pick_zotero_link(frontmatter: dict[str, Any]) -> str | None:
    for key in ("zotero_link", "zotero_url", "zotero_uri"):
        value = frontmatter.get(key)
        if value:
            text = str(value).strip()
            if text:
                return text
    url = frontmatter.get("url")
    if url:
        text = str(url).strip()
        if "zotero" in text.lower():
            return text
    return None


def _normalize_doi(doi_value: Any) -> str | None:
    if doi_value is None:
        return None
    text = str(doi_value).strip()
    if not text:
        return None
    if text.lower().startswith("http://") or text.lower().startswith("https://"):
        return text
    return f"https://doi.org/{text}"


def _artifact_paper_id_candidates(note_path: Path, frontmatter: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    raw_values = [frontmatter.get("id"), note_path.stem]
    for raw in raw_values:
        text = str(raw).strip() if raw is not None else ""
        if not text:
            continue
        if text not in candidates:
            candidates.append(text)
        if text.startswith("zotero:"):
            stripped = text.split(":", 1)[1].strip()
            if stripped and stripped not in candidates:
                candidates.append(stripped)
    return candidates


def _build_ops_summary(
    note_path: Path,
    frontmatter: dict[str, Any],
    *,
    artifacts_path: Path,
    artifact_cache: ArtifactSnapshotCache,
) -> PaperNoteOpsSummary | None:
    return build_ops_summary_for_candidate_ids(
        artifacts_path,
        _artifact_paper_id_candidates(note_path, frontmatter),
        artifact_cache,
    )


def _build_index_item(
    vault_path: Path,
    note_path: Path,
    *,
    artifacts_path: Path,
    artifact_cache: ArtifactSnapshotCache,
) -> PaperNoteIndexItem | None:
    content = _safe_read_text(note_path)
    frontmatter, body = _parse_frontmatter(content)
    relative_path = note_path.relative_to(vault_path)
    if not _is_paper_note(frontmatter, relative_path):
        return None

    _sync_note_frontmatter_to_paper_state(vault_path, note_path, frontmatter)

    aliases = _to_str_list(frontmatter.get("aliases"))
    title = aliases[0] if aliases else _extract_title(body, note_path.stem)
    tags = _to_str_list(frontmatter.get("tags"))
    paper_id = (str(frontmatter.get("id")).strip() if frontmatter.get("id") is not None else note_path.stem)
    operator_state = load_operator_state(vault_path, note_path.stem, paper_id)
    structured_state = _load_visible_structured_state(vault_path, note_path.stem, frontmatter)
    claim_tags = sorted(
        {
            tag
            for claim in (structured_state.claimset if structured_state else [])
            for tag in claim.tags
            if str(tag).strip()
        },
        key=lambda value: value.lower(),
    )
    entities = list(structured_state.entities) if structured_state else []
    mesh = list(structured_state.mesh) if structured_state else []
    outcomes = list(structured_state.outcomes) if structured_state else []
    pp = frontmatter.get("pp")
    pp_signals = dict(pp.get("signals")) if isinstance(pp, dict) and isinstance(pp.get("signals"), dict) else {}
    if structured_state is not None:
        for key, value in structured_state.signals.items():
            if value is None:
                continue
            pp_signals[key] = value
    reading_assist_locales = _reading_assist_locales_from_signals(pp_signals)
    reading_assist_available = bool(reading_assist_locales) or pp_signals.get("has_reading_assists") is True
    ops_summary = _build_ops_summary(
        note_path,
        frontmatter,
        artifacts_path=artifacts_path,
        artifact_cache=artifact_cache,
    )

    updated_at = datetime.fromtimestamp(note_path.stat().st_mtime, tz=timezone.utc).isoformat()
    item = PaperNoteIndexItem(
        slug=note_path.stem,
        title=title,
        note_path=relative_path.as_posix(),
        structured_state_present=structured_state is not None,
        reading_assist_available=reading_assist_available,
        reading_assist_locales=reading_assist_locales,
        id=(str(frontmatter.get("id")).strip() if frontmatter.get("id") is not None else None),
        aliases=aliases,
        tags=tags,
        date_processed=_to_date_string(frontmatter.get("date_processed")),
        confidence=_to_float(frontmatter.get("confidence")),
        status=_normalize_status(frontmatter.get("status")),
        doi=_normalize_doi(frontmatter.get("doi")),
        zotero_link=_pick_zotero_link(frontmatter),
        updated_at=updated_at,
        pp_signals=_jsonable(pp_signals),
        claim_tags=claim_tags,
        entities=entities,
        mesh=mesh,
        outcomes=outcomes,
        ops_summary=ops_summary,
        starred=operator_state.starred if operator_state else False,
        has_operator_note=bool(operator_state and operator_state.paper_note_text),
        triage_labels=list(operator_state.triage_labels) if operator_state else [],
    )
    item.set_runtime_source_metadata(
        source_url=frontmatter.get("url"),
        pdf_url=frontmatter.get("pdf_url"),
        pdf_path=frontmatter.get("pdf_path"),
        local_pdf_path=frontmatter.get("local_pdf_path"),
        structured_path=pp.get("structured_path") if isinstance(pp, dict) else None,
    )
    return item


def _reading_assist_locales_from_signals(signals: dict[str, Any]) -> list[str]:
    raw_locales = signals.get("reading_assist_locales")
    if not isinstance(raw_locales, list):
        return []
    normalized: list[str] = []
    for value in raw_locales:
        locale = str(value or "").strip().lower()
        if locale and locale not in normalized:
            normalized.append(locale)
    return normalized


def _resolve_vault_path() -> Path:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Obsidian vault path is not a directory: {vault_path}")
    return vault_path


def _slugify_import_title(title: str) -> str:
    normalized = SLUG_SANITIZE_PATTERN.sub("-", str(title or "").strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized[:80] or "imported-paper"


def _display_import_filename(filename: str) -> str:
    return str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()


def _sanitize_import_title(title: str, *, fallback: str = "Imported PDF") -> str:
    sanitized = sanitize_event_text_for_log(title)
    normalized = " ".join(str(sanitized or "").split()).strip()
    return normalized[:220] or fallback


def _extract_import_title(pdf_path: Path, *, fallback_name: str) -> str:
    fallback = _sanitize_import_title(str(fallback_name or "").strip(), fallback="Imported PDF")
    fallback = re.sub(r"[_-]+", " ", fallback).strip() or "Imported PDF"
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        raw_title = str((reader.metadata or {}).get("/Title") or "").strip()
        if raw_title:
            return _sanitize_import_title(raw_title, fallback=fallback[:220])
    except Exception:
        pass
    return _sanitize_import_title(fallback, fallback="Imported PDF")


def _normalize_import_doi(raw: str) -> str | None:
    doi = str(raw or "").strip()
    if doi.lower().startswith("doi:"):
        doi = doi[4:].strip()
    doi = doi.rstrip(".,;:)]]}").strip()
    if DOI_PATTERN.fullmatch(doi):
        return doi
    return None


def _normalize_frontmatter_doi_for_db(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = normalize_doi(text)
    return _normalize_import_doi(normalized) or (normalized if normalized else None)


def _frontmatter_paper_id(note_path: Path, frontmatter: dict[str, Any]) -> str | None:
    explicit_id = str(frontmatter.get("id") or "").strip()
    if explicit_id:
        return explicit_id
    stem = note_path.stem.strip()
    return stem or None


def _frontmatter_reading_status(frontmatter: dict[str, Any]) -> str | None:
    explicit = str(frontmatter.get("reading_status") or "").strip()
    if explicit:
        return explicit
    raw_status = str(frontmatter.get("status") or "").strip()
    if raw_status and _normalize_status(raw_status) not in _PAPER_PROCESSING_STATUSES:
        return raw_status
    return None


def _sync_note_frontmatter_to_paper_state(
    vault_path: Path,
    note_path: Path,
    frontmatter: dict[str, Any],
) -> bool:
    paper_id = _frontmatter_paper_id(note_path, frontmatter)
    if not paper_id:
        return False

    try:
        relative_note_path = note_path.relative_to(vault_path).as_posix()
    except ValueError:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(papers)")
        columns = {str(row[1]) for row in cursor.fetchall()}
        if "paper_id" not in columns:
            return False

        cursor.execute("SELECT * FROM papers WHERE paper_id = ? LIMIT 1", (paper_id,))
        row = cursor.fetchone()
        if row is None:
            return False

        assignments: list[str] = []
        params: list[Any] = []

        def _queue_update(column: str, value: str | None) -> None:
            if column not in columns or value is None:
                return
            current = row[column]
            if str(current or "") == value:
                return
            assignments.append(f"{column} = ?")
            params.append(value)

        normalized_status = _normalize_status(frontmatter.get("status"))
        if normalized_status in _PAPER_PROCESSING_STATUSES:
            _queue_update("status", normalized_status)
        _queue_update("reading_status", _frontmatter_reading_status(frontmatter))
        _queue_update("doi", _normalize_frontmatter_doi_for_db(frontmatter.get("doi")))
        _queue_update("obsidian_path", relative_note_path)

        if not assignments:
            return False
        if "updated_at" in columns:
            assignments.append("updated_at = ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        params.append(paper_id)
        cursor.execute(f"UPDATE papers SET {', '.join(assignments)} WHERE paper_id = ?", tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.OperationalError as exc:
        logger.debug("Skipping paper note frontmatter DB sync for %s: %s", paper_id, exc)
        return False
    finally:
        conn.close()


def _extract_import_doi_from_text(text: str) -> str | None:
    for match in DOI_PATTERN.finditer(str(text or "")):
        doi = _normalize_import_doi(match.group(0))
        if doi:
            return doi
    return None


def _select_import_doi_candidate(candidates: list[tuple[str, str]]) -> str | None:
    scores: dict[str, int] = {}
    order: dict[str, int] = {}
    for idx, (doi, context) in enumerate(candidates):
        if not doi:
            continue
        order.setdefault(doi, idx)
        scores[doi] = scores.get(doi, 0) + 100
        normalized_context = str(context or "").lower()
        if "doi.org/" in normalized_context or "science.org/doi/" in normalized_context:
            scores[doi] += 25
        if "/doi/" in normalized_context:
            scores[doi] += 10
    if not scores:
        return None
    return sorted(scores, key=lambda doi: (-scores[doi], order[doi], doi))[0]


def _extract_import_doi(pdf_path: Path, *, max_pages: int = 16) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        metadata = reader.metadata or {}
        for key in ("/doi", "/DOI", "doi", "DOI"):
            doi = _normalize_import_doi(str(metadata.get(key) or ""))
            if doi:
                return doi

        candidates: list[tuple[str, str]] = []
        for page in list(reader.pages)[:max(1, int(max_pages))]:
            text = page.extract_text() or ""
            for match in DOI_PATTERN.finditer(text):
                doi = _normalize_import_doi(match.group(0))
                if not doi:
                    continue
                start = max(0, match.start() - 80)
                end = min(len(text), match.end() + 80)
                candidates.append((doi, text[start:end]))
        return _select_import_doi_candidate(candidates)
    except Exception:
        pass
    return None


def _paper_notes_home_dir(vault_path: Path) -> Path:
    return vault_path / "Inbox" / "PaperPipe"


def _build_imported_note_markdown(
    *,
    paper_id: str,
    title: str,
    pdf_url: str,
    imported_at: str,
    doi: str | None = None,
) -> str:
    aliases = list(dict.fromkeys([title, paper_id]))
    frontmatter = {
        "id": paper_id,
        "aliases": aliases,
        "tags": ["PaperPipe/Imported"],
        "date_processed": imported_at,
        "status": "NEW",
        "pdf_url": pdf_url,
        "pp": {
            "signals": {
                "import_mode": "manual_pdf",
            }
        },
    }
    if doi:
        frontmatter["doi"] = doi
    frontmatter_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    references = [f"* [Open PDF]({pdf_url})"]
    if doi:
        references.append(f"* DOI: {doi}")
    body = "\n".join(
        [
            f"# {title}",
            "",
            "> Imported from a local PDF on this machine.",
            "",
            "## What To Do Next",
            "- Open PDF to check the original file.",
            "- Open in Workbench when you want extracted claims and checks.",
            "",
            "## References",
            *references,
            "",
        ]
    )
    return f"---\n{frontmatter_text}\n---\n\n{body}"


def _upsert_imported_note_doi(note_path: Path, *, paper_id: str, doi: str | None) -> bool:
    doi = _normalize_import_doi(doi or "")
    if not doi or not note_path.exists():
        return False

    content = _safe_read_text(note_path)
    frontmatter, body = _parse_frontmatter(content)
    if str(frontmatter.get("id") or "").strip() != paper_id:
        return False
    if str(frontmatter.get("doi") or "").strip() == doi and f"DOI: {doi}" in body:
        return False

    frontmatter["doi"] = doi
    if f"DOI: {doi}" not in body:
        if "## References" in body:
            body = body.replace("## References", f"## References\n* DOI: {doi}", 1)
        else:
            body = f"{body.rstrip()}\n\n## References\n* DOI: {doi}\n"

    frontmatter_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    atomic_write_text(note_path, f"---\n{frontmatter_text}\n---\n\n{body.lstrip()}")
    return True


def _find_imported_paper_id_by_doi(doi: str | None) -> str | None:
    doi = _normalize_import_doi(doi or "")
    if not doi:
        return None
    normalized_doi = normalize_doi(doi)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(papers)")
        columns = {str(row[1]) for row in cursor.fetchall()}
        if "paper_id" not in columns or "doi" not in columns:
            return None
        cursor.execute(
            "SELECT paper_id FROM papers WHERE doi = ? LIMIT 1",
            (normalized_doi,),
        )
        exact = cursor.fetchone()
        if exact:
            return str(exact["paper_id"] or "").strip() or None
        cursor.execute("SELECT paper_id, doi FROM papers WHERE doi IS NOT NULL")
        for row in cursor.fetchall():
            if normalize_doi(str(row["doi"] or "")) == normalized_doi:
                return str(row["paper_id"] or "").strip() or None
        return None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _persist_imported_note_path(paper_id: str, note_path: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(papers)")
        columns = {str(row[1]) for row in cursor.fetchall()}
        assignments: list[str] = []
        params: list[Any] = []
        if "obsidian_path" in columns:
            assignments.append("obsidian_path = ?")
            params.append(note_path)
        if "updated_at" in columns:
            assignments.append("updated_at = ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if not assignments:
            return
        params.append(paper_id)
        cursor.execute(f"UPDATE papers SET {', '.join(assignments)} WHERE paper_id = ?", tuple(params))
        conn.commit()
    except sqlite3.OperationalError:
        return
    finally:
        conn.close()


def import_pdf_payload(*, filename: str, payload: bytes) -> PaperNoteImportResponse:
    filename = _display_import_filename(filename)
    if not filename:
        raise HTTPException(status_code=400, detail="Choose a PDF file to import.")
    if not payload:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Paper Notes import currently supports PDF files only.")

    vault_path = _resolve_vault_path()
    config = load_config()
    pdf_storage_dir = Path(config.paths.pdf_storage_dir).expanduser()
    pdf_storage_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha1(payload).hexdigest()
    content_paper_id = f"userpdf-{digest[:16]}"
    pdf_path = pdf_storage_dir / f"{content_paper_id}.pdf"
    imported_at = datetime.now(tz=timezone.utc).date().isoformat()
    note_dir = _paper_notes_home_dir(vault_path)
    note_dir.mkdir(parents=True, exist_ok=True)

    created_pdf = False
    created_note = False
    should_upsert_existing_note_doi = False
    paper_id = content_paper_id
    note_path: Path | None = None
    paper_state_existed_before_import = False
    try:
        if not pdf_path.exists():
            _atomic_write_bytes(pdf_path, payload)
            created_pdf = True

        title = _extract_import_title(pdf_path, fallback_name=Path(filename).stem)
        doi = _extract_import_doi(pdf_path)
        existing_paper_id = _find_imported_paper_id_by_doi(doi)
        if existing_paper_id and existing_paper_id != paper_id:
            paper_id = existing_paper_id
        pdf_url = f"/papers/{quote(paper_id, safe='')}/pdf"
        paper_state_existed_before_import = _paper_state_persisted(paper_id)
        slug = f"{_slugify_import_title(title)}-{digest[:8]}"
        note_path = note_dir / f"{slug}.md"
        note_relative_path = note_path.relative_to(vault_path).as_posix()

        should_write_note = True
        if note_path.exists():
            existing_frontmatter, _ = _parse_frontmatter(_safe_read_text(note_path))
            existing_id = str(existing_frontmatter.get("id") or "").strip()
            if existing_id == paper_id:
                should_write_note = False
                should_upsert_existing_note_doi = True
            else:
                raise HTTPException(
                    status_code=409,
                    detail="An existing note already occupies this import path.",
                )

        if should_write_note:
            atomic_write_text(
                note_path,
                _build_imported_note_markdown(
                    paper_id=paper_id,
                    title=title,
                    pdf_url=pdf_url,
                    imported_at=imported_at,
                    doi=doi,
                ),
            )
            created_note = True

        save_paper_state(
            paper_id,
            title,
            "user_imported_pdf",
            imported_at,
            doi=doi,
            local_pdf_path=pdf_path,
            status="NEW",
            issues_state="unavailable",
        )
        if not _paper_state_persisted(paper_id):
            raise RuntimeError(f"Imported paper state was not persisted for paper_id={paper_id}")
        _persist_imported_note_path(paper_id, note_relative_path)
        if should_upsert_existing_note_doi:
            _upsert_imported_note_doi(note_path, paper_id=paper_id, doi=doi)
    except Exception as exc:
        if created_note and note_path is not None:
            note_path.unlink(missing_ok=True)
        if created_pdf:
            pdf_path.unlink(missing_ok=True)
        if not paper_state_existed_before_import and _paper_state_persisted(paper_id):
            _delete_imported_paper_state(paper_id)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Failed to persist imported paper state.") from exc

    return PaperNoteImportResponse(
        paper_id=paper_id,
        slug=slug,
        title=title,
        note_path=note_relative_path,
        pdf_url=pdf_url,
        doi=doi,
    )


def _parse_date_for_sort(value: str | None) -> tuple[int, str]:
    if not value:
        return (0, "")
    raw = value.strip()
    if not raw:
        return (0, "")
    try:
        return (1, datetime.fromisoformat(raw).date().isoformat())
    except Exception:
        return (1, raw)


def _parse_datetime_for_sort(value: str | None) -> tuple[int, str]:
    if not value:
        return (0, "")
    raw = value.strip()
    if not raw:
        return (0, "")
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return (1, parsed.astimezone(timezone.utc).isoformat())
    except Exception:
        return (1, raw)


def _claim_count_for_sort(item: PaperNoteIndexItem) -> int:
    signals = item.pp_signals if isinstance(item.pp_signals, dict) else {}
    value = signals.get("claim_count")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def _default_discoverability_sort_key(item: PaperNoteIndexItem) -> tuple[Any, ...]:
    return (
        1 if item.structured_state_present else 0,
        _claim_count_for_sort(item),
        _parse_datetime_for_sort(item.updated_at),
        _parse_date_for_sort(item.date_processed),
        item.confidence if item.confidence is not None else -1.0,
        item.title.lower(),
    )


def _index_sort_key(item: PaperNoteIndexItem) -> tuple[Any, ...]:
    return _default_discoverability_sort_key(item)


def _build_index(vault_path: Path) -> PaperNoteListResponse:
    artifacts_path = artifacts_root()
    cache_meta = _build_index_cache_meta(vault_path, artifacts_path=artifacts_path)
    if cached := _load_index_from_cache(cache_meta):
        return cached

    items: list[PaperNoteIndexItem] = []
    seen_slugs: set[str] = set()
    artifact_cache: ArtifactSnapshotCache = {}

    for note_path in vault_path.rglob("*.md"):
        if not _is_candidate_markdown(note_path, vault_path):
            continue
        parsed = _build_index_item(
            vault_path,
            note_path,
            artifacts_path=artifacts_path,
            artifact_cache=artifact_cache,
        )
        if not parsed:
            continue
        if parsed.slug in seen_slugs:
            # Prefer first hit for deterministic routing when duplicate stems exist.
            continue
        seen_slugs.add(parsed.slug)
        items.append(parsed)

    items = sorted(items, key=_index_sort_key, reverse=True)

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    available_tags = sorted({tag for item in items for tag in item.tags}, key=lambda value: value.lower())
    available_statuses = sorted(
        {(item.status or "").strip() for item in items if (item.status or "").strip()},
        key=lambda value: value.lower(),
    )
    payload = PaperNoteListResponse(
        generated_at=generated_at,
        index_path=str(_index_cache_path()),
        total=len(items),
        page=1,
        page_size=DEFAULT_PAGE_SIZE,
        total_pages=max(1, ceil(len(items) / DEFAULT_PAGE_SIZE)),
        available_tags=available_tags,
        available_statuses=available_statuses,
        items=items,
    )

    index_cache_path = _index_cache_path()
    index_cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = payload.model_dump()
    cache_payload[INDEX_CACHE_META_KEY] = cache_meta
    cache_payload[INDEX_CACHE_RUNTIME_NOTE_METADATA_KEY] = {
        item.slug: item.export_runtime_source_metadata()
        for item in items
    }
    atomic_write_text(
        index_cache_path,
        json.dumps(cache_payload, ensure_ascii=False, indent=2),
    )
    return payload


def _build_empty_index_response(*, page_size: int = DEFAULT_PAGE_SIZE) -> PaperNoteListResponse:
    return PaperNoteListResponse(
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
        index_path=str(_index_cache_path()),
        total=0,
        page=1,
        page_size=page_size,
        total_pages=1,
        available_tags=[],
        available_statuses=[],
        available_reading_assist_note_count=0,
        available_reading_assist_locales=[],
        items=[],
    )


def _build_home_context(index: PaperNoteListResponse) -> PaperNotesHomeContextResponse:
    visible_items = _dedupe_equivalent_note_items(index.items)
    note_slug_by_paper_id: dict[str, str] = {}
    triage_counts: dict[str, int] = {"revisit": 0, "needs_verification": 0, "experiment_relevant": 0}
    marked_papers = 0
    note_backed_papers = 0
    starred = 0
    for item in visible_items:
        raw_variants, _ = _paper_note_identity_sets(item)
        for variant in raw_variants:
            note_slug_by_paper_id.setdefault(variant, item.slug)
        note_starred = item.starred is True
        has_operator_note = item.has_operator_note is True
        triage_labels = list(item.triage_labels or [])
        if note_starred:
            starred += 1
        if has_operator_note:
            note_backed_papers += 1
        if note_starred or has_operator_note or triage_labels:
            marked_papers += 1
        for label in triage_labels:
            if label in triage_counts:
                triage_counts[label] += 1

    latest_note_updated_at = max(
        (item.updated_at for item in visible_items if item.updated_at),
        key=_parse_datetime_for_sort,
        default=None,
    )

    return PaperNotesHomeContextResponse(
        saved_notes=len(visible_items),
        structured_notes=sum(1 for item in visible_items if item.structured_state_present),
        latest_note_updated_at=latest_note_updated_at,
        note_context_limited=False,
        note_slug_by_paper_id=note_slug_by_paper_id,
        marker_summary=PaperNotesHomeMarkerSummary(
            marked_papers=marked_papers,
            note_backed_papers=note_backed_papers,
            starred=starred,
            triage_counts=triage_counts,
        ),
    )


def _normalize_heading_text(text: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(normalized.lower().split())


def _strip_sections_and_capture_references(markdown: str) -> tuple[str, str, list[str]]:
    lines = markdown.splitlines()
    output: list[str] = []
    references: list[str] = []
    filtered_sections: list[str] = []
    skip_mode: Literal["related", "references"] | None = None
    skip_level = 0

    for line in lines:
        heading_match = HEADING_PATTERN.match(line.strip())
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = _normalize_heading_text(heading_match.group(2))

            if skip_mode is not None and level <= skip_level:
                skip_mode = None
                skip_level = 0

            if skip_mode is None and "related papers" in heading_text:
                skip_mode = "related"
                skip_level = level
                if "related" not in filtered_sections:
                    filtered_sections.append("related")
                continue
            if skip_mode is None and "references" in heading_text:
                skip_mode = "references"
                skip_level = level
                if "references" not in filtered_sections:
                    filtered_sections.append("references")
                references.append(line)
                continue

        if skip_mode == "references":
            references.append(line)
            continue
        if skip_mode == "related":
            continue
        output.append(line)

    body = "\n".join(output).strip() + "\n"
    reference_block = "\n".join(references).strip()
    return body, reference_block, filtered_sections


def _convert_wikilinks(markdown: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        target_raw = match.group(1).strip()
        label_raw = (match.group(2) or "").strip()
        if not target_raw:
            return match.group(0)

        target_name = Path(target_raw).name
        if target_name.lower().endswith(".md"):
            target_name = target_name[:-3]
        if not target_name:
            return match.group(0)

        label = label_raw or target_name
        href = f"/papers/{quote(target_name)}"
        return f"[{label}]({href})"

    return WIKILINK_PATTERN.sub(_replace, markdown)


def _normalize_heading_text(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[*_`~#>\[\](){}:;,.!?/\\\-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return " ".join(text.split())


def _trim_display_excerpt(value: str | None, *, max_chars: int = 1200) -> str | None:
    if value is None:
        return None

    lines = [line.rstrip() for line in value.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    text = "\n".join(lines).strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _extract_heading_section(markdown: str, aliases: set[str], *, max_chars: int = 1200) -> str | None:
    lines = markdown.splitlines()
    start_index: int | None = None
    start_level = 0

    for index, line in enumerate(lines):
        match = HEADING_PATTERN.match(line.strip())
        if not match:
            continue
        heading = _normalize_heading_text(match.group(2))
        if heading in aliases:
            start_index = index + 1
            start_level = len(match.group(1))
            break

    if start_index is None:
        return None

    output: list[str] = []
    for line in lines[start_index:]:
        match = HEADING_PATTERN.match(line.strip())
        if match and len(match.group(1)) <= start_level:
            break
        output.append(line)

    return _trim_display_excerpt("\n".join(output), max_chars=max_chars)


def _extract_one_line_summary(markdown: str) -> str | None:
    match = ONE_LINE_SUMMARY_PATTERN.search(markdown)
    if match:
        body_lines = []
        for line in match.group("body").splitlines():
            cleaned = re.sub(r"^>\s?", "", line).strip()
            if cleaned:
                body_lines.append(cleaned)
        return _trim_display_excerpt("\n".join(body_lines), max_chars=400)

    return _extract_heading_section(
        markdown,
        READING_ASSIST_HEADING_ALIASES["one_line_summary"],
        max_chars=400,
    )


def _extract_canonical_summary_blocks(markdown: str) -> dict[str, str | None]:
    return {
        "one_line_summary": _extract_one_line_summary(markdown),
        "abstract": _extract_heading_section(markdown, READING_ASSIST_HEADING_ALIASES["abstract"], max_chars=1200),
        "critical_analysis": _extract_heading_section(
            markdown,
            READING_ASSIST_HEADING_ALIASES["critical_analysis"],
            max_chars=1600,
        ),
    }


def _build_paper_note_reading_assist(
    markdown: str,
    structured_state: Any,
    *,
    preferred_locale: str | None = None,
) -> PaperNoteReadingAssist | None:
    reading_assists = list(getattr(structured_state, "reading_assists", []) or [])
    if not reading_assists:
        return None

    normalized_preferred_locale = str(preferred_locale or "").strip().lower()
    preferred_by_query = (
        next(
            (
                payload
                for payload in reading_assists
                if str(getattr(payload, "locale", "")).strip().lower() == normalized_preferred_locale and payload.blocks
            ),
            None,
        )
        if normalized_preferred_locale
        else None
    )
    preferred = next(
        (payload for payload in reading_assists if str(getattr(payload, "locale", "")).strip().lower() == "ko" and payload.blocks),
        None,
    )
    selected = preferred_by_query or preferred or next((payload for payload in reading_assists if payload.blocks), None)
    if selected is None:
        return None

    canonical_blocks = _extract_canonical_summary_blocks(markdown)
    blocks: list[PaperNoteReadingAssistBlock] = []
    for block in selected.blocks:
        provenance = getattr(block, "provenance", None)
        source_field = str(getattr(provenance, "source_field", "") or block.kind).strip() or block.kind
        source_locale = str(getattr(provenance, "source_locale", "") or getattr(selected, "canonical_locale", "en")).strip() or "en"
        blocks.append(
            PaperNoteReadingAssistBlock(
                kind=block.kind,
                label=READING_ASSIST_LABELS.get(block.kind, block.kind.replace("_", " ").title()),
                canonical_text=canonical_blocks.get(block.kind),
                translated_text=block.text,
                source_field=source_field,
                source_heading=getattr(block, "source_heading", None),
                source_locale=source_locale.lower(),
                translator=getattr(provenance, "translator", None),
                model=getattr(provenance, "model", None),
                version=getattr(provenance, "version", None),
            )
        )

    if not blocks:
        return None

    return PaperNoteReadingAssist(
        locale=str(getattr(selected, "locale", "ko")).strip().lower() or "ko",
        canonical_locale=str(getattr(selected, "canonical_locale", "en")).strip().lower() or "en",
        machine_translated=bool(getattr(selected, "machine_translated", True)),
        partial=bool(getattr(selected, "partial", True)),
        blocks=blocks,
    )


def _normalize_link_url(url: str) -> str:
    text = url.strip()
    if not text:
        return text
    if text.lower().startswith("file://"):
        parsed = urlparse(text)
        local_path = unquote(parsed.path or "")
        if local_path:
            try:
                return Path(local_path).expanduser().as_uri()
            except Exception:
                return text
    if text.startswith(_ALLOWED_REFERENCE_INTERNAL_PREFIXES):
        return text
    parsed = urlparse(text)
    if parsed.scheme.lower() not in _ALLOWED_REFERENCE_URL_SCHEMES:
        return ""
    return text


def _extract_markdown_links(markdown: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for label, url in MARKDOWN_LINK_PATTERN.findall(markdown or ""):
        clean_label = label.strip()
        clean_url = _normalize_link_url(url)
        if clean_label and clean_url:
            links.append((clean_label, clean_url))
    return links


def _to_reference_source(label: str, url: str) -> Literal["pdf", "doi", "zotero", "external"]:
    lower_label = label.lower()
    lower_url = url.lower()
    if "open pdf" in lower_label or lower_url.startswith("file://") or lower_url.endswith(".pdf"):
        return "pdf"
    if "doi.org" in lower_url or lower_label == "doi":
        return "doi"
    if "zotero" in lower_url:
        return "zotero"
    return "external"


def _append_unique_reference(
    output: list[PaperNoteReferenceLink],
    seen_urls: set[str],
    *,
    label: str,
    url: str,
    source: Literal["pdf", "doi", "zotero", "external"],
) -> None:
    clean_url = _normalize_link_url(url)
    if not clean_url or clean_url in seen_urls:
        return
    output.append(PaperNoteReferenceLink(label=label, url=clean_url, source=source))
    seen_urls.add(clean_url)


def _build_references(frontmatter: dict[str, Any], reference_block: str) -> list[PaperNoteReferenceLink]:
    references: list[PaperNoteReferenceLink] = []
    seen_urls: set[str] = set()
    path_masking = is_path_masking_enabled()

    pdf_url = frontmatter.get("pdf_url")
    normalized_pdf_url = _normalize_link_url(str(pdf_url)) if pdf_url else ""
    if normalized_pdf_url and (not path_masking or normalized_pdf_url.startswith("/papers/")):
        _append_unique_reference(
            references,
            seen_urls,
            label="Open PDF",
            url=normalized_pdf_url,
            source="pdf",
        )

    extracted = _extract_markdown_links(reference_block)
    extracted_pdf = next((entry for entry in extracted if _to_reference_source(entry[0], entry[1]) == "pdf"), None)
    if extracted_pdf and (not path_masking or _normalize_link_url(extracted_pdf[1]).startswith("/papers/")):
        _append_unique_reference(
            references,
            seen_urls,
            label=extracted_pdf[0],
            url=extracted_pdf[1],
            source="pdf",
        )

    doi_url = _normalize_doi(frontmatter.get("doi"))
    if doi_url:
        _append_unique_reference(
            references,
            seen_urls,
            label="DOI",
            url=doi_url,
            source="doi",
        )

    zotero_url = _pick_zotero_link(frontmatter)
    if zotero_url:
        _append_unique_reference(
            references,
            seen_urls,
            label="Zotero",
            url=zotero_url,
            source="zotero",
        )

    for label, url in extracted:
        source = _to_reference_source(label, url)
        if source == "pdf" and path_masking:
            continue
        _append_unique_reference(
            references,
            seen_urls,
            label=label,
            url=url,
            source=source,
        )

    return references


def _apply_filters(
    items: list[PaperNoteIndexItem],
    *,
    q: str | None,
    tags: list[str],
    status: str | None,
    starred: bool,
    triage_label: str | None,
    structured_only: bool,
    has_reading_assist: bool,
    reading_assist_locale: str | None,
) -> list[PaperNoteIndexItem]:
    output = items

    if q:
        query_terms = _parse_query_terms(q)
        if query_terms:
            output = [
                item
                for item in output
                if all(_note_matches_query_term(item, term) for term in query_terms)
            ]

    if tags:
        tag_set = {value.lower() for value in tags if value.strip()}
        if tag_set:
            output = [item for item in output if any(t.lower() in tag_set for t in item.tags)]

    if status:
        target_status = status.strip().upper()
        if target_status:
            output = [item for item in output if (item.status or "").upper() == target_status]

    if starred:
        output = [item for item in output if item.starred]

    if triage_label:
        normalized_label = triage_label.strip().lower()
        if normalized_label:
            output = [item for item in output if normalized_label in item.triage_labels]

    if structured_only:
        output = [item for item in output if _has_structured_content(item)]

    if has_reading_assist:
        output = [item for item in output if _has_reading_assist(item)]

    if reading_assist_locale:
        target_locale = reading_assist_locale.strip().lower()
        if target_locale:
            output = [
                item
                for item in output
                if target_locale in [locale.strip().lower() for locale in item.reading_assist_locales]
            ]

    return output


def _has_structured_content(item: PaperNoteIndexItem) -> bool:
    if item.claim_tags or item.entities or item.mesh or item.outcomes:
        return True
    return item.pp_signals.get("has_claimset") is True


def _has_reading_assist(item: PaperNoteIndexItem) -> bool:
    if item.reading_assist_available or item.reading_assist_locales:
        return True
    return item.pp_signals.get("has_reading_assists") is True


def _collect_reading_assist_filter_metadata(items: list[PaperNoteIndexItem]) -> tuple[int, list[str]]:
    note_count = 0
    locales: list[str] = []
    for item in items:
        if not _has_reading_assist(item):
            continue
        note_count += 1
        for locale in item.reading_assist_locales:
            normalized = locale.strip().lower()
            if normalized and normalized not in locales:
                locales.append(normalized)
    return note_count, locales


def _parse_query_terms(q: str | None) -> list[str]:
    if not q:
        return []
    terms: list[str] = []
    for phrase, token in QUERY_TERM_PATTERN.findall(q):
        raw = phrase or token
        normalized = " ".join(raw.strip().lower().split())
        if normalized:
            terms.append(normalized)
    return terms


def _note_matches_query_term(item: PaperNoteIndexItem, token: str) -> bool:
    return (
        token in _normalize_search_text(item.title)
        or token in _normalize_search_text(item.slug)
        or token in _normalize_search_text(item.id or "")
        or any(token in _normalize_search_text(alias) for alias in item.aliases)
        or any(token in _normalize_search_text(tag) for tag in item.tags)
        or any(token in _normalize_search_text(tag) for tag in item.claim_tags)
        or any(token in _normalize_search_text(signal) for signal in item.entities)
        or any(token in _normalize_search_text(signal) for signal in item.mesh)
        or any(token in _normalize_search_text(signal) for signal in item.outcomes)
        or token in _normalize_search_text(str(item.pp_signals.get("last_appraisal", "")))
    )


def _normalize_search_text(value: str) -> str:
    return " ".join(value.lower().split())


def _normalize_paper_note_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _paper_id_variants(paper_id: str) -> list[str]:
    return paper_id_search_variants(paper_id)


def _paper_note_lookup_candidates(paper_id: str) -> list[str]:
    return paper_note_lookup_candidate_ids(paper_id)


def _paper_note_identity_sets(item: PaperNoteIndexItem) -> tuple[frozenset[str], frozenset[str]]:
    if (cached := item.get_runtime_identity_sets()) is not None:
        return cached

    raw_variants: set[str] = set()
    for candidate in (item.id, item.slug):
        if not candidate:
            continue
        for variant in _paper_id_variants(str(candidate)):
            if variant:
                raw_variants.add(variant)
    normalized_variants = {
        normalized
        for value in raw_variants
        if (normalized := _normalize_paper_note_id(value))
    }
    item.set_runtime_identity_sets(
        raw_variants=raw_variants,
        normalized_variants=normalized_variants,
    )
    cached = item.get_runtime_identity_sets()
    return cached if cached is not None else (frozenset(raw_variants), frozenset(normalized_variants))


def _merge_unique_text_values(*groups: list[str]) -> list[str]:
    values: list[str] = []
    for group in groups:
        for value in group:
            normalized = str(value or "").strip()
            if normalized and normalized not in values:
                values.append(normalized)
    return values


def _merge_triage_labels(
    preferred: list[PaperNoteOperatorTriageLabel],
    variant: list[PaperNoteOperatorTriageLabel],
) -> list[PaperNoteOperatorTriageLabel]:
    merged: list[PaperNoteOperatorTriageLabel] = []
    for label in PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER:
        if label in preferred or label in variant:
            merged.append(label)
    return merged


def _paper_note_variant_preference_key(item: PaperNoteIndexItem) -> tuple[Any, ...]:
    cached_listing_candidate = item.get_runtime_listing_candidate_metadata()
    if cached_listing_candidate is not None:
        is_fixture = cached_listing_candidate[3]
    else:
        paper_id = str(item.id or item.slug or "").strip()
        title = str(item.title or item.slug or paper_id).strip() or paper_id
        is_fixture = is_test_fixture_paper_record({"paper_id": paper_id, "title": title})
    return (
        0 if is_fixture else 1,
        1 if item.structured_state_present else 0,
        1 if ":" in str(item.id or "") else 0,
        1 if item.aliases else 0,
        1 if item.has_operator_note else 0,
        1 if item.starred else 0,
        len(item.triage_labels or []),
        _parse_datetime_for_sort(item.updated_at),
        _parse_date_for_sort(item.date_processed),
        item.confidence if item.confidence is not None else -1.0,
    )


def _paper_note_ops_summary_preference_key(summary: PaperNoteOpsSummary | None) -> tuple[Any, ...]:
    if summary is None:
        return (0, 0, 0, 0, 0)

    severity = 1
    if summary.state == "action_needed":
        severity = 2
        if summary.recommended_action == "repair_stats":
            severity = 3

    return (
        severity,
        1 if summary.has_claimset else 0,
        1 if summary.has_stats_report else 0,
        int(summary.stats_check_count or 0),
        1 if summary.latest_run_id else 0,
    )


def _merge_paper_note_variants(
    preferred: PaperNoteIndexItem,
    variant: PaperNoteIndexItem,
) -> PaperNoteIndexItem:
    merged = preferred.model_copy(deep=True)

    merged.aliases = _merge_unique_text_values(
        list(preferred.aliases),
        [preferred.title, preferred.slug, preferred.id or ""],
        list(variant.aliases),
        [variant.title, variant.slug, variant.id or ""],
    )
    merged.tags = _merge_unique_text_values(list(preferred.tags), list(variant.tags))
    merged.claim_tags = _merge_unique_text_values(list(preferred.claim_tags), list(variant.claim_tags))
    merged.entities = _merge_unique_text_values(list(preferred.entities), list(variant.entities))
    merged.mesh = _merge_unique_text_values(list(preferred.mesh), list(variant.mesh))
    merged.outcomes = _merge_unique_text_values(list(preferred.outcomes), list(variant.outcomes))
    merged.reading_assist_locales = _merge_unique_text_values(
        list(preferred.reading_assist_locales),
        list(variant.reading_assist_locales),
    )
    merged.reading_assist_available = merged.reading_assist_available or variant.reading_assist_available
    merged.structured_state_present = merged.structured_state_present or variant.structured_state_present
    merged.starred = merged.starred or variant.starred
    merged.has_operator_note = merged.has_operator_note or variant.has_operator_note
    merged.triage_labels = _merge_triage_labels(list(preferred.triage_labels), list(variant.triage_labels))

    selected_ops_summary = preferred.ops_summary
    if _paper_note_ops_summary_preference_key(variant.ops_summary) > _paper_note_ops_summary_preference_key(
        selected_ops_summary
    ):
        selected_ops_summary = variant.ops_summary
    merged.ops_summary = selected_ops_summary.model_copy(deep=True) if selected_ops_summary is not None else None

    merged_signals = dict(variant.pp_signals)
    merged_signals.update(preferred.pp_signals)
    merged.pp_signals = merged_signals

    raw_preferred, normalized_preferred = _paper_note_identity_sets(preferred)
    raw_variant, normalized_variant = _paper_note_identity_sets(variant)
    merged.set_runtime_identity_sets(
        raw_variants=raw_preferred | raw_variant,
        normalized_variants=normalized_preferred | normalized_variant,
    )
    return merged


def _dedupe_equivalent_note_items(items: list[PaperNoteIndexItem]) -> list[PaperNoteIndexItem]:
    return _dedupe_equivalent_note_items_with_ops(
        items,
        artifacts_path=artifacts_root(),
        artifact_cache={},
    )


def _dedupe_equivalent_note_items_with_ops(
    items: list[PaperNoteIndexItem],
    *,
    artifacts_path: Path | None = None,
    artifact_cache: ArtifactSnapshotCache | None = None,
) -> list[PaperNoteIndexItem]:
    deduped: list[PaperNoteIndexItem] = []
    seen_raw_to_index: dict[str, int] = {}
    seen_normalized_to_index: dict[str, int] = {}
    effective_artifact_cache = artifact_cache if artifact_cache is not None else {}

    for item in items:
        raw_variants, normalized_variants = _paper_note_identity_sets(item)
        matching_indexes = {
            seen_raw_to_index[value]
            for value in raw_variants
            if value in seen_raw_to_index
        }
        matching_indexes.update(
            seen_normalized_to_index[value]
            for value in normalized_variants
            if value in seen_normalized_to_index
        )

        if not matching_indexes:
            clone = item.model_copy(deep=True)
            clone.set_runtime_identity_sets(
                raw_variants=raw_variants,
                normalized_variants=normalized_variants,
            )
            deduped.append(clone)
            index = len(deduped) - 1
        else:
            index = min(matching_indexes)
            existing = deduped[index]
            preferred = existing
            variant = item
            if _paper_note_variant_preference_key(item) > _paper_note_variant_preference_key(existing):
                preferred = item
                variant = existing
            deduped[index] = _merge_paper_note_variants(preferred, variant)

        merged_raw_variants, merged_normalized_variants = _paper_note_identity_sets(deduped[index])
        if artifacts_path is not None:
            recomputed_ops_summary = build_ops_summary_for_candidate_ids(
                artifacts_path,
                list(merged_raw_variants),
                effective_artifact_cache,
            )
            if recomputed_ops_summary is not None:
                deduped[index].ops_summary = recomputed_ops_summary
        for value in merged_raw_variants:
            seen_raw_to_index[value] = index
        for value in merged_normalized_variants:
            seen_normalized_to_index[value] = index

    return deduped


def _find_note_item_for_paper_id(items: list[PaperNoteIndexItem], paper_id: str) -> PaperNoteIndexItem | None:
    ordered_candidates = _paper_note_lookup_candidates(paper_id)
    if not ordered_candidates:
        return None
    normalized_candidates = [
        normalized
        for candidate in ordered_candidates
        if (normalized := _normalize_paper_note_id(candidate))
    ]

    for candidate in ordered_candidates:
        for item in items:
            if item.id == candidate or item.slug == candidate:
                return item

    for normalized_candidate in normalized_candidates:
        for item in items:
            item_normalized_candidates = [
                _normalize_paper_note_id(value)
                for value in (item.id, item.slug)
                if value
            ]
            if normalized_candidate in item_normalized_candidates:
                return item
    return None


def _query_match_score(item: PaperNoteIndexItem, query_terms: list[str]) -> int:
    if not query_terms:
        return 0

    field_weights: list[tuple[str, int]] = [
        (_normalize_search_text(item.title), 6),
        (_normalize_search_text(item.slug), 4),
        (_normalize_search_text(item.id or ""), 4),
        (_normalize_search_text(str(item.pp_signals.get("last_appraisal", ""))), 2),
    ]
    field_weights.extend((_normalize_search_text(alias), 5) for alias in item.aliases)
    field_weights.extend((_normalize_search_text(tag), 4) for tag in item.tags)
    field_weights.extend((_normalize_search_text(tag), 5) for tag in item.claim_tags)
    field_weights.extend((_normalize_search_text(signal), 5) for signal in item.entities)
    field_weights.extend((_normalize_search_text(signal), 5) for signal in item.mesh)
    field_weights.extend((_normalize_search_text(signal), 5) for signal in item.outcomes)

    score = 0
    for term in query_terms:
        score += max((weight for text, weight in field_weights if text and term in text), default=0)
    return score


def _parse_tags(tag: str | None, tags: str | None) -> list[str]:
    if tags and tags.strip():
        values = [entry.strip() for entry in tags.split(",")]
        return [value for value in values if value]
    if tag and tag.strip():
        return [tag.strip()]
    return []


def _apply_sort(
    items: list[PaperNoteIndexItem],
    *,
    sort_by: Literal["date_processed", "confidence"],
    sort_order: Literal["asc", "desc"],
    query_terms: list[str] | None = None,
) -> list[PaperNoteIndexItem]:
    output = sorted(items, key=lambda item: item.title.lower())
    using_default_sort = sort_by == "date_processed" and sort_order == "desc" and not query_terms
    if using_default_sort:
        output = sorted(output, key=_default_discoverability_sort_key, reverse=True)
    elif sort_by == "confidence":
        output = sorted(
            output,
            key=lambda item: item.confidence if item.confidence is not None else -1.0,
            reverse=sort_order == "desc",
        )
    else:
        output = sorted(
            output,
            key=lambda item: _parse_date_for_sort(item.date_processed),
            reverse=sort_order == "desc",
        )

    if query_terms:
        output = sorted(output, key=lambda item: _query_match_score(item, query_terms), reverse=True)
    return output


def _compute_related(
    target: PaperNoteIndexItem,
    items: list[PaperNoteIndexItem],
    *,
    limit: int,
) -> list[PaperNoteRelatedItem]:
    target_tags = {tag.lower(): tag for tag in target.tags}
    target_signal_values = target.entities + target.mesh + target.outcomes + target.claim_tags
    target_signals = {value.lower(): value for value in target_signal_values}
    if not target_tags and not target_signals:
        return []

    scored: list[tuple[int, float, tuple[int, str], PaperNoteRelatedItem]] = []
    for item in items:
        if item.slug == target.slug:
            continue
        shared = [tag for tag in item.tags if tag.lower() in target_tags]
        shared_signals = sorted(
            {
                value
                for value in (item.entities + item.mesh + item.outcomes + item.claim_tags)
                if value.lower() in target_signals
            },
            key=lambda value: value.lower(),
        )
        if not shared and not shared_signals:
            continue

        related = PaperNoteRelatedItem(
            slug=item.slug,
            title=item.title,
            shared_tags=sorted(shared, key=lambda value: value.lower()),
            shared_signals=shared_signals,
        )
        scored.append(
            (
                len(related.shared_tags) + len(related.shared_signals),
                item.confidence if item.confidence is not None else -1.0,
                _parse_date_for_sort(item.date_processed),
                related,
            )
        )

    scored.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    return [entry[3] for entry in scored[:limit]]


def _build_context_trace_summary(
    trace: list[PaperNoteContextTraceEntry],
    *,
    related: list[PaperNoteRelatedItem],
    references: list[PaperNoteReferenceLink],
) -> PaperNoteContextTraceSummary:
    action_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    source_paths: list[str] = []
    related_slugs: list[str] = []
    reference_sources: list[str] = []

    for entry in trace:
        action_counts[entry.action] = action_counts.get(entry.action, 0) + 1
        outcome_counts[entry.outcome] = outcome_counts.get(entry.outcome, 0) + 1
        if entry.source_path and entry.source_path not in source_paths:
            source_paths.append(entry.source_path)
        for slug in entry.matched_slugs:
            if slug not in related_slugs:
                related_slugs.append(slug)

    for reference in references:
        if reference.source not in reference_sources:
            reference_sources.append(reference.source)

    return PaperNoteContextTraceSummary(
        entry_count=len(trace),
        source_path_count=len(source_paths),
        related_count=len(related),
        reference_count=len(references),
        action_counts=action_counts,
        outcome_counts=outcome_counts,
        source_paths=source_paths,
        related_slugs=related_slugs,
        reference_sources=reference_sources,
    )


def _build_paper_note_context_trace(
    *,
    target: PaperNoteIndexItem,
    filtered_sections: list[str],
    related: list[PaperNoteRelatedItem],
    references: list[PaperNoteReferenceLink],
    structured_state: Any,
    related_limit: int,
    structured_state_rel_path: str,
) -> PaperNoteContextTrace:
    trace: list[PaperNoteContextTraceEntry] = [
        PaperNoteContextTraceEntry(
            order=1,
            action="note_loaded",
            outcome="loaded",
            detail="Loaded note frontmatter and markdown body for detail rendering.",
            source_path=target.note_path,
            metadata={"note_slug": target.slug, "note_id": target.id},
        ),
        PaperNoteContextTraceEntry(
            order=2,
            action="body_sections_filtered",
            outcome="filtered",
            detail="Removed raw Related Papers and References sections from the center markdown body.",
            source_path=target.note_path,
            metadata={"filtered_sections": filtered_sections},
        ),
        PaperNoteContextTraceEntry(
            order=3,
            action="references_resolved",
            outcome="resolved",
            detail="Resolved preferred reference links from frontmatter and captured markdown references.",
            source_path=target.note_path,
            metadata={
                "reference_count": len(references),
                "reference_sources": list(dict.fromkeys(reference.source for reference in references)),
            },
        ),
        PaperNoteContextTraceEntry(
            order=4,
            action="related_computed",
            outcome="derived",
            detail="Computed related papers from shared tags and structured signals only.",
            source_path=str(_index_cache_path()),
            matched_slugs=[item.slug for item in related],
            metadata={"related_limit": related_limit},
        ),
    ]

    if structured_state is not None:
        trace.append(
            PaperNoteContextTraceEntry(
                order=5,
                action="structured_state_loaded",
                outcome="loaded",
                detail="Loaded canonical structured sidecar state for the note detail view.",
                source_path=structured_state_rel_path,
                metadata={
                    "run_count": len(getattr(structured_state, "runs", []) or []),
                    "has_claimset": bool(getattr(structured_state, "claimset", []) or []),
                },
            )
        )
    else:
        trace.append(
            PaperNoteContextTraceEntry(
                order=5,
                action="structured_state_loaded",
                outcome="missing",
                detail="No canonical structured sidecar state was available for this note.",
                source_path=structured_state_rel_path,
            )
        )

    return PaperNoteContextTrace(
        available=bool(trace),
        summary=_build_context_trace_summary(trace, related=related, references=references),
        trace=trace,
    )


def _find_note_item(items: list[PaperNoteIndexItem], slug: str) -> PaperNoteIndexItem | None:
    for item in items:
        if item.slug == slug:
            return item
    return _find_note_item_for_paper_id(items, slug)


@router.get("/home-context", response_model=PaperNotesHomeContextResponse)
def get_paper_notes_home_context():
    try:
        vault_path = _resolve_vault_path()
        index = _build_index(vault_path)
    except Exception:
        return PaperNotesHomeContextResponse(note_context_limited=True)
    return _build_home_context(index)


@router.get("", response_model=PaperNoteListResponse)
def list_paper_notes(
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    tags: str | None = Query(default=None, description="Comma-separated tags for OR filtering"),
    status: str | None = Query(default=None),
    starred: bool = Query(default=False),
    triage_label: str | None = Query(default=None),
    structured_only: bool = Query(default=False),
    has_reading_assist: bool = Query(default=False),
    reading_assist_locale: str | None = Query(default=None),
    sort_by: Literal["date_processed", "confidence"] = Query(default="date_processed"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=200),
):
    try:
        vault_path = _resolve_vault_path()
        index = _build_index(vault_path)
    except Exception:
        return _build_empty_index_response(page_size=page_size)
    artifact_cache: ArtifactSnapshotCache = {}
    visible_items = _dedupe_equivalent_note_items_with_ops(
        index.items,
        artifacts_path=artifacts_root(),
        artifact_cache=artifact_cache,
    )
    filter_tags = _parse_tags(tag=tag, tags=tags)
    query_terms = _parse_query_terms(q)
    base_filtered = _apply_filters(
        visible_items,
        q=q,
        tags=filter_tags,
        status=status,
        starred=starred,
        triage_label=triage_label,
        structured_only=structured_only,
        has_reading_assist=False,
        reading_assist_locale=None,
    )
    available_reading_assist_note_count, available_reading_assist_locales = _collect_reading_assist_filter_metadata(base_filtered)
    filtered = _apply_filters(
        base_filtered,
        q=None,
        tags=[],
        status=None,
        starred=False,
        triage_label=None,
        structured_only=False,
        has_reading_assist=has_reading_assist,
        reading_assist_locale=reading_assist_locale,
    )
    sorted_items = _apply_sort(filtered, sort_by=sort_by, sort_order=sort_order, query_terms=query_terms)
    total = len(sorted_items)
    total_pages = max(1, ceil(total / page_size))
    page_clamped = min(page, total_pages)
    start = (page_clamped - 1) * page_size
    end = start + page_size
    page_items = sorted_items[start:end]
    return PaperNoteListResponse(
        generated_at=index.generated_at,
        index_path=index.index_path,
        total=total,
        page=page_clamped,
        page_size=page_size,
        total_pages=total_pages,
        available_tags=index.available_tags,
        available_statuses=index.available_statuses,
        available_reading_assist_note_count=available_reading_assist_note_count,
        available_reading_assist_locales=available_reading_assist_locales,
        items=page_items,
    )


@router.get("/resolve-by-paper-id", response_model=PaperNoteStructuredStateLookupResponse)
def resolve_paper_note_by_paper_id(
    paper_id: str = Query(..., min_length=1),
):
    vault_path = _resolve_vault_path()
    index = _build_index(vault_path)
    target = _find_note_item_for_paper_id(index.items, paper_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Paper note not found for paper_id={paper_id}")

    _, frontmatter = _resolve_lookup_frontmatter(vault_path, target)
    path_masking = is_path_masking_enabled()
    raw_pdf_url = frontmatter.get("pdf_url")
    normalized_pdf_url = _normalize_link_url(str(raw_pdf_url)) if raw_pdf_url else ""
    if normalized_pdf_url and path_masking and not normalized_pdf_url.startswith("/papers/"):
        normalized_pdf_url = ""
    doi_url = _normalize_doi(frontmatter.get("doi"))
    structured_state = _load_visible_structured_state(vault_path, target.slug, frontmatter)
    operator_state = load_operator_state(vault_path, target.slug, target.id) or build_default_operator_state(
        note_slug=target.slug,
        paper_id=target.id,
    )
    return PaperNoteStructuredStateLookupResponse(
        paper_id=str(target.id or paper_id).strip() or paper_id,
        slug=target.slug,
        note_path=target.note_path,
        note=target,
        pdf_url=normalized_pdf_url or None,
        doi_url=doi_url,
        structured_state=structured_state,
        operator_state=operator_state,
    )


@router.post("/import-pdf", response_model=PaperNoteImportResponse)
async def import_paper_pdf(
    file: UploadFile = File(...),
):
    filename = str(file.filename or "").strip()

    try:
        payload = await _read_upload_with_size_limit(
            file,
            max_bytes=_resolve_import_pdf_max_bytes(),
        )
    finally:
        await file.close()
    return await anyio.to_thread.run_sync(
        lambda: import_pdf_payload(filename=filename, payload=payload)
    )


@router.get("/{slug}/operator-state", response_model=PaperNoteOperatorState)
def get_paper_note_operator_state(slug: str):
    vault_path = _resolve_vault_path()
    index = _build_index(vault_path)
    target = _find_note_item(index.items, slug)
    if not target:
        raise HTTPException(status_code=404, detail=f"Paper note not found for slug={slug}")
    return load_operator_state(vault_path, target.slug, target.id) or build_default_operator_state(
        note_slug=target.slug,
        paper_id=target.id,
    )


@router.put("/{slug}/operator-state", response_model=PaperNoteOperatorState)
def put_paper_note_operator_state(
    slug: str,
    request: PaperNoteOperatorStateUpdateRequest,
):
    vault_path = _resolve_vault_path()
    index = _build_index(vault_path)
    target = _find_note_item(index.items, slug)
    if not target:
        raise HTTPException(status_code=404, detail=f"Paper note not found for slug={slug}")
    return save_operator_state(
        vault_path,
        note_slug=target.slug,
        paper_id=target.id,
        update=request,
    )


@router.get("/{slug}", response_model=PaperNoteDetailResponse)
def get_paper_note(
    slug: str,
    related_limit: int = Query(default=5, ge=1, le=20),
    reading_assist_locale: str | None = Query(default=None),
):
    vault_path = _resolve_vault_path()
    index = _build_index(vault_path)
    target = _find_note_item(index.items, slug)
    if not target:
        raise HTTPException(status_code=404, detail=f"Paper note not found for slug={slug}")

    note_path = vault_path / target.note_path
    if not note_path.exists():
        raise HTTPException(status_code=404, detail=f"Note file not found: {target.note_path}")

    content = _safe_read_text(note_path)
    frontmatter, body = _parse_frontmatter(content)
    stripped_body, reference_block, filtered_sections = _strip_sections_and_capture_references(body)
    converted_body = _convert_wikilinks(stripped_body)
    references = _build_references(frontmatter, reference_block)
    related = _compute_related(target, index.items, limit=related_limit)
    structured_state = _load_visible_structured_state(vault_path, slug, frontmatter)
    section_navigator = _build_section_navigator(
        markdown=converted_body,
        note_title=target.title,
        structured_state=structured_state,
    )
    reading_assist = _build_paper_note_reading_assist(
        converted_body,
        structured_state,
        preferred_locale=reading_assist_locale,
    )
    operator_state = load_operator_state(vault_path, target.slug, target.id) or build_default_operator_state(
        note_slug=target.slug,
        paper_id=target.id,
    )
    pp = frontmatter.get("pp")
    structured_state_rel_path = f".pp/{target.slug}/state.json"
    if isinstance(pp, dict):
        candidate = str(pp.get("structured_path") or "").strip()
        if candidate:
            structured_state_rel_path = candidate
    context_trace = _build_paper_note_context_trace(
        target=target,
        filtered_sections=filtered_sections,
        related=related,
        references=references,
        structured_state=structured_state,
        related_limit=related_limit,
        structured_state_rel_path=structured_state_rel_path,
    )

    return PaperNoteDetailResponse(
        note=target,
        frontmatter=_jsonable(frontmatter),
        body_markdown=converted_body,
        related=related,
        references=references,
        context_trace=context_trace,
        structured_state=structured_state,
        section_navigator=section_navigator,
        reading_assist=reading_assist,
        operator_state=operator_state,
        available_actions=list_available_actions(),
    )
