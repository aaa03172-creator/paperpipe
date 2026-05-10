# Extraction Regression Eval Staging Prep

Date: 2026-03-27
Status: Ready for isolated packaging
Owner: Runtime maintainers

## Goal

Add a bounded extraction-regression comparison harness that classifies schema/core-field failures, writes comparison artifacts, and locks the expected bucket taxonomy with tests.

## Include

- `scripts/eval/compare_extraction_outputs.py`
- `tests/test_extraction_regression_eval.py`
- `docs/reports/Extraction_Regression_Eval_Staging_Prep_2026-03-27.md`

## Verification

Current worktree:
- `pytest -q tests/test_extraction_regression_eval.py`
- `python3 scripts/eval/compare_extraction_outputs.py --help >/dev/null`
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run the same pytest set
- run the same help check
- run `python3 scripts/lint_docs.py`

## Commit Message

`test(ingest): add extraction regression comparison harness`
