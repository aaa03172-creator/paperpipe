from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_downloader_ops_dashboard_runs_as_cli_from_arbitrary_cwd(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "state.db"
    out_path = tmp_path / "dashboard.md"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pdf_path TEXT,
            download_attempts TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "downloader_ops_dashboard.py"),
            "--db",
            str(db_path),
            "--out",
            str(out_path),
            "--hours",
            "24",
            "--rate-limit-warn",
            "3",
            "--temp-fail-warn",
            "5",
            "--bad-content-warn",
            "3",
            "--policy-block-warn",
            "1",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "dashboard written" in completed.stdout
    assert out_path.exists()


def test_qa_report_runs_as_cli_from_arbitrary_cwd(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            summary TEXT,
            feedback_json TEXT,
            pdf_path TEXT,
            obsidian_path TEXT,
            pdf_status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

    vault = tmp_path / "vault"
    inbox = vault / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "paper_001.md").write_text("## Critical Review (ClaimSet)\n", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    config_text = (repo_root / "config.example.yaml").read_text(encoding="utf-8")
    config_text = config_text.replace('/path/to/Obsidian/MyVault', vault.as_posix())
    config_text = config_text.replace('storage/pdfs', (tmp_path / 'pdfs').as_posix())
    config_path.write_text(config_text, encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "qa_report.py")],
        cwd=tmp_path,
        env={
            **os.environ,
            "PAPERPIPE_DB_PATH": str(db_path),
            "PAPERPIPE_CONFIG_PATH": str(config_path),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Missing Markdown Files: 0" in completed.stdout
