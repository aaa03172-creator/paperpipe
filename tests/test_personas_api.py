from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main


def _write_profiles(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_personas_lists_default_and_enabled_yaml_profiles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_profiles(
        tmp_path / "config" / "profiles.yaml",
        """
profiles:
  - id: mechanism
    title: Mechanism
    enabled: true
    schedule: daily
    query:
      must: ["microglia"]
      should: ["ASM"]
  - id: hidden
    title: Hidden
    enabled: false
    schedule: manual
    query:
      must: ["skip"]
defaults: {}
""".strip()
        + "\n",
    )

    client = TestClient(api_main.app)
    resp = client.get("/personas")
    assert resp.status_code == 200
    payload = resp.json()

    ids = [item["id"] for item in payload["personas"]]
    assert ids == ["default", "librarian", "researcher", "extractor_reviewer", "mechanism"]
    default = payload["personas"][0]
    assert default["kind"] == "compatibility"
    assert default["schedule"] is None
    assert default["query_focus"] is None
    librarian = next(item for item in payload["personas"] if item["id"] == "librarian")
    assert librarian["kind"] == "reasoning_persona"
    assert librarian["source"] == "builtin"
    mechanism = next(item for item in payload["personas"] if item["id"] == "mechanism")
    assert mechanism["kind"] == "profile"
    assert mechanism["schedule"] == "daily"
    assert mechanism["query_focus"] == "(microglia) AND (ASM)"
    assert mechanism["source"] == "yaml"


def test_personas_include_disabled_when_requested(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_profiles(
        tmp_path / "config" / "profiles.yaml",
        """
profiles:
  - id: enabled_profile
    title: Enabled
    enabled: true
    schedule: daily
    query:
      should: ["alpha"]
  - id: disabled_profile
    title: Disabled
    enabled: false
    schedule: manual
    query:
      should: ["beta"]
defaults: {}
""".strip()
        + "\n",
    )

    client = TestClient(api_main.app)
    resp = client.get("/personas", params={"include_disabled": "true"})
    assert resp.status_code == 200
    payload = resp.json()

    ids = [item["id"] for item in payload["personas"]]
    assert ids == [
        "default",
        "librarian",
        "researcher",
        "extractor_reviewer",
        "enabled_profile",
        "disabled_profile",
    ]
    disabled = next(item for item in payload["personas"] if item["id"] == "disabled_profile")
    assert disabled["kind"] == "profile"
    assert disabled["enabled"] is False
    assert disabled["schedule"] == "manual"
    assert disabled["query_focus"] == "(beta)"
