from __future__ import annotations

import importlib

from src.schemas.cloud_paper import (
    CloudPaperAuthPreflightCheck,
    CloudPaperAuthPreflightCheckStatus,
    CloudPaperAuthPreflightResponse,
    CloudPaperAuthPreflightStatus,
)
from src.services.cloud_paper_metadata import resolve_cloud_paper_metadata_config
from src.services.cloud_paper_submission_bundle import list_submission_demo_bundles, submission_demo_enabled, submission_demo_root
from src.services.cloud_paper_storage import resolve_cloud_paper_storage_config


def _check(
    check_id: str,
    label: str,
    status: CloudPaperAuthPreflightCheckStatus,
    message: str,
    remediation: str | None = None,
) -> CloudPaperAuthPreflightCheck:
    return CloudPaperAuthPreflightCheck(
        check_id=check_id,
        label=label,
        status=status,
        message=message,
        remediation=remediation,
    )


def _status_from_exception(exc: Exception) -> CloudPaperAuthPreflightStatus:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "defaultcredentials" in name or "could not automatically determine credentials" in message:
        return "auth_missing"
    if "permissiondenied" in name or "forbidden" in name or "permission" in message or "403" in message:
        return "permission_denied"
    if "unauthorized" in name or "401" in message:
        return "auth_missing"
    return "unavailable"


def _safe_failure_message(status: CloudPaperAuthPreflightStatus, label: str) -> str:
    if status == "auth_missing":
        return f"{label} could not find Application Default Credentials."
    if status == "permission_denied":
        return f"{label} reached Google Cloud but the current identity is not allowed."
    return f"{label} could not be checked from this runtime."


def _setup_commands(project_id: str | None) -> list[str]:
    commands = ["gcloud auth application-default login"]
    if project_id:
        commands.append(f"gcloud config set project {project_id}")
    return commands


