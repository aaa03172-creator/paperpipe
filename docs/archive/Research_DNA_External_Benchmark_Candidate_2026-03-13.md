# Research DNA External Benchmark Candidate Review (2026-03-13)

Status: Historical review note  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
현재 `Research DNA` probe의 goldset이 `retrospective_provisional`에 머물러 있기 때문에, independent external benchmark 후보 source를 검토하고 지금 바로 승격해도 되는지 판단한다.

이번 문서의 목적은 두 가지다.
- current DNA scope와 외부 review scope가 실제로 맞는지 확인
- 맞지 않으면 "후보 source"로만 남기고, 왜 아직 external benchmark가 아닌지 audit 근거를 남기기

## Candidate Sources Reviewed
### Candidate A
- [The Effects of Medium Chain Triglyceride for Alzheimer’s Disease Related Cognitive Impairment: A Systematic Review and Meta-Analysis (PMC10357178)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10357178/)
- 이 review는 MCT가 `MCI 또는 AD` 환자의 인지기능에 미치는 효과를 다룬다.

### Candidate B
- [The Effect of Medium-Chain Triglycerides on Cognitive Performance in Alzheimer's Disease and Mild Cognitive Impairment: A Systematic Review of Clinical Trials (PMC11074881)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11074881/)
- 이 review는 AD와 MCI를 함께 다루지만, 본문에서 MCI 포함 연구를 별도로 식별한다.
- review는 `Reger`, `Rebello`, 그리고 `Fortier/Roy`의 four BENEFIC trials를 MCI 포함 연구로 직접 언급한다.

### Candidate C
- [Ketogenic interventions in mild cognitive impairment, Alzheimer's disease, and Parkinson's disease: A systematic review and critical appraisal (PMC9947355)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9947355/)
- 이 review는 ketogenic intervention 전반을 다루지만, MCI 섹션에서 `Krikorian`, `Fortier`, `Roy` 계열 연구를 분리해 제시한다.
- current DNA 기준으로는 `ketogenic diet`는 제외해야 하고, `kMCT` 계열만 채택 가능하다.

## Current DNA Scope
대상 DNA:
- [profile.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml)

현재 DNA criteria:
- population: adults with mild cognitive impairment
- intervention/exposure: medium-chain triglycerides
- study type: human clinical study
- exclusions:
  - animal-only studies
  - non-cognitive outcomes only
  - protocol/editorial/review without primary human data

중요한 경계:
- 현재 DNA는 `MCI-only`에 가깝다.
- candidate review는 `MCI or AD`를 함께 다룬다.
- 따라서 review 전체를 그대로 external benchmark로 승격하면 scope drift가 생긴다.

## What Was Checked
1. review의 모집단 범위가 current DNA보다 넓은지
2. review에 포함된 primary studies 중 current DNA criteria와 직접 맞는 연구가 있는지
3. local pilot retrieved pool과 screening 결과가 그 판단과 일치하는지
4. 더 적합한 candidate source가 있으면 current goldset과 overlap이 실제로 커지는지

## Local Mapping
### Clean match
- `Fortier et al. 2021`
  - DOI: `10.1002/alz.12206`
  - review reference: candidate review reference list entry 39
  - local run presence:
    - [pilot_mci_mct_probe_20260312_02/retrieved.jsonl](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/retrieved.jsonl)
  - current DNA fit:
    - MCI
    - human clinical intervention
    - MCT-aligned
  - current status:
    - provisional goldset included

### Scope-mismatch example
- `Reger et al. 2004`
  - DOI: `10.1016/S0197-4580(03)00087-3`
  - review reference: candidate review reference list entry 40
  - local run presence:
    - [pilot_mci_mct_probe_20260312_02/retrieved.jsonl](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/retrieved.jsonl)
  - local summary indicates mixed `AD or MCI` memory-impaired adults, not current MCI-only target
  - current DNA fit:
    - fails current population boundary
  - local screening decision:
    - [screening.jsonl](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/screening.jsonl)
    - `exclude`
    - `reason_code=wrong_population`

## Study-Level Adjudication Snapshot
`Candidate A` review table 기준 포함 clinical trial 10건을 current DNA 기준으로 다시 본 결과는 아래와 같다.

| Study | Population/intervention snapshot | Current DNA fit | Note |
| --- | --- | --- | --- |
| Ota et al. 2019 (postprandial) | mild-moderate AD, MCT | Exclude | AD population |
| Ota et al. 2019 (chronic feeding) | mild-moderate AD, MCT | Exclude | AD population |
| Henderson et al. 2009 | mild-moderate AD, AC-1202 | Exclude | AD population |
| Gandotra et al. 2014 | moderate/severe AD, extra virgin coconut oil | Exclude | AD population and non-standard MCT exposure |
| Juby et al. 2022 | AD, MCT oil | Exclude | AD population |
| Ortí et al. 2017 | AD, coconut oil | Exclude | AD population and non-standard MCT exposure |
| Fortier et al. 2021 | MCI, ketogenic drink / MCT-aligned | Include | clean current-scope match |
| Reger et al. 2004 | probable AD plus amnestic MCI, caprylic acid | Exclude | mixed population; local screening marked `wrong_population` |
| Xu et al. 2020 | mild-moderate AD, MCT | Exclude | AD population |
| Henderson et al. 2020 | mild-to-moderate Alzheimer’s disease, AC-1204 | Exclude | AD population |

요약:
- clean include: `1/10`
- mixed / boundary case: `1/10`, but current DNA 기준에서는 exclude
- clear out-of-scope: `8/10`

이 숫자 자체가 현재 판단을 강하게 뒷받침한다.
- 이 review는 current DNA용 independent benchmark가 아니라, broader AD-related literature review에 가깝다.
- current DNA benchmark로 쓰려면 review 전체가 아니라 `adjudicated subset`만 따로 만들어야 한다.

## Better-Fit Candidate Follow-up
`Candidate B`는 current DNA와의 overlap이 더 크다.

review 본문이 MCI 포함 연구로 직접 짚는 항목 중, local provisional goldset과 겹치는 것은 아래다.
- `10.1016/j.bbacli.2015.01.001`
- `10.1016/j.jalz.2018.12.017`
- `10.1002/alz.12206`
- `10.1016/j.neurobiolaging.2022.04.005`
- `10.1002/trc2.12217`

실제 adjudicated subset manifest:
- [pmc11074881_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml)

즉 `Candidate B`는 current provisional goldset과 직접 겹치는 clean include `5건`을 제공하고, 추가로 mixed-population exclude `1건`을 제공한다.

남는 경계도 분명하다.
- `Reger et al. 2004`는 review가 MCI 포함 연구로 언급하지만, 실제 population은 `probable AD + amnestic MCI` 혼합이다.
- 그래서 current DNA 기준으로는 여전히 automatic include가 아니라 adjudication 대상이다.

정리하면:
- `Candidate A`: source quality는 괜찮지만 current DNA fit이 너무 약하다.
- `Candidate B`: 훨씬 더 강한 external candidate source다.
- 그래도 review-level source를 그대로 benchmark로 승격하면 안 되고, accepted subset manifest를 먼저 만들어야 한다.

## Independent Breadth Follow-up
`Candidate C`는 breadth 측면에서 실제 추가 가치가 있었다.

source manifest:
- [pmc9947355_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc9947355_mci_subset_20260313.yaml)

`Candidate C` adjudication:
- include `5`
- exclude `2`

현재 DNA 기준 clean include는 아래다.
- `10.1016/j.jalz.2018.12.017`
- `10.1002/alz.12206`
- `10.1002/trc2.12217`
- `10.1016/j.plefa.2020.102236`
- `10.1016/j.neurobiolaging.2022.04.005`

exclude:
- `10.1016/j.neurobiolaging.2010.10.006`
  - ketogenic diet intervention이라 current medium-chain triglyceride boundary 밖
- `10.1016/S0197-4580(03)00087-3`
  - mixed AD/MCI population

중요한 점:
- `Candidate C`는 `PMC11074881`에는 없던 `10.1016/j.plefa.2020.102236`를 새 clean include로 추가했다.
- 그래서 external benchmark breadth는 `5 -> 6`으로 실제 확장됐다.

union manifest:
- [mci_mct_external_union_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml)
- union summary:
  - include `6`
  - exclude `2`

## Judgment
현재 시점의 판단은 아래와 같다.
- external review는 좋은 `external source of candidate studies`다.
- `Candidate B`가 `Candidate A`보다 현재 DNA용 benchmark 후보로 더 적합하다.
- `Candidate C`는 현재까지 확인한 source 중 benchmark breadth를 실제로 넓힌 첫 independent source다.
- 하지만 current DNA의 canonical `external_benchmark`로 바로 승격하기에는 여전히 review scope가 넓다.
- 이유:
  - review 자체가 `MCI or AD`를 함께 다룬다.
  - current DNA는 `MCI + medium-chain triglycerides + human clinical study`로 더 좁다.
  - review에 포함된 일부 study는 current DNA 기준에서 제외되어야 한다.

따라서 지금 맞는 상태 표시는 다음이다.
- `pilot.goldset_kind = retrospective_provisional` 유지
- candidate review는 `goldset_sources`가 아니라 adjudication 후보 source로만 취급

## Why Promotion Is Deferred
지금 바로 external benchmark로 승격하면 아래 audit 문제가 생긴다.
- benchmark 분모에 scope 밖 study가 섞인다.
- recall 숫자가 좋아도 current DNA retrieval quality가 아니라 benchmark scope mismatch를 반영할 수 있다.
- 이후 refine compare가 current DNA 기준이 아니라 broader AD-related cohort 기준으로 흔들린다.

## Minimal Next Step
외부 benchmark 승격 전에 필요한 최소 작업은 하나다.
1. `Candidate B`와 `Candidate C`의 adjudicated subset을 기준으로 breadth를 다시 점검한다.

그 결과로 아래만 만들면 된다.
- `external benchmark manifest`
  - accepted studies only
  - identifier normalization
  - adjudication reason per study

`Candidate A`만 보면 clean include가 `Fortier et al. 2021` 하나뿐이라 benchmark 분모가 너무 얇다.
`Candidate B`는 훨씬 낫고, `Candidate C`는 실제로 분모를 `6`까지 넓혔다.
그래도 review-level source를 그대로 benchmark로 두기에는 mixed-population case와 intervention-boundary case가 남아 있다.

따라서 실무적으로는 둘 중 하나가 필요하다.
1. union manifest 기준으로도 benchmark breadth가 충분한지 다시 판단한다.
2. 그 다음에도 benchmark 분모가 얇으면 additional independent review/source를 더 찾는다.
3. 또는 current DNA scope를 더 넓히는 별도 DNA를 만든다.

그 전까지는 current probe의 goldset을 `external_benchmark`로 바꾸지 않는다.

## Conclusion
이번 검토로 확인된 것은 다음이다.
- external benchmark 후보 source는 찾았다.
- `Candidate B`와 `Candidate C`를 합친 union manifest가 현재 가장 강한 external subset artifact다.
- 하지만 current DNA scope와 1:1로 자동 정렬되지는 않는다.
- 따라서 지금 논리적으로 맞는 조치는 "즉시 승격"이 아니라 "union manifest까지 포함한 breadth 판단 후 추가 source 필요 여부 결정"이다.
