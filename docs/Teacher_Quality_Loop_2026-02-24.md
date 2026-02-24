# Teacher Quality Loop (2026-02-24)

This document records the minimal, local-first quality loop added for Teacher -> Gate -> Goldset -> Eval.

## SSOT Paths
All scripts resolve runtime paths via `src/services/runtime_paths.py`.

- `PAPERPIPE_HOME` (fallback: repo root)
- `PAPERPIPE_STORAGE_DIR` (fallback: `${PAPERPIPE_HOME}/storage`)
- `PAPERPIPE_DB_PATH` (fallback: `${PAPERPIPE_STORAGE_DIR}/state.db`)
- `PAPERPIPE_ARTIFACTS_DIR` (fallback: `${PAPERPIPE_STORAGE_DIR}/artifacts`)
- `PAPERPIPE_GOLDSET_DIR` (fallback: `${PAPERPIPE_HOME}/goldset`)

No script requires hardcoded absolute `/Users/...` paths.

## PR#1 Candidate Extractor
Script: `scripts/extract_teacher_candidates.py`

Output bundle:
- `storage/artifacts/{run_id}/teacher/{paper_id_safe}/manifest.json`
- `.../input_chunks.jsonl`
- `.../tables.json`
- `.../prior_output.json`

`manifest.json` includes reproducibility fields:
- `paper_id`, `bundle_id`, `created_at`
- `git_commit`, `model`, `prompt_version`
- `candidate_reason_codes`, `candidate_reason_details`

Run example:
```bash
python3 scripts/extract_teacher_candidates.py --run-id 20260224_teacher --limit 50
```

## PR#2 Gate Verifier
- Library: `src/quality/gates.py`
- Script: `scripts/verify_teacher_output.py`

Gate outputs are routed to:
- `goldset/accepted/{paper_id}.json`
- `goldset/quarantine/{paper_id}.json`

Every quarantined record stores `reason_codes[]`.
Current reason codes:
- `SCHEMA_INVALID`
- `NO_EVIDENCE_SPAN`
- `EVIDENCE_LOCATION_MISSING`
- `NUMERIC_SANITY_FAIL`
- `FORBIDDEN_PHRASE`
- `HALLUCINATION_PATTERN`
- `LEAKAGE_RISK`

Run example:
```bash
python3 scripts/verify_teacher_output.py \
  --bundle-dir storage/artifacts/20260224_teacher/teacher/paper_001 \
  --teacher-output /tmp/paper_001_teacher_output.json
```

## PR#3 Goldset Builder
Script: `scripts/build_goldset.py`

Split rule (stable, leak-free by `paper_id`):
- `sha256(paper_id) % 10 < 8` -> train
- else -> eval

Output:
- `goldset/splits/vYYYYMMDD/train.jsonl`
- `goldset/splits/vYYYYMMDD/eval.jsonl`
- `goldset/splits/vYYYYMMDD/split_meta.json`

Run example:
```bash
python3 scripts/build_goldset.py --version-tag v20260224
```

## PR#4 Eval + Promotion Gate
- Extended: `scripts/eval/run_eval.py` (`--mode quality`)
- Added: `scripts/eval/compare_eval.py`

Quality metrics:
- `schema_valid_rate`
- `evidence_location_rate`
- `summary_artifact_rate`
- `manual_correction_rate`

Compare + promotion example:
```bash
python3 scripts/eval/compare_eval.py \
  --baseline snapshots/baseline/metrics.json \
  --new snapshots/run_new/metrics.json \
  --out snapshots/compare/run_new_vs_baseline.json \
  --promote-dir baselines
```

Decision rule:
- required improvements (or equal with zero deltas) for schema/evidence/summary
- no regression on major metrics
- no increase in `manual_correction_rate` by default

## Regression Tests
Added tests:
- `tests/test_extract_teacher_candidates.py`
- `tests/test_teacher_gate_verifier.py`
- `tests/test_build_goldset.py`
- `tests/test_eval_quality_compare.py`
