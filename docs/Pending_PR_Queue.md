# Pending PR Queue

## PR-DOC-Blueprint-v2
- Title: `docs(blueprint): review and promote pragmatic blueprint v2`
- Priority: Medium
- Purpose: Keep the proposed v2 blueprint isolated from active runtime refactors.
- Source Draft: `docs/drafts/PaperPipe_v3_Pragmatic_Blueprint_v2_2026-02-22.md`
- Current Baseline (kept on main flow): `docs/PaperPipe_v3_Pragmatic_Blueprint_2026-02-22.md`
- Scope (docs-only):
  - Compare v1/v2 sections and resolve policy conflicts.
  - Decide replacement strategy for the baseline file.
  - Add a short migration note for changed PR sequencing.
- Merge Gate:
  - No runtime code changes in the PR.
  - Reviewer sign-off required (Antigravity + Codex).

## PR-BE-JobContract-Hardening
- Title: `fix(api-jobs): persist clean_reindex and harden startup/db paths`
- Priority: High
- Purpose: Remove API contract drift (`clean_reindex` dropped) and harden startup behavior in empty/new DB environments.
- Scope:
  - `backend/main.py`
  - `src/db_bootstrap.py`
  - `src/jobs/queue.py`
  - `src/jobs/schemas.py`
  - `tests/test_jobs_api_smoke.py`
  - `tests/test_papers_api.py`
- Merge Gate:
  - `pytest -q` must remain green.
  - `/jobs/deepread` must persist `clean_reindex` in `/jobs/{id}` payload.

## PR-BE-Queue-Claim-Atomic
- Title: `fix(jobs): make claim_next_job transactional and add queue claim tests`
- Priority: High
- Purpose: Prevent duplicate claim windows under parallel worker polling.
- Scope:
  - `src/jobs/queue.py`
  - `tests/test_jobs_queue_claim_next.py`
- Merge Gate:
  - `tests/test_jobs_queue_claim_next.py` passes.
  - `pytest -q` full suite passes.

## PR-QA-JobRunner-FailurePaths
- Title: `test(job-runner): add failure and cancellation path coverage`
- Priority: High
- Purpose: Lock fail-safe behavior for missing PDF, reader runtime error, verifier failure, and mid-run cancellation.
- Scope:
  - `tests/test_job_runner_failure_paths.py`
- Merge Gate:
  - `tests/test_job_runner_failure_paths.py` passes.
  - `pytest -q` full suite passes.

## PR-QA-JobCancel-Transitions
- Title: `test(api-jobs): add cancel endpoint state-transition coverage`
- Priority: High
- Purpose: Ensure `/jobs/{id}/cancel` enforces expected queued/running -> cancelled transitions and unblocks next claim.
- Scope:
  - `tests/test_jobs_cancel_api.py`
- Merge Gate:
  - `tests/test_jobs_cancel_api.py` passes.
  - `pytest -q` full suite passes.

## PR-BE-Worker-CancelSync
- Title: `fix(worker): sync cancelled status when runner returns cancelled`
- Priority: High
- Purpose: Prevent jobs from staying `running` when the runner exits with `cancelled` without prior DB status flip.
- Scope:
  - `src/jobs/worker.py`
  - `tests/test_worker_cancellation_sync.py`
- Merge Gate:
  - `tests/test_worker_cancellation_sync.py` passes.
  - `pytest -q` full suite passes.

## PR-QA-Runtime-Size-Guard
- Title: `test(health): add runtime module size guardrail`
- Priority: Medium
- Purpose: Keep large-module growth visible by enforcing the 700-line runtime threshold in automated tests.
- Scope:
  - `tests/test_runtime_module_size_guard.py`
  - `docs/engineering_health_2026-02-21.md`
- Merge Gate:
  - `tests/test_runtime_module_size_guard.py` passes.
  - `pytest -q` full suite passes.

## PR-BE-Queue-Legacy-Recovery
- Title: `fix(jobs): auto-recover enqueue against legacy column-missing schema`
- Priority: Medium
- Purpose: Allow enqueue to self-heal when jobs table exists but lacks newer columns (migration drift).
- Scope:
  - `src/db_bootstrap.py`
  - `src/jobs/queue.py`
  - `tests/test_jobs_queue_schema_recovery.py`
- Merge Gate:
  - `tests/test_jobs_queue_schema_recovery.py` passes.
  - `pytest -q` full suite passes.

## PR-BE-JobRunner-StageSplit
- Title: `refactor(job-runner): extract stage helpers while preserving fail-safe flow`
- Priority: Medium
- Purpose: Keep job runner maintainable by splitting repeated stage logic into helpers without behavior change.
- Scope:
  - `backend/services/job_runner.py`
- Merge Gate:
  - `tests/test_job_runner_failure_paths.py` passes.
  - `tests/test_worker_job_runner_chain.py` passes.
  - `pytest -q` full suite passes.
