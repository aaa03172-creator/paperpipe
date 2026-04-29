import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli
import src.downloads_watcher as downloads_watcher_module
import src.watcher as watcher_module


def test_watch_fails_fast_when_watchdog_missing(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: False)

    result = runner.invoke(cli.app, ["watch"])

    assert result.exit_code == 1
    assert "watcher dependency missing" in result.output.lower()
    assert "watch" in result.output


def test_watch_downloads_fails_fast_when_watchdog_missing(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: False)

    result = runner.invoke(cli.app, ["watch-downloads"])

    assert result.exit_code == 1
    assert "watcher dependency missing" in result.output.lower()
    assert "watch-downloads" in result.output


def test_watch_downloads_bootstraps_database_and_uses_downloads_watcher(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    captured: dict[str, object] = {}
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            downloads_watch_dir=tmp_path / "Downloads",
            pdf_storage_dir=tmp_path / "storage" / "pdfs",
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)

    def _bootstrap():
        captured["bootstrapped"] = True
        return tmp_path / "state.db"

    class _FakeDownloadsWatcherService:
        def __init__(self, downloads_watch_dir, pdf_storage_dir, title_threshold):
            captured["downloads_watch_dir"] = downloads_watch_dir
            captured["pdf_storage_dir"] = pdf_storage_dir
            captured["title_threshold"] = title_threshold

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(cli, "bootstrap_database", _bootstrap)
    monkeypatch.setattr(downloads_watcher_module, "DownloadsWatcherService", _FakeDownloadsWatcherService)

    result = runner.invoke(cli.app, ["watch-downloads"])

    assert result.exit_code == 0
    assert captured["bootstrapped"] is True
    assert captured["downloads_watch_dir"] == fake_config.paths.downloads_watch_dir
    assert captured["pdf_storage_dir"] == fake_config.paths.pdf_storage_dir
    assert captured["title_threshold"] == 0.90
    assert captured["started"] is True


def test_watch_downloads_fails_fast_when_downloads_watch_dir_overlaps_pdf_storage_dir(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    storage_dir = tmp_path / "storage" / "pdfs"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            downloads_watch_dir=storage_dir / "incoming",
            pdf_storage_dir=storage_dir,
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")

    result = runner.invoke(cli.app, ["watch-downloads"])

    assert result.exit_code == 1
    assert "downloads watch folder conflicts with managed output paths" in result.output.lower()
    assert "overlap" in result.output.lower()
    assert "pdf_storage_dir" in result.output


def test_watch_bootstraps_database_and_uses_watcher_module(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    captured: dict[str, object] = {}
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            watch_folder=tmp_path / "watch-folder",
            upload_dir=tmp_path / "uploads",
            pdf_storage_dir=tmp_path / "pdfs",
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)

    def _bootstrap():
        captured["bootstrapped"] = True
        return tmp_path / "state.db"

    class _FakeWatcherService:
        def __init__(self, config):
            captured["config"] = config

        def start(self, processor):
            captured["processor"] = processor

    monkeypatch.setattr(cli, "bootstrap_database", _bootstrap)
    monkeypatch.setattr(watcher_module, "WatcherService", _FakeWatcherService)

    result = runner.invoke(cli.app, ["watch"])

    assert result.exit_code == 0
    assert captured["bootstrapped"] is True
    assert captured["config"] is fake_config
    assert captured["processor"] is watcher_module


def test_watch_fails_fast_when_watch_folder_matches_upload_dir(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    shared = tmp_path / "shared"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            watch_folder=shared,
            upload_dir=shared,
            pdf_storage_dir=tmp_path / "pdfs",
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")

    result = runner.invoke(cli.app, ["watch"])

    assert result.exit_code == 1
    assert "watch folder conflicts with managed output paths" in result.output.lower()
    assert "upload_dir" in result.output


def test_watch_fails_fast_when_watch_folder_matches_pdf_storage_dir(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    shared = tmp_path / "shared"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            watch_folder=shared,
            upload_dir=tmp_path / "uploads",
            pdf_storage_dir=shared,
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")

    result = runner.invoke(cli.app, ["watch"])

    assert result.exit_code == 1
    assert "watch folder conflicts with managed output paths" in result.output.lower()
    assert "pdf_storage_dir" in result.output


def test_watch_fails_fast_when_watch_folder_contains_upload_dir(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    watch_folder = tmp_path / "watch-root"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            watch_folder=watch_folder,
            upload_dir=watch_folder / "uploads",
            pdf_storage_dir=tmp_path / "pdfs",
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")

    result = runner.invoke(cli.app, ["watch"])

    assert result.exit_code == 1
    assert "watch folder conflicts with managed output paths" in result.output.lower()
    assert "overlap" in result.output.lower()
    assert "upload_dir" in result.output


def test_watch_fails_fast_when_watch_folder_is_nested_under_pdf_storage_dir(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    pdf_storage_dir = tmp_path / "pdfs"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            watch_folder=pdf_storage_dir / "incoming",
            upload_dir=tmp_path / "uploads",
            pdf_storage_dir=pdf_storage_dir,
        )
    )

    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")

    result = runner.invoke(cli.app, ["watch"])

    assert result.exit_code == 1
    assert "watch folder conflicts with managed output paths" in result.output.lower()
    assert "overlap" in result.output.lower()
    assert "pdf_storage_dir" in result.output


def test_doctor_reports_missing_watchdog(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="cloud"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: False)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="degraded", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Watchdog: ❌ Missing" in result.output
    assert "Runtime is usable, but there are warnings to clean up." in result.output
    assert "All systems go!" not in result.output


def test_doctor_fix_creates_starter_config_and_safe_local_directories(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "storage" / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path / "logs")
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="ok", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "storage" / "state.db")),
    )

    result = runner.invoke(cli.app, ["doctor", "--fix"])

    assert result.exit_code == 0
    assert "Created starter config:" in result.output
    assert "Created Obsidian Vault: storage/obsidian_vault" in result.output
    assert "Created Watch Folder: storage/watch" in result.output
    assert (tmp_path / "config" / "config.yaml").exists()
    assert (tmp_path / "storage" / "obsidian_vault").is_dir()
    assert (tmp_path / "storage" / "watch").is_dir()
    assert (tmp_path / "storage" / "pdfs").is_dir()


def test_doctor_fix_skips_external_missing_paths(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    external_vault = tmp_path.parent / f"{tmp_path.name}_external_vault"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path / "storage" / "zotero",
            obsidian_vault=external_vault,
            upload_dir=tmp_path / "storage" / "uploads",
            export_dir=tmp_path / "export",
            watch_folder=tmp_path / "storage" / "watch",
            library_dir=tmp_path / "Library",
            pdf_storage_dir=tmp_path / "storage" / "pdfs",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="cloud", cloud=SimpleNamespace(provider="openai")),
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_ensure_starter_config", lambda: ["Config already exists: test"])
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "storage" / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path / "logs")
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="ok", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "storage" / "state.db")),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = runner.invoke(cli.app, ["doctor", "--fix"])

    assert result.exit_code == 0
    assert "Skipped Obsidian Vault: outside project-managed paths" in result.output
    assert not external_vault.exists()
    assert (tmp_path / "storage" / "watch").is_dir()


