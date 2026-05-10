from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.services.stale_jobs as stale_jobs_service
from backend import main as api_main
from backend.routers import method_comparisons as method_comparisons_router
from backend.routers import paper_notes as paper_notes_router
from src.image_evidence.store import save_image_evidence_bundle
from src.schemas.agent_artifacts import StatCheckEntry, StatsReport, VerificationStatus
from src.schemas.image_evidence import ImageEvidence
from src.schemas.talk_pack import (
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackOutputMember,
    TalkPackReviewArtifact,
    TalkPackUpstreamOwnerRef,
)
from src.skills import runner as skills_runner
from src.talk_packs.store import save_talk_pack_bundle


class _FakeRequest:
    def __init__(self, *, host: str):
        self.headers = {"host": host}
        self.scope = {}
        self.url = SimpleNamespace(hostname=host)


def _browser_headers() -> dict[str, str]:
    return {"origin": "http://testserver"}


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


def _seed_operator_state_note(tmp_path, monkeypatch) -> str:
    vault_dir = tmp_path / "vault"
    slug = "operator-state-note"
    paper_id = "zotero:operator-state-note"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "\n".join(
            [
                "---",
                f"id: {paper_id}",
                "aliases:",
                "  - Operator State Fixture",
                "tags:",
                "  - Medicine/Neurology",
                "  - Review",
                "date_processed: 2026-04-10",
                "confidence: 0.82",
                "status: INDEXED",
                "---",
                "",
                "body",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    return slug


def _sample_talk_pack(*, talk_pack_id: str, title: str) -> TalkPack:
    request = TalkPackGenerateRequest(
        paper_slug="paper_auth_allow_001",
        title=title,
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        selected_exports=["deck_pptx", "speaker_script"],
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id=talk_pack_id,
        paper_slug="paper_auth_allow_001",
        title=title,
        created_at="2026-04-21T01:02:03Z",
        updated_at="2026-04-21T01:02:03Z",
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/paper_auth_allow_001/state.json",
                role="canonical",
            )
        ],
        selected_outputs=["deck_pptx", "speaker_script"],
        required_outputs=["slide_manifest", "key_numbers", "deck_pptx", "speaker_script"],
        output_members=[
            TalkPackOutputMember(kind="slide_manifest", path="slide_manifest.json", required=True),
            TalkPackOutputMember(kind="key_numbers", path="key_numbers.md", required=True),
            TalkPackOutputMember(kind="deck_pptx", path="exports/deck.pptx", required=True),
            TalkPackOutputMember(kind="speaker_script", path="exports/speaker_script.md", required=True),
        ],
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
            TalkPackReviewArtifact(kind="style_lint", path="review/style_lint.json"),
        ],
    )


