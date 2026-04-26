from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

from src.schemas.skills import (
    build_section_signal_summary,
    ReadingAssistPayload,
    SkillClaimCard,
    SkillRunRecord,
    StructuredPaperState,
)
from src.services.fixture_visibility import visible_structured_state


AUTOMATION_HEADER = "## 🔧 Automation Results (short)"
AUTOMATION_SECTION_RE = re.compile(
    r"^## 🔧 Automation Results \(short\)\s*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
PAPER_NOTE_EXCLUDED_DIR_NAMES = {".obsidian", "_backup"}


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
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


def compose_note(frontmatter: dict[str, Any], body: str) -> str:
    rendered_frontmatter = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    cleaned_body = body.strip()
    if not rendered_frontmatter:
        return f"{cleaned_body}\n" if cleaned_body else ""
    if cleaned_body:
        return f"---\n{rendered_frontmatter}\n---\n\n{cleaned_body}\n"
    return f"---\n{rendered_frontmatter}\n---\n"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        handle.write(content)
        handle.flush()
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def resolve_note_path(vault_path: Path, slug: str) -> Path | None:
    exact = sorted(
        path
        for path in vault_path.rglob(f"{slug}.md")
        if path.is_file() and is_candidate_markdown_for_paper_note(path, vault_path)
    )
    if exact:
        return exact[0]
    for path in vault_path.rglob("*.md"):
        if not is_candidate_markdown_for_paper_note(path, vault_path):
            continue
        if path.stem == slug:
            return path
    legacy_structured_relpath = structured_relpath(slug)
    for path in vault_path.rglob("*.md"):
        if not path.is_file():
            continue
        if not is_candidate_markdown_for_paper_note(path, vault_path):
            continue
        frontmatter, _body = split_frontmatter(safe_read_text(path))
        pp = frontmatter.get("pp")
        if not isinstance(pp, dict):
            continue
        candidate = str(pp.get("structured_path") or "").strip()
        if candidate == legacy_structured_relpath:
            return path
    return None


def normalize_note_identifier(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return NON_ALNUM_RE.sub("", text)


def paper_id_lookup_variants(paper_id: str) -> list[str]:
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


def is_candidate_markdown_for_paper_note(path: Path, vault_path: Path) -> bool:
    try:
        relative = path.relative_to(vault_path)
    except ValueError:
        return False

    for part in relative.parts:
        if part in PAPER_NOTE_EXCLUDED_DIR_NAMES:
            return False
        if part.startswith("."):
            return False
    return True


def is_paper_note_candidate(frontmatter: dict[str, Any], relative_path: Path) -> bool:
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


def _paper_note_match_strength(
    *,
    slug: str,
    frontmatter: dict[str, Any],
    raw_variants: list[str],
    normalized_variants: set[str],
) -> int:
    candidates = (
        ("id", frontmatter.get("id")),
        ("doi", frontmatter.get("doi")),
        ("slug", slug),
    )
    best = 0
    for field, candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        if text in raw_variants:
            if field in {"id", "doi"}:
                best = max(best, 4)
            else:
                best = max(best, 3)
        normalized = normalize_note_identifier(text)
        if normalized and normalized in normalized_variants:
            if field in {"id", "doi"}:
                best = max(best, 2)
            else:
                best = max(best, 1)
    return best


def _paper_note_preference_score(
    *,
    vault_path: Path,
    note_path: Path,
    relative_path: Path,
    frontmatter: dict[str, Any],
) -> tuple[int, int, int]:
    structured_state = 1 if visible_structured_state(
        load_structured_state(vault_path, note_path.stem, frontmatter),
        vault_path=vault_path,
    ) is not None else 0
    metadata_score = sum(
        1
        for key in ("aliases", "tags", "date_processed", "confidence", "status", "doi")
        if frontmatter.get(key)
    )
    paperpipe_path = 1 if "paperpipe" in str(relative_path).lower() else 0
    return structured_state, paperpipe_path, metadata_score


def resolve_note_slug_by_paper_id(vault_path: Path, paper_id: str) -> str | None:
    raw_variants = paper_id_lookup_variants(paper_id)
    if not raw_variants:
        return None

    normalized_variants = {
        normalized
        for normalized in (normalize_note_identifier(value) for value in raw_variants)
        if normalized
    }
    markdown_paths = sorted(
        path
        for path in vault_path.rglob("*.md")
        if path.is_file() and is_candidate_markdown_for_paper_note(path, vault_path)
    )
    matches: list[tuple[int, int, int, int, str]] = []

    for note_path in markdown_paths:
        try:
            relative = note_path.relative_to(vault_path)
        except ValueError:
            continue
        frontmatter, _body = split_frontmatter(safe_read_text(note_path))
        if not is_paper_note_candidate(frontmatter, relative):
            continue
        match_strength = _paper_note_match_strength(
            slug=note_path.stem,
            frontmatter=frontmatter,
            raw_variants=raw_variants,
            normalized_variants=normalized_variants,
        )
        if match_strength <= 0:
            continue
        structured_state, paperpipe_path, metadata_score = _paper_note_preference_score(
            vault_path=vault_path,
            note_path=note_path,
            relative_path=relative,
            frontmatter=frontmatter,
        )
        matches.append(
            (
                match_strength,
                structured_state,
                paperpipe_path,
                metadata_score,
                note_path.stem,
            )
        )

    if not matches:
        return None

    matches.sort(key=lambda item: (-item[0], -item[1], -item[2], -item[3], item[4]))
    return matches[0][4]


def structured_relpath(slug: str) -> str:
    return f".pp/{slug}/state.json"


def structured_state_path(vault_path: Path, slug: str) -> Path:
    return vault_path / ".pp" / slug / "state.json"


def structured_run_path(vault_path: Path, slug: str, run_stamp: str, action: str) -> Path:
    return vault_path / ".pp" / slug / "runs" / f"{run_stamp}_{action}.json"


def load_structured_state(
    vault_path: Path,
    slug: str,
    frontmatter: dict[str, Any] | None = None,
) -> StructuredPaperState | None:
    rel_path = structured_relpath(slug)
    if isinstance(frontmatter, dict):
        pp = frontmatter.get("pp")
        if isinstance(pp, dict):
            candidate = str(pp.get("structured_path") or "").strip()
            if candidate:
                rel_path = candidate
    path = vault_path / rel_path
    if not path.exists():
        return None
    try:
        return StructuredPaperState.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def merge_state(
    slug: str,
    existing: StructuredPaperState | None,
    latest_run: SkillRunRecord,
    *,
    claimset: list[SkillClaimCard] | None = None,
    entities: list[str] | None = None,
    mesh: list[str] | None = None,
    outcomes: list[str] | None = None,
    reading_assists: list[ReadingAssistPayload] | None = None,
    signals: dict[str, Any] | None = None,
) -> StructuredPaperState:
    def _merge_values(current: list[str], update: list[str] | None) -> list[str]:
        merged: list[str] = []
        for item in current:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)
        for item in update or []:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)
        return merged

    def _merge_reading_assists(
        current: list[ReadingAssistPayload],
        update: list[ReadingAssistPayload] | None,
    ) -> list[ReadingAssistPayload]:
        merged_by_locale: dict[str, ReadingAssistPayload] = {}
        ordered_locales: list[str] = []

        def _store(payload: ReadingAssistPayload) -> None:
            locale = str(payload.locale).strip().lower()
            if not locale:
                return
            if locale not in merged_by_locale:
                ordered_locales.append(locale)
            merged_by_locale[locale] = payload

        for payload in current:
            _store(payload)
        for payload in update or []:
            _store(payload)
        return [merged_by_locale[locale] for locale in ordered_locales]

    base_claimset = existing.claimset if existing is not None else []
    resolved_claimset = claimset if claimset is not None else list(base_claimset)
    section_summary = build_section_signal_summary(resolved_claimset)
    latest_run_data = dict(latest_run.data)
    if section_summary:
        latest_run_data["section_summary"] = section_summary
        latest_run_data["section_count"] = len(section_summary)
    else:
        latest_run_data.pop("section_summary", None)
        latest_run_data.pop("section_count", None)
    latest_run = latest_run.model_copy(update={"data": latest_run_data})
    runs = [latest_run]
    if existing is not None:
        runs.extend(run for run in existing.runs if run.id != latest_run.id)
    runs = sorted(runs, key=lambda item: item.ts, reverse=True)
    resolved_reading_assists = _merge_reading_assists(
        existing.reading_assists if existing is not None else [],
        reading_assists,
    )
    reading_assist_locales = [payload.locale for payload in resolved_reading_assists if payload.blocks]
    merged_signals = dict(existing.signals if existing is not None else {})
    merged_signals.update(
        {
            "has_claimset": bool(resolved_claimset),
            "claim_count": len(resolved_claimset),
            "evidence_count": sum(len(card.evidence) for card in resolved_claimset),
            "run_count": len(runs),
            "section_count": len(section_summary),
            "has_reading_assists": bool(reading_assist_locales),
            "reading_assist_count": len(reading_assist_locales),
            "reading_assist_locales": reading_assist_locales,
            "last_run_id": latest_run.id,
            "last_action": latest_run.action,
            "last_status": latest_run.status,
        }
    )
    for key, value in (signals or {}).items():
        if value is None:
            continue
        merged_signals[key] = value

    return StructuredPaperState(
        paper_slug=slug,
        updated_at=datetime.now(timezone.utc).isoformat(),
        runs=runs,
        signals=merged_signals,
        claimset=resolved_claimset,
        entities=_merge_values(existing.entities if existing is not None else [], entities),
        mesh=_merge_values(existing.mesh if existing is not None else [], mesh),
        outcomes=_merge_values(existing.outcomes if existing is not None else [], outcomes),
        reading_assists=resolved_reading_assists,
    )


