import json

from backend.routers import obsidian
from src.core.artifact_paths import build_artifact_dir, build_legacy_paper_artifact_dir


def test_load_artifact_prefers_paper_key_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "doi:10.1000/obsidian"
    run_id = "run_obsidian_1"

    key_file = build_artifact_dir(run_id=run_id, paper_id=paper_id) / "claimset.json"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(json.dumps({"doc_id": "from-key", "claims": []}), encoding="utf-8")

    legacy_file = build_legacy_paper_artifact_dir(paper_id) / run_id / "claimset.json"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text(json.dumps({"doc_id": "from-legacy", "claims": []}), encoding="utf-8")

    loaded = obsidian._load_artifact(paper_id=paper_id, run_id=run_id, filename="claimset.json")
    assert loaded["doc_id"] == "from-key"


def test_load_artifact_falls_back_to_legacy_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "doi:10.1000/obsidian_legacy"
    run_id = "run_obsidian_2"

    legacy_file = build_legacy_paper_artifact_dir(paper_id) / run_id / "claimset.json"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text(json.dumps({"doc_id": "from-legacy", "claims": []}), encoding="utf-8")

    loaded = obsidian._load_artifact(paper_id=paper_id, run_id=run_id, filename="claimset.json")
    assert loaded["doc_id"] == "from-legacy"
