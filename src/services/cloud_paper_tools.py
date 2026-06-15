from __future__ import annotations

from src.schemas.cloud_paper import (
    CloudPaperBundlePublic,
    CloudPaperPermissions,
    CloudPaperToolCapability,
)


def filter_cloud_paper_tool_capabilities(
    capabilities: list[CloudPaperToolCapability],
    *,
    bundle: CloudPaperBundlePublic,
    permissions: CloudPaperPermissions,
) -> list[CloudPaperToolCapability]:
    allowed_actions = set(permissions.allowed_actions_for_status(bundle.processing_status))
    filtered: list[CloudPaperToolCapability] = []
    for capability in capabilities:
        if capability.action not in allowed_actions:
            continue
        if bundle.payload_class not in capability.allowed_payload_classes:
            continue
        if capability.requires_hydrated_bundle and (
            bundle.local_hydration is None or bundle.local_hydration.status != "hydrated"
        ):
            continue
        filtered.append(capability)
    return filtered
