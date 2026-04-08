import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault(
    "PAPERPIPE_CONFIG_PATH",
    str(Path(__file__).resolve().parents[1] / "config.example.yaml"),
)

from backend import main as api_main


def test_trusted_host_default_allows_local_and_blocks_untrusted_hosts():
    allowed_client = TestClient(api_main.app)
    allowed = allowed_client.get("/health")
    assert allowed.status_code == 200

    blocked_client = TestClient(api_main.app, base_url="http://evil.example")
    blocked = blocked_client.get("/health")
    assert blocked.status_code == 400
    assert "Invalid host header" in blocked.text


def test_trusted_host_env_override_is_respected(monkeypatch):
    monkeypatch.setenv("LATTICE_ALLOWED_HOSTS", "beta.example,localhost")
    monkeypatch.delenv("PAPERPIPE_ALLOWED_HOSTS", raising=False)

    reloaded_main = importlib.reload(api_main)
    try:
        allowed_client = TestClient(reloaded_main.app, base_url="http://beta.example")
        assert allowed_client.get("/health").status_code == 200

        blocked_client = TestClient(reloaded_main.app)
        blocked = blocked_client.get("/health")
        assert blocked.status_code == 400
        assert "Invalid host header" in blocked.text
    finally:
        monkeypatch.delenv("LATTICE_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("PAPERPIPE_ALLOWED_HOSTS", raising=False)
        importlib.reload(api_main)


def test_security_headers_are_applied_to_ui_and_health_responses():
    client = TestClient(api_main.app)

    ui_resp = client.get("/ui")
    assert ui_resp.status_code == 200
    assert ui_resp.headers["x-content-type-options"] == "nosniff"
    assert ui_resp.headers["x-frame-options"] == "DENY"
    assert ui_resp.headers["referrer-policy"] == "no-referrer"
    assert ui_resp.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert "frame-ancestors 'none'" in ui_resp.headers["content-security-policy"]
    assert "object-src 'none'" in ui_resp.headers["content-security-policy"]
    assert "strict-transport-security" not in ui_resp.headers

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.headers["x-content-type-options"] == "nosniff"
    assert health_resp.headers["x-frame-options"] == "DENY"
    assert health_resp.headers["referrer-policy"] == "no-referrer"
    assert health_resp.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert "content-security-policy" not in health_resp.headers


def test_hsts_is_only_added_for_https_requests():
    client = TestClient(api_main.app)

    http_resp = client.get("/health")
    assert "strict-transport-security" not in http_resp.headers

    https_resp = client.get("/health", headers={"x-forwarded-proto": "https"})
    assert https_resp.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"
