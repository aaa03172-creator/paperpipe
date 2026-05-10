# Research DNA External Benchmark Subset Eval (2026-03-13)

Status: Historical follow-up report  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
`PMC11074881`에서 뽑아낸 adjudicated subset manifest가 실제 `Research DNA` probe 평가에 어떤 추가 증거를 주는지 확인한다.

이번 follow-up의 목적은 두 가지다.
- `retrospective_provisional goldset recall`과 별도로 `external benchmark subset recall`을 측정
- current probe가 external candidate subset에도 실제로 맞는지 확인하되, 아직 `external_benchmark`로 승격하지는 않음

## Inputs
대상 DNA:
- [profile.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml)

subset manifest:
- [pmc11074881_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml)

manifest summary:
- included studies: `5`
- excluded mixed-population study: `1`

## Execution
평가는 기존 fixed harness에 optional manifest input을 추가한 경로로 수행했다.

명령:
```bash
python3 scripts/evaluate_search.py \
  --run-id pilot_mci_mct_probe_20260312_01 \
  --research-dna-root research_dna \
  --search-eval-root storage/search_eval \
  --external-benchmark-manifest research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml

python3 scripts/evaluate_search.py \
  --run-id pilot_mci_mct_probe_20260312_02 \
  --research-dna-root research_dna \
  --search-eval-root storage/search_eval \
  --external-benchmark-manifest research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml \
  --baseline-metrics storage/search_eval/pilot_mci_mct_probe_20260312_01/metrics.json \
  --promote-dir baselines/search_eval
```

## Results
### Run 1
- run: [pilot_mci_mct_probe_20260312_01](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_01)
- metrics:
  - `precision_proxy=0.05`
  - `goldset_recall=0.125`
  - `external_benchmark_recall=0.0`
  - `external_benchmark_hit_count=0/5`

해석:
- broad v1 query는 external subset 기준 clean MCI studies를 하나도 회수하지 못했다.
- 이 결과는 `v1`이 그냥 noisy한 정도가 아니라, current MCI-specific benchmark subset에도 맞지 않았다는 걸 보여준다.

### Run 2
- run: [pilot_mci_mct_probe_20260312_02](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02)
- metrics:
  - `precision_proxy=0.8888888888888888`
  - `goldset_recall=1.0`
  - `external_benchmark_recall=1.0`
  - `external_benchmark_hit_count=5/5`

해석:
- refined v2 query는 retrospective provisional goldset뿐 아니라 adjudicated external subset도 전부 회수했다.
- 따라서 current probe의 개선은 내부 self-confirmation만이 아니라, 좁지만 independent subset evidence에도 부합한다.

## Compare
v2 compare artifact:
- [diff.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/diff.json)
- [baseline_snapshot.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/baseline_snapshot.json)

핵심 delta:
- `precision_proxy`: `0.05 -> 0.8888888888888888`
- `goldset_recall`: `0.125 -> 1.0`
- `external_benchmark_recall`: `0.0 -> 1.0`

promotion:
- `KEEP`
- promoted history:
  - [pilot_mci_mct_probe_20260312_02__20260313T020439086723Z.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/history/pilot_mci_mct_probe_20260312_02__20260313T020439086723Z.metrics.json)

## Boundary
이번 follow-up으로도 바뀌지 않는 점:
- current `pilot.goldset_kind`는 여전히 `retrospective_provisional`이다.
- subset manifest는 좋은 external evidence이지만, benchmark 분모가 아직 `5 include`로 얇다.
- 따라서 이 결과만으로 canonical `external_benchmark` 승격을 선언하지는 않는다.

## Current Conclusion
현재 시점의 정확한 해석은 아래다.
- `PMC11074881` adjudicated subset은 current probe에 대해 유효한 external sanity layer를 제공한다.
- v2 query는 그 subset 기준에서도 `5/5`를 회수했다.
- 다만 benchmark breadth는 아직 제한적이므로, 다음 단계는 이 subset을 canonical benchmark로 승격하는 것이 아니라 분모를 더 넓힐 source를 1개 더 찾는 것이다.
