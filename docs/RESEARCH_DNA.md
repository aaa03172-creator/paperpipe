# Research DNA

Status: Active  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose
`Research DNA`는 Search Profile을 일회성 대화 결과가 아니라, 재현 가능한 search-design asset으로 다루기 위한 bounded spec이다.

현재 product exposure note:
- `Research DNA`는 active core lane이지만, 현 단계에서는 API/CLI operator surface가 canonical entry다.
- dedicated frontend/web viewer route는 아직 현재 main product surface에 포함되지 않는다.
- web viewer gate decision: `docs/reports/Research_DNA_Web_Viewer_Gate_2026-03-28.md`

이 문서의 목표는 세 가지다.
- `ResearchDNA`와 현재 실행용 `Profile`의 canonical boundary를 고정한다.
- v1 범위를 `DRAFT -> PILOT -> LOCKED` + pilot refine loop로 축소한다.
- 이후 구현이 들어가더라도 append-only audit와 fixed search evaluation contract를 먼저 지키게 만든다.

현재 이 문서와 연결된 실증 예시는 historical first probe였던 `MCI + medium-chain triglycerides`를 많이 사용한다.
이 예시는 schema와 refine loop를 검증하기 위한 bounded pilot asset이지, 제품의 기본 domain scope나 권장 query default를 뜻하지 않는다.
동일한 `Research DNA` contract는 oncology, immunology, cell biology, translational medicine, biomaterials-adjacent biomedical topics에도 그대로 적용된다.

## Current Status
2026-03-13 기준 현재 상태는 아래와 같다.

구현됨:
- `src/profiles/research_dna_schema.py`
- `src/profiles/research_dna_store.py`
- `src/profiles/research_dna_service.py`
  - `create_research_dna()`
  - `log_interview_response()`
  - `approve_pilot()`
  - `run_pilot()`
  - `load_research_dna_run_index()`
  - `load_screening_queue_artifact()`
  - `load_next_screening_candidate()`
  - `load_screening_session()`
  - `load_screening_progress_report()`
  - `load_screening_recommendation()`
  - `submit_screening_decision()`
  - `submit_screening_decision_and_load_next_candidate()`
  - `refine_query_version()`
  - `lock_research_dna()`
  - `unlock_research_dna()`
- `backend/main.py`
  - thin FastAPI wrappers for create/get/update/interview/approve-pilot/pilot/run-index/resume/rerank/guidance materialization/screening-queue/next-screening-candidate/screening-session/screening-progress/screening-guidance/screening-recommendation/rerank-gate/screening/screening-advance/screening-current/refine/lock/unlock/project-profile
