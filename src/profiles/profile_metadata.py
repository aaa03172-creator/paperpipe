from __future__ import annotations

from typing import Any

import yaml

from src.profiles.profile_schema import Profile


RESEARCH_DNA_PROFILE_PREFIX = "research_dna_"
RESEARCH_DNA_PROJECTION_SCHEMA = "schema_version: research_dna.profile_projection.v1"


def is_research_dna_projection_profile(profile: Profile) -> bool:
    return (
        profile.id.startswith(RESEARCH_DNA_PROFILE_PREFIX)
        and bool(profile.notes)
        and RESEARCH_DNA_PROJECTION_SCHEMA in profile.notes
    )


def parse_research_dna_projection_metadata(profile: Profile) -> dict[str, Any] | None:
    if not is_research_dna_projection_profile(profile):
        return None
    notes = str(profile.notes or "").strip()
    if not notes:
        return None
    lines = notes.splitlines()
    if len(lines) < 2:
        return None
    payload = yaml.safe_load("\n".join(lines[1:])) or {}
    if not isinstance(payload, dict):
        return None
    return payload
