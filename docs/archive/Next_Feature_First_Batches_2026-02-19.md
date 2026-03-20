# Next Feature: First Work Batches (2026-02-19)

Status: Historical working plan  
Date: 2026-02-19  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Status (Updated: 2026-02-20)
- Batch 1 (P0): Completed
- Batch 2 (P1): Completed
- Batch 3 (P1): Completed

## Batch 1 (P0): DeepRead 섹션 Upsert 표준화

### Goal
- DeepRead 결과 반영을 append/skip에서 **replace(upsert)**로 전환.
- 중복 `## 🤖 Agent Deep Read` 헤더가 있어도 최종적으로 1개만 유지.

### Why First
- 현재 `src/cli.py` deepread 경로는 헤더 존재 시 append를 건너뛰는 방식이라 idempotency 요구와 충돌 가능.
- 운영 노트 기준으로 post-merge 안정성 다음 우선순위가 반영 안정성(노트 품질)임.

### Scope (surgical)
- `src/cli.py`
- `src/obsidian.py` (공용 helper 추가 시)
- `tests/` 신규 테스트 1~2개

### AC
- [x] 동일 노트에 deepread 2회 실행 시 섹션 1개만 존재.
- [x] 중복 헤더가 이미 있는 노트도 실행 후 섹션 1개로 정규화.
- [x] 기존 본문(DeepRead 섹션 외)은 변경되지 않음.

### Tests
- `tests/test_cli_deepread_upsert.py`
  - 단일 헤더 교체
  - 다중 헤더 정리 후 1개 유지

---

## Batch 2 (P1): API-First 반영 경로 정리

### Goal
- 노트 반영 로직을 CLI 내부 로직에서 분리해 재사용 가능한 서비스 함수로 이동.
- 백엔드 잡 완료 경로에서도 동일한 반영 함수를 사용할 수 있게 준비.

### Scope (surgical)
- `src/services/deepread_note_writer.py` (신규)
- `src/cli.py` (서비스 함수 호출)
- `backend/services/job_runner.py` (후속 연결 포인트만 추가, 동작 변경 최소화)

### AC
- [x] DeepRead markdown 구성/반영 로직이 단일 함수로 관리됨.
- [x] CLI와 백엔드가 동일 contract를 사용할 수 있는 구조 확보.
- [x] 기존 deepread 출력 포맷 유지.

### Tests
- `tests/test_deepread_note_writer.py`
  - 입력 claim/stats → markdown 생성 포맷 확인
  - upsert 적용 결과 확인

---

## Batch 3 (P1): 회귀 가드 확장 (노트 반영 포함)

### Goal
- 현재 체인 스모크(Worker->JobRunner)에 노트 반영 idempotency 검증을 추가.

### Scope (surgical)
- `tests/test_worker_job_runner_chain.py` 확장 또는 별도 파일 추가
- 필요 시 작은 fixture 추가

### AC
- [x] 체인 실행 후 노트 반영 결과가 중복 없이 유지됨.
- [x] 재실행 시 동일 섹션 교체 동작이 유지됨.

### Tests
- `pytest -q tests/test_worker_job_runner_chain.py tests/test_cli_deepread_upsert.py tests/test_deepread_note_writer.py`

---

## Execution Order
1. Batch 1 완료 + 테스트 통과
2. Batch 2 최소 리팩터 + 테스트 통과
3. Batch 3 회귀 가드 추가 후 스모크 재확인

## Non-goals
- 대규모 리팩터링 금지
- 클라우드 의존 추가 금지
- 기존 agent 추론/통계 로직 변경 금지 (이번 배치 범위 아님)
