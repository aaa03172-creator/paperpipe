import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _reload_api_main_with_built_frontend(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle"
    frontend_dir = bundle_root / "frontend"
    dist_dir = frontend_dir / "dist"
    assets_dir = dist_dir / "assets"

    _write(
        dist_dir / "index.html",
        """<!doctype html><html><head><title>Lattice Analysis Workbench</title></head><body><script src="/assets/app.js"></script></body></html>""",
    )
    _write(assets_dir / "app.js", 'console.log("built-ui");')
    _write(dist_dir / "sample.pdf", b"%PDF-1.4\n%ui-shell-test\n")
    _write(dist_dir / "vite.svg", "<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    _write(frontend_dir / "index.html", "<html><body>fallback</body></html>")
    _write(frontend_dir / "ui-shell.html", "<html><body>ui-shell</body></html>")
    _write(frontend_dir / "styles" / "pp-theme.css", ":root { --pp-bg-canvas: #000; }")

    monkeypatch.setenv("PAPERPIPE_APP_BUNDLE_ROOT", str(bundle_root))
    return importlib.reload(api_main)


def test_ui_shell_serves_html():
    client = TestClient(api_main.app)
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Lattice Analysis Workbench" in resp.text


def test_ui_shell_serves_nested_deep_links(monkeypatch, tmp_path):
    reloaded_api_main = _reload_api_main_with_built_frontend(monkeypatch, tmp_path)
    client = TestClient(reloaded_api_main.app)

    root_resp = client.get("/ui")
    assert root_resp.status_code == 200
    assert "/assets/app.js" in root_resp.text

    resp = client.get("/ui/papers")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Lattice Analysis Workbench" in resp.text


def test_ui_theme_asset_is_served(monkeypatch, tmp_path):
    reloaded_api_main = _reload_api_main_with_built_frontend(monkeypatch, tmp_path)
    client = TestClient(reloaded_api_main.app)
    resp = client.get("/ui-assets/styles/pp-theme.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("content-type", "")
    assert "--pp-bg-canvas" in resp.text


def test_built_frontend_assets_are_served(monkeypatch, tmp_path):
    reloaded_api_main = _reload_api_main_with_built_frontend(monkeypatch, tmp_path)
    client = TestClient(reloaded_api_main.app)

    js_resp = client.get("/assets/app.js")
    assert js_resp.status_code == 200
    assert "javascript" in js_resp.headers.get("content-type", "") or "text/plain" in js_resp.headers.get("content-type", "")

    pdf_resp = client.get("/sample.pdf")
    assert pdf_resp.status_code == 200
    assert "application/pdf" in pdf_resp.headers.get("content-type", "")


def test_favicon_asset_is_served_without_404(monkeypatch, tmp_path):
    reloaded_api_main = _reload_api_main_with_built_frontend(monkeypatch, tmp_path)
    client = TestClient(reloaded_api_main.app)

    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("content-type", "")
