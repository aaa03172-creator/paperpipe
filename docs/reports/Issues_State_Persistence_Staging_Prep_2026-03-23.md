# Issues-State Persistence Staging Prep (2026-03-23)

## Goal
Split a narrow runtime lane that persists `issues_state` consistently from processor-owned and watcher-owned PDF ingestion paths.

## Included
- `/Users/jangseongjin/paperpipe/src/processor.py`
- `/Users/jangseongjin/paperpipe/src/watcher.py`
- `/Users/jangseongjin/paperpipe/tests/test_watcher_issue_state.py`
- `/Users/jangseongjin/paperpipe/tests/test_db_utils_sync_zotero_issue_state.py`
- `/Users/jangseongjin/paperpipe/tests/test_db_utils_update_paper_status_safety.py`
- `/Users/jangseongjin/paperpipe/tests/test_full_pipeline.py`
- `/Users/jangseongjin/paperpipe/tests/test_processor_institutional_proxy.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Issues_State_Persistence_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- `src/processor.py` now exposes `derive_saved_issues_state(...)` and uses it when persisting paper rows.
- `src/watcher.py` reuses the same helper so local watcher ingestion writes the same `issues_state` contract.
- The focused tests lock both the producer-side mapping and the DB-side safety assumptions relied on by that persistence path.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/tests/test_downloads_watcher.py`
- `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py`
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- all frontend pages, Playwright config, and visual snapshots

## Verification Plan
In a temp worktree containing only this patch:
- `PAPERPIPE_CONFIG_PATH=.../config.example.yaml pytest -q tests/test_watcher_issue_state.py tests/test_db_utils_sync_zotero_issue_state.py tests/test_db_utils_update_paper_status_safety.py tests/test_full_pipeline.py tests/test_processor_institutional_proxy.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
Both processor and watcher ingestion persist `clear`, `flagged`, or `unavailable` issues-state predictably, and regressions in the persistence contract are covered by targeted tests.
