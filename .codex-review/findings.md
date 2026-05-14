# Findings

## Finding 1: `/api/*` bridge bypasses protected root-route API-key behavior

Severity: P1
Confidence: High
Status: Resolved in working tree
Category: Conflict
File/line:
`backend/main.py:570`; `backend/main.py:1249`; `backend/main.py:1252`; `backend/main.py:1305`
Related files/call sites:
`frontend/src/app/lib/config.ts:26`; `tests/test_api_key_auth.py:1246`
Issue:
The middleware rewrites `/api/*` to root API paths and injects the server-side API key before final auth checks. This means protected root routes can be accessed through the bridge without caller credentials.
Evidence:
Root private paths require API keys through `_requires_api_key()`. For `/api/*`, `_rewrite_browser_api_path()` rewrites the path, then `MutableHeaders(scope=request.scope)["x-api-key"] = expected_key` injects the configured key. A local probe with `LATTICE_API_KEY=secret-key` returned 401 for `GET /jobs` and 200 for `GET /api/jobs`.
Current working tree note:
`backend/main.py` now requires valid API key, beta auth, or a trusted browser-shell signal before injecting the bridge API key for protected `/api/*` requests. `tests/test_api_key_auth.py` covers unauthenticated `/api/jobs`, `/api/papers`, and `/api/paper-notes`.
Why it matters:
If the backend is reachable by non-UI callers, protected reads and some writes are exposed through the browser bridge despite the root-route API-key contract.
Suggested fix:
Require API key/beta auth for non-trusted `/api/*` callers before server-side injection, or bind the bridge to a stronger same-origin/session check.
Suggested test:
With `LATTICE_API_KEY` set, assert unauthenticated `GET /api/jobs`, `/api/papers`, and `/api/paper-notes` fail unless an explicitly trusted browser-shell condition is met.

## Finding 2: Caller-supplied Image Evidence IDs can escape the storage root

Severity: P1
Confidence: High
Status: Resolved in working tree
Category: Missing wiring
File/line:
`src/schemas/image_evidence.py:240`; `src/schemas/image_evidence.py:257`; `src/image_evidence/service.py:55`; `src/image_evidence/store.py:17`; `src/image_evidence/store.py:169`
Related files/call sites:
`backend/routers/image_evidence.py:34`; `tests/test_image_evidence_api.py`
Issue:
`ImageEvidenceRequest.image_evidence_id` is unconstrained and flows directly into filesystem path construction.
Evidence:
The schema only strips `image_evidence_id`. The service selects `request.image_evidence_id` when provided. The store returns `base / image_evidence_id` and writes `image_evidence.json` there. A local reproduction with `../paperpipe-image-root-proof-outside/escape` wrote outside the configured root.
Current working tree note:
`src/schemas/image_evidence.py` now normalizes Image Evidence IDs with a strict allowlist, and `src/image_evidence/store.py` verifies the resolved path stays under the configured root. Schema, store, and API traversal tests cover the failure mode.
Why it matters:
A malformed production request can write or affect files outside the image evidence artifact root.
Suggested fix:
Validate IDs with a strict allowlist, reject separators/dot segments, and enforce `resolved_path.relative_to(root)` in the store.
Suggested test:
POST traversal IDs and encoded separator variants to `/image-evidence/register`; assert 400/422 and no out-of-root writes.

## Finding 3: Unmatched downloaded PDFs are not durably queued under the canonical schema

