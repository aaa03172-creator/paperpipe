# Soft Gate 재도입 점검 체크리스트 (2026-03-06)

Status: Historical working checklist  
Date: 2026-03-06  
Owner: Repository maintainers  
Canonical parent: `README.md`

## 0) 목적
- `master` 브랜치에 branch protection 없이도 최소 품질 게이트를 유지한다.
- 실패 커밋 자동 되돌리기 기능은 유지하되, 워크플로 자기 자신이 되돌려지는 사고를 방지한다.

## 1) 최근 사고 요약 (팩트)
- `5e465af`: `soft-gate-master` 워크플로 도입 커밋
- GitHub Actions run `22746554958`에서 `verify-mock`의 `npm ci` 단계 실패
- 실패 원인: `frontend/package.json`과 `frontend/package-lock.json` 불일치
- `auto-revert-on-failure`가 실패를 감지하고 `5e465af`를 즉시 되돌림
- `d0c0ad8`: 봇 자동 리버트 커밋 생성
- 결과: `.github/workflows/soft-gate-master.yml` 삭제됨 (현재 `master` 기준 미존재)

## 2) 원인 분해
### 직접 원인
- 테스트 실행 전 bootstrap 단계(`npm ci`) 실패로 워크플로 전체가 실패 처리됨

### 구조적 원인
- 자동 리버트 조건이 너무 넓어, "테스트 실패"와 "환경/의존성 실패"를 구분하지 못함
- soft-gate 도입 커밋 자체에도 동일 정책이 즉시 적용되어 self-revert 발생

## 3) 재도입 전 사전 체크 (Preflight)
- [ ] `frontend/package-lock.json` 최신 상태 동기화 (`npm install` 후 lockfile 커밋)
- [ ] 로컬에서 아래 명령이 통과하는지 확인
  - [ ] `cd frontend && npm ci`
  - [ ] `cd frontend && npm run e2e:mock`
  - [ ] `cd frontend && npm run e2e:backend`
- [ ] GitHub Actions 권한 확인 (`contents: write`로 push 가능)
- [ ] 리포 기본 브랜치가 `master`인지 재확인
- [ ] 봇 리버트 커밋 패턴(`revert(soft-gate):`) 유지 여부 확인

## 4) 워크플로 가드 조건 (필수 수정안)
재도입 시 아래 조건이 모두 반영되어야 한다.

1. **Self-revert 방지 (도입 커밋 보호)**
- `.github/workflows/soft-gate-master.yml`을 포함한 커밋은 자동 리버트 대상에서 제외

2. **실패 유형 필터링**
- 테스트 자체 실패일 때만 리버트 허용
- `npm ci`, `pip install`, `playwright install` 같은 bootstrap 실패는 리버트 금지

3. **실행 주체 보호**
- `github.actor == 'paperpipe-soft-gate[bot]'` 이면 리버트 금지

4. **HEAD 이동 보호**
- 현재 워크플로의 `TARGET_SHA == origin/master HEAD` 검증 유지

5. **단일 실행 직렬화**
- `concurrency: soft-gate-master` 유지 (`cancel-in-progress: false`)

## 5) 구현 순서 (PR-sized)
1. `frontend` lockfile 정합성 복구 커밋
2. `soft-gate-master.yml` 재도입 + 가드 조건 반영
3. canary 실패 시나리오 커밋 (의도적 테스트 실패)
4. 자동 리버트 동작 확인
5. canary 커밋 제거 및 정상 상태 복귀

## 6) 검증 시나리오 (필수)
### 시나리오 A: 정상 커밋
- 조건: mock/backend E2E 통과
- 기대: 리버트 없음, `master` 유지

### 시나리오 B: 테스트 실패 커밋
- 조건: E2E assertion 실패
- 기대: 해당 커밋 1개만 자동 리버트

### 시나리오 C: 의존성/lockfile 실패 커밋
- 조건: `npm ci` 실패
- 기대: 자동 리버트 **미실행** (운영자가 수동 조치)

### 시나리오 D: 경쟁 푸시 발생
- 조건: 실패 감지 후 HEAD가 다른 커밋으로 이동
- 기대: 리버트 스킵 (`head moved`) 후 종료

## 7) 롤백 기준
아래 중 하나라도 발생하면 soft-gate 재도입을 즉시 중단한다.
- workflow 파일 변경 커밋이 다시 self-revert 됨
- 단일 실패에서 2개 이상 커밋이 연쇄 리버트됨
- 봇 계정 커밋에 대해 재귀 리버트가 발생함

## 8) 운영 메모
- soft-gate는 branch protection의 대체재가 아니라 임시 안전망이다.
- plan 제약이 해소되면 GitHub Ruleset(Required checks)로 전환한다.
- 운영자가 확인할 우선 로그:
  1. `verify-mock` / `verify-backend` 실패 스텝
  2. `auto-revert-on-failure` 실행 조건 매칭 여부
  3. 리버트 push 대상 SHA 일치 여부
