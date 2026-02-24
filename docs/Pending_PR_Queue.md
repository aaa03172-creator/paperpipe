# Pending PR Queue

## Recently Completed (Runtime)
- `PR-BE-JobContract-Hardening`
- `PR-BE-Queue-Claim-Atomic`
- `PR-QA-JobRunner-FailurePaths`
- `PR-QA-JobCancel-Transitions`
- `PR-BE-Worker-CancelSync`
- `PR-BE-Queue-Legacy-Recovery`
- `PR-BE-JobRunner-StageSplit`
- `PR-BE-Evidence-Contract-v1`
- `PR-BE-Citation-Jump-MVP`
- `PR-BE-RunProfile-v1`
- `PR-BE-Discover-Queue-v1`
- `PR-BE-Stats-Trigger-v1`
- `PR-BE-Observability-Rollup`
- `PR-BE-V2-Identity-EventLog`
- `PR-BE-EventWriter-Buffered`
- `PR-BE-ArtifactPath-PaperKey`
- `PR-DOC-Blueprint-v2`
- `PR-BE-H2-Output-Contracts`
- `PR-BE-V2-EventLog-Taxonomy-ReplayTyping`
- `PR-BE-JobRunner-StageSplit-v2`
- `PR-BE-H0-LocalPdf-CanonicalIds`
- `PR-BE-H0-NonDb-Fallback-CanonicalIds`
- `PR-BE-H2-Obsidian-Resolved-Bridge`
- `PR-BE-JobRunner-Helper-Split`
- `PR-BE-H2-Obsidian-Artifacts-API`
- `PR-QA-Phase3-Stability-Gate`
- `PR-BE-H0-PaperId-Migration-Audit-Plan`
- `PR-BE-H0-ObsidianIndex-PaperId-Normalize`
- `PR-OPS-Orphan-PaperRef-Cleanup`
- `PR-BE-V2-EventLog-Followups`
- `PR-OPS-Backfill-Outputs`

## PR-QA-PR-Scope-Guard (Completed)
- Title: `chore(ci): enforce docs/code PR scope split guard`
- Priority: Medium
- Purpose: Reduce mixed-scope PRs by default; allow only minimal queue-sync doc file in code PRs.
- Scope:
  - [done] `scripts/check_pr_scope.py` 추가 (base/head diff 또는 explicit files 검사).
  - [done] `src/services/pr_scope_guard.py` 분류/판정 로직 추가.
  - [done] `tests/test_pr_scope_guard.py` 회귀 테스트 추가.
  - [done] `.github/workflows/pr-scope-guard.yml` PR 자동 가드 추가.
  - [done] merged via PR #60 (`22c75c3`).

## PR-QA-Jobs-Restart-Persistence (Completed)
- Title: `test(api): verify jobs status/events survive backend reload`
- Priority: Medium
- Purpose: Add regression guard for the Phase-2 DoD item "server restart preserves job status/logs".
- Scope:
  - [done] backend module reload scenario keeps `/jobs/{id}` status/progress/stage/log_path readable.
  - [done] post-reload `/jobs/{id}/events` still emits `status/log/done` for terminal jobs.
  - [done] merged via PR #58 (`81b3fbe`).

## PR-QA-Papers-API-Contract (Completed)
- Title: `test(api): expand /papers contract regression coverage`
- Priority: Medium
- Purpose: Guard list/detail contract behavior (`pdf_exists`, missing-status signaling, updated_at ordering, list limit).
- Scope:
  - [done] list/detail response keeps `pdf_exists` semantics.
  - [done] missing local pdf path is surfaced as `pdf_status='missing'`.
  - [done] list endpoint ordering (`updated_at DESC`) and `LIMIT 50` verified by regression test.
  - [done] merged via PR #56 (`e42019f`).

