from base64 import b64decode
from binascii import Error as BinasciiError
from collections import deque
from dataclasses import dataclass
import heapq
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import asyncio
import ipaddress
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlparse

import src.db_utils as db_utils
from src.db_utils import get_db_connection
from src.institutional_access import extract_institutional_proxy_link, generate_institutional_proxy_url
from src.jobs.queue import DuplicateOpenJobError, JobQueue, QueueBackpressureError
from src.jobs.schemas import JobBootstrapMeta, JobCreate, JobEnqueueResponse, JobStatus
from src.persona_modes import list_reasoning_personas, normalize_persona_selection
from src.schemas.chat import ChatRequest, ChatStubResponse
from src.output_modes import resolve_chat_output_mode_family
from src.schemas.ops import (
    ArtifactBundleResponse,
    ArtifactFileEntry,
    DownloaderOpsMetricsResponse,
    ErrorResponse,
    HomeWorkspaceSummaryResponse,
    PersonaListResponse,
    PersonaOption,
    RunInferenceLaneSummary,
    RunInferenceSummary,
    StaleJobDiagnosticsResponse,
    StaleJobIncidentListResponse,
    StaleJobIncidentSnapshotResponse,
    StaleJobReclaimResponse,
    StaleJobRequeueResponse,
    RuntimeReadinessCheck,
    RuntimeReadinessResponse,
    RunTimelineEvent,
    RunTimelineResponse,
    StatsRepairRequest,
    StatsRepairResponse,
    StatsRepairResult,
    UserActionCreateRequest,
    UserActionEntry,
    UserActionListResponse,
)
from src.schemas.privacy_preflight import PrivacyPreflightResponse
from src.schemas.paper_notes import PaperNoteIndexItem
from src.schemas.papers import PaperAccessSummary, PaperDetailResponse, PaperRailSummaryResponse, PaperSummaryResponse
from src.schemas.research_dna import (
    ResearchDNAActorRequest,
    ResearchDNACreateRequest,
    ResearchDNAEnvelope,
    ResearchDNAGuidanceMaterializeRequest,
    ResearchDNAInterviewEnvelope,
    ResearchDNAInterviewRequest,
    ResearchDNAResumeEnvelope,
    ResearchDNARunIndexEnvelope,
    ResearchDNAScreenCurrentRequest,
    ResearchDNANextScreeningCandidateEnvelope,
    ResearchDNARerankGateEnvelope,
    ResearchDNAProjectedProfileEnvelope,
    ResearchDNAProjectProfileRequest,
    ResearchDNAPilotRunEnvelope,
    ResearchDNAPilotRunRequest,
    ResearchDNARerankEnvelope,
    ResearchDNARerankRequest,
    ResearchDNAScreeningGuidanceArtifactEnvelope,
    ResearchDNAScreeningGuidanceEnvelope,
    ResearchDNAScreeningGuidanceIndexEnvelope,
    ResearchDNAScreeningAdvanceEnvelope,
    ResearchDNAScreeningAdvanceRequest,
    ResearchDNAScreeningProgressEnvelope,
    ResearchDNAScreeningRecommendationEnvelope,
    ResearchDNAScreeningQueueEnvelope,
    ResearchDNAScreeningSessionEnvelope,
    ResearchDNARefineRequest,
    ResearchDNAScreeningRequest,
    ResearchDNAUpdateRequest,
)
from src.profiles.research_dna_service import (
    ResearchDNAStateError,
    approve_pilot,
    create_research_dna,
    load_latest_screening_guidance_artifact,
    load_next_screening_candidate,
    load_research_dna_resume_snapshot,
    load_research_dna_run_index,
    resolve_research_dna_run_id,
    load_screening_progress_report,
    load_screening_guidance_index_artifact,
    load_screening_operator_guidance,
    load_screening_queue_artifact,
    load_screening_session,
    lock_research_dna,
    materialize_screening_guidance_artifact,
    log_interview_response,
    materialize_reranked_screening_queue,
    refine_query_version,
    run_pilot,
    screen_current_candidate_and_load_session,
    submit_screening_decision_and_load_session,
    submit_screening_decision,
    unlock_research_dna,
    update_research_dna,
)
from src.profiles.research_dna_projection import sync_research_dna_profile
from src.profiles.research_dna_store import ResearchDNARevisionConflictError, load_research_dna
from src.profiles.profile_store import load_profiles
from src.services.downloader_ops_metrics import Thresholds, collect_metrics, evaluate_alerts
from src.services.event_log import (
    get_execution_run_params,
    list_run_events,
    list_user_actions,
    log_request_audit,
    log_user_action,
    sanitize_event_payload_for_log,
    sanitize_event_text_for_log,
)
from src.services.path_masking import is_path_masking_enabled, mask_local_path
from src.services.paper_ops_summary import (
    artifact_snapshot_from_run_dir,
    ArtifactOperationalSnapshot,
    ArtifactSnapshotCache,
    build_ops_summary_from_snapshot,
    build_ops_summary_for_candidate_ids,
)
from src.services.fixture_visibility import include_test_fixtures_enabled, is_test_fixture_paper_record
from src.services.identity import paper_id_candidate_ids, paper_id_search_variants, paper_id_self_and_suffix_candidate_ids
from src.services.runtime_readiness import (
    collect_runtime_readiness,
    summarize_browser_runtime_readiness,
)
from src.services.stale_jobs import collect_stale_jobs
from src.services.stale_jobs import collect_stale_running_incidents
from src.services.stale_jobs import capture_stale_running_incident_snapshot
from src.services.stale_jobs import reclaim_stale_running_job
from src.services.stale_jobs import requeue_reclaimed_job
from src.services.runtime_paths import (
    artifact_paper_dir_candidates,
    artifact_run_dir,
    artifacts_root,
    frontend_runtime_dir,
    preferred_artifact_paper_dir,
)
from src.services.stats_repair import seed_stats_reports_from_claimset
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .routers import (
    artifact_feedback,
    artifact_generation_outcomes,
    chart_packs,
    feedback,
    image_evidence,
    meeting_packs,
    method_comparisons,
    obsidian,
    paper_syntheses,
    paper_notes,
    project_context_links,
    protocol_cards,
    skills,
    talk_packs,
)


_IP_NETWORK_TYPES = ipaddress.IPv4Network | ipaddress.IPv6Network


def _best_effort_log_user_action(
    *,
    paper_id: str | None,
    action_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        log_user_action(
            paper_id=paper_id,
            action_type=action_type,
            source=source,
            payload=payload,
        )
    except Exception:
        # User-action logging must never block the primary workflow.
        pass


def _best_effort_log_request_audit(
    *,
    source: str,
    client_ip: str | None,
    host: str | None,
    method: str,
    path: str,
    status_code: int,
    outcome: str,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        log_request_audit(
            source=source,
            client_ip=client_ip,
            host=host,
            method=method,
            path=path,
            status_code=status_code,
            outcome=outcome,
            payload=payload,
        )
    except Exception:
        # Security audit logging must stay best-effort.
        pass

def _resolve_cors_allow_origins() -> list[str]:
    raw = (
        os.getenv("LATTICE_CORS_ALLOW_ORIGINS")
        or os.getenv("PAPERPIPE_CORS_ALLOW_ORIGINS")
        or ""
    ).strip()
    if not raw:
        return [
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://testserver",
        ]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://testserver",
    ]


def _ops_summary_candidate_ids(paper_id: str) -> list[str]:
    return paper_id_self_and_suffix_candidate_ids(paper_id)


def _resolve_api_key() -> str:
    return (
        os.getenv("LATTICE_API_KEY")
        or os.getenv("PAPERPIPE_API_KEY")
        or ""
    ).strip()


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_beta_username() -> str:
    return (
        os.getenv("LATTICE_BETA_USERNAME")
        or os.getenv("PAPERPIPE_BETA_USERNAME")
        or "beta"
    ).strip() or "beta"


def _resolve_beta_password() -> str:
    return (
        os.getenv("LATTICE_BETA_PASSWORD")
        or os.getenv("PAPERPIPE_BETA_PASSWORD")
        or ""
    ).strip()


def _resolve_beta_auth_rate_limit_count() -> int:
    raw = (
        os.getenv("LATTICE_BETA_AUTH_RATE_LIMIT_COUNT")
        or os.getenv("PAPERPIPE_BETA_AUTH_RATE_LIMIT_COUNT")
        or ""
    ).strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            return 0
        return max(value, 0)
    return 20 if _resolve_beta_password() else 0


def _resolve_beta_auth_rate_limit_window_seconds() -> int:
    raw = (
        os.getenv("LATTICE_BETA_AUTH_RATE_LIMIT_WINDOW_SECONDS")
        or os.getenv("PAPERPIPE_BETA_AUTH_RATE_LIMIT_WINDOW_SECONDS")
        or ""
    ).strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            return 300
        return max(value, 1)
    return 300


def _resolve_api_docs_enabled() -> bool:
    raw = (
        os.getenv("LATTICE_ENABLE_API_DOCS")
        or os.getenv("PAPERPIPE_ENABLE_API_DOCS")
        or ""
    ).strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return not bool(_resolve_beta_password())


def _resolve_browser_detailed_runtime_readiness_enabled() -> bool:
    raw = (
        os.getenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS")
        or os.getenv("PAPERPIPE_BROWSER_DETAILED_RUNTIME_READINESS")
        or ""
    ).strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return not bool(_resolve_beta_password())


def _resolve_browser_audit_logging_enabled() -> bool:
    raw = (
        os.getenv("LATTICE_BROWSER_AUDIT_LOGGING")
        or os.getenv("PAPERPIPE_BROWSER_AUDIT_LOGGING")
        or ""
    ).strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return (
        bool(_resolve_beta_password())
        or _resolve_browser_write_rate_limit_count() > 0
        or _resolve_browser_read_rate_limit_count() > 0
    )


def _resolve_browser_write_rate_limit_count() -> int:
    raw = (
        os.getenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT")
        or os.getenv("PAPERPIPE_BROWSER_WRITE_RATE_LIMIT_COUNT")
        or ""
    ).strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            return 0
        return max(value, 0)
    return 30 if _resolve_beta_password() else 0


def _resolve_browser_write_rate_limit_window_seconds() -> int:
    raw = (
        os.getenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS")
        or os.getenv("PAPERPIPE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS")
        or ""
    ).strip()
    if not raw:
        return 60
    try:
        value = int(raw)
    except ValueError:
        return 60
    return max(value, 1)


def _resolve_browser_read_rate_limit_count() -> int:
    raw = (
        os.getenv("LATTICE_BROWSER_READ_RATE_LIMIT_COUNT")
        or os.getenv("PAPERPIPE_BROWSER_READ_RATE_LIMIT_COUNT")
        or ""
    ).strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            return 0
        return max(value, 0)
    return 300 if _resolve_beta_password() else 0


def _resolve_browser_read_rate_limit_window_seconds() -> int:
    raw = (
        os.getenv("LATTICE_BROWSER_READ_RATE_LIMIT_WINDOW_SECONDS")
        or os.getenv("PAPERPIPE_BROWSER_READ_RATE_LIMIT_WINDOW_SECONDS")
        or ""
    ).strip()
    if not raw:
        return 60
    try:
        value = int(raw)
    except ValueError:
        return 60
    return max(value, 1)


def _resolve_allowed_hosts() -> list[str]:
    raw = (
        os.getenv("LATTICE_ALLOWED_HOSTS")
        or os.getenv("PAPERPIPE_ALLOWED_HOSTS")
        or ""
    ).strip()
    if not raw:
        return ["127.0.0.1", "localhost", "testserver"]
    hosts = [item.strip() for item in raw.split(",") if item.strip()]
    return hosts or ["127.0.0.1", "localhost", "testserver"]


def _resolve_trusted_proxy_ips() -> set[str]:
    raw = (
        os.getenv("LATTICE_TRUSTED_PROXY_IPS")
        or os.getenv("PAPERPIPE_TRUSTED_PROXY_IPS")
        or ""
    ).strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _resolve_beta_allowed_ips() -> tuple[set[str], tuple[_IP_NETWORK_TYPES, ...]]:
    raw = (
        os.getenv("LATTICE_BETA_ALLOWED_IPS")
        or os.getenv("PAPERPIPE_BETA_ALLOWED_IPS")
        or ""
    ).strip()
    if not raw:
        return set(), ()

    literals: set[str] = set()
    networks: list[_IP_NETWORK_TYPES] = []
    for item in (part.strip().lower() for part in raw.split(",") if part.strip()):
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            literals.add(item)
    return literals, tuple(networks)


def _is_chat_enabled() -> bool:
    raw = (
        os.getenv("CHAT_ENABLED")
        or os.getenv("LATTICE_CHAT_ENABLED")
        or os.getenv("PAPERPIPE_CHAT_ENABLED")
        or "false"
    ).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _path_matches(normalized_path: str, prefix: str) -> bool:
    return normalized_path == prefix or normalized_path.startswith(f"{prefix}/")


_PRIVATE_DATA_ROUTE_PREFIXES: tuple[str, ...] = (
    "/artifacts",
    "/artifact-feedback",
    "/artifact-generation-outcomes",
    "/chart-packs",
    "/feedback",
    "/image-evidence",
    "/jobs",
    "/meeting-packs",
    "/method-comparisons",
    "/obsidian",
    "/ops",
    "/ops/downloader-metrics",
    "/paper-notes",
    "/paper-syntheses",
    "/papers",
    "/personas",
    "/project-context-links",
    "/protocol-cards",
    "/research-dna",
    "/runs",
    "/talk-packs",
    "/user-actions",
    "/workspace-summary",
)
_PROTECTED_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_protected_write_method(method: str) -> bool:
    return method.upper() in _PROTECTED_WRITE_METHODS


def _requires_api_key(method: str, path: str) -> bool:
    normalized_method = method.upper()
    if normalized_method in {"HEAD", "OPTIONS"}:
        return False

    normalized = path.rstrip("/") or "/"
    if normalized_method == "GET":
        if normalized == "/health/ready":
            return True
        if any(_path_matches(normalized, prefix) for prefix in _PRIVATE_DATA_ROUTE_PREFIXES):
            return True
        return bool(re.match(r"^/papers/[^/]+/pdf$", normalized))

    if not _is_protected_write_method(normalized_method):
        return False

    if bool(re.match(r"^/paper-notes/[^/]+/operator-state$", normalized)):
        return True

    if normalized in {
        "/api/chat",
        "/artifact-feedback",
        "/artifact-generation-outcomes",
        "/jobs/deepread",
        "/feedback",
        "/obsidian/sync",
        "/ops/repair-stats",
        "/paper-notes/import-pdf",
        "/project-context-links",
        "/skills/run",
        "/user-actions",
    }:
        return True
    if normalized == "/research-dna" or normalized.startswith("/research-dna/"):
        return True
    if bool(
        re.match(
            r"^/ops/jobs/[^/]+/(reclaim-stale|requeue-reclaimed|stale-incident-snapshot)$",
            normalized,
        )
    ):
        return True
    if normalized.startswith("/meeting-packs/"):
        return True
    if normalized.startswith("/image-evidence/"):
        return True
    if normalized.startswith("/chart-packs/"):
        return True
    if normalized.startswith("/method-comparisons/"):
        return True
    if normalized.startswith("/paper-syntheses/"):
        return True
    if normalized.startswith("/talk-packs/"):
        return True
    if normalized.startswith("/protocol-cards/") or normalized == "/protocol-cards":
        return True
    return bool(re.match(r"^/jobs/[^/]+/cancel$", normalized))


def _rewrite_browser_api_path(path: str) -> str | None:
    normalized = path.rstrip("/") or "/"
    if normalized == "/api/chat" or normalized.startswith("/api/chat/"):
        return None
    if normalized == "/api":
        return "/"
    if normalized.startswith("/api/"):
        return normalized[4:] or "/"
    return None


def _requires_beta_gate(method: str, path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if _requires_api_key("GET", normalized) or _requires_api_key(method, normalized):
        return True
    if normalized in {
        "/api",
        "/assets",
        "/favicon.ico",
        "/sample.pdf",
        "/ui",
        "/ui-assets",
        "/vite.svg",
    }:
        return True
    if any(
        normalized.startswith(prefix)
        for prefix in (
            "/api/",
            "/assets/",
            "/ui/",
            "/ui-assets/",
        )
    ):
        return True
    if not API_DOCS_ENABLED:
        return False
    if normalized in {"/docs", "/openapi.json", "/redoc"}:
        return True
    return any(normalized.startswith(prefix) for prefix in ("/docs/", "/redoc/"))


def _is_browser_api_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return normalized == "/api" or normalized.startswith("/api/")


def _should_throttle_browser_write(method: str, original_path: str, rewritten_path: str | None) -> bool:
    if not _is_protected_write_method(method) or not _is_browser_api_path(original_path):
        return False
    normalized = (rewritten_path or (original_path.rstrip("/") or "/")).rstrip("/") or "/"
    if normalized == "/user-actions":
        return False
    return _requires_api_key(method, normalized)


def _should_throttle_browser_read(method: str, original_path: str, rewritten_path: str | None) -> bool:
    if method.upper() != "GET" or not _is_browser_api_path(original_path):
        return False
    normalized = (rewritten_path or (original_path.rstrip("/") or "/")).rstrip("/") or "/"
    return _requires_api_key("GET", normalized)


def _should_throttle_direct_protected_read(method: str, original_path: str) -> bool:
    if method.upper() != "GET" or _is_browser_api_path(original_path):
        return False
    normalized = (original_path.rstrip("/") or "/").rstrip("/") or "/"
    return _requires_api_key("GET", normalized)


def _should_throttle_direct_protected_write(method: str, original_path: str) -> bool:
    if not _is_protected_write_method(method) or _is_browser_api_path(original_path):
        return False
    normalized = (original_path.rstrip("/") or "/").rstrip("/") or "/"
    if normalized == "/user-actions":
        return False
    return _requires_api_key(method, normalized)


def _should_audit_browser_request(method: str, original_path: str, rewritten_path: str | None) -> bool:
    if not _is_protected_write_method(method) or not _is_browser_api_path(original_path):
        return False
    normalized = (rewritten_path or (original_path.rstrip("/") or "/")).rstrip("/") or "/"
    return normalized != "/user-actions"


def _request_has_valid_beta_auth(request: Request) -> bool:
    expected_password = _resolve_beta_password()
    if not expected_password:
        return True
    auth_header = (MutableHeaders(scope=request.scope).get("authorization") or "").strip()
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "basic" or not token:
        return False
    try:
        decoded = b64decode(token).decode("utf-8")
    except (BinasciiError, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    return (
        secrets.compare_digest(username, _resolve_beta_username())
        and secrets.compare_digest(password, expected_password)
    )


def _request_has_beta_auth_attempt(request: Request) -> bool:
    return bool((MutableHeaders(scope=request.scope).get("authorization") or "").strip())


def _normalize_origin(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def _hostname_from_host_value(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(f"//{raw}")
    hostname = str(parsed.hostname or "").strip().lower()
    return hostname or None


def _is_loopback_host(value: str | None) -> bool:
    hostname = _hostname_from_host_value(value)
    if not hostname:
        return False
    if hostname in {"localhost", "testserver"}:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _origin_host(origin: str | None) -> str | None:
    normalized = _normalize_origin(origin)
    if not normalized:
        return None
    return _hostname_from_host_value(urlparse(normalized).netloc)


def _allowed_browser_origins_for_request(request: Request) -> set[str]:
    allowed = {
        normalized
        for normalized in (_normalize_origin(item) for item in _resolve_cors_allow_origins())
        if normalized
    }
    host = _host_for_request(request)
    if host:
        scheme = "https" if _request_is_https(request) else "http"
        allowed.add(f"{scheme}://{host.lower()}")
    return allowed


def _request_has_valid_browser_origin(request: Request, original_path: str) -> bool:
    if not _is_protected_write_method(request.method) or not _is_browser_api_path(original_path):
        return True
    origin = _normalize_origin(request.headers.get("origin"))
    if not origin:
        return False
    if origin in _allowed_browser_origins_for_request(request):
        return True
    # Local Vite/dev flows proxy browser writes through a loopback frontend origin.
    return _is_loopback_host(_host_for_request(request)) and _is_loopback_host(_origin_host(origin))


def _beta_gate_response() -> Response:
    return Response(
        status_code=401,
        content="Authentication required",
        headers={"WWW-Authenticate": 'Basic realm="Lattice Private Beta", charset="UTF-8"'},
    )


def _request_is_https(request: Request) -> bool:
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").strip().lower()
    return request.url.scheme == "https" or forwarded_proto == "https"


def _client_ip_for_request(request: Request) -> str | None:
    client = getattr(request.client, "host", None)
    value = str(client or "").strip()
    if value and value in _resolve_trusted_proxy_ips():
        forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
        if forwarded_for:
            first = forwarded_for.split(",", 1)[0].strip()
            if first:
                return first
    return value or None


def _request_ip_is_allowed(client_ip: str | None) -> bool:
    literals, networks = _resolve_beta_allowed_ips()
    if not literals and not networks:
        return True

    candidate = str(client_ip or "").strip().lower()
    if not candidate:
        return False
    if candidate in literals:
        return True
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return any(address in network for network in networks)


def _request_has_valid_api_key_header(request: Request, expected_key: str) -> bool:
    if not expected_key:
        return True
    provided = str(request.headers.get("x-api-key") or "").strip()
    return bool(provided) and secrets.compare_digest(provided, expected_key)


def _allow_missing_api_key_for_private_route(request: Request) -> bool:
    if _resolve_beta_password():
        return True
    if _truthy_env("LATTICE_ALLOW_UNAUTHENTICATED_PRIVATE_API") or _truthy_env("PAPERPIPE_ALLOW_UNAUTHENTICATED_PRIVATE_API"):
        return True
    return _is_loopback_host(_host_for_request(request))


def _host_for_request(request: Request) -> str | None:
    host = str(request.headers.get("host") or "").strip()
    if host:
        return host
    hostname = getattr(request.url, "hostname", None)
    value = str(hostname or "").strip()
    return value or None


def _audit_outcome_for_status(status_code: int) -> str:
    if status_code == 429:
        return "rate_limited"
    if status_code in {401, 403}:
        return "denied"
    if status_code >= 500:
        return "server_error"
    if status_code >= 400:
        return "client_error"
    return "allowed"


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, window_seconds: int, limit: int) -> tuple[bool, int, int]:
        if limit <= 0:
            return True, 0, 0
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - float(window_seconds)
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, math.ceil(bucket[0] + float(window_seconds) - now))
                return False, len(bucket), retry_after
            bucket.append(now)
            return True, len(bucket), 0

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


def _apply_security_headers(request: Request, response: Response) -> Response:
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _request_is_https(request):
        headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")

    content_type = str(headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type == "text/html":
        headers.setdefault(
            "Content-Security-Policy",
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'; object-src 'none'",
        )
    return response


_ABSOLUTE_PATH_TOKEN_RE = re.compile(
    r"(?<![:/\w])/(?:Users|private|var|tmp|Volumes|home|opt|mnt|srv|workspace|app)"
    r"(?:/[^\s\"'<>`|)\]}]+)*"
)


def _mask_local_paths_in_text(value: str) -> str:
    if not is_path_masking_enabled():
        return value

    def replace(match: re.Match[str]) -> str:
        raw_path = match.group(0)
        return mask_local_path(raw_path) or raw_path

    return _ABSOLUTE_PATH_TOKEN_RE.sub(replace, value)


def _sanitize_exception_detail_for_response(detail: Any) -> Any:
    sanitized = sanitize_event_payload_for_log(detail)
    if isinstance(sanitized, dict):
        return {
            str(key): _sanitize_exception_detail_for_response(value)
            for key, value in sanitized.items()
        }
    if isinstance(sanitized, list):
        return [_sanitize_exception_detail_for_response(item) for item in sanitized]
    if isinstance(sanitized, tuple):
        return [_sanitize_exception_detail_for_response(item) for item in sanitized]
    if isinstance(sanitized, str):
        return _mask_local_paths_in_text(sanitized)
    return sanitized


def _drop_validation_input_echo(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _drop_validation_input_echo(item)
            for key, item in value.items()
            if str(key) != "input"
        }
    if isinstance(value, list):
        return [_drop_validation_input_echo(item) for item in value]
    return value


def _sanitize_request_validation_errors(exc: RequestValidationError) -> Any:
    errors = jsonable_encoder(exc.errors())
    return _drop_validation_input_echo(_sanitize_exception_detail_for_response(errors))


def _request_trace_id(request: Request) -> str:
    raw = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
    value = str(raw or "").strip()
    return value or f"trace_{uuid.uuid4().hex}"


def _error_response_payload(
    *,
    request: Request,
    status_code: int,
    detail: Any,
    default_message: str,
    error_code: str | None = None,
) -> dict[str, Any]:
    message = default_message
    details: Any | None = detail
    resolved_error_code = error_code or f"HTTP_{status_code}"
    if isinstance(detail, dict):
        resolved_error_code = str(detail.get("error_code") or resolved_error_code)
        raw_message = detail.get("message")
        if raw_message is not None:
            message = str(raw_message)
    elif isinstance(detail, str) and detail.strip():
        message = detail.strip()
        details = None

    return ErrorResponse(
        error_code=resolved_error_code,
        message=message,
        trace_id=_request_trace_id(request),
        details=details,
        detail=detail,
    ).model_dump(exclude_none=True)


API_DOCS_ENABLED = _resolve_api_docs_enabled()
_BETA_AUTH_LIMITER = _SlidingWindowLimiter()
_BROWSER_READ_LIMITER = _SlidingWindowLimiter()
_BROWSER_WRITE_LIMITER = _SlidingWindowLimiter()

app = FastAPI(
    title="Lattice API",
    version="3.1.0",
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url="/redoc" if API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if API_DOCS_ENABLED else None,
)


@app.exception_handler(StarletteHTTPException)
async def sanitized_http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = _sanitize_exception_detail_for_response(exc.detail)
    response = JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=_error_response_payload(
            request=request,
            status_code=exc.status_code,
            detail=detail,
            default_message=str(exc.detail or exc.status_code),
        ),
    )
    return _apply_security_headers(request, response)


@app.exception_handler(RequestValidationError)
async def sanitized_request_validation_exception_handler(request: Request, exc: RequestValidationError):
    detail = _sanitize_request_validation_errors(exc)
    response = JSONResponse(
        status_code=422,
        content=_error_response_payload(
            request=request,
            status_code=422,
            detail=detail,
            default_message="Request validation failed",
            error_code="VALIDATION_ERROR",
        ),
    )
    return _apply_security_headers(request, response)


app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_resolve_allowed_hosts(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _reset_request_limiters() -> None:
    _BETA_AUTH_LIMITER.clear()
    _BROWSER_READ_LIMITER.clear()
    _BROWSER_WRITE_LIMITER.clear()


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    original_path = str(request.scope.get("path") or request.url.path or "/")
    rewritten_path = _rewrite_browser_api_path(original_path)
    client_ip = _client_ip_for_request(request)
    host = _host_for_request(request)
    if request.method.upper() != "OPTIONS" and _requires_beta_gate(request.method, original_path):
        if not _request_ip_is_allowed(client_ip):
            if _resolve_browser_audit_logging_enabled():
                _best_effort_log_request_audit(
                    source="access_policy",
                    client_ip=client_ip,
                    host=host,
                    method=request.method,
                    path=original_path,
                    status_code=403,
                    outcome="ip_denied",
                    payload={"scope": "ip_allowlist"},
                )
            return _apply_security_headers(
                request,
                JSONResponse(
                    status_code=403,
                    content={
                        "error_code": "IP_NOT_ALLOWED",
                        "message": "Client IP is not allowed for this deployment.",
                    },
                ),
            )
        if not _request_has_valid_beta_auth(request):
            beta_auth_limit = _resolve_beta_auth_rate_limit_count()
            if beta_auth_limit > 0 and _request_has_beta_auth_attempt(request):
                beta_auth_window_seconds = _resolve_beta_auth_rate_limit_window_seconds()
                limiter_key = f"{client_ip or 'unknown'}:beta_auth"
                allowed, seen_count, retry_after = _BETA_AUTH_LIMITER.allow(
                    limiter_key,
                    window_seconds=beta_auth_window_seconds,
                    limit=beta_auth_limit,
                )
                if not allowed:
                    if _resolve_browser_audit_logging_enabled():
                        _best_effort_log_request_audit(
                            source="browser_security",
                            client_ip=client_ip,
                            host=host,
                            method=request.method,
                            path=original_path,
                            status_code=429,
                            outcome="beta_auth_rate_limited",
                            payload={
                                "scope": "beta_gate",
                                "limit": beta_auth_limit,
                                "window_seconds": beta_auth_window_seconds,
                                "seen_count": seen_count,
                                "retry_after_seconds": retry_after,
                            },
                        )
                    return _apply_security_headers(
                        request,
                        JSONResponse(
                            status_code=429,
                            headers={"Retry-After": str(retry_after)},
                            content={
                                "error_code": "BETA_AUTH_RATE_LIMITED",
                                "message": "Beta auth retry limit exceeded.",
                                "retry_after_seconds": retry_after,
                                "limit": beta_auth_limit,
                                "window_seconds": beta_auth_window_seconds,
                            },
                        ),
                    )
            if _resolve_browser_audit_logging_enabled():
                _best_effort_log_request_audit(
                    source="browser_security",
                    client_ip=client_ip,
                    host=host,
                    method=request.method,
                    path=original_path,
                    status_code=401,
                    outcome="beta_auth_denied",
                    payload={"scope": "beta_gate"},
                )
            return _apply_security_headers(request, _beta_gate_response())

    if not _request_has_valid_browser_origin(request, original_path):
        if _resolve_browser_audit_logging_enabled():
            _best_effort_log_request_audit(
                source="browser_security",
                client_ip=client_ip,
                host=host,
                method=request.method,
                path=original_path,
                status_code=403,
                outcome="origin_denied",
                payload={"scope": "browser_origin"},
            )
        return _apply_security_headers(
            request,
            JSONResponse(
                status_code=403,
                content={
                    "error_code": "FORBIDDEN",
                    "message": "Cross-origin browser writes are not allowed.",
                },
            ),
        )

    if _should_throttle_browser_read(request.method, original_path, rewritten_path):
        rate_limit_count = _resolve_browser_read_rate_limit_count()
        if rate_limit_count > 0:
            window_seconds = _resolve_browser_read_rate_limit_window_seconds()
            limiter_key = f"{client_ip or 'unknown'}:browser_read"
            allowed, seen_count, retry_after = _BROWSER_READ_LIMITER.allow(
                limiter_key,
                window_seconds=window_seconds,
                limit=rate_limit_count,
            )
            if not allowed:
                if _resolve_browser_audit_logging_enabled():
                    _best_effort_log_request_audit(
                        source="browser_api",
                        client_ip=client_ip,
                        host=host,
                        method=request.method,
                        path=original_path,
                        status_code=429,
                        outcome="rate_limited",
                        payload={
                            "scope": "browser_read",
                            "window_seconds": window_seconds,
                            "limit": rate_limit_count,
                            "seen_count": seen_count,
                            "retry_after_seconds": retry_after,
                            "rewritten_path": rewritten_path,
                        },
                    )
                return _apply_security_headers(
                    request,
                    JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={
                            "error_code": "BROWSER_READ_RATE_LIMITED",
                            "message": "Browser read rate limit exceeded",
                            "retry_after_seconds": retry_after,
                            "limit": rate_limit_count,
                            "window_seconds": window_seconds,
                        },
                    ),
                )

    if _should_throttle_browser_write(request.method, original_path, rewritten_path):
        rate_limit_count = _resolve_browser_write_rate_limit_count()
        if rate_limit_count > 0:
            window_seconds = _resolve_browser_write_rate_limit_window_seconds()
            limiter_key = f"{client_ip or 'unknown'}:browser_write"
            allowed, seen_count, retry_after = _BROWSER_WRITE_LIMITER.allow(
                limiter_key,
                window_seconds=window_seconds,
                limit=rate_limit_count,
            )
            if not allowed:
                if _resolve_browser_audit_logging_enabled():
                    _best_effort_log_request_audit(
                        source="browser_api",
                        client_ip=client_ip,
                        host=host,
                        method=request.method,
                        path=original_path,
                        status_code=429,
                        outcome="rate_limited",
                        payload={
                            "scope": "browser_write",
                            "window_seconds": window_seconds,
                            "limit": rate_limit_count,
                            "seen_count": seen_count,
                            "retry_after_seconds": retry_after,
                            "rewritten_path": rewritten_path,
                        },
                    )
                return _apply_security_headers(
                    request,
                    JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={
                            "error_code": "BROWSER_WRITE_RATE_LIMITED",
                            "message": "Browser write rate limit exceeded",
                            "retry_after_seconds": retry_after,
                            "limit": rate_limit_count,
                            "window_seconds": window_seconds,
                        },
                    ),
                )

    expected_key = _resolve_api_key()
    if _should_throttle_direct_protected_read(request.method, original_path):
        if _request_has_valid_api_key_header(request, expected_key):
            rate_limit_count = _resolve_browser_read_rate_limit_count()
            if rate_limit_count > 0:
                window_seconds = _resolve_browser_read_rate_limit_window_seconds()
                limiter_key = f"{client_ip or 'unknown'}:protected_read"
                allowed, seen_count, retry_after = _BROWSER_READ_LIMITER.allow(
                    limiter_key,
                    window_seconds=window_seconds,
                    limit=rate_limit_count,
                )
                if not allowed:
                    if _resolve_browser_audit_logging_enabled():
                        _best_effort_log_request_audit(
                            source="protected_api",
                            client_ip=client_ip,
                            host=host,
                            method=request.method,
                            path=original_path,
                            status_code=429,
                            outcome="rate_limited",
                            payload={
                                "scope": "protected_read",
                                "window_seconds": window_seconds,
                                "limit": rate_limit_count,
                                "seen_count": seen_count,
                                "retry_after_seconds": retry_after,
                            },
                        )
                    return _apply_security_headers(
                        request,
                        JSONResponse(
                            status_code=429,
                            headers={"Retry-After": str(retry_after)},
                            content={
                                "error_code": "PROTECTED_READ_RATE_LIMITED",
                                "message": "Protected read rate limit exceeded",
                                "retry_after_seconds": retry_after,
                                "limit": rate_limit_count,
                                "window_seconds": window_seconds,
                            },
                        ),
                    )
    if _should_throttle_direct_protected_write(request.method, original_path):
        if _request_has_valid_api_key_header(request, expected_key):
            rate_limit_count = _resolve_browser_write_rate_limit_count()
            if rate_limit_count > 0:
                window_seconds = _resolve_browser_write_rate_limit_window_seconds()
                limiter_key = f"{client_ip or 'unknown'}:protected_write"
                allowed, seen_count, retry_after = _BROWSER_WRITE_LIMITER.allow(
                    limiter_key,
                    window_seconds=window_seconds,
                    limit=rate_limit_count,
                )
                if not allowed:
                    if _resolve_browser_audit_logging_enabled():
                        _best_effort_log_request_audit(
                            source="protected_api",
                            client_ip=client_ip,
                            host=host,
                            method=request.method,
                            path=original_path,
                            status_code=429,
                            outcome="rate_limited",
                            payload={
                                "scope": "protected_write",
                                "window_seconds": window_seconds,
                                "limit": rate_limit_count,
                                "seen_count": seen_count,
                                "retry_after_seconds": retry_after,
                            },
                        )
                    return _apply_security_headers(
                        request,
                        JSONResponse(
                            status_code=429,
                            headers={"Retry-After": str(retry_after)},
                            content={
                                "error_code": "PROTECTED_WRITE_RATE_LIMITED",
                                "message": "Protected write rate limit exceeded",
                                "retry_after_seconds": retry_after,
                                "limit": rate_limit_count,
                                "window_seconds": window_seconds,
                            },
                        ),
                    )
    if rewritten_path is not None:
        request.scope["path"] = rewritten_path
        request.scope["raw_path"] = rewritten_path.encode("utf-8")
        if expected_key:
            MutableHeaders(scope=request.scope)["x-api-key"] = expected_key
    elif expected_key and _is_browser_api_path(original_path):
        current_browser_path = (original_path.rstrip("/") or "/").rstrip("/") or "/"
        if _requires_api_key(request.method, current_browser_path):
            # Keep same-origin browser /api/* routes on the server-side secret boundary
            # even when they do not rewrite to a root backend path.
            MutableHeaders(scope=request.scope)["x-api-key"] = expected_key

    current_path = str(request.scope.get("path") or request.url.path or "/")
    if not expected_key and _requires_api_key(request.method, current_path) and not _allow_missing_api_key_for_private_route(request):
        return _apply_security_headers(
            request,
            JSONResponse(
                status_code=401,
                content={
                    "error_code": "API_KEY_NOT_CONFIGURED",
                    "message": "Protected private routes require LATTICE_API_KEY or beta auth when served on a non-loopback host.",
                },
            ),
        )

    if not expected_key:
        response = await call_next(request)
        response = _apply_security_headers(request, response)
        if _resolve_browser_audit_logging_enabled() and _should_audit_browser_request(request.method, original_path, rewritten_path):
            _best_effort_log_request_audit(
                source="browser_api",
                client_ip=client_ip,
                host=host,
                method=request.method,
                path=original_path,
                status_code=response.status_code,
                outcome=_audit_outcome_for_status(response.status_code),
                payload={"scope": "browser_write", "rewritten_path": rewritten_path},
            )
        return response
    if not _requires_api_key(request.method, current_path):
        response = await call_next(request)
        response = _apply_security_headers(request, response)
        if _resolve_browser_audit_logging_enabled() and _should_audit_browser_request(request.method, original_path, rewritten_path):
            _best_effort_log_request_audit(
                source="browser_api",
                client_ip=client_ip,
                host=host,
                method=request.method,
                path=original_path,
                status_code=response.status_code,
                outcome=_audit_outcome_for_status(response.status_code),
                payload={"scope": "browser_write", "rewritten_path": rewritten_path},
            )
        return response

    supplied_key = (MutableHeaders(scope=request.scope).get("x-api-key") or "").strip()
    if supplied_key != expected_key:
        return _apply_security_headers(
            request,
            JSONResponse(
                status_code=401,
                content={
                    "error_code": "UNAUTHORIZED",
                    "message": "Missing or invalid X-API-Key",
                },
            ),
        )
    response = await call_next(request)
    response = _apply_security_headers(request, response)
    if _resolve_browser_audit_logging_enabled() and _should_audit_browser_request(request.method, original_path, rewritten_path):
        _best_effort_log_request_audit(
            source="browser_api",
            client_ip=client_ip,
            host=host,
            method=request.method,
            path=original_path,
            status_code=response.status_code,
            outcome=_audit_outcome_for_status(response.status_code),
            payload={"scope": "browser_write", "rewritten_path": rewritten_path},
        )
    return response

queue = JobQueue()
FRONTEND_DIR = frontend_runtime_dir()
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_DIST_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
FRONTEND_DIST_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"
FRONTEND_INDEX_PATH = FRONTEND_DIR / "index.html"
UI_SHELL_PATH = FRONTEND_DIR / "ui-shell.html"

if FRONTEND_DIR.exists():
    app.mount("/ui-assets", StaticFiles(directory=str(FRONTEND_DIR)), name="ui-assets")
if FRONTEND_DIST_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_ASSETS_DIR)), name="ui-dist-assets")

