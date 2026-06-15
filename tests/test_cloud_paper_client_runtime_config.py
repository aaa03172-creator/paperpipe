from __future__ import annotations

from src.services.cloud_paper_runtime import get_cloud_paper_client_runtime_config


def test_client_runtime_config_defaults_to_mock_without_cloud_details(monkeypatch) -> None:
    monkeypatch.delenv("PAPERPIPE_CLOUD_ADAPTER", raising=False)
    monkeypatch.delenv("LATTICE_CLOUD_ADAPTER", raising=False)

    config = get_cloud_paper_client_runtime_config()

    assert config.cloud_adapter == "mock"
    assert config.gcs_configured is False
    assert "/api" == config.api_base_path
    assert "cloud_page_read" in config.enabled_contracts
    assert "paperpipe-" not in str(config.model_dump(mode="json"))


def test_client_runtime_config_reports_gcs_readiness_without_leaking_buckets(monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_CLOUD_ADAPTER", "gcs")
    monkeypatch.setenv("PAPERPIPE_GCP_PROJECT_ID", "paperpipe-secret-project")
    monkeypatch.setenv("PAPERPIPE_GCS_RAW_PDF_BUCKET", "paperpipe-raw-secret")
    monkeypatch.setenv("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET", "paperpipe-page-secret")

    config = get_cloud_paper_client_runtime_config()
    public_text = str(config.model_dump(mode="json"))

    assert config.cloud_adapter == "gcs"
    assert config.gcs_configured is True
    assert "paperpipe-secret-project" not in public_text
    assert "paperpipe-raw-secret" not in public_text
    assert "paperpipe-page-secret" not in public_text