- `src/cli.py`
  - thin CLI wrappers under `paperpipe research-dna ...`
  - interview logging command under `paperpipe research-dna interview`
  - reranked screening sidecar command under `paperpipe research-dna rerank`
  - run index command under `paperpipe research-dna runs`
    - returns a bounded run list for the current `Research DNA`, ordered newest-first
    - merges append-only `runs.jsonl` with the latest run-local `manifest.json` / `metrics.json` sidecars so screening counts stay resume-friendly after screening has started
  - resume snapshot command under `paperpipe research-dna resume`
    - returns a bounded latest-run snapshot so operators can re-enter the current screening workflow without manually copying a `run_id`
    - packages the latest run summary plus the existing session/progress/recommendation/gate reads into one additive response
    - returns `has_runs=false` with null run/session fields when the `Research DNA` has not been piloted yet
  - screening guidance snapshot command under `paperpipe research-dna materialize-guidance`
    - writes a run-local timestamped `screening_guidance_<timestamp>.json` audit snapshot without changing queue ownership
    - manifest/metrics keep a pointer to the latest snapshot, while older snapshots remain in the run directory
    - materialization also maintains `screening_guidance_index.json` so the run keeps a simple bounded history list of guidance snapshots
  - screening guidance artifact command under `paperpipe research-dna guidance-artifact`
    - returns the latest materialized guidance snapshot pointed to by the run manifest without rematerializing a new snapshot
  - screening recommendation command under `paperpipe research-dna recommend`
    - returns an advisory-only `original | reranked` recommendation without changing queue ownership
    - includes stable `primary_reason_code` plus `recommendation_summary` for operator-facing explanation without client-side code mapping
    - includes additive quantitative signal fields such as changed-position ratio and top-score margin for bounded read-side inspection
  - screening guidance command under `paperpipe research-dna guidance`
    - returns the current recommendation and rerank gate together as one bounded operator read
  - screening guidance history command under `paperpipe research-dna guidance-history`
    - returns a bounded read of `screening_guidance_index.json` so operators can inspect recent guidance snapshots without opening files manually
  - rerank gate command under `paperpipe research-dna rerank-gate`
    - returns a bounded `eligible | not_eligible | insufficient_signal` judgment for whether the current rerank result is strong enough to even consider stronger operator-default treatment later
    - includes stable `primary_reason_code` / `primary_warning_code` plus `gate_summary` for operator-facing explanation without changing default ownership
    - includes the same additive quantitative signal fields so operators can inspect heuristic strength without changing queue ownership
  - queue inspection command under `paperpipe research-dna queue`
  - next-candidate operator command under `paperpipe research-dna next`
  - screening-session snapshot command under `paperpipe research-dna session`
    - now also returns the current advisory screening recommendation and rerank gate so operators do not need extra read calls
    - recent decisions now carry additive screening-telemetry fields such as selected variant, recommended variant, gate status, and whether the operator followed the pre-write guidance
    - now also returns a small run-local `guidance_follow_summary` aggregate so operators can inspect adherence/divergence counts without counting recent decisions by hand
  - screening-progress report command under `paperpipe research-dna progress`
    - returns a bounded run-local summary that packages current counts, active next candidate, top reason codes, guidance-follow summary, and manifest/metrics/guidance artifact paths in one read
    - stays read-only and derived from the current queue/session/guidance state plus run-local `manifest.json` and `metrics.json`
  - screening-advance operator command under `paperpipe research-dna screen-next`
    - returns the updated next-candidate payload plus a bounded session snapshot after the write
    - now also returns the current advisory screening recommendation and rerank gate so operators do not need extra read calls
    - now also backfills run-local `metrics.json` and `manifest.json` screening-progress summaries so operator progress remains inspectable outside the live session read
    - accepts either an explicit `--run-id` or opt-in `--latest` so the operator can advance the newest run without manually copying the `run_id`
  - current-next screening shortcut under `paperpipe research-dna screen-current`
    - screens the current next candidate on the chosen queue variant and returns the refreshed session snapshot
    - now also returns the current advisory screening recommendation and rerank gate so operators do not need extra read calls
    - accepts either an explicit `--run-id` or opt-in `--latest` so the operator can act on the newest run without manually copying the `run_id`
  - projection materialization command under `paperpipe research-dna project-profile`
- `src/services/runtime_paths.py`
  - `research_dna_root()`
  - `search_eval_root()`
  - `profiles_config_path()`
- `src/profiles/research_dna_projection.py`
  - `build_projected_profile()`
  - `sync_research_dna_profile()`
  - deterministic projected profile ID: `research_dna_<dna_id>`
  - projected profiles are compatibility snapshots only:
    - `enabled=false`
    - `schedule=manual`
  - exact selected per-db query and DNA provenance are written to `Profile.notes`
- `src/profiles/profile_store.py`
  - `save_profiles_snapshot()`
  - `rewrite_profiles_config()`
  - `upsert_profile()`
  - operator-facing `profiles.yaml` writes now use lock + merge-safe update semantics
  - same-profile writes on operator-facing paths now use per-profile revision conflict checks
  - raw `save_profiles_snapshot()` overwrite is blocked on the operator-facing profiles path unless an explicit unsafe fixture/snapshot escape hatch is used
  - generic `rewrite_profiles_config()` bulk rewrites are also blocked on the operator-facing path unless an explicit system-owned opt-in is passed
  - double-check에서 잡힌 `upsert_profile()` operator-path regression도 수정되어 single-profile write path는 계속 허용된다
- real profile projection validation executed
  - [Research_DNA_Real_Profile_Projection_Validation_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Real_Profile_Projection_Validation_2026-03-13.md)
  - actual probe DNA was projected into `config/profiles.yaml`
  - sequential reruns confirmed idempotent upsert with no duplicate profile entry
  - post-hardening validation rerun confirmed the projected profile now carries `revision=1`
- YAML atomic writers hardened after a real parallel temp-path collision surfaced during projection validation
  - `src/profiles/profile_store.py`
  - `src/profiles/research_dna_store.py`
