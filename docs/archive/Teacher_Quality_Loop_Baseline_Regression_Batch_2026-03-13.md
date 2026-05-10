Status: Historical runtime report  
Date: 2026-03-13  
Owner: Quality/runtime maintainers  
Canonical parent: `docs/teacher_quality_loop.md`

## Goal
Promoted baseline 이후 첫 follow-up local-first teacher batch를 다시 실행해서, canonical quality metrics가 유지되는지 확인한다.

## Batch Definition
- extract run:
  - `qualityloop_20260313_batch01`
- extract command:
  - `python3 scripts/extract_teacher_candidates.py --run-id qualityloop_20260313_batch01 --limit 10`
- generate command:
  - `python3 scripts/generate_teacher_outputs.py --bundles-root storage/artifacts/qualityloop_20260313_batch01/teacher --pred-jsonl tmp/qualityloop_20260313_batch01.pred.jsonl`
- eval command:
  - `python3 scripts/eval/run_eval.py --mode quality --eval-jsonl goldset/splits/v20260310_teacher_compare/eval.jsonl --pred-jsonl tmp/qualityloop_20260313_batch01.pred.jsonl --manual-decisions-jsonl goldset/manual_decisions/human_decisions.jsonl --snapshots-dir snapshots --run-id quality_eval_teacher_batch_20260313_batch01`
- compare command:
  - `python3 scripts/eval/compare_eval.py --baseline baselines/quality_eval_teacher_compare_20260310/metrics.json --new snapshots/quality_eval_teacher_batch_20260313_batch01/metrics.json --out snapshots/compare/quality_eval_teacher_batch_20260313_batch01.json`

## Extraction Result
- requested limit:
  - `10`
- extracted bundles:
  - `9`
- bundle root:
  - [/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher](/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher)

Interpretation:
- 현재 candidate extraction으로는 `8`개의 canonical real bundles + `1`개의 local bundle이 선택됐다.
- 즉 “larger batch”를 요청했지만, 실제 eligible pool은 이 시점에서 `9`건이 상한이었다.

## Generation Result
- consolidated predictions:
  - [/Users/jangseongjin/paperpipe/tmp/qualityloop_20260313_batch01.pred.jsonl](/Users/jangseongjin/paperpipe/tmp/qualityloop_20260313_batch01.pred.jsonl)
- `success=8`
- `failed=1`

Success set:
- `zotero:bialystokBilingualismConsequencesMind2012`
- `zotero:duboisAlzheimerDiseaseClinicalBiological2024`
- `zotero:furtadoOvercomingBloodBrain2018`
- `zotero:hanssonBloodBiomarkersAlzheimers2023`
- `zotero:kistemakerVascularizedHumanBrain2025`
- `zotero:pichetbinetteConfoundingFactorsAlzheimers2023`
- `zotero:therriaultBiomarkerModelingAlzheimers2022`
- `zotero:zhouGliatoNeuronConversionCRISPRCasRx2020`

Failure set:
- `local--2340210413920451032`
  - failure:
    - `teacher_review_failed=no_supported_claims`
  - raw output:
    - [/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher/local--2340210413920451032/teacher_output.raw.txt](/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher/local--2340210413920451032/teacher_output.raw.txt)

Assessment:
- 이 실패는 gate/quarantine로 내려간 사례가 아니라, teacher generation 단계에서 supported claim이 없어 prediction row를 만들지 못한 사례다.
- 따라서 자연 quarantine 근거로는 채택하지 않는다.

## Quality Eval Result
- snapshot root:
  - [/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch01](/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch01)
- metrics:
  - [/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch01/metrics.json](/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch01/metrics.json)

Metrics:
- `total=3`
- `missing_prediction_count=0`
- `schema_valid_rate=1.0`
- `evidence_location_rate=1.0`
- `summary_artifact_rate=1.0`
- `manual_correction_rate=0.0`

Interpretation:
- canonical eval split `v20260310_teacher_compare`의 eval set은 `3`건이라, 이번 회귀 점검은 그 `3`건에 대해 no-regression을 확인한 셈이다.
- prediction row는 `8`건 생성됐지만, fixed comparison metric은 current eval split에 대해 계산된다.

## Compare Result
- compare report:
  - [/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch01.json](/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch01.json)
- decision:
  - `passed=true`
- promotion:
  - `none`

Delta vs promoted baseline:
- `schema_valid_rate: 0.0`
- `evidence_location_rate: 0.0`
- `summary_artifact_rate: 0.0`
- `manual_correction_rate: 0.0`

## Conclusion
- promoted baseline 대비 regression은 없었다.
- 이번 배치는 canonical quality metric을 그대로 유지했다.
- 다만 candidate pool이 `8 real + 1 local unsupported`에 머물러, “larger batch”의 폭 자체는 제한적이었다.
- 자연 quarantine evidence는 이번 run에서도 생기지 않았다.
