# Orphan Paper Ref Cleanup (2026-02-23)

## 목적
- `papers`에 없는 `paper_id`를 참조하는 `jobs/runs/...` 레코드를 운영적으로 통제한다.
- 기본 정책은 안전 우선:
  - dry-run 기본
  - apply 시 DB backup + transaction + 삭제 전 snapshot log 보관

## 도구
- Audit: `scripts/audit_orphan_paper_refs.py`
- Cleanup: `scripts/cleanup_orphan_paper_refs.py`
- Core logic: `src/db_orphan_refs.py`

## 기본 정책
- `--mode test_terminal` (default)
  - 대상: `jobs`, `runs`
  - 조건: orphan + test-like paper_id + terminal status(`completed/failed/cancelled/succeeded`)
- `--mode terminal_all`
  - 대상: `jobs`, `runs`
  - 조건: orphan + terminal status

`review_queue` / `user_actions`는 기본 cleanup 대상에서 제외한다.

## 실행 예시
```bash
python3 scripts/audit_orphan_paper_refs.py --db storage/state.db --sample-limit 5
python3 scripts/cleanup_orphan_paper_refs.py --db storage/state.db --mode test_terminal
python3 scripts/cleanup_orphan_paper_refs.py --db storage/state.db --mode test_terminal --apply
```

## 이번 실행 결과(운영 DB)
- Cleanup 전 audit:
  - orphan_total: `93`
  - jobs: `58` (`paper_id=test_paper_001`)
  - runs: `35` (`paper_id=test_paper_001`)
  - review_queue/user_actions: `0`
- Apply:
  - mode: `test_terminal`
  - backup: `storage/state.db.orphan_cleanup.bak.20260223_041302`
  - deleted: `jobs 58`, `runs 35` (total `93`)
- Cleanup 후 audit:
  - orphan_total: `0`
  - jobs/runs/review_queue/user_actions: 모두 `0`
- 검증:
  - `pytest -q -k "not docker_sandbox"` -> `294 passed, 1 skipped, 4 deselected`

## 보존/복구
- Apply 시 backup 생성:
  - 기본: `storage/state.db.orphan_cleanup.bak.<UTC timestamp>`
- 삭제 레코드는 `orphan_cleanup_log`에 JSON snapshot으로 저장된다.

## 재발 방지
- `scripts/test_phase3_integration.py`에서 통합 테스트 실행 전
  `papers`에 `test_paper_001` row를 upsert 하도록 보강했다.
- 목적: integration 실행 결과(`jobs/runs`)가 orphan으로 누적되는 패턴 방지.
