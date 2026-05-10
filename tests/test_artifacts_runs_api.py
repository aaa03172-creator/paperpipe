import json
import os

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.jobs.queue import JobQueue
from src.services.identity import artifact_paper_segment


def _set_artifacts_root(monkeypatch, root):
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))


def _privacy_preflight_payload() -> dict:
    return {
        "schema_version": "privacy_preflight.v1",
        "mode": "report_only",
        "status": "review_required",
        "rollback_flag": "LATTICE_PRIVACY_PREFLIGHT_MODE",
        "payload_class": "external_allowed",
        "scope": "clinical_extraction_external_payload",
        "redaction_applied": True,
        "mutation_applied": False,
        "findings": [
            {
                "finding_id": "privacy-preflight-001",
                "kind": "false_negative_risk",
                "severity": "high",
                "action": "manual_review",
                "message": "Short possessive names near clinical or personal event cues require review.",
                "label": "private_person",
                "source_surface": "methods_snippet",
                "detector": "paperpipe-runtime-privacy-preflight",
                "reason": "short_private_name_context",
                "text_preview": "<short_private_name>",
            }
        ],
        "manual_review": [
            {
                "review_id": "privacy-review-001",
                "severity": "high",
                "reason": "short_private_name_context",
                "message": "Short possessive names near clinical or personal event cues require review.",
                "source_surface": "methods_snippet",
                "finding_ids": ["privacy-preflight-001"],
                "recommended_action": "manual_review",
            }
        ],
        "summary": {
            "detector_spans": 0,
            "deterministic_spans": 0,
            "preserve_conflicts": 0,
            "false_negative_risks": 1,
            "unexpected_predictions": 0,
            "manual_review_records": 1,
            "manual_review_reasons": 1,
        },
        "input_refs": ["paper:paper_artifacts_001", "run:run_new"],
        "source_surfaces": ["methods_snippet", "paper_metadata"],
        "metadata": {},
    }


