# Reader Eval Sidecar Staging Prep (2026-03-23)

## Scope
Self-contained runtime lane for writing `reader_eval.json` after grounded deepread runs.

## Included files
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/schemas/reader_eval.py`
- `/Users/jangseongjin/paperpipe/src/services/reader_eval_sidecar.py`
- `/Users/jangseongjin/paperpipe/tests/test_reader_eval_sidecar.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Reader_Eval_Sidecar_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `pytest -q tests/test_reader_eval_sidecar.py`

Temp closure:
- `PAPERPIPE_CONFIG_PATH=config.example.yaml python3 -c "import backend.services.job_runner"`
- `PAPERPIPE_CONFIG_PATH=config.example.yaml pytest -q tests/test_reader_eval_sidecar.py`

## Notes
- This lane is additive. Failures while building the sidecar are warning-only in `job_runner`.
- The sidecar depends on already-landed grounded claimset output and deterministic chunk metadata.
