from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from backend.routers import method_comparisons as method_comparisons_router
from src.schemas.agent_artifacts import StatCheckEntry, StatsReport, VerificationStatus
from src.skills import runner as skills_runner


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    conn = db_utils.get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NEW',
            pdf_path TEXT,
            summary TEXT,
            feedback_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    return original_db_path


def test_write_endpoints_require_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        deepread = client.post("/jobs/deepread", json={"paper_id": "paper_auth_001"})
        assert deepread.status_code == 401
        assert deepread.json()["error_code"] == "UNAUTHORIZED"

        cancel = client.post("/jobs/job_auth_001/cancel")
        assert cancel.status_code == 401

        feedback = client.post(
            "/feedback",
            json={
                "paper_id": "paper_auth_001",
                "run_id": "run_auth_001",
                "user_correction": "fix claim wording",
                "accepted": True,
            },
        )
        assert feedback.status_code == 401

        obsidian_sync = client.post("/obsidian/sync", json={"paper_id": "paper_auth_001", "run_id": "run_auth_001"})
        assert obsidian_sync.status_code == 401

        repair_stats = client.post("/ops/repair-stats", json={"paper_ids": ["paper_auth_001"]})
        assert repair_stats.status_code == 401

        skills_run = client.post("/skills/run", json={"slug": "paper_auth_001", "action": "validate_citations"})
        assert skills_run.status_code == 401

        research_dna_create = client.post(
            "/research-dna",
            json={
                "topic": "Mild cognitive impairment and medium-chain triglycerides",
                "intent": "systematic_review",
                "actor_type": "human_api",
                "actor_id": "tester",
                "reason": "create via api",
            },
        )
        assert research_dna_create.status_code == 401

        meeting_pack_generate = client.post(
            "/meeting-packs/generate",
            json={"mode": "journal_club", "source_items": [{"type": "paper_slug", "ref": "paper_auth_001"}]},
        )
        assert meeting_pack_generate.status_code == 401

        method_comparison_generate = client.post(
            "/method-comparisons/generate",
            json={"paper_ids": ["paper_auth_001"], "field_ids": ["intervention"]},
        )
        assert method_comparison_generate.status_code == 401

        chart_pack_generate = client.post(
            "/chart-packs/generate",
            json={
                "charts": [
                    {
                        "template_id": "stats_check_status_counts",
                        "source_ref": {
                            "source_kind": "stats_report",
                            "paper_id": "paper_auth_001",
                            "run_id": "run_auth_001",
                        },
                        "field_mappings": [
                            {"target_field": "status", "source_field": "status"},
                            {"target_field": "value", "source_field": "count"},
                        ],
                    }
                ]
            },
        )
        assert chart_pack_generate.status_code == 401

        image_evidence_register = client.post(
            "/image-evidence/register",
            json={
                "source_ref": {"source_kind": "external_image_ref", "external_ref": "omero://image/123"},
                "content_format": "image/png",
            },
        )
        assert image_evidence_register.status_code == 401

    finally:
        db_utils.DB_PATH = original_db_path


