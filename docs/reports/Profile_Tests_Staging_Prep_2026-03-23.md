# Profile Tests Staging Prep (2026-03-23)

## Goal
Split a narrow test-only lane for profile persistence and profile-chat regression coverage.

## Included
- `/Users/jangseongjin/paperpipe/tests/test_profiles.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_chat.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Profile_Tests_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- `test_profiles.py` updates persistence coverage to use `save_profiles_snapshot(...)` and asserts default revision materialization.
- `test_profile_chat.py` now mocks `load_config()` so the tests no longer depend on a local `config.yaml` file.
- No runtime source changes are required for this slice.

## Verification Plan
- `PAPERPIPE_CONFIG_PATH=/Users/jangseongjin/paperpipe/config.example.yaml pytest -q /Users/jangseongjin/paperpipe/tests/test_profiles.py /Users/jangseongjin/paperpipe/tests/test_profile_chat.py`
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`

## Expected Outcome
Profile persistence and chat tests are stable in clean environments without relying on incidental local config files.
