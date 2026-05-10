import json
import subprocess

import src.db_utils as db_utils
from scripts.open_download_links import collect_institutional_links, open_links


def test_collect_institutional_links_respects_limit(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT,
                pdf_status TEXT,
                feedback_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for idx in range(3):
            payload = {
                "links": {
                    "institutional_proxy_url": f"https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/{idx}"
                }
            }
            conn.execute(
                "INSERT INTO papers (paper_id, title, pdf_status, feedback_json) VALUES (?, ?, ?, ?)",
                (f"p{idx}", f"Title {idx}", "manual_required", json.dumps(payload)),
            )
        conn.commit()
        conn.close()

        links = collect_institutional_links(limit=2, status="manual_required")
        assert len(links) == 2
        assert all(item["url"].startswith("https://libproxy.knu.ac.kr/_Lib_Proxy_Url/") for item in links)
    finally:
        db_utils.DB_PATH = original_db_path


def test_open_links_prints_and_invokes_open(monkeypatch, capsys):
    opened: list[list[str]] = []

    def _fake_run(cmd, check=False):
        assert check is False
        opened.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("scripts.open_download_links.subprocess.run", _fake_run)
    items = [
        {"paper_id": "p1", "title": "Title 1", "url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1/1"},
        {"paper_id": "p2", "title": "Title 2", "url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1/2"},
    ]

    open_links(items)
    out = capsys.readouterr().out

    assert "p1" in out and "p2" in out
    assert opened == [["open", items[0]["url"]], ["open", items[1]["url"]]]