def _sample_talk_pack_bundle_payloads() -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
    return (
        {
            "slide_manifest.json": '{"slides":[]}\n',
            "key_numbers.md": "# Key Numbers\n",
            "exports/speaker_script.md": "# Script\n",
        },
        {
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        {
            "exports/deck.pptx": b"PPTX placeholder bytes",
        },
    )


def _sample_image_evidence_with_derivative(*, image_evidence_id: str) -> ImageEvidence:
    return ImageEvidence(
        image_evidence_id=image_evidence_id,
        title="Auth allow image",
        created_at="2026-04-21T01:02:03Z",
        source_ref={"source_kind": "external_image_ref", "external_ref": "omero://image/auth"},
        content_format="image/png",
        derived_outputs=[
            {
                "derived_output_id": "thumb_01",
                "kind": "thumbnail",
                "source_image_evidence_id": image_evidence_id,
                "created_by": "tester",
                "created_at": "2026-04-21T01:02:03Z",
                "tool_name": "napari",
                "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
            }
        ],
    )


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

        artifact_feedback = client.post(
            "/artifact-feedback",
            json={
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_auth_001",
                "run_id": "run_auth_001",
                "decision": "correct",
                "reason_code": "missing_context",
                "actor_id": "reviewer_auth",
                "note": "Need clearer context.",
            },
        )
        assert artifact_feedback.status_code == 401

        artifact_generation_outcome = client.post(
            "/artifact-generation-outcomes",
            json={
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_auth_001",
                "run_id": "run_auth_001",
                "decision": "reused_after_correction",
                "downstream_use": "final_deliverable",
                "actor_id": "reviewer_auth",
                "note": "Used after correction.",
            },
        )
        assert artifact_generation_outcome.status_code == 401

        project_context_link = client.post(
            "/project-context-links",
            json={
                "project_id": "pmproj_auth_001",
                "entity_type": "paper",
                "entity_id": "paper_auth_001",
                "relationship_type": "primary_focus",
                "actor_id": "reviewer_auth",
                "note": "Core project paper.",
            },
        )
        assert project_context_link.status_code == 401

        obsidian_sync = client.post("/obsidian/sync", json={"paper_id": "paper_auth_001", "run_id": "run_auth_001"})
        assert obsidian_sync.status_code == 401

        repair_stats = client.post("/ops/repair-stats", json={"paper_ids": ["paper_auth_001"]})
        assert repair_stats.status_code == 401

        reclaim_stale = client.post("/ops/jobs/job_auth_001/reclaim-stale")
        assert reclaim_stale.status_code == 401

        requeue_reclaimed = client.post("/ops/jobs/job_auth_001/requeue-reclaimed")
        assert requeue_reclaimed.status_code == 401

        stale_incident_snapshot = client.post("/ops/jobs/job_auth_001/stale-incident-snapshot")
        assert stale_incident_snapshot.status_code == 401

        skills_run = client.post("/skills/run", json={"slug": "paper_auth_001", "action": "validate_citations"})
        assert skills_run.status_code == 401

        user_action = client.post("/user-actions", json={"paper_id": "paper_auth_001", "action_type": "open_workbench"})
        assert user_action.status_code == 401

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

        meeting_pack_outcome = client.post(
            "/meeting-packs/meetingpack_auth_001/outcome",
            json={
                "run_id": "run_auth_001",
                "decision": "reused_after_correction",
                "downstream_use": "final_deliverable",
                "actor_id": "reviewer_auth",
                "note": "Used after correction.",
            },
        )
        assert meeting_pack_outcome.status_code == 401

        meeting_pack_review = client.post(
            "/meeting-packs/meetingpack_auth_001/review",
            json={
                "run_id": "run_auth_001",
                "decision": "correct",
                "reason_code": "missing_context",
                "actor_id": "reviewer_auth",
                "note": "Needs stronger context.",
            },
        )
        assert meeting_pack_review.status_code == 401

        talk_pack_render = client.post("/talk-packs/talkpack_auth_001/render-deck")
        assert talk_pack_render.status_code == 401

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

        protocol_card_upsert = client.post(
            "/protocol-cards",
            json={
                "title": "Protocol auth demo",
                "source_kind": "paper_derived",
                "versions": [
                    {
                        "version_number": 1,
                        "content_snapshot": "Step 1",
                        "created_by": "tester",
                    }
                ],
            },
        )
        assert protocol_card_upsert.status_code == 401

        protocol_card_outcome = client.post(
            "/protocol-cards/protocol_auth_001/outcome",
            json={
                "paper_id": "paper_auth_001",
                "decision": "reused",
                "downstream_use": "supporting_context",
                "actor_id": "reviewer_auth",
                "note": "Used as supporting context.",
            },
        )
        assert protocol_card_outcome.status_code == 401

        protocol_card_review = client.post(
            "/protocol-cards/protocol_auth_001/review",
            json={
                "paper_id": "paper_auth_001",
                "decision": "correct",
                "reason_code": "missing_detail",
                "actor_id": "reviewer_auth",
                "note": "Needs more detail.",
            },
        )
        assert protocol_card_review.status_code == 401
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
        existing_pdf = tmp_path / "paper_auth_allow_001.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%auth-allow\n")
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_auth_allow_001", "Auth Allow PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.commit()
        conn.close()
        artifact_root = tmp_path / "artifacts"
        monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifact_root))
        artifact_run_dir = artifact_root / "paper_auth_allow_001" / "run_auth_allow_001"
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
        job_id = deepread.json()["job_id"]
        run_id = deepread.json()["run_id"]

        cancel = client.post(f"/jobs/{job_id}/cancel", headers=headers)
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

        artifact_feedback = client.post(
            "/artifact-feedback",
            json={
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_auth_allow_001",
                "run_id": "run_auth_allow_001",
                "decision": "accept",
                "reason_code": "ready_for_reuse",
                "actor_id": "reviewer_auth",
                "note": "Ready for reuse.",
            },
            headers=headers,
        )
        assert artifact_feedback.status_code == 200

        artifact_generation_outcome = client.post(
            "/artifact-generation-outcomes",
            json={
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_auth_allow_001",
                "run_id": "run_auth_allow_001",
                "decision": "reused_after_correction",
                "downstream_use": "final_deliverable",
                "actor_id": "reviewer_auth",
                "note": "Used after correction.",
            },
            headers=headers,
        )
        assert artifact_generation_outcome.status_code == 200

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

        user_action = client.post(
            "/user-actions",
            json={"paper_id": "paper_auth_allow_001", "action_type": "open_workbench", "source": "ui"},
            headers=headers,
        )
        assert user_action.status_code == 200

        jobs_list = client.get("/jobs", headers=headers)
        assert jobs_list.status_code == 200
        assert any(item["job_id"] == job_id for item in jobs_list.json())

        job_status = client.get(f"/jobs/{job_id}", headers=headers)
        assert job_status.status_code == 200
        assert job_status.json()["run_id"] == run_id

        run_status = client.get(f"/runs/{run_id}", headers=headers)
        assert run_status.status_code == 200
        assert run_status.json()["job_id"] == job_id

        artifact_bundle = client.get(
            "/artifacts",
            params={"paper_id": "paper_auth_allow_001", "run_id": "run_auth_allow_001"},
            headers=headers,
        )
        assert artifact_bundle.status_code == 200
        assert artifact_bundle.json()["files"]["claimset_resolved"]["exists"] is True

        paper_pdf = client.get("/papers/paper_auth_allow_001/pdf", headers=headers)
        assert paper_pdf.status_code == 200
        assert paper_pdf.content.startswith(b"%PDF")

        readiness = client.get("/health/ready", headers=headers)
        assert readiness.status_code == 200

        papers = client.get("/papers", headers=headers)
        assert papers.status_code == 200
        assert any(item["paper_id"] == "paper_auth_allow_001" for item in papers.json())

        workspace_summary = client.get("/workspace-summary", headers=headers)
        assert workspace_summary.status_code == 200

        personas = client.get("/personas", headers=headers)
        assert personas.status_code == 200

        user_actions = client.get(
            "/user-actions",
            params={"paper_id": "paper_auth_allow_001", "limit": 10},
            headers=headers,
        )
        assert user_actions.status_code == 200
        assert len(user_actions.json()["actions"]) >= 1

        project_dir = tmp_path / "storage" / "project_memory" / "pmproj_auth_allow"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "project.json").write_text(
            "\n".join(
                [
                    "{",
                    '  "project_id": "pmproj_auth_allow",',
                    '  "title": "Auth allow project",',
                    '  "layer": "raw_memory",',
                    '  "canonical_status": "non_canonical",',
                    '  "status": "active",',
                    '  "linked_paper_ids": [],',
                    '  "linked_research_dna_ids": [],',
                    '  "linked_meeting_pack_ids": [],',
                    '  "created_at": "2026-04-13T00:00:00Z",',
                    '  "updated_at": "2026-04-13T00:00:00Z"',
                    "}",
                ]
            ),
            encoding="utf-8",
        )

        project_context_link = client.post(
            "/project-context-links",
            json={
                "project_id": "pmproj_auth_allow",
                "entity_type": "paper",
                "entity_id": "paper_auth_allow_001",
                "relationship_type": "primary_focus",
                "actor_id": "reviewer_auth",
                "note": "Core project paper.",
            },
            headers=headers,
        )
        assert project_context_link.status_code == 200

        project_context_links = client.get(
            "/project-context-links",
            params={"project_id": "pmproj_auth_allow", "limit": 10},
            headers=headers,
        )
        assert project_context_links.status_code == 200
        assert len(project_context_links.json()) == 1

        artifact_generation_outcomes = client.get(
            "/artifact-generation-outcomes",
            params={"artifact_id": "meetingpack_auth_allow_001", "limit": 10},
            headers=headers,
        )
        assert artifact_generation_outcomes.status_code == 200
        assert len(artifact_generation_outcomes.json()) == 1

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
                    "    specialty_trial_extraction:",
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
        monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(tmp_path / "talk_packs"))
        monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(tmp_path / "meeting_packs"))
        monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(tmp_path / "method_comparisons"))

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

        talk_pack = _sample_talk_pack(
            talk_pack_id="talkpack_auth_allow_001",
            title="Auth allow talk",
        )
        talk_text_artifacts, talk_json_artifacts, talk_binary_artifacts = _sample_talk_pack_bundle_payloads()
        save_talk_pack_bundle(
            talk_pack,
            text_artifacts=talk_text_artifacts,
            json_artifacts=talk_json_artifacts,
            binary_artifacts=talk_binary_artifacts,
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

        meeting_pack_outcome = client.post(
            f"/meeting-packs/{pack_id}/outcome",
            json={
                "run_id": "run_auth_allow_001",
                "decision": "reused_after_correction",
                "downstream_use": "final_deliverable",
                "actor_id": "reviewer_auth",
                "note": "Used after correction.",
            },
            headers=headers,
        )
        assert meeting_pack_outcome.status_code == 200

        meeting_pack_review = client.post(
            f"/meeting-packs/{pack_id}/review",
            json={
                "run_id": "run_auth_allow_001",
                "decision": "correct",
                "reason_code": "missing_context",
                "actor_id": "reviewer_auth",
                "note": "Needs stronger context.",
            },
            headers=headers,
        )
        assert meeting_pack_review.status_code == 200

        meeting_pack_validate = client.get(f"/meeting-packs/{pack_id}/validate", headers=headers)
        assert meeting_pack_validate.status_code == 200

        talk_pack_detail = client.get("/talk-packs/talkpack_auth_allow_001", headers=headers)
        assert talk_pack_detail.status_code == 200

        talk_pack_listing = client.get("/talk-packs", headers=headers)
        assert talk_pack_listing.status_code == 200

        talk_pack_artifact = client.get(
            "/talk-packs/talkpack_auth_allow_001/artifacts/key_numbers.md",
            headers=headers,
        )
        assert talk_pack_artifact.status_code == 200

        talk_pack_render = client.post(
            "/talk-packs/talkpack_auth_allow_001/render-deck",
            headers=headers,
        )
        assert talk_pack_render.status_code == 400

        meeting_pack_listing = client.get("/meeting-packs", headers=headers)
        assert meeting_pack_listing.status_code == 200

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

        method_comparison_detail = client.get("/method-comparisons/methodcmp_auth_demo", headers=headers)
        assert method_comparison_detail.status_code == 200

        method_comparison_markdown = client.get(
            "/method-comparisons/methodcmp_auth_demo/markdown",
            headers=headers,
        )
        assert method_comparison_markdown.status_code == 200
        assert "## Comparison" in method_comparison_markdown.text

        method_comparison_listing = client.get("/method-comparisons", headers=headers)
        assert method_comparison_listing.status_code == 200

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

        chart_pack_detail = client.get("/chart-packs/chartpack_auth_allow_001", headers=headers)
        assert chart_pack_detail.status_code == 200

        chart_pack_markdown = client.get("/chart-packs/chartpack_auth_allow_001/markdown", headers=headers)
        assert chart_pack_markdown.status_code == 200
        assert "Chart Pack ID: chartpack_auth_allow_001" in chart_pack_markdown.text

        chart_pack_listing = client.get("/chart-packs", headers=headers)
        assert chart_pack_listing.status_code == 200

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

        image_evidence_detail = client.get("/image-evidence/img_auth_allow", headers=headers)
        assert image_evidence_detail.status_code == 200

        image_evidence_listing = client.get("/image-evidence", headers=headers)
        assert image_evidence_listing.status_code == 200

        save_image_evidence_bundle(
            _sample_image_evidence_with_derivative(image_evidence_id="img_auth_allow_derivative"),
            derivative_artifacts={"derivatives/thumb_01.png": b"PNG"},
            root=tmp_path / "storage" / "image_evidence",
        )
        image_evidence_derivative = client.get(
            "/image-evidence/img_auth_allow_derivative/derivatives/thumb_01.png",
            headers=headers,
        )
        assert image_evidence_derivative.status_code == 200
        assert image_evidence_derivative.content == b"PNG"

        monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(tmp_path / "protocol_cards"))
        protocol_card_upsert = client.post(
            "/protocol-cards",
            json={
                "protocol_id": "protocol_auth_allow",
                "title": "Protocol auth demo",
                "source_kind": "paper_derived",
                "versions": [
                    {
                        "version_id": "protver_auth_allow_v1",
                        "version_number": 1,
                        "content_snapshot": "Step 1",
                        "status": "active",
                        "created_by": "tester",
                    }
                ],
            },
            headers=headers,
        )
        assert protocol_card_upsert.status_code == 200
        assert protocol_card_upsert.json()["protocol_card"]["protocol_id"] == "protocol_auth_allow"

        protocol_card_detail = client.get("/protocol-cards/protocol_auth_allow", headers=headers)
        assert protocol_card_detail.status_code == 200

        protocol_card_markdown = client.get("/protocol-cards/protocol_auth_allow/markdown", headers=headers)
        assert protocol_card_markdown.status_code == 200
        assert protocol_card_markdown.text.startswith("# Protocol auth demo")

        protocol_card_outcome = client.post(
            "/protocol-cards/protocol_auth_allow/outcome",
            json={
                "paper_id": "paper_auth_allow_001",
                "decision": "reused",
                "downstream_use": "supporting_context",
                "actor_id": "reviewer_auth",
                "note": "Used as supporting context.",
            },
            headers=headers,
        )
        assert protocol_card_outcome.status_code == 200

        protocol_card_review = client.post(
            "/protocol-cards/protocol_auth_allow/review",
            json={
                "paper_id": "paper_auth_allow_001",
                "decision": "correct",
                "reason_code": "missing_detail",
                "actor_id": "reviewer_auth",
                "note": "Needs more detail.",
            },
            headers=headers,
        )
        assert protocol_card_review.status_code == 200

        protocol_card_listing = client.get("/protocol-cards", headers=headers)
        assert protocol_card_listing.status_code == 200

        paper_notes_listing = client.get("/paper-notes", headers=headers)
        assert paper_notes_listing.status_code == 200
        assert any(item["slug"] == "paper_auth_allow_001" for item in paper_notes_listing.json()["items"])
    finally:
        db_utils.DB_PATH = original_db_path


