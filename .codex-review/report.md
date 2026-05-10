# Functional Behavior, Conflict, and Wiring Review Report

## 1. Executive summary

Overall functional risk level: Medium after the implementation pass

Major code paths that appear connected and working:
FastAPI route registration, paper notes/list/detail, job enqueue/worker happy path, SSE/job timeline, protocol attachments, paper synthesis backend split manifest/markdown routes, Image Evidence registration/read with ID validation, artifact-family storage with ID/path validation, Project Memory storage with ID/path validation, structured paper-state storage with vault path confinement, stored vault note-path resolution for export/job/CLI/Obsidian flows, Research DNA API/CLI storage with ID/path validation, downloads watcher unmatched/rename handling, meeting-pack write error handling, feedback import behavior, and the main Vite route/API structure. Targeted verification passed after fixes, including backend smoke, full pytest, frontend lint/build, focused eslint, meeting-pack Playwright coverage, and the backend-backed frontend Playwright verification lane.

Remaining confirmed broken code paths:
No P1/P2/P3 code path from this review remains confirmed broken in the current working tree. Residual risk remains around script-only one-off utilities outside the reviewed eval/runtime-path set, real watchdog/browser behavior, and live deployment/reverse-proxy behavior.

Current-branch reconciliation:
The implementation pass resolved the review's high-priority unresolved items: `/api/*` bridge trust boundary, Image Evidence ID/root validation, artifact-family store ID/root validation, Project Memory store ID/root validation, structured paper-state vault confinement, stored vault note-path confinement, Research DNA direct-store ID/root validation, unmatched-download triage persistence, artifact route ambiguity, import-time feedback/Ollama initialization, frontend visual-evidence lineage display, meeting-pack write fallback, import-health default coverage, and watcher rename handling.

Modules that conflict:
Previously conflicting modules have targeted fixes in the working tree: API auth middleware vs `/api/*` bridge behavior; Image Evidence schema vs filesystem store; downloads watcher unmatched sentinel vs `review_queue` FK; artifact route patterns vs slash-bearing paper IDs; backend import health vs feedback router Ollama initialization; backend paper synthesis lineage vs frontend types/formatters; meeting-pack write behavior vs frontend docs.

Disconnected/partially wired code:
Research DNA was verified as intentionally API/CLI-only in the current docs, not a missing frontend route. Downloads watcher `on_moved`, visual-evidence lineage display, and meeting-pack no-mock write handling are now wired in the working tree.

Highest-value missing tests:
The highest-value tests from this review were added or updated: unauthenticated `/api/*` private-route tests, Image Evidence traversal tests, canonical-schema unmatched-download tests, slash-bearing artifact route tests, feedback lazy-import/import-health checks, visual evidence ledger frontend contract coverage, meeting-pack no-mock-write Playwright coverage, and watcher rename handling tests.

## 2. Scope reviewed

Reviewed:
FastAPI app/middleware, registered routes, paper notes/papers/workbench APIs, job queue/worker/runner, event/timeline path, artifact family routers, Image Evidence storage, Chart Pack storage, Meeting Pack storage, Method Comparison storage, Paper Synthesis storage, Protocol Card storage, Protocol Attachment storage, Talk Pack storage, Project Memory storage/context links, structured paper-state storage, paper synthesis contracts, protocol attachment API, artifact review/outcome JSONL logs, profile config store, paper operator-state store pathing, handoff artifact writers, artifact-history eval scripts, parser-eval inventory script, runtime cache/install-layout paths, downloads watcher, frontend route shell/API client/types, runtime schema/config.

Partially reviewed:
Skills internals, meeting/method/talk pack deep service behavior, stale-job recovery, and scientific output quality sidecars.

Skipped:
Live external service calls, production DB contents, deployment reverse proxy, generated/vendor/cache files.

Existing historical review subdirectories:
`.codex-review/dead-code-audit/`, `.codex-review/paper-pipeline-review/`, and `.codex-review/test-gap-review/` predate this top-level functional wiring review. Their older `Confirmed` or `Needs verification` notes were not normalized into the current six required artifacts unless the same issue was re-reviewed and listed in this report.