Severity: P1
Confidence: High
Status: Resolved in working tree
Category: Conflict
File/line:
`src/downloads_watcher.py:20`; `src/downloads_watcher.py:163`; `src/downloads_watcher.py:295`; `src/downloads_watcher.py:300`; `scripts/init_db.py:81`; `src/db_utils.py:233`
Related files/call sites:
`tests/test_downloads_watcher.py`; CLI watch-downloads path.
Issue:
The unmatched-download flow enqueues `paper_id="__UNMATCHED__"`, but the canonical `review_queue.paper_id` has a foreign key to `papers(paper_id)`.
Evidence:
The watcher defines `UNMATCHED_SENTINEL_PAPER_ID = "__UNMATCHED__"` and uses it for unmatched/no-candidate flows. Canonical schema creates `review_queue` with a paper FK and DB connections enable FK checks. `_enqueue_pdf_match_review()` catches the exception and returns false, while the caller still returns `status="unmatched"`. Subagent reproduction observed FK failure and `review_queue_count=0`.
Current working tree note:
`src/downloads_watcher.py` now ensures a valid `__UNMATCHED__` sentinel paper row before enqueueing unmatched review items. `tests/test_downloads_watcher.py` covers the canonical FK schema.
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
`backend/services/job_runner.py:1047`; `backend/services/job_runner.py:1792`; `backend/services/job_runner.py:2118`; `backend/services/job_runner.py:2122`; `src/jobs/worker.py:164`; `src/jobs/worker.py:186`
Related files/call sites:
`backend/main.py:5869`; `src/services/stale_jobs.py`
Issue:
Artifact directories created before a failure are not reliably persisted on the `jobs` row.
Evidence:
The runner creates and writes artifacts/failure metadata under `artifact_dir`. The worker always stores `artifact_dir` on success, but the failed update only uses `(result or {}).get("artifact_dir")`; the runner's generic failure result does not clearly include the created directory.
Current branch note:
`run_deepread_job()` now returns `artifact_dir` for created runs, including failed/cancelled results, and `src/jobs/worker.py` persists it on failed/cancelled job updates. The failure-handoff path also initializes `artifact_acceptance_contract_written` and `artifact_quality_gate_written` to `False` before attempting handoff artifact writes, so failed handoff metadata keeps a stable shape.
Why it matters:
Diagnostics and bootstrap metadata can exist on disk but be unreachable through job APIs and stale incident tooling.
Suggested fix:
Persist `jobs.artifact_dir` immediately after artifact directory creation or always return it from failed/cancelled runner results.
Suggested test:
Force a post-artifact-creation failure and assert `/jobs/{job_id}` includes `artifact_dir`, bootstrap metadata can be loaded, and handoff-write failure metadata contains explicit contract/gate written flags.

## Finding 7: Paper synthesis visual-evidence lineage is missing from the frontend contract

Severity: P2
Confidence: High
Status: Resolved in working tree
Category: Contract mismatch
File/line:
`src/schemas/paper_synthesis.py:17`; `src/schemas/paper_synthesis.py:26`; `src/paper_syntheses/service.py:264`; `frontend/src/app/lib/types.ts:995`; `frontend/src/app/components/ArtifactPanel.tsx:175`; `frontend/src/app/components/ArtifactPanel.tsx:184`
Related files/call sites:
`tests/test_paper_synthesis_service.py:311`; `frontend/e2e/backend.spec.ts:4352`; `frontend/e2e/backend.spec.ts:4419`
Issue:
Backend emits `visual_evidence_ledger` in paper synthesis lineage, but frontend unions and formatters do not include it.
Evidence:
Backend schemas include the kind and service adds the source ref. Frontend type allows only `quality_gate | acceptance_contract`; formatters fall through or map non-quality-gate values to acceptance contract.
Current working tree note:
`frontend/src/app/lib/types.ts` now includes `visual_evidence_ledger`, and `frontend/src/app/components/ArtifactPanel.tsx` renders it as “visual evidence ledger.”
Why it matters:
Compiled-knowledge source lineage can be mislabeled, undermining evidence traceability.
Suggested fix:
Add `visual_evidence_ledger` to frontend types and explicit labels.
Suggested test:
Seed a manifest with visual evidence ledger lineage and assert the artifact panel renders “visual evidence ledger.”

## Finding 8: Downloads watcher likely misses temp-file rename completion events