def test_health_endpoint_does_not_require_api_key(tmp_path, monkeypatch):
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
                    "    specialty_trial_extraction:",
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
            client.get("/health/ready"),
            client.get("/papers"),
            client.get("/workspace-summary"),
            client.get("/personas"),
            client.get("/paper-notes"),
            client.get("/paper-notes/home-context"),
            client.get("/talk-packs"),
            client.get("/talk-packs/talkpack_auth_read_001/artifacts/key_numbers.md"),
            client.get("/meeting-packs"),
            client.get("/method-comparisons"),
            client.get("/method-comparisons/methodcmp_auth_read_001/markdown"),
            client.get("/chart-packs"),
            client.get("/chart-packs/chartpack_auth_read_001/markdown"),
            client.get("/protocol-cards"),
            client.get("/protocol-cards/protocol_auth_read_001/markdown"),
            client.get("/image-evidence"),
            client.get("/image-evidence/img_auth_read_001/derivatives/thumb_01.png"),
            client.get("/paper-syntheses"),
            client.get("/artifact-feedback"),
            client.get("/artifact-generation-outcomes"),
            client.get("/feedback"),
            client.get("/obsidian/mirror"),
            client.get("/project-context-links"),
            client.get("/research-dna/dna_missing"),
            client.get("/papers/paper_auth_read_001/pdf"),
            client.get("/artifacts", params={"paper_id": "paper_auth_read_001", "run_id": "run_auth_read_001"}),
            client.get("/artifacts/paper_auth_read_001/latest"),
            client.get("/jobs"),
            client.get("/jobs/job_auth_read_001"),
            client.get("/jobs/job_auth_read_001/bootstrap-meta"),
            client.get("/jobs/job_auth_read_001/events"),
            client.get("/ops/stale-jobs"),
            client.get("/runs/run_auth_read_001"),
            client.get("/runs/run_auth_read_001/timeline"),
            client.get("/user-actions", params={"paper_id": "paper_auth_read_001", "limit": 10}),
        ]

        for response in responses:
            assert response.status_code == 401
            assert response.json()["error_code"] == "UNAUTHORIZED"

        import_pdf = client.post(
            "/paper-notes/import-pdf",
            files={"file": ("auth-read.pdf", b"%PDF-1.4\n%auth-read\n", "application/pdf")},
        )
        assert import_pdf.status_code == 401
        assert import_pdf.json()["error_code"] == "UNAUTHORIZED"
    finally:
        db_utils.DB_PATH = original_db_path