def test_artifacts_latest_and_run_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_old",
                "run_old",
                "paper_artifacts_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:00:00",
                "2026-02-24 00:00:05",
                str(tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_old"),
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_new",
                "run_new",
                "paper_artifacts_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:01:00",
                "2026-02-24 00:01:05",
                str(tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_new"),
            ),
        )
        conn.commit()
        conn.close()

        old_dir = tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_old"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "old"}), encoding="utf-8")

        new_dir = tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_new"
        new_dir.mkdir(parents=True, exist_ok=True)
        (new_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "new"}), encoding="utf-8")
        (new_dir / "claimset.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
        (new_dir / "bootstrap_meta.json").write_text(
            json.dumps(
                {
                    "claimset_readiness_badge": "READY",
                    "operator_note": "Authorization: Bearer bootstrap-token-123",
                    "OPENAI_API_KEY": "sk-proj-bootstrap-secret-abcdef",
                }
            ),
            encoding="utf-8",
        )
        (new_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "selected_backend": "mixed",
                    "payload_class": "mixed",
                    "redaction_applied": True,
                    "error": "Provider failed with Bearer artifact-token-123",
                    "verification_error": "Authorization: Basic beta:wrong-pass",
                    "inference_lanes": {
                        "reader": {
                            "selected_backend": "local",
                            "payload_class": "local_only",
                            "redaction_applied": False,
                        },
                        "clinical_extraction": {
                            "selected_backend": "commercial",
                            "payload_class": "external_allowed",
                            "redaction_applied": True,
                            "provider_name": "openai",
                            "provider_model": "gpt-5.4-mini",
                            "privacy_preflight": _privacy_preflight_payload(),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        client = TestClient(api_main.app)

        latest = client.get("/artifacts/paper_artifacts_001/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()
        assert latest_payload["run_id"] == "run_new"
        assert latest_payload["inference_summary"]["selected_backend"] == "mixed"
        assert latest_payload["inference_summary"]["payload_class"] == "mixed"
        assert latest_payload["inference_summary"]["redaction_applied"] is True
        assert latest_payload["inference_summary"]["lanes"]["reader"]["selected_backend"] == "local"
        assert latest_payload["inference_summary"]["lanes"]["clinical_extraction"]["provider_name"] == "openai"
        assert "artifact-token-123" not in json.dumps(latest_payload)
        assert "bootstrap-token-123" not in json.dumps(latest_payload)
        assert "sk-proj-bootstrap-secret-abcdef" not in json.dumps(latest_payload)
        assert "Basic beta:wrong-pass" not in json.dumps(latest_payload)
        assert latest_payload["files"]["bootstrap_meta"]["data"]["operator_note"] == "Authorization: <redacted>"
        assert latest_payload["files"]["bootstrap_meta"]["data"]["OPENAI_API_KEY"] == "<redacted>"
        assert latest_payload["files"]["run_meta"]["data"]["error"] == "Provider failed with <redacted>"
        assert latest_payload["files"]["run_meta"]["data"]["verification_error"] == "Authorization: <redacted>"
        privacy_preflight = latest_payload["inference_summary"]["lanes"]["clinical_extraction"]["privacy_preflight"]
        assert privacy_preflight["mode"] == "report_only"
        assert privacy_preflight["status"] == "review_required"
        assert privacy_preflight["summary"]["manual_review_records"] == 1
        assert privacy_preflight["findings"][0]["text_preview"] == "<short_private_name>"
        assert latest_payload["files"]["document_artifact"]["exists"] is True
        assert latest_payload["files"]["document_artifact"]["data"]["doc_id"] == "new"

        old = client.get("/artifacts/paper_artifacts_001/run_old")
        assert old.status_code == 200
        old_payload = old.json()
        assert old_payload["run_id"] == "run_old"
        assert old_payload["inference_summary"] is None
        assert old_payload["files"]["document_artifact"]["data"]["doc_id"] == "old"

        claimset = client.get("/artifacts/paper_artifacts_001/run_new/claimset")
        assert claimset.status_code == 200
        claimset_payload = claimset.json()
        assert claimset_payload["exists"] is True
        assert claimset_payload["data"]["claims"] == []

        stats_missing = client.get("/artifacts/paper_artifacts_001/run_new/stats")
        assert stats_missing.status_code == 404

        unknown_artifact = client.get("/artifacts/paper_artifacts_001/run_new/nope")
        assert unknown_artifact.status_code == 404

        missing = client.get("/artifacts/paper_artifacts_001/run_missing")
        assert missing.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_latest_honors_artifacts_root_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_override",
                "run_override",
                "paper_override_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:02:00",
                "2026-02-24 00:02:05",
                None,
            ),
        )
        conn.commit()
        conn.close()

        run_dir = custom_artifacts / "paper_override_001" / "run_override"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "override"}), encoding="utf-8")
        (run_dir / "claimset.resolved.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {"claim_id": "c1", "evidence_spans": [{"page": 0}]},
                        {"claim_id": "c2", "evidence_spans": [{"page": 2}]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "inference_lanes": {
                        "reader": {
                            "selected_backend": "local",
                            "payload_class": "local_only",
                            "redaction_applied": False,
                        },
                        "clinical_extraction": {
                            "selected_backend": "commercial",
                            "payload_class": "external_allowed",
                            "redaction_applied": True,
                            "provider_name": "openai",
                            "provider_model": "gpt-5.4",
                            "privacy_preflight": {"mode": "not-a-valid-mode"},
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

        client = TestClient(api_main.app)
        latest = client.get("/artifacts/paper_override_001/latest")
        assert latest.status_code == 200
        payload = latest.json()
        assert payload["run_id"] == "run_override"
        assert payload["inference_summary"]["selected_backend"] == "mixed"
        assert payload["inference_summary"]["payload_class"] == "mixed"
        assert payload["inference_summary"]["redaction_applied"] is True
        assert payload["inference_summary"]["lanes"]["clinical_extraction"]["provider_model"] == "gpt-5.4"
        assert payload["inference_summary"]["lanes"]["clinical_extraction"]["privacy_preflight"] is None
        assert payload["files"]["document_artifact"]["data"]["doc_id"] == "override"
        assert payload["files"]["claimset_resolved"]["exists"] is True
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_routes_support_unsafe_paper_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        paper_id = "doi:10.1000/test-paper"
        run_id = "run_override"
        run_dir = custom_artifacts / artifact_paper_segment(paper_id) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "unsafe"}), encoding="utf-8")

        client = TestClient(api_main.app)

        latest = client.get(f"/artifacts/{paper_id}/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()
        assert latest_payload["run_id"] == run_id
        assert latest_payload["files"]["document_artifact"]["data"]["doc_id"] == "unsafe"

        exact = client.get("/artifacts", params={"paper_id": paper_id, "run_id": run_id})
        assert exact.status_code == 200
        exact_payload = exact.json()
        assert exact_payload["run_id"] == run_id
        assert exact_payload["files"]["document_artifact"]["data"]["doc_id"] == "unsafe"

        path_run = client.get(f"/artifacts/{paper_id}/{run_id}")
        assert path_run.status_code == 200
        path_run_payload = path_run.json()
        assert path_run_payload["run_id"] == run_id
        assert path_run_payload["files"]["document_artifact"]["data"]["doc_id"] == "unsafe"
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_latest_resolves_zotero_alias_candidates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        paper_id = "zotero:alias-paper-001"
        run_id = "run_alias"
        run_dir = custom_artifacts / artifact_paper_segment(paper_id) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "zotero-alias"}), encoding="utf-8")

        client = TestClient(api_main.app)

        for lookup_id in ("zotero:alias-paper-001", "alias-paper-001"):
            latest = client.get(f"/artifacts/{lookup_id}/latest")
            assert latest.status_code == 200
            latest_payload = latest.json()
            assert latest_payload["paper_id"] == paper_id
            assert latest_payload["run_id"] == run_id
            assert latest_payload["files"]["document_artifact"]["data"]["doc_id"] == "zotero-alias"
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_latest_scans_legacy_and_canonical_candidate_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        paper_id = "zotero:legacy-canonical-001"
        legacy_run = custom_artifacts / paper_id / "run_legacy_old"
        canonical_run = custom_artifacts / artifact_paper_segment(paper_id) / "run_canonical_new"
        legacy_run.mkdir(parents=True, exist_ok=True)
        canonical_run.mkdir(parents=True, exist_ok=True)
        (legacy_run / "document_artifact.json").write_text(json.dumps({"doc_id": "legacy-old"}), encoding="utf-8")
        (canonical_run / "document_artifact.json").write_text(
            json.dumps({"doc_id": "canonical-new"}),
            encoding="utf-8",
        )
        legacy_time = 1_700_000_000
        canonical_time = legacy_time + 60
        legacy_run.touch()
        canonical_run.touch()

        os.utime(legacy_run, (legacy_time, legacy_time))
        os.utime(canonical_run, (canonical_time, canonical_time))

        latest = TestClient(api_main.app).get(f"/artifacts/{paper_id}/latest")

        assert latest.status_code == 200
        latest_payload = latest.json()
        assert latest_payload["run_id"] == "run_canonical_new"
        assert latest_payload["files"]["document_artifact"]["data"]["doc_id"] == "canonical-new"
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_routes_do_not_resolve_traversal_ids_outside_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "storage" / "artifacts"
    _set_artifacts_root(monkeypatch, artifacts)

    outside_run = tmp_path / "outside" / "run_escape"
    outside_run.mkdir(parents=True, exist_ok=True)
    (outside_run / "document_artifact.json").write_text(json.dumps({"doc_id": "escaped"}), encoding="utf-8")

    client = TestClient(api_main.app)

    paper_escape = client.get("/artifacts/..%2Foutside/run_escape")
    assert paper_escape.status_code == 404
    assert "escaped" not in paper_escape.text

    run_escape = client.get("/artifacts/paper_safe_001/..%2F..%2Foutside%2Frun_escape")
    assert run_escape.status_code == 404
    assert "escaped" not in run_escape.text

    query_escape = client.get(
        "/artifacts",
        params={"paper_id": "paper_safe_001", "run_id": "../../outside/run_escape"},
    )
    assert query_escape.status_code == 404
    assert "escaped" not in query_escape.text


