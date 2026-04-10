from base64 import b64decode
from binascii import Error as BinasciiError
from collections import deque
from fastapi import FastAPI, HTTPException, Query, Request
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
from pathlib import Path
from typing import Any
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
    HomeWorkspaceSummaryResponse,
    RuntimeReadinessCheck,
    RuntimeReadinessResponse,
    PersonaListResponse,
    PersonaOption,
    RunTimelineEvent,
    RunTimelineResponse,
    StatsRepairRequest,
    StatsRepairResponse,
    StatsRepairResult,
    UserActionCreateRequest,
    UserActionEntry,
    UserActionListResponse,
)
from src.schemas.papers import PaperAccessSummary, PaperDetailResponse, PaperSummaryResponse
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
    load_rerank_gate_report,
    load_screening_guidance_index_artifact,
    load_screening_operator_guidance,
    load_screening_recommendation,
    load_screening_queue_artifact,
    load_screening_session,
    lock_research_dna,
    materialize_screening_guidance_artifact,
    log_interview_response,
    materialize_reranked_screening_queue,
    refine_query_version,
    run_pilot,
    screen_current_candidate_and_load_session,
    submit_screening_decision_and_load_next_candidate,
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
)
from src.services.path_masking import is_path_masking_enabled, mask_local_path
from src.services.paper_ops_summary import ArtifactSnapshotCache, build_ops_summary_for_paper_id
from src.services.fixture_visibility import is_test_fixture_paper_record, prefer_non_fixture_items
from src.services.runtime_readiness import collect_runtime_readiness, summarize_browser_runtime_readiness
from src.services.runtime_paths import artifact_paper_dir, artifact_run_dir, artifacts_root, frontend_runtime_dir
from src.services.stats_repair import seed_stats_reports_from_claimset
from starlette.datastructures import MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .routers import (
    chart_packs,
    feedback,
    image_evidence,
    meeting_packs,
    method_comparisons,
    obsidian,
    paper_syntheses,
    paper_notes,
    protocol_cards,
    skills,
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
        return ["http://127.0.0.1:8000", "http://localhost:8000"]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://127.0.0.1:8000", "http://localhost:8000"]


def _resolve_api_key() -> str:
    return (
        os.getenv("LATTICE_API_KEY")
        or os.getenv("PAPERPIPE_API_KEY")
        or ""
    ).strip()


def _resolve_beta_password() -> str:
    return (
        os.getenv("LATTICE_BETA_PASSWORD")
        or os.getenv("PAPERPIPE_BETA_PASSWORD")
        or ""
    ).strip()


def _resolve_beta_username() -> str:
    return (
        os.getenv("LATTICE_BETA_USERNAME")
        or os.getenv("PAPERPIPE_BETA_USERNAME")
        or "beta"
    ).strip() or "beta"


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
    "/jobs",
    "/paper-notes",
    "/paper-syntheses",
    "/papers",
    "/workspace-summary",
)


def _requires_api_key(method: str, path: str) -> bool:
    normalized_method = method.upper()
    normalized = path.rstrip("/") or "/"
    if normalized_method == "GET":
        return any(_path_matches(normalized, prefix) for prefix in _PRIVATE_DATA_ROUTE_PREFIXES)
    if normalized_method != "POST":
        return False

    if normalized in {"/jobs/deepread", "/feedback", "/obsidian/sync", "/ops/repair-stats", "/skills/run", "/user-actions"}:
        return True
    if normalized == "/research-dna" or normalized.startswith("/research-dna/"):
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


