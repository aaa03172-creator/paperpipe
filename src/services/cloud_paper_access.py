from __future__ import annotations

from collections.abc import Mapping

from src.schemas.cloud_paper import CloudPaperAccessContext, CloudPaperPermissions


def derive_cloud_paper_access_context_from_headers(
    headers: Mapping[str, str],
    *,
    paper_lab_id: str,
) -> CloudPaperAccessContext:
    normalized = {str(key).lower(): str(value).strip() for key, value in headers.items()}
    role = normalized.get("x-paperpipe-role") or "reader"
    if role not in {"lab_admin", "maintainer", "reviewer", "reader"}:
        role = "reader"
    actor_id = normalized.get("x-paperpipe-actor-id") or "local_beta_user"
    lab_id = normalized.get("x-paperpipe-lab-id") or paper_lab_id
    return CloudPaperAccessContext(
        actor_id=actor_id,
        lab_id=lab_id,
        paper_lab_id=paper_lab_id,
        role=role,  # type: ignore[arg-type]
        authenticated=_header_bool(normalized, "x-paperpipe-authenticated", default=True),
        device_registered=_header_bool(normalized, "x-paperpipe-device-registered", default=True),
        session_approved=_header_bool(normalized, "x-paperpipe-session-approved", default=False),
        download_allowed_by_policy=_header_bool(normalized, "x-paperpipe-download-allowed", default=False),
    )


def _header_bool(headers: Mapping[str, str], name: str, *, default: bool) -> bool:
    value = headers.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def derive_cloud_paper_permissions_for_access_context(context: CloudPaperAccessContext) -> CloudPaperPermissions:
    if not context.authenticated:
        return CloudPaperPermissions(role=context.role)
    if context.lab_id != context.paper_lab_id:
        return CloudPaperPermissions(role=context.role)
    if not (context.device_registered or context.session_approved):
        return CloudPaperPermissions(role=context.role)

    can_download = context.download_allowed_by_policy
    if context.role == "lab_admin":
        return CloudPaperPermissions(
            role=context.role,
            can_read_page=True,
            can_read_pdf=True,
            can_hydrate=can_download,
            can_upload=True,
            can_delete=True,
            can_run_optional_ai=True,
            can_export=True,
            can_share=True,
        )
    if context.role == "maintainer":
        return CloudPaperPermissions(
            role=context.role,
            can_read_page=True,
            can_read_pdf=can_download,
            can_hydrate=can_download,
            can_upload=True,
            can_run_optional_ai=True,
            can_export=True,
        )
    if context.role == "reviewer":
        return CloudPaperPermissions(
            role=context.role,
            can_read_page=True,
            can_read_pdf=can_download,
            can_hydrate=can_download,
            can_export=True,
        )
    return CloudPaperPermissions(role=context.role, can_read_page=True)