def test_artifacts_latest_does_not_serve_db_artifact_dir_outside_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "storage" / "artifacts"
    _set_artifacts_root(monkeypatch, artifacts)

    outside_run = tmp_path / "outside-artifacts" / "paper_db_pointer_001" / "run_outside"
    outside_run.mkdir(parents=True, exist_ok=True)
    (outside_run / "document_artifact.json").write_text(json.dumps({"doc_id": "outside"}), encoding="utf-8")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_outside_pointer",
                "run_outside",
                "paper_db_pointer_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:03:00",
                "2026-02-24 00:03:05",
                str(outside_run),
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.get("/artifacts/paper_db_pointer_001/latest")

        assert response.status_code == 404
        assert "doc_id" not in response.text
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_bundle_reports_malformed_json_sidecar_without_breaking_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "storage" / "artifacts"
    _set_artifacts_root(monkeypatch, artifacts)

    run_dir = artifacts / "paper_malformed_sidecar" / "run_bad_json"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "document_artifact.json").write_text('{"doc_id": "ok"}', encoding="utf-8")
    (run_dir / "run_meta.json").write_text('{"selected_backend": ', encoding="utf-8")

    client = TestClient(api_main.app)

    bundle = client.get("/artifacts/paper_malformed_sidecar/run_bad_json")
    assert bundle.status_code == 200
    payload = bundle.json()
    assert payload["paper_id"] == "paper_malformed_sidecar"
    assert payload["run_id"] == "run_bad_json"
    assert payload["inference_summary"] is None
    assert payload["files"]["document_artifact"]["exists"] is True
    assert payload["files"]["document_artifact"]["data"]["doc_id"] == "ok"
    assert payload["files"]["run_meta"]["exists"] is True
    assert "_parse_error" in payload["files"]["run_meta"]["data"]

    run_meta = client.get("/artifacts/paper_malformed_sidecar/run_bad_json/meta")
    assert run_meta.status_code == 200
    assert run_meta.json()["exists"] is True
    assert "_parse_error" in run_meta.json()["data"]


