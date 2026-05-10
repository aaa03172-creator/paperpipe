# Flow Traces

## Flow: Frontend paper list and note detail

Purpose:
Show paper/note inventory and detail/workbench state.
Entry point:
`frontend/src/App.tsx:86`, `frontend/src/App.tsx:87`, `frontend/src/app/lib/api.ts:981`
Call path:
React route `/papers` or `/papers/:slug` -> `getPaperNotesIndex()` / `getPaperNoteDetail()` -> `apiPath()` prefixes `/api` -> FastAPI middleware rewrites to `/paper-notes...` -> `backend/routers/paper_notes.py`.
Data path:
Obsidian vault notes and `.pp` structured state -> Pydantic paper note schemas -> JSON response -> frontend state.
Auth/permission checks, if relevant to the flow:
GET `/paper-notes` is private per `backend/main.py:479` and `backend/main.py:520`; `/api/*` bridge injects key when configured at `backend/main.py:1249`.
External dependencies:
Obsidian vault and local PDF files.
Database reads/writes:
May enrich with `papers`, jobs/artifacts, and operator state.
Config or feature flags:
`paths.obsidian_vault`, `VITE_AUTO_MOCK_FALLBACK`, API key/beta auth.
Error handling:
Frontend read helpers can fall back to mock data after caught errors (`frontend/src/app/lib/config.ts:12`, `frontend/src/app/lib/api.ts:1135` pattern).
Tests found:
`tests/test_paper_notes_api.py`, `frontend/e2e/backend.spec.ts`, `frontend/e2e/mock.spec.ts`.
Missing or suspicious connections:
Mock fallback can mask real backend/auth/schema failures.
Potential conflicts:
Root route API-key contract conflicts with `/api/*` bridge behavior.
Conclusion: Probably working
Evidence:
Routes exist and targeted tests passed; trustworthiness under backend failure is a confirmed risk.

## Flow: Browser `/api/*` request to protected backend route

Purpose:
Allow the frontend to call private backend APIs without exposing an API key to browser env.
Entry point:
`frontend/src/app/lib/config.ts:26`, `backend/main.py:570`
Call path:
Frontend calls `/api/jobs` -> middleware rewrites to `/jobs` -> middleware injects `x-api-key` if configured -> route handler runs.
Data path:
Protected backend JSON returned to caller.
Auth/permission checks, if relevant to the flow:
Root `/jobs` without key returns 401; bridged `/api/jobs` now requires caller auth or a trusted browser/UI request before backend key injection.
External dependencies:
None.
Database reads/writes:
Reads `jobs`.
Config or feature flags:
`LATTICE_API_KEY`, beta auth, CORS/origin checks.
Error handling:
Unauthorized root and untrusted bridged routes return JSON errors; trusted UI/browser bridge requests can proceed.
Tests found:
`tests/test_api_key_auth.py` covers unauthenticated `/api/*` private-route behavior and trusted bridge success.
Missing or suspicious connections:
Resolved in the working tree: bridge key injection is gated by trusted UI/browser or caller auth checks.
Potential conflicts:
Previously protected root routes conflicted with unconditional server-side API-key injection on bridged routes.
Conclusion: Working after fix
Evidence:
The initial local probe with `LATTICE_API_KEY=secret-key` showed `GET /jobs` returned 401 while `GET /api/jobs` returned 200. Current bridge behavior is covered by API-key auth regression tests and backend smoke.

## Flow: Deep Read enqueue to worker completion

