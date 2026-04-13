import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from backend.routers import paper_notes as paper_notes_router
from src.services.path_masking import mask_local_path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_artifact_run(path: Path, *, claimset: dict | None = None, stats_report: dict | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if claimset is not None:
        (path / "claimset.resolved.json").write_text(json.dumps(claimset), encoding="utf-8")
    if stats_report is not None:
        (path / "stats_report.json").write_text(json.dumps(stats_report), encoding="utf-8")


def _note_content(
    *,
    note_id: str,
    alias: str,
    doi: str | None = None,
    pdf_url: str | None = None,
) -> str:
    frontmatter_lines = [
        "---",
        f"id: {note_id}",
        f"aliases: [\"{alias}\"]",
        "tags:",
        "  - Medicine/Neurology",
        "date_processed: 2026-02-24",
        "confidence: 0.9",
        "status: INDEXED",
    ]
    if doi is not None:
        frontmatter_lines.append(f"doi: {doi}")
    if pdf_url is not None:
        frontmatter_lines.append(f"pdf_url: {pdf_url}")
    frontmatter_lines.append("---")
    return (
        "\n".join(frontmatter_lines)
        + "\n\n"
        f"# {alias}\n\n"
        "## References\n"
        + (f"- [Open PDF]({pdf_url})\n" if pdf_url else "")
    )


def test_papers_endpoints_include_derived_access_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                doi TEXT,
                link TEXT,
                pdf_link TEXT,
                pdf_path TEXT,
                pdf_status TEXT,
                feedback_json TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        local_pdf = tmp_path / "manual.pdf"
        local_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_open",
                "Open Access Paper",
                "INDEXED",
                "10.1000/open",
                "https://publisher.example/open",
                "https://oa.example/open.pdf",
                None,
                None,
                "{}",
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_institution",
                "Institution Paper",
                "INDEXED",
                "10.1000/inst",
                "https://publisher.example/inst",
                None,
                None,
                "manual_required",
                "{}",
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_local",
                "Local PDF Paper",
                "INDEXED",
                "10.1000/local",
                "https://publisher.example/local",
                None,
                str(local_pdf),
                "downloaded",
                "{}",
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_unavailable",
                "Unavailable Paper",
                "INDEXED",
                None,
                None,
                None,
                None,
                None,
                "{}",
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}

        assert by_id["paper_open"]["access_summary"] == {
            "status_label": "open",
            "open_access_url": "https://oa.example/open.pdf",
            "institution_access_url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/open",
            "local_pdf_url": None,
        }
        assert by_id["paper_institution"]["access_summary"] == {
            "status_label": "institution_required",
            "open_access_url": None,
            "institution_access_url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/inst",
            "local_pdf_url": None,
        }
        assert by_id["paper_local"]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/local",
            "local_pdf_url": "/papers/paper_local/pdf",
        }
        assert by_id["paper_unavailable"]["access_summary"] == {
            "status_label": "unavailable",
            "open_access_url": None,
            "institution_access_url": None,
            "local_pdf_url": None,
        }

        detail = client.get("/papers/paper_institution")
        assert detail.status_code == 200
        assert detail.json()["access_summary"]["status_label"] == "institution_required"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_detail_includes_pdf_exists_and_missing_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_missing_pdf",
                "Missing PDF Paper",
                "INDEXED",
                str(tmp_path / "no_such_file.pdf"),
                "summary",
            ),
        )
        existing_pdf = tmp_path / "existing.pdf"
        existing_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_has_pdf",
                "Has PDF Paper",
                "INDEXED",
                str(existing_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        detail_missing = client.get("/papers/p_missing_pdf")
        assert detail_missing.status_code == 200
        payload_missing = detail_missing.json()
        assert payload_missing["paper_id"] == "p_missing_pdf"
        assert payload_missing["pdf_exists"] is False
        assert payload_missing["pdf_status"] == "missing"

        detail_ok = client.get("/papers/p_has_pdf")
        assert detail_ok.status_code == 200
        payload_ok = detail_ok.json()
        assert payload_ok["paper_id"] == "p_has_pdf"
        assert payload_ok["pdf_exists"] is True
        assert payload_ok["ops_summary"] is None

        missing = client.get("/papers/nope")
        assert missing.status_code == 404

        listing = client.get("/papers")
        assert listing.status_code == 200
        rows = listing.json()
        by_id = {row["paper_id"]: row for row in rows}
        assert by_id["p_missing_pdf"]["pdf_exists"] is False
        assert by_id["p_missing_pdf"]["pdf_status"] == "missing"
        assert by_id["p_has_pdf"]["pdf_exists"] is True
        assert by_id["p_has_pdf"]["pdf_status"] is None
        assert by_id["p_has_pdf"]["ops_summary"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_detail_and_pdf_route_fall_back_to_note_backed_local_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "dubois.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%note-backed fixture\n")

        note_id = "zotero:duboisAlzheimerDiseaseClinicalBiological2024"
        note_title = "Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1016/S1474-4422(24)00001-2",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )
        _write_artifact_run(
            artifacts_dir / "duboisAlzheimerDiseaseClinicalBiological2024" / "run-001",
            claimset={"claims": [{"id": "claim-1", "text": "Example claim"}]},
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{note_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["title"] == note_title
        assert payload["pdf_exists"] is True
        assert payload["status"] == "completed"
        assert payload["issues_state"] == "unavailable"
        assert payload["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1016/S1474-4422(24)00001-2",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }
        assert payload["ops_summary"]["state"] == "action_needed"
        assert payload["ops_summary"]["latest_run_id"] == "run-001"

        pdf_response = client.get(f"/papers/{note_id}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_db_row_with_stale_pdf_path_falls_back_to_note_backed_local_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                doi TEXT,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        note_id = "zotero:stalePdfFallback2026"
        note_title = "Stale PDF fallback note"
        stale_pdf = tmp_path / "library" / "stale.pdf"
        recovered_pdf = tmp_path / "library" / "recovered.pdf"
        recovered_pdf.parent.mkdir(parents=True, exist_ok=True)
        recovered_pdf.write_bytes(b"%PDF-1.4\n%recovered note-backed pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                note_id,
                note_title,
                "INDEXED",
                "10.1000/stale-fallback",
                str(stale_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/stale-fallback",
                pdf_url=recovered_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{note_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["pdf_exists"] is True
        assert payload["pdf_status"] is None
        assert payload["pdf_path"] == mask_local_path(str(recovered_pdf))

        assert payload["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/stale-fallback",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }

        pdf_response = client.get(f"/papers/{note_id}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF-1.4")

        listing = client.get("/papers")
        assert listing.status_code == 200
        list_payload = {row["paper_id"]: row for row in listing.json()}[note_id]
        assert list_payload["pdf_exists"] is True
        assert list_payload["pdf_status"] is None
        assert list_payload["pdf_path"] == mask_local_path(str(recovered_pdf))
        assert list_payload["access_summary"] == payload["access_summary"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_includes_note_backed_items_and_sorts_by_note_updated_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_db_only",
                "DB Paper",
                "INDEXED",
                None,
                "summary",
                "2000-01-01 00:00:00",
                "2000-01-01 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "note-only.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%note only\n")

        note_id = "zotero:noteOnlyPaper2026"
        note_title = "Note Only Paper"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-only",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows[:2]] == [note_id, "paper_db_only"]
        assert rows[0]["status"] == "completed"
        assert rows[0]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/note-only",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_prefers_existing_db_rows_over_note_id_variants(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "zotero:sharedPaper2026",
                "DB-authoritative Paper",
                "INDEXED",
                None,
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / "Shared Paper.md",
            _note_content(
                note_id="sharedPaper2026",
                alias="Shared Paper",
                doi="10.1000/shared-paper",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["zotero:sharedPaper2026"]
        assert rows[0]["title"] == "DB-authoritative Paper"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_expose_escalation_metadata_from_feedback_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                gate_decision TEXT,
                gate_reason TEXT,
                feedback_json TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_escalated",
                "Escalated Guideline Paper",
                "APPROVED",
                "APPROVED",
                "CONFIDENCE_MID,FASTLANE_GUIDANCE",
                json.dumps(
                    {
                        "escalation": {
                            "approved": True,
                            "reason": "Authoritative biomedical guidance is explicit; safe to auto-approve.",
                            "final_route": "FAST_LANE_APPROVE",
                            "in_biomedical_scope": True,
                            "reason_codes": ["FASTLANE_GUIDANCE"],
                        }
                    }
                ),
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_pending_escalation",
                "Pending Review Paper",
                "PENDING_REVIEW",
                "PENDING_REVIEW",
                "CONFIDENCE_MID,MODEL_REVIEW_REQUIRED",
                json.dumps(
                    {
                        "escalation": {
                            "approved": False,
                            "reason": "Interesting but uncertain from metadata alone.",
                            "final_route": "QUEUE_HUMAN_REVIEW",
                            "in_biomedical_scope": True,
                            "reason_codes": ["MODEL_REVIEW_REQUIRED"],
                        }
                    }
                ),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}

        assert by_id["paper_escalated"]["is_escalated"] is True
        assert by_id["paper_escalated"]["escalation_final_route"] == "FAST_LANE_APPROVE"
        assert by_id["paper_escalated"]["escalation_in_biomedical_scope"] is True
        assert by_id["paper_escalated"]["escalation_reason_codes"] == ["FASTLANE_GUIDANCE"]

        assert by_id["paper_pending_escalation"]["is_escalated"] is False
        assert by_id["paper_pending_escalation"]["escalation_final_route"] == "QUEUE_HUMAN_REVIEW"
        assert by_id["paper_pending_escalation"]["escalation_in_biomedical_scope"] is True
        assert by_id["paper_pending_escalation"]["escalation_reason_codes"] == ["MODEL_REVIEW_REQUIRED"]

        detail = client.get("/papers/paper_escalated")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["is_escalated"] is True
        assert payload["escalation_reason"] == "Authoritative biomedical guidance is explicit; safe to auto-approve."
        assert payload["escalation_final_route"] == "FAST_LANE_APPROVE"
        assert payload["escalation_reason_codes"] == ["FASTLANE_GUIDANCE"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_is_limited_and_sorted_by_updated_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        for idx in range(60):
            conn.execute(
                """
                INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"p_{idx:02d}",
                    f"Paper {idx:02d}",
                    "INDEXED",
                    None,
                    "summary",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                ),
            )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 50
        assert rows[0]["paper_id"] == "p_59"
        assert rows[-1]["paper_id"] == "p_10"
        assert rows[0]["pdf_exists"] is False
        assert rows[0]["pdf_status"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_operational_summary_from_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_healthy", "Healthy Paper", "INDEXED", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_missing", "Missing Stats Paper", "INDEXED", "summary"),
        )
        conn.commit()
        conn.close()

        _write_artifact_run(
            artifacts_dir / "paper_ops_healthy" / "run-healthy",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )
        _write_artifact_run(
            artifacts_dir / "paper_ops_missing" / "run-missing",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": []},
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_ops_healthy"]["ops_summary"]["state"] == "healthy"
        assert by_id["paper_ops_healthy"]["ops_summary"]["stats_check_count"] == 2
        assert by_id["paper_ops_healthy"]["latest_run_id"] == "run-healthy"
        assert by_id["paper_ops_missing"]["ops_summary"]["state"] == "action_needed"
        assert by_id["paper_ops_missing"]["ops_summary"]["reason"] == "Stats report is missing or empty."
        assert by_id["paper_ops_missing"]["latest_run_id"] == "run-missing"

        detail = client.get("/papers/paper_ops_missing")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"]["recommended_action"] == "repair_stats"
        assert payload["ops_summary"]["latest_run_id"] == "run-missing"
        assert payload["latest_run_id"] == "run-missing"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_prefer_latest_ops_summary_across_equivalent_paper_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("zotero:wenzelShortchainFattyAcids2020", "Candidate-linked paper", "INDEXED", "summary"),
        )
        conn.commit()
        conn.close()

        stale_run = artifacts_dir / "zotero:wenzelShortchainFattyAcids2020" / "run-stale"
        _write_artifact_run(
            stale_run,
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": []},
        )

        fresh_run = artifacts_dir / "wenzelShortchainFattyAcids2020" / "run-fresh"
        _write_artifact_run(
            fresh_run,
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        payload = listing.json()[0]
        assert payload["paper_id"] == "zotero:wenzelShortchainFattyAcids2020"
        assert payload["ops_summary"]["state"] == "healthy"
        assert payload["ops_summary"]["stats_check_count"] == 2
        assert payload["latest_run_id"] == "run-fresh"

        detail = client.get("/papers/zotero:wenzelShortchainFattyAcids2020")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["ops_summary"]["state"] == "healthy"
        assert detail_payload["ops_summary"]["latest_run_id"] == "run-fresh"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_hides_fixture_rows_when_real_papers_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "real.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-001",
                    "E2E Seed Paper",
                    "INDEXED",
                    str(fixture_pdf),
                    "fixture",
                    "2026-03-28 00:00:00",
                    "2026-03-28 00:00:00",
                ),
                (
                    "paper-real-001",
                    "Real Paper",
                    "INDEXED",
                    str(real_pdf),
                    "real",
                    "2026-03-27 00:00:00",
                    "2026-03-27 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper-real-001"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_keeps_fixture_rows_when_only_fixtures_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper-e2e-001",
                "E2E Seed Paper",
                "INDEXED",
                str(fixture_pdf),
                "fixture",
                "2026-03-28 00:00:00",
                "2026-03-28 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper-e2e-001"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_surface_latest_run_id_from_jobs_when_ops_summary_is_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_job_only", "Job-backed Paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_job_only" / "run-job-only"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-001", "run-job-only", "paper_job_only", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_job_only"]["ops_summary"] is None
        assert by_id["paper_job_only"]["latest_run_id"] == "run-job-only"

        detail = client.get("/papers/paper_job_only")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"] is None
        assert payload["latest_run_id"] == "run-job-only"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_content_review_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_flagged", "Flagged Paper", "INDEXED", 2, "2 mapping ambiguities", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_clear", "Clear Paper", "INDEXED", 0, "No critical issues", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_unavailable", "Unavailable Paper", "INDEXED", 0, "Not analyzed", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_explicit", "Explicit State Paper", "INDEXED", 0, "No critical issues", "unavailable", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_new", "New Paper", "NEW", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_pending", "Pending Paper", "PENDING_REVIEW", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_approved", "Approved Paper", "APPROVED", "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_flagged"]["issues_state"] == "flagged"
        assert by_id["paper_clear"]["issues_state"] == "clear"
        assert by_id["paper_unavailable"]["issues_state"] == "unavailable"
        assert by_id["paper_explicit"]["issues_state"] == "unavailable"
        assert by_id["paper_new"]["issues_state"] == "unavailable"
        assert by_id["paper_pending"]["issues_state"] == "flagged"
        assert by_id["paper_approved"]["issues_state"] == "clear"

        detail = client.get("/papers/paper_unavailable")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["issues_label"] == "Not analyzed"
        assert payload["issues_state"] == "unavailable"

        explicit_detail = client.get("/papers/paper_explicit")
        assert explicit_detail.status_code == 200
        explicit_payload = explicit_detail.json()
        assert explicit_payload["issues_label"] == "No critical issues"
        assert explicit_payload["issues_state"] == "unavailable"
    finally:
        db_utils.DB_PATH = original_db_path


def test_init_db_backfills_paper_issues_state_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.init_db()

        conn = db_utils.get_db_connection()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
        conn.close()

        assert "issues_state" in columns
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pdf_endpoint_serves_existing_file_and_handles_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        existing_pdf = tmp_path / "served.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%test\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_served", "Served PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_path", "Missing Path", "INDEXED", "", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_file", "Missing File", "INDEXED", str(tmp_path / "gone.pdf"), "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        served = client.get("/papers/p_served/pdf")
        assert served.status_code == 200
        assert served.headers.get("content-type", "").startswith("application/pdf")
        assert served.content.startswith(b"%PDF")

        missing_path = client.get("/papers/p_missing_path/pdf")
        assert missing_path.status_code == 404
        assert "PDF path not registered" in missing_path.json()["detail"]

        missing_file = client.get("/papers/p_missing_file/pdf")
        assert missing_file.status_code == 404
        assert "PDF file not found" in missing_file.json()["detail"]

        missing_paper = client.get("/papers/nope/pdf")
        assert missing_paper.status_code == 404
        assert missing_paper.json()["detail"] == "Paper not found"
    finally:
        db_utils.DB_PATH = original_db_path
