from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.services.fixture_visibility as fixture_visibility
from backend import main as api_main
from src.schemas.paper_notes import PaperNoteIndexItem
from src.schemas.ops import HomeWorkspaceSummaryResponse


def test_workspace_summary_counts_visible_papers_and_notes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        api_main,
        "_load_home_workspace_summary_context",
        lambda raw_limit=5000: SimpleNamespace(
            blocked=1,
            needs_review=1,
            note_context_limited=False,
            saved_notes=2,
            structured_notes=1,
            latest_note_updated_at="2026-04-10T00:00:00Z",
        ),
    )
    monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda vault_path: (_ for _ in ()).throw(AssertionError()))

    client = TestClient(api_main.app)
    response = client.get("/workspace-summary")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 2,
        "structured_notes": 1,
        "needs_review": 1,
        "blocked": 1,
        "latest_note_updated_at": "2026-04-10T00:00:00Z",
        "note_context_limited": False,
    }


def test_workspace_summary_marks_note_context_limited_when_note_index_fails(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "_load_home_workspace_summary_context",
        lambda raw_limit=5000: SimpleNamespace(
            blocked=0,
            needs_review=0,
            note_context_limited=True,
            saved_notes=0,
            structured_notes=0,
            latest_note_updated_at=None,
        ),
    )
    monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda vault_path: (_ for _ in ()).throw(AssertionError()))

    client = TestClient(api_main.app)
    response = client.get("/workspace-summary")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 0,
        "structured_notes": 0,
        "needs_review": 0,
        "blocked": 0,
        "latest_note_updated_at": None,
        "note_context_limited": True,
    }


