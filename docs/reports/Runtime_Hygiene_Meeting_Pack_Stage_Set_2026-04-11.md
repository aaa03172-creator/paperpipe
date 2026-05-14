# Runtime Hygiene Meeting Pack Stage Set

Date: 2026-04-11
Owner: Codex
Status: staged-slice-prep

## Intent

Isolate the runtime hygiene lane that:

- warns when hidden fixture structured states contaminate a normal vault
- warns when low-value Meeting Pack directories should be archived
- adds a CLI command to archive those Meeting Pack candidates safely

## Included scope

- `src/services/runtime_readiness.py`
  - add structured-state hygiene check
  - add Meeting Pack storage hygiene check
  - surface both checks in runtime readiness summaries
- `src/services/fixture_visibility.py`
  - add structured-state fixture detection and quarantine helpers
- `src/meeting_packs/hygiene.py`
  - add selection and archive helpers for low-value Meeting Pack directories
- `src/cli.py`
  - add doctor output for Meeting Pack storage hygiene
  - add `archive-meeting-pack-noise`

## Explicitly excluded

- unrelated `src/cli.py` tails
- Research DNA changes

## Verification plan

- `pytest -q tests/test_runtime_readiness_external_roots.py tests/test_cli_watch_commands.py`
- `python3 scripts/lint_docs.py`

## Verification results

- current worktree:
  - `pytest -q tests/test_runtime_readiness_external_roots.py tests/test_cli_watch_commands.py`
    - `12 passed, 5 warnings`
- staged index export:
  - `PYTHONPATH=. /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -c "import src.cli"`
    - passed
  - `pytest -q tests/test_runtime_readiness_external_roots.py`
    - `3 passed, 5 warnings`
  - `python3 scripts/lint_docs.py`
    - `docs lint passed`
- note:
  - `tests/test_cli_watch_commands.py` is currently a local worktree test file, so it is not available inside the staged index export
