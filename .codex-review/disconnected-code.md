# Disconnected Code

## Disconnected or suspicious code: Image Evidence caller-supplied ID is connected to writes but not validation

Status: Confirmed
File/line:
`src/schemas/image_evidence.py:240`, `src/image_evidence/service.py:55`, `src/image_evidence/store.py:17`
Expected connection:
Route/request IDs should pass through schema validation and store root confinement before filesystem use.
Actual connection:
The ID is only stripped, then used as a directory segment.
Evidence:
Local reproduction wrote outside the configured root using `image_evidence_id="../paperpipe-image-root-proof-outside/escape"`.
Impact:
Broken root confinement for a production-facing register endpoint.
Suggested fix:
Add strict ID validation and store-level path confinement.
Suggested test:
Path traversal and separator regression tests for POST/register and derivative read routes.

## Disconnected or suspicious code: `/api/*` bridge lacks caller trust proof before server-side key injection

Status: Confirmed
File/line:
`backend/main.py:570`, `backend/main.py:1249`, `backend/main.py:1252`
Expected connection:
The browser bridge should be connected to a trusted same-origin UI context or require caller auth.
Actual connection:
The middleware rewrites and injects the server-side key for `/api/*` when `expected_key` exists.
Evidence:
`GET /api/jobs` returned 200 without caller key while `GET /jobs` returned 401.
Impact:
Protected data can be reachable through the bridge.
Suggested fix:
Require API key/beta auth for direct callers, or add a real same-origin/session guard before injection.
Suggested test:
Unauthenticated `/api/*` protected route regression tests.

## Disconnected or suspicious code: Downloads watcher does not persist unmatched review queue item under canonical schema

Status: Confirmed
File/line:
`src/downloads_watcher.py:295`, `src/downloads_watcher.py:300`, `src/downloads_watcher.py:163`, `scripts/init_db.py:81`
Expected connection:
Unmatched PDF handling should create a durable operator triage item.
Actual connection:
The sentinel paper ID conflicts with the `review_queue.paper_id` FK and enqueue failure is swallowed.
Evidence:
Subagent canonical-schema reproduction yielded `review_queue_count=0` and FK failure while returning `status=unmatched`.
Impact:
Unmatched PDFs can be moved aside without durable follow-up.
Suggested fix:
Use a separate unmatched-download review store or insert a valid sentinel paper row before enqueue.
Suggested test:
Canonical-schema unmatched download test.

## Disconnected or suspicious code: Downloads watcher only handles created events, not temp-file rename completion

Status: Needs verification
File/line:
`src/downloads_watcher.py:347`, `src/downloads_watcher.py:351`, `src/downloads_watcher.py:373`
Expected connection:
Browser downloads that complete by renaming `.crdownload`/`.part` to `.pdf` should be processed.
Actual connection:
Only `on_created` is implemented; no `on_moved` handler was found.
Evidence:
Subagent searched watcher code and found no `on_moved`/`on_modified` path for the final PDF.
Impact:
Common browser download completion flows may be silently skipped.
Suggested fix:
Factor candidate handling into a helper and call it from `on_created` and `on_moved` using `event.dest_path`.
Suggested test:
Simulate temp-to-PDF rename and assert processing runs once after stable completion.

## Disconnected or suspicious code: Failed Deep Read artifact directory may not be connected to job row

Status: Confirmed
File/line:
`backend/services/job_runner.py:1047`, `backend/services/job_runner.py:1792`, `src/jobs/worker.py:164`, `src/jobs/worker.py:186`
Expected connection:
Any run that creates an artifact directory should persist that directory on the job row for diagnostics and bootstrap metadata access.
Actual connection:
Worker stores `artifact_dir` on success; failure path depends on result data and the runner's failure result may not include it.
Evidence:
Runner creates and writes failure artifacts, then worker failed-update omits `artifact_dir` unless returned.
Impact:
Failure diagnostics can exist on disk but be unreachable through job APIs.
Suggested fix:
Persist `artifact_dir` immediately after creation or always return it on failure/cancel.
Suggested test:
Force failure after artifact directory creation and assert `/jobs/{id}` includes `artifact_dir`.

## Disconnected or suspicious code: Paper synthesis visual evidence lineage lacks frontend display handling

