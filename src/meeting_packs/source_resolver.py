from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from src.profiles.profile_metadata import (
    is_research_dna_projection_profile,
    parse_research_dna_projection_metadata,
)
from src.profiles.profile_schema import Profile
from src.profiles.profile_store import load_profiles
from src.profiles.research_dna_schema import RunLogEntry, ScreeningLogEntry
from src.profiles.research_dna_store import research_dna_log_path, sanitize_research_dna_log_payload
from src.schemas.meeting_pack import (
    MeetingPackRetrievalTraceEntry,
    MeetingPackSourceItem,
    MeetingPackSourceSelector,
)
from src.schemas.skills import StructuredPaperState
from src.services.fixture_visibility import (
    fixture_structured_state_allowed,
    is_test_fixture_structured_state,
)
from src.services.runtime_paths import research_dna_root as default_research_dna_root
from src.skills.storage import (
    load_structured_state,
    resolve_note_path,
    resolve_vault_relative_path,
    safe_read_text,
    split_frontmatter,
)


WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True)
class ResolvedMeetingPackSource:
    source_item: MeetingPackSourceItem
    structured_state: StructuredPaperState


@dataclass(frozen=True)
class ResolvedMeetingPackScreeningContext:
    source_item: MeetingPackSourceItem
    dna_id: str
    run_id: str
    include_count: int
    exclude_count: int
    unclear_count: int
    top_reason_codes: list[str]
    notes: list[str]
    matched_paper_slugs: list[str]


@dataclass(frozen=True)
class ResolvedMeetingPackBundle:
    selected_items: list[MeetingPackSourceItem]
    sources: list[ResolvedMeetingPackSource]
    screening_contexts: list[ResolvedMeetingPackScreeningContext]
    retrieval_trace: list[MeetingPackRetrievalTraceEntry]


