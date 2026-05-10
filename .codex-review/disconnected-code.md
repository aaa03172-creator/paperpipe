# Disconnected Code

## Disconnected or suspicious code: Image Evidence caller-supplied ID is connected to writes but not validation

Status: Resolved in working tree
File/line:
`src/schemas/image_evidence.py:240`, `src/image_evidence/service.py:55`, `src/image_evidence/store.py:17`
Expected connection:
Route/request IDs should pass through schema validation and store root confinement before filesystem use.
Actual connection:
The working tree now normalizes IDs with a strict allowlist and confines resolved paths to the Image Evidence root.
Evidence:
Local reproduction wrote outside the configured root using `image_evidence_id="../paperpipe-image-root-proof-outside/escape"`.
Impact:
Previously broken root confinement for a production-facing register endpoint; blocked in the working tree.
Suggested fix:
Add strict ID validation and store-level path confinement.
Suggested test:
Path traversal and separator regression tests for POST/register and derivative read routes.

## Disconnected or suspicious code: Artifact/profile/memory/state helpers relied on upstream path validation

Status: Resolved in working tree
File/line:
`src/chart_packs/store.py:17`, `src/chart_packs/store.py:48`, `src/chart_packs/store.py:53`, `src/meeting_packs/store.py:15`, `src/method_comparisons/store.py:15`, `src/paper_syntheses/store.py:15`, `src/protocol_cards/store.py:15`, `src/protocol_cards/store.py:36`, `src/protocol_attachments/store.py:15`, `src/talk_packs/store.py:16`, `src/project_memory/store.py:18`, `src/skills/storage.py:115`, `src/skills/storage.py:318`, `src/skills/storage.py:323`, `src/skills/storage.py:328`, `src/profiles/research_dna_store.py:41`, `src/profiles/research_dna_store.py:69`, `src/exporter.py:233`, `backend/services/job_runner.py:213`, `backend/services/job_runner.py:240`, `src/services/cli_workflows.py:52`, `src/services/cli_workflows.py:161`, `src/obsidian.py:719`, `src/meeting_packs/source_resolver.py:778`
Expected connection:
Artifact/profile/memory/state store helpers and note-path consumers should enforce the same ID/path boundary as their Pydantic contracts and vault ownership before constructing filesystem paths.
Actual connection:
The working tree now validates artifact/profile/memory/state store IDs, filenames, slugs, and run/action segments for path safety before path construction, then confines resolved root-level directories, frontmatter structured paths, stored vault note paths, and Meeting Pack note selectors to the configured storage root/vault.
Evidence:
Chart Pack, Meeting Pack, Method Comparison, Paper Synthesis, Protocol Card, Protocol Attachment, Talk Pack, Project Memory, structured paper-state storage, Research DNA, export, job-runner, CLI deepread, Obsidian status, and Meeting Pack note selector helper paths are derived from caller IDs, artifact filenames, slugs, stored frontmatter paths, persisted `obsidian_path`, CSV `Note_Path`, or user-supplied note selector refs. New targeted tests reject path-like IDs and filenames, ignore escaping frontmatter structured paths, reject escaping stored note paths/selectors, and verify safe missing IDs still return 404 where that is the existing contract.
Impact:
Previously, direct store callers could bypass the intended schema contract and create malformed or escaping paths.
Suggested fix:
Keep store-level path checks and `resolve_vault_relative_path()` note-path resolution in place; apply the same pattern to stores outside these reviewed families during future audits.
Suggested test:
Store-level and note-path regression tests for `../escape`, nested paths, absolute paths, invalid filename characters, and escaping persisted vault paths.

## Disconnected or suspicious code: `/api/*` bridge lacks caller trust proof before server-side key injection

