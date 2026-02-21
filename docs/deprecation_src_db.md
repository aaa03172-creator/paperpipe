# Deprecation Notice: `src/db.py`

Date: 2026-02-21
Status: Deprecated (compatibility wrapper still available)

## Summary
`src/db.py` is now a legacy compatibility module.
New code should use `src/db_utils.py` as the primary DB access layer for PaperPipe runtime data.

## Why
- Canonical runtime schema is managed around `storage/state.db` with `papers/review_queue/jobs`.
- `src/db.py` historically mixed legacy assumptions (`doi`-primary) with newer schema (`paper_id`-primary).
- This created drift risk in CLI/processor/runtime flows.

## Current Rule
- `src/db_utils.py`: primary API for active runtime paths.
- `src/db.py`: compatibility only for legacy integrations/tests.

## Preferred Replacements
- `src.db.is_paper_processed` -> `src.db_utils.is_paper_processed`
- `src.db.save_paper_state` -> `src.db_utils.save_paper_state`
- `src.db.get_paper_by_id` -> `src.db_utils.get_paper_by_id`
- `src.db.update_paper_status` (reading-status flavor) -> `src.db_utils.update_reading_status`
- `src.db.get_all_papers` -> `src.db_utils.get_all_papers`
- `src.db.mark_as_retracted` -> `src.db_utils.mark_as_retracted`

## Migration Guidance
1. For new features, import from `src.db_utils` only.
2. Keep `src.db` usage only where unavoidable (legacy profile/run-stats flows).
3. If adding a new DB helper, add it to `src.db_utils` first and expose compatibility wrapper in `src.db` only if needed.

## Safety Note
All migrations must preserve:
- Fail-safe batch behavior
- Existing DB path (`storage/state.db`)
- Existing schema compatibility for local/test environments