Purpose:
Queue a deep-read run, process PDF, produce artifacts, and update job state.
Entry point:
`backend/main.py:5682`
Call path:
`POST /jobs/deepread` -> `JobQueue.enqueue()` -> DB `jobs` and `execution_runs` rows -> worker `claim_next_job()` -> `Worker.process_job()` -> `run_deepread_job()` -> ingest/index/reader/stats/sidecars -> job update.
Data path:
Paper ID -> PDF path -> document artifact -> index artifact -> claimset/resolved claimset -> stats/quality/coverage/visual sidecars -> `bootstrap_meta.json`, `run_meta.json`, note projection.
Auth/permission checks, if relevant to the flow:
POST `/jobs/deepread` is private at `backend/main.py:530`.
External dependencies:
Ollama/local models, optional OpenAI cloud table fallback, filesystem PDFs/artifacts.
Database reads/writes:
`jobs`, `execution_runs`, `job_events`, `user_actions`, optional `review_queue`.
Config or feature flags:
LLM/ingest/parser/cloud flags, queue limits, persona/profile selection.
Error handling:
Worker maps runner `succeeded` to completed; otherwise failed/cancelled. The runner now returns created `artifact_dir` values for failed/cancelled results, and the worker persists them on failed/cancelled job updates.
Tests found:
`tests/test_worker_job_runner_chain.py`, `tests/test_jobs_api_smoke.py`, `tests/test_worker_heartbeat.py`.
Missing or suspicious connections:
Failure artifact directory persistence was suspicious during the initial review and is resolved in the working tree.
Potential conflicts:
Cloud table fallback privacy preflight was suspicious during the initial review and is resolved in the working tree.
Conclusion: Probably working
Evidence:
Targeted worker/API suite passed: `85 passed, 7 warnings`; later targeted and full-suite checks passed after the failure-path artifact persistence fix.

## Flow: Job events and timeline

Purpose:
Stream and replay job status/progress and expose run timelines.
Entry point:
`backend/main.py:5895`, `backend/main.py:5822`
Call path:
Worker progress callback writes job updates/log JSONL and `job_events`; SSE reads current job/log lines and emits events; timeline combines DB events, user actions, and log lines.
Data path:
Worker event -> `jobs` row / log JSONL / `job_events` -> SSE or timeline response.
Auth/permission checks, if relevant to the flow:
GET `/jobs/{job_id}/events` is private through `/jobs` prefix.
External dependencies:
Filesystem logs.
Database reads/writes:
`jobs`, `job_events`, `user_actions`.
Config or feature flags:
Request audit, API key/beta auth.
Error handling:
SSE emits status/log/done and exits on terminal status.
Tests found:
`tests/test_jobs_events_persistence.py`, `tests/test_worker_heartbeat.py`.
Missing or suspicious connections:
No confirmed missing registration.
Potential conflicts:
Same `/api/*` bridge concern applies.
Conclusion: Working
Evidence:
Covered by targeted tests and route listing.

## Flow: Paper synthesis compiled knowledge

Purpose:
Generate/list/read compiled paper synthesis manifest and markdown with lineage.
Entry point:
`backend/routers/paper_syntheses.py:68`, `frontend/src/app/lib/api.ts:1151`
Call path:
API generate/list/detail routes -> `src/paper_syntheses/service.py` -> load structured state and latest eligible artifacts -> render markdown -> save bundle -> frontend loads manifest/markdown URL.
Data path:
Structured state, claimset, quality gate, acceptance contract, visual evidence ledger -> `PaperSynthesis` manifest + markdown.
Auth/permission checks, if relevant to the flow:
Private via `/paper-syntheses` prefix.
External dependencies:
Local artifacts and vault.
Database reads/writes:
File-backed synthesis store; DB not primary.
Config or feature flags:
Vault/artifact roots.
Error handling:
Missing state/artifacts become 404/400 through router.
Tests found:
`tests/test_paper_synthesis_service.py`, `tests/test_paper_synthesis_frontend_contract.py`.
Missing or suspicious connections:
Frontend type/formatters omit `visual_evidence_ledger`.
Potential conflicts:
Backend contract includes `visual_evidence_ledger`; frontend narrows it away/mislabels it.
Conclusion: Probably working
Evidence:
Backend routes exist and contract test passed; frontend display contract mismatch remains.

## Flow: Image Evidence registration and file-backed read

