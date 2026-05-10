# Runtime Regression Tests Staging Prep (2026-03-23)

## Scope
Test-only lane for regression coverage that locks recently landed runtime behavior.

## Included files
- `/Users/jangseongjin/paperpipe/tests/full_integration_test.py`
- `/Users/jangseongjin/paperpipe/tests/test_db_utils_download_attempts.py`
- `/Users/jangseongjin/paperpipe/tests/test_downloads_watcher.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_events_persistence.py`
- `/Users/jangseongjin/paperpipe/tests/test_pr_scope_guard.py`
- `/Users/jangseongjin/paperpipe/tests/test_processor_pdf_context.py`
- `/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Runtime_Regression_Tests_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `pytest -q tests/test_jobs_events_persistence.py tests/test_worker_job_runner_chain.py tests/test_downloads_watcher.py tests/test_db_utils_download_attempts.py tests/full_integration_test.py tests/test_pr_scope_guard.py tests/test_processor_pdf_context.py`

Temp closure:
- same pytest command against a clean checkout with only these test files applied

## Notes
- This lane adds no new runtime behavior. It only locks already-landed identity, claimset, issue-state, path, and PR-scope behavior.
