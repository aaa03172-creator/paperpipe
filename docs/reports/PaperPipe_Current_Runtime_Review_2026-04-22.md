# PaperPipe Current Runtime Review

Status: completed repo-grounded review
Date: 2026-04-22
Lane: `pp`
Source input:
- external review received in chat on 2026-04-22

Canonical parents:
- `README.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`

## Purpose

Rewrite the received review against the current repository implementation.

This note is intentionally code-grounded.
It separates:
- confirmed runtime facts
- actual current risks
- open questions that are still not safe to overstate as defects

It is not a new product plan and it does not replace the canonical docs above.

## Method

This review checked current runtime code and tests first, especially:
- `backend/main.py`
- `backend/services/job_runner.py`
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `src/db_utils.py`
- `src/schemas/agent_artifacts.py`
- `src/downloads_watcher.py`
- `src/skills/storage.py`
- `frontend/src/app/lib/config.ts`
- `tests/test_api_key_auth.py`
- `tests/test_browser_request_audit_api.py`
- `tests/test_jobs_events_persistence.py`
- `tests/test_downloads_watcher.py`
- `.github/workflows/frontend-e2e.yml`
- `.github/workflows/backend-api-smoke.yml`

## A. 한눈에 보는 총평

PaperPipe는 "큐도 없고 운영성도 거의 없는 MVP"보다는, 이미 현재형 로컬 연구 런타임에 더 가깝다.

현재 코드 기준으로 확인되는 강점은 다음과 같다:
- FastAPI-first runtime과 browser `/api/*` boundary가 실제 구현돼 있다.
- Pydantic schema와 paper/job/run/artifact 경계가 실제 코드에 반영돼 있다.
- queue/worker, SSE replay, API auth, request audit, atomic note/artifact writes, Playwright/pytest/CI가 이미 존재한다.
- note/export surface와 canonical structured state를 구분하려는 방향성이 코드와 문서에 모두 반영돼 있다.

다만 운영 준비도가 완전히 높은 것은 아니다.
가장 중요한 실제 리스크는 "구현 부재"보다는:
- worker crash 이후 stale `running` job 회수 전략
- 외부 알림/중앙 관측 surface 부족
- single-node SQLite queue의 확장 한계

즉, 이전 리뷰는 방향성 일부는 맞지만, 현재 구현을 충분히 읽지 않고 스펙의 열린 질문과 실제 결함을 섞은 부분이 있다.

## B. 가장 큰 리스크 5개

### 1. Worker crash 뒤 stale `running` job 회수 경로가 보이지 않음

현재 queue는 `jobs` 테이블 기반이고, `claim_next_job()`가 곧바로 job을 `running`으로 전환한다.
하지만 lease, heartbeat, stale timeout, 자동 reclaim 필드는 현재 스키마에서 확인되지 않는다.

왜 문제인가:
- worker 프로세스가 비정상 종료되면 `running` row가 남을 수 있다.
- `enqueue()`는 같은 `paper_id`의 열린 job을 막기 때문에, 해당 paper가 사실상 잠길 가능성이 있다.

현재 근거:
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `src/db_utils.py`

우선순위:
- `P1`

### 2. 관측 가능성은 로컬 중심이며 외부 알림/중앙 dashboard가 없음

현재는 `execution_runs`, `job_events`, `request_audits`, job JSONL log가 남는다.
즉 "관측 불가"는 아니다.
다만 운영자가 DB/파일 밖에서 이상 상태를 빨리 감지하는 surface는 보이지 않는다.

왜 문제인가:
- local-first personal runtime에는 충분할 수 있어도, 장시간 unattended run이나 alpha share에는 약하다.
- stuck job, 반복 실패, browser abuse, 다운로드 매칭 오류를 사전에 읽기 어렵다.

현재 근거:
- `src/db_utils.py`
- `src/services/event_log.py`
- `tests/test_browser_request_audit_api.py`

우선순위:
- `P2`

### 3. 현재 queue는 존재하지만 single-node SQLite poller에 강하게 묶여 있음

이전 리뷰의 "formal queue 부재"는 과장이다.
현재 queue/worker는 이미 구현돼 있다.
다만 지금 구조는 local single-node personal runtime에는 맞지만, multi-worker or multi-host 확장에는 불리하다.

왜 문제인가:
- 분산 실행, worker lease, durable retries, dead-letter 같은 운영 기능은 아직 직접 구현해야 한다.
- long-running batch가 늘어나면 control plane 부담이 커질 수 있다.

현재 근거:
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `README.md`

우선순위:
- `P2`

### 4. persona compatibility surface가 아직 남아 있어 개념적 복잡성이 있음

