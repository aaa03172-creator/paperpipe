from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from src.jobs.queue import JobQueue
from backend import main as api_main


def test_quality_metrics_endpoint_rollup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()

        artifact1 = tmp_path / "storage" / "artifacts" / "p1" / "run1"
        artifact2 = tmp_path / "storage" / "artifacts" / "p2" / "run2"
        artifact3 = tmp_path / "storage" / "artifacts" / "p3" / "run3"
        artifact1.mkdir(parents=True, exist_ok=True)
        artifact2.mkdir(parents=True, exist_ok=True)
        artifact3.mkdir(parents=True, exist_ok=True)

        (artifact1 / "bootstrap_meta.json").write_text(
            json.dumps(
                {
                    "evidence_grounded_ratio": 0.5,
                    "stats_cache_hit": True,
                }
            ),
            encoding="utf-8",
        )
        (artifact2 / "bootstrap_meta.json").write_text(
            json.dumps(
                {
                    "evidence_grounded_ratio": 1.0,
                    "stats_cache_hit": False,
                }
            ),
            encoding="utf-8",
        )

        j1 = queue.enqueue("p1")
        j2 = queue.enqueue("p2")
        j3 = queue.enqueue("p3")
        queue.update_job(j1, {"status": "completed", "artifact_dir": str(artifact1)})
        queue.update_job(j2, {"status": "completed", "artifact_dir": str(artifact2)})
        queue.update_job(j3, {"status": "completed", "artifact_dir": str(artifact3)})

        client = TestClient(api_main.app)
        resp = client.get("/metrics/quality")
        assert resp.status_code == 200
        payload = resp.json()

        assert payload["jobs_scanned"] == 3
        assert payload["bootstrap_meta_found"] == 2
        assert payload["evidence_grounded_ratio_count"] == 2
        assert payload["evidence_grounded_ratio_avg"] == 0.75
        assert payload["stats_cache_total"] == 2
        assert payload["stats_cache_hit_count"] == 1
        assert payload["stats_cache_hit_rate"] == 0.5
    finally:
        db_utils.DB_PATH = original_db_path
