# Teacher Quality Loop

Status: Active  
Date: 2026-03-09  
Owner: Quality/runtime maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose
운영 환경에서 teacher-derived outputs를 후보 추출, 게이트 검증, human quarantine review, goldset split, quality eval, baseline promotion까지 일관된 경로로 다루기 위한 runbook이다.

## Current Scope
- candidate extraction
- local-first teacher output generation from extracted bundles
- teacher output verification and routing
- quarantine review and accepted de/promote
- deterministic train/eval split
- quality eval metrics run
- baseline compare and optional promotion

## Runtime Paths
- default goldset root: `./goldset`
- override: `PAPERPIPE_GOLDSET_DIR`

Default subpaths:
- `goldset/accepted/`
- `goldset/quarantine/`
- `goldset/reviews/`
- `goldset/manual_decisions/human_decisions.jsonl`
- `goldset/splits/<version>/`

## Commands
### 1) Extract candidates
```bash
python3 scripts/extract_teacher_candidates.py \
  --run-id qualityloop_20260309 \
  --limit 20
```

### 2) Generate local-first teacher outputs
```bash
python3 scripts/generate_teacher_outputs.py \
  --bundles-root storage/artifacts/qualityloop_20260309/teacher \
  --pred-jsonl tmp/qualityloop_20260309.pred.jsonl
```

Outputs:
- per bundle: `teacher_output.json`, `teacher_output.meta.json`, `teacher_output.raw.txt`
- optional consolidated predictions: `tmp/qualityloop_20260309.pred.jsonl`

Notes:
- provider/model follows current runtime config (`config.yaml`)
- current canonical target is local Ollama (`llm.mode=local`)
- the generator is conservative: it drops unsupported claims instead of inventing evidence links

### 3) Verify teacher output and route to accepted/quarantine
```bash
python3 scripts/verify_teacher_output.py \
  --bundle-dir <bundle_dir> \
  --teacher-output <teacher_output_json>
```

Output:
- pass -> `goldset/accepted/<paper_id>.json`
- fail -> `goldset/quarantine/<paper_id>.json`

### 4) Review quarantine records
List unresolved review queue:
```bash
python3 scripts/review_teacher_quarantine.py list
```

Include already reviewed entries:
```bash
python3 scripts/review_teacher_quarantine.py list --all
```

Approve without manual correction:
```bash
python3 scripts/review_teacher_quarantine.py resolve \
  --paper-id <paper_id> \
  --resolution APPROVE_NO_EDIT \
  --reviewer <name>
```

Approve with manual correction:
```bash
python3 scripts/review_teacher_quarantine.py resolve \
  --paper-id <paper_id> \
  --resolution APPROVED_WITH_EDIT \
  --reviewer <name> \
  --notes "fixed evidence span mapping"
```

Keep in quarantine:
```bash
python3 scripts/review_teacher_quarantine.py resolve \
  --paper-id <paper_id> \
  --resolution KEEP_QUARANTINE \
  --reviewer <name> \
  --notes "still unsupported by source evidence"
```

Review side effects:
- audit record: `goldset/reviews/<paper_id>_<timestamp>.json`
- manual decisions log: `goldset/manual_decisions/human_decisions.jsonl`
- accepted copy is created or removed to match the review resolution

### 5) Build deterministic split
```bash
python3 scripts/build_goldset.py \
  --version-tag v20260309 \
  --goldset-root goldset
```

### 6) Run quality eval
```bash
python3 scripts/eval/run_eval.py --mode quality \
  --eval-jsonl goldset/splits/v20260309/eval.jsonl \
  --pred-jsonl tmp/qualityloop_20260309.pred.jsonl \
  --manual-decisions-jsonl goldset/manual_decisions/human_decisions.jsonl \
  --snapshots-dir snapshots \
  --run-id quality_eval_20260309
```

### 7) Compare against baseline and promote
```bash
python3 scripts/eval/compare_eval.py \
  --baseline snapshots/baseline/metrics.json \
  --new snapshots/quality_eval_20260309/metrics.json \
  --out snapshots/compare/quality_eval_20260309.json \
  --promote-dir baselines
```

## Review Resolution Semantics
- `APPROVE_NO_EDIT`
  - accepted set으로 승격
  - `manual_correction_rate`에는 포함되지 않음
- `APPROVED_WITH_EDIT`
  - accepted set으로 승격
  - `manual_correction_rate`에 포함
- `MANUAL_FIX`
  - accepted set으로 승격
  - `manual_correction_rate`에 포함
- `OVERRIDE`
  - accepted set으로 승격
  - `manual_correction_rate`에 포함
- `REWRITE`
  - accepted set으로 승격
  - `manual_correction_rate`에 포함
- `KEEP_QUARANTINE`
  - accepted set에서 제거 유지
  - quarantine 상태 유지

## What Is Still Open
- first real-output probe completed on 2026-03-09 (`docs/archive/Teacher_Quality_Loop_Real_Output_Probe_2026-03-09.md`)
- quarantine review drill completed on 2026-03-09 (`docs/archive/Teacher_Quality_Loop_Quarantine_Review_Drill_2026-03-09.md`)
- first baseline-vs-new compare/promotion cycle completed on 2026-03-10 (`docs/archive/Teacher_Quality_Loop_Baseline_Compare_2026-03-10.md`)
- follow-up baseline regression batch completed on 2026-03-13 with no metric regression (`docs/archive/Teacher_Quality_Loop_Baseline_Regression_Batch_2026-03-13.md`)
- expanded natural-quarantine probe completed on 2026-03-13 with `19 accepted / 0 quarantine`; controlled drill remains the only canonical quarantine workflow evidence for now (`docs/archive/Teacher_Quality_Loop_Natural_Quarantine_Probe_2026-03-13.md`)
- natural quarantine should only be retried if a materially different candidate pool or stricter gate configuration becomes available
