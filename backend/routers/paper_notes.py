from __future__ import annotations

from datetime import date, datetime, timezone
from math import ceil
from pathlib import Path
import json
import re
from typing import Any, Literal
from urllib.parse import quote, unquote, urlparse

from fastapi import APIRouter, HTTPException, Query
import yaml

from src.config import load_config
from src.schemas.paper_notes import (
    PaperNoteContextTrace,
    PaperNoteContextTraceEntry,
    PaperNoteContextTraceSummary,
    PaperNoteDetailResponse,
    PaperNoteIndexItem,
    PaperNoteListResponse,
    PaperNoteOpsSummary,
    PaperNoteReferenceLink,
    PaperNoteRelatedItem,
    PaperNoteStructuredStateLookupResponse,
)
from src.skills.registry import list_available_actions
from src.skills.storage import load_structured_state
from src.services.path_masking import is_path_masking_enabled
from src.services.paper_ops_summary import ArtifactSnapshotCache, build_ops_summary_for_candidate_ids
from src.services.runtime_paths import artifacts_root

router = APIRouter(prefix="/paper-notes", tags=["paper-notes"])

INDEX_CACHE_PATH = Path("storage/obsidian/paper_notes_index.json")
EXCLUDED_DIR_NAMES = {".obsidian", "_backup"}
DEFAULT_PAGE_SIZE = 30
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
QUERY_TERM_PATTERN = re.compile(r'"([^"]+)"|(\S+)')



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

    aliases = _to_str_list(frontmatter.get("aliases"))
    title = aliases[0] if aliases else _extract_title(body, note_path.stem)
    tags = _to_str_list(frontmatter.get("tags"))
    structured_state = load_structured_state(vault_path, note_path.stem, frontmatter)
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
    pp_signals = pp.get("signals") if isinstance(pp, dict) and isinstance(pp.get("signals"), dict) else {}
    ops_summary = _build_ops_summary(
        note_path,
        frontmatter,
        artifacts_path=artifacts_path,
        artifact_cache=artifact_cache,
    )

    updated_at = datetime.fromtimestamp(note_path.stat().st_mtime, tz=timezone.utc).isoformat()
    return PaperNoteIndexItem(
        slug=note_path.stem,
        title=title,
        note_path=relative_path.as_posix(),
        structured_state_present=structured_state is not None,
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
    )


def _resolve_vault_path() -> Path:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Obsidian vault path is not a directory: {vault_path}")
    return vault_path


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


def _index_sort_key(item: PaperNoteIndexItem) -> tuple[Any, ...]:
    return (
        _parse_date_for_sort(item.date_processed),
        item.confidence if item.confidence is not None else -1.0,
        item.title.lower(),
    )


def _build_index(vault_path: Path) -> PaperNoteListResponse:
    items: list[PaperNoteIndexItem] = []
    seen_slugs: set[str] = set()
    artifacts_path = artifacts_root()
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
        index_path=str(INDEX_CACHE_PATH),
        total=len(items),
        page=1,
        page_size=DEFAULT_PAGE_SIZE,
        total_pages=max(1, ceil(len(items) / DEFAULT_PAGE_SIZE)),
        available_tags=available_tags,
        available_statuses=available_statuses,
        items=items,
    )

    INDEX_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_CACHE_PATH.write_text(
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


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
    if pdf_url and not path_masking:
        _append_unique_reference(
            references,
            seen_urls,
            label="Open PDF",
            url=str(pdf_url),
            source="pdf",
        )

    extracted = _extract_markdown_links(reference_block)
    extracted_pdf = next((entry for entry in extracted if _to_reference_source(entry[0], entry[1]) == "pdf"), None)
    if extracted_pdf and not path_masking:
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
    structured_only: bool,
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

    if structured_only:
        output = [item for item in output if _has_structured_content(item)]

    return output


def _has_structured_content(item: PaperNoteIndexItem) -> bool:
    if item.claim_tags or item.entities or item.mesh or item.outcomes:
        return True
    return item.pp_signals.get("has_claimset") is True


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
    text = str(paper_id or "").strip()
    if not text:
        return []

    variants: list[str] = []

    def _append(value: str) -> None:
        candidate = value.strip()
        if candidate and candidate not in variants:
            variants.append(candidate)

    _append(text)
    _append(text.replace(":", ""))
    if ":" in text:
        suffix = text.split(":", 1)[1].strip()
        _append(suffix)
        _append(suffix.replace(":", ""))
    return variants


def _find_note_item_for_paper_id(items: list[PaperNoteIndexItem], paper_id: str) -> PaperNoteIndexItem | None:
    raw_variants = _paper_id_variants(paper_id)
    if not raw_variants:
        return None
    normalized_variants = {_normalize_paper_note_id(value) for value in raw_variants}

    def _matches_exact(item: PaperNoteIndexItem) -> bool:
        candidates = [item.id, item.slug]
        return any(candidate in raw_variants for candidate in candidates if candidate)

    for item in items:
        if _matches_exact(item):
            return item

    for item in items:
        candidates = [item.id, item.slug]
        normalized_candidates = {
            _normalize_paper_note_id(candidate)
            for candidate in candidates
            if candidate
        }
        if normalized_candidates & normalized_variants:
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
    if sort_by == "confidence":
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
) -> PaperNoteContextTrace:
    structured_state_rel_path = f".pp/{target.slug}/state.json"
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
            source_path=str(INDEX_CACHE_PATH),
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
    return None


@router.get("", response_model=PaperNoteListResponse)
def list_paper_notes(
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    tags: str | None = Query(default=None, description="Comma-separated tags for OR filtering"),
    status: str | None = Query(default=None),
    structured_only: bool = Query(default=False),
    sort_by: Literal["date_processed", "confidence"] = Query(default="date_processed"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=200),
):
    vault_path = _resolve_vault_path()
    index = _build_index(vault_path)
    filter_tags = _parse_tags(tag=tag, tags=tags)
    query_terms = _parse_query_terms(q)
    filtered = _apply_filters(index.items, q=q, tags=filter_tags, status=status, structured_only=structured_only)
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

    note_path = vault_path / target.note_path
    if not note_path.exists():
        raise HTTPException(status_code=404, detail=f"Note file not found: {target.note_path}")

    content = _safe_read_text(note_path)
    frontmatter, _ = _parse_frontmatter(content)
    structured_state = load_structured_state(vault_path, target.slug, frontmatter)
    return PaperNoteStructuredStateLookupResponse(
        paper_id=paper_id,
        slug=target.slug,
        note_path=target.note_path,
        structured_state=structured_state,
    )


@router.get("/{slug}", response_model=PaperNoteDetailResponse)
def get_paper_note(
    slug: str,
    related_limit: int = Query(default=5, ge=1, le=20),
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
    structured_state = load_structured_state(vault_path, slug, frontmatter)
    context_trace = _build_paper_note_context_trace(
        target=target,
        filtered_sections=filtered_sections,
        related=related,
        references=references,
        structured_state=structured_state,
        related_limit=related_limit,
    )

    return PaperNoteDetailResponse(
        note=target,
        frontmatter=_jsonable(frontmatter),
        body_markdown=converted_body,
        related=related,
        references=references,
        context_trace=context_trace,
        structured_state=structured_state,
        available_actions=list_available_actions(),
    )
