from src.services import runtime_readiness


def test_backend_entrypoint_check_surfaces_missing_dependency(monkeypatch):
    def fake_import_module(name: str):
        assert name == "backend.main"
        raise ModuleNotFoundError("No module named 'fastapi'", name="fastapi")

    monkeypatch.setattr(runtime_readiness.importlib, "import_module", fake_import_module)

    check = runtime_readiness._backend_entrypoint_check()

    assert check.name == "backend_entrypoint"
    assert check.status == "error"
    assert "fastapi" in check.detail
    assert "bootstrap_verification_env.py" in check.detail