Needs verification:
Whether script-only one-off utilities outside the reviewed eval/runtime-path set share the same path-boundary class; browser rename behavior in a real watchdog environment; live deployment auth/reverse-proxy assumptions.

## 3. Flow trace summary

| Flow name | Conclusion | Risk level | Key files | Main concern |
| --- | --- | --- | --- | --- |
| Frontend paper list and note detail | Probably working | Low | `frontend/src/app/lib/api.ts`, `backend/routers/paper_notes.py` | HTTP-error fallback risk resolved; continue browser regression coverage |
| Browser `/api/*` request to protected backend route | Working after fix | Medium | `backend/main.py` | protected routes now require API key/beta auth or browser-trust signal |
| Deep Read enqueue to worker completion | Probably working | Low | `src/jobs/queue.py`, `src/jobs/worker.py`, `backend/services/job_runner.py` | failed artifact_dir persistence resolved; continue smoke coverage |
| Job events and timeline | Working | Low | `backend/main.py`, `src/services/event_log.py` | no confirmed registration gap |
| Paper synthesis compiled knowledge | Probably working | Low | `src/paper_syntheses/service.py`, `frontend/src/app/lib/types.ts` | visual evidence lineage kind now has frontend type/label support |
| Image Evidence registration/read | Working after fix | Medium | `src/schemas/image_evidence.py`, `src/image_evidence/store.py` | caller IDs are validated and confined to storage root |
| Chart Pack generation/storage | Working after fix | Medium | `src/schemas/chart_pack.py`, `src/chart_packs/store.py` | chart pack/chart IDs and artifact filenames are now safe path segments |
| Meeting/Method/Paper/Protocol/Talk artifact stores | Working after fix | Medium | `src/meeting_packs/store.py`, `src/method_comparisons/store.py`, `src/paper_syntheses/store.py`, `src/protocol_cards/store.py`, `src/protocol_attachments/store.py`, `src/talk_packs/store.py` | store helpers now reject path-like IDs while preserving API 404 behavior |
| Project Memory storage/context links | Working after fix | Low | `src/project_memory/store.py`, `backend/routers/project_context_links.py` | project memory IDs now reject path-like direct-store values |
| Structured paper-state and note-path storage | Working after fix | Medium | `src/skills/storage.py`, `src/skills/runner.py`, `src/exporter.py`, `backend/services/job_runner.py`, `src/services/cli_workflows.py`, `src/obsidian.py` | slug/run segments, frontmatter structured paths, stored `obsidian_path`, and CSV `Note_Path` values are confined to the vault |
| Protocol attachment draft | Working after fix | Low | `backend/routers/protocol_cards.py`, `src/protocol_attachments/service.py`, `src/protocol_attachments/store.py` | targeted tests passed |
| Downloads watcher PDF handling | Working after fix | Medium | `src/downloads_watcher.py`, `scripts/init_db.py` | unmatched sentinel and move-event handling covered by tests |
| Artifact pages | Probably working | Medium | feature routers/stores | route registration ok; standardize path confinement and write fallback |
| Artifact run bundle/file lookup | Working after fix | Medium | `backend/main.py` | ambiguous slash-bearing run URLs recover to bundle lookup |
| Feedback import/provider path | Working after fix | Low | `backend/routers/feedback.py`, `src/llm_provider.py` | feedback retriever is lazy-initialized |
| Research DNA API | Working after fix | Low | `backend/main.py`, `src/profiles/*`, `README.md`, `docs/CLI_WORKFLOW_REFERENCE.md` | documented as API/CLI lane; direct store paths now enforce safe IDs |

## 4. Conflict summary

