from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
import json
import logging
import re
from pathlib import Path

from src.contracts.output_bridge import (
    bind_claim_cards_to_run,
    claim_cards_from_claimset_payload,
    normalize_claimset_payload,
)
from src.schemas.chat import ChatEvidenceRef, ChatLocator
from src.protocol_cards.renderer import render_protocol_card_markdown
from src.protocol_cards.store import (
    list_protocol_card_ids,
    load_protocol_card,
    load_protocol_card_markdown,
    load_protocol_version,
    load_protocol_versions,
    save_protocol_card_bundle,
)
from src.schemas.protocol_card import (
    ProtocolCard,
    ProtocolCardDraftRequest,
    ProtocolCardDraftResponse,
    ProtocolCardListResponse,
    ProtocolCardRequest,
    ProtocolCardResponse,
    ProtocolCardSummary,
    ProtocolDraftSourceSummary,
    ProtocolDraftWarning,
    ProtocolValidationStatus,
    ProtocolVersion,
    ProtocolVersionListResponse,
    build_protocol_version_summary,
    summarize_protocol_card,
)
from src.schemas.skills import SkillClaimCard
from src.services.fixture_visibility import visible_structured_state
from src.services.listing_resilience import load_available_items
from src.services.runtime_paths import artifact_paper_dir_candidates
from src.skills.storage import (
    load_structured_state,
    resolve_note_path,
    safe_read_text,
    split_frontmatter,
    structured_state_path,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProtocolCardResult:
    protocol_card: ProtocolCard
    versions: list[ProtocolVersion]
    markdown: str


@dataclass(frozen=True)
class ProtocolCardDraftResult:
    draft: ProtocolCardRequest
    source_summary: ProtocolDraftSourceSummary
    warnings: list[ProtocolDraftWarning]


_PROTOCOL_SECTION_KEYWORDS = (
    "materials and methods",
    "materials & methods",
    "experimental design",
    "study design",
    "procedure",
    "protocol",
    "methods",
    "method",
)
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")


def upsert_protocol_card(
    *,
    request: ProtocolCardRequest,
    root: Path | None = None,
    now: datetime | None = None,
) -> ProtocolCardResult:
    now = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    protocol_id = request.protocol_id or _new_protocol_id(request, now)
    versions = [
        ProtocolVersion(
            version_id=version.version_id or _new_version_id(protocol_id, version.version_number),
            protocol_id=protocol_id,
            version_number=version.version_number,
            key_steps_summary=list(version.key_steps_summary),
            materials=list(version.materials),
            equipment=list(version.equipment),
            critical_conditions=list(version.critical_conditions),
            readouts=list(version.readouts),
            cautions=list(version.cautions),
            content_snapshot=version.content_snapshot,
            change_reason=version.change_reason,
            status=version.status,
            created_by=version.created_by,
            created_at=version.created_at or now,
            source_refs=[ref.model_copy(deep=True) for ref in version.source_refs],
            note=version.note,
        )
        for version in request.versions
    ]
    current_version_id = _resolve_current_version_id(request.current_version_id, versions)
    protocol_card = ProtocolCard(
        protocol_id=protocol_id,
        title=request.title,
        purpose=request.purpose,
        context=request.context,
        source_kind=request.source_kind,
        linked_paper_ids=list(request.linked_paper_ids),
        linked_note_slugs=list(request.linked_note_slugs),
        current_version_id=current_version_id,
        validation_status=_resolve_validation_status(request.validation_status, versions),
        created_at=request.created_at or _resolve_created_at(versions, now),
        updated_at=request.updated_at or now,
        version_summaries=[build_protocol_version_summary(version) for version in versions],
    )
    markdown = render_protocol_card_markdown(protocol_card, versions)
    save_protocol_card_bundle(protocol_card, markdown, versions=versions, root=root)
    return ProtocolCardResult(protocol_card=protocol_card, versions=versions, markdown=markdown)


def get_protocol_card_bundle(protocol_id: str, *, root: Path | None = None) -> ProtocolCardResult:
    protocol_card = load_protocol_card(protocol_id, root)
    markdown = load_protocol_card_markdown(protocol_id, root)
    versions = load_protocol_versions(protocol_id, root)
    return ProtocolCardResult(protocol_card=protocol_card, versions=versions, markdown=markdown)


def list_protocol_card_summaries(*, root: Path | None = None) -> list[ProtocolCard]:
    items = load_available_items(
        list_protocol_card_ids(root),
        lambda protocol_id: load_protocol_card(protocol_id, root),
        item_kind="protocol card",
        logger=logger,
    )
    return sorted(items, key=lambda item: (item.updated_at, item.protocol_id), reverse=True)


def protocol_card_response_payload(result: ProtocolCardResult) -> ProtocolCardResponse:
    return ProtocolCardResponse(
        protocol_card=result.protocol_card,
        versions=result.versions,
        markdown=result.markdown,
    )


def protocol_card_list_response(*, root: Path | None = None) -> ProtocolCardListResponse:
    items: list[ProtocolCardSummary] = [
        summarize_protocol_card(protocol_card)
        for protocol_card in list_protocol_card_summaries(root=root)
    ]
    return ProtocolCardListResponse(items=items, total=len(items))


def protocol_version_list_response(protocol_id: str, *, root: Path | None = None) -> ProtocolVersionListResponse:
    load_protocol_card(protocol_id, root)
    items = load_protocol_versions(protocol_id, root)
    return ProtocolVersionListResponse(items=items, total=len(items))


def get_protocol_version_item(protocol_id: str, version_id: str, *, root: Path | None = None) -> ProtocolVersion:
    load_protocol_card(protocol_id, root)
    return load_protocol_version(protocol_id, version_id, root)


def build_protocol_card_draft_from_note(
    *,
    request: ProtocolCardDraftRequest,
    vault_path: Path,
    artifacts_root: Path | None = None,
) -> ProtocolCardDraftResult:
    resolved_vault = vault_path.expanduser().resolve()
    note_path = resolve_note_path(resolved_vault, request.note_slug)
    if note_path is None:
        raise FileNotFoundError(f"Paper note not found for protocol draft: note_slug={request.note_slug}")

    frontmatter, body = split_frontmatter(safe_read_text(note_path))
    structured_state = visible_structured_state(
        load_structured_state(resolved_vault, request.note_slug, frontmatter),
        vault_path=resolved_vault,
    )

    warnings: list[ProtocolDraftWarning] = []
    method_section = _extract_protocol_section(body)
    if method_section is None:
        warnings.append(
            ProtocolDraftWarning(
                code="METHOD_SECTION_MISSING",
                message="No dedicated methods/procedure heading was found in the note body; using a note excerpt fallback.",
            )
        )
    content_snapshot = method_section or _fallback_protocol_excerpt(body)
    if not content_snapshot:
        raise ValueError(f"Paper note {request.note_slug} does not contain enough markdown body content to draft a protocol.")

    title = _draft_title(frontmatter, body, request.note_slug)
    purpose = _draft_purpose(frontmatter, body, structured_state)
    linked_paper_id = _first_non_empty(request.paper_id, frontmatter.get("id"), frontmatter.get("paper_id"))
    run_id = _resolve_run_id(request.run_id, structured_state)

    claim_cards, claimset_found = _load_claim_cards_for_protocol_draft(
        note_slug=request.note_slug,
        linked_paper_id=linked_paper_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )
    if structured_state is None:
        warnings.append(
            ProtocolDraftWarning(
                code="STRUCTURED_STATE_MISSING",
                message="Structured paper state was not available; the draft is grounded only in the note body and any resolved claimset snapshot that could be found.",
            )
        )
    if run_id is not None and not claimset_found:
        warnings.append(
            ProtocolDraftWarning(
                code="CLAIMSET_MISSING",
                message="No resolved claimset snapshot was found for the selected note/run; source refs were built from the visible note state when possible.",
            )
        )

    visible_claim_cards = claim_cards or list(getattr(structured_state, "claimset", []) or [])
    source_refs = _build_protocol_source_refs(visible_claim_cards, paper_slug=request.note_slug)
    if not source_refs:
        source_refs = [ChatEvidenceRef(paper_slug=request.note_slug, run_id=run_id)]
        warnings.append(
            ProtocolDraftWarning(
                code="SOURCE_REFS_FALLBACK",
                message="No structured claim/evidence refs were available; the draft keeps only a note/run-level source reference.",
            )
        )

    key_steps_summary = _extract_key_steps(content_snapshot)
    if not key_steps_summary:
        warnings.append(
            ProtocolDraftWarning(
                code="KEY_STEPS_INFERRED",
                message="The draft could not infer clear step bullets from the source text; review the content snapshot before saving.",
            )
        )

    readouts = _unique_trimmed_strings(list(getattr(structured_state, "outcomes", []) or []))
    draft = ProtocolCardRequest(
        title=title,
        purpose=purpose,
        context=(
            f"Paper-derived protocol draft extracted from note {request.note_slug}. "
            "Review and edit before saving as a reusable protocol snapshot."
        ),
        source_kind="paper_derived",
        linked_paper_ids=[linked_paper_id] if linked_paper_id else [],
        linked_note_slugs=[request.note_slug],
        validation_status="unreviewed",
        versions=[
            {
                "version_number": 1,
                "key_steps_summary": key_steps_summary,
                "materials": [],
                "equipment": [],
                "critical_conditions": [],
                "readouts": readouts,
                "cautions": [],
                "content_snapshot": content_snapshot,
                "change_reason": "Initial paper-derived protocol draft extracted from note/runtime context.",
                "status": "draft",
                "created_by": "paper_derived_extractor",
                "source_refs": [ref.model_dump(exclude_none=True) for ref in source_refs],
                "note": f"Draft source note: {request.note_slug}",
            }
        ],
    )
    source_summary = ProtocolDraftSourceSummary(
        note_slug=request.note_slug,
        paper_id=linked_paper_id,
        note_path=_relative_to_root(note_path, resolved_vault),
        structured_state_path=(
            _relative_to_root(structured_state_path(resolved_vault, request.note_slug), resolved_vault)
            if structured_state is not None
            else None
        ),
        run_id=run_id,
        claim_count=len(visible_claim_cards),
        evidence_count=sum(len(card.evidence) for card in visible_claim_cards),
        used_note_body=True,
        used_structured_state=structured_state is not None,
        used_claimset=claimset_found,
    )
    return ProtocolCardDraftResult(
        draft=draft,
        source_summary=source_summary,
        warnings=warnings,
    )


def protocol_card_draft_response_payload(result: ProtocolCardDraftResult) -> ProtocolCardDraftResponse:
    return ProtocolCardDraftResponse(
        draft=result.draft,
        source_summary=result.source_summary,
        warnings=result.warnings,
    )


def _resolve_current_version_id(
    requested_current_version_id: str | None,
    versions: list[ProtocolVersion],
) -> str:
    if requested_current_version_id is not None:
        return requested_current_version_id
    active_versions = [version for version in versions if version.status == "active"]
    candidate_pool = active_versions or versions
    selected = max(candidate_pool, key=lambda item: (item.version_number, item.created_at, item.version_id))
    return selected.version_id


def _resolve_created_at(versions: list[ProtocolVersion], now: datetime) -> datetime:
    if not versions:
        return now
    return min(version.created_at for version in versions)


def _resolve_validation_status(
    requested_status: ProtocolValidationStatus,
    versions: list[ProtocolVersion],
) -> ProtocolValidationStatus:
    if requested_status != "unreviewed":
        return requested_status
    if any(version.status == "active" for version in versions):
        return "draft"
    return requested_status


def _new_protocol_id(request: ProtocolCardRequest, now: datetime) -> str:
    payload = request.model_dump(mode="json", exclude_none=True)
    digest = sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:8]
    return f"protocol_{now.strftime('%Y%m%dT%H%M%SZ')}_{digest}"


