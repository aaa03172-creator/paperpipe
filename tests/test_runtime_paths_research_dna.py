from src.services.runtime_paths import (
    artifact_paper_dir,
    artifact_run_dir,
    artifacts_root,
    config_file_path,
    paperpipe_home,
    profiles_config_path,
    research_dna_root,
    search_eval_root,
    state_db_path,
)
import src.services.runtime_paths as runtime_paths


def test_research_dna_root_defaults_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_RESEARCH_DNA_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_SEARCH_EVAL_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert research_dna_root() == (tmp_path / "research_dna").resolve()
    assert search_eval_root() == (tmp_path / "storage" / "search_eval").resolve()


def test_research_dna_and_search_eval_roots_respect_env_override(tmp_path, monkeypatch):
    dna_root = tmp_path / "custom_dna"
    eval_root = tmp_path / "custom_eval"

    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    monkeypatch.setenv("PAPERPIPE_SEARCH_EVAL_DIR", str(eval_root))

    assert research_dna_root() == dna_root.resolve()
    assert search_eval_root() == eval_root.resolve()


def test_profiles_config_path_respects_env_override(tmp_path, monkeypatch):
    profiles_path = tmp_path / "custom_profiles.yaml"
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
    assert profiles_config_path() == profiles_path.resolve()


def test_profiles_config_path_follows_config_override_workspace(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("system: {}\n", encoding="utf-8")
    derived_profiles = tmp_path / "config" / "profiles.yaml"
    derived_profiles.parent.mkdir(parents=True, exist_ok=True)
    derived_profiles.write_text("profiles: []\n", encoding="utf-8")

    monkeypatch.delenv("PAPERPIPE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    assert config_file_path() == config_path.resolve()
    assert profiles_config_path() == derived_profiles.resolve()


def test_artifacts_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_ARTIFACTS_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_HOME", raising=False)
    monkeypatch.chdir(tmp_path)

    assert artifacts_root() == (tmp_path / "storage" / "artifacts").resolve()


def test_storage_and_state_db_follow_install_layout_on_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_HOME", raising=False)
    monkeypatch.delenv("PAPERPIPE_STORAGE_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_DB_PATH", raising=False)
    monkeypatch.delenv("PAPERPIPE_ARTIFACTS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")

    install_root = tmp_path / "Library" / "Application Support" / "Lattice"
    assert runtime_paths.storage_root() == (install_root / "storage").resolve()
    assert state_db_path() == (install_root / "storage" / "state.db").resolve()
    assert artifacts_root() == (install_root / "storage" / "artifacts").resolve()


def test_artifact_paths_hash_unsafe_paper_ids_when_no_legacy_dir_exists(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))

    paper_id = "doi:10.1000/test"
    paper_dir = artifact_paper_dir(paper_id)
    run_dir = artifact_run_dir(paper_id, "run_001")

    assert paper_dir.parent == root.resolve()
    assert paper_dir.name.startswith("paper_")
    assert run_dir == paper_dir / "run_001"


def test_artifact_paths_prefer_existing_legacy_dirs_for_unsafe_paper_ids(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))

    legacy_run_dir = root / "doi:10.1000" / "test" / "run_legacy"
    legacy_run_dir.mkdir(parents=True, exist_ok=True)

    paper_id = "doi:10.1000/test"
    assert artifact_paper_dir(paper_id) == legacy_run_dir.parent.resolve()
    assert artifact_run_dir(paper_id, "run_legacy") == legacy_run_dir.resolve()


def test_artifact_paths_keep_preferring_legacy_when_hashed_dir_also_exists(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))

    paper_id = "doi:10.1000/test"
    legacy_run_dir = root / "doi:10.1000" / "test" / "run_legacy"
    hashed_run_dir = artifact_run_dir(paper_id, "run_hashed")
    legacy_run_dir.mkdir(parents=True, exist_ok=True)
    hashed_run_dir.mkdir(parents=True, exist_ok=True)

    assert artifact_paper_dir(paper_id) == legacy_run_dir.parent.resolve()
    assert artifact_run_dir(paper_id, "run_new") == legacy_run_dir.parent.resolve() / "run_new"


def test_artifact_paths_confine_traversal_like_paper_ids(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))

    paper_id = "../../outside"
    paper_dir = artifact_paper_dir(paper_id)
    run_dir = artifact_run_dir(paper_id, "run_001")

    assert paper_dir.parent == root.resolve()
    assert paper_dir.name.startswith("paper_")
    assert run_dir == paper_dir / "run_001"


def test_artifact_paths_confine_traversal_like_run_ids(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))

    run_dir = artifact_run_dir("paper_safe_001", "../../outside")

    assert run_dir.parent == root.resolve() / "paper_safe_001"
    assert run_dir.name.startswith("paper_")
    assert root.resolve() in run_dir.parents
