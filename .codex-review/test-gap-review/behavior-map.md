## Behavior: API auth, beta gate, browser bridge, and sanitized errors

Purpose: Protect private data and write routes, bridge trusted browser `/api/*` calls, rate-limit beta/auth paths, and avoid leaking secrets/local paths in errors.
Production files: `backend/main.py`
Entry points: middleware around lines 1052-1451; `/health`, `/health/ready`, private routes, `/api/*`
Main branches: API key configured/unconfigured, loopback/non-loopback, beta password enabled, allowed/disallowed origin, browser signal present/missing, direct protected read/write, validation/HTTP error handling
Important edge cases: OPTIONS bypass, IP allowlist, docs enabled under beta gate, HSTS only on HTTPS, invalid host, invalid validation input with secret-like data
Failure modes: unauthorized access, secret/path leakage, false 401/403, excessive rate limiting, CORS/host bypass
Existing tests: `tests/test_api_key_auth.py`, `tests/test_beta_gate_api.py`, `tests/test_browser_security_headers_api.py`, `tests/test_cors_policy.py`, `tests/test_http_exception_sanitizer.py`, `tests/test_path_masking_api.py`, `tests/test_browser_request_audit_api.py`
Test quality: Strong
Risk level: High
Reason: Security boundary is high impact; tests are unusually broad, but audit logging permutations and CI env coverage remain worth watching.

## Behavior: Job queue, worker lifecycle, SSE status/log events, cancellation, stale recovery

Purpose: Enqueue deepread jobs, persist run/job state, claim with concurrency limits, stream progress/logs, cancel/reclaim stale jobs, and write artifacts.
Production files: `backend/main.py`, `src/jobs/queue.py`, `src/jobs/worker.py`, `backend/services/job_runner.py`, `src/services/event_log.py`, `src/services/stale_jobs.py`
Entry points: `/jobs/deepread`, `/jobs`, `/jobs/{job_id}`, `/jobs/{job_id}/events`, `/jobs/{job_id}/cancel`, `/ops/jobs/*`
Main branches: duplicate open job, queue backpressure, claim concurrency, completed/failed/cancelled terminal states, malformed/missing bootstrap meta, Last-Event-ID replay, stale running job reclaim/requeue
Important edge cases: late worker writes after cancellation, stale heartbeat, unknown job, sanitized log replay, parser backend metadata, clean reindex, run IDs for rapid enqueues
Failure modes: duplicate jobs, orphan execution runs, stale terminal state overwrite, UI never receives done, real runner failure hidden by fake worker
Existing tests: `tests/test_jobs_api_smoke.py`, `tests/test_jobs_events_persistence.py`, `tests/test_jobs_restart_persistence.py`, `tests/test_stale_jobs_api.py`, `tests/test_worker_heartbeat.py`, frontend backend E2E
Test quality: Partial
Risk level: Critical
Reason: Queue/state is well tested, but the browser to real worker to real artifact chain is mostly patched or fake-worker based, and browser `EventSource` behavior is not directly covered.

## Behavior: Deepread pipeline, ingestion, reader/indexer/stats/artifact handoff

Purpose: Run real document ingestion, indexing, reading, verification/stats, privacy preflight, clinical extraction, and artifact sidecars.
Production files: `backend/services/job_runner.py`, `src/agents/*`, `src/ingest/*`, `src/services/*`, `src/schemas/agent_artifacts.py`
Entry points: `run_deepread_job`, worker `process_job`, deepread CLI/workflows
Main branches: parser backend selection/fallback, privacy preflight report/block, timeout sidecars, clinical/non-clinical extraction, artifact write flags, verify run on/off
Important edge cases: failed parser fallback, missing config sections, cancelled job mid-run, partial artifact writes, malformed LLM JSON, local/external inference payload boundaries
Failure modes: pipeline appears green in UI while real runner would fail; privacy gate bypass; artifacts missing or inconsistent
Existing tests: `tests/test_job_runner_clinical_extraction.py`, `tests/test_job_runner_ingest_backend.py`, `tests/test_job_runner_table_meta.py`, `tests/test_reader_eval_sidecar.py`, `tests/test_worker_job_runner_chain.py`, parser/eval tests
Test quality: Partial
Risk level: Critical
Reason: Many unit/contract slices exist, but high-value end-to-end runtime path is heavily mocked around the expensive model/parser boundary.

## Behavior: Canonical SQLite state, migrations, event logs, request audit logs

