from __future__ import annotations

from src.schemas.cloud_paper import CloudPaperAccessContext
from src.services.cloud_paper_access import (
    derive_cloud_paper_access_context_from_headers,
    derive_cloud_paper_permissions_for_access_context,
)


def test_reader_on_authorized_device_can_read_page_but_not_hydrate() -> None:
    context = CloudPaperAccessContext(
        actor_id="user_001",
        lab_id="lab_001",
        paper_lab_id="lab_001",
        role="reader",
        authenticated=True,
        device_registered=True,
    )

    permissions = derive_cloud_paper_permissions_for_access_context(context)

    assert permissions.can_read_page is True
    assert permissions.can_read_pdf is False
    assert permissions.can_hydrate is False
    assert permissions.allowed_actions_for_status("ready") == ["read_page"]


def test_maintainer_with_download_policy_can_hydrate() -> None:
    context = CloudPaperAccessContext(
        actor_id="user_002",
        lab_id="lab_001",
        paper_lab_id="lab_001",
        role="maintainer",
        authenticated=True,
        device_registered=True,
        download_allowed_by_policy=True,
    )

    permissions = derive_cloud_paper_permissions_for_access_context(context)

    assert permissions.can_read_page is True
    assert permissions.can_read_pdf is True
    assert permissions.can_hydrate is True
    assert "hydrate_download" in permissions.allowed_actions_for_status("ready")


def test_cross_lab_or_untrusted_device_gets_no_permissions() -> None:
    cross_lab = CloudPaperAccessContext(
        actor_id="user_003",
        lab_id="lab_other",
        paper_lab_id="lab_001",
        role="lab_admin",
        authenticated=True,
        device_registered=True,
        download_allowed_by_policy=True,
    )
    untrusted_device = CloudPaperAccessContext(
        actor_id="user_004",
        lab_id="lab_001",
        paper_lab_id="lab_001",
        role="lab_admin",
        authenticated=True,
        device_registered=False,
        session_approved=False,
        download_allowed_by_policy=True,
    )

    assert derive_cloud_paper_permissions_for_access_context(cross_lab).allowed_actions_for_status("ready") == []
    assert derive_cloud_paper_permissions_for_access_context(untrusted_device).allowed_actions_for_status("ready") == []


def test_beta_access_context_derives_role_device_and_download_policy_from_headers() -> None:
    context = derive_cloud_paper_access_context_from_headers(
        {
            "x-paperpipe-actor-id": "user_005",
            "x-paperpipe-lab-id": "lab_001",
            "x-paperpipe-role": "maintainer",
            "x-paperpipe-device-registered": "true",
            "x-paperpipe-download-allowed": "true",
        },
        paper_lab_id="lab_001",
    )

    permissions = derive_cloud_paper_permissions_for_access_context(context)

    assert context.actor_id == "user_005"
    assert context.role == "maintainer"
    assert permissions.can_read_page is True
    assert permissions.can_hydrate is True


def test_beta_access_context_defaults_to_reader_without_download_for_local_compatibility() -> None:
    context = derive_cloud_paper_access_context_from_headers({}, paper_lab_id="lab_001")

    permissions = derive_cloud_paper_permissions_for_access_context(context)

    assert context.authenticated is True
    assert context.device_registered is True
    assert permissions.allowed_actions_for_status("ready") == ["read_page"]