- `scripts/evaluate_search.py`
  - recompute comparable metrics from pilot artifacts + screening logs
  - compute optional goldset recall from `ResearchDNA.pilot.goldset` against the retrieved pilot pool
  - optional baseline diff output
  - optional baseline promotion output
  - append recalculated run snapshots to `runs.jsonl`
  - first-run baseline seed helper when `promote_dir` exists and current baseline is missing
- optimistic revision guard on `profile.yaml` mutations
  - duplicate create blocked
  - stale write rejected as revision conflict
- real PubMed pilot probe executed
  - [Research_DNA_Real_Pilot_Probe_2026-03-12.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Real_Pilot_Probe_2026-03-12.md)
  - v1 `precision_proxy=0.05`
  - v2 `precision_proxy=0.8888888888888888`
  - baseline seed + compare/promotion recorded
 - retrospective provisional goldset sanity follow-up executed
 - [Research_DNA_Goldset_Sanity_Followup_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Goldset_Sanity_Followup_2026-03-13.md)
  - v1 `goldset_recall=0.125`
  - v2 `goldset_recall=1.0`
 - goldset provenance fields added
   - `pilot.goldset_kind`
   - `pilot.goldset_sources`
   - `pilot.goldset_note`
 - external benchmark candidate review recorded
   - [Research_DNA_External_Benchmark_Candidate_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Candidate_2026-03-13.md)
   - strongest candidate path started from `PMC11074881`; broader AD-scope papers were kept out until study-level adjudication completed
 - adjudicated subset manifest captured for the strongest current candidate
   - [pmc11074881_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc11074881_mci_subset_20260313.yaml)
   - current manifest result: `5 include`, `1 exclude (mixed AD/MCI)`
 - external benchmark subset eval executed against the real probe
   - [Research_DNA_External_Benchmark_Subset_Eval_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Subset_Eval_2026-03-13.md)
   - run1 `external_benchmark_recall=0.0`
   - run2 `external_benchmark_recall=1.0`
 - second independent source adjudicated and union manifest recorded
   - [pmc9947355_mci_subset_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/pmc9947355_mci_subset_20260313.yaml)
   - [mci_mct_external_union_20260313.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/benchmarks/mci_mct_external_union_20260313.yaml)
   - union manifest result: `6 include`, `2 exclude`
 - breadth-sensitive union eval executed against the real probe
   - [Research_DNA_External_Benchmark_Breadth_Followup_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Breadth_Followup_2026-03-13.md)
   - run1 `external_benchmark_recall=0.0 (0/6)`
   - run2 `external_benchmark_recall=1.0 (6/6)`
 - bounded external benchmark policy note recorded
   - [Research_DNA_Bounded_External_Benchmark_Policy_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Bounded_External_Benchmark_Policy_2026-03-13.md)
   - the probe satisfied the minimum bar for a `bounded external benchmark candidate`, and explicit operator approval on 2026-03-13 was then used to promote `goldset_kind`
 - explicit external benchmark promotion recorded
   - [Research_DNA_External_Benchmark_Promotion_2026-03-13.md](/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Promotion_2026-03-13.md)
   - `profile revision 2 -> 3`
   - `pilot.goldset_kind retrospective_provisional -> external_benchmark`
   - canonical benchmark set is the adjudicated union include set (`6 studies`)
   - one invalid parallel rerun was discarded; only the sequential rerun is canonical
   - current promoted comparison is `run1 0/6 -> run2 6/6`

아직 active runtime으로 구현되지 않은 항목:
- broader source expansion beyond the initial policy-allowed pilot path
- richer policy dimensions beyond the current `labeled_count + precision_delta + optional goldset_recall_delta` rule

현재 이미 존재하는 compatibility-safe executable lane은 그대로 유지된다.
- `config/profiles.yaml`
- `src/profiles/profile_schema.py`
- `src/profiles/patch_schema.py`
- `src/profiles/patch_apply.py`
- `src/agents/profile_chat_agent.py`

## Current Bounded Scope
현재 bounded scope는 아래로 제한한다.
- standards-backed Search Profile structure
- two-round interview only
  - `Researcher 4`
  - `Librarian 4`
- append-only `query_versions`
- append-only `run_log`
- append-only `approval_audit`
- append-only `screening_log`
- `pilot -> screening -> refine` loop
- `reason_code`-based query refinement
- `recommended_databases`와 `available_databases` 분리
- goldset sanity check는 optional