| Conflict | Status | Files involved | Impact | Suggested fix |
| --- | --- | --- | --- | --- |
| `/api/*` bridge bypasses API-key behavior | Resolved in working tree | `backend/main.py` | protected routes reachable via bridge | browser-trust/auth gate added before bridge key injection |
| Image Evidence ID vs filesystem root | Resolved in working tree | `src/schemas/image_evidence.py`, `src/image_evidence/store.py` | out-of-root writes | strict ID validation and path confinement added |
| Artifact/profile/memory/state store IDs and stored/user-supplied note paths vs filesystem roots | Resolved in working tree | `src/chart_packs/store.py`, `src/meeting_packs/store.py`, `src/method_comparisons/store.py`, `src/paper_syntheses/store.py`, `src/protocol_cards/store.py`, `src/protocol_attachments/store.py`, `src/talk_packs/store.py`, `src/project_memory/store.py`, `src/skills/storage.py`, `src/profiles/research_dna_store.py`, `src/exporter.py`, `backend/services/job_runner.py`, `src/services/cli_workflows.py`, `src/obsidian.py`, `src/meeting_packs/source_resolver.py` | out-of-root writes/reads via direct store, persisted note-path, or note selector helpers | safe-segment validation and root/vault confinement added |
| Paper synthesis lineage kind mismatch | Resolved in working tree | `src/schemas/paper_synthesis.py`, `frontend/src/app/lib/types.ts` | mislabeled lineage | frontend `visual_evidence_ledger` type/label support added |
| Downloads unmatched sentinel vs FK | Resolved in working tree | `src/downloads_watcher.py`, `scripts/init_db.py` | no durable unmatched triage | sentinel paper row is ensured before enqueue |
| Auto mock fallback vs live backend errors | Resolved in current branch | `frontend/src/app/lib/config.ts`, `frontend/src/app/lib/api.ts` | HTTP errors no longer fall back to fixtures | keep no-mock-on-401 coverage |
| Cloud table fallback vs privacy boundary | Resolved in current branch | `src/ingest/cloud_table_fallback.py`, `backend/services/job_runner.py` | preflight callback now blocks before LLM extraction | keep blocking preflight coverage |
| Artifact route shadowing | Resolved in working tree | `backend/main.py`, `src/services/identity.py` | run artifacts unreachable for slash IDs | ambiguous slash-bearing bundle URLs recover in the file route |
| Meeting-pack write fallback vs docs | Resolved in working tree | `frontend/src/app/lib/api.ts`, `frontend/README.md` | fake write success | write path now fails outside explicit mock mode |
| Backend import initializes Ollama | Resolved in working tree | `backend/routers/feedback.py`, `src/llm_provider.py` | startup/import checks depend on Ollama | lazy provider initialization added |

## 5. Disconnected code summary

| Item | Status | Expected connection | Actual connection | Impact | Suggested fix |
| --- | --- | --- | --- | --- | --- |
| Image Evidence ID validation | Resolved in working tree | schema/store root validation | strict ID pattern and resolved-path confinement | out-of-root writes blocked | keep traversal coverage |
| Artifact/profile/memory/state path helpers | Resolved in working tree | schema/store root validation plus vault note-path confinement | safe-segment checks and `resolve_vault_relative_path()` | direct store/vault path escape blocked | keep path-like ID and stored note-path coverage |
| `/api/*` bridge trust proof | Resolved in working tree | trusted UI/session or caller auth | browser-trust/auth gate before key injection | protected API exposure blocked for unauthenticated non-browser callers | keep bridge auth coverage |
| Unmatched download queue item | Resolved in working tree | durable triage record | sentinel paper row ensured before queue insert | unmatched follow-up persists | keep canonical FK schema coverage |
| Watcher rename handling | Resolved in working tree | created/moved handling | shared candidate processing handles `on_created` and `on_moved` | completed browser downloads processed | keep move-event coverage |
| Failed job artifact_dir | Resolved in current branch | artifact path persisted for all created runs | runner returns and worker persists failure/cancel artifact_dir | diagnostics discoverable | keep failure-path coverage |
| Visual evidence frontend display | Resolved in working tree | backend lineage kind rendered | type/label now include `visual_evidence_ledger` | UI lineage label is explicit | keep contract coverage |
| Research DNA frontend reachability | Verified intended API/CLI-only | no frontend route expected in current product surface | README and CLI workflow docs explicitly mark API/CLI lane | not a missing route | no source change needed |
| Artifact run endpoint for slash IDs | Resolved in working tree | valid paper IDs resolve to run/file artifacts | ambiguous slash-bearing run URL recovers to bundle lookup | run artifacts reachable | keep slash-bearing route coverage |
| Feedback provider startup | Resolved in working tree | initialize on route use | feedback retriever lazy proxy | import/startup no longer initializes retriever | keep import-health coverage |
| Meeting-pack write path | Resolved in working tree | live backend write or explicit mock | generate write no longer falls back outside forced mock | false persisted result blocked | keep Playwright no-mock-write coverage |

