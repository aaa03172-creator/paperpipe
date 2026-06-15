from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.cloud_paper import (
    CloudPaperBundlePublic,
    CloudPaperHydrationState,
    CloudPaperPermissions,
    CloudPaperProvenanceSummary,
    CloudPaperToolCapability,
)
from src.services.cloud_paper_tools import filter_cloud_paper_tool_capabilities


def _bundle(*, payload_class: str = "local_only", hydrated: bool = False) -> CloudPaperBundlePublic:
    return CloudPaperBundlePublic(
        paper_id="paper_mock_ready",
        lab_id="lab_001",
        processing_status="ready",
        payload_class=payload_class,
        page_schema_version="cloud_page_artifact.v1",
        run_id="run_paper_mock_ready",
        permissions=CloudPaperPermissions(role="maintainer", can_read_page=True, can_run_optional_ai=True),
        provenance_summary=CloudPaperProvenanceSummary(
            uploaded_by="mock_user",
            processor_name="mock-worker",
            processor_version="0.1.0",
            created_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
            source_pdf_sha256="a" * 64,
        ),
        local_hydration=CloudPaperHydrationState(status="hydrated") if hydrated else None,
        allowed_actions=["read_page", "run_optional_ai"],
    )


def test_tool_capabilities_filter_by_permission_payload_class_and_hydration() -> None:
    capabilities = [
        CloudPaperToolCapability(
            tool_id="local_summary",
            label="Local summary",
            action="run_optional_ai",
            allowed_payload_classes=["local_only", "lab_allowed"],
            requires_hydrated_bundle=False,
        ),
        CloudPaperToolCapability(
            tool_id="external_summary",
            label="External summary",
            action="run_optional_ai",
            allowed_payload_classes=["external_allowed"],
            requires_hydrated_bundle=False,
        ),
        CloudPaperToolCapability(
            tool_id="hydrated_export",
            label="Hydrated export",
            action="export",
            allowed_payload_classes=["local_only"],
            requires_hydrated_bundle=True,
        ),
    ]

    visible = filter_cloud_paper_tool_capabilities(
        capabilities,
        bundle=_bundle(payload_class="local_only", hydrated=False),
        permissions=CloudPaperPermissions(role="maintainer", can_read_page=True, can_run_optional_ai=True),
    )

    assert [capability.tool_id for capability in visible] == ["local_summary"]


def test_hydrated_export_requires_export_permission_and_hydrated_bundle() -> None:
    capability = CloudPaperToolCapability(
        tool_id="hydrated_export",
        label="Hydrated export",
        action="export",
        allowed_payload_classes=["local_only"],
        requires_hydrated_bundle=True,
    )

    visible = filter_cloud_paper_tool_capabilities(
        [capability],
        bundle=_bundle(payload_class="local_only", hydrated=True),
        permissions=CloudPaperPermissions(role="maintainer", can_read_page=True, can_export=True),
    )

    assert [item.tool_id for item in visible] == ["hydrated_export"]