def test_workspace_summary_skips_eager_note_lookup_for_live_pdf_db_rows(tmp_path, monkeypatch):
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
        live_pdf = tmp_path / "library" / "workspace-live.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%workspace summary live pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_workspace_live_pdf",
                "Workspace live PDF",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        note_path = tmp_path / "vault" / "Inbox" / "PaperPipe" / "Workspace live PDF.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            "---\n"
            "id: paper_workspace_live_pdf\n"
            "aliases: [\"Workspace live PDF\"]\n"
            "status: INDEXED\n"
            "---\n\n"
            "# Workspace live PDF\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")

        def _unexpected_full_lookup(*args, **kwargs):
            raise AssertionError("workspace summary should not build a full note lookup for live-PDF DB rows")

        monkeypatch.setattr(api_main, "_build_note_item_lookup", _unexpected_full_lookup, raising=False)
        monkeypatch.setattr(
            api_main,
            "_load_visible_paper_items_context",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("workspace summary should not route through full visible paper item shaping")
            ),
            raising=False,
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 1,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 0,
            "latest_note_updated_at": api_main.paper_notes._build_index(tmp_path / "vault").items[0].updated_at,
            "note_context_limited": False,
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_uses_summary_row_subset_query(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_get_db_connection = api_main.get_db_connection
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                feedback_json TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_summary_query",
                "Summary query paper",
                "INDEXED",
                str(tmp_path / "paper.pdf"),
                0,
                None,
                "clear",
                "{\"debug\": true}",
                "large payload not needed by workspace summary",
                "2026-04-19 00:00:00",
                "2026-04-19 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "missing-vault")

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert any(
            query
            == "SELECT paper_id, title, pdf_path, status, issues, issues_label, issues_state FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET 0"
            and params == (5000,)
            for query, params in executed_queries
        )
        assert not any("SELECT * FROM papers" in query for query, _ in executed_queries)
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_derives_db_issues_state_once_per_visible_row(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "one-pass.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_summary_issue_once",
                "Summary issue once",
                "INDEXED",
                str(live_pdf),
                0,
                None,
                "clear",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "missing-vault")
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        derive_calls: list[str] = []
        original_derive = api_main._derive_paper_issues_state

        def _record_derive(item):
            derive_calls.append(str(item.get("paper_id") or ""))
            return original_derive(item)

        monkeypatch.setattr(api_main, "_derive_paper_issues_state", _record_derive)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert derive_calls == ["paper_summary_issue_once"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_skips_db_issues_state_for_blocked_rows(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "blocked-summary.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_summary_blocked_skip_issues",
                "Summary blocked skip issues",
                "INDEXED",
                str(live_pdf),
                1,
                "Needs attention",
                "warning",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            api_main,
            "build_ops_summary_for_candidate_ids",
            lambda *args, **kwargs: SimpleNamespace(state="action_needed"),
        )
        monkeypatch.setattr(
            api_main,
            "_derive_paper_issues_state",
            lambda item: (_ for _ in ()).throw(
                AssertionError("workspace summary should skip issues-state derivation for blocked DB rows")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 0,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 1,
            "latest_note_updated_at": None,
            "note_context_limited": True,
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_skips_db_identity_sets_when_note_context_is_unavailable(tmp_path, monkeypatch):
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
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_summary_no_note_context",
                "Summary no note context",
                "INDEXED",
                "",
                0,
                None,
                "clear",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        def _missing_vault():
            raise FileNotFoundError("vault unavailable")

        def _unexpected_identity_sets(*args, **kwargs):
            raise AssertionError("workspace summary should skip DB identity normalization when note context is unavailable")

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", _missing_vault)
        monkeypatch.setattr(api_main, "_paper_id_identity_sets", _unexpected_identity_sets)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        payload = response.json()
        assert payload["note_context_limited"] is True
        assert payload["blocked"] == 0
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_skips_db_identity_sets_when_note_index_is_empty(tmp_path, monkeypatch):
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
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_summary_empty_note_index",
                "Summary empty note index",
                "INDEXED",
                "",
                0,
                None,
                "clear",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=[]))
        monkeypatch.setattr(
            api_main,
            "_paper_id_identity_sets",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("workspace summary should skip DB identity normalization when the note index is empty")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        payload = response.json()
        assert payload["note_context_limited"] is False
        assert payload["saved_notes"] == 0
        assert payload["structured_notes"] == 0
        assert payload["blocked"] == 0
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_reuses_db_ops_candidate_ids_across_preload_and_final_loop(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "reuse-ops-candidates.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "zotero:paper_summary_ops_candidates",
                "Summary ops candidates",
                "INDEXED",
                str(live_pdf),
                0,
                None,
                "clear",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))

        ops_candidate_calls: list[str] = []
        original_ops_candidate_ids = api_main._ops_summary_candidate_ids

        def _record_ops_candidate_ids(paper_id):
            ops_candidate_calls.append(str(paper_id))
            return original_ops_candidate_ids(paper_id)

        monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _record_ops_candidate_ids)
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert ops_candidate_calls == ["zotero:paper_summary_ops_candidates"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_skips_db_ops_candidate_ids_for_hidden_fixture_rows(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "summary-visible-real.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-summary-hidden-ops",
                    "E2E Hidden Fixture Summary Ops",
                    "INDEXED",
                    str(fixture_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-21 00:00:00",
                    "2026-04-21 00:00:00",
                ),
                (
                    "paper_summary_visible_ops",
                    "Visible summary ops paper",
                    "INDEXED",
                    str(real_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-20 00:00:00",
                    "2026-04-20 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))

        ops_candidate_calls: list[str] = []
        original_ops_candidate_ids = api_main._ops_summary_candidate_ids

        def _record_ops_candidate_ids(paper_id):
            ops_candidate_calls.append(str(paper_id))
            return original_ops_candidate_ids(paper_id)

        monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _record_ops_candidate_ids)
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert ops_candidate_calls == ["paper_summary_visible_ops"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_uses_minimal_db_fixture_preview_record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_loader = api_main._load_paper_rows_for_workspace_summary
    original_fixture_checker = api_main.is_test_fixture_paper_record
    try:
        def _fake_loader(*, raw_limit=5000):
            return [
                {
                    "paper_id": "paper_summary_preview_real",
                    "title": "Summary preview real",
                    "pdf_path": None,
                    "status": "INDEXED",
                    "issues": 0,
                    "issues_label": None,
                    "issues_state": "clear",
                    "authors": "Real Author",
                    "doi": "10.1000/summary-preview-real",
                },
                {
                    "paper_id": "paper-e2e-summary-preview-fixture",
                    "title": "E2E Summary Preview Fixture",
                    "pdf_path": "/tmp/tests/summary-preview-fixture.pdf",
                    "status": "INDEXED",
                    "issues": 0,
                    "issues_label": None,
                    "issues_state": "clear",
                    "authors": "Fixture Author",
                    "doi": "10.1000/summary-preview-fixture",
                },
            ]

        seen_key_sets: list[tuple[str, ...]] = []

        def _counted_fixture_checker(record):
            seen_key_sets.append(tuple(sorted(record.keys())))
            return original_fixture_checker(record)

        monkeypatch.setattr(api_main, "_load_paper_rows_for_workspace_summary", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert seen_key_sets
        assert set(seen_key_sets) == {("paper_id", "pdf_path", "title")}
    finally:
        api_main._load_paper_rows_for_workspace_summary = original_loader
        api_main.is_test_fixture_paper_record = original_fixture_checker


def test_workspace_summary_resolves_fixture_inclusion_once_per_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    fixture_flag_calls = 0

    def _fixture_flag():
        nonlocal fixture_flag_calls
        fixture_flag_calls += 1
        return False

    monkeypatch.setattr(
        api_main,
        "_load_paper_rows_for_workspace_summary",
        lambda raw_limit=5000: [
            {
                "paper_id": "workspace_summary_fixture_flag_db",
                "title": "Workspace Summary Fixture Flag DB",
                "pdf_path": None,
                "status": "INDEXED",
                "issues": 0,
                "issues_label": None,
                "issues_state": "clear",
            }
        ],
    )
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        api_main,
        "_load_deduped_note_items_without_ops",
        lambda vault_path: [
            PaperNoteIndexItem(
                id="workspace_summary_fixture_flag_note",
                slug="workspace-summary-fixture-flag-note",
                title="Workspace Summary Fixture Flag Note",
                note_path="Inbox/PaperPipe/Workspace Summary Fixture Flag Note.md",
                status="INDEXED",
                updated_at="2026-04-22T00:00:00Z",
            )
        ],
        raising=False,
    )
    monkeypatch.setattr(api_main, "include_test_fixtures_enabled", _fixture_flag)
    monkeypatch.setattr(
        fixture_visibility,
        "_include_test_fixtures_enabled",
        lambda: (_ for _ in ()).throw(
            AssertionError("workspace summary should reuse the request-local fixture inclusion flag")
        ),
    )
    monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

    context = api_main._load_home_workspace_summary_context()

    assert context.saved_notes == 1
    assert context.needs_review == 0
    assert context.blocked == 0
    assert fixture_flag_calls == 1


def test_workspace_summary_skips_full_row_materialization_for_blocked_visible_db_rows(monkeypatch):
    class _BlockedRow:
        def __init__(self):
            self._payload = {
                "paper_id": "paper_summary_blocked_materialize",
                "title": "Blocked summary row",
                "pdf_path": None,
                "status": "INDEXED",
                "issues": 0,
                "issues_label": None,
                "issues_state": "clear",
            }

        def __getitem__(self, key):
            return self._payload[key]

        def get(self, key, default=None):
            return self._payload.get(key, default)

        def __iter__(self):
            raise AssertionError("blocked visible DB rows should not be materialized into dict(row)")

    original_loader = api_main._load_paper_rows_for_workspace_summary
    try:
        monkeypatch.setattr(
            api_main,
            "_load_paper_rows_for_workspace_summary",
            lambda raw_limit=5000: [_BlockedRow()],
        )
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            api_main,
            "build_ops_summary_for_candidate_ids",
            lambda *args, **kwargs: SimpleNamespace(state="action_needed"),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["blocked"] == 1
    finally:
        api_main._load_paper_rows_for_workspace_summary = original_loader


def test_workspace_summary_skips_note_candidate_group_key_for_fixture_note_hidden_by_real_note(monkeypatch, tmp_path):
    original_loader = api_main._load_paper_rows_for_workspace_summary
    original_group_key = api_main._normalized_candidate_id_group
    try:
        monkeypatch.setattr(api_main, "_load_paper_rows_for_workspace_summary", lambda raw_limit=5000: [])
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="paper-e2e-summary-note-only-fixture",
                    slug="summary-note-only-fixture",
                    title="E2E Summary Note Only Fixture",
                    note_path="Inbox/PaperPipe/E2E Summary Note Only Fixture.md",
                    status="INDEXED",
                    updated_at="2026-04-22T00:00:00Z",
                ),
                PaperNoteIndexItem(
                    id="summary-note-only-real",
                    slug="summary-note-only-real",
                    title="Summary Note Only Real",
                    note_path="Inbox/PaperPipe/Summary Note Only Real.md",
                    status="INDEXED",
                    updated_at="2026-04-21T00:00:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        recorded_group_keys: list[tuple[str, ...]] = []

        def _record_group_key(candidate_ids):
            normalized = original_group_key(candidate_ids)
            recorded_group_keys.append(normalized)
            return normalized

        monkeypatch.setattr(api_main, "_normalized_candidate_id_group", _record_group_key)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["saved_notes"] == 2
        assert recorded_group_keys == [("summary-note-only-real",)]
    finally:
        api_main._load_paper_rows_for_workspace_summary = original_loader
        api_main._normalized_candidate_id_group = original_group_key


def test_workspace_summary_uses_minimal_issues_preview_record_for_visible_non_blocked_rows(monkeypatch):
    class _VisibleRow:
        def __init__(self):
            self._payload = {
                "paper_id": "paper_summary_visible_materialize",
                "title": "Visible summary row",
                "pdf_path": None,
                "status": "INDEXED",
                "issues": 1,
                "issues_label": "Needs review",
                "issues_state": "flagged",
            }

        def __getitem__(self, key):
            return self._payload[key]

        def get(self, key, default=None):
            return self._payload.get(key, default)

        def __iter__(self):
            raise AssertionError("visible non-blocked DB rows should not be materialized into dict(row)")

    original_loader = api_main._load_paper_rows_for_workspace_summary
    try:
        monkeypatch.setattr(
            api_main,
            "_load_paper_rows_for_workspace_summary",
            lambda raw_limit=5000: [_VisibleRow()],
        )
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 1
    finally:
        api_main._load_paper_rows_for_workspace_summary = original_loader


def test_workspace_summary_reuses_ops_summary_for_equivalent_candidate_groups(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "shared-summary-ops.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "zotero:paper_summary_shared_ops",
                    "Summary shared ops A",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-21 00:00:00",
                    "2026-04-21 00:00:00",
                ),
                (
                    "paper_summary_shared_ops",
                    "Summary shared ops B",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-20 00:00:00",
                    "2026-04-20 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )

        original_ops_candidate_ids = api_main._ops_summary_candidate_ids
        recorded_ops_summary_calls: list[tuple[str, ...]] = []

        def _shared_ops_candidate_ids(paper_id):
            if str(paper_id) in {"zotero:paper_summary_shared_ops", "paper_summary_shared_ops"}:
                return ["paper_summary_shared_ops", "zotero:paper_summary_shared_ops"]
            return original_ops_candidate_ids(paper_id)

        def _record_ops_summary(artifacts_path, candidate_ids, cache):
            recorded_ops_summary_calls.append(tuple(sorted(str(value) for value in candidate_ids)))
            return None

        monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _shared_ops_candidate_ids)
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", _record_ops_summary)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert recorded_ops_summary_calls == [
            ("paper_summary_shared_ops", "zotero:paper_summary_shared_ops")
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_reuses_db_candidate_group_normalization_for_equivalent_visible_rows(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "shared-summary-group-normalization.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "zotero:paper_summary_shared_group_norm_a",
                    "Summary shared group norm A",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-21 00:00:00",
                    "2026-04-21 00:00:00",
                ),
                (
                    "paper_summary_shared_group_norm_b",
                    "Summary shared group norm B",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-20 00:00:00",
                    "2026-04-20 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        original_ops_candidate_ids = api_main._ops_summary_candidate_ids
        def _shared_ops_candidate_ids(paper_id):
            if str(paper_id) == "zotero:paper_summary_shared_group_norm_a":
                return ["paper_summary_shared_group_norm", "zotero:paper_summary_shared_group_norm"]
            if str(paper_id) == "paper_summary_shared_group_norm_b":
                return ["zotero:paper_summary_shared_group_norm", "paper_summary_shared_group_norm"]
            return original_ops_candidate_ids(paper_id)

        monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _shared_ops_candidate_ids)
        monkeypatch.setattr(
            api_main,
            "_normalized_candidate_id_group",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("summary DB group cache should build group keys from already-normalized candidate ids")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_preloads_unique_visible_db_candidate_groups_once(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "unique-summary-preload.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "zotero:summary_shared_group_a",
                    "Summary shared group A",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-21 00:00:00",
                    "2026-04-21 00:00:00",
                ),
                (
                    "summary_shared_group_b",
                    "Summary shared group B",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-20 00:00:00",
                    "2026-04-20 00:00:00",
                ),
                (
                    "summary_distinct_group_c",
                    "Summary distinct group C",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-19 00:00:00",
                    "2026-04-19 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))
        original_ops_candidate_ids = api_main._ops_summary_candidate_ids

        def _shared_ops_candidate_ids(paper_id):
            if str(paper_id) in {"zotero:summary_shared_group_a", "summary_shared_group_b"}:
                return ["summary_shared_group", "zotero:summary_shared_group"]
            if str(paper_id) == "summary_distinct_group_c":
                return ["summary_distinct_group_c"]
            return original_ops_candidate_ids(paper_id)

        preloaded_candidate_id_groups: list[list[tuple[str, ...]]] = []

        def _record_preload(artifacts_path, candidate_id_groups, cache):
            preloaded_candidate_id_groups.append([tuple(group) for group in candidate_id_groups])

        monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _shared_ops_candidate_ids)
        monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", _record_preload)
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json()["needs_review"] == 0
        assert preloaded_candidate_id_groups == [
            [
                ("summary_shared_group", "zotero:summary_shared_group"),
                ("summary_distinct_group_c",),
            ]
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_reuses_preloaded_artifact_cache_for_visible_db_candidate_groups(
    tmp_path, monkeypatch
):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "cached-summary-preload.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "summary_cached_group_a",
                    "Summary cached group A",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-21 00:00:00",
                    "2026-04-21 00:00:00",
                ),
                (
                    "summary_cached_group_b",
                    "Summary cached group B",
                    "INDEXED",
                    str(live_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-20 00:00:00",
                    "2026-04-20 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))

        def _seed_preload(artifacts_path, candidate_id_groups, cache):
            for group in candidate_id_groups:
                for candidate_id in group:
                    cache[str(candidate_id)] = api_main.ArtifactOperationalSnapshot(
                        paper_id=str(candidate_id),
                        run_id=f"run-{candidate_id}",
                        updated_at="2026-04-21T00:00:00+00:00",
                        mtime=1.0,
                        has_claimset=True,
                        has_stats_report=True,
                        stats_check_count=1,
                    )

        monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", _seed_preload)
        monkeypatch.setattr(
            api_main,
            "build_ops_summary_for_candidate_ids",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("workspace summary should reuse preloaded artifact cache before rebuilding ops summaries")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 0,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 0,
            "latest_note_updated_at": None,
            "note_context_limited": True,
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_skips_hidden_fixture_rows_before_artifact_preload(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
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
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-hidden",
                    "E2E Hidden Fixture",
                    "INDEXED",
                    str(fixture_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-18 00:00:00",
                    "2026-04-18 00:00:00",
                ),
                (
                    "paper_real_visible",
                    "Real visible paper",
                    "INDEXED",
                    str(real_pdf),
                    0,
                    None,
                    "clear",
                    "2026-04-17 00:00:00",
                    "2026-04-17 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        preloaded_candidate_id_groups: list[list[list[str]]] = []

        def _record_preload(artifacts_path, candidate_id_groups, cache):
            preloaded_candidate_id_groups.append([list(group) for group in candidate_id_groups])

        def _guarded_ops_summary(artifacts_path, candidate_ids, cache):
            assert candidate_ids == ["paper_real_visible"]
            return None

        def _missing_vault():
            raise FileNotFoundError()

        monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", _record_preload)
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", _guarded_ops_summary)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", _missing_vault)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 0,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 0,
            "latest_note_updated_at": None,
            "note_context_limited": True,
        }
        assert preloaded_candidate_id_groups == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_defers_note_ops_until_note_only_items_are_visible(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "shared.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_shared_summary",
                "Shared summary paper",
                "INDEXED",
                str(live_pdf),
                0,
                None,
                "clear",
                "2026-04-20 00:00:00",
                "2026-04-20 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("workspace summary should not precompute note ops for all notes")
            ),
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="paper_shared_summary",
                    slug="paper_shared_summary",
                    title="Shared summary paper",
                    note_path="Inbox/PaperPipe/Shared summary paper.md",
                    status="INDEXED",
                    updated_at="2026-04-20T00:00:00Z",
                ),
                PaperNoteIndexItem(
                    id="note_only_summary",
                    slug="note_only_summary",
                    title="Note only summary paper",
                    note_path="Inbox/PaperPipe/Note only summary paper.md",
                    status="INDEXED",
                    updated_at="2026-04-19T00:00:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )

        recorded_candidate_calls: list[tuple[str, ...]] = []

        def _record_ops_summary(artifacts_path, candidate_ids, cache):
            recorded_candidate_calls.append(tuple(sorted(str(value) for value in candidate_ids)))
            return None

        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", _record_ops_summary)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 0,
            "latest_note_updated_at": "2026-04-20T00:00:00Z",
            "note_context_limited": False,
        }
        assert len(recorded_candidate_calls) == 2
        assert any("paper_shared_summary" in call for call in recorded_candidate_calls)
        assert any("note_only_summary" in call for call in recorded_candidate_calls)
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_skips_fixture_db_artifact_work_when_note_only_non_fixture_wins_visibility(tmp_path, monkeypatch):
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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "fixture.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper-e2e-summary-fixture",
                "E2E Summary Fixture",
                "INDEXED",
                str(fixture_pdf),
                0,
                None,
                "clear",
                "2026-04-20 00:00:00",
                "2026-04-20 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="workspace_note_only_visible",
                    slug="workspace-note-only-visible",
                    title="Workspace Note Only Visible",
                    note_path="Inbox/PaperPipe/Workspace Note Only Visible.md",
                    status="INDEXED",
                    updated_at="2026-04-21T00:00:00Z",
                ),
                PaperNoteIndexItem(
                    id="paper-e2e-note-fixture",
                    slug="workspace-note-fixture",
                    title="E2E Fixture Note",
                    note_path="Inbox/PaperPipe/E2E Fixture Note.md",
                    status="INDEXED",
                    updated_at="2026-04-19T00:00:00Z",
                ),
            ],
            raising=False,
        )

        preloaded_paper_ids: list[list[str]] = []
        recorded_ops_candidates: list[tuple[str, ...]] = []

        def _record_preload(artifacts_path, paper_ids, cache):
            preloaded_paper_ids.append(list(paper_ids))

        def _record_ops_summary(artifacts_path, candidate_ids, cache):
            recorded_ops_candidates.append(tuple(sorted(str(value) for value in candidate_ids)))
            return None

        monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", _record_preload)
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", _record_ops_summary)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 0,
            "latest_note_updated_at": "2026-04-21T00:00:00Z",
            "note_context_limited": False,
        }
        assert preloaded_paper_ids == []
        assert len(recorded_ops_candidates) == 1
        assert "paper-e2e-summary-fixture" not in recorded_ops_candidates[0]
        assert "paper-e2e-note-fixture" not in recorded_ops_candidates[0]
        assert "workspace_note_only_visible" in recorded_ops_candidates[0]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_defers_note_only_status_and_ops_until_after_fixture_filter(
    tmp_path, monkeypatch
):
    class _HiddenFixtureNote:
        def __init__(self):
            self.id = "paper-e2e-summary-deferred-fixture"
            self.slug = "summary-deferred-hidden-fixture"
            self.title = "E2E Summary Deferred Fixture"
            self.note_path = "Inbox/PaperPipe/E2E Summary Deferred Fixture.md"
            self.structured_state_present = False
            self.updated_at = "2026-07-08T09:26:00Z"

        def __getattribute__(self, name):
            if name in {"ops_summary", "status"}:
                raise AssertionError(
                    "workspace summary should not read status or ops summary for fixture notes hidden by final visibility filtering"
                )
            return object.__getattribute__(self, name)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    hidden_fixture_note = _HiddenFixtureNote()
    original_identity_sets = api_main._paper_note_identity_sets
    original_metadata = api_main._paper_note_listing_candidate_metadata
    original_fixture_preview = api_main._paper_note_fixture_preview_is_fixture
    original_group_key = api_main._paper_note_ops_candidate_group_key

    def _identity_sets(note_item):
        if note_item is hidden_fixture_note:
            raw_variants = {hidden_fixture_note.id, hidden_fixture_note.slug}
            normalized_variants = {
                normalized
                for value in raw_variants
                if (normalized := api_main.paper_notes._normalize_paper_note_id(value))
            }
            return raw_variants, normalized_variants
        return original_identity_sets(note_item)

    def _listing_metadata(note_item):
        if note_item is hidden_fixture_note:
            return (
                hidden_fixture_note.id,
                hidden_fixture_note.title,
                hidden_fixture_note.updated_at,
                True,
            )
        return original_metadata(note_item)

    def _fixture_preview(note_item):
        if note_item is hidden_fixture_note:
            return False
        return original_fixture_preview(note_item)

    def _group_key(note_item):
        if note_item is hidden_fixture_note:
            raise AssertionError(
                "workspace summary should not compute ops group keys for notes hidden by final visibility filtering"
            )
        return original_group_key(note_item)

    monkeypatch.setattr(api_main, "_load_paper_rows_for_workspace_summary", lambda raw_limit=5000: [])
    monkeypatch.setattr(api_main, "include_test_fixtures_enabled", lambda: False)
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        api_main,
        "_load_deduped_note_items_without_ops",
        lambda vault_path: [
            PaperNoteIndexItem(
                id="summary-deferred-real-note",
                slug="summary-deferred-real-note",
                title="Summary Deferred Real Note",
                note_path="Inbox/PaperPipe/Summary Deferred Real Note.md",
                status="NEW",
                updated_at="2026-07-08T09:25:00Z",
            ),
            hidden_fixture_note,
        ],
        raising=False,
    )
    monkeypatch.setattr(api_main, "_paper_note_identity_sets", _identity_sets)
    monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _listing_metadata)
    monkeypatch.setattr(api_main, "_paper_note_fixture_preview_is_fixture", _fixture_preview)
    monkeypatch.setattr(api_main, "_paper_note_ops_candidate_group_key", _group_key)
    monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

    context = api_main._load_home_workspace_summary_context()

    assert context.saved_notes == 2
    assert context.structured_notes == 0
    assert context.needs_review == 1
    assert context.blocked == 0
    assert context.latest_note_updated_at == "2026-07-08T09:26:00Z"


def test_workspace_summary_preloads_multi_group_note_only_candidates_once(tmp_path, monkeypatch):
    class _ArtifactBackedNote(PaperNoteIndexItem):
        def __getattribute__(self, name):
            if name == "ops_summary":
                raise AssertionError(
                    "workspace summary should not read note ops summaries when artifact cache already has a summary"
                )
            return super().__getattribute__(name)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                _ArtifactBackedNote(
                    id="workspace_note_only_group_a",
                    slug="workspace-note-only-group-a",
                    title="Workspace Note Only Group A",
                    note_path="Inbox/PaperPipe/Workspace Note Only Group A.md",
                    status="INDEXED",
                    updated_at="2026-04-21T00:00:00Z",
                ),
                _ArtifactBackedNote(
                    id="workspace_note_only_group_b",
                    slug="workspace-note-only-group-b",
                    title="Workspace Note Only Group B",
                    note_path="Inbox/PaperPipe/Workspace Note Only Group B.md",
                    status="INDEXED",
                    updated_at="2026-04-20T00:00:00Z",
                ),
            ],
            raising=False,
        )

        preloaded_candidate_groups: list[list[tuple[str, ...]]] = []

        def _record_preload(artifacts_path, candidate_id_groups, cache):
            preloaded_candidate_groups.append([tuple(group) for group in candidate_id_groups])
            for group in candidate_id_groups:
                for candidate_id in group:
                    cache[str(candidate_id)] = api_main.ArtifactOperationalSnapshot(
                        paper_id=str(candidate_id),
                        run_id=f"run-{candidate_id}",
                        updated_at="2026-04-21T00:00:00+00:00",
                        mtime=1.0,
                        has_claimset=True,
                        has_stats_report=True,
                        stats_check_count=1,
                    )

        monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", _record_preload)
        monkeypatch.setattr(
            api_main,
            "build_ops_summary_for_candidate_ids",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("workspace summary should reuse preloaded artifact cache for multi-group note-only candidates")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 0,
            "blocked": 0,
            "latest_note_updated_at": "2026-04-21T00:00:00Z",
            "note_context_limited": False,
        }
        assert preloaded_candidate_groups == [
            [
                ("workspace-note-only-group-a", "workspace_note_only_group_a"),
                ("workspace-note-only-group-b", "workspace_note_only_group_b"),
            ]
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_hidden_fixture_note_does_not_block_later_real_duplicate_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

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
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "summary-real-anchor.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_summary_real_anchor",
                "Summary real anchor",
                "INDEXED",
                str(live_pdf),
                0,
                None,
                "clear",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        shared_note_id = "shared-summary-note-2026"
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id=shared_note_id,
                    slug="e2e-summary-hidden-fixture",
                    title="E2E Summary Hidden Fixture",
                    note_path="Inbox/PaperPipe/E2E Summary Hidden Fixture.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id=shared_note_id,
                    slug="summary-real-note",
                    title="Summary Real Note",
                    note_path="Inbox/PaperPipe/Summary Real Note.md",
                    status="NEW",
                    updated_at="2026-07-03T09:24:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 1,
            "blocked": 0,
            "latest_note_updated_at": "2026-07-03T09:25:00Z",
            "note_context_limited": False,
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_fixture_note_does_not_block_later_real_duplicate_without_db_anchor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="shared-summary-note-only-duplicate-2026",
                    slug="e2e-summary-note-only-fixture",
                    title="E2E Summary Note-only Fixture",
                    note_path="Inbox/PaperPipe/E2E Summary Note-only Fixture.md",
                    status="INDEXED",
                    updated_at="2026-07-06T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id="shared-summary-note-only-duplicate-2026",
                    slug="summary-note-only-real",
                    title="Summary Note-only Real",
                    note_path="Inbox/PaperPipe/Summary Note-only Real.md",
                    status="NEW",
                    updated_at="2026-07-06T09:24:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 1,
            "blocked": 0,
            "latest_note_updated_at": "2026-07-06T09:25:00Z",
            "note_context_limited": False,
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_hidden_fixture_note_skips_metadata_when_real_note_is_already_visible(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_metadata_helper = api_main._paper_note_listing_candidate_metadata
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="summary-real-visible-note-2026",
                    slug="summary-real-visible-note",
                    title="Summary Real Visible Note",
                    note_path="Inbox/PaperPipe/Summary Real Visible Note.md",
                    status="NEW",
                    updated_at="2026-07-06T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id="paper-e2e-summary-hidden-fixture-note",
                    slug="summary-hidden-fixture-note",
                    title="E2E Summary Hidden Fixture Note",
                    note_path="Inbox/PaperPipe/E2E Summary Hidden Fixture Note.md",
                    status="INDEXED",
                    updated_at="2026-07-06T09:24:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        def _guarded_metadata(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "paper-e2e-summary-hidden-fixture-note":
                raise AssertionError(
                    "workspace summary should not build listing metadata for hidden fixture notes after a real note is visible"
                )
            return original_metadata_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _guarded_metadata)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 1,
            "blocked": 0,
            "latest_note_updated_at": "2026-07-06T09:25:00Z",
            "note_context_limited": False,
        }
    finally:
        api_main._paper_note_listing_candidate_metadata = original_metadata_helper
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_hidden_fixture_note_skips_identity_sets_when_real_note_is_already_visible(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_identity_helper = api_main._paper_note_identity_sets
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="summary-real-visible-note-identity-2026",
                    slug="summary-real-visible-note-identity",
                    title="Summary Real Visible Note Identity",
                    note_path="Inbox/PaperPipe/Summary Real Visible Note Identity.md",
                    status="NEW",
                    updated_at="2026-07-07T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id="paper-e2e-summary-hidden-fixture-note-identity",
                    slug="summary-hidden-fixture-note-identity",
                    title="E2E Summary Hidden Fixture Note Identity",
                    note_path="Inbox/PaperPipe/E2E Summary Hidden Fixture Note Identity.md",
                    status="INDEXED",
                    updated_at="2026-07-07T09:24:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        def _guarded_identity_sets(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "paper-e2e-summary-hidden-fixture-note-identity":
                raise AssertionError(
                    "workspace summary should not build identity sets for hidden fixture notes after a real note is visible"
                )
            return original_identity_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _guarded_identity_sets)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 2,
            "structured_notes": 0,
            "needs_review": 1,
            "blocked": 0,
            "latest_note_updated_at": "2026-07-07T09:25:00Z",
            "note_context_limited": False,
        }
    finally:
        api_main._paper_note_identity_sets = original_identity_helper
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_hidden_fixture_db_row_does_not_block_later_real_duplicate_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

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
            INSERT INTO papers (paper_id, title, status, pdf_path, issues, issues_label, issues_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper-e2e-summary-fixture-db-duplicate",
                "E2E Summary Fixture DB Duplicate",
                "INDEXED",
                None,
                0,
                None,
                "clear",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="workspace-summary-real-duplicate-note",
                    slug="paper-e2e-summary-fixture-db-duplicate",
                    title="Summary Real Duplicate Note",
                    note_path="Inbox/PaperPipe/Summary Real Note From Fixture DB.md",
                    status="NEW",
                    updated_at="2026-07-04T09:25:00Z",
                ),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_preload_artifact_snapshots_for_candidate_id_groups",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        assert response.json() == {
            "saved_notes": 1,
            "structured_notes": 0,
            "needs_review": 1,
            "blocked": 0,
            "latest_note_updated_at": "2026-07-04T09:25:00Z",
            "note_context_limited": False,
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_handles_missing_papers_table_with_note_context(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(tmp_path / "state.db"))

    api_main.db_utils.init_db()
    note_path = tmp_path / "vault" / "Inbox" / "PaperPipe" / "Note only.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\n"
        "id: note-only\n"
        "aliases: [\"Note only\"]\n"
        "status: INDEXED\n"
        "---\n\n"
        "# Note only\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        api_main.paper_notes,
        "_build_index",
        lambda vault_path: SimpleNamespace(
            items=[
                PaperNoteIndexItem(
                    id="note-only",
                    slug="note-only",
                    title="Note only",
                    note_path="Inbox/PaperPipe/Note only.md",
                    status="INDEXED",
                    structured_state_present=False,
                    updated_at="2026-04-14T00:00:00Z",
                )
            ]
        ),
    )

    client = TestClient(api_main.app)
    response = client.get("/workspace-summary")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 1,
        "structured_notes": 0,
        "needs_review": 0,
        "blocked": 0,
        "latest_note_updated_at": "2026-04-14T00:00:00Z",
        "note_context_limited": False,
    }


def test_workspace_summary_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")

    client = TestClient(api_main.app)
    blocked = client.get("/workspace-summary")
    assert blocked.status_code == 401
    assert blocked.json()["error_code"] == "UNAUTHORIZED"

    monkeypatch.setattr(
        api_main,
        "_build_home_workspace_summary",
        lambda: HomeWorkspaceSummaryResponse(
            saved_notes=1,
            structured_notes=1,
            needs_review=0,
            blocked=0,
            latest_note_updated_at="2026-04-10T00:00:00Z",
            note_context_limited=False,
        ),
    )
    allowed = client.get("/workspace-summary", headers={"X-API-Key": "secret-key"})
    assert allowed.status_code == 200
    assert allowed.json()["saved_notes"] == 1
