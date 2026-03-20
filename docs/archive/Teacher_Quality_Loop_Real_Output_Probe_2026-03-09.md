# Teacher Quality Loop Real-Output Probe (2026-03-09)

Status: Historical validation report  
Date: 2026-03-09  
Owner: Quality/runtime maintainers  
Canonical parent: `docs/teacher_quality_loop.md`

## Scope
Validated the local-first teacher quality loop with real local LLM outputs instead of synthetic fixtures.

Covered steps:
1. candidate extraction
2. local-first teacher output generation
3. teacher output verification/gating
4. deterministic split build
5. quality eval metrics run
6. seed baseline capture

## Environment
- Repo: `paperpipe`
- Runtime config: `llm.mode=local`, `local.provider=ollama`, `chat/teacher model=llama3:latest`
- Run date: 2026-03-09 (Asia/Seoul)

## Bundles Used
- `zotero:bialystokBilingualismConsequencesMind2012`
- `zotero:duboisAlzheimerDiseaseClinicalBiological2024`
- `zotero:furtadoOvercomingBloodBrain2018`
- `zotero:hanssonBloodBiomarkersAlzheimers2023`

Bundle root:
- `storage/artifacts/dry_probe_20260309/teacher/`

## Commands
```bash
# 1) extract candidates
python3 scripts/extract_teacher_candidates.py \
  --run-id dry_probe_20260309 \
  --limit 5

# 2) generate local-first teacher outputs
python3 scripts/generate_teacher_outputs.py \
  --bundle-dir storage/artifacts/dry_probe_20260309/teacher/zotero_bialystokBilingualismConsequencesMind2012 \
  --bundle-dir storage/artifacts/dry_probe_20260309/teacher/zotero_duboisAlzheimerDiseaseClinicalBiological2024 \
  --bundle-dir storage/artifacts/dry_probe_20260309/teacher/zotero_furtadoOvercomingBloodBrain2018 \
  --bundle-dir storage/artifacts/dry_probe_20260309/teacher/zotero_hanssonBloodBiomarkersAlzheimers2023 \
  --pred-jsonl tmp/teacher_quality_probe_20260309.jsonl

# 3) verify teacher outputs
python3 scripts/verify_teacher_output.py \
  --bundle-dir <bundle_dir> \
  --teacher-output <bundle_dir>/teacher_output.json

# 4) build split
python3 scripts/build_goldset.py \
  --version-tag v20260309_teacher_probe \
  --goldset-root goldset

# 5) run quality eval
python3 scripts/eval/run_eval.py --mode quality \
  --eval-jsonl goldset/splits/v20260309_teacher_probe/eval.jsonl \
  --pred-jsonl tmp/teacher_quality_probe_20260309.jsonl \
  --manual-decisions-jsonl goldset/manual_decisions/human_decisions.jsonl \
  --snapshots-dir snapshots \
  --run-id quality_eval_teacher_probe_20260309
```

## Results
- teacher generation: `4/4 success`
- verify accepted: `4`
- verify quarantine: `0`
- split result: `train=3`, `eval=1`, `overlap=0`

Quality metrics:
- `schema_valid_rate=1.0`
- `evidence_location_rate=1.0`
- `summary_artifact_rate=1.0`
- `manual_correction_rate=0.0`

Artifacts:
- predictions: `tmp/teacher_quality_probe_20260309.jsonl`
- split: `goldset/splits/v20260309_teacher_probe/`
- metrics: `snapshots/quality_eval_teacher_probe_20260309/metrics.json`

## Notes
- This run used real local LLM teacher outputs from Ollama, not synthetic fixtures.
- `generate_teacher_outputs.py` performs chunk selection plus post-generation evidence location remapping before gate verification.
- No prior quality baseline existed for real teacher outputs, so this run was copied to:
  - `baselines/quality_eval_teacher_probe_20260309.metrics.json`
- The next meaningful compare/promotion step should use a later real-output run against that seed baseline.

## Follow-up
- quarantine review workflow evidence was added later on the same day via:
  - `docs/archive/Teacher_Quality_Loop_Quarantine_Review_Drill_2026-03-09.md`
- that drill used a controlled quarantine on a real bundle because this real-output probe produced `0` natural quarantine cases
