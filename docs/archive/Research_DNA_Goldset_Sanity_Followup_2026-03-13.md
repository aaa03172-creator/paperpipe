# Research DNA Goldset Sanity Follow-up (2026-03-13)

Status: Historical follow-up report  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
`Research DNA`의 optional goldset recall이 실제 운영 산출물에서 필요한지와 논리에 맞는지를 다시 점검하고, 기존 real PubMed probe에 bounded sanity evidence를 추가한다.

이번 follow-up의 목적은 두 가지다.
- `scripts/evaluate_search.py`에 추가한 goldset-backed recall 계산이 실제 DNA artifact에서 작동하는지 확인
- recall 숫자가 과대해석되지 않도록 goldset provenance와 해석 경계를 같이 고정

## Why This Was Necessary
- 이전 probe는 precision 개선(`0.05 -> 0.8889`)은 입증했지만 recall 관점은 비어 있었다.
- `goldset sanity check는 optional`이라는 spec 문구만 있고, 실제 운영 DNA에 goldset이 없는 상태는 계약 검증이 덜 된 상태였다.
- 따라서 다음 단계는 기능 확대가 아니라, 이미 구현한 optional recall metric을 실제 artifact에 연결해 보는 것이 맞았다.

## Boundary Check
이번 follow-up이 논리적으로 허용되는 이유:
- 새 source를 추가하지 않았다.
- query를 다시 바꾸지 않았다.
- UI/API surface를 넓히지 않았다.
- 기존 수동 screening으로 이미 `include` 처리된 primary-study set만 사용했다.

이번 follow-up의 한계:
- goldset은 외부 benchmark가 아니라 retrospective provisional set이다.
- 따라서 이 recall은 external benchmark가 아니라 bounded sanity metric으로만 해석해야 한다.

## Goldset Provenance
대상 DNA:
- [profile.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml)

추가한 `pilot.goldset[]`:
- `doi:10.1016/j.jad.2025.03.008`
- `doi:10.1016/j.neurobiolaging.2022.04.005`
- `doi:10.1111/eci.13806`
- `doi:10.1002/trc2.12217`
- `doi:10.1016/j.plefa.2020.102236`
- `doi:10.1002/alz.12206`
- `doi:10.1016/j.jalz.2018.12.017`
- `doi:10.1016/j.bbacli.2015.01.001`

선정 기준:
- `pilot_mci_mct_probe_20260312_02`에서 human screening 결과 `include`로 남은 primary-study set
- review, hypothesis, broad memory-impaired cohort는 제외

audit trail:
- `approval_audit`에 update action으로 기록됨
- reason:
  - `add retrospective provisional goldset from manually included primary MCI plus medium-chain triglyceride studies for recall sanity check`

## Execution Note
처음 rerun 시도는 `goldset update`와 `evaluate_search.py`를 병렬로 돌려 순서가 꼬였기 때문에 무효로 폐기했다.

유효한 결과는 아래 순차 실행에서만 채택했다.
1. DNA `pilot.goldset[]` update
2. `pilot_mci_mct_probe_20260312_01` 재평가
3. `pilot_mci_mct_probe_20260312_02` 재평가 + baseline current/history 갱신

## Results
### Run 1
- run: [pilot_mci_mct_probe_20260312_01](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_01)
- metrics:
  - `precision_proxy=0.05`
  - `goldset_hit_count=1`
  - `goldset_total=8`
  - `goldset_recall=0.125`

해석:
- v1 broad query는 provisional goldset 8건 중 1건만 회수했다.
- acronym noise와 review-heavy drift가 recall/precision 둘 다 나쁘게 만들었다.

### Run 2
- run: [pilot_mci_mct_probe_20260312_02](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02)
- metrics:
  - `precision_proxy=0.8888888888888888`
  - `goldset_hit_count=8`
  - `goldset_total=8`
  - `goldset_recall=1.0`

해석:
- v2 query는 provisional goldset 전부를 회수했다.
- 이번 probe에서는 precision 개선과 recall 유지가 아니라, precision 개선과 recall 회복이 동시에 관찰됐다.

## Baseline Impact
- current baseline: [current.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/current.metrics.json)
- latest goldset-aware run2 history: [pilot_mci_mct_probe_20260312_02__20260313T013920781852Z.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/history/pilot_mci_mct_probe_20260312_02__20260313T013920781852Z.metrics.json)
- run1 history refreshed after goldset curation:
  - [pilot_mci_mct_probe_20260312_01.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/history/pilot_mci_mct_probe_20260312_01.metrics.json)
- compare provenance snapshot:
  - [baseline_snapshot.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/baseline_snapshot.json)

compare result:
- `KEEP`
- promotion: `true`

주의:
- baseline의 `goldset_recall`은 이전 current baseline에 없었기 때문에, 이번 promotion은 recall-improved compare라기보다 recall-aware baseline refresh에 가깝다.
- first goldset-aware promotion 시점에는 compare provenance snapshot artifact가 아직 없었기 때문에, 당시 `diff.json` provenance는 불완전했다.
- 이후 코드에서는 compare 시점 baseline을 `baseline_snapshot.json`으로 별도 보존하고, goldset-aware compare를 다시 실행해 현재 artifact를 갱신했다.
- repeated promotion이 같은 `history/<run_id>.metrics.json`를 덮어쓸 수 있던 문제도 append-only suffix naming으로 보강됐다.

## What Changed Logically
이 follow-up으로 달라진 점:
- optional goldset recall이 문서 규칙이 아니라 실제 운영 metric이 됐다.
- 기존 probe는 precision-only evidence였지만, 지금은 bounded recall sanity evidence까지 갖게 됐다.

여전히 달라지지 않은 점:
- 이 goldset은 retrospective provisional set이다.
- external benchmark 또는 independent adjudicated goldset은 아직 없다.
- 따라서 이 결과만으로 search policy를 일반화하면 안 된다.

## Current Conclusion
현재 시점에서 맞는 해석은 아래다.
- `Research DNA v0`의 bounded pilot/eval loop는 계획과 일치한다.
- goldset-backed recall 기능은 필요했고, 실제로 작동한다.
- 다만 현재 recall evidence는 sanity 수준이며, next-level evidence는 independent goldset이 있는 다른 DNA에서 확보해야 한다.
