# Deepread Base Stance Staging Prep

Date: 2026-03-27
Status: Ready for isolated packaging
Owner: Runtime maintainers

## Goal

Close the bounded prompt/terminology lane that separates the fixed Deep Read base stance from optional runtime overlays such as reasoning persona, profile context, and similar-feedback hints.

## Include

- `backend/services/job_runner.py`
- `src/agents/deep_reader.py`
- `src/agents/reader_agent.py`
- `tests/test_reader_agent_reliability.py`
- `docs/reports/Deepread_Base_Stance_Staging_Prep_2026-03-27.md`

## Exclude

- `src/agents/profile_chat_agent.py`
- `src/cli.py`
- `tests/test_librarian_advanced.py`
- `tests/test_paper_notes_api.py`

## Verification

Current worktree:
- `pytest -q tests/test_deep_reader.py tests/test_reader_agent_reliability.py`
- `python3 -c "from backend.services.job_runner import run_deepread_job; print('ok')"`
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run the same pytest set with `PAPERPIPE_CONFIG_PATH=config.example.yaml`
- run the same import check with `PAPERPIPE_CONFIG_PATH=config.example.yaml`
- run `python3 scripts/lint_docs.py`

## Commit Message

`refactor(deepread): separate base stance from runtime overlays`