## PR-QA-Jobs-SSE-Boundary (Completed)
- Title: `test(api): harden /jobs/{id}/events boundary behavior`
- Priority: Medium
- Purpose: Expand SSE runtime regression guard for cancel/not-found/reconnect terminal scenarios.
- Scope:
  - [done] cancelled job stream emits terminal `done` event.
  - [done] unknown job stream emits `error` event and exits.
  - [done] terminal job stream is replayable across reconnect calls.
  - [done] merged via PR #54 (`ac4e8c8`).

## PR-QA-Jobs-Events-Persistence (Completed)
- Title: `test(api): add jobs events stream + queue persistence regression guards`
- Priority: Medium
- Purpose: Lock API runtime guarantees for `/jobs/{id}/events` terminal delivery and DB-backed queue state persistence across queue instances.
- Scope:
  - [done] `tests/test_jobs_events_persistence.py` 추가.
  - [done] SSE endpoint response includes `status/log/done` events for completed jobs.
  - [done] `JobQueue` state persistence across new queue objects (`queued -> running`) 회귀 확인.
  - [done] merged via PR #52 (`ef56dbb`).

## PR-BE-Downloader-Router-Runtime-Attach (Completed)
- Title: `feat(downloader): runtime-safe provider chain attach + CLI compatibility`
- Priority: High
- Purpose: Make downloader router defaults fully active in runtime while preserving existing CLI smoke command compatibility.
- Scope:
  - [done] default provider chain expanded to `direct_link -> arxiv -> pmc -> unpaywall`.
  - [done] provider HTTP policy defaults now include `arxiv` and `pmc`.
  - [done] compatibility helper `_fetch_oa_link` re-exposed via `src.downloader` for `src/cli.py:test_unpaywall`.
  - [done] downloader regression tests updated/expanded (provider order + compatibility helper).
  - [done] merged via PR #50 (`f874dc7`).

## PR-BE-H0-Canonical-PaperID (Completed)
- Title: `feat(core): canonical paper_id issuance and normalization utilities`
- Priority: Medium
- Purpose: Close remaining `PR-H0` identity gap.
- Scope:
  - [done] `normalize_doi`, canonical `paper_id` issuance helper module(`src/core/ids.py`).
  - [done] Discovery/Zotero/PubMed entrypoints adopt shared helper without schema break.
  - [done] legacy/local PDF 진입점 canonical issuance 확대(`process_local_pdf_legacy`, `create_paper_from_pdf`).
  - [done] non-DB helper/legacy fallback 경로(`obsidian_index`, `llm_provider_tasks`)의 `paper_id` fallback canonical 정렬.
  - [done] 기존 CSV/노트 legacy `Paper_ID` 점검/정규화 도구 추가(`scripts/audit_obsidian_index_ids.py`, `scripts/normalize_obsidian_index_ids.py`).
  - [done] 릴리즈 체크포인트(2026-02-23)에서 운영 vault CSV 재감사 완료: `canonical_ratio=1.0`, `migratable_candidates=0`, normalize dry-run `candidates=0`으로 추가 `--apply` 불필요 결정.
- Merge Gate:
  - Existing records remain readable and untouched.
  - New records follow canonical issuance policy deterministically.

## PR-BE-V2-EventLog-Followups (Completed)
- Title: `chore(event-log): harden taxonomy/replay and ops observability`
- Priority: Medium
- Purpose: Close residual hardening after baseline event-log rollout.
- Merge Gate:
  - [done] Replay/read models for `runs -> jobs -> events` are query-ready for UI/ops (`/runs/{run_id}`, `/runs/{run_id}/timeline`).
  - [done] Error taxonomy mapping is standardized across worker/job_runner failure paths.
  - [done] `pytest -q -k "not docker_sandbox"` + phase3 integration green.

