from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.schemas.skills import SkillActionName, SkillNetworkMode, SkillRunStatus


@dataclass(frozen=True)
class SkillActionDefinition:
    action: SkillActionName
    title: str
    button_label: str
    description: str
    source_skills: tuple[str, ...]


@dataclass(frozen=True)
class SkillActionPolicy:
    action: SkillActionName
    enabled: bool
    category: str
    source_skill: str
    license: str
    sandbox: str
    network: SkillNetworkMode
    network_allowlist: tuple[str, ...] = ()
    secrets_required: tuple[str, ...] = ()
    timeout_seconds: int = 30
    notes: str | None = None


@dataclass
class SkillHandlerResult:
    status: SkillRunStatus
    summary: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    signals: dict[str, Any] = field(default_factory=dict)
    claimset: list[dict[str, Any]] | None = None
    entities: list[str] | None = None
    mesh: list[str] | None = None
    outcomes: list[str] | None = None
    logs: list[str] = field(default_factory=list)


@dataclass
class NoteExecutionContext:
    slug: str
    note_path: Any
    vault_path: Any
    frontmatter: dict[str, Any]
    body: str
    config: Any