## 6. Findings summary

| ID | Severity | Confidence | Category | File/line | Short issue | Suggested action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 | High | Conflict | `backend/main.py:1249` | `/api/*` bridge bypasses root API-key behavior | resolved in working tree |
| 2 | P1 | High | Missing wiring | `src/image_evidence/store.py:17` | Image Evidence ID escapes root | resolved in working tree |
| 3 | P1 | High | Conflict | `src/downloads_watcher.py:295` | unmatched PDFs not queued under FK schema | resolved in working tree |
| 4 | P1 | High | Functional behavior | `frontend/src/app/lib/config.ts:12` | mock fallback masks backend failures | resolved in current branch |
| 5 | P2 | High | Functional behavior | `src/ingest/cloud_table_fallback.py:199` | cloud table fallback lacks privacy preflight | resolved in current branch |
| 6 | P2 | High | Missing wiring | `src/jobs/worker.py:186` | failed artifacts can be orphaned | resolved in current branch |
| 7 | P2 | High | Contract mismatch | `frontend/src/app/lib/types.ts:995` | visual evidence lineage missing in frontend | resolved in working tree |
| 8 | P2 | Medium | Missing wiring | `src/downloads_watcher.py:347` | watcher likely misses rename completion | resolved in working tree |
| 9 | P2 | High | Functional behavior | `backend/routers/paper_notes.py:1402` | rendered links lack scheme allowlist | resolved in current branch |
| 10 | P1 | High | Conflict | `backend/main.py:5712` | artifact routes misparse slash-bearing paper IDs | resolved in working tree |
| 11 | P1 | High | Functional behavior | `backend/routers/feedback.py:33` | backend import initializes Ollama | resolved in working tree |
| 12 | P2 | High | Contract mismatch | `frontend/src/app/lib/api.ts:1240` | meeting-pack write falls back to mock | resolved in working tree |
| 13 | P2 | Medium | Test gap | `scripts/check_python_import_health.py:16` | import-health test misses default side effects | resolved in working tree |
| 14 | P3 | High | Disconnected code | `README.md:68`; `docs/CLI_WORKFLOW_REFERENCE.md:71` | Research DNA route absent by design | verified intended API/CLI-only; no code change |
| 15 | P2 | High | Conflict | `src/chart_packs/store.py:17`; `src/meeting_packs/store.py:15`; `src/project_memory/store.py:18`; `src/skills/storage.py:115`; `src/exporter.py:233`; `backend/services/job_runner.py:213`; `src/services/cli_workflows.py:52`; `src/obsidian.py:719`; `src/meeting_packs/source_resolver.py:778` | artifact/profile/memory/state helpers trusted caller IDs or stored/user-supplied vault paths for filesystem paths | resolved in working tree |
| 16 | P3 | High | Functional behavior | `scripts/backfill_operational_outputs.py:19`; `scripts/backfill_operational_outputs.py:70` | operational markdown backfill trusted stored note paths when checking missing exports | resolved in working tree |

## 7. Detailed findings

See `.codex-review/findings.md`.

## 8. Tests and commands