## Current Non-Goals
다음 항목은 현재 bounded scope 밖에 둔다.
- full PRESS automation
- mandatory grey literature at intake
- external DOI archiving
- OpenAlex-first design
- large frontend wizard or onboarding flow
- chat UI / memory / RAG
- unrestricted external source expansion

## Multi-Angle Boundary Check
이 문서는 아래 리스크를 막는 것을 선행 조건으로 삼는다.

### Architecture
- `ResearchDNA`는 상위 설계 자산이다.
- 현재 `Profile`은 executable projection 또는 compatibility surface다.
- 둘을 같은 수준의 editable canonical로 두지 않는다.
- profile mutation은 optimistic revision guard를 거쳐야 한다.

### Implementation
- 추가 implementation slice가 필요하면 문서/스키마/스토어/서비스 순서로 작게 나눈다.
- CLI/API는 wrapper여야 하며, 로직이 CLI-only가 되면 안 된다.

### Operations
- 모든 상태 전이와 refine 수락은 append-only log를 남긴다.
- `LOCKED` 전이는 actor attribution 없이 허용하지 않는다.
- concurrent mutation은 last-write-wins로 두지 않고 revision conflict로 막는다.

### Evaluation
- search eval은 현재 quality eval에 얹어 쓰지 않는다.
- 별도 artifact contract와 comparable metrics를 가진 fixed harness를 사용한다.

### Policy
- source allowlist, network rule, pilot cap은 문서 또는 정책 레이어에 먼저 선언되어야 한다.
- prompt wording만으로 임의 source를 추가할 수 없다.

### Compatibility
- legacy `config/profiles.yaml` 기반 operator flow는 유지한다.
- DNA-managed program은 projection rule이 생기기 전까지 기존 수동 profile과 섞어 편집하지 않는다.

## Canonical Boundary

### `ResearchDNA` owns
아래 필드는 DNA가 소유한다.
- `intent`
- `revision`
- `status`
- `scope`
- `criteria`
- `recommended_databases`
- `available_databases`
- `filters`
- `query_versions`
- `pilot`
- `governance`
- interview / screening / approval history

### `Profile` owns
아래 필드는 현재 executable projection이 소유한다.
- `id`
- `title`
- `enabled`
- `schedule`
- `limits`
- `query`
- `notes`

### Projection rule
- 하나의 DNA version은 최대 하나의 executable profile snapshot을 만든다.
- projection은 deterministic해야 한다.
- DNA-only 필드는 profile로 조용히 누락되면 안 된다.
- DNA-managed program에서 operator가 DNA와 projected profile을 동등한 source of truth처럼 직접 수정하는 것은 금지한다.
- 기존 수동 profile은 explicit migration 전까지 계속 지원한다.
- projected profile ID는 deterministic하게 `research_dna_<dna_id>`를 사용한다.
- projected profile은 v0에서 compatibility snapshot으로만 취급한다.
  - `enabled=false`
  - `schedule=manual`
- exact selected per-db query, selected database, DNA revision, source-of-truth path는 모두 `Profile.notes`에 provenance로 남긴다.
- legacy `profiles` / `audit` CLI는 projected profile을 read-only로 취급해야 한다.
- operator-facing `profiles.yaml` mutation은 raw overwrite가 아니라 lock + update/upsert path를 사용해 unrelated entries를 보존해야 한다.
- same `profile.id` mutation은 operator surface에서 expected revision을 확인하고 conflict를 내야 한다.
- raw `save_profiles_snapshot()`는 operator-facing path에서 기본 금지하고, fixture/bootstrap snapshot 같은 bounded 예외에서만 explicit unsafe flag로 허용한다.
- generic `rewrite_profiles_config()` bulk rewrite도 operator-facing path에서는 기본 금지하고, projection 같은 system-owned flow만 explicit opt-in으로 허용한다.

## Runtime Paths
Research DNA는 하드코딩된 repo-root 경로를 만들지 않는다.

현재 runtime path 원칙:
- path resolution은 `src/services/runtime_paths.py`를 통해 들어간다.
- human-editable DNA asset root의 기본 경로는 `<paperpipe_home>/research_dna/`를 권장한다.
- generated eval artifacts는 `<storage_root>/search_eval/` 아래에 둔다.
- projected executable profile path의 기본 위치는 `<paperpipe_home>/config/profiles.yaml`이며, `PAPERPIPE_PROFILES_PATH`로 override할 수 있다.
- projected profile validation should treat sequential sync as canonical if a concurrent write probe exposed temp-path race behavior.
- legacy `profiles` / `audit` CLI도 동일한 `PAPERPIPE_PROFILES_PATH`를 따라야 한다.

