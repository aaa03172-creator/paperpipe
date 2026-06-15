# Lattice Runtime Security Env

Status: Active
Date: 2026-04-07
Owner: Runtime/security maintainers
Canonical runbook: `docs/runtime_security_env.md`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Recommended Local Defaults

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_MAX_CONCURRENT_JOBS="1"
export LATTICE_MAX_QUEUED_JOBS="20"
```

Path masking is now on by default. Only set `LATTICE_MASK_LOCAL_PATHS="false"` when a trusted local debugging flow truly needs raw absolute paths in API responses.

Start server:

```bash
lattice start
```

## Optional Cloud LLM Provider Keys

PaperPipe's cloud LLM path is now provider-aware:

- `llm.cloud.provider: "openai"` reads `OPENAI_API_KEY`
- `llm.cloud.provider: "anthropic"` reads `ANTHROPIC_API_KEY`

Recommended pattern:

- leave `llm.cloud.api_key` blank in normal setups
- set the matching provider env var instead
- keep `OPENAI_API_KEY` if you need OpenAI embeddings, because Anthropic is currently text/chat-only in the generic runtime path

## Optional Cloud Paper Storage And Metadata Adapters

Cloud paper/page development defaults to a no-credential mock storage adapter:

```bash
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

Allowed values:

- `mock`: default local/test mode; does not import GCP SDKs or require GCP credentials.
- `gcs`: GCS-ready mode for the cloud paper upload path; validates config and fails closed until the runtime dependency and real upload implementation are present.

When `PAPERPIPE_CLOUD_ADAPTER="gcs"`, set:

```bash
export PAPERPIPE_GCP_PROJECT_ID="your-gcp-project"
export PAPERPIPE_GCS_RAW_PDF_BUCKET="your-raw-pdf-bucket"
export PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="your-page-artifact-bucket"
```