ARTIFACT_FILE_MAP: dict[str, str] = {
    "document_artifact": "document_artifact.json",
    "index_artifact": "index_artifact.json",
    "claimset": "claimset.json",
    "claimset_resolved": "claimset.resolved.json",
    "stats_report": "stats_report.json",
    "bootstrap_meta": "bootstrap_meta.json",
    "run_meta": "run_meta.json",
    "chunks": "chunks.jsonl",
    "evidence_extraction_bundle": "evidence_extraction_bundle.json",
}

ARTIFACT_ALIAS_MAP: dict[str, str] = {
    "document": "document_artifact",
    "document_artifact": "document_artifact",
    "index": "index_artifact",
    "index_artifact": "index_artifact",
    "claimset": "claimset",
    "claimset_resolved": "claimset_resolved",
    "claimset-resolved": "claimset_resolved",
    "stats": "stats_report",
    "stats_report": "stats_report",
    "bootstrap": "bootstrap_meta",
    "bootstrap_meta": "bootstrap_meta",
    "meta": "run_meta",
    "run_meta": "run_meta",
    "chunks": "chunks",
    "evidence_extraction_bundle": "evidence_extraction_bundle",
    "evidence-extraction-bundle": "evidence_extraction_bundle",
}

TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}


def _derive_paper_issues_state(item: dict[str, Any]) -> str:
    explicit_state = str(item.get("issues_state") or "").strip().lower()
    if explicit_state in {"flagged", "clear", "unavailable"}:
        return explicit_state
    issues_value = item.get("issues")
    issue_count = issues_value if isinstance(issues_value, int) else 0
    if issue_count > 0:
        return "flagged"
    issues_label = str(item.get("issues_label") or "").strip()
    if issues_label and re.search(r"not analy[sz]ed|unavailable|not available|pending|not reviewed|not run", issues_label, re.IGNORECASE):
        return "unavailable"
    status_value = str(item.get("status") or "").strip().upper()
    if status_value in {"NEW", "FETCHED", "PDF_MISSING", "GATED"}:
        return "unavailable"
    if status_value in {"PENDING_REVIEW", "QUARANTINED", "FAILED"}:
        return "flagged"
    if status_value in {"APPROVED", "INDEXED"}:
        return "clear"
    return "clear"


def _parse_iso_timestamp_sort_key(value: str | None) -> float:
    from datetime import datetime, timezone

    text = str(value or "").strip()
    if not text:
        return 0.0
    normalized = text.replace("Z", "+00:00")
    if "T" not in normalized and " " in normalized:
        normalized = normalized.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def _public_path(path_value: str | None) -> str | None:
    if path_value is None:
        return None
    if not is_path_masking_enabled():
        return path_value
    return mask_local_path(path_value)


@dataclass(frozen=True)
class _IndexedNoteItemLookup:
    exact: dict[str, tuple[int, PaperNoteIndexItem]]
    normalized: dict[str, tuple[int, PaperNoteIndexItem]]


@dataclass(frozen=True)
class _VisiblePaperCandidatePage:
    selected_candidates: list[dict[str, Any]]
    vault_path: Path | None
    note_items: list[PaperNoteIndexItem] | None
    note_slug_by_db_paper_id: dict[str, str]
    paper_table_columns: set[str]


@dataclass(frozen=True)
class _HomeWorkspaceSummaryContext:
    blocked: int
    needs_review: int
    note_context_limited: bool
    saved_notes: int = 0
    structured_notes: int = 0
    latest_note_updated_at: str | None = None


@dataclass(frozen=True)
class _SelectedDbPaperPageContext:
    selected_db_paper_ids: list[str]
    selected_db_rows_by_id: dict[str, Any]
    ops_candidate_ids_by_paper_id: dict[str, list[str]]
    note_item_lookup: _IndexedNoteItemLookup | None
    artifact_cache: ArtifactSnapshotCache


def _build_note_item_lookup_for_paper_ids(
    items: list[PaperNoteIndexItem],
    paper_ids: list[str],
) -> _IndexedNoteItemLookup:
    requested_paper_ids: list[str] = []
    seen_paper_ids: set[str] = set()
    for candidate in paper_ids:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        requested_paper_ids.append(paper_id)

    if not requested_paper_ids:
        return _IndexedNoteItemLookup(exact={}, normalized={})

    exact: dict[str, tuple[int, PaperNoteIndexItem]] = {}
    normalized: dict[str, tuple[int, PaperNoteIndexItem]] = {}
    remaining_paper_ids = set(requested_paper_ids)
    requested_exact_candidates: dict[str, set[str]] = {}
    requested_normalized_candidates: dict[str, set[str]] = {}
    for paper_id in requested_paper_ids:
        for candidate in paper_notes._paper_note_lookup_candidates(paper_id):
            requested_exact_candidates.setdefault(candidate, set()).add(paper_id)
            normalized_candidate = paper_notes._normalize_paper_note_id(candidate)
            if normalized_candidate:
                requested_normalized_candidates.setdefault(normalized_candidate, set()).add(paper_id)

    for order, item in enumerate(items):
        raw_variants, normalized_variants = _paper_note_identity_sets(item)
        for candidate in raw_variants:
            if candidate in requested_exact_candidates and candidate not in exact:
                exact[candidate] = (order, item)
        for candidate in normalized_variants:
            if candidate in requested_normalized_candidates and candidate not in normalized:
                normalized[candidate] = (order, item)
        resolved_now: set[str] = set()
        for candidate in raw_variants:
            resolved_now.update(requested_exact_candidates.get(candidate, ()))
        for candidate in normalized_variants:
            resolved_now.update(requested_normalized_candidates.get(candidate, ()))
        resolved_now.intersection_update(remaining_paper_ids)
        if not resolved_now:
            continue
        remaining_paper_ids.difference_update(resolved_now)
        if not remaining_paper_ids:
            break

    return _IndexedNoteItemLookup(exact=exact, normalized=normalized)