Commands run:
- `.venv/bin/python -m pytest -q tests/test_worker_job_runner_chain.py tests/test_jobs_api_smoke.py tests/test_db_schema_compat.py tests/test_paper_notes_api.py tests/test_paper_synthesis_frontend_contract.py tests/test_protocol_attachments_api.py`
  - Result: passed, `85 passed, 7 warnings in 203.02s`.
- `cd frontend && npm run build`
  - Result: passed, Vite production build completed.
- Route listing via `.venv/bin/python` importing `backend.main`.
  - Result: completed; noted Ollama connection side effect on import.
- Local Image Evidence root-escape reproduction.
  - Result: confirmed out-of-root write.
- Local `/api/jobs` auth bridge probe.
  - Result: `GET /jobs` 401; `GET /api/jobs` 200 without caller key.

Additional subagent verification:
- Jobs/events/downloads targeted set: `pytest tests/test_jobs_events_persistence.py tests/test_worker_heartbeat.py tests/test_downloads_watcher.py tests/test_jobs_api_smoke.py -q`
  - Result reported by subagent: `41 passed, 5 warnings`.
- Canonical-schema unmatched-download reproduction.
  - Result reported by subagent: `status=unmatched`, `review_queue_count=0`, FK failure.
- Artifact route-matching probe.
  - Result reported by subagent: `/artifacts/foo/bar/run1` matched the file route as `paper_id=foo`, `run_id=bar`, `artifact_name=run1`.
- Feedback/import-health focused checks.
  - Result reported by subagent: feedback/import-health tests passed, but default import-health probes can still hit import-time Ollama initialization.
- `.venv/bin/python -m pytest -q tests/test_chart_pack_schema.py tests/test_chart_pack_store.py tests/test_chart_pack_service.py tests/test_chart_packs_api.py`
  - Result: passed, `29 passed, 5 warnings in 1.44s`.
- `ruff check src/schemas/chart_pack.py src/chart_packs/store.py tests/test_chart_pack_schema.py tests/test_chart_pack_store.py --select F,E701,E9`
  - Result: passed.
- `.venv/bin/python -m pytest -q tests/test_research_dna_schema.py tests/test_research_dna_store.py tests/test_research_dna_service.py tests/test_research_dna_api.py`
  - Result: passed, `26 passed, 5 warnings in 2.18s`.
- `ruff check src/profiles/research_dna_store.py tests/test_research_dna_store.py --select F,E701,E9`
  - Result: passed.
- `./scripts/run_backend_api_smoke.sh`
  - Result: passed after the artifact/profile store-boundary changes.
- `.venv/bin/python -m pytest -q tests/test_meeting_pack_store.py tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_protocol_card_store.py tests/test_protocol_attachment_store.py tests/test_talk_pack_store.py`
  - Result: passed, `36 passed, 5 warnings in 2.43s`.
- `ruff check src/meeting_packs/store.py src/method_comparisons/store.py src/paper_syntheses/store.py src/protocol_cards/store.py src/protocol_attachments/store.py src/talk_packs/store.py tests/test_meeting_pack_store.py tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_protocol_card_store.py tests/test_protocol_attachment_store.py tests/test_talk_pack_store.py --select F,E701,E9`
  - Result: passed.
- `.venv/bin/python -m pytest -q tests/test_meeting_packs_api.py tests/test_method_comparisons_api.py tests/test_paper_syntheses_api.py tests/test_protocol_cards_api.py tests/test_protocol_attachments_api.py tests/test_talk_packs_api.py`
  - Initial result: one failure where Protocol Card missing-safe-ID reads changed from 404 to 400; store validation was narrowed to path-safety only.
  - Final result: passed, `48 passed, 5 warnings in 99.35s`.
- `.venv/bin/python -m pytest -q tests/test_project_memory_store.py tests/test_project_memory_schema.py tests/test_runtime_paths_project_memory.py tests/test_project_context_link_api.py`
  - Result: passed, `21 passed, 5 warnings in 4.06s`.
