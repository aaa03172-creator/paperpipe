from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from backend.routers import method_comparisons as method_comparisons_router
from src.skills import runner as skills_runner


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
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
    finally:
        db_utils.DB_PATH = original_db_path


def test_read_endpoints_do_not_require_api_key(tmp_path, monkeypatch):
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
