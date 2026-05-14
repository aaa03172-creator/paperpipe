# Paper Notes Default Sort Test Staging Prep

Date: 2026-03-27
Status: Ready for isolated packaging
Owner: Runtime maintainers

## Goal

Lock the paper-notes default-sort expectation that richer saved state sorts ahead of lighter placeholder state when no explicit sort is requested.

## Include

- `tests/test_paper_notes_api.py`
- `docs/reports/Paper_Notes_Default_Sort_Test_Staging_Prep_2026-03-27.md`

## Verification

Current worktree:
- `pytest -q tests/test_paper_notes_api.py -k default_sort_prioritizes_saved_state_with_richer_claims`
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run the same pytest selector with `PAPERPIPE_CONFIG_PATH=config.example.yaml`
- run `python3 scripts/lint_docs.py`

## Commit Message

`test(paper-notes): lock default saved-state sort`