def _selected_db_paper_ids_needing_note_lookup(
    selected_candidates: list[dict[str, Any]],
    selected_db_rows_by_id: dict[str, Any],
) -> list[str]:
    paper_ids_needing_note_lookup: list[str] = []
    seen_paper_ids: set[str] = set()
    for candidate in selected_candidates:
        if candidate.get("kind") != "db":
            continue
        paper_id = str(candidate["row"]["paper_id"] or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        row = selected_db_rows_by_id.get(paper_id, candidate["row"])
        if not _db_row_may_need_note_backed_pdf_lookup(row):
            continue
        seen_paper_ids.add(paper_id)
        paper_ids_needing_note_lookup.append(paper_id)
    return paper_ids_needing_note_lookup


def _normalized_candidate_id_list(candidate_ids: Any) -> list[str]:
    normalized_candidate_ids: list[str] = []
    seen_candidate_ids: set[str] = set()
    for candidate_id in candidate_ids:
        normalized_candidate_id = str(candidate_id or "").strip()
        if not normalized_candidate_id or normalized_candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(normalized_candidate_id)
        normalized_candidate_ids.append(normalized_candidate_id)
    return normalized_candidate_ids


def _latest_run_id_from_artifact_cache_for_candidate_ids(
    candidate_ids: list[str],
    artifact_cache: ArtifactSnapshotCache,
) -> str | None:
    snapshots = [
        snapshot
        for candidate_id in _normalized_candidate_id_list(candidate_ids)
        if (snapshot := artifact_cache.get(candidate_id)) is not None and str(snapshot.run_id or "").strip()
    ]
    if not snapshots:
        return None
    selected = max(snapshots, key=lambda item: item.mtime)
    return str(selected.run_id or "").strip() or None


def _artifact_cache_covers_candidate_ids(
    candidate_ids: list[str],
    artifact_cache: ArtifactSnapshotCache,
) -> bool:
    normalized_candidate_ids = _normalized_candidate_id_list(candidate_ids)
    if not normalized_candidate_ids:
        return False
    return all(candidate_id in artifact_cache for candidate_id in normalized_candidate_ids)


_UNCACHED_ARTIFACT_GROUP = object()


def _ops_summary_from_artifact_cache_for_candidate_ids(
    candidate_ids: list[str],
    artifact_cache: ArtifactSnapshotCache,
) -> Any:
    snapshots: list[ArtifactOperationalSnapshot] = []
    for candidate_id in _normalized_candidate_id_list(candidate_ids):
        if candidate_id not in artifact_cache:
            return _UNCACHED_ARTIFACT_GROUP
        snapshot = artifact_cache[candidate_id]
        if snapshot is not None:
            snapshots.append(snapshot)
    if not snapshots:
        return None
    selected = max(snapshots, key=lambda item: item.mtime)
    return build_ops_summary_from_snapshot(selected)


def _normalized_candidate_id_group(candidate_ids: Any) -> tuple[str, ...]:
    return tuple(sorted(_normalized_candidate_id_list(candidate_ids)))


def _selected_db_paper_ids_needing_latest_run_lookup(
    selected_db_paper_ids: list[str],
    artifact_cache: ArtifactSnapshotCache,
    *,
    ops_candidate_ids_by_paper_id: dict[str, list[str]] | None = None,
) -> list[str]:
    paper_ids_needing_lookup: list[str] = []
    seen_paper_ids: set[str] = set()
    latest_run_from_cache_by_candidate_ids: dict[tuple[str, ...], str | None] = {}
    artifact_coverage_by_candidate_ids: dict[tuple[str, ...], bool] = {}
    for candidate in selected_db_paper_ids:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        ops_candidate_ids = (
            ops_candidate_ids_by_paper_id.get(paper_id)
            if ops_candidate_ids_by_paper_id is not None
            else None
        ) or _ops_summary_candidate_ids(paper_id)
        candidate_ids_key = _normalized_candidate_id_group(ops_candidate_ids)
        if not candidate_ids_key:
            continue
        if candidate_ids_key not in latest_run_from_cache_by_candidate_ids:
            latest_run_from_cache_by_candidate_ids[candidate_ids_key] = _latest_run_id_from_artifact_cache_for_candidate_ids(
                list(candidate_ids_key),
                artifact_cache,
            )
        if latest_run_from_cache_by_candidate_ids[candidate_ids_key]:
            continue
        if candidate_ids_key not in artifact_coverage_by_candidate_ids:
            artifact_coverage_by_candidate_ids[candidate_ids_key] = _artifact_cache_covers_candidate_ids(
                list(candidate_ids_key),
                artifact_cache,
            )
        if artifact_coverage_by_candidate_ids[candidate_ids_key]:
            continue
        paper_ids_needing_lookup.append(paper_id)
    return paper_ids_needing_lookup


def _selected_db_paper_ids_missing_note_slug(
    selected_db_paper_ids: list[str],
    note_slug_by_db_paper_id: dict[str, str],
) -> list[str]:
    missing_paper_ids: list[str] = []
    seen_paper_ids: set[str] = set()
    for candidate in selected_db_paper_ids:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        if paper_id not in note_slug_by_db_paper_id:
            missing_paper_ids.append(paper_id)
    return missing_paper_ids


def _combine_selected_db_paper_ids_for_note_lookup(
    primary_paper_ids: list[str],
    secondary_paper_ids: list[str],
) -> list[str]:
    combined_paper_ids: list[str] = []
    seen_paper_ids: set[str] = set()
    for candidate in [*primary_paper_ids, *secondary_paper_ids]:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        combined_paper_ids.append(paper_id)
    return combined_paper_ids


def _backfill_note_slug_mapping_for_selected_db_paper_ids(
    note_item_lookup: _IndexedNoteItemLookup | None,
    note_items: list[PaperNoteIndexItem] | None,
    selected_db_paper_ids: list[str],
    note_slug_by_db_paper_id: dict[str, str],
    *,
    missing_note_slug_paper_ids: list[str] | None = None,
) -> _IndexedNoteItemLookup | None:
    if missing_note_slug_paper_ids is None:
        missing_note_slug_paper_ids = _selected_db_paper_ids_missing_note_slug(
            selected_db_paper_ids,
            note_slug_by_db_paper_id,
        )
    if not missing_note_slug_paper_ids or note_items is None:
        return note_item_lookup

    if note_item_lookup is None:
        remaining_paper_ids = set(missing_note_slug_paper_ids)
        requested_exact_candidates: dict[str, set[str]] = {}
        requested_normalized_candidates: dict[str, set[str]] = {}
        for paper_id in missing_note_slug_paper_ids:
            for candidate in paper_notes._paper_note_lookup_candidates(paper_id):
                requested_exact_candidates.setdefault(candidate, set()).add(paper_id)
                normalized_candidate = paper_notes._normalize_paper_note_id(candidate)
                if normalized_candidate:
                    requested_normalized_candidates.setdefault(normalized_candidate, set()).add(paper_id)

        for item in note_items:
            note_slug = str(getattr(item, "slug", "") or "").strip()
            if not note_slug:
                continue
            direct_raw_variants: set[str] = set()
            for candidate in (getattr(item, "id", None), note_slug):
                if not candidate:
                    continue
                for variant in paper_notes._paper_id_variants(str(candidate)):
                    if variant:
                        direct_raw_variants.add(variant)
            if not direct_raw_variants:
                continue
            direct_normalized_variants = {
                normalized
                for value in direct_raw_variants
                if (normalized := paper_notes._normalize_paper_note_id(value))
            }
            resolved_now: set[str] = set()
            for candidate in direct_raw_variants:
                resolved_now.update(requested_exact_candidates.get(candidate, ()))
            for candidate in direct_normalized_variants:
                resolved_now.update(requested_normalized_candidates.get(candidate, ()))
            resolved_now.intersection_update(remaining_paper_ids)
            if not resolved_now:
                continue
            for paper_id in resolved_now:
                note_slug_by_db_paper_id.setdefault(paper_id, note_slug)
            remaining_paper_ids.difference_update(resolved_now)
            if not remaining_paper_ids:
                break
        return note_item_lookup

    for paper_id in missing_note_slug_paper_ids:
        resolved_note_item = _resolve_note_item_for_paper_id_from_lookup(note_item_lookup, paper_id)
        note_slug = str(getattr(resolved_note_item, "slug", "") or "").strip()
        if note_slug:
            note_slug_by_db_paper_id.setdefault(paper_id, note_slug)
    return note_item_lookup


def _prepare_selected_db_note_lookup_context(
    *,
    selected_candidates: list[dict[str, Any]],
    note_items: list[PaperNoteIndexItem] | None,
    selected_db_paper_ids: list[str],
    selected_db_rows_by_id: dict[str, Any],
    note_slug_by_db_paper_id: dict[str, str],
) -> _IndexedNoteItemLookup | None:
    if note_items is None or not selected_db_paper_ids:
        return None

    missing_note_slug_paper_ids = _selected_db_paper_ids_missing_note_slug(
        selected_db_paper_ids,
        note_slug_by_db_paper_id,
    )
    paper_ids_needing_note_lookup = _selected_db_paper_ids_needing_note_lookup(
        selected_candidates,
        selected_db_rows_by_id,
    )
    if not missing_note_slug_paper_ids and not paper_ids_needing_note_lookup:
        return None
    note_item_lookup: _IndexedNoteItemLookup | None = None
    if paper_ids_needing_note_lookup:
        note_item_lookup = _build_note_item_lookup_for_paper_ids(
            note_items,
            _combine_selected_db_paper_ids_for_note_lookup(
                paper_ids_needing_note_lookup,
                missing_note_slug_paper_ids,
            ),
        )
    return _backfill_note_slug_mapping_for_selected_db_paper_ids(
        note_item_lookup,
        note_items,
        selected_db_paper_ids,
        note_slug_by_db_paper_id,
        missing_note_slug_paper_ids=missing_note_slug_paper_ids,
    )


def _prepare_selected_db_paper_page_context(
    *,
    selected_candidates: list[dict[str, Any]],
    note_items: list[PaperNoteIndexItem] | None,
    note_slug_by_db_paper_id: dict[str, str],
    row_loader: Callable[[list[str]], dict[str, Any]],
) -> _SelectedDbPaperPageContext:
    selected_db_paper_ids: list[str] = []
    seen_selected_db_paper_ids: set[str] = set()
    for candidate in selected_candidates:
        if candidate.get("kind") != "db":
            continue
        paper_id = str(candidate["row"]["paper_id"] or "").strip()
        if not paper_id or paper_id in seen_selected_db_paper_ids:
            continue
        seen_selected_db_paper_ids.add(paper_id)
        selected_db_paper_ids.append(paper_id)
    if not selected_db_paper_ids:
        return _SelectedDbPaperPageContext(
            selected_db_paper_ids=[],
            selected_db_rows_by_id={},
            ops_candidate_ids_by_paper_id={},
            note_item_lookup=None,
            artifact_cache={},
        )
    selected_db_rows_by_id = row_loader(selected_db_paper_ids)
    ops_candidate_ids_by_paper_id = {
        paper_id: _ops_summary_candidate_ids(paper_id)
        for paper_id in selected_db_paper_ids
    }
    note_item_lookup = _prepare_selected_db_note_lookup_context(
        selected_candidates=selected_candidates,
        note_items=note_items,
        selected_db_paper_ids=selected_db_paper_ids,
        selected_db_rows_by_id=selected_db_rows_by_id,
        note_slug_by_db_paper_id=note_slug_by_db_paper_id,
    )
    artifact_cache: ArtifactSnapshotCache = {}
    _preload_artifact_snapshots_for_papers(
        artifacts_root(),
        selected_db_paper_ids,
        artifact_cache,
        ops_candidate_ids_by_paper_id=ops_candidate_ids_by_paper_id,
    )
    return _SelectedDbPaperPageContext(
        selected_db_paper_ids=selected_db_paper_ids,
        selected_db_rows_by_id=selected_db_rows_by_id,
        ops_candidate_ids_by_paper_id=ops_candidate_ids_by_paper_id,
        note_item_lookup=note_item_lookup,
        artifact_cache=artifact_cache,
    )


def _load_papers_table_columns() -> set[str]:
    conn = get_db_connection()
    try:
        try:
            return {
                str(row[1]).strip()
                for row in conn.execute("PRAGMA table_info(papers)").fetchall()
                if len(row) > 1 and str(row[1]).strip()
            }
        except sqlite3.OperationalError:
            return set()
    finally:
        conn.close()


def _load_paper_rows_for_listing(
    *,
    raw_limit: int = 5000,
    raw_offset: int = 0,
    lightweight: bool = False,
    table_columns: set[str] | None = None,
) -> list[Any]:
    conn = get_db_connection()
    try:
        try:
            select_columns = "*"
            order_by = "updated_at DESC"
            if lightweight:
                if table_columns is None:
                    table_columns = {
                        str(row[1]).strip()
                        for row in conn.execute("PRAGMA table_info(papers)").fetchall()
                        if len(row) > 1 and str(row[1]).strip()
                    }
                selected_columns: list[str] = [
                    column
                    for column in ("paper_id", "title", "pdf_path")
                    if column in table_columns
                ]
                if "updated_at" in table_columns:
                    selected_columns.insert(2, "updated_at")
                    order_by = "updated_at DESC"
                elif "created_at" in table_columns:
                    selected_columns.insert(2, "created_at AS updated_at")
                    order_by = "created_at DESC"
                else:
                    selected_columns.insert(2, "NULL AS updated_at")
                    order_by = "paper_id ASC"
                select_columns = ", ".join(selected_columns) if selected_columns else "paper_id"
            return conn.execute(
                f"SELECT {select_columns} FROM papers ORDER BY {order_by} LIMIT ? OFFSET ?",
                (raw_limit, raw_offset),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()


def _load_paper_rows_for_workspace_summary(*, raw_limit: int = 5000) -> list[Any]:
    conn = get_db_connection()
    try:
        try:
            table_columns = {
                str(row[1]).strip()
                for row in conn.execute("PRAGMA table_info(papers)").fetchall()
                if len(row) > 1 and str(row[1]).strip()
            }
            selected_columns = [
                column
                for column in (
                    "paper_id",
                    "title",
                    "pdf_path",
                    "status",
                    "issues",
                    "issues_label",
                    "issues_state",
                )
                if column in table_columns
            ]
            select_clause = ", ".join(selected_columns) if selected_columns else "paper_id"
            if "updated_at" in table_columns:
                order_by = "updated_at DESC"
            elif "created_at" in table_columns:
                order_by = "created_at DESC"
            else:
                order_by = "paper_id ASC"
            return conn.execute(
                f"SELECT {select_clause} FROM papers ORDER BY {order_by} LIMIT ? OFFSET 0",
                (raw_limit,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()


def _initial_listing_scan_limit(
    *,
    limit: int,
    offset: int,
    max_scan_limit: int,
) -> int:
    return max(
        limit,
        min(
            max_scan_limit,
            offset + max(limit * 4, 200),
        ),
    )


def _initial_listing_scan_limit_without_note_context(
    *,
    limit: int,
    offset: int,
    max_scan_limit: int,
) -> int:
    return max(
        1,
        min(
            max_scan_limit,
            offset + limit,
        ),
    )


def _next_listing_scan_limit(current_scan_limit: int, *, max_scan_limit: int) -> int:
    if current_scan_limit >= max_scan_limit:
        return current_scan_limit
    return min(max_scan_limit, max(current_scan_limit * 2, current_scan_limit + 200))


def _fetch_listing_response_rows_by_ids(
    paper_ids: list[str],
    *,
    table_columns: set[str] | None = None,
) -> dict[str, Any]:
    unique_paper_ids: list[str] = []
    seen_paper_ids: set[str] = set()
    for candidate in paper_ids:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        unique_paper_ids.append(paper_id)

    if not unique_paper_ids:
        return {}

    conn = get_db_connection()
    try:
        try:
            if table_columns is None:
                table_columns = {
                    str(row[1]).strip()
                    for row in conn.execute("PRAGMA table_info(papers)").fetchall()
                    if len(row) > 1 and str(row[1]).strip()
                }
            selected_columns = [
                column
                for column in (
                    "paper_id",
                    "title",
                    "authors",
                    "year",
                    "doi",
                    "link",
                    "pdf_link",
                    "pdf_path",
                    "pdf_status",
                    "status",
                    "issues",
                    "issues_label",
                    "issues_state",
                    "latest_job_id",
                    "is_escalated",
                    "escalation_reason",
                    "escalation_final_route",
                    "escalation_in_biomedical_scope",
                    "escalation_reason_codes",
                )
                if column in table_columns
            ]
            if "updated_at" in table_columns:
                selected_columns.append("updated_at")
            elif "created_at" in table_columns:
                selected_columns.append("created_at AS updated_at")
            else:
                selected_columns.append("NULL AS updated_at")
            escalation_columns = {
                "is_escalated",
                "escalation_reason",
                "escalation_final_route",
                "escalation_in_biomedical_scope",
                "escalation_reason_codes",
            }
            if "feedback_json" in table_columns and not escalation_columns.issubset(table_columns):
                selected_columns.append("feedback_json")
            select_clause = ", ".join(selected_columns) if selected_columns else "paper_id"
            placeholders = ", ".join("?" for _ in unique_paper_ids)
            rows = conn.execute(
                f"SELECT {select_clause} FROM papers WHERE paper_id IN ({placeholders})",
                tuple(unique_paper_ids),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
    finally:
        conn.close()

    return {
        str(row["paper_id"] or "").strip(): row
        for row in rows
        if str(row["paper_id"] or "").strip()
    }


def _fetch_listing_rail_rows_by_ids(
    paper_ids: list[str],
    *,
    table_columns: set[str] | None = None,
) -> dict[str, Any]:
    unique_paper_ids: list[str] = []
    seen_paper_ids: set[str] = set()
    for candidate in paper_ids:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        unique_paper_ids.append(paper_id)

    if not unique_paper_ids:
        return {}

    conn = get_db_connection()
    try:
        try:
            if table_columns is None:
                table_columns = {
                    str(row[1]).strip()
                    for row in conn.execute("PRAGMA table_info(papers)").fetchall()
                    if len(row) > 1 and str(row[1]).strip()
                }
            selected_columns = [
                column
                for column in (
                    "paper_id",
                    "title",
                    "authors",
                    "doi",
                    "link",
                    "pdf_link",
                    "pdf_path",
                    "status",
                    "issues",
                    "issues_label",
                    "issues_state",
                    "feedback_json",
                )
                if column in table_columns
            ]
            if "updated_at" in table_columns:
                selected_columns.append("updated_at")
            elif "created_at" in table_columns:
                selected_columns.append("created_at AS updated_at")
            else:
                selected_columns.append("NULL AS updated_at")
            select_clause = ", ".join(selected_columns) if selected_columns else "paper_id"
            placeholders = ", ".join("?" for _ in unique_paper_ids)
            rows = conn.execute(
                f"SELECT {select_clause} FROM papers WHERE paper_id IN ({placeholders})",
                tuple(unique_paper_ids),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
    finally:
        conn.close()

    return {
        str(row["paper_id"] or "").strip(): row
        for row in rows
        if str(row["paper_id"] or "").strip()
    }


def _resolve_note_item_for_paper_id_from_lookup(
    lookup: _IndexedNoteItemLookup,
    paper_id: str,
) -> PaperNoteIndexItem | None:
    ordered_candidates = paper_notes._paper_note_lookup_candidates(paper_id)
    if not ordered_candidates:
        return None

    for candidate in ordered_candidates:
        match = lookup.exact.get(candidate)
        if match is not None:
            return match[1]

    for candidate in ordered_candidates:
        normalized = paper_notes._normalize_paper_note_id(candidate)
        if not normalized:
            continue
        match = lookup.normalized.get(normalized)
        if match is not None:
            return match[1]
    return None


def _match_db_paper_id_for_note_variants(
    raw_variants: set[str],
    normalized_variants: set[str],
    *,
    db_paper_ids_by_exact_variant: dict[str, str],
    db_paper_ids_by_normalized_variant: dict[str, str],
) -> str | None:
    for candidate in raw_variants:
        matched = db_paper_ids_by_exact_variant.get(candidate)
        if matched:
            return matched
    for candidate in normalized_variants:
        matched = db_paper_ids_by_normalized_variant.get(candidate)
        if matched:
            return matched
    return None


def _push_visible_paper_candidate_window(
    heap: list[tuple[float, int, dict[str, Any]]],
    candidate: dict[str, Any],
    *,
    sequence: int,
    target_count: int,
) -> None:
    if target_count <= 0:
        return
    rank = (
        _parse_iso_timestamp_sort_key(candidate.get("sort_updated_at")),
        -sequence,
    )
    entry = (rank[0], rank[1], candidate)
    if len(heap) < target_count:
        heapq.heappush(heap, entry)
        return
    if rank > (heap[0][0], heap[0][1]):
        heapq.heapreplace(heap, entry)


def _paper_listing_fixture_record_from_row(row: Any) -> dict[str, Any]:
    def _value(column: str) -> Any:
        getter = getattr(row, "get", None)
        if callable(getter):
            return getter(column)
        try:
            return row[column]
        except Exception:
            return None

    return {
        "paper_id": str(_value("paper_id") or "").strip(),
        "title": str(_value("title") or "").strip(),
        "pdf_path": str(_value("pdf_path") or "").strip() or None,
    }


def _workspace_summary_issues_record_from_row(row: Any) -> dict[str, Any]:
    def _value(column: str) -> Any:
        getter = getattr(row, "get", None)
        if callable(getter):
            return getter(column)
        try:
            return row[column]
        except Exception:
            return None

    return {
        "paper_id": str(_value("paper_id") or "").strip() or None,
        "status": str(_value("status") or "").strip() or None,
        "issues": _value("issues"),
        "issues_label": str(_value("issues_label") or "").strip() or None,
        "issues_state": str(_value("issues_state") or "").strip() or None,
    }


def _paper_access_record_from_row(row: Any) -> dict[str, Any]:
    def _value(column: str) -> Any:
        getter = getattr(row, "get", None)
        if callable(getter):
            return getter(column)
        try:
            return row[column]
        except Exception:
            return None

    return {
        "doi": str(_value("doi") or "").strip() or None,
        "link": str(_value("link") or "").strip() or None,
        "publisher_url": str(_value("publisher_url") or "").strip() or None,
        "pdf_link": str(_value("pdf_link") or "").strip() or None,
        "feedback_json": _value("feedback_json"),
    }


def _recent_paper_preview_record_from_row(row: Any) -> dict[str, Any]:
    def _value(column: str) -> Any:
        getter = getattr(row, "get", None)
        if callable(getter):
            return getter(column)
        try:
            return row[column]
        except Exception:
            return None

    preview_record = {
        "paper_id": str(_value("paper_id") or "").strip(),
        "title": str(_value("title") or "").strip(),
        "status": str(_value("status") or "").strip() or None,
        "updated_at": str(_value("updated_at") or "").strip() or None,
        "pdf_path": str(_value("pdf_path") or "").strip() or None,
    }
    preview_record["is_fixture"] = is_test_fixture_paper_record(preview_record)
    return preview_record


def _paper_summary_response_record_from_row(row: Any) -> dict[str, Any]:
    def _value(column: str) -> Any:
        getter = getattr(row, "get", None)
        if callable(getter):
            return getter(column)
        try:
            return row[column]
        except Exception:
            return None

    return {
        "paper_id": _value("paper_id"),
        "title": _value("title"),
        "authors": _value("authors"),
        "year": _value("year"),
        "doi": _value("doi"),
        "link": _value("link"),
        "publisher_url": _value("publisher_url"),
        "pdf_link": _value("pdf_link"),
        "pdf_path": _value("pdf_path"),
        "pdf_status": _value("pdf_status"),
        "status": _value("status"),
        "issues": _value("issues"),
        "issues_label": _value("issues_label"),
        "issues_state": _value("issues_state"),
        "latest_job_id": _value("latest_job_id"),
        "updated_at": _value("updated_at"),
        "is_escalated": _value("is_escalated"),
        "escalation_reason": _value("escalation_reason"),
        "escalation_final_route": _value("escalation_final_route"),
        "escalation_in_biomedical_scope": _value("escalation_in_biomedical_scope"),
        "escalation_reason_codes": _value("escalation_reason_codes"),
        "feedback_json": _value("feedback_json"),
        "abstract": _value("abstract"),
    }


def _finalize_visible_paper_candidate_window(
    *,
    non_fixture_heap: list[tuple[float, int, dict[str, Any]]],
    fixture_heap: list[tuple[float, int, dict[str, Any]]],
    any_non_fixture: bool,
    any_fixture: bool,
    include_test_fixtures: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    if include_test_fixtures:
        candidate_entries = [*non_fixture_heap, *fixture_heap]
    elif non_fixture_heap:
        candidate_entries = non_fixture_heap
    else:
        candidate_entries = fixture_heap

    visible_candidates = [
        entry[2]
        for entry in sorted(
            candidate_entries,
            key=lambda entry: (entry[0], entry[1]),
            reverse=True,
        )
    ]
    visible_candidates_are_only_fixtures = (
        not include_test_fixtures
        and any_fixture
        and not any_non_fixture
    )
    return visible_candidates[offset : offset + limit], visible_candidates_are_only_fixtures

def _select_visible_paper_candidates_page(
    *,
    limit: int,
    offset: int,
    raw_limit: int = 5000,
) -> _VisiblePaperCandidatePage:
    max_scan_limit = max(1, min(raw_limit, 5000))
    paper_table_columns = _load_papers_table_columns()
    try:
        vault_path = paper_notes._resolve_vault_path()
        note_items = _load_deduped_note_items_without_ops(vault_path)
        if not note_items:
            vault_path = None
            note_items = None
    except Exception:
        vault_path = None
        note_items = None
    has_note_context = note_items is not None and vault_path is not None
    scan_limit = (
        _initial_listing_scan_limit(limit=limit, offset=offset, max_scan_limit=max_scan_limit)
        if has_note_context
        else _initial_listing_scan_limit_without_note_context(
            limit=limit,
            offset=offset,
            max_scan_limit=max_scan_limit,
        )
    )
    papers = _load_paper_rows_for_listing(
        raw_limit=scan_limit,
        raw_offset=0,
        lightweight=True,
        table_columns=paper_table_columns,
    )

    target_count = max(0, offset + limit)
    include_test_fixtures = include_test_fixtures_enabled()
    sorted_note_items_for_listing: list[PaperNoteIndexItem] | None = None
    paper_identity_cache: dict[str, tuple[set[str], set[str]]] = {}
    db_candidate_cache: dict[str, tuple[dict[str, Any], str | None, bool]] = {}
    while True:
        visible_raw_ids: set[str] = set()
        visible_normalized_ids: set[str] = set()
        provisional_fixture_db_raw_ids: set[str] = set()
        provisional_fixture_db_normalized_ids: set[str] = set()
        provisional_fixture_note_raw_ids: set[str] = set()
        provisional_fixture_note_normalized_ids: set[str] = set()
        db_paper_ids_by_exact_variant: dict[str, str] = {}
        db_paper_ids_by_normalized_variant: dict[str, str] = {}
        note_slug_by_db_paper_id: dict[str, str] = {}
        note_slug_source_is_fixture_by_db_paper_id: dict[str, bool] = {}
        non_fixture_heap: list[tuple[float, int, dict[str, Any]]] = []
        fixture_heap: list[tuple[float, int, dict[str, Any]]] = []
        any_non_fixture = False
        any_fixture = False
        sequence = 0

        for row in papers:
            paper_id = str(row["paper_id"] or "").strip()
            cached_db_candidate = db_candidate_cache.get(paper_id)
            if cached_db_candidate is None:
                fixture_record = _paper_listing_fixture_record_from_row(row)
                cached_db_candidate = (
                    fixture_record,
                    row["updated_at"],
                    is_test_fixture_paper_record(fixture_record),
                )
                db_candidate_cache[paper_id] = cached_db_candidate
            fixture_record, sort_updated_at, is_fixture = cached_db_candidate
            hidden_fixture_db_candidate = is_fixture and any_non_fixture and not include_test_fixtures
            candidate = {
                "kind": "db",
                "sort_updated_at": sort_updated_at,
                "fixture_record": fixture_record,
                "row": row,
            }
            if is_fixture:
                any_fixture = True
                if not hidden_fixture_db_candidate:
                    _push_visible_paper_candidate_window(
                        fixture_heap,
                        candidate,
                        sequence=sequence,
                        target_count=target_count,
                    )
            else:
                any_non_fixture = True
                _push_visible_paper_candidate_window(
                    non_fixture_heap,
                    candidate,
                    sequence=sequence,
                    target_count=target_count,
                )
            sequence += 1
            if has_note_context:
                if hidden_fixture_db_candidate:
                    continue
                cached_identity_sets = paper_identity_cache.get(paper_id)
                if cached_identity_sets is None:
                    cached_identity_sets = _paper_id_identity_sets(paper_id)
                    paper_identity_cache[paper_id] = cached_identity_sets
                raw_variants, normalized_variants = cached_identity_sets
                if include_test_fixtures or not is_fixture:
                    visible_raw_ids.update(raw_variants)
                    visible_normalized_ids.update(normalized_variants)
                else:
                    provisional_fixture_db_raw_ids.update(raw_variants)
                    provisional_fixture_db_normalized_ids.update(normalized_variants)
                for candidate_id in raw_variants:
                    db_paper_ids_by_exact_variant.setdefault(candidate_id, paper_id)
                for candidate_id in normalized_variants:
                    db_paper_ids_by_normalized_variant.setdefault(candidate_id, paper_id)
            elif target_count > 0:
                if include_test_fixtures:
                    if len(non_fixture_heap) + len(fixture_heap) >= target_count:
                        break
                elif any_non_fixture and len(non_fixture_heap) >= target_count:
                    break

        if has_note_context:
            note_iteration = note_items
            if target_count > 0:
                if sorted_note_items_for_listing is None:
                    sorted_note_items_for_listing = _note_items_sorted_for_listing(note_items)
                note_iteration = sorted_note_items_for_listing
            for note_item in note_iteration:
                if target_count > 0 and (
                    (any_non_fixture and len(non_fixture_heap) >= target_count)
                    or (
                        not any_non_fixture
                        and include_test_fixtures
                        and len(fixture_heap) >= target_count
                    )
                ):
                    current_rank = (
                        _parse_iso_timestamp_sort_key(getattr(note_item, "updated_at", None)),
                        -sequence,
                    )
                    cutoff_heap = non_fixture_heap if any_non_fixture else fixture_heap
                    if current_rank <= (cutoff_heap[0][0], cutoff_heap[0][1]):
                        break
                note_is_fixture_preview = False
                if (
                    not include_test_fixtures
                    and (
                        any_non_fixture
                        or provisional_fixture_db_raw_ids
                        or provisional_fixture_db_normalized_ids
                    )
                ):
                    note_is_fixture_preview = _paper_note_fixture_preview_is_fixture(note_item)
                note_slug = str(getattr(note_item, "slug", "") or "").strip()
                if note_is_fixture_preview and any_non_fixture and not include_test_fixtures and not note_slug:
                    continue
                if (
                    note_is_fixture_preview
                    and any_non_fixture
                    and not include_test_fixtures
                    and not db_paper_ids_by_exact_variant
                    and not db_paper_ids_by_normalized_variant
                ):
                    continue
                raw_variants, normalized_variants = _paper_note_identity_sets(note_item)
                matched_db_paper_id = _match_db_paper_id_for_note_variants(
                    raw_variants,
                    normalized_variants,
                    db_paper_ids_by_exact_variant=db_paper_ids_by_exact_variant,
                    db_paper_ids_by_normalized_variant=db_paper_ids_by_normalized_variant,
                )
                if matched_db_paper_id and note_slug:
                    note_slug_source_is_fixture = _paper_note_fixture_preview_is_fixture(note_item)
                    existing_note_slug = note_slug_by_db_paper_id.get(matched_db_paper_id)
                    if existing_note_slug is None:
                        note_slug_by_db_paper_id[matched_db_paper_id] = note_slug
                        note_slug_source_is_fixture_by_db_paper_id[matched_db_paper_id] = (
                            note_slug_source_is_fixture
                        )
                    elif (
                        not include_test_fixtures
                        and note_slug_source_is_fixture_by_db_paper_id.get(matched_db_paper_id, False)
                        and not note_slug_source_is_fixture
                    ):
                        note_slug_by_db_paper_id[matched_db_paper_id] = note_slug
                        note_slug_source_is_fixture_by_db_paper_id[matched_db_paper_id] = False
                if raw_variants & visible_raw_ids or normalized_variants & visible_normalized_ids:
                    continue
                if note_is_fixture_preview and (
                    raw_variants & provisional_fixture_db_raw_ids
                    or normalized_variants & provisional_fixture_db_normalized_ids
                    or raw_variants & provisional_fixture_note_raw_ids
                    or normalized_variants & provisional_fixture_note_normalized_ids
                ):
                    continue
                if note_is_fixture_preview and any_non_fixture and not include_test_fixtures:
                    continue
                note_candidate_metadata = _paper_note_listing_candidate_metadata(note_item)
                if note_candidate_metadata is None:
                    continue
                note_paper_id, note_title, note_sort_updated_at, note_is_fixture = note_candidate_metadata
                candidate = {
                    "kind": "note",
                    "sort_updated_at": note_sort_updated_at,
                    "fixture_record": {
                        "paper_id": note_paper_id,
                        "title": note_title,
                    },
                    "note_item": note_item,
                    "paper_id": note_paper_id,
                }
                if note_is_fixture:
                    any_fixture = True
                    if any_non_fixture and not include_test_fixtures:
                        continue
                    _push_visible_paper_candidate_window(
                        fixture_heap,
                        candidate,
                        sequence=sequence,
                        target_count=target_count,
                    )
                else:
                    any_non_fixture = True
                    _push_visible_paper_candidate_window(
                        non_fixture_heap,
                        candidate,
                        sequence=sequence,
                        target_count=target_count,
                    )
                sequence += 1
                if note_is_fixture and not include_test_fixtures:
                    provisional_fixture_note_raw_ids.update(raw_variants)
                    provisional_fixture_note_normalized_ids.update(normalized_variants)
                else:
                    visible_raw_ids.update(raw_variants)
                    visible_normalized_ids.update(normalized_variants)

        selected_candidates, visible_candidates_are_only_fixtures = _finalize_visible_paper_candidate_window(
            non_fixture_heap=non_fixture_heap,
            fixture_heap=fixture_heap,
            any_non_fixture=any_non_fixture,
            any_fixture=any_fixture,
            include_test_fixtures=include_test_fixtures,
            offset=offset,
            limit=limit,
        )
        needs_expanded_scan = (
            scan_limit < max_scan_limit
            and len(papers) >= scan_limit
            and (
                len(selected_candidates) < limit
                or visible_candidates_are_only_fixtures
            )
        )
        if not needs_expanded_scan:
            break
        next_scan_limit = _next_listing_scan_limit(scan_limit, max_scan_limit=max_scan_limit)
        if next_scan_limit == scan_limit:
            break
        papers.extend(
            _load_paper_rows_for_listing(
                raw_limit=next_scan_limit - scan_limit,
                raw_offset=scan_limit,
                lightweight=True,
                table_columns=paper_table_columns,
            )
        )
        scan_limit = next_scan_limit

    return _VisiblePaperCandidatePage(
        selected_candidates=selected_candidates,
        vault_path=vault_path,
        note_items=note_items,
        note_slug_by_db_paper_id=note_slug_by_db_paper_id,
        paper_table_columns=paper_table_columns,
    )


def _list_visible_paper_items_page(
    *,
    limit: int,
    offset: int,
    raw_limit: int = 5000,
) -> list[dict[str, Any]]:
    page = _select_visible_paper_candidates_page(limit=limit, offset=offset, raw_limit=raw_limit)
    selected_candidates = page.selected_candidates
    vault_path = page.vault_path
    note_items = page.note_items
    note_slug_by_db_paper_id = page.note_slug_by_db_paper_id
    selected_db_context = _prepare_selected_db_paper_page_context(
        selected_candidates=selected_candidates,
        note_items=note_items,
        note_slug_by_db_paper_id=note_slug_by_db_paper_id,
        row_loader=lambda paper_ids: _fetch_listing_response_rows_by_ids(
            paper_ids,
            table_columns=page.paper_table_columns,
        ),
    )

    artifacts_path = artifacts_root()
    note_window_artifact_cache: ArtifactSnapshotCache = {}
    selected_note_candidate_groups = _selected_note_candidate_id_groups(selected_candidates)
    if len(selected_note_candidate_groups) > 1:
        _preload_artifact_snapshots_for_candidate_id_groups(
            artifacts_path,
            selected_note_candidate_groups,
            note_window_artifact_cache,
        )
    paper_ids_needing_latest_run_lookup = (
        _selected_db_paper_ids_needing_latest_run_lookup(
            selected_db_context.selected_db_paper_ids,
            selected_db_context.artifact_cache,
            ops_candidate_ids_by_paper_id=selected_db_context.ops_candidate_ids_by_paper_id,
        )
        if len(selected_db_context.selected_db_paper_ids) > 1
        else []
    )
    latest_run_id_lookup = (
        _preload_latest_run_ids_for_papers(
            paper_ids_needing_latest_run_lookup,
            ops_candidate_ids_by_paper_id=selected_db_context.ops_candidate_ids_by_paper_id,
            artifact_cache=selected_db_context.artifact_cache,
        )
        if paper_ids_needing_latest_run_lookup
        else {}
    )

    window_items: list[dict[str, Any]] = []
    for candidate in selected_candidates:
        if candidate.get("kind") == "note":
            note_backed = _build_note_backed_paper_item_from_index_item(
                vault_path,
                candidate["note_item"],
                paper_id=candidate["paper_id"],
                artifact_cache=note_window_artifact_cache,
                artifacts_path=artifacts_path,
            )
            if note_backed is None:
                continue
            window_items.append(note_backed[0])
            continue
        paper_id = str(candidate["row"]["paper_id"] or "").strip()
        full_row = selected_db_context.selected_db_rows_by_id.get(paper_id, candidate["row"])
        window_items.append(
            _build_db_backed_paper_item_from_row(
                full_row,
                artifact_cache=selected_db_context.artifact_cache,
                vault_path=vault_path,
                note_items=note_items,
                note_item_lookup=selected_db_context.note_item_lookup,
                artifacts_path=artifacts_path,
                latest_run_id_lookup=latest_run_id_lookup,
                note_slug=note_slug_by_db_paper_id.get(paper_id),
                ops_candidate_ids=selected_db_context.ops_candidate_ids_by_paper_id.get(paper_id),
            )
        )
    return window_items


def _list_visible_paper_rail_items_page(
    *,
    limit: int,
    offset: int,
    raw_limit: int = 5000,
) -> list[dict[str, Any]]:
    page = _select_visible_paper_candidates_page(limit=limit, offset=offset, raw_limit=raw_limit)
    selected_candidates = page.selected_candidates
    vault_path = page.vault_path
    note_items = page.note_items
    note_slug_by_db_paper_id = page.note_slug_by_db_paper_id
    selected_db_context = _prepare_selected_db_paper_page_context(
        selected_candidates=selected_candidates,
        note_items=note_items,
        note_slug_by_db_paper_id=note_slug_by_db_paper_id,
        row_loader=lambda paper_ids: _fetch_listing_rail_rows_by_ids(
            paper_ids,
            table_columns=page.paper_table_columns,
        ),
    )

    artifacts_path = artifacts_root()
    note_window_artifact_cache: ArtifactSnapshotCache = {}
    selected_note_candidate_groups = _selected_note_candidate_id_groups(selected_candidates)
    if len(selected_note_candidate_groups) > 1:
        _preload_artifact_snapshots_for_candidate_id_groups(
            artifacts_path,
            selected_note_candidate_groups,
            note_window_artifact_cache,
        )
    window_items: list[dict[str, Any]] = []
    for candidate in selected_candidates:
        if candidate.get("kind") == "note":
            note_backed = _build_note_backed_paper_rail_item_from_index_item(
                vault_path,
                candidate["note_item"],
                paper_id=candidate["paper_id"],
                artifact_cache=note_window_artifact_cache,
                artifacts_path=artifacts_path,
            )
            if note_backed is None:
                continue
            window_items.append(note_backed)
            continue
        paper_id = str(candidate["row"]["paper_id"] or "").strip()
        full_row = selected_db_context.selected_db_rows_by_id.get(paper_id, candidate["row"])
        window_items.append(
            _build_db_backed_paper_rail_item_from_row(
                full_row,
                artifact_cache=selected_db_context.artifact_cache,
                vault_path=vault_path,
                note_items=note_items,
                note_item_lookup=selected_db_context.note_item_lookup,
                artifacts_path=artifacts_path,
                note_slug=note_slug_by_db_paper_id.get(paper_id),
                ops_candidate_ids=selected_db_context.ops_candidate_ids_by_paper_id.get(paper_id),
            )
        )
    return window_items


def _preload_latest_run_ids_for_papers(
    paper_ids: list[str],
    *,
    ops_candidate_ids_by_paper_id: dict[str, list[str]] | None = None,
    artifact_cache: ArtifactSnapshotCache | None = None,
) -> dict[str, str]:
    unique_paper_ids: list[str] = []
    seen_paper_ids: set[str] = set()
    owners_by_candidate_id: dict[str, list[str]] = {}
    candidate_ids: list[str] = []
    seen_candidate_ids: set[str] = set()
    for candidate in paper_ids:
        paper_id = str(candidate or "").strip()
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        unique_paper_ids.append(paper_id)
        ops_candidate_ids = (
            ops_candidate_ids_by_paper_id.get(paper_id)
            if ops_candidate_ids_by_paper_id is not None
            else None
        ) or _ops_summary_candidate_ids(paper_id)
        for normalized_candidate_id in _normalized_candidate_id_list(ops_candidate_ids):
            if artifact_cache is not None and normalized_candidate_id in artifact_cache:
                continue
            owners = owners_by_candidate_id.setdefault(normalized_candidate_id, [])
            if paper_id not in owners:
                owners.append(paper_id)
            if normalized_candidate_id not in seen_candidate_ids:
                seen_candidate_ids.add(normalized_candidate_id)
                candidate_ids.append(normalized_candidate_id)

    if not unique_paper_ids or not candidate_ids:
        return {}

    conn = get_db_connection()
    resolved_run_ids: dict[str, str] = {}
    try:
        for start in range(0, len(candidate_ids), 400):
            chunk = candidate_ids[start : start + 400]
            placeholders = ", ".join("?" for _ in chunk)
            try:
                rows = conn.execute(
                    f"""
                    SELECT paper_id, run_id, artifact_dir
                    FROM jobs
                    WHERE run_id IS NOT NULL
                      AND paper_id IN ({placeholders})
                    ORDER BY COALESCE(finished_at, started_at, created_at) DESC
                    """,
                    tuple(chunk),
                ).fetchall()
            except sqlite3.OperationalError:
                return {}

            for row in rows:
                paper_id = str(row["paper_id"] or "").strip()
                run_id = str(row["run_id"] or "").strip()
                if not paper_id or not run_id:
                    continue
                artifact_dir = str(row["artifact_dir"] or "").strip()
                is_valid = False
                if artifact_dir:
                    if Path(artifact_dir).exists():
                        is_valid = True
                elif _artifact_run_dir(paper_id, run_id).exists():
                    is_valid = True
                if not is_valid:
                    continue

                for owner_paper_id in owners_by_candidate_id.get(paper_id, []):
                    if owner_paper_id not in resolved_run_ids:
                        resolved_run_ids[owner_paper_id] = run_id
                if len(resolved_run_ids) == len(unique_paper_ids):
                    break
            if len(resolved_run_ids) == len(unique_paper_ids):
                break
        return resolved_run_ids
    finally:
        conn.close()


def _preload_artifact_snapshots_for_papers(
    artifacts_path: Path,
    paper_ids: list[str],
    cache: ArtifactSnapshotCache,
    *,
    ops_candidate_ids_by_paper_id: dict[str, list[str]] | None = None,
) -> None:
    _preload_artifact_snapshots_for_candidate_id_groups(
        artifacts_path,
        (
            (
                ops_candidate_ids_by_paper_id.get(paper_id)
                if ops_candidate_ids_by_paper_id is not None
                else None
            ) or _ops_summary_candidate_ids(paper_id)
            for paper_id in paper_ids
        ),
        cache,
    )


def _selected_note_candidate_id_groups(
    selected_candidates: list[dict[str, Any]],
) -> list[tuple[str, ...]]:
    candidate_id_groups: list[tuple[str, ...]] = []
    seen_group_keys: set[tuple[str, ...]] = set()
    deferred_first_note_item: PaperNoteIndexItem | None = None
    for candidate in selected_candidates:
        if candidate.get("kind") != "note":
            continue
        note_item = candidate.get("note_item")
        if note_item is None:
            continue
        if deferred_first_note_item is None and not candidate_id_groups:
            deferred_first_note_item = note_item
            continue
        if deferred_first_note_item is not None:
            first_group_key = _paper_note_ops_candidate_group_key(deferred_first_note_item)
            if first_group_key and first_group_key not in seen_group_keys:
                seen_group_keys.add(first_group_key)
                candidate_id_groups.append(first_group_key)
            deferred_first_note_item = None
        group_key = _paper_note_ops_candidate_group_key(note_item)
        if not group_key or group_key in seen_group_keys:
            continue
        seen_group_keys.add(group_key)
        candidate_id_groups.append(group_key)
    return candidate_id_groups


def _preload_artifact_snapshots_for_candidate_id_groups(
    artifacts_path: Path,
    candidate_id_groups: Any,
    cache: ArtifactSnapshotCache,
) -> None:
    candidate_ids: list[str] = []
    seen_candidate_ids: set[str] = set()
    for group in candidate_id_groups:
        for candidate_id in _normalized_candidate_id_list(group):
            if candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate_id)
            if candidate_id in cache:
                continue
            candidate_ids.append(candidate_id)

    if not candidate_ids:
        return

    conn = get_db_connection()
    try:
        for start in range(0, len(candidate_ids), 400):
            chunk = candidate_ids[start : start + 400]
            placeholders = ", ".join("?" for _ in chunk)
            try:
                rows = conn.execute(
                    f"""
                    SELECT paper_id, run_id, artifact_dir
                    FROM jobs
                    WHERE run_id IS NOT NULL
                      AND paper_id IN ({placeholders})
                    ORDER BY COALESCE(finished_at, started_at, created_at) DESC
                    """,
                    tuple(chunk),
                ).fetchall()
            except sqlite3.OperationalError:
                return

            for row in rows:
                paper_id = str(row["paper_id"] or "").strip()
                run_id = str(row["run_id"] or "").strip()
                if not paper_id or not run_id or paper_id in cache:
                    continue

                artifact_dir = str(row["artifact_dir"] or "").strip()
                run_dir: Path | None = None
                if artifact_dir:
                    candidate_path = Path(artifact_dir)
                    if candidate_path.exists() and candidate_path.is_dir():
                        run_dir = candidate_path
                if run_dir is None:
                    candidate_path = _artifact_run_dir(paper_id, run_id)
                    if candidate_path.exists() and candidate_path.is_dir():
                        run_dir = candidate_path
                if run_dir is None:
                    continue

                snapshot: ArtifactOperationalSnapshot | None = artifact_snapshot_from_run_dir(paper_id, run_dir)
                if snapshot is not None:
                    cache[paper_id] = snapshot

        # Keep file-system fallback alive for fs-only artifact dirs, but cache
        # clear misses so later ops-summary evaluation does not re-scan them.
        for candidate_id in candidate_ids:
            if candidate_id in cache:
                continue
            paper_dir = preferred_artifact_paper_dir(candidate_id, root=artifacts_path)
            if not paper_dir.exists() or not paper_dir.is_dir():
                cache[candidate_id] = None
    finally:
        conn.close()


def _load_recent_db_rows(
    *,
    raw_limit: int,
    raw_offset: int = 0,
    table_columns: set[str] | None = None,
) -> list[Any]:
    conn = get_db_connection()
    try:
        try:
            if table_columns is None:
                table_columns = {
                    str(row[1]).strip()
                    for row in conn.execute("PRAGMA table_info(papers)").fetchall()
                    if len(row) > 1 and str(row[1]).strip()
                }
            selected_columns = [
                column
                for column in ("paper_id", "title", "status", "pdf_path")
                if column in table_columns
            ]
            if "updated_at" in table_columns:
                selected_columns.append("updated_at")
                order_by = "updated_at DESC"
            elif "created_at" in table_columns:
                selected_columns.append("created_at AS updated_at")
                order_by = "created_at DESC"
            else:
                selected_columns.append("NULL AS updated_at")
                order_by = "paper_id ASC"
            select_clause = ", ".join(selected_columns) if selected_columns else "paper_id"
            return conn.execute(
                f"SELECT {select_clause} FROM papers ORDER BY {order_by} LIMIT ? OFFSET ?",
                (raw_limit, raw_offset),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()


def _list_recent_db_paper_items(*, limit: int) -> list[dict[str, Any]]:
    include_test_fixtures = include_test_fixtures_enabled()
    scan_limit = max(1, min(limit, 200))
    scan_offset = 0
    paper_table_columns = _load_papers_table_columns()
    rows: list[dict[str, Any]] = []
    visible_non_fixture_rows: list[dict[str, Any]] = []
    has_any_non_fixture_row = False
    recent: list[dict[str, Any]] = []
    while True:
        chunk_rows = _load_recent_db_rows(
            raw_limit=scan_limit,
            raw_offset=scan_offset,
            table_columns=paper_table_columns,
        )
        chunk_preview_rows = [_recent_paper_preview_record_from_row(row) for row in chunk_rows]
        rows.extend(chunk_preview_rows)
        if include_test_fixtures:
            items = rows
            visible_rows_are_only_fixtures = False
        else:
            for preview_row in chunk_preview_rows:
                if bool(preview_row.get("is_fixture")):
                    continue
                has_any_non_fixture_row = True
                visible_non_fixture_rows.append(preview_row)
            items = visible_non_fixture_rows if has_any_non_fixture_row else rows
            visible_rows_are_only_fixtures = bool(items) and not has_any_non_fixture_row

        recent = []
        seen_paper_ids: set[str] = set()
        for row in items:
            paper_id = str(row.get("paper_id") or "").strip()
            title = str(row.get("title") or "").strip()
            if not paper_id or not title or paper_id in seen_paper_ids:
                continue
            seen_paper_ids.add(paper_id)
            recent.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "status": str(row.get("status") or "").strip() or None,
                    "updated_at": str(row.get("updated_at") or "").strip() or None,
                }
            )
            if len(recent) >= limit:
                break

        if len(chunk_rows) < scan_limit:
            break
        if len(recent) >= limit and not visible_rows_are_only_fixtures:
            break
        scan_offset += scan_limit
        scan_limit = min(200, max(scan_limit * 2, 200))

    if len(recent) >= limit:
        return recent[:limit]

    try:
        vault_path = paper_notes._resolve_vault_path()
        note_items = _note_items_sorted_for_listing(_load_deduped_note_items_without_ops(vault_path))
    except Exception:
        return recent
    if not note_items:
        return recent

    seen_raw_ids: set[str] = set()
    seen_normalized_ids: set[str] = set()
    for candidate in recent:
        raw_variants, normalized_variants = _paper_id_identity_sets(str(candidate.get("paper_id") or "").strip())
        seen_raw_ids.update(raw_variants)
        seen_normalized_ids.update(normalized_variants)

    for note_item in note_items:
        if recent and not include_test_fixtures and _paper_note_fixture_preview_is_fixture(note_item):
            continue
        raw_variants, normalized_variants = _paper_note_identity_sets(note_item)
        if raw_variants & seen_raw_ids or normalized_variants & seen_normalized_ids:
            continue
        note_candidate_metadata = _paper_note_listing_candidate_metadata(note_item)
        if note_candidate_metadata is None:
            continue
        paper_id, title, updated_at, note_is_fixture = note_candidate_metadata
        if not paper_id or not title or paper_id in seen_paper_ids:
            continue
        candidate = {
            "paper_id": paper_id,
            "title": title,
            "status": str(getattr(note_item, "status", None) or "").strip() or None,
            "updated_at": updated_at,
        }
        if note_is_fixture and not include_test_fixtures:
            continue
        seen_paper_ids.add(paper_id)
        seen_raw_ids.update(raw_variants)
        seen_normalized_ids.update(normalized_variants)
        recent.append(candidate)
        if len(recent) >= limit:
            break
    return recent


def _load_home_workspace_summary_context(*, raw_limit: int = 5000) -> _HomeWorkspaceSummaryContext:
    papers = _load_paper_rows_for_workspace_summary(raw_limit=raw_limit)
    note_items: list[PaperNoteIndexItem] | None = None
    note_context_limited = False
    try:
        vault_path = paper_notes._resolve_vault_path()
        note_items = _load_deduped_note_items_without_ops(vault_path)
        if not note_items:
            note_items = None
    except Exception:
        note_context_limited = True

    saved_notes = 0
    structured_notes = 0
    latest_note_updated_at: str | None = None
    if note_items is not None:
        saved_notes = len(note_items)
        structured_notes = sum(1 for item in note_items if item.structured_state_present)
        latest_note_updated_at = max(
            (item.updated_at for item in note_items if item.updated_at),
            key=_parse_iso_timestamp_sort_key,
            default=None,
        )

    include_test_fixtures = include_test_fixtures_enabled()
    artifacts_path = artifacts_root()
    artifact_cache: ArtifactSnapshotCache = {}
    ops_summary_by_candidate_id_group: dict[tuple[str, ...], Any] = {}
    normalized_group_key_by_candidate_ids: dict[frozenset[str], tuple[str, ...]] = {}

    def _cached_ops_summary_for_candidate_group(cache_key: tuple[str, ...]) -> Any:
        if not cache_key:
            return None
        if cache_key not in ops_summary_by_candidate_id_group:
            cached_ops_summary = _ops_summary_from_artifact_cache_for_candidate_ids(
                list(cache_key),
                artifact_cache,
            )
            if cached_ops_summary is _UNCACHED_ARTIFACT_GROUP:
                cached_ops_summary = build_ops_summary_for_candidate_ids(
                    artifacts_path,
                    list(cache_key),
                    artifact_cache,
                )
            ops_summary_by_candidate_id_group[cache_key] = cached_ops_summary
        return ops_summary_by_candidate_id_group[cache_key]

    def _cached_db_ops_candidate_group_key(paper_id: str) -> tuple[str, ...]:
        normalized_paper_id = str(paper_id or "").strip()
        if not normalized_paper_id:
            return ()
        candidate_ids = tuple(_ops_summary_candidate_ids(normalized_paper_id))
        candidate_ids_cache_key = frozenset(_normalized_candidate_id_list(candidate_ids))
        if not candidate_ids_cache_key:
            return ()
        if candidate_ids_cache_key not in normalized_group_key_by_candidate_ids:
            normalized_group_key_by_candidate_ids[candidate_ids_cache_key] = tuple(
                sorted(candidate_ids_cache_key)
            )
        return normalized_group_key_by_candidate_ids[candidate_ids_cache_key]

    visible_raw_ids: set[str] = set()
    visible_normalized_ids: set[str] = set()
    provisional_fixture_db_raw_ids: set[str] = set()
    provisional_fixture_db_normalized_ids: set[str] = set()
    provisional_fixture_note_raw_ids: set[str] = set()
    provisional_fixture_note_normalized_ids: set[str] = set()
    db_rows_with_visibility: list[tuple[str, Any, bool]] = []
    note_only_candidates: list[dict[str, Any]] = []

    for row in papers:
        paper_id = str(row["paper_id"] or "").strip()
        db_rows_with_visibility.append(
            (
                paper_id,
                row,
                is_test_fixture_paper_record(_paper_listing_fixture_record_from_row(row)),
            )
        )

    if include_test_fixtures:
        visible_db_rows = db_rows_with_visibility
    else:
        non_fixture_db_rows = [
            candidate
            for candidate in db_rows_with_visibility
            if not candidate[2]
        ]
        visible_db_rows = non_fixture_db_rows or db_rows_with_visibility
    has_non_fixture_visible_db_row = any(not is_fixture for _, _, is_fixture in visible_db_rows)
    has_non_fixture_note_only_candidate = False
    if note_items is not None:
        for paper_id, _, is_fixture in visible_db_rows:
            raw_variants, normalized_variants = _paper_id_identity_sets(paper_id)
            if include_test_fixtures or not is_fixture:
                visible_raw_ids.update(raw_variants)
                visible_normalized_ids.update(normalized_variants)
            else:
                provisional_fixture_db_raw_ids.update(raw_variants)
                provisional_fixture_db_normalized_ids.update(normalized_variants)

    if note_items is not None:
        for note_item in note_items:
            note_is_fixture_preview = False
            if not include_test_fixtures and (
                has_non_fixture_visible_db_row
                or has_non_fixture_note_only_candidate
                or provisional_fixture_db_raw_ids
                or provisional_fixture_db_normalized_ids
            ):
                note_is_fixture_preview = _paper_note_fixture_preview_is_fixture(note_item)
            if (
                note_is_fixture_preview
                and not include_test_fixtures
                and (has_non_fixture_visible_db_row or has_non_fixture_note_only_candidate)
            ):
                continue
            raw_variants, normalized_variants = _paper_note_identity_sets(note_item)
            if raw_variants & visible_raw_ids or normalized_variants & visible_normalized_ids:
                continue
            if (
                note_is_fixture_preview
                and (
                    raw_variants & provisional_fixture_db_raw_ids
                    or normalized_variants & provisional_fixture_db_normalized_ids
                    or raw_variants & provisional_fixture_note_raw_ids
                    or normalized_variants & provisional_fixture_note_normalized_ids
                )
            ):
                continue
            note_candidate_metadata = _paper_note_listing_candidate_metadata(note_item)
            if note_candidate_metadata is None:
                continue
            _, _, _, note_is_fixture = note_candidate_metadata
            note_only_candidates.append(
                {
                    "note_item": note_item,
                    "is_fixture": note_is_fixture,
                }
            )
            if not note_is_fixture:
                has_non_fixture_note_only_candidate = True
                visible_raw_ids.update(raw_variants)
                visible_normalized_ids.update(normalized_variants)
            elif include_test_fixtures:
                visible_raw_ids.update(raw_variants)
                visible_normalized_ids.update(normalized_variants)
            else:
                provisional_fixture_note_raw_ids.update(raw_variants)
                provisional_fixture_note_normalized_ids.update(normalized_variants)

    combined_has_non_fixture_visible_item = (
        include_test_fixtures
        or has_non_fixture_visible_db_row
        or has_non_fixture_note_only_candidate
    )
    if not include_test_fixtures and combined_has_non_fixture_visible_item:
        visible_db_rows = [candidate for candidate in visible_db_rows if not candidate[2]]
        note_only_candidates = [
            candidate for candidate in note_only_candidates if not candidate["is_fixture"]
        ]

    for candidate in note_only_candidates:
        note_item = candidate["note_item"]
        note_status = str(getattr(note_item, "status", "") or "").strip().upper()
        note_is_completed = note_item.structured_state_present or note_status == "INDEXED"
        candidate["issues_state"] = "clear" if note_is_completed else "unavailable"
        candidate["ops_candidate_group_key"] = _paper_note_ops_candidate_group_key(note_item)

    visible_db_rows_with_groups = [
        (
            paper_id,
            row,
            is_fixture,
            _cached_db_ops_candidate_group_key(paper_id),
        )
        for paper_id, row, is_fixture in visible_db_rows
    ]

    unique_visible_db_candidate_group_keys = list(
        dict.fromkeys(
            group_key
            for _, _, _, group_key in visible_db_rows_with_groups
            if group_key
        )
    )
    unique_visible_note_only_candidate_group_keys = list(
        dict.fromkeys(
            candidate["ops_candidate_group_key"]
            for candidate in note_only_candidates
            if candidate["ops_candidate_group_key"]
        )
    )
    preloaded_candidate_group_keys = list(
        dict.fromkeys(
            [*unique_visible_db_candidate_group_keys, *unique_visible_note_only_candidate_group_keys]
        )
    )
    if len(preloaded_candidate_group_keys) > 1:
        _preload_artifact_snapshots_for_candidate_id_groups(
            artifacts_path,
            preloaded_candidate_group_keys,
            artifact_cache,
        )

    blocked = 0
    needs_review = 0
    for paper_id, row, _, ops_candidate_group_key in visible_db_rows_with_groups:
        ops_summary = _cached_ops_summary_for_candidate_group(ops_candidate_group_key)
        if getattr(ops_summary, "state", None) == "action_needed":
            blocked += 1
            continue
        issues_state = _derive_paper_issues_state(_workspace_summary_issues_record_from_row(row))
        if issues_state != "clear":
            needs_review += 1

    for candidate in note_only_candidates:
        note_item = candidate.pop("note_item", None)
        note_ops_summary = _cached_ops_summary_for_candidate_group(candidate["ops_candidate_group_key"])
        if note_ops_summary is None and note_item is not None:
            note_ops_summary = getattr(note_item, "ops_summary", None)
        if getattr(note_ops_summary, "state", None) == "action_needed":
            blocked += 1
            continue
        if candidate["issues_state"] != "clear":
            needs_review += 1

    return _HomeWorkspaceSummaryContext(
        blocked=blocked,
        needs_review=needs_review,
        note_context_limited=note_context_limited,
        saved_notes=saved_notes,
        structured_notes=structured_notes,
        latest_note_updated_at=latest_note_updated_at,
    )


def _build_home_workspace_summary() -> HomeWorkspaceSummaryResponse:
    context = _load_home_workspace_summary_context()
    saved_notes = context.saved_notes
    structured_notes = context.structured_notes
    latest_note_updated_at = context.latest_note_updated_at
    note_context_limited = context.note_context_limited

    return HomeWorkspaceSummaryResponse(
        saved_notes=saved_notes,
        structured_notes=structured_notes,
        needs_review=context.needs_review,
        blocked=context.blocked,
        latest_note_updated_at=latest_note_updated_at,
        note_context_limited=note_context_limited,
    )


def _load_deduped_note_items_without_ops(vault_path: Path) -> list[PaperNoteIndexItem]:
    note_index = paper_notes._build_index(vault_path)
    return paper_notes._dedupe_equivalent_note_items_with_ops(
        list(note_index.items),
        artifacts_path=None,
        artifact_cache=None,
    )


def _build_paper_access_summary(item: dict[str, Any], *, paper_id: str, pdf_exists: bool) -> PaperAccessSummary:
    open_access_url = str(item.get("pdf_link") or "").strip() or None
    institution_access_url = (
        extract_institutional_proxy_link(item.get("feedback_json"))
        or generate_institutional_proxy_url(paper=item)
    )
    local_pdf_url = f"/papers/{quote(paper_id, safe='')}/pdf" if pdf_exists and paper_id else None

    if pdf_exists:
        status_label = "user_imported_pdf"
    elif open_access_url:
        status_label = "open"
    elif institution_access_url:
        status_label = "institution_required"
    else:
        status_label = "unavailable"

    return PaperAccessSummary(
        status_label=status_label,
        open_access_url=open_access_url,
        institution_access_url=institution_access_url,
        local_pdf_url=local_pdf_url,
    )


def _resolve_note_backed_pdf_path(frontmatter: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    for key in ("pdf_path", "local_pdf_path"):
        raw_value = str(frontmatter.get(key) or "").strip()
        if raw_value:
            candidates.append(Path(raw_value).expanduser())

    pdf_url = str(frontmatter.get("pdf_url") or "").strip()
    if pdf_url.lower().startswith("file://"):
        local_path = unquote(urlparse(pdf_url).path or "")
        if local_path:
            candidates.append(Path(local_path).expanduser())
    elif pdf_url and not re.match(r"^[a-z][a-z0-9+.-]*://", pdf_url, flags=re.IGNORECASE) and not pdf_url.startswith("/papers/"):
        candidates.append(Path(pdf_url).expanduser())

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _build_note_backed_paper_access_summary(
    frontmatter: dict[str, Any],
    *,
    paper_id: str,
    pdf_path: Path | None,
) -> PaperAccessSummary:
    item: dict[str, Any] = {
        "doi": frontmatter.get("doi"),
        "link": frontmatter.get("url"),
        "pdf_link": None,
        "feedback_json": None,
    }
    pdf_url = str(frontmatter.get("pdf_url") or "").strip()
    if pdf_url.lower().startswith(("http://", "https://")):
        item["pdf_link"] = pdf_url
    return _build_paper_access_summary(item, paper_id=paper_id, pdf_exists=pdf_path is not None)


def _paper_id_identity_sets(paper_id: str) -> tuple[set[str], set[str]]:
    raw_variants = {value for value in paper_id_search_variants(paper_id) if value}
    normalized_variants = {
        normalized
        for value in raw_variants
        if (normalized := paper_notes._normalize_paper_note_id(value))
    }
    return raw_variants, normalized_variants


def _paper_route_candidate_ids(paper_id: str) -> list[str]:
    return paper_id_candidate_ids(paper_id)


def _lookup_paper_row_by_route_id(
    conn: sqlite3.Connection,
    paper_id: str,
    *,
    columns: str = "*",
) -> Any | None:
    candidate_ids = _paper_route_candidate_ids(paper_id)
    if not candidate_ids:
        return None

    placeholders = ", ".join("?" for _ in candidate_ids)
    rows = conn.execute(
        f"SELECT {columns} FROM papers WHERE paper_id IN ({placeholders})",
        tuple(candidate_ids),
    ).fetchall()
    if not rows:
        return None

    rows_by_paper_id = {
        str(row["paper_id"] or "").strip(): row
        for row in rows
        if str(row["paper_id"] or "").strip()
    }
    for candidate_id in candidate_ids:
        matched = rows_by_paper_id.get(candidate_id)
        if matched is not None:
            return matched
    return rows[0]


def _lookup_paper_row_by_note_identity(
    conn: sqlite3.Connection,
    paper_id: str,
    *,
    columns: str = "*",
) -> tuple[Any | None, Path | None, list[PaperNoteIndexItem] | None, PaperNoteIndexItem | None]:
    try:
        vault_path = paper_notes._resolve_vault_path()
        note_items = _load_deduped_note_items_without_ops(vault_path)
        if not note_items:
            return None, None, None, None
    except (FileNotFoundError, HTTPException):
        return None, None, None, None

    target = paper_notes._find_note_item_for_paper_id(note_items, paper_id)
    if target is None:
        return None, vault_path, note_items, None

    canonical_paper_id = str(getattr(target, "id", None) or "").strip()
    if not canonical_paper_id:
        return None, vault_path, note_items, target

    row = _lookup_paper_row_by_route_id(conn, canonical_paper_id, columns=columns)
    return row, vault_path, note_items, target


def _paper_note_identity_sets(target: PaperNoteIndexItem) -> tuple[set[str], set[str]]:
    if (cached := target.get_runtime_identity_sets()) is not None:
        return cached

    raw_variants: set[str] = set()
    for candidate in (target.id, target.slug):
        if not candidate:
            continue
        candidate_variants, _ = _paper_id_identity_sets(candidate)
        raw_variants.update(candidate_variants)
    normalized_variants = {
        normalized
        for value in raw_variants
        if (normalized := paper_notes._normalize_paper_note_id(value))
    }
    target.set_runtime_identity_sets(
        raw_variants=raw_variants,
        normalized_variants=normalized_variants,
    )
    cached = target.get_runtime_identity_sets()
    return cached if cached is not None else (frozenset(raw_variants), frozenset(normalized_variants))


def _paper_note_listing_candidate_metadata(target: PaperNoteIndexItem) -> tuple[str, str, str | None, bool] | None:
    if (cached := target.get_runtime_listing_candidate_metadata()) is not None:
        return cached

    paper_id = str(target.id or target.slug or "").strip()
    if not paper_id:
        return None
    title = str(target.title or target.slug or paper_id).strip() or paper_id
    fixture_record = {
        "paper_id": paper_id,
        "title": title,
    }
    target.set_runtime_listing_candidate_metadata(
        paper_id=paper_id,
        title=title,
        sort_updated_at=getattr(target, "updated_at", None),
        is_fixture=is_test_fixture_paper_record(fixture_record),
    )
    return target.get_runtime_listing_candidate_metadata()


def _paper_note_fixture_preview_is_fixture(target: PaperNoteIndexItem) -> bool:
    if (cached_listing_metadata := target.get_runtime_listing_candidate_metadata()) is not None:
        return cached_listing_metadata[3]
    if (cached_fixture_preview := target.get_runtime_fixture_preview_is_fixture()) is not None:
        return cached_fixture_preview

    preview_paper_id = str(getattr(target, "id", None) or getattr(target, "slug", None) or "").strip()
    preview_title = str(
        getattr(target, "title", None)
        or getattr(target, "slug", None)
        or preview_paper_id
    ).strip() or preview_paper_id
    is_fixture = is_test_fixture_paper_record({"paper_id": preview_paper_id, "title": preview_title})
    target.set_runtime_fixture_preview_is_fixture(is_fixture)
    return is_fixture


def _paper_note_ops_candidate_group_key(target: PaperNoteIndexItem) -> tuple[str, ...]:
    if (cached_group_key := target.get_runtime_ops_candidate_group_key()) is not None:
        return cached_group_key
    raw_variants, _ = _paper_note_identity_sets(target)
    group_key = _normalized_candidate_id_group(raw_variants)
    target.set_runtime_ops_candidate_group_key(group_key)
    return group_key


def _paper_note_artifact_candidate_ids(target: PaperNoteIndexItem) -> list[str]:
    if (cached_group_key := target.get_runtime_ops_candidate_group_key()) is not None:
        return list(cached_group_key)
    raw_variants, _ = _paper_note_identity_sets(target)
    group_key = _normalized_candidate_id_group(raw_variants)
    target.set_runtime_ops_candidate_group_key(group_key)
    return list(group_key)


def _note_items_sorted_for_listing(note_items: list[PaperNoteIndexItem]) -> list[PaperNoteIndexItem]:
    return [
        item
        for _, item in sorted(
            enumerate(note_items),
            key=lambda pair: (
                _parse_iso_timestamp_sort_key(getattr(pair[1], "updated_at", None)),
                -pair[0],
            ),
            reverse=True,
        )
    ]


def _load_note_backed_frontmatter_from_index_item(
    vault_path: Path,
    target: PaperNoteIndexItem,
) -> tuple[Path, dict[str, Any]] | None:
    note_path = vault_path / target.note_path
    if not note_path.exists():
        return None

    if target.has_runtime_source_metadata():
        frontmatter = target.build_runtime_source_frontmatter()
    else:
        content = paper_notes._safe_read_text(note_path)
        frontmatter, _ = paper_notes._parse_frontmatter(content)
        target.set_runtime_source_metadata(
            source_url=frontmatter.get("url"),
            pdf_url=frontmatter.get("pdf_url"),
            pdf_path=frontmatter.get("pdf_path"),
            local_pdf_path=frontmatter.get("local_pdf_path"),
        )
    return note_path, frontmatter


def _build_note_backed_paper_item_from_index_item(
    vault_path: Path,
    target: PaperNoteIndexItem,
    *,
    paper_id: str,
    artifact_cache: ArtifactSnapshotCache | None = None,
    artifacts_path: Path | None = None,
) -> tuple[dict[str, Any], Path | None] | None:
    loaded = _load_note_backed_frontmatter_from_index_item(vault_path, target)
    if loaded is None:
        return None
    _, frontmatter = loaded
    local_pdf_path = _resolve_note_backed_pdf_path(frontmatter)
    resolved_artifacts_path = artifacts_path or artifacts_root()
    resolved_artifact_cache = artifact_cache if artifact_cache is not None else {}
    candidate_ids = _paper_note_artifact_candidate_ids(target)
    ops_summary = _ops_summary_from_artifact_cache_for_candidate_ids(
        candidate_ids,
        resolved_artifact_cache,
    )
    if ops_summary is _UNCACHED_ARTIFACT_GROUP:
        ops_summary = build_ops_summary_for_candidate_ids(
            resolved_artifacts_path,
            candidate_ids,
            resolved_artifact_cache,
        )
    if ops_summary is None:
        ops_summary = target.ops_summary
    ops_summary_latest_run_id = getattr(ops_summary, "latest_run_id", None) if ops_summary is not None else None
    artifact_latest_run_id = (
        None
        if ops_summary_latest_run_id
        else _latest_run_id_from_artifact_cache_for_candidate_ids(
            candidate_ids,
            resolved_artifact_cache,
        )
    )
    latest_run_id = (
        ops_summary_latest_run_id
        or artifact_latest_run_id
        or (
            None
            if _artifact_cache_covers_candidate_ids(candidate_ids, resolved_artifact_cache)
            else (
                None
                if _artifact_cache_covers_candidate_ids(
                    latest_run_candidate_ids := _ops_summary_candidate_ids(paper_id),
                    resolved_artifact_cache,
                )
                else _latest_run_id_for_candidate_ids(latest_run_candidate_ids)
            )
        )
        or None
    )
    note_status = str(getattr(target, "status", "") or "").strip().upper()
    status = "completed" if target.structured_state_present or note_status == "INDEXED" else "not_started"
    item = {
        "paper_id": paper_id,
        "note_slug": target.slug,
        "title": target.title or target.slug or paper_id,
        "authors": None,
        "year": None,
        "pdf_exists": local_pdf_path is not None,
        "pdf_path": _public_path(str(local_pdf_path)) if local_pdf_path is not None else None,
        "pdf_status": None,
        "status": status,
        "issues": 0,
        "issues_label": "No critical issues",
        "issues_state": "clear" if status == "completed" else "unavailable",
        "latest_job_id": None,
        "latest_run_id": latest_run_id,
        "updated_at": getattr(target, "updated_at", None),
        "ops_summary": ops_summary,
        "access_summary": _build_note_backed_paper_access_summary(
            frontmatter,
            paper_id=paper_id,
            pdf_path=local_pdf_path,
        ),
        "abstract": None,
    }
    return item, local_pdf_path


def _build_note_backed_paper_rail_item_from_index_item(
    vault_path: Path,
    target: PaperNoteIndexItem,
    *,
    paper_id: str,
    artifact_cache: ArtifactSnapshotCache | None = None,
    artifacts_path: Path | None = None,
) -> dict[str, Any] | None:
    loaded = _load_note_backed_frontmatter_from_index_item(vault_path, target)
    if loaded is None:
        return None
    _, frontmatter = loaded
    local_pdf_path = _resolve_note_backed_pdf_path(frontmatter)
    resolved_artifacts_path = artifacts_path or artifacts_root()
    resolved_artifact_cache = artifact_cache if artifact_cache is not None else {}
    candidate_ids = _paper_note_artifact_candidate_ids(target)
    ops_summary = _ops_summary_from_artifact_cache_for_candidate_ids(
        candidate_ids,
        resolved_artifact_cache,
    )
    if ops_summary is _UNCACHED_ARTIFACT_GROUP:
        ops_summary = build_ops_summary_for_candidate_ids(
            resolved_artifacts_path,
            candidate_ids,
            resolved_artifact_cache,
        )
    if ops_summary is None:
        ops_summary = target.ops_summary
    note_status = str(getattr(target, "status", "") or "").strip().upper()
    status = "completed" if target.structured_state_present or note_status == "INDEXED" else "not_started"
    return {
        "paper_id": paper_id,
        "note_slug": target.slug,
        "title": target.title or target.slug or paper_id,
        "authors": None,
        "status": status,
        "issues": 0,
        "issues_label": "No critical issues",
        "issues_state": "clear" if status == "completed" else "unavailable",
        "updated_at": getattr(target, "updated_at", None),
        "ops_summary": ops_summary,
        "access_summary": _build_note_backed_paper_access_summary(
            frontmatter,
            paper_id=paper_id,
            pdf_path=local_pdf_path,
        ),
    }


def _resolve_note_backed_pdf_path_from_index_item(
    vault_path: Path,
    target: PaperNoteIndexItem,
) -> Path | None:
    loaded = _load_note_backed_frontmatter_from_index_item(vault_path, target)
    if loaded is None:
        return None
    _, frontmatter = loaded
    return _resolve_note_backed_pdf_path(frontmatter)


def _resolve_note_backed_pdf_path_for_paper_id(
    vault_path: Path,
    note_items: list[PaperNoteIndexItem],
    paper_id: str,
    *,
    note_item_lookup: _IndexedNoteItemLookup | None = None,
) -> Path | None:
    target = (
        _resolve_note_item_for_paper_id_from_lookup(note_item_lookup, paper_id)
        if note_item_lookup is not None
        else paper_notes._find_note_item_for_paper_id(note_items, paper_id)
    )
    if not target:
        return None
    return _resolve_note_backed_pdf_path_from_index_item(vault_path, target)


def _build_note_backed_paper_item(paper_id: str) -> tuple[dict[str, Any], Path | None] | None:
    try:
        vault_path = paper_notes._resolve_vault_path()
        note_items = _load_deduped_note_items_without_ops(vault_path)
        if not note_items:
            return None
        return _resolve_note_backed_paper_item(
            vault_path,
            note_items,
            paper_id,
        )
    except (FileNotFoundError, HTTPException):
        return None


def _resolve_note_backed_paper_item(
    vault_path: Path,
    note_items: list[PaperNoteIndexItem],
    paper_id: str,
    *,
    note_item_lookup: _IndexedNoteItemLookup | None = None,
) -> tuple[dict[str, Any], Path | None] | None:
    target = (
        _resolve_note_item_for_paper_id_from_lookup(note_item_lookup, paper_id)
        if note_item_lookup is not None
        else paper_notes._find_note_item_for_paper_id(note_items, paper_id)
    )
    if not target:
        return None
    resolved_paper_id = str(getattr(target, "id", None) or paper_id).strip() or paper_id
    return _build_note_backed_paper_item_from_index_item(vault_path, target, paper_id=resolved_paper_id)


def _build_note_backed_pdf_path(paper_id: str) -> Path | None:
    try:
        vault_path = paper_notes._resolve_vault_path()
        note_items = _load_deduped_note_items_without_ops(vault_path)
        if not note_items:
            return None
        return _resolve_note_backed_pdf_path_for_paper_id(
            vault_path,
            note_items,
            paper_id,
        )
    except (FileNotFoundError, HTTPException):
        return None


def _resolve_db_backed_paper_pdf_availability(
    paper_id: str,
    raw_pdf_path: str | None,
    *,
    vault_path: Path | None = None,
    note_items: list[PaperNoteIndexItem] | None = None,
    note_item_lookup: _IndexedNoteItemLookup | None = None,
    resolved_note_target: PaperNoteIndexItem | None = None,
) -> tuple[str | None, bool]:
    effective_pdf_path = raw_pdf_path
    pdf_exists = bool(raw_pdf_path and os.path.exists(raw_pdf_path))
    if not pdf_exists and paper_id:
        if vault_path is not None and resolved_note_target is not None:
            note_pdf_path = _resolve_note_backed_pdf_path_from_index_item(vault_path, resolved_note_target)
        elif vault_path is not None and note_items is not None:
            note_pdf_path = _resolve_note_backed_pdf_path_for_paper_id(
                vault_path,
                note_items,
                paper_id,
                note_item_lookup=note_item_lookup,
            )
        else:
            note_pdf_path = _build_note_backed_pdf_path(paper_id)
        if note_pdf_path is not None:
            effective_pdf_path = str(note_pdf_path)
            pdf_exists = True
    return effective_pdf_path, pdf_exists


def _db_row_may_need_note_backed_pdf_lookup(row: Any) -> bool:
    getter = getattr(row, "get", None)
    if callable(getter):
        raw_pdf_path = str(getter("pdf_path") or "").strip()
    else:
        try:
            raw_pdf_path = str(row["pdf_path"] or "").strip()
        except Exception:
            raw_pdf_path = ""
    if not raw_pdf_path:
        return True
    return not os.path.exists(raw_pdf_path)


def _build_db_backed_paper_item_from_row(
    row: Any,
    *,
    artifact_cache: ArtifactSnapshotCache,
    artifacts_path: Path,
    vault_path: Path | None = None,
    note_items: list[PaperNoteIndexItem] | None = None,
    note_item_lookup: _IndexedNoteItemLookup | None = None,
    resolved_note_target: PaperNoteIndexItem | None = None,
    latest_run_id_lookup: dict[str, str] | None = None,
    note_slug: str | None = None,
    ops_candidate_ids: list[str] | None = None,
) -> dict[str, Any]:
    item = _paper_summary_response_record_from_row(row)
    paper_id = str(item.get("paper_id") or "").strip()
    ops_candidate_ids = list(ops_candidate_ids) if ops_candidate_ids is not None else _ops_summary_candidate_ids(paper_id)
    item["note_slug"] = note_slug
    raw_pdf_path = str(item.get("pdf_path") or "").strip() or None
    effective_pdf_path, pdf_exists = _resolve_db_backed_paper_pdf_availability(
        paper_id,
        raw_pdf_path,
        vault_path=vault_path,
        note_items=note_items,
        note_item_lookup=note_item_lookup,
        resolved_note_target=resolved_note_target,
    )

    item["pdf_exists"] = pdf_exists
    item["pdf_path"] = _public_path(effective_pdf_path)
    if not pdf_exists and raw_pdf_path:
        item["pdf_status"] = "missing"
    else:
        item["pdf_status"] = None
    item["issues_state"] = _derive_paper_issues_state(item)
    ops_summary = _ops_summary_from_artifact_cache_for_candidate_ids(
        ops_candidate_ids,
        artifact_cache,
    )
    if ops_summary is _UNCACHED_ARTIFACT_GROUP:
        ops_summary = build_ops_summary_for_candidate_ids(
            artifacts_path,
            ops_candidate_ids,
            artifact_cache,
        )
    ops_summary_latest_run_id = getattr(ops_summary, "latest_run_id", None) if ops_summary is not None else None
    artifact_latest_run_id = (
        None
        if ops_summary_latest_run_id
        else _latest_run_id_from_artifact_cache_for_candidate_ids(
            ops_candidate_ids,
            artifact_cache,
        )
    )
    preloaded_latest_run_id = latest_run_id_lookup.get(paper_id) if latest_run_id_lookup is not None else None
    item["ops_summary"] = ops_summary
    item["latest_run_id"] = (
        ops_summary_latest_run_id
        or artifact_latest_run_id
        or preloaded_latest_run_id
        or (
            None
            if _artifact_cache_covers_candidate_ids(ops_candidate_ids, artifact_cache)
            else _latest_run_id_for_candidate_ids(ops_candidate_ids)
        )
    )
    item["access_summary"] = _build_paper_access_summary(item, paper_id=paper_id, pdf_exists=pdf_exists)
    _apply_escalation_response_fields(item)
    return item


def _build_db_backed_paper_rail_item_from_row(
    row: Any,
    *,
    artifact_cache: ArtifactSnapshotCache,
    artifacts_path: Path,
    vault_path: Path | None = None,
    note_items: list[PaperNoteIndexItem] | None = None,
    note_item_lookup: _IndexedNoteItemLookup | None = None,
    note_slug: str | None = None,
    ops_candidate_ids: list[str] | None = None,
) -> dict[str, Any]:
    getter = getattr(row, "get", None)

    def _value(column: str) -> Any:
        if callable(getter):
            return getter(column)
        try:
            return row[column]
        except Exception:
            return None

    paper_id = str(_value("paper_id") or "").strip()
    ops_candidate_ids = list(ops_candidate_ids) if ops_candidate_ids is not None else _ops_summary_candidate_ids(paper_id)
    raw_pdf_path = str(_value("pdf_path") or "").strip() or None
    _, pdf_exists = _resolve_db_backed_paper_pdf_availability(
        paper_id,
        raw_pdf_path,
        vault_path=vault_path,
        note_items=note_items,
        note_item_lookup=note_item_lookup,
    )
    issues_record = _workspace_summary_issues_record_from_row(row)
    issues_state = _derive_paper_issues_state(issues_record)
    ops_summary = _ops_summary_from_artifact_cache_for_candidate_ids(
        ops_candidate_ids,
        artifact_cache,
    )
    if ops_summary is _UNCACHED_ARTIFACT_GROUP:
        ops_summary = build_ops_summary_for_candidate_ids(
            artifacts_path,
            ops_candidate_ids,
            artifact_cache,
        )
    return {
        "paper_id": paper_id,
        "note_slug": note_slug,
        "title": str(_value("title") or paper_id).strip() or paper_id,
        "authors": str(_value("authors") or "").strip() or None,
        "status": str(_value("status") or "").strip() or None,
        "issues": issues_record.get("issues") if isinstance(issues_record.get("issues"), int) else None,
        "issues_label": str(issues_record.get("issues_label") or "").strip() or None,
        "issues_state": issues_state,
        "updated_at": str(_value("updated_at") or "").strip() or None,
        "ops_summary": ops_summary,
        "access_summary": _build_paper_access_summary(
            _paper_access_record_from_row(row),
            paper_id=paper_id,
            pdf_exists=pdf_exists,
        ),
    }


def _apply_escalation_response_fields(item: dict[str, Any]) -> None:
    item["is_escalated"] = bool(item.get("is_escalated", False))

    raw_reason_codes = item.get("escalation_reason_codes")
    if isinstance(raw_reason_codes, list):
        item["escalation_reason_codes"] = [str(code).strip() for code in raw_reason_codes if str(code).strip()]
    else:
        item["escalation_reason_codes"] = []

    if isinstance(item.get("escalation_in_biomedical_scope"), bool):
        pass
    else:
        item["escalation_in_biomedical_scope"] = None

    if item.get("escalation_reason") is not None:
        item["escalation_reason"] = str(item.get("escalation_reason") or "").strip() or None
    else:
        item["escalation_reason"] = None
    if item.get("escalation_final_route") is not None:
        item["escalation_final_route"] = str(item.get("escalation_final_route") or "").strip() or None
    else:
        item["escalation_final_route"] = None

    feedback_json = item.get("feedback_json")
    if not feedback_json:
        return

    try:
        parsed = json.loads(feedback_json)
    except Exception:
        return
    if not isinstance(parsed, dict):
        return
    escalation = parsed.get("escalation")
    if not isinstance(escalation, dict):
        return

    item["is_escalated"] = bool(item.get("is_escalated")) or bool(escalation.get("approved", False))
    if not item.get("escalation_reason"):
        item["escalation_reason"] = str(escalation.get("reason") or "").strip() or None
    if not item.get("escalation_final_route"):
        item["escalation_final_route"] = str(escalation.get("final_route") or "").strip() or None
    if item.get("escalation_in_biomedical_scope") is None and isinstance(
        escalation.get("in_biomedical_scope"), bool
    ):
        item["escalation_in_biomedical_scope"] = escalation.get("in_biomedical_scope")
    if not item.get("escalation_reason_codes"):
        raw_codes = escalation.get("reason_codes")
        if isinstance(raw_codes, list):
            item["escalation_reason_codes"] = [str(code).strip() for code in raw_codes if str(code).strip()]


def _resolve_bootstrap_meta_path(job: JobStatus) -> str | None:
    artifact_dir = getattr(job, "artifact_dir", None)
    if not artifact_dir:
        return None
    return str(Path(artifact_dir) / "bootstrap_meta.json")


def _read_bootstrap_meta(meta_path: str | None) -> dict:
    if not meta_path:
        return {}
    path = Path(meta_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _with_bootstrap_meta_path(job: JobStatus) -> JobStatus:
    meta_path = _resolve_bootstrap_meta_path(job)
    meta = _read_bootstrap_meta(meta_path)
    params = get_execution_run_params(getattr(job, "run_id", None))
    requested_parser_backend = str(params.get("parser_backend") or "").strip() or None
    selection = normalize_persona_selection(
        persona_id=meta.get("persona_id") or params.get("persona_id") or getattr(job, "persona_id", None),
        reasoning_persona=meta.get("reasoning_persona") or params.get("reasoning_persona") or getattr(job, "reasoning_persona", None),
        profile_id=meta.get("profile_id") or params.get("profile_id") or getattr(job, "profile_id", None),
    )
    readiness = meta.get("claimset_readiness")
    badge = meta.get("claimset_readiness_badge")
    if badge is None:
        if readiness == "ready":
            badge = "READY"
        elif readiness == "not_ready":
            badge = "NOT_READY"
        elif readiness == "unknown":
            badge = "UNKNOWN"
    return job.model_copy(
        update={
            "artifact_dir": _public_path(getattr(job, "artifact_dir", None)),
            "log_path": _public_path(getattr(job, "log_path", None)),
            "bootstrap_meta_path": _public_path(meta_path),
            "error_message": sanitize_event_text_for_log(getattr(job, "error_message", None)),
            "persona_id": selection.persona_id,
            "reasoning_persona": selection.reasoning_persona,
            "profile_id": selection.profile_id,
            "requested_parser_backend": requested_parser_backend,
            "parser_backend": meta.get("parser_backend"),
            "similar_feedback_count": meta.get("similar_feedback_count"),
            "persona_applied": meta.get("persona_applied"),
            "artifact_document_written": meta.get("artifact_document_written"),
            "artifact_index_written": meta.get("artifact_index_written"),
            "artifact_claimset_written": meta.get("artifact_claimset_written"),
            "artifact_claimset_resolved_written": meta.get("artifact_claimset_resolved_written"),
            "artifact_stats_written": meta.get("artifact_stats_written"),
            "claimset_readiness": meta.get("claimset_readiness"),
            "claimset_ready": meta.get("claimset_ready"),
            "claimset_claim_count": meta.get("claimset_claim_count"),
            "claimset_grounded_span_count": meta.get("claimset_grounded_span_count"),
            "claimset_unresolved_span_count": meta.get("claimset_unresolved_span_count"),
            "claimset_readiness_reason": meta.get("claimset_readiness_reason"),
            "claimset_readiness_badge": badge,
            "claimset_ops_action": meta.get("claimset_ops_action"),
            "claimset_ops_alert": meta.get("claimset_ops_alert"),
            "claimset_ops_note": meta.get("claimset_ops_note"),
        }
    )


def _artifact_run_dir(paper_id: str, run_id: str) -> Path:
    return artifact_run_dir(paper_id, run_id)


def _safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_parse_error": str(exc)}


def _sanitize_operational_artifact_for_api(payload: Any) -> Any:
    return sanitize_event_payload_for_log(payload)


def _safe_read_artifact_json(key: str, path: Path) -> Any:
    payload = _safe_read_json(path)
    if key in {"run_meta", "bootstrap_meta"}:
        return _sanitize_operational_artifact_for_api(payload)
    return payload


def _normalize_inference_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _summarize_inference_lanes(
    lanes: dict[str, RunInferenceLaneSummary],
) -> tuple[str, str, bool]:
    backends = {
        lane.selected_backend.strip()
        for lane in lanes.values()
        if lane.selected_backend.strip() and lane.selected_backend.strip() != "none"
    }
    payload_classes = {
        lane.payload_class.strip()
        for lane in lanes.values()
        if lane.payload_class.strip() and lane.payload_class.strip() != "none"
    }
    selected_backend = next(iter(backends)) if len(backends) == 1 else ("mixed" if backends else "none")
    payload_class = next(iter(payload_classes)) if len(payload_classes) == 1 else ("mixed" if payload_classes else "none")
    redaction_applied = any(lane.redaction_applied for lane in lanes.values())
    return selected_backend, payload_class, redaction_applied


def _extract_lane_privacy_preflight(payload: Any) -> PrivacyPreflightResponse | None:
    if not isinstance(payload, dict):
        return None
    try:
        return PrivacyPreflightResponse.model_validate(payload)
    except Exception:
        return None


def _extract_run_inference_summary(run_meta_payload: Any) -> RunInferenceSummary | None:
    if not isinstance(run_meta_payload, dict) or "_parse_error" in run_meta_payload:
        return None

    lanes: dict[str, RunInferenceLaneSummary] = {}
    raw_lanes = run_meta_payload.get("inference_lanes")
    if isinstance(raw_lanes, dict):
        for lane_name, lane_payload in raw_lanes.items():
            normalized_name = str(lane_name or "").strip()
            if not normalized_name or not isinstance(lane_payload, dict):
                continue
            selected_backend = _normalize_inference_text(lane_payload.get("selected_backend")) or "none"
            payload_class = _normalize_inference_text(lane_payload.get("payload_class")) or "none"
            provider_name = _normalize_inference_text(lane_payload.get("provider_name"))
            provider_model = _normalize_inference_text(lane_payload.get("provider_model"))
            redaction_applied = bool(lane_payload.get("redaction_applied"))
            privacy_preflight = _extract_lane_privacy_preflight(lane_payload.get("privacy_preflight"))
            if (
                selected_backend == "none"
                and payload_class == "none"
                and not redaction_applied
                and provider_name is None
                and provider_model is None
                and privacy_preflight is None
            ):
                continue
            lanes[normalized_name] = RunInferenceLaneSummary(
                selected_backend=selected_backend,
                payload_class=payload_class,
                redaction_applied=redaction_applied,
                provider_name=provider_name,
                provider_model=provider_model,
                privacy_preflight=privacy_preflight,
            )

    lane_backend, lane_payload_class, lane_redaction = _summarize_inference_lanes(lanes)
    selected_backend = _normalize_inference_text(run_meta_payload.get("selected_backend")) or lane_backend
    payload_class = _normalize_inference_text(run_meta_payload.get("payload_class")) or lane_payload_class
    if "redaction_applied" in run_meta_payload:
        redaction_applied = bool(run_meta_payload.get("redaction_applied"))
    else:
        redaction_applied = lane_redaction

    if selected_backend == "none" and payload_class == "none" and not redaction_applied and not lanes:
        return None

    return RunInferenceSummary(
        selected_backend=selected_backend,
        payload_class=payload_class,
        redaction_applied=redaction_applied,
        lanes=lanes,
    )


def _build_artifact_bundle(paper_id: str, run_id: str) -> ArtifactBundleResponse:
    resolved_paper_id: str | None = None
    run_dir: Path | None = None
    for candidate_id in _paper_route_candidate_ids(paper_id):
        candidate_run_dir = _artifact_run_dir(candidate_id, run_id)
        if candidate_run_dir.exists():
            resolved_paper_id = candidate_id
            run_dir = candidate_run_dir
            break
    if run_dir is None or resolved_paper_id is None:
        raise HTTPException(status_code=404, detail=f"Artifacts not found for paper_id={paper_id}, run_id={run_id}")

    files: dict[str, ArtifactFileEntry] = {}
    inference_summary: RunInferenceSummary | None = None
    for key, filename in ARTIFACT_FILE_MAP.items():
        path = run_dir / filename
        entry = ArtifactFileEntry(
            exists=path.exists(),
            path=_public_path(str(path)) if path.exists() else None,
        )
        if path.exists() and path.suffix == ".json":
            entry.data = _safe_read_artifact_json(key, path)
            if key == "run_meta":
                inference_summary = _extract_run_inference_summary(entry.data)
        files[key] = entry

    return ArtifactBundleResponse(
        paper_id=resolved_paper_id,
        run_id=run_id,
        inference_summary=inference_summary,
        files=files,
    )


def _resolve_artifact_key(artifact_name: str) -> str | None:
    normalized = artifact_name.strip().lower()
    return ARTIFACT_ALIAS_MAP.get(normalized)


def _latest_run_id_for_candidate_ids(candidate_ids: list[str]) -> str | None:
    normalized_candidate_ids = _normalized_candidate_id_list(candidate_ids)
    if not normalized_candidate_ids:
        return None

    conn = get_db_connection()
    try:
        placeholders = ", ".join("?" for _ in normalized_candidate_ids)
        try:
            rows = conn.execute(
                f"""
                SELECT run_id, artifact_dir
                FROM jobs
                WHERE paper_id IN ({placeholders}) AND run_id IS NOT NULL
                ORDER BY COALESCE(finished_at, started_at, created_at) DESC
                LIMIT 100
                """,
                tuple(normalized_candidate_ids),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        for row in rows:
            run_id = str(row["run_id"] or "").strip()
            if not run_id:
                continue
            artifact_dir = str(row["artifact_dir"] or "").strip()
            if artifact_dir:
                if Path(artifact_dir).exists():
                    return run_id
            else:
                for candidate_id in normalized_candidate_ids:
                    if _artifact_run_dir(candidate_id, run_id).exists():
                        return run_id
    finally:
        conn.close()

    latest_dir: Path | None = None
    latest_mtime = -1.0
    for candidate_id in normalized_candidate_ids:
        for paper_dir in artifact_paper_dir_candidates(candidate_id):
            if not paper_dir.exists():
                continue
            for candidate in paper_dir.iterdir():
                if not candidate.is_dir():
                    continue
                candidate_mtime = candidate.stat().st_mtime
                if candidate_mtime > latest_mtime:
                    latest_mtime = candidate_mtime
                    latest_dir = candidate
    return latest_dir.name if latest_dir is not None else None


def _latest_run_id_for_paper(paper_id: str) -> str | None:
    return _latest_run_id_for_candidate_ids(_paper_route_candidate_ids(paper_id))


def _job_for_run_id(run_id: str) -> JobStatus | None:
    conn = get_db_connection()
    try:
        try:
            row = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE run_id = ?
                ORDER BY COALESCE(finished_at, started_at, created_at) DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if not row:
            return None
        return JobStatus(**dict(row))
    finally:
        conn.close()


def _job_sort_timestamp(job: JobStatus) -> float:
    from datetime import datetime, timezone

    for raw in (job.finished_at, job.started_at, job.created_at):
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = text.replace("Z", "+00:00")
        if "T" not in normalized and " " in normalized:
            normalized = normalized.replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    return 0.0


def _list_jobs(*, paper_id: str | None, status: str | None, limit: int) -> list[JobStatus]:
    conn = get_db_connection()
    try:
        where: list[str] = []
        params: list[Any] = []
        if paper_id:
            candidate_ids = _paper_route_candidate_ids(paper_id)
            if candidate_ids:
                placeholders = ", ".join("?" for _ in candidate_ids)
                where.append(f"paper_id IN ({placeholders})")
                params.extend(candidate_ids)
        if status:
            where.append("status = ?")
            params.append(status)

        query = "SELECT * FROM jobs"
        if where:
            query += " WHERE " + " AND ".join(where)
        try:
            rows = conn.execute(query, params).fetchall()
        except sqlite3.OperationalError:
            return []
        jobs = [_with_bootstrap_meta_path(JobStatus(**dict(row))) for row in rows]
        jobs.sort(key=_job_sort_timestamp, reverse=True)
        return jobs[:limit]
    finally:
        conn.close()


def _timeline_events_from_job(job: JobStatus, limit: int) -> list[RunTimelineEvent]:
    db_events = []
    if job.run_id:
        db_events = list_run_events(str(job.run_id), limit=limit)
    user_action_events: list[RunTimelineEvent] = []
    if job.paper_id and job.run_id:
        action_rows = list_user_actions(paper_id=str(job.paper_id), limit=max(limit * 3, 50))
        for row in reversed(action_rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("run_id") or "").strip() != str(job.run_id):
                continue
            action_type = str(row.get("action_type") or "").strip()
            message = action_type
            if action_type == "deepread_enqueued":
                message = "User queued deep read"
            elif action_type == "repair_stats":
                message = "User requested stats repair"
            elif action_type == "obsidian_sync":
                message = "User synced note to Obsidian"
            elif action_type == "skill_run":
                skill_action = str(payload.get("action") or "").strip()
                message = f"User ran skill: {skill_action}" if skill_action else "User ran skill"
            elif action_type == "workbench_select_claim":
                claim_id = str(payload.get("claim_id") or "").strip()
                message = f"User selected claim: {claim_id}" if claim_id else "User selected claim"
            elif action_type == "workbench_jump_mirror_claim":
                target_claim_id = str(payload.get("target_claim_id") or "").strip()
                message = f"User jumped from mirror claim to: {target_claim_id}" if target_claim_id else "User jumped from mirror claim"
            elif action_type == "workbench_jump_stats_check":
                check_id = str(payload.get("check_id") or "").strip()
                message = f"User jumped from stats check: {check_id}" if check_id else "User jumped from stats check"
            user_action_events.append(
                RunTimelineEvent(
                    event="status",
                    source="user_action",
                    ts=str(row.get("ts") or ""),
                    stage=action_type or "user_action",
                    level="INFO",
                    message=message,
                )
            )

    log_events: list[RunTimelineEvent] = []
    if job.log_path and Path(job.log_path).exists():
        lines = [
            line.strip()
            for line in Path(job.log_path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for raw in lines[-limit:]:
            try:
                payload = sanitize_event_payload_for_log(json.loads(raw))
                if not isinstance(payload, dict):
                    raise ValueError("job log line is not an object")
                level = str(payload.get("level") or "INFO")
                evt = "error" if level.upper() == "ERROR" else "log"
                log_events.append(
                    RunTimelineEvent(
                        event=evt,
                        source="job_log",
                        ts=str(payload.get("timestamp") or ""),
                        stage=sanitize_event_text_for_log(str(payload.get("stage") or "")) or None,
                        progress=int(payload.get("progress")) if payload.get("progress") is not None else None,
                        level=sanitize_event_text_for_log(level),
                        message=sanitize_event_text_for_log(str(payload.get("message") or "")),
                    )
                )
            except Exception:
                log_events.append(
                    RunTimelineEvent(
                        event="log",
                        source="job_log",
                        raw=sanitize_event_text_for_log(raw),
                    )
                )

    if db_events:
        events: list[RunTimelineEvent] = []
        for row in db_events[-limit:]:
            payload: dict[str, Any] = {}
            try:
                payload_raw = row.get("payload_json")
                if payload_raw:
                    payload = json.loads(str(payload_raw))
            except Exception:
                payload = {}

            level = str(row.get("level") or payload.get("level") or "INFO")
            event_name = "error" if level.upper() == "ERROR" else "log"
            events.append(
                RunTimelineEvent(
                    event=event_name,
                    source="db_event",
                    ts=str(row.get("ts") or ""),
                    stage=payload.get("stage") or payload.get("status"),
                    progress=int(payload.get("progress")) if payload.get("progress") is not None else None,
                    level=level,
                    message=str(row.get("message") or payload.get("message") or row.get("event_type") or ""),
                )
            )

        events.extend(log_events)
        events.extend(user_action_events)
        terminal = (
            RunTimelineEvent(
                event="done",
                source="synthetic",
                ts=str(job.finished_at or job.started_at or job.created_at),
                stage=job.status,
                progress=job.progress,
                level="ERROR" if job.status == "failed" else "INFO",
                message=sanitize_event_text_for_log(job.error_message) or job.status,
            )
            if job.status in TERMINAL_JOB_STATUSES
            else RunTimelineEvent(
                event="status",
                source="synthetic",
                ts=str(job.started_at or job.created_at),
                stage=job.stage or job.status,
                progress=job.progress,
                level="INFO",
                message=job.status,
            )
        )
        events.append(terminal)
        if len(events) > limit:
            return events[-limit:]
        return events

    events: list[RunTimelineEvent] = []
    if log_events:
        events.extend(log_events)
    if user_action_events:
        events.extend(user_action_events)

    terminal = (
        RunTimelineEvent(
            event="done",
            source="synthetic",
            ts=str(job.finished_at or job.started_at or job.created_at),
            stage=job.status,
            progress=job.progress,
            level="ERROR" if job.status == "failed" else "INFO",
            message=sanitize_event_text_for_log(job.error_message) or job.status,
        )
        if job.status in TERMINAL_JOB_STATUSES
        else RunTimelineEvent(
            event="status",
            source="synthetic",
            ts=str(job.started_at or job.created_at),
            stage=job.stage or job.status,
            progress=job.progress,
            level="INFO",
            message=job.status,
        )
    )
    events.append(terminal)

    if len(events) > limit:
        return events[-limit:]
    return events


def _read_log_lines(log_path: str | None) -> list[str]:
    if not log_path:
        return []
    path = Path(log_path)
    if not path.exists():
        return []
    sanitized_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = sanitize_event_payload_for_log(json.loads(raw))
            sanitized_lines.append(json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            safe_raw = sanitize_event_text_for_log(raw)
            if safe_raw:
                sanitized_lines.append(safe_raw)
    return sanitized_lines


def _parse_last_event_cursor(last_event_id: str | None) -> tuple[int, str]:
    """
    Parse Last-Event-ID into (sequence, kind).
    kind is one of: log | done | seq.
    """
    if not last_event_id:
        return (0, "seq")
    token = last_event_id.strip()
    if not token:
        return (0, "seq")
    if token.isdigit():
        return (max(0, int(token)), "seq")
    if "-" in token:
        prefix, tail = token.rsplit("-", 1)
        kind = prefix.strip().lower()
        if tail.isdigit():
            if kind not in {"log", "done"}:
                kind = "seq"
            return (max(0, int(tail)), kind)
    return (0, "seq")


def _normalize_replay_cursor(replay_cursor: int, replay_kind: str, total_logs: int, is_terminal: bool) -> tuple[int, str]:
    """
    Normalize replay cursor semantics for log rotations and terminal cursor handling.
    - stale cursor (out of range): replay from head
    - done cursor on terminal exact seq: no duplicate done replay
    - done cursor on non-terminal job: treat as stale
    """
    max_seq = total_logs + (1 if is_terminal else 0)
    if replay_kind == "done":
        if not is_terminal:
            return 0, "seq"
        if replay_cursor == max_seq:
            return replay_cursor, "done"
        if replay_cursor < max_seq:
            return replay_cursor, "seq"
    if replay_cursor > max_seq:
        return 0, "seq"
    return replay_cursor, replay_kind


def _persona_options(include_disabled: bool) -> list[PersonaOption]:
    options: list[PersonaOption] = [
        PersonaOption(
            id="default",
            title="Default (No Persona Override)",
            enabled=True,
            kind="compatibility",
            notes="Compatibility alias. New clients should split reasoning persona and profile context explicitly.",
            source="builtin",
        )
    ]
    for definition in list_reasoning_personas():
        options.append(
            PersonaOption(
                id=definition.id,
                title=definition.title,
                enabled=True,
                kind="reasoning_persona",
                notes=definition.notes,
                source="builtin",
            )
        )
    conf = load_profiles()
    for profile in conf.profiles:
        if not include_disabled and not profile.enabled:
            continue
        options.append(
            PersonaOption(
                id=profile.id,
                title=profile.title,
                enabled=profile.enabled,
                kind="profile",
                notes=profile.notes,
                schedule=profile.schedule,
                query_focus=profile.query.to_boolean_string(),
                source="yaml",
            )
        )
    return options

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "3.1.0"}


@app.get("/health/ready", response_model=RuntimeReadinessResponse)
def health_ready():
    readiness = collect_runtime_readiness()
    if not _resolve_browser_detailed_runtime_readiness_enabled():
        readiness = summarize_browser_runtime_readiness(readiness)
    return RuntimeReadinessResponse(
        status=readiness.status,
        checks=[
            RuntimeReadinessCheck(
                name=check.name,
                status=check.status,
                detail=check.detail,
                path=_public_path(check.path),
                metadata=dict(check.metadata or {}),
            )
            for check in readiness.checks
        ],
    )


@app.post("/api/chat", response_model=ChatStubResponse)
def chat_stub(req: ChatRequest):
    output_mode_family = resolve_chat_output_mode_family(req.output_mode_family)
    if not _is_chat_enabled():
        return JSONResponse(
            status_code=501,
            content=ChatStubResponse(
                chat_enabled=False,
                output_mode_family=output_mode_family,
                message=(
                    "CHAT_ENABLED=false. /api/chat is a stub only in this sprint; "
                    "no LLM provider, memory, or RAG call is executed."
                ),
            ).model_dump(),
        )
    return JSONResponse(
        status_code=501,
        content=ChatStubResponse(
            chat_enabled=True,
            output_mode_family=output_mode_family,
            message=(
                "/api/chat is intentionally stubbed. This sprint does not implement "
                "LLM execution, conversation storage, or retrieval."
            ),
        ).model_dump(),
    )


@app.post("/research-dna", response_model=ResearchDNAEnvelope)
def create_research_dna_endpoint(req: ResearchDNACreateRequest):
    try:
        dna = create_research_dna(
            topic=req.topic,
            intent=req.intent,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
            dna_id=req.dna_id,
            title=req.title,
            recommended_databases=req.recommended_databases,
            available_databases=req.available_databases,
        )
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.get("/research-dna/{dna_id}", response_model=ResearchDNAEnvelope)
def get_research_dna_endpoint(dna_id: str):
    try:
        dna = load_research_dna(dna_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/approve-pilot", response_model=ResearchDNAEnvelope)
def approve_research_dna_pilot_endpoint(dna_id: str, req: ResearchDNAActorRequest):
    try:
        dna = approve_pilot(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to approve pilot: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/update", response_model=ResearchDNAEnvelope)
def update_research_dna_endpoint(dna_id: str, req: ResearchDNAUpdateRequest):
    try:
        dna = update_research_dna(
            dna_id,
            patch=req.patch,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/interview", response_model=ResearchDNAInterviewEnvelope)
def log_research_dna_interview_endpoint(dna_id: str, req: ResearchDNAInterviewRequest):
    try:
        dna, interview = log_interview_response(
            dna_id,
            round=req.round,
            question_id=req.question_id,
            question=req.question,
            answer=req.answer,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to log interview response: {exc}")
    return ResearchDNAInterviewEnvelope(dna=dna, interview=interview)


@app.post("/research-dna/{dna_id}/pilot", response_model=ResearchDNAPilotRunEnvelope)
def run_research_dna_pilot_endpoint(dna_id: str, req: ResearchDNAPilotRunRequest):
    try:
        pilot_run = run_pilot(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            run_id=req.run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to run pilot: {exc}")
    return ResearchDNAPilotRunEnvelope(pilot_run=pilot_run)


@app.post("/research-dna/{dna_id}/rerank", response_model=ResearchDNARerankEnvelope)
def rerank_research_dna_screening_endpoint(dna_id: str, req: ResearchDNARerankRequest):
    try:
        rerank = materialize_reranked_screening_queue(
            dna_id,
            run_id=req.run_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to rerank screening queue: {exc}")
    return ResearchDNARerankEnvelope(rerank=rerank)


@app.post("/research-dna/{dna_id}/guidance/materialize", response_model=ResearchDNAScreeningGuidanceArtifactEnvelope)
def materialize_research_dna_guidance_endpoint(dna_id: str, req: ResearchDNAGuidanceMaterializeRequest):
    try:
        guidance_artifact = materialize_screening_guidance_artifact(
            dna_id,
            run_id=req.run_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to materialize screening guidance: {exc}")
    return ResearchDNAScreeningGuidanceArtifactEnvelope(guidance_artifact=guidance_artifact)


@app.get("/research-dna/{dna_id}/runs", response_model=ResearchDNARunIndexEnvelope)
def get_research_dna_run_index_endpoint(
    dna_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    try:
        run_index = load_research_dna_run_index(
            dna_id,
            limit=limit,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load run index: {exc}")
    return ResearchDNARunIndexEnvelope(run_index=run_index)


@app.get("/research-dna/{dna_id}/resume", response_model=ResearchDNAResumeEnvelope)
def get_research_dna_resume_endpoint(
    dna_id: str,
    variant: str = Query("original", pattern="^(original|reranked)$"),
    recent_limit: int = Query(5, ge=1, le=20),
):
    try:
        resume = load_research_dna_resume_snapshot(
            dna_id,
            variant=variant,  # type: ignore[arg-type]
            recent_limit=recent_limit,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load resume snapshot: {exc}")
    return ResearchDNAResumeEnvelope(resume=resume)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/screening-guidance-artifact",
    response_model=ResearchDNAScreeningGuidanceArtifactEnvelope,
)
def get_research_dna_screening_guidance_artifact_endpoint(dna_id: str, run_id: str):
    try:
        guidance_artifact = load_latest_screening_guidance_artifact(
            dna_id,
            run_id=run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening guidance artifact: {exc}")
    return ResearchDNAScreeningGuidanceArtifactEnvelope(guidance_artifact=guidance_artifact)


@app.get("/research-dna/{dna_id}/runs/{run_id}/screening-queue", response_model=ResearchDNAScreeningQueueEnvelope)
def get_research_dna_screening_queue_endpoint(
    dna_id: str,
    run_id: str,
    variant: str = Query("original", pattern="^(original|reranked)$"),
):
    try:
        screening_queue = load_screening_queue_artifact(
            dna_id,
            run_id=run_id,
            variant=variant,  # type: ignore[arg-type]
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening queue: {exc}")
    return ResearchDNAScreeningQueueEnvelope(screening_queue=screening_queue)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/next-screening-candidate",
    response_model=ResearchDNANextScreeningCandidateEnvelope,
)
def get_research_dna_next_screening_candidate_endpoint(
    dna_id: str,
    run_id: str,
    variant: str = Query("original", pattern="^(original|reranked)$"),
):
    try:
        next_candidate = load_next_screening_candidate(
            dna_id,
            run_id=run_id,
            variant=variant,  # type: ignore[arg-type]
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to select next screening candidate: {exc}")
    return ResearchDNANextScreeningCandidateEnvelope(next_candidate=next_candidate)


@app.get("/research-dna/{dna_id}/runs/{run_id}/screening-session", response_model=ResearchDNAScreeningSessionEnvelope)
def get_research_dna_screening_session_endpoint(
    dna_id: str,
    run_id: str,
    variant: str = Query("original", pattern="^(original|reranked)$"),
    recent_limit: int = Query(5, ge=1, le=20),
):
    try:
        session = load_screening_session(
            dna_id,
            run_id=run_id,
            variant=variant,  # type: ignore[arg-type]
            recent_limit=recent_limit,
        )
        recommendation, gate = load_screening_operator_guidance(
            dna_id,
            run_id=run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening session: {exc}")
    return ResearchDNAScreeningSessionEnvelope(session=session, recommendation=recommendation, gate=gate)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/screening-progress",
    response_model=ResearchDNAScreeningProgressEnvelope,
)
def get_research_dna_screening_progress_endpoint(
    dna_id: str,
    run_id: str,
    variant: str = Query("original", pattern="^(original|reranked)$"),
):
    try:
        progress = load_screening_progress_report(
            dna_id,
            run_id=run_id,
            variant=variant,  # type: ignore[arg-type]
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening progress: {exc}")
    return ResearchDNAScreeningProgressEnvelope(progress=progress)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/screening-guidance",
    response_model=ResearchDNAScreeningGuidanceEnvelope,
)
def get_research_dna_screening_guidance_endpoint(dna_id: str, run_id: str):
    try:
        recommendation, gate = load_screening_operator_guidance(
            dna_id,
            run_id=run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening guidance: {exc}")
    return ResearchDNAScreeningGuidanceEnvelope(recommendation=recommendation, gate=gate)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/screening-guidance-history",
    response_model=ResearchDNAScreeningGuidanceIndexEnvelope,
)
def get_research_dna_screening_guidance_history_endpoint(
    dna_id: str,
    run_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    try:
        guidance_index = load_screening_guidance_index_artifact(
            dna_id,
            run_id=run_id,
            limit=limit,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening guidance history: {exc}")
    return ResearchDNAScreeningGuidanceIndexEnvelope(guidance_index=guidance_index)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/screening-recommendation",
    response_model=ResearchDNAScreeningRecommendationEnvelope,
)
def get_research_dna_screening_recommendation_endpoint(dna_id: str, run_id: str):
    try:
        recommendation, _ = load_screening_operator_guidance(
            dna_id,
            run_id=run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load screening recommendation: {exc}")
    return ResearchDNAScreeningRecommendationEnvelope(recommendation=recommendation)


@app.get(
    "/research-dna/{dna_id}/runs/{run_id}/rerank-gate",
    response_model=ResearchDNARerankGateEnvelope,
)
def get_research_dna_rerank_gate_endpoint(dna_id: str, run_id: str):
    try:
        _, gate = load_screening_operator_guidance(
            dna_id,
            run_id=run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load rerank gate report: {exc}")
    return ResearchDNARerankGateEnvelope(gate=gate)


@app.post("/research-dna/{dna_id}/screening", response_model=ResearchDNAEnvelope)
def submit_research_dna_screening_endpoint(dna_id: str, req: ResearchDNAScreeningRequest):
    try:
        dna = submit_screening_decision(
            dna_id,
            run_id=req.run_id,
            candidate_id=req.candidate_id,
            decision=req.decision,
            reason_code=req.reason_code,
            note=req.note,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to submit screening decision: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/screening/advance", response_model=ResearchDNAScreeningAdvanceEnvelope)
def advance_research_dna_screening_endpoint(dna_id: str, req: ResearchDNAScreeningAdvanceRequest):
    try:
        resolved_run_id = resolve_research_dna_run_id(
            dna_id,
            run_id=req.run_id,
            latest=req.latest_run,
        )
        dna, next_candidate, session = submit_screening_decision_and_load_session(
            dna_id,
            run_id=resolved_run_id,
            candidate_id=req.candidate_id,
            decision=req.decision,
            reason_code=req.reason_code,
            note=req.note,
            variant=req.variant,  # type: ignore[arg-type]
            recent_limit=req.recent_limit,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
        recommendation, gate = load_screening_operator_guidance(
            dna_id,
            run_id=resolved_run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to advance screening workflow: {exc}")
    return ResearchDNAScreeningAdvanceEnvelope(
        dna=dna,
        next_candidate=next_candidate,
        session=session,
        recommendation=recommendation,
        gate=gate,
        screened_candidate_id=req.candidate_id,
        decision=req.decision,
        reason_code=req.reason_code,
        variant=req.variant,
    )


@app.post("/research-dna/{dna_id}/screening/current", response_model=ResearchDNAScreeningAdvanceEnvelope)
def screen_current_research_dna_candidate_endpoint(dna_id: str, req: ResearchDNAScreenCurrentRequest):
    try:
        resolved_run_id = resolve_research_dna_run_id(
            dna_id,
            run_id=req.run_id,
            latest=req.latest_run,
        )
        dna, screened_candidate_id, next_candidate, session = screen_current_candidate_and_load_session(
            dna_id,
            run_id=resolved_run_id,
            decision=req.decision,
            reason_code=req.reason_code,
            note=req.note,
            variant=req.variant,  # type: ignore[arg-type]
            recent_limit=req.recent_limit,
            expected_candidate_id=req.expected_candidate_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
        recommendation, gate = load_screening_operator_guidance(
            dna_id,
            run_id=resolved_run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to screen current candidate: {exc}")
    return ResearchDNAScreeningAdvanceEnvelope(
        dna=dna,
        next_candidate=next_candidate,
        session=session,
        recommendation=recommendation,
        gate=gate,
        screened_candidate_id=screened_candidate_id,
        decision=req.decision,
        reason_code=req.reason_code,
        variant=req.variant,
    )


@app.post("/research-dna/{dna_id}/refine", response_model=ResearchDNAEnvelope)
def refine_research_dna_endpoint(dna_id: str, req: ResearchDNARefineRequest):
    try:
        dna = refine_query_version(
            dna_id,
            query_version=req.query_version,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refine query version: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/lock", response_model=ResearchDNAEnvelope)
def lock_research_dna_endpoint(dna_id: str, req: ResearchDNAActorRequest):
    try:
        dna = lock_research_dna(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to lock Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/project-profile", response_model=ResearchDNAProjectedProfileEnvelope)
def project_research_dna_profile_endpoint(dna_id: str, req: ResearchDNAProjectProfileRequest):
    try:
        projection = sync_research_dna_profile(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
            query_version_name=req.query_version,
            database=req.database,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to project Research DNA profile: {exc}")
    return ResearchDNAProjectedProfileEnvelope(projection=projection)


@app.post("/research-dna/{dna_id}/unlock", response_model=ResearchDNAEnvelope)
def unlock_research_dna_endpoint(dna_id: str, req: ResearchDNAActorRequest):
    try:
        dna = unlock_research_dna(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to unlock Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.get("/personas", response_model=PersonaListResponse)
def list_personas(include_disabled: bool = Query(default=False)):
    try:
        return PersonaListResponse(personas=_persona_options(include_disabled=include_disabled))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load persona profiles: {exc}")


def _resolve_ui_shell_response() -> FileResponse:
    if FRONTEND_DIST_INDEX_PATH.exists():
        return FileResponse(FRONTEND_DIST_INDEX_PATH)
    if UI_SHELL_PATH.exists():
        return FileResponse(UI_SHELL_PATH)
    if FRONTEND_INDEX_PATH.exists():
        return FileResponse(FRONTEND_INDEX_PATH)
    raise HTTPException(
        status_code=404,
        detail=(
            "UI shell not found: "
            f"{FRONTEND_DIST_INDEX_PATH} or {UI_SHELL_PATH} or {FRONTEND_INDEX_PATH}"
        ),
    )


@app.get("/ui", include_in_schema=False)
def ui_shell():
    return _resolve_ui_shell_response()


@app.get("/ui/{path:path}", include_in_schema=False)
def ui_shell_deep_link(path: str):
    return _resolve_ui_shell_response()


@app.get("/sample.pdf", include_in_schema=False)
def sample_pdf_asset():
    path = FRONTEND_DIST_DIR / "sample.pdf"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail=f"Frontend asset not found: {path}")


@app.get("/vite.svg", include_in_schema=False)
def vite_svg_asset():
    path = FRONTEND_DIST_DIR / "vite.svg"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail=f"Frontend asset not found: {path}")


@app.get("/favicon.ico", include_in_schema=False)
def favicon_asset():
    path = FRONTEND_DIST_DIR / "vite.svg"
    if path.exists():
        return FileResponse(path, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/ops/downloader-metrics", response_model=DownloaderOpsMetricsResponse)
def get_downloader_metrics(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    rate_limit_warn: int = Query(default=3, ge=1),
    temp_fail_warn: int = Query(default=5, ge=1),
    bad_content_warn: int = Query(default=3, ge=1),
    policy_block_warn: int = Query(default=1, ge=1),
):
    thresholds = Thresholds(
        rate_limit_warn=rate_limit_warn,
        temp_fail_warn=temp_fail_warn,
        bad_content_warn=bad_content_warn,
        policy_block_warn=policy_block_warn,
    )
    metrics = collect_metrics(db_utils.get_db_path(), hours)
    alerts = evaluate_alerts(metrics, thresholds)
    return DownloaderOpsMetricsResponse(metrics=metrics, alerts=alerts)


@app.get("/ops/stale-jobs", response_model=StaleJobDiagnosticsResponse)
def get_stale_jobs(
    stale_after_seconds: int = Query(default=900, ge=60, le=60 * 60 * 24 * 30),
    limit: int = Query(default=50, ge=1, le=500),
):
    payload = collect_stale_jobs(
        db_path=db_utils.get_db_path(),
        stale_after_seconds=int(stale_after_seconds),
        limit=int(limit),
    )
    return StaleJobDiagnosticsResponse(**payload)


@app.get("/ops/stale-incidents", response_model=StaleJobIncidentListResponse)
def get_stale_running_incidents(limit: int = Query(default=50, ge=1, le=500)):
    payload = collect_stale_running_incidents(limit=int(limit))
    return StaleJobIncidentListResponse(**payload)


@app.post("/ops/jobs/{job_id}/reclaim-stale", response_model=StaleJobReclaimResponse)
def reclaim_stale_job(
    job_id: str,
    stale_after_seconds: int = Query(default=900, ge=60, le=60 * 60 * 24 * 30),
):
    result = reclaim_stale_running_job(
        db_path=db_utils.get_db_path(),
        job_id=job_id,
        stale_after_seconds=int(stale_after_seconds),
    )
    outcome = str(result.get("outcome") or "")
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    if outcome == "not_running":
        raise HTTPException(status_code=409, detail="Job is not currently running")
    if outcome == "not_stale":
        raise HTTPException(status_code=409, detail="Job is not stale enough to reclaim")
    return StaleJobReclaimResponse(**result)


@app.post("/ops/jobs/{job_id}/requeue-reclaimed", response_model=StaleJobRequeueResponse)
def requeue_reclaimed_stale_job(job_id: str):
    result = requeue_reclaimed_job(
        db_path=db_utils.get_db_path(),
        job_id=job_id,
    )
    outcome = str(result.get("outcome") or "")
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    if outcome == "not_reclaimed":
        raise HTTPException(status_code=409, detail="Job is not a reclaimed stale-running failure")
    if outcome == "missing_paper":
        raise HTTPException(status_code=409, detail="Reclaimed job has no paper_id to requeue")
    if outcome == "duplicate_open":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "JOB_ALREADY_OPEN",
                "message": f"Open job already exists for paper_id={result.get('paper_id')}",
                "paper_id": result.get("paper_id"),
                "job_id": result.get("job_id"),
                "run_id": result.get("run_id"),
                "status": result.get("status"),
            },
        )
    if outcome == "queue_full":
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "QUEUE_FULL",
                "message": "Queued jobs limit reached",
                "queued_count": result.get("queued_count"),
                "limit": result.get("limit"),
            },
        )
    return StaleJobRequeueResponse(**result)


@app.post(
    "/ops/jobs/{job_id}/stale-incident-snapshot",
    response_model=StaleJobIncidentSnapshotResponse,
)
def capture_stale_job_incident_snapshot(
    job_id: str,
    stale_after_seconds: int = Query(default=900, ge=60, le=60 * 60 * 24 * 30),
):
    result = capture_stale_running_incident_snapshot(
        db_path=db_utils.get_db_path(),
        job_id=job_id,
        stale_after_seconds=int(stale_after_seconds),
    )
    if str(result.get("outcome") or "") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    return StaleJobIncidentSnapshotResponse(**result)


@app.get("/papers")
def list_papers(
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[PaperSummaryResponse]:
    return _list_visible_paper_items_page(limit=limit, offset=offset)


@app.get("/papers/rail", response_model=list[PaperRailSummaryResponse])
def list_paper_rail(
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[PaperRailSummaryResponse]:
    return _list_visible_paper_rail_items_page(limit=limit, offset=offset)


@app.get("/papers/recent", response_model=list[PaperSummaryResponse])
def list_recent_papers(
    limit: int = Query(default=6, ge=1, le=20),
) -> list[PaperSummaryResponse]:
    return _list_recent_db_paper_items(limit=limit)


@app.get("/workspace-summary", response_model=HomeWorkspaceSummaryResponse)
def get_workspace_summary() -> HomeWorkspaceSummaryResponse:
    return _build_home_workspace_summary()


@app.get("/papers/{paper_id}")
def get_paper(paper_id: str) -> PaperDetailResponse:
    conn = get_db_connection()
    vault_path: Path | None = None
    note_items: list[PaperNoteIndexItem] | None = None
    resolved_note_target: PaperNoteIndexItem | None = None
    try:
        row = _lookup_paper_row_by_route_id(conn, paper_id)
        if row is None:
            row, vault_path, note_items, resolved_note_target = _lookup_paper_row_by_note_identity(
                conn,
                paper_id,
            )
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if not row:
        note_backed = (
            _resolve_note_backed_paper_item(vault_path, note_items, paper_id)
            if vault_path is not None and note_items is not None
            else _build_note_backed_paper_item(paper_id)
        )
        if note_backed is not None:
            return note_backed[0]
        raise HTTPException(status_code=404, detail="Paper not found")

    resolved_paper_id = str(row["paper_id"] or "").strip()
    note_item_lookup: _IndexedNoteItemLookup | None = None
    note_slug: str | None = str(getattr(resolved_note_target, "slug", "") or "").strip() or None
    try:
        if vault_path is None or note_items is None:
            vault_path = paper_notes._resolve_vault_path()
            note_items = _load_deduped_note_items_without_ops(vault_path)
            if not note_items:
                vault_path = None
                note_items = None
        target = resolved_note_target
        if resolved_note_target is not None and note_items is not None:
            if _db_row_may_need_note_backed_pdf_lookup(row):
                note_item_lookup = _build_note_item_lookup_for_paper_ids([resolved_note_target], [resolved_paper_id])
        elif note_items is not None:
            note_item_lookup = _build_note_item_lookup_for_paper_ids(note_items, [resolved_paper_id])
            target = _resolve_note_item_for_paper_id_from_lookup(note_item_lookup, resolved_paper_id)
        if target is not None and note_slug is None:
            note_slug = str(getattr(target, "slug", "") or "").strip() or None
    except Exception:
        vault_path = None
        note_items = None
        note_item_lookup = None
        note_slug = None

    item = _build_db_backed_paper_item_from_row(
        row,
        artifact_cache={},
        artifacts_path=artifacts_root(),
        vault_path=vault_path,
        note_items=note_items,
        note_item_lookup=note_item_lookup,
        resolved_note_target=resolved_note_target,
        note_slug=note_slug,
    )
    return item


@app.get("/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: str):
    conn = get_db_connection()
    vault_path: Path | None = None
    note_items: list[PaperNoteIndexItem] | None = None
    resolved_note_target: PaperNoteIndexItem | None = None
    try:
        row = _lookup_paper_row_by_route_id(conn, paper_id, columns="paper_id, pdf_path")
        if row is None:
            row, vault_path, note_items, resolved_note_target = _lookup_paper_row_by_note_identity(
                conn,
                paper_id,
                columns="paper_id, pdf_path",
            )
    except sqlite3.OperationalError:
        row = None
    conn.close()
    pdf_path: Path | None = None
    stale_db_pdf_path = False

    if row:
        raw_pdf_path = str(row["pdf_path"] or "").strip()
        if raw_pdf_path:
            candidate_pdf_path = Path(raw_pdf_path).expanduser()
            if candidate_pdf_path.exists() and candidate_pdf_path.is_file():
                pdf_path = candidate_pdf_path
            else:
                stale_db_pdf_path = True

    if pdf_path is None:
        note_pdf_path = (
            _resolve_note_backed_pdf_path_from_index_item(vault_path, resolved_note_target)
            if vault_path is not None and resolved_note_target is not None
            else _resolve_note_backed_pdf_path_for_paper_id(vault_path, note_items, paper_id)
            if vault_path is not None and note_items is not None
            else _build_note_backed_pdf_path(paper_id)
        )
        if note_pdf_path is not None:
            pdf_path = note_pdf_path
        else:
            note_backed = (
                _resolve_note_backed_paper_item(vault_path, note_items, paper_id)
                if vault_path is not None and note_items is not None
                else _build_note_backed_paper_item(paper_id)
            )
            if note_backed is None:
                if row:
                    if stale_db_pdf_path:
                        raise HTTPException(status_code=404, detail="PDF file not found")
                    raise HTTPException(status_code=404, detail="PDF path not registered for this paper")
                raise HTTPException(status_code=404, detail="Paper not found")
            _, note_pdf_path = note_backed
            if note_pdf_path is None:
                if stale_db_pdf_path:
                    raise HTTPException(status_code=404, detail="PDF file not found")
                raise HTTPException(status_code=404, detail="PDF path not registered for this paper")
            pdf_path = note_pdf_path

    return FileResponse(path=pdf_path, media_type="application/pdf", filename=pdf_path.name)


@app.get("/artifacts/{paper_id:path}/latest", response_model=ArtifactBundleResponse)
def get_latest_artifacts(paper_id: str):
    run_id = _latest_run_id_for_paper(paper_id)
    if not run_id:
        raise HTTPException(status_code=404, detail=f"No artifact runs found for paper_id={paper_id}")
    return _build_artifact_bundle(paper_id, run_id)


@app.get("/artifacts", response_model=ArtifactBundleResponse)
def get_artifacts_for_run_query(paper_id: str, run_id: str):
    return _build_artifact_bundle(paper_id, run_id)


@app.get("/artifacts/{paper_id:path}/{run_id}/{artifact_name}", response_model=ArtifactFileEntry)
def get_artifact_file(paper_id: str, run_id: str, artifact_name: str):
    artifact_key = _resolve_artifact_key(artifact_name)
    if not artifact_key:
        raise HTTPException(status_code=404, detail=f"Unsupported artifact_name={artifact_name}")

    bundle = _build_artifact_bundle(paper_id, run_id)
    entry = bundle.files.get(artifact_key)
    if not entry or not entry.exists:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact file not found for paper_id={paper_id}, run_id={run_id}, artifact_name={artifact_key}",
        )
    return entry


@app.get("/artifacts/{paper_id:path}/{run_id}", response_model=ArtifactBundleResponse)
def get_artifacts_for_run(paper_id: str, run_id: str):
    return _build_artifact_bundle(paper_id, run_id)

@app.post("/jobs/deepread", response_model=JobEnqueueResponse)
def enqueue_job(job_req: JobCreate):
    selection = normalize_persona_selection(
        persona_id=job_req.persona_id,
        reasoning_persona=job_req.reasoning_persona,
        profile_id=job_req.profile_id,
    )
    try:
        job_id = queue.enqueue(
            job_req.paper_id,
            job_req.clean_reindex,
            job_req.run_verify,
            job_req.persona_id,
            job_req.reasoning_persona,
            job_req.profile_id,
            job_req.parser_backend,
        )
    except DuplicateOpenJobError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "JOB_ALREADY_OPEN",
                "message": f"Open job already exists for paper_id={exc.paper_id}",
                "paper_id": exc.paper_id,
                "job_id": exc.job_id,
                "run_id": exc.run_id,
                "status": exc.status,
            },
        )
    except QueueBackpressureError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "QUEUE_FULL",
                "message": "Queued jobs limit reached",
                "queued_count": exc.queued_count,
                "limit": exc.limit,
            },
        )
    job = queue.get_job(job_id)
    _best_effort_log_user_action(
        paper_id=job_req.paper_id,
        action_type="deepread_enqueued",
        source="ui",
        payload={
            "job_id": job_id,
            "run_id": job.run_id if job else None,
            "persona_id": selection.persona_id,
            "reasoning_persona": selection.reasoning_persona,
            "profile_id": selection.profile_id,
            "parser_backend": job_req.parser_backend,
            "run_verify": bool(job_req.run_verify),
            "clean_reindex": bool(job_req.clean_reindex),
        },
    )
    return JobEnqueueResponse(job_id=job_id, run_id=job.run_id if job else None, status="queued")


@app.post("/ops/repair-stats", response_model=StatsRepairResponse)
def repair_stats(req: StatsRepairRequest):
    paper_ids = [str(pid).strip() for pid in (req.paper_ids or []) if str(pid).strip()]
    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids must include at least one id")

    try:
        results = seed_stats_reports_from_claimset(
            paper_ids=paper_ids,
            artifacts_root=Path(req.artifacts_root),
            run_id=req.run_id,
            max_checks=int(req.max_checks),
            write_bootstrap_meta=bool(req.write_bootstrap_meta),
            skip_existing=bool(req.skip_existing),
            dry_run=bool(req.dry_run),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"repair-stats failed: {exc}")

    serialized = [
        StatsRepairResult(
            paper_id=item.paper_id,
            run_id=item.run_id,
            status=item.status,  # type: ignore[arg-type]
            checks=int(item.checks),
            reason=str(item.reason),
        )
        for item in results
    ]
    for item in serialized:
        _best_effort_log_user_action(
            paper_id=item.paper_id,
            action_type="repair_stats",
            source="ui",
            payload={
                "run_id": item.run_id,
                "status": item.status,
                "checks": int(item.checks),
                "reason": str(item.reason),
                "skip_existing": bool(req.skip_existing),
                "write_bootstrap_meta": bool(req.write_bootstrap_meta),
                "dry_run": bool(req.dry_run),
                "max_checks": int(req.max_checks),
            },
        )
    seeded = sum(1 for item in serialized if item.status == "seeded")
    planned = sum(1 for item in serialized if item.status == "planned")
    skipped = sum(1 for item in serialized if item.status == "skipped")
    return StatsRepairResponse(
        seeded=seeded,
        planned=planned,
        skipped=skipped,
        total=len(serialized),
        results=serialized,
    )


@app.get("/jobs", response_model=list[JobStatus])
def list_jobs(
    paper_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    return _list_jobs(paper_id=paper_id, status=status, limit=limit)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _with_bootstrap_meta_path(job)


@app.get("/runs/{run_id}", response_model=JobStatus)
def get_run_status(run_id: str):
    job = _job_for_run_id(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")
    return _with_bootstrap_meta_path(job)


@app.get("/runs/{run_id}/timeline", response_model=RunTimelineResponse)
def get_run_timeline(run_id: str, limit: int = Query(default=500, ge=1, le=5000)):
    job = _job_for_run_id(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")
    events = _timeline_events_from_job(job, limit=limit)
    return RunTimelineResponse(run_id=run_id, job_id=job.job_id, paper_id=job.paper_id, events=events)


@app.get("/user-actions", response_model=UserActionListResponse)
def get_user_actions(
    paper_id: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    actions = list_user_actions(
        paper_id=paper_id,
        action_type=action_type,
        source=source,
        limit=limit,
    )
    return UserActionListResponse(actions=[UserActionEntry.model_validate(item) for item in actions])


@app.post("/user-actions", response_model=UserActionEntry)
def create_user_action(req: UserActionCreateRequest):
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    action_id = log_user_action(
        paper_id=req.paper_id,
        action_type=req.action_type,
        source=req.source,
        payload=req.payload if isinstance(req.payload, dict) else req.payload,
        ts=ts,
    )
    return UserActionEntry(
        action_id=action_id,
        ts=ts,
        paper_id=req.paper_id,
        action_type=req.action_type,
        source=req.source,
        payload=req.payload,
    )


@app.get("/jobs/{job_id}/bootstrap-meta", response_model=JobBootstrapMeta)
def get_job_bootstrap_meta(job_id: str):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    meta_path = _resolve_bootstrap_meta_path(job)
    if not meta_path:
        raise HTTPException(status_code=404, detail="bootstrap_meta not available")
    path = Path(meta_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="bootstrap_meta file not found")
    try:
        payload = sanitize_event_payload_for_log(json.loads(path.read_text(encoding="utf-8")))
        return JobBootstrapMeta.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse bootstrap_meta: {exc}")

@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    result = queue.cancel_job(job_id)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    if result == "already_terminal":
        raise HTTPException(status_code=409, detail="Job is already in a terminal state")
    return {"status": "cancelled"}

@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """SSE endpoint for job logs/status with Last-Event-ID replay support."""
    replay_cursor, replay_kind = _parse_last_event_cursor(request.headers.get("last-event-id"))

    async def event_generator():
        nonlocal replay_cursor, replay_kind
        artifact_announced = False
        while True:
            if await request.is_disconnected():
                break
                
            job = queue.get_job(job_id)
            if not job:
                yield {"event": "error", "data": "Job not found", "retry": 2000}
                break
            
            # Send status update
            enriched = _with_bootstrap_meta_path(job)
            yield {"event": "status", "data": json.dumps(enriched.model_dump(), default=str), "retry": 2000}

            if not artifact_announced and job.artifact_dir and Path(job.artifact_dir).exists():
                yield {
                    "event": "artifact_ready",
                    "data": json.dumps(
                        {
                            "paper_id": job.paper_id,
                            "run_id": job.run_id,
                            "artifact_dir": _public_path(job.artifact_dir),
                        }
                    ),
                    "retry": 2000,
                }
                artifact_announced = True

            log_lines = _read_log_lines(job.log_path)
            total_logs = len(log_lines)
            replay_cursor, replay_kind = _normalize_replay_cursor(
                replay_cursor=replay_cursor,
                replay_kind=replay_kind,
                total_logs=total_logs,
                is_terminal=job.status in TERMINAL_JOB_STATUSES,
            )

            if replay_cursor < total_logs:
                for idx in range(replay_cursor + 1, total_logs + 1):
                    yield {"id": f"log-{idx}", "event": "log", "data": log_lines[idx - 1], "retry": 2000}
                replay_cursor = total_logs
                replay_kind = "log"

            if job.status in TERMINAL_JOB_STATUSES:
                terminal_seq = total_logs + 1
                if replay_cursor < terminal_seq:
                    yield {"id": f"done-{terminal_seq}", "event": "done", "data": job.status, "retry": 2000}
                    replay_cursor = terminal_seq
                    replay_kind = "done"
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator(), ping=20)

app.include_router(obsidian.router)
app.include_router(artifact_feedback.router)
app.include_router(artifact_generation_outcomes.router)
app.include_router(feedback.router)
app.include_router(paper_notes.router)
app.include_router(project_context_links.router)
app.include_router(skills.router)
app.include_router(talk_packs.router)
app.include_router(meeting_packs.router)
app.include_router(image_evidence.router)
app.include_router(chart_packs.router)
app.include_router(method_comparisons.router)
app.include_router(paper_syntheses.router)
app.include_router(protocol_cards.router)