def _new_version_id(protocol_id: str, version_number: int) -> str:
    protocol_suffix = protocol_id.removeprefix("protocol_")
    safe_suffix = re.sub(r"[^A-Za-z0-9._-]+", "_", protocol_suffix).strip("._") or "protocol"
    return f"protver_{safe_suffix}_v{version_number}"


def _draft_title(frontmatter: dict[str, object], body: str, note_slug: str) -> str:
    frontmatter_title = str(frontmatter.get("title") or "").strip()
    if frontmatter_title:
        return f"{frontmatter_title} protocol draft"
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return f"{stripped[2:].strip()} protocol draft"
    return f"{note_slug} protocol draft"


def _draft_purpose(frontmatter: dict[str, object], body: str, structured_state) -> str | None:
    summary = str(frontmatter.get("summary") or "").strip()
    if summary:
        return summary
    outcomes = _unique_trimmed_strings(list(getattr(structured_state, "outcomes", []) or [])) if structured_state is not None else []
    if outcomes:
        return f"Track procedure context for: {', '.join(outcomes[:3])}"
    text = _first_meaningful_sentence(body)
    if text:
        return text
    return None


def _resolve_run_id(requested_run_id: str | None, structured_state) -> str | None:
    if requested_run_id:
        return requested_run_id
    if structured_state is None:
        return None
    signal_run_id = str(getattr(structured_state, "signals", {}).get("last_run_id") or "").strip()
    if signal_run_id:
        return signal_run_id
    runs = list(getattr(structured_state, "runs", []) or [])
    if not runs:
        return None
    return str(getattr(runs[0], "id", "") or "").strip() or None