- `ruff check src/project_memory/store.py tests/test_project_memory_store.py --select F,E701,E9`
  - Result: passed.
- `.venv/bin/python -m pytest -q tests/test_chart_pack_schema.py tests/test_chart_pack_store.py tests/test_research_dna_store.py tests/test_meeting_pack_store.py tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_protocol_card_store.py tests/test_protocol_attachment_store.py tests/test_talk_pack_store.py tests/test_project_memory_store.py tests/test_project_context_link_api.py`
  - Result: passed, `81 passed, 5 warnings in 1.44s`.
- `.venv/bin/python -m pytest -q tests/test_storage_note_resolution.py tests/test_skills_api.py tests/test_paper_notes_api.py -k "structured or skills or operator_state"`
  - Result: passed, `26 passed, 41 deselected, 6 warnings in 2.26s`.
- `ruff check src/skills/storage.py tests/test_storage_note_resolution.py --select F,E701,E9`
  - Result: passed.
- `pytest -q tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py -k "obsidian_path or resolve_note_path_for_paper"`
  - Result: passed, `6 passed, 9 deselected, 5 warnings in 7.59s`.
- `pytest -q tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py tests/test_runtime_shell_scripts.py -k "obsidian_path or resolve_note_path_for_paper or deepread_falls_back_to_db_obsidian_path"`
  - Result: passed, `7 passed, 32 deselected, 5 warnings in 5.12s`.
- `pytest -q tests/test_obsidian_save.py tests/test_runtime_shell_scripts.py tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py -k "status or Note_Path or obsidian_path or resolve_note_path_for_paper or deepread_falls_back_to_db_obsidian_path"`
  - Result: passed, `8 passed, 35 deselected, 5 warnings in 5.94s`.
- `ruff check src/skills/storage.py src/exporter.py backend/services/job_runner.py src/services/cli_workflows.py src/obsidian.py tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py --select F,E701,E9`
  - Result: passed.
- `ruff check src/skills/storage.py src/exporter.py backend/services/job_runner.py src/services/cli_workflows.py src/obsidian.py tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py tests/test_obsidian_save.py tests/test_runtime_shell_scripts.py --select F,E701,E9`
  - Result: passed.
- `pytest -q tests/test_meeting_pack_source_resolver.py -k "project_note or paper_note or escaping_note_selector"`
  - Result: passed, `4 passed, 15 deselected, 5 warnings in 2.68s`.
- `ruff check src/meeting_packs/source_resolver.py tests/test_meeting_pack_source_resolver.py --select F,E701,E9`
  - Result: passed.
- `pytest -q tests/test_no_new_trial_extraction_alias.py`
  - Result: passed after removing deprecated alias literals from `.codex-review/dead-code-audit` review artifacts.
- `pytest -q tests/test_worker_job_runner_chain.py::test_failed_runner_preserves_original_error_when_handoff_write_fails tests/test_no_new_trial_extraction_alias.py`
  - Result: passed, `2 passed, 5 warnings in 19.84s`.
- `ruff check backend/main.py backend/services/job_runner.py src/meeting_packs/source_resolver.py tests/test_meeting_pack_source_resolver.py --select F,E701,E9`
  - Result: passed after removing an unused `artifact_paper_dir` import from `backend/main.py`.
- `pytest -q`
  - Initial post-review result: failed with `.codex-review/*` deprecated alias literals and an order-sensitive missing failure-handoff metadata flag.
  - Final pre-backfill-fix result: passed, `2051 passed, 5 skipped, 7 warnings in 460.94s`.
- `./scripts/run_backend_api_smoke.sh`
  - Result: passed after the Project Memory store-boundary change.
- `./scripts/run_backend_api_smoke.sh`
  - Result: passed after the structured paper-state vault confinement change.
- `./scripts/run_backend_api_smoke.sh`
  - Result: passed after the stored vault note-path confinement change.
- `./scripts/run_backend_api_smoke.sh`
  - Initial final-check result: failed on `backend/main.py` unused import.
  - Final result: passed after removing the unused import.
