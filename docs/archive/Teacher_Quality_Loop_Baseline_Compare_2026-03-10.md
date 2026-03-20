# Teacher Quality Loop Baseline Compare (2026-03-10)

Status: Historical validation report  
Date: 2026-03-10  
Owner: Quality/runtime maintainers  
Canonical parent: `docs/teacher_quality_loop.md`

## Purpose
Capture the first baseline-vs-new compare and promotion run after the initial 2026-03-09 seed baseline was established.

## Inputs
- accepted records: `8`
- seed baseline:
  - `baselines/quality_eval_teacher_probe_20260309.metrics.json`
- merged prediction rows:
  - `tmp/teacher_quality_all_20260310.jsonl`

## Commands
```bash
# 1) merge prediction rows from the two real-output probes
python3 - <<'PY'
import json
from pathlib import Path
sources = [
    Path("tmp/teacher_quality_probe_20260309.jsonl"),
    Path("tmp/qreview_probe_20260309.pred.jsonl"),
]
out = Path("tmp/teacher_quality_all_20260310.jsonl")
rows = {}
for source in sources:
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["paper_id"]] = row
with out.open("w", encoding="utf-8") as handle:
    for paper_id in sorted(rows):
        handle.write(json.dumps(rows[paper_id], ensure_ascii=False) + "\n")
PY

# 2) rebuild deterministic split from the expanded accepted set
python3 scripts/build_goldset.py \
  --version-tag v20260310_teacher_compare \
  --goldset-root goldset

# 3) run quality eval on the new eval split
python3 scripts/eval/run_eval.py --mode quality \
  --eval-jsonl goldset/splits/v20260310_teacher_compare/eval.jsonl \
  --pred-jsonl tmp/teacher_quality_all_20260310.jsonl \
  --manual-decisions-jsonl goldset/manual_decisions/human_decisions.jsonl \
  --snapshots-dir snapshots \
  --run-id quality_eval_teacher_compare_20260310

# 4) compare against the seed baseline and promote on pass
python3 scripts/eval/compare_eval.py \
  --baseline baselines/quality_eval_teacher_probe_20260309.metrics.json \
  --new snapshots/quality_eval_teacher_compare_20260310/metrics.json \
  --out snapshots/compare/quality_eval_teacher_compare_20260310.json \
  --promote-dir baselines
```

## Results
- split result:
  - `train=5`
  - `eval=3`
  - `overlap=0`
- quality eval:
  - `schema_valid_rate=1.0`
  - `evidence_location_rate=1.0`
  - `summary_artifact_rate=1.0`
  - `manual_correction_rate=0.0`
- compare decision:
  - `passed=true`
  - `failed_checks=[]`
  - `regressions=[]`
- promotion:
  - `baselines/quality_eval_teacher_compare_20260310`

## Artifacts
- eval metrics:
  - `snapshots/quality_eval_teacher_compare_20260310/metrics.json`
- compare report:
  - `snapshots/compare/quality_eval_teacher_compare_20260310.json`
- promoted baseline:
  - `baselines/quality_eval_teacher_compare_20260310/metrics.json`

## Notes
- The new run matched the seed baseline on all four tracked metrics.
- This is the first completed `seed baseline -> compare -> promotion` cycle for the local-first teacher quality loop.
