from backend import main as api_main


def test_cors_default_policy_is_not_wildcard():
    cors = next((m for m in api_main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"), None)
    assert cors is not None
    origins = cors.kwargs.get("allow_origins", [])
    assert "*" not in origins
    assert "http://127.0.0.1:8000" in origins
    assert "http://localhost:8000" in origins
