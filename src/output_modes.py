from __future__ import annotations

from typing import Literal


OutputModeFamily = Literal["learner", "lab_meeting", "project_update", "builder_debug"]
MeetingPackOutputMode = Literal[
    "journal_club",
    "literature_update",
    "project_progress_update",
    "experiment_proposal",
]
DEFAULT_CHAT_OUTPUT_MODE_FAMILY: OutputModeFamily = "learner"

MEETING_PACK_MODE_TO_OUTPUT_MODE_FAMILY: dict[MeetingPackOutputMode, OutputModeFamily] = {
    "journal_club": "lab_meeting",
    "literature_update": "lab_meeting",
    "project_progress_update": "project_update",
    "experiment_proposal": "builder_debug",
}


def resolve_meeting_pack_output_mode_family(
    mode: MeetingPackOutputMode,
    *,
    explicit_family: OutputModeFamily | None = None,
) -> OutputModeFamily:
    if explicit_family is not None:
        return explicit_family
    return MEETING_PACK_MODE_TO_OUTPUT_MODE_FAMILY[mode]


def resolve_chat_output_mode_family(
    explicit_family: OutputModeFamily | None = None,
) -> OutputModeFamily:
    if explicit_family is not None:
        return explicit_family
    return DEFAULT_CHAT_OUTPUT_MODE_FAMILY