def _requires_beta_gate(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized == "/health/ready":
        return True
    if _requires_api_key("GET", normalized) or _requires_api_key("POST", normalized):
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
    if method.upper() != "POST" or not _is_browser_api_path(original_path):
        return False
    normalized = (rewritten_path or (original_path.rstrip("/") or "/")).rstrip("/") or "/"
    if normalized == "/user-actions":
        return False
    return _requires_api_key("POST", normalized)


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
    if method.upper() != "POST" or _is_browser_api_path(original_path):
        return False
    normalized = (original_path.rstrip("/") or "/").rstrip("/") or "/"
    if normalized == "/user-actions":
        return False
    return _requires_api_key("POST", normalized)


def _should_audit_browser_request(method: str, original_path: str, rewritten_path: str | None) -> bool:
    if method.upper() != "POST" or not _is_browser_api_path(original_path):
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
    if request.method.upper() != "POST" or not _is_browser_api_path(original_path):
        return True
    origin = _normalize_origin(request.headers.get("origin"))
    if not origin:
        return False
    if origin in _allowed_browser_origins_for_request(request):
        return True
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


API_DOCS_ENABLED = _resolve_api_docs_enabled()
_BROWSER_READ_LIMITER = _SlidingWindowLimiter()
_BROWSER_WRITE_LIMITER = _SlidingWindowLimiter()

app = FastAPI(
    title="Lattice API",
    version="3.1.0",
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url="/redoc" if API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if API_DOCS_ENABLED else None,
)

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


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    original_path = str(request.scope.get("path") or request.url.path or "/")
    rewritten_path = _rewrite_browser_api_path(original_path)
    client_ip = _client_ip_for_request(request)
    host = _host_for_request(request)
    if request.method.upper() != "OPTIONS" and _requires_beta_gate(original_path):
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
    current_path = str(request.scope.get("path") or request.url.path or "/")
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


def _list_visible_paper_items(*, raw_limit: int = 5000) -> list[dict[str, Any]]:
    conn = get_db_connection()
    papers = conn.execute(
        "SELECT * FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (raw_limit, 0),
    ).fetchall()
    conn.close()
    artifacts_path = artifacts_root()
    artifact_cache: ArtifactSnapshotCache = {}
    out: list[dict[str, Any]] = []
    for row in papers:
        item = dict(row)
        paper_id = str(item.get("paper_id") or "").strip()
        item["issues_state"] = _derive_paper_issues_state(item)
        item["ops_summary"] = build_ops_summary_for_paper_id(artifacts_path, paper_id, artifact_cache)
        out.append(item)
    return prefer_non_fixture_items(out, is_test_fixture_paper_record)


def _build_home_workspace_summary() -> HomeWorkspaceSummaryResponse:
    visible_papers = _list_visible_paper_items()

    blocked = 0
    needs_review = 0
    for item in visible_papers:
        ops_summary = item.get("ops_summary")
        if getattr(ops_summary, "state", None) == "action_needed":
            blocked += 1
            continue
        if _derive_paper_issues_state(item) != "clear":
            needs_review += 1

    saved_notes = 0
    structured_notes = 0
    latest_note_updated_at: str | None = None
    note_context_limited = False
    try:
        vault_path = paper_notes._resolve_vault_path()
        note_index = paper_notes._build_index(vault_path)
        note_items = note_index.items
        saved_notes = len(note_items)
        structured_notes = sum(1 for item in note_items if item.structured_state_present)
        latest_note_updated_at = max(
            (item.updated_at for item in note_items if item.updated_at),
            key=_parse_iso_timestamp_sort_key,
            default=None,
        )
    except Exception:
        note_context_limited = True

    return HomeWorkspaceSummaryResponse(
        saved_notes=saved_notes,
        structured_notes=structured_notes,
        needs_review=needs_review,
        blocked=blocked,
        latest_note_updated_at=latest_note_updated_at,
        note_context_limited=note_context_limited,
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


def _build_note_backed_paper_item(paper_id: str) -> tuple[dict[str, Any], Path | None] | None:
    try:
        vault_path = paper_notes._resolve_vault_path()
        index = paper_notes._build_index(vault_path)
        target = paper_notes._find_note_item_for_paper_id(index.items, paper_id)
        if not target:
            return None

        note_path = vault_path / target.note_path
        if not note_path.exists():
            return None

        content = paper_notes._safe_read_text(note_path)
        frontmatter, _ = paper_notes._parse_frontmatter(content)
        local_pdf_path = _resolve_note_backed_pdf_path(frontmatter)
        ops_summary = paper_notes._build_ops_summary(
            note_path,
            frontmatter,
            artifacts_path=artifacts_root(),
            artifact_cache={},
        )
        latest_run_id = (getattr(ops_summary, "latest_run_id", None) if ops_summary is not None else None) or None
        note_status = str(getattr(target, "status", "") or "").strip().upper()
        status = "completed" if target.structured_state_present or note_status == "INDEXED" else "not_started"
        item = {
            "paper_id": paper_id,
            "title": target.title or target.slug or paper_id,
            "authors": None,
            "year": None,
            "pdf_exists": local_pdf_path is not None,
            "pdf_path": _public_path(str(local_pdf_path)) if local_pdf_path is not None else None,
            "pdf_status": None,
            "status": status,
            "issues": 0,
            "issues_label": "No critical issues",
            "issues_state": "unavailable",
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
    except (FileNotFoundError, HTTPException):
        return None


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


def _build_artifact_bundle(paper_id: str, run_id: str) -> ArtifactBundleResponse:
    run_dir = _artifact_run_dir(paper_id, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Artifacts not found for paper_id={paper_id}, run_id={run_id}")

    files: dict[str, ArtifactFileEntry] = {}
    for key, filename in ARTIFACT_FILE_MAP.items():
        path = run_dir / filename
        entry = ArtifactFileEntry(
            exists=path.exists(),
            path=_public_path(str(path)) if path.exists() else None,
        )
        if path.exists() and path.suffix == ".json":
            entry.data = _safe_read_json(path)
        files[key] = entry

    return ArtifactBundleResponse(paper_id=paper_id, run_id=run_id, files=files)


def _resolve_artifact_key(artifact_name: str) -> str | None:
    normalized = artifact_name.strip().lower()
    return ARTIFACT_ALIAS_MAP.get(normalized)


def _latest_run_id_for_paper(paper_id: str) -> str | None:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT run_id, artifact_dir
            FROM jobs
            WHERE paper_id = ? AND run_id IS NOT NULL
            ORDER BY COALESCE(finished_at, started_at, created_at) DESC
            LIMIT 50
            """,
            (paper_id,),
        ).fetchall()
        for row in rows:
            run_id = str(row["run_id"] or "").strip()
            if not run_id:
                continue
            artifact_dir = str(row["artifact_dir"] or "").strip()
            if artifact_dir:
                if Path(artifact_dir).exists():
                    return run_id
            elif _artifact_run_dir(paper_id, run_id).exists():
                return run_id
    finally:
        conn.close()

    paper_dir = artifact_paper_dir(paper_id)
    if not paper_dir.exists():
        return None
    candidates = [p for p in paper_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None
    latest = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return latest.name


def _job_for_run_id(run_id: str) -> JobStatus | None:
    conn = get_db_connection()
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
            where.append("paper_id = ?")
            params.append(paper_id)
        if status:
            where.append("status = ?")
            params.append(status)

        query = "SELECT * FROM jobs"
        if where:
            query += " WHERE " + " AND ".join(where)

        rows = conn.execute(query, params).fetchall()
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
                payload = json.loads(raw)
                level = str(payload.get("level") or "INFO")
                evt = "error" if level.upper() == "ERROR" else "log"
                log_events.append(
                    RunTimelineEvent(
                        event=evt,
                        source="job_log",
                        ts=str(payload.get("timestamp") or ""),
                        stage=payload.get("stage"),
                        progress=int(payload.get("progress")) if payload.get("progress") is not None else None,
                        level=level,
                        message=payload.get("message"),
                    )
                )
            except Exception:
                log_events.append(
                    RunTimelineEvent(
                        event="log",
                        source="job_log",
                        raw=raw,
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
                message=job.error_message or job.status,
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
            message=job.error_message or job.status,
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
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
            )
            for check in readiness.checks
        ],
    )


@app.get("/api/health/ready", response_model=RuntimeReadinessResponse)
def api_health_ready():
    return health_ready()


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

@app.get("/papers")
def list_papers(
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[PaperSummaryResponse]:
    conn = get_db_connection()
    papers = conn.execute(
        "SELECT * FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    artifacts_path = artifacts_root()
    artifact_cache: ArtifactSnapshotCache = {}
    out = []
    for p in papers:
        item = dict(p)
        paper_id = str(item.get("paper_id") or "").strip()
        pdf_path = item.get("pdf_path")
        pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
        item["pdf_exists"] = pdf_exists
        item["pdf_path"] = _public_path(pdf_path)
        if not pdf_exists and pdf_path:
            item["pdf_status"] = "missing"
        item["issues_state"] = _derive_paper_issues_state(item)
        ops_summary = build_ops_summary_for_paper_id(artifacts_path, paper_id, artifact_cache)
        item["ops_summary"] = ops_summary
        item["latest_run_id"] = (
            getattr(ops_summary, "latest_run_id", None) if ops_summary is not None else None
        ) or _latest_run_id_for_paper(paper_id)
        item["access_summary"] = _build_paper_access_summary(item, paper_id=paper_id, pdf_exists=pdf_exists)
        _apply_escalation_response_fields(item)
        out.append(item)
    return out


@app.get("/workspace-summary", response_model=HomeWorkspaceSummaryResponse)
def get_workspace_summary() -> HomeWorkspaceSummaryResponse:
    return _build_home_workspace_summary()


@app.get("/papers/{paper_id}")
def get_paper(paper_id: str) -> PaperDetailResponse:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if not row:
        note_backed = _build_note_backed_paper_item(paper_id)
        if note_backed is not None:
            return note_backed[0]
        raise HTTPException(status_code=404, detail="Paper not found")

    item = dict(row)
    pdf_path = item.get("pdf_path")
    pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
    item["pdf_exists"] = pdf_exists
    item["pdf_path"] = _public_path(pdf_path)
    if not pdf_exists and pdf_path:
        item["pdf_status"] = "missing"
    item["issues_state"] = _derive_paper_issues_state(item)
    ops_summary = build_ops_summary_for_paper_id(artifacts_root(), paper_id, {})
    item["ops_summary"] = ops_summary
    item["latest_run_id"] = (
        getattr(ops_summary, "latest_run_id", None) if ops_summary is not None else None
    ) or _latest_run_id_for_paper(paper_id)
    item["access_summary"] = _build_paper_access_summary(item, paper_id=paper_id, pdf_exists=pdf_exists)
    _apply_escalation_response_fields(item)
    return item


@app.get("/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: str):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT paper_id, pdf_path FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    pdf_path: Path | None = None

    if row:
        raw_pdf_path = str(row["pdf_path"] or "").strip()
        if raw_pdf_path:
            candidate_pdf_path = Path(raw_pdf_path).expanduser()
            if candidate_pdf_path.exists() and candidate_pdf_path.is_file():
                pdf_path = candidate_pdf_path
            else:
                raise HTTPException(status_code=404, detail="PDF file not found")

    if pdf_path is None:
        note_backed = _build_note_backed_paper_item(paper_id)
        if note_backed is None:
            if row:
                raise HTTPException(status_code=404, detail="PDF path not registered for this paper")
            raise HTTPException(status_code=404, detail="Paper not found")
        _, note_pdf_path = note_backed
        if note_pdf_path is None:
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
        return JobBootstrapMeta.model_validate(json.loads(path.read_text(encoding="utf-8")))
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
app.include_router(feedback.router)
app.include_router(paper_notes.router)
app.include_router(skills.router)
app.include_router(meeting_packs.router)
app.include_router(image_evidence.router)
app.include_router(chart_packs.router)
app.include_router(method_comparisons.router)
app.include_router(paper_syntheses.router)
app.include_router(protocol_cards.router)
