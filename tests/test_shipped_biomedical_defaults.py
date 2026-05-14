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


def test_shipped_runtime_config_uses_biomedical_general_defaults() -> None:
    data = _load_yaml("config.yaml")

    assert data["paths"]["index_clinical"] == "00_Index/clinical_trials.csv"
    assert data["llm"]["features"]["clinical_extraction"]["enabled"] is True
    assert data["llm"]["features"]["specialty_trial_extraction"]["enabled"] is False
    assert "trial_extraction" not in data["llm"]["features"]

    mechanism_query = data["search"]["slots"]["mechanism"]["query"].lower()
    clinical_query = data["search"]["slots"]["clinical"]["query"].lower()
    methods_query = data["search"]["slots"]["methods"]["query"].lower()

    assert "microglia" not in mechanism_query
    assert "mild cognitive impairment" not in clinical_query
    assert "ketone" not in clinical_query
    assert "cre-loxp" not in methods_query
    assert "tamoxifen" not in methods_query
