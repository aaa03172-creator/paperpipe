# Ingest Backend Eval Same-Page Merge Staging Prep (2026-03-23)

## Scope
Bounded eval-lane follow-up for reclassifying same-page table merges as non-loss cases in backend comparison metrics.

## Included files
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Ingest_Backend_Eval_Same_Page_Merge_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `pytest -q tests/test_ingest_backend_eval.py`

Temp closure:
- `pytest -q tests/test_ingest_backend_eval.py`

## Notes
- This lane only changes comparison/eval semantics.
- It does not alter ingest runtime behavior or parser selection.
- Same-page merged table output should not be treated as a meaningful table-loss regression when page coverage is preserved.
