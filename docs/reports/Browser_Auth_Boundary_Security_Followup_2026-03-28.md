# Browser Auth Boundary Security Follow-up

Status: Active review note
Date: 2026-04-07
Owner: Runtime/security maintainers
Canonical parent:
- `docs/runtime_security_env.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

Record the post-PR3 security posture after moving the browser UI to same-origin `/api/*` and removing frontend API secrets, then note the remaining private-beta follow-up checks that are still worth addressing.

This is not a new auth spec.

## 2026-04-07 Update

PR4 implemented the first hosted-beta hardening slice:

- optional thin HTTP Basic gate for `/ui`, `/ui/*`, browser-facing `/api/*`, UI assets, and `/health/ready`
- docs/OpenAPI exposure policy:
  - no beta gate: docs remain available by default
  - beta gate enabled: `/docs`, `/redoc`, and `/openapi.json` are disabled by default
  - explicit opt-in remains possible through `LATTICE_ENABLE_API_DOCS=true`

Repo anchors:

- `backend/main.py`
- `tests/test_beta_gate_api.py`
- `docs/runtime_security_env.md`

PR5 implemented the next browser hardening slice:

- `TrustedHostMiddleware` with an env-driven allowlist
- minimal default browser security headers
- HSTS only on HTTPS requests

Repo anchors:

- `backend/main.py`
- `tests/test_browser_security_headers_api.py`
- `docs/runtime_security_env.md`

PR6 implemented the first lightweight browser abuse/audit slice:

- same-origin browser write throttling for protected `/api/*` `POST` routes
- append-only internal `request_audits` logging for browser security denials and write requests

Repo anchors:

- `backend/main.py`
- `src/db_utils.py`
- `src/services/event_log.py`
- `tests/test_browser_request_audit_api.py`

## What PR3 Fixed

Current repo state:

- the browser no longer reads `VITE_API_KEY`
- the browser no longer sends `X-API-Key` directly
- browser requests use same-origin `/api/*`
- FastAPI rewrites `/api/*` to the existing backend routes and injects `X-API-Key` from server env when `LATTICE_API_KEY` is configured

Repo anchors:

- `frontend/src/app/lib/config.ts`
- `frontend/src/app/lib/api.ts`
- `frontend/vite.config.ts`
- `backend/main.py`
- `tests/test_api_key_auth.py`

## Current Judgment

PR3 fixes the highest-risk issue for private beta:

- backend secrets are no longer exposed to the browser bundle
- SSE and normal browser fetches now share the same server-side trust boundary

But PR3 is not a user-authentication system.

Current boundary:

- browser callers can reach `/ui`
- browser callers can reach same-origin `/api/*`
- the server decides when to inject `X-API-Key`

That is a reasonable private-beta posture for close-person sharing, but it is not sufficient if the deployment becomes broadly reachable on the public internet.

## Remaining Follow-up Checks

### Done in PR4. Thin beta gate in front of `/ui` and browser-facing `/api/*`

Why:

- same-origin routing removes browser secret leakage
- it does not decide who is allowed to use the UI

Current repo evidence:

- `LATTICE_BETA_PASSWORD` now enables an HTTP Basic gate in the FastAPI runtime
- the gate applies to browser-facing UI and same-origin API surfaces without introducing a user-account system

Current judgment:

- sufficient for close-person hosted beta
- still not a full authentication/authorization platform

### Done in PR4. Docs/OpenAPI exposure policy for hosted beta

Why:

- FastAPI docs can expose the full API surface and schemas to anyone who can reach the app

Current repo evidence:

- docs stay on by default only when no beta gate is configured
- gated runtimes disable docs by default unless `LATTICE_ENABLE_API_DOCS=true` is set explicitly
- when re-enabled in a gated runtime, docs inherit the same HTTP Basic gate

Current judgment:

- acceptable for the current hosted-beta target

### Done in PR5. Add host-header allowlisting before broader hosting

Why:

- browser-facing services should reject unexpected host headers early

Current repo evidence:

- `TrustedHostMiddleware` now protects the FastAPI app
- local/test defaults allow `localhost`, `127.0.0.1`, and `testserver`
- hosted deployments can set `LATTICE_ALLOWED_HOSTS` explicitly

Current judgment:

- good default posture for the current beta target
- operators still need to set the real public hostname(s) when deploying behind a proxy

### Done in PR5. Add a small security-header layer for `/ui`

Why:

- UI responses currently do not set common browser hardening headers

Current repo evidence:

- responses now include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`
- HTML responses now include a minimal CSP
- HSTS is only emitted on HTTPS requests

Current judgment:

- appropriate minimal hardening without risking a brittle frontend CSP rollout

### Done in PR7. Simplify browser-facing `/health/ready` in hosted beta by default

Why:

- path masking is on by default, which is good
- but `/health/ready` still reveals runtime topology and readiness details

Current repo evidence:

- without a beta gate, `GET /health/ready` remains available
- with `LATTICE_BETA_PASSWORD`, `GET /health/ready` still inherits the same HTTP Basic gate
- gated browser sessions now receive a narrowed summary instead of detailed internal check rows such as `runtime_db`, `storage_root`, `logs_root`, and `cache_root`
- trusted operators can explicitly opt back into the detailed browser payload with `LATTICE_BROWSER_DETAILED_RUNTIME_READINESS=true`

Current judgment:

- appropriate default for hosted beta because it keeps the readiness UI usable without exposing the full internal runtime topology
- local development still keeps the detailed payload by default

### Done in PR6. Add request-level throttling and internal request-audit logging

Why:

- queue backpressure limits queued jobs, but it is not the same as browser/API request throttling

Current repo evidence:

- browser-facing same-origin protected writes can now be throttled per client IP
- throttled requests return `429` with a `Retry-After` header
- the backend now writes append-only browser request audit rows into `request_audits`

Current judgment:

- sufficient for the current hosted-beta posture
- still intentionally narrow; this is not a full analytics or SIEM layer

## What Does Not Look Urgent Right Now

- CORS is not wildcard by default and already has a test for that posture
- browser bundle secret exposure was the main immediate risk and is now addressed
- path masking is already default-on and should stay that way

## Suggested Next PR Order

1. `PR8`: tighten CSP further only if deployment evidence shows it is safe
2. `PR9`: add a minimal operator-facing audit/metrics surface only if the current internal logs prove insufficient
3. `PR10`: revisit `/health` probe shape only if deployment posture changes beyond the current private beta

## Verification Notes

Repo-grounded checks used for this note:

```bash
python3 - <<'PY'
from backend.main import app
print({'docs_url': app.docs_url, 'redoc_url': app.redoc_url, 'openapi_url': app.openapi_url})
print([m.cls.__name__ for m in app.user_middleware])
PY

python3 - <<'PY'
from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app)
for path in ['/docs', '/redoc', '/openapi.json', '/health', '/health/ready', '/ui']:
    r = client.get(path)
    print(path, r.status_code)
PY
```
