# Research DNA External Benchmark Promotion (2026-03-13)

Status: Historical runtime report  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Purpose
`Research DNA` probe에서 bounded external benchmark candidate를 실제 canonical `external_benchmark`로 승격한 근거와 채택된 운영 결과를 고정한다.

## Approval
- operator approval received: `2026-03-13`
- approval mechanism: `update_research_dna(...)` through the service layer
- approval log:
  - `/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/approval_audit.jsonl`
- taxonomy note:
  - this historical promotion row is recorded as `update`
  - the dedicated `change_goldset_kind` audit action was added afterward so future promotions are no longer mixed into generic updates
- approval reason:
  - `explicit operator approval to promote pilot goldset from retrospective_provisional to external_benchmark using adjudicated union subset after bounded external benchmark criteria were met`

## Canonical State Transition
- profile:
  - [/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml)
- revision:
  - `2 -> 3`
- `pilot.goldset_kind`:
  - `retrospective_provisional -> external_benchmark`
- canonical benchmark set:
  - adjudicated union include set with `6 studies`

## Benchmark Sources
- union manifest:
  - [/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml)
- supporting subset manifests:
  - [/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml)
  - [/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc9947355_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc9947355_mci_subset_20260313.yaml)

Canonical benchmark identifiers:
- `doi:10.1016/j.bbacli.2015.01.001`
- `doi:10.1016/j.jalz.2018.12.017`
- `doi:10.1016/j.neurobiolaging.2022.04.005`
- `doi:10.1002/trc2.12217`
- `doi:10.1002/alz.12206`
- `doi:10.1016/j.plefa.2020.102236`

## Evaluation Rerun Handling
One rerun attempt was discarded.

Reason:
- run1 and run2 were re-evaluated in parallel immediately after promotion
- that ordering let run2 compare against a stale baseline state
- the result was therefore non-canonical and not adopted

Accepted rerun rule:
- evaluate run1 first
- then evaluate run2 against the updated run1 baseline
- only this sequential rerun is treated as canonical

## Canonical Result
- run1 metrics:
  - [/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_01/metrics.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_01/metrics.json)
  - `goldset_recall = 0.0 (0/6)`
  - `external_benchmark_recall = 0.0 (0/6)`
- run2 metrics:
  - [/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/metrics.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/metrics.json)
  - `goldset_recall = 1.0 (6/6)`
  - `external_benchmark_recall = 1.0 (6/6)`
- compare artifact:
  - [/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/diff.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/diff.json)
  - `decision = KEEP`
  - `promotion.promoted = true`

## Remaining Risk
- current benchmark breadth is still bounded rather than broad.
- this is sufficient for the current probe, but it is not evidence that every future DNA should adopt `external_benchmark` after only one union manifest.
