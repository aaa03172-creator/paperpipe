# Legacy Root Report Delete Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Delete remaining root-level validation and release-note report files that should now live under `docs/reports/` or `docs/archive/` only.

## Included scope

- delete `docs/Local_Batch_Validation_2026-03-06_30_fast.json`
- delete `docs/Local_Batch_Validation_2026-03-06_30_fast.md`
- delete `docs/Local_Batch_Validation_2026-03-06_30_full_timeout.json`
- delete `docs/Local_Batch_Validation_2026-03-06_30_full_timeout.md`
- delete `docs/release_notes_2026-02-21_watcher_qa.md`
- delete `docs/release_notes_2026-02-25_ui_mock_test_stability.md`
- add `docs/reports/Legacy_Root_Report_Delete_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- edits to `docs/README.md`
- edits to `docs/archive/README.md`
- any runtime/frontend code changes

## Verification

1. `python3 scripts/lint_docs.py`
2. staged diff remains delete-only plus this manifest

## Commit target

`docs(cleanup): remove legacy root report files`