def test_doctor_reports_anthropic_cloud_key(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="cloud", cloud=SimpleNamespace(provider="anthropic")),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: False)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="degraded", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test-key")

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Anthropic API Key detected." in result.output
    assert "OpenAI API Key detected." not in result.output


def test_doctor_reports_watch_boundary_warning(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(
            status="degraded",
            checks=[
                SimpleNamespace(
                    name="watch_folder_boundary",
                    status="warn",
                    detail="watch folder overlaps managed output paths; `paperpipe watch` will fail until this is separated: pdf_storage_dir=/tmp/storage/pdfs",
                    path=str(tmp_path / "watch-folder"),
                ),
                SimpleNamespace(
                    name="downloads_watch_dir_boundary",
                    status="ok",
                    detail="downloads watch folder does not overlap PDF storage",
                    path=str(tmp_path / "Downloads"),
                ),
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Watch Folder Boundary: ⚠️ watch folder overlaps managed output paths" in result.output
    assert "Downloads Watch Boundary:" in result.output
    assert "First paper path" in result.output
    assert "Web import: http://127.0.0.1:8000/ui/papers#import-pdf" in result.output
    assert "CLI import: paperpipe import-pdf path/to/paper.pdf" in result.output
    assert "Automatic pickup: use Import PDF first; fix pickup setup later from /ready." in result.output
    assert "Runtime is usable, but there are warnings to clean up." in result.output


def test_doctor_reports_hidden_fixture_structured_state_warning(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="degraded", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(
            status="warn",
            detail="hidden fixture structured states detected (1): .pp/fixture-note/state.json",
            path=str(tmp_path / ".pp" / "fixture-note" / "state.json"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Structured State Hygiene: ⚠️ hidden fixture structured states detected" in result.output
    assert "Runtime is usable, but there are warnings to clean up." in result.output


def test_doctor_reports_meeting_pack_storage_hygiene_warning(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="degraded", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(
            status="warn",
            detail="Meeting Pack archive candidates detected (2; fixture_like_pack=1, superseded_by_recent_healthy_pack=1)",
            path=str(tmp_path / "storage" / "meeting_packs"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Meeting Pack Storage Hygiene: ⚠️ Meeting Pack archive candidates detected" in result.output
    assert "Runtime is usable, but there are warnings to clean up." in result.output


def test_doctor_reports_fixture_paper_hygiene_warning(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="degraded", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(
            status="warn",
            detail=(
                "fixture paper cleanup candidates detected (2; fixture_visibility_rule=1, paper_id_test_prefix=1); "
                "archive with `paperpipe archive-fixture-no-feedback-papers` before trusting local classification-audit counts: "
                "paper-e2e-001, test_local_id"
            ),
            path=str(tmp_path / "state.db"),
        ),
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Fixture Paper Hygiene: ⚠️ fixture paper cleanup candidates detected" in result.output
    assert "archive-fixture-no-feedback-papers" in result.output
    assert "Runtime is usable, but there are warnings to clean up." in result.output


def test_doctor_reports_cli_entrypoint_warning(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(
            status="degraded",
            checks=[
                SimpleNamespace(
                    name="cli_entrypoint",
                    status="warn",
                    detail="CLI entrypoint smoke skipped: no repo-local or packaged launcher detected",
                    path=None,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "CLI Entrypoint: ⚠️ CLI entrypoint smoke skipped" in result.output
    assert "Runtime is usable, but there are warnings to clean up." in result.output


def test_doctor_reports_latest_intake_override_audit_hint(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )
    latest_run = tmp_path / "snapshots" / "intake_override_audits" / "intake_override_audit_latest"
    latest_run.mkdir(parents=True, exist_ok=True)
    latest_threshold_review_run = (
        tmp_path / "snapshots" / "intake_override_threshold_review" / "intake_override_audit_latest__threshold_review"
    )
    latest_threshold_review_run.mkdir(parents=True, exist_ok=True)
    (latest_threshold_review_run / "summary.json").write_text(
        json.dumps(
            {
                "schema_version": "intake_override_threshold_review.v1",
                "generated_at": "2026-04-21T00:00:00Z",
                "run_id": "intake_override_audit_latest__threshold_review",
                "decision": {
                    "recommended_action": "hold_current_threshold",
                    "review_ready": False,
                    "decision_reason": "only 1 sufficiently-audited run(s) exist, below the 3-run review floor; persistent adjudication signals: slot_adjudication, tagging_adjudication",
                    "next_step": "collect_more_audit_runs",
                    "focus_signals": ["slot_adjudication", "slot", "triage", "tagging_adjudication"],
                    "latest_run_id": "intake_override_audit_latest",
                    "latest_run_status": "warn",
                    "latest_warn_signals": ["triage", "slot", "slot_adjudication", "tagging_adjudication"],
                    "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                    "blocking_action": {
                        "order": 1,
                        "action": "collect_more_audit_runs",
                        "target": None,
                        "blocking": True,
                        "signals": [],
                        "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                        "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                    },
                    "tuning_targets": ["slot_classification", "tagging_first_pass"],
                    "tuning_actions": [
                        {
                            "target": "slot_classification",
                            "action": "audit_slot_ambiguity_thresholds",
                            "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                        },
                        {
                            "target": "tagging_first_pass",
                            "action": "audit_tagging_first_pass_quality",
                            "summary": "Inspect first-pass tagging robustness, soft-tag formatting, and evidence-span quality before policy changes.",
                        },
                    ],
                    "action_plan": [
                        {
                            "order": 1,
                            "action": "collect_more_audit_runs",
                            "target": None,
                            "blocking": True,
                            "signals": [],
                            "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                            "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                        },
                        {
                            "order": 2,
                            "action": "audit_slot_ambiguity_thresholds",
                            "target": "slot_classification",
                            "blocking": False,
                            "signals": ["slot_adjudication"],
                            "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                            "evidence": "Triggered because slot adjudication remains present in the threshold-review focus/latest-warn signals, which points to slot-classification ambiguity rather than a pure threshold-only issue.",
                        },
                        {
                            "order": 3,
                            "action": "audit_tagging_first_pass_quality",
                            "target": "tagging_first_pass",
                            "blocking": False,
                            "signals": ["tagging_adjudication"],
                            "summary": "Inspect first-pass tagging robustness, soft-tag formatting, and evidence-span quality before policy changes.",
                            "evidence": "Triggered because tagging adjudication remains present in the threshold-review focus/latest-warn signals, which points to first-pass tagging robustness rather than a pure threshold-only issue.",
                        },
                    ],
                    "tuning_recommendations": [
                        "Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy.",
                        "Audit first-pass tagging robustness, soft-tag formatting, and evidence-span quality before changing warning-threshold heuristics.",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    (latest_threshold_review_run / "audit.md").write_text(
        "# threshold review markdown\n",
        encoding="utf-8",
    )
    latest_processor_gate_threshold_review_run = (
        tmp_path / "snapshots" / "processor_gate_threshold_review" / "processor_gate_threshold_review_latest"
    )
    latest_processor_gate_threshold_review_run.mkdir(parents=True, exist_ok=True)
    replay_drift_run = (
        tmp_path / "snapshots" / "processor_gate_replay_drift" / "processor_gate_replay_drift_preapply_20260421_r11"
    )
    replay_drift_run.mkdir(parents=True, exist_ok=True)
    (replay_drift_run / "summary.json").write_text("{}\n", encoding="utf-8")
    (replay_drift_run / "details.json").write_text("{}\n", encoding="utf-8")
    (replay_drift_run / "audit.md").write_text("# replay drift markdown\n", encoding="utf-8")
    (replay_drift_run / "threshold_replay.json").write_text(
        json.dumps(
            {
                "threshold_replay_mode": "threshold_change_proposal_replay",
                "high_threshold": 0.85,
                "low_threshold": 0.7,
                "reviewed_high_threshold": 0.85,
                "proposal_run_id": "gate_threshold_review_ready",
                "threshold_review_command": (
                    "python3 scripts/eval/recommend_processor_gate_threshold_review.py "
                    "--drift-summary summary.json --run-id validation__threshold_review"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (replay_drift_run / "threshold_replay.md").write_text(
        "# threshold replay context\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "summary.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_threshold_review.v1",
                "generated_at": "2026-04-21T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "inputs": {
                    "drift_summary_path": str(replay_drift_run / "summary.json"),
                    "drift_details_path": str(replay_drift_run / "details.json"),
                    "high_threshold": 0.9,
                    "low_threshold": 0.7,
                    "min_candidate_rows": 20,
                    "drift_warn_threshold": 0.25,
                },
                "decision": {
                    "recommended_action": "manual_gate_threshold_review",
                    "review_ready": True,
                    "decision_reason": "latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold; threshold-relevant drift is concentrated in historical mid-confidence approvals, so review the mid-confidence escalation policy before lowering the high threshold",
                    "next_step": "review_gate_thresholds_and_mid_confidence_policy",
                    "focus_areas": [
                        "high_threshold",
                        "mid_confidence_escalation",
                        "high_confidence_pending_policy",
                        "indexed_pending_policy",
                    ],
                    "latest_run_id": "processor_gate_replay_drift_preapply_20260421_r11",
                    "latest_run_status": "warn",
                    "tuning_targets": [
                        "mid_confidence_escalation",
                        "indexed_pending_policy",
                    ],
                    "tuning_actions": [
                        {
                            "target": "mid_confidence_escalation",
                            "action": "review_mid_confidence_escalation_policy",
                        },
                        {
                            "target": "indexed_pending_policy",
                            "action": "exclude_indexed_pending_rows_from_threshold_tuning",
                        },
                    ],
                    "action_plan": [
                        {
                            "order": 1,
                            "action": "review_gate_thresholds_and_mid_confidence_policy",
                        },
                        {
                            "order": 2,
                            "action": "review_mid_confidence_escalation_policy",
                            "target": "mid_confidence_escalation",
                        },
                        {
                            "order": 3,
                            "action": "exclude_indexed_pending_rows_from_threshold_tuning",
                            "target": "indexed_pending_policy",
                        },
                    ],
                    "tuning_recommendations": [
                        "Current threshold-relevant drift is entirely mid-confidence approval debt, so review the mid-confidence escalation policy before lowering the high threshold.",
                        "Keep the current high threshold unchanged unless manual review of the threshold-relevant bucket shows true high-threshold misses.",
                    ],
                    "threshold_change_ready": False,
                    "threshold_change_status": "blocked_policy_only",
                    "threshold_change_next_step": "review_mid_confidence_escalation_policy",
                    "threshold_change_blocker": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                },
                "signal_summary": {
                    "candidate_count": 54,
                    "promotable_count": 28,
                    "drift_count": 26,
                    "drift_rate": 0.481481,
                    "decision_transition_counts": {
                        "APPROVED->PENDING_REVIEW": 23,
                        "PENDING_REVIEW->PENDING_REVIEW": 2,
                    },
                    "probable_drift_cause_counts": {
                        "legacy_mid_confidence_approval": 21,
                        "legacy_indexed_pending_review": 2,
                        "legacy_high_confidence_pending": 1,
                    },
                },
                "manual_review_scope": {
                    "threshold_relevant": {
                        "count": 21,
                        "paper_ids": [
                            "zotero:bialystokBilingualismConsequencesMind2012",
                            "zotero:chandraGutMicrobiomeAlzheimers2023",
                            "zotero:coricTargetingProdromalAlzheimer2015",
                            "zotero:craftSafetyEfficacyFeasibility2020",
                        ],
                    },
                    "policy_edge_cases": {"count": 1},
                    "excluded": {
                        "manual_override": {"count": 2, "paper_ids": ["manual-1", "manual-2"]},
                        "indexed_pending": {"count": 2, "paper_ids": ["indexed-1", "indexed-2"]},
                        "fixture_or_test": {"count": 1, "paper_ids": ["phase0_test"]},
                        "other": {"count": 0},
                    },
                    "focus_recommendation": "Focus threshold tuning on 21 threshold-relevant row(s) first; exclude 5 manual-override, indexed-pending, or fixture/test row(s) from raw threshold changes.",
                    "worksheet_summary": {
                        "pending_count": 21,
                        "review_bucket": "threshold_relevant",
                        "primary_review_target": "mid_confidence_escalation_policy",
                        "excluded_count": 5,
                        "summary": "21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 5 non-threshold row(s) from raw threshold changes.",
                    },
                    "prefill_summary": {
                        "threshold_relevant_count": 21,
                        "policy_only_review_count": 21,
                        "boundary_review_count": 0,
                        "manual_triage_count": 0,
                        "priority_review_now_count": 0,
                        "priority_review_first_count": 2,
                        "priority_review_later_count": 19,
                        "supports_mid_confidence_policy_review_count": 21,
                        "supports_high_threshold_change_count": 0,
                        "summary": "Default prefills: policy_only=21, boundary=0, triage=0. Priority: now=0, first=2, later=19.",
                    },
                },
                "manual_review_basis": {
                    "preliminary_call": "mid_confidence_policy_only",
                    "summary": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                    "threshold_relevant_count": 21,
                    "policy_edge_case_count": 1,
                    "mid_confidence_policy_support_count": 21,
                    "high_threshold_support_count": 0,
                    "evidence_source_counts": {"evidence_span": 21},
                    "historical_rewrite_hint_counts": {
                        "post_feedback_precanonical_confidence_overwrite_candidate": 19,
                        "none": 2,
                    },
                    "exact_confidence_counts": {"0.8": 21},
                    "decision_transition_counts": {"APPROVED->PENDING_REVIEW": 21},
                    "probable_drift_cause_counts": {"legacy_mid_confidence_approval": 21},
                    "sample_titles": [
                        "Bilingualism: consequences for mind and brain",
                        "The gut microbiome in Alzheimer’s disease: what we know and what remains to be explored",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "audit.md").write_text(
        "# processor gate threshold review markdown\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_rows.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review.md").write_text(
        "# manual review\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_checklist.csv").write_text(
        "paper_id\npaper-1\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_seed.csv").write_text(
        "paper_id\npaper-1\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_frontier.csv").write_text(
        "paper_id\npaper-1\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_frontier_notes.md").write_text(
        "# frontier notes\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_frontier_crosscheck_packet.md").write_text(
        "# frontier crosscheck packet\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_frontier_claude_crosscheck.md").write_text(
        "# claude crosscheck\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_frontier_claude_crosscheck.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_basis.md").write_text(
        "# manual review basis\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_decision.md").write_text(
        "# manual review decision\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_outcome.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_manual_review_outcome.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "total_row_count": 2,
                "completed_row_count": 2,
                "supports_high_threshold_change_count": 0,
                "default_divergence_count": 0,
                "status": "policy_only_confirmed",
                "summary": "All 2 reviewed row(s) support policy-only treatment and none support a high-threshold change.",
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_review_outcome.md").write_text(
        "# manual review outcome\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "threshold_change_decision.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_threshold_change_decision.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "final_status": "no_threshold_change_supported",
                "recommended_action": "keep_current_high_threshold",
                "threshold_change_ready": False,
                "threshold_change_next_step": "continue_mid_confidence_escalation_policy_review",
                "summary": "Manual review confirmed 2/2 threshold-relevant row(s) as policy-only; none support a high-threshold change.",
                "manual_review_counts": {
                    "total": 2,
                    "completed": 2,
                    "supports_mid_confidence_policy_review": 2,
                    "supports_high_threshold_change": 0,
                    "default_divergence": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "threshold_change_decision.md").write_text(
        "# threshold change decision\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "mid_confidence_policy_decision.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_mid_confidence_policy_decision.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "final_status": "mid_confidence_escalation_policy_confirmed",
                "recommended_action": "keep_mid_confidence_pending_review_policy",
                "policy_decision_ready": True,
                "runtime_change_ready": False,
                "next_step": "treat_legacy_mid_confidence_approvals_as_policy_debt",
                "summary": "Manual review confirmed 2/2 reviewed row(s) as mid-confidence policy debt; keep the current pending-review behavior for mid-confidence rows.",
                "manual_review_counts": {
                    "total": 2,
                    "completed": 2,
                    "supports_mid_confidence_policy_review": 2,
                    "supports_high_threshold_change": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "mid_confidence_policy_decision.md").write_text(
        "# mid-confidence policy decision\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "mid_confidence_policy_debt_reconciliation.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_mid_confidence_policy_debt_reconciliation.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "final_status": "legacy_policy_debt_confirmed",
                "recommended_action": "keep_historical_approvals_as_legacy_policy_debt",
                "reconciliation_ready": True,
                "runtime_change_ready": False,
                "historical_mutation_ready": False,
                "next_step": "monitor_future_mid_confidence_pending_review",
                "summary": "Manual review confirmed 2/2 historical mid-confidence approval row(s) as policy debt. Keep the current pending-review behavior for future mid-confidence rows and do not mass-rewrite historical approvals from this artifact.",
                "manual_review_counts": {
                    "total": 2,
                    "completed": 2,
                    "supports_mid_confidence_policy_review": 2,
                    "supports_high_threshold_change": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "mid_confidence_policy_debt_reconciliation.md").write_text(
        "# policy debt reconciliation\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_override_policy_decision.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_manual_override_policy_decision.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "final_status": "manual_override_exception_policy_confirmed",
                "recommended_action": "exclude_manual_override_rows_from_threshold_tuning",
                "policy_decision_ready": True,
                "threshold_change_ready": False,
                "runtime_change_ready": False,
                "historical_mutation_ready": False,
                "manual_override_count": 2,
                "indexed_pending_count": 2,
                "next_step": "review_indexed_pending_status_contract",
                "summary": "2 manual or human override row(s) remain explicit policy exceptions and should stay outside raw threshold tuning.",
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "manual_override_policy_decision.md").write_text(
        "# manual override policy decision\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "indexed_pending_policy_decision.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_indexed_pending_policy_decision.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "final_status": "indexed_pending_status_contract_confirmed",
                "recommended_action": "keep_indexed_pending_rows_out_of_threshold_tuning",
                "policy_decision_ready": True,
                "threshold_change_ready": False,
                "runtime_change_ready": False,
                "historical_mutation_ready": False,
                "indexed_pending_count": 2,
                "manual_override_count": 2,
                "next_step": "monitor_processor_gate_excluded_policy_buckets",
                "summary": "2 indexed-pending row(s) remain status-contract cases and should stay outside raw threshold tuning.",
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "indexed_pending_policy_decision.md").write_text(
        "# indexed pending policy decision\n",
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "fixture_or_test_policy_decision.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_fixture_or_test_policy_decision.v1",
                "generated_at": "2026-04-22T00:00:00Z",
                "run_id": "processor_gate_threshold_review_latest",
                "final_status": "fixture_or_test_hygiene_exclusion_confirmed",
                "recommended_action": "keep_fixture_or_test_rows_out_of_threshold_tuning",
                "policy_decision_ready": True,
                "threshold_change_ready": False,
                "runtime_change_ready": False,
                "historical_mutation_ready": False,
                "archive_action_ready": False,
                "fixture_or_test_count": 1,
                "manual_override_count": 2,
                "indexed_pending_count": 2,
                "next_step": "monitor_processor_gate_excluded_policy_buckets",
                "summary": "1 fixture/test row(s) remain hygiene-scope cases and should stay outside raw threshold tuning.",
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "fixture_or_test_policy_decision.md").write_text(
        "# fixture/test policy decision\n",
        encoding="utf-8",
    )
    validation_replay_command = (
        "python3 scripts/eval/audit_processor_gate_replay_drift.py "
        "--threshold-change-proposal threshold_change_proposal.json "
        "--reviewed-high-threshold '<REVIEWED_HIGH_THRESHOLD>' "
        "--run-id processor_gate_threshold_review_latest__threshold_validation_replay"
    )
    (latest_processor_gate_threshold_review_run / "threshold_change_proposal.json").write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_threshold_change_proposal.v1",
                "validation_replay_run_id": (
                    "processor_gate_threshold_review_latest__threshold_validation_replay"
                ),
                "validation_replay_command_template": validation_replay_command,
            }
        ),
        encoding="utf-8",
    )
    (latest_processor_gate_threshold_review_run / "threshold_change_proposal.md").write_text(
        "# threshold change proposal\n",
        encoding="utf-8",
    )
    latest_slot_tuning_review_run = (
        tmp_path
        / "snapshots"
        / "slot_classification_tuning_review"
        / "slot_classification_tuning_review_20260422_r1"
    )
    latest_slot_tuning_review_run.mkdir(parents=True, exist_ok=True)
    (latest_slot_tuning_review_run / "summary.json").write_text(
        json.dumps(
            {
                "schema_version": "slot_classification_tuning_review.v1",
                "generated_at": "2026-04-22T01:49:08.825177Z",
                "run_id": "slot_classification_tuning_review_20260422_r1",
                "advisory_only": True,
                "decision": {
                    "recommended_action": "hold_current_prompt_policy",
                    "review_ready": False,
                    "decision_reason": "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
                    "next_step": "hold_current_prompt_policy",
                    "latest_compare_run_id": "slot_classification_tie_breaker_compare_20260422_r1",
                    "paired_compare_status": "regressed",
                    "default_rerun_status": "warn",
                    "boundary_rerun_status": "warn",
                    "prompt_change_ready": False,
                    "prompt_change_status": "blocked_advisory",
                    "prompt_change_blocker": "paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']",
                    "tuning_targets": ["slot_classification"],
                    "tuning_actions": [
                        {
                            "target": "slot_classification",
                            "action": "audit_slot_policy_with_paired_compare_and_rerun_drift",
                            "summary": "Evaluate any slot prompt or policy candidate with both paired benchmark comparison and rerun-drift evidence before treating it as durable.",
                        }
                    ],
                    "action_plan": [
                        {
                            "order": 1,
                            "action": "hold_current_prompt_policy",
                            "target": "slot_classification",
                            "blocking": True,
                            "summary": "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
                            "evidence": "paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']",
                        },
                        {
                            "order": 2,
                            "action": "collect_default_rerun_stability_evidence",
                            "target": "slot_classification",
                            "blocking": True,
                            "summary": "Same-code reruns on the default benchmark are unstable above the allowed drift rate.",
                            "evidence": "default benchmark rerun drift is 1 row(s) / 0.0909, above the allowed 0.0000",
                        },
                        {
                            "order": 3,
                            "action": "collect_boundary_rerun_stability_evidence",
                            "target": "slot_classification",
                            "blocking": True,
                            "summary": "Same-code reruns on the boundary benchmark are unstable above the allowed drift rate.",
                            "evidence": "boundary benchmark rerun drift is 1 row(s) / 0.2500, above the allowed 0.0000",
                        },
                    ],
                    "tuning_recommendations": [
                        "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark regresses.",
                        "Same-code reruns on the default benchmark are not yet stable enough for a durable prompt/policy conclusion.",
                        "Same-code reruns on the boundary benchmark are not yet stable enough for a durable prompt/policy conclusion.",
                    ],
                },
                "signal_summary": {
                    "paired_compare_failed_checks": [
                        "default_template_accuracy",
                        "default_template_mismatch_count",
                    ],
                    "paired_compare_regressions": [
                        "default_template_accuracy",
                        "default_template_mismatch_count",
                    ],
                    "paired_compare_error_migration_detected": True,
                    "default_rerun_drift_rate": 0.09090909090909091,
                    "boundary_rerun_drift_rate": 0.25,
                    "default_rerun_drift_count": 1,
                    "boundary_rerun_drift_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    (latest_slot_tuning_review_run / "audit.md").write_text(
        "# slot tuning review markdown\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(
            status="ok",
            checks=[
                SimpleNamespace(
                    name="latest_intake_override_audit",
                    status="ok",
                    detail="latest intake override audit is available (intake_override_audit_latest)",
                    path=str(latest_run / "audit.md"),
                    metadata={
                        "available": True,
                        "run_id": "intake_override_audit_latest",
                        "source": "rows_jsonl",
                        "row_count": 4,
                        "audited_document_count": 3,
                        "triage_override_rate": 0.333,
                        "slot_disagreement_rate": 0.5,
                        "llm_slot_adjudication_rate": 0.5,
                        "llm_tagging_adjudication_rate": 0.25,
                        "selection_fallback_rate": 0.0,
                        "quality_signals": [
                            "slot_disagreement_present",
                            "triage_override_present",
                            "slot_adjudication_present",
                            "tagging_adjudication_present",
                        ],
                    },
                ),
                SimpleNamespace(
                    name="latest_intake_override_audit_quality",
                    status="warn",
                    detail="latest intake override audit quality needs attention: triage=33.3%, slot=50.0%",
                    path=None,
                    metadata={
                        "available": True,
                        "warn_threshold": 0.25,
                        "quality_signals": [
                            "slot_disagreement_present",
                            "triage_override_present",
                            "slot_adjudication_present",
                            "tagging_adjudication_present",
                        ],
                    },
                )
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(status="ok", detail="no fixture paper cleanup candidates detected", path=str(tmp_path / "state.db")),
    )
    monkeypatch.setattr(
        cli,
        "build_intake_override_audit_viewer_command",
        lambda run_root: f"paperpipe show-intake-override-audit {run_root}",
    )
    monkeypatch.setattr(
        cli,
        "build_intake_override_audit_calibration_snapshot",
        lambda **kwargs: {
            "root": str(tmp_path / "snapshots" / "intake_override_audits"),
            "total_runs": 2,
            "eligible_runs": 1,
            "warn_runs": 1,
            "warn_threshold": 0.25,
            "min_audited_docs": 3,
            "calibration_target_runs": 3,
            "recommendations": [
                "Keep the current 25% warning threshold for now; only 1 run(s) meet the 3-document sample floor, below the 3-run calibration floor."
            ],
        },
    )
    monkeypatch.setattr(
        cli,
        "latest_intake_override_threshold_review_run",
        lambda: latest_threshold_review_run,
    )
    monkeypatch.setattr(
        cli,
        "build_intake_override_threshold_review_viewer_command",
        lambda run_root: f"paperpipe show-intake-override-threshold-review {run_root}",
    )
    monkeypatch.setattr(
        cli,
        "latest_processor_gate_threshold_review_run",
        lambda: latest_processor_gate_threshold_review_run,
    )
    monkeypatch.setattr(
        cli,
        "build_processor_gate_threshold_review_viewer_command",
        lambda run_root: f"paperpipe show-processor-gate-threshold-review {run_root}",
    )
    monkeypatch.setattr(
        cli,
        "load_processor_gate_threshold_review_summary",
        lambda run_root: json.loads((run_root / "summary.json").read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        cli,
        "latest_slot_classification_tuning_review_run",
        lambda: latest_slot_tuning_review_run,
    )
    monkeypatch.setattr(
        cli,
        "load_slot_classification_tuning_review_summary",
        lambda run_root: json.loads((run_root / "summary.json").read_text(encoding="utf-8")),
    )

    result = runner.invoke(cli.app, ["doctor"])
    normalized_output = " ".join(result.output.split())

    assert result.exit_code == 0
    assert "Latest Intake Override Audit: intake_override_audit_latest" in normalized_output
    assert "audit.md" in normalized_output
    assert "paperpipe show-intake-override-audit" in normalized_output
    assert "intake_override_audit_latest" in normalized_output
    assert "Latest Audit Quality: ⚠️ latest intake override audit quality needs attention" in normalized_output
    assert "Scope: source=rows_jsonl, rows=4, audited=3" in normalized_output
    assert "Quality: triage=33.3%, slot=50.0%, slot_adj=50.0%, tag_adj=25.0%, fallback=0.0%" in normalized_output
    assert "Signals: slot_disagreement_present, triage_override_present, slot_adjudication_present, tagging_adjudication_present" in normalized_output
    assert "Calibration: runs=2, sufficient=1/3, warn=1, threshold=25.0%, sample>=3" in normalized_output
    assert "Advice: Keep the current 25% warning threshold for now; only 1 run(s) meet the 3-document sample floor, below the 3-run calibration floor." in normalized_output
    assert "Latest Intake Override Threshold Review: intake_override_audit_latest__threshold_review" in normalized_output
    assert "Markdown:" in normalized_output
    assert "paperpipe show-intake-override-threshold-review" in normalized_output
    assert "Decision: action=hold_current_threshold, review_ready=no, next=collect_more_audit_runs, latest=intake_override_audit_latest (warn)" in normalized_output
    assert "Focus: slot_adjudication, slot, triage, tagging_adjudication" in normalized_output
    assert "Latest Warn Signals: triage, slot, slot_adjudication, tagging_adjudication" in normalized_output
    assert "Blocking: 1.collect_more_audit_runs" in normalized_output
    assert "Blocking Why: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates." in normalized_output
    assert "Blocking Summary: 1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates." in normalized_output
    assert "Targets: slot_classification, tagging_first_pass" in normalized_output
    assert "Actions: slot_classification:audit_slot_ambiguity_thresholds | tagging_first_pass:audit_tagging_first_pass_quality" in normalized_output
    assert "Plan: 1.collect_more_audit_runs | 2.audit_slot_ambiguity_thresholds->slot_classification | 3.audit_tagging_first_pass_quality->tagging_first_pass" in normalized_output
    assert "Plan Signals: 2.slot_adjudication | 3.tagging_adjudication" in normalized_output
    assert "Plan Why: 1.1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates." in normalized_output
    assert "2.Triggered because slot adjudication remains present in the threshold-review focus/latest-warn signals, which points to slot-classification ambiguity rather than a pure threshold-only issue." in normalized_output
    assert "3.Triggered because tagging adjudication remains present in the threshold-review focus/latest-warn signals, which points to first-pass tagging robustness rather than a pure threshold-only issue." in normalized_output
    assert "Tuning: Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy. | Audit first-pass tagging robustness, soft-tag formatting, and evidence-span quality before changing warning-threshold heuristics." in normalized_output
    assert "Reason: only 1 sufficiently-audited run(s) exist, below the 3-run review floor; persistent adjudication signals: slot_adjudication, tagging_adjudication" in normalized_output
    assert "Latest Processor Gate Threshold Review: processor_gate_threshold_review_latest" in normalized_output
    assert "processor_gate_threshold_review_latest/audit.md" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_rows.json" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review.md" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_checklist.csv" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_seed.csv" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_frontier.csv" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_frontier_notes.md" in normalized_output
    assert "Manual Review Frontier Crosscheck Packet:" in normalized_output
    assert "Manual Review Frontier Claude Crosscheck:" in normalized_output
    assert "Manual Review Frontier Claude Crosscheck JSON:" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_basis.md" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_decision.md" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_outcome.json" in normalized_output
    assert "processor_gate_threshold_review_latest/manual_review_outcome.md" in normalized_output
    assert "processor_gate_threshold_review_latest/threshold_change_decision.json" in normalized_output
    assert "processor_gate_threshold_review_latest/threshold_change_decision.md" in normalized_output
    assert "processor_gate_threshold_review_latest/mid_confidence_policy_decision.json" in normalized_output
    assert "processor_gate_threshold_review_latest/mid_confidence_policy_decision.md" in normalized_output
    assert "Mid-Confidence Policy Debt Reconciliation:" in normalized_output
    assert "mid_confidence_policy_debt_reconciliation" in normalized_output
    assert "Mid-Confidence Policy Debt Reconciliation Markdown:" in normalized_output
    assert "Manual Override Policy Decision:" in normalized_output
    assert "manual_override_policy_decision" in normalized_output
    assert "Manual Override Policy Decision Markdown:" in normalized_output
    assert "Indexed Pending Policy Decision:" in normalized_output
    assert "indexed_pending_policy_decision" in normalized_output
    assert "Indexed Pending Policy Decision Markdown:" in normalized_output
    assert "Fixture/Test Policy Decision:" in normalized_output
    assert "fixture_or_test_policy_decision" in normalized_output
    assert "Fixture/Test Policy Decision Markdown:" in normalized_output
    assert "Threshold Change Proposal:" in normalized_output
    assert "threshold_change_proposal.json" in normalized_output
    assert "Threshold Change Validation Replay:" in normalized_output
    assert "audit_processor_gate_replay_drift.py" in normalized_output
    assert "processor_gate_threshold_review_latest__threshold_validation_replay" in normalized_output
    assert "Threshold Change Proposal Markdown:" in normalized_output
    assert "threshold_change_proposal.md" in normalized_output
    assert "Replay Drift Summary:" in normalized_output
    assert "processor_gate_replay_drift_preapply_20260421_r11/summary.json" in normalized_output
    assert "Replay Drift Details:" in normalized_output
    assert "processor_gate_replay_drift_preapply_20260421_r11/details.json" in normalized_output
    assert "Replay Drift Markdown:" in normalized_output
    assert "processor_gate_replay_drift_preapply_20260421_r11/audit.md" in normalized_output
    assert "Threshold Replay Context:" in normalized_output
    assert "processor_gate_replay_drift_preapply_20260421_r11/threshold_replay.json" in normalized_output
    assert "Threshold Replay Context Markdown:" in normalized_output
    assert "processor_gate_replay_drift_preapply_20260421_r11/threshold_replay.md" in normalized_output
    assert "Threshold Replay: mode=threshold_change_proposal_replay, high=0.85, low=0.70, reviewed_high=0.85, proposal=gate_threshold_review_ready" in normalized_output
    assert "Threshold Replay Review Command:" in normalized_output
    assert "recommend_processor_gate_threshold_review.py" in normalized_output
    assert "Threshold Change Validation Replay Status:" in normalized_output
    assert "mismatched_validation_run_id" in normalized_output
    assert "needs_rerun=yes" in normalized_output
    assert "Threshold Change Manual Decision:" in normalized_output
    assert (
        "ready=no, status=blocked_validation_replay, blocker=mismatched_validation_run_id"
        in normalized_output
    )
    assert "paperpipe show-processor-gate-threshold-review" in normalized_output
    assert "Decision: action=manual_gate_threshold_review, review_ready=yes, next=review_gate_thresholds_and_mid_confidence_policy, latest=processor_gate_replay_drift_preapply_20260421_r11 (warn)" in normalized_output
    assert "Threshold Change: ready=no, status=blocked_policy_only, next=review_mid_confidence_escalation_policy" in normalized_output
    assert "Threshold Blocker: All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone." in normalized_output
    assert "Focus: high_threshold, mid_confidence_escalation, high_confidence_pending_policy, indexed_pending_policy" in normalized_output
    assert "Targets: mid_confidence_escalation, indexed_pending_policy" in normalized_output
    assert "Actions: mid_confidence_escalation:review_mid_confidence_escalation_policy | indexed_pending_policy:exclude_indexed_pending_rows_from_threshold_tuning" in normalized_output
    assert "Plan: 1.review_gate_thresholds_and_mid_confidence_policy | 2.review_mid_confidence_escalation_policy->mid_confidence_escalation | 3.exclude_indexed_pending_rows_from_threshold_tuning->indexed_pending_policy" in normalized_output
    assert "Scope: relevant=21, policy=1, excluded.manual_override=2, excluded.indexed_pending=2, excluded.fixture_or_test=1, excluded.other=0" in normalized_output
    assert "Scope Samples: relevant=zotero:bialystokBilingualismConsequencesMind2012, zotero:chandraGutMicrobiomeAlzheimers2023, zotero:coricTargetingProdromalAlzheimer2015 (+1 more) | excluded.manual_override=manual-1, manual-2 | excluded.indexed_pending=indexed-1, indexed-2 | excluded.fixture_or_test=phase0_test" in normalized_output
    assert "Review Basis: Focus threshold tuning on 21 threshold-relevant row(s) first; exclude 5 manual-override, indexed-pending, or fixture/test row(s) from raw threshold changes." in normalized_output
    assert "Worksheet: pending=21, target=mid_confidence_escalation_policy, excluded=5" in normalized_output
    assert "Worksheet Summary: 21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 5 non-threshold row(s) from raw threshold changes." in normalized_output
    assert "Prefill: policy_only=21, boundary=0, triage=0, now=0, first=2, later=19" in normalized_output
    assert "Prefill Summary: Default prefills: policy_only=21, boundary=0, triage=0. Priority: now=0, first=2, later=19." in normalized_output
    assert "Basis: call=mid_confidence_policy_only, policy=21, high=0" in normalized_output
    assert "Basis Summary: All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone." in normalized_output
    assert "Outcome: status=policy_only_confirmed, completed=2/2, high=0, diverged=0" in normalized_output
    assert "Outcome Summary: All 2 reviewed row(s) support policy-only treatment and none support a high-threshold change." in normalized_output
    assert "Threshold Decision: status=no_threshold_change_supported, action=keep_current_high_threshold, reviewed=2/2, high=0" in normalized_output
    assert "Threshold Decision Summary: Manual review confirmed 2/2 threshold-relevant row(s) as policy-only; none support a high-threshold change." in normalized_output
    assert "Mid-Confidence Policy: status=mid_confidence_escalation_policy_confirmed, action=keep_mid_confidence_pending_review_policy, mid=2, high=0" in normalized_output
    assert "Mid-Confidence Policy Summary: Manual review confirmed 2/2 reviewed row(s) as mid-confidence policy debt; keep the current pending-review behavior for mid-confidence rows." in normalized_output
    assert "Policy Debt: status=legacy_policy_debt_confirmed, action=keep_historical_approvals_as_legacy_policy_debt, debt=2/2, mutate=no" in normalized_output
    assert "Policy Debt Summary: Manual review confirmed 2/2 historical mid-confidence approval row(s) as policy debt." in normalized_output
    assert "Manual Override Policy: status=manual_override_exception_policy_confirmed, action=exclude_manual_override_rows_from_threshold_tuning, manual=2, mutate=no" in normalized_output
    assert "Manual Override Policy Summary: 2 manual or human override row(s) remain explicit policy exceptions" in normalized_output
    assert "Indexed Pending Policy: status=indexed_pending_status_contract_confirmed, action=keep_indexed_pending_rows_out_of_threshold_tuning, indexed=2, mutate=no" in normalized_output
    assert "Indexed Pending Policy Summary: 2 indexed-pending row(s) remain status-contract cases" in normalized_output
    assert "Fixture/Test Policy: status=fixture_or_test_hygiene_exclusion_confirmed, action=keep_fixture_or_test_rows_out_of_threshold_tuning, fixture=1, archive=no, mutate=no" in normalized_output
    assert "Fixture/Test Policy Summary: 1 fixture/test row(s) remain hygiene-scope cases" in normalized_output
    assert "Tuning: Current threshold-relevant drift is entirely mid-confidence approval debt, so review the mid-confidence escalation policy before lowering the high threshold. | Keep the current high threshold unchanged unless manual review of the threshold-relevant bucket shows true high-threshold misses." in normalized_output
    assert "Thresholds: high=0.90, low=0.70, warn=25.0%, sample>=20" in normalized_output
    assert "Coverage: candidates=54, promotable=28, drift=26, rate=48.1%" in normalized_output
    assert "Transitions: APPROVED->PENDING_REVIEW=23, PENDING_REVIEW->PENDING_REVIEW=2" in normalized_output
    assert "Causes: legacy_mid_confidence_approval=21, legacy_indexed_pending_review=2, legacy_high_confidence_pending=1" in normalized_output
    assert "Reason: latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold; threshold-relevant drift is concentrated in historical mid-confidence approvals, so review the mid-confidence escalation policy before lowering the high threshold" in normalized_output
    assert "Latest Slot Classification Tuning Review: slot_classification_tuning_review_20260422_r1" in normalized_output
    assert "slot_classification_tuning_review_20260422_r1/audit.md" in normalized_output
    assert "Decision: action=hold_current_prompt_policy, review_ready=no, next=hold_current_prompt_policy, compare=slot_classification_tie_breaker_compare_20260422_r1" in normalized_output
    assert "Compare: regressed" in normalized_output
    assert "Reruns: default=warn, boundary=warn" in normalized_output
    assert "Prompt Change: ready=no, status=blocked_advisory" in normalized_output
    assert "Prompt Blocker: paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']" in normalized_output
    assert "Targets: slot_classification" in normalized_output
    assert "Actions: slot_classification:audit_slot_policy_with_paired_compare_and_rerun_drift" in normalized_output
    assert "Plan: 1.hold_current_prompt_policy->slot_classification | 2.collect_default_rerun_stability_evidence->slot_classification | 3.collect_boundary_rerun_stability_evidence->slot_classification" in normalized_output
    assert "Plan Why: 1.paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count'] | 2.default benchmark rerun drift is 1 row(s) / 0.0909, above the allowed 0.0000 | 3.boundary benchmark rerun drift is 1 row(s) / 0.2500, above the allowed 0.0000" in normalized_output
    assert "Signals: compare.failed=default_template_accuracy,default_template_mismatch_count, compare.regressions=default_template_accuracy,default_template_mismatch_count, compare.migration=yes, default=1/9.1%, boundary=1/25.0%" in normalized_output
    assert "Tuning: Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark regresses. | Same-code reruns on the default benchmark are not yet stable enough for a durable prompt/policy conclusion. | Same-code reruns on the boundary benchmark are not yet stable enough for a durable prompt/policy conclusion." in normalized_output
    assert "Reason: Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression." in normalized_output
    assert "All systems go!" in normalized_output


def test_doctor_reports_fixture_paper_hygiene_error_when_candidates_are_high(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "logs_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "_optional_dependency_installed", lambda module_name: True)
    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: SimpleNamespace(status="error", checks=[]),
    )
    monkeypatch.setattr(
        cli,
        "collect_structured_state_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no hidden fixture structured states detected", path=str(vault_path)),
    )
    monkeypatch.setattr(
        cli,
        "collect_meeting_pack_storage_hygiene_check",
        lambda vault_path: SimpleNamespace(status="ok", detail="no low-value Meeting Pack archive candidates detected", path=str(tmp_path / "meeting_packs")),
    )
    monkeypatch.setattr(
        cli,
        "collect_fixture_paper_hygiene_check",
        lambda: SimpleNamespace(
            status="error",
            detail=(
                "fixture paper cleanup candidates detected (10; fixture_visibility_rule=10); "
                "too many fixture rows are distorting local classification-audit counts, so archive them with "
                "`paperpipe archive-fixture-no-feedback-papers` before trusting this runtime DB"
            ),
            path=str(tmp_path / "state.db"),
        ),
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Fixture Paper Hygiene: ❌ fixture paper cleanup candidates detected" in result.output
    assert "archive-fixture-no-feedback-papers" in result.output
    assert "Runtime needs fixes before you should trust it." in result.output


def test_quarantine_fixture_states_dry_run_and_apply(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    vault_dir = tmp_path / "vault"
    fixture_state = vault_dir / ".pp" / "fixture-note" / "state.json"
    fixture_state.parent.mkdir(parents=True, exist_ok=True)
    fixture_state.write_text(
        """
{
  "paper_slug": "fixture-note",
  "updated_at": "2026-03-10T09:00:00Z",
  "runs": [],
  "claimset": [
    {
      "id": "claim_c0ffee000001",
      "source_claim_id": "e2e-claim-1",
      "claim": "Fixture claim",
      "evidence": [
        {
          "id": "evidence_deadbeef0001",
          "claim_id": "claim_c0ffee000001",
          "text": "Fixture evidence",
          "locator": {"chunk_id": "chunk-e2e-001", "source": "bbox"}
        }
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=vault_dir,
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)

    preview = runner.invoke(cli.app, ["quarantine-fixture-states"])
    assert preview.exit_code == 0
    assert "Found 1 hidden fixture structured state(s)." in preview.output
    assert "Dry run only" in preview.output
    assert fixture_state.exists()

    applied = runner.invoke(cli.app, ["quarantine-fixture-states", "--apply"])
    assert applied.exit_code == 0
    assert "Moved:" in applied.output
    assert not fixture_state.exists()


def test_archive_meeting_pack_noise_dry_run_and_apply(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    meeting_root = tmp_path / "meeting_packs"
    archive_root = tmp_path / "_quarantine" / "meeting_packs" / "20260410T040000Z"
    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path / "vault",
            watch_folder=tmp_path / "watch-folder",
        ),
        system=SimpleNamespace(log_level="INFO", unpaywall_email=""),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        llm=SimpleNamespace(mode="local"),
    )
    candidates = [
        SimpleNamespace(
            pack_id="meetingpack_20260410T000000000000Z_journal_club_alpha",
            reason="superseded_by_recent_healthy_pack",
            selector_key="journal_club|paper_slug:alpha",
            title="Alpha title",
            source_dir=meeting_root / "meetingpack_20260410T000000000000Z_journal_club_alpha",
            destination_dir=archive_root / "meetingpack_20260410T000000000000Z_journal_club_alpha",
        )
    ]
    apply_calls: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(cli, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "default_meeting_packs_root", lambda: meeting_root)
    monkeypatch.setattr(cli, "default_meeting_pack_archive_root", lambda root: archive_root)
    monkeypatch.setattr(cli, "select_meeting_pack_archive_candidates", lambda root, vault_path, keep_latest: candidates)
    monkeypatch.setattr(
        cli,
        "apply_meeting_pack_archive",
        lambda selected, archive_root: apply_calls.append(([item.pack_id for item in selected], archive_root)) or len(selected),
    )

    preview = runner.invoke(cli.app, ["archive-meeting-pack-noise"])
    assert preview.exit_code == 0
    assert "Found 1 Meeting Pack archive candidate(s)." in preview.output
    assert "Dry run only" in preview.output
    assert apply_calls == []

    applied = runner.invoke(cli.app, ["archive-meeting-pack-noise", "--apply"])
    assert applied.exit_code == 0
    assert "Moved: meetingpack_20260410T000000000000Z_journal_club_alpha" in applied.output
    assert "Archived 1 Meeting Pack directories." in applied.output
    assert apply_calls == [(["meetingpack_20260410T000000000000Z_journal_club_alpha"], archive_root)]


def test_archive_fixture_no_feedback_papers_dry_run_and_apply(tmp_path: Path):
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT,
                pdf_path TEXT,
                feedback_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("paper-e2e-001", "E2E Seed Paper", "NEW", "tests/temp_rag_test/Library/Test_ID.pdf", None),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("paper-real-001", "Real Paper", "INDEXED", "/tmp/real.pdf", '{"ok": true}'),
        )
        conn.commit()
    finally:
        conn.close()

    preview = runner.invoke(cli.app, ["archive-fixture-no-feedback-papers", "--db", str(db_path)])
    assert preview.exit_code == 0
    assert "Found 1 fixture paper candidate(s)." in preview.output
    assert "Would archive: paper-e2e-001" in preview.output
    assert "Dry run only" in preview.output

    applied = runner.invoke(cli.app, ["archive-fixture-no-feedback-papers", "--db", str(db_path), "--apply"])
    assert applied.exit_code == 0
    assert "Archived: paper-e2e-001" in applied.output
    assert "Backup:" in applied.output
    assert "Archived 1 fixture paper row(s)." in applied.output

    conn = sqlite3.connect(db_path)
    try:
        remaining_ids = {row[0] for row in conn.execute("SELECT paper_id FROM papers")}
        archived_count = conn.execute("SELECT COUNT(*) FROM fixture_papers_archive").fetchone()[0]
    finally:
        conn.close()

    assert remaining_ids == {"paper-real-001"}
    assert archived_count == 1
