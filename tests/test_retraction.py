from __future__ import annotations

from src.retraction import check_retraction


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_check_retraction_accepts_string_true_assertion(monkeypatch):
    def fake_get(*_args, **_kwargs):
        return _FakeResponse(
            {
                "message": {
                    "assertions": [
                        {"name": "is-retracted", "value": "true"},
                    ],
                }
            }
        )

    monkeypatch.setattr("src.retraction.requests.get", fake_get)

    result = check_retraction("10.1000/retracted")

    assert result["is_retracted"] is True
    assert "Retraction Watch" in result["retraction_details"]