def update_frontmatter_pp(
    frontmatter: dict[str, Any],
    state: StructuredPaperState,
    latest_run: SkillRunRecord,
    *,
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = dict(frontmatter)
    current_pp = updated.get("pp")
    pp = dict(current_pp) if isinstance(current_pp, dict) else {}
    existing_actions = pp.get("actions_done")
    actions_done: list[str] = []
    if isinstance(existing_actions, list):
        for item in existing_actions:
            text = str(item).strip()
            if text and text not in actions_done:
                actions_done.append(text)
    if latest_run.action not in actions_done:
        actions_done.append(latest_run.action)

    current_signals = pp.get("signals")
    merged_signals = dict(current_signals) if isinstance(current_signals, dict) else {}
    for key, value in state.signals.items():
        if value is None:
            continue
        merged_signals[key] = value
    for key, value in (signals or {}).items():
        if value is None:
            continue
        merged_signals[key] = value

    pp["structured_path"] = structured_relpath(state.paper_slug)
    pp["last_run"] = latest_run.ts
    pp["actions_done"] = actions_done
    pp["signals"] = merged_signals
    updated["pp"] = pp
    return updated


def write_structured_state(path: Path, state: StructuredPaperState) -> None:
    atomic_write_text(path, state.model_dump_json(indent=2))


def normalize_link_url(url: str) -> str:
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


def extract_markdown_links(markdown: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for label, url in MARKDOWN_LINK_PATTERN.findall(markdown or ""):
        clean_label = label.strip()
        clean_url = normalize_link_url(url)
        if clean_label and clean_url:
            links.append((clean_label, clean_url))
    return links


def extract_reference_block(body: str) -> str:
    lines = body.splitlines()
    references: list[str] = []
    collecting = False
    level = 0
    for line in lines:
        match = HEADING_PATTERN.match(line.strip())
        if match:
            heading_level = len(match.group(1))
            heading_text = " ".join(re.sub(r"[^\w\s]", " ", match.group(2)).lower().split())
            if collecting and heading_level <= level:
                break
            if not collecting and "references" in heading_text:
                collecting = True
                level = heading_level
                references.append(line)
                continue
        if collecting:
            references.append(line)
    return "\n".join(references).strip()


def upsert_automation_results_section(body: str, entry_line: str, *, max_entries: int = 8) -> str:
    entry = entry_line.strip()
    if not entry.startswith("- "):
        entry = f"- {entry}"

    existing_entries: list[str] = []
    match = AUTOMATION_SECTION_RE.search(body)
    if match:
        section_lines = match.group(0).splitlines()[1:]
        existing_entries = [line.strip() for line in section_lines if line.strip().startswith("- ")]

    merged_entries = [entry]
    for line in existing_entries:
        if line != entry and line not in merged_entries:
            merged_entries.append(line)

    section = AUTOMATION_HEADER + "\n" + "\n".join(merged_entries[:max_entries]) + "\n"
    if match:
        replaced = body[: match.start()] + section + body[match.end() :]
        return replaced.strip() + "\n"

    base = body.strip()
    if not base:
        return section
    return f"{base}\n\n{section}"
