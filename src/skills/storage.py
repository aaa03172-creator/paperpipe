from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

from src.schemas.skills import SkillClaimCard, SkillRunRecord, StructuredPaperState


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
        if not path.is_file() or not is_candidate_markdown_for_paper_note(path, vault_path):
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
    signals: dict[str, Any] | None = None,
) -> StructuredPaperState:
    runs = [latest_run]
    if existing is not None:
        runs.extend(run for run in existing.runs if run.id != latest_run.id)
    runs = sorted(runs, key=lambda item: item.ts, reverse=True)

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

    base_claimset = existing.claimset if existing is not None else []
    resolved_claimset = claimset if claimset is not None else list(base_claimset)
    merged_signals = dict(existing.signals if existing is not None else {})
    merged_signals.update(
        {
            "has_claimset": bool(resolved_claimset),
            "claim_count": len(resolved_claimset),
            "evidence_count": sum(len(card.evidence) for card in resolved_claimset),
            "run_count": len(runs),
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
