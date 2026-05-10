# Conflicts

## Conflict: `/api/*` bridge bypasses protected root-route API-key behavior

Status: Confirmed
Files involved:
`backend/main.py:570`, `backend/main.py:1249`, `backend/main.py:1252`, `backend/main.py:1305`, `tests/test_api_key_auth.py:1246`
Type of conflict:
Route/auth contract conflict
Evidence:
Root private routes require `X-API-Key` when `LATTICE_API_KEY` is configured, but the middleware rewrites `/api/*` and injects the server-side key. A local probe showed `GET /jobs` returned 401 while `GET /api/jobs` returned 200 with no caller credential.
Runtime impact:
Any caller that can reach the app can request protected reads through `/api/*`; writes are also bridged when request-origin checks are satisfied.
Suggested fix:
Require API key/beta auth for non-trusted `/api/*` callers, or bind the bridge to the served UI shell with a stronger same-origin/session boundary before injecting the key.
Suggested test:
With `LATTICE_API_KEY` set, assert unauthenticated `GET /api/jobs`, `GET /api/papers`, and `GET /api/paper-notes` return 401/403 unless a trusted browser-shell condition is explicitly met.

## Conflict: Image Evidence request IDs conflict with filesystem-root ownership

Status: Confirmed
Files involved:
`src/schemas/image_evidence.py:240`, `src/schemas/image_evidence.py:257`, `src/image_evidence/service.py:55`, `src/image_evidence/store.py:17`, `src/image_evidence/store.py:169`
Type of conflict:
Schema/path-boundary conflict
Evidence:
`ImageEvidenceRequest.image_evidence_id` is unconstrained and is used directly to build `base / image_evidence_id`. A local reproduction with `../paperpipe-image-root-proof-outside/escape` wrote `image_evidence.json` outside the configured root.
Runtime impact:
A malformed registration request can write/read/delete managed image evidence files outside the image evidence root.
Suggested fix:
Constrain image evidence IDs with a strict pattern such as `^imageev_[A-Za-z0-9._-]+$`, reject separators and dot segments, and enforce resolved-path confinement in the store.
Suggested test:
POST `/image-evidence/register` with `../escape` and encoded separator variants; assert 422/400 and no filesystem writes outside root.

## Conflict: Backend paper synthesis lineage includes `visual_evidence_ledger`, frontend contract does not

Status: Confirmed
Files involved:
`src/schemas/paper_synthesis.py:17`, `src/schemas/paper_synthesis.py:26`, `src/paper_syntheses/service.py:264`, `frontend/src/app/lib/types.ts:995`, `frontend/src/app/components/ArtifactPanel.tsx:175`, `frontend/src/app/components/ArtifactPanel.tsx:184`
Type of conflict:
Frontend/backend type and display contract mismatch
Evidence:
Backend schema and service include `visual_evidence_ledger`; frontend type only allows `quality_gate | acceptance_contract`, and formatters fall through/mislabel unknown review artifacts.
Runtime impact:
Live compiled-knowledge lineage can be displayed as the wrong source/review artifact, weakening traceability.
Suggested fix:
Add `visual_evidence_ledger` to frontend source/review artifact unions and explicit display labels.
Suggested test:
Seed a synthesis manifest with `visual_evidence_ledger` in `source_refs` and `lineage_summary.review_artifact_kinds`; assert the UI renders “visual evidence ledger.”

## Conflict: Downloads watcher unmatched sentinel conflicts with canonical review_queue foreign key

Status: Confirmed
Files involved:
`src/downloads_watcher.py:20`, `src/downloads_watcher.py:163`, `src/downloads_watcher.py:295`, `src/downloads_watcher.py:300`, `scripts/init_db.py:81`, `src/db_utils.py:233`
Type of conflict:
Persistence schema conflict
Evidence:
Unmatched downloads enqueue `paper_id="__UNMATCHED__"`, but canonical `review_queue.paper_id` references `papers(paper_id)` and runtime connections enable FK checks.
Runtime impact:
Unmatched PDF triage records are not durably persisted under the canonical schema, while the watcher still returns `status="unmatched"`.
Suggested fix:
Create a real sentinel paper row, remove the FK assumption for unmatched review items, or introduce a separate unmatched-download review table/artifact.
Suggested test:
Use `scripts.init_db.init_db()` plus `src.db_utils.init_db()`, run an unmatched PDF through `process_downloaded_pdf()`, and assert a durable review item exists.

## Conflict: Frontend read fallback conflicts with live backend error truth

