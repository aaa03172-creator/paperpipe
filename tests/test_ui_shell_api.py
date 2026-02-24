from fastapi.testclient import TestClient

from backend import main as api_main


def test_ui_shell_serves_html():
    client = TestClient(api_main.app)
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Lattice Analysis Workbench" in resp.text


def test_ui_theme_asset_is_served():
    client = TestClient(api_main.app)
    resp = client.get("/ui-assets/styles/pp-theme.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("content-type", "")
    assert "--pp-bg-canvas" in resp.text