권장 구조:
```text
<paperpipe_home>/research_dna/
  <dna_id>/
    profile.yaml
    versions/
      v1.yaml          # query-only snapshot
      v2.yaml          # query-only snapshot
    benchmarks/
      pmc11074881_mci_subset_20260313.yaml   # optional adjudicated external subset manifest
      mci_mct_external_union_20260313.yaml   # optional approved union benchmark manifest
    logs/
      interview.jsonl
      runs.jsonl
      screening.jsonl
      approval_audit.jsonl
```

Search eval artifact root:
```text
<storage_root>/search_eval/<run_id>/
  manifest.json
  queries.json
  retrieved.jsonl
  screening_queue.jsonl
  metrics.json
  diff.json            # optional
```

## Data Contract
v1 `profile.yaml`은 아래 최소 필드를 가진다.
- `id`
- `revision`
- `title`
- `intent`
  - `explore | systematic_review | update`
- `status`
  - `DRAFT | PILOT | LOCKED`
- `scope`
  - PICO/PECO 또는 concept blocks
- `criteria`
  - `include[]`
  - `exclude[]`
- `recommended_databases[]`
- `available_databases[]`
- `filters`
  - `year`
  - `language`
  - `study_type`
- `query_versions[]`
- `pilot`
  - `n`
  - `goldset_kind`
  - optional `goldset`
  - optional `goldset_sources`
  - optional `goldset_note`
- `governance`
  - `approved_for_pilot_at`
  - `approved_for_pilot_by`
  - `locked_at`
  - `locked_by`
  - `change_policy`

Standards-backed의 의미:
- field shape는 PRESS / PRISMA-S / Cochrane류 검색전략 관리 원칙을 참고한다.
- 그러나 v1은 full PRESS automation을 하지 않는다.

## Interview Contract
인터뷰는 v1에서 두 라운드만 허용한다.

### Round 1: `Researcher 4`
질문 목표는 연구 의도와 개념 경계를 좁히는 것이다.
1. 연구 의도는 무엇인가
   - `explore`, `systematic_review`, `update` 중 무엇인지
2. 핵심 population 또는 condition은 무엇인가
3. intervention/exposure 또는 비교 조건은 무엇인가
4. outcome 또는 꼭 제외해야 할 경계는 무엇인가

### Round 2: `Librarian 4`
질문 목표는 검색식과 source policy를 실행 가능한 수준으로 정제하는 것이다.
1. `recommended_databases` 대비 실제 사용 가능한 `available_databases`는 무엇인가
2. 기본 모드는 `recall` 우선인가 `precision` 우선인가
3. controlled vocabulary와 free-text를 어떻게 함께 쓸 것인가
4. 약어, 동음이의어, broad noise를 막기 위한 blocking rule은 무엇인가

질문 수를 더 늘리는 것은 v1 범위 밖이다.

## State Machine

### `DRAFT`
허용:
- interview 기록
- scope/criteria 초안 작성
- query version `v1` 초안 생성
- source recommendation 작성

제약:
- pilot run 전에는 `approve_pilot` 또는 동등한 승인 기록이 필요하다.
- `LOCKED`로 직접 전이할 수 없다.

### `PILOT`
허용:
- pilot run 실행
- screening queue 생성
- screening label 기록
- reason-code 기반 refine 제안
- query version bump

제약:
- refine 수락은 `approval_audit`에 actor attribution이 있어야 한다.
- pilot 중간 변경도 append-only version/audit 없이 덮어쓰면 안 된다.

### `LOCKED`
허용:
- read-only inspection
- full run 또는 scheduled update의 사전조건으로 사용

제약:
- query/criteria는 원칙적으로 수정 금지
- 변경이 필요하면:
  - 새 major version 또는 새 `dna_id`를 만든다
  - 또는 explicit unlock + audit reason을 남긴다

## Append-Only Logs
v1에서는 log를 둘로 나누지 않고, 아래 네 종류를 canonical로 둔다.
- `interview.jsonl`
- `runs.jsonl`
- `screening.jsonl`
- `approval_audit.jsonl`