def test_private_root_routes_require_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        for path in (
            "/health/ready",
            "/papers",
            "/workspace-summary",
            "/personas",
            "/paper-notes",
            "/paper-notes/home-context",
            "/talk-packs",
            "/meeting-packs",
            "/method-comparisons",
            "/chart-packs",
            "/protocol-cards",
            "/image-evidence",
            "/paper-syntheses",
            "/artifact-feedback",
            "/artifact-generation-outcomes",
            "/feedback",
            "/obsidian/mirror",
            "/project-context-links",
            "/research-dna/dna_missing",
        ):
            response = client.get(path)
            assert response.status_code == 401
            assert response.json()["error_code"] == "UNAUTHORIZED"

        upload = client.post(
            "/paper-notes/import-pdf",
            files={"file": ("blocked.pdf", b"%PDF-1.4\n%blocked\n", "application/pdf")},
        )
        assert upload.status_code == 401
        assert upload.json()["error_code"] == "UNAUTHORIZED"
    finally:
        db_utils.DB_PATH = original_db_path


def test_operator_state_put_requires_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        slug = _seed_operator_state_note(tmp_path, monkeypatch)
        client = TestClient(api_main.app)

        blocked_root = client.put(
            f"/paper-notes/{slug}/operator-state",
            json={"starred": True},
        )
        assert blocked_root.status_code == 401
        assert blocked_root.json()["error_code"] == "UNAUTHORIZED"

        allowed_root = client.put(
            f"/paper-notes/{slug}/operator-state",
            json={"starred": True},
            headers={"X-API-Key": "secret-key"},
        )
        assert allowed_root.status_code == 200
        assert allowed_root.json()["starred"] is True

        browser_put = client.put(
            f"/api/paper-notes/{slug}/operator-state",
            json={"starred": False},
            headers=_browser_headers(),
        )
        assert browser_put.status_code == 200
        assert browser_put.json()["starred"] is False
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
            headers=_browser_headers(),
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

        stale_jobs = client.get("/api/ops/stale-jobs")
        assert stale_jobs.status_code == 200
        assert stale_jobs.json()["running_jobs_total"] == 0

        paper_pdf = client.get("/api/papers/paper_browser_api_001/pdf")
        assert paper_pdf.status_code == 200
        assert paper_pdf.content.startswith(b"%PDF")

        events = client.get("/api/jobs/job_browser_api_001/events")
        assert events.status_code == 200
        assert "event: status" in events.text
    finally:
        db_utils.DB_PATH = original_db_path


