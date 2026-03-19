from __future__ import annotations

from typing import Any

from .registry import list_available_actions


def run_skill_action(*args: Any, **kwargs: Any):
    from .runner import run_skill_action as _run_skill_action

    return _run_skill_action(*args, **kwargs)


__all__ = ["list_available_actions", "run_skill_action"]