Cloud paper metadata defaults to an in-memory store for local/test runs:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
```

Accepted values:

- `memory`: default demo-safe local mode; process-local and not production durable.
- `firestore`: durable metadata direction for the GCP production path.

When `PAPERPIPE_CLOUD_METADATA_STORE="firestore"`, set:

```bash
export PAPERPIPE_GCP_PROJECT_ID="your-gcp-project"
export PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="cloud_papers"
```

Install the optional cloud dependency in runtimes that actually use GCS:

```bash
python -m pip install ".[cloud]"
```

Compatibility aliases are accepted for early local experiments:

- `LATTICE_CLOUD_ADAPTER`
- `LATTICE_CLOUD_METADATA_STORE`
- `LATTICE_GCP_PROJECT_ID`
- `LATTICE_GCS_RAW_PDF_BUCKET`
- `LATTICE_GCS_PAGE_ARTIFACT_BUCKET`
- `LATTICE_FIRESTORE_CLOUD_PAPER_COLLECTION`

Do not expose these values through `VITE_*`, frontend config, public DTOs, logs intended for users, or persisted public cloud paper bundles. If GCS mode is selected before the dependency/credentials/implementation are ready, `/cloud/papers/upload-intents`, `/cloud/papers/{paper_id}/source-pdf`, or `/cloud/papers/{paper_id}/complete-upload` returns `503 CLOUD_PAPER_STORAGE_UNAVAILABLE` rather than leaking storage details or silently falling back to mock.

If Firestore metadata mode is selected before the dependency/credentials/configuration are ready, the backend must fail closed during the metadata-store initialization path rather than silently falling back to process-local metadata. For the challenge demo, Firestore Native `(default)` exists in `asia-northeast3` and the real Firestore + GCS smoke passed with collection `cloud_papers_demo`; keep `PAPERPIPE_CLOUD_METADATA_STORE="memory"` as the rollback path.

Current real-GCS slice:

- `CloudPaperMetadataStore` has an in-memory implementation and a Firestore implementation wired behind `PAPERPIPE_CLOUD_METADATA_STORE=firestore`. The Firestore store is the accepted production direction, but the June 5, 2026 challenge demo may keep process-local metadata if that is the safer stage path.
- `POST /cloud/papers/upload-intents` returns a redacted backend-mediated upload intent when GCS is configured.
- `POST /cloud/papers/{paper_id}/source-pdf` accepts a multipart `source_pdf` file and writes it to the configured raw PDF bucket through the backend.
- The backend writes server-computed metadata to each raw PDF object: `paper_id`, `lab_id`, and `source_pdf_sha256`.
- `POST /cloud/papers/{paper_id}/complete-upload` verifies the raw object exists and that its metadata checksum matches the upload intent before marking the paper ready.
- Missing objects and checksum mismatches return a blocked public bundle; they do not expose GCS refs, bucket names, signed URLs, credentials, or local paths.
- `complete-upload` writes the current schema-backed mock page-worker artifact to the configured page artifact bucket before marking an upload-intent-backed paper ready.
- Page processing currently runs through an in-process worker boundary. It records `running`, `ready`, or `failed` metadata states and writes page artifacts through the storage adapter; it is not yet a deployed Cloud Run/Pub/Sub worker.
- `GET /cloud/papers/{paper_id}/page` reads stored page artifacts for upload-intent-backed papers and returns only the normalized public page DTO.
- `POST /cloud/papers/{paper_id}/hydrate-local` reads the source PDF and page artifact through the storage adapter, writes `source/source.pdf`, `page/page.json`, and `cloud_hydration_manifest.json` under the local artifacts root, and returns only redacted hydration state.
- Hydration is idempotent for existing matching manifests; conflicting existing manifests are treated as stale and are not overwritten.
- Public responses include checksum, size, status, and ids only; they do not expose GCS object refs, bucket names, signed URLs, credentials, or local paths.

Beta cloud access headers:

- `X-PaperPipe-Actor-Id`
- `X-PaperPipe-Lab-Id`
- `X-PaperPipe-Role`: `lab_admin`, `maintainer`, `reviewer`, or `reader`
- `X-PaperPipe-Device-Registered`: boolean
- `X-PaperPipe-Session-Approved`: boolean
- `X-PaperPipe-Download-Allowed`: boolean

When the beta headers are absent, cloud read routes default to local reader compatibility: authenticated, same-lab, registered device, page-read only, no PDF download or hydrate permission. Cross-lab, unauthenticated, or untrusted-device contexts receive no paper actions. `hydrate-local` requires `X-PaperPipe-Download-Allowed: true` on a role that can download.

Cloud status reads, page reads, and hydrate/download actions write best-effort `user_actions` audit rows with source `cloud_papers`. These rows intentionally record actor/lab/role/device policy and paper/run ids only; they must not include GCS refs, bucket names, signed URLs, credentials, service accounts, local paths, or PDF/page contents.

This beta header policy is not production user authentication. Keep it behind the existing API-key/same-origin or beta gate until real user/session/lab identity is adopted.

## Reserved Privacy Preflight Pilot Flag

The reserved rollback flag for a future export/external-inference privacy preflight pilot is:

```bash
export LATTICE_PRIVACY_PREFLIGHT_MODE="off"
```

Allowed values:

- `off`: default and rollback value; no preflight gate should run
- `report_only`: emit a preflight report without blocking or mutating text
- `block_on_review`: block export or external inference when manual-review items exist

The first pilot must use the Pydantic contract in `src/schemas/privacy_preflight.py`. It must not silently mutate canonical state. Set `LATTICE_PRIVACY_PREFLIGHT_MODE="off"` to roll back the pilot.

Current narrow pilot scope:

- only the deep-read clinical extraction external-inference payload participates
- `report_only` records lane metadata and still runs clinical extraction
- `block_on_review` skips only the clinical extraction sidecar when review items exist
- local filesystem paths and signed private URLs are not sent as the clinical extraction `link` value
- `/health/ready` and same-origin `/api/health/ready` expose a `privacy_preflight_config` readiness check that reports only the effective mode, validity, rollback flag name, and pilot scope; invalid mode values are not echoed back.

## Protected API Authentication Scope

When `LATTICE_API_KEY` is set, these write endpoints require `X-API-Key`:

- `POST /jobs/deepread`
- `POST /jobs/{id}/cancel`
- `POST /ops/jobs/{id}/reclaim-stale`
- `POST /ops/jobs/{id}/requeue-reclaimed`
- `POST /ops/jobs/{id}/stale-incident-snapshot`
- `POST /feedback`
- `POST /obsidian/sync`
- `POST /ops/repair-stats`
- `POST /skills/run`
- `POST /user-actions`
- `POST /research-dna*`
- `POST /meeting-packs/*`
- `POST /image-evidence/*`
- `POST /chart-packs/*`
- `POST /cloud/*`
- `POST /method-comparisons/*`
- `POST /protocol-cards*`

These sensitive read endpoints also require `X-API-Key`:

- `GET /health/ready`
- `GET /ops*`
- `GET /papers*`
- `GET /workspace-summary`
- `GET /personas`
- `GET /obsidian/*`
- `GET /paper-notes*`
- `GET /meeting-packs*`
- `GET /method-comparisons*`
- `GET /chart-packs*`
- `GET /cloud*`
- `GET /protocol-cards*`
- `GET /image-evidence*`
- `GET /paper-syntheses*`
- `GET /research-dna/*`
- `GET /feedback`
- `GET /papers/{paper_id}/pdf`
- `GET /artifacts*`
- `GET /jobs*`
- `GET /runs/{run_id}*`
- `GET /user-actions`

Browser-facing `/ui` note:

- The browser UI should call same-origin `/api/*` only.
- FastAPI rewrites `/api/*` to the existing backend routes server-side and injects `X-API-Key` from server env when `LATTICE_API_KEY` is configured.
- Browser-facing `/api/*` `POST` requests now require an allowed `Origin` header. Same-origin backend runtime requests are accepted automatically; when the backend itself is running on loopback, local Vite/dev origins on `localhost`, `127.0.0.1`, or `::1` are allowed by default, and hosted deployments should set `LATTICE_CORS_ALLOW_ORIGINS` explicitly.
- Do not place `LATTICE_API_KEY` or any replacement frontend API secret in `VITE_*` env vars.
- Direct root-route access to the same private data surfaces is now also protected when `LATTICE_API_KEY` is set. `/health` remains the only public probe by default.

Hosted beta follow-up:

- PR3 removes browser-exposed secrets, but it does not create end-user authentication for `/ui` or same-origin `/api/*`.
- For internet-facing or shared private beta deployments, review the remaining follow-up note in `docs/reports/Browser_Auth_Boundary_Security_Followup_2026-03-28.md`.
- Example reverse-proxy templates that add an outer IP allowlist + Basic-auth layer live in `packaging/reverse_proxy/`.

## Thin Hosted-Beta Gate

For a close-person hosted beta, you can add a thin HTTP Basic gate in front of browser-facing surfaces:

```bash
export LATTICE_BETA_PASSWORD="change-me"
# optional; defaults to "beta"
export LATTICE_BETA_USERNAME="beta"
export LATTICE_BETA_AUTH_RATE_LIMIT_COUNT="20"
export LATTICE_BETA_AUTH_RATE_LIMIT_WINDOW_SECONDS="300"
```

When `LATTICE_BETA_PASSWORD` is set:

- `/ui` and `/ui/*` require HTTP Basic auth
- browser-facing same-origin `/api/*` requires HTTP Basic auth
- UI assets (`/assets/*`, `/ui-assets/*`, `/sample.pdf`, `/vite.svg`, `/favicon.ico`) require HTTP Basic auth
- `/health/ready` requires HTTP Basic auth
- `/health/ready` defaults to a browser-safe summary instead of the full internal runtime topology
- repeated invalid beta-password attempts are rate-limited per client IP before the request reaches protected surfaces
- `/health` stays public for lightweight probes

This is intentionally not a user-account system. It is a thin beta gate only.

Invalid beta-auth throttling:

- applies only when `LATTICE_BETA_PASSWORD` is set
- defaults to `20` failed attempts per `300` seconds per client IP
- returns:
  - `429`
  - `error_code: BETA_AUTH_RATE_LIMITED`
  - `Retry-After: <seconds>`
- set `LATTICE_BETA_AUTH_RATE_LIMIT_COUNT=0` to disable the app-side limiter if an outer proxy already owns this policy

To opt a gated browser session back into the full readiness payload:

```bash
export LATTICE_BROWSER_DETAILED_RUNTIME_READINESS="true"
```

- Without a beta gate, detailed runtime readiness stays enabled by default.
- With a beta gate, detailed runtime readiness is off by default so browser users only see a narrowed summary.

## API Docs Exposure Policy

- Without a beta gate, FastAPI docs stay available by default.
- When `LATTICE_BETA_PASSWORD` is set, `/docs`, `/redoc`, and `/openapi.json` are disabled by default.
- To re-enable docs explicitly in a gated environment:

```bash
export LATTICE_ENABLE_API_DOCS="true"
```

If docs are re-enabled while the beta gate is active, they inherit the same HTTP Basic gate.

## Host Allowlist

Browser-facing runtimes should restrict accepted `Host` headers:

```bash
export LATTICE_ALLOWED_HOSTS="localhost,127.0.0.1,beta.example.com"
```

- When unset, local/test defaults allow `localhost`, `127.0.0.1`, and `testserver`.
- When set, the allowlist is taken from the comma-separated env value.
- Use the exact public hostname(s) that your reverse proxy or hosted runtime will receive.

## Beta Client IP Allowlist

Hosted private-beta runtimes can also restrict browser/protected surfaces to a small client-IP allowlist:

```bash
export LATTICE_BETA_ALLOWED_IPS="203.0.113.7,198.51.100.0/24"
```

- Scope: every route that participates in the beta/protected access boundary, including `/ui`, `/api/*`, UI assets, `/health/ready`, and direct protected root routes such as `/papers` or `/jobs`.
- The allowlist is checked before the HTTP Basic challenge or API-key check, so disallowed clients are rejected with `403` immediately.
- Client IP resolution uses `LATTICE_TRUSTED_PROXY_IPS` when present; otherwise the direct socket peer is used.
- Values may be exact IPs or CIDR blocks. Keep the list small and deployment-specific.
- Disallowed requests return:
  - `403`
  - `error_code: IP_NOT_ALLOWED`

## Response Security Headers

The backend now adds a small default browser hardening set:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

For HTML responses, the backend also adds a minimal CSP:

- `Content-Security-Policy: base-uri 'self'; frame-ancestors 'none'; form-action 'self'; object-src 'none'`

For HTTPS requests, the backend adds:

- `Strict-Transport-Security: max-age=63072000; includeSubDomains`

This is intentionally minimal. It is a browser hardening layer, not a full CSP lockdown.

## Browser Write Rate Limiting

Hosted beta runtimes can throttle browser-facing same-origin writes:

```bash
export LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT="30"
export LATTICE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS="60"
```

- Scope: browser-facing same-origin `/api/*` `POST` requests that map to protected write routes.
- Excluded: `/api/user-actions` is intentionally excluded so UI telemetry does not become the first throttling bottleneck.
- The same limit also applies to direct protected root `POST` requests (for example `/jobs/deepread`, `/meeting-packs/generate`, `/paper-notes/import-pdf`) once the caller has passed the beta gate and, when configured, supplied a valid `X-API-Key`, so authenticated root-route clients cannot bypass the hosted-beta write throttle.
- Default behavior:
  - when `LATTICE_BETA_PASSWORD` is set, the default write limit is `30` requests per `60` seconds per client IP
  - without a beta gate, the default is disabled unless you set the env explicitly
- When exceeded, the backend returns:
  - `429`
  - `error_code: BROWSER_WRITE_RATE_LIMITED`
  - `Retry-After` header

Direct protected root `POST` throttling returns:

- `429`
- `error_code: PROTECTED_WRITE_RATE_LIMITED`
- `Retry-After` header

## Browser Read Rate Limiting

Hosted beta runtimes can also throttle browser-facing same-origin protected reads:

```bash
export LATTICE_BROWSER_READ_RATE_LIMIT_COUNT="300"
export LATTICE_BROWSER_READ_RATE_LIMIT_WINDOW_SECONDS="60"
```

- Scope: browser-facing same-origin `/api/*` `GET` requests that map to protected read routes.
- The same limit also applies to direct protected root `GET` requests (for example `/papers`, `/jobs`, `/meeting-packs`) once the caller has passed the beta gate and, when configured, supplied a valid `X-API-Key`, so authenticated root-route clients cannot bypass the hosted-beta read throttle.
- Default behavior:
  - when `LATTICE_BETA_PASSWORD` is set, the default read limit is `300` requests per `60` seconds per client IP
  - without a beta gate, the default is disabled unless you set the env explicitly
- When exceeded, the backend returns:
  - `429`
  - `error_code: BROWSER_READ_RATE_LIMITED`
  - `Retry-After` header

Direct protected root `GET` throttling returns:

- `429`
- `error_code: PROTECTED_READ_RATE_LIMITED`
- `Retry-After` header

## Trusted Proxy Headers

Only trust `X-Forwarded-For` when requests arrive from an explicit trusted proxy:

```bash
export LATTICE_TRUSTED_PROXY_IPS="127.0.0.1,10.0.0.10"
```

- When unset, the backend ignores `X-Forwarded-For` and uses the direct client address for rate limiting and browser request audits.
- Set this only to the exact proxy IPs or hosts that sit immediately in front of the app.

## Browser Request Audit Logging

The backend now keeps an append-only internal request-audit trail for browser-facing security events and write requests.

Optional explicit env:

```bash
export LATTICE_BROWSER_AUDIT_LOGGING="true"
```

Default behavior:

- enabled automatically when the beta gate is on
- enabled automatically when browser write throttling is configured
- otherwise off unless explicitly enabled

Current audit scope:

- browser-facing same-origin write requests (`/api/*` `POST`, excluding `/api/user-actions`)
- browser beta-gate denials

The audit trail is stored internally in the runtime DB as `request_audits`. This is intentionally separate from `user_actions`.

Event and audit payloads are sanitized at the event-log storage boundary. If a future caller accidentally passes auth headers, cookies, password/token/API-key fields, OpenAI-style `sk-*` strings, or database URLs inside `payload`, those values are stored as `<redacted>` while non-sensitive context such as scope, status, and rate-limit metadata is preserved. The same sanitizer also applies to job-event messages, job status error messages, worker progress JSONL logs, and execution-run params/metrics. List helpers, timeline APIs, SSE job-log replay, `run_meta.json` artifact reads, and `bootstrap_meta.json` reads sanitize again on read so older local rows or legacy log files are not re-exposed through APIs. HTTP error `detail` payloads are also sanitized before response so exception text cannot echo secret-like values or raw absolute local paths to the browser. Request validation errors keep `type`/`loc`/`msg` diagnostics but drop FastAPI's raw `input` echo.

Feedback corrections are also sanitized before storage and before accepted feedback is indexed for future similar-feedback prompt reuse. This keeps operator-entered API keys, auth headers, and database URLs out of `storage/feedback.jsonl`, the local feedback index, `/feedback` responses, and Deep Read similar-feedback overlays. Read paths sanitize again so older local feedback rows or legacy index previews are masked before reuse.

Artifact lifecycle review logs use the same boundary. Artifact review feedback and generation outcome notes/metadata are sanitized before JSONL storage and again on read, so operator-entered secrets are not preserved in `artifact_review_feedback.jsonl`, `artifact_generation_outcomes.jsonl`, or their API responses.

Project context link decisions are also raw-memory records. Link notes and metadata are sanitized before `storage/project_context_links.jsonl` append and again on read, so project-scoping decisions cannot accidentally preserve API keys, auth headers, passwords, or database URLs in the JSONL log or `/project-context-links` responses.

Research DNA append-only logs follow the same raw-memory boundary. Interview answers, screening notes, and approval/run audit fields are sanitized before `logs/interview.jsonl`, `logs/screening.jsonl`, `logs/runs.jsonl`, or `logs/approval_audit.jsonl` writes. Research DNA API read paths and Meeting Pack screening-source resolution sanitize log rows again before legacy notes can be returned or reused. Screening queue artifacts and canonical Research DNA profile content are not rewritten by this log sanitizer.

Project Memory workspaces and items are raw-memory records, not canonical paper evidence. Workspace title/objective/notes and memory item content/link notes are sanitized before `project.json` or `memory.jsonl` writes and again on read, so project scratchpads cannot durably store accidental auth headers, API keys, or database URLs.

Protocol attachment raw source is preserved for review, but attachment-derived user surfaces are sanitized. Draft responses, attachment bundle excerpts, and `/protocol-cards/attachments/{id}/extracted-markdown` mask secret-like strings before returning to the browser. The raw uploaded source download remains raw by design and stays behind the protected protocol-card route boundary.

Paper Notes PDF import keeps the uploaded PDF as raw source, but filename/PDF-title-derived metadata is sanitized before it becomes the imported note title, slug seed, DB title, or import API response. This prevents accidental API keys or auth tokens in local filenames or PDF metadata from becoming durable user-facing note metadata.

Paper Notes operator state is raw memory, not canonical paper state. Operator note text is sanitized before storage and again on read, so quick private annotations do not preserve accidental auth headers, API keys, or database URLs in `.pp/operator_state/*.json` or Paper Notes API responses.

Error contract:

```json
{
  "error_code": "UNAUTHORIZED",
  "message": "Missing or invalid X-API-Key"
}
```

## Path Masking Scope

By default, API responses mask absolute local paths (for example `pdf_path`, `artifact_dir`, `log_path`, `bootstrap_meta_path`, and the Obsidian sync file path).

Explicit opt-out:

```bash
export LATTICE_MASK_LOCAL_PATHS="false"
```

## Paper Notes Import Size Limit

Local PDF import now enforces a maximum upload size before reading the full file into memory:

```bash
export LATTICE_MAX_IMPORT_PDF_BYTES="26214400"
```

- Default: `26214400` bytes (`25 MiB`)
- Requests above the limit return `413`

## Legacy Env Aliases

- `PAPERPIPE_API_KEY`
- `PAPERPIPE_ALLOWED_HOSTS`
- `PAPERPIPE_BETA_PASSWORD`
- `PAPERPIPE_BETA_ALLOWED_IPS`
- `PAPERPIPE_BETA_AUTH_RATE_LIMIT_COUNT`
- `PAPERPIPE_BETA_AUTH_RATE_LIMIT_WINDOW_SECONDS`
- `PAPERPIPE_BETA_USERNAME`
- `PAPERPIPE_BROWSER_DETAILED_RUNTIME_READINESS`
- `PAPERPIPE_BROWSER_AUDIT_LOGGING`
- `PAPERPIPE_BROWSER_READ_RATE_LIMIT_COUNT`
- `PAPERPIPE_BROWSER_READ_RATE_LIMIT_WINDOW_SECONDS`
- `PAPERPIPE_BROWSER_WRITE_RATE_LIMIT_COUNT`
- `PAPERPIPE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS`
- `PAPERPIPE_ENABLE_API_DOCS`
- `PAPERPIPE_MAX_IMPORT_PDF_BYTES`
- `PAPERPIPE_MASK_LOCAL_PATHS`
- `PAPERPIPE_CORS_ALLOW_ORIGINS`
- `PAPERPIPE_MAX_CONCURRENT_JOBS`
- `PAPERPIPE_MAX_QUEUED_JOBS`
- `PAPERPIPE_TRUSTED_PROXY_IPS`
