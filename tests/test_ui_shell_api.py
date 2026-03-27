from fastapi.testclient import TestClient

from backend import main as api_main


def _write_file(path, content, mode="w"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode) as handle:
        handle.write(content)


def _configure_fake_frontend_dist(tmp_path, monkeypatch):
    frontend_dir = tmp_path / "frontend"
    dist_dir = frontend_dir / "dist"
    assets_dir = dist_dir / "assets"
    index_path = dist_dir / "index.html"

    _write_file(
        index_path,
        """<!doctype html>
<html lang="ko">
  <head><meta charset="UTF-8" /></head>
  <body>
    <div id="root">Lattice Analysis Workbench</div>
    <script type="module" src="/assets/app.js"></script>
  </body>
</html>
""",
    )
    _write_file(assets_dir / "app.js", "console.log('dist');\n")
    _write_file(dist_dir / "sample.pdf", b"%PDF-1.4\n% test pdf\n", mode="wb")

    monkeypatch.setattr(api_main, "FRONTEND_DIR", frontend_dir)
    monkeypatch.setattr(api_main, "FRONTEND_DIST_DIR", dist_dir)
    monkeypatch.setattr(api_main, "FRONTEND_DIST_ASSETS_DIR", assets_dir)
    monkeypatch.setattr(api_main, "FRONTEND_DIST_INDEX_PATH", index_path)
    monkeypatch.setattr(api_main, "FRONTEND_INDEX_PATH", frontend_dir / "index.html")
    monkeypatch.setattr(api_main, "UI_SHELL_PATH", frontend_dir / "ui-shell.html")


def test_ui_shell_serves_html(tmp_path, monkeypatch):
    _configure_fake_frontend_dist(tmp_path, monkeypatch)
    client = TestClient(api_main.app)
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Lattice Analysis Workbench" in resp.text
    assert "/assets/" in resp.text


def test_ui_theme_asset_is_served():
    client = TestClient(api_main.app)
    resp = client.get("/ui-assets/styles/pp-theme.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("content-type", "")
    assert "--pp-bg-canvas" in resp.text


def test_built_frontend_assets_are_served(tmp_path, monkeypatch):
    _configure_fake_frontend_dist(tmp_path, monkeypatch)
    client = TestClient(api_main.app)

    ui_resp = client.get("/ui")
    assert ui_resp.status_code == 200

    js_path = ui_resp.text.split('src="', 1)[1].split('"', 1)[0]
    js_resp = client.get(js_path)
    assert js_resp.status_code == 200
    content_type = js_resp.headers.get("content-type", "")
    assert "javascript" in content_type or "text/plain" in content_type

    pdf_resp = client.get("/sample.pdf")
    assert pdf_resp.status_code == 200
    assert "application/pdf" in pdf_resp.headers.get("content-type", "")
