# Stats Fallback Eval Sidecar Staging Prep (2026-03-23)

## Scope
Bounded stats-review lane for deriving a structured fallback taxonomy sidecar from `stats_report.json` and `bootstrap_meta.json`.

## Included files
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/schemas/stats_fallback_eval.py`
- `/Users/jangseongjin/paperpipe/src/services/stats_fallback_eval_sidecar.py`
- `/Users/jangseongjin/paperpipe/tests/test_stats_fallback_eval_sidecar.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Stats_Fallback_Taxonomy_Real_Replay_Batch_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Stats_Fallback_Eval_Sidecar_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `pytest -q tests/test_stats_fallback_eval_sidecar.py`

Temp closure:
- `pytest -q tests/test_stats_fallback_eval_sidecar.py`

## Notes
- This lane is additive only. It does not change stats-verifier semantics.
- The runtime writes `stats_fallback_eval.json` as a sidecar and records summary counts in `bootstrap_meta.json`.
- The replay report is intentionally bounded to existing artifacts and is included as evidence for the taxonomy buckets only.
