from src.core.artifact_paths import (
    build_artifact_dir,
    build_legacy_paper_artifact_dir,
    resolve_existing_artifact_dir,
)


def test_resolve_existing_artifact_dir_prefers_paper_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "doi:10.1000/AbC"
    run_id = "run_1"

    key_dir = build_artifact_dir(run_id=run_id, paper_id=paper_id)
    legacy_dir = build_legacy_paper_artifact_dir(paper_id) / run_id
    key_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir.mkdir(parents=True, exist_ok=True)

    resolved = resolve_existing_artifact_dir(run_id=run_id, paper_id=paper_id)
    assert resolved == key_dir


def test_resolve_existing_artifact_dir_falls_back_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "doi:10.1000/legacy_only"
    run_id = "run_2"

    legacy_dir = build_legacy_paper_artifact_dir(paper_id) / run_id
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "claimset.json").write_text('{"claims":[]}', encoding="utf-8")

    resolved = resolve_existing_artifact_dir(run_id=run_id, paper_id=paper_id)
    assert resolved == legacy_dir
    assert (resolved / "claimset.json").exists()
