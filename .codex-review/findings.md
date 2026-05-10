# Findings

## Finding 1: `/api/*` bridge bypasses protected root-route API-key behavior

Severity: P1
Confidence: High
Status: Confirmed
Category: Conflict
File/line:
`backend/main.py:570`; `backend/main.py:1249`; `backend/main.py:1252`; `backend/main.py:1305`
Related files/call sites:
`frontend/src/app/lib/config.ts:26`; `tests/test_api_key_auth.py:1246`
Issue:
The middleware rewrites `/api/*` to root API paths and injects the server-side API key before final auth checks. This means protected root routes can be accessed through the bridge without caller credentials.
Evidence:
Root private paths require API keys through `_requires_api_key()`. For `/api/*`, `_rewrite_browser_api_path()` rewrites the path, then `MutableHeaders(scope=request.scope)["x-api-key"] = expected_key` injects the configured key. A local probe with `LATTICE_API_KEY=secret-key` returned 401 for `GET /jobs` and 200 for `GET /api/jobs`.
Why it matters:
If the backend is reachable by non-UI callers, protected reads and some writes are exposed through the browser bridge despite the root-route API-key contract.
Suggested fix:
Require API key/beta auth for non-trusted `/api/*` callers before server-side injection, or bind the bridge to a stronger same-origin/session check.
Suggested test:
With `LATTICE_API_KEY` set, assert unauthenticated `GET /api/jobs`, `/api/papers`, and `/api/paper-notes` fail unless an explicitly trusted browser-shell condition is met.

## Finding 2: Caller-supplied Image Evidence IDs can escape the storage root

Severity: P1
Confidence: High
Status: Confirmed
Category: Missing wiring
File/line:
`src/schemas/image_evidence.py:240`; `src/schemas/image_evidence.py:257`; `src/image_evidence/service.py:55`; `src/image_evidence/store.py:17`; `src/image_evidence/store.py:169`
Related files/call sites:
`backend/routers/image_evidence.py:34`; `tests/test_image_evidence_api.py`
Issue:
`ImageEvidenceRequest.image_evidence_id` is unconstrained and flows directly into filesystem path construction.
Evidence:
The schema only strips `image_evidence_id`. The service selects `request.image_evidence_id` when provided. The store returns `base / image_evidence_id` and writes `image_evidence.json` there. A local reproduction with `../paperpipe-image-root-proof-outside/escape` wrote outside the configured root.
Why it matters:
A malformed production request can write or affect files outside the image evidence artifact root.
Suggested fix:
Validate IDs with a strict allowlist, reject separators/dot segments, and enforce `resolved_path.relative_to(root)` in the store.
Suggested test:
POST traversal IDs and encoded separator variants to `/image-evidence/register`; assert 400/422 and no out-of-root writes.

## Finding 3: Unmatched downloaded PDFs are not durably queued under the canonical schema

Severity: P1
Confidence: High
Status: Confirmed
Category: Conflict
File/line:
`src/downloads_watcher.py:20`; `src/downloads_watcher.py:163`; `src/downloads_watcher.py:295`; `src/downloads_watcher.py:300`; `scripts/init_db.py:81`; `src/db_utils.py:233`
Related files/call sites:
`tests/test_downloads_watcher.py`; CLI watch-downloads path.
Issue:
The unmatched-download flow enqueues `paper_id="__UNMATCHED__"`, but the canonical `review_queue.paper_id` has a foreign key to `papers(paper_id)`.
Evidence:
The watcher defines `UNMATCHED_SENTINEL_PAPER_ID = "__UNMATCHED__"` and uses it for unmatched/no-candidate flows. Canonical schema creates `review_queue` with a paper FK and DB connections enable FK checks. `_enqueue_pdf_match_review()` catches the exception and returns false, while the caller still returns `status="unmatched"`. Subagent reproduction observed FK failure and `review_queue_count=0`.
Why it matters:
The user-facing promise of a manual follow-up queue is broken for unmatched PDFs; files can be moved to `_unmatched` without durable triage.
Suggested fix:
Use a separate unmatched-download review table/artifact or create a valid sentinel paper row before enqueue.
Suggested test:
Run unmatched processing against a DB initialized by `scripts.init_db.init_db()` plus `src.db_utils.init_db()` and assert a durable triage item exists.

## Finding 4: Frontend can render mock data after real backend/auth failures

