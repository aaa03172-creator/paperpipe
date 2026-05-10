# Research DNA Real Pilot Probe (2026-03-12)

Status: Historical execution report  
Date: 2026-03-12  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
`Research DNA v0`의 실제 운영 경로를 한 번 끝까지 태워서 아래를 확인한다.
- real PubMed pilot retrieval
- append-only screening / run / approval audit
- baseline seed
- fixed compare/promotion

## Probe Setup
- `dna_id`: `dna_mci_medium_chain_triglycerides_probe_20260312`
- topic: `Mild cognitive impairment and medium-chain triglycerides`
- intent: `systematic_review`
- `recommended_databases`: `pubmed`, `embase`
- `available_databases`: `pubmed`
- pilot `n=20`
- goldset: 없음
- actor: `human_cli:codex`

## Query Versions
### `v1`
- mode: `recall`
- PubMed query:
  - `("mild cognitive impairment"[Title/Abstract] OR MCI[Title/Abstract]) AND (("medium-chain triglycerides"[Title/Abstract]) OR ("medium chain triglyceride"[Title/Abstract]) OR ("medium chain triglyceride oil"[Title/Abstract]) OR MCT[Title/Abstract])`

### `v2`
- mode: `precision`
- refinement rationale:
  - `MCT` acronym noise 제거
  - review/meta-analysis/hypothesis title signal 차단
- PubMed query:
  - `("mild cognitive impairment"[Title/Abstract] OR "mild neurocognitive disorder"[Title/Abstract]) AND (("medium-chain triglycerides"[Title/Abstract]) OR ("medium chain triglyceride"[Title/Abstract]) OR ("medium chain triglyceride oil"[Title/Abstract])) NOT (("systematic review"[Title]) OR ("meta-analysis"[Title]) OR ("narrative review"[Title]) OR (review[Publication Type]) OR (hypothesis[Title]))`

## Runs
### Run 1
- `run_id`: `pilot_mci_mct_probe_20260312_01`
- artifact dir: [pilot_mci_mct_probe_20260312_01](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_01)
- retrieved: `20`
- deduped: `20`
- labeled: `20`
- include: `1`
- exclude: `19`
- precision proxy: `0.05`
- top noise:
  - `protocol_editorial_or_review_only`
  - `wrong_domain_or_condition`
  - `wrong_intervention_or_exposure`

### Run 2
- `run_id`: `pilot_mci_mct_probe_20260312_02`
- artifact dir: [pilot_mci_mct_probe_20260312_02](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02)
- retrieved: `9`
- deduped: `9`
- labeled: `9`
- include: `8`
- exclude: `1`
- precision proxy: `0.8888888888888888`
- remaining noise:
  - `wrong_population`

## Baseline Seed And Promotion
### Seed
- baseline root: [dna_mci_medium_chain_triglycerides_probe_20260312](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312)
- seed method:
  - `run1 metrics.json`을 `current.metrics.json`과 `history/pilot_mci_mct_probe_20260312_01.metrics.json`으로 수동 seed
- note:
  - probe 실행 시점에는 `evaluate_search.py`에 first-run baseline seed helper가 없어서 수동 seed가 필요했다.
  - 이후 helper가 추가되어, 후속 run부터는 `--promote-dir ... --seed-baseline-if-missing`로 자동 seed 가능하다.

### Compare / Promotion
- compare artifact: [diff.json](/Users/jangseongjin/paperpipe/storage/search_eval/pilot_mci_mct_probe_20260312_02/diff.json)
- result: `KEEP`
- promotion: `true`
- promoted current:
  - [current.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/current.metrics.json)
- promoted history:
  - [pilot_mci_mct_probe_20260312_02.metrics.json](/Users/jangseongjin/paperpipe/baselines/search_eval/dna_mci_medium_chain_triglycerides_probe_20260312/history/pilot_mci_mct_probe_20260312_02.metrics.json)

## What This Validated
- `ResearchDNA` 생성, update, refine, pilot, screening, evaluate 경로가 실제 PubMed 데이터로 동작했다.
- post-probe follow-up으로 `interview.jsonl` operator surface도 실제 DNA artifact에 연결됐다.
- `runs.jsonl`는 run-start snapshot과 evaluate-after-screening snapshot을 append-only로 남겼다.
- v1 screening reason codes를 기준으로 v2 query를 조정했을 때 precision proxy가 실질적으로 개선됐다.
- `recommended_databases`와 `available_databases` 분리도 artifact와 DNA profile에 그대로 남았다.

## Observations
- v1 query의 가장 큰 문제는 `MCT` acronym ambiguity였다.
  - metacognitive training
  - movement control impairment / motor control test
- review-heavy noise도 컸다.
- v2는 retrieval count를 `20 -> 9`로 줄였지만, precision proxy를 `0.05 -> 0.8889`로 올렸다.
- probe 자체는 goldset이 없어서 recall 관점은 비어 있었다.
- 이후 `scripts/evaluate_search.py`에 goldset-backed recall 계산이 추가되어, `pilot.goldset[]`가 있는 DNA에서는 `retrieved.jsonl` 기준 recall을 계산할 수 있다.

## Residual Gaps
- 이번 probe는 `pubmed` 단일 source만 사용했다.
- 이 DNA는 운영 probe 성격이라 아직 `LOCKED`로 전이하지 않았다.

Post-probe follow-up:
- interview logging operator surface는 이후 구현으로 보강됐다.
- optimistic revision guard로 duplicate create와 stale overwrite도 이후 구현으로 보강됐다.
- goldset-backed recall sanity follow-up은 별도 기록으로 분리했다:
  - [Research_DNA_Goldset_Sanity_Followup_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Goldset_Sanity_Followup_2026-03-13.md)

## Key Files
- DNA profile: [profile.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml)
- interview log: [interview.jsonl](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/interview.jsonl)
- approval audit: [approval_audit.jsonl](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/approval_audit.jsonl)
- screening log: [screening.jsonl](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/screening.jsonl)
- run log: [runs.jsonl](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/runs.jsonl)
