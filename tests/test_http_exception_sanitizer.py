import json

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend import main as api_main


_TEST_SECRET_DETAIL_PATH = "/__test/http-exception-secret-redaction"
_TEST_VALIDATION_SECRET_PATH = "/__test/request-validation-secret-redaction"


class _ValidationPayload(BaseModel):
    required_int: int


def _ensure_secret_detail_test_route() -> None:
    if any(getattr(route, "path", None) == _TEST_SECRET_DETAIL_PATH for route in api_main.app.router.routes):
        return

    @api_main.app.get(_TEST_SECRET_DETAIL_PATH, include_in_schema=False)
    def _secret_detail_route():
        raise HTTPException(
            status_code=418,
            headers={"X-Test-Header": "preserved"},
            detail={
                "message": "Provider failed with Bearer http-token-123",
                "headers": {
                    "Authorization": "Basic beta:wrong-pass",
                    "Content-Type": "application/json",
                },
                "OPENAI_API_KEY": "sk-proj-http-secret-abcdef",
                "database_url": "postgresql://paperpipe:secret@example.local/db",
                "path_message": "Obsidian vault not found: /Users/example/private-vault",
                "url_message": "Docs: https://example.com/private/path and http://localhost:8000/api/jobs",
            },
        )


def _ensure_validation_test_route() -> None:
    if any(getattr(route, "path", None) == _TEST_VALIDATION_SECRET_PATH for route in api_main.app.router.routes):
        return

    @api_main.app.post(_TEST_VALIDATION_SECRET_PATH, include_in_schema=False)
    def _validation_route(payload: _ValidationPayload):
        return payload.model_dump()


def test_http_exception_detail_sanitizes_secret_like_values():
    _ensure_secret_detail_test_route()
    client = TestClient(api_main.app)

    response = client.get(_TEST_SECRET_DETAIL_PATH)

    assert response.status_code == 418
    assert response.headers["x-test-header"] == "preserved"
    assert response.headers["x-content-type-options"] == "nosniff"
    payload = response.json()
    serialized = json.dumps(payload)
    assert "http-token-123" not in serialized
    assert "beta:wrong-pass" not in serialized
    assert "sk-proj-http-secret-abcdef" not in serialized
    assert "postgresql://paperpipe:secret@example.local/db" not in serialized
    assert "/Users/example/private-vault" not in serialized
    assert payload["detail"]["message"] == "Provider failed with <redacted>"
    assert payload["detail"]["headers"]["Authorization"] == "<redacted>"
    assert payload["detail"]["headers"]["Content-Type"] == "application/json"
    assert payload["detail"]["OPENAI_API_KEY"] == "<redacted>"
    assert payload["detail"]["database_url"] == "<redacted>"
    assert payload["detail"]["path_message"] == "Obsidian vault not found: .../private-vault"
    assert (
        payload["detail"]["url_message"]
        == "Docs: https://example.com/private/path and http://localhost:8000/api/jobs"
    )


def test_request_validation_detail_drops_raw_input_echo():
    _ensure_validation_test_route()
    client = TestClient(api_main.app)

    response = client.post(
        _TEST_VALIDATION_SECRET_PATH,
        json={
            "required_int": "Bearer validation-token-123 /Users/example/private-input",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    serialized = json.dumps(payload)
    assert "validation-token-123" not in serialized
    assert "/Users/example/private-input" not in serialized
    assert '"input"' not in serialized
    assert payload["detail"][0]["loc"] == ["body", "required_int"]
    assert payload["detail"][0]["type"] == "int_parsing"