## PR-BE-H2-ReadModel-Expansion (Completed)
- Title: `feat(contracts): expand resolved/chunks read-model across API/UI paths`
- Priority: Medium
- Purpose: Reduce legacy `claimset.json` dependency and make contract-first reads the default.
- Merge Gate:
  - [done] Obsidian sync prefers `claimset.resolved.json` with legacy bridge fallback.
  - [done] Obsidian artifact API added: `GET /obsidian/artifacts?paper_id=...&run_id=...` (resolved/chunks/stats bundle).
  - [done] Remaining runtime consumers(`backend/routers/obsidian.py`, `src/exporter_claimset.py`) contract-first path adopted.
  - [done] Contract-first path regression tests expanded for API endpoints.

## PR-BE-H0-PaperId-Migration-Apply (Completed)
- Title: `chore(ids): apply paper_id canonical migration with fallback-safe mapping`
- Priority: Medium
- Purpose: Move DB `papers.paper_id` from legacy values to canonical IDs using dry-run output.
- Merge Gate:
  - [done] `scripts/apply_paper_id_migration.py` 추가 (default dry-run, `--apply` 시 backup+transaction).
  - [done] `scripts/plan_paper_id_migration.py` 기반 apply 수행(52 mappings) + backup 생성.
  - [done] apply 전후 count/샘플/SQL 검증 문서화 (`docs/PaperId_Migration_Apply_2026-02-23.md`).
  - [done] rollback 리허설(backup vs current copy 검증) 1회 실행.

## PR-OPS-Orphan-PaperRef-Cleanup (Completed)
- Title: `chore(ops): audit and cleanup orphan jobs/runs paper_id references`
- Priority: Medium
- Purpose: 운영 DB에서 `papers` 미존재 `paper_id`를 참조하는 `jobs/runs` test 흔적을 통제한다.
- Merge Gate:
  - [done] audit 스크립트 추가(`scripts/audit_orphan_paper_refs.py`).
  - [done] cleanup 스크립트 추가(`scripts/cleanup_orphan_paper_refs.py`, dry-run default).
  - [done] apply 시 backup + transaction + `orphan_cleanup_log` snapshot 기록.
  - [done] 단위테스트 추가(`tests/test_orphan_paper_refs.py`).

## PR-OPS-Backfill-Outputs (Completed)
- Title: `chore(ops): backfill markdown outputs and seed claimset recovery queue`
- Priority: High
- Purpose: 운영 backlog에서 markdown 누락을 제거하고 claimset 누락을 배치 처리 경로로 전환.
- Merge Gate:
  - [done] `scripts/qa_report.py` direct run 안정화 + claimset 출력 개선.
  - [done] `scripts/backfill_operational_outputs.py` 추가 (dry-run default).
  - [done] markdown 누락 backfill 실행 (`Missing Markdown Files: 52 -> 0`).
  - [done] claimset recovery queue seed(`+10`) 및 실패 원인 확인(`PDF not found`).
  - [done] backfill enqueue guard 강화(`pdf_ready` default required, `--allow-missing-pdf` opt-in).
  - [done] `job_runner` DB pdf_path 우선 탐색 hotfix로 canonical ID 경로 실패 해소.
  - [done] claimset backfill batch 처리(`52 -> 0`, 총 52건 처리 완료).
  - [done] queued drain 완료(`queued: 0`, `running: 0` at checkpoint).
  - [done] 운영 QA 기준 clean 상태(`Missing Markdown Files=0`, `Missing/Invalid ClaimSet=0`).

## PR-OPS-LegacyFailedJobs-Archive (Completed)
- Title: `chore(ops): archive legacy failed jobs after recovery`
- Priority: Medium
- Purpose: pre-fix 실패 이력을 `jobs` 운영 뷰에서 분리하고 보존 테이블로 아카이브.
- Merge Gate:
  - [done] `scripts/archive_legacy_failed_jobs.py` 추가 (dry-run default, backup + apply).
  - [done] 아카이브 테이블 생성(`job_failures_archive`) + 원본 row_json 보존.
  - [done] 운영 DB 적용: `failed 12 -> 0`, archive rows `12`.
  - [done] 회귀 테스트 추가(`tests/test_archive_legacy_failed_jobs.py`).