Status: Resolved in working tree
File/line:
`backend/main.py:570`, `backend/main.py:1249`, `backend/main.py:1252`
Expected connection:
The browser bridge should be connected to a trusted same-origin UI context or require caller auth.
Actual connection:
The working tree now requires API key, beta auth, or a trusted browser-shell signal before bridge key injection.
Evidence:
`GET /api/jobs` returned 200 without caller key while `GET /jobs` returned 401.
Impact:
Protected data can be reachable through the bridge.
Suggested fix:
Require API key/beta auth for direct callers, or add a real same-origin/session guard before injection.
Suggested test:
Unauthenticated `/api/*` protected route regression tests.

## Disconnected or suspicious code: Downloads watcher does not persist unmatched review queue item under canonical schema

Status: Resolved in working tree
File/line:
`src/downloads_watcher.py:295`, `src/downloads_watcher.py:300`, `src/downloads_watcher.py:163`, `scripts/init_db.py:81`
Expected connection:
Unmatched PDF handling should create a durable operator triage item.
Actual connection:
The working tree now ensures a sentinel `papers` row before enqueueing unmatched review items.
Evidence:
Subagent canonical-schema reproduction yielded `review_queue_count=0` and FK failure while returning `status=unmatched`.
Impact:
Unmatched PDFs can be moved aside without durable follow-up.
Suggested fix:
Use a separate unmatched-download review store or insert a valid sentinel paper row before enqueue.
Suggested test:
Canonical-schema unmatched download test.

## Disconnected or suspicious code: Downloads watcher only handles created events, not temp-file rename completion

Status: Resolved in working tree
File/line:
`src/downloads_watcher.py:347`, `src/downloads_watcher.py:351`, `src/downloads_watcher.py:373`
Expected connection:
Browser downloads that complete by renaming `.crdownload`/`.part` to `.pdf` should be processed.
Actual connection:
The working tree handles both `on_created` and `on_moved` through shared stable-file candidate processing.
Evidence:
Subagent searched watcher code and found no `on_moved`/`on_modified` path for the final PDF.
Impact:
Common browser download completion flows may be silently skipped.
Suggested fix:
Factor candidate handling into a helper and call it from `on_created` and `on_moved` using `event.dest_path`.
Suggested test:
Simulate temp-to-PDF rename and assert processing runs once after stable completion.

## Disconnected or suspicious code: Failed Deep Read artifact directory may not be connected to job row

Status: Resolved in working tree
File/line:
`backend/services/job_runner.py:1047`, `backend/services/job_runner.py:1792`, `src/jobs/worker.py:164`, `src/jobs/worker.py:186`
Expected connection:
Any run that creates an artifact directory should persist that directory on the job row for diagnostics and bootstrap metadata access.
Actual connection:
The working tree returns `artifact_dir` from created Deep Read runs, including failed and cancelled results, and the worker persists it on failed/cancelled job updates.
Evidence:
Runner creates and writes failure artifacts, then worker failed-update omits `artifact_dir` unless returned.
Impact:
Failure diagnostics are connected to job state in the reviewed path; previously, diagnostics could exist on disk but be unreachable through job APIs.
Suggested fix:
Persist `artifact_dir` immediately after creation or always return it on failure/cancel.
Suggested test:
Force failure after artifact directory creation and assert `/jobs/{id}` includes `artifact_dir`.

## Disconnected or suspicious code: Paper synthesis visual evidence lineage lacks frontend display handling

Status: Resolved in current branch
File/line:
`frontend/src/app/lib/types.ts:995`, `frontend/src/app/components/ArtifactPanel.tsx:175`, `frontend/src/app/components/ArtifactPanel.tsx:184`
Expected connection:
Every backend lineage kind emitted by `PaperSynthesis` should be represented by frontend types and labels.
Actual connection:
The working tree includes `visual_evidence_ledger` in frontend types and labels it explicitly.
Evidence:
Backend service adds source ref at `src/paper_syntheses/service.py:264`; frontend only knows two review artifact kinds.
Impact:
Lineage UI can mislabel evidence review artifacts.
Suggested fix:
Add `visual_evidence_ledger` frontend type and label coverage.
Suggested test:
UI contract/e2e fixture with visual evidence ledger lineage.