Purpose: Initialize and evolve local canonical structured state, preserve backward compatibility, log events/actions/audits, and sanitize persisted payloads.
Production files: `src/db_utils.py`, `src/services/event_log.py`, `src/services/paper_operator_state_store.py`
Entry points: `init_db`, `save_paper_state`, `update_paper_status`, queue/event helpers, user action/request audit APIs
Main branches: legacy schema backfill, missing columns, invalid update columns, legacy rows without run IDs, request audit filtering, secret redaction
Important edge cases: schema drift, missing additive tables, local path/API key redaction, transaction rollback
Failure modes: data loss, unsanitized secrets, migration failures, stale cache/state
Existing tests: `tests/test_db_schema_compat.py`, `tests/test_db_utils_*`, `tests/test_event_log_db.py`, `tests/test_jobs_events_persistence.py`, `tests/test_project_memory_store.py`
Test quality: Strong
Risk level: High
Reason: Good migration and redaction coverage, though broad concurrent DB behavior is mostly covered through targeted slices.

## Behavior: Paper notes list/detail/import/operator state/cache

Purpose: Build paper-note index, resolve by paper ID/slug, import PDFs, serve PDFs, cache note metadata, persist user operator state, and render details with references/related items.
Production files: `backend/routers/paper_notes.py`, `src/schemas/paper_notes.py`, `src/services/paper_operator_state_store.py`, `src/services/fixture_visibility.py`
Entry points: `/paper-notes`, `/paper-notes/home-context`, `/paper-notes/import-pdf`, `/paper-notes/{slug}`, `/paper-notes/{slug}/operator-state`, `/paper-notes/resolve-by-paper-id`
Main branches: DB-backed vs note-backed, legacy renamed slug, fixture hidden/allowed, cache fresh/stale, import DOI extraction/reimport/rollback, operator state sanitization
Important edge cases: note path collision, oversized upload, DB persist failure cleanup, unsafe reference URLs, path masking, multi-tag/search/pagination sorting
Failure modes: duplicate/missing papers, stale cache, unsafe links, partial imports, secret leakage in operator notes
Existing tests: extensive `tests/test_paper_notes_api.py`, `tests/test_papers_api.py`, frontend backend/mock E2E
Test quality: Strong
Risk level: High
Reason: One of the strongest areas. Remaining mock risk exists where some tests patch `_build_index()` with partial `SimpleNamespace`.

## Behavior: Obsidian artifact sync and markdown idempotency

Purpose: Expose artifact payloads, mirror artifacts into note blocks, sync generated sections idempotently, and avoid blind appends.
Production files: `backend/routers/obsidian.py`, `src/obsidian.py`, `src/exporter.py`
Entry points: `/obsidian/artifacts`, `/obsidian/mirror`, `/obsidian/sync`, exporter/Obsidian save helpers
Main branches: resolved vs legacy claimset, missing artifact, one-index page conversion, frontmatter lookup, atomic note write
Important edge cases: duplicate sync, existing section replacement, local path masking, missing note/frontmatter
Failure modes: repeated appends, note corruption, stale legacy claimset preferred over resolved
Existing tests: `tests/test_obsidian_artifacts_api.py`, `tests/test_obsidian_save.py`, `tests/test_idempotency_sync.py`, `tests/test_exporter*.py`
Test quality: Strong
Risk level: High
Reason: Critical repo rule is covered by targeted tests.

## Behavior: Derived artifact pack APIs and file-backed stores

Purpose: Generate/read/list/export meeting packs, chart packs, image evidence, method comparisons, paper syntheses, protocol cards/attachments, and talk packs.
Production files: `backend/routers/{meeting_packs,chart_packs,image_evidence,method_comparisons,paper_syntheses,protocol_cards,talk_packs}.py`, `src/*_packs/*`, `src/image_evidence/*`, `src/method_comparisons/*`, `src/protocol_*/*`
Entry points: pack `/generate`, list/detail, markdown/export routes, review/outcome routes, derivative artifact routes, talk-pack render deck
Main branches: generate/list/detail/missing, corrupt bundle skip, declared artifact paths, fixture hidden/allowed, regenerate/rerender/validate, path masking, review/outcome logging
Important edge cases: malformed IDs/subpaths, rollback on partial write, stale source refs, missing sources, corrupt bundles
Failure modes: path traversal, partial bundle corruption, hidden fixture leakage, stale derived artifacts treated canonical
Existing tests: many API/store/schema/service tests for each pack family; Playwright route tests; visual snapshots
Test quality: Partial
Risk level: High
Reason: Broad positive and missing-path coverage. Cross-pack encoded/dot-segment ID path-safety is not uniformly proven, and some frontend flows are mock-heavy.

