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
  - Output contract split start:
    - `chunks.json`, `claimset.raw.json`, `claimset.resolved.json` written per run
    - legacy `claimset.json` remains for backward compatibility
    - exporter artifact lookup supports resolved-contract bridge
  - Canonical ID helper start:
    - `src/core/ids.py` (`normalize_doi`, `make_paper_id`) 추가
    - Discovery/Zotero/PubMed 신규 입력 경로에서 canonical issuance 적용
  - Replay read-model API start:
    - `GET /runs/{run_id}`
    - `GET /runs/{run_id}/timeline` (runs/jobs/events/user_actions 집계 조회)
  - Event-log taxonomy hardening:
    - worker/job_runner failure paths emit `error_code` + `error_taxonomy_code`
    - `/runs/*` 응답 모델 typed contract(`RunDetailResponse`, `RunTimelineResponse`) 적용
  - job_runner 2차 모듈화:
    - ingest/index/read/verify stage를 `backend/services/job_stages/`로 분리
    - `backend/services/job_runner_stages.py`는 호환 브리지 유지
    - helper 책임을 `backend/services/job_runner_helpers.py`로 분리(기존 monkeypatch 계약 유지)
  - H0 local PDF canonical gap closed:
    - `process_local_pdf_legacy`, `create_paper_from_pdf`가 `make_paper_id`로 결정론적 ID 발급
  - H2 read-model start:
    - Obsidian sync가 `claimset.resolved.json`을 우선 사용하고 legacy `claimset.json`으로 fallback
    - Obsidian artifact bundle API 추가: `GET /obsidian/artifacts`(query: `paper_id`, `run_id`)
  - 운영 안정성 게이트:
    - `scripts/run_phase3_stability_gate.py --runs 3` 결과 `PASS 3/3`
  - H0 migration prep:
    - `scripts/audit_paper_id_policy.py` + `scripts/plan_paper_id_migration.py`로 비파괴(dry-run) 마이그레이션 후보 산출

## Decision Gate (Closed: 2026-02-23)
1. v2 (`PR-H0..H2`)를 기준 실행 프레임으로 승격한다.
2. v1 (`PR-0..PR-4`) 라벨은 이력 추적용으로만 유지한다.
3. 승격은 docs-only로 처리하며, 런타임 정책은 기존 Fail-safe/API-first/Idempotent 원칙을 유지한다.

## Recommended Next Execution Order (Current Safe Path)
1. H0 운영 후속: dry-run 결과 기반 `paper_id` canonical migration apply 실행(스크립트 준비 완료) 및 rollback 리허설.
2. `PR-H2` 유지보수: contract-first read model 확장을 신규 API/화면 추가 시 기본 규칙으로 지속 적용.
