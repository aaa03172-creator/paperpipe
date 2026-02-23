# Blueprint Change Review (2026-02-22)

## Scope Reviewed
- Baseline execution blueprint: `docs/PaperPipe_v3_Pragmatic_Blueprint_2026-02-22.md` (v1)
- Draft update: `docs/drafts/PaperPipe_v3_Pragmatic_Blueprint_v2_2026-02-22.md` (v2 draft)
- Active queue context: `docs/Pending_PR_Queue.md`

## What Changed After Baseline v1
1. Plan granularity changed from `PR-0..PR-4` to `PR-H0..PR-H2`.
2. v2 introduces stricter identity model:
   - `paper_id` policy (`zotero:`, `doi:`, `pdfsha256:`)
   - filesystem-safe `paper_key`
3. v2 adds event-log persistence layer:
   - `runs`, `jobs`, `job_events`, `user_actions`
4. v2 formalizes artifact contracts:
   - `chunks.json` / `claims.json`
   - evidence resolver as mandatory core path

## Compatibility Check (Current Code vs v2 Draft)
- Already compatible (partial):
  - API-first worker path and DB bootstrap/ensure pattern.
  - Fail-safe runtime behavior and idempotent note upsert.
  - `jobs` lifecycle and cancellation/queue hardening tests.
- Already compatible (newly closed):
  - Deterministic `chunk_id` contract (`pXX_cYY`) in indexing path.
  - Evidence grounding resolver + certainty bands applied before claimset persistence.
  - Citation-jump MVP rendering (`[p.X]` + certainty/hold fallback).
  - `run_profile` contract persisted from API -> queue -> worker -> runner.
  - Discover queue path (`seed` expansion + DB status + Obsidian related-works upsert).
  - Stats trigger path (`run_verify` + tag trigger + stats cache contract).
  - Observability rollup (`evidence_grounded_ratio`, `stats_cache_hit`) via API.
  - v2 migration bootstrap start:
    - deterministic `paper_key` column/backfill in `papers`
    - `runs` schema extension + `job_events` / `user_actions` ensure
    - runtime event instrumentation hooks from worker/progress paths
  - `job_events` buffered writer with batch flush hooks in worker lifecycle.
- Newly closed (this update):
  - Runtime artifact writes now use `storage/artifacts/{paper_key}/{run_id}`.
  - Read paths keep compatibility fallback to legacy `storage/artifacts/{paper_id}/{run_id}`.

## Decision Gate (Closed: 2026-02-23)
1. v2 (`PR-H0..H2`)를 기준 실행 프레임으로 승격한다.
2. v1 (`PR-0..PR-4`) 라벨은 이력 추적용으로만 유지한다.
3. 승격은 docs-only로 처리하며, 런타임 정책은 기존 Fail-safe/API-first/Idempotent 원칙을 유지한다.

## Recommended Next Execution Order (Current Safe Path)
1. `PR-H2` 잔여 범위: output contract 분리(`chunks.json`, `claimset.raw/resolved.json`) + 브리지 어댑터.
2. `PR-H0` 잔여 범위: canonical `paper_id` issuance/normalization 유틸 정리.
