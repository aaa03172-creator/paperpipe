# Review Coverage

Status values: reviewed, skimmed, skipped, pending.

## Coverage Summary

- Production files/modules discovered: 258 tracked files under `backend/**/*.py`, `src/**/*.py`, and `frontend/src/**/*`.
- Review depth: risk-based whole-repository review, with direct inspection of the highest-risk API, auth, state, artifact, background job, frontend API, CI, packaging, and release paths.
- Generated/vendor/build/cache/snapshot/lock artifacts: skipped unless directly relevant.
- Subagents used: architecture/API contracts, security/auth/secrets/privacy, data model/DB, async/jobs/reliability, frontend client boundaries, tests/CI/release safety.
- Reviewed or skimmed modules are listed below; pending entries are explicitly scoped blind spots, not silent omissions.

## Module Coverage

| Area | Status | Reason / prioritization |
| --- | --- | --- |
| `AGENTS.md` | reviewed | Repository rules, review policy, architectural boundaries. |
| `README.md` | reviewed | Install/runtime entry points, user-facing commands, security setup. |
| `docs/Lattice_v3_Master_Spec.md` | reviewed | Canonical API/runtime contract and error envelope expectations. |
| `docs/PERSONA_MODE_BOUNDARY.md` | skimmed | Architecture boundary context; no direct finding. |
| Other architecture/contribution docs under `docs/` | skimmed | Used to orient canonical docs, UX/product rules, and operating notes; not exhaustively line-reviewed. |
| `pyproject.toml` | reviewed | Python version, dependencies, package data, CLI entry points. |
| `requirements.txt` | reviewed | Dependency parity with package metadata. |
| `frontend/package.json` | reviewed | Frontend build/lint/e2e commands and dependency surface. |
| `.github/workflows/` | reviewed | CI/release gates, Python version mismatch, smoke command setup. |
| Runtime/deployment configs | skimmed | Local/server environment controls reviewed where tied to auth/secrets; external infra not visible. |
| `backend/main.py` | reviewed | FastAPI app, auth middleware, private route list, error handlers, jobs, artifacts, SSE/static UI. |
| `backend/routers/feedback.py` | reviewed | Mutation response contract. |
| `backend/routers/artifact_generation_outcomes.py` | reviewed | Mutation response contract. |
| `backend/routers/paper_notes.py` | reviewed | Note/reference parsing, API compatibility, link boundary. |
| `backend/routers/protocol_cards.py` | reviewed | Artifact mutation contracts and protocol attachment boundary. |
| `backend/routers/meeting_packs.py` | reviewed | Artifact mutation contract and pack access. |
| `backend/routers/image_evidence.py` | reviewed | Derivative artifact serving and bundle access boundary. |
| Other `backend/routers/*.py` | skimmed | Route inventory, response-model patterns, artifact access; no exhaustive endpoint-by-endpoint review. |
| `backend/services/job_runner.py` | reviewed | Deep-read side effects, artifacts, privacy lanes, cancellation/failure behavior. |
| `src/jobs/queue.py` | reviewed | Queue concurrency, duplicate jobs, run ID assignment, execution-run sync. |
| `src/jobs/worker.py` | reviewed | Worker loop, success/failure persistence, cancellation result handling, heartbeat/logging. |
| `src/jobs/schemas.py` | skimmed | Job API contracts and client compatibility. |
| `src/db_utils.py` | reviewed | SQLite schema init/migrations, paper state writes, Zotero sync, queue tables. |
| `scripts/init_db.py` | reviewed | Canonical DB schema creation. |
| `scripts/migrate_legacy.py` | skimmed | Migration context; no direct finding. |
| `scripts/check_sqlite_restore_drill.py` | reviewed | Backup/restore readiness coverage. |
| `src/services/event_log.py` | reviewed | Execution-run upsert, events, audit persistence. |
| `src/services/identity.py` | reviewed | Job/run ID helpers. |
| `src/services/runtime_paths.py` | reviewed | Runtime roots, artifact path helpers, ID-to-path mapping. |
| `src/services/stale_jobs.py` | reviewed | Stale job/reclaim interaction with artifact/job state. |
| `src/protocol_attachments/` | reviewed | Attachment store/service path boundary and upload persistence. |
| `src/image_evidence/` | reviewed | Image evidence bundle store/service path boundary. |
| `src/meeting_packs/` | skimmed | Store path shape and artifact contract; deeper generation semantics not fully reviewed. |
| `src/chart_packs/` | skimmed | Store path shape and artifact contract; deeper chart-generation correctness not fully reviewed. |
| `src/method_comparisons/` | skimmed | Store/export path shape; statistical/methodological correctness not fully reviewed. |
| `src/paper_syntheses/` | skimmed | Store path shape and manifest compatibility. |
| `src/protocol_cards/` | skimmed | Store/version behavior and attachment interactions. |
| `src/talk_packs/` | skimmed | Store path shape and preview artifact serving. |
| `src/skills/` | skimmed | Policy/allowlist boundary; no runtime execution pass. |
| `config/skills_policy.yaml` | skimmed | Skill adoption boundary; no direct finding. |
| `src/ingest/` | reviewed | Parser options, cloud table fallback, external payload boundary. |
| `src/agents/ingest_agent.py` | reviewed | Table extraction pass orchestration and cloud fallback trigger. |
| `src/ingest/cloud_table_fallback.py` | reviewed | External OpenAI table extraction request. |
| `src/agents/stats_agent.py` | reviewed | Undeclared `langgraph` dependency. |
| Other `src/agents/` | skimmed | LLM-facing runtime context; not exhaustively prompt-reviewed. |
| `src/downloader/` and `src/providers/` | skimmed | External fetch/download behavior; file-stability issue reviewed through watcher path. |
| `src/downloads_watcher.py` | reviewed | PDF movement, matching, review queue behavior. |
| `src/schemas/` | skimmed | Contract inventory; targeted schema gaps captured. |
| `src/cli.py` | skimmed | CLI entry points, `deepread --verify`, launcher commands. |
| `scripts/release_macos_personal_runtime.py` | reviewed | Release preflight readiness checks. |
| `tests/test_release_macos_personal_runtime.py` | reviewed | Release preflight regression coverage. |
| `tests/test_packaging_entrypoints.py` | reviewed | Packaging installability coverage. |
| Other `tests/` | skimmed | Targeted coverage for jobs, API keys, identity, DB, artifact lanes; not every test file line-reviewed. |
| `frontend/src/App.tsx` | skimmed | Route shell and major page routing. |
| `frontend/src/main.tsx` | skimmed | App bootstrap. |
| `frontend/src/app/lib/config.ts` | reviewed | Browser env flags and mock fallback default. |
| `frontend/src/app/lib/api.ts` | reviewed | API prefix, mock fallback, caches, paper/note endpoints. |
| `frontend/src/app/lib/sse.ts` | skimmed | Reconnect behavior; no direct finding. |
| `frontend/src/app/lib/accessSummary.ts` | reviewed | Link passthrough into UI. |
| `frontend/src/app/lib/types.ts` | skimmed | Client-side response contract references. |
| `frontend/src/app/pages/PaperNotesListPage.tsx` | reviewed | Fallback data installation and note list state. |
| `frontend/src/app/pages/PaperNoteDetailPage.tsx` | reviewed | Reference link rendering. |
| `frontend/src/app/pages/TriageDashboard.tsx` | reviewed | Access-summary link rendering. |
| Other `frontend/src/app/pages/` | skimmed | Routing/state/forms/client-server boundaries; no exhaustive UI copy/layout review. |
| `frontend/src/app/stores/` | skimmed | Client state inventory; no direct finding. |

## Skipped

| Area | Status | Reason |
| --- | --- | --- |
| `frontend/node_modules/`, `frontend/dist/`, `dist/`, `build/` | skipped | Generated/vendor/build output. |
| `.venv*`, `.pytest_cache/`, `.ruff_cache/`, caches | skipped | Local environment/cache output. |
| Lockfiles | skipped | Excluded by instruction unless directly relevant; dependency declarations were reviewed instead. |
| Snapshots, baselines, generated logs, historical artifact directories | skipped | Generated or runtime data; not needed for confirmed findings. |
| Obvious fixtures under tests/sample output | skipped | Excluded unless directly tied to a finding. |

## Remaining Blind Spots

- No live production SQLite contents, historical artifact directories, or deployment secrets/infrastructure were inspected.
- Static path traversal analysis found weak ID confinement but did not confirm an exploit; API tests should verify encoded traversal behavior.
- Frontend was built but not exercised with Playwright in this pass.
- Full pytest suite was not run; focused packaging/release/identity tests were run and failed due the local `.venv314` lacking `pip` for packaging wheel tests.
- Scientific/biomedical correctness of generated claims, tables, notes, and chart content was outside this code review pass.