def test_api_prefixed_ops_reclaim_stale_job_bridges_browser_calls_without_exposing_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        monkeypatch.setattr(
            stale_jobs_service,
            "utc_now",
            lambda: datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
        )
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_browser_reclaim_001",
                "paper_browser_reclaim_001",
                "api",
                "deepread",
                "running",
                "2026-04-22T01:00:00+00:00",
                "2026-04-22T01:15:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_browser_reclaim_001",
                "run_browser_reclaim_001",
                "paper_browser_reclaim_001",
                "running",
                36,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                "2026-04-22T01:20:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        snapshot = client.post(
            "/api/ops/jobs/job_browser_reclaim_001/stale-incident-snapshot",
            params={"stale_after_seconds": 1800},
            headers=_browser_headers(),
        )
        assert snapshot.status_code == 200
        assert snapshot.json()["job_id"] == "job_browser_reclaim_001"
        assert snapshot.json()["is_stale_candidate"] is True
        assert Path(snapshot.json()["incident_path"]).exists()

        reclaim = client.post(
            "/api/ops/jobs/job_browser_reclaim_001/reclaim-stale",
            params={"stale_after_seconds": 1800},
            headers=_browser_headers(),
        )
        assert reclaim.status_code == 200
        assert reclaim.json()["error_code"] == "STALE_RUNNING_RECLAIMED"

        job_status = client.get("/api/jobs/job_browser_reclaim_001")
        assert job_status.status_code == 200
        assert job_status.json()["status"] == "failed"
        assert job_status.json()["error_code"] == "STALE_RUNNING_RECLAIMED"

        requeue = client.post(
            "/api/ops/jobs/job_browser_reclaim_001/requeue-reclaimed",
            headers=_browser_headers(),
        )
        assert requeue.status_code == 200
        assert requeue.json()["paper_id"] == "paper_browser_reclaim_001"
        assert requeue.json()["status"] == "queued"
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


