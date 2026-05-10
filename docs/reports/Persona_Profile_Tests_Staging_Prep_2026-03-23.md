# Persona/Profile Tests Staging Prep (2026-03-23)

## Goal
Split a narrow test-only lane that locks persona/profile runtime behavior already present in the backend.

## Included
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_persona.py`
- `/Users/jangseongjin/paperpipe/tests/test_librarian_advanced.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Persona_Profile_Tests_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- `test_job_runner_persona.py` extends coverage around profile context vs reasoning persona application in deep-read jobs.
- `test_librarian_advanced.py` updates legacy librarian tests so they no longer depend on an implicit local `config.yaml`.
- No runtime source files are required for this slice because the exercised behavior is already present in committed code.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/config.example.yaml`
- `/Users/jangseongjin/paperpipe/config/profiles.yaml`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/src/config.py`
- all frontend files and Playwright assets

## Verification Plan
In a temp worktree containing only this patch:
- `PAPERPIPE_CONFIG_PATH=.../config.example.yaml pytest -q tests/test_job_runner_persona.py tests/test_librarian_advanced.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
Persona/profile regressions are pinned by tests without dragging the much larger config/profile lane into the same commit.