Severity: P2
Confidence: Medium
Status: Resolved in working tree
Category: Missing wiring
File/line:
`src/downloads_watcher.py:347`; `src/downloads_watcher.py:351`; `src/downloads_watcher.py:373`
Related files/call sites:
`tests/test_downloads_watcher.py`
Issue:
The watcher only implements `on_created`; common browser flows create a temporary file and then rename/move it to `.pdf`.
Evidence:
`on_created` ignores temp suffixes such as `.crdownload`/`.part`, and no `on_moved`/`on_modified` handler was found.
Current working tree note:
`DownloadsFileHandler` now routes both `on_created` and `on_moved` through shared candidate processing, using `event.dest_path` for moved files. `tests/test_downloads_watcher.py` simulates `.part` -> `.pdf`.
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
Status: Resolved in working tree
Category: Conflict
File/line:
`backend/main.py:5712`; `backend/main.py:5728`; `src/services/identity.py:95`
Related files/call sites:
Artifact bundle/file readers and frontend artifact pages.
Issue:
The artifact file route with `{paper_id:path}` is registered before the artifact run-bundle route, so paper IDs containing `/` can be split as `paper_id`, `run_id`, and `artifact_name` incorrectly.
Evidence:
`/artifacts/{paper_id:path}/{run_id}/{artifact_name}` is registered at `backend/main.py:5712` before `/artifacts/{paper_id:path}/{run_id}` at `backend/main.py:5728`. `src/services/identity.py:95` hashes unsafe IDs, which shows slash-bearing DOI-like paper IDs are expected elsewhere. A route probe showed `/artifacts/foo/bar/run1` matches the file route first as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`.
Current working tree note:
The file route now recognizes ambiguous slash-bearing run-bundle requests and recovers to `_build_artifact_bundle()`. `tests/test_artifacts_runs_api.py` covers a direct path run request for a slash-bearing paper ID.
Why it matters:
Artifact bundle lookup for slash-bearing paper IDs can return the wrong file lookup or 404, making run-level artifacts unreachable for valid papers.
Suggested fix:
Use a non-path route segment for paper IDs, move paper IDs to query parameters for run/file artifact reads, or require callers to use the canonical hashed artifact segment consistently.
Suggested test:
Create an artifact run for a paper ID containing `/` and assert both bundle and file endpoints retrieve the intended run and artifact.

## Finding 11: Importing the backend initializes Ollama through the feedback router

Severity: P1
Confidence: High
Status: Resolved in working tree
Category: Functional behavior
File/line:
`backend/routers/feedback.py:33`; `src/agents/feedback_retriever.py:43`; `src/agents/adapter.py:39`; `src/llm_provider.py:537`; `src/llm_provider.py:2480`
Related files/call sites:
`backend/main.py`; `scripts/check_python_import_health.py`
Issue:
Backend import has a network/runtime side effect because the feedback router constructs `FeedbackRetriever()` at module import time, which initializes the Ollama adapter/provider.
Evidence:
`backend/routers/feedback.py:33` creates `feedback_retriever = FeedbackRetriever()`. That constructor creates `OllamaModelAdapter`, which creates `OllamaProvider`; provider initialization calls `_initialize()`, and Ollama initialization calls `ollama_client.list()`. Importing `backend.main` during route listing emitted a `GET http://localhost:11434/api/tags` attempt.
Current working tree note:
`backend/routers/feedback.py` now exposes a lazy feedback retriever proxy. `tests/test_feedback_api.py` asserts retriever construction waits until first use, and `scripts/check_python_import_health.py` default probes complete.
Why it matters:
Route listing, import-health checks, tests, and deployments can hang or fail when Ollama is unavailable, even before any feedback endpoint is used.
Suggested fix:
Lazy-initialize the feedback retriever on first endpoint use, or inject a provider factory that does not perform network checks during import.
Suggested test:
Patch the Ollama client to raise if called, import `backend.main`, and assert no Ollama call occurs until a feedback route explicitly needs retrieval.

## Finding 12: Meeting-pack write flow falls back to mock success despite documented live-backend requirement

Severity: P2
Confidence: High
Status: Resolved in working tree
Category: Contract mismatch
File/line:
`frontend/src/app/lib/api.ts:1225`; `frontend/src/app/lib/api.ts:1240`; `frontend/README.md:48`; `frontend/README.md:60`
Related files/call sites:
`frontend/e2e/meeting-pack.fallback.spec.ts`
Issue:
`generateMeetingPack()` can return a mock meeting pack after a proxy/backend availability error, while frontend docs say write actions require a live backend unless forced mock mode is enabled.
Evidence:
The README states write actions require the live backend and fallback is for read/inspection only. The API helper catches backend availability failures and returns `createMockMeetingPack()` from the write path. Existing fallback e2e coverage pins this behavior.
Current working tree note:
`generateMeetingPack()` now only returns a mock response when `VITE_FORCE_MOCK` is active; otherwise the write request propagates backend/proxy failures. `frontend/e2e/meeting-pack.fallback.spec.ts` now asserts no mock write success when the backend is unavailable.
Why it matters:
A user can see apparent generated meeting-pack success when no real backend artifact was created.
Suggested fix:
Fail write/generation requests unless `VITE_FORCE_MOCK=1` or another explicit mock mode is active; keep fallback limited to read-only inspection.
Suggested test:
With forced mock disabled and backend/proxy unavailable, submit meeting-pack generation and assert an error state rather than a mock success artifact.