def test_runs_status_and_timeline_from_job_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_runs_001")
        run_id = queue.get_job(job_id).run_id

        log_path = tmp_path / "logs" / "jobs" / f"{job_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "job_id": job_id,
                            "run_id": run_id,
                            "stage": "read",
                            "progress": 70,
                            "message": "analysis running",
                            "level": "INFO",
                            "timestamp": "2026-02-24T00:00:01Z",
                        }
                    ),
                    "plain text line",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
                "finished_at": "2026-02-24T00:00:03+00:00",
            },
        )

        client = TestClient(api_main.app)

        run_status = client.get(f"/runs/{run_id}")
        assert run_status.status_code == 200
        run_payload = run_status.json()
        assert run_payload["job_id"] == job_id
        assert run_payload["run_id"] == run_id
        assert run_payload["status"] == "completed"

        timeline = client.get(f"/runs/{run_id}/timeline", params={"limit": 10})
        assert timeline.status_code == 200
        timeline_payload = timeline.json()
        assert timeline_payload["run_id"] == run_id
        assert timeline_payload["job_id"] == job_id
        assert len(timeline_payload["events"]) >= 2
        assert any(evt["event"] == "log" and evt.get("message") == "analysis running" for evt in timeline_payload["events"])
        assert any(evt["event"] == "done" and evt.get("message") == "completed" for evt in timeline_payload["events"])

        no_run = client.get("/runs/no_such_run")
        assert no_run.status_code == 404
        no_timeline = client.get("/runs/no_such_run/timeline")
        assert no_timeline.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path


def test_run_status_returns_not_found_when_jobs_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        client = TestClient(api_main.app)

        response = client.get("/runs/run_missing_jobs_table")

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"
    finally:
        db_utils.DB_PATH = original_db_path