`decisions.jsonl` 같은 병렬 log는 v1에서 추가하지 않는다. approval/decision stream은 `approval_audit.jsonl` 하나로 유지한다.

## Revision Guard
`profile.yaml` mutation은 optimistic revision rule을 따른다.

규칙:
- create는 기존 `dna_id`를 덮어쓰지 않는다.
- mutation service는 load 시점 `revision`을 기억하고 save 시 compare-and-swap 한다.
- 현재 revision과 읽은 revision이 다르면 conflict로 실패한다.
- API에서는 이 충돌을 `409`로 돌려준다.

### `interview.jsonl`
필수 필드:
- `ts`
- `dna_id`
- `round`
  - `researcher | librarian`
- `question_id`
- `question`
- `answer`
- `actor_type`
- `actor_id`

### `runs.jsonl`
필수 필드:
- `ts`
- `run_id`
- `dna_id`
- `query_version`
- `status`
  - `started | completed | partial | failed`
- `actor_type`
- `actor_id`
- `sources[]`
- `retrieved_count`
- `deduped_count`
- `dedupe_rate`
- `pilot_n`
- `labeled_count`
- `include_count`
- `exclude_count`
- `unclear_count`
- `precision_proxy`
- optional `goldset_recall`
- optional `goldset_hit_count`
- optional `goldset_total`
- optional `external_benchmark_recall`
- optional `external_benchmark_hit_count`
- optional `external_benchmark_total`
- `top_reason_codes`

### `screening.jsonl`
필수 필드:
- `ts`
- `dna_id`
- `run_id`
- `candidate_id`
- `decision`
  - `include | exclude | unclear`
- `reason_code`
- optional `note`
- `actor_type`
- `actor_id`

### `approval_audit.jsonl`
필수 필드:
- `ts`
- `dna_id`
- `action`
  - `create | update | approve_pilot | refine | lock | unlock | submit_screening | change_goldset_kind | project_profile`
- `actor_type`
  - `human_cli | human_api | system | agent`
- `actor_id`
- `reason`
- optional `before_version`
- optional `after_version`
- optional `run_id`

## Query Versioning
`query_versions`는 append-only다.

규칙:
- 현재 version을 inplace overwrite하지 않는다.
- refine 수락 시 새 version을 추가한다.
- version bump는 최소 아래를 가져야 한다.
  - `version`
  - `mode`
    - `recall | precision`
  - `per_db`
  - `change_summary`
  - `created_at`
  - `created_by`

v1에서 `query_versions`는 `profile.yaml` 안에 보관하되, `versions/vN.yaml` query-only snapshot을 함께 남긴다.

규칙:
- `versions/vN.yaml`은 full mutable state snapshot이 아니다.
- 여기에는 `dna_id`와 해당 `query_version` payload만 deterministic하게 저장한다.
- `pilot`, `governance`, `criteria` 같은 mutable metadata의 audit source는 항상 `profile.yaml` + append-only logs다.

## Screening And Reason Codes
Pilot screening은 `include | exclude | unclear`만 허용한다.

v1 최소 `reason_code` 세트:
- `wrong_population`
- `wrong_intervention_or_exposure`
- `wrong_outcome`
- `wrong_study_type`
- `wrong_domain_or_condition`
- `protocol_editorial_or_review_only`
- `non_human_or_preclinical_only`
- `duplicate`
- `insufficient_metadata`
- `other_noise`

Refinement rule:
- reason code 분포를 요약해 query broadening/narrowing 제안을 만든다.
- refine 수락 시:
  - `query_versions`에 새 version 추가
  - `approval_audit.jsonl`에 이유 기록
  - `runs.jsonl`에서 비교 가능한 메트릭을 남긴다

`runs.jsonl`은 append-only snapshot log로 해석한다.
- 같은 `run_id`에 대해 pilot 실행 시점 snapshot과 evaluate 재계산 snapshot이 둘 다 존재할 수 있다.
- 나중 snapshot이 더 풍부한 screening/metric 상태를 담는다.

## Search Source Policy
v1의 source policy는 문서에 명시된 allowlist에서만 출발한다.

초기 원칙:
- `recommended_databases`는 방법론상 권장 세트다.
- `available_databases`는 실제 현재 환경에서 실행 가능한 세트다.
- 실행은 `available_databases`에서만 한다.
- `recommended_databases`에만 있고 `available_databases`에 없는 source는 audit reason과 함께 남긴다.
- 임의 웹 검색, 임의 크롤링, prompt-only source 추가는 금지한다.

