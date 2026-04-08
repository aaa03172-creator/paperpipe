import base64
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault(
    "PAPERPIPE_CONFIG_PATH",
    str(Path(__file__).resolve().parents[1] / "config.example.yaml"),
)

from backend import main as api_main


def _basic_auth_headers(password: str, username: str = "beta") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_health_ready_reports_runtime_checks():
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in {"ok", "degraded", "error"}
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "obsidian_vault",
        "zotero_base_dir",
        "watch_folder",
        "downloads_watch_dir",
        "pdf_storage_dir",
        "runtime_db",
        "storage_root",
        "logs_root",
        "cache_root",
        "ui_bundle",
    } <= names


def test_api_health_ready_bridge_reports_runtime_checks():
    client = TestClient(api_main.app)

    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in {"ok", "degraded", "error"}
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "obsidian_vault",
        "zotero_base_dir",
        "watch_folder",
        "downloads_watch_dir",
        "pdf_storage_dir",
        "runtime_db",
        "storage_root",
        "logs_root",
        "cache_root",
        "ui_bundle",
    } <= names


def test_health_ready_masks_paths_by_default(monkeypatch):
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    path_values = [entry.get("path") for entry in payload["checks"] if entry.get("path")]
    assert path_values
    assert all(not value.startswith("/Users/") for value in path_values)


def test_health_ready_returns_browser_safe_summary_when_beta_gate_enabled(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.delenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)
    monkeypatch.delenv("PAPERPIPE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)

    client = TestClient(api_main.app)
    resp = client.get("/api/health/ready", headers=_basic_auth_headers("beta-pass"))

    assert resp.status_code == 200
    payload = resp.json()
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "external_roots",
        "watch_folder",
        "downloads_watch_dir",
        "pdf_storage_dir",
        "runtime_storage",
        "ui_bundle",
        "backend_runtime",
    } <= names
    assert "runtime_db" not in names
    assert "storage_root" not in names
    assert "logs_root" not in names
    assert "cache_root" not in names
    assert "backend_entrypoint" not in names
    assert all(entry.get("path") is None for entry in payload["checks"])


def test_health_ready_can_opt_back_into_detailed_mode_under_beta_gate(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS", "true")

    client = TestClient(api_main.app)
    resp = client.get("/health/ready", headers=_basic_auth_headers("beta-pass"))

    assert resp.status_code == 200
    payload = resp.json()
    names = {entry["name"] for entry in payload["checks"]}
    assert "runtime_db" in names
    assert "storage_root" in names
    assert "logs_root" in names
    assert "cache_root" in names
    assert "backend_entrypoint" in names
