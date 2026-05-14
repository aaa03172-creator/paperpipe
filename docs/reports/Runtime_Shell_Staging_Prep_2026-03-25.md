# Runtime Shell Staging Prep (2026-03-25)

## Goal
- Close the bounded runtime shell lane around bootstrap orchestration, direct batch execution, and CLI deepread timeout behavior.

## Include
- `/Users/jangseongjin/paperpipe/scripts/bootstrap.py`
- `/Users/jangseongjin/paperpipe/scripts/run_batch.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_shell_scripts.py`

## Exclude
- `/Users/jangseongjin/paperpipe/src/cli.py`
  - Current dirty hunk is profile-assistant wording only and is unrelated to runtime shell behavior.
- `/Users/jangseongjin/paperpipe/tests/test_librarian_advanced.py`
- `/Users/jangseongjin/paperpipe/tests/test_paper_notes_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_reader_agent_reliability.py`

## Intended behavior
- `scripts/bootstrap.py`
  - Use the configured local-first provider instead of hardcoded Anthropic wiring.
  - Accept repaired JSON wrapped under `ClaimSet` or `claimset`.
- `scripts/run_batch.py`
  - Support direct `python3 scripts/run_batch.py` execution without `ModuleNotFoundError: No module named 'scripts'`.
- `src/services/cli_workflows.py`
  - Respect ingest parser config.
  - Apply adaptive reader/stats timeout budgets and degrade gracefully on timeout.

## Verification
- `pytest -q /Users/jangseongjin/paperpipe/tests/test_runtime_shell_scripts.py /Users/jangseongjin/paperpipe/tests/test_timeout_policy.py /Users/jangseongjin/paperpipe/tests/test_cli_smoke_db_paths.py`
- `python3 -m src.cli deepread --help`
- Clean temp worktree closure:
  - same pytest set
  - same CLI help check
  - direct batch import-path check using temp cwd with empty `storage/`

## Notes
- Do not use repo-root `python3 scripts/run_batch.py` as a smoke check for this lane. In the current workspace it will consume the local Zotero export and attempt real `/jobs/deepread` calls.
