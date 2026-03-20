# Research DNA Bounded External Benchmark Policy (2026-03-13)

Status: Historical policy note  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
`Research DNA`에서 external subset evidence가 어느 수준이면 "bounded external benchmark"로 간주할 수 있는지 최소 판단 기준을 고정한다.

이 문서는 자동 승격 규칙이 아니라, operator 판단 기준을 좁히기 위한 정책 메모다.

## Why This Is Needed
- current workspace에서는 `external_benchmark_recall` 계산, logging, keep/discard policy 연동까지 끝났다.
- 하지만 어떤 시점에 현재 union subset을 충분한 bounded external benchmark로 볼지 기준이 없으면, 같은 evidence를 두고도 해석이 흔들린다.

## Recommended Minimum Bar
아래 네 조건을 모두 만족하면 `bounded external benchmark candidate`로 인정할 수 있다.

1. independent sources `>= 2`
- 서로 다른 review/source에서 온 adjudicated subset이어야 한다.

2. adjudicated union include `>= 6`
- current DNA scope 기준 clean include가 최소 6건 이상이어야 한다.
- mixed-population 또는 off-boundary intervention은 분모에 넣지 않는다.

3. unresolved mixed includes `= 0`
- mixed AD/MCI population 같은 경계 사례는 include가 아니라 exclude 또는 pending adjudication이어야 한다.

4. latest target run shows `external_benchmark_recall = 1.0`
- union subset 기준으로 실제 run이 전량 회수해야 한다.

## Current Probe Status
current probe는 이 기준을 아래처럼 충족한다.
- independent sources: `2`
  - `PMC11074881`
  - `PMC9947355`
- adjudicated union include: `6`
- unresolved mixed includes: `0`
- latest target run:
  - `pilot_mci_mct_probe_20260312_02`
  - `external_benchmark_recall = 1.0 (6/6)`

## Decision
현재 probe는 `bounded external benchmark candidate`로는 충분하다.

다만 아래 이유로 즉시 canonical `pilot.goldset_kind=external_benchmark`로 바꾸지는 않는다.
- 현재 DNA는 이미 `retrospective_provisional` goldset 운영 기록을 갖고 있다.
- 승격은 기술적 가능 여부보다 operator 승인 기록이 더 중요하다.
- 따라서 kind 변경은 별도 explicit approval action으로만 수행한다.

## Operational Rule
현재 권장 rule은 아래다.
- default:
  - `pilot.goldset_kind`는 그대로 유지
- allowed:
  - explicit approval이 있으면 `retrospective_provisional -> external_benchmark` 승격 가능
- not allowed:
  - source/manifest가 생겼다는 이유만으로 자동 승격

## Current Recommendation
현재 상태에서 가장 맞는 선택은 아래다.
- current probe는 `bounded external benchmark candidate confirmed`로 문서화
- 실제 `goldset_kind` 승격은 별도 approval이 있을 때만 수행

## Post-Approval Update
이 문서 작성 직후 explicit operator approval이 실제로 들어왔고, 승격도 적용됐다.

적용 결과:
- profile revision:
  - `2 -> 3`
- `pilot.goldset_kind`:
  - `retrospective_provisional -> external_benchmark`
- canonical benchmark:
  - adjudicated union include set `6 studies`
- promotion report:
  - [Research_DNA_External_Benchmark_Promotion_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Promotion_2026-03-13.md)

운영 처리에서 한 번의 parallel rerun은 폐기됐다.
- 이유: run2가 stale baseline과 비교될 수 있었기 때문이다.
- canonical 채택 결과는 순차 재실행만 사용한다.
- accepted result:
  - run1 `0/6`
  - run2 `6/6`
