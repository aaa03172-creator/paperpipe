from fastapi.testclient import TestClient

from backend import main as api_main


def test_paper_syntheses_endpoints_require_api_key_when_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(tmp_path / "paper_syntheses"))

    client = TestClient(api_main.app)

    list_response = client.get("/paper-syntheses")
    assert list_response.status_code == 401
    assert list_response.json()["error_code"] == "UNAUTHORIZED"

    generate_response = client.post("/paper-syntheses/generate", json={"paper_slug": "paper-alpha"})
    assert generate_response.status_code == 401
    assert generate_response.json()["error_code"] == "UNAUTHORIZED"


def test_paper_syntheses_list_accepts_valid_api_key_when_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(tmp_path / "paper_syntheses"))

    client = TestClient(api_main.app)
    response = client.get("/paper-syntheses", headers={"X-API-Key": "secret-key"})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
