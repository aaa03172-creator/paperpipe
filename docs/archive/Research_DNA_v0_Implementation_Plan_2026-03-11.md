# Research DNA v0 Implementation Plan (2026-03-11)

Status: Historical implementation plan  
Date: 2026-03-11  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Purpose
이 문서는 `docs/RESEARCH_DNA.md`를 실제 코드로 내릴 때 단계별 의도, 방향성, 금지사항, acceptance를 고정하기 위한 구현 계획이다.

핵심 원칙은 세 가지다.
- `ResearchDNA`는 현재 `config/profiles.yaml`를 대체하지 않는다.
- 작은 PR 순서로 내려가며, 각 단계는 독립 검증 가능해야 한다.
- append-only audit와 fixed evaluation contract를 깨는 지름길은 허용하지 않는다.

## Phase 1: Schema + Store + Runtime Paths
목적:
- `ResearchDNA`를 human-editable asset으로 저장할 최소 구조를 만든다.
- current `Profile`과 별개로 DNA-only metadata를 보존한다.
- 하드코딩 경로 없이 `research_dna_root()` / `search_eval_root()`의 기반을 만든다.

의도:
- 지금 필요한 것은 저장 계약과 path policy다.
- 아직 pilot logic이나 API 표면을 열 시점이 아니다.

범위:
- `src/profiles/research_dna_schema.py`
- `src/profiles/research_dna_store.py`
- `src/services/runtime_paths.py` extension
- schema/store/path regression tests

비범위:
- FastAPI endpoint
- CLI subcommand
- pilot execution
- screening queue generation
- search eval harness

Acceptance:
- DNA asset를 save/load할 수 있다.
- `profile.yaml`, `versions/`, `logs/` 구조를 deterministic하게 만든다.
- append-only log entry를 typed contract로 저장할 수 있다.
- env override로 DNA/search eval root를 바꿀 수 있다.

## Phase 2: Service Layer For Pilot And Audit
목적:
- `DRAFT -> PILOT -> LOCKED` 전이와 append-only audit를 service contract로 묶는다.

의도:
- core logic은 API/CLI보다 먼저 service layer에 있어야 한다.
- actor attribution과 lock semantics를 여기서 강제해야 한다.

범위:
- create/update/approve_pilot/run_pilot/submit_screening/refine/lock service primitives
- state transition validation
- append-only approval and run logging

비범위:
- UI wizard
- chat UX
- provider-specific orchestration

Acceptance:
- invalid transition은 deterministic하게 거부된다.
- `LOCKED` 전이는 actor-attributed approval log 없이 진행되지 않는다.
- refine acceptance는 version bump + audit log를 남긴다.

## Phase 3: Thin CLI/API Wrappers
목적:
- service contract를 operator surface에 연결한다.

의도:
- runtime은 API-first여야 하고, CLI-only logic이 되면 안 된다.

범위:
- thin CLI wrappers
- minimal FastAPI endpoints
- request/response schema validation

비범위:
- multi-step frontend wizard
- conversational intake UI

Acceptance:
- CLI와 API가 같은 service layer를 사용한다.
- write path가 모두 동일한 audit semantics를 따른다.

## Phase 4: Fixed Search Evaluation Harness
목적:
- pilot/refine 결과를 keep/discard 가능한 comparable metrics로 바꾼다.

의도:
- search eval은 quality eval과 별도 계약이어야 한다.
- baseline comparison은 artifact contract가 정해진 뒤에만 의미가 있다.

범위:
- `scripts/evaluate_search.py`
- `storage/search_eval/<run_id>/...` artifact set
- precision proxy / optional goldset recall / top reason codes

비범위:
- PRESS automation
- external DOI archiving
- broad source expansion

Acceptance:
- 같은 input DNA/run에 대해 동일 artifact layout이 나온다.
- compare 가능한 `metrics.json`을 안정적으로 만든다.

## Cross-Cutting Guardrails
아래 규칙은 모든 phase에 공통 적용한다.