Status: Confirmed
File/line:
`frontend/src/app/lib/types.ts:995`, `frontend/src/app/components/ArtifactPanel.tsx:175`, `frontend/src/app/components/ArtifactPanel.tsx:184`
Expected connection:
Every backend lineage kind emitted by `PaperSynthesis` should be represented by frontend types and labels.
Actual connection:
`visual_evidence_ledger` is emitted by backend but not included in frontend union/formatters.
Evidence:
Backend service adds source ref at `src/paper_syntheses/service.py:264`; frontend only knows two review artifact kinds.
Impact:
Lineage UI can mislabel evidence review artifacts.
Suggested fix:
Add `visual_evidence_ledger` frontend type and label coverage.
Suggested test:
UI contract/e2e fixture with visual evidence ledger lineage.

## Disconnected or suspicious code: Research DNA API is registered but not reachable from current frontend shell

Status: Needs verification
File/line:
`backend/main.py:4711`, `frontend/src/App.tsx:84`
Expected connection:
If Research DNA is user-facing in this build, a route or UI entry should reach it.
Actual connection:
Multiple backend routes are registered, but no corresponding React route was found in `App.tsx`.
Evidence:
Route listing shows `/research-dna...`; frontend route list has papers/artifacts/readiness/workbench but no research DNA route.
Impact:
Feature may be API-only or partially wired for UI.
Suggested fix:
Clarify intended exposure; add frontend route/link only if product-facing.
Suggested test:
Frontend route reachability test if intended user-facing.

## Disconnected or suspicious code: Artifact run endpoint is not unambiguously reachable for slash-bearing paper IDs

Status: Confirmed
File/line:
`backend/main.py:5712`, `backend/main.py:5728`, `src/services/identity.py:95`
Expected connection:
Artifact run and artifact file routes should both resolve valid paper IDs, including DOI-like IDs containing `/`.
Actual connection:
The file route with `{paper_id:path}` is registered before the run route, so a slash-bearing paper ID path can be parsed as a shorter paper ID plus run/file segments.
Evidence:
A route probe matched `/artifacts/foo/bar/run1` to the file route as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`.
Impact:
Valid artifact bundles can be unreachable or misread through the run endpoint.
Suggested fix:
Move paper identity to a query parameter or canonical hashed segment; avoid non-final path converters for ambiguous identifiers.
Suggested test:
Create an artifact for `10.1234/example.paper` and assert both bundle and file reads retrieve the intended artifact.

## Disconnected or suspicious code: Feedback retriever is connected at import time instead of request time

Status: Confirmed
File/line:
`backend/routers/feedback.py:33`, `src/agents/feedback_retriever.py:43`, `src/agents/adapter.py:39`
Expected connection:
LLM/Ollama provider initialization should happen when a feedback route actually needs retrieval.
Actual connection:
The feedback router constructs the retriever during module import, initializing the Ollama provider while importing `backend.main`.
Evidence:
Route-listing import emitted an Ollama `/api/tags` request before any feedback endpoint was invoked.
Impact:
Import-health, tests, and startup checks depend on a live Ollama service unnecessarily.
Suggested fix:
Use a lazy dependency/factory for the feedback retriever and cache it after first successful construction.
Suggested test:
Patch Ollama client calls to fail, import `backend.main`, and assert no call happens until the feedback endpoint is exercised.

## Disconnected or suspicious code: Meeting-pack write action can report a mock artifact

Status: Confirmed
File/line:
`frontend/src/app/lib/api.ts:1225`, `frontend/src/app/lib/api.ts:1240`, `frontend/README.md:48`
Expected connection:
Meeting-pack generation should connect to a live backend write path unless forced mock mode is explicitly enabled.
Actual connection:
On backend/proxy availability failure, the API helper returns `createMockMeetingPack()`.
Evidence:
The README limits fallback to read/inspection behavior, but the write helper still creates a mock success object.
Impact:
Users can believe an export/generation was persisted when no backend artifact exists.
Suggested fix:
Return an error for write failures outside explicit forced mock mode.
Suggested test:
Run the meeting-pack generation flow with backend unavailable and forced mock disabled; assert error UI rather than mock output.