def build_cloud_paper_auth_preflight() -> CloudPaperAuthPreflightResponse:
    storage_config = resolve_cloud_paper_storage_config()
    metadata_config = resolve_cloud_paper_metadata_config()
    project_id = storage_config.gcp_project_id or metadata_config.gcp_project_id
    checks: list[CloudPaperAuthPreflightCheck] = []

    if submission_demo_enabled():
        root = submission_demo_root()
        bundles = list_submission_demo_bundles()
        if root is not None and bundles:
            return CloudPaperAuthPreflightResponse(
                status="submission_bundle",
                adapter="mock",
                project_id=None,
                firestore_collection=None,
                credential_source="not_required",
                checks=[
                    _check(
                        "submission_demo_bundle",
                        "Submitted demo bundle",
                        "ok",
                        f"{len(bundles)} bundled cloud paper snapshot is available without Google Cloud sign-in.",
                    )
                ],
                next_action_label="Open the bundled cloud paper snapshot.",
                setup_commands=[],
            )
        return CloudPaperAuthPreflightResponse(
            status="misconfigured",
            adapter="mock",
            project_id=None,
            firestore_collection=None,
            credential_source="not_required",
            checks=[
                _check(
                    "submission_demo_bundle",
                    "Submitted demo bundle",
                    "error",
                    "Submission demo mode is enabled, but no bundled cloud paper snapshot was found.",
                    "Rebuild or copy the submission demo bundle into the app resources.",
                )
            ],
            next_action_label="Rebuild the submission demo app copy.",
            setup_commands=[],
        )

    if storage_config.adapter == "mock":
        return CloudPaperAuthPreflightResponse(
            status="mock_mode",
            adapter="mock",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="not_required",
            checks=[
                _check(
                    "cloud_adapter",
                    "Cloud adapter",
                    "warning",
                    "Cloud papers are running in mock storage mode.",
                    "Switch PAPERPIPE_CLOUD_ADAPTER to gcs for shared GCP-backed papers.",
                )
            ],
            next_action_label="Use local mock mode or switch to the GCS demo configuration.",
            setup_commands=_setup_commands(project_id),
        )

    missing = []
    if not storage_config.gcp_project_id:
        missing.append("PAPERPIPE_GCP_PROJECT_ID")
    if not storage_config.raw_pdf_bucket:
        missing.append("PAPERPIPE_GCS_RAW_PDF_BUCKET")
    if not storage_config.page_artifact_bucket:
        missing.append("PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET")
    if metadata_config.store == "firestore" and not metadata_config.gcp_project_id:
        missing.append("PAPERPIPE_GCP_PROJECT_ID")
    if missing:
        checks.append(
            _check(
                "cloud_config",
                "Cloud configuration",
                "error",
                f"Missing required cloud configuration: {', '.join(sorted(set(missing)))}.",
                "Use the installed demo cloud configuration before checking Google authentication.",
            )
        )
        return CloudPaperAuthPreflightResponse(
            status="misconfigured",
            adapter="gcs",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="unknown",
            checks=checks,
            next_action_label="Fix the local cloud configuration, then check again.",
            setup_commands=_setup_commands(project_id),
        )

    try:
        storage_module = importlib.import_module("google.cloud.storage")
        firestore_module = importlib.import_module("google.cloud.firestore")
        auth_module = importlib.import_module("google.auth")
    except ModuleNotFoundError:
        checks.append(
            _check(
                "cloud_dependencies",
                "Google Cloud libraries",
                "error",
                "The packaged runtime is missing Google Cloud client libraries.",
                "Install or rebuild the runtime with the cloud extras included.",
            )
        )
        return CloudPaperAuthPreflightResponse(
            status="dependency_missing",
            adapter="gcs",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="unknown",
            checks=checks,
            next_action_label="Install the cloud-enabled runtime, then check again.",
            setup_commands=[],
        )

    try:
        auth_module.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    except Exception as exc:
        status = _status_from_exception(exc)
        checks.append(
            _check(
                "application_default_credentials",
                "Application Default Credentials",
                "error",
                _safe_failure_message(status, "Google authentication"),
                "Run the Application Default Credentials login command, then reopen Lattice.",
            )
        )
        return CloudPaperAuthPreflightResponse(
            status=status,
            adapter="gcs",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="application_default_credentials",
            checks=checks,
            next_action_label="Sign in with Application Default Credentials on this computer.",
            setup_commands=_setup_commands(project_id),
        )

    checks.append(
        _check(
            "application_default_credentials",
            "Application Default Credentials",
            "ok",
            "Application Default Credentials were found for this computer.",
        )
    )

    try:
        storage_client = storage_module.Client(project=storage_config.gcp_project_id)
        raw_bucket = storage_client.bucket(storage_config.raw_pdf_bucket)
        raw_bucket.exists()
        checks.append(_check("raw_pdf_bucket", "Raw PDF bucket", "ok", "The raw PDF bucket is reachable."))
    except Exception as exc:
        status = _status_from_exception(exc)
        checks.append(
            _check(
                "raw_pdf_bucket",
                "Raw PDF bucket",
                "error",
                _safe_failure_message(status, "Raw PDF bucket"),
                "Ask a project admin for read access to the demo raw PDF bucket.",
            )
        )
        return CloudPaperAuthPreflightResponse(
            status=status,
            adapter="gcs",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="application_default_credentials",
            checks=checks,
            next_action_label="Ask for GCS bucket access, then check again.",
            setup_commands=_setup_commands(project_id),
        )

    try:
        storage_client = storage_module.Client(project=storage_config.gcp_project_id)
        page_bucket = storage_client.bucket(storage_config.page_artifact_bucket)
        page_bucket.exists()
        checks.append(_check("page_artifact_bucket", "Page artifact bucket", "ok", "The page artifact bucket is reachable."))
    except Exception as exc:
        status = _status_from_exception(exc)
        checks.append(
            _check(
                "page_artifact_bucket",
                "Page artifact bucket",
                "error",
                _safe_failure_message(status, "Page artifact bucket"),
                "Ask a project admin for read access to the demo page artifact bucket.",
            )
        )
        return CloudPaperAuthPreflightResponse(
            status=status,
            adapter="gcs",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="application_default_credentials",
            checks=checks,
            next_action_label="Ask for GCS bucket access, then check again.",
            setup_commands=_setup_commands(project_id),
        )

    try:
        firestore_client = firestore_module.Client(project=metadata_config.gcp_project_id or storage_config.gcp_project_id)
        collection = firestore_client.collection(metadata_config.firestore_collection)
        query = collection.limit(1) if hasattr(collection, "limit") else collection
        list(query.stream())
        checks.append(
            _check(
                "firestore_collection",
                "Firestore metadata",
                "ok",
                "The cloud paper metadata collection is reachable.",
            )
        )
    except Exception as exc:
        status = _status_from_exception(exc)
        checks.append(
            _check(
                "firestore_collection",
                "Firestore metadata",
                "error",
                _safe_failure_message(status, "Firestore metadata"),
                "Ask a project admin for read access to the demo Firestore metadata collection.",
            )
        )
        return CloudPaperAuthPreflightResponse(
            status=status,
            adapter="gcs",
            project_id=project_id,
            firestore_collection=metadata_config.firestore_collection,
            credential_source="application_default_credentials",
            checks=checks,
            next_action_label="Ask for Firestore metadata access, then check again.",
            setup_commands=_setup_commands(project_id),
        )

    return CloudPaperAuthPreflightResponse(
        status="ready",
        adapter="gcs",
        project_id=project_id,
        firestore_collection=metadata_config.firestore_collection,
        credential_source="application_default_credentials",
        checks=checks,
        next_action_label="Cloud paper access is ready on this computer.",
        setup_commands=_setup_commands(project_id),
    )
