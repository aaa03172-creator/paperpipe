from __future__ import annotations

from src.schemas.cloud_paper import CloudPaperClientRuntimeConfig
from src.services.cloud_paper_storage import CloudPaperStorageConfigError, resolve_cloud_paper_storage_config


def get_cloud_paper_client_runtime_config() -> CloudPaperClientRuntimeConfig:
    try:
        storage_config = resolve_cloud_paper_storage_config()
    except CloudPaperStorageConfigError:
        return CloudPaperClientRuntimeConfig(
            cloud_adapter="mock",
            gcs_configured=False,
            enabled_contracts=_enabled_contracts(),
        )

    gcs_configured = bool(
        storage_config.adapter == "gcs"
        and storage_config.gcp_project_id
        and storage_config.raw_pdf_bucket
        and storage_config.page_artifact_bucket
    )
    return CloudPaperClientRuntimeConfig(
        cloud_adapter=storage_config.adapter,
        gcs_configured=gcs_configured,
        enabled_contracts=_enabled_contracts(),
    )


def _enabled_contracts() -> list[str]:
    return [
        "cloud_upload_intent",
        "cloud_page_read",
        "page_artifact_adapter",
        "local_hydration_contract",
        "device_access_policy",
        "agent_tool_capabilities",
    ]
