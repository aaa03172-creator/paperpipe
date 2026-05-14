import json
import sqlite3
from pathlib import Path

from scripts.downloader_ops_dashboard import collect_metrics, render_markdown


def test_collect_metrics_exposes_retry_fields(tmp_path: Path):
    db_path = tmp_path / "state.db"
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
    attempts = [
        {"provider": "unpaywall", "status": "rate_limit", "retry_no": 0, "will_retry": True},
        {"provider": "unpaywall", "status": "rate_limit", "retry_no": 1, "will_retry": False},
        {"provider": "direct_link", "status": "temp_fail", "retry_no": 0, "will_retry": False},
    ]
    conn.execute(
        "INSERT INTO papers (paper_id, pdf_path, download_attempts) VALUES (?, ?, ?)",
        ("p1", None, json.dumps(attempts)),
    )
    conn.commit()
    conn.close()

    metrics = collect_metrics(db_path, hours=24)
    assert metrics["retry_attempts_total"] == 1
    assert metrics["retry_attempts_by_provider"]["unpaywall"] == 1
    assert metrics["rate_limit_retry_signals"] == 1
    assert metrics["rate_limit_exhausted"] == 1


def test_render_markdown_includes_retry_section():
    metrics = {
        "db_exists": True,
        "window_hours": 24,
        "paper_rows": 1,
        "attempt_rows": 1,
        "missing_pdf_rows": 1,
        "has_download_attempts_column": True,
        "status_counts": {"rate_limit": 2},
        "provider_counts": {"unpaywall": 2},
        "retry_attempts_total": 1,
        "retry_attempts_by_provider": {"unpaywall": 1},
        "rate_limit_retry_signals": 1,
        "rate_limit_exhausted": 1,
    }
    rendered = render_markdown(metrics, alerts=[])
    assert "## Retry Attempt Counts" in rendered
    assert "Rate-limit retry signals: 1" in rendered
    assert "Rate-limit exhausted: 1" in rendered