1. Canonical boundary
- `ResearchDNA`는 design/audit asset이다.
- `Profile`은 executable projection이다.
- 둘을 같은 editable source of truth로 취급하지 않는다.

2. Append-only discipline
- `query_versions`는 overwrite 금지다.
- screening/run/approval 기록은 append-only다.

3. Actor attribution
- `lock`, `unlock`, `refine`, `approve_pilot`는 actor metadata가 필수다.

4. Policy-first sources
- source allowlist는 먼저 문서/정책에 있어야 한다.
- 구현 코드가 prompt wording만으로 source를 확장하면 안 된다.

5. Local-first compatibility
- env override 가능
- repo-relative fallback 유지
- 기존 `config/profiles.yaml` operator flow를 깨지 않는다.

## Immediate Development Start
이번 작업에서 바로 시작할 범위는 Phase 1이다.
- `research_dna_schema.py`
- `research_dna_store.py`
- `runtime_paths.py` 확장
- tests

Execution status:
- 2026-03-11 workspace 기준 Phase 1은 완료됐다.
- 2026-03-11 workspace 기준 Phase 2의 state transition + audit service slice도 부분 완료됐다.
- 2026-03-12 workspace 기준 `run_pilot` + initial search-eval artifact generation도 완료됐다.
- 2026-03-12 workspace 기준 thin FastAPI wrapper도 완료됐다.
- 2026-03-12 workspace 기준 thin CLI wrapper와 `scripts/evaluate_search.py`도 완료됐다.
- 2026-03-12 workspace 기준 `update_dna` path와 `DRAFT` 단계 query draft 허용도 반영됐다.
- 2026-03-12 workspace 기준 compare/promotion workflow도 baseline 운영 루프로 연결됐다.
- 2026-03-12 workspace 기준 keep/discard threshold policy와 baseline naming rule도 정리됐다.
- 2026-03-12 workspace 기준 `partial` pilot status와 `runs.jsonl` metric snapshot 정합성도 보완됐다.
- 2026-03-12 workspace 기준 real PubMed pilot batch로 baseline seed/compare/promotion 운영 기록도 남겼다.
- 2026-03-12 workspace 기준 first-run baseline seed helper도 추가됐다.
- 2026-03-12 workspace 기준 interview logging operator surface도 추가됐다.
- 2026-03-13 workspace 기준 optimistic revision 기반 concurrency-safe mutation rule도 추가됐다.
- 2026-03-13 workspace 기준 optional goldset-backed recall evaluation도 `scripts/evaluate_search.py`에 연결됐다.
- 2026-03-13 workspace 기준 retrospective provisional goldset을 사용한 real pilot recall sanity follow-up도 기록됐다.
- 2026-03-13 workspace 기준 repeated promotion history overwrite를 막는 append-only history naming과 compare provenance snapshot도 보강됐다.
- 2026-03-13 workspace 기준 `versions/vN.yaml`은 full state가 아니라 deterministic query-only snapshot으로 의미를 좁혔다.
- 2026-03-13 workspace 기준 `pilot.goldset_kind / goldset_sources / goldset_note` provenance fields도 추가됐다.
- 2026-03-13 workspace 기준 independent external benchmark candidate source review도 문서로 고정됐다.
- 현재 결론은 immediate promotion이 아니라, current DNA criteria에 맞는 study-level adjudication 후 subset benchmark를 만드는 것이다.
- 2026-03-13 workspace 기준 `PMC11074881` adjudicated subset manifest도 실제 artifact로 저장됐다 (`5 include`, `1 exclude`).
- 2026-03-13 workspace 기준 real probe run1/run2를 subset manifest로 다시 평가했고, `external_benchmark_recall`이 `0.0 -> 1.0`으로 기록됐다.
- 2026-03-13 workspace 기준 second independent source(`PMC9947355`)도 adjudicate했고, union manifest breadth를 `6 include / 2 exclude`까지 넓혔다.
- 2026-03-13 workspace 기준 union manifest로 real probe run1/run2를 다시 평가했고 `external_benchmark_recall`이 `0.0 (0/6) -> 1.0 (6/6)`으로 유지됐다.
- 2026-03-13 workspace 기준 `keep/discard` policy도 optional `external_benchmark_recall_delta`를 읽도록 정합성을 보강했다.
- 2026-03-13 workspace 기준 `bounded external benchmark candidate`의 최소 판단 기준도 문서로 고정했다.
- 2026-03-13 workspace 기준 explicit operator approval이 실제로 적용됐고, `pilot.goldset_kind`도 `retrospective_provisional -> external_benchmark`로 승격됐다.
- 2026-03-13 workspace 기준 promotion 직후의 parallel rerun은 stale baseline 비교 가능성 때문에 폐기했고, 순차 재평가 결과(`run1 0/6`, `run2 6/6`)만 canonical로 채택했다.
- 2026-03-13 workspace 기준 future goldset-kind changes는 generic `update`가 아니라 dedicated `change_goldset_kind` audit action으로 남기도록 taxonomy를 보강했다.
- 2026-03-13 workspace 기준 `ResearchDNA -> Profile` deterministic projection helper도 추가됐다.
  - projected profile ID: `research_dna_<dna_id>`
  - projection mode: compatibility snapshot only
  - `enabled=false`, `schedule=manual`
  - exact per-db query와 DNA provenance는 `Profile.notes`에 기록
