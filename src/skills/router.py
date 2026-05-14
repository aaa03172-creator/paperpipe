from __future__ import annotations

from src.schemas.skills import SkillRunRequest, SkillRunResponse
from src.skills.runner import run_skill_action


def dispatch_skill_action(request: SkillRunRequest) -> SkillRunResponse:
    return run_skill_action(request)