Severity: P1
Confidence: High
Status: Resolved in current branch
Category: Functional behavior
File/line:
`frontend/src/app/lib/config.ts:12`; `frontend/src/app/lib/api.ts:1135`; `frontend/src/app/lib/api.ts:1200`; `frontend/src/app/lib/api.ts:1261`; `frontend/src/app/pages/PaperNotesListPage.tsx:697`
Related files/call sites:
`frontend/src/app/lib/mock.ts`; `frontend/e2e/mock.spec.ts`; backend private routes.
Issue:
`VITE_AUTO_MOCK_FALLBACK` defaults to true, and shared read helpers can substitute fixtures after any caught read failure.
Evidence:
`autoMockFallback` is true when env is unset. Read helpers call `withMockFallback()`/similar patterns and pages install `result.data` into UI state.
Current branch note:
`frontend/src/app/lib/api.ts` now routes fallback decisions through `canFallbackForReadError()`, which blocks reached-backend HTTP errors and only allows non-HTTP fallback for `TypeError` network-style failures.
Why it matters:
Auth failures, backend regressions, schema mismatches, or 5xx errors can appear as valid fixture-backed review data.
Suggested fix:
Only fallback in explicit mock/dev mode or network-unreachable conditions; never fallback for reached-backend HTTP errors.
Suggested test:
Stub `/api/paper-notes` as 401 and assert no mock paper notes are rendered.

## Finding 5: Cloud table fallback sends PDF text without the repo's privacy preflight lane

Severity: P2
Confidence: High
Status: Resolved in current branch
Category: Functional behavior
File/line:
`src/agents/ingest_agent.py:230`; `src/ingest/cloud_table_fallback.py:199`; `backend/services/job_runner.py:1243`
Related files/call sites:
`src/config.py:304`; `backend/services/job_runner.py:1322`
Issue:
The cloud table fallback can send PDF page text to OpenAI without the privacy preflight/payload classification used by later clinical extraction.
Evidence:
Ingest Pass3 calls the cloud extractor when enabled; `CloudTableFallbackExtractor` sends `page_text` to `client.chat.completions.create()`. The job runner privacy-preflight block is later and applies to clinical extraction, not table fallback.
Current branch note:
`backend/services/job_runner.py` now installs a cloud table preflight callback, and `src/ingest/cloud_table_fallback.py` skips LLM extraction when the callback blocks.
Why it matters:
Potentially sensitive source text can leave local runtime without the inference payload boundary required by project rules.
Suggested fix:
Classify/preflight selected page text before cloud table fallback, block according to policy, and persist `inference_lanes.cloud_table_fallback` metadata.
Suggested test:
Enable cloud table fallback with privacy blocking and assert no cloud call occurs and run metadata records the blocked lane.

## Finding 6: Failed Deep Read artifacts can become orphaned from job state

Severity: P2
Confidence: High
Status: Resolved in current branch
Category: Missing wiring
File/line:
`backend/services/job_runner.py:1047`; `backend/services/job_runner.py:1792`; `src/jobs/worker.py:164`; `src/jobs/worker.py:186`
Related files/call sites:
`backend/main.py:5869`; `src/services/stale_jobs.py`
Issue:
Artifact directories created before a failure are not reliably persisted on the `jobs` row.
Evidence:
The runner creates and writes artifacts/failure metadata under `artifact_dir`. The worker always stores `artifact_dir` on success, but the failed update only uses `(result or {}).get("artifact_dir")`; the runner's generic failure result does not clearly include the created directory.
Current branch note:
`run_deepread_job()` now returns `artifact_dir` for created runs, including failed/cancelled results, and `src/jobs/worker.py` persists it on failed/cancelled job updates.
Why it matters:
Diagnostics and bootstrap metadata can exist on disk but be unreachable through job APIs and stale incident tooling.
Suggested fix:
Persist `jobs.artifact_dir` immediately after artifact directory creation or always return it from failed/cancelled runner results.
Suggested test:
Force a post-artifact-creation failure and assert `/jobs/{job_id}` includes `artifact_dir` and bootstrap metadata can be loaded.

## Finding 7: Paper synthesis visual-evidence lineage is missing from the frontend contract

