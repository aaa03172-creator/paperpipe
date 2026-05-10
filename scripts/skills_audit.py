#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "skills_policy.yaml"
SOURCE_ROOT = ROOT / "rules" / "scientific-skills" / "scientific-skills"
OUTPUT_PATH = ROOT / "docs" / "SKILLS_AUDIT.md"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def load_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def parse_skill_metadata(skill_dir: Path) -> dict[str, str]:
    skill_path = skill_dir / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.search(content)
    metadata = {}
    if match:
        try:
            metadata = yaml.safe_load(match.group(1)) or {}
        except Exception:
            metadata = {}
    description = str(metadata.get("description", "") or "").strip().replace("\n", " ")
    return {
        "name": str(metadata.get("name", skill_dir.name) or skill_dir.name).strip(),
        "license": str(metadata.get("license", "Unknown") or "Unknown").strip(),
        "description": description[:140],
    }


def main() -> int:
    if not SOURCE_ROOT.exists():
        print(f"missing source root: {SOURCE_ROOT}", file=sys.stderr)
        return 1

    policy = load_policy()
    installed = {
        str(item).strip()
        for item in policy.get("project_scoped_skills", []) or []
        if str(item).strip()
    }
    action_map = {}
    for action, payload in (policy.get("actions", {}) or {}).items():
        if not isinstance(payload, dict):
            continue
        action_map[str(payload.get("source_skill", "")).strip()] = action

    rows: list[dict[str, str]] = []
    for skill_dir in sorted(path for path in SOURCE_ROOT.iterdir() if path.is_dir()):
        meta = parse_skill_metadata(skill_dir)
        meta["status"] = "project-scoped" if meta["name"] in installed else "not-installed"
        meta["action"] = action_map.get(meta["name"], "")
        rows.append(meta)

    lines = [
        "# Skills Audit",
        "",
        "Status: Generated audit report",
        "Date: 2026-03-09",
        "Owner: Skills maintainers",
        "Canonical: `docs/SKILLS_AUDIT.md`",
        "Canonical parent: `config/skills_policy.yaml`",
        "",
        f"- Source root: `{SOURCE_ROOT.relative_to(ROOT)}`",
        f"- Policy: `{POLICY_PATH.relative_to(ROOT)}`",
        f"- Project-scoped skills: {len(installed)}",
        f"- Total audited skills: {len(rows)}",
        "",
        "| Skill | Status | Action | License | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        notes = row["description"].replace("|", "/")
        lines.append(
            f"| `{row['name']}` | {row['status']} | `{row['action'] or '-'}` | {row['license']} | {notes or '-'} |"
        )

    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
