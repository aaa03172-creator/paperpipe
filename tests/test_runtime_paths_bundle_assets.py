import src.services.runtime_paths as runtime_paths
from src.services import runtime_readiness


def test_bundle_root_override_enables_install_layout_and_frontend_runtime_dir(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    monkeypatch.setenv("PAPERPIPE_APP_BUNDLE_ROOT", str(bundle))
    monkeypatch.delenv("PAPERPIPE_INSTALL_LAYOUT", raising=False)

    assert runtime_paths.bundle_root() == bundle.resolve()
    assert runtime_paths.app_source_root() == bundle.resolve()
    assert runtime_paths.frontend_runtime_dir() == (bundle / "frontend").resolve()
    assert runtime_paths.install_layout_enabled() is True


def test_runtime_readiness_frontend_roots_follow_bundle_override(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    monkeypatch.setenv("PAPERPIPE_APP_BUNDLE_ROOT", str(bundle))

    built_root, dev_root = runtime_readiness._frontend_roots()

    assert built_root == (bundle / "frontend" / "dist" / "index.html").resolve()
    assert dev_root == (bundle / "frontend" / "index.html").resolve()