Status: Confirmed
Files involved:
`frontend/src/app/lib/config.ts:12`, `frontend/src/app/lib/api.ts:1135`, `frontend/src/app/lib/api.ts:1200`, `frontend/src/app/lib/api.ts:1261`, `frontend/src/app/pages/PaperNotesListPage.tsx:697`
Type of conflict:
Runtime behavior / test fixture conflict
Evidence:
`VITE_AUTO_MOCK_FALLBACK` defaults to enabled, and read helpers use mock data after caught fetch errors.
Runtime impact:
401/403/422/5xx responses and schema failures can render fixture data in user-facing review screens.
Suggested fix:
Limit fallback to explicit mock/dev mode or network-unreachable cases; do not fallback after a reached-backend HTTP error.
Suggested test:
Mock `/api/paper-notes` to return 401 and assert no mock notes render.

## Conflict: Cloud table fallback lacks the privacy preflight used by clinical extraction

Status: Confirmed
Files involved:
`src/agents/ingest_agent.py:230`, `src/ingest/cloud_table_fallback.py:199`, `backend/services/job_runner.py:1243`
Type of conflict:
Inference payload boundary conflict
Evidence:
Cloud table fallback sends page text to OpenAI when enabled, while the job runner privacy-preflight block covers clinical extraction later in the flow, not table fallback.
Runtime impact:
Potentially sensitive PDF excerpts can leave the local runtime without the payload classification/audit gate required by repo policy.
Suggested fix:
Classify and preflight cloud table payloads before request and persist lane metadata under `inference_lanes.cloud_table_fallback`.
Suggested test:
Enable cloud table fallback with blocking privacy preflight and assert no cloud request is made.

## Conflict: Artifact routes with non-final `{paper_id:path}` conflict with slash-bearing paper IDs

Status: Confirmed
Files involved:
`backend/main.py:5712`, `backend/main.py:5728`, `src/services/identity.py:95`
Type of conflict:
Route matching / identifier contract conflict
Evidence:
The file route `/artifacts/{paper_id:path}/{run_id}/{artifact_name}` is registered before the run route `/artifacts/{paper_id:path}/{run_id}`. Slash-bearing paper IDs are expected elsewhere and are converted to hashed artifact segments by `artifact_paper_segment()`. A route probe showed `/artifacts/foo/bar/run1` matches the file route as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`.
Runtime impact:
Run-bundle reads for paper IDs containing `/` can be routed as file reads with the wrong paper/run split.
Suggested fix:
Avoid non-final `{path}` parameters for paper IDs; use query parameters or the canonical hashed paper segment for artifact routes.
Suggested test:
Create a run for a DOI-like paper ID containing `/` and assert the run and file artifact endpoints both resolve the intended bundle.

## Conflict: Meeting-pack write fallback conflicts with documented live-backend contract

Status: Confirmed
Files involved:
`frontend/src/app/lib/api.ts:1225`, `frontend/src/app/lib/api.ts:1240`, `frontend/README.md:48`, `frontend/README.md:60`
Type of conflict:
Frontend runtime behavior / documented contract conflict
Evidence:
The README says write actions require a live backend unless `VITE_FORCE_MOCK=1`, but `generateMeetingPack()` catches proxy/backend availability failures and returns `createMockMeetingPack()`.
Runtime impact:
The UI can report a generated meeting pack even though no real artifact was persisted.
Suggested fix:
Disable write fallback unless explicit forced mock mode is active; surface a real error for unavailable backend writes.
Suggested test:
With forced mock disabled and backend unavailable, assert meeting-pack generation renders an error and no mock artifact.

## Conflict: Backend import health conflicts with import-time Ollama initialization

Status: Confirmed
Files involved:
`backend/routers/feedback.py:33`, `src/agents/feedback_retriever.py:43`, `src/agents/adapter.py:39`, `src/llm_provider.py:537`, `src/llm_provider.py:2480`
Type of conflict:
Import-time side effect / runtime dependency conflict
Evidence:
Importing `backend.main` imports the feedback router, which constructs `FeedbackRetriever()` at module load and initializes the Ollama provider. Route-listing import emitted an Ollama `/api/tags` request.
Runtime impact:
Backend import, route listing, and import-health checks can block/fail when Ollama is unavailable even if no feedback endpoint is called.
Suggested fix:
Lazy-initialize the feedback retriever/provider on first request or inject a provider factory that avoids network checks during import.
Suggested test:
Import `backend.main` with Ollama calls patched to fail and assert import completes without invoking Ollama.
