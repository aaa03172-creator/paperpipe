# Profile Assistant Terminology Staging Prep

Date: 2026-03-27
Status: Ready for isolated packaging
Owner: Runtime maintainers

## Goal

Close the bounded profile-edit terminology lane that makes the profile patch helper distinct from Deep Read reasoning persona language in prompts, logs, and CLI copy.

## Include

- `src/agents/profile_chat_agent.py`
- `src/cli.py`
- `tests/test_librarian_advanced.py`
- `docs/reports/Profile_Assistant_Terminology_Staging_Prep_2026-03-27.md`

## Exclude

- `docs/CLI_WORKFLOW_REFERENCE.md`
- `tests/test_paper_notes_api.py`
- reader/deep-read follow-ups already handled elsewhere

## Verification

Current worktree:
- `pytest -q tests/test_librarian_advanced.py`
- `python3 -m src.cli profiles --help >/dev/null`
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run the same pytest set
- run the same CLI help check with `PAPERPIPE_CONFIG_PATH=config.example.yaml`
- run `python3 scripts/lint_docs.py`

## Commit Message

`refactor(cli): clarify profile assistant terminology`