- `cd frontend && npm run lint`
  - Result: passed.
- `cd frontend && npm run build`
  - Result: passed, TypeScript compile and Vite production build completed.
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "canonical structured lookup|synthesizes from structured lookup"`
  - Result: passed, `2 passed`.
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "protocol knowledge detail layout|meeting pack detail layout"`
  - Result: passed after updating the two stale desktop snapshots, `4 passed`.
- `cd frontend && npm run verify:frontend:backend`
  - Result: passed after the frontend contract/snapshot updates: backend lane `136 passed, 13 skipped`; gated backend lane `1 passed`; parser-worker lane `2 passed`.
- `cd frontend && npm run verify:frontend`
  - Result: passed on the final all-lane rerun: mock lane `40 passed`; backend lane `136 passed, 13 skipped`; gated backend lane `1 passed`; parser-worker lane `2 passed`.
- `pytest -q tests/test_artifact_review_feedback_api.py tests/test_artifact_generation_outcome_api.py tests/test_runtime_paths_logs.py tests/test_runtime_paths_config.py tests/test_config_agent_path_defaults.py tests/test_storage_note_resolution.py -k "artifact or runtime or profiles or structured or operator_state"`
  - Result: passed, `23 passed, 2 deselected, 5 warnings in 5.65s`.
- `pytest -q tests/test_artifact_history_promotion_gate.py tests/test_artifact_history_capture_candidates.py tests/test_parser_eval_artifact_inventory.py tests/test_runtime_paths_cache.py tests/test_runtime_paths_bundle_assets.py tests/test_config_install_layout_paths.py`
  - Result: passed, `18 passed, 5 warnings in 0.92s`.
- Local `.venv/bin/python` probe for `scripts.backfill_operational_outputs._note_exists()`.
  - Result: confirmed `_note_exists(vault, {"obsidian_path": "../outside.md"})` returns `True` when the outside file exists.
- `pytest -q tests/test_backfill_operational_outputs.py -k escaping_obsidian_path`
  - Initial result: failed, confirming `collect_backfill_candidates()` skipped the escaping-path row before the fix.
  - Final result: passed after `_note_exists()` switched to `resolve_vault_relative_path()`.
- `pytest -q tests/test_backfill_operational_outputs.py`
  - Result: passed, `6 passed, 5 warnings in 2.14s`.
- `ruff check scripts/backfill_operational_outputs.py tests/test_backfill_operational_outputs.py --select F,E701,E9`
  - Result: passed.
- `pytest -q tests/test_backfill_operational_outputs.py tests/test_exporter_obsidian_path.py tests/test_storage_note_resolution.py tests/test_worker_job_runner_chain.py -k "backfill or obsidian_path or resolve_note_path_for_paper or vault_relative_path or escaping"`
  - Result: passed, `13 passed, 19 deselected, 5 warnings in 7.74s`.
- `pytest -q tests/test_backfill_operational_outputs.py tests/test_runtime_shell_scripts.py tests/test_exporter_obsidian_path.py tests/test_storage_note_resolution.py tests/test_worker_job_runner_chain.py -k "backfill or obsidian_path or resolve_note_path_for_paper or vault_relative_path or escaping or runtime"`
  - Result: passed, `38 passed, 18 deselected, 5 warnings in 14.41s`.
- `./scripts/run_backend_api_smoke.sh`
  - Result: passed after the backfill path-confinement fix.
- `pytest -q`
  - Final post-backfill-fix result: passed, `2064 passed, 5 skipped, 7 warnings in 470.55s`.
- `pytest -q tests/test_research_dna_api.py tests/test_research_dna_service.py tests/test_research_dna_store.py tests/test_research_dna_projection.py`
  - Result: passed, `28 passed, 5 warnings in 9.82s`.