## Finding 13: Import-health defaults do not cover their own side-effect risk

Severity: P2
Confidence: Medium
Status: Resolved in working tree
Category: Test gap
File/line:
`scripts/check_python_import_health.py:16`; `scripts/check_python_import_health.py:115`; `tests/test_python_import_health.py:19`
Related files/call sites:
`backend/routers/feedback.py`; `backend/main.py`
Issue:
The import-health script defaults include side-effectful imports, but the tests only exercise harmless modules.
Evidence:
Default probes include `site:src.cli` and `site:backend.main`, with timeout handling in the script. The test uses probes such as `json` and `math`, so it does not catch backend import side effects like Ollama initialization.
Current working tree note:
`tests/test_python_import_health.py` now runs the default probe list and asserts all default probes, including `src.cli` and `backend.main`, complete without errors or timeouts.
Why it matters:
CI can pass the import-health test while the real default script times out or performs unwanted network work.
Suggested fix:
Remove import-time side effects first, then add a test that runs the default probe list with external clients patched/disabled.
Suggested test:
Run `check_python_import_health` with its default probe list under mocked Ollama/network clients and assert it completes without external calls.

## Finding 14: Research DNA backend routes are intentionally API/CLI-only in the current frontend shell

Severity: P3
Confidence: High
Status: Verified non-issue
Category: Disconnected code
File/line:
`README.md:68`; `README.md:69`; `README.md:70`; `README.md:71`; `docs/CLI_WORKFLOW_REFERENCE.md:71`; `docs/CLI_WORKFLOW_REFERENCE.md:73`; `backend/main.py:4832`
Related files/call sites:
`src/profiles/research_dna_service.py`; `tests/test_research_dna_api.py`
Issue:
Initial review suspicion was that Research DNA might be missing a React route. Follow-up evidence shows it is intentionally exposed as an API/CLI operator lane, not a dedicated frontend viewer route.
Evidence:
`README.md` explicitly says Research DNA is implemented as an API/CLI operator lane and intentionally not part of the current main web viewer route set. `docs/CLI_WORKFLOW_REFERENCE.md` says Research DNA is a real API/CLI lane, not a dedicated frontend viewer route. FastAPI routes remain registered under `/research-dna...`.
Why it matters:
No source change is required for the current contract. Adding a frontend route without a product decision would widen the UI surface unnecessarily.
Suggested fix:
No fix for the current contract. Reopen only if a product requirement makes Research DNA a web viewer surface.
Suggested test:
Keep API/CLI tests for Research DNA; add frontend reachability only if a route is intentionally introduced.

## Finding 15: Artifact/profile/memory/state helpers trusted caller IDs or stored vault paths for filesystem paths

