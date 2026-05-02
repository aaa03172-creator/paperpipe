# External Harness / Discipline Fit Review

Status: Active evaluation note
Date: 2026-04-03
Owner: Runtime/design maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

Reference sources:
- [Anthropic engineering: Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [engineering-discipline README](https://github.com/tmdgusya/engineering-discipline)
- [engineering-discipline clarification skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/clarification/SKILL.md)
- [engineering-discipline plan-crafting skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/plan-crafting/SKILL.md)
- [engineering-discipline run-plan skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/run-plan/SKILL.md)
- [engineering-discipline review-work skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/review-work/SKILL.md)
- [engineering-discipline long-run skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/long-run/SKILL.md)
- [engineering-discipline simplify skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/simplify/SKILL.md)
- [engineering-discipline clean-ai-slop skill](https://raw.githubusercontent.com/tmdgusya/engineering-discipline/main/skills/clean-ai-slop/SKILL.md)

## 1. Current Repo Read

### 현재 repo 핵심 목적

현재 PaperPipe/Lattice는:

- local-first
- paper-centered / paper-first
- job/run/artifact-first
- single-operator-first
- evidence-linked, human-reviewable biomedical research workspace

핵심 제품 약속은 generic agent platform이 아니라:

- paper deep-read
- schema-backed structured state
- reproducible search design (`Research DNA`)
- bounded downstream artifacts (`Meeting Pack`, `Chart Pack`, `Method Comparison`, `Image Evidence`, `Protocol Card`)

현재 truth boundary는 명확하다:

- source data owner: Zotero/PDF
- canonical structured state owner: Lattice runtime
- human-facing mirror/export: Obsidian

### 주요 실행 흐름

현재 실제 deep-read 핵심 흐름은 다음과 같다.

1. `backend/services/job_runner.py`
   - `run_deepread_job()`가 `Ingest -> Index -> Read -> Verify`를 orchestration한다.
2. artifact dir 기록
   - `document_artifact.json`
   - `index_artifact.json`
   - `claimset.json`
   - `claimset.resolved.json`
   - `stats_report.json` when requested
   - `run_meta.json`
   - `bootstrap_meta.json`
3. post-run evaluation / handoff sidecars
   - `reader_eval.json`
   - `stats_fallback_eval.json`
   - `acceptance_contract.json`
   - `quality_gate.json`
   - `context_manifest.json`
4. best-effort note promotion
   - structured state promotion
   - deep-read section upsert
5. repo-level release proof
   - `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
   - targeted smoke/e2e/doc lint commands

이 repo는 이미 “무형의 대화 기억”보다:

- schema
- run metadata
- artifact files
- release gate docs

를 더 신뢰하는 쪽에 가깝다.

### 현재 취약점 3개

1. `사전 계약`은 약하고 `사후 평가`는 상대적으로 강하다.
   - 런타임에는 `acceptance_contract.json`과 `quality_gate.json`이 있지만, repo 작업 자체에는 작은 변경 단위의 명시적 sprint contract가 아직 일관되게 표준화되어 있지 않다.

2. `평가 분리`가 부분적이다.
   - `reader_eval`/`stats_fallback_eval`/`quality_gate`는 존재하지만, 구현자 서술과 분리된 release-style 독립 검토가 모든 변경 흐름의 기본 규칙은 아니다.

3. `장시간 작업 재개용 handoff`가 런타임 artifacts 쪽에 비해 개발 작업 쪽에서는 약하다.
   - `.codex/work/...`는 좋은 시작이지만, 장시간 repo 작업에서 항상 같은 최소 handoff bundle
     (`goal/scope/verify/fail/next`)을 남기는 규칙은 아직 얇다.

## 2. Anthropic Review

### 핵심 주장

이 글의 핵심은 “많은 에이전트를 붙이면 좋아진다”가 아니다.

핵심은:

- 모델이 혼자서 안정적으로 못하는 부분만 하니스로 보완하라
- spec expansion, scoped implementation, independent evaluation을 분리하라
- 각 루프의 성공 조건을 테스트 가능한 계약으로 바꿔라
- 모델이 좋아지면 하니스를 단순화하라

`planner / generator / evaluator`의 목적은 각각 다르다.

- `planner`
  - 짧은 사용자 요청을 high-level spec으로 확장
  - 너무 이른 low-level 설계 확정으로 downstream cascade failure를 막음
- `generator`
  - 작은 sprint 단위 구현
  - spec을 코드와 testable behavior로 번역
- `evaluator`
  - 실제 사용 흐름을 눌러 보며 contract 위반을 잡음
  - “겉보기 그럴듯함”과 “실사용 가능성”을 분리

글에서 sprint contract가 중요한 이유:

- high-level spec과 실제 테스트 가능한 구현 사이의 간극을 메우기 때문
- 구현 전에 “이번 덩어리에서 무엇이 done인가”를 명시하기 때문

context reset / compaction이 중요한 이유:

- 장시간 실행에서 chat memory는 무너지기 쉽기 때문
- reset을 하든 compaction을 하든, 하니스는 그 상태 변화 후에도 계속 살아남아야 하기 때문

structured handoff가 중요한 이유:

- agent 간 인상비평 전달이 아니라 계약/파일/검증 기준 전달이 되어야 하기 때문

evaluator 분리가 중요한 이유:

- generator가 만들어낸 narrative를 evaluator가 그대로 믿으면 bug-catching 성능이 급락하기 때문
- criterion별 hard threshold가 없으면 evaluator가 “괜찮다”고 넘어가 버리기 쉽기 때문

### 가져올 것

#### Keep as-is

- `criterion별 hard fail`
  - 하나라도 핵심 기준을 못 넘으면 fail 처리하는 원칙은 현재 repo와 잘 맞는다.
- `structured file handoff`
  - chat 설명보다 file artifact를 handoff 중심에 두는 원칙은 현재 repo가 이미 따르고 있다.
- `simplest harness first`
  - 하니스를 load-bearing 부분만 남기고 계속 줄여야 한다는 원칙은 현재 repo에 특히 중요하다.

### 수정해서 가져올 것

#### Adapt lightly

- `planner / generator / evaluator`
  - 현재 repo에는 항상 3-agent 체계를 도입할 필요는 없다.
  - 대신 `Current State Read -> Sprint Contract -> Implementation -> Evaluation Report -> Final Verdict`로 번역하는 것이 안전하다.
- `sprint contract`
  - app-builder용 대형 sprint 계약이 아니라, repo 작업용 작은 PR-sized 계약으로 축소해야 한다.
- `context reset / compaction survival`
  - 모델별 context-reset 전략을 들여오기보다, `.codex/work/...`와 artifact files를 재개 기준으로 삼는 것이 맞다.
- `evaluator separation`
  - Playwright MCP 중심 evaluator를 그대로 들여오기보다, surface별로 독립 검토를 선택적으로 적용해야 한다.
  - 예: viewer/UI는 Playwright, deep-read runtime은 artifact/schema/test-based evaluation

### 지금은 보류할 것

#### Not now

- `항상-on 멀티에이전트 하니스`
  - 현재 repo의 주된 병목은 generic full-stack app generation이 아니다.
- `모든 sprint마다 heavy QA loop`
  - viewer-facing 변경 일부에는 맞지만, 모든 backend/docs/runtime change에 일괄 적용할 수준은 아니다.
- `planner가 scope를 공격적으로 확장하는 방식`
  - 현재 repo는 boundary discipline이 더 중요하다.

### 버릴 것

#### Reject

- `repo boundary를 넘어서는 spec expansion`
  - 현재 repo는 project/memory/platform으로 다시 넓어지면 안 된다.
- `모델 특정 행동을 repo 운영 규칙으로 고정`
  - Sonnet/Opus의 당시 context 특성은 참고사항일 뿐, 현재 repo의 SSOT가 되면 안 된다.

## 3. engineering-discipline Review

### 핵심 철학

이 레포의 실제 운영 철학은 “좋은 작업은 좋은 절차를 강제해야 한다”에 가깝다.

핵심 체인은 다음과 같다.

- `clarification`
  - ambiguity를 context brief로 줄인다.
- `plan-crafting`
  - worker가 추가 질문 없이 실행 가능한 plan 문서를 만든다.
- `run-plan`
  - worker-validator 분리로 plan을 실행한다.
- `review-work`
  - plan 문서와 현재 codebase만으로 독립 검증한다.
- `milestone-planning`
  - 큰 작업을 milestone DAG로 분해한다.
- `long-run`
  - checkpoint/recovery/retry policy를 가진 multi-day orchestrator다.
- `simplify`, `clean-ai-slop`
  - 구현 후 품질 정리 pass다.

강한 부분은 분명하다.

- 정보 격리 검증
- 실행 가능한 문서화
- checkpoint / recovery discipline
- post-diff quality pass

### 가져올 것

#### Keep as-is

- `plan은 실행 가능해야 한다`
  - placeholder 없는 plan, scope/verification 명시는 현재 repo에 직접 도움이 된다.
- `독립 검토는 구현자 narrative를 입력으로 받지 않는다`
  - 현재 repo의 release-style review와 잘 맞는다.
- `checkpoint / recovery artifact`
  - 장시간 작업은 상태를 디스크에 남겨야 한다는 원칙은 바로 채택 가치가 있다.

### 수정해서 가져올 것

#### Adapt lightly

- `clarification -> context brief`
  - 애매한 작업에서만 쓰고, 작은 bug/doc/runtime slice에는 강제하지 않는 것이 맞다.
- `worker / validator 분리`
  - 역할 분리는 좋지만, 현재 repo에서 모든 작은 작업마다 강제 subagent pair로 고정할 필요는 없다.
- `simplify / clean-ai-slop`
  - 대형 AI-generated diff나 정리 작업에서만 선택적으로 쓰는 후처리 pass로 두는 것이 좋다.
- `milestone / long-run discipline`
  - full DAG/worktree/5-reviewer 체계가 아니라, `.codex/work/...` + checkpoint-like progress log로 축소해야 한다.

### 지금은 보류할 것

#### Not now

- `5 parallel reviewer milestone-planning`
  - 현재 repo에서 비용 대비 과하다.
- `worktree 기반 병렬 milestone 실행`
  - 현재 환경과 작업 크기를 기준으로 기본값이 되기 어렵다.
- `git commit structure까지 plan에 박아두는 방식`
  - 현재 repo의 안전한 소단위 작업에는 과한 의식이다.
- `모든 검토를 binary PASS/FAIL로만 처리`
  - 현재 repo의 bounded release gate에는 useful하지만, exploratory fitting 문서나 research notes까지 동일 적용하면 경직된다.

### 버릴 것

#### Reject

- `항상 subagent 사용`
  - 현재 Codex/PaperPipe 환경에서 기본 규칙으로 들여오면 과설계다.
- `plugin/skill 체계 자체의 도입`
  - 현재 task의 목적은 외부 repo를 도입하는 것이 아니다.
- `작은 작업에도 동일 프로토콜 강제`
  - 현재 repo는 smallest-safe-patch가 더 중요한 곳이다.

## 4. Unified Lightweight Harness Proposal

현재 repo에 맞는 가장 안전한 경량 운영 구조는 아래다.

이것은 새 runtime이 아니다.
현재 repo에 이미 있는 artifact, working-file, release-gate 관행을 묶는 최소 운영 규칙이다.

### 1. Current State Read

작업 시작 전에 반드시 확인:

- canonical docs
  - `README.md`
  - `docs/Lattice_v3_Master_Spec.md`
  - 필요 시 lane-specific doc
- target code paths
- current verification path
  - smallest relevant smoke/test/build/e2e

출력:

- 현재 구조와 충돌하지 않는 범위
- 이번 작업의 실제 touched surface
- 가장 작은 verification slice

### 2. Sprint Contract

저장 위치:

- 장시간 작업: `.codex/work/<date>_<slug>/plan.md`
- durable evaluation이 필요한 작업: `docs/reports/<dated_note>.md`

필수 필드:

- Goal
- In scope
- Out of scope
- Files likely affected
- Expected artifacts / outputs
- Verification method
- Hard fail conditions

`Hard fail conditions`는 최소한 아래를 포함한다.

- canonical boundary 위반
- verification command 실패
- schema / artifact handoff 누락
- destructive overwrite risk
- review-ready여야 하는 surface에서 readiness 미달

### 3. Implementation

Generator 역할은 “작은 계약을 실제 변경으로 번역하는 것”으로 제한한다.

규칙:

- smallest safe slice부터 구현
- artifact-based progress를 남김
- 기존 run/artifact lineage를 유지
- additive or guarded regeneration 우선

장시간 작업은:

- `progress.md`에 phase change
- `findings.md`에 decision-relevant fact

만 남기면 충분하다.

### 4. Evaluation Report

Evaluator 역할은 구현자의 서술을 검증하는 것이 아니라:

- contract
- 현재 코드/아티팩트
- 실제 verification 결과

만으로 verdict를 내리는 것이다.

저장 형태:

- repo 작업: short evaluation note or review section
- runtime run: existing
  - `reader_eval.json`
  - `stats_fallback_eval.json`
  - `quality_gate.json`
  - `context_manifest.json`

핵심 규칙:

- implementer summary는 참고로만 쓰고 판정 근거로 쓰지 않는다.
- evaluator는 가능하면 target files / artifacts를 다시 연다.
- verdict는 최소 `pass / warn / fail`로 남긴다.

### 5. Final Verdict

release-style independent review는 현재 repo의 launch checklist 방식으로 번역하는 것이 가장 자연스럽다.

즉, 마지막 판단은:

- `pass`
  - scope 달성
  - hard fail 없음
  - verification 통과
  - handoff artifact 충분
- `warn`
  - usable하지만 independent reviewer 관점에서 release note가 필요한 약점이 있음
- `fail`
  - hard fail 충족
  - verification 실패
  - contract drift
  - missing artifact / missing lineage

### Generator / Evaluator 분리

현재 repo에 필요한 것은 “항상 2개 agent”가 아니라:

- 구현 단계와 판정 단계를 분리하는 것
- 판정자가 구현 narrative를 사실상 그대로 받아 적지 않게 하는 것

이다.

### Artifact-based handoff

현재 repo에는 이미 좋은 기반이 있다.

runtime handoff:

- `run_meta.json`
- `bootstrap_meta.json`
- `acceptance_contract.json`
- `quality_gate.json`
- `context_manifest.json`

dev-task handoff는 이것만 추가하면 충분하다.

- `plan.md`
- `findings.md`
- `progress.md`
- short evaluation note

### Release-style independent review

새 검토 체계를 만들기보다 현재 release-gate language를 재사용한다.

- launch-defining change면 `green / yellow / red`
- task-level change면 `pass / warn / fail`

둘 다 independent reviewer가:

- stated contract
- current repo state
- verification rerun

기준으로 판정한다.

## 5. Immediate Application

### 1. `working-files`에 Sprint Contract 필드 추가

- Why now
  - 현재 repo는 장시간 작업용 working-files를 이미 채택했지만, `verify`와 `hard fail`이 suggested shape에 아직 약하다.
- In scope
  - `docs/working-files.md`에 Sprint Contract 최소 필드를 추가
  - `plan.md` suggested shape에 `Files likely affected / Verification method / Hard fail conditions` 추가
- Out of scope
  - 새 상태머신
  - 새 workflow engine
- Files likely affected
  - `docs/working-files.md`
- Verification method
  - `python3 scripts/lint_docs.py`
  - template fields가 existing repo workflow와 모순 없는지 수동 확인
- Hard fail condition
  - working-files가 second SSOT처럼 보이거나 master spec을 대체하기 시작하면 fail

### 2. deep-read handoff에 explicit `hard_fail_conditions` 추가

- Why now
  - 현재 `acceptance_contract.json`과 `quality_gate.json`은 이미 존재한다.
  - 여기에 explicit hard fail을 추가하면 evaluator와 release review가 훨씬 일관돼진다.
- In scope
  - deep-read handoff schema에 hard-fail 목록 추가
  - quality gate generation에서 machine-readable fail reasons 정리
- Out of scope
  - 자동 note promotion 차단
  - 전체 runtime orchestration 교체
- Files likely affected
  - `src/schemas/deepread_handoff.py`
  - `src/services/deepread_handoff_artifacts.py`
  - `tests/test_deepread_handoff_artifacts.py`
  - `tests/test_worker_job_runner_chain.py`
- Verification method
  - `pytest -q tests/test_deepread_handoff_artifacts.py tests/test_worker_job_runner_chain.py`
- Hard fail condition
  - existing artifact readers를 깨는 비호환 schema 변경이 생기면 fail

### 3. PR-sized independent review note template 추가

- Why now
  - 현재 repo는 release checklist는 강하지만, 작은 변경 단위 독립 검토 artifact는 일정하지 않다.
- In scope
  - short review template 추가
  - contract / verify / verdict / residual risk만 담는 최소 양식
- Out of scope
  - engineering-discipline식 full review protocol 도입
  - commit-history police
- Files likely affected
  - `docs/reports/` 아래 template note or `docs/working-files.md`
  - 필요 시 `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`에서 terminology만 재사용
- Verification method
  - `python3 scripts/lint_docs.py`
  - 실제 최근 PR-sized 작업 1건에 시범 적용 가능한지 수동 확인
- Hard fail condition
  - template이 작은 작업의 속도를 해치거나 mandatory bureaucracy처럼 작동하면 fail

## 6. Final Recommendation

### `adopt partially`

이유는 명확하다.

- Anthropic 글에서 가져올 것은 `harness minimalism`, `sprint contract`, `evaluator separation`, `hard thresholds`, `file-based handoff`다.
- engineering-discipline에서 가져올 것은 `executable plan`, `independent review`, `checkpoint/recovery`, `post-pass cleanup discipline`이다.
- 하지만 두 자료 모두의 full protocol을 현재 repo에 그대로 들여오면 과설계가 된다.

현재 repo에 맞는 정답은:

- 더 많은 agent가 아니라
- 더 작은 계약
- 더 명시적인 hard fail
- 더 독립적인 review
- 더 file-backed handoff

이다.

즉:

- Anthropic의 무거운 app-building harness 전체를 도입하지 않는다.
- engineering-discipline의 전체 skill protocol도 도입하지 않는다.
- 현재 repo가 이미 가지고 있는 `artifact handoff + release gate + working files`를 묶어
  “경량 하니스”로만 채택하는 것이 가장 안전하다.

## 7. Double-Check Notes

이 문서를 다시 검토하면서 아래 관점으로 재확인했다.

### 아키텍처 관점

- 기존 repo에는 이미 유사한 Anthropic fit review가 있다:
  - `docs/reports/Harness_Design_Fit_Review_2026-03-27.md`
- 그 문서도 결론이 같다:
  - full harness 도입은 과함
  - bounded workflow에만 handoff/quality-gate를 더하는 것이 안전함
- 따라서 이번 결론은 단독 해석이 아니라 기존 내부 판단과도 정합적이다.

### 운영/복구 관점

- 현재 repo는 “하니스가 없는 상태”가 아니다.
- 실제로는 이미 아래가 존재한다:
  - `jobs / execution_runs / job_events`
  - `run_meta.json`
  - `bootstrap_meta.json`
  - `acceptance_contract.json`
  - `quality_gate.json`
  - `context_manifest.json`
- 따라서 가장 큰 공백은 새 orchestration layer가 아니라:
  - repo 작업의 pre-implementation contract
  - 장시간 작업의 dev-side checkpoint discipline

### 검증 관점

- engineering-discipline의 강한 binary review는 현재 repo에 부분 충돌이 있다.
- 이유:
  - 현재 repo는 lane에 따라 `pass / warn / fail`과 `green / yellow / red`를 함께 사용한다.
  - 또 “smallest relevant verification” 원칙이 중요하다.
- 따라서 engineering-discipline의
  - full test suite 강제
  - commit-structure 검증
  - binary PASS/FAIL only
  는 current default로 채택하면 과하다.

### 개발자 워크플로 관점

- `PR-sized independent review template`는 유용할 수 있지만, 지금 즉시 mandatory default로 두면 bureaucracy가 될 가능성이 있다.
- 즉시 적용 우선순위는 아래처럼 다시 정리하는 편이 더 안전하다.
  1. `docs/working-files.md`에 sprint contract 최소 필드 추가
  2. deep-read handoff에 explicit hard-fail metadata 추가
  3. PR-sized independent review note는 optional pilot로만 시도

### 최종 보정

- 원래 결론인 `adopt partially`는 유지한다.
- 다만 실제 적용 범위는 처음 생각보다 더 좁게 잡는 것이 맞다.
- 가장 안전한 번역은:
  - 새 체계를 “도입”하는 것이 아니라
  - existing artifact/handoff/release-gate discipline을 더 명시적으로 묶는 것

## 8. Applied Follow-up

2026-04-03 follow-up에서 실제로 반영된 항목:

- `docs/working-files.md`
  - smallest sprint-contract fields 추가
- `src/schemas/deepread_handoff.py`
- `src/services/deepread_handoff_artifacts.py`
  - additive `hard_fail_conditions` / `hard_fail_codes` 추가
- `docs/INDEPENDENT_REVIEW_TEMPLATE.md`
  - optional PR-sized independent review template 추가
- `docs/PaperPipe_Minimum_Operating_Principles.md`
  - lightweight contracts / additive review artifacts 원칙을 canonical operating note로 승격
- `docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md`
  - compatibility stub로 유지

Follow-up review record:

- `docs/reports/Lightweight_Contracts_Followup_Review_2026-04-03.md`
