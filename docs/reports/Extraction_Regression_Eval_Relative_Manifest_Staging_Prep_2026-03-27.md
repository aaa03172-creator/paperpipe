# Extraction Regression Eval Relative Manifest Staging Prep

Date: 2026-03-27
Status: Ready for isolated follow-up packaging
Owner: Runtime maintainers

## Goal

Close the bounded follow-up that lets `compare_extraction_outputs.py` resolve manifest paths relative to the manifest file, and lock that behavior in the CLI regression test.

## Include

- `scripts/eval/compare_extraction_outputs.py`
- `tests/test_extraction_regression_eval.py`
- `docs/reports/Extraction_Regression_Eval_Relative_Manifest_Staging_Prep_2026-03-27.md`

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

`fix(ingest): resolve extraction manifests relative to source`