Severity: P2
Confidence: High
Status: Resolved in working tree
Category: Conflict
File/line:
`src/chart_packs/store.py:17`; `src/chart_packs/store.py:48`; `src/chart_packs/store.py:53`; `src/meeting_packs/store.py:15`; `src/method_comparisons/store.py:15`; `src/paper_syntheses/store.py:15`; `src/protocol_cards/store.py:15`; `src/protocol_cards/store.py:36`; `src/protocol_attachments/store.py:15`; `src/talk_packs/store.py:16`; `src/project_memory/store.py:18`; `src/skills/storage.py:115`; `src/skills/storage.py:318`; `src/skills/storage.py:323`; `src/skills/storage.py:328`; `src/profiles/research_dna_store.py:41`; `src/profiles/research_dna_store.py:69`; `src/exporter.py:233`; `backend/services/job_runner.py:213`; `backend/services/job_runner.py:240`; `src/services/cli_workflows.py:52`; `src/services/cli_workflows.py:161`; `src/obsidian.py:719`; `src/meeting_packs/source_resolver.py:778`
Related files/call sites:
`tests/test_chart_pack_store.py:84`; `tests/test_meeting_pack_store.py:86`; `tests/test_method_comparison_store.py:68`; `tests/test_paper_synthesis_store.py:83`; `tests/test_protocol_card_store.py:87`; `tests/test_protocol_attachment_store.py:49`; `tests/test_talk_pack_store.py:153`; `tests/test_project_memory_store.py:79`; `tests/test_storage_note_resolution.py:53`; `tests/test_research_dna_store.py:246`; `tests/test_exporter_obsidian_path.py:57`; `tests/test_worker_job_runner_chain.py:1083`; `tests/test_meeting_pack_source_resolver.py:287`
Issue:
Several artifact/profile/memory/state stores define narrow model contracts, but path helpers previously assembled filesystem paths directly from caller-provided IDs, filenames, slugs, frontmatter paths, or stored vault-relative note paths.
Evidence:
Chart Pack helpers derive directories and files from `chart_pack_id`, `chart_id`, and artifact filenames. Meeting Pack, Method Comparison, Paper Synthesis, Protocol Card, Protocol Attachment, Talk Pack, Project Memory, and Research DNA helpers derive directories or files from caller IDs. Structured paper-state helpers derive paths from note slugs, run stamps, actions, and frontmatter `pp.structured_path`. Export, job-runner, CLI deepread, Obsidian status, and Meeting Pack note selector flows also resolve persisted or user-supplied note paths under the vault. Before the current working tree changes, those helpers returned `base / caller_value`, `vault / rel_path`, or `... / f"{caller_value}.ext"` without local safe-segment validation or resolved-root/vault confinement.
Current working tree note:
The affected stores now reject path-like IDs and confine root-level directories to the configured storage root. Structured paper-state helpers now reject path-like slug/run/action segments and ignore frontmatter structured paths outside the vault. Export, job-runner, CLI deepread, Obsidian status, and Meeting Pack note selector flows now resolve note paths through `resolve_vault_relative_path()`, rejecting absolute or escaping values. Store validation is intentionally path-safety focused so safe-but-missing API IDs still produce the existing 404 behavior; semantic prefix validation remains with the Pydantic models used on writes.
Why it matters:
Direct store callers can bypass API/schema assumptions in tests, CLI, maintenance scripts, or future services. Store-level validation keeps artifact/profile files within their intended roots even when upstream validation is missed.
Suggested fix:
Keep schema and store-level path validation together for artifact/profile/memory/state stores; use `resolve_vault_relative_path()` anywhere persisted, CSV-backed, or user-supplied vault-relative note paths are converted into files.
Suggested test:
Pass `../escape`, nested paths, absolute paths, invalid filenames, and escaping stored vault paths to affected helpers; assert `ValueError` or ignored load and no out-of-root writes/reads, while safe-but-missing API IDs still return 404.

## Finding 16: Operational markdown backfill trusts stored note paths when checking for missing exports

Severity: P3
Confidence: High
Status: Resolved in working tree
Category: Functional behavior
File/line:
`scripts/backfill_operational_outputs.py:19`; `scripts/backfill_operational_outputs.py:66`; `scripts/backfill_operational_outputs.py:70`; `scripts/backfill_operational_outputs.py:71`; `tests/test_backfill_operational_outputs.py:63`
Related files/call sites:
`src.skills.storage.resolve_vault_relative_path`; `src.exporter.run_export`
Issue:
The operational backfill helper checks whether a markdown note exists by joining `vault_path / obsidian_path` without using the vault-relative confinement helper. If a persisted `obsidian_path` escapes the vault and happens to exist, `_note_exists()` reports the note as present.
Evidence:
`_note_exists()` reads `obsidian_path`, normalizes separators, falls back only when the string is empty, then checks `(vault_path / rel_path).exists()`. A local probe with `vault_path=/tmp/paperpipe-backfill-proof/vault`, `obsidian_path="../outside.md"`, and `/tmp/paperpipe-backfill-proof/outside.md` present returned `note_exists=True`. `collect_backfill_candidates()` uses `_note_exists()` to compute `markdown_missing`, so `--export-missing` can skip a row whose stored note path is outside the configured vault.
Current working tree note:
`_note_exists()` now resolves stored or derived note paths through `resolve_vault_relative_path()` and treats absolute or escaping paths as missing. `tests/test_backfill_operational_outputs.py` includes a regression case with `obsidian_path="../outside.md"` and an existing outside file.
Why it matters:
This is not a live request path, but it can make the maintenance helper under-report missing markdown exports and leave operator-facing notes unrepaired during an operational backfill.
Suggested fix:
Resolved in the working tree by resolving stored `obsidian_path` with `resolve_vault_relative_path(vault_path, rel_path)` and treating escaping or absolute paths as missing/invalid so `--export-missing` can repair them through the exporter.
Suggested test:
Added: create a row with `obsidian_path="../outside.md"` and an existing file outside the vault; assert `collect_backfill_candidates()` marks `markdown_missing=True` and does not treat the outside file as a valid note.