`persona_id`, `reasoning_persona`, `profile_id`가 함께 유지된다.
현재 코드는 이것을 의도적으로 compatibility bridge로 다루고 있다.

왜 문제인가:
- 즉시 장애를 만드는 문제는 아니지만, 새 기여자에게는 mental model이 복잡하다.
- 장기적으로는 selection normalization과 compatibility semantics를 계속 이해해야 한다.

현재 근거:
- `src/persona_modes.py`
- `backend/services/job_runner.py`
- `backend/main.py`

우선순위:
- `P3`

### 5. 개인 런타임 친화적이지만 운영/설정 경로가 넓어져 온보딩 비용이 있음

이전 리뷰가 `.venv` 여러 개만 보고 환경 관리가 혼란스럽다고 쓴 것은 약한 근거다.
하지만 README만 봐도 submodule, install, self-test, optional verification env, personal runtime path가 함께 존재해 진입 비용은 낮지 않다.

왜 문제인가:
- 신규 기여자나 미래 운영자는 어느 경로가 current blessed path인지 헷갈릴 수 있다.
- local-first product에는 acceptable할 수 있지만, "쉽다"라고 말할 정도는 아니다.

현재 근거:
- `README.md`
- `docs/README.md`
- `docs/PERSONAL_RUNTIME_INSTALL.md`

우선순위:
- `P3`

## C. 사용자 관점에서 막히는 지점 4개

### 1. 초기 설정은 아직 가볍지 않다

Quick Start는 `git submodule update`, dependency install, `paperpipe self-test`, runtime start까지 요구한다.
개인 연구용 로컬 런타임으로는 이해되지만, 첫 진입 장벽은 분명히 있다.

### 2. `Research DNA`는 일부러 web main route 밖에 있다

이전 리뷰가 이 점을 잡은 것은 맞다.
README도 현재 boundary를 명시한다.
현재는 API/CLI operator lane이다.

### 3. PDF/manual-required/operator review 흐름은 자동화되어도 여전히 운영자 친화성이 완전하진 않다

downloads watcher와 review queue는 구현돼 있지만, 사용자가 왜 어떤 PDF가 unmatched/ambiguous가 되었는지 한눈에 보는 product surface는 아직 제한적이다.

### 4. 문제 발생 시 recovery story가 UI보다 operator knowledge에 더 의존한다

SSE, logs, audits는 존재한다.
하지만 "worker가 죽어서 run이 stuck처럼 보일 때 어떻게 recovery할지"는 코드보다 운영자 숙련에 더 기대는 편이다.

## D. 운영 관점에서 당장 보완해야 할 것 5개

### 1. stale `running` job recovery 규칙 추가

가장 작은 안전한 개선은:
- `claimed_at` 또는 `heartbeat_at` 필드 추가
- stale threshold를 넘긴 `running` job을 진단하거나 회수하는 bounded command 추가
- 자동 회수 전에는 operator-visible warning부터 시작

### 2. `/health/ready` 또는 runtime readiness에 stuck-job/queue-age 신호 추가

현재 readiness surface는 이미 존재한다.
새 시스템을 만들기보다, queue age와 stale running count를 거기에 붙이는 편이 맞다.

### 3. 실패/이상 상태를 요약하는 operator-facing ops report 추가

현재 DB/audit/log는 충분히 쌓인다.
하지만 운영자가 바로 읽을 summary는 더 작게 제공하는 것이 좋다.

### 4. crash recovery runbook 문서화

특히 다음 항목은 문서가 있으면 좋다:
- job이 `running`에 멈춘 경우
- log는 있는데 artifact가 불완전한 경우
- download watcher가 unmatched를 쌓는 경우

### 5. current blessed setup path를 더 강하게 명시

개발자용, personal runtime용, verification용 경로를 구분해도 되지만, README 첫 화면에서는 "기본 경로 하나"를 더 강하게 밀어주는 편이 좋다.

## E. 향후 기능 추가 시 병목이 될 구조적 문제 5개

### 1. SQLite queue는 multi-host control plane으로 바로 확장되기 어렵다

현재 구조는 현재 product boundary에는 적합하다.
하지만 shared runtime이나 heavier batch 운영을 하려면 queue backend decision이 필요해진다.

### 2. single primary operator 가정은 멀티유저 확장의 직접 전제 조건이 아니다

README가 이 경계를 분명히 하고 있으므로 지금은 결함이 아니다.
다만 미래에 team/shared project surface를 추가하려면 auth, ownership, conflict semantics를 다시 설계해야 한다.

### 3. filesystem-local surfaces가 많다

Obsidian vault, local PDFs, downloads watcher, storage roots는 local-first에 잘 맞는다.
반대로 hosted/shared runtime으로 갈수록 경계 재정리가 필요하다.

