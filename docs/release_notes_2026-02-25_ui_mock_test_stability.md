# Release Notes - 2026-02-25

## Title
fix(ui,test): stabilize mock-mode flow and local test reliability

## Commits
- b1e486f
- 29d9267
- bd9582d (PR #85 merge commit)

## What Changed
- UI stream reliability improvements:
  - unified SSE endpoint usage to `/jobs/{job_id}/events`
  - fixed mock fallback subscription cleanup to avoid stale interval updates after teardown
  - removed extra `decodeURIComponent` on `paperId` route param to prevent malformed URI crashes
- Mock-mode execution hardening:
  - added `VITE_FORCE_MOCK` support (`1`, `true`, `yes`, `on`)
  - mock E2E now runs with forced mock mode enabled for deterministic behavior
- Test and tooling stability:
  - updated eslint flat config to ignore `.vite` artifacts
  - added encoded `paperId` route regression test (`/workbench/paper%25id`)
  - fixed DB path cleanup leak in API key auth test to prevent cross-test contamination
  - docker sandbox tests now skip when local Docker daemon is unavailable
- Documentation:
  - added frontend README section for forced mock mode usage

## Impact
- Reduced false fallback/noise during UI streaming and safer route handling for encoded IDs.
- Mock E2E behavior is deterministic and less dependent on local backend reachability.
- Local full test runs are more stable across environments with/without Docker daemon.

## Verification
- Frontend:
  - `npm run lint`
  - `npm run build`
  - `npm run e2e:mock`
  - `npm run e2e:backend`
- Repository:
  - `pytest -q` → `254 passed, 5 skipped, 8 warnings`

## Rollback
- Revert commits `b1e486f`, `29d9267`, and `bd9582d` in reverse order if needed.

## Korean Summary
- UI SSE 연결 경로/정리 로직을 보강하고, 인코딩된 `paperId` 라우팅 크래시를 제거했습니다.
- `VITE_FORCE_MOCK`를 도입해 mock E2E를 환경 의존성 없이 안정적으로 실행하도록 했습니다.
- `pytest` 전역 경로 누수와 Docker 의존 테스트를 정리해 로컬 전체 테스트 신뢰도를 높였습니다.
