Status: Historical runtime report  
Date: 2026-03-13  
Owner: Quality/runtime maintainers  
Canonical parent: `docs/teacher_quality_loop.md`

## Goal
Controlled quarantine drill을 대체할 수 있는 자연 발생 quarantine 사례가 실제 local-first batch에서 나오는지 확인한다.

## Batch Definition
- extract run:
  - `qualityloop_20260313_batch02`
- extract command:
  - `python3 scripts/extract_teacher_candidates.py --run-id qualityloop_20260313_batch02 --limit 20 --low-confidence-threshold 0.95`
- generate command:
  - `python3 scripts/generate_teacher_outputs.py --bundles-root storage/artifacts/qualityloop_20260313_batch02/teacher --pred-jsonl tmp/qualityloop_20260313_batch02.pred.jsonl`
- verify root:
  - [/Users/jangseongjin/paperpipe/tmp/teacher_quality_batch02_verify_final/goldset](/Users/jangseongjin/paperpipe/tmp/teacher_quality_batch02_verify_final/goldset)
- eval command:
  - `python3 scripts/eval/run_eval.py --mode quality --eval-jsonl goldset/splits/v20260310_teacher_compare/eval.jsonl --pred-jsonl tmp/qualityloop_20260313_batch02.pred.jsonl --manual-decisions-jsonl goldset/manual_decisions/human_decisions.jsonl --snapshots-dir snapshots --run-id quality_eval_teacher_batch_20260313_batch02`
- compare command:
  - `python3 scripts/eval/compare_eval.py --baseline baselines/quality_eval_teacher_compare_20260310/metrics.json --new snapshots/quality_eval_teacher_batch_20260313_batch02/metrics.json --out snapshots/compare/quality_eval_teacher_batch_20260313_batch02.json`

## Extraction Result
- requested limit:
  - `20`
- low-confidence threshold:
  - `0.95`
- extracted bundles:
  - `20`
- bundle root:
  - [/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher](/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher)

Interpretation:
- 이전 batch01은 candidate pool 자체가 `8 real + 1 local unsupported`로 좁았다.
- 이번 probe는 threshold를 넓혀 `20`개 bundle까지 끌어와, “자연 quarantine가 안 나오는 이유가 단순히 표본이 좁아서인지”를 다시 확인한 run이다.

## Generation Result
- consolidated predictions:
  - [/Users/jangseongjin/paperpipe/tmp/qualityloop_20260313_batch02.pred.jsonl](/Users/jangseongjin/paperpipe/tmp/qualityloop_20260313_batch02.pred.jsonl)
- `success=19`
- `failed=1`

Failure set:
- `local--2340210413920451032`
  - failure:
    - `teacher_review_failed=no_supported_claims`
  - raw output:
    - [/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher/local--2340210413920451032/teacher_output.raw.txt](/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher/local--2340210413920451032/teacher_output.raw.txt)

Assessment:
- 이 실패는 verify gate가 reject한 quarantine 사례가 아니다.
- generation 단계에서 supported claims가 비어 prediction row를 만들지 못한 local bundle 1건일 뿐이다.

## Verification Result
- verified outputs:
  - `19`
- accepted:
  - `19`
- quarantine:
  - `0`
- verification root:
  - [/Users/jangseongjin/paperpipe/tmp/teacher_quality_batch02_verify_final/goldset](/Users/jangseongjin/paperpipe/tmp/teacher_quality_batch02_verify_final/goldset)

Interpretation:
- widened candidate pool에서도 자연 quarantine는 발생하지 않았다.
- 현재 gate가 지나치게 느슨하다는 증거는 아니고, 현재 local-first candidate pool과 teacher output 형태에서는 gate reject 케이스가 잘 생성되지 않는다는 쪽이 더 정확하다.

## Quality Eval Result
- snapshot root:
  - [/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch02](/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch02)
- metrics:
  - [/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch02/metrics.json](/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch02/metrics.json)

Metrics:
- `total=3`
- `missing_prediction_count=0`
- `schema_valid_rate=1.0`
- `evidence_location_rate=1.0`
- `summary_artifact_rate=1.0`
- `manual_correction_rate=0.0`

## Compare Result
- compare report:
  - [/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch02.json](/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch02.json)
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
- widened extraction으로 실번들 수를 늘려도 자연 quarantine 사례는 나오지 않았다.
- current promoted baseline 대비 quality regression도 없다.
- 따라서 현재 canonical quarantine evidence는 여전히 controlled drill이다.
- 자연 quarantine는 “반드시 더 찾아야 하는 미완료”가 아니라, materially different candidate pool 또는 stricter gate change가 생길 때 다시 시도할 optional follow-up으로 보는 게 맞다.