- Final artifact-structure/status checks:
  - `git diff --check`: passed.
  - Required top-level review artifacts exist and are non-empty.
  - Top-level review artifacts contain no remaining `Conclusion: Broken`, `Conclusion: Needs verification`, or `Status: Confirmed`.
  - `pytest -q tests/test_backfill_operational_outputs.py`: passed, `6 passed, 5 warnings in 2.72s`.
  - `ruff check scripts/backfill_operational_outputs.py tests/test_backfill_operational_outputs.py --select F,E701,E9`: passed.
- Post-handoff targeted recheck on 2026-05-11:
  - `pytest -q tests/test_backfill_operational_outputs.py`: passed, `6 passed, 5 warnings in 3.34s`.
  - `ruff check scripts/backfill_operational_outputs.py tests/test_backfill_operational_outputs.py --select F,E701,E9`: passed.
  - `git diff --check -- <review/backfill tracked files>`: passed.

Failures:
- Initial `ruff check src/skills/storage.py src/exporter.py backend/services/job_runner.py src/services/cli_workflows.py src/obsidian.py tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py --select F,E701,E9` flagged existing/in-scope exporter lint issues (`os` unused, duplicate `artifacts_root`, unused local, one-line conditionals). These were cleaned up and the final ruff command passed.
- Initial `pytest -q tests/test_exporter_obsidian_path.py tests/test_worker_job_runner_chain.py -k "obsidian_path or resolve_note_path_for_paper"` failed because the new test fixture did not create the minimal `papers` table before insertion. The fixture was corrected and the final pytest command passed.
- Full `pytest -q` initially failed because untracked `.codex-review/dead-code-audit` and `.codex-review/test-gap-review` artifacts repeated a deprecated compatibility alias literal. The review artifacts were reworded and `tests/test_no_new_trial_extraction_alias.py` passed.
- Full `pytest -q` also surfaced an order-sensitive failure-handoff metadata gap: `bootstrap_meta` could miss `artifact_acceptance_contract_written` and `artifact_quality_gate_written` when handoff artifact writing failed. The failure path now initializes both flags to `False` before attempting handoff writes, and the targeted plus full suites pass.
- Final backend smoke initially failed because `backend/main.py` had an unused `artifact_paper_dir` import. The unused import was removed and backend smoke passed.
- Frontend backend verification initially failed on two stale request-count expectations and two stale visual snapshots. The request-count assertions were updated to match the current canonical structured lookup path, the stale snapshots were refreshed, and `npm run verify:frontend:backend` passed.

Commands not run and why:
- Live external service calls: intentionally avoided.

## 9. Remaining blind spots

- Research DNA was verified as API/CLI-only for frontend reachability, direct store ID paths were hardened, and local API/service/store/projection tests pass; live fetch/ranking providers were not exercised.
- Artifact path-boundary analysis covered Image Evidence, Chart Pack, Meeting Pack, Method Comparison, Paper Synthesis, Protocol Card, Protocol Attachment, Talk Pack, Project Memory, structured paper-state storage, stored vault note-path consumers, Research DNA, artifact review/outcome logs, profile config store, paper operator-state store pathing, handoff artifact writers, artifact-history eval scripts, parser-eval inventory, and runtime cache/install-layout paths; script-only one-off utilities outside these reviewed sets were not exhaustively audited.
- Real browser download rename behavior should still be verified with watchdog or an integration test.
- Live deployment auth/reverse proxy assumptions were not inspected.
- Scientific correctness of biomedical outputs was out of scope.

## 10. Recommended next actions

1. Keep the new targeted regression tests in CI or the backend/frontend smoke path: `/api/*` auth bridge, Image Evidence traversal, canonical unmatched download, slash-bearing artifact routes, feedback import health, meeting-pack no-mock write, visual evidence ledger UI contract, and watcher rename handling.
2. Continue the same path-boundary audit for one-off scripts and generated/cache utilities outside the reviewed artifact/profile/eval/runtime-path families.
3. Run a real watchdog/browser-download integration check to confirm OS-level move events match the simulated `on_moved` test.
4. Inspect live deployment auth/reverse-proxy behavior before exposing the backend beyond the local UI shell.