## Behavior: Research DNA/profile project memory and screening flows

Purpose: Manage research profiles, Research DNA screening/current/guidance flows, project memory, and profile projections.
Production files: `backend/main.py`, `src/profiles/*`, `src/project_memory/store.py`, `src/schemas/research_dna.py`, `src/schemas/project_memory.py`
Entry points: Research DNA endpoints in `backend/main.py` around 4832-5426, profile APIs/CLI/services
Main branches: profile create/update, screening advance/current selectors, locks, projections, guidance/history/recommendations, secret/path sanitization
Important edge cases: stale profile updates, concurrent writes, malformed selectors, missing/hidden raw memory, screening lock conflicts
Failure modes: profile data loss, incorrect screening state, raw memory/canonical boundary drift
Existing tests: `tests/test_research_dna_api.py`, `tests/test_research_dna_service.py`, `tests/test_research_dna_projection.py`, `tests/test_profile_store_concurrency.py`, `tests/test_project_memory_*`
Test quality: Partial
Risk level: High
Reason: Good service/store slices, but route-level coverage for every Research DNA subroute/failure mode is not obviously complete.

## Behavior: External scholarly fetch/download integrations

Purpose: Fetch paper metadata/PDF candidates from PubMed, arXiv, OpenAlex, Unpaywall, PMC/direct providers and handle provider failures/rate limits.
Production files: `src/fetch/*.py`, `src/fetchers.py`, `src/downloader/providers/*.py`, `src/downloader/router.py`
Entry points: fetchers, downloader router, CLI unpaywall test, daily slot processing
Main branches: provider ordering, DOI normalization, HTTP status/error, malformed JSON/XML, OA candidate selection, retry/rate-limit policy, existing PDF short-circuit
Important edge cases: upstream response shape changes, invalid XML/JSON, 429/5xx, no email, HTML returned as PDF, provider exception fail-safe
Failure modes: intake/download silently fails, bad metadata persisted, rate-limit storms, wrong PDF selected
Existing tests: `tests/test_downloader.py`, `tests/test_fetch_providers.py`, `tests/test_cli_unpaywall_smoke.py`, provider/unit tests
Test quality: Weak
Risk level: High
Reason: Downloader has useful router tests, but external API contracts are mostly minimal mocks and provider selection tests.

## Behavior: Frontend API client, routes, and UI state

Purpose: Display paper review, workbench, runtime readiness, artifact viewers, and handle live/mock API results.
Production files: `frontend/src/App.tsx`, `frontend/src/app/pages/**`, `frontend/src/app/lib/api.ts`, `frontend/src/app/lib/types.ts`, `frontend/src/app/lib/sse.ts`
Entry points: `/`, `/papers`, `/papers/:slug`, `/workbench/:paperId`, `/meeting-packs`, `/chart-packs`, `/image-evidence`, `/method-comparisons`, `/protocol-cards`, `/ready`
Main branches: live fetch vs mock fallback, API errors, SSE status/log/done/artifact events, route params, filters/search, viewer detail/index states
Important edge cases: backend contract drift, EventSource reconnect, mock fallback masking real failures, handwritten type mismatch, browser-only CORS/SSE behavior
Failure modes: UI compiles but breaks on real payload, job progress stuck, wrong route shape, fallback hides production outage
Existing tests: Playwright mock/backend/visual E2E; no frontend unit tests found
Test quality: Partial
Risk level: High
Reason: Strong route-level E2E, weak client contract/unit coverage and browser SSE contract.

## Behavior: Skills policy and skill run side effects

Purpose: Enforce approved skills, run skill actions, write sidecars, update frontmatter/markdown safely, and gate secrets.
Production files: `backend/routers/skills.py`, `src/skills/*`, `src/schemas/skills.py`
Entry points: `/skills/run`
Main branches: allowed/blocked skill, missing required secret, markdown summary append on/off, hidden fixture state, structured review sidecar
Important edge cases: unapproved skill execution, secret missing, sidecar/frontmatter mismatch, hidden fixture fallback
Failure modes: unauthorized skill execution, note corruption, fixture data leak
Existing tests: `tests/test_skills_api.py`, `tests/test_skill_state_contract.py`, `tests/test_privacy_preflight_contract.py`
Test quality: Partial
Risk level: High
Reason: Good API slices, but external/local skill packaging policy execution surface remains high-risk and should stay deny-by-default.
