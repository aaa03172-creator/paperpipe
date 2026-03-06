# Soft Gate 재도입 점검 체크리스트 (2026-03-06)

## 목적
- branch protection/ruleset이 없는 환경에서 `master` 최소 품질 게이트를 유지한다.
- 자동 리버트를 유지하되, self-revert 및 bootstrap 오탐 리버트를 방지한다.

## 최근 사고 요약
- `5e465af`: `soft-gate-master` 도입 커밋
- `npm ci` lockfile 불일치로 `verify-mock` 실패
- `auto-revert-on-failure`가 도입 커밋을 즉시 리버트
- `d0c0ad8`: 워크플로 파일 자체가 삭제되는 self-revert 형태 발생

## 재도입 후 검증 결과
- 안정 베이스라인 커밋: `664f2e4`
  - soft-gate run `22747571695`: `success`
  - `verify-mock`/`verify-backend` 통과, `auto-revert-on-failure` 스킵
- canary 드릴 커밋: `49a6b48`
  - soft-gate run `22747654747`: `failure` + auto-revert 실행
  - 리버트 커밋: `80f8443`

## 필수 가드 조건
1. `.github/workflows/soft-gate-master.yml` 변경 커밋은 auto-revert 대상 제외
2. bootstrap 실패(`npm ci`, dependency install, browser install)는 auto-revert 제외
3. 테스트 실패(`e2e:mock`, `e2e:backend`)만 auto-revert 대상
4. `TARGET_SHA == origin/master HEAD` 불일치 시 리버트 스킵
5. `revert(soft-gate):` 접두 커밋 및 봇 액터는 재귀 리버트 제외

## 운영 체크 순서
1. `frontend/package-lock.json` 정합성 확인 (`npm ci` 통과)
2. 로컬 검증
   - `cd frontend && npm run e2e:mock`
   - `cd frontend && npm run e2e:backend`
3. `master` push 후 soft-gate 실행 확인
4. run 결과에서 아래만 우선 확인
   - `verify-mock`/`verify-backend`의 실패 단계
   - `Classify * verification result` 출력값
   - `auto-revert-on-failure` 실행 조건 매칭 여부

## 드릴 정책
- 실제 테스트 파일에 의도적 실패 코드를 상시 두지 않는다.
- canary 드릴은 수동 워크플로(`soft-gate-canary-drill`)로 실행한다.
- master 자동 리버트 검증이 필요할 때만 단발 canary 커밋을 사용하고 즉시 복구한다.

## 중단(롤백) 기준
- workflow 파일 수정 커밋이 다시 self-revert 됨
- 단일 실패에서 2개 이상 커밋 연쇄 리버트 발생
- 봇 커밋에 대한 재귀 리버트 발생
