# Research DNA External Benchmark Breadth Follow-up (2026-03-13)

Status: Historical follow-up report  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
두 번째 independent source를 추가했을 때 external benchmark breadth가 실제로 넓어지는지 확인한다.

이번 follow-up의 목적은 두 가지다.
- `PMC9947355`가 current DNA 기준 clean include를 실제로 추가하는지 확인
- union manifest 기준으로 real probe run1/run2를 다시 평가해 breadth-sensitive evidence를 남기기

## Added Source
- [Ketogenic interventions in mild cognitive impairment, Alzheimer's disease, and Parkinson's disease: A systematic review and critical appraisal (PMC9947355)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9947355/)

source manifest:
- [pmc9947355_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc9947355_mci_subset_20260313.yaml)

adjudication summary:
- include `5`
- exclude `2`

new clean include contributed by this source:
- `doi:10.1016/j.plefa.2020.102236`

## Union Manifest
- [mci_mct_external_union_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml)

union summary:
- include `6`
- exclude `2`

include identifiers:
- `doi:10.1016/j.bbacli.2015.01.001`
- `doi:10.1016/j.jalz.2018.12.017`
- `doi:10.1016/j.neurobiolaging.2022.04.005`
- `doi:10.1002/trc2.12217`
- `doi:10.1002/alz.12206`
- `doi:10.1016/j.plefa.2020.102236`

## Execution
```bash
python3 scripts/evaluate_search.py \
  --run-id pilot_mci_mct_probe_20260312_01 \
  --research-dna-root research_dna \
  --search-eval-root storage/search_eval \
  --external-benchmark-manifest research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml

python3 scripts/evaluate_search.py \
  --run-id pilot_mci_mct_probe_20260312_02 \
  --research-dna-root research_dna \
  --search-eval-root storage/search_eval \
  --external-benchmark-manifest research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml \
  --baseline-metrics storage/search_eval/pilot_mci_mct_probe_20260312_01/metrics.json \
  --promote-dir baselines/search_eval
```

## Results
### Run 1
- [metrics.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_01/metrics.json)
- `external_benchmark_hit_count=0/6`
- `external_benchmark_recall=0.0`

### Run 2
- [metrics.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/metrics.json)
- `external_benchmark_hit_count=6/6`
- `external_benchmark_recall=1.0`

compare:
- [diff.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/diff.json)
- `external_benchmark_recall: 0.0 -> 1.0`

promotion:
- [pilot_mci_mct_probe_20260312_02__20260313T021008213218Z.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/history/pilot_mci_mct_probe_20260312_02__20260313T021008213218Z.metrics.json)

## Interpretation
이 follow-up으로 달라진 점:
- external subset breadth가 `5`에서 `6`으로 늘었다.
- run2는 더 넓어진 union manifest 기준에서도 `6/6`을 유지했다.

여전히 달라지지 않은 점:
- current `pilot.goldset_kind`는 그대로 `retrospective_provisional`
- union manifest는 좋은 independent external sanity layer지만, 아직 canonical external benchmark 승격 선언까지는 가지 않는다

## Current Conclusion
현재 시점에서 맞는 해석은 아래다.
- `PMC9947355`는 benchmark breadth를 실제로 넓힌 유의미한 두 번째 source다.
- current probe v2는 breadth-sensitive union manifest 기준에서도 전량 회수(`6/6`)를 유지한다.
- 다만 benchmark breadth가 아직 아주 크진 않으므로, 승격 여부는 추가 source 1개를 더 보거나 현재 `6 include`를 충분한 bounded benchmark로 볼지 정책 판단이 필요하다.