Severity: P2
Confidence: High
Status: Confirmed
Category: Contract mismatch
File/line:
`src/schemas/paper_synthesis.py:17`; `src/schemas/paper_synthesis.py:26`; `src/paper_syntheses/service.py:264`; `frontend/src/app/lib/types.ts:995`; `frontend/src/app/components/ArtifactPanel.tsx:175`; `frontend/src/app/components/ArtifactPanel.tsx:184`
Related files/call sites:
`tests/test_paper_synthesis_service.py:311`; `frontend/e2e/backend.spec.ts:4352`; `frontend/e2e/backend.spec.ts:4419`
Issue:
Backend emits `visual_evidence_ledger` in paper synthesis lineage, but frontend unions and formatters do not include it.
Evidence:
Backend schemas include the kind and service adds the source ref. Frontend type allows only `quality_gate | acceptance_contract`; formatters fall through or map non-quality-gate values to acceptance contract.
Why it matters:
Compiled-knowledge source lineage can be mislabeled, undermining evidence traceability.
Suggested fix:
Add `visual_evidence_ledger` to frontend types and explicit labels.
Suggested test:
Seed a manifest with visual evidence ledger lineage and assert the artifact panel renders “visual evidence ledger.”

## Finding 8: Downloads watcher likely misses temp-file rename completion events

Severity: P2
Confidence: Medium
Status: Needs verification
Category: Missing wiring
File/line:
`src/downloads_watcher.py:347`; `src/downloads_watcher.py:351`; `src/downloads_watcher.py:373`
Related files/call sites:
`tests/test_downloads_watcher.py`
Issue:
The watcher only implements `on_created`; common browser flows create a temporary file and then rename/move it to `.pdf`.
Evidence:
`on_created` ignores temp suffixes such as `.crdownload`/`.part`, and no `on_moved`/`on_modified` handler was found.
Why it matters:
Auto-collection can skip completed browser downloads.
Suggested fix:
Handle `on_moved` using `event.dest_path` and shared stable-file processing.
Suggested test:
Simulate `.crdownload` -> `.pdf` rename and assert processing occurs once.

## Finding 9: Rendered note and access links lack a complete URL scheme allowlist

Severity: P2
Confidence: High
Status: Resolved in current branch
Category: Functional behavior
File/line:
`backend/routers/paper_notes.py:1402`; `backend/routers/paper_notes.py:1439`; `frontend/src/app/pages/PaperNoteDetailPage.tsx:2360`; `frontend/src/app/lib/accessSummary.ts:14`; `frontend/src/app/pages/TriageDashboard.tsx:972`
Related files/call sites:
Markdown reference parsing and access-summary rendering.
Issue:
Persisted note/reference/access URLs are normalized lightly and rendered as `href` values.
Evidence:
Backend normalization returns most schemes unchanged; frontend renders reference and access URLs directly.
Current branch note:
`backend/routers/paper_notes.py` now drops unsupported reference URL schemes, and frontend rendering uses `sanitizeRenderableHref()` for paper references and access-summary links.
Why it matters:
Unexpected schemes such as `javascript:` or `data:` can become clickable if present in note metadata/reference markdown.
Suggested fix:
Centralize URL sanitation and allow only `http:`, `https:`, approved internal paths, and explicitly approved schemes.
Suggested test:
Use a note fixture with `[bad](javascript:alert(1))` and assert it is omitted or inert.

## Finding 10: Slash-bearing paper IDs can be misparsed by artifact run routes

