# Teacher Quality Loop Smoke Report (2026-02-24)

## Scope
Validated the end-to-end local quality loop after PR #76 merge:

1. candidate extraction
2. teacher output verification/gating
3. goldset split build
4. quality eval metrics run
5. baseline comparison and promotion gate

## Environment
- Repo: `paperpipe`
- Base branch state: `master` at merge commit `f60064b`
- Run date: 2026-02-24 (UTC+09)

## Commands
```bash
# 1) extract candidates
PAPERPIPE_DB_PATH=/Users/jangseongjin/paperpipe/storage/state.db \
python3 scripts/extract_teacher_candidates.py \
  --run-id smoke_20260224_qualityloop --limit 5

# 2) verify teacher outputs -> accepted/quarantine
python3 scripts/verify_teacher_output.py \
  --bundle-dir <bundle_dir> --teacher-output <teacher_output_json>

# 3) build deterministic split
python3 scripts/build_goldset.py \
  --version-tag v20260224_smoke --goldset-root goldset

# 4) run quality eval
python3 scripts/eval/run_eval.py --mode quality \
  --eval-jsonl goldset/splits/v20260224_smoke/eval.jsonl \
  --pred-jsonl tmp/pred_smoke.jsonl \
  --snapshots-dir snapshots --run-id smoke_quality_eval_20260224

# 5) compare vs baseline and promote
python3 scripts/eval/compare_eval.py \
  --baseline snapshots/baseline_smoke/metrics.json \
  --new snapshots/smoke_quality_eval_20260224/metrics.json \
  --out snapshots/compare/smoke_vs_baseline.json \
  --promote-dir baselines
```

## Results
- extraction bundles: `5`
- verify accepted: `5`
- verify quarantine: `0`
- split result: `train=4`, `eval=1`, `overlap=0`

Quality metrics (`snapshots/smoke_quality_eval_20260224/metrics.json`):
- `schema_valid_rate=1.0`
- `evidence_location_rate=1.0`
- `summary_artifact_rate=1.0`
- `manual_correction_rate=0.0`

Comparison (`snapshots/compare/smoke_vs_baseline.json`):
- decision: `passed=true`
- promotion: `baselines/smoke_quality_eval_20260224`

## Notes
- This was a smoke validation with synthetic teacher outputs for routing/eval pipeline verification.
- Production-quality acceptance still depends on real teacher outputs and quarantine review flows.