def resolve_meeting_pack_sources(
    *,
    vault_path: Path,
    source_selectors: list[MeetingPackSourceSelector],
    profiles_path: Path | None = None,
    research_dna_root: Path | None = None,
) -> ResolvedMeetingPackBundle:
    if not source_selectors:
        raise ValueError("Meeting Pack generation requires at least one source selector.")

    selected_items: list[MeetingPackSourceItem] = []
    resolved_by_slug: dict[str, ResolvedMeetingPackSource] = {}
    screening_contexts: list[ResolvedMeetingPackScreeningContext] = []
    retrieval_trace: list[MeetingPackRetrievalTraceEntry] = []
    seen_selectors: set[tuple[str, str]] = set()

    for index, selector in enumerate(source_selectors, start=1):
        selector_type = selector.type
        selector_ref = selector.ref.strip()
        dedupe_key = (selector_type, selector_ref)
        if dedupe_key in seen_selectors:
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="selector_deduped",
                outcome="deduped",
                detail="Duplicate selector was skipped before source resolution.",
            )
            continue
        seen_selectors.add(dedupe_key)

        if selector_type in {"paper_slug", "paper_state"}:
            selected_item = _build_source_item(
                item_id=f"src_{index:02d}",
                item_type=selector_type,
                ref=selector_ref,
                title=_paper_title(vault_path, selector_ref),
                priority=1,
            )
            selected_items.append(selected_item)
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="selector_selected",
                outcome="selected",
                detail="Direct structured paper selector accepted.",
                source_item_id=selected_item.id,
            )
            if selector_ref in resolved_by_slug:
                _append_retrieval_trace(
                    retrieval_trace,
                    selector_type=selector_type,
                    selector_ref=selector_ref,
                    action="paper_state_loaded",
                    outcome="loaded",
                    detail="Canonical structured paper state was already loaded earlier in this resolution pass.",
                    source_item_id=selected_item.id,
                    source_path=f".pp/{selector_ref}/state.json",
                    matched_paper_slugs=[selector_ref],
                    metadata={"loaded_count": 0, "reused_count": 1},
                )
            else:
                source = _load_paper_source(
                    vault_path,
                    selector_ref,
                    paper_index=len(resolved_by_slug) + 1,
                    direct_source_item=selected_item,
                )
                resolved_by_slug[selector_ref] = source
                _append_retrieval_trace(
                    retrieval_trace,
                    selector_type=selector_type,
                    selector_ref=selector_ref,
                    action="paper_state_loaded",
                    outcome="loaded",
                    detail="Loaded canonical structured paper state from the paper sidecar.",
                    source_item_id=selected_item.id,
                    source_path=f".pp/{selector_ref}/state.json",
                    matched_paper_slugs=[selector_ref],
                    metadata={"loaded_count": 1, "reused_count": 0},
                )
            continue

        if selector_type in {"paper_note", "project_note", "research_note"}:
            note_path = _resolve_note_selector_path(vault_path, selector_ref)
            note_relpath = str(note_path.relative_to(vault_path))
            frontmatter, body = split_frontmatter(safe_read_text(note_path))
            note_title = _note_title(frontmatter, body, note_path.stem)
            priority = 2 if selector_type == "paper_note" else 3
            selected_item = _build_source_item(
                item_id=f"src_{index:02d}",
                item_type=selector_type,
                ref=note_relpath,
                title=note_title,
                priority=priority,
            )
            selected_items.append(selected_item)
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="selector_selected",
                outcome="selected",
                detail="Note selector accepted for context-based source resolution.",
                source_item_id=selected_item.id,
                source_path=note_relpath,
            )
            linked_slugs = _extract_note_paper_slugs(frontmatter, body)
            if not linked_slugs:
                linked_slugs = _fallback_note_selector_slugs(
                    vault_path=vault_path,
                    note_path=note_path,
                    selector_type=selector_type,
                )
                if linked_slugs:
                    _append_retrieval_trace(
                        retrieval_trace,
                        selector_type=selector_type,
                        selector_ref=selector_ref,
                        action="note_fallback_resolved",
                        outcome="resolved",
                        detail="No explicit linked paper list was found; same-slug structured state fallback was used.",
                        source_item_id=selected_item.id,
                        source_path=note_relpath,
                        matched_paper_slugs=linked_slugs,
                    )
            else:
                _append_retrieval_trace(
                    retrieval_trace,
                    selector_type=selector_type,
                    selector_ref=selector_ref,
                    action="note_links_resolved",
                    outcome="resolved",
                    detail="Resolved linked paper slugs from note frontmatter/body only.",
                    source_item_id=selected_item.id,
                    source_path=note_relpath,
                    matched_paper_slugs=linked_slugs,
                )
            matched_slugs, loaded_slugs, reused_slugs = _resolve_selector_slugs(
                vault_path=vault_path,
                slugs=linked_slugs,
                selector_type=selector_type,
                selector_ref=selector_ref,
                resolved_by_slug=resolved_by_slug,
            )
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="paper_states_loaded",
                outcome="loaded",
                detail=(
                    f"Resolved {len(matched_slugs)} paper slug(s) from the note selector; "
                    f"loaded {len(loaded_slugs)} new state(s) and reused {len(reused_slugs)} existing state(s)."
                ),
                source_item_id=selected_item.id,
                source_path=note_relpath,
                matched_paper_slugs=matched_slugs,
                metadata={
                    "loaded_slugs": loaded_slugs,
                    "reused_slugs": reused_slugs,
                },
            )
            continue

        if selector_type == "topic":
            selected_item = _build_source_item(
                item_id=f"src_{index:02d}",
                item_type=selector_type,
                ref=selector_ref,
                title=selector_ref,
                priority=4,
            )
            selected_items.append(selected_item)
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="selector_selected",
                outcome="selected",
                detail="Topic selector accepted for structured-signal matching.",
                source_item_id=selected_item.id,
            )
            matched_slugs = _resolve_topic_slugs(vault_path, selector_ref)
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="topic_matches_resolved",
                outcome="resolved",
                detail="Resolved topic selector from structured state signals only.",
                source_item_id=selected_item.id,
                matched_paper_slugs=matched_slugs,
            )
            matched_slugs, loaded_slugs, reused_slugs = _resolve_selector_slugs(
                vault_path=vault_path,
                slugs=matched_slugs,
                selector_type=selector_type,
                selector_ref=selector_ref,
                resolved_by_slug=resolved_by_slug,
            )
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="paper_states_loaded",
                outcome="loaded",
                detail=(
                    f"Resolved {len(matched_slugs)} paper slug(s) from structured topic signals; "
                    f"loaded {len(loaded_slugs)} new state(s) and reused {len(reused_slugs)} existing state(s)."
                ),
                source_item_id=selected_item.id,
                matched_paper_slugs=matched_slugs,
                metadata={
                    "loaded_slugs": loaded_slugs,
                    "reused_slugs": reused_slugs,
                },
            )
            continue

        if selector_type in {"project_profile", "research_profile"}:
            profile = _load_profile(selector_ref, profiles_path)
            selected_item = _build_source_item(
                item_id=f"src_{index:02d}",
                item_type=selector_type,
                ref=selector_ref,
                title=profile.title,
                priority=4,
            )
            selected_items.append(selected_item)
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="selector_selected",
                outcome="selected",
                detail="Projection-backed profile selector accepted.",
                source_item_id=selected_item.id,
            )
            matched_slugs = _resolve_projection_profile_slugs(
                vault_path=vault_path,
                profile=profile,
                research_dna_root=research_dna_root,
            )
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="projection_profile_resolved",
                outcome="resolved",
                detail="Resolved projection-backed profile selector to screened include-set paper slugs.",
                source_item_id=selected_item.id,
                matched_paper_slugs=matched_slugs,
                metadata={"profile_id": profile.id},
            )
            matched_slugs, loaded_slugs, reused_slugs = _resolve_selector_slugs(
                vault_path=vault_path,
                slugs=matched_slugs,
                selector_type=selector_type,
                selector_ref=selector_ref,
                resolved_by_slug=resolved_by_slug,
            )
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="paper_states_loaded",
                outcome="loaded",
                detail=(
                    f"Resolved {len(matched_slugs)} paper slug(s) from the profile selector; "
                    f"loaded {len(loaded_slugs)} new state(s) and reused {len(reused_slugs)} existing state(s)."
                ),
                source_item_id=selected_item.id,
                matched_paper_slugs=matched_slugs,
                metadata={
                    "loaded_slugs": loaded_slugs,
                    "reused_slugs": reused_slugs,
                    "profile_id": profile.id,
                },
            )
            continue

        if selector_type == "screening_decision":
            screening_context = _load_screening_context(
                vault_path=vault_path,
                selector_ref=selector_ref,
                item_id=f"src_{index:02d}",
                research_dna_root=research_dna_root,
            )
            selected_items.append(screening_context.source_item)
            screening_contexts.append(screening_context)
            _append_retrieval_trace(
                retrieval_trace,
                selector_type=selector_type,
                selector_ref=selector_ref,
                action="screening_context_loaded",
                outcome="loaded",
                detail="Loaded screening run context and mapped included candidates to structured paper slugs when available.",
                source_item_id=screening_context.source_item.id,
                matched_paper_slugs=screening_context.matched_paper_slugs,
                metadata={
                    "dna_id": screening_context.dna_id,
                    "run_id": screening_context.run_id,
                    "include_count": screening_context.include_count,
                    "exclude_count": screening_context.exclude_count,
                    "unclear_count": screening_context.unclear_count,
                    "top_reason_codes": screening_context.top_reason_codes,
                },
            )
            if screening_context.matched_paper_slugs:
                matched_slugs, loaded_slugs, reused_slugs = _resolve_selector_slugs(
                    vault_path=vault_path,
                    slugs=screening_context.matched_paper_slugs,
                    selector_type=selector_type,
                    selector_ref=selector_ref,
                    resolved_by_slug=resolved_by_slug,
                )
                _append_retrieval_trace(
                    retrieval_trace,
                    selector_type=selector_type,
                    selector_ref=selector_ref,
                    action="paper_states_loaded",
                    outcome="loaded",
                    detail=(
                        f"Resolved {len(matched_slugs)} included paper slug(s) from the screening selector; "
                        f"loaded {len(loaded_slugs)} new state(s) and reused {len(reused_slugs)} existing state(s)."
                    ),
                    source_item_id=screening_context.source_item.id,
                    matched_paper_slugs=matched_slugs,
                    metadata={
                        "loaded_slugs": loaded_slugs,
                        "reused_slugs": reused_slugs,
                        "dna_id": screening_context.dna_id,
                        "run_id": screening_context.run_id,
                    },
                )
            continue

        raise NotImplementedError(f"Meeting Pack source type not yet supported: {selector_type}")

    return ResolvedMeetingPackBundle(
        selected_items=selected_items,
        sources=list(resolved_by_slug.values()),
        screening_contexts=screening_contexts,
        retrieval_trace=retrieval_trace,
    )


