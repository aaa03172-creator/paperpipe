from fastapi.testclient import TestClient

from backend import main as api_main


def test_health_ready_reports_runtime_checks():
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in {"ok", "degraded", "error"}
    names = {entry["name"] for entry in payload["checks"]}
    assert {"config_file", "config_root", "runtime_db", "storage_root", "logs_root", "cache_root", "ui_bundle"} <= names


def test_health_ready_masks_paths_when_enabled(monkeypatch):
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "true")
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    path_values = [entry.get("path") for entry in payload["checks"] if entry.get("path")]
    assert path_values
    assert all(not value.startswith("/Users/") for value in path_values)
