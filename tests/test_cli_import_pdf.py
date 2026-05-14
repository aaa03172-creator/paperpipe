import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli
from backend.routers import paper_notes as paper_notes_router
from src import db_utils


def _init_minimal_papers_db(db_path: Path) -> None:
    db_utils.init_db()
    conn = db_utils.get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def test_import_pdf_cli_imports_local_pdf_and_prints_next_steps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _init_minimal_papers_db(db_path)

    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    sample_pdf_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample.pdf"
    result = CliRunner().invoke(cli.app, ["import-pdf", str(sample_pdf_path)])

    assert result.exit_code == 0
    assert "Imported PDF into Paper Notes" in result.output
    assert "paper_id: userpdf-" in result.output
    assert "next: open /papers/" in result.output
    assert len(list((vault_dir / "Inbox" / "PaperPipe").glob("*.md"))) == 1
    assert len(list(pdf_storage_dir.glob("userpdf-*.pdf"))) == 1


def test_import_pdf_cli_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _init_minimal_papers_db(db_path)

    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    sample_pdf_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample.pdf"
    result = CliRunner().invoke(cli.app, ["import-pdf", str(sample_pdf_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["paper_id"].startswith("userpdf-")
    assert payload["slug"].startswith("sample")
    assert payload["pdf_url"] == f"/papers/{payload['paper_id']}/pdf"


def test_demo_first_paper_cli_imports_bundled_sample_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _init_minimal_papers_db(db_path)

    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    result = CliRunner().invoke(cli.app, ["demo-first-paper"])

    assert result.exit_code == 0
    assert "Imported bundled sample PDF into Paper Notes" in result.output
    assert "paper_id: userpdf-" in result.output
    assert "next: open /papers/" in result.output
    assert len(list((vault_dir / "Inbox" / "PaperPipe").glob("*.md"))) == 1
    assert len(list(pdf_storage_dir.glob("userpdf-*.pdf"))) == 1


def test_demo_first_paper_cli_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _init_minimal_papers_db(db_path)

    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    result = CliRunner().invoke(cli.app, ["demo-first-paper", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["paper_id"].startswith("userpdf-")
    assert payload["slug"].startswith("sample")
    assert payload["pdf_url"] == f"/papers/{payload['paper_id']}/pdf"