### 4. compatibility surfaces가 누적되면 repo mental load가 올라간다

`persona_id` 같은 bridge는 지금은 합리적이지만, 많아질수록 새 기능 추가 속도를 깎는다.

### 5. broadening evidence consumers가 늘어날수록 additive locator model 정합성이 중요해진다

현재 `EvidenceSpan`은 additive design이다.
이건 장점이지만, downstream renderer와 QA lane이 늘어나면 어떤 field를 어떤 우선순위로 믿는지 명확한 contract가 더 필요해질 수 있다.

## F. 문서 / 테스트 / 배포 / 관측가능성 측면의 현재 상태와 빈 구멍

### 문서

강점:
- 문서가 많고 현재 posture를 읽는 경로도 README에 적혀 있다.

구멍:
- 문서가 "부족"하기보다 "넓고 분산"되어 있다.
- 초심자는 무엇이 current blessed path인지 읽기 비용이 높다.

### 테스트

강점:
- auth, SSE replay, downloads watcher, API routes, frontend E2E가 실제로 존재한다.

구멍:
- stale running recovery나 worker crash recovery drill은 현재 직접적인 coverage가 잘 보이지 않는다.

### 배포 / CI

강점:
- GitHub Actions smoke/E2E workflow가 존재한다.

구멍:
- README에도 적혀 있듯 default branch는 `main`인데 PR checks는 아직 `master` 기준이다.
- 즉, "CI 부재"는 아니고 "branch strategy / protection posture가 완전히 정리되지 않음"이 더 정확하다.

### 관측가능성

강점:
- request audit, run logs, event logs, readiness surfaces가 있다.

구멍:
- 외부 alerting, consolidated dashboard, stuck-job auto-diagnosis는 약하다.

## G. 이번 주에 바로 할 일 5개

### 1. stale job 진단 스크립트 또는 CLI 추가

가장 작은 결과물:
- `running` job duration
- `log_path` 존재 여부
- `artifact_dir` 생성 여부
- operator recommendation

### 2. runtime readiness에 queue stuck check 추가

새 서비스보다 기존 readiness surface 확장이 더 안전하다.

### 3. worker crash recovery 운영 문서 1장 추가

`docs/reports` 또는 runbook 형식으로:
- 증상
- 확인 명령
- 안전한 회복 절차

### 4. current setup path를 README 상단에서 더 좁게 안내

개인 runtime, 개발 runtime, verification runtime을 짧게 구분하되 기본 경로를 더 선명하게 보여준다.

### 5. stale job 회수 테스트 1개 추가

설계를 크게 바꾸기 전에, 원하는 회수 semantics부터 테스트로 고정하는 편이 좋다.

## H. 이번 분기 안에 정리할 일 5개

### 1. queue lease / reclaim semantics 결정

지금 가장 중요한 구조 결정이다.
즉시 Celery로 가지 않아도 되지만, 최소한 stale recovery contract는 정해야 한다.

### 2. queue backend의 장기 방향 결정

선택지는 대체로 다음 둘 중 하나다:
- 현재 SQLite queue를 personal runtime 최적화 방향으로 다듬기
- future shared runtime을 염두에 둔 broker migration path를 미리 정의하기

### 3. externalized ops surface 추가

개인 runtime 기본은 local log/DB여도 괜찮다.
하지만 alpha share나 장시간 실행을 생각하면 요약형 ops surface는 필요하다.

### 4. compatibility surface 정리 계획 수립

특히 persona/profile selection 쪽은 deprecation 없이 영구 유지하기보다, 장기 정리 경로를 잡는 편이 좋다.

### 5. branch / CI gating posture 통일

`main`과 `master` split은 계속 쌓이면 운영 실수의 원인이 된다.

## I. 지금은 굳이 손대지 않아도 되는 것 3개

### 1. 즉시 Redis/Celery로 갈아타기

현재 문제의 핵심은 "formal queue 이름"이 아니라 stale recovery semantics다.
그 규칙 없이 broker만 바꿔도 운영 복잡성만 늘 수 있다.

### 2. `EvidenceSpan`을 단일 locator 모델로 강제 축소하기

현재 additive design은 오히려 repo 현실과 맞다.
지금 당장 줄이는 것은 손실이 더 클 수 있다.

### 3. `persona_id` compatibility를 즉시 제거하기

현재 bridge는 의도적이다.
지금 바로 제거하는 것보다, migration path를 먼저 정리하는 편이 안전하다.

## J. 확인이 더 필요한 쟁점

### 1. 실제 운영에서 stale job이 얼마나 자주 생기는가

