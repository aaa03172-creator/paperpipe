# Deep Read Note-State Promotion Staging Prep (2026-03-25)

## Scope
Close the currently-open deep-read note-state promotion lane without widening into unrelated visual/docs/runtime shells.

## Included tracked files
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/routers/paper_notes.py`
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/jobs/queue.py`
- `/Users/jangseongjin/paperpipe/src/jobs/schemas.py`
- `/Users/jangseongjin/paperpipe/src/jobs/worker.py`
- `/Users/jangseongjin/paperpipe/src/llm_provider.py`
- `/Users/jangseongjin/paperpipe/src/schemas/paper_notes.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/api.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/sse.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/types.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/package.json`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`
- `/Users/jangseongjin/paperpipe/tests/test_event_log_db.py`
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_ingest_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py`
- `/Users/jangseongjin/paperpipe/tests/test_papers_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md`
- `/Users/jangseongjin/paperpipe/docs/WEB_VIEWER.md`

## Included untracked files
- `/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py`
- `/Users/jangseongjin/paperpipe/frontend/playwright.backend.parser.config.ts`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_fake_worker_for_e2e.py`
- `/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py`

## Explicitly excluded
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts-snapshots/`
- `/Users/jangseongjin/paperpipe/scripts/bootstrap.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md`
- broader canonical/docs packaging tail under `/Users/jangseongjin/paperpipe/docs/reports/`

## Verification
Run sequentially because backend parser-worker and backend smoke share the same e2e runtime root and will contaminate each other if executed in parallel.
For clean temp-worktree verification, export `PAPERPIPE_CONFIG_PATH=/tmp/.../config.example.yaml` before running the Python/API subset because repo startup still assumes an explicit config path in a fresh checkout.

1. Python targeted regression
   - `pytest -q /Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py /Users/jangseongjin/paperpipe/tests/test_papers_api.py /Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py /Users/jangseongjin/paperpipe/tests/test_event_log_db.py /Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py /Users/jangseongjin/paperpipe/tests/test_job_runner_ingest_backend.py`
   - Result: `50 passed`

2. Frontend build
   - `cd /Users/jangseongjin/paperpipe/frontend && npm run build`
   - Result: passed

3. Mock parser route flow
   - `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.mock.config.ts /Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts -g "workbench query param scopes parser pilot override into the enqueue path|workbench rail keeps parser pilot query when selecting another paper"`
   - Result: `2 passed`

4. Backend cold-load parser metadata checks
   - `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts /Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts -g "backend workbench shows requested and resolved parser backends separately|backend workbench does not infer requested parser from route query when persisted job metadata is absent"`
   - Result: `2 passed`

5. Backend parser-worker flow
   - `cd /Users/jangseongjin/paperpipe/frontend && PAPERPIPE_E2E_ENABLE_PARSER_WORKER=1 npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.backend.parser.config.ts`
   - Result: `2 passed`

6. Docs lint
   - `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
   - Result: passed

## Notes
- `AnalysisWorkbench` now distinguishes three parser-selection states:
  - cold-load real backend without persisted parser metadata: hidden
  - queued/requested-only state: `Requested parser ...`
  - resolved fallback: `Parser fitz_pdfplumber (requested docling)`
- `run_backend_for_e2e.sh` now anchors itself to repo root and uses an isolated runtime DB at `/Users/jangseongjin/paperpipe/frontend/.e2e-backend-runtime/storage/state.db`.
- Initial timeline hydration now aborts if the screen no longer owns the job, so completed fixture logs do not overwrite a just-enqueued parser run.
