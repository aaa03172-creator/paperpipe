# Release Notes - 2026-02-21

## Title
fix(watcher,qa): harden DOI matching and restore unmatched metrics contract

## Commit
- 1237b90 (pushed to origin/master)

## What Changed
- Added confidence gating for PDF content DOI auto-matching in downloads watcher.
- Reduced open duplicate accumulation risk for `__UNMATCHED__` review queue entries.
- Restored QA metric contract clarity:
  - `unmatched`: DB open review count
  - `unmatched_files`: file count in `_unmatched` directory
- Updated regression tests for watcher and QA counters.

## Impact
- DOI auto-match is more conservative; uncertain matches are routed to review instead of forced linking.
- Any downstream QA consumer that needs file-level unmatched count should use `unmatched_files`.

## Verification
- Targeted tests: `14 passed`
- Full test suite: `143 passed, 7 warnings`

## Rollback
- Revert commit `1237b90` if needed.

## Korean Summary
- Downloads watcher의 DOI 자동 연결을 보수적으로 변경해 오매칭 위험을 줄였습니다.
- `__UNMATCHED__` 리뷰 큐 중복 누적 가능성을 줄였습니다.
- QA 리포트 지표 의미를 분리/복구했습니다.
  - `unmatched`: DB 기준 open 리뷰 건수
  - `unmatched_files`: `_unmatched` 폴더 PDF 개수