Severity: P1
Confidence: High
Status: Confirmed
Category: Conflict
File/line:
`backend/main.py:5712`; `backend/main.py:5728`; `src/services/identity.py:95`
Related files/call sites:
Artifact bundle/file readers and frontend artifact pages.
Issue:
The artifact file route with `{paper_id:path}` is registered before the artifact run-bundle route, so paper IDs containing `/` can be split as `paper_id`, `run_id`, and `artifact_name` incorrectly.
Evidence:
`/artifacts/{paper_id:path}/{run_id}/{artifact_name}` is registered at `backend/main.py:5712` before `/artifacts/{paper_id:path}/{run_id}` at `backend/main.py:5728`. `src/services/identity.py:95` hashes unsafe IDs, which shows slash-bearing DOI-like paper IDs are expected elsewhere. A route probe showed `/artifacts/foo/bar/run1` matches the file route first as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`.
Why it matters:
Artifact bundle lookup for slash-bearing paper IDs can return the wrong file lookup or 404, making run-level artifacts unreachable for valid papers.
Suggested fix:
Use a non-path route segment for paper IDs, move paper IDs to query parameters for run/file artifact reads, or require callers to use the canonical hashed artifact segment consistently.
Suggested test:
Create an artifact run for a paper ID containing `/` and assert both bundle and file endpoints retrieve the intended run and artifact.

## Finding 11: Importing the backend initializes Ollama through the feedback router

Severity: P1
Confidence: High
Status: Confirmed
Category: Functional behavior
File/line:
`backend/routers/feedback.py:33`; `src/agents/feedback_retriever.py:43`; `src/agents/adapter.py:39`; `src/llm_provider.py:537`; `src/llm_provider.py:2480`
Related files/call sites:
`backend/main.py`; `scripts/check_python_import_health.py`
Issue:
Backend import has a network/runtime side effect because the feedback router constructs `FeedbackRetriever()` at module import time, which initializes the Ollama adapter/provider.
Evidence:
`backend/routers/feedback.py:33` creates `feedback_retriever = FeedbackRetriever()`. That constructor creates `OllamaModelAdapter`, which creates `OllamaProvider`; provider initialization calls `_initialize()`, and Ollama initialization calls `ollama_client.list()`. Importing `backend.main` during route listing emitted a `GET http://localhost:11434/api/tags` attempt.
Why it matters:
Route listing, import-health checks, tests, and deployments can hang or fail when Ollama is unavailable, even before any feedback endpoint is used.
Suggested fix:
Lazy-initialize the feedback retriever on first endpoint use, or inject a provider factory that does not perform network checks during import.
Suggested test:
Patch the Ollama client to raise if called, import `backend.main`, and assert no Ollama call occurs until a feedback route explicitly needs retrieval.

## Finding 12: Meeting-pack write flow falls back to mock success despite documented live-backend requirement

Severity: P2
Confidence: High
Status: Confirmed
Category: Contract mismatch
File/line:
`frontend/src/app/lib/api.ts:1225`; `frontend/src/app/lib/api.ts:1240`; `frontend/README.md:48`; `frontend/README.md:60`
Related files/call sites:
`frontend/e2e/meeting-pack.fallback.spec.ts`
Issue:
`generateMeetingPack()` can return a mock meeting pack after a proxy/backend availability error, while frontend docs say write actions require a live backend unless forced mock mode is enabled.
Evidence:
The README states write actions require the live backend and fallback is for read/inspection only. The API helper catches backend availability failures and returns `createMockMeetingPack()` from the write path. Existing fallback e2e coverage pins this behavior.
Why it matters:
A user can see apparent generated meeting-pack success when no real backend artifact was created.
Suggested fix:
Fail write/generation requests unless `VITE_FORCE_MOCK=1` or another explicit mock mode is active; keep fallback limited to read-only inspection.
Suggested test:
With forced mock disabled and backend/proxy unavailable, submit meeting-pack generation and assert an error state rather than a mock success artifact.

## Finding 13: Import-health defaults do not cover their own side-effect risk

Severity: P2
Confidence: Medium
Status: Needs verification
Category: Test gap
File/line:
`scripts/check_python_import_health.py:16`; `scripts/check_python_import_health.py:115`; `tests/test_python_import_health.py:19`
Related files/call sites:
`backend/routers/feedback.py`; `backend/main.py`
Issue:
The import-health script defaults include side-effectful imports, but the tests only exercise harmless modules.
Evidence:
Default probes include `site:src.cli` and `site:backend.main`, with timeout handling in the script. The test uses probes such as `json` and `math`, so it does not catch backend import side effects like Ollama initialization.
Why it matters:
CI can pass the import-health test while the real default script times out or performs unwanted network work.
Suggested fix:
Remove import-time side effects first, then add a test that runs the default probe list with external clients patched/disabled.
Suggested test:
Run `check_python_import_health` with its default probe list under mocked Ollama/network clients and assert it completes without external calls.

## Finding 14: Research DNA backend routes appear API-only in the current frontend shell

Severity: P3
Confidence: Medium
Status: Needs verification
Category: Disconnected code
File/line:
`backend/main.py:4711`; `backend/main.py:5304`; `frontend/src/App.tsx:84`
Related files/call sites:
`src/profiles/research_dna_service.py`; `tests/test_research_dna_api.py`
Issue:
Research DNA has many registered backend routes but no corresponding React route in the current app shell.
Evidence:
FastAPI route listing includes `/research-dna...`; `App.tsx` routes cover triage, papers, workbench, artifact pages, and readiness only.
Why it matters:
If Research DNA is intended as user-facing in this frontend, the UI route is missing.
Suggested fix:
Clarify whether the feature is API-only. If product-facing, add route and navigation entry.
Suggested test:
Frontend route reachability/e2e smoke for the Research DNA flow.
