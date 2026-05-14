from __future__ import annotations

import os
from pathlib import Path

import yaml

from src.schemas.skills import SkillActionName, SkillNetworkMode
from src.skills.types import SkillActionPolicy


DEFAULT_POLICY_PATH = Path("config/skills_policy.yaml")


def resolve_skills_policy_path(policy_path: Path | str | None = None) -> Path:
    if policy_path is not None:
        return Path(policy_path)
    override_path = os.getenv("PAPERPIPE_SKILLS_POLICY_PATH")
    if override_path and override_path.strip():
        return Path(override_path)
    return DEFAULT_POLICY_PATH


def _normalize_string_list(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def load_skills_policy(policy_path: Path | str | None = None) -> dict[SkillActionName, SkillActionPolicy]:
    path = resolve_skills_policy_path(policy_path)
    if not path.exists():
        return {}

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = raw.get("defaults") if isinstance(raw, dict) else {}
    actions = raw.get("actions") if isinstance(raw, dict) else {}
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(actions, dict):
        actions = {}

    default_enabled = bool(defaults.get("enabled", True))
    default_timeout = int(defaults.get("timeout_seconds", 30))
    default_network = str(defaults.get("network", "none") or "none").strip().lower()
    default_sandbox = str(defaults.get("sandbox", "native") or "native").strip()

    resolved: dict[SkillActionName, SkillActionPolicy] = {}
    for action, payload in actions.items():
        if action not in {"extract_markdown", "validate_citations", "critical_appraisal"}:
            continue
        data = payload if isinstance(payload, dict) else {}
        network_value = str(data.get("network", default_network) or default_network).strip().lower()
        network: SkillNetworkMode = "none"
        if network_value in {"allowlist", "full"}:
            network = network_value
        resolved[action] = SkillActionPolicy(
            action=action,
            enabled=bool(data.get("enabled", default_enabled)),
            category=str(data.get("category", "core-safe") or "core-safe").strip(),
            source_skill=str(data.get("source_skill", "") or "").strip(),
            license=str(data.get("license", "Unknown") or "Unknown").strip(),
            sandbox=str(data.get("sandbox", default_sandbox) or default_sandbox).strip(),
            network=network,
            network_allowlist=_normalize_string_list(data.get("network_allowlist")),
            secrets_required=_normalize_string_list(data.get("secrets_required")),
            timeout_seconds=max(1, int(data.get("timeout_seconds", default_timeout))),
            notes=str(data.get("notes", "") or "").strip() or None,
        )
    return resolved


def get_action_policy(
    action: SkillActionName,
    policy_path: Path | str | None = None,
) -> SkillActionPolicy:
    policy = load_skills_policy(policy_path=policy_path)
    if action not in policy:
        raise KeyError(f"Action policy not found: {action}")
    return policy[action]
