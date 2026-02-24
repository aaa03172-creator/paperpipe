# Next Feature Kickoff Checklist (2026-02-19)

Status Update (2026-02-24):
- post-merge runtime/QA batches through PR #54 are merged on `master`.
- remaining hygiene item: keep code/docs PR split stricter (PR #51 had mixed scope).

## 1) Baseline Sync
- [x] 현재 브랜치 확인: `codex/*` 작업 브랜치 정책으로 운영
- [x] `master` 최신 반영 여부 확인: `git fetch origin && git merge --ff-only origin/master` (master에서 1회)
- [x] 작업 트리 오염 여부 확인: `git status --short`

## 2) Post-Merge Guard Recheck
- [x] Worker/JobRunner 체인 스모크
  - `pytest -q tests/test_worker_job_runner_chain.py tests/test_jobs_api_smoke.py`
- [x] v2 호환 회귀
  - `pytest -q tests/test_stats_agent.py tests/test_artifact_bridge.py`

## 3) Feature Start Contract
- [x] API-First 준수 (CLI 전용 로직 금지)
- [x] 입출력 스키마를 `src/schemas/` Pydantic 계약으로 고정
- [x] Obsidian 마크다운 갱신은 섹션 교체(idempotent) 유지
- [x] fail-safe / unknown-allowed / evidence-first 원칙 유지

## 4) Implementation Plan (Small Batches)
- [x] 변경 단위를 1~3 파일 수준으로 분리
- [x] 각 배치마다 테스트 1개 이상 동반
- [x] 런타임 경로 영향 시 `worker -> job_runner` 스모크 재실행

## 5) PR Hygiene
- [ ] 코드 PR과 문서 PR 분리
- [x] PR 본문에 Scope / AC / Test Commands / Artifact Paths 포함
- [x] 비관련 변경 파일 제외 후 스테이징

## 6) Done Criteria
- [x] 핵심 회귀 세트 통과
- [x] 운영 노트 업데이트
  - `/Users/jangseongjin/paperpipe/docs/PostMerge_Operations_Note_2026-02-19.md`
- [x] 다음 작업 인수인계 문구 5줄 이내 작성