def test_write_endpoints_accept_valid_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        note_path = vault_dir / "Inbox" / "PaperPipe" / "paper_auth_allow_001.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    "id: zotero:paper_auth_allow_001",
                    'aliases: ["Auth Note"]',
                    "tags:",
                    "  - Auth/Test",
                    "date_processed: 2026-03-09",
                    "confidence: 0.75",
                    "status: INDEXED",
                    "doi: 10.1000/182",
                    "---",
                    "",
                    "# Auth Note",
                    "",
                    "## 🔗 References",
                    "* [Publisher Link](https://example.org/auth)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        policy_path = tmp_path / "config" / "skills_policy.yaml"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            "\n".join(
                [
                    "version: 1",
                    "",
                    "defaults:",
                    "  enabled: false",
                    "  sandbox: native",
                    "  network: none",
                    "  timeout_seconds: 30",
                    "",
                    "actions:",
                    "  validate_citations:",
                    "    enabled: true",
                    "    category: core-safe",
                    "    source_skill: citation-management",
                    "    license: MIT",
                    "    sandbox: native",
                    "    network: none",
                    "    timeout_seconds: 15",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            skills_runner,
            "load_config",
            lambda: type(
                "Config",
                (),
                {
                    "paths": type(
                        "Paths",
                        (),
                        {
                            "obsidian_vault": vault_dir,
                            "library_dir": tmp_path / "Library",
                        },
                    )(),
                    "system": type("System", (), {"unpaywall_email": None})(),
                },
            )(),
        )
        monkeypatch.setattr(
            method_comparisons_router,
            "load_config",
            lambda: type(
                "Config",
                (),
                {
                    "paths": type(
                        "Paths",
                        (),
                        {
                            "obsidian_vault": vault_dir,
                            "library_dir": tmp_path / "Library",
                        },
                    )(),
                    "system": type("System", (), {"unpaywall_email": None})(),
                },
            )(),
        )

        client = TestClient(api_main.app)
        headers = {"X-API-Key": "secret-key"}

        deepread = client.post("/jobs/deepread", json={"paper_id": "paper_auth_allow_001"}, headers=headers)
        assert deepread.status_code == 200

        cancel = client.post("/jobs/job_auth_allow_001/cancel", headers=headers)
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"

        feedback = client.post(
            "/feedback",
            json={
                "paper_id": "paper_auth_allow_001",
                "run_id": "run_auth_allow_001",
                "user_correction": "accepted correction",
                "accepted": True,
            },
            headers=headers,
        )
        assert feedback.status_code == 200

        repair_stats = client.post(
            "/ops/repair-stats",
            json={"paper_ids": ["paper_auth_allow_001"], "dry_run": True},
            headers=headers,
        )
        assert repair_stats.status_code == 200

        skills_run = client.post(
            "/skills/run",
            json={"slug": "paper_auth_allow_001", "action": "validate_citations"},
            headers=headers,
        )
        assert skills_run.status_code == 200

        monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
        research_dna_create = client.post(
            "/research-dna",
            json={
                "topic": "Mild cognitive impairment and medium-chain triglycerides",
                "intent": "systematic_review",
                "actor_type": "human_api",
                "actor_id": "tester",
                "reason": "create via api",
            },
            headers=headers,
        )
        assert research_dna_create.status_code == 200

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "system:",
                    "  log_level: INFO",
                    "paths:",
                    f"  zotero_base_dir: {vault_dir}",
                    f"  obsidian_vault: {vault_dir}",
                    "search:",
                    "  constraints:",
                    "    min_pubmed: 2",
                    "    max_preprint: 1",
                    "  slots:",
                    "    primary:",
                    '      query: "test"',
                    "llm:",
                    "  mode: local",
                    "  features:",
                    "    trial_extraction:",
                    "      enabled: false",
                    "    slot_classification:",
                    "      enabled: false",
                    "    one_liner:",
                    "      enabled: false",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
        monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(tmp_path / "meeting_packs"))
        monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(tmp_path / "method_comparisons"))
        monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(tmp_path / "chart_packs"))
        monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

        structured_state_path = vault_dir / ".pp" / "paper_auth_allow_001" / "state.json"
        structured_state_path.parent.mkdir(parents=True, exist_ok=True)
        structured_state_path.write_text(
            "\n".join(
                [
                    "{",
                    '  "paper_slug": "paper_auth_allow_001",',
                    '  "updated_at": "2026-03-13T00:00:00Z",',
                    '  "runs": [{"id": "skill-20260313T000000Z-critical_appraisal", "action": "critical_appraisal", "ts": "2026-03-13T00:00:00Z", "status": "succeeded", "summary": "Generated claim/evidence state."}],',
                    '  "signals": {"has_claimset": true, "claim_count": 1, "evidence_count": 1, "run_count": 1},',
                    '  "claimset": [{"id": "claim_auth_001", "run_id": "skill-20260313T000000Z-critical_appraisal", "claim": "Auth claim", "evidence_ids": ["evidence_auth_001"], "evidence": [{"id": "evidence_auth_001", "claim_id": "claim_auth_001", "run_id": "skill-20260313T000000Z-critical_appraisal", "text": "Auth evidence", "locator": {"page": 1, "section": "Abstract", "source": "state.json"}}]}],',
                    '  "entities": [],',
                    '  "mesh": [],',
                    '  "outcomes": []',
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        artifact_run_dir = tmp_path / "artifacts" / "paper_auth_allow_001" / "run_auth_allow_001"
        artifact_run_dir.mkdir(parents=True, exist_ok=True)
        (artifact_run_dir / "claimset.resolved.json").write_text(
            "\n".join(
                [
                    "{",
                    '  "doc_id": "paper_auth_allow_001",',
                    '  "claims": [',
                    '    {',
                    '      "claim_id": "CLM-AUTH-001",',
                    '      "statement": "Intervention: Auth intervention.",',
                    '      "evidence_spans": [{"quote": "Intervention: Auth intervention.", "page": 1}]',
                    "    }",
                    "  ]",
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        (artifact_run_dir / "stats_report.json").write_text(
            StatsReport(
                doc_id="paper_auth_allow_001",
                run_id="run_auth_allow_001",
                checks=[
                    StatCheckEntry(
                        check_id="c1",
                        test_type="t-test",
                        reported_p="0.05",
                        computed_p=0.04,
                        code="print('ok')",
                        outputs="ok",
                        verdict=VerificationStatus.VERIFIED,
                    )
                ],
            ).model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

        meeting_pack_generate = client.post(
            "/meeting-packs/generate",
            json={"mode": "journal_club", "source_items": [{"type": "paper_slug", "ref": "paper_auth_allow_001"}]},
            headers=headers,
        )
        assert meeting_pack_generate.status_code == 200
        pack_id = meeting_pack_generate.json()["pack"]["id"]

        meeting_pack_regenerate = client.post(
            f"/meeting-packs/{pack_id}/regenerate",
            headers=headers,
        )
        assert meeting_pack_regenerate.status_code == 200

        meeting_pack_rerender = client.post(
            f"/meeting-packs/{pack_id}/rerender",
            headers=headers,
        )
        assert meeting_pack_rerender.status_code == 200

        method_comparison_generate = client.post(
            "/method-comparisons/generate",
            json={
                "comparison_id": "methodcmp_auth_demo",
                "paper_ids": ["paper_auth_allow_001"],
                "field_ids": ["intervention"],
            },
            headers=headers,
        )
        assert method_comparison_generate.status_code == 200

        chart_pack_generate = client.post(
            "/chart-packs/generate",
            json={
                "chart_pack_id": "chartpack_auth_allow_001",
                "charts": [
                    {
                        "template_id": "stats_check_status_counts",
                        "source_ref": {
                            "source_kind": "stats_report",
                            "paper_id": "paper_auth_allow_001",
                            "run_id": "run_auth_allow_001",
                        },
                        "field_mappings": [
                            {"target_field": "status", "source_field": "status"},
                            {"target_field": "value", "source_field": "count"},
                        ],
                    }
                ],
            },
            headers=headers,
        )
        assert chart_pack_generate.status_code == 200

        image_evidence_register = client.post(
            "/image-evidence/register",
            json={
                "image_evidence_id": "img_auth_allow",
                "source_ref": {"source_kind": "external_image_ref", "external_ref": "omero://image/123"},
                "content_format": "image/png",
            },
            headers=headers,
        )
        assert image_evidence_register.status_code == 200
        assert image_evidence_register.json()["image_evidence"]["image_evidence_id"] == "img_auth_allow"

    finally:
        db_utils.DB_PATH = original_db_path


def test_non_sensitive_endpoints_do_not_require_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "system:",
                    "  log_level: INFO",
                    "paths:",
                    f"  zotero_base_dir: {vault_dir}",
                    f"  obsidian_vault: {vault_dir}",
                    "search:",
                    "  constraints:",
                    "    min_pubmed: 2",
                    "    max_preprint: 1",
                    "  slots:",
                    "    primary:",
                    '      query: "test"',
                    "llm:",
                    "  mode: local",
                    "  features:",
                    "    trial_extraction:",
                    "      enabled: false",
                    "    slot_classification:",
                    "      enabled: false",
                    "    one_liner:",
                    "      enabled: false",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
        monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(tmp_path / "meeting_packs"))

        structured_state_path = vault_dir / ".pp" / "paper_auth_read_001" / "state.json"
        structured_state_path.parent.mkdir(parents=True, exist_ok=True)
        structured_state_path.write_text(
            "\n".join(
                [
                    "{",
                    '  "paper_slug": "paper_auth_read_001",',
                    '  "updated_at": "2026-03-13T00:00:00Z",',
                    '  "runs": [{"id": "skill-20260313T000000Z-critical_appraisal", "action": "critical_appraisal", "ts": "2026-03-13T00:00:00Z", "status": "succeeded", "summary": "Generated claim/evidence state."}],',
                    '  "signals": {"has_claimset": true, "claim_count": 1, "evidence_count": 1, "run_count": 1},',
                    '  "claimset": [{"id": "claim_read_001", "run_id": "skill-20260313T000000Z-critical_appraisal", "claim": "Read claim", "evidence_ids": ["evidence_read_001"], "evidence": [{"id": "evidence_read_001", "claim_id": "claim_read_001", "run_id": "skill-20260313T000000Z-critical_appraisal", "text": "Read evidence", "locator": {"page": 1, "section": "Abstract", "source": "state.json"}}]}],',
                    '  "entities": [],',
                    '  "mesh": [],',
                    '  "outcomes": []',
                    "}",
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(api_main.app)

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        chat_stub = client.post("/api/chat", json={"paper_slug": "paper_auth_001", "message": "hello"})
        assert chat_stub.status_code == 501
        assert chat_stub.json()["error_code"] == "CHAT_NOT_IMPLEMENTED"

        pack_id = "meetingpack_20260313T090000Z_journal_club_authread"
        pack_dir = tmp_path / "meeting_packs" / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "meeting_pack.json").write_text(
            "\n".join(
                [
                    "{",
                    f'  "id": "{pack_id}",',
                    '  "mode": "journal_club",',
                    '  "title": "Read auth draft",',
                    '  "created_at": "2026-03-13T09:00:00Z",',
                    '  "status": "draft",',
                    '  "readiness": "evidence_backed",',
                    '  "source_items": [{"id": "src_01", "type": "paper_slug", "ref": "paper_auth_read_001", "title": "paper_auth_read_001", "priority": 1, "included": true}],',
                    '  "one_page_summary": {"overview": "Read auth summary"},',
                    '  "slides": [],',
                    '  "speaker_notes": [],',
                    '  "discussion_questions": [],',
                    '  "expected_questions": [],',
                    '  "next_steps": [],',
                    '  "evidence_refs": []',
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        (pack_dir / "meeting_pack.md").write_text("# Read auth draft\n", encoding="utf-8")

        meeting_pack_validate = client.get(f"/meeting-packs/{pack_id}/validate")
        assert meeting_pack_validate.status_code == 200
    finally:
        db_utils.DB_PATH = original_db_path


def test_sensitive_read_endpoints_require_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        existing_pdf = tmp_path / "served.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%auth-read\n")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_auth_read_001" / "run_auth_read_001"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "document_artifact.json").write_text('{"doc_id":"paper_auth_read_001"}', encoding="utf-8")
        (artifact_dir / "bootstrap_meta.json").write_text('{"claimset_readiness_badge":"READY"}', encoding="utf-8")

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_auth_read_001", "Auth Read PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_auth_read_001",
                "run_auth_read_001",
                "paper_auth_read_001",
                "completed",
                100,
                "completed",
                "2026-03-28 00:00:00",
                "2026-03-28 00:00:05",
                str(artifact_dir),
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        responses = [
            client.get("/papers/paper_auth_read_001/pdf"),
            client.get("/artifacts", params={"paper_id": "paper_auth_read_001", "run_id": "run_auth_read_001"}),
            client.get("/artifacts/paper_auth_read_001/latest"),
            client.get("/jobs"),
            client.get("/jobs/job_auth_read_001"),
            client.get("/jobs/job_auth_read_001/bootstrap-meta"),
            client.get("/jobs/job_auth_read_001/events"),
            client.get("/runs/run_auth_read_001"),
            client.get("/runs/run_auth_read_001/timeline"),
            client.get("/user-actions", params={"paper_id": "paper_auth_read_001", "limit": 10}),
        ]

        for response in responses:
            assert response.status_code == 401
            assert response.json()["error_code"] == "UNAUTHORIZED"
    finally:
        db_utils.DB_PATH = original_db_path


def test_api_prefixed_routes_bridge_browser_calls_without_exposing_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        existing_pdf = tmp_path / "browser.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%browser-api\n")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_browser_api_001" / "run_browser_api_001"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "document_artifact.json").write_text('{"doc_id":"paper_browser_api_001"}', encoding="utf-8")
        (artifact_dir / "bootstrap_meta.json").write_text('{"claimset_readiness_badge":"READY"}', encoding="utf-8")

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_browser_api_001", "Browser API PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_browser_api_001",
                "run_browser_api_001",
                "paper_browser_api_001",
                "completed",
                100,
                "completed",
                "2026-03-28 00:00:00",
                "2026-03-28 00:00:05",
                str(artifact_dir),
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        user_action = client.post(
            "/api/user-actions",
            json={"paper_id": "paper_browser_api_001", "action_type": "open_workbench", "source": "ui"},
        )
        assert user_action.status_code == 200

        user_actions = client.get(
            "/api/user-actions",
            params={"paper_id": "paper_browser_api_001", "limit": 10},
        )
        assert user_actions.status_code == 200
        assert len(user_actions.json()["actions"]) >= 1

        jobs = client.get("/api/jobs")
        assert jobs.status_code == 200
        assert any(item["job_id"] == "job_browser_api_001" for item in jobs.json())

        job_status = client.get("/api/jobs/job_browser_api_001")
        assert job_status.status_code == 200
        assert job_status.json()["run_id"] == "run_browser_api_001"

        bootstrap_meta = client.get("/api/jobs/job_browser_api_001/bootstrap-meta")
        assert bootstrap_meta.status_code == 200
        assert bootstrap_meta.json()["claimset_readiness_badge"] == "READY"

        run_status = client.get("/api/runs/run_browser_api_001")
        assert run_status.status_code == 200
        assert run_status.json()["job_id"] == "job_browser_api_001"

        artifact_bundle = client.get(
            "/api/artifacts",
            params={"paper_id": "paper_browser_api_001", "run_id": "run_browser_api_001"},
        )
        assert artifact_bundle.status_code == 200
        assert artifact_bundle.json()["files"]["document_artifact"]["exists"] is True

        artifact_latest = client.get("/api/artifacts/paper_browser_api_001/latest")
        assert artifact_latest.status_code == 200
        assert artifact_latest.json()["run_id"] == "run_browser_api_001"

        paper_pdf = client.get("/api/papers/paper_browser_api_001/pdf")
        assert paper_pdf.status_code == 200
        assert paper_pdf.content.startswith(b"%PDF")

        events = client.get("/api/jobs/job_browser_api_001/events")
        assert events.status_code == 200
        assert "event: status" in events.text
    finally:
        db_utils.DB_PATH = original_db_path


def test_legacy_api_key_env_is_supported(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.setenv("PAPERPIPE_API_KEY", "legacy-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        blocked = client.post("/jobs/deepread", json={"paper_id": "paper_legacy_auth_001"})
        assert blocked.status_code == 401

        allowed = client.post(
            "/jobs/deepread",
            json={"paper_id": "paper_legacy_auth_001"},
            headers={"X-API-Key": "legacy-key"},
        )
        assert allowed.status_code == 200
    finally:
        db_utils.DB_PATH = original_db_path