초기 P0 source 예시:
- `pubmed`
- `openalex`는 optional supplemental candidate로만 고려한다

초기 실행 정책:
- network access는 allowlist 기반이어야 한다.
- pilot run은 `N=20..50`, 기본 `30`
- dedupe precedence는 `DOI -> PMID -> title+year`
- source failure나 truncation은 `runs.jsonl` 및 eval artifact에 기록한다.

## Pilot Loop
v1 loop는 아래 순서로 고정한다.
1. `create_dna(topic, intent)`로 `DRAFT` 생성
2. `Researcher 4`와 `Librarian 4` 인터뷰 기록
3. `approve_pilot`
4. `run_pilot`
5. screening queue 생성
6. `submit_screening`
7. `refine_queries`
8. 안정화되면 `lock_dna`

Pilot 기본 규칙:
- `n=30` default
- allowed sources only
- dedupe 후 screening queue 저장
- goldset sanity check는 있으면 계산하고, 없으면 건너뛴다
- goldset이 있으면 `retrieved.jsonl` 기준으로 identifier match recall을 계산한다.
- retrospective goldset이면 recall은 external benchmark가 아니라 bounded sanity metric으로만 해석한다.
- `goldset_kind`는 최소 `none | retrospective_provisional | external_benchmark`로 구분한다.

## Fixed Search Evaluation Contract
Search eval은 current quality eval의 변형이 아니라 별도 contract를 가진다.

최소 artifact 세트:
- `manifest.json`
- `queries.json`
- `retrieved.jsonl`
- `screening_queue.jsonl`
- optional `reranked_screening_queue.jsonl`
- optional `rerank_report.json`
- `metrics.json`
- optional `diff.json`
- optional `baseline_snapshot.json`

최소 메트릭:
- `retrieved_count`
- `deduped_count`
- `dedupe_rate`
- `labeled_count`
- `include_count`
- `exclude_count`
- `unclear_count`
- `precision_proxy`
- optional `goldset_recall`
- optional `goldset_hit_count`
- optional `goldset_total`
- `top_reason_codes`
- `refinement_report`
  - `decision_counts`
  - `decision_shares`
  - `reason_code_counts[]`
  - `refinement_focus_reason_codes[]`

Keep/discard 판단은 이 메트릭과 diff를 기준으로 한다.

현재 구현:
- `scripts/evaluate_search.py`가 `metrics.json`을 재계산한다.
- `pilot.goldset[]`가 있으면 `scripts/evaluate_search.py`가 `retrieved.jsonl`을 기준으로 `goldset_hit_count`, `goldset_total`, `goldset_recall`을 계산한다.
- optional adjudicated external subset manifest가 주어지면 같은 스크립트가 `external_benchmark_hit_count`, `external_benchmark_total`, `external_benchmark_recall`도 계산한다.
- baseline metrics가 주어지면 `diff.json`을 추가로 생성한다.
- `diff.json`은 raw check list 외에도 `decision_summary`를 같이 기록한다.
  - `blocking_checks`
  - `passed_checks`
  - `metrics_snapshot`
  - `refinement_focus_reason_codes`
- baseline compare가 돌면 compare 시점 baseline을 `baseline_snapshot.json`으로 같이 보존한다.
- `promote_dir`만 주어졌을 때 `<promote_dir>/<dna_id>/current.metrics.json`이 있으면 baseline을 자동 사용한다.
- baseline이 없고 `seed_baseline_if_missing=true`면 first-run baseline을 `current/history`로 자동 seed한다.
- 기본 threshold policy:
  - `min_labeled_count`
  - `min_precision_delta`
  - optional `min_goldset_recall_delta`
  - optional `min_external_benchmark_recall_delta`
  - `allow_missing_goldset=true` default
  - `allow_missing_external_benchmark=true` default

Pilot refine reporting rule:
- refine discussion는 free-form impression보다 `metrics.json.refinement_report`를 먼저 본다.
- 특히 `reason_code_counts[]`와 `refinement_focus_reason_codes[]`는 query broadening/narrowing의 1차 근거로 사용한다.
- baseline compare가 있는 경우 keep/discard 근거는 `diff.json.decision_summary`를 기본 summary surface로 사용한다.

