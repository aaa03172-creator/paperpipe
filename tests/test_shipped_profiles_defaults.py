from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml(path: str):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_shipped_profiles_default_to_biomedical_general() -> None:
    data = _load_yaml("config/profiles.yaml")
    profiles = data["profiles"]

    enabled_profiles = [profile for profile in profiles if profile.get("enabled")]
    assert enabled_profiles
    assert enabled_profiles[0]["id"] == "biomedical_general"
    assert enabled_profiles[0]["title"] == "Biomedical General"

    neuro_profiles = [profile for profile in profiles if profile["id"] == "neuroscience_mechanism"]
    assert neuro_profiles
    assert neuro_profiles[0]["enabled"] is False
