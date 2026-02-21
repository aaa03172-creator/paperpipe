# Hold Mode Checklist (2026-02-20)

## Purpose
- Antigravity 작업 완료 전, 코드 충돌 없이 진행할 수 있는 준비 항목만 정리한다.
- 완료 후 즉시 실행할 검증/정리 순서를 고정한다.

## Current Snapshot (Do Not Modify Yet)
- 명령: `git status --short`
- 확인된 항목:
  - `M pyproject.toml`
  - `D tests/full_integration_test.py`
  - `D tests/test_full_pipeline.py`
  - `M tests/test_ingest.py`
  - `D tests/test_watcher_logic.py`
  - `?? storage/feedback_index/`
  - `?? tests/test_feedback_manual.py`

## Hold-Mode Tasks (No Core Code Changes)
- [ ] 상태 스냅샷 보관
  - `git status --short`
  - `git log --oneline -n 10`
- [ ] 다음 작업 범위 고정
  - Top-3 동적 주입 경로는 `accepted=true` only 유지
  - 수동 테스트 파일(`tests/test_feedback_manual.py`)은 자동 회귀 범위에서 제외
- [ ] 임시/로컬 산출물 처리 규칙 합의
  - `storage/feedback_index/`는 커밋 금지
  - 필요 시 `.gitignore` 반영 여부 확인

## Resume Commands (After Antigravity Done)
1. 워킹트리 재확인
   - `git status --short`
2. 핵심 회귀
   - `pytest -q tests/test_feedback_retriever.py tests/test_feedback_api.py tests/test_job_runner_persona.py`
3. 파이프라인 스모크
   - `pytest -q tests/test_worker_job_runner_chain.py tests/test_jobs_api_smoke.py`
4. 범위 외 변경 점검
   - `git diff --name-only`
5. 커밋 직전 스테이징 규칙
   - 기능 관련 파일만 `git add <file...>`로 명시 스테이징
   - `pyproject.toml`/수동 테스트/로컬 산출물은 별도 의도 없으면 제외

## Next Commit Scope (Planned)
- 포함 후보:
  - `src/agents/feedback_retriever.py`
  - `src/config.py` (`feedback_index_path`)
  - `tests/test_feedback_retriever.py`
- 제외 후보:
  - `storage/feedback_index/`
  - `tests/test_feedback_manual.py`
  - `pyproject.toml` (근거 없는 의존성 추가는 보류)
