from __future__ import annotations

import scripts.cloud_downstream_registry_firestore_smoke as smoke


def test_cloud_downstream_registry_firestore_smoke_defaults(monkeypatch) -> None:
    monkeypatch.delenv("PAPERPIPE_GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION", raising=False)

    args = smoke._parse_args([])

    assert args.project_id == "knudc-a01068202087"
    assert args.registry_collection == "cloud_downstream_registry_demo"
    assert args.paper_id == "paper_mock_ready"


def test_cloud_downstream_registry_firestore_smoke_redaction_guard_fails_on_private_terms() -> None:
    try:
        smoke._assert_public_payload_is_redacted({"bad": "signed_url"}, label="test")
    except RuntimeError as exc:
        assert "signed_url" in str(exc)
    else:  # pragma: no cover - explicit assertion branch
        raise AssertionError("expected redaction guard to fail")