External benchmark interpretation rule:
- `external_benchmark_recall`이 계산된다고 해서 자동으로 canonical `external_benchmark` 승격이 일어나지는 않는다.
- 승격 판단은 최소한 `independent sources >= 2`, `adjudicated union include >= 6`, `unresolved mixed includes = 0`, `latest target run external_benchmark_recall = 1.0`을 충족한 뒤 별도 approval로 처리한다.
- 2026-03-13 현재 probe는 이 approval을 실제로 소비했고, `pilot.goldset_kind=external_benchmark`와 adjudicated union benchmark(`6 include`)를 canonical state로 사용한다.
- future `goldset_kind` changes are expected to log as `change_goldset_kind` rather than generic `update`.
- 기본 baseline naming rule:
  - `<promote_dir>/<dna_id>/current.metrics.json`
  - first promotion: `<promote_dir>/<dna_id>/history/<run_id>.metrics.json`
  - repeated promotion for the same `run_id`: `<promote_dir>/<dna_id>/history/<run_id>__<timestamp>.metrics.json`

## Example
아래 v1 예시는 historical bounded probe example이다.
즉, `Research DNA`의 canonical default topic이 아니라 첫 end-to-end pilot에서 사용한 sample asset이다.
실제 운용에서는 같은 schema로 다른 biomedical domains를 동일하게 설계할 수 있다.

권장 예시:
- `mild cognitive impairment + medium-chain triglycerides`

약어 규칙:
- full phrase 우선
- acronym은 alias로만 추가
- 예시의 편의 때문에 broad ambiguous acronym을 기본 query anchor로 쓰지 않는다

예시 `profile.yaml`:
```yaml
id: dna_mci_medium_chain_triglycerides
title: Mild cognitive impairment and medium-chain triglycerides
intent: systematic_review
status: DRAFT
scope:
  population:
    - mild cognitive impairment
  intervention_or_exposure:
    - medium-chain triglycerides
  outcomes:
    - cognition
criteria:
  include:
    - adults with mild cognitive impairment
    - medium-chain triglyceride intervention or exposure
  exclude:
    - animal-only studies
    - non-cognitive outcomes only
recommended_databases:
  - pubmed
  - embase
available_databases:
  - pubmed
filters:
  language:
    - en
  study_type:
    - randomized_controlled_trial
    - cohort
query_versions:
  - version: v1
    mode: recall
    per_db:
      pubmed: "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\" OR \"medium chain triglyceride oil\")"
    change_summary: initial draft from interview
    created_at: "2026-03-11T00:00:00Z"
    created_by: "human_cli:example"
pilot:
  n: 30
  goldset_kind: none
  goldset: []
  goldset_sources: []
  goldset_note: null
governance:
  approved_for_pilot_at: null
  approved_for_pilot_by: null
  locked_at: null
  locked_by: null
  change_policy: "lock after stable pilot precision/noise review"
```

## Minimal API Or Service Hooks
이 문서는 구현 순서를 강제하지 않지만, 코어 로직은 service layer에 있어야 한다.

현재 최소 service operations는 아래와 같다.
1. `create_dna(topic, intent)`
2. `log_interview(dna_id, round, question_id, question, answer)`
3. `update_dna(dna_id, patch)`
4. `run_pilot(dna_id)`
5. `submit_screening(dna_id, labels[])`
6. `refine_queries(dna_id)`
7. `lock_dna(dna_id, reason)`

규칙:
- `LOCKED` 상태에서 casual mutation 금지
- 모든 write path는 append-only audit를 남겨야 함
- CLI/API는 동일 service contract를 재사용해야 함

## Historical Small-PR Sequence
현재 lane이 어떤 순서로 작게 열렸는지 기록으로 남긴다.
1. `docs/RESEARCH_DNA.md`
2. `src/profiles/research_dna_schema.py`
3. `src/profiles/research_dna_store.py`
4. `src/services/runtime_paths.py` extension for `research_dna_root()`
5. service-layer pilot/refinement hooks
6. thin CLI/API wrappers
7. `scripts/evaluate_search.py`

## References
- `docs/archive/Deep_Research_Report5_Fit_Review_2026-03-11.md`
- `docs/archive/Prompt_Review_Integrated_Priority_2026-03-11.md`
- `docs/archive/Prompt_Review_01_Autoresearch_Search_2026-03-11.md`
- `docs/archive/Prompt_Review_05_Research_DNA_2026-03-11.md`