def test_private_routes_fail_closed_without_api_key_on_non_loopback_host(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    monkeypatch.delenv("LATTICE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("LATTICE_ALLOW_UNAUTHENTICATED_PRIVATE_API", raising=False)
    monkeypatch.setenv("LATTICE_ALLOWED_HOSTS", "paperpipe.example.com")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        response = client.get("/papers", headers={"host": "paperpipe.example.com"})

        assert response.status_code == 401
        assert response.json()["error_code"] == "API_KEY_NOT_CONFIGURED"
    finally:
        db_utils.DB_PATH = original_db_path


def test_private_routes_allow_missing_api_key_on_loopback_host(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    monkeypatch.delenv("LATTICE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("LATTICE_ALLOW_UNAUTHENTICATED_PRIVATE_API", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        response = client.get("/papers", headers={"host": "127.0.0.1"})

        assert response.status_code != 401
        assert response.json() == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_private_routes_allow_explicit_unauthenticated_opt_in_on_non_loopback_host(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    monkeypatch.delenv("LATTICE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)
    monkeypatch.setenv("LATTICE_ALLOW_UNAUTHENTICATED_PRIVATE_API", "true")

    assert api_main._allow_missing_api_key_for_private_route(_FakeRequest(host="paperpipe.example.com")) is True