def _load_claim_cards_for_protocol_draft(
    *,
    note_slug: str,
    linked_paper_id: str | None,
    run_id: str | None,
    artifacts_root: Path | None = None,
) -> tuple[list[SkillClaimCard], bool]:
    if not run_id:
        return [], False
    root_path = artifacts_root.expanduser().resolve() if artifacts_root is not None else None
    paper_id_candidates = _unique_trimmed_strings([linked_paper_id, note_slug])
    for paper_id in paper_id_candidates:
        for paper_dir in artifact_paper_dir_candidates(paper_id, root=root_path):
            run_dir = paper_dir / run_id
            claimset_path = run_dir / "claimset.resolved.json"
            if not claimset_path.exists():
                continue
            try:
                payload = json.loads(claimset_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise ValueError(f"Failed to parse resolved claimset for protocol draft: {claimset_path}: {exc}") from exc
            normalized = normalize_claimset_payload(payload)
            if normalized is None:
                raise ValueError(f"Resolved claimset payload is missing a claims array: {claimset_path}")
            return bind_claim_cards_to_run(claim_cards_from_claimset_payload(normalized), run_id), True
    return [], False


def _extract_protocol_section(body: str) -> str | None:
    lines = body.splitlines()
    active_level: int | None = None
    collecting = False
    collected: list[str] = []
    for line in lines:
        match = _MARKDOWN_HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            heading = _normalize_heading(match.group(2))
            if collecting and active_level is not None and level <= active_level:
                break
            if _looks_like_protocol_heading(heading):
                collecting = True
                active_level = level
                collected = []
                continue
        if collecting:
            collected.append(line)
    rendered = "\n".join(collected).strip()
    return rendered or None


def _looks_like_protocol_heading(heading: str) -> bool:
    return any(keyword in heading for keyword in _PROTOCOL_SECTION_KEYWORDS)


def _normalize_heading(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _fallback_protocol_excerpt(body: str, *, max_chars: int = 1600) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return ""
    excerpt_parts: list[str] = []
    total = 0
    for line in lines:
        if line.startswith("#"):
            continue
        next_total = total + len(line) + (1 if excerpt_parts else 0)
        if next_total > max_chars:
            break
        excerpt_parts.append(line)
        total = next_total
    return "\n".join(excerpt_parts).strip()


def _extract_key_steps(content_snapshot: str, *, max_items: int = 6) -> list[str]:
    steps: list[str] = []
    for raw_line in content_snapshot.splitlines():
        match = _LIST_ITEM_RE.match(raw_line)
        candidate = match.group(1).strip() if match else ""
        if candidate and candidate not in steps:
            steps.append(candidate)
        if len(steps) >= max_items:
            return steps

    sentence_candidates = re.split(r"(?:\.\s+|\n+)", content_snapshot)
    for sentence in sentence_candidates:
        normalized = " ".join(sentence.strip().split())
        if len(normalized) < 20:
            continue
        if normalized not in steps:
            steps.append(normalized)
        if len(steps) >= max_items:
            break
    return steps


def _build_protocol_source_refs(claim_cards: list[SkillClaimCard], *, paper_slug: str, max_items: int = 8) -> list[ChatEvidenceRef]:
    refs: list[ChatEvidenceRef] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for card in claim_cards:
        claim_id = card.source_claim_id or card.id
        evidence_entries = list(card.evidence or [])
        if not evidence_entries:
            key = (paper_slug, claim_id, None, card.run_id)
            if key in seen:
                continue
            refs.append(
                ChatEvidenceRef(
                    paper_slug=paper_slug,
                    claim_id=claim_id,
                    run_id=card.run_id,
                )
            )
            seen.add(key)
        for evidence in evidence_entries[:1]:
            locator = (
                ChatLocator.model_validate(evidence.locator.model_dump(exclude_none=True))
                if evidence.locator is not None
                else None
            )
            key = (paper_slug, claim_id, evidence.id, card.run_id)
            if key in seen:
                continue
            refs.append(
                ChatEvidenceRef(
                    paper_slug=paper_slug,
                    claim_id=claim_id,
                    evidence_id=evidence.id,
                    run_id=card.run_id,
                    locator=locator,
                )
            )
            seen.add(key)
            if len(refs) >= max_items:
                return refs
    return refs


def _first_meaningful_sentence(body: str) -> str | None:
    for sentence in re.split(r"(?:\.\s+|\n+)", body):
        normalized = " ".join(sentence.strip().split())
        if len(normalized) >= 24 and not normalized.startswith("#"):
            return normalized
    return None


def _unique_trimmed_strings(values: list[object]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            items.append(text)
            seen.add(text)
    return items


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
