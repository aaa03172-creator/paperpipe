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
- Missing or conflicting with v2 (not yet adopted):
  - Artifact path still uses `storage/artifacts/{paper_id}/{run_id}` (paper_key path migration pending).

## Decision Gate (Before v2 Adoption)
1. Confirm whether v2 (`PR-H0..H2`) replaces v1 (`PR-0..PR-4`) as SSOT execution order.
2. If yes, run docs-only approval PR first:
   - no runtime code change
   - explicit migration note for open v1 tickets
3. If no, continue v1 order and cherry-pick v2-compatible pieces only.

## Recommended Next Execution Order (Current Safe Path)
1. Keep current refactor line (done): worker/job_runner modular hardening.
2. Migrate artifact storage path from `{paper_id}` to `{paper_key}` with compatibility fallback.