Purpose:
Register image evidence bundles, derivatives, view state, and handoff targets.
Entry point:
`backend/routers/image_evidence.py:34`, `frontend/src/app/lib/api.ts:1332`
Call path:
`POST /image-evidence/register` -> `register_image_evidence()` -> `save_image_evidence_bundle()` -> JSON/view-state/handoff/derivatives under image evidence root -> list/detail/derivative routes.
Data path:
Request JSON -> `ImageEvidenceRequest` -> `ImageEvidence` bundle -> filesystem -> frontend detail/list.
Auth/permission checks, if relevant to the flow:
Private GET/POST via `/image-evidence` prefix.
External dependencies:
Local files or external image refs.
Database reads/writes:
File-backed; no DB primary.
Config or feature flags:
`image_evidence_root`.
Error handling:
Schema validation and route 404/400 for load failures.
Tests found:
`tests/test_image_evidence_api.py`, `tests/test_image_evidence_service.py`, `tests/test_image_evidence_store.py`.
Missing or suspicious connections:
Resolved in the working tree: caller-provided `image_evidence_id` is validated before filesystem path composition.
Potential conflicts:
Previously the store root boundary was not enforced for ID path segments.
Conclusion: Working after fix
Evidence:
Initial reproduction wrote `/tmp/paperpipe-image-root-proof-outside/escape/image_evidence.json` using request ID `../paperpipe-image-root-proof-outside/escape`. Current schema/store validation rejects path-like IDs and targeted image evidence tests pass.

## Flow: Protocol attachment draft to protocol card

Purpose:
Upload source files, preserve raw source, optionally extract markdown, and create protocol card draft state.
Entry point:
`backend/routers/protocol_cards.py:124`, `frontend/src/app/lib/api.ts:1385`
Call path:
Paper note attachment picker -> multipart POST -> `build_protocol_card_draft_from_attachment()` -> protocol attachment store -> frontend protocol card page consumes attachment draft/bundle/source/markdown routes.
Data path:
Uploaded file bytes -> `ProtocolAttachmentBundle` + source/extracted markdown -> draft response -> UI state.
Auth/permission checks, if relevant to the flow:
Private via `/protocol-cards`.
External dependencies:
Filesystem and optional extraction runtime.
Database reads/writes:
File-backed.
Config or feature flags:
`LATTICE_MAX_PROTOCOL_ATTACHMENT_BYTES`, vault/artifact roots.
Error handling:
Size/empty file checks; route returns 404/400 on service exceptions.
Tests found:
`tests/test_protocol_attachments_api.py`, `tests/test_protocol_attachment_service.py`.
Missing or suspicious connections:
No confirmed missing connection.
Potential conflicts:
None confirmed.
Conclusion: Working
Evidence:
Targeted API tests passed in the `85 passed` run.

## Flow: Downloads watcher matched/unmatched PDF handling

Purpose:
Auto-handle PDFs landing in the downloads folder, match them to candidate papers, move them, and enqueue manual triage when ambiguous/unmatched.
Entry point:
`src/downloads_watcher.py:347`, `src/downloads_watcher.py:373`
Call path:
watchdog created event -> ignore temp suffixes -> `process_downloaded_pdf()` -> metadata extraction/candidate match -> move matched or `_unmatched` -> `_enqueue_pdf_match_review()`.
Data path:
PDF path -> DOI/title metadata -> candidate match and review queue row.
Auth/permission checks, if relevant to the flow:
Local CLI/background process only.
External dependencies:
Filesystem watcher.
Database reads/writes:
`papers`, `review_queue`.
Config or feature flags:
Downloads/library/watch folder config.
Error handling:
Unmatched handling ensures the sentinel paper row before queue insertion and move events use the same processing path.
Tests found:
`tests/test_downloads_watcher.py`.
Missing or suspicious connections:
Resolved in the working tree: `on_moved` handles temp-file rename completion, and unmatched sentinel queue writes satisfy the canonical FK schema.
Potential conflicts:
Previously `review_queue.paper_id` FK conflicted with the `__UNMATCHED__` sentinel.
Conclusion: Working after fix
Evidence:
Initial canonical-schema reproduction showed `status=unmatched`, `review_queue_count=0`, and an FK failure. Current downloads watcher tests cover unmatched persistence and move-event handling.

