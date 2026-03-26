# CLI Readme Follow-up Staging Prep

Date: 2026-03-27
Status: Ready for isolated docs packaging
Owner: Runtime/product maintainers

## Goal

Close the remaining docs-only follow-up that:
- clarifies README command/api wording
- adds an honest CLI workflow reference
- documents the parser-worker backend E2E path in frontend docs
- records the Feynman messaging lane as applied

## Include

- `README.md`
- `frontend/README.md`
- `docs/CLI_WORKFLOW_REFERENCE.md`
- `docs/reports/Feynman_Workflow_Messaging_Fit_Review_2026-03-27.md`
- `docs/reports/CLI_Readme_Followup_Staging_Prep_2026-03-27.md`

## Exclude

- runtime code/test follow-ups already closed
- extraction eval lane files
- local runtime/storage artifacts

## Verification

Current worktree:
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run `python3 scripts/lint_docs.py`

## Commit Message

`docs(cli): add workflow reference and readme follow-ups`