def _resolve_selector_slugs(
    *,
    vault_path: Path,
    slugs: list[str],
    selector_type: str,
    selector_ref: str,
    resolved_by_slug: dict[str, ResolvedMeetingPackSource],
) -> tuple[list[str], list[str], list[str]]:
    matched_slugs: list[str] = []
    loaded_slugs: list[str] = []
    reused_slugs: list[str] = []
    seen_slugs: set[str] = set()
    for slug in slugs:
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        if slug in resolved_by_slug:
            matched_slugs.append(slug)
            reused_slugs.append(slug)
            continue
        try:
            source = _load_paper_source(
                vault_path,
                slug,
                paper_index=len(resolved_by_slug) + 1,
                reject_hidden_fixture=False,
            )
        except FileNotFoundError:
            continue
        resolved_by_slug[slug] = source
        matched_slugs.append(slug)
        loaded_slugs.append(slug)

    if not matched_slugs:
        raise FileNotFoundError(
            f"No structured paper states resolved from {selector_type}={selector_ref}"
        )
    return matched_slugs, loaded_slugs, reused_slugs


def _append_retrieval_trace(
    trace: list[MeetingPackRetrievalTraceEntry],
    *,
    selector_type: str,
    selector_ref: str,
    action: str,
    outcome: str,
    detail: str,
    source_item_id: str | None = None,
    source_path: str | None = None,
    matched_paper_slugs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    trace.append(
        MeetingPackRetrievalTraceEntry(
            order=len(trace) + 1,
            selector_type=selector_type,
            selector_ref=selector_ref,
            action=action,
            outcome=outcome,
            detail=detail,
            source_item_id=source_item_id,
            source_path=source_path,
            matched_paper_slugs=list(matched_paper_slugs or []),
            metadata=dict(metadata or {}),
        )
    )


def _load_paper_source(
    vault_path: Path,
    slug: str,
    *,
    paper_index: int,
    direct_source_item: MeetingPackSourceItem | None = None,
    reject_hidden_fixture: bool = True,
) -> ResolvedMeetingPackSource:
    state = _load_visible_structured_state(
        vault_path,
        slug,
        reject_hidden_fixture=reject_hidden_fixture,
    )
    if state is None:
        raise FileNotFoundError(f"Structured paper state not found for slug={slug}")

    source_item = direct_source_item or _build_source_item(
        item_id=f"paper_{paper_index:02d}",
        item_type="paper_state",
        ref=slug,
        title=_paper_title(vault_path, slug),
        priority=1,
    )
    return ResolvedMeetingPackSource(source_item=source_item, structured_state=state)


def _load_visible_structured_state(
    vault_path: Path,
    slug: str,
    *,
    reject_hidden_fixture: bool,
) -> StructuredPaperState | None:
    state = load_structured_state(vault_path, slug, None)
    if state is None:
        return None
    if is_test_fixture_structured_state(state) and not fixture_structured_state_allowed(vault_path):
        if reject_hidden_fixture:
            raise ValueError(
                f"Structured paper state for slug={slug} appears to be a test fixture and is hidden outside isolated E2E runtimes."
            )
        return None
    return state


def _load_screening_context(
    *,
    vault_path: Path,
    selector_ref: str,
    item_id: str,
    research_dna_root: Path | None,
) -> ResolvedMeetingPackScreeningContext:
    dna_id, run_id = _parse_screening_selector_ref(selector_ref)
    entries = _load_screening_entries(dna_id, research_dna_root)
    if not entries:
        raise FileNotFoundError(f"No screening entries found for dna_id={dna_id}")

    run_entries = [entry for entry in entries if entry.run_id == run_id]
    if not run_entries:
        raise FileNotFoundError(f"No screening entries found for dna_id={dna_id}, run_id={run_id}")

    include_count = sum(1 for entry in run_entries if entry.decision == "include")
    exclude_count = sum(1 for entry in run_entries if entry.decision == "exclude")
    unclear_count = sum(1 for entry in run_entries if entry.decision == "unclear")
    top_reason_codes = [
        code
        for code, _count in Counter(entry.reason_code for entry in run_entries).most_common(3)
    ]

    notes: list[str] = []
    matched_paper_slugs: list[str] = []
    for entry in run_entries:
        note = str(entry.note or "").strip()
        if note and note not in notes:
            notes.append(note)
        if entry.decision != "include":
            continue
        slug = _find_slug_by_candidate_id(vault_path, entry.candidate_id)
        if slug and slug not in matched_paper_slugs:
            matched_paper_slugs.append(slug)

    source_item = _build_source_item(
        item_id=item_id,
        item_type="screening_decision",
        ref=selector_ref,
        title=f"Screening {dna_id}:{run_id}",
        priority=4,
    )
    return ResolvedMeetingPackScreeningContext(
        source_item=source_item,
        dna_id=dna_id,
        run_id=run_id,
        include_count=include_count,
        exclude_count=exclude_count,
        unclear_count=unclear_count,
        top_reason_codes=top_reason_codes,
        notes=notes[:3],
        matched_paper_slugs=matched_paper_slugs,
    )


def _parse_screening_selector_ref(ref: str) -> tuple[str, str]:
    value = ref.strip()
    if not value:
        raise ValueError("screening_decision ref must not be empty")
    if ":" not in value:
        raise ValueError("screening_decision ref must be <dna_id>:<run_id>")
    dna_id, run_id = value.split(":", 1)
    if not dna_id.strip() or not run_id.strip():
        raise ValueError("screening_decision ref must be <dna_id>:<run_id>")
    return dna_id.strip(), run_id.strip()


def _load_screening_entries(
    dna_id: str,
    research_dna_root: Path | None,
) -> list[ScreeningLogEntry]:
    path = research_dna_log_path(dna_id, "screening", research_dna_root or default_research_dna_root())
    if not path.exists():
        raise FileNotFoundError(f"Screening log not found: {path}")

    entries: list[ScreeningLogEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        entries.append(ScreeningLogEntry.model_validate(sanitize_research_dna_log_payload(json.loads(text))))
    return entries


def _load_run_entries(
    dna_id: str,
    research_dna_root: Path | None,
) -> list[RunLogEntry]:
    path = research_dna_log_path(dna_id, "runs", research_dna_root or default_research_dna_root())
    if not path.exists():
        raise FileNotFoundError(f"Run log not found: {path}")

    entries: list[RunLogEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        entries.append(RunLogEntry.model_validate(sanitize_research_dna_log_payload(json.loads(text))))
    return entries


def _resolve_projection_profile_slugs(
    *,
    vault_path: Path,
    profile: Profile,
    research_dna_root: Path | None,
) -> list[str]:
    if not is_research_dna_projection_profile(profile):
        raise NotImplementedError(
            "Meeting Pack profile selectors currently support only ResearchDNA projection profiles."
        )

    metadata = parse_research_dna_projection_metadata(profile)
    if metadata is None:
        raise ValueError(f"Projection metadata missing or invalid for profile {profile.id}")

    dna_id = str(metadata.get("source_dna_id") or "").strip()
    query_version = str(metadata.get("source_query_version") or "").strip()
    if not dna_id or not query_version:
        raise ValueError(
            f"Projection profile {profile.id} must include source_dna_id and source_query_version metadata"
        )

    screening_entries = _load_screening_entries(dna_id, research_dna_root)
    run_entry = _select_projection_profile_run(
        dna_id=dna_id,
        query_version=query_version,
        run_entries=_load_run_entries(dna_id, research_dna_root),
        screening_entries=screening_entries,
    )
    include_entries = [
        entry for entry in screening_entries if entry.run_id == run_entry.run_id and entry.decision == "include"
    ]
    if not include_entries:
        raise FileNotFoundError(
            f"No included screening decisions found for profile-backed selector {profile.id} ({dna_id}:{query_version})"
        )

    matched_slugs: list[str] = []
    for entry in include_entries:
        slug = _find_slug_by_candidate_id(vault_path, entry.candidate_id)
        if slug and slug not in matched_slugs:
            matched_slugs.append(slug)
    if not matched_slugs:
        raise FileNotFoundError(
            "No structured paper states matched the included screening decisions for "
            f"profile-backed selector {profile.id} ({dna_id}:{run_entry.run_id})"
        )
    return matched_slugs


def _select_projection_profile_run(
    *,
    dna_id: str,
    query_version: str,
    run_entries: list[RunLogEntry],
    screening_entries: list[ScreeningLogEntry],
) -> RunLogEntry:
    latest_by_run: dict[str, RunLogEntry] = {}
    for entry in run_entries:
        if entry.query_version != query_version or entry.status not in {"completed", "partial"}:
            continue
        existing = latest_by_run.get(entry.run_id)
        if existing is None or entry.ts > existing.ts:
            latest_by_run[entry.run_id] = entry

    if not latest_by_run:
        raise FileNotFoundError(
            f"No completed projection-backed run found for dna_id={dna_id}, query_version={query_version}"
        )

    screened_run_ids = {entry.run_id for entry in screening_entries}
    candidates = [
        entry
        for entry in latest_by_run.values()
        if entry.run_id in screened_run_ids
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No screened run found for dna_id={dna_id}, query_version={query_version}"
        )

    candidates.sort(
        key=lambda entry: (
            entry.include_count > 0,
            entry.labeled_count > 0,
            entry.ts,
        ),
        reverse=True,
    )
    return candidates[0]


def _find_slug_by_candidate_id(vault_path: Path, candidate_id: str) -> str | None:
    target_variants = _identifier_variants(candidate_id)
    sidecar_root = vault_path / ".pp"
    if not sidecar_root.exists():
        return None

    for state_path in sorted(sidecar_root.glob("*/state.json")):
        slug = state_path.parent.name
        variants = {slug.lower()}
        note_path = resolve_note_path(vault_path, slug)
        if note_path is not None:
            frontmatter, _body = split_frontmatter(safe_read_text(note_path))
            for key in ("id", "doi"):
                variants.update(_identifier_variants(frontmatter.get(key)))
        if target_variants & variants:
            return slug
    return None


def _identifier_variants(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    variants = {text}
    if text.startswith("doi:"):
        variants.add(text.split(":", 1)[1].strip())
    if "doi.org/" in text:
        variants.add(text.split("doi.org/", 1)[1].strip("/"))
    if text.startswith("zotero:"):
        variants.add(text.split(":", 1)[1].strip())
    return {variant for variant in variants if variant}


def _build_source_item(
    *,
    item_id: str,
    item_type: str,
    ref: str,
    title: str,
    priority: int,
) -> MeetingPackSourceItem:
    return MeetingPackSourceItem(
        id=item_id,
        type=item_type,
        ref=ref,
        title=title,
        priority=priority,
        included=True,
    )


def _resolve_note_selector_path(vault_path: Path, ref: str) -> Path:
    direct_path = resolve_vault_relative_path(vault_path, ref)
    if direct_path is None:
        raise FileNotFoundError(f"Meeting Pack note source not found: {ref}")
    if direct_path.exists() and direct_path.is_file():
        return direct_path
    if not direct_path.suffix:
        markdown_path = direct_path.with_suffix(".md")
        if markdown_path.exists() and markdown_path.is_file():
            return markdown_path
    resolved = resolve_note_path(vault_path, Path(ref).stem)
    if resolved is None:
        raise FileNotFoundError(f"Meeting Pack note source not found: {ref}")
    return resolved


def _note_title(frontmatter: dict[str, Any], body: str, fallback: str) -> str:
    aliases = _to_str_list(frontmatter.get("aliases"))
    if aliases:
        return aliases[0]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return fallback


def _paper_title(vault_path: Path, slug: str) -> str:
    note_path = resolve_note_path(vault_path, slug)
    if note_path is None:
        return slug
    frontmatter, body = split_frontmatter(safe_read_text(note_path))
    return _note_title(frontmatter, body, slug)


def _extract_note_paper_slugs(frontmatter: dict[str, Any], body: str) -> list[str]:
    slugs: list[str] = []
    for key in ("paper_slugs", "papers", "related_papers"):
        for value in _to_str_list(frontmatter.get(key)):
            slug = Path(value).stem.strip()
            if slug and slug not in slugs:
                slugs.append(slug)
    for raw, _label in WIKILINK_PATTERN.findall(body or ""):
        slug = Path(raw).stem.strip()
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def _fallback_note_selector_slugs(
    *,
    vault_path: Path,
    note_path: Path,
    selector_type: str,
) -> list[str]:
    if selector_type != "paper_note":
        return []

    slug = note_path.stem.strip()
    if slug and _load_visible_structured_state(vault_path, slug, reject_hidden_fixture=False) is not None:
        return [slug]
    return []


def _resolve_topic_slugs(vault_path: Path, topic_ref: str) -> list[str]:
    topic_key = _normalize_topic_key(topic_ref)
    if not topic_key:
        raise ValueError("topic ref must contain at least one alphanumeric token")

    sidecar_root = vault_path / ".pp"
    if not sidecar_root.exists():
        return []

    matched: list[str] = []
    for state_path in sorted(sidecar_root.glob("*/state.json")):
        slug = state_path.parent.name
        state = _load_visible_structured_state(vault_path, slug, reject_hidden_fixture=False)
        if state is None:
            continue
        if topic_key in _structured_topic_signal_keys(vault_path, slug, state):
            matched.append(slug)
    return matched


def _structured_topic_signal_keys(
    vault_path: Path,
    slug: str,
    state: StructuredPaperState,
) -> set[str]:
    note_path = resolve_note_path(vault_path, slug)
    frontmatter: dict[str, Any] = {}
    if note_path is not None:
        frontmatter, _body = split_frontmatter(safe_read_text(note_path))

    values: list[str] = []
    values.extend(_to_str_list(frontmatter.get("tags")))
    values.extend(_to_str_list(frontmatter.get("topic")))
    values.extend(_to_str_list(frontmatter.get("topics")))
    values.extend(state.entities)
    values.extend(state.mesh)
    values.extend(state.outcomes)
    for claim in state.claimset:
        values.extend(claim.tags)
        values.extend(claim.outcomes)
    return {
        normalized
        for normalized in (_normalize_topic_key(value) for value in values)
        if normalized
    }


def _normalize_topic_key(value: Any) -> str:
    return " ".join(TOKEN_PATTERN.findall(str(value or "").strip().lower()))


def _load_profile(profile_id: str, profiles_path: Path | None = None) -> Profile:
    config = load_profiles(profiles_path)
    for profile in config.profiles:
        if profile.id == profile_id:
            return profile
    raise FileNotFoundError(f"Meeting Pack profile source not found: {profile_id}")


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("ref") or item.get("id") or "").strip()
            else:
                text = str(item).strip()
            if text:
                out.append(text)
        return out
    text = str(value).strip()
    return [text] if text else []