## Flow: Meeting/method/chart/protocol/talk artifact pages

Purpose:
Generate/list/render/export user-facing derived artifacts.
Entry point:
Frontend routes `frontend/src/App.tsx:88` through `frontend/src/App.tsx:97` and feature routers.
Call path:
Frontend page -> API client -> feature router -> service/store -> response/export route.
Data path:
Requests and source selectors -> file-backed artifact bundle -> JSON/markdown/CSV/SVG/PPTX -> frontend.
Auth/permission checks, if relevant to the flow:
Private route prefixes.
External dependencies:
Vault/artifacts, chart/PPTX rendering helpers.
Database reads/writes:
Mostly file-backed; some source resolution uses DB/vault.
Config or feature flags:
Runtime roots, vault paths.
Error handling:
Routers generally catch FileNotFoundError/ValueError to 404/400.
Tests found:
Feature API tests and frontend e2e specs.
Missing or suspicious connections:
Meeting-pack generation is a write path but can still return `createMockMeetingPack()` after backend/proxy availability failure.
Potential conflicts:
General artifact ID/path confinement should be standardized; Image Evidence confirmed. Meeting-pack write fallback conflicts with the documented live-backend write contract.
Conclusion: Probably working
Evidence:
Routes listed successfully and targeted protocol/paper synthesis tests passed.

## Flow: Artifact run bundle and file lookup

Purpose:
Read a run-level artifact bundle or a named artifact file for a paper.
Entry point:
`GET /artifacts/{paper_id:path}/{run_id}/{artifact_name}` at `backend/main.py:5712`; `GET /artifacts/{paper_id:path}/{run_id}` at `backend/main.py:5728`
Call path:
Frontend artifact route/API helper -> FastAPI route matcher -> artifact read helper.
Data path:
Paper ID and run ID from URL -> artifact root lookup -> manifest/file response.
Auth/permission checks, if relevant to the flow:
Private `/artifacts` prefix under API-key middleware.
External dependencies:
Filesystem artifact root.
Database reads/writes:
No direct DB write in the traced route.
Config or feature flags:
Artifact root/runtime path config.
Error handling:
Missing or invalid artifact paths return 404/400 depending on helper.
Tests found:
Artifact route tests cover slash-bearing paper IDs and ambiguous route recovery.
Missing or suspicious connections:
Resolved in the working tree: ambiguous slash-bearing artifact URLs recover to the intended bundle/file lookup.
Potential conflicts:
Previously `{paper_id:path}` was non-final in both routes and could shadow bundle lookup for slash-bearing IDs.
Conclusion: Working after fix
Evidence:
Initial route-matching probe showed `/artifacts/foo/bar/run1` mapped to the file route as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`. Current artifact route tests and backend smoke pass with the recovery behavior.

## Flow: Feedback submit/index and backend import

Purpose:
Serve feedback retrieval/index endpoints without making unrelated startup checks depend on LLM availability.
Entry point:
`backend/routers/feedback.py`
Call path:
`backend.main` imports feedback router -> feedback retriever lazy proxy -> provider initializes only on route use.
Data path:
Feedback route dependencies are constructed without triggering provider network discovery during import.
Auth/permission checks, if relevant to the flow:
Feedback API route auth not deeply traced; issue occurs before request auth.
External dependencies:
Ollama local service.
Database reads/writes:
Not reached during import side effect.
Config or feature flags:
LLM/Ollama provider config.
Error handling:
Provider initialization is deferred; import-health/default probes no longer require Ollama availability.
Tests found:
`tests/test_feedback_api.py` and `tests/test_python_import_health.py`; import-health now exercises default backend probes.
Missing or suspicious connections:
Resolved in the working tree: provider is connected on route use, not backend import.
Potential conflicts:
Previously import-health defaults included `backend.main`, while backend import attempted Ollama network initialization.
Conclusion: Working after fix
Evidence:
Initial route listing/import emitted an Ollama `GET http://localhost:11434/api/tags` request. Current import-health tests and backend smoke pass with lazy initialization.