현재 코드는 위험을 시사하지만, 실제 빈도는 별도 확인이 필요하다.

### 2. personal runtime을 넘어서는 운영 시나리오가 가까운가

가까우면 queue/backend/alerts 우선순위가 올라간다.
아니면 current local-first 최적화가 더 중요하다.

### 3. 외부 알림이 정말 필요한가

single operator personal runtime이면 local summary로 충분할 수 있다.

### 4. 현재 실제 병목이 setup인지, run reliability인지, artifact review UX인지

코드만으로는 모두의 상대적 무게를 확정하기 어렵다.

## What The Previous Review Got Right

- local-first, paper-centered, single-operator boundary 평가는 맞다.
- API-first / Pydantic-first / note upsert / provenance emphasis 평가는 대체로 맞다.
- setup complexity, Research DNA web boundary, local runtime 운영성 보완 필요성도 대체로 맞다.

## What The Previous Review Overstated Or Misread

- queue/worker가 없는 것처럼 묘사한 점
- browser secret boundary를 아직 확인 안 된 gap처럼 둔 점
- `EvidenceSpan`이 아직 미결정처럼 서술한 점
- Zotero sync open question을 current runtime defect처럼 서술한 점
- CI/CD, E2E, observability가 거의 없는 것처럼 쓴 점

## Current Repo-Grounded Judgment

PaperPipe는 이미 꽤 많은 current-runtime bones를 갖춘 로컬 연구 런타임이다.

정확한 현재 평가는 다음에 가깝다:
- FastAPI/Pydantic/job-artifact-first
- browser secret boundary implemented
- note/artifact atomic writes implemented
- SSE replay implemented
- downloads watcher and manual-review queue implemented
- pytest/Playwright/GitHub Actions present

따라서 다음 우선순위는:
1. stale running recovery
2. operator-facing ops visibility
3. queue/backend long-term posture

이 순서가 현재 코드와 가장 잘 맞는다.

## Next PR-Sized Actions

### PR 1. Stale running 진단 lane 추가

목표:
- worker crash 이후 stuck처럼 보이는 job을 안전하게 진단할 수 있게 한다.

범위:
- `jobs` / `execution_runs` / `log_path` / `artifact_dir`를 읽어 stale 후보를 요약하는 작은 CLI 또는 ops endpoint 추가
- 출력 필드 예시:
  - `job_id`
  - `paper_id`
  - `run_id`
  - `running_for_seconds`
  - `log_exists`
  - `artifact_dir_exists`
  - `recommended_action`

가드레일:
- 자동 회수는 이 PR에서 하지 않는다
- 먼저 진단-only surface로 시작한다

완료 기준:
- local broken-worker 상황을 사람이 1분 안에 설명할 수 있다

### PR 2. Runtime readiness에 queue health 신호 추가

목표:
- 기존 readiness surface에서 queue 이상 징후를 읽을 수 있게 한다.

범위:
- readiness 또는 ops summary에 다음 신호를 추가
  - open queued count
  - running count
  - oldest queued age
  - stale-running suspected count

가드레일:
- 새로운 별도 dashboard를 만들지 않는다
- 현재 readiness surface를 확장한다

완료 기준:
- "지금 queue가 건강한가"를 health/readiness 응답만 보고 대략 판단할 수 있다

### PR 3. Crash recovery runbook + 테스트 1개 추가

목표:
- stuck running semantics를 문서와 테스트로 고정한다.

범위:
- 운영 문서 1장:
  - 증상
  - 확인 경로
  - 안전한 수동 회복 절차
- 테스트 1개:
  - stale running candidate가 진단 surface에 노출되는지 확인

가드레일:
- 문서가 queue semantics를 새로 발명하지 않게 한다
- 현재 구현을 설명하고, 다음 단계만 좁게 제안한다

완료 기준:
- future PR에서 auto-reclaim을 넣더라도 baseline semantics를 되짚을 기준이 생긴다

현 구현 기준 anchor:
- runbook: `docs/STALE_RUNNING_RECOVERY.md`
- stale candidate coverage: `tests/test_stale_jobs_api.py`
- readiness warning coverage: `tests/test_runtime_readiness_external_roots.py`
- follow-on RFC: `docs/reports/Queue_Lease_Reclaim_RFC_2026-04-22.md`

## Recommended Order

1. PR 1부터 시작한다.
2. PR 2로 readiness에 붙인다.
3. PR 3으로 운영 절차와 테스트를 닫는다.

이 순서가 좋은 이유는:
- 먼저 "보이게" 만들고
- 그다음 "항상 읽히게" 만들고
- 마지막에 "운영 절차와 테스트"로 고정하기 때문이다.