- 2026-03-13 workspace 기준 legacy `profiles` / `audit` CLI도 projected profile을 read-only로 취급하도록 guard를 추가했다.
- 2026-03-13 workspace 기준 real workspace projection validation도 완료됐다.
  - actual probe DNA projected into `config/profiles.yaml`
  - sequential rerun confirmed idempotent upsert with no duplicate profile entry
  - validation 과정에서 드러난 fixed-temp-path race는 `profile_store.py` / `research_dna_store.py` atomic writer hardening으로 보완했다
- 2026-03-13 workspace 기준 legacy `profiles` / `audit` CLI는 `PAPERPIPE_PROFILES_PATH` override도 따르도록 정렬됐다.
- 2026-03-13 workspace 기준 operator-facing `profiles.yaml` writes는 `rewrite_profiles_config()` / `upsert_profile()` 기반 lock + merge-safe path로 전환됐다.
- 2026-03-13 workspace 기준 legacy `profiles` / `audit` CLI에서 same-profile mutation은 per-profile revision conflict로 stale overwrite를 막는다.
- 2026-03-13 workspace 기준 raw `save_profiles_snapshot()` overwrite는 operator-facing profiles path에서 기본 금지되고, fixture/bootstrap snapshot만 explicit unsafe escape hatch로 허용된다.
- 2026-03-13 workspace 기준 generic `rewrite_profiles_config()` bulk rewrite도 operator-facing profiles path에서는 기본 금지되고, projection 같은 system-owned path만 explicit opt-in으로 허용된다.
- 2026-03-13 workspace 기준 `profile_store` public surface는 low-level snapshot(`save_profiles_snapshot`) / system-owned bulk rewrite(`rewrite_profiles_config`) / operator-safe single-profile write(`upsert_profile`)로 명시적으로 분리됐다.
- 2026-03-13 workspace 기준 double-check 과정에서 `upsert_profile()`가 operator-path bulk guard에 같이 걸리는 회귀를 잡았고, 내부 구현을 `rewrite_profiles_config(..., allow_operator_bulk_update=True)`로 정렬해 수정했다.
- 현재 시점에서 `Research DNA v0`의 blocking gap은 없다. 이후 작업은 optional benchmark breadth 확대나 explicit projection helper 같은 follow-up이다.

## References
- `docs/RESEARCH_DNA.md`
- `docs/archive/Deep_Research_Report5_Fit_Review_2026-03-11.md`
- `docs/archive/Prompt_Review_Integrated_Priority_2026-03-11.md`