## Flow: Research DNA API

Purpose:
Create/update/interview/rerank/screen research DNA project state.
Entry point:
`backend/main.py:4711` through `backend/main.py:5304`
Call path:
Direct FastAPI routes -> research DNA service/store/project profile projection.
Data path:
Request schema -> file-backed DNA/profile/screening artifacts -> response envelope.
Auth/permission checks, if relevant to the flow:
Private via `/research-dna` prefix.
External dependencies:
Fetch/ranking providers depending on service call.
Database reads/writes:
File-backed project/profile data; may read runtime paper state.
Config or feature flags:
Provider/source config.
Error handling:
Routes catch exceptions in several places but not exhaustively traced.
Tests found:
`tests/test_research_dna_api.py`, `tests/test_research_dna_service.py`, `tests/test_research_dna_store.py`, `tests/test_research_dna_projection.py`.
Missing or suspicious connections:
No frontend route found in current `App.tsx`; README and CLI workflow docs mark Research DNA as an API/CLI operator lane rather than a dedicated frontend viewer route.
Potential conflicts:
Live fetch/ranking providers were not exercised; frontend reachability should only be revisited if the product contract changes from API/CLI lane to web viewer surface.
Conclusion: Probably working
Evidence:
Backend route registrations exist, docs define Research DNA as API/CLI-only, and `pytest -q tests/test_research_dna_api.py tests/test_research_dna_service.py tests/test_research_dna_store.py tests/test_research_dna_projection.py` passed with `28 passed`.

## Flow: Operational markdown and claimset backfill

Purpose:
Find approved/indexed papers missing Obsidian markdown exports or claimset artifacts, then optionally run exporter and/or enqueue Deep Read backfill jobs.
Entry point:
`scripts/backfill_operational_outputs.py:150`
Call path:
Operator command -> `main()` -> `get_db_connection()` -> `_paper_rows()` -> `collect_backfill_candidates()` -> `_note_exists()` / `_has_valid_claimset()` / `_has_claimset_artifact()` -> optional `run_export(overwrite=False)` and `JobQueue.enqueue()`.
Data path:
SQLite `papers` rows provide `paper_id`, `title`, `feedback_json`, `pdf_path`, and `obsidian_path`; Obsidian vault path comes from config; artifact existence comes from storage artifact helpers; optional actions write markdown via exporter or enqueue DB-backed jobs.
Auth/permission checks, if relevant to the flow:
No request auth; this is a local operator script. Apply mode requires explicit flags such as `--apply`, `--confirm-vault-backup`, and `--confirm-enqueue`.
External dependencies:
Local filesystem, Obsidian vault, SQLite DB, optional worker/job processing after enqueue.
Database reads/writes:
Reads `papers`; optional enqueue writes job rows; optional DB backup is written before apply actions.
Config or feature flags:
Obsidian vault path from `load_config()`, DB path from runtime DB helper, command flags for apply/export/enqueue/backup/fixture inclusion.
Error handling:
Dry-run by default; apply mode creates a DB backup before actions. Missing backup confirmations stop export/enqueue apply modes.
Tests found:
`tests/test_backfill_operational_outputs.py`, including an escaping stored `obsidian_path` regression case.
Missing or suspicious connections:
Resolved in the working tree: `_note_exists()` now uses `resolve_vault_relative_path()` and treats escaping stored note paths as missing.
Potential conflicts:
Previously conflicted with the runtime vault-note-path confinement pattern used by exporter, job runner, CLI workflow, Obsidian status, and Meeting Pack note selectors.
Conclusion: Working after fix
Evidence:
`scripts/backfill_operational_outputs.py:19` imports `resolve_vault_relative_path`; `scripts/backfill_operational_outputs.py:70` resolves the stored or expected note path through that helper; `scripts/backfill_operational_outputs.py:71` treats invalid/escaping paths as missing. `tests/test_backfill_operational_outputs.py:63` covers `obsidian_path="../outside.md"` with an existing outside file.