## Disconnected or suspicious code: Research DNA API is intentionally API/CLI-only in current frontend shell

Status: Verified non-issue
File/line:
`README.md:68`, `README.md:69`, `README.md:70`, `README.md:71`, `docs/CLI_WORKFLOW_REFERENCE.md:71`, `docs/CLI_WORKFLOW_REFERENCE.md:73`, `backend/main.py:4832`
Expected connection:
No frontend route is expected unless Research DNA becomes a web viewer surface.
Actual connection:
Multiple backend routes are registered, and current docs explicitly define Research DNA as an API/CLI operator lane rather than a dedicated frontend viewer route.
Evidence:
`README.md` says Research DNA is implemented today as an API/CLI operator lane and intentionally not part of the current main web viewer route set. `docs/CLI_WORKFLOW_REFERENCE.md` says it is a real API/CLI lane, not a dedicated frontend viewer route.
Impact:
No current wiring defect. A frontend route would require a new product decision.
Suggested fix:
No source fix for the current contract; reopen only if Research DNA becomes product-facing in the frontend.
Suggested test:
Keep Research DNA API/CLI coverage; add frontend reachability only when a route is intentionally introduced.

## Disconnected or suspicious code: Artifact run endpoint is not unambiguously reachable for slash-bearing paper IDs

Status: Resolved in working tree
File/line:
`backend/main.py:5712`, `backend/main.py:5728`, `src/services/identity.py:95`
Expected connection:
Artifact run and artifact file routes should both resolve valid paper IDs, including DOI-like IDs containing `/`.
Actual connection:
The working tree recovers ambiguous slash-bearing run-bundle requests from the file route into bundle lookup.
Evidence:
A route probe matched `/artifacts/foo/bar/run1` to the file route as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`.
Impact:
Valid artifact bundles can be unreachable or misread through the run endpoint.
Suggested fix:
Move paper identity to a query parameter or canonical hashed segment; avoid non-final path converters for ambiguous identifiers.
Suggested test:
Create an artifact for `10.1234/example.paper` and assert both bundle and file reads retrieve the intended artifact.

## Disconnected or suspicious code: Feedback retriever is connected at import time instead of request time

Status: Resolved in working tree
File/line:
`backend/routers/feedback.py:33`, `src/agents/feedback_retriever.py:43`, `src/agents/adapter.py:39`
Expected connection:
LLM/Ollama provider initialization should happen when a feedback route actually needs retrieval.
Actual connection:
The working tree exposes a lazy retriever proxy, so construction waits until feedback retrieval is used.
Evidence:
Route-listing import emitted an Ollama `/api/tags` request before any feedback endpoint was invoked.
Impact:
Import-health, tests, and startup checks depend on a live Ollama service unnecessarily.
Suggested fix:
Use a lazy dependency/factory for the feedback retriever and cache it after first successful construction.
Suggested test:
Patch Ollama client calls to fail, import `backend.main`, and assert no call happens until the feedback endpoint is exercised.

## Disconnected or suspicious code: Meeting-pack write action can report a mock artifact

Status: Resolved in working tree
File/line:
`frontend/src/app/lib/api.ts:1225`, `frontend/src/app/lib/api.ts:1240`, `frontend/README.md:48`
Expected connection:
Meeting-pack generation should connect to a live backend write path unless forced mock mode is explicitly enabled.
Actual connection:
The working tree only returns a mock meeting-pack write result in explicit forced mock mode; backend/proxy failures are surfaced otherwise.
Evidence:
The README limits fallback to read/inspection behavior, but the write helper still creates a mock success object.
Impact:
Users can believe an export/generation was persisted when no backend artifact exists.
Suggested fix:
Return an error for write failures outside explicit forced mock mode.
Suggested test:
Run the meeting-pack generation flow with backend unavailable and forced mock disabled; assert error UI rather than mock output.
