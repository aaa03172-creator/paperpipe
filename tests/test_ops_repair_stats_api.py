import json
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def _write_claimset(run_dir: Path) -> None:
    claimset = {
        "doc_id": "paper_ops_001",
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "efficacy",
                "statement": "Intervention improved endpoint by 18% (p=0.01).",
                "confidence": 0.9,
                "limitations": [],
                "evidence_spans": [
                    {
                        "page": 0,
                        "chunk_id": "chunk_001",
                        "raw_text": "Intervention improved endpoint by 18% (p=0.01).",
                        "quote": "improved endpoint by 18% (p=0.01)",
                        "rationale": "Directly reported in results section.",
                        "section": "results",
                    }
                ],
            }
        ],
    }
    (run_dir / "claimset.json").write_text(json.dumps(claimset), encoding="utf-8")


def test_ops_repair_stats_seeds_missing_stats_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    run_dir = tmp_path / "storage" / "artifacts" / "paper_ops_001" / "run_ops_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_claimset(run_dir)
    (run_dir / "bootstrap_meta.json").write_text(json.dumps({"paper_id": "paper_ops_001"}), encoding="utf-8")

    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        resp = client.post(
            "/ops/repair-stats",
            json={
                "paper_ids": ["paper_ops_001"],
                "skip_existing": True,
                "write_bootstrap_meta": True,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["seeded"] == 1
        assert payload["total"] == 1
        assert payload["results"][0]["status"] == "seeded"
        assert payload["results"][0]["run_id"] == "run_ops_001"

        stats_payload = json.loads((run_dir / "stats_report.json").read_text(encoding="utf-8"))
        assert stats_payload["run_id"] == "run_ops_001"
        assert stats_payload["checks"][0]["method"] == "claimset_fallback"
        assert stats_payload["checks"][0]["verdict"] == "unverifiable"

        bootstrap = json.loads((run_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        assert bootstrap["stats_report_written"] is True
        assert bootstrap["artifact_stats_written"] is True

        conn = db_utils.get_db_connection()
        action_row = conn.execute(
            """
            SELECT paper_id, action_type, source, payload_json
            FROM user_actions
            WHERE paper_id = ?
            ORDER BY ts DESC, rowid DESC
            LIMIT 1
            """,
            ("paper_ops_001",),
        ).fetchone()
        conn.close()
        assert action_row is not None
        assert action_row["action_type"] == "repair_stats"
        assert action_row["source"] == "ui"
        action_payload = json.loads(action_row["payload_json"])
        assert action_payload["run_id"] == "run_ops_001"
        assert action_payload["status"] == "seeded"
    finally:
        db_utils.DB_PATH = original_db_path


def test_ops_repair_stats_skip_existing_and_validate_request(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    client = TestClient(api_main.app)
    bad_req = client.post("/ops/repair-stats", json={"paper_ids": []})
    assert bad_req.status_code == 400

    run_dir = tmp_path / "storage" / "artifacts" / "paper_ops_002" / "run_ops_002"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_claimset(run_dir)
    (run_dir / "stats_report.json").write_text(json.dumps({"doc_id": "x", "run_id": "run_ops_002", "checks": []}), encoding="utf-8")

    resp = client.post(
        "/ops/repair-stats",
        json={
            "paper_ids": ["paper_ops_002"],
            "skip_existing": True,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["seeded"] == 0
    assert payload["skipped"] == 1
    assert payload["results"][0]["reason"] == "stats_exists"


def test_ops_repair_stats_overwrites_existing_when_requested(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    run_dir = tmp_path / "storage" / "artifacts" / "paper_ops_003" / "run_ops_003"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_claimset(run_dir)
    (run_dir / "stats_report.json").write_text(
        json.dumps(
            {
                "doc_id": "paper_ops_003",
                "run_id": "run_ops_003",
                "checks": [
                    {
                        "check_id": "legacy-check",
                        "test_type": "legacy",
                        "method": "legacy",
                        "verdict": "pass",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    resp = client.post(
        "/ops/repair-stats",
        json={
            "paper_ids": ["paper_ops_003"],
            "skip_existing": False,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["seeded"] == 1
    assert payload["skipped"] == 0
    assert payload["results"][0]["status"] == "seeded"

    stats_payload = json.loads((run_dir / "stats_report.json").read_text(encoding="utf-8"))
    assert stats_payload["run_id"] == "run_ops_003"
    assert len(stats_payload["checks"]) == 1
    assert stats_payload["checks"][0]["check_id"] == "CLM-001"
    assert stats_payload["checks"][0]["method"] == "claimset_fallback"
