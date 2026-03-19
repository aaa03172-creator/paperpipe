from __future__ import annotations

import os

from src.schemas.skills import SkillActionInfo, SkillActionName
from src.skills.policy import load_skills_policy
from src.skills.types import SkillActionDefinition


ACTION_REGISTRY: dict[SkillActionName, SkillActionDefinition] = {
    "extract_markdown": SkillActionDefinition(
        action="extract_markdown",
        title="Extract Markdown",
        button_label="Extract Markdown",
        description="Generate a compact machine-readable extraction snapshot from the local paper source.",
        source_skills=("markitdown",),
    ),
    "validate_citations": SkillActionDefinition(
        action="validate_citations",
        title="Validate Citations",
        button_label="Validate Citations",
        description="Check DOI/Zotero/reference links and store citation signals for search and review.",
        source_skills=("citation-management", "pyzotero"),
    ),
    "critical_appraisal": SkillActionDefinition(
        action="critical_appraisal",
        title="Critical Appraisal",
        button_label="Critical Appraisal",
        description="Summarize ClaimSet evidence quality and verification health into card-ready structured output.",
        source_skills=("peer-review",),
    ),
}


def get_action_definition(action: SkillActionName) -> SkillActionDefinition:
    if action not in ACTION_REGISTRY:
        raise KeyError(f"Unknown skill action: {action}")
    return ACTION_REGISTRY[action]


def _format_missing_secret_reason(missing_secrets: tuple[str, ...]) -> str:
    if len(missing_secrets) == 1:
        return f"Blocked: missing required secret {missing_secrets[0]}."
    joined = ", ".join(missing_secrets)
    return f"Blocked: missing required secrets {joined}."


def _resolve_action_availability(enabled_by_policy: bool, secrets_required: tuple[str, ...], policy_notes: str | None) -> tuple[bool, str | None]:
    if not enabled_by_policy:
        return False, (policy_notes or "Blocked by project skills policy.")
    missing_secrets = tuple(secret for secret in secrets_required if not os.getenv(secret))
    if missing_secrets:
        return False, _format_missing_secret_reason(missing_secrets)
    return True, None


def list_available_actions() -> list[SkillActionInfo]:
    policy = load_skills_policy()
    actions: list[SkillActionInfo] = []
    for action, definition in ACTION_REGISTRY.items():
        action_policy = policy.get(action)
        secrets_required = tuple(action_policy.secrets_required) if action_policy else ()
        enabled, disabled_reason = _resolve_action_availability(
            bool(action_policy.enabled) if action_policy else False,
            secrets_required,
            action_policy.notes if action_policy else "Blocked by project skills policy.",
        )
        actions.append(
            SkillActionInfo(
                action=action,
                title=definition.title,
                button_label=definition.button_label,
                description=definition.description,
                source_skills=list(definition.source_skills),
                license=action_policy.license if action_policy else None,
                network=action_policy.network if action_policy else "none",
                sandbox=action_policy.sandbox if action_policy else None,
                secrets_required=list(secrets_required),
                enabled=enabled,
                disabled_reason=disabled_reason,
            )
        )
    return actions
